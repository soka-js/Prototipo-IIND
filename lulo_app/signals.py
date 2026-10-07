"""Paso 1 del núcleo: detectar señales de hábito en los movimientos.

Cada regla lee el año de movimientos de un cliente y responde si el hábito
existe, con qué fuerza y con qué evidencia. Son reglas fijas y explicables;
en la fase 2 se reemplazan por un modelo predictivo.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from functools import lru_cache

from . import fmt
from .simulator import TODAY, Persona, get

THRESHOLD_VEHICLE = 12   # peajes + tanqueadas en 12 meses
THRESHOLD_PAYROLL = 3    # abonos de nómina consecutivos del mismo originador
THRESHOLD_TRAVEL = 3     # abonos a una cajita de viaje
THRESHOLD_DEPENDENT = 3  # meses distintos con transferencias al mismo tercero

NAMES = {
    "vehiculo": "Uso de vehículo propio",
    "nomina": "Ingreso laboral estable",
    "viaje": "Viaje en preparación",
    "vida": "Dependientes económicos",
    "credito": "Obligación de crédito",
}
OFFER_FOR = {
    "vehiculo": "SOAT y seguros del carro",
    "nomina": "Seguro de nómina",
    "viaje": "Seguro de viaje",
    "vida": "Vida voluntario",
    "credito": "Pago protegido",
}


def _signal(key: str, detected: bool, rule: str, headline: str, evidence: list[str], metrics: dict,
            weak: bool = False) -> dict:
    return {
        "key": key, "name": NAMES[key], "offer": OFFER_FOR[key], "detected": detected,
        "strength": "fuerte" if detected else ("débil" if weak else "ninguna"),
        "rule": rule, "headline": headline, "evidence": evidence, "metrics": metrics,
    }


def _vehicle(p: Persona, txs: list[dict]) -> dict:
    tolls = [t for t in txs if t["cat"] == "peajes"]
    fuel = [t for t in txs if t["cat"] == "combustible"]
    parking = [t for t in txs if t["cat"] == "parqueadero"]
    fuel_total = -sum(t["a"] for t in fuel)
    top = Counter(t["n"] for t in tolls).most_common(1)
    top_name, top_count = (top[0] if top else ("", 0))
    toll, _, route = top_name.partition(" · ")
    m = {"tolls": len(tolls), "fuel": len(fuel), "fuel_total": fuel_total, "parking": len(parking),
         "top_toll": toll, "top_route": route, "top_toll_count": top_count}
    rule = f"{THRESHOLD_VEHICLE} o más peajes y tanqueadas en 12 meses, o un vehículo con SOAT registrado"
    ev = [f"{fmt.plural(len(tolls), 'peaje', 'peajes')}" + (f" · el más frecuente: {toll} ({top_count} veces)" if top_count > 1 else ""),
          f"{fmt.plural(len(fuel), 'tanqueada', 'tanqueadas')}" + (f" por {fmt.cop(fuel_total)}" if fuel else ""),
          f"{fmt.plural(len(parking), 'pago', 'pagos')} de parqueadero"]
    if p.car:
        days = (fmt.d(p.car["soat_expiry"]) - TODAY).days
        m.update(plate=p.car["plate"], soat_days=days)
        ev.append(f"SOAT de {p.car['plate']} vence el {fmt.date_long(p.car['soat_expiry'], year=False)} (en {days} días)")
    detected = bool(p.car) or len(tolls) + len(fuel) >= THRESHOLD_VEHICLE
    headline = (f"{len(tolls)} peajes y {len(fuel)} tanqueadas" if detected
                else f"{fmt.plural(len(tolls) + len(fuel), 'movimiento', 'movimientos')} de vehículo: no alcanza el umbral")
    return _signal("vehiculo", detected, rule, headline, ev, m, weak=len(tolls) + len(fuel) > 0)


def _payroll(p: Persona, txs: list[dict]) -> dict:
    rule = f"{THRESHOLD_PAYROLL} o más abonos de nómina seguidos del mismo originador"
    payroll = [t for t in txs if t["cat"] == "nomina" and t["n"].startswith("Nómina")]
    if payroll:
        employer = Counter(t["cp"] for t in payroll).most_common(1)[0][0]
        months = sorted({fmt.d(t["date"]).replace(day=1) for t in payroll if t["cp"] == employer})
        streak, cur = 1, months[-1]
        for prev in reversed(months[:-1]):
            expected = (cur.replace(year=cur.year - 1, month=12) if cur.month == 1 else cur.replace(month=cur.month - 1))
            if prev != expected:
                break
            streak, cur = streak + 1, prev
        days = [fmt.d(t["date"]).day for t in payroll if t["cp"] == employer]
        on_time = max(days) - min(days) <= 2
        usual_day = Counter(days).most_common(1)[0][0]
        amount = payroll[0]["a"]
        start = months[-streak]
        m = {"employer": employer, "streak": streak, "count": len(months), "amount": amount, "on_time": on_time,
             "since": fmt.month_long(start.year, start.month), "since_iso": start.isoformat(),
             "full_period": len(months) >= 11}
        ev = [f"{streak} abonos seguidos de {employer} por {fmt.cop(amount)}",
              f"Llegan hacia el día {usual_day} de cada mes" + (" sin retrasos" if on_time else ""),
              f"En Lulo desde {fmt.month_long(start.year, start.month)}"]
        return _signal("nomina", streak >= THRESHOLD_PAYROLL, rule,
                       f"{streak} de {streak} nóminas de {employer} a tiempo", ev, m)
    income = [t for t in txs if t["cat"] == "ingreso" and t.get("tag") == "nomina"]
    sources = Counter(t["cp"] for t in income)
    by_month = defaultdict(int)
    for t in income:
        by_month[t["date"][:7]] += t["a"]
    vals = list(by_month.values()) or [0]
    avg = sum(vals) // max(1, len(vals))
    m = {"sources": len(sources), "payments": len(income), "avg_month": avg, "min_month": min(vals),
         "max_month": max(vals), "clients": [c for c, _ in sources.most_common()]}
    ev = [f"{fmt.plural(len(income), 'pago', 'pagos')} de {len(sources)} originadores distintos",
          "Ningún abono llega como nómina",
          f"Ingreso mensual entre {fmt.cop(min(vals))} y {fmt.cop(max(vals))}"]
    return _signal("nomina", False, rule, f"Ingreso independiente de {len(sources)} clientes", ev, m,
                   weak=bool(income))


def _travel(p: Persona, txs: list[dict]) -> dict:
    rule = f"{THRESHOLD_TRAVEL} o más abonos a una cajita de viaje, o una compra de tiquetes"
    deposits = [t for t in txs if t["cat"] == "cajitas" and t.get("tag") == "viaje"]
    flights = [t for t in txs if t["cat"] == "viajes"]
    caj = next((c for c in p.cajitas if c["travel"]), None)
    total = -sum(t["a"] for t in deposits)
    m = {"cajita": caj["name"] if caj else None, "deposits": len(deposits), "total": total,
         "flights": [{"n": t["n"], "a": -t["a"], "date": t["date"]} for t in flights]}
    ev = []
    if deposits:
        ev.append(f"{fmt.plural(len(deposits), 'abono', 'abonos')} a la cajita «{caj['name']}» por {fmt.cop(total)}")
    for f in flights:
        ev.append(f"Compra en {f['n']} por {fmt.cop(-f['a'])} ({fmt.date_long(f['date'], year=False)})")
    if not ev:
        ev.append("Sin abonos a cajitas de viaje ni compras de tiquetes en 12 meses")
    detected = len(deposits) >= THRESHOLD_TRAVEL or bool(flights)
    headline = (f"{fmt.millions(total)} ahorrados para viajar" if deposits else
                "Compró tiquetes de avión" if flights else "Sin señal de viaje")
    return _signal("viaje", detected, rule, headline, ev, m)


def _dependents(p: Persona, txs: list[dict]) -> dict:
    rule = f"Transferencias o pagos al mismo tercero en {THRESHOLD_DEPENDENT} o más meses distintos"
    names = {c["id"]: c["name"] for c in p.contacts}
    groups: dict[str, list[dict]] = defaultdict(list)
    for t in txs:
        if t.get("tag") == "vida" and t["a"] < 0:
            groups[t["cp"]].append(t)
    bens = []
    for cp, items in groups.items():
        months = sorted({t["date"][:7] for t in items})
        first = fmt.d(min(t["date"] for t in items))
        bens.append({"id": cp, "name": names.get(cp, cp), "months": len(months), "total": -sum(t["a"] for t in items),
                     "amount": -items[0]["a"], "since": fmt.month_long(first.year, first.month)})
    bens.sort(key=lambda b: -b["total"])
    strong = [b for b in bens if b["months"] >= THRESHOLD_DEPENDENT]
    total = sum(b["total"] for b in strong)
    m = {"beneficiaries": strong, "total": total}
    ev = [f"{b['name']}: {b['months']} meses desde {b['since']}, {fmt.cop(b['total'])} en total" for b in strong] \
        or ["Sin transferencias fijas a un mismo tercero"]
    headline = (f"{fmt.millions(total)} enviados a {strong[0]['name']}" if len(strong) == 1 else
                f"{fmt.millions(total)} para {len(strong)} dependientes" if strong else "Sin señal")
    return _signal("vida", bool(strong), rule, headline, ev, m)


def _credit(p: Persona, txs: list[dict]) -> dict:
    rule = "Crédito activo con cuotas en curso"
    if not p.credit:
        return _signal("credito", False, rule, "Sin crédito en Lulo",
                       [f"Tiene un cupo preaprobado de {fmt.cop(p.preapproved)}"] if p.preapproved else ["Sin crédito"],
                       {"preapproved": p.preapproved})
    c = p.credit
    paid = sum(1 for t in txs if t["cat"] == "credito")
    m = {"paid": paid, "cuotas": c["cuotas"], "cuota": c["cuota"], "amount": c["amount"], "protected": c["protected"]}
    ev = [f"Desembolso de {fmt.cop(c['amount'])} el {fmt.date_long(c['disbursed'])}",
          f"{paid} de {c['cuotas']} cuotas de {fmt.cop(c['cuota'])} pagadas a tiempo",
          "Con pago protegido de SBS" if c["protected"] else "Sin pago protegido"]
    return _signal("credito", True, rule, f"{paid} de {c['cuotas']} cuotas pagadas", ev, m)


@lru_cache(maxsize=None)
def for_persona(persona_id: str) -> dict[str, dict]:
    p = get(persona_id)
    if p is None:
        raise KeyError(persona_id)
    txs = p.txs
    return {s["key"]: s for s in (_vehicle(p, txs), _payroll(p, txs), _travel(p, txs), _dependents(p, txs),
                                   _credit(p, txs))}
