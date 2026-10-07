import json

from fastapi.testclient import TestClient

from lulo_app.main import app

client = TestClient(app)


def test_index_renders_with_bootstrap_data():
    r = client.get("/")
    assert r.status_code == 200
    html = r.text
    assert 'id="bootstrap"' in html and "/static/js/app.js" in html
    raw = html.split('<script id="bootstrap" type="application/json">')[1].split("</script>")[0]
    data = json.loads(raw)
    assert set(data["events"]) == {"credito", "vehiculo", "nomina", "viaje", "vida"}
    assert data["soatQuotes"]["30"]["total"] < data["soatQuotes"]["30"]["base"]


def test_static_assets_served():
    for path in ["/static/js/app.js", "/static/css/app.css", "/static/img/logo-lulo.png",
                 "/static/fonts/sora-400.woff2"]:
        assert client.get(path).status_code == 200, path


def test_engine_endpoint():
    r = client.post("/api/engine/event", json={"event": "viaje"})
    assert r.status_code == 200 and r.json()["outcome"] == "shown"
    assert client.post("/api/engine/event", json={"event": "nope"}).status_code == 422


def test_soat_quote_validation():
    assert client.get("/api/soat/quote?days=15").json()["days"] == 15
    assert client.get("/api/soat/quote?days=10").status_code == 422


def test_csv_download():
    r = client.post("/api/report/csv", json=[{"t": "1", "ev": "e", "offer": "o", "res": "Aceptó", "tipo": "ok"}])
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    assert r.content.startswith("﻿".encode())
