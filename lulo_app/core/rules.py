"""Reglas v1 del motor, aprobadas el 2026-10-10 antes de medir.

Cambiar cualquier valor exige subir VERSION: cada decisión guarda la versión con la
que se tomó, así que el registro siempre dice con qué reglas se decidió.

Origen de cada parámetro:
  [base]       sale de la base del reto (se cita la pestaña)
  [aprobado]   umbral propuesto por el equipo y aprobado (tabla de cobertura del 2026-10-10)
  [hipótesis]  no se puede estimar con la base (no hay resultados por cliente); se mide con el grupo de control
"""

from __future__ import annotations

VERSION = "v1"
APPROVED_ON = "2026-10-10"

# Ventana de historia que leen las señales.
LOOKBACK_DAYS = 365

# Fuerza de la señal → multiplicador del valor esperado. [hipótesis]
STRENGTH_MULT = {"fuerte": 1.0, "media": 0.6, "débil": 0.0}

# Desempleo. Requisito de la hoja Elegibilidad: antigüedad laboral ≥ 6 meses. [base]
# La base no trae antigüedad laboral: se usa como proxy la racha de abonos recurrentes en Lulo.
DESEMPLEO_MIN_STREAK = 6
# Una racha solo cuenta si el último abono es reciente. [aprobado]
STREAK_MAX_GAP_DAYS = 45

# Vida: transferencias fijas a un tercero en ≥ 3 meses distintos. [aprobado]
VIDA_MIN_MONTHS = 3
VIDA_INCOME_MIN_STREAK = 3          # con ingreso recurrente la señal es fuerte (hoja Resumen) [base]

# Viajes: compra en aerolínea u hotel en los últimos 90 días, o ≥ 3 abonos a un bolsillo de viajes. [aprobado]
VIAJES_PURCHASE_DAYS = 90
VIAJES_POCKET_MIN = 3

# Mascotas: ≥ 2 compras en tiendas de mascotas o ≥ 1 abono a un bolsillo de mascotas. [aprobado]
MASCOTAS_SPEND_MIN = 2
MASCOTAS_POCKET_MIN = 1

# Hogar: ≥ 2 abonos a un bolsillo de vivienda. [aprobado]
HOGAR_POCKET_MIN = 2

# SOAT. Cotización por uso de vehículo: ≥ 3 peajes (media), ≥ 6 (fuerte). [aprobado]
SOAT_TOLLS_MEDIA = 3
SOAT_TOLLS_FUERTE = 6
# Recordatorio de renovación: días de anticipación (el cliente puede elegir 30, 15 o 7). [aprobado]
SOAT_REMINDER_DAYS = 30
SOAT_REMINDER_OPTIONS = (30, 15, 7)

# Conversión previa para Hogar, que no tiene campaña previa: la menor observada. [hipótesis]
HOGAR_PRIOR_RULE = "min"

# Política de contacto. Supuesto de la hoja Juridico_Entrega: push, SMS, llamada o correo cuentan
# como contacto comercial (Ley 2300); un banner pasivo no. [base]
FATIGUE_MIN_IGNORED = 3             # ignoradas ≥ 3 y ≥ 2 × abiertas → banner [aprobado]
FATIGUE_RATIO = 2
REALTIME_LATENCIES = ("<1 min", "1-5 min", "5-30 min")   # «Mismo día» no sirve para disparo inmediato [base]

# Una oferta mostrada o rechazada no se repite antes de 30 días. [aprobado]
COOLDOWN_DAYS = 30

# Grupo de control. [aprobado]
CONTROL_PCT = 10
CONTROL_SALT = "reto19-v1"

# Rango «56+»: se excluye de los ramos con tope de edad. [aprobado]
EXCLUDE_OPEN_AGE_BAND = True

# Desempate entre ramos con el mismo valor esperado (orden fijo, no se usa para decidir otra cosa).
TIEBREAK = ("Pago protegido", "SOAT", "Desempleo", "Vida", "Viajes", "Mascotas", "Hogar")


def as_dict() -> dict:
    """Todos los parámetros, para mostrarlos en el panel y guardarlos con cada decisión."""
    return {k: v for k, v in globals().items() if k.isupper()}
