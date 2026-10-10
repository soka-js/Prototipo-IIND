"""La entrada de Vercel restaura la ruta original que el rewrite manda en ?__path=."""

from fastapi.testclient import TestClient

from api.index import app

client = TestClient(app)


def test_restores_original_path_and_query():
    assert client.get("/api/index", params={"__path": "/api/health"}).json()["status"] == "ok"
    r = client.get("/api/index", params={"__path": "/api/clients/sebastian/movements", "q": "peaje", "limit": 2})
    assert r.status_code == 200 and len(r.json()["items"]) == 2
    home = client.get("/api/index", params={"__path": "/", "cliente": "valentina"})
    assert home.status_code == 200 and '"id": "valentina"' in home.text
    old = client.get("/api/index", params={"__path": "/v2", "cliente": "andres"})
    assert old.status_code == 200 and "/static/js/app.js" in old.text


def test_post_through_rewrite():
    r = client.post("/api/index?__path=/api/engine/event", json={"event": "viaje"})
    assert r.json()["outcome"] == "shown"


def test_direct_paths_still_work():
    assert client.get("/api/health").status_code == 200
