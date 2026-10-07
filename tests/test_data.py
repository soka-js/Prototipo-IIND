"""El simulador, las señales y Tu año: datos reproducibles y coherentes entre sí."""

from lulo_app import simulator
from lulo_app.clients import Action, bootstrap, find_movements, movement_detail, run_action
from lulo_app.signals import for_persona as signals
from lulo_app.year import chapters


def test_simulation_is_deterministic_and_balanced():
    for p in simulator.personas().values():
        again = {"sebastian": simulator._sebastian, "valentina": simulator._valentina, "andres": simulator._andres}[p.id]()
        assert [t["a"] for t in again.txs] == [t["a"] for t in p.txs]
        opening = p.balance - sum(t["a"] for t in p.txs)
        assert opening >= 0, f"{p.id} arranca con saldo negativo"
        assert all(simulator.PERIOD_START.isoformat() <= t["date"] <= simulator.TODAY.isoformat() for t in p.txs)
        assert len({t["id"] for t in p.txs}) == len(p.txs)


def test_sebastian_matches_the_presentation():
    p = simulator.get("sebastian")
    assert len(p.txs) == 1284
    s = signals("sebastian")
    assert (s["vehiculo"]["metrics"]["tolls"], s["vehiculo"]["metrics"]["fuel"]) == (46, 31)
    assert s["nomina"]["metrics"]["streak"] == 3
    assert s["viaje"]["metrics"]["total"] == 1_200_000
    assert s["vida"]["metrics"]["total"] == 1_800_000
    assert s["credito"]["metrics"]["paid"] == 3
    by_id = {c["id"]: c for c in chapters("sebastian")}
    assert by_id["intro"]["stats"][0]["big"] == "1.284"
    assert by_id["dinero"]["stats"][0]["big"] == "$33 M"


def test_chapters_follow_signals():
    ids = lambda pid: [c["id"] for c in chapters(pid)]
    assert ids("sebastian") == ["intro", "dinero", "ingreso", "carro", "viajes", "gente", "credito", "gustos", "cierre"]
    assert "carro" not in ids("valentina") and "credito" not in ids("valentina")
    assert next(c for c in chapters("valentina") if c["id"] == "ingreso")["name"] == "Tu trabajo"
    assert "viajes" not in ids("andres")


def test_movement_search_and_detail():
    r = find_movements("sebastian", q="peaje andes")
    assert r["total"] > 0 and all("Andes" in t["n"] for t in r["items"])
    r = find_movements("sebastian", group="ingresos", limit=5)
    assert len(r["items"]) == 5 and all(t["a"] > 0 for t in r["items"])
    toll = find_movements("sebastian", q="peaje", limit=1)["items"][0]
    d = movement_detail("sebastian", toll["id"])
    assert d["signal"]["key"] == "vehiculo" and d["same_count"] > 1


def test_actions_become_signals():
    r = run_action("sebastian", Action(type="transfer", target="laura", amount=450_000))
    assert r.event == "vida" and r.movement["a"] == -450_000
    assert run_action("sebastian", Action(type="transfer", target="juan", amount=20_000)).event is None
    assert run_action("valentina", Action(type="cajita", target="peru", amount=300_000)).event == "viaje"
    assert run_action("andres", Action(type="cajita", target="matricula", amount=300_000)).event is None
    assert run_action("valentina", Action(type="desembolso", amount=3_000_000)).event == "credito"


def test_bootstrap_has_everything_the_app_needs():
    b = bootstrap("andres")
    assert b["car"]["days"] == 9 and b["credit"]["paid"] == 10
    assert set(b["offers"]) == {"nomina", "viaje", "vida", "pago"}
    assert len(b["recent"]) == 40 and b["movCount"] == len(simulator.get("andres").txs)
