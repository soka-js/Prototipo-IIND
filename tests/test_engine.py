from lulo_app.engine import Decision, EventRequest, handle_event, soat_quote
from lulo_app.report import LoggedResponse, metrics, to_csv


def ev(event, **ctx):
    return handle_event(EventRequest(event=event, **ctx))


def busy_window():
    return Decision(key="viaje", prio=4, kind="offer", offerName="Seguro de viaje", ev="x", text="")


def test_offer_shown_when_window_free():
    r = ev("nomina")
    assert r.outcome == "shown"
    assert r.decision.offerName == "Seguro de nómina"
    assert r.chain == 2 and r.log is None


def test_control_group_never_shows():
    r = ev("nomina", control=True)
    assert r.outcome == "control" and r.decision is None
    assert r.log.tipo == "ctrl"


def test_suggestions_off_never_shows():
    assert ev("viaje", suggestions=False).outcome == "optout"


def test_credit_disbursement_is_ineligible_because_payment_protection_exists():
    r = ev("credito")
    assert r.outcome == "ineligible"
    assert "ya tiene la cobertura" in r.log.res


def test_already_active_coverage_is_ineligible():
    assert ev("nomina", active=["nomina"]).outcome == "ineligible"


def test_vehicle_offers_renewal_until_soat_is_renewed():
    r = ev("vehiculo", soat_days=27)
    assert r.outcome == "shown" and r.decision.kind == "renew"
    assert "27 días" in r.decision.text
    assert ev("vehiculo", soat_renewed=True).outcome == "ineligible"


def test_busy_window_queues_by_priority_without_duplicates():
    r1 = ev("vida", window=busy_window())
    assert r1.outcome == "queued" and r1.log.tipo == "hold"
    r2 = ev("nomina", window=busy_window(), queue=r1.queue)
    assert [d.key for d in r2.queue] == ["nomina", "vida"]  # prioridad 3 antes que 5
    r3 = ev("vida", window=busy_window(), queue=r2.queue)
    assert [d.key for d in r3.queue] == ["nomina", "vida"]


def test_soat_quote_scales_discount_with_notice():
    q30, q7 = soat_quote(30), soat_quote(7)
    assert q30["total"] == q30["base"] - q30["discount"]
    assert q30["discount"] > q7["discount"] > 0


def test_metrics_and_csv():
    log = [
        LoggedResponse(t="10:00:00", ev="e", offer="Seguro de viaje", res="Mostrada en la app", tipo="info"),
        LoggedResponse(t="10:00:05", ev="e", offer="Seguro de viaje", res="Aceptó", tipo="ok"),
        LoggedResponse(t="10:01:00", ev="Perfil", offer="Sugerencias", res="Desactivó sugerencias", tipo="harm"),
    ]
    m = metrics(log)
    assert (m["mostradas"], m["aceptadas"], m["dano"]) == (1, 1, 1)
    assert m["por_oferta"]["Seguro de viaje"]["aceptadas"] == 1
    out = to_csv(log)
    assert out.startswith("﻿") and out.count("\n") == 4 and '"No daño"' in out
