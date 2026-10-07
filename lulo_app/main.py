"""Aplicación web del prototipo «Tu año en Lulo» · Grupo 14.

Local:   python run.py           (http://127.0.0.1:8000)
Vercel:  api/index.py expone `app`; los estáticos salen de public/ por la CDN.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import clients as cl
from .catalog import soat_quote
from .engine import EngineResult, EventRequest, UnknownClient, handle_event
from .report import LoggedResponse, metrics, to_csv
from .signals import for_persona as signals_for
from .simulator import DEFAULT_ID, get
from .year import chapters

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "public" / "static"
VERSION = "2.0.0"

app = FastAPI(
    title="Prototipo Lulo Bank · Grupo 14",
    description="Clientes simulados, detección de señales, Tu año en Lulo, motor de disparadores y recordatorio del SOAT.",
    version=VERSION,
)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# En Vercel la CDN sirve public/ antes de llegar a la función; en local lo sirve FastAPI.
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _persona(client_id: str):
    p = get(client_id)
    if p is None:
        raise HTTPException(status_code=404, detail=f"Cliente desconocido: {client_id}")
    return p


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index(request: Request, cliente: str = DEFAULT_ID):
    if get(cliente) is None:
        cliente = DEFAULT_ID
    boot = {"version": VERSION, "clients": cl.clients(), "current": cl.bootstrap(cliente)}
    data = json.dumps(boot, ensure_ascii=False).replace("</", "<\\/")
    return templates.TemplateResponse(request, "index.html", {"bootstrap": data, "version": VERSION})


@app.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return Response(content=json.dumps({
        "name": "Tu año en Lulo · Prototipo Grupo 14", "short_name": "Lulo Demo", "lang": "es-CO",
        "start_url": "/", "display": "standalone", "background_color": "#1F2739", "theme_color": "#1F2739",
        "icons": [{"src": "/static/img/icon-192.png", "sizes": "192x192", "type": "image/png"},
                  {"src": "/static/img/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"}],
    }, ensure_ascii=False), media_type="application/manifest+json")


@app.get("/api/health")
def health():
    return {"status": "ok", "version": VERSION}


@app.get("/api/clients")
def list_clients():
    return cl.clients()


@app.get("/api/clients/{client_id}")
def client_bootstrap(client_id: str):
    _persona(client_id)
    return cl.bootstrap(client_id)


@app.get("/api/clients/{client_id}/movements")
def client_movements(client_id: str, q: str = "", group: str = "todos",
                     offset: int = Query(0, ge=0), limit: int = Query(40, ge=1, le=200)):
    _persona(client_id)
    return cl.find_movements(client_id, q=q, group=group, offset=offset, limit=limit)


@app.get("/api/clients/{client_id}/movements/{tx_id}")
def client_movement(client_id: str, tx_id: str):
    _persona(client_id)
    out = cl.movement_detail(client_id, tx_id)
    if out is None:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    return out


@app.get("/api/clients/{client_id}/signals")
def client_signals(client_id: str):
    """Paso 1: lo que el motor detecta en los 12 meses de movimientos."""
    _persona(client_id)
    return signals_for(client_id)


@app.get("/api/clients/{client_id}/year")
def client_year(client_id: str):
    _persona(client_id)
    return chapters(client_id)


@app.post("/api/clients/{client_id}/actions", response_model=cl.ActionResult)
def client_action(client_id: str, action: cl.Action):
    """Una acción en la app (transferir, abonar, pagar, pedir crédito) convertida en movimiento y señal."""
    _persona(client_id)
    try:
        return cl.run_action(client_id, action)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/api/engine/event", response_model=EngineResult)
def engine_event(req: EventRequest):
    """Procesa un evento: autorización, control, preferencias, fuerza de la señal, elegibilidad y prioridad."""
    try:
        return handle_event(req)
    except UnknownClient as e:
        raise HTTPException(status_code=404, detail=f"Cliente desconocido: {e}") from e


@app.get("/api/soat/quote")
def get_soat_quote(days: int = 30, cliente: str = DEFAULT_ID):
    p = _persona(cliente)
    if not p.car:
        raise HTTPException(status_code=404, detail="El cliente no tiene vehículo registrado")
    try:
        return soat_quote(p.car["soat_price"], days)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@app.post("/api/report/metrics")
def report_metrics(log: list[LoggedResponse]):
    return metrics(log)


@app.post("/api/report/csv")
def report_csv(log: list[LoggedResponse]):
    return Response(
        content=to_csv(log).encode("utf-8"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="registro-respuestas-lulo-grupo14.csv"'},
    )
