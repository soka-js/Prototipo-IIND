"""Dashboard de impacto en Power BI y sus datos: la base, lo que decide el motor, un piloto simulado y el laboratorio.

    python scripts/exportar_powerbi.py            # escribe powerbi/ (datos/, tablas/, Lulo_Impacto.pbip, vista previa)
                                                  # y la página /dashboard (lulo_app/templates/dashboard.html)
    python scripts/exportar_powerbi.py --check    # falla si algo de powerbi/ no coincide con lo que se genera hoy

Las tablas de detalle (powerbi/datos) son la fuente: de ellas salen las 10 tablas chicas del dashboard
(scripts/powerbi_modelo.py, powerbi/tablas) y la vista previa (scripts/powerbi_vista.py).

Cuatro tipos de tabla, y cada una dice cuál es (meta.csv y powerbi/GUIA.md):

  base_*     la base del reto tal cual. Es 100 % sintética y académica: sus cifras no son métricas de Lulo Bank.
  motor_*    lo que decide el motor sobre la base: el plan al corte, el backtest y sus invariantes.
  piloto_*   SIMULADO. La base no trae respuestas a ofertas, así que todavía nadie sabe si el motor vende. Aquí se
             repite el año de la base semana a semana con el motor de verdad (el de la app, con su grupo de control,
             su política de contacto y lo que aprende de cada cliente) y solo se inventan las respuestas:
               · si el cliente ve la oferta: con el alcance que el motor le calcula al canal (M3 o el banner)
               · si la acepta: con la verdad del laboratorio (scripts/laboratorio.py), en dos mundos posibles
                 «señal» (el motor ve más que la regla) y «regla correcta» (la regla v1.3 tenía razón)
               · si compra por su cuenta, sin oferta, en los dos grupos: al ritmo con el que estos clientes le
                 compraron seguros a otras aseguradoras en el año de la base (Pagos_Seguros)
             Los sorteos son comunes a los dos mundos: el grupo de control queda idéntico en ambos.
  lab_*      lulo_app/ml/laboratorio.json en tablas.
  casos      casos reales de otras empresas, curados a mano con su fuente (powerbi/casos.csv).

Las tablas piloto_* siguen el formato de docs/DATOS_REALES.md (más columnas que solo existen en la simulación):
el registro del piloto real tendrá esas mismas columnas, y con él se entrena el motor (train_motor.py --respuestas).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import date, timedelta
from fnmatch import fnmatch
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import laboratorio as lab  # noqa: E402
import powerbi_modelo  # noqa: E402
import powerbi_vista  # noqa: E402
import powerbi_web  # noqa: E402
from lulo_app.core import backtest, experiment, rules  # noqa: E402
from lulo_app.core.catalog import DATASET, campaign_ramo, product  # noqa: E402
from lulo_app.core.engine import OUTCOME_LABEL, Context, OfferLog, evaluate  # noqa: E402
from lulo_app.core.features import compute  # noqa: E402
from lulo_app.core.schema import RAMOS  # noqa: E402
from lulo_app.core.signals import detect  # noqa: E402
from lulo_app.core.store import store  # noqa: E402
from lulo_app.ml import bayes, rasgos  # noqa: E402
from lulo_app.ml import models as ml  # noqa: E402
from lulo_app.ml import motor as mot  # noqa: E402

POWERBI = ROOT / "powerbi"
OUT = POWERBI / "datos"
CASOS = ROOT / "powerbi" / "casos.csv"
VERSION = "pbi-1.0"
SEED = 19
PILOTO_DESDE_DIAS = 90      # como el backtest: el motor arranca con tres meses de historia
CADA_DIAS = 7
ETIQUETA = "Prototipo académico · datos simulados"
ESCENARIOS = {
    "señal": ("El motor ve más que la regla",
              "Verdad del escenario «señal» del laboratorio: efectos que la regla no ve (uso de la app, perfil, "
              "bolsillos, peajes), momento × 1,6, señal media × 0,45 y un apetito propio por cliente (desviación 0,20)."),
    "regla correcta": ("La regla tenía razón",
                       "Verdad igual a la regla v1.3: conversión de la campaña previa del ramo × 0,6 si la señal es "
                       "media, sin momento ni apetito propio. Muestra lo que se vería si el motor no tuviera nada "
                       "más que aprender."),
}
# Tramos de P(acepta) del motor: columna tramo_p_motor de piloto_decisiones (lo que predijo frente a lo que pasó).
TRAMOS_P = ((0.06, "menos de 6 %"), (0.08, "6 a 8 %"), (0.10, "8 a 10 %"), (0.13, "10 a 13 %"), (9.0, "13 % o más"))
# Lo que se escribe a mano en powerbi/: la guía y los casos reales con su fuente.
MANUALES = {"GUIA.md", "casos.csv"}
# El mismo dashboard en la web, para el cliente: prototipo-iind.vercel.app/dashboard (ruta /dashboard de lulo_app/main.py).
WEB = "../lulo_app/templates/dashboard.html"
ORDEN_POLITICA = ("motor", "regla", "oraculo", "azar", "motor_sin_explorar", "motor_sin_dato")
LAB_ESCENARIOS = {   # scripts/laboratorio.py
    "señal": "La verdad tiene efectos que la regla no ve (rasgos, momento, señal media más débil).",
    "regla correcta": "La verdad es exactamente la regla v1.3: el motor no debería empeorar.",
    "ruido": "Como «señal», más 20 variables de puro ruido: el motor no debería confundirse.",
    "oportunidad oculta": "Como «señal», pero la señal media vende tanto como la fuerte: hay que explorar para verlo.",
    "dato nuevo": "Como «señal», más una columna que la base no trae y que sí mueve la aceptación (sobre todo de Vida).",
}
CASOS_COLUMNAS = ("id", "empresa", "sector", "pais", "anio", "metodo", "conexion", "resultado", "cifra", "leccion",
                  "fuente", "url", "confianza")


# ------------------------------------------------------------------ formato
def fmt(v, d: int = 6) -> str:
    """Celda de CSV: punto decimal, sin notación científica, 1/0 para sí/no y vacío para lo que no aplica."""
    if v is None:
        return ""
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, float):
        if math.isnan(v):
            return ""
        t = f"{v:.{d}f}".rstrip("0").rstrip(".")
        return "0" if t in ("-0", "") else t
    if isinstance(v, date):
        return v.isoformat()
    return str(v)


def tabla(cols: list[str], filas: list[dict], decimales: dict[str, int] | None = None) -> str:
    dec = decimales or {}
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(cols)
    for f in filas:
        w.writerow([fmt(f.get(c), dec.get(c, 6)) for c in cols])
    return buf.getvalue()


def _rows(name: str) -> list[dict]:
    with open(DATASET / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def tramo(p: float | None) -> tuple[str | None, int | None]:
    if p is None:
        return None, None
    i = next(i for i, (hasta, _) in enumerate(TRAMOS_P) if p < hasta)
    return TRAMOS_P[i][1], i + 1


def u(*k) -> float:
    """Sorteo determinista por clave: el mismo cliente, día y ramo dan el mismo número en los dos mundos."""
    return bayes.rng("piloto", *k, SEED).random()


# ------------------------------------------------------------------ dimensiones y base
def dim_fecha(s) -> list[dict]:
    meses = ("ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic")
    out, d = [], s.start
    while d <= s.cutoff:
        out.append({"fecha": d, "anio": d.year, "mes_num": d.month, "mes": d.strftime("%Y-%m"),
                    "mes_nombre": f"{meses[d.month - 1]} {d.year}", "orden_mes": d.year * 100 + d.month,
                    "semana_inicio": d - timedelta(days=d.weekday()), "dia_semana": d.isoweekday()})
        d += timedelta(days=1)
    return out


def dim_ramo(propias: dict[str, dict]) -> list[dict]:
    piloto = json.loads((ROOT / "lulo_app" / "ml" / "modelos.json").read_text(encoding="utf-8"))["piloto"]
    out = []
    for i, ramo in enumerate(RAMOS):
        p = product(ramo)
        out.append({"ramo": ramo, "titulo": p.title, "aliado": p.partner or "", "periodicidad": p.periodicity,
                    "prima_cop": p.premium, "comision_pct": p.commission_pct, "persistencia_6m": p.persistence_6m,
                    "persistencia_12m": p.persistence_12m, "cancelacion_pct": p.cancellation,
                    "meses_esperados": p.expected_months, "comision_12m_cop": p.commission_12m,
                    "conversion_previa": p.prior, "fuente_conversion": p.prior_source,
                    "compras_por_su_cuenta": propias[ramo]["compras"],
                    "ritmo_semanal_por_su_cuenta": propias[ramo]["ritmo"],
                    "piloto_n_20": piloto[ramo]["lift_20"], "piloto_n_50": piloto[ramo]["lift_50"],
                    "piloto_n_100": piloto[ramo]["lift_100"], "orden": i + 1})
    return out


def compras_propias(s) -> dict[str, dict]:
    """Ritmo semanal con el que un cliente compra un ramo por su cuenta: compras a otras aseguradoras del año de la
    base (pares cliente-ramo distintos de Pagos_Seguros) sobre clientes × semanas de la base."""
    pares = {(r["cliente_id"], r["ramo"]) for r in _rows("pagos_seguros.csv")}
    semanas = (s.cutoff - s.start).days / 7
    n = len(s.ids("reto"))
    c = Counter(r for _, r in pares)
    return {ramo: {"compras": c.get(ramo, 0), "ritmo": c.get(ramo, 0) / (n * semanas)} for ramo in RAMOS}


def dim_cliente(s, plan: dict[str, dict]) -> list[dict]:
    uso = {r["cliente_id"]: r for r in _rows("uso_app.csv")}
    out = []
    for r in _rows("clientes.csv"):
        cid = r["cliente_id"]
        if cid not in plan:
            continue
        e = experiment.group(cid, "reto")
        pols = [x for x in r["seguros_vigentes"].split("|") if x]
        a = uso.get(cid, {})
        out.append({"cliente_id": cid, "rango_edad": r["rango_edad"], "ocupacion": r["ocupacion"],
                    "antiguedad_meses": int(r["antiguedad_meses"]), "segmento": r["segmento"],
                    "saldo_promedio_cop": int(r["saldo_promedio_cop"]), "ingreso_mensual_cop": int(r["ingreso_mensual_cop"]),
                    "credito_activo": r["credito_activo"], "cajitas_activas": r["cajitas_activas"],
                    "cdt_activo": r["cdt_activo"], "seguros_lulo": " · ".join(pols), "n_seguros_lulo": len(pols),
                    "autoriza_ofertas": r["autoriza_ofertas"], "sesiones_30d": a.get("sesiones_30d"),
                    "max_contactos_mes": a.get("max_contactos_mes"), "latencia_eventos": a.get("latencia_eventos"),
                    "grupo": e["group"], "grupo_orden": 1 if e["group"] == "tratamiento" else 2,
                    "politica": e["policy"] or "", "bucket": e["bucket"],
                    "segmento_motor": plan[cid]["segmento_motor"]})
    return out


def base_campanas() -> list[dict]:
    return [{"campana": r["campana"], "ramo": campaign_ramo(r), "canal": r["canal"], "elegibles": int(r["elegibles"]),
             "impactados": int(r["impactados"]), "interesados": int(r["interesados"]), "ventas": int(r["ventas"]),
             "conv_ventas_impactados": float(r["conv_ventas_impactados"]), "nota_calidad": r.get("qa_nota", "")}
            for r in _rows("campanas_previas.csv")]


def base_seguros_mensual() -> list[dict]:
    out = []
    for r in _rows("seguros_mensual.csv"):
        f = {k: (float(v) if v != "" else None) for k, v in r.items() if k not in ("mes", "ramo")}
        out.append({"mes": date.fromisoformat(r["mes"] + "-01"), "ramo": r["ramo"],
                    "polizas_emitidas": int(f["polizas_emitidas"]), "renovaciones": int(f["renovaciones"]),
                    "prima_promedio_cop": int(f["prima_promedio_cop"]), "comision_pct": f["comision_pct"],
                    "persistencia_6m": f["persistencia_6m"], "persistencia_12m": f["persistencia_12m"],
                    "cancelacion_pct": f["cancelacion_pct"]})
    return out


def base_pagos_externos() -> list[dict]:
    return [{"pago_id": r["pago_id"], "cliente_id": r["cliente_id"], "fecha": r["fecha_pago"], "ramo": r["ramo"],
             "monto_cop": int(r["monto_cop"]), "fecha_vencimiento": r["fecha_vencimiento"]}
            for r in _rows("pagos_seguros.csv")]


# ------------------------------------------------------------------ motor
def plan_al_corte(s) -> dict[str, dict]:
    """Lo que el motor le ofrecería hoy (al corte) a cada cliente, con su alcance y lo que se espera vender."""
    out = {}
    for cid in s.ids("reto"):
        r = evaluate(cid, Context(mode="lote"), lite=True)
        d = r["decision"] or {}
        pr = d.get("prob") or {}
        al = (d.get("alcance") or {}).get("p")
        trat = r["outcome"] in ("shown", "banner")
        out[cid] = {
            "cliente_id": cid, "resultado": r["outcome"], "resultado_texto": OUTCOME_LABEL[r["outcome"]],
            "ramo": d.get("ramo"), "tipo": d.get("kind"), "fuerza": d.get("strength"),
            "canal": (r["channel"] or {}).get("channel") or ("ninguno" if d else None),
            "motivo_canal": ((r["channel"] or {}).get("reason") or "").split(":")[0] or None,
            "grupo": (r["experiment"] or {}).get("group"), "politica": (r["experiment"] or {}).get("policy"),
            "explora": d.get("explora") if d else None, "p_motor": pr.get("p"),
            "p_ic90_bajo": (pr.get("ic90") or [None, None])[0], "p_ic90_alto": (pr.get("ic90") or [None, None])[1],
            "alcance": al, "valor_esperado_cop": d.get("ev"),
            "ventas_esperadas": al * pr["p"] if trat and al is not None and pr.get("p") is not None else None,
            "comision_esperada_cop": al * d["ev"] if trat and al is not None and d.get("ev") is not None else None,
            "ev_regla_cop": d.get("ev_regla"), "ramo_regla": (r.get("regla") or {}).get("ramo"),
            "coincide_regla": (r.get("regla") or {}).get("coincide") if d else None,
            "n_ofrecibles": sum(1 for x in r["candidates"] if x["status"] == "ofrecer"),
            "momento": (d.get("momento_dias") is not None) if d else None,
            "segmento_motor": ((r.get("ml") or {}).get("segmento") or {}).get("nombre")}
    return out


INVARIANTES = (
    ("oferta sin autorización", "Nadie sin autorización de datos recibe una oferta"),
    ("con estado", "Solo se muestra lo que las compuertas permiten ofrecer"),
    ("no elegible", "Nadie recibe un ramo para el que no es elegible"),
    ("ya lo tiene", "Nadie recibe un ramo que ya tiene con Lulo"),
    ("dos push con", f"Entre dos push pasan al menos {rules.MIN_DAYS_BETWEEN_PUSH} días"),
    ("push en 30 días", "Nadie recibe más push que su tope en 30 días"),
    ("repetido a los", f"El mismo ramo no se repite antes de {rules.COOLDOWN_DAYS} días"),
)


def motor_backtest() -> tuple[list[dict], list[dict]]:
    bt = backtest.run()
    met = [("evaluaciones", bt["evaluations"], "clientes × fechas evaluadas"),
           ("ofertas", bt["offers"], "push + banner"), ("push", bt["push"], ""), ("banner", bt["banner"], ""),
           ("control", bt["control"], "decisiones registradas sin mostrar"),
           ("clientes_alcanzados", bt["clients_reached"], "con al menos una oferta"),
           ("max_push_30d", bt["max_push_30d"], "el máximo de push a un cliente en 30 días"),
           ("violaciones", len(bt["violations"]), "debe ser 0"),
           ("desde", bt["start"], ""), ("hasta", bt["end"], ""), ("cada_dias", bt["every_days"], "")]
    metricas = [{"metrica": k, "valor": v, "nota": n} for k, v, n in met]
    inv = [{"invariante": txt, "violaciones": sum(1 for v in bt["violations"] if pat in v),
            "fuente": "backtest: python -m lulo_app.core backtest"} for pat, txt in INVARIANTES]
    return metricas, inv


# ------------------------------------------------------------------ piloto simulado
def _x(h, ramo: str, day: date, s, sp: dict, cache: dict) -> dict:
    """El vector del motor bayesiano para ese cliente, ramo y día (como train_motor.ejemplos)."""
    key = (h.client.id, day)
    if key not in cache:
        f = compute(h, day, s.cutoff)
        cache[key] = (detect(f), rasgos.estandarizar(rasgos.crudos(h, day, s.cutoff), sp["rasgos"]),
                      ml.propensity(h, min(day, s.cutoff)))
    sigs, z, prop = cache[key]
    mom = mot.momento(h, ramo, day, sp["momento"]["ventana_dias"]) is not None
    aff = mot.afinidad_probit(ramo, prop[ramo]["afinidad_cruda"], sp)
    return mot.vector(ramo, z, sigs[ramo].strength, mom, aff, h.client.id)


def piloto(s, esc: str, propias: dict[str, dict]) -> dict[str, list[dict]]:
    sp = mot.spec()
    ids = sorted(s.ids("reto"))
    V = lab.verdad(esc, sp, [{"cid": c} for c in ids])
    externos = {(r["cliente_id"], r["ramo"]) for r in _rows("pagos_seguros.csv")}
    valor = {r: product(r).commission_12m for r in RAMOS}
    ledger: dict[str, list[OfferLog]] = defaultdict(list)
    tiene: dict[str, list[str]] = defaultdict(list)
    decisiones, ventas, cache = [], [], {}
    day = s.start + timedelta(days=PILOTO_DESDE_DIAS)
    while day <= s.cutoff:
        for cid in ids:
            h = s.history(cid)
            for ramo in RAMOS:         # compras por su cuenta, sin oferta, en los dos grupos
                rt = propias[ramo]["ritmo"]
                if rt and ramo not in tiene[cid] and not h.client.holds(ramo) and (cid, ramo) not in externos \
                        and u("propia", cid, day, ramo) < rt:
                    tiene[cid].append(ramo)
                    ventas.append({"fecha": day, "cliente_id": cid, "ramo": ramo, "origen": "por su cuenta",
                                   "canal": None})
            r = evaluate(cid, Context(as_of=day, mode="lote", history=ledger[cid], accepted=tiene[cid]), lite=True)
            out = r["outcome"]
            if out not in ("shown", "banner", "control"):
                continue
            d, exp = r["decision"], r["experiment"]
            ramo, rr = d["ramo"], r["regla"]["ramo"]
            pv = lab.p_verdad(V, _x(h, ramo, day, s, sp, cache), cid)
            pvr = pv if rr == ramo else lab.p_verdad(V, _x(h, rr, day, s, sp, cache), cid)
            fila = {"fecha": day, "cliente_id": cid, "ramo": ramo, "grupo": exp["group"], "politica": exp["policy"],
                    "p_motor": (d.get("prob") or {}).get("p"), "version_reglas": rules.VERSION,
                    "fuerza": d["strength"], "momento": d["momento_dias"] is not None, "tipo": d["kind"],
                    "explora": d["explora"], "valor_esperado_cop": d["ev"], "comision_12m_cop": valor[ramo],
                    "ramo_regla": rr, "coincide_regla": rr == ramo, "comision_12m_regla_cop": valor[rr],
                    "p_verdad": pv, "p_verdad_regla": pvr}
            fila["tramo_p_motor"], fila["tramo_orden"] = tramo(fila["p_motor"])
            fila["momento_texto"] = "con evento reciente" if fila["momento"] else "sin evento reciente"
            if out == "control":
                ledger[cid].append(OfferLog(ramo=ramo, date=day, result="control", channel="ninguno"))
                decisiones.append(fila | {"canal": "ninguno", "resultado": "control", "alcance": None})
                continue
            canal = "push" if out == "shown" else "banner"
            al = d["alcance"]["p"]
            if u("vista", cid, day, ramo) >= al:
                res = "ignorada"
                ledger[cid].append(OfferLog(ramo=ramo, date=day, result="mostrada" if canal == "push" else "banner",
                                            channel=canal))
            else:
                res = "aceptada" if u("respuesta", cid, day, ramo) < pv else "rechazada"
                ledger[cid].append(OfferLog(ramo=ramo, date=day, result=res, channel=canal))
                if res == "aceptada":
                    tiene[cid].append(ramo)
                    ventas.append({"fecha": day, "cliente_id": cid, "ramo": ramo, "origen": "oferta", "canal": canal})
            decisiones.append(fila | {"canal": canal, "resultado": res, "alcance": al})
        day += timedelta(days=CADA_DIAS)

    # Intención de tratar desde el disparo: entra al piloto quien tuvo al menos una decisión (oferta o control),
    # y sus compras cuentan desde esa primera decisión, igual en los dos grupos.
    primera = {}
    for f in decisiones:
        primera.setdefault(f["cliente_id"], f["fecha"])
    ventas = [v | {"comision_12m_cop": valor[v["ramo"]]} for v in ventas
              if v["cliente_id"] in primera and v["fecha"] >= primera[v["cliente_id"]]]
    por = defaultdict(lambda: {"decisiones": 0, "vistas": 0, "aceptadas": 0, "ventas": 0, "comision_12m_cop": 0})
    for f in decisiones:
        c = por[f["cliente_id"]]
        c["decisiones"] += 1
        c["vistas"] += f["resultado"] in ("aceptada", "rechazada")
        c["aceptadas"] += f["resultado"] == "aceptada"
    for v in ventas:
        por[v["cliente_id"]]["ventas"] += 1
        por[v["cliente_id"]]["comision_12m_cop"] += v["comision_12m_cop"]
    clientes = []
    for cid, d0 in sorted(primera.items()):
        e = experiment.group(cid, "reto")
        clientes.append({"cliente_id": cid, "grupo": e["group"], "politica": e["policy"], "primera_decision": d0,
                         **por[cid], "compro": por[cid]["ventas"] > 0})
    for t in (decisiones, ventas, clientes):
        for f in t:
            f["escenario"] = esc
    return {"decisiones": decisiones, "ventas": ventas, "clientes": clientes}


def lectura(clientes: list[dict]) -> dict:
    """Diferencia de proporciones tratamiento − control con IC 95 % y prueba z (la misma cuenta que las medidas DAX)."""
    g = {k: [c for c in clientes if c["grupo"] == k] for k in ("tratamiento", "control")}
    n = {k: len(v) for k, v in g.items()}
    x = {k: sum(c["compro"] for c in v) for k, v in g.items()}
    p = {k: x[k] / n[k] if n[k] else 0.0 for k in g}
    d = p["tratamiento"] - p["control"]
    se = math.sqrt(sum(p[k] * (1 - p[k]) / n[k] for k in g if n[k]))
    pp = (x["tratamiento"] + x["control"]) / (n["tratamiento"] + n["control"])
    se0 = math.sqrt(pp * (1 - pp) * (1 / n["tratamiento"] + 1 / n["control"]))
    z = d / se0 if se0 else 0.0
    pval = math.erfc(abs(z) / math.sqrt(2))
    return {"n": n, "compraron": x, "tasa": p, "uplift": d, "ic95": (d - 1.96 * se, d + 1.96 * se), "z": z, "p": pval,
            "ventas_incrementales": d * n["tratamiento"]}


# ------------------------------------------------------------------ laboratorio
def laboratorio() -> dict[str, list[dict]]:
    L = json.loads((ROOT / "lulo_app" / "ml" / "laboratorio.json").read_text(encoding="utf-8"))
    series, calib, pesos, resumen, apetito = [], [], [], [], []
    for esc, e in L["escenarios"].items():
        for pol, v in e["politicas"].items():
            for t, (com, ac) in enumerate(zip(v["comision"], v["aceptacion"])):
                series.append({"escenario": esc, "politica": pol, "politica_nombre": v["nombre"],
                               "politica_orden": ORDEN_POLITICA.index(pol) + 1, "ronda": t + 1,
                               "respuestas_acumuladas": e["respuestas_acumuladas"][t], "comision_por_oferta": com,
                               "aceptacion": ac})
        for mod, v in e["calibracion"].items():
            for t, err in enumerate(v):
                calib.append({"escenario": esc, "modelo": mod, "ronda": t + 1, "error_medio": err})
        for k, v in e["pesos"].items():
            for t, est in enumerate(v["estimado"]):
                pesos.append({"escenario": esc, "variable": k, "etiqueta": v["label"], "verdad": v["verdad"],
                              "ronda": t + 1, "estimado": est})
        resumen.append({"escenario": esc, "motor_frente_a_regla": e["frente_a_regla_final"],
                        "motor_del_techo": e["del_techo_final"], "regla_del_techo": e["regla_del_techo"],
                        "ronda_supera_regla": e["ronda_supera_regla"],
                        "respuestas_para_superar": e["respuestas_para_superar"],
                        "valor_del_dato": e.get("valor_del_dato"),
                        **{f"comision_final_{p}": v for p, v in e["final"].items()}})
        for fila in e["apetito"]["estimado"]:
            for pol in ("motor", "motor_sin_explorar"):
                a = fila[pol]
                apetito.append({"escenario": esc, "ronda": fila["ronda"], "politica": pol, "tau": a["tau"],
                                "ic95_bajo": a["ic95"][0], "ic95_alto": a["ic95"][1], "verdad": e["apetito"]["verdad"],
                                "previa": e["apetito"]["previa"]})
    return {"series": series, "calibracion": calib, "pesos": pesos, "resumen": resumen, "apetito": apetito,
            "texto": L["resumen"], "version": L["version"]}


def casos() -> list[dict]:
    if not CASOS.exists():
        return []
    with open(CASOS, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        falta = [c for c in CASOS_COLUMNAS if not (r.get(c) or "").strip()]
        if falta:
            raise SystemExit(f"powerbi/casos.csv, caso {r.get('id')}: faltan {falta} (cada caso lleva su fuente)")
        if r["resultado"] not in ("éxito", "fracaso", "sin efecto", "mixto"):
            raise SystemExit(f"powerbi/casos.csv, caso {r['id']}: resultado «{r['resultado']}» no reconocido")
    return rows


# ------------------------------------------------------------------ armado
def build(verbose: bool = True) -> dict[str, str]:
    s = store()
    say = print if verbose else (lambda *a, **k: None)
    sha = json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))["fuente"]["sha256"]
    propias = compras_propias(s)
    say("Plan del motor al corte…")
    plan = plan_al_corte(s)
    say("Backtest…")
    bt_met, bt_inv = motor_backtest()
    pil = {}
    for esc in ESCENARIOS:
        say(f"Piloto simulado · {esc}…")
        pil[esc] = piloto(s, esc, propias)
    # El grupo de control nunca ve una oferta: se verifica en el piloto, con las mismas decisiones del motor.
    vistas_control = sum(1 for p in pil.values() for f in p["decisiones"] if f["grupo"] == "control" and f["canal"] != "ninguno")
    bt_inv.append({"invariante": "El grupo de control nunca ve una oferta", "violaciones": vistas_control,
                   "fuente": "piloto simulado: decisiones del motor"})
    L = laboratorio()
    desde = s.start + timedelta(days=PILOTO_DESDE_DIAS)
    meta = [
        ("etiqueta", ETIQUETA, ""), ("exportador", VERSION, "scripts/exportar_powerbi.py"),
        ("base_sha256", sha, "lulo_app/dataset/manifest.json"), ("base_inicio", s.start.isoformat(), "base"),
        ("base_corte", s.cutoff.isoformat(), "base"), ("clientes", len(plan), "base"),
        ("reglas", rules.VERSION, "lulo_app/core/rules.py"), ("motor", mot.spec()["version"], "lulo_app/ml/motor.json"),
        ("laboratorio", L["version"], "lulo_app/ml/laboratorio.json"),
        ("piloto_desde", desde.isoformat(), "simulado"), ("piloto_hasta", s.cutoff.isoformat(), "simulado"),
        ("piloto_cada_dias", CADA_DIAS, "simulado"), ("semilla", SEED, "simulado"),
        ("aviso_base", "La base es 100 % sintética y académica: sus cifras no son métricas de Lulo Bank.", "base"),
        ("aviso_piloto", "Piloto simulado: el motor y sus decisiones son reales; las respuestas son inventadas con "
                         "la verdad del laboratorio. No dice si el motor vende: muestra cómo se va a saber.", "simulado"),
        ("lab_resumen", L["texto"], "lulo_app/ml/laboratorio.json"),
    ]
    tablas = {
        "meta.csv": tabla(["clave", "valor", "fuente"], [dict(zip(("clave", "valor", "fuente"), m)) for m in meta]),
        "dim_fecha.csv": tabla(["fecha", "anio", "mes_num", "mes", "mes_nombre", "orden_mes", "semana_inicio",
                                "dia_semana"], dim_fecha(s)),
        "dim_ramo.csv": tabla(["ramo", "titulo", "aliado", "periodicidad", "prima_cop", "comision_pct", "persistencia_6m",
                               "persistencia_12m", "cancelacion_pct", "meses_esperados", "comision_12m_cop",
                               "conversion_previa", "fuente_conversion", "compras_por_su_cuenta",
                               "ritmo_semanal_por_su_cuenta", "piloto_n_20", "piloto_n_50", "piloto_n_100", "orden"],
                              dim_ramo(propias), {"meses_esperados": 4, "ritmo_semanal_por_su_cuenta": 7}),
        "dim_cliente.csv": tabla(["cliente_id", "rango_edad", "ocupacion", "antiguedad_meses", "segmento",
                                  "saldo_promedio_cop", "ingreso_mensual_cop", "credito_activo", "cajitas_activas",
                                  "cdt_activo", "seguros_lulo", "n_seguros_lulo", "autoriza_ofertas", "sesiones_30d",
                                  "max_contactos_mes", "latencia_eventos", "grupo", "grupo_orden", "politica", "bucket",
                                  "segmento_motor"], dim_cliente(s, plan)),
        "dim_escenario.csv": tabla(["escenario", "nombre", "descripcion", "orden"],
                                   [{"escenario": k, "nombre": v[0], "descripcion": v[1], "orden": i + 1}
                                    for i, (k, v) in enumerate(ESCENARIOS.items())]),
        "base_campanas.csv": tabla(["campana", "ramo", "canal", "elegibles", "impactados", "interesados", "ventas",
                                    "conv_ventas_impactados", "nota_calidad"], base_campanas()),
        "base_seguros_mensual.csv": tabla(["mes", "ramo", "polizas_emitidas", "renovaciones", "prima_promedio_cop",
                                           "comision_pct", "persistencia_6m", "persistencia_12m", "cancelacion_pct"],
                                          base_seguros_mensual()),
        "base_pagos_externos.csv": tabla(["pago_id", "cliente_id", "fecha", "ramo", "monto_cop", "fecha_vencimiento"],
                                         base_pagos_externos()),
        "motor_plan.csv": tabla(["cliente_id", "resultado", "resultado_texto", "ramo", "tipo", "fuerza", "canal",
                                 "motivo_canal", "grupo", "politica", "explora", "p_motor", "p_ic90_bajo", "p_ic90_alto",
                                 "alcance", "valor_esperado_cop", "ventas_esperadas", "comision_esperada_cop",
                                 "ev_regla_cop", "ramo_regla", "coincide_regla", "n_ofrecibles", "momento",
                                 "segmento_motor"], [plan[c] for c in sorted(plan)],
                                {"ventas_esperadas": 6, "comision_esperada_cop": 0}),
        "motor_backtest.csv": tabla(["metrica", "valor", "nota"], bt_met),
        "motor_invariantes.csv": tabla(["invariante", "violaciones", "fuente"], bt_inv),
        "piloto_decisiones.csv": tabla(
            ["escenario", "fecha", "cliente_id", "ramo", "canal", "resultado", "grupo", "politica", "p_motor",
             "version_reglas", "fuerza", "momento", "tipo", "explora", "alcance", "valor_esperado_cop",
             "comision_12m_cop", "ramo_regla", "coincide_regla", "comision_12m_regla_cop", "p_verdad",
             "p_verdad_regla", "tramo_p_motor", "tramo_orden", "momento_texto"],
            [f for p in pil.values() for f in p["decisiones"]], {"p_verdad": 5, "p_verdad_regla": 5}),
        "piloto_ventas.csv": tabla(["escenario", "fecha", "cliente_id", "ramo", "origen", "canal", "comision_12m_cop"],
                                   [f for p in pil.values() for f in p["ventas"]]),
        "piloto_clientes.csv": tabla(["escenario", "cliente_id", "grupo", "politica", "primera_decision", "decisiones",
                                      "vistas", "aceptadas", "ventas", "compro", "comision_12m_cop"],
                                     [f for p in pil.values() for f in p["clientes"]]),
        "dim_lab_escenario.csv": tabla(["escenario", "descripcion", "orden"],
                                       [{"escenario": k, "descripcion": v, "orden": i + 1}
                                        for i, (k, v) in enumerate(LAB_ESCENARIOS.items())]),
        "lab_series.csv": tabla(["escenario", "politica", "politica_nombre", "politica_orden", "ronda", "respuestas_acumuladas",
                                 "comision_por_oferta", "aceptacion"], L["series"]),
        "lab_calibracion.csv": tabla(["escenario", "modelo", "ronda", "error_medio"], L["calibracion"]),
        "lab_pesos.csv": tabla(["escenario", "variable", "etiqueta", "verdad", "ronda", "estimado"], L["pesos"]),
        "lab_resumen.csv": tabla(["escenario", "motor_frente_a_regla", "motor_del_techo", "regla_del_techo",
                                  "ronda_supera_regla", "respuestas_para_superar", "valor_del_dato",
                                  "comision_final_regla", "comision_final_motor", "comision_final_motor_sin_explorar",
                                  "comision_final_oraculo", "comision_final_azar", "comision_final_motor_sin_dato"],
                                 L["resumen"]),
        "lab_apetito.csv": tabla(["escenario", "ronda", "politica", "tau", "ic95_bajo", "ic95_alto", "verdad", "previa"],
                                 L["apetito"]),
        "casos.csv": tabla(list(CASOS_COLUMNAS), casos()),
    }
    if verbose:
        for esc, p in pil.items():
            le = lectura(p["clientes"])
            dec = p["decisiones"]
            vis = [f for f in dec if f["resultado"] in ("aceptada", "rechazada")]
            ace = sum(f["resultado"] == "aceptada" for f in vis)
            com = sum(c["comision_12m_cop"] for c in p["clientes"] if c["grupo"] == "tratamiento")
            say(f"  {esc:15} decisiones {len(dec):,} · vistas {len(vis):,} · aceptadas {ace} "
                f"({ace / max(1, len(vis)):.1%} de las vistas) · clientes tratamiento {le['n']['tratamiento']} "
                f"compran {le['tasa']['tratamiento']:.1%} · control {le['n']['control']} compran "
                f"{le['tasa']['control']:.1%} · diferencia {le['uplift'] * 100:+.1f} pp "
                f"(IC 95 % {le['ic95'][0] * 100:+.1f} a {le['ic95'][1] * 100:+.1f}) · p = {le['p']:.4f} · "
                f"ventas incrementales {le['ventas_incrementales']:.0f} · comisión 12 m del tratamiento {com:,.0f}")
        say(f"  invariantes: {sum(i['violaciones'] for i in bt_inv)} violaciones")
    return tablas


def archivos(verbose: bool = True) -> dict[str, str]:
    """Todo lo generado, por ruta relativa a powerbi/: las tablas de detalle (datos/), las 10 tablas chicas del
    dashboard (tablas/), el proyecto de Power BI con esas tablas adentro, la vista previa y la página web (WEB)."""
    tablas = build(verbose)
    chicas, notas = powerbi_modelo.agregar(tablas)
    return ({f"datos/{n}": t for n, t in tablas.items()} | powerbi_modelo.proyecto(chicas, notas)
            | {"vista_previa.html": powerbi_vista.html(chicas, notas), WEB: powerbi_web.html(chicas, notas)})


def en_disco() -> set[str]:
    """Archivos de powerbi/ con forma de generados: los CSV, el proyecto, las medidas, el tema y la vista previa.
    Nunca la guía, los casos, la caché local de Power BI ni un .pbix guardado por alguien."""
    def generado(r: str) -> bool:
        return (fnmatch(r, "datos/*.csv") or fnmatch(r, "tablas/*.csv") or fnmatch(r, "Lulo*.pbip")
                or (fnmatch(r, "Lulo*.Report/*") or fnmatch(r, "Lulo*.SemanticModel/*")) and "/.pbi/" not in r
                or r.endswith(".dax") or fnmatch(r, "tema-*.json") or fnmatch(r, "vista_previa*.html"))
    rel = (p.relative_to(POWERBI).as_posix() for p in POWERBI.rglob("*") if p.is_file())
    return {r for r in rel if r not in MANUALES and generado(r)}


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="falla si los archivos del repositorio no coinciden")
    a = ap.parse_args()
    todo = archivos()
    if a.check:
        malos = [n for n, t in todo.items()
                 if not (POWERBI / n).exists() or (POWERBI / n).read_text(encoding="utf-8") != t]
        sobran = sorted(en_disco() - set(todo))
        if malos or sobran:
            print(f"powerbi/ no coincide con lo que se genera hoy: {malos + sobran}", file=sys.stderr)
            sys.exit(1)
        print(f"powerbi/ coincide ({len(todo)} archivos)")
        return
    for n in sorted(en_disco() - set(todo)):          # lo que ya no se genera (por ejemplo, un dashboard anterior)
        (POWERBI / n).unlink()
    for d in sorted((p for p in POWERBI.rglob("*") if p.is_dir()), reverse=True):
        if not any(d.iterdir()):
            d.rmdir()
    for n, t in todo.items():
        (POWERBI / n).parent.mkdir(parents=True, exist_ok=True)
        (POWERBI / n).write_text(t, encoding="utf-8")
    h = hashlib.sha256("".join(todo[n] for n in sorted(todo)).encode()).hexdigest()[:12]
    print(f"Escritos {len(todo)} archivos en powerbi/ · sha256 {h}")


if __name__ == "__main__":
    main()
