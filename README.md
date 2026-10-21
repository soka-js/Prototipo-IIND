# Prototipo Lulo Bank · Grupo 14 · Reto 19

**🔗 App en línea: https://prototipo-iind.vercel.app** · versión que vio el cliente: [`/v2`](https://prototipo-iind.vercel.app/v2) y rama `backup-main`

**Más seguros, mejor ofrecidos, dentro de la app de Lulo Bank.** Prototipo académico con datos simulados: una app con el look de la app real, un **motor bayesiano que decide qué seguro ofrecer y aprende de cada respuesta**, corriendo de verdad sobre la base sintética del reto (600 clientes, 20.473 movimientos) y sobre los tres personajes de la presentación, y un **recorrido guiado** que muestra qué es nuevo frente a la app real.

| Idea | Qué es |
|---|---|
| **Pasado**: Tu año en Lulo | Resumen de 12 meses calculado con los datos de cada cliente; el momento de protección de cada capítulo lo decide el motor. |
| **Presente**: Motor de disparadores | Lee lo que el cliente hace (nómina, transferencia fija, bolsillo, aerolínea, mascotas, peaje, desembolso), decide qué ofrecer, por qué canal y cuándo, y registra la respuesta. |
| **Futuro**: SOAT y disparos agendados | Flujo real del SOAT con Seguros Mundial, captura de canal para SOAT externos y disparos agendados (desempleo al sexto abono, vida al tercer mes). |

## Motor bayesiano y experiencia guiada (reglas v2.1)

- **Decide con probabilidad aprendida de los datos.** Valor esperado = P(acepta | ve la oferta) × comisión a 12 meses. P sale de una regresión probit bayesiana cuyas creencias previas vienen de la base: la conversión de cada ramo con un Beta-Binomial jerárquico sobre las campañas previas, y el efecto del momento (el evento pasó hace menos de 30 días) con las compras externas de Pagos_Seguros (serie de casos autocontrolada). 38 rasgos del cliente se descubren de los datos y empiezan en «no sé». Aprende en línea de cada respuesta (como AdPredictor), estima con Bayes empírico cuánto se distinguen los clientes (v2.1), explora con muestreo de Thompson en un 10 % del tratamiento y solo promueve lo aprendido si mejora fuera de muestra. Las compuertas de v1.3 no cambian. Método, resultados, supuestos y preguntas difíciles: [`docs/MOTOR.md`](docs/MOTOR.md).
- **Laboratorio con verdad simulada**: con efectos que la regla no ve, el motor gana +10 % de comisión por oferta frente a la regla v1.3; si la regla tenía razón, queda a −1,0 %; con 20 variables de ruido, igual; con una columna nueva que sí predice, la aprende solo y gana +0,8 % frente al mismo motor sin ella.
- **Listo para datos reales**: `scripts/validar_datos.py` y `scripts/train_motor.py --datos` corren en el equipo de Lulo sin subir nada ([`docs/DATOS_REALES.md`](docs/DATOS_REALES.md)).
- **Solo la app, con guía**: la página es el teléfono. Hay una bienvenida que explica qué es el prototipo y un recorrido de 11 pasos con Sebastián (qué tocar, qué es nuevo, por qué le sirve a Lulo), paso a paso con «Hazlo por mí» o **en automático**: se reproduce solo, sin tocar nada, con pausa (unos 3 minutos; `?ritmo=0.5` lo acelera y `?ritmo=1.5` lo hace más lento). Los escenarios rápidos dicen qué decidió el motor y por qué. Están también «Resaltar lo nuevo», el cambio de personaje y «Descargar respuestas (CSV)», con las ofertas de la sesión en el formato de datos reales. La guía aparece al lado del teléfono solo cuando se pide; en el celular se abre como hoja desde «Guía».

## Versión 3 (en `main` desde el 2026-10-14)

- **Look de la app real**: Home · Explora · (+) · Tu año · Protección; Explora con Ahorro, Inversión, Crédito y Seguros; Alertas, Ayuda, mapa de cajeros, Lulo Cuenta y el flujo real del SOAT. Colores tomados de capturas de la app.
- **Motor real** (`lulo_app/core`), reglas versionadas (hoy `v2.1`):
  1. Autorización de datos (Ley 1581): sin ella no se leen los movimientos.
  2. Señales con regla, fuerza y evidencia (solo fecha, monto, canal, categoría y MCC).
  3. Elegibilidad de la hoja Elegibilidad (el rango «56+» se excluye de Desempleo y Vida) y capacidad de pago (v1.3): la prima mensual no pasa del 5 % del ingreso y la de pago único no pasa del saldo promedio.
  4. Exclusiones: ya lo tiene con Lulo; vigente con otra aseguradora (salvo renovar el SOAT); espera de 30 días.
  5. Orden: fecha límite primero (SOAT por vencer, desembolso) y luego valor esperado = P(acepta) × comisión a 12 meses (v2.0; hasta v1.3 era conversión previa × comisión × fuerza × afinidad). En SOAT y Viajes, de pago único, la comisión descuenta la cancelación de la base (v1.3).
  6. Grupo de control del 10 % por hash del id; otro 10 % explora con muestreo de Thompson (v2.0).
  7. Canal: push si quedan contactos (tope 4 en 30 días), no hay fatiga, la latencia lo permite y pasaron 7 días desde el último push; si no, banner pasivo.
- **Base del reto validada** (`scripts/ingest_reto.py`): lo posterior al corte (444 movimientos y 118 abonos) se excluye con su razón; `conversion_impactados` es en realidad ventas/elegibles y se recalcula; todo queda en `lulo_app/dataset/manifest.json` y `CALIDAD.md`.
- **Backtest**: recorre el año y verifica las invariantes (tope, autorización, elegibilidad, control, espera y espaciado). Resultado: 0 violaciones. Toma las mismas decisiones sin armar la traza (en local, de 10,7 s a 6,3 s).
- **Modelos entrenados con la base (reglas v1.2 y v1.3)**: propensión por ramo, segmentos, respuesta al push, demanda (emisiones y renovaciones), momento de compra (frente a la nómina y frente al evento que dispara cada ramo) y tamaño del piloto. La afinidad del modelo ajusta el valor esperado solo en los ramos donde el modelo le gana al azar; con esta base no le gana en ninguno una vez se excluye «visitas a Seguros», que es consecuencia de tener seguro, así que el motor decide con la regla. Método y resultados en [`docs/MODELOS.md`](docs/MODELOS.md); en la app, `GET /api/v3/models`.

## Cómo colaborar

Antes de tocar el código, lee [`CLAUDE.md`](CLAUDE.md): define el modelo de Claude permitido, qué se puede hacer sin consultar, qué cambios hay que consultar con SOKA y cómo se documentan. Todo cambio se anota en [`CAMBIOS.md`](CAMBIOS.md). Se trabaja en ramas `feat/<nombre>-<tema>` creadas desde `main`, con pull request hacia `main` que aprueba SOKA. Nunca se hace push directo a `main` (es producción) ni a las ramas congeladas `backup-main` y `v2-cliente`.

## Correr en local

Se necesita Python 3.12 o superior.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # en macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
python run.py                          # abre http://127.0.0.1:8000
python -m playwright install chromium  # una vez: navegador para las pruebas de punta a punta
python -m pytest                       # pruebas (las de punta a punta se saltan si no hay navegador)
```

Motor desde la terminal:

```powershell
python -m lulo_app.core catalogo                 # productos con prima, comisión y conversión
python -m lulo_app.core reglas                   # parámetros (hoy v2.1)
python -m lulo_app.core cliente C00002           # traza completa de una decisión
python -m lulo_app.core explicar C00002          # de dónde sale cada probabilidad
python -m lulo_app.core motor                    # piezas del motor bayesiano y sus datos
python -m lulo_app.core campana --csv plan.csv   # plan de campaña de los 600 (y la comparación con v1.3)
python -m lulo_app.core campana --motor regla    # el mismo plan ordenado como v1.3
python -m lulo_app.core backtest                 # el año completo con invariantes
python scripts/ingest_reto.py                    # vuelve a ingerir el Excel (data/raw)
python scripts/train_models.py                   # reentrena los modelos (lulo_app/ml/modelos.json)
python scripts/train_models.py --check           # verifica que modelos.json coincide (scikit-learn 1.8.0, numpy 2.4.6)
python scripts/train_motor.py [--check]          # entrena el motor bayesiano (lulo_app/ml/motor.json, Python puro)
python scripts/laboratorio.py [--check]          # laboratorio con verdad simulada (lulo_app/ml/laboratorio.json)
python scripts/validar_datos.py CARPETA          # valida otra base con el mismo esquema (datos reales)
```

## Volver a la versión del cliente

- La versión que vio el cliente sigue en `/v2` dentro de esta misma app.
- Las ramas `backup-main` y `v2-cliente` congelan el commit `04f1b26`, que estuvo en producción hasta el 2026-10-14.
- En Vercel, ese despliegue de producción se puede volver a promover con *Instant Rollback* (URL fija: `prototipo-iind-4q3q7hpqv-proyects-soka.vercel.app`).

## Estructura

```
api/index.py                 entrada serverless para Vercel
data/raw/                    Excel original del reto (no se despliega)
scripts/ingest_reto.py       ingesta y validación
scripts/train_models.py      entrenamiento y validación de los modelos M1 a M6
scripts/train_motor.py       entrenamiento del motor bayesiano (embudo, momento, previas, respuestas)
scripts/laboratorio.py       laboratorio con verdad simulada
scripts/validar_datos.py     validación y manifiesto de otra base (datos reales)
docs/MODELOS.md              método, resultados y límites de los modelos M1 a M6
docs/MOTOR.md                el motor bayesiano: método, resultados, supuestos y preguntas difíciles
docs/DATOS_REALES.md         cómo correr el motor con los datos de Lulo
lulo_app/
  dataset/                   CSV normalizados, manifest.json y CALIDAD.md
  core/                      motor v3: schema, store, personas, catalog, rules, features,
                             signals, eligibility, contact, experiment, engine, year, view, backtest
  ml/                        modelos M1 a M6 (vector, modelos.json) y motor bayesiano (bayes, rasgos, motor,
                             motor.json, laboratorio.json), todo calculado en Python puro
  api_v3.py                  rutas /api/v3
  main.py                    app FastAPI: / (v3), /v2 (versión del cliente) y API v2
  simulator.py … engine.py   prototipo v2 (personajes y motor anterior)
public/static/v3/            app v3 (JS sin framework y CSS): app.js (estado, flujos, guía y escenarios), screens.js,
                             content.js (lo nuevo), tour.js (recorrido guiado), aprende.js (probabilidad por pasos y
                             decisión en lenguaje claro), util.js, icons.js
public/static/js|css         app v2
tests/                       ingesta, motor, API v2 y v3, entrada de Vercel y de punta a punta (test_e2e.py, Playwright)
```

## API v3

Documentación interactiva en `/docs`.

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/v3/meta` | Corte, reglas, catálogo y calidad de la base |
| GET | `/api/v3/clients?q=&outcome=&ramo=&source=` | Explorador de los 603 clientes con la decisión de hoy |
| GET | `/api/v3/clients/{id}?as_of=` | Todo lo que la app necesita para un cliente |
| GET | `/api/v3/clients/{id}/movements` · `/movements/{mid}` | Extracto paginado y detalle con la señal que alimenta |
| POST | `/api/v3/clients/{id}/events` | Evento de la app → movimiento → señal → decisión |
| POST | `/api/v3/clients/{id}/evaluate?focus=` | Evaluación con el contexto de la sesión |
| POST | `/api/v3/clients/{id}/year` · `/upcoming` | Tu año y disparos agendados |
| GET | `/api/v3/campaign` · `/campaign.csv` | Plan de campaña a una fecha |
| GET | `/api/v3/backtest?every=14` | Backtest con invariantes |
| GET | `/api/v3/models` | Modelos entrenados: validación, uso en el motor y resultados |
| GET | `/api/v3/motor` | Motor bayesiano: embudo, momento, rasgos, previas, validación y laboratorio |

## Supuestos

La base es 100% sintética y académica: sus cifras no son métricas de Lulo Bank. La señal media (× 0,6 de la fuerte) es una hipótesis con su duda que el motor corrige con las respuestas; el efecto del momento sale de compras orgánicas y se supone que se traslada a la aceptación de una oferta; el laboratorio usa una verdad simulada (muestra que el método aprende, no cuánto venderá Lulo); la afinidad del modelo de propensión estima parecido con quienes ya tienen el seguro (no respuesta a una oferta) y con esta base no pasa la compuerta en ningún ramo; el umbral de capacidad de pago (5 % del ingreso) y la lectura de `cancelacion_pct` como comisión devuelta en pago único son supuestos de v1.3 a validar con Lulo; Hogar no tiene campaña previa: el motor usa la predictiva de una campaña nueva (la regla v1.3 usaba la menor conversión observada); Pago protegido no está en la base y se ofrece solo al desembolsar; el uso de la app de los personajes es supuesto. Clientes, montos, placas y números de cuenta son simulados.

## Equipo

Julián Ordoñez, Nicolás Ramírez, Sebastián Socarrás y Tomás Carrillo.
