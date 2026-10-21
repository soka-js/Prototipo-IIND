"""Entrena el motor bayesiano y deja sus creencias en lulo_app/ml/motor.json (método: docs/MOTOR.md).

    python scripts/train_motor.py                         # entrena con la base del reto y escribe motor.json
    python scripts/train_motor.py --check                 # falla si motor.json no coincide con el entrenamiento
    python scripts/train_motor.py --respuestas r.csv      # además aprende de respuestas reales a ofertas
    python scripts/train_motor.py --datos CARPETA --salida motor-lulo.json --reporte reporte.md [--sin-clientes]
                                                          # otra base con el mismo esquema (docs/DATOS_REALES.md)

Python puro, sin numpy ni scikit-learn, y determinista: dos corridas dan el mismo archivo.

Piezas que entrena:
  B1 embudo    Campanas_Previas → conversión de cada ramo con un Beta-Binomial jerárquico (Bayes empírico):
               cada campaña aporta su evidencia y se encoge hacia el promedio de las campañas; Hogar, que no
               tiene campaña, recibe la distribución de la población. También interés, cierre y alcance.
  B2 momento   Movimientos + Cajitas + Pagos_Seguros → ¿se compra más un seguro en los 30 días después del
               evento que lo dispara? Serie de casos autocontrolada (cada cliente se compara consigo mismo),
               jerárquica entre ramos y resuelta exacta en una rejilla.
  B3 rasgos    Clientes + Movimientos + Cajitas + Pagos_Seguros + Uso_App → vocabulario y estandarización.
  B4 previas   creencias previas de la regresión probit: base (B1), señal media (hipótesis aprobada × 0,6),
               momento (B2), afinidad (M1, si pasa su compuerta), rasgos y apetito del cliente (en 0).
  respuestas   si hay respuestas a ofertas, actualiza las creencias en orden cronológico (ADF) y solo las
               promueve si mejoran la log-pérdida en el 20 % más reciente (campeón/retador).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "lulo_app" / "ml" / "motor.json"
# La versión entra en la semilla del sorteo de exploración (motor.muestra): cambiarla vuelve a sortear a quienes
# exploran. Sube solo cuando cambia cómo puntúa el motor; v2.1 (Bayes empírico del apetito) solo actúa con
# respuestas y deja igual el puntaje sin ellas, así que conserva motor-1.0.
VERSION = "motor-1.0"
SEED = 19
GRID = (-4.0, 4.0, 321)            # rejilla del log de la razón de tasas del momento
SENSIBILIDAD = (7, 15, 30, 60, 90)
N_BOOT = 2000


def r(x, n=6):
    return None if x is None else round(float(x), n)


def _c(x) -> str:
    return str(x).replace(".", ",")


def rb(d: dict, n=6) -> dict:
    return {k: (r(v, n) if isinstance(v, float) else [r(t, n) for t in v] if isinstance(v, list) else v) for k, v in d.items()}


# ------------------------------------------------------------------ B1 embudo
def _por_ramo(rows: list[dict]) -> list[dict]:
    """Una fila por ramo: si Lulo trae varias campañas del mismo ramo, se suman sus conteos."""
    from lulo_app.core.catalog import campaign_ramo

    out: dict[str, dict] = {}
    for c in rows:
        ramo = campaign_ramo(c)
        if not ramo:
            continue
        o = out.setdefault(ramo, {"ramo": ramo, "campana": [], "canal": [], "elegibles": 0, "impactados": 0,
                                  "interesados": 0, "ventas": 0})
        o["campana"].append(c["campana"])
        o["canal"].append(c["canal"])
        for k in ("elegibles", "impactados", "interesados", "ventas"):
            o[k] += int(c[k])
    for o in out.values():
        o["campana"], o["canal"] = " + ".join(o["campana"]), " + ".join(sorted(set(o["canal"])))
    return list(out.values())


def _canal(c: dict, tipo: str) -> bool:
    """Campaña de un solo canal: solo banner o solo push (para estimar el alcance de cada uno)."""
    k = c["canal"].lower()
    return tipo in k and ("push" if tipo == "banner" else "banner") not in k


def embudo(dataset: Path) -> dict:
    from lulo_app.core.schema import RAMOS
    from lulo_app.ml import bayes

    with open(dataset / "campanas_previas.csv", encoding="utf-8", newline="") as f:
        camp = _por_ramo(list(csv.DictReader(f)))
    # Cuatro tasas del embudo, cada una con su modelo jerárquico (Bayes completo en rejilla, BDA3 5.3).
    conv = bayes.beta_binomial_bayes([(c["ventas"], c["impactados"]) for c in camp])
    inter = bayes.beta_binomial_bayes([(c["interesados"], c["impactados"]) for c in camp])
    cierre = bayes.beta_binomial_bayes([(c["ventas"], c["interesados"]) for c in camp])
    alc = bayes.beta_binomial_bayes([(c["impactados"], c["elegibles"]) for c in camp])
    idx = {c["ramo"]: i for i, c in enumerate(camp)}
    por_ramo = {}
    for ramo in RAMOS:
        i = idx.get(ramo)
        if i is not None:
            c = camp[i]
            por_ramo[ramo] = {
                "campana": c["campana"], "canal": c["canal"], "elegibles": c["elegibles"], "impactados": c["impactados"],
                "interesados": c["interesados"], "ventas": c["ventas"], "cruda": r(c["ventas"] / c["impactados"]),
                "interes": r(inter["grupos"][i]["media"]), "cierre": r(cierre["grupos"][i]["media"]),
                "alcance": r(alc["grupos"][i]["media"]), "posterior": rb(conv["grupos"][i]),
                "fuente": "Campanas_Previas: ventas / impactados, encogida hacia el promedio de las campañas"}
        else:
            por_ramo[ramo] = {"campana": None, "cruda": None, "posterior": rb(conv["nuevo"]),
                              "fuente": "Sin campaña previa: predictiva de una campaña nueva (promedio de las demás, "
                                        "con más duda)"}
    alcance = {}
    for canal in ("banner", "push"):
        i = next((j for j, x in enumerate(camp) if _canal(x, canal)), None)
        if i is not None:
            alcance[canal] = {**rb(alc["grupos"][i]), "campana": camp[i]["campana"],
                              "fuente": f"Campanas_Previas: impactados / elegibles de «{camp[i]['campana']}» "
                                        f"({camp[i]['canal']})"}
    hiper = {k: {"mu": r(v["mu"]), "kappa": r(v["kappa_mediana_geom"], 2), "kappa_eb": r(v["eb"]["kappa"], 2)}
             for k, v in (("conversion", conv), ("interes", inter), ("cierre", cierre), ("alcance", alc))}
    m = hiper["conversion"]["mu"]
    print(f"  B1 conversión de las campañas: promedio {m:.3f}, concentración κ ≈ {hiper['conversion']['kappa']:.0f} · "
          + ", ".join(f"{k} {v['cruda'] or 0:.3f}→{v['posterior']['media']:.3f}" for k, v in por_ramo.items()))
    return {"metodo": "Beta-Binomial jerárquico con Bayes completo en rejilla (Gelman et al., BDA3, 5.3), previa "
                      "p(μ, κ) ∝ κ^(−3/2)", "hiper": hiper, "por_ramo": por_ramo, "alcance": alcance,
            "lectura": (f"De cada 100 clientes que ven una oferta de seguro, cerca de "
                        f"{round(hiper['interes']['mu'] * 100)} se interesan y {round(m * 100)} compran. "
                        f"Cada ramo conserva su evidencia, encogida un poco hacia el promedio de las campañas; Hogar, "
                        f"sin campaña, recibe ese promedio con mucha más duda.")}


# ------------------------------------------------------------------ B2 momento
def _cubiertos(evs: list[date], start: date, end: date, ventana: int) -> set[int]:
    out = set()
    a, b = start.toordinal(), end.toordinal()
    for e in evs:
        o = e.toordinal()
        for k in range(ventana):
            if a <= o + k <= b:
                out.add(o + k)
    return out


def _casos(s, ids, ramo, ventana, start):
    """Por cada pago externo del ramo: (fracción de días del periodo dentro de la ventana, cayó dentro)."""
    from lulo_app.ml import motor

    n_days = s.cutoff.toordinal() - start.toordinal() + 1
    out = []
    for cid in ids:
        h = s.history(cid)
        pays = [e for e in h.external if e.ramo == ramo and e.paid_on <= s.cutoff]
        if not pays:
            continue
        evs = motor.eventos(h, ramo, s.cutoff)
        cov = _cubiertos(evs, start, s.cutoff, ventana)
        p = len(cov) / n_days
        for e in pays:
            hit = any(0 <= (e.paid_on - d).days < ventana for d in evs)
            out.append((p, int(hit)))
    return out


def _loglik(casos, grid):
    from lulo_app.ml import bayes

    inf = [(bayes.logit(p), h) for p, h in casos if 0 < p < 1]
    out = []
    for t in grid:
        ll = 0.0
        for lo, h in inf:
            z = t + lo
            # log σ(z) y log(1 − σ(z)) estables
            ll += -math.log1p(math.exp(-z)) if z >= 0 else z - math.log1p(math.exp(z))
            if not h:
                ll -= z
        out.append(ll)
    return out if inf else []


def momento(s, ids, ventana) -> dict:
    from lulo_app.core.schema import RAMOS
    from lulo_app.ml import bayes, motor

    start = min(m.date for cid in ids for m in s.history(cid).movements)
    grid = bayes.rejilla(*GRID)
    casos = {ramo: _casos(s, ids, ramo, ventana, start) for ramo in RAMOS}
    ll = {ramo: _loglik(c, grid) for ramo, c in casos.items()}
    jer = bayes.jerarquico_rejilla(ll, grid)
    por_ramo = {}
    for ramo in RAMOS:
        c, th = casos[ramo], jer["grupos"][ramo]
        por_ramo[ramo] = {
            "evento": motor.EVENTOS[ramo]["texto"], "pagos": len(c), "sin_evento": sum(1 for p, _ in c if p == 0),
            "informativos": sum(1 for p, _ in c if 0 < p < 1), "en_ventana": sum(h for _, h in c),
            "esperados": r(sum(p for p, _ in c), 2), "con_datos": bool(ll[ramo]),
            "theta": rb(th, 4), "rr": {"media": r(math.exp(th["media"]), 3),
                                       "ic90": [r(math.exp(th["q05"]), 3), r(math.exp(th["q95"]), 3)]}}
    tot_h = sum(v["en_ventana"] for v in por_ramo.values())
    tot_e = sum(v["esperados"] for v in por_ramo.values())
    print(f"  B2 momento ({ventana} días): {tot_h} compras externas tras el evento frente a {tot_e:.1f} esperadas · "
          + ", ".join(f"{k} RR {v['rr']['media']:.2f} [{v['rr']['ic90'][0]:.2f}–{v['rr']['ic90'][1]:.2f}]"
                      for k, v in por_ramo.items()))
    sens = {}
    for w in SENSIBILIDAD:
        allc = [x for ramo in RAMOS for x in _casos(s, ids, ramo, w, start)]
        llw = _loglik(allc, grid)
        lp = [a - 0.5 * t * t for a, t in zip(llw, grid)]
        mx = max(lp)
        wts = [math.exp(x - mx) for x in lp]
        tot = sum(wts)
        su = bayes.resumen_rejilla(grid, [x / tot for x in wts])
        sens[str(w)] = {"en_ventana": sum(h for _, h in allc), "esperados": r(sum(p for p, _ in allc), 2),
                        "rr": r(math.exp(su["media"]), 3), "ic90": [r(math.exp(su["q05"]), 3), r(math.exp(su["q95"]), 3)],
                        "p_positivo": r(su["p_positivo"], 3)}
    mu = jer["mu"]
    return {"ventana_dias": ventana, "metodo": "Serie de casos autocontrolada (Farrington, 1995): cada pago externo se "
            "compara con el resto del periodo del mismo cliente; el efecto de cada ramo se encoge hacia el "
            "promedio de los ramos (modelo jerárquico resuelto en rejilla).",
            "periodo": [start.isoformat(), s.cutoff.isoformat()], "por_ramo": por_ramo,
            "promedio": {"theta": rb(mu, 4), "rr": r(math.exp(mu["media"]), 3),
                         "ic90": [r(math.exp(mu["q05"]), 3), r(math.exp(mu["q95"]), 3)]},
            "tau": rb(jer["tau"], 4), "sensibilidad": sens,
            "total": {"en_ventana": tot_h, "esperados": r(tot_e, 2)}}


# ------------------------------------------------------------------ B3 rasgos y B4 previas
def rasgos_base(s, ids) -> dict:
    from lulo_app.ml import rasgos

    spec = rasgos.ajustar([rasgos.crudos(s.history(cid), s.cutoff, s.cutoff) for cid in ids])
    print(f"  B3 rasgos: {len(spec['vocabulario'])} variables descubiertas · "
          + ", ".join(f"{k} {v}" for k, v in spec["familias"].items()))
    return spec


def exposicion(s, ids, ventana) -> dict:
    """Fracción de clientes con señal ofrecible del ramo que están «en el momento» (evento hace menos de
    `ventana` días), promediada en el corte y en los cinco meses anteriores. La conversión de la campaña es
    un promedio entre clientes en el momento y fuera de él: con esta fracción se separan los dos."""
    from lulo_app.core.features import compute
    from lulo_app.core.schema import RAMOS
    from lulo_app.core.signals import detect
    from lulo_app.ml import motor

    tot = {r: 0 for r in RAMOS}
    enm = {r: 0 for r in RAMOS}
    for k in range(6):
        d = s.cutoff - timedelta(days=30 * k)
        for cid in ids:
            h = s.history(cid)
            sig = detect(compute(h, d, s.cutoff))
            for ramo in RAMOS:
                if sig[ramo].actionable:
                    tot[ramo] += 1
                    enm[ramo] += motor.momento(h, ramo, d, ventana) is not None
    out = {r: {"evaluaciones": tot[r], "en_momento": enm[r], "fraccion": r_(enm[r] / tot[r]) if tot[r] else 0.0}
           for r in RAMOS}
    print("  B2 exposición (clientes con señal que están en el momento): "
          + ", ".join(f"{k} {v['fraccion']:.2f}" for k, v in out.items()))
    return out


def r_(x):
    return r(x, 4)


def previas(emb: dict, mom: dict, n_rasgos: int) -> dict:
    from lulo_app.core import rules
    from lulo_app.core.schema import RAMOS
    from lulo_app.ml import bayes
    from lulo_app.ml import models as ml

    prop = ml.bundle()["propension"]
    por_var = rules.PRIOR_SD_RASGOS_TOTAL / math.sqrt(max(n_rasgos, 1))
    g_sd = r(por_var * math.sqrt(rules.PRIOR_FRACCION_COMUN))
    r_sd = r(por_var * math.sqrt(1 - rules.PRIOR_FRACCION_COMUN))
    out = {"base": {}, "senal_media": {}, "momento": {}, "afinidad": {},
           "global_sd": g_sd, "ramo_sd": r_sd, "cliente_sd": rules.PRIOR_SD_CLIENTE,
           "origen": {
               "base": "B1: conversión de la campaña previa del ramo (Beta-Binomial jerárquico), llevada a «fuera "
                       "del momento» con la exposición de B2 para que el promedio siga siendo el de la campaña",
               "senal_media": f"Hipótesis aprobada en v1: × {_c(rules.PRIOR_SENAL_MEDIA_RATIO)} frente a la señal "
                              f"fuerte, con duda (de × 0,3 a × 1,0 al 90 %)",
               "momento": f"B2: compras externas en los {rules.MOMENTO_VENTANA_DIAS} días después del evento",
               "afinidad": "M1: media 1 si M1 le gana al azar en el ramo; 0 si no",
               "rasgos": f"Sin datos de respuesta: media 0; la duda total de los rasgos ({_c(rules.PRIOR_SD_RASGOS_TOTAL)}) "
                         f"se reparte entre las {n_rasgos} variables: {_c(g_sd)} el peso común y {_c(r_sd)} el del ramo",
               "cliente": f"Media 0 y desviación {_c(rules.PRIOR_SD_CLIENTE)}; aprende con las respuestas del cliente"}}
    for ramo in RAMOS:
        post = emb["por_ramo"][ramo]["posterior"]
        th = mom["por_ramo"][ramo]["theta"]
        rr, pi = math.exp(th["media"]), mom["exposicion"][ramo]["fraccion"]
        # La campaña mezcla clientes en el momento (fracción pi, conversión × rr) y fuera de él: la base del
        # modelo es la conversión fuera del momento, b = p0 / (pi·rr + 1 − pi), y el promedio sigue siendo p0.
        mezcla = pi * rr + 1 - pi
        b, sd_b = post["media"] / mezcla, post["sd"] / mezcla
        z0 = bayes.Phi_inv(b)
        out["base"][ramo] = [r(z0), r(sd_b / bayes.phi(z0))]
        q = rules.PRIOR_SENAL_MEDIA_RATIO * b
        zq = bayes.Phi_inv(q)
        out["senal_media"][ramo] = [r(zq - z0), r(rules.PRIOR_SENAL_LOGSD * q / bayes.phi(zq))]
        q = min(rr * b, 0.95)
        zm = bayes.Phi_inv(q)
        out["momento"][ramo] = [r(zm - z0), r(th["sd"] * q / bayes.phi(zm))]
        out["afinidad"][ramo] = list(rules.PRIOR_AFINIDAD["usable" if prop[ramo]["usable"] else "no_usable"])
    return out


def chequeo_previo(s, ids, sp) -> dict:
    """Chequeo predictivo previo: con las creencias previas (sin respuestas), ¿qué probabilidades de aceptar
    son plausibles para los clientes reales? Se sortean los pesos 20 veces por oferta ofrecible al corte."""
    from lulo_app.core.features import compute
    from lulo_app.core.schema import RAMOS
    from lulo_app.core.signals import detect
    from lulo_app.ml import bayes, motor, rasgos
    from lulo_app.ml import models as ml

    cr = motor.creencias(sp)
    g = bayes.rng("chequeo", SEED)
    ps, medias = [], []
    for cid in ids:
        h = s.history(cid)
        if not h.client.consent:
            continue
        sig = detect(compute(h, s.cutoff, s.cutoff))
        z = rasgos.estandarizar(rasgos.crudos(h, s.cutoff, s.cutoff), sp["rasgos"])
        prop = ml.propensity(h, s.cutoff)
        for ramo in RAMOS:
            if not sig[ramo].actionable:
                continue
            mom = motor.momento(h, ramo, s.cutoff, sp["momento"]["ventana_dias"]) is not None
            x = motor.vector(ramo, z, sig[ramo].strength, mom, motor.afinidad_probit(ramo, prop[ramo]["afinidad_cruda"], sp), cid)
            medias.append(bayes.Phi(cr.lineal(x)[0]))
            for _ in range(20):
                w = cr.muestra(sorted(x), g)
                ps.append(bayes.Phi(sum(v * w[k] for k, v in x.items())))
    ps.sort()
    medias.sort()
    q = lambda v, t: v[min(int(t * len(v)), len(v) - 1)]  # noqa: E731
    out = {"ofertas": len(medias), "sorteos": len(ps),
           "p_sorteada": {k: r(q(ps, t), 4) for k, t in (("p05", .05), ("p25", .25), ("p50", .5), ("p75", .75), ("p95", .95))},
           "p_media": {k: r(q(medias, t), 4) for k, t in (("p05", .05), ("p50", .5), ("p95", .95))}}
    print(f"  Chequeo previo: {out['ofertas']} ofertas al corte; P(acepta) sorteada entre "
          f"{out['p_sorteada']['p05']:.3f} y {out['p_sorteada']['p95']:.3f} (90 %), mediana {out['p_sorteada']['p50']:.3f}")
    return out


# ------------------------------------------------------------------ respuestas (opcional)
CAMPOS_RESPUESTAS = ("cliente_id", "fecha", "ramo", "canal", "resultado")


def cargar_respuestas(path: Path) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    falta = [c for c in CAMPOS_RESPUESTAS if rows and c not in rows[0]]
    if falta:
        raise SystemExit(f"{path}: faltan columnas {falta} (esquema en docs/DATOS_REALES.md)")
    return rows


def ejemplos(s, rows: list[dict], sp: dict) -> list[tuple]:
    """(fecha, cliente, ramo, x, y) por cada respuesta aceptada o rechazada, con los rasgos a esa fecha."""
    from lulo_app.core.features import compute
    from lulo_app.core.schema import RAMOS
    from lulo_app.core.signals import detect
    from lulo_app.ml import models as ml
    from lulo_app.ml import motor, rasgos

    out, cache = [], {}
    for row in rows:
        y = {"aceptada": 1, "rechazada": 0}.get(row["resultado"].strip().lower())
        cid, ramo = row["cliente_id"], row["ramo"]
        if y is None or ramo not in RAMOS or s.history(cid) is None:
            continue
        d = date.fromisoformat(row["fecha"])
        key = (cid, d)
        if key not in cache:
            h = s.history(cid)
            f = compute(h, d, s.cutoff)
            prop = ml.propensity(h, min(d, s.cutoff))
            z = rasgos.estandarizar(rasgos.crudos(h, d, s.cutoff), sp["rasgos"])
            cache[key] = (h, detect(f), prop, z)
        h, sigs, prop, z = cache[key]
        mom = motor.momento(h, ramo, d, sp["momento"]["ventana_dias"]) is not None
        aff = motor.afinidad_probit(ramo, prop[ramo]["afinidad_cruda"], sp)
        out.append((d, cid, ramo, motor.vector(ramo, z, sigs[ramo].strength, mom, aff, cid), y))
    out.sort(key=lambda t: (t[0], t[1], t[2]))
    return out


def _logloss(p: float, y: int) -> float:
    p = min(max(p, 1e-9), 1 - 1e-9)
    return -math.log(p if y else 1 - p)


def aprender(ej: list[tuple], sp: dict):
    """Creencias aprendidas de las respuestas `ej` (en orden de fecha), con la dispersión del apetito entre
    clientes estimada por Bayes empírico (v2.1). Cada respuesta entra a la marginal con el predictor que había
    antes de verla; al final, el apetito de cada cliente cambia su previa de 0,25 a τ̂ (bayes.ApetitoEB)."""
    from lulo_app.core import rules
    from lulo_app.ml import bayes, motor

    cr = motor.creencias(sp)
    eb = bayes.ApetitoEB()
    for _, cid, _, x, y in ej:
        eb.agregar(cid, *cr.sin(x, f"cliente:{cid}"), y)
        cr.actualizar(x, y)
    est = eb.estimar()
    tau = max(est["tau"], rules.APETITO_TAU_MIN)
    sd0 = sp["previas"]["cliente_sd"]
    for k in [k for k in cr.medias if k.startswith("cliente:")]:
        cr.cambiar_previa(k, sd0, tau)
    sp_tau = json.loads(json.dumps(sp))
    sp_tau["previas"]["cliente_sd"] = tau        # los clientes sin respuestas también parten de τ̂
    out = bayes.Creencias(cr.medias, cr.varianzas, motor.creencias(sp_tau).default)
    return out, {**est, "usado": tau}


def validar(ej: list[tuple], sp: dict) -> dict:
    """Campeón (creencias previas) contra retador (previas + 80 % más antiguo de las respuestas, con τ por Bayes
    empírico), medido en el 20 % más reciente. Se promueve si la log-pérdida baja y el intervalo bootstrap al
    95 % no cruza 0."""
    from lulo_app.ml import bayes, motor

    n = len(ej)
    if n < 50:
        return {"respuestas": n, "promovido": False, "motivo": "Menos de 50 respuestas: se mantienen las previas"}
    cut = int(n * 0.8)
    camp = motor.creencias(sp)
    ret, ap = aprender(ej[:cut], sp)
    d, ll0s, ll1s = [], [], []
    for _, _, _, x, y in ej[cut:]:
        a, b = _logloss(camp.predictiva(x), y), _logloss(ret.predictiva(x), y)
        ll0s.append(a)
        ll1s.append(b)
        d.append(b - a)
    g = bayes.rng("bootstrap", SEED)
    means = sorted(sum(d[g.randrange(len(d))] for _ in d) / len(d) for _ in range(N_BOOT))
    lo, hi = means[int(0.025 * N_BOOT)], means[int(0.975 * N_BOOT) - 1]
    md = sum(d) / len(d)
    ok = md < 0 and hi < 0
    return {"respuestas": n, "entrenamiento": cut, "prueba": n - cut, "logloss_campeon": r(sum(ll0s) / len(d), 4),
            "logloss_retador": r(sum(ll1s) / len(d), 4), "diferencia": r(md, 4), "ic95": [r(lo, 4), r(hi, 4)],
            "apetito_entrenamiento": ap, "promovido": ok, "motivo": ("El retador mejora fuera de muestra: se usan las creencias aprendidas" if ok else
                                        "El retador no mejora con claridad: se mantienen las previas")}


# ------------------------------------------------------------------ armado
def datos_usados(s) -> dict:
    f = s.manifest.get("filas", {})
    return {
        "Clientes": {"filas": f.get("clientes"), "usa": "Elegibilidad, capacidad de pago, rasgos de perfil, consentimiento"},
        "Movimientos": {"filas": f.get("movimientos"), "usa": "Señales, momento (B2) y rasgos de conducta y canal"},
        "Cajitas": {"filas": f.get("cajitas"), "usa": "Señales de viaje, mascotas y hogar, momento (B2) y rasgos"},
        "Pagos_Seguros": {"filas": f.get("pagos_seguros"), "usa": "Compras externas con fecha: efecto del momento (B2), exclusiones"},
        "Uso_App": {"filas": f.get("uso_app"), "usa": "Canal (tope, fatiga, latencia, apertura M3) y rasgos de uso"},
        "Seguros_Mensual": {"filas": f.get("seguros_mensual"), "usa": "Valor: prima, comisión, persistencia y cancelación"},
        "Campanas_Previas": {"filas": f.get("campanas_previas"), "usa": "Conversión, interés, cierre y alcance (B1)"},
        "Elegibilidad": {"filas": f.get("elegibilidad"), "usa": "Edad, ocupación y requisito de cada ramo"},
        "Juridico_Entrega": {"filas": f.get("juridico"), "usa": "Qué cuenta como contacto (Ley 2300): push frente a banner"},
    }


def build(respuestas: Path | None) -> dict:
    from lulo_app.core import rules
    from lulo_app.core.store import DATASET, store

    s = store()
    ids = sorted(s.ids("reto"))
    src = s.manifest["fuente"]["sha256"]
    print(f"Base {src[:12]}… · {len(ids)} clientes · corte {s.cutoff}")
    emb = embudo(DATASET)
    mom = momento(s, ids, rules.MOMENTO_VENTANA_DIAS)
    mom["exposicion"] = exposicion(s, ids, rules.MOMENTO_VENTANA_DIAS)
    ras = rasgos_base(s, ids)
    sp = {"version": VERSION, "embudo": emb, "momento": mom, "rasgos": ras,
          "previas": previas(emb, mom, len(ras["vocabulario"])), "pesos": {}, "clientes": {}}
    sp["previas"]["chequeo"] = chequeo_previo(s, ids, sp)
    resp_info = {"respuestas": 0, "archivo": None}
    val = {"respuestas": 0, "promovido": False,
           "motivo": "La base del reto no trae respuestas a ofertas por cliente: el motor decide con las creencias "
                     "previas y aprende en línea de las respuestas de cada sesión"}
    if respuestas:
        rows = cargar_respuestas(respuestas)
        ej = ejemplos(s, rows, sp)
        resp_info = {"respuestas": len(ej), "archivo": respuestas.name,
                     "sha256": hashlib.sha256(respuestas.read_bytes()).hexdigest()}
        val = validar(ej, sp)
        print(f"  Respuestas: {len(ej)} · {val['motivo']}"
              + (f" (log-pérdida {val['logloss_campeon']} → {val['logloss_retador']})" if "logloss_campeon" in val else ""))
        if val["promovido"]:
            cr, ap = aprender(ej, sp)
            sp["previas"]["cliente_sd"] = ap["usado"]
            sp["previas"]["origen"]["cliente"] = (
                f"Bayes empírico con {ap['respuestas']} respuestas de {ap['clientes']} clientes: τ̂ = {_c(ap['tau'])} "
                f"(95 %: {_c(ap['ic95'][0])} a {_c(ap['ic95'][1])}); antes de las respuestas era "
                f"{_c(rules.PRIOR_SD_CLIENTE)}")
            val["apetito"] = ap
            sp["pesos"] = {k: [r(cr.medias[k]), r(math.sqrt(cr.varianzas[k]))] for k in sorted(cr.medias)
                           if not k.startswith("cliente:")}
            sp["clientes"] = {k.split(":", 1)[1]: [r(cr.medias[k]), r(math.sqrt(cr.varianzas[k]))]
                              for k in sorted(cr.medias) if k.startswith("cliente:")}
    sp["validacion"] = val
    sp["entrenado_con"] = {"sha256_base": src, "clientes": len(ids), "corte": s.cutoff.isoformat(),
                           "reglas": rules.VERSION, "semilla": SEED, **resp_info}
    sp["datos"] = datos_usados(s)
    order = ["version", "entrenado_con", "datos", "embudo", "momento", "rasgos", "previas", "validacion", "pesos", "clientes"]
    return {k: sp[k] for k in order}


def dump(model: dict) -> str:
    return json.dumps(model, ensure_ascii=False, indent=1) + "\n"


def reporte(model: dict) -> str:
    """Resumen legible para compartir con el equipo de Lulo (no incluye datos de clientes)."""
    e, m, v = model["embudo"], model["momento"], model["validacion"]
    lines = [f"# Motor bayesiano · {model['version']}", "",
             f"- Base: sha256 {model['entrenado_con']['sha256_base'][:16]}… · {model['entrenado_con']['clientes']} clientes · "
             f"corte {model['entrenado_con']['corte']} · respuestas {model['entrenado_con']['respuestas']}", "",
             "## B1 · Conversión por ramo", "", "| Ramo | Campaña | Cruda | Posterior | IC 90 % |", "|---|---|---:|---:|---|"]
    for k, x in e["por_ramo"].items():
        p = x["posterior"]
        lines.append(f"| {k} | {x['campana'] or '—'} | {x['cruda'] if x['cruda'] is not None else '—'} | "
                     f"{p['media']:.4f} | {p['ic90'][0]:.4f} a {p['ic90'][1]:.4f} |")
    lines += ["", f"## B2 · Momento ({m['ventana_dias']} días)", "", "| Ramo | Pagos | Tras el evento | Esperados | RR | IC 90 % |",
              "|---|---:|---:|---:|---:|---|"]
    for k, x in m["por_ramo"].items():
        lines.append(f"| {k} | {x['pagos']} | {x['en_ventana']} | {x['esperados']} | {x['rr']['media']} | "
                     f"{x['rr']['ic90'][0]} a {x['rr']['ic90'][1]} |")
    lines += ["", "## Validación", "", f"- {v['motivo']}"]
    if "logloss_campeon" in v:
        lines.append(f"- Log-pérdida: campeón {v['logloss_campeon']}, retador {v['logloss_retador']}, "
                     f"diferencia {v['diferencia']} (IC 95 % {v['ic95'][0]} a {v['ic95'][1]})")
    ap = v.get("apetito") or v.get("apetito_entrenamiento")
    if ap and ap.get("tau") is not None:
        from lulo_app.core import rules
        lines.append(f"- Dispersión del apetito entre clientes (Bayes empírico): τ̂ = {ap['tau']} "
                     f"(IC 95 % {ap['ic95'][0]} a {ap['ic95'][1]}) con {ap['respuestas']} respuestas de {ap['clientes']} "
                     f"clientes; sin respuestas se supone {rules.PRIOR_SD_CLIENTE}")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", action="store_true", help="falla si el JSON no coincide con lo que se entrena hoy")
    ap.add_argument("--respuestas", type=Path, help="CSV de respuestas a ofertas (esquema en docs/DATOS_REALES.md)")
    ap.add_argument("--datos", type=Path, help="carpeta con la base en el esquema canónico (por defecto, la del reto)")
    ap.add_argument("--salida", type=Path, help="dónde escribir el JSON (por defecto, lulo_app/ml/motor.json)")
    ap.add_argument("--reporte", type=Path, help="escribe además un resumen en Markdown")
    ap.add_argument("--sin-clientes", action="store_true",
                    help="no guarda el apetito aprendido por cliente (para compartir el JSON sin datos por cliente)")
    a = ap.parse_args()
    if a.datos:
        os.environ["LULO_DATASET"] = str(a.datos.resolve())
    sys.path.insert(0, str(ROOT))
    out = a.salida or OUT
    model = build(a.respuestas)
    if a.sin_clientes:
        model["clientes"] = {}
    text = dump(model)
    if a.check:
        cur = out.read_text(encoding="utf-8") if out.exists() else ""
        if cur != text:
            print(f"{out.name} no coincide con el entrenamiento actual", file=sys.stderr)
            sys.exit(1)
        print(f"{out.name} coincide con el entrenamiento")
        return
    out.write_text(text, encoding="utf-8")
    print(f"Escrito {out} · sha256 {hashlib.sha256(text.encode()).hexdigest()[:12]}")
    if a.reporte:
        a.reporte.write_text(reporte(json.loads(text)), encoding="utf-8")
        print(f"Reporte: {a.reporte}")


if __name__ == "__main__":
    main()
