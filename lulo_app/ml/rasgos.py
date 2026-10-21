"""Rasgos genéricos del cliente para el motor bayesiano (pieza B3 de docs/MOTOR.md).

A diferencia de `vector.py` (41 variables fijas que usan M1 y M2), aquí las variables se descubren de los
datos: cada categoría de movimiento, canal de pago, tipo de bolsillo y ocupación que aparezca en la base se
vuelve una variable. Si Lulo entrega una categoría nueva (por ejemplo, combustible), al reentrenar aparece
sola en el vocabulario; el motor le pone una creencia previa centrada en cero y no cambia ninguna decisión
hasta que las respuestas muestren que importa.

Solo se leen campos canónicos (fecha, monto, canal, categoría, tipo de bolsillo, ramo, perfil y uso de la
app): nunca nombres de comercios ni de terceros. «Visitas a Seguros» no entra: es consecuencia de tener un
seguro (decisión de SOKA del 2026-10-20, ver docs/MODELOS.md).

El vocabulario, las medias y las escalas se calculan al entrenar (scripts/train_motor.py) y se guardan en
motor.json; en producción se usan esos mismos valores, así que entrenamiento y producción no difieren.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

from ..core.schema import AGE_BANDS, RAMOS, History

VENTANA_RECIENTE = 90      # días: conteos de movimientos por categoría (lo reciente pesa más que el año)
VENTANA_ANO = 365          # días: canales, gasto y bolsillos
RECORTE_Z = 3.0            # las variables estandarizadas se recortan a [−3, 3]
AGE_ORDER = list(AGE_BANDS)

# De qué hoja de la base sale cada familia de variables (se muestra en el panel y en docs/MOTOR.md).
FUENTES = {
    "perfil": "Clientes", "ocupacion": "Clientes", "mov": "Movimientos", "canal": "Movimientos",
    "gasto": "Movimientos + Clientes", "bolsillo": "Cajitas", "seguros": "Clientes + Pagos_Seguros", "uso": "Uso_App",
}
_PERFIL_LABEL = {
    "perfil:edad": "Rango de edad", "perfil:ingreso": "Ingreso mensual", "perfil:saldo": "Saldo promedio",
    "perfil:antiguedad": "Antigüedad en Lulo", "perfil:credito": "Crédito activo", "perfil:cdt": "CDT activo",
    "perfil:bolsillos": "Usa bolsillos", "perfil:pro": "Segmento Pro", "gasto:ingreso": "Gasto frente a ingreso",
    "seguros:n": "Seguros que ya tiene", "uso:sesiones": "Sesiones en la app", "uso:apertura": "Abre notificaciones",
}


def etiqueta(k: str) -> str:
    if k in _PERFIL_LABEL:
        return _PERFIL_LABEL[k]
    fam, _, v = k.partition(":")
    return {"ocupacion": f"Ocupación: {v.lower()}", "mov": f"Movimientos recientes: {v.lower()}",
            "canal": f"Paga por {v}", "bolsillo": f"Abonos al bolsillo {v.lower()}"}.get(fam, k)


def crudos(h: History, as_of: date, cutoff: date) -> dict[str, float]:
    """Variables antes de estandarizar. El comportamiento se congela en el corte, como en core/features.py."""
    c, u = h.client, h.client.usage
    until = min(as_of, cutoff)
    # Los movimientos de la sesión llevan la fecha de evaluación: cuentan aunque la fecha pase del corte.
    lim = max(as_of, until)
    out: dict[str, float] = {
        "perfil:edad": float(AGE_ORDER.index(c.age_band)) if c.age_band in AGE_ORDER else 1.0,
        "perfil:ingreso": math.log1p(max(c.monthly_income, 0)), "perfil:saldo": math.log1p(max(c.avg_balance, 0)),
        "perfil:antiguedad": float(c.tenure_months), "perfil:credito": float(c.has_credit),
        "perfil:cdt": float(c.has_cdt), "perfil:bolsillos": float(c.has_pockets), "perfil:pro": float(c.segment == "Pro"),
        f"ocupacion:{c.occupation}": 1.0,
    }
    rec, ano = until - timedelta(days=VENTANA_RECIENTE), until - timedelta(days=VENTANA_ANO)
    cats: dict[str, int] = {}
    chans: dict[str, int] = {}
    n_ano, gasto = 0, 0
    for m in h.movements:
        if m.date > lim or m.date <= ano:
            continue
        n_ano += 1
        chans[m.channel] = chans.get(m.channel, 0) + 1
        if m.amount < 0 and m.category != "Abono recurrente":
            gasto += -m.amount
        if m.date > rec:
            cats[m.category] = cats.get(m.category, 0) + 1
    for k, n in cats.items():
        out[f"mov:{k}"] = math.log1p(n)
    for k, n in chans.items():
        out[f"canal:{k}"] = n / n_ano
    out["gasto:ingreso"] = min(gasto / 12 / c.monthly_income, 3.0) if c.monthly_income > 0 else 0.0
    pk: dict[str, int] = {}
    for d in h.deposits:
        if ano < d.date <= lim:
            pk[d.pocket_type] = pk.get(d.pocket_type, 0) + 1
    for k, n in pk.items():
        out[f"bolsillo:{k}"] = math.log1p(n)
    # Solo ramos voluntarios: lo inducido por el crédito (Vida grupo deudor, asistencias) no cuenta.
    held = {p.ramo for p in c.lulo_policies} | {e.ramo for e in h.external if e.paid_on <= until and e.expires_on >= as_of}
    out["seguros:n"] = float(len(held & set(RAMOS)))
    out["uso:sesiones"] = float(u.sessions_30d)
    out["uso:apertura"] = u.opened_30d / u.notifs_sent_30d if u.notifs_sent_30d else 0.0
    return out


def ajustar(filas: list[dict[str, float]]) -> dict:
    """Vocabulario, medias y escalas a partir de los rasgos crudos de la base (al entrenar).

    Una variable entra al vocabulario si aparece en la base y no es constante. Las que faltan en un cliente
    valen 0 (no tiene movimientos de esa categoría, no usa ese canal).
    """
    keys = sorted({k for f in filas for k in f})
    n = len(filas)
    voc, media, escala = [], {}, {}
    for k in keys:
        vals = [f.get(k, 0.0) for f in filas]
        mu = sum(vals) / n
        sd = math.sqrt(sum((v - mu) ** 2 for v in vals) / n)
        if sd < 1e-9:
            continue
        voc.append(k)
        media[k], escala[k] = round(mu, 6), round(sd, 6)
    return {"vocabulario": voc, "media": media, "escala": escala,
            "etiquetas": {k: etiqueta(k) for k in voc},
            "familias": {fam: sum(1 for k in voc if k.split(":")[0] == fam) for fam in FUENTES}}


def estandarizar(raw: dict[str, float], spec: dict) -> dict[str, float]:
    """z = (x − media) / escala, recortado a [−3, 3], para cada variable del vocabulario."""
    out = {}
    for k in spec["vocabulario"]:
        z = (raw.get(k, 0.0) - spec["media"][k]) / spec["escala"][k]
        out[k] = max(-RECORTE_Z, min(RECORTE_Z, z))
    return out
