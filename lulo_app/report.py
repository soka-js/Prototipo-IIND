"""Medición: métricas del registro de respuestas y exportación a CSV."""

from __future__ import annotations

import csv
import io

from pydantic import BaseModel

LABELS = {"ok": "Acepta", "no": "Rechaza", "hold": "Cola", "ctrl": "Sin contacto",
          "harm": "No daño", "info": "Contacto", "val": "Validación"}


class LoggedResponse(BaseModel):
    t: str
    ev: str
    offer: str
    res: str
    tipo: str


def metrics(log: list[LoggedResponse]) -> dict:
    """Totales del panel más la aceptación por oferta (base para medir contra control)."""
    by_offer: dict[str, dict[str, int]] = {}
    for r in log:
        row = by_offer.setdefault(r.offer, {"mostradas": 0, "aceptadas": 0, "rechazadas": 0, "control": 0})
        if r.res == "Mostrada en la app":
            row["mostradas"] += 1
        elif r.tipo == "ok":
            row["aceptadas"] += 1
        elif r.tipo == "no":
            row["rechazadas"] += 1
        elif r.res.startswith("Grupo de control"):
            row["control"] += 1
    return {
        "mostradas": sum(r.res == "Mostrada en la app" for r in log),
        "aceptadas": sum(r.tipo == "ok" for r in log),
        "rechazadas": sum(r.tipo == "no" for r in log),
        "dano": sum(r.tipo == "harm" for r in log),
        "por_oferta": by_offer,
    }


def to_csv(log: list[LoggedResponse]) -> str:
    """CSV con BOM y separador ';' para que Excel en español lo abra directo."""
    buf = io.StringIO()
    w = csv.writer(buf, delimiter=";", quoting=csv.QUOTE_ALL, lineterminator="\n")
    w.writerow(["hora", "evento", "oferta", "resultado", "tipo", "etiqueta"])
    for r in log:
        w.writerow([r.t, r.ev, r.offer, r.res, r.tipo, LABELS.get(r.tipo, r.tipo)])
    return "﻿" + buf.getvalue()
