"""Motor v3 sobre la base del reto y los personajes."""

from dataclasses import replace
from datetime import date

import pytest

from lulo_app.core import backtest, catalog, engine, experiment, rules
from lulo_app.core.engine import Context, Event, OfferLog, evaluate, on_event
from lulo_app.core.features import compute, streak
from lulo_app.core.schema import History
from lulo_app.core.signals import detect
from lulo_app.core.store import store

CUTOFF = date(2026, 10, 8)


def cand(r, ramo):
    return next(x for x in r["candidates"] if x["ramo"] == ramo)


# --------------------------------------------------------------------------- datos y catálogo
def test_store_loads_base_and_personas():
    s = store()
    assert s.cutoff == CUTOFF and s.start == date(2025, 11, 1)
    assert len(s.ids("reto")) == 600 and set(s.ids("persona")) == {"sebastian", "valentina", "andres"}
    assert sum(len(s.history(c).movements) for c in s.ids("reto")) == 20473
    # Ningún dato posterior al corte entra al motor.
    assert max(m.date for c in s.ids("reto") for m in s.history(c).movements) <= CUTOFF


def test_catalog_numbers_come_from_the_base():
    p = catalog.products()
    assert p["Vida"].commission_12m == round(28500 * 0.32 * (6 * (1 + 0.91) / 2 + 6 * (0.91 + 0.83) / 2))
    assert p["SOAT"].commission_12m == round(365000 * 0.085)
    assert p["SOAT"].prior == pytest.approx(178 / 1380, abs=1e-4)          # ventas / impactados, no / elegibles
    assert p["Hogar"].prior == min(p[r].prior for r in ("SOAT", "Vida", "Desempleo", "Mascotas", "Viajes"))
    assert "supuesto" in p["Hogar"].prior_source
    assert p["Pago protegido"].expected_value("fuerte") is None and p["Pago protegido"].source == "prototipo"


def test_streak_counts_consecutive_months_only():
    assert streak(["2026-01", "2026-02", "2026-04", "2026-05", "2026-06"]) == 3
    assert streak(["2025-11", "2025-12", "2026-01"]) == 3
    assert streak([]) == 0


# --------------------------------------------------------------------------- personajes
def test_personas_keep_their_story_with_shifted_dates():
    seb = evaluate("sebastian", Context(mode="lote"))
    assert cand(seb, "SOAT")["signal"]["metrics"]["days"] == 27          # igual que en la presentación
    assert cand(seb, "Vida")["strength"] == "fuerte"                       # Laura + nómina
    assert cand(seb, "Desempleo")["status"] == "weak"                      # 3 de 6 abonos: aún no acredita antigüedad
    assert cand(seb, "Pago protegido")["status"] == "none"
    andres = evaluate("andres", Context(mode="lote"))
    assert cand(andres, "SOAT")["signal"]["metrics"]["days"] == 9
    assert cand(andres, "Desempleo")["status"] == "has"                    # ya tiene seguro de nómina (Chubb)
    val = evaluate("valentina", Context(mode="lote"))
    assert cand(val, "Viajes")["strength"] == "fuerte"                     # tiquete + bolsillo Perú
    assert cand(val, "Desempleo")["status"] == "none"                      # independiente: sin abonos recurrentes


def test_decisions_never_read_merchant_names():
    """Los personajes conservan comercio y tercero solo para mostrarlos: sin ellos, el motor decide igual."""
    s = store()
    for pid in ("sebastian", "valentina", "andres"):
        h = s.history(pid)
        bare = History(client=h.client, deposits=list(h.deposits), external=list(h.external),
                       movements=[replace(m, merchant=None, counterparty=None, channel_label=None) for m in h.movements])
        a = detect(compute(h, CUTOFF, CUTOFF))
        b = detect(compute(bare, CUTOFF, CUTOFF))
        assert {k: (v.strength, v.kind) for k, v in a.items()} == {k: (v.strength, v.kind) for k, v in b.items()}, pid


def test_vida_grupo_deudor_is_not_voluntary_life():
    seb = store().client("sebastian")
    assert seb.holds("Vida grupo deudor") and not seb.holds("Vida")


# --------------------------------------------------------------------------- reglas sobre la base
def test_open_age_band_is_excluded_from_capped_ramos():
    r = evaluate("C00003", Context(mode="lote"))
    assert store().client("C00003").age_band == "56+"
    assert cand(r, "Desempleo")["status"] == "ineligible"
    assert "Edad por confirmar" in cand(r, "Desempleo")["reason"]


def test_external_policies():
    s = store()
    # SOAT pagado por fuera y vigente: no se ofrece como nuevo; se recuerda al acercarse el vencimiento.
    ext = [c for c in s.ids("reto") if any(e.ramo == "SOAT" for e in s.history(c).external)]
    soonest = min(ext, key=lambda c: s.history(c).external[0].expires_on)
    exp = s.history(soonest).external[0].expires_on
    far = evaluate(soonest, Context(mode="lote"))
    assert cand(far, "SOAT")["status"] in ("weak", "external")
    near = evaluate(soonest, Context(mode="lote", as_of=date.fromordinal(exp.toordinal() - 20)))
    assert cand(near, "SOAT")["kind"] == "captura" and cand(near, "SOAT")["strength"] == "fuerte"
    assert near["data_until"] == CUTOFF.isoformat()           # el comportamiento se congela en el corte


def test_consent_stops_before_reading_data():
    no = [c for c in store().ids("reto") if not store().client(c).consent]
    assert len(no) == 84
    r = evaluate(no[0], Context(mode="lote"))
    assert r["outcome"] == "noconsent" and r["features"] is None and r["chain"] == 0


def test_control_assignment_is_deterministic_and_close_to_ten_percent():
    ids = store().ids("reto")
    ctrl = [c for c in ids if experiment.group(c, "reto")["group"] == "control"]
    assert ctrl == [c for c in ids if experiment.bucket(c) < rules.CONTROL_PCT]
    assert 40 <= len(ctrl) <= 80
    assert experiment.group("sebastian", "persona")["group"] == "tratamiento"


# --------------------------------------------------------------------------- tiempo real
def test_events_feed_their_ramo():
    r = on_event("sebastian", Event(type="transferencia_fija", amount=450_000, counterparty="Laura M."))
    assert r["outcome"] == "shown" and r["evaluation"]["decision"]["ramo"] == "Vida"
    assert "Laura M." in r["evaluation"]["decision"]["why"]
    assert on_event("sebastian", Event(type="transferencia", amount=20_000))["outcome"] == "none"
    assert on_event("sebastian", Event(type="desembolso", amount=9_000_000))["outcome"] == "has"
    v = on_event("valentina", Event(type="desembolso", amount=5_000_000))
    assert v["outcome"] == "shown" and v["evaluation"]["decision"]["ramo"] == "Pago protegido"
    w = on_event("valentina", Event(type="abono_nomina", amount=2_400_000))
    assert w["outcome"] == "weak" and "Empleado" in w["message"]


def test_window_queue_control_optout_and_consent():
    busy = Context(window={"ramo": "Vida", "title": "Seguro de vida"})
    q = on_event("sebastian", Event(type="abono_bolsillo", amount=300_000, pocket_type="Viajes"), busy)
    assert q["outcome"] == "queued" and q["evaluation"]["queue"][0]["ramo"] == "Viajes"
    ev = Event(type="transferencia_fija", amount=450_000)
    assert on_event("sebastian", ev, Context(control=True))["outcome"] == "control"
    assert on_event("sebastian", ev, Context(suggestions=False))["outcome"] == "optout"
    assert on_event("sebastian", ev, Context(consent=False))["outcome"] == "noconsent"


def test_cooldown_and_accepted():
    ev = Event(type="transferencia_fija", amount=450_000)
    seen = Context(history=[OfferLog(ramo="Vida", date=CUTOFF, result="rechazada")])
    assert on_event("sebastian", ev, seen)["outcome"] == "cooldown"
    assert on_event("sebastian", ev, Context(accepted=["Vida"]))["outcome"] == "has"


def test_contact_cap_moves_to_banner():
    # Andrés ya usó 3 de 4 contactos (supuesto); con un push más en la sesión llega al tope.
    ev = Event(type="compra_aerolinea", amount=1_640_000, merchant="Avianca")
    assert on_event("andres", ev)["outcome"] == "shown"
    full = Context(history=[OfferLog(ramo="SOAT", date=CUTOFF, result="mostrada", channel="push")])
    r = on_event("andres", ev, full)
    assert r["outcome"] == "banner" and "Tope de contactos" in r["evaluation"]["channel"]["reason"]


def test_deadline_first_and_push_spacing():
    # v1.1: el SOAT de Andrés vence en 9 días y gana la ventana aunque Vida tenga más valor esperado.
    r = evaluate("andres", Context(mode="lote"))
    assert r["decision"]["ramo"] == "SOAT" and r["decision"]["deadline"]
    assert cand(r, "Vida")["ev"] > cand(r, "SOAT")["ev"]
    # Un push hace 3 días: el siguiente va como banner aunque queden contactos.
    recent = Context(history=[OfferLog(ramo="Viajes", date=date(2026, 10, 5), result="mostrada", channel="push")])
    out = on_event("sebastian", Event(type="transferencia_fija", amount=450_000), recent)
    assert out["outcome"] == "banner" and "Espaciado" in out["evaluation"]["channel"]["reason"]


def test_upcoming_triggers():
    seb = engine.upcoming("sebastian")
    assert seb[0]["ramo"] == "Desempleo" and seb[0]["missing"] == 3
    assert engine.upcoming("andres") == []                      # SOAT dentro de la ventana: ya es un disparo de hoy


def test_renewed_soat_is_not_offered_again():
    assert cand(evaluate("andres", Context(mode="lote", renewed=["SOAT"])), "SOAT")["status"] == "has"


# --------------------------------------------------------------------------- lote y backtest
def test_campaign_respects_gates():
    out = engine.campaign()
    rows = {r["client_id"]: r for r in out["rows"]}
    s = store()
    for cid, r in rows.items():
        c = s.client(cid)
        if not c.consent:
            assert r["outcome"] == "noconsent"
        if r["outcome"] in ("shown", "banner"):
            assert not c.holds(r["ramo"]) and r["group"] == "tratamiento"
    assert out["summary"]["by_outcome"]["noconsent"] == 84


def test_backtest_has_zero_violations():
    r = backtest.run(every=14)
    assert r["violations"] == []
    assert r["max_push_30d"] <= 4 and r["offers"] > 0 and r["control"] > 0
