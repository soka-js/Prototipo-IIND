"""Cálculo en producción de los modelos entrenados (Python puro, sin scikit-learn).

Lee `modelos.json`, que escribe `scripts/train_models.py`. Cada función devuelve también de dónde sale
el número, para que el panel y el registro puedan mostrarlo.
"""

from __future__ import annotations

import json
import math
from datetime import date
from functools import lru_cache
from pathlib import Path

from ..core.schema import RAMOS, AppUsage, History
from .vector import vector

PATH = Path(__file__).resolve().parent / "modelos.json"


@lru_cache(maxsize=None)
def bundle() -> dict:
    return json.loads(PATH.read_text(encoding="utf-8"))


def _sigmoid(x: float) -> float:
    return 1 / (1 + math.exp(-x)) if x >= 0 else math.exp(x) / (1 + math.exp(x))


def propensity(h: History, as_of: date) -> dict[str, dict]:
    """Probabilidad de tener el ramo, afinidad (probabilidad / tasa base) y qué la empuja."""
    b = bundle()
    lo, hi = b["regla_de_uso"]["afinidad_min"], b["regla_de_uso"]["afinidad_max"]
    v = vector(h, as_of)
    out = {}
    for ramo in RAMOS:
        m = b["propension"][ramo]
        z = m["intercepto"]
        contrib = []
        for n, c in m["coeficientes"].items():
            zz = (v[n] - m["media"][n]) / (m["escala"][n] or 1)
            z += c * zz
            contrib.append((n, c * zz))
        p = _sigmoid(z)
        raw = p / m["tasa_base"] if m["tasa_base"] else 1.0
        aff = min(max(raw, lo), hi) if m["usable"] else 1.0
        drivers = [{"variable": n, "label": b["etiquetas"].get(n, n), "aporte": round(x, 3)}
                   for n, x in sorted(contrib, key=lambda t: -t[1]) if x > 0.02][:3]
        out[ramo] = {"p": round(p, 4), "tasa_base": m["tasa_base"], "afinidad": round(aff, 3),
                     "afinidad_cruda": round(raw, 3), "usable": m["usable"], "auc": m["auc_cv"],
                     "drivers": drivers}
    return out


def segment(h: History, as_of: date) -> dict:
    s = bundle()["segmentos"]
    v = vector(h, as_of)
    z = [(v[n] - mu) / (sd or 1) for n, mu, sd in zip(s["variables"], s["media"], s["escala"])]
    best = min(s["segmentos"], key=lambda g: sum((a - c) ** 2 for a, c in zip(z, g["centro"])))
    return {"id": best["id"], "nombre": best["nombre"], "rasgos": best["rasgos"], "clientes": best["clientes"],
            "ramo_afin": best["ramo_afin"], "lift": best["lift"]}


def push_open(usage: AppUsage) -> dict:
    """Probabilidad de abrir un push con Bayes empírico: (abiertas + α) / (enviadas + α + β)."""
    m = bundle()["respuesta_push"]
    a, b = m["alfa"], m["beta"]
    p = (usage.opened_30d + a) / (usage.notifs_sent_30d + a + b)
    return {"p": round(p, 3), "previa": m["media_previa"], "heterogeneo": m["heterogeneo"],
            "bajo_umbral": p < m["umbral_push"], "umbral": m["umbral_push"], "supuesto": usage.assumed}


def for_client(h: History, as_of: date) -> dict:
    return {"version": bundle()["version"], "propension": propensity(h, as_of), "segmento": segment(h, as_of),
            "push": push_open(h.client.usage)}


def summary() -> dict:
    """Lo que el panel muestra de los modelos: métricas, decisiones de uso y resultados agregados."""
    b = bundle()
    prop = {k: {kk: v[kk] for kk in ("positivos", "tasa_base", "auc_cv", "auc_sd", "p_permutacion", "auc_por_conjunto",
                                     "auc_gbm", "lift_decil_superior", "usable", "motivo", "coeficientes",
                                     "excluidas_por_regla")}
            for k, v in b["propension"].items()}
    for k, v in prop.items():
        v["coeficientes"] = [{"variable": n, "label": b["etiquetas"].get(n, n), "coef": c}
                             for n, c in sorted(v["coeficientes"].items(), key=lambda t: -abs(t[1]))]
    seg = b["segmentos"]
    return {"version": b["version"], "entrenado_con": b["entrenado_con"], "objetivo": b["objetivo"],
            "regla_de_uso": b["regla_de_uso"], "propension": prop,
            "segmentos": {"k": seg["k"], "silueta": seg["silueta"],
                          "grupos": [{kk: g[kk] for kk in ("nombre", "rasgos", "clientes", "tenencia", "lift", "ramo_afin")}
                                     for g in seg["segmentos"]]},
            "respuesta_push": b["respuesta_push"], "demanda": b["demanda"], "momento": b["momento"],
            "piloto": b["piloto"]}
