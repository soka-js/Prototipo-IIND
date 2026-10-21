# Motor bayesiano de ofertas de seguros · reglas v2.0 · Grupo 14 · Reto 19

Este documento explica cómo decide y cómo aprende el motor del prototipo, para estudiarlo y defenderlo. Cada cifra sale de `lulo_app/ml/motor.json` (lo escribe `scripts/train_motor.py`) o de `lulo_app/ml/laboratorio.json` (lo escribe `scripts/laboratorio.py`), calculadas sobre la base del reto (`Base_Datos_Reto_Universidad.xlsx`, sha256 `5029790b7a29…`, 600 clientes, corte 2026-10-08). **La base es 100 % sintética y académica: sus cifras no son métricas de Lulo Bank.**

Complementa a [`docs/MODELOS.md`](MODELOS.md) (los modelos M1 a M6) y a [`docs/DATOS_REALES.md`](DATOS_REALES.md) (cómo correr el motor con los datos de Lulo).

---

## 0. En un minuto (para la presentación)

- **Qué decide.** A quién ofrecerle qué seguro, en qué momento y por qué canal.
- **Cómo.** Las reglas aprobadas son **compuertas**: dicen qué se puede ofrecer (autorización de datos, elegibilidad, capacidad de pago, lo que ya tiene, tope de contactos, grupo de control). El modelo de probabilidad **ordena** lo que las reglas permiten: ofrece el seguro con mayor valor esperado.
- **La fórmula.**

  > **Valor esperado = P(acepta | ve la oferta) × comisión a 12 meses**

  con P = Φ(base + señal + momento + afinidad + rasgos + cliente), una regresión probit bayesiana.
- **Qué usa de los datos.** Las 9 tablas de la base: las campañas previas dan la conversión de cada ramo; las compras de seguros a otras aseguradoras dan el efecto del momento; los movimientos, bolsillos, perfil y uso de la app dan las señales, los rasgos y el canal; Seguros_Mensual da el valor; Elegibilidad y Jurídico dan las compuertas.
- **Por qué mejora con más datos.** (1) Empieza en lo que la base sabe hoy y cada respuesta mueve solo lo que la evidencia muestra. (2) Una variable nueva empieza en «no sé» (peso 0) y no cambia nada hasta que los datos digan que importa; la duda total está fija, así que sumar variables no agrega ruido. (3) Lo aprendido se usa solo si mejora fuera de muestra (campeón contra retador).
- **Qué muestra el laboratorio** (verdad simulada, no datos de Lulo). Con efectos que la regla no ve, el motor gana **+10 %** de comisión por oferta frente a la regla v1.3 y recorre el **91 %** del camino entre el azar y el oráculo (la regla, 58 %). Si la regla tenía razón, el motor queda a **−1,1 %**. Con 20 variables de ruido, sigue en **+10 %**.
- **Qué no promete.** No dice cuánto venderá Lulo: con esta base el motor sabe poco más que la regla, y lo dice. Lo que sí garantiza es que aprende lo que los datos reales muestren y que cada decisión queda registrada para medirla contra el grupo de control.

---

## 1. Qué cambió frente a la regla v1.3

| | Regla v1.3 | Motor bayesiano v2.0 |
|---|---|---|
| Valor esperado | conversión previa × comisión × fuerza (1,0 / 0,6 / 0) × afinidad | P(acepta) × comisión, con P en escala de probabilidad y con su intervalo |
| Conversión de cada ramo | la de su campaña; Hogar, la menor observada (supuesto) | la de su campaña encogida hacia el promedio de las campañas; Hogar, la predictiva de una campaña nueva, con su duda |
| Señal media | × 0,6, fijo | × 0,6 como creencia previa con duda; las respuestas la corrigen |
| Momento | no existía | estimado con las compras externas después de cada evento |
| Aprendizaje | no aprende | aprende el apetito de cada cliente en la sesión y, con respuestas de la población, todos los pesos |
| Exploración | no | 10 % del tratamiento decide con un sorteo de las creencias (Thompson) |
| Compuertas, canal, control | — | **iguales a v1.3** |

`rules.MOTOR = "regla"` (o `Context.motor = "regla"`, o `python -m lulo_app.core campana --motor regla`) vuelve a ordenar como v1.3, y cada evaluación dice qué habría elegido la regla.

**Efecto en el plan de campaña al corte** (`python -m lulo_app.core campana`): mismos resultados y canales que v1.3 (219 push, 183 banner, 84 sin autorización, 74 sin oferta, 40 de control). De las 442 decisiones con ramo, **403 son iguales** y **39 cambian**: 19 de Vida a Desempleo (la conversión de Desempleo se encoge hacia arriba y la de Vida fuera del momento baja), 12 hacia Hogar (que deja de usar «la menor conversión») y 8 entre otros ramos. **9 de esos 39 son clientes que exploran**; los otros 30 cambian por lo que dicen los datos.

---

## 2. Las piezas

| Pieza | Pregunta | Datos | Método | Archivo |
|---|---|---|---|---|
| B1 Embudo | ¿Cuánto convierte cada ramo? | Campanas_Previas | Beta-Binomial jerárquico con Bayes completo | `scripts/train_motor.py` (`embudo`) |
| B2 Momento | ¿Se compra más justo después del evento? | Pagos_Seguros, Movimientos, Cajitas | Serie de casos autocontrolada, jerárquica por ramo | `scripts/train_motor.py` (`momento`) |
| B3 Rasgos | ¿Qué más sabemos del cliente? | Clientes, Movimientos, Cajitas, Pagos_Seguros, Uso_App | Vocabulario descubierto de los datos, estandarizado | `lulo_app/ml/rasgos.py` |
| B4 Aceptación | ¿Qué probabilidad hay de que acepte? | todo lo anterior + respuestas | Regresión probit bayesiana con actualización en línea | `lulo_app/ml/motor.py`, `lulo_app/ml/bayes.py` |
| B5 Canal | ¿La va a ver? | Uso_App, Campanas_Previas, Juridico_Entrega | M3 (apertura del push) y alcance del banner; reglas de contacto | `lulo_app/core/contact.py`, `lulo_app/ml/motor.py` |
| B6 Valor | ¿Cuánto vale si acepta? | Seguros_Mensual | Comisión esperada a 12 meses | `lulo_app/core/catalog.py` |
| B7 Decisión | ¿Qué se ofrece? | — | Compuertas + valor esperado; explotar, explorar o control | `lulo_app/core/engine.py` |
| B8 Aprendizaje | ¿Qué cambió con las respuestas? | respuestas | ADF en la sesión; campeón/retador con la población | `lulo_app/ml/motor.py`, `scripts/train_motor.py` |

Todo corre en **Python puro**: en Vercel no se instala nada nuevo, y el entrenamiento es determinista (dos corridas dan el mismo archivo; `--check` lo verifica).

### B1 · Embudo jerárquico: cuánto convierte cada ramo

**Intuición.** Cada campaña previa dice cuántos clientes vieron la oferta (impactados) y cuántos compraron (ventas). Una campaña de 580 personas tiene ruido: si convirtió 10,2 %, la verdad puede estar entre 8,5 % y 12,1 %. Como las cinco campañas se parecen, lo razonable es **encoger** cada tasa un poco hacia el promedio: mientras menos datos tenga un ramo, más se acerca al promedio. Hogar no tuvo campaña: recibe el promedio con mucha más duda.

**Modelo** (Gelman et al., *Bayesian Data Analysis*, 3.ª ed., sección 5.3, el ejemplo de los tumores en ratas):

- ventas_r ~ Binomial(impactados_r, p_r)
- p_r ~ Beta(μκ, (1 − μ)κ): μ es la conversión promedio de las campañas y κ cuánto se parecen entre sí
- previa no informativa del libro: p(μ, κ) ∝ κ^(−3/2)

Se integra sobre (μ, κ) en una rejilla de 121 × 121 puntos: es Bayes completo, sin simulación. A diferencia del Bayes empírico, que fija κ en su mejor valor, aquí la duda sobre cuánto se parecen las campañas entra al resultado.

**Resultado con la base.** Promedio μ = 10,7 %; κ ≈ 202 (con Bayes empírico serían 479: encogería el doble).

| Ramo | Campaña (ventas / impactados) | Creencia | Intervalo al 90 % |
|---|---:|---:|---|
| SOAT | 12,9 % | 12,5 % | 11,0 % a 14,0 % |
| Vida | 9,2 % | 9,5 % | 8,1 % a 11,0 % |
| Desempleo | 8,0 % | 8,6 % | 7,1 % a 10,4 % |
| Hogar | sin campaña | 10,7 % | 5,2 % a 17,6 % |
| Mascotas | 10,6 % | 10,5 % | 8,9 % a 12,3 % |
| Viajes | 10,2 % | 10,2 % | 8,5 % a 12,1 % |

Con el mismo modelo se estiman el interés (interesados / impactados, 30,8 % en promedio), el cierre (ventas / interesados, 33,7 %) y el alcance de cada canal (impactados / elegibles): 25,4 % para la campaña de banner y 27,3 % para la de push. Lectura para negocio: **de cada 100 clientes que ven una oferta de seguro, cerca de 31 se interesan y 11 compran.**

### B2 · Momento: ¿se compra más justo después del evento?

**Intuición.** La idea central del proyecto es ofrecer el seguro cuando pasa algo (un peaje, una transferencia fija, un abono al bolsillo de vivienda). La base no trae respuestas a ofertas, pero sí trae **113 compras de seguros a otras aseguradoras con su fecha** (Pagos_Seguros). La pregunta es si esas compras caen más de lo esperado en los 30 días después del evento del mismo cliente.

**Modelo: serie de casos autocontrolada** (Farrington, 1995; Petersen, Douglas y Whitaker, 2016). Cada compra se compara con el resto del periodo **del mismo cliente**: si los días «después de un evento» son el 30 % de su año, una compra al azar caería ahí con probabilidad 0,3. Si las compras caen ahí más seguido, el momento importa. Como cada cliente es su propio control, sus diferencias (ingreso, edad, gustos) no confunden el resultado. Para una compra j con fracción p_j de días en la ventana:

> P(la compra cae en la ventana) = σ(θ + logit p_j), con e^θ = razón de tasas (cuántas veces más se compra en la ventana)

θ tiene un efecto por ramo que se encoge hacia el promedio de los ramos (θ_r ~ N(θ̄, τ²)), y se resuelve exacto en una rejilla. Desempleo y Viajes no tienen compras externas en la base: reciben la predictiva del promedio.

**Resultado con la base.** 12 compras cayeron en la ventana frente a 8,1 esperadas al azar (igual que M5b en `docs/MODELOS.md`). Razón de tasas promedio **1,54** (90 %: 0,78 a 2,86; probabilidad de que sea mayor que 1: 85 %).

| Ramo | Evento | Compras | En la ventana | Esperadas | Razón de tasas (90 %) |
|---|---|---:|---:|---:|---|
| SOAT | peaje | 50 | 7 | 4,3 | 1,64 (0,88 a 2,93) |
| Vida | transferencia fija a un tercero | 27 | 4 | 2,8 | 1,63 (0,78 a 3,40) |
| Hogar | abono al bolsillo de vivienda | 24 | 0 | 0,3 | 1,45 (0,55 a 3,32) |
| Mascotas | compra o abono para la mascota | 12 | 1 | 0,6 | 1,56 (0,67 a 3,40) |
| Desempleo | abono de nómina | 0 | — | — | 1,54 (0,61 a 3,67), promedio |
| Viajes | compra de viaje o abono al bolsillo | 0 | — | — | 1,54 (0,61 a 3,67), promedio |

**Sensibilidad a la ventana** (todos los ramos juntos; solo descriptiva, la ventana de 30 días se fijó antes de mirar):

| Ventana | En la ventana | Esperadas | Razón de tasas (90 %) |
|---:|---:|---:|---|
| 7 días | 1 | 2,0 | 0,60 (0,19 a 1,69) |
| 15 días | 4 | 4,2 | 0,89 (0,39 a 1,87) |
| **30 días** | **12** | **8,1** | **1,63 (0,91 a 2,86)** |
| 60 días | 22 | 14,3 | 2,18 (1,32 a 3,58) |
| 90 días | 24 | 18,6 | 1,71 (1,03 a 2,86) |

Lectura honesta: en esta base las compras **no** se concentran en la primera semana después del evento, sino entre uno y dos meses después. Mirar varias ventanas y quedarse con la mejor sería hacer trampa, así que el motor usa la de 30 días aprobada (la misma de la espera entre ofertas y del aviso del SOAT). Con datos reales, la ventana es un parámetro (`MOMENTO_VENTANA_DIAS`) que se calibra con el piloto.

**Cómo entra al motor sin inflar nada.** La conversión de una campaña es un promedio entre clientes que estaban en el momento y clientes que no. Con la fracción π de clientes con señal que están en el momento (medida en la base: SOAT 31 %, Vida 41 %, Desempleo 100 %, Hogar 30 %, Mascotas 29 %, Viajes 39 %), la base del modelo es la conversión **fuera del momento**:

> b = p_campaña / (π · razón + 1 − π)  →  en el momento: razón · b;  promedio: π · razón · b + (1 − π) · b = p_campaña

Así el promedio sigue siendo el de la campaña y el momento solo **redistribuye** la probabilidad hacia quien acaba de tener el evento. En Desempleo todos los clientes con señal están en el momento (su nómina llega cada mes), así que la base sola (5,6 %) nunca se usa: con el momento vuelve al 8,6 % de la campaña.

**Supuesto clave.** Se supone que el efecto del momento en la compra orgánica (sin oferta) se traslada a la aceptación de una oferta. Es la mejor evidencia que la base permite; el piloto con grupo de control la confirma o la corrige, y el motor se ajusta solo con las respuestas.

### B3 · Rasgos: todo lo demás que se sabe del cliente

`lulo_app/ml/rasgos.py` arma el vector del cliente **descubriendo las variables de los datos**: cada categoría de movimiento, canal de pago, tipo de bolsillo y ocupación que aparece en la base se vuelve una variable. Con la base salen **38**:

| Familia | Variables | Tabla |
|---|---:|---|
| Perfil (edad, ingreso, saldo, antigüedad, crédito, CDT, bolsillos, Pro) | 8 | Clientes |
| Ocupación | 4 | Clientes |
| Movimientos de los últimos 90 días por categoría | 13 | Movimientos |
| Participación de cada canal de pago | 4 | Movimientos |
| Gasto frente a ingreso | 1 | Movimientos + Clientes |
| Abonos del año por tipo de bolsillo | 5 | Cajitas |
| Seguros voluntarios que ya tiene | 1 | Clientes + Pagos_Seguros |
| Sesiones y apertura de notificaciones | 2 | Uso_App |

- Si Lulo trae una categoría nueva (por ejemplo, combustible, que la base no tiene), al reentrenar aparece sola.
- Solo usa campos canónicos: **nunca nombres de comercios ni de terceros** (`test_features_never_read_merchant_names_and_skip_induced_policies`).
- **«Visitas a Seguros» no entra**: es consecuencia de tener un seguro, no causa (decisión de SOKA del 2026-10-20).
- **Vida grupo deudor y las asistencias no cuentan** como seguros del cliente: vienen con el crédito, no son voluntarios.

**La duda previa se reparte.** Antes de ver respuestas, el peso de cada rasgo es N(0, σ²): media 0 («no sé si importa»). La duda **total** que pueden aportar todos los rasgos juntos está fija (`PRIOR_SD_RASGOS_TOTAL` = 0,45 en escala probit) y se reparte entre las D variables: cada una recibe 0,45/√D (con D = 38, un peso común a todos los ramos de 0,057 y una desviación propia del ramo de 0,046). Por eso **sumar variables no agrega ruido** ni a las predicciones ni a la exploración. El chequeo predictivo previo (Gabry et al., 2019) confirma que es plausible: sin respuestas, la probabilidad sorteada de aceptar una oferta real queda entre 0,7 % y 31,6 % (90 %), mediana 6,9 %.

### B4 · Probabilidad de aceptar: regresión probit bayesiana que aprende en línea

**Modelo.** P(acepta | ve, x) = Φ(Σ_k x_k · w_k), con Φ la acumulada de la normal estándar. Cada peso tiene una creencia gaussiana w_k ~ N(m_k, v_k). Las variables de una oferta (ramo r, cliente c) son:

| Variable | Valor | Creencia previa del peso | De dónde sale |
|---|---|---|---|
| `r|base` | 1 | Φ⁻¹(b) con su duda | B1 + exposición de B2 |
| `r|senal_media` | 1 si la señal es media | Φ⁻¹(0,6·b) − Φ⁻¹(b), duda de × 0,3 a × 1,0 al 90 % | hipótesis aprobada en v1 |
| `r|momento` | 1 si el evento pasó hace < 30 días | Φ⁻¹(razón·b) − Φ⁻¹(b), duda de B2 | B2 |
| `r|afinidad` | desplazamiento probit de M1 | media 0 (M1 no le gana al azar) | M1, `docs/MODELOS.md` |
| `*|rasgo` y `r|rasgo` | rasgo estandarizado | media 0, duda repartida | B3 |
| `cliente:c` | 1 | media 0, desviación 0,25 | apetito del cliente |

**Aprendizaje.** Cada respuesta (aceptó o no) actualiza las creencias en una sola pasada, con el filtrado de densidad supuesta (ADF) que usa AdPredictor, el modelo de clics de Bing (Graepel et al., 2010):

```
s² = 1 + Σ x_k² v_k        z = t · (Σ x_k m_k) / s,   t = +1 si aceptó, −1 si no
m_k ← m_k + t · x_k · v_k / s · ψ(z)                   ψ(z) = φ(z) / Φ(z)
v_k ← v_k · (1 − x_k² · v_k / s² · ψ(z) · (ψ(z) + z))
```

Por qué este modelo: (1) la actualización es exacta en forma cerrada y cuesta lo mismo que leer la oferta, así que escala a millones de respuestas; (2) una variable que nunca aparece conserva su creencia previa; (3) la duda de cada peso está a la vista, y es lo que usa la exploración.

**Qué ve el cliente y el panel.** La probabilidad es Φ(Σ x_k m_k), con un intervalo al 90 % que suma la duda de lo que ya tiene evidencia (base, señal, momento, afinidad, lo aprendido de los rasgos y del cliente). Los rasgos que todavía no aprendieron nada se cuentan aparte («38 rasgos esperan respuestas para pesar») para no mostrar un intervalo de 1 % a 60 % que solo diría «no hay respuestas todavía».

### B5 · Canal: ¿la va a ver?

Las reglas de contacto de v1.3 no cambian: tope de 4 contactos en 30 días, 7 días entre push, fatiga, latencia; en cualquiera de esos casos la oferta va como banner pasivo, que no cuenta como contacto (supuesto de la hoja Jurídico, Ley 2300). Lo nuevo es que cada decisión dice con qué probabilidad el cliente verá la oferta: el push con el modelo M3 de apertura del cliente (Bayes empírico, `docs/MODELOS.md`) y el banner con el alcance de la campaña de banner (25,4 %). `ev_contacto` = P(ve) × valor esperado.

### B6 · Valor

El mismo de v1.3 (`lulo_app/core/catalog.py`): prima × comisión × meses esperados por la persistencia a 6 y 12 meses; en SOAT y Viajes, de pago único, × (1 − cancelación). Con datos reales en los que la prima o la comisión cambian mes a mes, se usa su promedio ponderado por pólizas emitidas.

### B7 · Decisión: explotar, explorar y control

1. Las compuertas de v1.3 dejan los ramos que se pueden ofrecer.
2. Las ofertas con fecha límite van primero (SOAT por vencer, desembolso), como en v1.1.
3. Entre las demás gana el mayor valor esperado:
   - **Control (10 %)**, por hash del id, igual que antes: el motor decide y registra, pero no muestra. La diferencia con el resto es el efecto real.
   - **Exploración (10 %)**, los buckets 10 a 19 del mismo hash: deciden con un sorteo de las creencias (**muestreo de Thompson**; Thompson, 1933; Chapelle y Li, 2011; Russo et al., 2018). El sorteo usa una semilla derivada del cliente y la fecha: la misma situación da la misma decisión.
   - **Explotación (80 %)**: la mejor estimación.

**Lo que dice el laboratorio de explorar.** Con estos clientes, explorar casi no cambia el resultado (−0,5 % en el escenario con señal, +0,1 % en el de hipótesis equivocada): la variedad de clientes ya obliga al motor a probar de todo (Bastani, Bayati y Khosravi, 2021). Se deja el 10 % por dos razones: protege contra creencias previas equivocadas en opciones que el motor casi nunca elegiría, y deja datos con azar conocido para **evaluar políticas nuevas fuera de línea sin probarlas en clientes** (Li et al., 2011). Lulo puede bajarlo con `EXPLORE_PCT`.

### B8 · Aprendizaje: en la sesión y con la población

- **En la sesión.** El motor no guarda estado: el registro de respuestas viaja en cada llamada. Con él, actualiza solo el apetito del cliente (`cliente:c`); los pesos de la población no se tocan, porque una persona no cambia lo que se sabe de todos. Ejemplo del recorrido: Sebastián renueva el SOAT (aceptó) y su apetito pasa de 0 a +0,06; luego acepta Vida y llega a +0,12, y su probabilidad para el seguro de viaje sube de 9,2 % a 10,3 %. Un rechazo mueve mucho menos: cuando casi todos rechazan, rechazar dice poco.
- **Con la población.** `python scripts/train_motor.py --respuestas respuestas.csv` actualiza todas las creencias con las respuestas reales en orden cronológico, y **solo las promueve si mejoran**: el retador (previas + el 80 % más antiguo) debe bajar la log-pérdida en el 20 % más reciente frente al campeón (las previas), con un intervalo bootstrap al 95 % que no cruce 0. Si no, `motor.json` se queda con las previas y lo dice en `validacion`. `test_training_with_responses_learns_and_validates` lo prueba con respuestas sembradas.

---

## 3. Un ejemplo completo: Sebastián le transfiere a Laura

`python -m lulo_app.core explicar sebastian` y el evento `transferencia_fija` del recorrido:

1. **Compuertas.** Autoriza el uso de sus datos; tiene la señal de dependientes (transferencias fijas a Laura en 5 meses distintos y nómina): **fuerte**; es elegible; no tiene Vida voluntario (Vida grupo deudor no cuenta); no se le ofreció en los últimos 30 días.
2. **Probabilidad.** Base de Vida fuera del momento: **7,5 %**. La transferencia acaba de pasar (momento, × 1,63): **12,3 %**, con 90 % entre 5,2 % y 24,4 %.
3. **Valor esperado.** 12,3 % × $99.864 de comisión a 12 meses = **$12.305** (la regla v1.3 daba $9.217).
4. **Canal.** Le quedan contactos (2 de 4 en 30 días), no hay fatiga y su latencia permite disparar al instante: **push**. La abriría con probabilidad 34 %, así que el valor por contacto es $4.208.
5. **Registro.** Se guarda la decisión con su probabilidad, la versión de reglas (v2.0), la del motor (motor-1.0), el grupo y el canal.

Antes de la transferencia, el SOAT de Sebastián vence en 27 días y tiene fecha límite: gana la ventana aunque Vida tenga más valor esperado (regla v1.1).

---

## 4. ¿Mejora con más datos? El laboratorio

La base no trae respuestas a ofertas, así que no se puede probar con ella que el motor aprende. `scripts/laboratorio.py` **inventa una verdad conocida** sobre los clientes reales de la base (sus señales, su momento y sus rasgos son los de verdad), simula 40 rondas de ofertas a los 442 clientes que tienen una oferta permitida, y compara cinco políticas: la regla v1.3 (no aprende), el motor v2.0 (aprende después de cada ronda), el motor sin explorar, un oráculo que conoce la verdad (el techo) y el azar (el piso). Todas enfrentan la misma suerte (números aleatorios comunes). **No son resultados de Lulo**: muestran que el método aprende.

Efectos sembrados en la verdad del escenario «con señal» (escala probit): abrir notificaciones +0,12 y sesiones +0,08 en todos los ramos; crédito activo en Desempleo +0,30; abonos al bolsillo de viajes en Viajes +0,30; edad en Vida +0,20; abonos al bolsillo de mascotas en Mascotas +0,25; peajes recientes en SOAT +0,20; saldo en Hogar +0,15; señal media × 0,45 (el motor cree × 0,6); momento × 1,6; apetito de cada cliente con desviación 0,20.

| Escenario | Regla v1.3 | Motor | Motor sin explorar | Oráculo | Azar | Motor frente a regla | Del azar al oráculo |
|---|---:|---:|---:|---:|---:|---:|---:|
| Con señal | $8.004 | $8.811 | $8.854 | $9.043 | $6.590 | **+10,1 %** | 91 % (regla 58 %) |
| La regla tenía razón | $5.921 | $5.856 | $5.882 | $5.921 | $4.652 | **−1,1 %** | 95 % (regla 100 %) |
| Con 20 variables de ruido | $8.004 | $8.835 | $8.840 | $9.043 | $6.590 | **+10,4 %** | 92 % |
| Hipótesis equivocada (señal media × 1,0) | $10.056 | $11.124 | $11.118 | $11.356 | $8.887 | **+10,6 %** | 91 % (regla 47 %) |

Comisión esperada por oferta, promedio de las últimas 10 rondas.

Lo que muestra:

1. **Aprende lo que la regla no ve.** Con señal, el error medio de su probabilidad frente a la verdad baja de 5,5 a 3,1 puntos porcentuales; el de la regla se queda en 5,9.
2. **Descubre los pesos despacio, a propósito.** Los efectos sembrados se acercan a la verdad sin pasarse (por ejemplo, abrir notificaciones: 0 → 0,10, verdad 0,12; abonos al bolsillo de mascotas: 0 → 0,11, verdad 0,25). La previa estrecha frena perseguir ruido; con más respuestas siguen subiendo.
3. **El ruido no lo confunde.** Con 20 variables que no significan nada, su peso medio queda en 0,012 y el resultado es el mismo que sin ellas.
4. **Corrige hipótesis equivocadas.** Si la señal media vende tanto como la fuerte, el motor lo aprende y gana +10,6 %, donde la regla, atada a × 0,6, se queda en el 47 % del camino.
5. **Si la regla tenía razón, cuesta poco.** El motor empieza 2,7 % por debajo (cree en el momento y en un Hogar mejor que en esa verdad) y termina a −1,1 %.

**Una limitación que el laboratorio deja ver.** En el mundo donde la regla tenía razón, el error de la probabilidad sube de 1,4 a cerca de 3 puntos en las primeras rondas y baja despacio (2,1 en la ronda 40). El motor supone que los clientes difieren entre sí (desviación 0,25 del apetito) y, con pocas respuestas por cliente, al principio confunde suerte con apetito. A las decisiones les cuesta poco, pero con datos reales conviene **estimar esa desviación con las respuestas** (Bayes empírico sobre el apetito), que es el siguiente paso natural.

---

## 5. Por qué funciona igual o mejor con más datos y más tipos de datos

1. **Las previas son lo que se sabe hoy; los datos mueven solo lo que muestran.** Sin respuestas, el motor decide como v1.3 corregido por lo que la base sí trae (el embudo y el momento). Cada respuesta actualiza la creencia en proporción a lo que informa.
2. **Una variable nueva no cambia nada hasta que importa.** Empieza con media 0 y la duda total se reparte (0,45/√D): más tipos de datos no agregan ruido. El laboratorio con 20 variables de ruido lo confirma.
3. **Solo se promueve lo que mejora fuera de muestra.** El campeón/retador del entrenamiento con respuestas evita que un reentrenamiento empeore el motor.
4. **Las compuertas no dependen del modelo.** Autorización (Ley 1581), contacto (Ley 2300), elegibilidad, capacidad de pago, control: ningún dato nuevo puede saltárselas.
5. **Todo queda medido.** Cada decisión guarda su probabilidad y su versión; el grupo de control da el efecto real.

**Qué puede salir mal y cómo se cuida.** Variables que son consecuencia de tener seguro (se excluyen, como «visitas a Seguros»); datos con sesgo de selección (el control y la exploración dan datos sin ese sesgo); cambios en el tiempo (la actualización en línea sigue a los datos; se puede agregar olvido gradual); la transferencia del efecto del momento de compras orgánicas a ofertas (la corrige el piloto).

---

## 6. Supuestos para validar con Lulo

- El efecto del momento en compras orgánicas se traslada a la aceptación de ofertas.
- La conversión de cada campaña corresponde a una señal fuerte, y la media vale × 0,6 (con su duda).
- Hogar, sin campaña, se parece a las demás campañas (con mucha duda).
- La ventana del momento es de 30 días; la base sugiere que el efecto aparece entre 30 y 60.
- Un banner pasivo no es contacto comercial (hoja Jurídico).
- Los supuestos de v1.3 siguen: capacidad de pago (5 % del ingreso), cancelación como comisión devuelta, el rango «56+» excluido, el uso de la app de los personajes.

---

## 7. Reproducir

```bash
pip install -r requirements-dev.txt
python scripts/train_motor.py              # escribe lulo_app/ml/motor.json (≈ 2 s, Python puro)
python scripts/train_motor.py --check      # verifica que coincide
python scripts/laboratorio.py              # escribe lulo_app/ml/laboratorio.json (≈ 20 s)
python scripts/laboratorio.py --check
python -m lulo_app.core motor              # piezas del motor y sus datos
python -m lulo_app.core explicar C00002    # de dónde sale cada probabilidad
python -m lulo_app.core campana            # plan de los 600, con la comparación frente a la regla v1.3
python -m lulo_app.core campana --motor regla
python -m pytest                           # incluye tests/test_motor.py
```

Si cambia una regla (`lulo_app/core/rules.py`) o el vector de rasgos, hay que volver a correr `train_motor.py` y `laboratorio.py`, y sus `--check` deben pasar.

---

## 8. Preguntas difíciles y cómo responderlas

**¿Esto es machine learning de verdad o reglas disfrazadas?**
Es un modelo de probabilidad entrenado con los datos (un embudo jerárquico con las campañas, un estudio autocontrolado con las compras externas) que además aprende en línea de cada respuesta, como los modelos de clics de los buscadores. Las reglas siguen, pero como compuertas legales y de negocio, no como la decisión.

**Si el modelo M1 no le ganó al azar, ¿qué aprende el motor?**
M1 intentó predecir quién tiene seguro con su perfil y sus hábitos, y no pudo: en esta base no hay esa señal. El motor no inventa una: la conversión sale de las campañas y el momento de las compras externas, que sí tienen evidencia. Lo que la base no trae (respuestas a ofertas) lo aprende cuando llegan.

**¿Por qué bayesiano y no un XGBoost o una red neuronal?**
Porque no hay respuestas a ofertas para entrenarlos, y con pocos datos un modelo complejo memoriza ruido. El enfoque bayesiano empieza en lo que se sabe, dice cuánta duda tiene, aprende con cada respuesta y usa esa duda para explorar. Cuando Lulo tenga cientos de miles de respuestas se puede comparar con un modelo de *boosting* usando el mismo campeón/retador: el que gane fuera de muestra, se queda.

**¿Cómo saben que funciona si los datos son simulados?**
De dos formas. Con la base: lo que estima (conversión, momento) sale de sus datos, con intervalos honestos. Sin respuestas reales: con el laboratorio, que siembra una verdad conocida y muestra que el motor la recupera, que no empeora si no hay nada que aprender y que el ruido no lo confunde. El piloto con grupo de control es la prueba real.

**¿El efecto del momento no es casualidad?**
Puede serlo: 12 compras frente a 8,1 esperadas, con 85 % de probabilidad de que el efecto sea positivo. Por eso entra con toda su duda (de × 0,78 a × 2,86) y el motor lo corrige con las respuestas.

**¿Por qué el motor cambia 39 decisiones si casi no sabe más que la regla?**
Por tres cosas que la regla hacía mal: tomaba la conversión de cada campaña sin su ruido, le asignaba a Hogar la peor conversión por no tener campaña, e ignoraba el momento. Y 9 cambios son la exploración.

**¿Qué pasa si Lulo trae una variable nueva, por ejemplo combustible?**
Se declara en el esquema (o llega como una categoría nueva de movimientos), se reentrena y entra con peso 0. Solo cambia decisiones si las respuestas muestran que importa, y el campeón/retador solo la acepta si mejora fuera de muestra.

**¿No es invasivo usar los movimientos?**
Sin autorización (Ley 1581) el motor no lee nada. Solo usa categoría, MCC, canal, fecha y monto, nunca nombres; el cliente puede apagar las sugerencias y eso se mide como señal de daño; cada oferta explica por qué aparece.

**¿Por qué no se sale de los datos simulados para los números de negocio?**
Porque la base es sintética. El prototipo muestra el método y deja todo listo para correrlo con los datos reales (`docs/DATOS_REALES.md`).

---

## 9. Glosario

- **Valor esperado:** probabilidad de que el cliente acepte × lo que gana Lulo si acepta.
- **Previa (creencia previa):** lo que el modelo cree antes de ver nuevos datos, con su duda.
- **Posterior:** la creencia actualizada con los datos.
- **Encogimiento (*shrinkage*):** acercar la estimación de un grupo con pocos datos al promedio de los grupos.
- **Intervalo al 90 %:** con 90 % de probabilidad el valor está entre esos dos números, según el modelo.
- **Probit, Φ:** convierte una suma de pesos en una probabilidad usando la normal estándar.
- **Razón de tasas:** cuántas veces más se compra en la ventana que fuera de ella.
- **Muestreo de Thompson:** decidir con un sorteo de las creencias, para probar más lo que todavía es dudoso.
- **Log-pérdida:** qué tan bien predicen las probabilidades; menor es mejor.
- **Campeón/retador:** el modelo nuevo reemplaza al actual solo si lo supera fuera de muestra.
- **Chequeo predictivo previo:** simular con las creencias previas para ver si dan resultados plausibles.

---

## 10. Referencias

- Bastani, H., Bayati, M. y Khosravi, K. (2021). Mostly exploration-free algorithms for contextual bandits. *Management Science*, 67(3), 1329–1349.
- Chapelle, O. y Li, L. (2011). An empirical evaluation of Thompson sampling. *Advances in Neural Information Processing Systems 24*.
- Efron, B. y Morris, C. (1975). Data analysis using Stein's estimator and its generalizations. *Journal of the American Statistical Association*, 70(350), 311–319.
- Farrington, C. P. (1995). Relative incidence estimation from case series for vaccine safety evaluation. *Biometrics*, 51(1), 228–235.
- Gabry, J., Simpson, D., Vehtari, A., Betancourt, M. y Gelman, A. (2019). Visualization in Bayesian workflow. *Journal of the Royal Statistical Society A*, 182(2), 389–402.
- Gelman, A., Carlin, J. B., Stern, H. S., Dunson, D. B., Vehtari, A. y Rubin, D. B. (2013). *Bayesian Data Analysis* (3.ª ed.). CRC Press. Sección 5.3.
- Graepel, T., Quiñonero Candela, J., Borchert, T. y Herbrich, R. (2010). Web-scale Bayesian click-through rate prediction for sponsored search advertising in Microsoft's Bing search engine. *Proceedings of ICML 2010*.
- Li, L., Chu, W., Langford, J. y Wang, X. (2011). Unbiased offline evaluation of contextual-bandit-based news article recommendation algorithms. *Proceedings of WSDM 2011*.
- Minka, T. (2001). *A family of algorithms for approximate Bayesian inference*. Tesis doctoral, MIT.
- Petersen, I., Douglas, I. y Whitaker, H. (2016). Self controlled case series methods: an alternative to standard epidemiological study designs. *BMJ*, 354, i4515.
- Russo, D., Van Roy, B., Kazerouni, A., Osband, I. y Wen, Z. (2018). A tutorial on Thompson sampling. *Foundations and Trends in Machine Learning*, 11(1), 1–96.
- Thompson, W. R. (1933). On the likelihood that one unknown probability exceeds another in view of the evidence of two samples. *Biometrika*, 25(3–4), 285–294.
