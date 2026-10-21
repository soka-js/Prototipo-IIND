"""Vector numérico de un cliente a una fecha. Solo usa campos canónicos (fecha, monto, canal,
categoría y MCC, más el perfil de la hoja Clientes y Uso_App): nunca nombres de comercio o terceros.

Lo usan igual el entrenamiento y el cálculo en producción, para que no haya diferencias entre los dos.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

from ..core.schema import AGE_BANDS, RAMOS, History

LOOKBACK_DAYS = 365
AGE_ORDER = list(AGE_BANDS)
OCCUPATIONS = ("Empleado", "Independiente", "Estudiante", "Pensionado")
CATEGORIES = ("Peajes", "Mascotas", "Aerolineas", "Hoteles", "Transferencia fija tercero", "Salud",
              "E-commerce", "Restaurantes", "Transporte", "Supermercados", "Servicios")
POCKETS = ("Viajes", "Mascotas", "Vivienda", "Emergencias", "Otras")
CHANNELS = ("PSE", "QR", "Tarjeta débito", "Transferencia")

PROFILE = ["edad", *[f"ocup_{o}" for o in OCCUPATIONS], "pro", "antiguedad", "log_saldo", "log_ingreso",
           "credito", "cdt", "cajitas"]
BEHAVIOR = ["log_movs", *[f"n_{c}" for c in CATEGORIES], "racha_ingreso", "meses_ingreso", "meses_fija",
            "ratio_consumo", "log_gasto_mes", *[f"abonos_{p}" for p in POCKETS], *[f"canal_{c}" for c in CHANNELS]]
USAGE = ["sesiones", "visitas_seguros", "tasa_apertura"]
NAMES = PROFILE + BEHAVIOR + USAGE

LABELS = {
    "edad": "Rango de edad", "pro": "Segmento Pro", "antiguedad": "Antigüedad en Lulo", "log_saldo": "Saldo promedio",
    "log_ingreso": "Ingreso mensual", "credito": "Crédito activo", "cdt": "CDT activo", "cajitas": "Usa bolsillos",
    "log_movs": "Movimientos en el año", "racha_ingreso": "Meses seguidos con nómina",
    "meses_ingreso": "Meses con nómina", "meses_fija": "Meses con transferencia fija",
    "ratio_consumo": "Gasto frente a ingreso", "log_gasto_mes": "Gasto mensual",
    "sesiones": "Sesiones en la app", "visitas_seguros": "Visitas a Seguros", "tasa_apertura": "Abre notificaciones",
    **{f"ocup_{o}": f"Ocupación: {o.lower()}" for o in OCCUPATIONS},
    **{f"n_{c}": f"Compras en {c.lower()}" for c in CATEGORIES},
    "n_Transferencia fija tercero": "Transferencias fijas a un tercero", "n_Peajes": "Pasos por peaje",
    **{f"abonos_{p}": f"Abonos al bolsillo {p.lower()}" for p in POCKETS},
    **{f"canal_{c}": f"Uso de {c}" for c in CHANNELS},
}


def _ym(d: date) -> str:
    return f"{d.year:04d}-{d.month:02d}"


def _streak(months: set[str]) -> int:
    if not months:
        return 0
    ms = sorted(months)
    n, (y, m) = 1, map(int, ms[-1].split("-"))
    for prev in reversed(ms[:-1]):
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
        if prev != f"{y:04d}-{m:02d}":
            break
        n += 1
    return n


def holdings(h: History, until: date) -> set[str]:
    """Ramos que el cliente tiene o ha pagado: con Lulo (Clientes) o con otra aseguradora (Pagos_Seguros)."""
    out = {p.ramo for p in h.client.lulo_policies}
    out |= {e.ramo for e in h.external if e.paid_on <= until}
    return out & set(RAMOS)


def vector(h: History, as_of: date) -> dict[str, float]:
    c, u = h.client, h.client.usage
    start = as_of - timedelta(days=LOOKBACK_DAYS)
    movs = [m for m in h.movements if start < m.date <= as_of]
    v: dict[str, float] = {
        "edad": float(AGE_ORDER.index(c.age_band)) if c.age_band in AGE_ORDER else 1.0,
        **{f"ocup_{o}": float(c.occupation == o) for o in OCCUPATIONS},
        "pro": float(c.segment == "Pro"), "antiguedad": float(c.tenure_months),
        "log_saldo": math.log1p(max(c.avg_balance, 0)), "log_ingreso": math.log1p(max(c.monthly_income, 0)),
        "credito": float(c.has_credit), "cdt": float(c.has_cdt), "cajitas": float(c.has_pockets),
    }
    cnt = {k: 0 for k in CATEGORIES}
    ch = {k: 0 for k in CHANNELS}
    income_m, fixed_m, spend = set(), set(), 0
    for m in movs:
        if m.category in cnt:
            cnt[m.category] += 1
        if m.channel in ch:
            ch[m.channel] += 1
        if m.category == "Abono recurrente":
            income_m.add(_ym(m.date))
        elif m.amount < 0:
            spend += -m.amount
        if m.category == "Transferencia fija tercero":
            fixed_m.add(_ym(m.date))
    n = len(movs)
    v["log_movs"] = math.log1p(n)
    for k in CATEGORIES:
        v[f"n_{k}"] = math.log1p(cnt[k])
    v["racha_ingreso"] = float(_streak(income_m))
    v["meses_ingreso"] = float(len(income_m))
    v["meses_fija"] = float(len(fixed_m))
    spend_month = spend / 12
    v["ratio_consumo"] = min(spend_month / c.monthly_income, 3.0) if c.monthly_income else 0.0
    v["log_gasto_mes"] = math.log1p(spend_month)
    pk = {k: 0 for k in POCKETS}
    for d in h.deposits:
        if start < d.date <= as_of and d.pocket_type in pk:
            pk[d.pocket_type] += 1
    for k in POCKETS:
        v[f"abonos_{k}"] = math.log1p(pk[k])
    for k in CHANNELS:
        v[f"canal_{k}"] = ch[k] / n if n else 0.0
    v["sesiones"] = float(u.sessions_30d)
    v["visitas_seguros"] = float(u.insurance_visits_30d)
    v["tasa_apertura"] = u.opened_30d / u.notifs_sent_30d if u.notifs_sent_30d else 0.0
    return v
