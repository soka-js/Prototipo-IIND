# Correr el motor con datos reales de Lulo Bank (pruebas internas)

El motor del prototipo está hecho para que Lulo lo pruebe con sus datos **en su propio equipo**, sin subir nada a ningún lado. Este documento dice qué exportar, cómo validarlo, cómo entrenar y qué devolverle al equipo. El método está en [`docs/MOTOR.md`](MOTOR.md).

> **Privacidad.** Este repositorio es público. Los datos de clientes (y los archivos que se generan con ellos) **nunca se suben aquí** ni salen del equipo de Lulo. Sin autorización de uso de datos (Ley 1581) un cliente no debe entrar a la exportación de movimientos; el motor, además, no lee los movimientos de quien tiene `autoriza_ofertas = No`.

## 1. Qué exportar

Una carpeta con los mismos CSV que `lulo_app/dataset/` (UTF-8, coma como separador, fechas `AAAA-MM-DD`, montos en pesos enteros). Las columnas que lee el motor:

| Archivo | Columnas | Notas |
|---|---|---|
| `clientes.csv` | `cliente_id, rango_edad, ocupacion, antiguedad_meses, segmento, saldo_promedio_cop, ingreso_mensual_cop, credito_activo, cajitas_activas, cdt_activo, seguros_vigentes, autoriza_ofertas` | `rango_edad` en 18-25, 26-35, 36-45, 46-55 o 56+; «Sí»/«No»; `seguros_vigentes` con los ramos separados por `|` |
| `movimientos.csv` | `mov_id, cliente_id, fecha, monto_cop, canal, categoria, mcc, tipo_movimiento` | **sin nombres de comercios ni de terceros**: el motor solo usa categoría, MCC, canal, fecha y monto. `tipo_movimiento` en «Crédito»/«Débito». Las categorías nuevas (por ejemplo, combustible) entran solas como variables |
| `cajitas.csv` | `abono_id, cliente_id, fecha_abono, tipo_cajita, monto_abono_cop` | abonos a bolsillos; los tipos Viajes, Mascotas y Vivienda alimentan señales |
| `pagos_seguros.csv` | `pago_id, cliente_id, fecha_pago, ramo, monto_cop, fecha_vencimiento, proveedor` | pagos a otras aseguradoras desde la cuenta: son la evidencia del efecto del momento |
| `uso_app.csv` | `cliente_id, sesiones_30d, visitas_seguros_30d, notificaciones_enviadas_30d, abiertas_30d, ignoradas_30d, max_contactos_mes, latencia_eventos` | ventana de 30 días antes del corte |
| `seguros_mensual.csv` | `mes, ramo, polizas_emitidas, renovaciones, prima_promedio_cop, comision_pct, persistencia_6m, persistencia_12m, cancelacion_pct` | si la prima o la comisión cambian mes a mes, el motor usa el promedio ponderado por pólizas emitidas |
| `campanas_previas.csv` | `campana, canal, elegibles, impactados, interesados, ventas` y, opcional, `ramo` | con varias campañas del mismo ramo, se suman; sin la columna `ramo`, el nombre debe ser uno de los de la base («SOAT renovación», «Seguro vida»…) |
| `elegibilidad.csv` | `ramo, edad, ocupacion, requisito_simulado, periodicidad` | igual que en la base |

Los ramos son los de la base: SOAT, Vida, Desempleo, Hogar, Mascotas y Viajes. Un ramo nuevo exige agregarlo al catálogo y a las reglas (es un cambio grande del motor).

### Respuestas a ofertas (lo que más le enseña al motor)

Si Lulo tiene registro de ofertas mostradas y su resultado, un CSV aparte (fuera de la carpeta de la base):

| Columna | Valores |
|---|---|
| `cliente_id` | el de `clientes.csv` |
| `fecha` | día en que se mostró la oferta |
| `ramo` | SOAT, Vida, Desempleo, Hogar, Mascotas o Viajes |
| `canal` | push, banner, correo… |
| `resultado` | `aceptada`, `rechazada` o `ignorada` |

Hoy el entrenamiento usa `aceptada` y `rechazada` (la aceptación cuando el cliente vio la oferta); `ignorada` queda para el modelo de canal. Si existen, sirven también `grupo` (control o tratamiento) y `politica` (explotar o explorar): el grupo de control es lo que permite medir el efecto real.

El prototipo descarga este mismo archivo con «Descargar respuestas (CSV)» en el encabezado. Trae las ofertas que el motor mostró en la sesión, de todos los clientes que se abrieron, con su resultado; las que quedaron sin respuesta salen como `ignorada`. Agrega `grupo`, `politica`, `p_motor` (la probabilidad con la que se decidió) y `version_reglas`. Sirve para probar el entrenamiento de punta a punta: `python scripts/train_motor.py --respuestas respuestas-prototipo.csv --salida motor-prueba.json`.

## 2. Validar la carpeta

```bash
python scripts/validar_datos.py CARPETA --inicio 2025-11-01 --corte 2026-10-08
```

Comprueba archivos, columnas, fechas, montos, que cada cliente exista en `clientes.csv` y los valores cerrados. Si algo falla, lo lista y no escribe nada; si todo pasa, escribe `CARPETA/manifest.json` con el periodo, las filas y el sha256 de los archivos.

## 3. Entrenar y revisar

```bash
# M1 a M6 (opcional; usa scikit-learn) y el motor bayesiano (Python puro)
LULO_DATASET=CARPETA python scripts/train_models.py
python scripts/train_motor.py --datos CARPETA --respuestas respuestas.csv \
       --salida CARPETA/motor.json --reporte CARPETA/reporte.md --sin-clientes

# El motor completo con esos datos: trazas, plan de campaña y backtest
LULO_DATASET=CARPETA python -m lulo_app.core motor
LULO_DATASET=CARPETA python -m lulo_app.core explicar CLIENTE_ID
LULO_DATASET=CARPETA python -m lulo_app.core campana --csv CARPETA/plan.csv
LULO_DATASET=CARPETA python -m lulo_app.core backtest
```

En Windows (PowerShell) la variable se fija con `$env:LULO_DATASET = "CARPETA"` antes de cada comando.

- `train_models.py` escribe `lulo_app/ml/modelos.json` en la copia local del repositorio: no la suban.
- `train_motor.py --datos` no toca el repositorio: escribe donde diga `--salida`. Para que la app use ese motor, copien el JSON a `lulo_app/ml/motor.json` **solo en su copia local**.
- `--sin-clientes` deja fuera el apetito aprendido de cada cliente (que va con su id), para poder compartir el JSON.

## 4. Cómo leer el reporte

`reporte.md` trae, sin datos de clientes:

- **B1 · Conversión por ramo:** la de cada campaña y la creencia encogida, con su intervalo. Si un ramo cambia mucho al encogerse, tiene pocas ventas.
- **B2 · Momento:** cuántas compras externas caen en los 30 días después del evento frente a lo esperado al azar, por ramo. Una razón de tasas con intervalo por encima de 1 es evidencia de que ofrecer en el momento funciona.
- **Validación:** si hubo respuestas, la log-pérdida del campeón (las creencias previas) y del retador (lo aprendido) en el 20 % más reciente. Lo aprendido solo se usa si el retador mejora con un intervalo al 95 % que no cruza 0.
- **Dispersión del apetito (τ̂):** cuánto se distinguen los clientes entre sí, estimado con Bayes empírico sobre las respuestas (reglas v2.1). Cerca de 0 quiere decir que las diferencias entre clientes se explican con sus variables; un τ̂ alto, que cada cliente tiene un apetito propio que el motor aprende rápido de sus respuestas. Sin respuestas se supone 0,25.

## 5. Qué devolverle al equipo

- `reporte.md` y, si quieren, el `motor.json` entrenado con `--sin-clientes`: no tienen datos de clientes, solo parámetros agregados.
- Las conclusiones del plan de campaña y del backtest en cifras agregadas (por ramo, por canal, por mes).
- Nunca los CSV, el plan por cliente ni un `motor.json` sin `--sin-clientes`.

## 6. Qué esperar

- Con solo los datos de la base (sin respuestas), el motor ordena con la conversión de las campañas y el efecto del momento: sabe poco más que las reglas, y lo dice con sus intervalos.
- Con respuestas, aprende qué rasgos importan, corrige las hipótesis (por ejemplo, la señal media × 0,6), estima cuánto se distinguen los clientes (τ̂) y el apetito de cada uno. El laboratorio (`docs/MOTOR.md`, sección 4) muestra cuánto puede mejorar y que no empeora si no hay nada que aprender.
- El paso siguiente con datos reales es el piloto con grupo de control: para detectar un aumento de 50 % en el SOAT hacen falta 510 clientes por grupo (modelo M6).
