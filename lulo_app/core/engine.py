"""Motor v3: detectar → decidir → mostrar → registrar, sobre la base del reto.

El motor no guarda estado. Cada llamada recibe el contexto de la sesión (lo que el cliente hizo,
lo que ya aceptó o rechazó, sus preferencias, la ventana de contacto) y devuelve la decisión con
toda su traza: rasgos, señales, elegibilidad, valor esperado, grupo experimental y canal.

Orden de las compuertas (cada una deja rastro en `steps`):
  0. autorización de datos (Ley 1581): sin ella no se leen los movimientos
  1. detectar: rasgos y señales a la fecha
  2. decidir: elegibilidad, exclusiones, espera entre ofertas y valor esperado
  3. experimento: el grupo de control registra la decisión pero no la muestra
  4. preferencias: si el cliente apagó las sugerencias no se muestra nada
  5. canal: push si quedan contactos y no hay fatiga ni latencia; si no, banner pasivo
  6. ventana: en tiempo real, si hay una oferta abierta, la nueva espera en cola
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import replace
from datetime import date, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from . import contact, experiment, rules
from .catalog import Product, product
from .eligibility import check
from .features import Features, compute
from .schema import PAGO_PROTEGIDO, History, LuloPolicy, Movement, PocketDeposit
from .signals import Signal, detect
from .store import store
from .text import cop, date_long, plural

Outcome = Literal["shown", "banner", "queued", "control", "optout", "noconsent", "ineligible", "weak", "has",
                  "cooldown", "external", "none"]

OUTCOME_LABEL = {
    "shown": "Se muestra (push)", "banner": "Se muestra como banner", "queued": "En cola: ventana ocupada",
    "control": "Grupo de control: no se muestra", "optout": "Sugerencias apagadas por el cliente",
    "noconsent": "Sin autorización de datos", "ineligible": "No elegible", "weak": "Señal débil",
    "has": "Ya tiene el seguro", "cooldown": "En espera: ya se le ofreció hace poco",
    "external": "Lo tiene vigente con otra aseguradora", "none": "Nada que ofrecer",
}
LOG_TYPE = {"shown": "info", "banner": "info", "queued": "hold", "control": "ctrl", "optout": "ctrl",
            "noconsent": "ctrl", "ineligible": "ctrl", "weak": "ctrl", "has": "ctrl", "cooldown": "ctrl",
            "external": "ctrl", "none": "ctrl"}
CHAIN = {"noconsent": 0, "shown": 2, "banner": 2}

POCKET_RAMO = {"Viajes": "Viajes", "Mascotas": "Mascotas", "Vivienda": "Hogar"}


class UnknownClient(LookupError):
    pass


class OfferLog(BaseModel):
    ramo: str
    date: _dt.date
    result: Literal["mostrada", "banner", "rechazada", "pospuesta", "aceptada", "control"]
    channel: Literal["push", "banner", "ninguno"] = "push"


class SessionMovement(BaseModel):
    category: str
    amount: int = Field(description="Con signo: + entra, − sale")
    date: _dt.date | None = None
    merchant: str | None = None
    counterparty: str | None = None
    channel: str = "Transferencia"


class SessionDeposit(BaseModel):
    pocket_type: str
    amount: int = Field(gt=0)
    pocket_name: str | None = None
    date: _dt.date | None = None


class Context(BaseModel):
    as_of: date | None = Field(None, description="Fecha de evaluación; por defecto, la fecha de corte de la base")
    mode: Literal["lote", "tiempo_real"] = "tiempo_real"
    consent: bool | None = Field(None, description="None: lo que dice la base (autoriza_ofertas)")
    suggestions: bool = True
    alert_days: int = Field(rules.SOAT_REMINDER_DAYS)
    control: bool | None = Field(None, description="None: asignación por hash; True/False: forzado desde el panel")
    accepted: list[str] = Field(default_factory=list, description="Ramos activados en la sesión")
    renewed: list[str] = Field(default_factory=list, description="Ramos renovados en la sesión (SOAT)")
    history: list[OfferLog] = Field(default_factory=list)
    session_movements: list[SessionMovement] = Field(default_factory=list)
    session_deposits: list[SessionDeposit] = Field(default_factory=list)
    window: dict | None = Field(None, description="Oferta que ocupa la ventana de contacto")
    queue: list[dict] = Field(default_factory=list)


EVENT_TYPES: dict[str, dict] = {
    "abono_nomina": {"category": "Abono recurrente", "sign": 1, "ramo": "Desempleo", "label": "Abono de nómina"},
    "transferencia_fija": {"category": "Transferencia fija tercero", "sign": -1, "ramo": "Vida",
                           "label": "Transferencia fija a un tercero"},
    "transferencia": {"category": "Transferencia", "sign": -1, "ramo": None, "label": "Transferencia ocasional"},
    "abono_bolsillo": {"pocket": True, "ramo": None, "label": "Abono a un bolsillo"},
    "compra_aerolinea": {"category": "Aerolineas", "sign": -1, "ramo": "Viajes", "label": "Compra en aerolínea"},
    "compra_hotel": {"category": "Hoteles", "sign": -1, "ramo": "Viajes", "label": "Compra en hotel"},
    "compra_mascotas": {"category": "Mascotas", "sign": -1, "ramo": "Mascotas", "label": "Compra en tienda de mascotas"},
    "peaje": {"category": "Peajes", "sign": -1, "ramo": "SOAT", "label": "Pago de peaje"},
    "desembolso": {"category": "Desembolso crédito", "sign": 1, "ramo": PAGO_PROTEGIDO,
                   "label": "Desembolso de Lulo Crédito"},
    "cuota": {"category": "Cuota crédito", "sign": -1, "ramo": None, "label": "Pago de cuota"},
}
MCC = {"Aerolineas": "4511", "Hoteles": "7011", "Mascotas": "5995", "Peajes": "4784", "Abono recurrente": "0000",
       "Transferencia fija tercero": "0001"}


class Event(BaseModel):
    type: Literal[tuple(EVENT_TYPES)]  # type: ignore[valid-type]
    amount: int = Field(gt=0, le=200_000_000)
    merchant: str | None = None
    counterparty: str | None = None
    pocket_type: str | None = None
    pocket_name: str | None = None


# --------------------------------------------------------------------------- utilidades
def _history(cid: str) -> History:
    h = store().history(cid)
    if h is None:
        raise UnknownClient(cid)
    return h


def _overlay(h: History, ctx: Context, as_of: date) -> History:
    """La historia de la base más lo que pasó en la sesión (y las pólizas renovadas)."""
    movs = list(h.movements)
    for i, m in enumerate(ctx.session_movements):
        movs.append(Movement(id=f"s{i + 1}", client_id=h.client.id, date=m.date or as_of, amount=m.amount,
                             channel=m.channel, category=m.category, mcc=MCC.get(m.category, ""), merchant=m.merchant,
                             counterparty=m.counterparty))
    deps = list(h.deposits)
    for i, d in enumerate(ctx.session_deposits):
        deps.append(PocketDeposit(id=f"sd{i + 1}", client_id=h.client.id, date=d.date or as_of,
                                  pocket_type=d.pocket_type, amount=d.amount, pocket_name=d.pocket_name))
    client = h.client
    if ctx.renewed:
        pols = []
        for p in client.lulo_policies:
            if p.ramo in ctx.renewed and p.expires_on:
                p = replace(p, expires_on=p.expires_on.replace(year=p.expires_on.year + 1))
            pols.append(p)
        for r in ctx.renewed:
            if not any(p.ramo == r for p in pols):
                pols.append(LuloPolicy(ramo=r, title=r, expires_on=as_of.replace(year=as_of.year + 1)))
        client = replace(client, lulo_policies=tuple(pols))
    movs.sort(key=lambda m: (m.date, m.id))
    deps.sort(key=lambda x: (x.date, x.id))
    return History(client=client, movements=movs, deposits=deps, external=list(h.external))


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:16]


def why(sig: Signal, f: Features) -> str:
    """«Por qué lo ves»: sale de la evidencia del cliente, nunca de un texto genérico."""
    r, m = sig.ramo, sig.metrics
    if sig.kind == "recuperar":
        return f"Tu seguro de {r.lower()} con otra aseguradora <b>venció el {date_long(m['lapsed_on'], False)}</b>. " \
               f"Puedes retomarlo aquí, sin papeles."
    if r == "SOAT":
        if sig.kind == "renovacion":
            return f"Tu SOAT <b>vence el {date_long(m['expiry'], False)}</b>. Renuévalo aquí y págalo desde tu cuenta Lulo."
        if sig.kind == "captura":
            return f"Tu SOAT con otra aseguradora <b>vence el {date_long(m['expiry'], False)}</b>. " \
                   f"Esta vez renuévalo desde Lulo, en minutos."
        return f"Este año pagaste <b>{plural(m['tolls_12m'], 'peaje', 'peajes')}</b> desde Lulo" \
               + (f", el más frecuente en {m['top_toll']}" if m.get("top_toll") else "") \
               + ". Si tu carro es tuyo, cotiza aquí tu SOAT."
    if r == "Desempleo":
        base = f"Tu ingreso llega a Lulo hace <b>{m['streak']} meses seguidos</b>."
        return base + (" Si pierdes el empleo, este seguro cubre tus pagos y tu crédito no se detiene."
                       if m["has_credit"] else " Si pierdes el empleo, este seguro te respalda.")
    if r == "Vida":
        who = m["counterparties"][0] if m["counterparties"] else None
        amt = cop(m["amounts"][0]) if len(m["amounts"]) == 1 else "dinero"
        target = f"a <b>{who}</b>" if who else "a la misma persona"
        return f"Hace {plural(m['months'], 'mes', 'meses')} envías {amt} {target}. Si alguien depende de ti, " \
               f"este seguro la protege."
    if r == "Viajes":
        recent = [t for t in f.travel_12m if t["days_ago"] <= rules.VIAJES_PURCHASE_DAYS]
        if recent:
            t = recent[-1]
            where = t["merchant"] or ("una aerolínea" if t["category"] == "Aerolineas" else "un hotel")
            return f"Hace {t['days_ago']} días compraste en <b>{where}</b>. Que el viaje sea solo de buenos recuerdos."
        return f"Llevas <b>{m['pocket_deposits']} abonos</b> a tu bolsillo «{m.get('pocket_name') or 'Viajes'}». " \
               f"Parece que se viene un viaje."
    if r == "Mascotas":
        return "Compras seguido en <b>tiendas de mascotas</b>" + \
               (" y ahorras para tu mascota" if m["pocket_deposits"] else "") + ". Protégela por menos de lo que cuesta una consulta."
    if r == "Hogar":
        return f"Llevas <b>{m['pocket_deposits']} abonos</b> a tu bolsillo de vivienda. Protege lo que estás construyendo."
    if r == PAGO_PROTEGIDO:
        return f"Acabas de recibir <b>{cop(m['amount'])} de Lulo Crédito</b>. Si algo pasa, tus cuotas no se detienen."
    return sig.headline


def notification(sig: Signal, p: Product) -> dict:
    if sig.ramo == "SOAT" and sig.kind in ("renovacion", "captura"):
        days = sig.metrics["days"]
        return {"t": f"Tu SOAT vence en {days} días" if days >= 0 else "Tu SOAT está vencido",
                "b": "Renuévalo aquí y págalo desde tu cuenta Lulo."}
    return {"t": f"{p.title} para ti", "b": {
        "Desempleo": "Tu ingreso llega a Lulo. Protégelo.",
        "Vida": "Protege a quien depende de ti.",
        "Viajes": "Viaja con asistencia médica.",
        "Mascotas": "Tu mascota también merece protección.",
        "Hogar": "Protege lo que estás construyendo.",
        "SOAT": "Cotiza tu SOAT en minutos.",
        PAGO_PROTEGIDO: "Que tus cuotas no se detengan si algo pasa.",
    }[sig.ramo]}


# --------------------------------------------------------------------------- evaluación
def _candidate(sig: Signal, p: Product, f: Features, h: History, ctx: Context, as_of: date) -> dict:
    c = h.client
    held = c.holds(sig.ramo) or sig.ramo in ctx.accepted
    ext_vig = [e for e in f.external if e["ramo"] == sig.ramo and e["status"] == "vigente"]
    renewal = sig.ramo == "SOAT" and sig.kind in ("renovacion", "captura") and sig.strength == "fuerte"
    el = check(c, p, f)
    cool = [o for o in ctx.history if o.ramo == sig.ramo and o.result != "aceptada"
            and as_of - timedelta(days=rules.COOLDOWN_DAYS) < o.date <= as_of]
    status, reason = "ofrecer", ""
    if sig.strength == "ninguna":
        status, reason = "none", "Sin señal"
    elif sig.ramo in ctx.renewed:
        status, reason = "has", "Renovado en esta sesión"
    elif held and not renewal:
        status, reason = "has", "Ya lo tiene con Lulo"
    elif ext_vig and not renewal:
        status, reason = "external", f"Vigente con otra aseguradora hasta el {date_long(ext_vig[0]['expires_on'], False)}"
    elif not sig.actionable:
        status, reason = "weak", "; ".join([sig.headline, *el.reasons])
    elif not el.ok:
        status, reason = "ineligible", "; ".join(el.reasons)
    elif cool:
        status, reason = "cooldown", f"Se le mostró el {date_long(cool[-1].date, False)}; espera {rules.COOLDOWN_DAYS} días"
    ev = p.expected_value(sig.strength) if sig.actionable else None
    deadline = sig.kind == "momento" or (renewal and sig.metrics.get("days") is not None)
    return {"ramo": sig.ramo, "title": p.title, "partner": p.partner, "price": p.price_label(), "status": status,
            "reason": reason, "strength": sig.strength, "kind": sig.kind,
            "ev": round(ev) if ev is not None else None, "momento": sig.kind == "momento", "deadline": deadline,
            "eligibility": el.to_dict(), "signal": sig.to_dict()}


def _rank_key(c: dict) -> tuple:
    """Fecha límite primero (v1.1), luego valor esperado, luego el orden fijo de desempate."""
    first = c["deadline"] if rules.DEADLINE_FIRST else c["momento"]
    return (0 if first else 1, -(c["ev"] or 0), rules.TIEBREAK.index(c["ramo"]))


def evaluate(cid: str, ctx: Context | None = None, *, focus: str | None = None,
             disbursement: int | None = None) -> dict:
    """Evalúa a un cliente. `focus` restringe la decisión al ramo que alimentó un evento."""
    ctx = ctx or Context()
    s = store()
    h0 = _history(cid)
    as_of = ctx.as_of or s.cutoff
    if as_of < s.start:
        raise ValueError(f"La fecha {as_of} es anterior al inicio de la base ({s.start})")
    h = _overlay(h0, ctx, as_of)
    c = h.client
    consent = c.consent if ctx.consent is None else ctx.consent
    base = {"client_id": cid, "source": c.source, "as_of": as_of.isoformat(),
            "data_until": min(as_of, s.cutoff).isoformat(), "rules_version": rules.VERSION, "mode": ctx.mode,
            "focus": focus}
    steps = []
    if not consent:
        steps.append({"step": "autorización", "ok": False,
                      "detail": "El cliente no autorizó ofertas con sus datos: el motor no lee sus movimientos"})
        return {**base, "outcome": "noconsent", "label": OUTCOME_LABEL["noconsent"], "chain": 0, "steps": steps,
                "features": None, "signals": {}, "candidates": [], "decision": None, "queue": list(ctx.queue),
                "experiment": None, "channel": None, "record": _record(base, "noconsent", None, None, None, None)}
    steps.append({"step": "autorización", "ok": True, "detail": "Autoriza ofertas (Ley 1581)"})

    f = compute(h, as_of, s.cutoff)
    sigs = detect(f, ctx.alert_days, disbursement)
    cands = [_candidate(sig, product(r), f, h, ctx, as_of) for r, sig in sigs.items()]
    offer = sorted([x for x in cands if x["status"] == "ofrecer"], key=_rank_key)
    steps.append({"step": "detectar", "ok": True,
                  "detail": f"{sum(sig.actionable for sig in sigs.values())} señales con fuerza suficiente de {len(sigs)} ramos"})
    pool = [x for x in offer if x["ramo"] == focus] if focus else offer
    if not pool:
        if focus:
            fc = next(x for x in cands if x["ramo"] == focus)
            outcome = {"weak": "weak", "none": "weak", "ineligible": "ineligible", "has": "has", "cooldown": "cooldown",
                       "external": "external"}[fc["status"]]
            detail = fc["reason"]
        else:
            outcome, detail = "none", "Ninguna señal fuerte o media es elegible hoy"
        steps.append({"step": "decidir", "ok": False, "detail": detail})
        return {**base, "outcome": outcome, "label": OUTCOME_LABEL[outcome], "chain": 1, "steps": steps,
                "features": f.to_dict(), "signals": {k: v.to_dict() for k, v in sigs.items()}, "candidates": cands,
                "decision": None, "queue": list(ctx.queue), "experiment": None, "channel": None,
                "message": detail, "record": _record(base, outcome, focus, None, None, f)}

    top = pool[0]
    sig = sigs[top["ramo"]]
    p = product(top["ramo"])
    decision = {"ramo": top["ramo"], "title": p.title, "partner": p.partner, "price": p.price_label(),
                "covers": list(p.covers), "concept": p.concept, "kind": top["kind"], "strength": top["strength"],
                "ev": top["ev"], "deadline": top["deadline"], "why": why(sig, f), "notif": notification(sig, p),
                "prio": [x["ramo"] for x in offer].index(top["ramo"]) + 1}
    if top["ramo"] == "SOAT":
        decision["soat"] = {"expiry": sig.metrics.get("expiry"), "days": sig.metrics.get("days"),
                            "source": sig.metrics.get("source"), "price": f.soat_price or p.premium}
    steps.append({"step": "decidir", "ok": True,
                  "detail": f"{p.title}: señal {top['strength']}, elegible, "
                            + ("con fecha límite, " if top["deadline"] else "") + "valor esperado "
                            + (f"{cop(top['ev'])}" if top["ev"] is not None else "n/d (momento único)")})

    exp = experiment.group(cid, c.source, ctx.control)
    if exp["group"] == "control":
        steps.append({"step": "experimento", "ok": False, "detail": f"Grupo de control ({exp['via']})"})
        return _final(base, "control", steps, f, sigs, cands, decision, ctx, exp, None, top)
    steps.append({"step": "experimento", "ok": True, "detail": f"Tratamiento ({exp['via']})"})
    if not ctx.suggestions:
        steps.append({"step": "preferencias", "ok": False, "detail": "El cliente apagó las sugerencias de seguros"})
        return _final(base, "optout", steps, f, sigs, cands, decision, ctx, exp, None, top)

    pushes = sorted(o.date for o in ctx.history if o.channel == "push" and o.result != "control" and o.date <= as_of)
    valid = contact.usage_snapshot_valid(as_of, s.cutoff)
    snap = c.usage.notifs_sent_30d if valid else 0
    ch = contact.choose(c.usage, snap + contact.contacts_in_window(pushes, as_of), ctx.mode, valid,
                        (as_of - pushes[-1]).days if pushes else None)
    steps.append({"step": "canal", "ok": True, "detail": f"{'Push' if ch.channel == 'push' else 'Banner pasivo'}: {ch.reason}"
                  + (" (uso de la app supuesto)" if c.usage.assumed else "")})
    if ctx.mode == "tiempo_real" and ctx.window is not None:
        queue = [q for q in ctx.queue if q.get("ramo") != decision["ramo"]] + [decision]
        queue.sort(key=lambda d: (0 if d.get("deadline") else 1, -(d.get("ev") or 0)))
        steps.append({"step": "ventana", "ok": False, "detail": f"Ventana ocupada por {ctx.window.get('title', 'otra oferta')}"})
        out = _final(base, "queued", steps, f, sigs, cands, decision, ctx, exp, ch, top)
        out["queue"] = queue
        return out
    return _final(base, "shown" if ch.channel == "push" else "banner", steps, f, sigs, cands, decision, ctx, exp, ch, top)


def _final(base, outcome, steps, f, sigs, cands, decision, ctx, exp, ch, top) -> dict:
    return {**base, "outcome": outcome, "label": OUTCOME_LABEL[outcome], "chain": CHAIN.get(outcome, 1),
            "steps": steps, "features": f.to_dict(), "signals": {k: v.to_dict() for k, v in sigs.items()},
            "candidates": cands, "decision": decision, "queue": list(ctx.queue), "experiment": exp,
            "channel": ch.__dict__ if ch else None, "message": steps[-1]["detail"],
            "record": _record(base, outcome, top["ramo"], top["strength"], top["ev"], f, exp, ch)}


def _record(base, outcome, ramo, strength, ev, f, exp=None, ch=None) -> dict:
    """Lo que se guarda en el registro: suficiente para auditar y reproducir la decisión."""
    return {"client_id": base["client_id"], "as_of": base["as_of"], "rules_version": base["rules_version"],
            "mode": base["mode"], "ramo": ramo, "outcome": outcome, "strength": strength, "ev": ev,
            "group": exp["group"] if exp else None, "channel": ch.channel if ch else None,
            "inputs_sha": _sha(f.to_dict()) if f else None}


# --------------------------------------------------------------------------- eventos en tiempo real
def on_event(cid: str, ev: Event, ctx: Context | None = None) -> dict:
    """Una acción en la app: se convierte en movimiento, se suma a la historia y se decide sobre el ramo que alimenta."""
    ctx = (ctx or Context()).model_copy(deep=True)
    ctx.mode = "tiempo_real"
    spec = EVENT_TYPES[ev.type]
    as_of = ctx.as_of or store().cutoff
    ramo = spec["ramo"]
    created: dict
    if spec.get("pocket"):
        if not ev.pocket_type:
            raise ValueError("abono_bolsillo necesita pocket_type")
        dep = SessionDeposit(pocket_type=ev.pocket_type, amount=ev.amount, pocket_name=ev.pocket_name, date=as_of)
        ctx.session_deposits.append(dep)
        ramo = POCKET_RAMO.get(ev.pocket_type)
        created = {"kind": "deposit", **dep.model_dump(mode="json")}
    else:
        mov = SessionMovement(category=spec["category"], amount=spec["sign"] * ev.amount, date=as_of,
                              merchant=ev.merchant, counterparty=ev.counterparty)
        ctx.session_movements.append(mov)
        created = {"kind": "movement", **mov.model_dump(mode="json")}
    if ramo is None:
        return {"client_id": cid, "event": ev.type, "label": spec["label"], "created": created, "focus": None,
                "outcome": "none", "chain": 1, "message": f"{spec['label']}: no alimenta ninguna señal de seguros",
                "evaluation": None}
    out = evaluate(cid, ctx, focus=ramo, disbursement=ev.amount if ev.type == "desembolso" else None)
    sig = out["signals"].get(ramo) if out["signals"] else None
    return {"client_id": cid, "event": ev.type, "label": spec["label"], "created": created, "focus": ramo,
            "outcome": out["outcome"], "chain": out["chain"], "message": out.get("message") or out["label"],
            "signal": sig, "evaluation": out}


# --------------------------------------------------------------------------- lote
def campaign(as_of: date | None = None, *, include_personas: bool = False, alert_days: int = rules.SOAT_REMINDER_DAYS) -> dict:
    """Plan de campaña: qué se le ofrece a cada cliente a una fecha, por qué canal y con qué valor esperado."""
    s = store()
    ctx = Context(as_of=as_of, mode="lote", alert_days=alert_days)
    rows = []
    for cid in s.ids(None if include_personas else "reto"):
        r = evaluate(cid, ctx)
        d = r["decision"] or {}
        rows.append({"client_id": cid, "outcome": r["outcome"], "ramo": d.get("ramo"), "title": d.get("title"),
                     "kind": d.get("kind"), "strength": d.get("strength"), "ev": d.get("ev"),
                     "channel": (r["channel"] or {}).get("channel"), "channel_reason": (r["channel"] or {}).get("reason"),
                     "group": (r["experiment"] or {}).get("group"),
                     "offerable": [x["ramo"] for x in r["candidates"] if x["status"] == "ofrecer"],
                     "message": r.get("message")})
    return {"as_of": (as_of or s.cutoff).isoformat(), "data_until": min(as_of or s.cutoff, s.cutoff).isoformat(),
            "rules_version": rules.VERSION, "rows": rows, "summary": summarize(rows)}


def summarize(rows: list[dict]) -> dict:
    from collections import Counter
    by_outcome = Counter(r["outcome"] for r in rows)
    shown = [r for r in rows if r["outcome"] in ("shown", "banner")]
    by_ramo = Counter(r["ramo"] for r in shown)
    by_channel = Counter(r["outcome"] for r in shown)
    ctrl = [r for r in rows if r["outcome"] == "control"]
    return {"clients": len(rows), "by_outcome": dict(by_outcome.most_common()),
            "shown_by_ramo": dict(by_ramo.most_common()), "shown_by_channel": dict(by_channel),
            "control": len(ctrl), "control_by_ramo": dict(Counter(r["ramo"] for r in ctrl).most_common()),
            "ev_total": round(sum(r["ev"] or 0 for r in shown)),
            "reasons_banner": dict(Counter((r["channel_reason"] or "").split(":")[0] for r in shown
                                           if r["outcome"] == "banner").most_common())}


# --------------------------------------------------------------------------- próximos disparos
def _add_months(d: date, n: int) -> date:
    y, m = divmod(d.month - 1 + n, 12)
    y, m = d.year + y, m + 1
    for day in (d.day, 30, 29, 28):
        try:
            return date(y, m, day)
        except ValueError:
            continue
    raise ValueError(d)


def upcoming(cid: str, ctx: Context | None = None) -> list[dict]:
    """Disparos que el motor ya sabe que vendrán, con fecha y razón (el motor también agenda)."""
    ctx = ctx or Context()
    s = store()
    h0 = _history(cid)
    as_of = ctx.as_of or s.cutoff
    h = _overlay(h0, ctx, as_of)
    c = h.client
    f = compute(h, as_of, s.cutoff)
    out = []
    if f.soat_expiry and f.soat_days is not None and f.soat_days > ctx.alert_days and "SOAT" not in ctx.renewed:
        when = date.fromordinal(f.soat_expiry.toordinal() - ctx.alert_days)
        out.append({"ramo": "SOAT", "date": when.isoformat(), "days": (when - as_of).days,
                    "title": "Recordatorio de renovación del SOAT",
                    "reason": f"Vence el {date_long(f.soat_expiry)}; el aviso sale {ctx.alert_days} días antes"})
    if (c.occupation == "Empleado" and not c.holds("Desempleo") and "Desempleo" not in ctx.accepted
            and f.income_current and 0 < f.income_streak < rules.DESEMPLEO_MIN_STREAK):
        missing = rules.DESEMPLEO_MIN_STREAK - f.income_streak
        when = _add_months(f.income_last, missing)
        out.append({"ramo": "Desempleo", "date": when.isoformat(), "days": (when - as_of).days,
                    "title": "Seguro de desempleo", "missing": missing,
                    "missing_label": plural(missing, "abono", "abonos"),
                    "reason": f"Lleva {f.income_streak} de {rules.DESEMPLEO_MIN_STREAK} abonos seguidos; con "
                              f"{plural(missing, 'abono más', 'abonos más')} acredita la antigüedad laboral"})
    if 0 < f.fixed_months < rules.VIDA_MIN_MONTHS and not c.holds("Vida") and "Vida" not in ctx.accepted:
        missing = rules.VIDA_MIN_MONTHS - f.fixed_months
        when = _add_months(f.fixed_last, missing)
        out.append({"ramo": "Vida", "date": when.isoformat(), "days": (when - as_of).days, "title": "Seguro de vida",
                    "missing": missing, "missing_label": plural(missing, "mes", "meses"), "reason": f"Lleva {f.fixed_months} de {rules.VIDA_MIN_MONTHS} meses con "
                                                  f"transferencias fijas"})
    for e in f.external:
        if e["status"] == "vigente" and e["ramo"] != "SOAT" and not c.holds(e["ramo"]):
            when = date.fromisoformat(e["expires_on"])
            out.append({"ramo": e["ramo"], "date": when.isoformat(), "days": (when - as_of).days,
                        "title": f"Seguro de {e['ramo'].lower()}",
                        "reason": "Vence su póliza con otra aseguradora: desde ese día cuenta como interés"})
    return sorted(out, key=lambda x: x["date"])
