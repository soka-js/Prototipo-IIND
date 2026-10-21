"""Modelos entrenados (lulo_app/ml): coherencia con la base, uso acotado y sin datos prohibidos."""

import hashlib
import json
from dataclasses import replace
from pathlib import Path

from lulo_app.core import rules
from lulo_app.core.engine import Context, evaluate
from lulo_app.core.schema import RAMOS, History
from lulo_app.core.store import store
from lulo_app.ml import models
from lulo_app.ml.vector import NAMES, vector

ROOT = Path(__file__).resolve().parent.parent


def test_model_was_trained_on_this_dataset():
    b = models.bundle()
    assert b["entrenado_con"]["sha256_base"] == store().manifest["fuente"]["sha256"]
    assert b["entrenado_con"]["clientes"] == 600 and b["entrenado_con"]["corte"] == store().cutoff.isoformat()


def test_gate_only_lets_models_that_beat_chance():
    b = models.bundle()
    for ramo, m in b["propension"].items():
        if m["usable"]:
            assert m["p_permutacion"] < b["regla_de_uso"]["p_max"] and m["auc_cv"] >= b["regla_de_uso"]["auc_min"], ramo
            assert m["coeficientes"], ramo


def test_model_never_uses_the_variables_of_its_own_rule():
    for ramo, m in models.bundle()["propension"].items():
        assert not set(m["coeficientes"]) & set(m["excluidas_por_regla"]), ramo


def test_model_never_uses_variables_that_follow_from_holding_insurance():
    """«Visitas a Seguros» es consecuencia de tener una póliza Lulo y no entra a M1 (decisión de SOKA, 2026-10-20)."""
    b = models.bundle()
    q = b["consecuencia"]
    assert "visitas_seguros" in q["variables"]
    assert q["visitas_media_con_poliza_lulo"] > q["visitas_media_sin_poliza_lulo"]
    for ramo, m in b["propension"].items():
        assert set(m["excluidas_por_consecuencia"]) == set(q["variables"]), ramo
        assert not set(m["coeficientes"]) & set(q["variables"]), ramo
        assert not set(m["media"]) & set(q["variables"]), ramo


def test_affinity_is_bounded_and_neutral_when_unusable():
    s = store()
    lo, hi = models.bundle()["regla_de_uso"]["afinidad_min"], models.bundle()["regla_de_uso"]["afinidad_max"]
    for cid in s.ids("reto")[:120]:
        for ramo, p in models.propensity(s.history(cid), s.cutoff).items():
            assert 0 < p["p"] < 1
            assert lo <= p["afinidad"] <= hi
            if not p["usable"]:
                assert p["afinidad"] == 1.0


def test_expected_value_uses_affinity():
    r = evaluate("C00002", Context(mode="lote"))
    d = r["decision"]
    assert d["ml"] is not None and d["afinidad"] == d["ml"]["afinidad"]
    assert r["rules_version"] == rules.VERSION == "v2.1"


def test_no_consent_means_no_model():
    s = store()
    cid = next(c for c in s.ids("reto") if not s.client(c).consent)
    r = evaluate(cid, Context(mode="lote"))
    assert r["outcome"] == "noconsent" and "ml" not in r


def test_vector_never_reads_merchant_names():
    s = store()
    for pid in ("sebastian", "valentina", "andres"):
        h = s.history(pid)
        bare = History(client=h.client, deposits=list(h.deposits), external=list(h.external),
                       movements=[replace(m, merchant=None, counterparty=None, channel_label=None) for m in h.movements])
        assert vector(h, s.cutoff) == vector(bare, s.cutoff), pid
        assert set(vector(h, s.cutoff)) == set(NAMES)


def test_every_client_gets_a_segment():
    s = store()
    names = {g["nombre"] for g in models.bundle()["segmentos"]["segmentos"]}
    for cid in s.ids():
        assert models.segment(s.history(cid), s.cutoff)["nombre"] in names


def test_summary_is_json_serializable():
    json.dumps(models.summary())
    assert set(models.summary()["propension"]) == set(RAMOS)


def test_demand_includes_renewals():
    for ramo, d in models.bundle()["demanda"].items():
        r = d["renovaciones"]
        assert len(r["historia"]) == 12 and len(r["pronostico"]) == 3, ramo
        assert 0 <= r["tasa_sobre_emitidas"] < 1, ramo


def test_event_timing_is_reported_honestly():
    e = models.bundle()["momento"]["eventos"]
    assert e["ventana_dias"] == 30 and set(e["por_ramo"]) == {"SOAT", "Vida", "Hogar", "Mascotas"}
    assert sum(v["pagos"] for v in e["por_ramo"].values()) == e["total"]["pagos"] == 113
    assert e["hay_efecto"] == (e["total"]["p"] < 0.05)
