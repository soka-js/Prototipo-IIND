"""API v3: el motor real expuesto para la app y el panel."""

from fastapi.testclient import TestClient

from lulo_app.main import app

client = TestClient(app)


def test_meta():
    m = client.get("/api/v3/meta").json()
    assert m["cutoff"] == "2026-10-08" and m["rules_version"] == "v1.1"
    assert m["clients"] == {"reto": 600, "persona": 3}
    assert {e["type"] for e in m["events"]} >= {"transferencia_fija", "desembolso", "abono_bolsillo"}


def test_bootstrap_for_persona_and_base_client():
    seb = client.get("/api/v3/clients/sebastian").json()
    assert seb["movCount"] == 1284 and seb["car"]["days"] == 27
    ch = {c["id"]: c for c in seb["chapters"]}
    assert ch["dinero"]["stats"][0]["big"] == "$33 M"                    # la cifra de la presentación
    assert ch["ingreso"]["protect"]["state"] == "soon"                    # le faltan 3 abonos
    c2 = client.get("/api/v3/clients/C00002").json()
    assert c2["client"]["source"] == "reto" and c2["evaluation"]["decision"]["ramo"] == "Desempleo"
    assert client.get("/api/v3/clients/C99999").status_code == 404
    assert client.get("/api/v3/clients/C00002?as_of=nope").status_code == 422


def test_movements_paging_and_detail():
    r = client.get("/api/v3/clients/C00002/movements", params={"group": "ingresos", "limit": 3}).json()
    assert r["total"] == 11 and all(x["amount"] > 0 for x in r["items"])
    d = client.get(f"/api/v3/clients/C00002/movements/{r['items'][0]['id']}").json()
    assert d["signal"]["ramo"] == "Desempleo"
    assert client.get("/api/v3/clients/C00002/movements/nope").status_code == 404


def test_events_and_evaluate():
    body = {"event": {"type": "transferencia_fija", "amount": 450000, "counterparty": "Laura M."}, "context": {}}
    r = client.post("/api/v3/clients/sebastian/events", json=body).json()
    assert r["outcome"] == "shown" and r["created"]["category"] == "Transferencia fija tercero"
    bad = {"event": {"type": "abono_bolsillo", "amount": 1000}, "context": {}}
    assert client.post("/api/v3/clients/sebastian/events", json=bad).status_code == 422
    e = client.post("/api/v3/clients/andres/evaluate", json={"mode": "lote"}).json()
    assert e["decision"]["ramo"] == "SOAT"


def test_explorer_campaign_and_backtest():
    ex = client.get("/api/v3/clients", params={"outcome": "noconsent", "limit": 5}).json()
    assert ex["total"] == 84 and len(ex["items"]) == 5
    assert client.get("/api/v3/clients", params={"q": "sebas"}).json()["items"][0]["client_id"] == "sebastian"
    camp = client.get("/api/v3/campaign").json()
    assert camp["summary"]["clients"] == 600
    csv = client.get("/api/v3/campaign.csv")
    assert csv.status_code == 200 and csv.content.startswith("﻿".encode())
    bt = client.get("/api/v3/backtest", params={"every": 30}).json()
    assert bt["violations"] == [] and "events" not in bt
