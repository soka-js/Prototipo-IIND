import pytest

from lulo_app.catalog import soat_quote
from lulo_app.engine import Decision, EventRequest, UnknownClient, handle_event
from lulo_app.report import LoggedResponse, metrics, to_csv


def ev(event, client="sebastian", **ctx):
    return handle_event(EventRequest(event=event, client_id=client, **ctx))


def busy_window():
    return Decision(key="viaje", prio=4, kind="offer", offer="viaje", offerName="Seguro de viaje", ev="x", text="")


def test_offer_shown_with_personalized_text():
    r = ev("nomina")
    assert r.outcome == "shown"
    assert r.decision.offer == "nomina" and r.chain == 2 and r.log is None
    assert r.signal["detected"] is True


def test_consent_control_and_preferences_stop_before_deciding():
    assert ev("nomina", consent=False).outcome == "noconsent"
    assert ev("nomina", control=True).outcome == "control"
    assert ev("viaje", suggestions=False).outcome == "optout"


def test_disbursement_depends_on_existing_protection():
    assert ev("credito").outcome == "ineligible"                  # Sebastián ya tiene pago protegido
    r = ev("credito", client="valentina")                          # Valentina no tiene crédito ni protección
    assert r.outcome == "shown" and r.decision.offer == "pago"
    assert ev("credito", client="valentina", active=["pago"]).outcome == "ineligible"


def test_weak_signals_do_not_trigger_offers():
    assert ev("nomina", client="valentina").outcome == "weak"     # ingreso freelance, no nómina
    r = ev("vehiculo", client="valentina")                         # un peaje aislado y sin carro
    assert r.outcome == "weak" and r.log.tipo == "ctrl"


def test_existing_policies_make_events_ineligible():
    assert ev("nomina", client="andres").outcome == "ineligible"  # ya tiene seguro de nómina
    assert ev("nomina", active=["nomina"]).outcome == "ineligible"


def test_strong_event_works_without_history():
    r = ev("viaje", client="andres")                               # compra de tiquetes: basta el evento
    assert r.outcome == "shown" and "Avianca" in r.decision.text


def test_vehicle_offers_renewal_until_soat_is_renewed():
    r = ev("vehiculo")
    assert r.outcome == "shown" and r.decision.kind == "renew" and "27 días" in r.decision.text
    assert "9 días" in ev("vehiculo", client="andres").decision.text
    assert ev("vehiculo", soat_renewed=True).outcome == "ineligible"


def test_busy_window_queues_by_priority_without_duplicates():
    r1 = ev("vida", window=busy_window())
    assert r1.outcome == "queued" and r1.log.tipo == "hold"
    r2 = ev("nomina", window=busy_window(), queue=r1.queue)
    assert [d.key for d in r2.queue] == ["nomina", "vida"]
    r3 = ev("vida", window=busy_window(), queue=r2.queue)
    assert [d.key for d in r3.queue] == ["nomina", "vida"]


def test_unknown_client():
    with pytest.raises(UnknownClient):
        ev("nomina", client="nadie")


def test_soat_quote_scales_discount_with_notice():
    q30, q7 = soat_quote(745_300, 30), soat_quote(745_300, 7)
    assert q30["total"] == q30["base"] - q30["discount"]
    assert q30["discount"] > q7["discount"] > 0
    with pytest.raises(ValueError):
        soat_quote(745_300, 10)


def test_metrics_and_csv():
    log = [
        LoggedResponse(t="10:00:00", client="Sebastián", ev="e", offer="Seguro de viaje", res="Mostrada en la app", tipo="info"),
        LoggedResponse(t="10:00:05", client="Sebastián", ev="e", offer="Seguro de viaje", res="Aceptó", tipo="ok"),
        LoggedResponse(t="10:01:00", ev="Perfil", offer="Sugerencias", res="Desactivó sugerencias", tipo="harm"),
    ]
    m = metrics(log)
    assert (m["mostradas"], m["aceptadas"], m["dano"]) == (1, 1, 1)
    assert m["por_oferta"]["Seguro de viaje"]["aceptadas"] == 1
    out = to_csv(log)
    assert out.startswith("﻿") and out.count("\n") == 4 and '"No daño"' in out and '"Sebastián"' in out
