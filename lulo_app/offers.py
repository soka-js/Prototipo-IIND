"""Ofertas personalizadas: el texto «Por qué lo ves» sale de la señal que la disparó."""

from __future__ import annotations

from functools import lru_cache

from . import fmt
from .signals import for_persona as signals_for
from .simulator import get

BASE: dict[str, dict] = {
    "nomina": {
        "title": "Seguro de nómina", "aliado": "Chubb", "price": "$14.500 al mes",
        "figure": "3 meses", "figLabel": "de tu ingreso cubiertos si pierdes el empleo",
        "covers": ["Hasta 3 cuotas de $1.200.000 si pierdes tu empleo", "Incapacidad total temporal",
                   "Se cobra desde tu cuenta Lulo, sin papeles"],
        "sub": "3 meses de ingreso cubiertos",
        "notif": "Tu ingreso llega a Lulo. Protégelo desde $14.500 al mes.",
    },
    "viaje": {
        "title": "Seguro de viaje", "aliado": "IGS Asistencias", "price": "$18.900 por viaje",
        "figure": "USD 30.000", "figLabel": "en asistencia médica en el exterior",
        "covers": ["Asistencia médica y odontológica en el exterior", "Pérdida o demora de equipaje",
                   "Cancelación del viaje por causa médica"],
        "sub": "Activo para tu próximo viaje",
        "notif": "Viaja con asistencia médica desde $18.900 por viaje.",
    },
    "vida": {
        "title": "Vida voluntario", "aliado": "AXA Colpatria", "price": "$22.000 al mes", "concept": True,
        "figure": "$50.000.000", "figLabel": "de suma asegurada",
        "covers": ["Tú eliges quién es el beneficiario", "Cubre muerte e incapacidad total permanente",
                   "Independiente de cualquier crédito"],
        "sub": "Beneficiarios elegidos por ti",
        "notif": "Protege a quien depende de ti desde $22.000 al mes.",
    },
    "pago": {
        "title": "Pago protegido", "aliado": "SBS Seguros", "price": "$9.800 al mes, con tu cuota",
        "figure": "6 cuotas", "figLabel": "de tu crédito cubiertas si pierdes tus ingresos",
        "covers": ["Hasta 6 cuotas si pierdes tu empleo o tus ingresos", "Incapacidad total temporal",
                   "Se paga junto con la cuota, sin trámites"],
        "sub": "Ligado a tu Lulo Crédito",
        "notif": "Que tus cuotas no se detengan si algo pasa.",
    },
}


@lru_cache(maxsize=None)
def for_persona(persona_id: str) -> dict[str, dict]:
    p = get(persona_id)
    sig = signals_for(persona_id)
    out = {k: dict(v) for k, v in BASE.items()}

    nom = sig["nomina"]["metrics"]
    if sig["nomina"]["detected"]:
        out["nomina"]["why"] = (f"Recibiste tu <b>{fmt.ordinal(nom['streak'])} abono seguido de {nom['employer']}</b> "
                                f"en Lulo. Tu ingreso ya tiene un respaldo.")
    else:
        out["nomina"]["why"] = "Recibiste un abono en Lulo."

    tr = sig["viaje"]["metrics"]
    if tr["deposits"]:
        out["viaje"]["why"] = (f"Llevas <b>{tr['deposits']} abonos a tu cajita «{tr['cajita']}»</b>. "
                               f"Parece que estás preparando un viaje.")
        out["viaje"]["notif"] = f"Tu cajita «{tr['cajita']}» va bien. Viaja con asistencia médica."
    else:
        airline = p.events["viaje"]["mov"]["n"].split(" · ")[0]
        out["viaje"]["why"] = f"Acabas de <b>comprar tiquetes en {airline}</b>. Que el viaje sea solo de buenos recuerdos."
        out["viaje"]["notif"] = f"Compraste tiquetes en {airline}. Viaja con asistencia médica."

    bens = sig["vida"]["metrics"]["beneficiaries"]
    if len(bens) == 1:
        out["vida"]["why"] = (f"Cada mes <b>envías dinero a {bens[0]['name']}</b>. Si alguien depende de ti, "
                              f"este seguro la protege.")
        out["vida"]["sub"] = f"Beneficiaria: {bens[0]['name']}"
    elif bens:
        out["vida"]["why"] = ("Cada mes <b>pagas el colegio y apoyas a tu familia</b>. Si alguien depende de ti, "
                              "este seguro la protege.")
        out["vida"]["sub"] = "Beneficiarios: tu familia"
    else:
        out["vida"]["why"] = "Acabas de enviar dinero a alguien cercano. Si alguien depende de ti, este seguro la protege."

    first = not p.credit
    out["pago"]["why"] = (f"Acabas de recibir <b>{'tu primer' if first else 'un nuevo'} desembolso de Lulo Crédito</b>. "
                          f"Si algo pasa, tus cuotas no se detienen.")
    return out
