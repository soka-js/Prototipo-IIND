"""Reglas v1 del motor, aprobadas el 2026-10-10 antes de medir.

Cambiar cualquier valor exige subir VERSION: cada decisión guarda la versión con la
que se tomó, así que el registro siempre dice con qué reglas se decidió.

Origen de cada parámetro:
  [base]       sale de la base del reto (se cita la pestaña)
  [aprobado]   umbral propuesto por el equipo y aprobado (tabla de cobertura del 2026-10-10)
  [hipótesis]  no se puede estimar con la base (no hay resultados por cliente); se mide con el grupo de control
"""

from __future__ import annotations

VERSION = "v2.1"
APPROVED_ON = "2026-10-21"
CHANGELOG = {
    "v1": "Umbrales de la tabla de cobertura, valor esperado, control 10 %, banner al tope, 56+ excluido.",
    "v1.1": "Ofertas con fecha límite primero; mínimo 7 días entre push.",
    "v1.2": "Modelos entrenados con la base: la afinidad del modelo de propensión ajusta el valor esperado en los "
            "ramos donde el modelo le gana al azar; el modelo de respuesta al push puede mandar la oferta a banner.",
    "v1.3": "Capacidad de pago en la elegibilidad (prima frente a ingreso mensual y saldo); la comisión de los "
            "ramos de pago único descuenta la cancelación de la base.",
    "v2.0": "Motor bayesiano: el valor esperado es P(acepta | ve) × comisión, con P de una regresión probit "
            "bayesiana cuyas creencias previas salen de la base (embudo jerárquico de campañas y efecto del "
            "momento con las compras externas) y de las hipótesis aprobadas (señal media × 0,6); aprende de las "
            "respuestas (de la sesión y de la población) y explora con muestreo de Thompson en un 10 % de los "
            "clientes. Las compuertas de v1.3 (autorización, elegibilidad, exclusiones, espera, control, canal) "
            "no cambian. MOTOR = \"regla\" reproduce v1.3.",
    "v2.1": "Con respuestas a ofertas, la dispersión del apetito entre clientes (τ) se estima con Bayes empírico "
            "(verosimilitud marginal) en vez de quedar fija en 0,25; sin respuestas sigue en 0,25 y ninguna "
            "decisión cambia. El backtest y el plan de campaña toman la misma decisión sin armar la traza.",
}

# Motor de decisión. "bayesiano" (v2.0) o "regla" (reproduce v1.3: conversión previa × comisión × fuerza ×
# afinidad). Las compuertas son las mismas en los dos; solo cambia cómo se ordenan las ofertas permitidas.
MOTOR = "bayesiano"

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

# Mínimo de días entre dos push al mismo cliente; antes de eso, la oferta va como banner. [aprobado v1.1]
MIN_DAYS_BETWEEN_PUSH = 7

# Ofertas con fecha límite (SOAT por vencer y desembolso) ganan la ventana antes que el valor esperado. [aprobado v1.1]
DEADLINE_FIRST = True

# Una oferta mostrada o rechazada no se repite antes de 30 días. [aprobado]
COOLDOWN_DAYS = 30

# Grupo de control. [aprobado]
CONTROL_PCT = 10
CONTROL_SALT = "reto19-v1"

# Rango «56+»: se excluye de los ramos con tope de edad. [aprobado]
EXCLUDE_OPEN_AGE_BAND = True

# Modelos entrenados (lulo_app/ml/modelos.json, scripts/train_models.py). [base + aprobado v1.2]
# Valor esperado = conversión previa × comisión a 12 meses × fuerza × afinidad. La afinidad es la
# probabilidad del modelo dividida por la tasa base del ramo, acotada a [0,5; 2]; vale 1 en los ramos
# donde el modelo no le gana al azar (prueba de permutación p < 0,05 y AUC ≥ 0,55).
ML_PROPENSITY = True
# Si la probabilidad de abrir un push (Bayes empírico) queda bajo el umbral del modelo, la oferta va como banner.
ML_PUSH_RESPONSE = True

# Capacidad de pago (dato 2.2 de la solicitud a Lulo: saldo e ingreso «para medir capacidad de pago»). [hipótesis v1.3]
# Pólizas mensuales: la prima no puede pasar de esta fracción del ingreso mensual (Clientes.ingreso_mensual_cop).
# Pólizas de pago único (SOAT anual, Viajes por viaje): la prima no puede pasar del saldo promedio
# (Clientes.saldo_promedio_cop). El umbral no se puede estimar con la base (no hay rechazos por precio):
# es un supuesto de trabajo que se valida con Lulo.
CAPACITY_MAX_SHARE = 0.05
CAPACITY_SINGLE_PAY_VS_BALANCE = True

# Cancelación (Seguros_Mensual.cancelacion_pct, dato 1.3). [base + hipótesis v1.3]
# En las pólizas mensuales la persistencia a 6 y 12 meses ya descuenta las salidas, así que la cancelación
# no se aplica otra vez. En las de pago único (SOAT, Viajes), que no traen persistencia, la comisión se
# multiplica por (1 − cancelación): se supone que una póliza cancelada devuelve la comisión. El diccionario
# de la base no define el campo; se valida con Lulo.
CANCEL_SINGLE_PAY = True

# ---------------------------------------------------------------- motor bayesiano (v2.0, docs/MOTOR.md)
# Lo usa scripts/train_motor.py para escribir las creencias previas de lulo_app/ml/motor.json: cambiar un
# valor exige reentrenar (python scripts/train_motor.py) y subir VERSION.

# Exploración: dentro del tratamiento, los clientes con bucket en [CONTROL_PCT, CONTROL_PCT + EXPLORE_PCT)
# deciden con un sorteo de las creencias (muestreo de Thompson) en vez de con la media: así el motor prueba
# opciones de las que todavía duda y aprende de sus respuestas. El grupo de control no cambia. [hipótesis v2.0]
EXPLORE_PCT = 10

# Ventana del momento: el evento que dispara el ramo pasó hace menos de estos días. Igual a la espera entre
# ofertas y a la anticipación del recordatorio del SOAT. [aprobado v1 + base: M5b]
MOMENTO_VENTANA_DIAS = 30

# Señal media frente a fuerte: P(acepta) × 0,6, como STRENGTH_MULT de v1, con una duda que cubre de × 0,3 a
# × 1,0 al 90 % (desviación del logaritmo de la razón). [hipótesis v1 con su duda]
PRIOR_SENAL_MEDIA_RATIO = 0.6
PRIOR_SENAL_LOGSD = 0.37

# Duda previa de los rasgos genéricos (escala probit). Se fija la duda TOTAL que pueden aportar juntos para un
# cliente típico y se reparte entre las D variables del vocabulario (cada una recibe TOTAL/√D): así, sumar
# tipos de datos no agranda la duda ni el ruido de la exploración. Con 0,45 y el apetito del cliente (0,25),
# antes de ver respuestas la probabilidad de un cliente típico queda entre 2 % y 35 % cuando la base es 10 %
# (chequeo predictivo previo en motor.json). El 60 % de la varianza va al peso común a todos los ramos y el
# 40 % a la desviación propia del ramo. [hipótesis v2.0]
PRIOR_SD_RASGOS_TOTAL = 0.45
PRIOR_FRACCION_COMUN = 0.6
PRIOR_SD_CLIENTE = 0.25

# Con respuestas, la dispersión del apetito (τ) sale de los datos: Bayes empírico sobre la verosimilitud
# marginal de las respuestas de cada cliente (bayes.ApetitoEB). Si la estimación es 0 (los clientes no se
# distinguen), se usa este piso para no perder lo que digan las respuestas siguientes. [v2.1]
APETITO_TAU_MIN = 0.02

# Peso de la afinidad de M1: media 1 si M1 pasa la compuerta del ramo (se cree a M1), 0 si no (no se cree
# hasta que las respuestas lo confirmen). [aprobado v1.2]
PRIOR_AFINIDAD = {"usable": (1.0, 0.25), "no_usable": (0.0, 0.10)}

# Desempate entre ramos con el mismo valor esperado (orden fijo, no se usa para decidir otra cosa).
TIEBREAK = ("Pago protegido", "SOAT", "Desempleo", "Vida", "Viajes", "Mascotas", "Hogar")


def as_dict() -> dict:
    """Todos los parámetros, para mostrarlos en el panel y guardarlos con cada decisión."""
    return {k: v for k, v in globals().items() if k.isupper()}
