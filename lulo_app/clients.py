"""Vista de cada cliente simulado: lo que la app necesita para pintar sus pantallas."""

from __future__ import annotations

import unicodedata
from datetime import timedelta
from functools import lru_cache
from typing import Literal

from pydantic import BaseModel, Field

from . import fmt
from .catalog import ALERT_DAYS_OPTIONS, events_for, movement, soat_quote
from .offers import for_persona as offers_for
from .signals import for_persona as signals_for
from .simulator import CATEGORIES, GROUPS, PERIOD_START, TODAY, Persona, get, personas
from .year import chapters

SIGNAL_LABEL = {"vehiculo": "Uso de vehículo propio", "nomina": "Ingreso laboral", "viaje": "Viaje en preparación",
                "vida": "Dependientes económicos", "credito": "Obligación de crédito"}


def _norm(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s.lower()) if unicodedata.category(c) != "Mn")


def summary(p: Persona) -> dict:
    return {"id": p.id, "first": p.first, "full": p.full, "age": p.age, "city": p.city, "occupation": p.occupation,
            "summary": p.summary, "tags": p.tags, "color": p.color}


def clients() -> list[dict]:
    return [summary(p) for p in personas().values()]


def _cajitas(p: Persona) -> list[dict]:
    out = []
    for c in p.cajitas:
        deposits = [t for t in p.txs if t["cat"] == "cajitas" and t.get("cp") == c["id"]]
        saved = -sum(t["a"] for t in deposits)
        out.append({**c, "saved": saved, "deposits": len(deposits),
                    "history": [{"date": t["date"], "a": -t["a"]} for t in deposits[:6]]})
    return out


def _credit(p: Persona) -> dict | None:
    if not p.credit:
        return None
    c = p.credit
    paid = sum(1 for t in p.txs if t["cat"] == "credito")
    last = next(t for t in p.txs if t["cat"] == "credito")
    nd = fmt.d(last["date"])
    nxt = nd.replace(year=nd.year + 1, month=1) if nd.month == 12 else nd.replace(month=nd.month + 1)
    return {**c, "paid": paid, "remaining": (c["cuotas"] - paid) * c["cuota"], "next_date": nxt.isoformat()}


def _car(p: Persona) -> dict | None:
    if not p.car:
        return None
    exp = fmt.d(p.car["soat_expiry"])
    new_from = exp
    new_to = exp.replace(year=exp.year + 1) - timedelta(days=1)
    return {**p.car, "days": (exp - TODAY).days, "expiry_long": fmt.date_long(exp),
            "new_from": fmt.date_short(new_from) + f" {new_from.year}", "new_to": fmt.date_short(new_to) + f" {new_to.year}",
            "new_to_long": fmt.date_long(new_to),
            "quotes": {d: soat_quote(p.car["soat_price"], d) for d in ALERT_DAYS_OPTIONS}}


def _notifications(p: Persona, n_chapters: int) -> list[dict]:
    out = [{"id": "n-anio", "t": "Tu año en Lulo ya está listo",
            "b": f"{fmt.num(len(p.txs))} movimientos contados en {n_chapters} capítulos.", "when": "Hoy, 8:00",
            "go": "anio", "unread": True}]
    if p.car:
        days = (fmt.d(p.car["soat_expiry"]) - TODAY).days
        out.append({"id": "n-soat", "t": f"Tu SOAT vence en {days} días",
                    "b": f"{p.car['plate']} · Renuévalo aquí con descuento por anticipación.", "when": "Hoy, 7:30",
                    "go": "renew", "unread": True})
    pay = next((t for t in p.txs if t["cat"] in ("nomina", "ingreso") and t["a"] >= 500_000), None)
    if pay:
        out.append({"id": "n-pay", "t": f"Recibiste {fmt.cop(pay['a'])}", "b": pay["n"],
                    "when": fmt.date_short(pay["date"]), "go": f"mov:{pay['id']}", "unread": False})
    cuota = next((t for t in p.txs if t["cat"] == "credito"), None)
    if cuota:
        out.append({"id": "n-cuota", "t": "Pagamos tu cuota de Lulo Crédito", "b": f"{cuota['n']} · {fmt.cop(-cuota['a'])}",
                    "when": fmt.date_short(cuota["date"]), "go": "credito", "unread": False})
    for c in _cajitas(p):
        if c["travel"]:
            pct = round(c["saved"] / c["goal"] * 100)
            out.append({"id": f"n-caj-{c['id']}", "t": f"Tu cajita «{c['name']}» va en {pct}%",
                        "b": f"Llevas {fmt.cop(c['saved'])} de {fmt.cop(c['goal'])}.", "when": "Hace 12 días",
                        "go": f"cajita:{c['id']}", "unread": False})
    return out


@lru_cache(maxsize=None)
def bootstrap(persona_id: str) -> dict:
    """Todo lo que la app necesita para arrancar con un cliente."""
    p = get(persona_id)
    chs = chapters(persona_id)
    return {
        "client": {**summary(p), "card_name": p.card_name, "since": p.since, "card_last4": p.card_last4,
                   "preapproved": p.preapproved},
        "today": TODAY.isoformat(), "period_start": PERIOD_START.isoformat(),
        "balance": p.balance, "movCount": len(p.txs), "recent": p.txs[:40],
        "contacts": p.contacts, "cajitas": _cajitas(p), "credit": _credit(p), "car": _car(p),
        "policies": p.policies, "events": events_for(p), "offers": offers_for(persona_id),
        "signals": signals_for(persona_id), "chapters": chs, "notifications": _notifications(p, len(chs)),
        "groups": GROUPS,
    }


def find_movements(persona_id: str, q: str = "", group: str = "todos", offset: int = 0, limit: int = 40) -> dict:
    p = get(persona_id)
    items = p.txs
    if group and group != "todos":
        items = [t for t in items if t["g"] == group]
    if q:
        nq = _norm(q.strip())
        items = [t for t in items if nq in _norm(t["n"]) or nq in _norm(t["c"])]
    return {"total": len(items), "offset": offset, "items": items[offset:offset + limit],
            "in": sum(t["a"] for t in items if t["a"] > 0), "out": -sum(t["a"] for t in items if t["a"] < 0)}


def signal_note(persona_id: str, tag: str | None) -> dict | None:
    if not tag:
        return None
    s = signals_for(persona_id)[tag]
    return {"key": tag, "name": s["name"], "headline": s["headline"], "rule": s["rule"], "strength": s["strength"],
            "offer": s["offer"]}


def movement_detail(persona_id: str, tx_id: str) -> dict | None:
    p = get(persona_id)
    tx = next((t for t in p.txs if t["id"] == tx_id), None)
    if tx is None:
        return None
    same = [t for t in p.txs if t["n"] == tx["n"]]
    return {"tx": tx, "signal": signal_note(persona_id, tx.get("tag")),
            "same_count": len(same), "same_total": sum(t["a"] for t in same)}


# --------------------------------------------------------------------------- acciones del cliente
class Action(BaseModel):
    type: Literal["transfer", "cajita", "cuota", "desembolso"]
    target: str | None = Field(None, description="Contacto o cajita")
    amount: int = Field(gt=0, le=50_000_000)


class ActionResult(BaseModel):
    movement: dict
    event: str | None = Field(None, description="Evento que dispara en el motor, si alguno")
    note: str
    signal: dict | None = None


def run_action(persona_id: str, a: Action) -> ActionResult:
    """Paso 1 con acciones reales: convierte lo que hizo el cliente en un movimiento y decide si es una señal."""
    p = get(persona_id)
    if a.type == "transfer":
        c = next((c for c in p.contacts if c["id"] == a.target), None)
        if c is None:
            raise ValueError("Contacto desconocido")
        cat = "educacion" if c["id"] == "colegio" else "transferencia"
        name = f"{c['name']} · Pensión" if cat == "educacion" else f"Transferencia a {c['name']}"
        mov = movement({"n": name, "cat": cat, "a": -a.amount, "ch": "PSE" if cat == "educacion" else "Bre-B"}, p,
                       cp=c["id"], tag="vida" if c.get("dependent") else None)
        if c.get("dependent"):
            return ActionResult(movement=mov, event="vida", signal=signal_note(persona_id, "vida"),
                                note=f"Pago recurrente a {c['name']}: alimenta la señal «Dependientes económicos».")
        return ActionResult(movement=mov, note="Transferencia ocasional: no alimenta ninguna señal de seguros.")
    if a.type == "cajita":
        c = next((c for c in p.cajitas if c["id"] == a.target), None)
        if c is None:
            raise ValueError("Cajita desconocida")
        mov = movement({"n": f"Cajita {c['name']}", "cat": "cajitas", "a": -a.amount, "ic": c["emoji"], "ch": "Cajita"},
                       p, cp=c["id"], tag="viaje" if c["travel"] else None)
        if c["travel"]:
            return ActionResult(movement=mov, event="viaje", signal=signal_note(persona_id, "viaje"),
                                note=f"Abono a una cajita de viaje: alimenta la señal «Viaje en preparación».")
        return ActionResult(movement=mov, note="Ahorro sin una meta asociada a seguros: no dispara nada.")
    if a.type == "cuota":
        mov = movement({"n": "Pago de cuota Lulo Crédito", "cat": "credito", "a": -a.amount, "ch": "Cuenta Lulo"}, p,
                       tag="credito")
        return ActionResult(movement=mov, signal=signal_note(persona_id, "credito"),
                            note="Pago de cuota: el motor lo cuenta en «Tu crédito», no dispara una oferta.")
    mov = movement({"n": "Desembolso Lulo Crédito", "cat": "desembolso", "a": a.amount, "ch": "Lulo Crédito"}, p,
                   tag="credito")
    return ActionResult(movement=mov, event="credito", signal=signal_note(persona_id, "credito"),
                        note="Desembolso de crédito: nueva obligación mensual, el motor revisa si tiene pago protegido.")


def categories() -> dict:
    return {k: {"label": v[0], "group": v[1], "ic": v[2]} for k, v in CATEGORIES.items()}
