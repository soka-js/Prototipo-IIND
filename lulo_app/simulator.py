"""Clientes simulados y un año de movimientos para cada uno.

Los movimientos se generan con una semilla fija: cada vez que corre la app salen
exactamente los mismos datos, así que las cifras de Tu año y las decisiones del
motor son reproducibles. Todo es ilustrativo.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from datetime import date, timedelta
from functools import lru_cache

TODAY = date(2026, 9, 17)          # "hoy" dentro de la simulación
PERIOD_START = date(2025, 10, 1)   # Tu año: octubre 2025 → septiembre 2026
MONTHS = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]
MONTHS_LONG = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto",
               "septiembre", "octubre", "noviembre", "diciembre"]

# Categoría → (etiqueta, grupo del filtro, ícono por defecto)
CATEGORIES: dict[str, tuple[str, str, str]] = {
    "nomina": ("Abono de nómina", "ingresos", "💼"),
    "ingreso": ("Ingreso", "ingresos", "↙"),
    "desembolso": ("Crédito", "ingresos", "💳"),
    "peajes": ("Peaje", "transporte", "🛣️"),
    "combustible": ("Combustible", "transporte", "⛽"),
    "parqueadero": ("Parqueadero", "transporte", "🅿️"),
    "movilidad": ("Movilidad", "transporte", "🚕"),
    "mercado": ("Mercado", "comida", "🛒"),
    "restaurantes": ("Restaurantes", "comida", "🍽️"),
    "domicilios": ("Domicilios", "comida", "🛵"),
    "cafe": ("Café", "comida", "☕"),
    "transferencia": ("Bre-B", "transferencias", "↗"),
    "suscripciones": ("Suscripción", "pagos", "♫"),
    "servicios": ("Servicios del hogar", "pagos", "💡"),
    "credito": ("Crédito", "pagos", "💳"),
    "educacion": ("Educación", "pagos", "🎓"),
    "seguros": ("Seguros", "pagos", "🛡️"),
    "arriendo": ("Arriendo", "pagos", "🏠"),
    "salud": ("Salud", "compras", "💊"),
    "compras": ("Compras", "compras", "🛍️"),
    "entretenimiento": ("Entretenimiento", "compras", "🎬"),
    "viajes": ("Viajes", "compras", "✈️"),
    "cajitas": ("Cajitas", "ahorro", "🐷"),
}
GROUPS = [
    ("todos", "Todos"), ("ingresos", "Ingresos"), ("transporte", "Transporte"), ("comida", "Comida"),
    ("transferencias", "Transferencias"), ("pagos", "Pagos"), ("compras", "Compras"), ("ahorro", "Ahorro"),
]


@dataclass
class Persona:
    id: str
    first: str
    full: str
    card_name: str
    age: int
    city: str
    occupation: str
    since: int
    summary: str
    tags: list[str]
    color: str
    card_last4: str
    balance: int
    seed: int
    contacts: list[dict]
    cajitas: list[dict]
    policies: list[dict]
    events: dict[str, dict]
    car: dict | None = None
    credit: dict | None = None
    preapproved: int = 0
    target_total: int | None = None
    opening_balance: int = 500_000
    txs: list[dict] = field(default_factory=list)


# --------------------------------------------------------------------------- utilidades
def months_in_period() -> list[tuple[int, int]]:
    out, y, m = [], PERIOD_START.year, PERIOD_START.month
    while (y, m) <= (TODAY.year, TODAY.month):
        out.append((y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def _day(y: int, m: int, d: int) -> date:
    """Fecha válida (si el día no existe en el mes, usa el último)."""
    for dd in (d, 30, 29, 28):
        try:
            return date(y, m, dd)
        except ValueError:
            continue
    raise ValueError


class Builder:
    """Acumula movimientos con ids, referencias y horas deterministas."""

    def __init__(self, p: Persona):
        self.p = p
        self.rng = random.Random(p.seed)
        self.items: list[dict] = []

    def add(self, d: date, n: str, cat: str, a: int, ch: str | None = None, *, tag: str | None = None,
            cp: str | None = None, ic: str | None = None, hour: tuple[int, int] = (7, 22)) -> None:
        if d < PERIOD_START or d > TODAY:
            return
        label, group, icon = CATEGORIES[cat]
        h = self.rng.randint(*hour)
        self.items.append({
            "date": d.isoformat(), "time": f"{h:02d}:{self.rng.randint(0, 59):02d}",
            "n": n, "c": label, "cat": cat, "g": group, "a": int(a), "ic": ic or icon,
            "ch": ch or f"Tarjeta débito ••{self.p.card_last4}", "tag": tag, "cp": cp,
        })

    def monthly(self, day: int, n: str, cat: str, a: int, ch: str | None = None, *, start=None, end=None,
                jitter: int = 0, **kw) -> None:
        for y, m in months_in_period():
            if start and (y, m) < start:
                continue
            if end and (y, m) > end:
                continue
            amt = a + (self.rng.randint(-jitter, jitter) // 100 * 100 if jitter else 0)
            self.add(_day(y, m, day), n, cat, -abs(amt) if a < 0 else amt, ch, **kw)

    def spread(self, count: int, options: list[tuple], *, tag=None, weekend_bias: float = 0.0) -> None:
        """`count` movimientos repartidos en el periodo. options: (nombre, cat, lo, hi, peso)."""
        days = (TODAY - PERIOD_START).days
        names = [o for o in options]
        weights = [o[4] for o in options]
        for _ in range(count):
            d = PERIOD_START + timedelta(days=self.rng.randrange(days + 1))
            if weekend_bias and d.weekday() < 5 and self.rng.random() < weekend_bias:
                d += timedelta(days=5 - d.weekday())
                if d > TODAY:
                    d = TODAY
            n, cat, lo, hi, _w = self.rng.choices(names, weights)[0]
            amt = round(self.rng.uniform(lo, hi) / 100) * 100
            self.add(d, n, cat, -amt, tag=tag)

    def filler(self, count: int, options: list[tuple], budget: int) -> None:
        """Gasto cotidiano escalado para que el total cuadre con `budget`."""
        days = (TODAY - PERIOD_START).days
        weights = [o[4] for o in options]
        raw = []
        for _ in range(count):
            d = PERIOD_START + timedelta(days=self.rng.randrange(days + 1))
            n, cat, lo, hi, _w = self.rng.choices(options, weights)[0]
            raw.append((d, n, cat, self.rng.uniform(lo, hi)))
        scale = max(0.4, min(1.8, budget / sum(r[3] for r in raw)))
        for d, n, cat, amt in raw:
            v = max(1_500, round(amt * scale / 100) * 100)
            self.add(d, n, cat, -v)

    def finish(self) -> list[dict]:
        self.items.sort(key=lambda t: (t["date"], t["time"]), reverse=True)
        for i, t in enumerate(reversed(self.items), start=1):
            t["id"] = f"{self.p.id[:2]}{i:05d}"
            t["ref"] = f"LB{(self.p.seed * 7919 + i * 104729) % 10**8:08d}"
        return self.items


def _sum(items: list[dict], pred) -> int:
    return sum(t["a"] for t in items if pred(t))


# --------------------------------------------------------------------------- Sebastián
def _sebastian() -> Persona:
    p = Persona(
        id="sebastian", first="Sebastián", full="Sebastián S.", card_name="Sebas", age=29, city="Bogotá",
        occupation="Analista en ACME S.A.S.", since=2023,
        summary="Carro propio, nómina nueva en Lulo, ahorra para un viaje y apoya a Laura.",
        tags=["Carro", "Nómina", "Crédito", "Viaje"], color="#E5FF00", card_last4="4821", balance=1_742_300,
        seed=14, target_total=1284, opening_balance=650_000,
        contacts=[
            {"id": "laura", "name": "Laura M.", "key": "@lauram", "bank": "Nequi", "dependent": True},
            {"id": "juan", "name": "Juan P.", "key": "310 ••• 2291", "bank": "Bancolombia"},
            {"id": "camila", "name": "Camila R.", "key": "@camirojas", "bank": "Lulo Bank"},
            {"id": "arriendo", "name": "Inmobiliaria Cedritos", "key": "NIT 900.••• .114", "bank": "Davivienda"},
        ],
        cajitas=[
            {"id": "viajes", "name": "Viajes", "emoji": "✈️", "goal": 3_000_000, "travel": True,
             "note": "Cartagena en diciembre"},
            {"id": "emergencias", "name": "Emergencias", "emoji": "🧯", "goal": 2_000_000, "travel": False,
             "note": "Fondo de 3 meses"},
        ],
        car={"plate": "WGY-482", "model": "Chevrolet Onix 2021", "insurer": "Seguros Mundial",
             "soat_expiry": "2026-10-14", "soat_price": 745_300},
        credit={"name": "Lulo Crédito", "amount": 4_200_000, "disbursed": "2026-05-28", "cuotas": 18,
                "cuota": 275_192, "protected": True, "rate": "1,79% M.V."},
        policies=[
            {"id": "soat", "offer": "soat", "title": "SOAT · WGY-482", "aliado": "Seguros Mundial",
             "status": "due", "sub": "vence el 14 de octubre"},
            {"id": "pago", "offer": "pago", "title": "Pago protegido", "aliado": "SBS Seguros", "status": "ok",
             "sub": "ligado a tu Lulo Crédito", "hint": "Nunca has revisado qué cubre"},
            {"id": "vida-deudor", "offer": None, "title": "Vida grupo deudor", "aliado": "AXA Colpatria",
             "status": "ok", "sub": "beneficiario: el banco"},
            {"id": "asis", "offer": None, "title": "Asistencias", "aliado": "IGS", "status": "ok",
             "sub": "renovación automática en enero"},
        ],
        events={
            "credito": {"label": "Desembolso adicional de Lulo Crédito", "strong": True,
                        "mov": {"n": "Desembolso Lulo Crédito", "cat": "desembolso", "a": 9_000_000, "ch": "Lulo Crédito"}},
            "vehiculo": {"label": "Peajes, combustible y parqueaderos",
                         "mov": {"n": "Peaje Andes · Autopista Norte", "cat": "peajes", "a": -12_800}},
            "nomina": {"label": "Cuarto abono de nómina de ACME S.A.S.",
                       "mov": {"n": "Nómina ACME S.A.S.", "cat": "nomina", "a": 3_200_000, "ch": "Abono de nómina"}},
            "viaje": {"label": "Abono a la cajita «Viajes»", "strong": True,
                      "mov": {"n": "Cajita Viajes · abono 5", "cat": "cajitas", "a": -300_000, "ic": "✈️", "ch": "Cajita"}},
            "vida": {"label": "Transferencia fija a Laura M. (mes 5)", "strong": True,
                     "mov": {"n": "Transferencia a Laura M.", "cat": "transferencia", "a": -450_000, "ch": "Bre-B"}},
        },
    )
    b = Builder(p)
    flow = [1.8, 2.1, 3.4, 1.6, 1.9, 2.0, 2.2, 2.4, 2.6, 4.1, 4.3, 4.6]  # millones que entran por mes
    for i, (y, m) in enumerate(months_in_period()):
        friends = 0
        for _ in range(b.rng.randint(1, 3)):
            v = b.rng.randint(2, 9) * 10_000
            friends += v
            who = b.rng.choice(["Juan P.", "Camila R.", "Andrea L."])
            b.add(_day(y, m, b.rng.randint(2, 27)), f"Transferencia de {who}", "ingreso", v, "Bre-B", cp=who)
        payroll = 3_200_000 if (y, m) >= (2026, 7) else 0
        if payroll:
            b.add(_day(y, m, 15), "Nómina ACME S.A.S.", "nomina", payroll, "Abono de nómina", tag="nomina",
                  cp="ACME S.A.S.", hour=(6, 8))
        rest = round(flow[i] * 1_000_000) - friends - payroll
        if (y, m) == (2025, 12):
            b.add(_day(y, m, 18), "Prima de servicios · desde Bancolombia", "ingreso", 1_500_000, "Transferencia",
                  cp="Bancolombia")
            rest -= 1_500_000
        if rest > 0:
            first = rest // 2 // 1000 * 1000
            b.add(_day(y, m, 1), "Transferencia desde Bancolombia", "ingreso", first, "Transferencia", cp="Bancolombia")
            b.add(_day(y, m, 16), "Transferencia desde Bancolombia", "ingreso", rest - first, "Transferencia",
                  cp="Bancolombia")
    # Carro: peajes, combustible, parqueaderos
    tolls = [("Peaje Andes · Autopista Norte", "peajes", 12_800, 12_800, 20),
             ("Peaje Fusca · La Calera", "peajes", 13_900, 13_900, 8),
             ("Peaje Chusacá · Autopista Sur", "peajes", 14_200, 14_200, 6),
             ("Peaje Patios · Vía La Calera", "peajes", 11_300, 11_300, 6),
             ("Peaje Siberia · Calle 80", "peajes", 9_800, 9_800, 6)]
    b.spread(46, tolls, tag="vehiculo", weekend_bias=0.6)
    fuel = [("Terpel · Calle 80", "combustible", 80_000, 110_000, 4), ("Primax · Autopista Norte", "combustible", 80_000, 110_000, 3),
            ("Texaco · Calle 127", "combustible", 80_000, 110_000, 2), ("Biomax · Suba", "combustible", 80_000, 110_000, 1)]
    b.spread(30, fuel, tag="vehiculo")
    b.add(TODAY, "Terpel · Calle 80", "combustible", -98_000, tag="vehiculo", hour=(7, 8))
    parking = [("Parqueadero Andino", "parqueadero", 8_000, 18_000, 3), ("City Parking · Unicentro", "parqueadero", 6_000, 15_000, 3),
               ("Parqueadero Andino", "parqueadero", 9_000, 16_000, 1)]
    b.spread(23, parking, tag="vehiculo")
    b.add(_day(2026, 9, 14), "Parqueadero Andino", "parqueadero", -14_000, tag="vehiculo")
    # Cajitas
    for k, mo in enumerate([6, 7, 8, 9], start=1):
        b.add(_day(2026, mo, 5), f"Cajita Viajes · abono {k}", "cajitas", -300_000, "Cajita", tag="viaje",
              ic="✈️", cp="viajes")
    for mo in range(2, 10):
        b.add(_day(2026, mo, 2), "Cajita Emergencias", "cajitas", -100_000, "Cajita", ic="🧯", cp="emergencias")
    # Laura
    for mo in [6, 7, 8, 9]:
        b.add(_day(2026, mo, 1), "Transferencia a Laura M.", "transferencia", -450_000, "Bre-B", tag="vida", cp="laura")
    # Crédito
    b.add(date(2026, 5, 28), "Desembolso Lulo Crédito", "desembolso", 4_200_000, "Lulo Crédito", tag="credito")
    for k, mo in enumerate([6, 7, 8], start=1):
        b.add(_day(2026, mo, 30), f"Cuota Lulo Crédito {k}/18", "credito", -275_192, "Débito automático", tag="credito")
    # Suscripciones y hogar
    b.monthly(28, "Spotify", "suscripciones", -26_900, "Débito automático", ic="♫")
    b.monthly(10, "Netflix", "suscripciones", -38_900, "Débito automático", ic="📺")
    b.monthly(5, "Smart Fit", "suscripciones", -99_900, "Débito automático", ic="🏋️")
    b.monthly(20, "Claro Hogar · Internet", "servicios", -95_000, "Débito automático", ic="📶")
    b.monthly(12, "Enel · Energía", "servicios", -82_000, "PSE", jitter=14_000, ic="💡")
    b.monthly(14, "Vanti · Gas natural", "servicios", -38_000, "PSE", jitter=8_000, ic="🔥")
    # Gasto cotidiano hasta completar 1.284 movimientos
    daily = [("Rappi", "domicilios", 22_000, 58_000, 10), ("Éxito Calle 80", "mercado", 30_000, 160_000, 5),
             ("Carulla Pasadena", "mercado", 25_000, 140_000, 4), ("Tiendas D1", "mercado", 8_000, 55_000, 9),
             ("Ara", "mercado", 7_000, 40_000, 4), ("Juan Valdez", "cafe", 6_000, 14_000, 10),
             ("Tostao'", "cafe", 3_500, 9_000, 9), ("Crepes & Waffles", "restaurantes", 35_000, 85_000, 3),
             ("El Corral", "restaurantes", 25_000, 48_000, 3), ("Frisby", "restaurantes", 20_000, 42_000, 2),
             ("Uber", "movilidad", 9_000, 28_000, 4), ("DiDi", "movilidad", 7_000, 22_000, 3),
             ("Farmatodo", "salud", 12_000, 70_000, 3), ("Mercado Libre", "compras", 40_000, 220_000, 2),
             ("Falabella", "compras", 60_000, 260_000, 1), ("Cine Colombia", "entretenimiento", 18_000, 45_000, 2),
             ("Oxxo", "mercado", 4_000, 22_000, 6), ("Transferencia a Juan P.", "transferencia", 15_000, 80_000, 2)]
    _fill_to_target(b, p, daily)
    p.txs = b.finish()
    return p


# --------------------------------------------------------------------------- Valentina
def _valentina() -> Persona:
    p = Persona(
        id="valentina", first="Valentina", full="Valentina R.", card_name="Valentina", age=26, city="Medellín",
        occupation="Diseñadora freelance", since=2024,
        summary="Ingresos de varios clientes, sin carro ni crédito. Ahorra para viajar y apoya a su mamá.",
        tags=["Freelance", "Viaje", "Sin carro", "Sin crédito"], color="#FF9BB5", card_last4="7310",
        balance=2_350_800, seed=26, target_total=968, opening_balance=1_100_000, preapproved=6_000_000,
        contacts=[
            {"id": "mama", "name": "Mamá · Gloria R.", "key": "315 ••• 8820", "bank": "Bancolombia", "dependent": True},
            {"id": "sara", "name": "Sara V.", "key": "@saravelez", "bank": "Nequi"},
            {"id": "tomas", "name": "Tomás A.", "key": "@tomasa", "bank": "Lulo Bank"},
            {"id": "arriendo", "name": "Arrendamientos Laureles", "key": "NIT 811.••• .203", "bank": "Bancolombia"},
        ],
        cajitas=[
            {"id": "peru", "name": "Mochilazo por Perú", "emoji": "🎒", "goal": 4_000_000, "travel": True,
             "note": "Cusco y Lima en noviembre"},
            {"id": "equipo", "name": "Computador nuevo", "emoji": "💻", "goal": 6_500_000, "travel": False,
             "note": "Para trabajar"},
        ],
        policies=[],
        events={
            "credito": {"label": "Desembolso de su primer Lulo Crédito", "strong": True,
                        "mov": {"n": "Desembolso Lulo Crédito", "cat": "desembolso", "a": 5_000_000, "ch": "Lulo Crédito"}},
            "vehiculo": {"label": "Peaje aislado (carro alquilado)",
                         "mov": {"n": "Peaje Copacabana · Autopista Norte", "cat": "peajes", "a": -13_400}},
            "nomina": {"label": "Pago de Agencia Pixel (freelance)",
                       "mov": {"n": "Pago Agencia Pixel S.A.S.", "cat": "ingreso", "a": 2_400_000, "ch": "Transferencia"}},
            "viaje": {"label": "Abono a la cajita «Mochilazo por Perú»", "strong": True,
                      "mov": {"n": "Cajita Mochilazo por Perú", "cat": "cajitas", "a": -350_000, "ic": "🎒", "ch": "Cajita"}},
            "vida": {"label": "Transferencia a Mamá · Gloria R. (mes 10)", "strong": True,
                     "mov": {"n": "Transferencia a Mamá · Gloria R.", "cat": "transferencia", "a": -300_000, "ch": "Bre-B"}},
        },
    )
    b = Builder(p)
    clients = [("Agencia Pixel S.A.S.", 3_200_000, 6), ("Estudio Norte", 2_400_000, 5),
               ("Payoneer · Upwork", 1_800_000, 8), ("Fundación Aves de Colombia", 1_500_000, 2),
               ("Café Pergamino", 800_000, 1), ("Editorial Laberinto", 1_200_000, 4)]
    months = months_in_period()
    for name, base, times in clients:
        for k in sorted(b.rng.sample(range(len(months)), times)):
            y, m = months[k]
            amt = round(base * b.rng.uniform(0.85, 1.2) / 1000) * 1000
            b.add(_day(y, m, b.rng.randint(1, 28)), f"Pago {name}", "ingreso", amt, "Transferencia", cp=name,
                  tag="nomina")
    for y, m in months:
        if b.rng.random() < 0.6:
            v = b.rng.randint(3, 12) * 10_000
            b.add(_day(y, m, b.rng.randint(1, 28)), "Transferencia de Sara V.", "ingreso", v, "Bre-B", cp="Sara V.")
    b.spread(1, [("Peaje Copacabana · Autopista Norte", "peajes", 13_400, 13_400, 1)], tag="vehiculo")
    for k, mo in enumerate([4, 5, 6, 7, 8, 9], start=1):
        b.add(_day(2026, mo, 8), "Cajita Mochilazo por Perú", "cajitas", -[250_000, 300_000, 250_000, 300_000, 250_000, 250_000][k - 1],
              "Cajita", tag="viaje", ic="🎒", cp="peru")
    for mo in [3, 5, 7, 9]:
        b.add(_day(2026, mo, 20), "Cajita Computador nuevo", "cajitas", -400_000, "Cajita", ic="💻", cp="equipo")
    b.add(date(2026, 8, 22), "LATAM Airlines · MDE–CUZ", "viajes", -1_380_000, tag="viaje")
    for y, m in months:
        if (y, m) >= (2026, 1):
            b.add(_day(y, m, 3), "Transferencia a Mamá · Gloria R.", "transferencia", -300_000, "Bre-B", tag="vida", cp="mama")
    b.monthly(1, "Arrendamientos Laureles", "arriendo", -1_350_000, "PSE", cp="arriendo")
    b.monthly(28, "Spotify", "suscripciones", -16_900, "Débito automático", ic="♫")
    b.monthly(9, "Adobe Creative Cloud", "suscripciones", -219_000, "Tarjeta débito ••7310", ic="🎨")
    b.monthly(15, "Platzi", "suscripciones", -69_000, "Débito automático", ic="📚")
    b.monthly(6, "Bodytech", "suscripciones", -159_000, "Débito automático", ic="🏋️")
    b.monthly(18, "EPM · Servicios públicos", "servicios", -142_000, "PSE", jitter=20_000, ic="💡")
    b.monthly(21, "Tigo · Internet", "servicios", -89_000, "Débito automático", ic="📶")
    daily = [("Rappi", "domicilios", 18_000, 52_000, 14), ("Pergamino Café", "cafe", 7_000, 16_000, 9),
             ("Juan Valdez", "cafe", 6_000, 13_000, 4), ("Tiendas D1", "mercado", 8_000, 50_000, 7),
             ("Éxito Laureles", "mercado", 25_000, 140_000, 4), ("Uber", "movilidad", 8_000, 25_000, 10),
             ("Metro de Medellín · Cívica", "movilidad", 10_000, 20_000, 3), ("Crepes & Waffles", "restaurantes", 30_000, 80_000, 3),
             ("Mondongo's", "restaurantes", 35_000, 70_000, 2), ("Arturo Calle", "compras", 80_000, 220_000, 1),
             ("Mercado Libre", "compras", 30_000, 180_000, 3), ("Cruz Verde", "salud", 10_000, 60_000, 2),
             ("Cine Colombia", "entretenimiento", 16_000, 40_000, 2), ("Transferencia a Sara V.", "transferencia", 15_000, 60_000, 2)]
    _fill_to_target(b, p, daily)
    p.txs = b.finish()
    return p


# --------------------------------------------------------------------------- Andrés
def _andres() -> Persona:
    p = Persona(
        id="andres", first="Andrés", full="Andrés G.", card_name="Andrés", age=41, city="Cali",
        occupation="Ingeniero en Constructora Andina", since=2022,
        summary="Nómina de un año en Lulo, dos hijos en el colegio, SOAT a punto de vencer y nómina ya protegida.",
        tags=["Nómina", "Familia", "Carro", "SOAT urgente"], color="#62E3A0", card_last4="1953",
        balance=6_920_400, seed=41, target_total=1416, opening_balance=3_400_000,
        contacts=[
            {"id": "martha", "name": "Martha G. (mamá)", "key": "@marthag", "bank": "Banco de Bogotá", "dependent": True},
            {"id": "colegio", "name": "Colegio Bilingüe Los Andes", "key": "NIT 805.••• .771", "bank": "Banco de Occidente",
             "dependent": True},
            {"id": "carlos", "name": "Carlos M.", "key": "317 ••• 4410", "bank": "Nequi"},
        ],
        cajitas=[
            {"id": "matricula", "name": "Matrícula 2027", "emoji": "🎓", "goal": 7_000_000, "travel": False,
             "note": "Colegio de los niños"},
            {"id": "carro", "name": "Mantenimiento del carro", "emoji": "🔧", "goal": 1_500_000, "travel": False,
             "note": "Llantas y revisión"},
        ],
        car={"plate": "KTR-913", "model": "Mazda CX-30 2022", "insurer": "Seguros Mundial",
             "soat_expiry": "2026-09-26", "soat_price": 912_400},
        credit={"name": "Lulo Crédito", "amount": 18_000_000, "disbursed": "2025-11-05", "cuotas": 24,
                "cuota": 912_450, "protected": True, "rate": "1,65% M.V."},
        policies=[
            {"id": "soat", "offer": "soat", "title": "SOAT · KTR-913", "aliado": "Seguros Mundial", "status": "due",
             "sub": "vence el 26 de septiembre"},
            {"id": "pago", "offer": "pago", "title": "Pago protegido", "aliado": "SBS Seguros", "status": "ok",
             "sub": "ligado a tu Lulo Crédito"},
            {"id": "nomina-chubb", "offer": "nomina", "title": "Seguro de nómina", "aliado": "Chubb", "status": "ok",
             "sub": "activo desde marzo de 2026"},
            {"id": "vida-deudor", "offer": None, "title": "Vida grupo deudor", "aliado": "AXA Colpatria",
             "status": "ok", "sub": "beneficiario: el banco"},
            {"id": "asis", "offer": None, "title": "Asistencias", "aliado": "IGS", "status": "ok",
             "sub": "renovación automática en enero"},
        ],
        events={
            "credito": {"label": "Desembolso adicional de Lulo Crédito", "strong": True,
                        "mov": {"n": "Desembolso Lulo Crédito", "cat": "desembolso", "a": 6_000_000, "ch": "Lulo Crédito"}},
            "vehiculo": {"label": "Peaje Villarica · Cali–Jamundí",
                         "mov": {"n": "Peaje Villarica · Cali–Jamundí", "cat": "peajes", "a": -14_600}},
            "nomina": {"label": "Abono de nómina de Constructora Andina",
                       "mov": {"n": "Nómina Constructora Andina S.A.", "cat": "nomina", "a": 5_800_000, "ch": "Abono de nómina"}},
            "viaje": {"label": "Compra en Avianca · Cali–Cartagena", "strong": True,
                      "mov": {"n": "Avianca · CLO–CTG", "cat": "viajes", "a": -1_640_000}},
            "vida": {"label": "Pago de pensión del Colegio Los Andes", "strong": True,
                     "mov": {"n": "Colegio Bilingüe Los Andes · Pensión", "cat": "educacion", "a": -1_350_000, "ch": "PSE"}},
        },
    )
    b = Builder(p)
    for y, m in months_in_period():
        b.add(_day(y, m, 30), "Nómina Constructora Andina S.A.", "nomina", 5_800_000, "Abono de nómina", tag="nomina",
              cp="Constructora Andina S.A.", hour=(6, 8))
        if m in (6, 12):
            b.add(_day(y, m, 20), "Prima de servicios · Constructora Andina", "nomina", 2_900_000, "Abono de nómina",
                  tag="nomina", cp="Constructora Andina S.A.", hour=(6, 8))
        if m not in (12, 1):
            b.add(_day(y, m, 5), "Colegio Bilingüe Los Andes · Pensión", "educacion", -1_350_000, "PSE", tag="vida",
                  cp="colegio")
        b.add(_day(y, m, 2), "Transferencia a Martha G.", "transferencia", -500_000, "Bre-B", tag="vida", cp="martha")
        b.add(_day(y, m, 10), "Cajita Matrícula 2027", "cajitas", -500_000, "Cajita", ic="🎓", cp="matricula")
    b.add(date(2025, 11, 5), "Desembolso Lulo Crédito", "desembolso", 18_000_000, "Lulo Crédito", tag="credito")
    for k, (y, m) in enumerate([(2025, 12), (2026, 1), (2026, 2), (2026, 3), (2026, 4), (2026, 5), (2026, 6),
                                (2026, 7), (2026, 8), (2026, 9)], start=1):
        b.add(_day(y, m, 5), f"Cuota Lulo Crédito {k}/24", "credito", -912_450, "Débito automático", tag="credito")
    b.monthly(15, "Chubb · Seguro de nómina", "seguros", -14_500, "Débito automático", start=(2026, 3), ic="🛡️")
    tolls = [("Peaje Villarica · Cali–Jamundí", "peajes", 14_600, 14_600, 6), ("Peaje Cencar · Vía Yumbo", "peajes", 13_100, 13_100, 3),
             ("Peaje Rozo · Vía Palmira", "peajes", 12_300, 12_300, 2), ("Peaje Loboguerrero · Vía Buenaventura", "peajes", 19_800, 19_800, 1)]
    b.spread(64, tolls, tag="vehiculo", weekend_bias=0.5)
    fuel = [("Terpel · Av. Pasoancho", "combustible", 110_000, 150_000, 3), ("Primax · Av. Roosevelt", "combustible", 110_000, 150_000, 2),
            ("Esso · Av. 6N", "combustible", 110_000, 150_000, 1)]
    b.spread(48, fuel, tag="vehiculo")
    b.spread(30, [("Parqueadero Chipichape", "parqueadero", 6_000, 14_000, 2), ("Parqueadero Unicentro Cali", "parqueadero", 5_000, 12_000, 2)],
             tag="vehiculo")
    b.monthly(12, "Emcali · Servicios públicos", "servicios", -310_000, "PSE", jitter=40_000, ic="💡")
    b.monthly(20, "Movistar Hogar", "servicios", -149_000, "Débito automático", ic="📶")
    b.monthly(8, "Disney+", "suscripciones", -38_900, "Débito automático", ic="📺")
    b.monthly(10, "Netflix", "suscripciones", -44_900, "Débito automático", ic="📺")
    daily = [("Éxito Unicentro", "mercado", 40_000, 220_000, 3), ("Carulla Ciudad Jardín", "mercado", 30_000, 180_000, 2),
             ("Tiendas D1", "mercado", 8_000, 60_000, 6), ("Rappi", "domicilios", 25_000, 75_000, 5),
             ("Juan Valdez", "cafe", 6_000, 16_000, 5), ("Frisby", "restaurantes", 35_000, 95_000, 3),
             ("Crepes & Waffles", "restaurantes", 50_000, 140_000, 2), ("Farmacia Pasteur", "salud", 12_000, 70_000, 3),
             ("Uber", "movilidad", 9_000, 26_000, 2), ("Panamericana", "compras", 15_000, 120_000, 2),
             ("Decathlon", "compras", 60_000, 240_000, 1), ("Cine Colombia", "entretenimiento", 30_000, 80_000, 2),
             ("Tienda Don Pepe", "mercado", 3_000, 25_000, 10), ("Transferencia a Carlos M.", "transferencia", 20_000, 120_000, 1)]
    _fill_to_target(b, p, daily)
    p.txs = b.finish()
    return p


def _fill_to_target(b: Builder, p: Persona, daily: list[tuple]) -> None:
    """Completa con gasto cotidiano hasta el número de movimientos y el saldo final del cliente."""
    count = (p.target_total or len(b.items) + 900) - len(b.items)
    net_needed = p.balance - p.opening_balance - sum(t["a"] for t in b.items)
    b.filler(count, daily, budget=max(1, -net_needed))


# --------------------------------------------------------------------------- acceso
@lru_cache(maxsize=None)
def personas() -> dict[str, Persona]:
    out = {}
    for factory in (_sebastian, _valentina, _andres):
        p = factory()
        out[p.id] = p
    return out


def get(persona_id: str) -> Persona | None:
    return personas().get(persona_id)


DEFAULT_ID = "sebastian"
