# Resumen de una página · Prototipo Lulo Bank · Grupo 14 · Reto 19

**Seguros en el momento justo, dentro de la app de Lulo.** App con el look de la app real, un motor que decide qué seguro ofrecer a quién, cuándo y por qué canal, y aprende de cada respuesta. Prototipo académico: la base del reto es 100 % sintética y sus cifras no son métricas de Lulo Bank.

App: https://prototipo-iind.vercel.app · Detalle: [`docs/MOTOR.md`](MOTOR.md) · Datos reales: [`docs/DATOS_REALES.md`](DATOS_REALES.md)

## Lo que ve el cliente (cuatro cosas nuevas)

1. **Aviso y renovación del SOAT**: antes de que venza, en dos toques y pagando desde la Lulo Cuenta.
2. **Ofertas en el momento justo**: una transferencia fija, un abono a un bolsillo o un crédito disparan el seguro que tiene sentido, con «Por qué lo ves».
3. **Tu año en Lulo**: doce meses contados como una historia, con un momento de protección por capítulo.
4. **Tu protección**: lo que tiene, lo que le sugerimos, lo agendado y por qué no le ofrecemos lo demás.

## Cómo decide el motor

**Valor esperado = P(acepta | ve la oferta) × comisión a 12 meses.** Las reglas son compuertas que no dependen del modelo: autorización de datos (Ley 1581), elegibilidad, capacidad de pago, lo que ya tiene, tope de contactos (Ley 2300) y grupo de control. P sale de una regresión probit bayesiana cuyas creencias previas vienen de la base:

| Pieza | Qué dice la base | Fuente |
|---|---|---|
| Conversión por ramo (Beta-Binomial jerárquico) | SOAT 12,5 %, Hogar 10,7 % (de 5,1 % a 17,6 %), Mascotas 10,5 %, Viajes 10,2 %, Vida 9,5 %, Desempleo 8,6 % | Campanas_Previas |
| Efecto del momento (serie de casos autocontrolada) | 12 compras externas en los 30 días después del evento frente a 8,1 esperadas: × 1,54 (de 0,78 a 2,86; 85 % de probabilidad de que sea positivo) | Pagos_Seguros, 113 pagos |
| Rasgos del cliente | 38 variables de perfil, movimientos, bolsillos y uso de la app, que empiezan con peso 0 | Clientes, Movimientos, Cajitas, Uso_App |
| Dispersión entre clientes (v2.1) | 0,25 sin respuestas; con respuestas, Bayes empírico | respuestas a ofertas |

## Qué hace con los 600 clientes al corte (2026-10-08)

- **Plan de hoy**: 219 push, 183 banner pasivo, 40 en grupo de control, 84 sin autorización y 74 sin oferta. De las 442 decisiones con ramo, 403 coinciden con la regla v1.3 y 39 cambian.
- **El año recorrido** (backtest cada 7 días desde el 2026-01-30): 4.168 ofertas a 437 clientes, nadie pasa de 4 push en 30 días y **0 violaciones** de las reglas.

## Por qué funciona igual o mejor con más datos

En un laboratorio con verdad simulada sobre los clientes de la base (no son datos de Lulo):

| Si… | El motor frente a la regla v1.3 |
|---|---|
| hay efectos que la regla no ve | **+10 %** de comisión por oferta; recorre el 91 % del camino entre el azar y el oráculo (la regla, 58 %) |
| la regla tenía razón | **−1,0 %**: cuesta poco |
| se suman 20 variables de puro ruido | **+10 %**: el ruido no lo confunde |
| llega una columna nueva que sí predice | la aprende sola: **+0,8 %** frente al mismo motor sin ella (el techo era 3 %) |

Lo aprendido de respuestas reales solo se usa si mejora fuera de muestra (campeón contra retador).

## El siguiente paso: el piloto

Con la base completa del banco y un grupo de control, **510 clientes por grupo** bastan para detectar un aumento de 50 % en la conversión del SOAT (12,9 %), con α = 5 % y potencia 80 % (modelo M6). Lulo puede correr el motor con sus datos en su propio equipo, sin subir nada (`scripts/validar_datos.py`, `scripts/train_motor.py --datos`).

---

Origen de cada cifra: `lulo_app/ml/motor.json` (conversión, momento, rasgos), `python -m lulo_app.core campana` (plan), `python -m lulo_app.core backtest` (año), `lulo_app/ml/laboratorio.json` (laboratorio) y `lulo_app/ml/modelos.json` (piloto). Reglas v2.1.
