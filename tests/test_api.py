import json

from fastapi.testclient import TestClient

from lulo_app.main import app

client = TestClient(app)


def boot_data(html: str) -> dict:
    raw = html.split('<script id="bootstrap" type="application/json">')[1].split("</script>")[0]
    return json.loads(raw)


def test_v2_index_is_kept_intact():
    """La versión que vio el cliente sigue en /v2 con sus mismos datos."""
    r = client.get("/v2")
    assert r.status_code == 200
    data = boot_data(r.text)
    assert [c["id"] for c in data["clients"]] == ["sebastian", "valentina", "andres"]
    assert data["current"]["client"]["id"] == "sebastian"
    assert '/static/js/app.js' in r.text and 'type="module"' in r.text
    assert boot_data(client.get("/v2?cliente=valentina").text)["current"]["client"]["id"] == "valentina"
    assert boot_data(client.get("/v2?cliente=desconocido").text)["current"]["client"]["id"] == "sebastian"


def test_v3_index_renders_with_bootstrap_data():
    r = client.get("/")
    assert r.status_code == 200 and "/static/v3/app.js" in r.text and 'name="robots" content="noindex' in r.text
    data = boot_data(r.text)
    assert [p["id"] for p in data["personas"]] == ["sebastian", "valentina", "andres"]
    assert data["meta"]["cutoff"] == "2026-10-08" and data["current"]["client"]["id"] == "sebastian"
    assert boot_data(client.get("/?cliente=C00002").text)["current"]["client"]["id"] == "C00002"
    assert boot_data(client.get("/?cliente=nadie").text)["current"]["client"]["id"] == "sebastian"
    later = boot_data(client.get("/?cliente=C00210&fecha=2026-11-07").text)["current"]
    assert later["as_of"] == "2026-11-07" and later["car"]["days"] <= 30


def test_static_assets_and_manifest():
    for path in ["/static/js/app.js", "/static/js/screens.js", "/static/js/content.js", "/static/js/util.js",
                 "/static/js/icons.js", "/static/css/app.css", "/static/img/logo-lulo.png", "/static/img/icon-512.png",
                 "/static/fonts/sora-400.woff2", "/static/v3/app.js", "/static/v3/screens.js", "/static/v3/content.js",
                 "/static/v3/util.js", "/static/v3/icons.js", "/static/v3/app.css"]:
        assert client.get(path).status_code == 200, path
    m = client.get("/manifest.webmanifest")
    assert m.status_code == 200 and m.json()["display"] == "standalone"


def test_client_endpoints():
    assert len(client.get("/api/clients").json()) == 3
    assert client.get("/api/clients/andres").json()["car"]["plate"] == "KTR-913"
    assert client.get("/api/clients/nadie").status_code == 404
    movs = client.get("/api/clients/sebastian/movements", params={"q": "nómina", "limit": 3}).json()
    assert movs["total"] == 3 and len(movs["items"]) == 3
    tx = movs["items"][0]["id"]
    assert client.get(f"/api/clients/sebastian/movements/{tx}").json()["signal"]["key"] == "nomina"
    assert client.get("/api/clients/sebastian/movements/xx").status_code == 404
    assert client.get("/api/clients/valentina/signals").json()["nomina"]["strength"] == "débil"
    assert client.get("/api/clients/valentina/year").json()[-1]["id"] == "cierre"


def test_actions_endpoint():
    r = client.post("/api/clients/sebastian/actions", json={"type": "transfer", "target": "laura", "amount": 450000})
    assert r.status_code == 200 and r.json()["event"] == "vida"
    assert client.post("/api/clients/sebastian/actions", json={"type": "transfer", "target": "x", "amount": 1}).status_code == 422
    assert client.post("/api/clients/sebastian/actions", json={"type": "transfer", "target": "laura", "amount": 0}).status_code == 422


def test_engine_endpoint():
    r = client.post("/api/engine/event", json={"event": "viaje"})
    assert r.status_code == 200 and r.json()["outcome"] == "shown"
    assert client.post("/api/engine/event", json={"event": "nomina", "client_id": "valentina"}).json()["outcome"] == "weak"
    assert client.post("/api/engine/event", json={"event": "nope"}).status_code == 422
    assert client.post("/api/engine/event", json={"event": "viaje", "client_id": "nadie"}).status_code == 404


def test_soat_quote():
    assert client.get("/api/soat/quote", params={"days": 15, "cliente": "andres"}).json()["base"] == 912_400
    assert client.get("/api/soat/quote", params={"days": 10}).status_code == 422
    assert client.get("/api/soat/quote", params={"cliente": "valentina"}).status_code == 404


def test_csv_download():
    r = client.post("/api/report/csv", json=[{"t": "1", "client": "Andrés", "ev": "e", "offer": "o", "res": "Aceptó", "tipo": "ok"}])
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert r.content.startswith("﻿".encode()) and "Andrés".encode() in r.content
