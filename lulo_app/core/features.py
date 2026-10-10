"""Rasgos de un cliente a una fecha: lo único que el motor sabe para decidir.

Regla temporal: los datos de comportamiento llegan hasta la fecha de corte de la base. Si se
evalúa después del corte (para ver qué pasa con un vencimiento, por ejemplo), los rasgos de
comportamiento se congelan en el corte y la respuesta lo dice en `data_until`.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

from . import rules
from .schema import History

TRAVEL_CATEGORIES = ("Aerolineas", "Hoteles")


def _ym(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _prev_ym(ym: str) -> str:
    y, m = int(ym[:4]), int(ym[5:])
    return f"{y - 1:04d}-12" if m == 1 else f"{y:04d}-{m - 1:02d}"


def streak(months: list[str]) -> int:
    """Meses seguidos hasta el último mes con dato."""
    if not months:
        return 0
    ms = sorted(set(months))
    n, cur = 1, ms[-1]
    for prev in reversed(ms[:-1]):
        if prev != _prev_ym(cur):
            break
        n, cur = n + 1, prev
    return n


@dataclass
class Features:
    as_of: date
    data_until: date
    window_start: date
    # ingreso recurrente
    income_months: list[str] = field(default_factory=list)
    income_streak: int = 0
    income_last: date | None = None
    income_amount: int | None = None
    income_current: bool = False
    # transferencias fijas a terceros
    fixed_months: int = 0
    fixed_amounts: list[int] = field(default_factory=list)
    fixed_total: int = 0
    fixed_last: date | None = None
    fixed_counterparties: list[str] = field(default_factory=list)
    # vehículo
    tolls_12m: int = 0
    tolls_last: date | None = None
    top_toll: str | None = None
    # viajes
    travel_12m: list[dict] = field(default_factory=list)
    travel_30d: int = 0
    travel_90d: int = 0
    # bolsillos
    pockets_12m: dict[str, int] = field(default_factory=dict)
    pockets_total: dict[str, int] = field(default_factory=dict)
    pockets_last: dict[str, date] = field(default_factory=dict)
    pocket_names: dict[str, str] = field(default_factory=dict)
    # mascotas
    pet_spend_12m: int = 0
    # seguros
    lulo_ramos: list[str] = field(default_factory=list)
    external: list[dict] = field(default_factory=list)
    soat_expiry: date | None = None
    soat_source: str | None = None     # "lulo" | "externa"
    soat_days: int | None = None
    soat_price: int | None = None
    # contexto
    has_credit: bool = False
    movements_12m: int = 0

    def to_dict(self) -> dict:
        out = asdict(self)
        for k, v in list(out.items()):
            if isinstance(v, date):
                out[k] = v.isoformat()
        out["pockets_last"] = {k: v.isoformat() for k, v in self.pockets_last.items()}
        return out


def compute(h: History, as_of: date, cutoff: date) -> Features:
    until = min(as_of, cutoff)
    start = until - timedelta(days=rules.LOOKBACK_DAYS)
    f = Features(as_of=as_of, data_until=until, window_start=start, has_credit=h.client.has_credit)
    movs = [m for m in h.movements if start < m.date <= until]
    f.movements_12m = len(movs)

    income = [m for m in movs if m.category == "Abono recurrente"]
    if income:
        f.income_months = sorted({_ym(m.date) for m in income})
        f.income_streak = streak(f.income_months)
        f.income_last = income[-1].date
        f.income_amount = income[-1].amount
        f.income_current = (as_of - f.income_last).days <= rules.STREAK_MAX_GAP_DAYS

    fixed = [m for m in movs if m.category == "Transferencia fija tercero"]
    if fixed:
        f.fixed_months = len({_ym(m.date) for m in fixed})
        f.fixed_amounts = sorted({-m.amount for m in fixed})
        f.fixed_total = -sum(m.amount for m in fixed)
        f.fixed_last = fixed[-1].date
        f.fixed_counterparties = [n for n, _ in Counter(m.counterparty or m.merchant for m in fixed
                                                        if (m.counterparty or m.merchant)).most_common()]

    tolls = [m for m in movs if m.category == "Peajes"]
    f.tolls_12m = len(tolls)
    if tolls:
        f.tolls_last = tolls[-1].date
        named = Counter(m.merchant for m in tolls if m.merchant)
        f.top_toll = named.most_common(1)[0][0] if named else None

    for m in movs:
        if m.category in TRAVEL_CATEGORIES:
            days = (as_of - m.date).days
            f.travel_12m.append({"date": m.date.isoformat(), "category": m.category, "amount": -m.amount,
                                 "merchant": m.merchant, "days_ago": days})
            f.travel_30d += days <= 30
            f.travel_90d += days <= rules.VIAJES_PURCHASE_DAYS

    f.pet_spend_12m = sum(1 for m in movs if m.category == "Mascotas")

    for d in h.deposits:
        if start < d.date <= until:
            f.pockets_12m[d.pocket_type] = f.pockets_12m.get(d.pocket_type, 0) + 1
            f.pockets_total[d.pocket_type] = f.pockets_total.get(d.pocket_type, 0) + d.amount
            f.pockets_last[d.pocket_type] = d.date
            if d.pocket_name:
                f.pocket_names[d.pocket_type] = d.pocket_name

    f.lulo_ramos = [p.ramo for p in h.client.lulo_policies]
    for e in h.external:
        if e.paid_on > until:
            continue
        f.external.append({"ramo": e.ramo, "paid_on": e.paid_on.isoformat(), "expires_on": e.expires_on.isoformat(),
                           "amount": e.amount, "provider": e.provider,
                           "status": "vigente" if e.expires_on >= as_of else "vencida",
                           "days_to_expiry": (e.expires_on - as_of).days})

    soat_lulo = next((p for p in h.client.lulo_policies if p.ramo == "SOAT"), None)
    soat_ext = [e for e in f.external if e["ramo"] == "SOAT" and e["status"] == "vigente"]
    if soat_lulo and soat_lulo.expires_on:
        f.soat_expiry, f.soat_source, f.soat_price = soat_lulo.expires_on, "lulo", soat_lulo.price
    elif soat_ext:
        e = min(soat_ext, key=lambda x: x["expires_on"])
        f.soat_expiry, f.soat_source = date.fromisoformat(e["expires_on"]), "externa"
    if f.soat_expiry:
        f.soat_days = (f.soat_expiry - as_of).days
    return f
