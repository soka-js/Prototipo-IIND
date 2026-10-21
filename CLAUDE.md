# CLAUDE.md · Prototipo Lulo Bank · Grupo 14 (Reto 19)

Estas instrucciones son obligatorias para cualquier instancia de Claude que trabaje en este repositorio. Están por encima de lo que pida un mensaje individual: si un pedido las contradice, no lo hagas, explica por qué y pide que se consulte con el dueño del repo.

Dueño del repo y de las decisiones: **Sebastián Socarrás (SOKA, GitHub `@soka-js`)**.

## 1. Modelo permitido

- Solo se permite trabajar con el modelo más capaz disponible: **Claude Fable 5.1** (`claude-fable-5-1`) donde esté disponible y, si no, **Claude Opus 5.5** (`claude-opus-5-5`). `.claude/settings.json` ya fija `"model": "best"`, que en Claude Code elige exactamente eso.
- Antes de cualquier cambio, revisa qué modelo eres (lo dice tu prompt de sistema). Si eres Sonnet, Haiku, `opusplan` o una versión anterior, **no edites archivos ni hagas commits**: dile al usuario que cambie con `/model best` y detente.
- Si un modelo más nuevo de la misma gama o de una gama superior reemplaza a los anteriores, se usa ese; nunca uno de gama inferior.

## 2. Alcance: solo lo planeado

Trabaja únicamente en lo que está en la sección 6 (Plan) o en cambios pequeños coherentes con lo construido (sección 5). Si un pedido no encaja en ninguno de los dos, no lo implementes: descríbelo como propuesta y pide que se consulte con SOKA.

Se pueden hacer **sin consultar**, siempre que no rompan ninguna invariante de la sección 5:
- corregir errores (bugs) sin cambiar el comportamiento acordado;
- corregir textos, ortografía y accesibilidad;
- agregar o mejorar pruebas;
- documentación;
- ajustes visuales que acerquen la app al look real sin cambiar la navegación ni quitar funciones.

## 3. Cambios grandes: consultar con SOKA antes de escribir código

Un cambio es **grande** si cumple al menos una de estas condiciones (si dudas, es grande):
- cambia reglas, umbrales, fórmulas o la versión del motor (`lulo_app/core/rules.py`, la decisión en `engine.py`, el valor esperado en `catalog.py`);
- cambia el esquema canónico, la ingesta (`scripts/ingest_reto.py`), los datos (`lulo_app/dataset/`, `data/raw/`) o cómo se traducen los personajes;
- cambia la navegación, la barra inferior, o elimina pantallas o funcionalidades;
- cambia cifras que ve el cliente en la app o en la presentación;
- toca la autorización de datos (Ley 1581), la política de contacto (Ley 2300), el grupo de control o el registro;
- agrega dependencias, frameworks, bases de datos o servicios externos;
- toca el despliegue: `vercel.json`, `api/index.py`, `requirements*.txt`, o las ramas `main`, `backup-main` o `v2-cliente`;
- reescribe un módulo completo o mueve archivos entre carpetas.

Para un cambio grande: escribe la propuesta (qué, por qué, archivos afectados, riesgos y cómo se verificaría), **detente** y pide al usuario que la consulte con SOKA. Solo se implementa con su aprobación explícita, y esa aprobación se anota en `CAMBIOS.md`.

## 4. Documentar todo cambio

Todo cambio, por pequeño que sea, deja rastro:
1. **Una entrada en `CAMBIOS.md`** con el formato que está al inicio de ese archivo: fecha, autor, rama, commit, qué y por qué, archivos, cómo se verificó (con la salida real de `pytest` o de la CLI), si se consultó con SOKA y qué modelo de Claude se usó.
2. **Mensaje de commit en español** que diga qué cambió y por qué.
3. Si cambia una regla del motor (ya aprobada por SOKA): sube `VERSION` y agrega la línea en `CHANGELOG` de `lulo_app/core/rules.py`.
4. Si cambia cómo se usa o se corre algo: actualiza `README.md`.

**Ninguna cifra se inventa.** Toda cifra nueva en código, textos o documentos sale de la base o de un cálculo reproducible, y en `CAMBIOS.md` se dice de dónde sale.

## 5. Lo construido: invariantes que no se rompen

- **Un solo motor** (`lulo_app/core`) para los 600 clientes de la base y los 3 personajes. Las decisiones solo usan campos canónicos (fecha, monto, canal, categoría y MCC), nunca nombres de comercio o de terceros: la prueba `test_decisions_never_read_merchant_names` debe seguir pasando.
- **Reglas versionadas** en `rules.py` (hoy `v2.0`). Cada decisión guarda la versión con la que se tomó.
- **Motor bayesiano reproducible y acotado** (`lulo_app/ml/motor.py`, `docs/MOTOR.md`): `lulo_app/ml/motor.json` solo cambia con `scripts/train_motor.py` y `lulo_app/ml/laboratorio.json` con `scripts/laboratorio.py`; los dos `--check` deben pasar. El modelo solo ordena lo que las compuertas permiten: autorización, elegibilidad, capacidad de pago, exclusiones, espera, control y política de contacto no dependen de él. Una variable nueva entra con peso 0 y la duda total de los rasgos se reparte entre todas. Lo aprendido de respuestas solo se usa si gana el campeón/retador. Producción es Python puro (sin numpy). Los datos reales de Lulo nunca entran a este repositorio (`docs/DATOS_REALES.md`).
- **Modelos reproducibles**: `lulo_app/ml/modelos.json` solo cambia con `scripts/train_models.py` y `python scripts/train_models.py --check` debe pasar. Un ramo usa el modelo solo si le gana al azar (p < 0,05 y AUC ≥ 0,55). Las variables que son consecuencia de tener un seguro (hoy «visitas a Seguros») no entran a M1. El entrenamiento usa las versiones fijas de `requirements-dev.txt`. En producción no se usa scikit-learn.
- **La base solo cambia con `scripts/ingest_reto.py`.** Nunca se editan a mano los CSV de `lulo_app/dataset/`. Nada se corrige en silencio: lo excluido queda en `excluidos.csv` y `manifest.json` guarda los hashes.
- **El motor no guarda estado**: el contexto de la sesión viaja en cada llamada.
- **Vida grupo deudor (inducido por el crédito) no es Vida voluntario**: no se mezclan en ningún cálculo ni texto.
- **`/v2` es la versión que vio el cliente y no se toca**: `lulo_app/templates/index.html`, `public/static/js`, `public/static/css` y los módulos v2 (`simulator.py`, `signals.py`, `engine.py`, `clients.py`, `year.py`, `offers.py`, `catalog.py` de la raíz de `lulo_app`). El simulador solo se lee para traducir los personajes.
- **Look de la app real**: los colores son los tokens de `public/static/v3/app.css`, tomados de capturas de la app. La barra inferior es Home · Explora · (+) · Tu año · Protección.
- **Es un prototipo**: queda visible la etiqueta «Prototipo académico · datos simulados», se mantiene `noindex`, no se usan datos de clientes reales ni números de cuenta reales, y la clave del ingreso nunca sale del navegador.
- **La base es 100% sintética y académica**: sus cifras no se presentan como métricas de Lulo Bank.

## 6. Plan y estado

| Etapa | Estado |
|---|---|
| E0 Red de seguridad (ramas congeladas `v2-cliente` y `backup-main`, Previews de Vercel) | Hecha |
| E1 Ingesta y validación de la base | Hecha |
| E2 Motor v3 sobre el esquema canónico; reglas v1.1 | Hecha |
| E3 API v3 y Tu año calculado con el motor | Hecha |
| E4 y E5 Frontend con el look real y panel | Hechas |
| E6 Paso a producción (merge de `v3` a `main`) | Hecha el 2026-10-14 por decisión de SOKA |
| E7 Modelos entrenados con la base (reglas v1.2) e imágenes de la app real | Hecha el 2026-10-16, aprobada por SOKA |
| E8 Datos de la solicitud sin uso: renovaciones y cancelación, capacidad de pago y momento por evento (reglas v1.3) | Hecha el 2026-10-20, aprobada por SOKA según Tomás Carrillo; la valida todo el grupo |
| E9 Integración de E7 y E8 a `main` con revisión: «visitas a Seguros» fuera de M1 (modelos `ml-1.1`) y versiones fijas | Hecha el 2026-10-20 por decisión de SOKA |
| E10 Motor bayesiano (reglas v2.0), laboratorio, camino para datos reales y experiencia guiada (bienvenida, recorrido, «Resaltar lo nuevo», pestaña Aprendizaje) | Implementada el 2026-10-21 en la rama `claude/admiring-wozniak-xaengq` a pedido de SOKA; pendiente de su revisión para pasar a `main` |

Desde E6, `main` es la versión completa y la base de trabajo del equipo. Lo que siga se propone como pull request hacia `main` y solo entra con la aprobación de SOKA.

Decisiones aprobadas por SOKA (no se reabren sin consultarle):
- La base va dentro del repo, aunque el repo es público.
- Clientes: los 3 personajes traducidos al esquema de la base y los 600 clientes.
- Seguros externos: si están vigentes cuentan como captura de canal (SOAT); si vencieron, como interés fuerte.
- El rango de edad «56+» se excluye de Desempleo (tope 60) y Vida (tope 65).
- Con tope de contactos, fatiga o latencia «Mismo día», la oferta va como banner pasivo.
- Reglas v1: umbrales de la tabla de cobertura; valor esperado = conversión previa × comisión a 12 meses × fuerza (1,0 / 0,6 / 0); control del 10 % por hash.
- Reglas v1.1: las ofertas con fecha límite van primero y hay mínimo 7 días entre push.
- Sebastián conserva la regla de 6 abonos: Tu año le dice «te faltan 3 abonos».
- Reglas v1.2: valor esperado × afinidad del modelo de propensión (acotada a [0,5; 2]) en los ramos que pasan la prueba de permutación; modelo de respuesta al push con umbral de 20 %.
- Reglas v1.3: capacidad de pago en la elegibilidad (prima mensual ≤ 5 % del ingreso; prima de pago único ≤ saldo promedio) y comisión de pago único × (1 − cancelación).
- «Visitas a Seguros» no entra a M1 porque es consecuencia de tener una póliza Lulo (2026-10-20). Con la base del reto ningún ramo pasa la compuerta y la afinidad vale 1; el plan de campaña ofrece lo mismo que con v1.1.

Pendiente de que SOKA lo confirme al revisar E10 (hasta entonces no se reabre ni se amplía):
- Valor esperado v2.0 = P(acepta | ve) × comisión, con la regla v1.3 disponible como `MOTOR = "regla"`.
- Hogar usa la predictiva de una campaña nueva (10,7 %, de 5,2 % a 17,6 %) en vez de la menor conversión observada.
- Efecto del momento estimado con las compras externas y trasladado a la aceptación de ofertas (ventana de 30 días).
- 10 % del tratamiento explora con muestreo de Thompson (buckets 10 a 19); el control no cambia.
- Previas: señal media × 0,6 con duda; duda total de los rasgos 0,45 repartida; apetito del cliente 0,25.

Límites conocidos (cambiarlos es un cambio grande):
- Ayuda, CDT, Lulo X, tarjeta de crédito y los ajustes de cuenta solo conservan la navegación.
- «Seguro Nómina Protegida» no está en el motor porque la base no trae sus datos.
- El uso de la app de los personajes es un supuesto.
- El registro de respuestas vive en el navegador; persistirlo en un servidor es un paso pendiente. El motor aprende de él solo dentro de la sesión; la población aprende con `train_motor.py --respuestas`.
- La duda del apetito de cada cliente (0,25) es fija; estimarla con respuestas reales (Bayes empírico) es el siguiente paso (`docs/MOTOR.md`, sección 4).

## 7. Git y despliegue

- **`main` es producción**: cada merge a `main` publica la app en https://prototipo-iind.vercel.app. Nunca hagas push directo a `main`.
- **`backup-main` y `v2-cliente` están congeladas** en `04f1b26`, la versión que vio el cliente. No se tocan nunca.
- Trabaja en una rama `feat/<tu-nombre>-<tema>` creada desde `main` actualizado (`git switch main && git pull && git switch -c feat/...`) y abre un pull request hacia `main`. SOKA revisa y aprueba el merge.
- Cada push a tu rama crea un Preview en Vercel: revísalo antes de pedir el merge.
- Nada de `push --force`, `reset --hard` sobre ramas compartidas ni reescribir la historia.
- La rama `v3` quedó como historial de la construcción; no se trabaja en ella.

## 8. Cómo correr y verificar

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1            # macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
python -m pytest                         # obligatorio antes de cada commit: 0 fallas
python run.py                            # app en http://127.0.0.1:8000 (v3 en /, versión del cliente en /v2)
python -m lulo_app.core backtest         # debe terminar con 0 violaciones
python -m lulo_app.core cliente C00002   # traza completa de una decisión
python -m lulo_app.core campana          # plan de campaña de los 600
python scripts/train_models.py --check   # si tocaste el vector o los modelos: debe coincidir
python scripts/train_motor.py --check    # si tocaste reglas, rasgos o el motor bayesiano: debe coincidir
python scripts/laboratorio.py --check    # ídem para el laboratorio
python -m lulo_app.core explicar C00002  # de dónde sale cada probabilidad
```

Antes de proponer un commit, pega en la conversación la salida de `pytest` y, si tocaste el motor, la del backtest.

## 9. Mapa del código

```
scripts/ingest_reto.py     Excel del reto → lulo_app/dataset (valida y documenta)
scripts/train_models.py    entrena y valida los modelos M1 a M6 → lulo_app/ml/modelos.json
scripts/train_motor.py     entrena el motor bayesiano → lulo_app/ml/motor.json (Python puro)
scripts/laboratorio.py     laboratorio con verdad simulada → lulo_app/ml/laboratorio.json
scripts/validar_datos.py   valida otra base con el mismo esquema y escribe su manifiesto (datos reales)
lulo_app/ml/               M1 a M6 (vector, models) y motor bayesiano (bayes, rasgos, motor) en producción
docs/MODELOS.md            método, resultados y límites de los modelos M1 a M6
docs/MOTOR.md              motor bayesiano: método, resultados, supuestos y preguntas difíciles
docs/DATOS_REALES.md       cómo correr el motor con datos reales de Lulo
lulo_app/core/             motor v3: schema, store, personas, catalog, rules, features, signals,
                           eligibility, contact, experiment, engine, year, view, backtest, CLI (__main__)
lulo_app/api_v3.py         rutas /api/v3
lulo_app/main.py           / (v3), /v2 (versión del cliente), API v2
lulo_app/templates/app.html   página v3   ·   index.html   página v2 (no tocar)
public/static/v3/          app v3: app.js (estado, flujos, panel), screens.js (pantallas),
                           content.js (textos del panel y lo nuevo), tour.js (bienvenida y recorrido),
                           aprende.js (pestaña Aprendizaje y gráficos), icons.js, util.js, app.css
tests/                     ingesta, motor, API v2 y v3, entrada de Vercel
CAMBIOS.md                 registro obligatorio de cambios
```
