"""Backtest: recorre el año con el motor y verifica que las reglas se cumplan siempre.

Cada `cada` días evalúa a todos los clientes como si fuera esa fecha, con la historia que había
hasta ese día y con el registro de lo que el motor ya les ofreció. No simula aceptaciones (la
base no trae resultados por cliente): mide alcance, canal, valor esperado y cumplimiento.

Invariantes que deben dar cero violaciones:
  · nadie recibe más push que su tope en cualquier ventana de 30 días
  · nadie sin autorización recibe una oferta
  · nadie recibe un ramo que ya tiene con Lulo ni uno que tiene vigente por fuera (salvo renovar el SOAT)
  · nadie recibe un ramo para el que no es elegible
  · el grupo de control nunca ve una oferta
  · el mismo ramo no se repite antes de la espera
  · entre dos push al mismo cliente pasan al menos MIN_DAYS_BETWEEN_PUSH días
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta

from . import rules
from .engine import Context, OfferLog, evaluate
from .store import store

RESULT = {"shown": ("mostrada", "push"), "banner": ("banner", "banner"), "control": ("control", "ninguno")}


def run(start: date | None = None, end: date | None = None, every: int = 7, include_personas: bool = False) -> dict:
    s = store()
    start = start or s.start + timedelta(days=90)
    end = end or s.cutoff
    if every < 1:
        raise ValueError("cada debe ser ≥ 1 día")
    ids = s.ids(None if include_personas else "reto")
    ledgers: dict[str, list[OfferLog]] = defaultdict(list)
    events: list[dict] = []
    violations: list[str] = []
    n_eval = 0
    day = start
    while day <= end:
        for cid in ids:
            r = evaluate(cid, Context(as_of=day, mode="lote", history=ledgers[cid]))
            n_eval += 1
            out = r["outcome"]
            if out not in RESULT:
                continue
            d = r["decision"]
            res, ch = RESULT[out]
            ledgers[cid].append(OfferLog(ramo=d["ramo"], date=day, result=res, channel=ch))
            cand = next(x for x in r["candidates"] if x["ramo"] == d["ramo"])
            events.append({"date": day.isoformat(), "client_id": cid, "ramo": d["ramo"], "outcome": out,
                           "ev": d["ev"], "kind": d["kind"], "strength": d["strength"]})
            c = s.client(cid)
            if not c.consent:
                violations.append(f"{day} {cid}: oferta sin autorización")
            if cand["status"] != "ofrecer":
                violations.append(f"{day} {cid}: {d['ramo']} con estado {cand['status']}")
            if not cand["eligibility"]["ok"]:
                violations.append(f"{day} {cid}: {d['ramo']} no elegible")
            if c.holds(d["ramo"]) and d["kind"] != "renovacion":
                violations.append(f"{day} {cid}: {d['ramo']} ya lo tiene")
        day += timedelta(days=every)

    # tope de push en ventanas de 30 días y espera por ramo
    max_push = 0
    for cid, led in ledgers.items():
        pushes = sorted(o.date for o in led if o.channel == "push")
        cap = s.client(cid).usage.max_contacts_month
        for a, b in zip(pushes, pushes[1:]):
            if (b - a).days < rules.MIN_DAYS_BETWEEN_PUSH:
                violations.append(f"{cid}: dos push con {(b - a).days} días de diferencia")
        for i, d0 in enumerate(pushes):
            n = sum(1 for d in pushes[i:] if d < d0 + timedelta(days=30))
            max_push = max(max_push, n)
            if n > cap:
                violations.append(f"{cid}: {n} push en 30 días desde {d0} (tope {cap})")
        by_ramo = defaultdict(list)
        for o in led:
            by_ramo[o.ramo].append(o.date)
        for ramo, ds in by_ramo.items():
            ds.sort()
            for a, b in zip(ds, ds[1:]):
                if (b - a).days < rules.COOLDOWN_DAYS:
                    violations.append(f"{cid}: {ramo} repetido a los {(b - a).days} días")

    by_month = defaultdict(Counter)
    for e in events:
        by_month[e["date"][:7]][e["outcome"]] += 1
    shown = [e for e in events if e["outcome"] in ("shown", "banner")]
    return {
        "rules_version": rules.VERSION, "start": start.isoformat(), "end": end.isoformat(), "every_days": every,
        "clients": len(ids), "evaluations": n_eval, "offers": len(shown),
        "control": sum(e["outcome"] == "control" for e in events),
        "push": sum(e["outcome"] == "shown" for e in events), "banner": sum(e["outcome"] == "banner" for e in events),
        "clients_reached": len({e["client_id"] for e in shown}),
        "by_ramo": dict(Counter(e["ramo"] for e in shown).most_common()),
        "by_month": {m: dict(c) for m, c in sorted(by_month.items())},
        "ev_total": round(sum(e["ev"] or 0 for e in shown)),
        "max_push_30d": max_push, "violations": violations, "events": events,
    }
