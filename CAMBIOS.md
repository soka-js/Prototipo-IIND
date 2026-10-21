# Registro de cambios

Todo cambio al repositorio se anota aquí, el más reciente arriba. Es obligatorio (ver `CLAUDE.md`, sección 4).

## Formato de cada entrada

```
## AAAA-MM-DD · <autor> · rama <rama> · commit <hash corto>
- Qué cambió:
- Por qué:
- Archivos:
- Cómo se verificó: <salida real de pytest / backtest / CLI>
- Consultado con SOKA: sí (fecha y qué aprobó) / no aplica (cambio pequeño de la sección 2)
- Cifras nuevas y su origen: <de qué pestaña o cálculo sale cada una> / ninguna
- Modelo de Claude usado: <id del modelo>
```

---

## 2026-10-21 · Claude con SOKA · rama claude/admiring-wozniak-xaengq → main · aprobación de E10 (reglas v2.0)
- Qué cambió: SOKA aprobó completa la etapa E10 (motor bayesiano, laboratorio, camino para datos reales y experiencia guiada) y pidió pasarla a `main`. `CLAUDE.md` mueve lo que estaba «pendiente de confirmar» a las decisiones aprobadas (reglas v2.0) y marca E10 como hecha. Sin cambios de código.
- Por qué: queda registrada la aprobación antes del merge, como pide `CLAUDE.md` (sección 3).
- Archivos: `CLAUDE.md`, `CAMBIOS.md`.
- Cómo se verificó (sobre 8b221c3, antes del merge):
  - `python -m pytest` → 93 passed.
  - `python -m lulo_app.core backtest` → 0 violaciones; máximo de 4 push en 30 días.
  - `python scripts/train_motor.py --check`, `python scripts/laboratorio.py --check` y `python scripts/train_models.py --check` → coinciden.
- Consultado con SOKA: sí, el 2026-10-21: «todo aprobado, pásalo a main».
- Cifras nuevas y su origen: ninguna.
- Modelo de Claude usado: claude-opus-5-5.

## 2026-10-21 · Claude con SOKA · rama claude/admiring-wozniak-xaengq · commits 527da5e, ac41307 y 3cbeb29 · reglas v2.0
- Qué cambió:
  - (0) A pedido de SOKA se creó y se hizo merge del pull request soka-js/Prototipo-IIND#1 (`feat/equipo-modelos-v1.3` → `main`, commit d9c95e6) con 72 passed, backtest con 0 violaciones, `--check` y el Preview de Vercel en `success`.
  - (1) **Motor bayesiano (reglas v2.0).** El valor esperado pasa a ser P(acepta | ve) × comisión a 12 meses. P sale de una regresión probit bayesiana con actualización en línea (`lulo_app/ml/bayes.py`, `lulo_app/ml/motor.py`). Sus creencias previas vienen de la base: la conversión de cada ramo, con un Beta-Binomial jerárquico con Bayes completo sobre Campanas_Previas; el efecto del momento (el evento pasó hace menos de 30 días), con una serie de casos autocontrolada sobre las 113 compras externas de Pagos_Seguros, jerárquica por ramo y con la exposición medida para no inflar el promedio; y la señal media (× 0,6 con duda). 38 rasgos se descubren de los datos (`lulo_app/ml/rasgos.py`), empiezan con peso 0 y la duda total se reparte entre todos (0,45/√D). El motor aprende el apetito del cliente con las respuestas de la sesión y explora con muestreo de Thompson en el 10 % del tratamiento (buckets 10 a 19; el control no cambia). Las compuertas de v1.3 no cambian. `MOTOR = "regla"` (o `Context.motor`) reproduce v1.3, y cada evaluación dice qué habría elegido la regla.
  - (2) `scripts/train_motor.py` escribe `lulo_app/ml/motor.json` en Python puro y de forma determinista. Tiene `--check`, `--respuestas` (aprende de respuestas reales y solo promueve con campeón/retador), `--datos`, `--salida`, `--reporte` y `--sin-clientes`.
  - (3) `scripts/laboratorio.py` escribe `lulo_app/ml/laboratorio.json`: verdad simulada, 4 escenarios y 5 políticas.
  - (4) Camino para datos reales: `LULO_DATASET` en `core/store.py` y `core/catalog.py`, y `scripts/validar_datos.py`. El catálogo acepta valores mensuales que cambian (promedio ponderado por pólizas) y varias campañas por ramo (columna opcional `ramo`). `train_models.py` lee Seguros_Mensual de `LULO_DATASET`.
  - (5) CLI `explicar` y `motor`, `campana --motor`, ruta `GET /api/v3/motor` y columnas nuevas en el plan (`p`, `ev_regla`, `ramo_regla`, `policy`).
  - (6) **Experiencia guiada** en la v3: bienvenida con qué es el prototipo, las cuatro cosas nuevas y tres caminos; recorrido de 11 pasos con Sebastián (`public/static/v3/tour.js`); «Resaltar lo nuevo» (`data-new` en las pantallas) y su lista en «Estás viendo»; «Lo que acaba de decidir el motor» debajo del teléfono; pestañas «Recorrido» y «Aprendizaje» (`public/static/v3/aprende.js`, con gráficos accesibles y tabla equivalente); P(acepta) en la tabla de candidatos. En el celular, el recorrido va como tarjeta dentro del teléfono.
  - (7) Corrige «Laura M..» (punto doble) en «Por qué lo ves» y en el comprobante.
  - (8) `docs/MOTOR.md` y `docs/DATOS_REALES.md` nuevos; `README.md` y `CLAUDE.md` (invariante del motor, etapa E10, lo pendiente de aprobar) actualizados.
- Por qué: SOKA pidió, después de hablar con Lulo, dos cosas. Primero, un motor con lógica real de machine learning o probabilidad que use los datos, funcione igual o mejor con más datos y más tipos de datos, y esté explicado para que el equipo lo estudie y lo justifique. Segundo, un prototipo que se entienda al abrirlo: el contacto de Lulo dijo que no sabía qué hacer ni qué era nuevo.
- Archivos: `lulo_app/ml/bayes.py`, `lulo_app/ml/rasgos.py`, `lulo_app/ml/motor.py`, `lulo_app/ml/motor.json`, `lulo_app/ml/laboratorio.json`, `lulo_app/core/engine.py`, `lulo_app/core/experiment.py`, `lulo_app/core/rules.py`, `lulo_app/core/__main__.py`, `lulo_app/core/store.py`, `lulo_app/core/catalog.py`, `lulo_app/api_v3.py`, `scripts/train_motor.py`, `scripts/laboratorio.py`, `scripts/validar_datos.py`, `scripts/train_models.py`, `lulo_app/templates/app.html`, `public/static/v3/` (`app.js`, `screens.js`, `content.js`, `app.css`, `tour.js`, `aprende.js`), `tests/test_motor.py`, `tests/test_api_v3.py`, `tests/test_ml.py`, `docs/MOTOR.md`, `docs/DATOS_REALES.md`, `README.md`, `CLAUDE.md`, `CAMBIOS.md`.
- Cómo se verificó:
  - `python -m pytest` → 93 passed (21 pruebas nuevas en `tests/test_motor.py`).
  - `python -m lulo_app.core backtest` → 0 violaciones; máximo de 4 push en 30 días.
  - `python scripts/train_motor.py --check`, `python scripts/laboratorio.py --check` y `python scripts/train_models.py --check` → coinciden. Dos entrenamientos seguidos dieron el mismo sha256.
  - Plan de campaña al corte: mismos resultados y canales que v1.3 (219 push, 183 banner, 84 sin autorización, 74 sin oferta, 40 de control). De 442 decisiones, 403 iguales y 39 cambian (9 de clientes que exploran).
  - El camino de datos reales probado con una copia de la base fuera del repositorio: validar, escribir el manifiesto, entrenar con `--datos` y obtener el mismo embudo y el mismo momento.
  - Recorrido completo en Playwright, en escritorio (1440×900) y en celular (390×844); también exploración libre, escenarios rápidos, pestañas «Aprendizaje» y «Motor» y `/v2`: sin errores de consola. Sin cambios en `/v2`, en `vercel.json`, en `api/` ni en `requirements*.txt`.
- Consultado con SOKA: sí. El 2026-10-21 pidió en la conversación implementarlo en una rama aparte, completo y sin consultas intermedias. Queda para su revisión antes de pasar a `main`; en `CLAUDE.md` se lista lo que debe confirmar: valor esperado v2.0, Hogar con la predictiva, traslado del efecto del momento, 10 % de exploración y previas.
- Cifras nuevas y su origen:
  - De `scripts/train_motor.py` sobre la base (`motor.json`):
    - Conversión encogida: SOAT 12,5 %, Vida 9,5 %, Desempleo 8,6 %, Hogar 10,7 % (de 5,2 % a 17,6 %), Mascotas 10,5 % y Viajes 10,2 %. Interés 30,8 %, cierre 33,7 % y alcance del banner 25,4 % (Campanas_Previas).
    - Momento: 12 compras externas en la ventana frente a 8,1 esperadas; razón de tasas 1,54 (90 %: 0,78 a 2,86). Exposición por ramo de 29 % a 100 %. Sensibilidad: 7 días 0,60; 60 días 2,18 (Pagos_Seguros, Movimientos y Cajitas).
    - Chequeo previo: P(acepta) sorteada de 0,7 % a 31,6 %.
  - De `scripts/laboratorio.py` (verdad simulada, no son métricas de Lulo): +10,1 % con señal, −1,1 % si la regla tenía razón, +10,4 % con ruido y +10,6 % con la hipótesis equivocada.
  - Supuestos nuevos para validar con Lulo: el traslado del efecto del momento a ofertas, las previas, el 10 % de exploración y la ventana de 30 días (la base sugiere que el efecto está entre 30 y 60 días).
- Modelo de Claude usado: claude-opus-5-5.

## 2026-10-20 · Claude con SOKA · rama feat/equipo-modelos-v1.3 → main · sobre 4b0fc9e
- Qué cambió: (1) Se integró a `main` el aporte de Julián (v1.2) y Tomás (v1.3). Llegó como zip sin historial de git y entró tal cual en el commit 4b0fc9e. (2) M1 ya no usa «visitas a Seguros» en ningún ramo (`CONSEQUENCE_FEATURES` en `scripts/train_models.py`), y la evidencia queda en la llave `consecuencia` de `modelos.json`. Los modelos pasan de `ml-1.0` a `ml-1.1`. (3) El optimizador liblinear de M1 ahora usa la semilla 19. (4) `requirements-dev.txt` fija scikit-learn 1.8.0 y numpy 2.4.6. (5) La pestaña «Modelos» lee de `modelos.json` qué se excluye y qué ramos pasan la compuerta, en vez de un texto fijo. (6) Prueba nueva `test_model_never_uses_variables_that_follow_from_holding_insurance`. (7) `docs/MODELOS.md`, `README.md` y `CLAUDE.md` (decisión aprobada y etapa E9).
- Por qué: al revisar el aporte salió que «visitas a Seguros» es consecuencia de tener una póliza Lulo y no causa, y que era lo único que hacía pasar la compuerta a SOAT, Vida y Desempleo. Con ella, la afinidad subía el valor esperado de quien ya tiene otra póliza Lulo y bajaba el de quien no tiene ninguna, y la app se lo presentaba al cliente como «Clientes como tú». Además, el entrenamiento no era determinista: liblinear usaba el azar global y `--check` dependía de la versión instalada.
- Archivos: `scripts/train_models.py`, `lulo_app/ml/modelos.json`, `lulo_app/ml/models.py`, `public/static/v3/app.js`, `tests/test_ml.py`, `requirements-dev.txt`, `docs/MODELOS.md`, `README.md`, `CLAUDE.md`, `CAMBIOS.md`.
- Cómo se verificó:
  - `python -m pytest` → 72 passed.
  - `python -m lulo_app.core backtest` → 0 violaciones; máximo de 4 push en 30 días.
  - `python scripts/train_models.py --check` → coincide, dos veces seguidas.
  - Con la semilla de liblinear, 4 entrenamientos en procesos separados dieron el mismo archivo. Con la versión final, la escritura y dos `--check` seguidos coinciden (sha256 `eab826948ab4`). Antes de fijar la semilla, 4 corridas dieron 3 archivos distintos: cambiaban la estabilidad y el valor p de Vida.
  - Plan de campaña al corte (`engine.campaign()`): mismo ramo, canal y resultado que v1.1 en los 600 clientes (219 push, 183 banner, 84 sin autorización, 74 sin oferta y 40 de control). Cambia el valor esperado de 56 ofertas de SOAT y Viajes por la cancelación de v1.3. Total $2.394.020, frente a $2.396.652 en v1.1.
  - Demo guiada de 16 pasos, panel, móvil y pestaña Modelos con Playwright: sin errores de consola. `/v2` sin cambios.
- Consultado con SOKA: sí, el 2026-10-20. Aprobó sacar «visitas a Seguros» de M1 y reentrenar, fijar las versiones de scikit-learn y numpy, y pasar el resultado a `main`.
- Cifras nuevas y su origen:
  - Salen de `scripts/train_models.py` (llave `consecuencia` y `propension` de `modelos.json`):
    - Visitas a Seguros en 30 días: 2,52 con alguna póliza Lulo (274 clientes) frente a 1,13 sin ninguna.
    - AUC de las visitas para reconocer a quien ya tiene póliza Lulo: 0,731.
    - Entre quienes no tienen pólizas Lulo, AUC de las visitas: 0,448 para SOAT y 0,598 para Vida.
    - M1 en `ml-1.1`: SOAT AUC 0,53 (p 0,114), Vida 0,53 (p 0,229), Desempleo 0,57 (p 0,189); Hogar, Mascotas y Viajes en 0,50.
  - De la revisión de `ml-1.0` (`models.propensity` con el `modelos.json` de 4b0fc9e, entre quienes no tienen el ramo con Lulo):
    - Afinidad media de 1,13 en SOAT, 1,12 en Vida y 1,10 en Desempleo para quien tiene otra póliza Lulo, frente a 0,88, 0,88 y 0,82 para quien no tiene ninguna.
    - El modelo de Desempleo que corría en producción, con la selección por estabilidad dentro de cada pliegue (5×3), daba AUC 0,563 y no el 0,638 reportado.
    - Con la corrección de Holm por los 6 ramos, solo el SOAT pasaba.
- Modelo de Claude usado: claude-opus-5-5.

## 2026-10-20 · Tomás Carrillo con Claude · rama feat/tomas-datos-solicitud · reglas v1.3
- Qué cambió: (1) M5b en `scripts/train_models.py`: prueba si los pagos a otras aseguradoras caen en los 30 días siguientes al evento que dispara cada ramo (peaje, transferencia fija, bolsillo de vivienda, compra o bolsillo de mascotas), con lo esperado calculado por cliente y valor p por 20.000 simulaciones. (2) Reglas v1.3: capacidad de pago en la elegibilidad (prima mensual ≤ 5 % del ingreso mensual, prima de pago único ≤ saldo promedio) y comisión de pago único (SOAT, Viajes) × (1 − cancelación). (3) M4 pronostica también las renovaciones. (4) Pestaña «Modelos» del panel con renovaciones y M5b, y texto de M1 corregido (en Desempleo el perfil sí aporta). (5) Documentación: `docs/MODELOS.md`, `README.md`, `CLAUDE.md`.
- Por qué: cuatro datos de la solicitud a Lulo (Datos_Requeridos_Lulo_Bank) llegaron en la base y no se usaban para lo que se pidieron: renovaciones (1.1), cancelación (1.3), saldo e ingreso para capacidad de pago (2.2) y pagos externos para validar el momento de la oferta.
- Archivos: `lulo_app/core/rules.py`, `lulo_app/core/eligibility.py`, `lulo_app/core/catalog.py`, `scripts/train_models.py`, `lulo_app/ml/modelos.json`, `public/static/v3/app.js`, `tests/test_core.py`, `tests/test_ml.py`, `tests/test_api_v3.py`, `docs/MODELOS.md`, `README.md`, `CLAUDE.md`, `CAMBIOS.md`.
- Cómo se verificó: `python -m pytest` → 71 passed; `python -m lulo_app.core backtest` → 0 violaciones; `python scripts/train_models.py --check` → modelos.json coincide con el entrenamiento; plan de campaña al corte idéntico al de v1.2 en ramo, canal y resultado de los 600 clientes (402 ofertas, 50 cambios por el modelo).
- Consultado con SOKA: sí, según Tomás Carrillo el 2026-10-20 (Sebastián Socarrás dio permiso); el grupo valida el cambio antes de unir a `main`.
- Cifras nuevas y su origen: M5b 12 compras tras el evento frente a 8,1 esperadas, p = 0,083 (Pagos_Seguros, Movimientos y Cajitas); renovaciones 29 % a 34 % de lo emitido (Seguros_Mensual); VE fuerte SOAT $3.842 y Viajes $1.847 (Seguros_Mensual.cancelacion_pct); prima mensual máxima 2,5 % del ingreso mínimo (Clientes). Supuestos de v1.3 a validar con Lulo: el tope de 5 % y leer `cancelacion_pct` como comisión devuelta. Al reentrenar con scikit-learn 1.8 y numpy 2.4, el AUC del boosting cambió en el tercer decimal y el pronóstico de Viajes (45,5 exacto) redondea a 46.
- Modelo de Claude usado: claude-opus-5-5.

## 2026-10-16 · Julián Ordoñez con Claude · rama feat/julian-modelos · reglas v1.2
- Qué cambió: (1) seis modelos entrenados con la base: propensión por ramo (regresión logística L1 con selección por estabilidad), segmentos (k-medias), respuesta al push (beta-binomial con Bayes empírico), demanda por ramo (tendencia lineal), momento de compra (χ²) y tamaño del piloto (z de dos proporciones). (2) Reglas v1.2: el valor esperado se multiplica por la afinidad del modelo (probabilidad / tasa base, acotada a [0,5; 2]) solo en los ramos que pasan la prueba de permutación (SOAT, Vida y Desempleo); el modelo de push puede mandar la oferta a banner con un umbral de 20 %. (3) Pestaña «Modelos» en el panel, columna de afinidad en la traza, línea «Clientes como tú» en la oferta y segmento en Tu año. (4) Imágenes tomadas de capturas de la app real: foto del banner de seguros, ilustraciones de crédito, tarjeta y CDT, y logo de Seguros Mundial.
- Por qué: la fuerza de la señal era una hipótesis; los modelos la reemplazan por evidencia donde la base la tiene y dejan explícito dónde no.
- Archivos: `scripts/train_models.py`, `lulo_app/ml/` (`__init__.py`, `vector.py`, `models.py`, `modelos.json`), `lulo_app/core/rules.py`, `lulo_app/core/engine.py`, `lulo_app/core/contact.py`, `lulo_app/api_v3.py`, `lulo_app/templates/app.html`, `public/static/v3/app.js`, `public/static/v3/screens.js`, `public/static/v3/app.css`, `public/static/img/` (5 imágenes nuevas), `tests/test_ml.py`, `tests/test_api_v3.py` (versión v1.2), `requirements-dev.txt`, `docs/MODELOS.md`, `README.md`, `CLAUDE.md`.
- Cómo se verificó: `python -m pytest` → 67 passed; `python -m lulo_app.core backtest` → 0 violaciones; `python scripts/train_models.py --check` → modelos.json coincide con el entrenamiento; recorrido de la app con Playwright sin errores de consola.
- Consultado con SOKA: sí; Julián confirmó su aprobación el 2026-10-16.
- Cifras nuevas y su origen: todas salen de `scripts/train_models.py` sobre la base (sha256 5029790b7a29…) y quedan en `lulo_app/ml/modelos.json`; resumen en `docs/MODELOS.md`. El modelo cambia el ramo ofrecido a 50 de 600 clientes en el plan de campaña al corte (cálculo: `engine.campaign()` con y sin `rules.ML_PROPENSITY`).
- Modelo de Claude usado: claude-opus-5-5.

## 2026-10-14 · Claude con SOKA · rama main · versión 3 en producción
- Qué cambió: la versión 3 pasó a `main` (avance rápido desde `04f1b26`, sin reescribir historia) y quedó en producción en https://prototipo-iind.vercel.app. Antes se creó la rama `backup-main` en `04f1b26`, el `main` anterior, que queda congelada junto con `v2-cliente`. `CLAUDE.md`, `README.md` y `.claude/settings.json` se ajustaron al nuevo flujo: ramas `feat/<nombre>-<tema>` desde `main` y pull request hacia `main` que aprueba SOKA. Además, se bloquea el push a `backup-main`.
- Por qué: SOKA pidió que todo el equipo trabaje sobre la versión más completa y que las reglas de colaboración estén en `main`.
- Archivos: `CLAUDE.md` (secciones 3, 6 y 7), `README.md`, `.claude/settings.json`, `CAMBIOS.md`.
- Cómo se verificó: `python -m pytest` → 58 passed; `python -m lulo_app.core backtest` → 0 violaciones; `04f1b26` es ancestro de la rama `v3` (avance rápido posible); el Preview de Vercel del commit quedó en `success` antes de mover `main`.
- Consultado con SOKA: sí, lo pidió el 2026-10-14.
- Cifras nuevas y su origen: ninguna.
- Modelo de Claude usado: claude-opus-5-5.

## 2026-10-14 · Claude con SOKA · rama v3 · commit 5c928da
- Qué cambió: reglas de colaboración para compartir el repo con el equipo. `CLAUDE.md` con el modelo permitido, el alcance, qué es un cambio grande, la documentación obligatoria, las invariantes, el plan y el flujo de git. Además `.claude/settings.json`, que fija el modelo `best` y bloquea push a `main` y `v2-cliente`, push forzado y la edición manual de la base. También este registro, `.github/CODEOWNERS` y la plantilla de pull request.
- Por qué: SOKA va a compartir el repo con compañeros y pidió que sus instancias de Claude sigan solo lo planeado, usen el modelo más capaz, consulten los cambios grandes y documenten todo.
- Archivos: `CLAUDE.md`, `CAMBIOS.md`, `.claude/settings.json`, `.github/CODEOWNERS`, `.github/pull_request_template.md`, `README.md`.
- Cómo se verificó: `python -m pytest` → 58 passed; `.claude/settings.json` es JSON válido.
- Consultado con SOKA: sí, lo pidió el 2026-10-14.
- Cifras nuevas y su origen: ninguna.
- Modelo de Claude usado: claude-opus-5-5.

## 2026-10-10 · Claude con SOKA · rama v3 · commits 118b1d1 a 0db4181
Construcción de la versión 3, por etapas, con aprobación de SOKA en cada punto de control.

- **118b1d1 · E1 Ingesta.** Se agregaron `scripts/ingest_reto.py` y `lulo_app/dataset/` (CSV, `manifest.json`, `CALIDAD.md`). Verificación: 33 passed y reingesta idéntica byte a byte. Cifras: 444 movimientos y 118 abonos posteriores al corte excluidos; `conversion_impactados` = ventas/elegibles en 5 de 5 filas (Campanas_Previas).
- **66a483d · E2 Motor v3.** Se agregó `lulo_app/core` con reglas v1 aprobadas por SOKA: tabla de cobertura, valor esperado, control 10 %, banner al tope y 56+ excluido. Verificación: 50 passed y backtest con 0 violaciones.
- **bc80632 · Reglas v1.1.** Fecha límite primero, 7 días entre push y próximos disparos, aprobados por SOKA. Verificación: 52 passed y backtest con 0 violaciones.
- **2451b01 · E3 API v3.** Se agregaron `/api/v3` y Tu año calculado con el motor. Verificación: 57 passed. Cifra: Sebastián conserva $33 M (suma de ingresos de los 365 días del periodo).
- **8b76534 · E4 App v3.** Look de la app real; `/` sirve v3 y `/v2` conserva la versión del cliente. Verificación: 58 passed, la demo guiada de 16 pasos corre sin errores de consola y el Preview de Vercel quedó en `success`. Los colores salen de capturas de la app real.
- **0db4181 · Ajustes.** Tipografía y densidad como la app real; coberturas en el catálogo. Verificación: 58 passed y Preview en `success`.
- Modelo de Claude usado: claude-opus-5-5.
