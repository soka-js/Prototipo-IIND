"""Requisitos de la hoja Elegibilidad: edad, ocupación y requisito del ramo.

Cada requisito se marca según cómo se verifica:
  dato      se verifica con la base (edad, ocupación, capacidad de pago)
  proxy     se aproxima con la base (antigüedad laboral ≈ racha de abonos en Lulo)
  cotizacion no está en la base: se pide al cliente en la cotización (placa, dirección, mascota, fecha de viaje)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from . import rules
from .catalog import Product
from .features import Features
from .schema import AGE_BANDS, PAGO_PROTEGIDO, Client
from .text import cop, pct


@dataclass
class Eligibility:
    ok: bool
    reasons: list[str] = field(default_factory=list)       # por qué no es elegible
    checks: list[dict] = field(default_factory=list)       # cada requisito con su verificación

    def to_dict(self) -> dict:
        return asdict(self)


def check(c: Client, p: Product, f: Features) -> Eligibility:
    e = Eligibility(ok=True)
    lo, hi = AGE_BANDS[c.age_band]
    age_txt = f"{p.age_min}+" if p.age_max is None else f"{p.age_min}-{p.age_max}"
    if hi is None and p.age_max is not None and rules.EXCLUDE_OPEN_AGE_BAND:
        e.ok = False
        e.reasons.append(f"Edad por confirmar: el rango «{c.age_band}» puede superar el tope de {p.age_max} años")
        e.checks.append({"req": f"Edad {age_txt}", "via": "dato", "ok": False})
    elif hi is not None and (hi < p.age_min or (p.age_max is not None and lo > p.age_max)):
        e.ok = False
        e.reasons.append(f"Fuera del rango de edad {age_txt}")
        e.checks.append({"req": f"Edad {age_txt}", "via": "dato", "ok": False})
    else:
        e.checks.append({"req": f"Edad {age_txt}", "via": "dato", "ok": True})

    if p.occupations is not None:
        ok = c.occupation in p.occupations
        e.checks.append({"req": f"Ocupación: {', '.join(p.occupations)}", "via": "dato", "ok": ok})
        if not ok:
            e.ok = False
            e.reasons.append(f"Ocupación «{c.occupation}»: el ramo exige {', '.join(p.occupations)}")

    cap = capacity(c, p, f)
    if cap is not None:
        reason = cap.pop("reason")
        e.checks.append(cap)
        if not cap["ok"]:
            e.ok = False
            e.reasons.append(reason)

    if p.ramo == "Desempleo":
        ok = f.income_current and f.income_streak >= rules.DESEMPLEO_MIN_STREAK
        e.checks.append({"req": p.requirement, "via": "proxy",
                         "detail": f"{f.income_streak} abonos recurrentes seguidos en Lulo", "ok": ok})
        if not ok:
            e.ok = False
            e.reasons.append(f"Antigüedad laboral sin acreditar: {f.income_streak} de {rules.DESEMPLEO_MIN_STREAK} "
                             f"abonos seguidos en Lulo")
    elif p.ramo == PAGO_PROTEGIDO:
        e.checks.append({"req": p.requirement, "via": "dato", "ok": True})
    else:
        e.checks.append({"req": p.requirement, "via": "cotizacion", "ok": None})
    return e


def capacity(c: Client, p: Product, f: Features) -> dict | None:
    """Capacidad de pago de la prima (reglas v1.3). None si el producto no tiene prima en la base."""
    if p.premium is None:
        return None
    if p.periodicity == "Mensual":
        share = p.premium / c.monthly_income if c.monthly_income > 0 else None
        ok = share is not None and share <= rules.CAPACITY_MAX_SHARE
        detail = (f"Prima {cop(p.premium)} al mes = {pct(share)} de su ingreso mensual ({cop(c.monthly_income)})"
                  if share is not None else "Sin ingreso mensual registrado")
        return {"req": f"Capacidad de pago: prima ≤ {pct(rules.CAPACITY_MAX_SHARE, 0)} del ingreso mensual",
                "via": "dato", "detail": detail, "ok": ok, "share": round(share, 4) if share is not None else None,
                "reason": f"Capacidad de pago: la prima pasa del {pct(rules.CAPACITY_MAX_SHARE, 0)} de su ingreso mensual"}
    if not rules.CAPACITY_SINGLE_PAY_VS_BALANCE:
        return None
    ok = p.premium <= c.avg_balance
    return {"req": "Capacidad de pago: prima de pago único ≤ saldo promedio", "via": "dato",
            "detail": f"Prima {cop(p.premium)} frente a un saldo promedio de {cop(c.avg_balance)}", "ok": ok,
            "share": round(p.premium / c.avg_balance, 4) if c.avg_balance > 0 else None,
            "reason": "Capacidad de pago: la prima de pago único supera su saldo promedio"}
