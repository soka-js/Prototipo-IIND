"""Aplicación web del prototipo «Tu año en Lulo» · Grupo 14.

Local:   python run.py           (http://127.0.0.1:8000)
Vercel:  api/index.py expone `app`; los estáticos salen de public/ por la CDN.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import catalog
from .engine import EngineResult, EventRequest, handle_event, soat_quote
from .report import LoggedResponse, metrics, to_csv

ROOT = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT / "public" / "static"
VERSION = "1.0.0"

app = FastAPI(
    title="Prototipo Lulo Bank · Grupo 14",
    description="Motor de disparadores, Tu año en Lulo y recordatorio del SOAT.",
    version=VERSION,
)
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")

# En Vercel la CDN sirve public/ antes de llegar a la función; en local lo sirve FastAPI.
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def bootstrap() -> dict:
    """Datos con los que arranca el front: catálogo, estado inicial y cotizaciones del SOAT."""
    return {
        "events": catalog.EVENTS,
        "offers": catalog.OFFERS,
        "policies": catalog.INITIAL_POLICIES,
        "movs": catalog.INITIAL_MOVS,
        "balance": catalog.INITIAL_BALANCE,
        "soatQuotes": {d: soat_quote(d) for d in catalog.ALERT_DAYS_OPTIONS},
        "version": VERSION,
    }


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def index(request: Request):
    data = json.dumps(bootstrap(), ensure_ascii=False).replace("</", "<\\/")
    return templates.TemplateResponse(request, "index.html", {"bootstrap": data, "version": VERSION})


@app.get("/api/health")
def health():
    return {"status": "ok", "version": VERSION}


@app.get("/api/catalog")
def get_catalog():
    return bootstrap()


@app.post("/api/engine/event", response_model=EngineResult)
def engine_event(req: EventRequest):
    """Procesa un evento del cliente: elegibilidad, control, preferencias y prioridad."""
    return handle_event(req)


@app.get("/api/soat/quote")
def get_soat_quote(days: int = 30):
    try:
        return soat_quote(days)
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
