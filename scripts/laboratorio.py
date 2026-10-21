"""Laboratorio con verdad simulada: ¿el motor aprende, mejora frente a la regla y no empeora sin señal?

    python scripts/laboratorio.py            # corre los escenarios y escribe lulo_app/ml/laboratorio.json
    python scripts/laboratorio.py --check    # falla si el JSON no coincide

La base del reto no trae respuestas a ofertas, así que no se puede medir con ella si el motor aprende. Aquí se
inventa una «verdad» conocida sobre los clientes reales de la base (sus señales, su momento y sus rasgos de
verdad), se simulan rondas de ofertas y respuestas, y se compara lo que logra cada política:

  regla            v1.3: conversión previa × comisión × fuerza (no aprende)
  motor            v2.0: la mejor estimación en el 90 % y muestreo de Thompson en el 10 % (aprende cada ronda)
  motor sin explorar  v2.0 sin el 10 % de exploración (para ver lo que aporta explorar)
  oráculo          conoce la verdad: el techo de lo posible
  azar             cualquier oferta permitida: el piso

Escenarios:
  señal            la verdad tiene efectos que la regla no ve (rasgos, momento, señal media más débil)
  regla correcta   la verdad es exactamente la regla v1.3: el motor no debería empeorar
  ruido            como «señal», más 20 variables de puro ruido: el motor no debería confundirse
  oportunidad oculta  como «señal», pero la señal media vende tanto como la fuerte (el motor cree que × 0,6):
                   sin explorar, el motor casi nunca elige una oferta de señal media si hay otra, y tarda en descubrirlo
  dato nuevo       como «señal», más una columna que la base no trae y que sí mueve la aceptación (sobre todo de
                   Vida): el motor la recibe con peso 0, como cualquier variable nueva, y se compara con el mismo
                   motor sin esa columna. Muestra qué gana Lulo al conectar un tipo de dato más.

Cada 5 rondas el motor reestima con Bayes empírico (bayes.ApetitoEB) cuánto se distinguen los clientes entre sí
(τ, la dispersión del apetito) y cambia con eso la previa del apetito de cada uno.

Todas las políticas enfrentan la misma suerte (números aleatorios comunes): si dos políticas le ofrecen lo mismo
al mismo cliente en la misma ronda, reciben la misma respuesta. Nada de esto son resultados de Lulo Bank.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lulo_app.core import experiment, rules  # noqa: E402
from lulo_app.core.catalog import product  # noqa: E402
from lulo_app.core.features import compute  # noqa: E402
from lulo_app.core.schema import RAMOS  # noqa: E402
from lulo_app.core.signals import detect  # noqa: E402
from lulo_app.core.store import store  # noqa: E402
from lulo_app.ml import bayes, motor, rasgos  # noqa: E402
from lulo_app.ml import models as ml  # noqa: E402

OUT = ROOT / "lulo_app" / "ml" / "laboratorio.json"
VERSION = "lab-1.1"
SEED = 19
RONDAS = 40
SD_CLIENTE_VERDAD = 0.20
N_RUIDO = 20
EB_CADA = 5          # cada cuántas rondas el motor reestima la dispersión del apetito (Bayes empírico, v2.1)
POLITICAS = ("regla", "motor", "motor_sin_explorar", "oraculo", "azar")
NOMBRE = {"regla": "Regla v1.3", "motor": "Motor bayesiano v2.0", "motor_sin_explorar": "Motor sin explorar",
          "oraculo": "Oráculo (conoce la verdad)", "azar": "Al azar", "motor_sin_dato": "Motor sin el dato nuevo"}

# Efectos sembrados en la verdad del escenario «señal» (escala probit). La regla no los ve; el motor empieza
# creyendo que valen 0 y tiene que descubrirlos con las respuestas.
SEMBRADOS = {
    "*|uso:apertura": 0.12, "*|uso:sesiones": 0.08, "Desempleo|perfil:credito": 0.30,
    "Viajes|bolsillo:Viajes": 0.30, "Vida|perfil:edad": 0.20, "Mascotas|bolsillo:Mascotas": 0.25,
    "SOAT|mov:Peajes": 0.20, "Hogar|perfil:saldo": 0.15,
}
ESCENARIOS = ("señal", "regla correcta", "ruido", "oportunidad oculta", "dato nuevo")
RAZON_SENAL_VERDAD = {"señal": 0.45, "regla correcta": 0.60, "ruido": 0.45, "oportunidad oculta": 1.0, "dato nuevo": 0.45}
RR_MOMENTO_VERDAD = {"señal": 1.6, "regla correcta": 1.0, "ruido": 1.6, "oportunidad oculta": 1.6, "dato nuevo": 1.6}
FACTOR_BASE: dict[str, dict[str, float]] = {}
# «ruido», «oportunidad oculta» y «dato nuevo» usan la misma suerte que «señal»: solo cambia lo que se describe.
SUERTE = {"señal": "señal", "regla correcta": "regla correcta", "ruido": "señal", "oportunidad oculta": "señal",
          "dato nuevo": "señal"}
# «dato nuevo»: una columna estandarizada que la base no trae (simulada) y su efecto verdadero (escala probit).
DATO_NUEVO = "nuevo:dato"
EFECTO_DATO = {f"*|{DATO_NUEVO}": 0.10, f"Vida|{DATO_NUEVO}": 0.30}


def r(x, n=5):
    return round(float(x), n)


def pc(x: float, signo: bool = True, d: int = 0) -> str:
    """Porcentaje con coma decimal: +10 %, −1,1 %."""
    t = f"{abs(x) * 100:.{d}f}".replace(".", ",") + " %"
    return (("+" if x >= 0 else "−") + t) if signo else t


# ------------------------------------------------------------------ población
def poblacion(sp: dict) -> list[dict]:
    """Clientes de la base con autorización y al menos un ramo ofrecible al corte (señal fuerte o media,
    elegible y sin tenerlo), con lo que el motor sabe de ellos."""
    from lulo_app.core.eligibility import check

    s = store()
    out = []
    for cid in sorted(s.ids("reto")):
        h = s.history(cid)
        if not h.client.consent:
            continue
        f = compute(h, s.cutoff, s.cutoff)
        sig = detect(f)
        held = {e["ramo"] for e in f.external if e["status"] == "vigente"}
        ramos = [ramo for ramo in RAMOS if sig[ramo].actionable and not h.client.holds(ramo) and ramo not in held
                 and check(h.client, product(ramo), f).ok]
        if not ramos:
            continue
        prop = ml.propensity(h, s.cutoff)
        out.append({"cid": cid, "ramos": ramos, "fuerza": {k: sig[k].strength for k in ramos},
                    "z": rasgos.estandarizar(rasgos.crudos(h, s.cutoff, s.cutoff), sp["rasgos"]),
                    "aff": {k: motor.afinidad_probit(k, prop[k]["afinidad_cruda"], sp) for k in ramos},
                    "explora": rules.CONTROL_PCT <= experiment.bucket(cid) < rules.CONTROL_PCT + rules.EXPLORE_PCT})
    return out


def con_variables(sp: dict, pob: list[dict], nombres: list[str], semilla: str) -> dict:
    """Agrega variables al vocabulario (normales estándar, recortadas a ±3) y reparte la duda previa de los rasgos
    entre más variables, como lo haría el entrenamiento si los datos trajeran esas columnas."""
    sp = json.loads(json.dumps(sp))
    g = bayes.rng(semilla, SEED)
    for c in pob:
        for k in nombres:
            c["z"][k] = max(-3.0, min(3.0, g.gauss(0.0, 1.0)))
    d = len(sp["rasgos"]["vocabulario"]) + len(nombres)
    por_var = rules.PRIOR_SD_RASGOS_TOTAL / math.sqrt(d)
    sp["previas"]["global_sd"] = por_var * math.sqrt(rules.PRIOR_FRACCION_COMUN)
    sp["previas"]["ramo_sd"] = por_var * math.sqrt(1 - rules.PRIOR_FRACCION_COMUN)
    return sp


# ------------------------------------------------------------------ verdad
def verdad(esc: str, sp: dict, pob: list[dict]) -> dict:
    """Pesos verdaderos y apetito verdadero de cada cliente para el escenario."""
    pv = sp["previas"]
    w = {}
    for ramo in RAMOS:
        if esc == "regla correcta":
            # La verdad de la regla: la conversión cruda de la campaña (Hogar, la menor) y nada más.
            from lulo_app.core.catalog import products
            p0 = products()[ramo].prior
            b = bayes.Phi_inv(p0)
        else:
            b = pv["base"][ramo][0]
            fac = FACTOR_BASE.get(esc, {}).get(ramo)
            if fac:
                b = bayes.Phi_inv(fac * bayes.Phi(b))
        w[f"{ramo}|base"] = b
        p0 = bayes.Phi(b)
        w[f"{ramo}|senal_media"] = bayes.Phi_inv(RAZON_SENAL_VERDAD[esc] * p0) - b
        w[f"{ramo}|momento"] = bayes.Phi_inv(min(RR_MOMENTO_VERDAD[esc] * p0, 0.95)) - b
    if esc != "regla correcta":
        w.update(SEMBRADOS)
    if esc == "dato nuevo":
        w.update(EFECTO_DATO)
    g = bayes.rng("lab-cliente", SUERTE[esc], SEED)
    u = {c["cid"]: (g.gauss(0.0, SD_CLIENTE_VERDAD) if esc != "regla correcta" else 0.0) for c in pob}
    return {"w": w, "u": u}


def p_verdad(V: dict, x: dict[str, float], cid: str) -> float:
    z = V["u"][cid]
    for k, v in x.items():
        if k.startswith("cliente:"):
            continue
        z += v * V["w"].get(k, 0.0)
    return bayes.Phi(z)


# ------------------------------------------------------------------ simulación
def correr(esc: str, sp: dict, pob: list[dict], sp_sin: dict | None = None) -> dict:
    """Simula las rondas. Con `sp_sin`, agrega la política «motor sin el dato nuevo»: el mismo motor (explora
    igual) con las previas de `sp_sin` y sin ver la columna nueva."""
    V = verdad(esc, sp, pob)
    pols = POLITICAS + (("motor_sin_dato",) if sp_sin else ())
    expo = {k: v["fraccion"] for k, v in sp["momento"]["exposicion"].items()}
    valor = {ramo: product(ramo).commission_12m for ramo in RAMOS}
    regla_p = {ramo: product(ramo).prior for ramo in RAMOS}
    mult = rules.STRENGTH_MULT
    cre = {"motor": motor.creencias(sp), "motor_sin_explorar": motor.creencias(sp)}
    if sp_sin:
        cre["motor_sin_dato"] = motor.creencias(sp_sin)
    ebs = {p: bayes.ApetitoEB() for p in cre}
    tau = {p: sp["previas"]["cliente_sd"] for p in cre}
    serie_tau = []
    g_mom = bayes.rng("lab-momento", SUERTE[esc], SEED)
    g_u = bayes.rng("lab-respuesta", SUERTE[esc], SEED)
    g_az = bayes.rng("lab-azar", SUERTE[esc], SEED)
    serie = {p: {"comision": [], "aceptacion": []} for p in pols}
    por_ramo = {p: {k: 0 for k in RAMOS} for p in pols}
    calib, calib_regla = [], []
    vigilar = [k for k in SEMBRADOS] + ["Vida|senal_media", "Desempleo|senal_media", "SOAT|momento", "Vida|momento"]
    if sp_sin:
        vigilar += list(EFECTO_DATO)
    pesos = {k: [] for k in vigilar}
    ruido_abs = []
    n_resp = []
    total = 0
    for t in range(RONDAS):
        filas = []
        for c in pob:
            mom = {k: g_mom.random() < expo[k] for k in c["ramos"]}
            xs = {k: motor.vector(k, c["z"], c["fuerza"][k], mom[k], c["aff"][k], c["cid"]) for k in c["ramos"]}
            pt = {k: p_verdad(V, xs[k], c["cid"]) for k in c["ramos"]}
            us = {k: g_u.random() for k in c["ramos"]}
            if sp_sin:   # lo que ve el motor sin el dato: el mismo vector sin la columna nueva
                xs = {k: (x, {j: v for j, v in x.items() if not j.endswith(f"|{DATO_NUEVO}")}) for k, x in xs.items()}
            else:
                xs = {k: (x, x) for k, x in xs.items()}
            filas.append((c, xs, pt, us))
        # Calibración: qué tan cerca está la probabilidad del motor de la verdadera, antes de esta ronda.
        err = [abs(bayes.Phi(cre["motor"].lineal(x)[0]) - pt[k]) for c, xs, pt, _ in filas for k, (x, _) in xs.items()]
        errr = [abs(regla_p[k] * mult[c["fuerza"][k]] - pt[k]) for c, xs, pt, _ in filas for k in xs]
        calib.append(r(sum(err) / len(err)))
        calib_regla.append(r(sum(errr) / len(errr)))
        for k in vigilar:
            pesos[k].append(r(cre["motor"].get(k)[0], 4))
        ruido_keys = [f"*|ruido:{i:02d}" for i in range(N_RUIDO)]
        if esc == "ruido":
            ruido_abs.append(r(sum(abs(cre["motor"].get(k)[0]) for k in ruido_keys) / N_RUIDO, 4))
        elegidas = {p: [] for p in pols}
        for c, xx, pt, us in filas:
            xs = {k: x for k, (x, _) in xx.items()}
            ramos = c["ramos"]
            tb = rules.TIEBREAK.index
            elegidas["regla"].append(min(ramos, key=lambda k: (-(regla_p[k] * mult[c["fuerza"][k]] * valor[k]), tb(k))))
            elegidas["oraculo"].append(min(ramos, key=lambda k: (-(pt[k] * valor[k]), tb(k))))
            elegidas["azar"].append(ramos[g_az.randrange(len(ramos))])
            m = cre["motor_sin_explorar"]
            elegidas["motor_sin_explorar"].append(min(ramos, key=lambda k: (-(bayes.Phi(m.lineal(xs[k])[0]) * valor[k]), tb(k))))
            m = cre["motor"]
            if c["explora"]:
                ps = motor.muestra(m, xs, ("lab", SUERTE[esc], t, c["cid"]))
            else:
                ps = {k: bayes.Phi(m.lineal(xs[k])[0]) for k in ramos}
            elegidas["motor"].append(min(ramos, key=lambda k: (-(ps[k] * valor[k]), tb(k))))
            if sp_sin:
                m, xv = cre["motor_sin_dato"], {k: v for k, (_, v) in xx.items()}
                if c["explora"]:
                    ps = motor.muestra(m, xv, ("lab", SUERTE[esc], t, c["cid"]))
                else:
                    ps = {k: bayes.Phi(m.lineal(xv[k])[0]) for k in ramos}
                elegidas["motor_sin_dato"].append(min(ramos, key=lambda k: (-(ps[k] * valor[k]), tb(k))))
        for p in pols:
            com = ac = 0.0
            for (c, xx, pt, us), k in zip(filas, elegidas[p]):
                por_ramo[p][k] += 1
                com += pt[k] * valor[k]
                ac += pt[k]
                if p in cre:
                    x = xx[k][1] if p == "motor_sin_dato" else xx[k][0]
                    y = int(us[k] < pt[k])
                    ebs[p].agregar(c["cid"], *cre[p].sin(x, f"cliente:{c['cid']}"), y)
                    cre[p].actualizar(x, y)
            serie[p]["comision"].append(r(com / len(filas), 1))
            serie[p]["aceptacion"].append(r(ac / len(filas)))
        total += len(filas)
        n_resp.append(total)
        if (t + 1) % EB_CADA == 0 and t + 1 < RONDAS:
            fila = {"ronda": t + 1}
            for p in cre:
                est = ebs[p].estimar()
                nuevo = max(est["tau"], rules.APETITO_TAU_MIN)
                for c in pob:
                    cre[p].cambiar_previa(f"cliente:{c['cid']}", tau[p], nuevo)
                tau[p] = nuevo
                fila[p] = {"tau": est["tau"], "ic95": est["ic95"]}
            serie_tau.append(fila)
    out = resumir(esc, serie, calib, calib_regla, pesos, ruido_abs, n_resp, V, sp, pob)
    out["ofertas_por_ramo"] = por_ramo
    out["apetito"] = {"verdad": 0.0 if esc == "regla correcta" else SD_CLIENTE_VERDAD,
                      "previa": sp["previas"]["cliente_sd"], "estimado": serie_tau}
    return out


def _prom(v: list[float], a: int, b: int) -> float:
    return sum(v[a:b]) / (b - a)


def resumir(esc, serie, calib, calib_regla, pesos, ruido_abs, n_resp, V, sp, pob) -> dict:
    T = RONDAS
    fin = {p: _prom(serie[p]["comision"], T - 10, T) for p in serie}
    ini = {p: serie[p]["comision"][0] for p in serie}
    gana = next((t for t in range(T) if _prom(serie["motor"]["comision"], max(0, t - 2), t + 1)
                 > _prom(serie["regla"]["comision"], max(0, t - 2), t + 1)), None)
    etiquetas = sp["rasgos"]["etiquetas"]

    def label(k):
        ramo, _, var = k.partition("|")
        base = {"senal_media": "señal media", "momento": "momento", DATO_NUEVO: "dato nuevo (simulado)"}.get(var) \
            or etiquetas.get(var, var)
        return f"{'Todos los ramos' if ramo == '*' else ramo} · {base}"

    out = {
        "politicas": {p: {"nombre": NOMBRE[p], **serie[p]} for p in serie},
        "respuestas_acumuladas": n_resp,
        "calibracion": {"motor": calib, "regla": calib_regla},
        "pesos": {k: {"label": label(k), "verdad": r(V["w"].get(k, 0.0), 4), "estimado": v} for k, v in pesos.items()},
        "final": {p: r(v, 1) for p, v in fin.items()}, "inicio": {p: r(v, 1) for p, v in ini.items()},
        "frente_a_regla_final": r(fin["motor"] / fin["regla"] - 1, 4),
        "del_techo_final": r((fin["motor"] - fin["azar"]) / (fin["oraculo"] - fin["azar"]), 4) if fin["oraculo"] > fin["azar"] else None,
        "regla_del_techo": r((fin["regla"] - fin["azar"]) / (fin["oraculo"] - fin["azar"]), 4) if fin["oraculo"] > fin["azar"] else None,
        "ronda_supera_regla": gana + 1 if gana is not None else None,
        "respuestas_para_superar": n_resp[gana] if gana is not None else None,
    }
    if ruido_abs:
        out["ruido_peso_medio"] = ruido_abs
    if "motor_sin_dato" in fin:
        out["valor_del_dato"] = r(fin["motor"] / fin["motor_sin_dato"] - 1, 4)
    print(f"  {esc:15} comisión por oferta (últimas 10 rondas): " + ", ".join(f"{p} {fin[p]:,.0f}" for p in serie)
          + f" · motor frente a regla {out['frente_a_regla_final']:+.1%}"
          + (f" · lo supera desde la ronda {out['ronda_supera_regla']}" if gana is not None else " · no la supera"))
    return out


def build() -> dict:
    sp = motor.spec()
    pob = poblacion(sp)
    print(f"Laboratorio · {len(pob)} clientes de la base con ofertas permitidas · {RONDAS} rondas · semilla {SEED}")
    esc = {}
    for nombre in ESCENARIOS:
        p = [dict(c, z=dict(c["z"])) for c in pob]
        if nombre == "ruido":
            esc[nombre] = correr(nombre, con_variables(sp, p, [f"ruido:{k:02d}" for k in range(N_RUIDO)], "lab-ruido"), p)
        elif nombre == "dato nuevo":
            esc[nombre] = correr(nombre, con_variables(sp, p, [DATO_NUEVO], "lab-dato-nuevo"), p, sp_sin=sp)
        else:
            esc[nombre] = correr(nombre, sp, p)
    a, b, c, o, n = esc["señal"], esc["regla correcta"], esc["ruido"], esc["oportunidad oculta"], esc["dato nuevo"]
    resumen = (f"Con señal que la regla no ve, el motor gana {pc(a['frente_a_regla_final'])} de comisión por oferta "
               f"frente a la regla en las últimas 10 de {RONDAS} rondas y recorre el {pc(a['del_techo_final'], False)} del "
               f"camino entre el azar y el oráculo (la regla, el {pc(a['regla_del_techo'], False)}). Si la regla tenía "
               f"razón, el motor queda a {pc(b['frente_a_regla_final'], True, 1)} de ella. Con 20 variables de ruido, "
               f"{pc(c['frente_a_regla_final'])}. Si la señal media vende más de lo que se creía, el motor logra "
               f"{pc(o['frente_a_regla_final'])} y sin explorar {pc(o['final']['motor_sin_explorar'] / o['final']['regla'] - 1)}. "
               f"Con una columna nueva que sí predice, el motor la aprende sola y gana {pc(n['valor_del_dato'], True, 1)} "
               f"frente al mismo motor sin ese dato.")
    return {"version": VERSION,
            "aviso": "Verdad simulada sobre los clientes de la base: muestra que el método aprende; no son resultados "
                     "ni métricas de Lulo Bank.",
            "config": {"clientes": len(pob), "rondas": RONDAS, "ofertas_por_ronda": len(pob), "semilla": SEED,
                       "motor": sp["version"], "exploran": sum(1 for x in pob if x["explora"]),
                       "efectos_sembrados": SEMBRADOS, "razon_senal_media": RAZON_SENAL_VERDAD,
                       "rr_momento": RR_MOMENTO_VERDAD, "sd_cliente": SD_CLIENTE_VERDAD, "variables_ruido": N_RUIDO,
                       "efecto_dato_nuevo": EFECTO_DATO, "eb_cada": EB_CADA, "tau_min": rules.APETITO_TAU_MIN},
            "escenarios": esc, "resumen": resumen}


def dump(model: dict) -> str:
    return json.dumps(model, ensure_ascii=False, indent=1) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    text = dump(build())
    if a.check:
        cur = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if cur != text:
            print("laboratorio.json no coincide con la simulación actual", file=sys.stderr)
            sys.exit(1)
        print("laboratorio.json coincide con la simulación")
        return
    OUT.write_text(text, encoding="utf-8")
    print(f"Escrito {OUT.relative_to(ROOT)} · sha256 {hashlib.sha256(text.encode()).hexdigest()[:12]}")


if __name__ == "__main__":
    main()
