"""Catálogo de productos: cada cifra sale de la base ingerida, salvo lo marcado como supuesto.

Valor esperado por contacto = conversión previa × comisión esperada a 12 meses × fuerza de la señal.

  comisión esperada a 12 meses
    · pólizas mensuales: prima × comisión × meses esperados, con meses esperados por interpolación
      lineal de la persistencia: 6·(1+p6)/2 + 6·(p6+p12)/2
    · SOAT (anual) y Viajes (por viaje): prima × comisión, un solo pago
  conversión previa = ventas / impactados de la campaña previa del ramo (hoja Campanas_Previas)
"""

from __future__ import annotations

import csv
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from . import rules
from .schema import PAGO_PROTEGIDO, RAMOS

DATASET = Path(__file__).resolve().parent.parent / "dataset"

CAMPAIGN_FOR = {"SOAT renovación": "SOAT", "Seguro vida": "Vida", "Seguro desempleo": "Desempleo",
                "Seguro mascotas": "Mascotas", "Seguro viaje": "Viajes"}

# Lo que ve el cliente. Los aliados vienen de la investigación del equipo; donde no hay aliado conocido
# se dice así en vez de inventarlo.
DISPLAY = {
    "SOAT": {"title": "SOAT", "partner": "Seguros Mundial", "icon": "car",
             "covers": ["Gastos médicos de víctimas de accidentes de tránsito", "Obligatorio para circular en Colombia",
                        "Póliza digital en tu correo"]},
    "Vida": {"title": "Seguro de vida", "partner": "AXA Colpatria", "icon": "heart", "concept": True,
             "covers": ["Tú eliges a quién proteger", "Cubre muerte e incapacidad total permanente",
                        "Independiente de cualquier crédito"]},
    "Desempleo": {"title": "Seguro de desempleo", "partner": "Chubb", "icon": "briefcase",
                  "covers": ["Cubre tus pagos si pierdes el empleo", "Incapacidad total temporal",
                             "Se cobra desde tu cuenta Lulo, sin papeles"]},
    "Hogar": {"title": "Seguro de hogar", "partner": None, "icon": "home",
              "covers": ["Daños por incendio, agua y eventos de la naturaleza", "Hurto de contenidos",
                         "Asistencia de plomería, cerrajería y electricidad"]},
    "Mascotas": {"title": "Seguro de mascotas", "partner": None, "icon": "paw",
                 "covers": ["Consultas veterinarias y urgencias", "Responsabilidad civil por tu mascota",
                            "Para mascotas de 3 meses a 9 años"]},
    "Viajes": {"title": "Seguro de viaje", "partner": "IGS Asistencias", "icon": "plane",
               "covers": ["Asistencia médica en el exterior", "Pérdida o demora de equipaje",
                          "Cancelación del viaje por causa médica"]},
    PAGO_PROTEGIDO: {"title": "Seguro Pago Protegido", "partner": "SBS Seguros", "icon": "shield",
                     "covers": ["Cubre tus cuotas si pierdes tus ingresos", "Incapacidad total temporal",
                                "Se paga junto con la cuota, sin trámites"]},
}


@dataclass(frozen=True)
class Product:
    ramo: str
    title: str
    partner: str | None
    icon: str
    covers: tuple[str, ...]
    concept: bool                  # producto por negociar (no existe hoy en versión voluntaria)
    periodicity: str               # Anual, Mensual, Por viaje
    premium: int | None            # prima promedio de la base
    commission_pct: float | None
    persistence_6m: float | None
    persistence_12m: float | None
    expected_months: float | None
    commission_12m: int | None
    prior: float | None            # conversión previa (ventas / impactados)
    prior_source: str
    age_min: int
    age_max: int | None
    occupations: tuple[str, ...] | None   # None = cualquier ocupación
    requirement: str
    source: str                    # "reto" | "prototipo"

    def expected_value(self, strength: str) -> float | None:
        if self.prior is None or self.commission_12m is None:
            return None
        return self.prior * self.commission_12m * rules.STRENGTH_MULT[strength]

    def price_label(self) -> str:
        if self.premium is None:
            return "Por cotizar"
        n = f"{self.premium:,}".replace(",", ".")
        return {"Mensual": f"${n} al mes", "Anual": f"${n} al año", "Por viaje": f"${n} por viaje"}[self.periodicity]


def _rows(name: str) -> list[dict]:
    with open(DATASET / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _f(v: str) -> float | None:
    return float(v) if v != "" else None


def _age(spec: str) -> tuple[int, int | None]:
    m = re.fullmatch(r"(\d+)\+", spec)
    if m:
        return int(m.group(1)), None
    m = re.fullmatch(r"(\d+)-(\d+)", spec)
    if not m:
        raise ValueError(f"Edad de elegibilidad no reconocida: {spec!r}")
    return int(m.group(1)), int(m.group(2))


@lru_cache(maxsize=None)
def products() -> dict[str, Product]:
    sm: dict[str, list[dict]] = {}
    for r in _rows("seguros_mensual.csv"):
        sm.setdefault(r["ramo"], []).append(r)
    priors = {CAMPAIGN_FOR[r["campana"]]: float(r["conv_ventas_impactados"]) for r in _rows("campanas_previas.csv")}
    eleg = {r["ramo"]: r for r in _rows("elegibilidad.csv")}
    out: dict[str, Product] = {}
    for ramo in RAMOS:
        rows = sm[ramo]
        # La prima, la comisión y la persistencia deben ser constantes en los 12 meses; si no, fallar.
        for col in ("prima_promedio_cop", "comision_pct", "persistencia_6m", "persistencia_12m"):
            vals = {r[col] for r in rows}
            if len(vals) != 1:
                raise ValueError(f"{ramo}: {col} cambia entre meses {sorted(vals)}; el catálogo supone un valor único")
        r0 = rows[0]
        premium, com = int(r0["prima_promedio_cop"]), float(r0["comision_pct"])
        p6, p12 = _f(r0["persistencia_6m"]), _f(r0["persistencia_12m"])
        e = eleg[ramo]
        if e["periodicidad"] == "Mensual":
            if p6 is None or p12 is None:
                raise ValueError(f"{ramo}: póliza mensual sin persistencia")
            months = 6 * (1 + p6) / 2 + 6 * (p6 + p12) / 2
            c12 = round(premium * com * months)
        else:
            months, c12 = None, round(premium * com)
        if ramo in priors:
            prior, src = priors[ramo], "ventas / impactados de la campaña previa"
        else:
            prior, src = min(priors.values()), "supuesto: sin campaña previa, se usa la menor conversión observada"
        lo, hi = _age(e["edad"])
        occ = None if e["ocupacion"] == "Cualquier ocupación" else (e["ocupacion"],)
        d = DISPLAY[ramo]
        out[ramo] = Product(ramo=ramo, title=d["title"], partner=d["partner"], icon=d["icon"], covers=tuple(d["covers"]),
                            concept=d.get("concept", False), periodicity=e["periodicidad"], premium=premium,
                            commission_pct=com, persistence_6m=p6, persistence_12m=p12, expected_months=months,
                            commission_12m=c12, prior=prior, prior_source=src, age_min=lo, age_max=hi,
                            occupations=occ, requirement=e["requisito_simulado"], source="reto")
    d = DISPLAY[PAGO_PROTEGIDO]
    out[PAGO_PROTEGIDO] = Product(
        ramo=PAGO_PROTEGIDO, title=d["title"], partner=d["partner"], icon=d["icon"], covers=tuple(d["covers"]),
        concept=False, periodicity="Mensual", premium=None, commission_pct=None, persistence_6m=None,
        persistence_12m=None, expected_months=None, commission_12m=None, prior=None,
        prior_source="no está en la base: se ofrece solo en el momento del desembolso", age_min=18, age_max=None,
        occupations=None, requirement="Crédito Lulo desembolsado", source="prototipo")
    return out


def product(ramo: str) -> Product:
    return products()[ramo]


def summary() -> list[dict]:
    """Tabla del catálogo para el panel: cada cifra con su origen."""
    out = []
    for p in products().values():
        out.append({"ramo": p.ramo, "title": p.title, "partner": p.partner, "periodicity": p.periodicity,
                    "premium": p.premium, "price": p.price_label(), "commission_pct": p.commission_pct,
                    "expected_months": round(p.expected_months, 2) if p.expected_months else None,
                    "commission_12m": p.commission_12m, "prior": p.prior, "prior_source": p.prior_source,
                    "ev_fuerte": round(p.expected_value("fuerte")) if p.expected_value("fuerte") is not None else None,
                    "age": f"{p.age_min}+" if p.age_max is None else f"{p.age_min}-{p.age_max}",
                    "occupations": p.occupations, "requirement": p.requirement, "source": p.source,
                    "concept": p.concept, "covers": list(p.covers), "icon": p.icon})
    return out
