"""Paso 1: señales. Una por ramo, con fuerza, regla y evidencia legible.

Fuerzas: «fuerte» y «media» pueden convertirse en oferta; «débil» queda registrada pero no se
ofrece; «ninguna» significa que no hay rastro del hábito.

Tipos (kind):
  nuevo       ofrecer un seguro que el cliente no tiene
  renovacion  el SOAT que ya tiene con Lulo está por vencer
  captura     el SOAT con otra aseguradora está por vencer: renovarlo en Lulo
  cotizacion  usa vehículo pero no se le conoce SOAT: invitar a cotizar
  recuperar   pagó ese seguro por fuera y ya venció
  momento     momento único (desembolso de crédito)
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field

from . import rules
from .features import Features
from .schema import PAGO_PROTEGIDO, RAMOS
from .text import cop, date_long, millions, plural

NAMES = {
    "SOAT": "Uso de vehículo", "Vida": "Dependientes económicos", "Desempleo": "Ingreso laboral estable",
    "Hogar": "Ahorro para vivienda", "Mascotas": "Tiene mascota", "Viajes": "Viaje en preparación",
    PAGO_PROTEGIDO: "Nueva obligación de crédito",
}


@dataclass
class Signal:
    ramo: str
    name: str
    strength: str          # fuerte | media | débil | ninguna
    kind: str
    rule: str
    headline: str
    evidence: list[str] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    @property
    def actionable(self) -> bool:
        return self.strength in ("fuerte", "media")

    def to_dict(self) -> dict:
        return asdict(self)


def _external(f: Features, ramo: str) -> list[dict]:
    return [e for e in f.external if e["ramo"] == ramo]


def _recover(f: Features, ramo: str) -> Signal | None:
    """Pagó el ramo por fuera y la póliza ya venció: interés fuerte (regla aprobada)."""
    lapsed = [e for e in _external(f, ramo) if e["status"] == "vencida"]
    if not lapsed or any(e["status"] == "vigente" for e in _external(f, ramo)):
        return None
    e = max(lapsed, key=lambda x: x["expires_on"])
    return Signal(ramo, NAMES[ramo], "fuerte", "recuperar",
                  "Pagó este seguro a otra aseguradora y la póliza venció",
                  f"Su seguro de {ramo.lower()} con otra aseguradora venció el {date_long(e['expires_on'], False)}",
                  [f"Pago de {cop(e['amount'])} el {date_long(e['paid_on'], False)} a «{e['provider']}»",
                   f"Vencimiento: {date_long(e['expires_on'])}"],
                  {"lapsed_on": e["expires_on"]})


def desempleo(f: Features) -> Signal:
    rule = (f"Empleado con {rules.DESEMPLEO_MIN_STREAK} o más abonos recurrentes seguidos (proxy de la antigüedad "
            f"laboral de la hoja Elegibilidad); fuerte si además tiene crédito activo")
    m = {"streak": f.income_streak, "current": f.income_current, "amount": f.income_amount,
         "has_credit": f.has_credit}
    if not f.income_months:
        return Signal("Desempleo", NAMES["Desempleo"], "ninguna", "nuevo", rule,
                      "Sin abonos recurrentes en Lulo", ["Ningún ingreso llega como abono recurrente"], m)
    ev = [f"{plural(f.income_streak, 'abono recurrente seguido', 'abonos recurrentes seguidos')}"
          + (f" de {cop(f.income_amount)}" if f.income_amount else ""),
          f"Último abono: {date_long(f.income_last, False)}" + ("" if f.income_current else " (racha interrumpida)")]
    if f.has_credit:
        ev.append("Tiene un crédito activo: el seguro protegería sus cuotas")
    ok = f.income_current and f.income_streak >= rules.DESEMPLEO_MIN_STREAK
    strength = ("fuerte" if f.has_credit else "media") if ok else "débil"
    head = (f"{f.income_streak} meses seguidos de ingreso en Lulo" if ok else
            f"{f.income_streak} de {rules.DESEMPLEO_MIN_STREAK} abonos seguidos")
    return Signal("Desempleo", NAMES["Desempleo"], strength, "nuevo", rule, head, ev, m)


def vida(f: Features) -> Signal:
    rule = (f"Transferencias fijas a un tercero en {rules.VIDA_MIN_MONTHS} o más meses distintos; fuerte si además "
            f"recibe ingreso recurrente ({rules.VIDA_INCOME_MIN_STREAK}+ abonos seguidos)")
    m = {"months": f.fixed_months, "amounts": f.fixed_amounts, "total": f.fixed_total,
         "counterparties": f.fixed_counterparties}
    if not f.fixed_months:
        return _recover(f, "Vida") or Signal("Vida", NAMES["Vida"], "ninguna", "nuevo", rule,
                                             "Sin transferencias fijas a terceros",
                                             ["Ninguna transferencia fija en 12 meses"], m)
    who = f" a {', '.join(f.fixed_counterparties[:2])}" if f.fixed_counterparties else ""
    amt = (cop(f.fixed_amounts[0]) if len(f.fixed_amounts) == 1 else
           f"entre {cop(f.fixed_amounts[0])} y {cop(f.fixed_amounts[-1])}")
    ev = [f"{plural(f.fixed_months, 'mes', 'meses')} con transferencias fijas{who} de {amt}",
          f"{millions(f.fixed_total)} enviados en 12 meses"]
    income = f.income_current and f.income_streak >= rules.VIDA_INCOME_MIN_STREAK
    if income:
        ev.append(f"Recibe ingreso recurrente ({f.income_streak} abonos seguidos)")
    if f.fixed_months >= rules.VIDA_MIN_MONTHS:
        strength = "fuerte" if income else "media"
    else:
        strength = "débil"
    head = f"{millions(f.fixed_total)} enviados{who} en {plural(f.fixed_months, 'mes', 'meses')}"
    sig = Signal("Vida", NAMES["Vida"], strength, "nuevo", rule, head, ev, m)
    rec = _recover(f, "Vida")
    return rec if rec and strength != "fuerte" else sig


def viajes(f: Features) -> Signal:
    rule = (f"Compra en aerolínea u hotel en los últimos {rules.VIAJES_PURCHASE_DAYS} días, o "
            f"{rules.VIAJES_POCKET_MIN} o más abonos a un bolsillo de viajes; fuerte si hay ambas cosas")
    pocket = f.pockets_12m.get("Viajes", 0)
    recent = [t for t in f.travel_12m if t["days_ago"] <= rules.VIAJES_PURCHASE_DAYS]
    m = {"pocket_deposits": pocket, "pocket_total": f.pockets_total.get("Viajes", 0), "purchases_90d": len(recent),
         "purchases_12m": len(f.travel_12m), "pocket_name": f.pocket_names.get("Viajes")}
    ev = []
    if pocket:
        name = f.pocket_names.get("Viajes", "Viajes")
        ev.append(f"{plural(pocket, 'abono', 'abonos')} al bolsillo «{name}» por {cop(m['pocket_total'])}")
    for t in recent[-3:]:
        where = t["merchant"] or ("una aerolínea" if t["category"] == "Aerolineas" else "un hotel")
        ev.append(f"Compra en {where} por {cop(t['amount'])} hace {t['days_ago']} días")
    if not ev:
        ev.append("Sin compras de viaje recientes ni bolsillo de viajes"
                  + (f" ({len(f.travel_12m)} compras de viaje hace más de {rules.VIAJES_PURCHASE_DAYS} días)"
                     if f.travel_12m else ""))
    has_p, has_b = bool(recent), pocket >= rules.VIAJES_POCKET_MIN
    if has_p and pocket >= 1:
        strength = "fuerte"
    elif has_p or has_b:
        strength = "media"
    elif pocket or f.travel_12m:
        strength = "débil"
    else:
        strength = "ninguna"
    head = ("Compró un viaje y está ahorrando para él" if strength == "fuerte" else
            f"Compra de viaje hace {recent[-1]['days_ago']} días" if has_p else
            f"{pocket} abonos a su bolsillo de viajes" if has_b else
            "Rastros de viaje sin fuerza suficiente" if strength == "débil" else "Sin señal de viaje")
    return Signal("Viajes", NAMES["Viajes"], strength, "nuevo", rule, head, ev, m)


def mascotas(f: Features) -> Signal:
    rule = (f"{rules.MASCOTAS_SPEND_MIN} o más compras en tiendas de mascotas (MCC 5995) o un bolsillo de mascotas; "
            f"fuerte si hay ambas cosas")
    pocket = f.pockets_12m.get("Mascotas", 0)
    m = {"spend_12m": f.pet_spend_12m, "pocket_deposits": pocket}
    ev = []
    if f.pet_spend_12m:
        ev.append(f"{plural(f.pet_spend_12m, 'compra', 'compras')} en tiendas de mascotas en 12 meses")
    if pocket:
        ev.append(f"{plural(pocket, 'abono', 'abonos')} a un bolsillo de mascotas")
    if not ev:
        ev.append("Sin compras de mascotas ni bolsillo de mascotas")
    if f.pet_spend_12m >= 1 and pocket >= rules.MASCOTAS_POCKET_MIN:
        strength = "fuerte"
    elif f.pet_spend_12m >= rules.MASCOTAS_SPEND_MIN or pocket >= rules.MASCOTAS_POCKET_MIN:
        strength = "media"
    elif f.pet_spend_12m:
        strength = "débil"
    else:
        strength = "ninguna"
    head = {"fuerte": "Compra para su mascota y ahorra para ella", "media": "Señales de que tiene mascota",
            "débil": "Una compra suelta en tienda de mascotas", "ninguna": "Sin señal de mascota"}[strength]
    sig = Signal("Mascotas", NAMES["Mascotas"], strength, "nuevo", rule, head, ev, m)
    rec = _recover(f, "Mascotas")
    return rec if rec and strength != "fuerte" else sig


def hogar(f: Features) -> Signal:
    rule = f"{rules.HOGAR_POCKET_MIN} o más abonos a un bolsillo de vivienda en 12 meses"
    pocket = f.pockets_12m.get("Vivienda", 0)
    m = {"pocket_deposits": pocket, "pocket_total": f.pockets_total.get("Vivienda", 0)}
    if pocket >= rules.HOGAR_POCKET_MIN:
        strength = "media"
    elif pocket:
        strength = "débil"
    else:
        strength = "ninguna"
    ev = ([f"{plural(pocket, 'abono', 'abonos')} al bolsillo de vivienda por {cop(m['pocket_total'])}"] if pocket
          else ["Sin bolsillo de vivienda"])
    head = f"Ahorra para su vivienda ({pocket} abonos)" if pocket else "Sin señal de vivienda"
    sig = Signal("Hogar", NAMES["Hogar"], strength, "nuevo", rule, head, ev, m)
    rec = _recover(f, "Hogar")
    return rec if rec else sig


def soat(f: Features, alert_days: int) -> Signal:
    m = {"tolls_12m": f.tolls_12m, "top_toll": f.top_toll, "expiry": f.soat_expiry.isoformat() if f.soat_expiry else None,
         "days": f.soat_days, "source": f.soat_source, "alert_days": alert_days}
    if f.soat_expiry is not None:
        rule = f"SOAT con vencimiento conocido dentro de los próximos {alert_days} días"
        ev = [f"Vence el {date_long(f.soat_expiry)} (en {f.soat_days} días)",
              "Con Lulo (Seguros Mundial)" if f.soat_source == "lulo" else "Con otra aseguradora (pago desde la cuenta)"]
        if f.tolls_12m:
            ev.append(f"{plural(f.tolls_12m, 'peaje', 'peajes')} en 12 meses")
        kind = "renovacion" if f.soat_source == "lulo" else "captura"
        if 0 <= f.soat_days <= alert_days:
            return Signal("SOAT", "SOAT por vencer", "fuerte", kind, rule, f"Su SOAT vence en {f.soat_days} días", ev, m)
        if f.soat_days < 0:
            return Signal("SOAT", "SOAT vencido", "fuerte", kind, rule, f"Su SOAT venció hace {-f.soat_days} días", ev, m)
        return Signal("SOAT", "SOAT al día", "débil", kind, rule,
                      f"Su SOAT vence en {f.soat_days} días: el aviso llega {alert_days} días antes", ev, m)
    rec = _recover(f, "SOAT")
    if rec:
        rec.kind = "captura"
        return rec
    rule = (f"{rules.SOAT_TOLLS_MEDIA} o más peajes en 12 meses (media), {rules.SOAT_TOLLS_FUERTE} o más (fuerte), "
            f"sin SOAT conocido")
    ev = [f"{plural(f.tolls_12m, 'peaje', 'peajes')} en 12 meses" + (f"; el más frecuente: {f.top_toll}" if f.top_toll else ""),
          "La base no trae combustible: la señal se apoya solo en peajes"]
    if "SOAT" in f.lulo_ramos:
        ev.append("Tiene SOAT con Lulo, pero la base no trae su vencimiento")
    if f.tolls_12m >= rules.SOAT_TOLLS_FUERTE:
        strength = "fuerte"
    elif f.tolls_12m >= rules.SOAT_TOLLS_MEDIA:
        strength = "media"
    elif f.tolls_12m:
        strength = "débil"
    else:
        strength = "ninguna"
    head = f"{plural(f.tolls_12m, 'peaje', 'peajes')} en 12 meses" if f.tolls_12m else "Sin señal de vehículo"
    return Signal("SOAT", NAMES["SOAT"], strength, "cotizacion", rule, head, ev, m)


def pago_protegido(disbursement: int | None) -> Signal:
    rule = "Desembolso de Lulo Crédito sin pago protegido (momento único: solo ocurre al desembolsar)"
    if disbursement is None:
        return Signal(PAGO_PROTEGIDO, NAMES[PAGO_PROTEGIDO], "ninguna", "momento", rule,
                      "Sin desembolso en esta sesión", ["El motor solo lo evalúa cuando hay un desembolso"], {})
    return Signal(PAGO_PROTEGIDO, NAMES[PAGO_PROTEGIDO], "fuerte", "momento", rule,
                  f"Acaba de recibir un desembolso de {cop(disbursement)}",
                  [f"Desembolso de Lulo Crédito por {cop(disbursement)}"], {"amount": disbursement})


def detect(f: Features, alert_days: int = rules.SOAT_REMINDER_DAYS, disbursement: int | None = None) -> dict[str, Signal]:
    out = {"SOAT": soat(f, alert_days), "Desempleo": desempleo(f), "Vida": vida(f), "Viajes": viajes(f),
           "Mascotas": mascotas(f), "Hogar": hogar(f), PAGO_PROTEGIDO: pago_protegido(disbursement)}
    assert set(out) == {*RAMOS, PAGO_PROTEGIDO}
    return out
