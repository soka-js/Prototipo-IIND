"""Catálogo común: tipos de evento, prioridades y precios. Los datos de cada cliente viven en simulator.py."""

from __future__ import annotations

from .simulator import CATEGORIES, TODAY, Persona

# Tipos de evento que el motor sabe leer. `prio`: 1 = mayor prioridad.
EVENT_META: dict[str, dict] = {
    "credito": {"habit": "Nueva obligación mensual", "offer": "Pago protegido", "offer_key": "pago", "prio": 1},
    "vehiculo": {"habit": "Uso frecuente de vehículo propio", "offer": "SOAT y seguros del carro", "offer_key": "soat",
                 "prio": 2},
    "nomina": {"habit": "Ingreso laboral estable", "offer": "Seguro de nómina", "offer_key": "nomina", "prio": 3},
    "viaje": {"habit": "Hay un viaje en preparación", "offer": "Seguro de viaje", "offer_key": "viaje", "prio": 4},
    "vida": {"habit": "Hay dependientes económicos", "offer": "Vida voluntario", "offer_key": "vida", "prio": 5},
}

SOAT_MAX_DISCOUNT = 0.05  # con aviso a 30 días; se escala con la anticipación
ALERT_DAYS_OPTIONS = (30, 15, 7)


def movement(spec: dict, persona: Persona, **extra) -> dict:
    """Completa un movimiento nuevo (categoría, grupo, ícono y medio de pago) a partir de un spec corto."""
    label, group, icon = CATEGORIES[spec["cat"]]
    return {
        "n": spec["n"], "c": label, "cat": spec["cat"], "g": group, "a": int(spec["a"]),
        "ic": spec.get("ic", icon), "ch": spec.get("ch", f"Tarjeta débito ••{persona.card_last4}"),
        "date": TODAY.isoformat(), **extra,
    }


def events_for(p: Persona) -> dict[str, dict]:
    out = {}
    for key, meta in EVENT_META.items():
        e = p.events[key]
        out[key] = {"key": key, "label": e["label"], "habit": meta["habit"], "offer": meta["offer"],
                    "prio": meta["prio"], "strong": e.get("strong", False), "mov": movement(e["mov"], p)}
    return out


def soat_quote(price: int, alert_days: int) -> dict:
    """Precio de renovación con descuento proporcional a la anticipación del aviso."""
    if alert_days not in ALERT_DAYS_OPTIONS:
        raise ValueError(f"alert_days debe ser uno de {ALERT_DAYS_OPTIONS}")
    discount = round(price * SOAT_MAX_DISCOUNT * (alert_days / 30))
    return {"days": alert_days, "base": price, "discount": discount, "total": price - discount}
