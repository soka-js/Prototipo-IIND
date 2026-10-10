"""Tipos canónicos. Todo lo que el motor lee tiene esta forma, venga de la base o de un personaje."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

# Ramos de la base del reto (hoja Elegibilidad). «Pago protegido» existe en Lulo y en el prototipo,
# pero no en la base: se maneja aparte y se marca como supuesto.
RAMOS: tuple[str, ...] = ("SOAT", "Vida", "Desempleo", "Hogar", "Mascotas", "Viajes")
PAGO_PROTEGIDO = "Pago protegido"
ALL_RAMOS: tuple[str, ...] = (*RAMOS, PAGO_PROTEGIDO)

# Rangos de edad de la base: (mínimo, máximo); None = sin tope conocido.
AGE_BANDS: dict[str, tuple[int, int | None]] = {
    "18-25": (18, 25), "26-35": (26, 35), "36-45": (36, 45), "46-55": (46, 55), "56+": (56, None),
}


@dataclass(frozen=True, slots=True)
class Movement:
    id: str
    client_id: str
    date: date
    amount: int                    # con signo: + entra, − sale
    channel: str                   # Transferencia, Tarjeta débito, PSE, QR
    category: str                  # categoría de la base (o equivalente para personajes)
    mcc: str
    merchant: str | None = None    # solo personajes: nombre del comercio o del tercero
    channel_label: str | None = None
    counterparty: str | None = None


@dataclass(frozen=True, slots=True)
class PocketDeposit:
    id: str
    client_id: str
    date: date
    pocket_type: str               # Emergencias, Viajes, Otras, Vivienda, Mascotas
    amount: int
    pocket_name: str | None = None


@dataclass(frozen=True, slots=True)
class ExternalPolicy:
    """Pago a una aseguradora externa desde la cuenta (hoja Pagos_Seguros)."""

    id: str
    client_id: str
    paid_on: date
    ramo: str
    amount: int
    expires_on: date
    provider: str


@dataclass(frozen=True, slots=True)
class LuloPolicy:
    """Seguro que el cliente ya tiene con Lulo. `expires_on` es None si la base no trae el vencimiento."""

    ramo: str
    title: str
    partner: str | None = None
    expires_on: date | None = None
    price: int | None = None


@dataclass(frozen=True, slots=True)
class AppUsage:
    sessions_30d: int
    insurance_visits_30d: int
    notifs_sent_30d: int
    opened_30d: int
    ignored_30d: int
    max_contacts_month: int
    event_latency: str
    assumed: bool = False          # True: valores supuestos (personajes), no vienen de la base


@dataclass(frozen=True, slots=True)
class Client:
    id: str
    source: str                    # "reto" | "persona"
    age_band: str
    occupation: str
    tenure_months: int
    segment: str
    avg_balance: int
    monthly_income: int
    has_credit: bool
    has_pockets: bool
    has_cdt: bool
    consent: bool
    lulo_policies: tuple[LuloPolicy, ...]
    usage: AppUsage
    name: str | None = None

    def holds(self, ramo: str) -> bool:
        return any(p.ramo == ramo for p in self.lulo_policies)


@dataclass(slots=True)
class History:
    """Lo que el motor sabe de un cliente: historia de la base más lo que pasó en la sesión."""

    client: Client
    movements: list[Movement] = field(default_factory=list)
    deposits: list[PocketDeposit] = field(default_factory=list)
    external: list[ExternalPolicy] = field(default_factory=list)
