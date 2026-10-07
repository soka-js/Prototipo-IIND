"""Catálogo del prototipo: eventos, ofertas y estado inicial del cliente.

Todos los datos (nombres, placas, precios, cifras) son ilustrativos.
"""

from __future__ import annotations

# Eventos que el motor sabe leer. `prio`: 1 = mayor prioridad.
EVENTS: dict[str, dict] = {
    "credito": {
        "label": "Desembolso de Lulo Crédito",
        "habit": "Nueva obligación mensual",
        "offer": "Pago protegido",
        "prio": 1,
        "mov": {"n": "Desembolso Lulo Crédito", "c": "Crédito", "a": 9_000_000, "ic": "💳"},
    },
    "vehiculo": {
        "label": "Peajes, combustible y parqueaderos",
        "habit": "Uso frecuente de vehículo propio",
        "offer": "SOAT y seguros del carro",
        "prio": 2,
        "mov": {"n": "Peaje Andes · Autopista Norte", "c": "Transporte", "a": -12_800, "ic": "🛣️"},
    },
    "nomina": {
        "label": "Tercer abono de nómina de ACME S.A.S.",
        "habit": "Ingreso laboral estable",
        "offer": "Seguro de nómina",
        "prio": 3,
        "mov": {"n": "Nómina ACME S.A.S.", "c": "Abono recurrente", "a": 3_200_000, "ic": "💼"},
    },
    "viaje": {
        "label": "Abono a la cajita «Viajes»",
        "habit": "Hay un viaje en preparación",
        "offer": "Seguro de viaje",
        "prio": 4,
        "mov": {"n": "Cajita Viajes · abono 4", "c": "Cajitas", "a": -300_000, "ic": "✈️"},
    },
    "vida": {
        "label": "Transferencia fija a Laura M. (mes 4)",
        "habit": "Hay dependientes económicos",
        "offer": "Vida voluntario",
        "prio": 5,
        "mov": {"n": "Transferencia a Laura M.", "c": "Bre-B", "a": -450_000, "ic": "↗"},
    },
}

OFFERS: dict[str, dict] = {
    "nomina": {
        "title": "Seguro de nómina",
        "aliado": "Chubb",
        "price": "$14.500 al mes",
        "why": "Recibiste tu <b>tercer abono seguido de ACME S.A.S.</b> en Lulo. Tu ingreso ya tiene un respaldo.",
        "figure": "3 meses",
        "figLabel": "de tu ingreso cubiertos si pierdes el empleo",
        "covers": [
            "Hasta 3 cuotas de $1.200.000 si pierdes tu empleo",
            "Incapacidad total temporal",
            "Se cobra desde tu cuenta Lulo, sin papeles",
        ],
        "sub": "3 meses de ingreso cubiertos",
        "notif": "Tu ingreso llega a Lulo. Protégelo desde $14.500 al mes.",
    },
    "viaje": {
        "title": "Seguro de viaje",
        "aliado": "IGS Asistencias",
        "price": "$18.900 por viaje",
        "why": "Llevas <b>4 abonos a tu cajita «Viajes»</b>. Parece que estás preparando un viaje.",
        "figure": "USD 30.000",
        "figLabel": "en asistencia médica en el exterior",
        "covers": [
            "Asistencia médica y odontológica en el exterior",
            "Pérdida o demora de equipaje",
            "Cancelación del viaje por causa médica",
        ],
        "sub": "Activo para tu próximo viaje",
        "notif": "Tu cajita «Viajes» va bien. Viaja con asistencia médica.",
    },
    "vida": {
        "title": "Vida voluntario",
        "aliado": "AXA Colpatria",
        "price": "$22.000 al mes",
        "concept": True,
        "why": "Cada mes <b>envías dinero a la misma persona</b>. Si alguien depende de ti, este seguro la protege.",
        "figure": "$50.000.000",
        "figLabel": "de suma asegurada",
        "covers": [
            "Tú eliges quién es el beneficiario",
            "Cubre muerte e incapacidad total permanente",
            "Independiente de cualquier crédito",
        ],
        "sub": "Beneficiaria: Laura M.",
        "notif": "Protege a quien depende de ti desde $22.000 al mes.",
    },
}

INITIAL_POLICIES: list[dict] = [
    {"id": "soat", "title": "SOAT · WGY-482", "aliado": "Seguros Mundial", "status": "due",
     "sub": "vence el 14 de octubre", "days": 27},
    {"id": "pago", "title": "Pago protegido", "aliado": "SBS Seguros", "status": "ok",
     "sub": "ligado a tu Lulo Crédito", "hint": "Nunca has revisado qué cubre"},
    {"id": "vida", "title": "Vida grupo deudor", "aliado": "AXA Colpatria", "status": "ok",
     "sub": "beneficiario: el banco"},
    {"id": "asis", "title": "Asistencias", "aliado": "IGS", "status": "ok",
     "sub": "renovación automática en enero"},
]

INITIAL_MOVS: list[dict] = [
    {"n": "Terpel · Calle 80", "c": "Combustible", "a": -98_000, "ic": "⛽", "d": "Hoy"},
    {"n": "Nómina ACME S.A.S.", "c": "Abono recurrente", "a": 3_200_000, "ic": "💼", "d": "15 sep"},
    {"n": "Parqueadero Andino", "c": "Transporte", "a": -14_000, "ic": "🅿️", "d": "14 sep"},
    {"n": "Transferencia a Laura M.", "c": "Bre-B", "a": -450_000, "ic": "↗", "d": "1 sep"},
    {"n": "Cuota Lulo Crédito 3/18", "c": "Crédito", "a": -275_192, "ic": "💳", "d": "30 ago"},
    {"n": "Spotify", "c": "Suscripción", "a": -26_900, "ic": "♫", "d": "28 ago"},
]

INITIAL_BALANCE = 1_742_300

# SOAT del vehículo del cliente
SOAT_BASE_PRICE = 745_300
SOAT_MAX_DISCOUNT = 0.05  # con aviso a 30 días; se escala con la anticipación
ALERT_DAYS_OPTIONS = (30, 15, 7)
