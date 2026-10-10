"""Los tres personajes de la presentación traducidos al esquema de la base.

Así el motor v3 corre igual para Sebastián, Valentina y Andrés que para los 600 clientes:
lee solo los campos que la base también tiene (fecha, monto, canal, categoría, MCC). El
nombre del comercio y del tercero se conservan aparte para mostrarlos, nunca para decidir.

Fechas: los personajes se generaron con «hoy» = 2026-09-17. Se corren para que su «hoy»
coincida con la fecha de corte de la base; los días que faltan para cada evento no cambian.
"""

from __future__ import annotations

from datetime import date, timedelta

from .. import simulator
from .schema import AppUsage, Client, History, LuloPolicy, Movement, PocketDeposit

# Categoría del simulador → (categoría canónica, MCC). Las que no existen en la base quedan con
# nombre propio y el motor no las usa para decidir.
_CAT = {
    "peajes": ("Peajes", "4784"), "combustible": ("Combustible", "5541"), "parqueadero": ("Parqueaderos", "7523"),
    "movilidad": ("Transporte", "4121"), "mercado": ("Supermercados", "5411"), "restaurantes": ("Restaurantes", "5812"),
    "domicilios": ("Restaurantes", "5812"), "cafe": ("Restaurantes", "5812"), "suscripciones": ("E-commerce", "5969"),
    "compras": ("E-commerce", "5969"), "servicios": ("Servicios", "4900"), "salud": ("Salud", "8099"),
    "entretenimiento": ("Otros", "5999"), "viajes": ("Aerolineas", "4511"), "seguros": ("Seguros", "6300"),
    "arriendo": ("Arriendo", "6513"), "credito": ("Cuota crédito", ""), "desembolso": ("Desembolso crédito", ""),
    "ingreso": ("Ingreso ocasional", ""), "educacion": ("Educación", "8211"), "transferencia": ("Transferencia", ""),
}
_POCKET = {"viajes": "Viajes", "peru": "Viajes", "emergencias": "Emergencias", "matricula": "Otras",
           "carro": "Otras", "equipo": "Otras"}
_RAMO_OF_OFFER = {"soat": "SOAT", "pago": "Pago protegido", "nomina": "Desempleo"}

# Uso de la app: la base no lo trae para los personajes. Valores supuestos, marcados como tales.
_USAGE = {
    "sebastian": AppUsage(24, 1, 1, 1, 0, 4, "<1 min", assumed=True),
    "valentina": AppUsage(31, 2, 2, 1, 1, 4, "1-5 min", assumed=True),
    "andres": AppUsage(12, 0, 3, 1, 2, 4, "<1 min", assumed=True),
}
_OCCUPATION = {"sebastian": "Empleado", "valentina": "Independiente", "andres": "Empleado"}


def _band(age: int) -> str:
    for band, (lo, hi) in (("18-25", (18, 25)), ("26-35", (26, 35)), ("36-45", (36, 45)), ("46-55", (46, 55))):
        if lo <= age <= hi:
            return band
    return "56+"


def _channel(ch: str) -> str:
    if ch.startswith("Tarjeta"):
        return "Tarjeta débito"
    if ch == "PSE":
        return "PSE"
    return "Transferencia"


def shift_days(cutoff: date) -> int:
    return (cutoff - simulator.TODAY).days


def translate(p: simulator.Persona, cutoff: date) -> History:
    shift = timedelta(days=shift_days(cutoff))
    names = {c["id"]: c["name"] for c in p.contacts}
    pockets = {c["id"]: c for c in p.cajitas}
    movs, deps = [], []
    for t in p.txs:
        d = date.fromisoformat(t["date"]) + shift
        if t["cat"] == "cajitas":
            caj = pockets[t["cp"]]
            deps.append(PocketDeposit(id=t["id"], client_id=p.id, date=d, pocket_type=_POCKET[caj["id"]],
                                      amount=-t["a"], pocket_name=caj["name"]))
            continue
        if t["cat"] == "nomina":
            # Solo el abono mensual del empleador es ingreso recurrente; la prima es un ingreso ocasional.
            cat, mcc = ("Abono recurrente", "0000") if t["n"].startswith("Nómina") else ("Ingreso ocasional", "")
        elif t.get("tag") == "vida" and t["a"] < 0:
            cat, mcc = "Transferencia fija tercero", "0001"
        else:
            cat, mcc = _CAT[t["cat"]]
        movs.append(Movement(id=t["id"], client_id=p.id, date=d, amount=t["a"], channel=_channel(t["ch"]),
                             category=cat, mcc=mcc, merchant=t["n"], channel_label=t["ch"],
                             counterparty=names.get(t["cp"]) if t.get("cp") else None))
    policies = []
    for pol in p.policies:
        ramo = _RAMO_OF_OFFER.get(pol["offer"] or "")
        if ramo is None:
            # Vida grupo deudor y asistencias: inducidos por el crédito, no son el ramo voluntario.
            policies.append(LuloPolicy(ramo=pol["title"], title=pol["title"], partner=pol["aliado"]))
            continue
        exp = date.fromisoformat(p.car["soat_expiry"]) + shift if ramo == "SOAT" else None
        price = p.car["soat_price"] if ramo == "SOAT" else None
        policies.append(LuloPolicy(ramo=ramo, title=pol["title"], partner=pol["aliado"], expires_on=exp, price=price))
    income = [t["a"] for t in p.txs if t["cat"] == "nomina" and t["n"].startswith("Nómina")]
    monthly = income[0] if income else round(sum(t["a"] for t in p.txs if t["cat"] == "ingreso" and t.get("tag") == "nomina") / 12)
    tenure = (cutoff.year - p.since) * 12 + cutoff.month
    c = Client(id=p.id, source="persona", age_band=_band(p.age), occupation=_OCCUPATION[p.id], tenure_months=tenure,
               segment="No Pro", avg_balance=p.balance, monthly_income=monthly, has_credit=bool(p.credit),
               has_pockets=bool(p.cajitas), has_cdt=False, consent=True, lulo_policies=tuple(policies),
               usage=_USAGE[p.id], name=p.full)
    movs.sort(key=lambda m: (m.date, m.id))
    deps.sort(key=lambda x: (x.date, x.id))
    return History(client=c, movements=movs, deposits=deps, external=[])


def load_personas(cutoff: date) -> dict[str, History]:
    return {pid: translate(p, cutoff) for pid, p in simulator.personas().items()}
