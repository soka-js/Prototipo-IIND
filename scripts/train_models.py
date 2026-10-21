"""Entrena los modelos sobre la base del reto y deja sus parámetros en lulo_app/ml/modelos.json.

    python scripts/train_models.py            # entrena, valida y escribe modelos.json
    python scripts/train_models.py --check    # falla si el JSON en el repo no coincide con lo que se entrena hoy

Corre fuera de producción y necesita scikit-learn (requirements-dev.txt). La app solo lee el JSON y
calcula con Python puro, así que en Vercel no se instala nada nuevo.

Modelos:
  M1 propensión por ramo     regresión logística con regularización L1, validada con 5×5 CV y prueba de permutación
  M2 segmentos               k-medias sobre el comportamiento, k elegido por silueta
  M3 respuesta al push       beta-binomial empírico (Bayes empírico) sobre abiertas / enviadas
  M4 demanda por ramo        tendencia lineal de pólizas emitidas y de renovaciones con intervalo de predicción al 80 %
  M5 momento de compra       prueba χ² de los pagos de seguros frente al día de la nómina
  M5b momento por evento     ¿los pagos de seguros caen en los 30 días después del evento que dispara el ramo?
                             (probabilidad esperada por cliente y valor p por simulación)
  M6 tamaño del piloto       clientes por grupo para detectar un aumento de conversión (z de dos proporciones)

Todo es determinista (semilla fija): dos corridas producen el mismo archivo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import warnings
from datetime import date, timedelta
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sklearn.cluster import KMeans  # noqa: E402
from sklearn.ensemble import HistGradientBoostingClassifier  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import roc_auc_score, silhouette_score  # noqa: E402
from sklearn.model_selection import RepeatedStratifiedKFold, StratifiedKFold, cross_val_predict  # noqa: E402
from sklearn.pipeline import make_pipeline  # noqa: E402
from sklearn.preprocessing import StandardScaler  # noqa: E402

from lulo_app.core import catalog  # noqa: E402
from lulo_app.core.schema import RAMOS  # noqa: E402
from lulo_app.core.store import store  # noqa: E402
from lulo_app.ml.vector import BEHAVIOR, LABELS, NAMES, PROFILE, USAGE, holdings, vector  # noqa: E402

OUT = ROOT / "lulo_app" / "ml" / "modelos.json"
SEED = 19
N_PERM = 200
N_BOOT = 100
STABLE_FREQ = 0.8
C_GRID = (0.05, 0.1, 0.2, 0.5)
# Un ramo usa el modelo solo si le gana al azar: p de permutación < 0,05 y AUC promedio ≥ 0,55.
GATE_P, GATE_AUC = 0.05, 0.55
AFFINITY_CLIP = (0.5, 2.0)
SEGMENT_FEATURES = ["n_Peajes", "n_Mascotas", "n_Aerolineas", "n_Hoteles", "meses_fija", "racha_ingreso",
                    "ratio_consumo", "log_gasto_mes", "abonos_Viajes", "abonos_Mascotas", "abonos_Vivienda",
                    "abonos_Emergencias", "sesiones", "visitas_seguros", "credito", "pro"]

warnings.filterwarnings("ignore")


def r(x, n=4):
    return None if x is None else round(float(x), n)


# ------------------------------------------------------------------ datos
def dataset():
    s = store()
    ids = sorted(s.ids("reto"))
    X, Y = [], {k: [] for k in RAMOS}
    for cid in ids:
        h = s.history(cid)
        v = vector(h, s.cutoff)
        X.append([v[n] for n in NAMES])
        hs = holdings(h, s.cutoff)
        for k in RAMOS:
            Y[k].append(int(k in hs))
    return s, ids, np.array(X, dtype=float), {k: np.array(v) for k, v in Y.items()}


def cols(names):
    return [NAMES.index(n) for n in names]


# ------------------------------------------------------------------ M1 propensión
def lr(C):
    return make_pipeline(StandardScaler(), LogisticRegression(penalty="l1", solver="liblinear", C=C, max_iter=5000))


def cv_auc(model, X, y, repeats=5):
    rs = RepeatedStratifiedKFold(n_splits=5, n_repeats=repeats, random_state=SEED)
    aucs = []
    for tr, te in rs.split(X, y):
        m = model.fit(X[tr], y[tr])
        aucs.append(roc_auc_score(y[te], m.predict_proba(X[te])[:, 1]))
    return float(np.mean(aucs)), float(np.std(aucs))


def lift_top_decile(y, p):
    k = max(1, int(round(len(y) * 0.1)))
    top = np.argsort(-p, kind="stable")[:k]
    return float(y[top].mean() / y.mean()) if y.mean() else None


# Variables que la regla del ramo ya usa para su señal: el modelo no las vuelve a contar, así aporta solo lo
# que la regla no ve y no contradice la hipótesis de negocio de la señal.
RULE_FEATURES = {
    "SOAT": ["n_Peajes"], "Vida": ["meses_fija", "racha_ingreso", "meses_ingreso"],
    "Desempleo": ["racha_ingreso", "meses_ingreso"], "Hogar": ["abonos_Vivienda"],
    "Mascotas": ["n_Mascotas", "abonos_Mascotas"], "Viajes": ["n_Aerolineas", "n_Hoteles", "abonos_Viajes"],
}


def propensity(X_all, Y):
    out = {}
    rng = np.random.default_rng(SEED)
    for ramo in RAMOS:
        y = Y[ramo]
        feats = [n for n in NAMES if n not in RULE_FEATURES[ramo]]
        X = X_all[:, cols(feats)]
        # C por validación interna (AUC promedio de 5×3)
        best_c, best = None, -1
        for C in C_GRID:
            a, _ = cv_auc(lr(C), X, y, repeats=3)
            if a > best:
                best_c, best = C, a
        auc, sd = cv_auc(lr(best_c), X, y)
        # Comparación de conjuntos de variables con el mismo C
        sets = {}
        for name, cs in (("perfil", PROFILE), ("comportamiento", BEHAVIOR + USAGE), ("todas", NAMES)):
            cs = [c for c in cs if c in feats]
            sets[name] = r(cv_auc(lr(best_c), X[:, [feats.index(c) for c in cs]], y, repeats=3)[0], 3)
        gbm_auc, _ = cv_auc(HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=150,
                                                           random_state=SEED), X, y, repeats=2)
        # Prueba de permutación: AUC de validación cruzada con etiquetas barajadas
        skf = StratifiedKFold(5, shuffle=True, random_state=SEED)
        obs = roc_auc_score(y, cross_val_predict(lr(best_c), X, y, cv=skf, method="predict_proba")[:, 1])
        null = []
        for _ in range(N_PERM):
            yp = rng.permutation(y)
            null.append(roc_auc_score(yp, cross_val_predict(lr(best_c), X, yp, cv=skf, method="predict_proba")[:, 1]))
        pval = (1 + sum(a >= obs for a in null)) / (N_PERM + 1)
        oof = cross_val_predict(lr(best_c), X, y, cv=skf, method="predict_proba")[:, 1]
        # Selección por estabilidad: solo quedan las variables que el L1 elige en ≥ 80 % de 100 remuestreos.
        freq = np.zeros(len(feats))
        for _ in range(N_BOOT):
            ix = rng.choice(len(y), len(y), replace=True)
            if y[ix].min() == y[ix].max():
                continue
            freq += np.abs(lr(best_c).fit(X[ix], y[ix]).named_steps["logisticregression"].coef_[0]) > 1e-9
        freq /= N_BOOT
        keep = [n for n, f in zip(feats, freq) if f >= STABLE_FREQ]
        sc = StandardScaler().fit(X)
        coefs, icpt = {}, float(np.log(y.mean() / (1 - y.mean())))
        if keep:
            k_ix = [feats.index(n) for n in keep]
            est = LogisticRegression(C=1.0, max_iter=5000).fit(sc.transform(X)[:, k_ix], y)
            coefs = {n: r(c, 5) for n, c in zip(keep, est.coef_[0])}
            icpt = float(est.intercept_[0])
        usable = bool(pval < GATE_P and auc >= GATE_AUC and keep)
        out[ramo] = {
            "positivos": int(y.sum()), "tasa_base": r(y.mean()), "C": best_c,
            "auc_cv": r(auc, 3), "auc_sd": r(sd, 3), "auc_oof": r(obs, 3), "p_permutacion": r(pval, 4),
            "auc_por_conjunto": sets, "auc_gbm": r(gbm_auc, 3), "lift_decil_superior": r(lift_top_decile(y, oof), 2),
            "usable": usable,
            "motivo": ("Le gana al azar: se usa para ajustar el valor esperado" if usable else
                       f"No le gana al azar (AUC {auc:.2f}, p = {pval:.2f}): el motor sigue con la regla"),
            "excluidas_por_regla": RULE_FEATURES[ramo],
            "media": {n: r(v, 6) for n, v in zip(feats, sc.mean_) if n in keep},
            "escala": {n: r(v, 6) for n, v in zip(feats, sc.scale_) if n in keep},
            "intercepto": r(icpt, 5), "coeficientes": coefs,
            "estabilidad": {n: r(f, 2) for n, f in zip(feats, freq) if f >= 0.3},
        }
        print(f"  M1 {ramo:<10} n+={int(y.sum()):>3}  AUC {auc:.3f}±{sd:.3f}  p={pval:.3f}  "
              f"perfil {sets['perfil']}  comport. {sets['comportamiento']}  estables {keep}  → {'usa' if usable else 'regla'}")
    return out


# ------------------------------------------------------------------ M2 segmentos
SEGMENT_NAMES = {
    "n_Peajes": ("En la carretera", "Usa peajes con frecuencia"),
    "n_Aerolineas": ("Viajero", "Compra vuelos y hoteles"), "n_Hoteles": ("Viajero", "Compra vuelos y hoteles"),
    "abonos_Viajes": ("Ahorra para viajar", "Abona a un bolsillo de viajes"),
    "n_Mascotas": ("Con mascota", "Compra en tiendas de mascotas"),
    "abonos_Mascotas": ("Con mascota", "Ahorra para su mascota"),
    "abonos_Vivienda": ("Construye hogar", "Ahorra para vivienda"),
    "abonos_Emergencias": ("Previsivo", "Tiene fondo de emergencias"),
    "meses_fija": ("Apoya a otros", "Envía plata fija a un tercero"),
    "racha_ingreso": ("Nómina estable", "Recibe nómina todos los meses"),
    "ratio_consumo": ("Gasta lo que entra", "Gasta buena parte de su ingreso"),
    "log_gasto_mes": ("Gasto alto", "Gasto mensual alto"),
    "sesiones": ("Usuario activo", "Entra seguido a la app"),
    "visitas_seguros": ("Curioso de seguros", "Visita la sección de seguros"),
    "credito": ("Con crédito", "Tiene un crédito activo"), "pro": ("Pro", "Es cliente Pro"),
}


SEGMENT_LOW = {
    "ratio_consumo": ("Gasto contenido", "Gasta poco frente a su ingreso"),
    "log_gasto_mes": ("Gasto contenido", "Gasto mensual bajo"),
    "abonos_Emergencias": ("Sin colchón", "No ahorra para emergencias"),
    "sesiones": ("Usuario ocasional", "Entra poco a la app"),
    "n_Aerolineas": ("Viaja poco", "Casi no compra vuelos"),
    "meses_fija": ("Sin dependientes a la vista", "No envía plata fija a terceros"),
}


def segments(X, Y, ids):
    Z = X[:, cols(SEGMENT_FEATURES)]
    sc = StandardScaler().fit(Z)
    Zs = sc.transform(Z)
    sil = {}
    for k in range(3, 8):
        km = KMeans(n_clusters=k, n_init=20, random_state=SEED).fit(Zs)
        sil[k] = float(silhouette_score(Zs, km.labels_))
    k = max(sil, key=sil.get)
    km = KMeans(n_clusters=k, n_init=20, random_state=SEED).fit(Zs)
    seg = []
    used = set()
    order = np.argsort(-np.bincount(km.labels_), kind="stable")
    for j in order:
        cen = km.cluster_centers_[j]
        mask = km.labels_ == j
        ranked = sorted(zip(SEGMENT_FEATURES, cen), key=lambda t: -abs(t[1]))
        name = None
        for feat, z in ranked:
            book = SEGMENT_NAMES if z > 0 else SEGMENT_LOW
            if feat in book and book[feat][0] not in used:
                name = book[feat][0]
                break
        name = name or "Uso básico"
        used.add(name)
        traits = [(SEGMENT_NAMES if z > 0 else SEGMENT_LOW)[f][1] for f, z in ranked
                  if abs(z) > 0.35 and f in (SEGMENT_NAMES if z > 0 else SEGMENT_LOW)][:3]
        rates = {ramo: r(Y[ramo][mask].mean(), 3) for ramo in RAMOS}
        lifts = {ramo: r(Y[ramo][mask].mean() / Y[ramo].mean(), 2) for ramo in RAMOS}
        seg.append({"id": int(j), "nombre": name, "rasgos": traits or ["Sin un hábito que sobresalga"],
                    "clientes": int(mask.sum()), "centro": [r(c, 5) for c in cen],
                    "tenencia": rates, "lift": lifts,
                    "ramo_afin": max(lifts, key=lambda q: (lifts[q] or 0))})
        print(f"  M2 segmento {name:<20} {int(mask.sum()):>3} clientes  rasgos: {', '.join(traits[:2])}")
    return {"variables": SEGMENT_FEATURES, "media": [r(v, 6) for v in sc.mean_], "escala": [r(v, 6) for v in sc.scale_],
            "k": k, "silueta": {str(a): r(b, 3) for a, b in sil.items()}, "segmentos": seg}


# ------------------------------------------------------------------ M3 respuesta al push
def push_response(s, ids):
    ab = np.array([s.client(i).usage.opened_30d for i in ids], dtype=float)
    en = np.array([s.client(i).usage.notifs_sent_30d for i in ids], dtype=float)
    m = en > 0
    # Máxima verosimilitud de la beta-binomial sobre una rejilla (sin scipy)
    def ll(a, b):
        k, n = ab[m], en[m]
        return float(np.sum(_lbeta(k + a, n - k + b) - _lbeta(a, b)))
    mean = ab[m].sum() / en[m].sum()
    # Rejilla en (media, concentración): la concentración grande equivale a «todos abren igual».
    grid = [(mu * kap, (1 - mu) * kap) for mu in np.linspace(0.2, 0.5, 61) for kap in np.geomspace(0.5, 5000, 81)]
    a, b = max(grid, key=lambda t: ll(*t))
    rho = 1 / (a + b + 1)
    post = (ab + a) / (en + a + b)
    pooled = ab[m].sum() / en[m].sum()
    thr = 0.20
    print(f"  M3 beta-binomial α={a:.1f} β={b:.1f} correlación intra-cliente ρ={rho:.4f}  media previa {a / (a + b):.3f}  tasa agregada {pooled:.3f}  "
          f"bajo {thr:.0%}: {(post < thr).sum()} clientes")
    return {"alfa": r(a, 2), "beta": r(b, 2), "rho": r(rho, 5),
            "heterogeneo": bool(rho > 0.02), "media_previa": r(a / (a + b)), "tasa_agregada": r(pooled),
            "clientes_con_envios": int(m.sum()), "umbral_push": thr,
            "bajo_umbral": int((post < thr).sum()),
            "percentiles": {str(q): r(np.percentile(post, q), 3) for q in (10, 25, 50, 75, 90)}}


def _lbeta(a, b):
    from math import lgamma
    f = np.vectorize(lambda x, y: lgamma(x) + lgamma(y) - lgamma(x + y))
    return f(a, b)


# ------------------------------------------------------------------ M4 demanda
def _trend(rr, col):
    """Tendencia lineal de una columna mensual con intervalo de predicción al 80 % para los 3 meses siguientes."""
    y = np.array([int(x[col]) for x in rr], dtype=float)
    t = np.arange(len(y), dtype=float)
    A = np.vstack([np.ones_like(t), t]).T
    beta, res, *_ = np.linalg.lstsq(A, y, rcond=None)
    n, p = len(y), 2
    yhat = A @ beta
    s2 = float(np.sum((y - yhat) ** 2) / (n - p))
    XtXi = np.linalg.inv(A.T @ A)
    se_slope = math.sqrt(s2 * XtXi[1, 1])
    tcrit80, tcrit95 = 1.372, 2.228  # t de Student con 10 grados de libertad
    fc = []
    last = rr[-1]["mes"]
    yy, mm = int(last[:4]), int(last[5:])
    for h in range(1, 4):
        mm += 1
        if mm > 12:
            yy, mm = yy + 1, 1
        x0 = np.array([1.0, n - 1 + h])
        pred = float(x0 @ beta)
        se = math.sqrt(s2 * (1 + x0 @ XtXi @ x0))
        fc.append({"mes": f"{yy:04d}-{mm:02d}", "pronostico": round(pred), "bajo": round(pred - tcrit80 * se),
                   "alto": round(pred + tcrit80 * se)})
    sig = bool(se_slope > 0 and abs(beta[1]) > tcrit95 * se_slope)
    return y, beta, sig, fc


def demand():
    import csv
    rows = list(csv.DictReader(open(ROOT / "lulo_app/dataset/seguros_mensual.csv", encoding="utf-8")))
    out = {}
    for ramo in RAMOS:
        rr = sorted([x for x in rows if x["ramo"] == ramo], key=lambda x: x["mes"])
        y, beta, sig, fc = _trend(rr, "polizas_emitidas")
        out[ramo] = {"historia": [{"mes": x["mes"], "polizas": int(x["polizas_emitidas"])} for x in rr],
                     "pendiente_mes": r(beta[1], 2), "pendiente_significativa": bool(sig),
                     "promedio": r(y.mean(), 1), "pronostico": fc}
        # Renovaciones (dato 1.1 de la solicitud): misma tendencia y tasa de renovación sobre las emitidas.
        yr, br, sr, fr = _trend(rr, "renovaciones")
        out[ramo]["renovaciones"] = {"historia": [{"mes": x["mes"], "polizas": int(x["renovaciones"])} for x in rr],
                                     "pendiente_mes": r(br[1], 2), "pendiente_significativa": bool(sr),
                                     "promedio": r(yr.mean(), 1), "pronostico": fr,
                                     "tasa_sobre_emitidas": r(yr.sum() / y.sum(), 3)}
        print(f"  M4 {ramo:<10} promedio {y.mean():6.1f}  pendiente {beta[1]:+.2f}/mes "
              f"{'(significativa)' if sig else '(no significativa)'}  {fc[0]['mes']}: {fc[0]['pronostico']}  "
              f"· renovaciones {yr.mean():5.1f}/mes ({yr.sum() / y.sum():.0%} de las emitidas), {fr[0]['mes']}: {fr[0]['pronostico']}")
    return out


# ------------------------------------------------------------------ M5 momento de compra
def timing(s, ids):
    bins = [(0, 7), (8, 14), (15, 21), (22, 31)]
    obs = [0] * len(bins)
    n_sin = 0
    for cid in ids:
        h = s.history(cid)
        pays = [m.date for m in h.movements if m.category == "Abono recurrente"]
        for e in h.external:
            prev = [d for d in pays if d <= e.paid_on]
            if not prev:
                n_sin += 1
                continue
            d = min((e.paid_on - max(prev)).days, 31)
            for i, (a, b) in enumerate(bins):
                if a <= d <= b:
                    obs[i] += 1
                    break
    n = sum(obs)
    widths = [b - a + 1 for a, b in bins]
    exp = [n * w / sum(widths) for w in widths]
    chi2 = sum((o - e) ** 2 / e for o, e in zip(obs, exp))
    crit = 7.815  # χ² con 3 grados de libertad, 5 %
    print(f"  M5 pagos con nómina previa {n}  χ²={chi2:.2f} (crítico {crit})  "
          f"{'hay momento preferido' if chi2 > crit else 'sin momento preferido del mes'}")
    return {"pagos_analizados": n, "pagos_sin_nomina_previa": n_sin,
            "ventanas": [{"dias": f"{a}-{b}", "observados": o, "esperados": r(e, 1)} for (a, b), o, e in zip(bins, obs, exp)],
            "chi2": r(chi2, 3), "critico_5pct": crit, "hay_momento": bool(chi2 > crit)}


# ------------------------------------------------------------------ M5b momento por evento
# Evento que dispara cada ramo en el motor y que se puede ver en la base antes de un pago externo.
# Viajes y Desempleo no tienen pagos externos en la base, así que no se pueden probar.
EVENT_WINDOW = 30          # días: igual a la anticipación del recordatorio del SOAT y a la espera entre ofertas
EVENT_SIMS = 20000
EVENT_LABEL = {"SOAT": "peaje", "Vida": "transferencia fija a un tercero", "Hogar": "abono al bolsillo de vivienda",
               "Mascotas": "compra en tienda de mascotas o abono al bolsillo de mascotas"}


def _event_dates(h, ramo):
    if ramo == "SOAT":
        return [m.date for m in h.movements if m.category == "Peajes"]
    if ramo == "Vida":
        return [m.date for m in h.movements if m.category == "Transferencia fija tercero"]
    if ramo == "Hogar":
        return [d.date for d in h.deposits if d.pocket_type == "Vivienda"]
    if ramo == "Mascotas":
        return ([m.date for m in h.movements if m.category == "Mascotas"]
                + [d.date for d in h.deposits if d.pocket_type == "Mascotas"])
    return []


def event_timing(s, ids):
    """¿Se paga un seguro externo en los 30 días siguientes al evento que el motor usa para ofrecerlo?

    Para cada pago se calcula qué fracción de los días del periodo cae dentro de 30 días después de un evento
    del mismo cliente: es la probabilidad de «acertar» si el pago fuera en un día al azar. La suma de esas
    probabilidades es lo esperado; el valor p sale de simular los pagos al azar (Poisson-binomial)."""
    start = min(m.date for cid in ids for m in s.history(cid).movements)
    days = np.array([(start + timedelta(i)).toordinal() for i in range((s.cutoff - start).days + 1)])
    rng = np.random.default_rng(SEED)
    out, all_p, all_hit = {}, [], 0
    for ramo in EVENT_LABEL:
        probs, hits, sin_evento = [], 0, 0
        for cid in ids:
            h = s.history(cid)
            for e in h.external:
                if e.ramo != ramo or e.paid_on > s.cutoff:
                    continue
                ev = np.array(sorted(d.toordinal() for d in _event_dates(h, ramo) if d <= s.cutoff))
                if ev.size == 0:
                    sin_evento += 1
                    probs.append(0.0)
                    continue
                gap = days[:, None] - ev[None, :]
                probs.append(float(((gap >= 0) & (gap < EVENT_WINDOW)).any(axis=1).mean()))
                g = e.paid_on.toordinal() - ev
                hits += int(((g >= 0) & (g < EVENT_WINDOW)).any())
        pr = np.array(probs)
        sims = (rng.random((EVENT_SIMS, pr.size)) < pr).sum(axis=1)
        exp = float(pr.sum())
        pval = float((sims >= hits).mean())
        out[ramo] = {"evento": EVENT_LABEL[ramo], "pagos": int(pr.size), "pagos_sin_evento": sin_evento,
                     "observados": hits, "esperados": r(exp, 1), "razon": r(hits / exp, 2) if exp > 0 else None,
                     "p": r(pval, 3)}
        all_p.extend(probs)
        all_hit += hits
        print(f"  M5b {ramo:<9} {pr.size:3d} pagos ({sin_evento} sin el evento en el año): {hits} tras el evento, "
              f"esperados {exp:.1f}, p = {pval:.3f}")
    pr = np.array(all_p)
    sims = (rng.random((EVENT_SIMS, pr.size)) < pr).sum(axis=1)
    exp = float(pr.sum())
    pval = float((sims >= all_hit).mean())
    print(f"  M5b total     {pr.size:3d} pagos: {all_hit} tras el evento, esperados {exp:.1f}, p = {pval:.3f}")
    return {"ventana_dias": EVENT_WINDOW, "simulaciones": EVENT_SIMS, "por_ramo": out,
            "total": {"pagos": int(pr.size), "observados": all_hit, "esperados": r(exp, 1),
                      "razon": r(all_hit / exp, 2) if exp > 0 else None, "p": r(pval, 3)},
            "hay_efecto": bool(pval < 0.05)}


# ------------------------------------------------------------------ M6 tamaño del piloto
def sample_size(p, rel_lift, alpha_z=1.959964, power_z=0.841621):
    p2 = p * (1 + rel_lift)
    pbar = (p + p2) / 2
    num = (alpha_z * math.sqrt(2 * pbar * (1 - pbar)) + power_z * math.sqrt(p * (1 - p) + p2 * (1 - p2))) ** 2
    return math.ceil(num / (p2 - p) ** 2)


def pilot():
    out = {}
    for ramo, prod in catalog.products().items():
        if prod.prior is None or prod.source != "reto":
            continue
        out[ramo] = {"conversion_base": r(prod.prior), **{f"lift_{int(l * 100)}": sample_size(prod.prior, l)
                                                          for l in (0.2, 0.5, 1.0)}}
    print("  M6 clientes por grupo para detectar +50 %: " + ", ".join(f"{k} {v['lift_50']:,}" for k, v in out.items()))
    return out


# ------------------------------------------------------------------ main
def build():
    s, ids, X, Y = dataset()
    src = s.manifest["fuente"]["sha256"]
    print(f"Base {src[:12]}… · {len(ids)} clientes · corte {s.cutoff} · {len(NAMES)} variables")
    model = {
        "version": "ml-1.0", "entrenado_con": {"sha256_base": src, "clientes": len(ids), "corte": s.cutoff.isoformat(),
                                              "variables": len(NAMES), "semilla": SEED, "permutaciones": N_PERM},
        "etiquetas": {n: LABELS.get(n, n) for n in NAMES},
        "objetivo": "Tenencia del ramo: con Lulo (Clientes.seguros_vigentes) o pagado a otra aseguradora (Pagos_Seguros)",
        "regla_de_uso": {"p_max": GATE_P, "auc_min": GATE_AUC, "afinidad_min": AFFINITY_CLIP[0],
                         "afinidad_max": AFFINITY_CLIP[1]},
        "propension": propensity(X, Y),
        "segmentos": segments(X, Y, ids),
        "respuesta_push": push_response(s, ids),
        "demanda": demand(),
        "momento": {**timing(s, ids), "eventos": event_timing(s, ids)},
        "piloto": pilot(),
    }
    return model


def dump(model) -> str:
    return json.dumps(model, ensure_ascii=False, indent=1, sort_keys=False) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    text = dump(build())
    if a.check:
        cur = OUT.read_text(encoding="utf-8") if OUT.exists() else ""
        if cur != text:
            print("modelos.json no coincide con el entrenamiento actual", file=sys.stderr)
            sys.exit(1)
        print("modelos.json coincide con el entrenamiento")
        return
    OUT.write_text(text, encoding="utf-8")
    print(f"Escrito {OUT.relative_to(ROOT)} · sha256 {hashlib.sha256(text.encode()).hexdigest()[:12]}")


if __name__ == "__main__":
    main()
