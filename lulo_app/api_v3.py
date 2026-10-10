"""API v3: el motor real sobre la base del reto. Las rutas de v2 siguen funcionando aparte."""

from __future__ import annotations

import csv
import io
from datetime import date

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel

from .core import backtest as bt
from .core import catalog, engine, rules, view
from .core.store import store

router = APIRouter(prefix="/api/v3", tags=["v3"])


def _client(cid: str):
    if store().client(cid) is None:
        raise HTTPException(status_code=404, detail=f"Cliente desconocido: {cid}")


def _date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=f"Fecha inválida: {s}") from e


@router.get("/meta")
def meta():
    """Fecha de corte, reglas vigentes, catálogo y calidad de la base."""
    s = store()
    m = s.manifest
    return {"cutoff": s.cutoff.isoformat(), "start": s.start.isoformat(), "rules_version": rules.VERSION,
            "rules": rules.as_dict(), "catalog": catalog.summary(),
            "dataset": {"fuente": m["fuente"], "filas": m["filas"], "chequeos": m["chequeos"], "uso": m["uso"],
                        "restriccion": m["restriccion"]},
            "events": [{"type": k, **{x: v[x] for x in ("label", "ramo") if x in v}} for k, v in engine.EVENT_TYPES.items()],
            "clients": {"reto": len(s.ids("reto")), "persona": len(s.ids("persona"))}}


@router.get("/clients")
def clients(q: str = "", outcome: str = "", ramo: str = "", source: str = "",
            offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=200)):
    """Explorador: los 603 clientes con lo que el motor decidiría hoy."""
    return view.explorer(q=q, outcome=outcome, ramo=ramo, source=source, offset=offset, limit=limit)


@router.get("/clients/{cid}")
def client(cid: str, as_of: str | None = None):
    _client(cid)
    try:
        return view.bootstrap(cid, _date(as_of))
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.get("/clients/{cid}/movements")
def movements(cid: str, q: str = "", group: str = "todos", offset: int = Query(0, ge=0),
              limit: int = Query(40, ge=1, le=200)):
    _client(cid)
    return view.find(cid, q=q, group=group, offset=offset, limit=limit)


@router.get("/clients/{cid}/movements/{rid}")
def movement(cid: str, rid: str):
    _client(cid)
    d = view.detail(cid, rid)
    if d is None:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    return d


@router.post("/clients/{cid}/evaluate")
def evaluate(cid: str, ctx: engine.Context, focus: str | None = None):
    """Evalúa al cliente con el contexto de la sesión. `focus` restringe la decisión a un ramo (siguiente ventana)."""
    _client(cid)
    try:
        return engine.evaluate(cid, ctx, focus=focus)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


class EventRequest(BaseModel):
    event: engine.Event
    context: engine.Context = engine.Context()


@router.post("/clients/{cid}/events")
def event(cid: str, req: EventRequest):
    """Una acción en la app → movimiento → señal → decisión."""
    _client(cid)
    try:
        return engine.on_event(cid, req.event, req.context)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e


@router.post("/clients/{cid}/year")
def year(cid: str, ctx: engine.Context):
    _client(cid)
    from .core.year import chapters
    return chapters(cid, ctx)


@router.post("/clients/{cid}/upcoming")
def upcoming(cid: str, ctx: engine.Context):
    _client(cid)
    return engine.upcoming(cid, ctx)


@router.get("/campaign")
def campaign(as_of: str | None = None, personas: bool = False):
    """Plan de campaña de todos los clientes a una fecha."""
    d = _date(as_of) or store().cutoff
    out = view.campaign_cached(d.isoformat(), personas)
    return {**out, "rows": out["rows"]}


@router.get("/campaign.csv")
def campaign_csv(as_of: str | None = None, personas: bool = False):
    d = _date(as_of) or store().cutoff
    out = view.campaign_cached(d.isoformat(), personas)
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", lineterminator="\n")
    cols = ["client_id", "outcome", "ramo", "kind", "strength", "ev", "channel", "channel_reason", "group", "offerable",
            "message"]
    w.writerow(cols)
    for r in out["rows"]:
        w.writerow([("|".join(r[c]) if c == "offerable" else r[c]) for c in cols])
    return Response(content=("﻿" + buf.getvalue()).encode("utf-8"), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="plan-campana-{d.isoformat()}.csv"'})


_BT: dict = {}


@router.get("/backtest")
def backtest(every: int = Query(14, ge=7, le=60)):
    """Recorre el año con el motor y verifica las invariantes (se guarda en memoria por proceso)."""
    if every not in _BT:
        r = bt.run(every=every)
        r.pop("events")
        _BT[every] = r
    return _BT[every]
