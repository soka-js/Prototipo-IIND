"""Motor bayesiano en producción (piezas B4 a B8 de docs/MOTOR.md). Python puro: lee `motor.json`.

Para cada ramo que las reglas dejan ofrecer, calcula la probabilidad de que el cliente acepte si ve la
oferta, con su intervalo y con la descomposición de dónde sale:

    P(acepta | ve) = Φ( base del ramo + señal + momento + afinidad + rasgos + cliente )

  base      conversión de la campaña previa del ramo, encogida hacia el promedio de las campañas (B1)
  señal     señal media frente a fuerte: hipótesis del equipo (× 0,6), con su duda
  momento   el evento que dispara el ramo pasó hace 30 días o menos: efecto estimado con las compras
            externas de la base (modelo autocontrolado, B2)
  afinidad  parecido con quien ya tiene el seguro (M1); pesa 0 mientras M1 no le gane al azar
  rasgos    perfil, movimientos, canales, bolsillos, seguros y uso de la app (B3): empiezan en 0 y solo
            mueven la probabilidad cuando las respuestas reales les dan peso
  cliente   apetito del cliente por seguros: empieza en 0 y aprende de sus respuestas (B8)

Todo en escala probit: Φ es la acumulada de la normal estándar.
"""

from __future__ import annotations

import json
import math
from datetime import date
from functools import lru_cache
from pathlib import Path

from ..core.schema import History
from . import bayes

PATH = Path(__file__).resolve().parent / "motor.json"
Z90 = 1.6448536269514722

# Evento que dispara cada ramo: lo mismo que lee la regla de la señal (core/signals.py). Lo usan el modelo
# del momento al entrenar (B2) y la decisión en producción.
EVENTOS: dict[str, dict] = {
    "SOAT": {"categorias": ("Peajes",), "bolsillos": (), "texto": "un peaje"},
    "Vida": {"categorias": ("Transferencia fija tercero",), "bolsillos": (), "texto": "una transferencia fija a un tercero"},
    "Desempleo": {"categorias": ("Abono recurrente",), "bolsillos": (), "texto": "un abono de nómina"},
    "Hogar": {"categorias": (), "bolsillos": ("Vivienda",), "texto": "un abono al bolsillo de vivienda"},
    "Mascotas": {"categorias": ("Mascotas",), "bolsillos": ("Mascotas",), "texto": "una compra o un abono para la mascota"},
    "Viajes": {"categorias": ("Aerolineas", "Hoteles"), "bolsillos": ("Viajes",), "texto": "una compra de viaje o un abono al bolsillo de viajes"},
}


@lru_cache(maxsize=None)
def spec() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8"))


def eventos(h: History, ramo: str, hasta: date) -> list[date]:
    """Fechas del evento que dispara el ramo, hasta `hasta` inclusive."""
    e = EVENTOS[ramo]
    out = [m.date for m in h.movements if m.category in e["categorias"] and m.date <= hasta]
    out += [d.date for d in h.deposits if d.pocket_type in e["bolsillos"] and d.date <= hasta]
    return sorted(out)


def momento(h: History, ramo: str, as_of: date, ventana: int) -> int | None:
    """Días desde el último evento del ramo si está dentro de la ventana; None si no."""
    ev = eventos(h, ramo, as_of)
    if not ev:
        return None
    dias = (as_of - ev[-1]).days
    return dias if 0 <= dias < ventana else None


# --------------------------------------------------------------------------- creencias
def _previa_por_defecto(sp: dict):
    pv = sp["previas"]

    def f(k: str) -> tuple[float, float]:
        if k.startswith("cliente:"):
            return 0.0, pv["cliente_sd"]
        ramo, _, var = k.partition("|")
        if ramo == "*":
            return 0.0, pv["global_sd"]
        if var in ("base", "senal_media", "momento", "afinidad"):
            m, s = pv[var][ramo]
            return m, s
        return 0.0, pv["ramo_sd"]
    return f


def creencias(sp: dict | None = None) -> bayes.Creencias:
    """Creencias de la población: previas de motor.json más lo aprendido de respuestas (si las hubo)."""
    sp = sp or spec()
    cr = bayes.Creencias(default=_previa_por_defecto(sp))
    for k, (m, s) in sp.get("pesos", {}).items():
        cr.medias[k], cr.varianzas[k] = m, s * s
    for cid, (m, s) in sp.get("clientes", {}).items():
        cr.medias[f"cliente:{cid}"], cr.varianzas[f"cliente:{cid}"] = m, s * s
    return cr


def vector(ramo: str, z: dict[str, float], strength: str, en_momento: bool, afinidad: float, cid: str) -> dict[str, float]:
    """Variables de la oferta (ramo, cliente). Las genéricas entran dos veces: un peso común a todos los ramos
    («*|») y una desviación propia del ramo («ramo|»), así lo que se aprende en un ramo ayuda a los demás."""
    x = {f"{ramo}|base": 1.0}
    if strength == "media":
        x[f"{ramo}|senal_media"] = 1.0
    if en_momento:
        x[f"{ramo}|momento"] = 1.0
    if afinidad:
        x[f"{ramo}|afinidad"] = afinidad
    for g, v in z.items():
        if v:
            x[f"*|{g}"] = v
            x[f"{ramo}|{g}"] = v
    x[f"cliente:{cid}"] = 1.0
    return x


def afinidad_probit(ramo: str, afinidad_cruda: float | None, sp: dict | None = None) -> float:
    """Desplazamiento probit que implica la afinidad de M1: Φ⁻¹(p0·afinidad) − Φ⁻¹(p0)."""
    if not afinidad_cruda or afinidad_cruda <= 0:
        return 0.0
    p0 = (sp or spec())["embudo"]["por_ramo"][ramo]["posterior"]["media"]
    a = min(max(afinidad_cruda, 0.25), 4.0)
    return round(bayes.Phi_inv(min(p0 * a, 0.95)) - bayes.Phi_inv(p0), 6)


def aprender_sesion(cr: bayes.Creencias, cid: str, respuestas: list[tuple[dict[str, float], int]]) -> dict:
    """Actualiza solo el apetito del cliente con sus respuestas de la sesión (aceptó = 1, rechazó = 0).

    Los pesos de la población no se tocan: una persona no cambia lo que el motor sabe de todos. La duda de
    esos pesos sí entra a la actualización (hace que una sola respuesta mueva poco)."""
    k = f"cliente:{cid}"
    m0, v0 = cr.get(k)
    for x, y in respuestas:
        cr.actualizar(x, y, solo={k})
    m1, v1 = cr.get(k)
    return {"respuestas": len(respuestas), "aceptadas": sum(y for _, y in respuestas),
            "previa": [round(m0, 4), round(math.sqrt(v0), 4)], "posterior": [round(m1, 4), round(math.sqrt(v1), 4)]}


# --------------------------------------------------------------------------- puntaje y explicación
def _aprendida(cr: bayes.Creencias, k: str, prev_sd: float, umbral: float = 0.5) -> bool:
    """Un peso cuenta como aprendido cuando las respuestas bajaron su varianza bajo `umbral` × la previa."""
    _, v = cr.get(k)
    return v < umbral * prev_sd * prev_sd


def puntuar(cr: bayes.Creencias, x: dict[str, float], ramo: str, sp: dict | None = None) -> dict:
    """Probabilidad (media de la creencia), intervalo al 90 % y descomposición en factores sobre la base."""
    sp = sp or spec()
    pv = sp["previas"]
    fixed = ("base", "senal_media", "momento", "afinidad")
    contrib = {"base": 0.0, "senal_media": 0.0, "momento": 0.0, "afinidad": 0.0, "rasgos": 0.0, "cliente": 0.0}
    var_known, pend, top = 0.0, 0, []
    for k, xk in x.items():
        mk, vk = cr.get(k)
        c = xk * mk
        if k.startswith("cliente:"):
            # El apetito del cliente entra al intervalo solo cuando ya aprendió algo de sus respuestas:
            # antes, el intervalo describe al cliente promedio con esas señales.
            contrib["cliente"] += c
            if _aprendida(cr, k, pv["cliente_sd"], 0.95):
                var_known += xk * xk * vk
            continue
        r, _, var = k.partition("|")
        if var in fixed:
            contrib[var] += c
            var_known += xk * xk * vk
            continue
        prev_sd = pv["global_sd"] if r == "*" else pv["ramo_sd"]
        if _aprendida(cr, k, prev_sd):
            contrib["rasgos"] += c
            var_known += xk * xk * vk
            top.append((var, c))
        elif r == "*":
            pend += 1
    m = sum(contrib.values())
    s = math.sqrt(var_known)
    p = bayes.Phi(m)
    steps, acc = [], 0.0
    for key in ("base", "senal_media", "momento", "afinidad", "rasgos", "cliente"):
        before = bayes.Phi(acc) if key != "base" else None
        acc += contrib[key]
        if key != "base" and abs(contrib[key]) < 1e-9:
            continue
        after = bayes.Phi(acc)
        steps.append({"k": key, "p": round(after, 5), "factor": round(after / before, 3) if before else None})
    agg: dict[str, float] = {}
    for var, c in top:
        agg[var] = agg.get(var, 0.0) + c
    rasg = [{"variable": v, "label": sp["rasgos"]["etiquetas"].get(v, v), "aporte": round(c, 4)}
            for v, c in sorted(agg.items(), key=lambda t: -abs(t[1]))[:3]]
    return {"p": round(p, 5), "ic90": [round(bayes.Phi(m - Z90 * s), 5), round(bayes.Phi(m + Z90 * s), 5)],
            "z": round(m, 5), "sd": round(s, 5), "pasos": steps, "rasgos_aprendidos": rasg,
            "rasgos_en_espera": pend, "base_ramo": sp["embudo"]["por_ramo"][ramo]["posterior"]["media"]}


def muestra(cr: bayes.Creencias, xs: dict[str, dict[str, float]], semilla: tuple) -> dict[str, float]:
    """Muestreo de Thompson: un solo sorteo de todos los pesos y la probabilidad de cada ramo con ese sorteo."""
    keys = sorted({k for x in xs.values() for k in x})
    w = cr.muestra(keys, bayes.rng(*semilla))
    return {r: round(bayes.Phi(sum(v * w[k] for k, v in x.items())), 5) for r, x in xs.items()}


def alcance(canal: str, push_p: float | None, sp: dict | None = None) -> dict:
    """P(ve la oferta | canal): push con el modelo de apertura del cliente (M3), banner con el alcance de la
    campaña de banner de la base (Campanas_Previas: impactados / elegibles)."""
    sp = sp or spec()
    if canal == "push" and push_p is not None:
        return {"p": push_p, "fuente": "M3: apertura de notificaciones del cliente (Bayes empírico)"}
    b = sp["embudo"]["alcance"].get("banner")
    if b is None:   # datos sin una campaña solo de banner: el alcance promedio de las campañas
        return {"p": round(sp["embudo"]["hiper"]["alcance"]["mu"], 4), "fuente": "Campanas_Previas: alcance promedio"}
    return {"p": round(b["media"], 4), "fuente": b["fuente"]}


def resumen() -> dict:
    """Lo que el panel y el API muestran del motor: piezas, datos que usa y validación."""
    sp = spec()
    lab = None
    lp = PATH.parent / "laboratorio.json"
    if lp.exists():
        lab = json.loads(lp.read_text(encoding="utf-8"))
    return {k: sp[k] for k in ("version", "entrenado_con", "datos", "embudo", "momento", "previas", "validacion")} | {
        "rasgos": {"n": len(sp["rasgos"]["vocabulario"]), "familias": sp["rasgos"]["familias"],
                   "etiquetas": sp["rasgos"]["etiquetas"]},
        "pesos_aprendidos": len(sp.get("pesos", {})), "laboratorio": lab}
