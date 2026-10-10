"""Vista de un cliente para la app: lo que el frontend necesita para pintar sus pantallas.

Todo sale del esquema canónico. Lo que los personajes traen de más (nombre del comercio, metas de
bolsillos, placa del carro) se usa solo para mostrar.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict
from datetime import date, timedelta
from functools import lru_cache

from .. import simulator
from . import catalog, rules
from .engine import EVENT_TYPES, Context, campaign, evaluate, upcoming
from .features import compute
from .personas import _POCKET, shift_days
from .schema import PAGO_PROTEGIDO, History, Movement, PocketDeposit
from .store import store
from .text import cop, date_long
from .year import chapters

LABEL = {"Abono recurrente": "Abono de nómina", "Transferencia fija tercero": "Transferencia a tercero",
         "Supermercados": "Supermercado", "Restaurantes": "Restaurante", "E-commerce": "Compra en línea",
         "Transporte": "Transporte", "Salud": "Salud", "Servicios": "Pago de servicios", "Peajes": "Peaje",
         "Aerolineas": "Aerolínea", "Hoteles": "Hotel", "Mascotas": "Tienda de mascotas", "Otros": "Compra",
         "Combustible": "Combustible", "Parqueaderos": "Parqueadero", "Arriendo": "Arriendo",
         "Cuota crédito": "Cuota Lulo Crédito", "Desembolso crédito": "Desembolso Lulo Crédito",
         "Ingreso ocasional": "Ingreso", "Educación": "Educación", "Seguros": "Seguro", "Transferencia": "Transferencia"}
ICON = {"Abono recurrente": "income", "Ingreso ocasional": "income", "Desembolso crédito": "coin",
        "Transferencia fija tercero": "send", "Transferencia": "send", "Supermercados": "cart",
        "Restaurantes": "food", "E-commerce": "bag", "Transporte": "bus", "Salud": "health", "Servicios": "bolt",
        "Peajes": "road", "Aerolineas": "plane", "Hoteles": "bed", "Mascotas": "paw", "Otros": "dots",
        "Combustible": "fuel", "Parqueaderos": "parking", "Arriendo": "home", "Cuota crédito": "coin",
        "Educación": "school", "Seguros": "shield"}
FEEDS = {"Abono recurrente": "Desempleo", "Transferencia fija tercero": "Vida", "Peajes": "SOAT",
         "Aerolineas": "Viajes", "Hoteles": "Viajes", "Mascotas": "Mascotas", "Desembolso crédito": PAGO_PROTEGIDO}
POCKET_FEEDS = {"Viajes": "Viajes", "Mascotas": "Mascotas", "Vivienda": "Hogar"}
POCKET_EMOJI = {"Viajes": "✈️", "Mascotas": "🐾", "Vivienda": "🏠", "Emergencias": "🧯", "Otras": "🎯"}
COLORS = ["#E5FF00", "#FF9BB5", "#62E3A0", "#8FB8FF", "#C8B6FF", "#FFB547"]


def _persona(cid: str):
    return simulator.get(cid)


def _hash(cid: str) -> int:
    return int(hashlib.sha256(cid.encode()).hexdigest()[:12], 16)


def mov_row(m: Movement, occupation: str) -> dict:
    label = m.merchant or LABEL.get(m.category, m.category)
    if m.category == "Abono recurrente" and not m.merchant and occupation == "Pensionado":
        label = "Abono de pensión"
    return {"id": m.id, "kind": "mov", "date": m.date.isoformat(), "label": label, "category": m.category,
            "cat_label": LABEL.get(m.category, m.category), "icon": ICON.get(m.category, "dots"),
            "channel": m.channel_label or m.channel, "mcc": m.mcc, "amount": m.amount,
            "group": "ingresos" if m.amount > 0 else "gastos", "feeds": FEEDS.get(m.category),
            "counterparty": m.counterparty}


def dep_row(d: PocketDeposit) -> dict:
    name = d.pocket_name or d.pocket_type
    return {"id": d.id, "kind": "dep", "date": d.date.isoformat(), "label": f"Bolsillo {name}",
            "category": "Bolsillo", "cat_label": f"Abono a bolsillo · {d.pocket_type}", "icon": "pocket",
            "channel": "Bolsillos", "mcc": "", "amount": -d.amount, "group": "gastos",
            "feeds": POCKET_FEEDS.get(d.pocket_type), "pocket_type": d.pocket_type}


def _rows(h: History, until: date) -> list[dict]:
    occ = h.client.occupation
    rows = [mov_row(m, occ) for m in h.movements if m.date <= until] + [dep_row(d) for d in h.deposits if d.date <= until]
    rows.sort(key=lambda r: (r["date"], r["id"]), reverse=True)
    return rows


@lru_cache(maxsize=64)
def rows(cid: str) -> list[dict]:
    s = store()
    return _rows(s.history(cid), s.cutoff)


def find(cid: str, q: str = "", group: str = "todos", offset: int = 0, limit: int = 40) -> dict:
    import unicodedata

    def norm(x: str) -> str:
        return "".join(c for c in unicodedata.normalize("NFD", x.lower()) if unicodedata.category(c) != "Mn")

    items = rows(cid)
    if group in ("ingresos", "gastos"):
        items = [r for r in items if r["group"] == group]
    elif group == "pendientes":
        items = []
    if q.strip():
        nq = norm(q.strip())
        items = [r for r in items if nq in norm(f"{r['label']} {r['cat_label']} {r['channel']}")]
    return {"total": len(items), "offset": offset, "items": items[offset:offset + limit],
            "in": sum(r["amount"] for r in items if r["amount"] > 0),
            "out": -sum(r["amount"] for r in items if r["amount"] < 0)}


def detail(cid: str, rid: str) -> dict | None:
    r = next((x for x in rows(cid) if x["id"] == rid), None)
    if r is None:
        return None
    same = [x for x in rows(cid) if x["label"] == r["label"]]
    sig = None
    if r["feeds"]:
        ev = evaluate(cid, Context(mode="lote"))
        s = (ev["signals"] or {}).get(r["feeds"])
        if s:
            sig = {k: s[k] for k in ("ramo", "name", "strength", "headline", "rule", "kind")}
    return {"row": r, "signal": sig, "same_count": len(same), "same_total": sum(x["amount"] for x in same)}


def _pockets(h: History, cid: str) -> list[dict]:
    p = _persona(cid)
    deps = h.deposits
    if p:
        out = []
        for c in p.cajitas:
            mine = [d for d in deps if d.pocket_name == c["name"]]
            out.append({"id": c["id"], "type": _POCKET[c["id"]],
                        "name": c["name"], "emoji": c["emoji"], "goal": c["goal"], "note": c["note"],
                        "saved": sum(d.amount for d in mine), "deposits": len(mine),
                        "history": [{"date": d.date.isoformat(), "a": d.amount} for d in reversed(mine[-6:])]})
        return out
    by: dict[str, list[PocketDeposit]] = {}
    for d in deps:
        by.setdefault(d.pocket_type, []).append(d)
    return [{"id": t.lower(), "type": t, "name": t, "emoji": POCKET_EMOJI.get(t, "🎯"), "goal": None, "note": None,
             "saved": sum(d.amount for d in ds), "deposits": len(ds),
             "history": [{"date": d.date.isoformat(), "a": d.amount} for d in reversed(ds[-6:])]}
            for t, ds in sorted(by.items())]


def _contacts(cid: str, f) -> list[dict]:
    p = _persona(cid)
    if p:
        out = []
        for c in p.contacts:
            amt = next((-t["a"] for t in p.txs if t.get("cp") == c["id"] and t["a"] < 0), None)
            out.append({**c, "dependent": bool(c.get("dependent")), "amount": amt})
        return out
    out = []
    if f.fixed_amounts:
        out.append({"id": "tercero", "name": "Tercero frecuente", "key": "Transferencia fija", "bank": "Otro banco",
                    "dependent": True, "amount": f.fixed_amounts[0]})
    out.append({"id": "otro", "name": "Otra persona", "key": "Llave Bre-B", "bank": "Cualquier banco",
                "dependent": False, "amount": None})
    return out


def _credit(h: History, cid: str, until: date) -> dict | None:
    if not h.client.has_credit:
        return None
    p = _persona(cid)
    if not p or not p.credit:
        return {"name": "Lulo Crédito", "details": False, "protected": h.client.holds(PAGO_PROTEGIDO)}
    c = p.credit
    cuotas = [m for m in h.movements if m.category == "Cuota crédito" and m.date <= until]
    last = cuotas[-1].date if cuotas else until
    nxt = last.replace(day=1) + timedelta(days=32)
    nxt = nxt.replace(day=min(last.day, 28))
    paid = len(cuotas)
    return {"name": c["name"], "details": True, "amount": c["amount"], "cuotas": c["cuotas"], "cuota": c["cuota"],
            "paid": paid, "remaining": (c["cuotas"] - paid) * c["cuota"], "next_date": nxt.isoformat(),
            "rate": c["rate"], "protected": h.client.holds(PAGO_PROTEGIDO)}


def soat_quote(price: int, alert_days: int) -> dict:
    """Descuento por anticipación: hipótesis del prototipo v2 (hasta 5 % con aviso a 30 días)."""
    from ..catalog import SOAT_MAX_DISCOUNT
    discount = round(price * SOAT_MAX_DISCOUNT * (alert_days / 30))
    return {"days": alert_days, "base": price, "discount": discount, "total": price - discount}


def _car(h: History, cid: str, f) -> dict | None:
    p = _persona(cid)
    if p and p.car:
        exp = date.fromisoformat(p.car["soat_expiry"]) + timedelta(days=shift_days(store().cutoff))
        price = p.car["soat_price"]
        out = {"plate": p.car["plate"], "model": p.car["model"], "insurer": p.car["insurer"], "source": "lulo"}
    elif f.soat_expiry:
        exp, price = f.soat_expiry, catalog.product("SOAT").premium
        out = {"plate": None, "model": None, "insurer": "Otra aseguradora" if f.soat_source == "externa" else "Seguros Mundial",
               "source": f.soat_source}
    elif h.client.holds("SOAT"):
        return {"plate": None, "model": None, "insurer": "Seguros Mundial", "source": "lulo", "expiry": None,
                "days": None, "price": catalog.product("SOAT").premium, "quotes": {},
                "note": "La base no trae el vencimiento de este SOAT"}
    else:
        return None
    new_to = exp.replace(year=exp.year + 1) - timedelta(days=1)
    return {**out, "expiry": exp.isoformat(), "expiry_long": date_long(exp), "days": (exp - f.as_of).days,
            "price": price, "new_from": exp.isoformat(), "new_to": new_to.isoformat(), "new_to_long": date_long(new_to),
            "quotes": {d: soat_quote(price, d) for d in rules.SOAT_REMINDER_OPTIONS}}


def _notifications(cid: str, ev: dict, chs: list[dict], recent: list[dict], cutoff: date) -> list[dict]:
    out = []
    if chs:
        n = chs[0]["stats"][0]["big"]
        out.append({"id": "n-anio", "t": "Tu año en Lulo ya está listo", "b": f"{n} movimientos contados en "
                    f"{len(chs)} capítulos.", "date": cutoff.isoformat(), "time": "8:00 a. m.", "go": "anio",
                    "icon": "star", "unread": True})
    d = ev.get("decision")
    if d and ev["outcome"] == "shown":
        out.append({"id": f"n-{d['ramo']}", "t": d["notif"]["t"], "b": d["notif"]["b"], "date": cutoff.isoformat(),
                    "time": "7:30 a. m.", "go": "renew" if d["ramo"] == "SOAT" and d["kind"] in ("renovacion", "captura")
                    else f"offer:{d['ramo']}", "icon": "shield", "unread": True, "ramo": d["ramo"]})
    inc = next((r for r in recent if r["amount"] >= 500_000), None)
    if inc:
        out.append({"id": "n-inc", "t": f"Recibiste {cop(inc['amount'])}", "b": inc["label"], "date": inc["date"],
                    "time": "6:42 a. m.", "go": f"mov:{inc['id']}", "icon": "info", "unread": False})
    out.append({"id": "n-face", "t": "Reconocimiento facial activado", "b": "Ya puedes entrar a Lulo con tu cara.",
                "date": (cutoff - timedelta(days=49)).isoformat(), "time": "9:35 p. m.", "go": "perfil",
                "icon": "shield", "unread": False})
    return out


def event_defaults(cid: str, f, pockets: list[dict], credit: dict | None) -> list[dict]:
    p = _persona(cid)
    trip = p.events["viaje"]["mov"]["n"] if p and p.events["viaje"]["mov"]["cat"] == "viajes" else "Avianca · BOG–CTG"
    pocket = next((x for x in pockets if x["type"] in POCKET_FEEDS), None)
    defaults = {
        "abono_nomina": {"amount": f.income_amount or 3_200_000, "merchant": None},
        "transferencia_fija": {"amount": (f.fixed_amounts or [300_000])[0],
                               "counterparty": (f.fixed_counterparties or [None])[0]},
        "transferencia": {"amount": 50_000},
        "abono_bolsillo": {"amount": 200_000, "pocket_type": pocket["type"] if pocket else "Viajes",
                           "pocket_name": pocket["name"] if pocket else "Viajes"},
        "compra_aerolinea": {"amount": 1_200_000, "merchant": trip},
        "compra_hotel": {"amount": 650_000, "merchant": None},
        "compra_mascotas": {"amount": 120_000, "merchant": None},
        "peaje": {"amount": 12_800, "merchant": None},
        "desembolso": {"amount": 5_000_000},
        "cuota": {"amount": (credit or {}).get("cuota") or 250_000},
    }
    return [{"type": k, "label": v["label"], "ramo": v.get("ramo"), **defaults[k]} for k, v in EVENT_TYPES.items()]


def client_card(cid: str) -> dict:
    s = store()
    c = s.client(cid)
    p = _persona(cid)
    if p:
        return {"id": cid, "source": c.source, "name": p.full, "first": p.first, "card_name": p.card_name,
                "color": p.color, "summary": p.summary, "tags": p.tags, "age": p.age, "city": p.city,
                "card_last4": p.card_last4, "since": p.since, "preapproved": p.preapproved}
    h = _hash(cid)
    return {"id": cid, "source": c.source, "name": f"Cliente {cid}", "first": cid, "card_name": cid,
            "color": COLORS[h % len(COLORS)], "summary": f"{c.occupation} · {c.age_band} años · {c.segment}",
            "tags": [c.occupation, c.age_band, c.segment], "age": None, "city": None,
            "card_last4": f"{h % 10000:04d}", "since": None, "preapproved": 0}


def bootstrap(cid: str, as_of: date | None = None) -> dict:
    s = store()
    h = s.history(cid)
    if h is None:
        raise KeyError(cid)
    as_of = as_of or s.cutoff
    c = h.client
    f = compute(h, as_of, s.cutoff)
    ev = evaluate(cid, Context(as_of=as_of, mode="lote"))
    chs = chapters(cid, Context(as_of=as_of))
    all_rows = rows(cid)
    pockets = _pockets(h, cid)
    credit = _credit(h, cid, min(as_of, s.cutoff))
    card = client_card(cid)
    p = _persona(cid)
    balance = p.balance if p else c.avg_balance
    acct = f"4{_hash(cid + 'acct') % 10**11:011d}"
    return {
        "client": {**card, "age_band": c.age_band, "occupation": c.occupation, "segment": c.segment,
                   "tenure_months": c.tenure_months, "consent": c.consent, "has_cdt": c.has_cdt,
                   "account": f"{acct[:4]} {acct[4:8]} {acct[8:]}", "usage": asdict(c.usage)},
        "cutoff": s.cutoff.isoformat(), "as_of": as_of.isoformat(), "rules_version": rules.VERSION,
        "balance": balance, "balance_source": "saldo del personaje" if p else "saldo_promedio_cop de la base",
        "movCount": len(all_rows), "recent": all_rows[:40],
        "pockets": pockets, "contacts": _contacts(cid, f), "credit": credit, "car": _car(h, cid, f),
        "policies": {"lulo": [{"ramo": x.ramo, "title": x.title, "partner": x.partner,
                               "expires_on": x.expires_on.isoformat() if x.expires_on else None,
                               "voluntary": x.ramo in catalog.products()} for x in c.lulo_policies],
                     "external": f.external},
        "evaluation": ev, "upcoming": upcoming(cid, Context(as_of=as_of)), "chapters": chs,
        "notifications": _notifications(cid, ev, chs, all_rows, s.cutoff),
        "events": event_defaults(cid, f, pockets, credit), "catalog": catalog.summary(),
    }


@lru_cache(maxsize=8)
def campaign_cached(as_of_iso: str, include_personas: bool) -> dict:
    return campaign(date.fromisoformat(as_of_iso), include_personas=include_personas)


def explorer(q: str = "", outcome: str = "", ramo: str = "", source: str = "", offset: int = 0, limit: int = 50) -> dict:
    s = store()
    camp = campaign_cached(s.cutoff.isoformat(), True)
    out = []
    for r in camp["rows"]:
        c = s.client(r["client_id"])
        if source and c.source != source:
            continue
        if outcome and r["outcome"] != outcome:
            continue
        if ramo and r["ramo"] != ramo and ramo not in r["offerable"]:
            continue
        if q and q.lower() not in r["client_id"].lower() and q.lower() not in (c.name or "").lower():
            continue
        out.append({**r, "source": c.source, "name": c.name or f"Cliente {c.id}", "age_band": c.age_band,
                    "occupation": c.occupation, "segment": c.segment, "consent": c.consent,
                    "lulo": [x.ramo for x in c.lulo_policies]})
    out.sort(key=lambda r: (r["source"] != "persona", r["client_id"]))
    return {"total": len(out), "offset": offset, "items": out[offset:offset + limit], "summary": camp["summary"],
            "as_of": camp["as_of"]}
