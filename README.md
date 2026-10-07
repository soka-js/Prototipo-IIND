# Prototipo Lulo Bank · Grupo 14

**🔗 App en línea: https://prototipo-iind.vercel.app**

**Más seguros, mejor ofrecidos, dentro de la app de Lulo Bank.** Es una app navegable con datos simulados. Muestra tres ideas que comparten un mismo mecanismo:

| Idea | Qué es |
|---|---|
| **Pasado**: Tu año en Lulo | Un resumen tipo historia de 12 meses, armado con los movimientos del cliente, con un momento de protección por capítulo. |
| **Presente**: Motor de disparadores | Lee lo que el cliente hace (transferir, abonar, pedir crédito), decide qué ofrecer y registra la respuesta. |
| **Futuro**: Recordatorio del SOAT | Aviso de vencimiento, renovación con descuento por anticipación y pago desde la cuenta Lulo. |

## Qué trae

- **App completa en el teléfono:** ingreso con clave o Face ID, saldo, tarjeta, notificaciones, un extracto de todo el año con búsqueda, filtros y carga por páginas, el detalle de cada movimiento, transferencias Bre-B con teclado, cajitas, crédito (pagar una cuota o pedir más) y perfil con preferencias y autorización de datos.
- **Tres clientes simulados** con un año de movimientos generado con una semilla fija:
  - **Sebastián:** carro, nómina nueva y crédito. Son los datos de la presentación: 1.284 movimientos y $33 M de ingresos.
  - **Valentina:** freelance, sin carro ni crédito.
  - **Andrés:** familia, SOAT a 9 días y nómina ya protegida.
- **Motor en Python:**
  1. Detecta señales con reglas explícitas, con umbral y evidencia.
  2. Arma los capítulos de Tu año. Un capítulo solo aparece si la señal que lo sostiene existe.
  3. Decide aplicando, en orden, la autorización de datos, el grupo de control, las preferencias, la fuerza de la señal, la elegibilidad y la cola por prioridad.
- **Lo que haces en la app lo lee el motor.** Por ejemplo, una transferencia a la persona que el cliente apoya cada mes dispara la oferta de vida voluntario unos segundos después.
- **Panel de presentación:**
  - Selector de cliente.
  - Desplegables de funcionalidades.
  - Motor en vivo: señales, los cuatro pasos, eventos, cola, grupo de control, métricas y registro exportable a CSV.
  - Demo guiada de 15 pasos.
- **En el celular** la app ocupa toda la pantalla y el panel se abre como una hoja. Se puede instalar en la pantalla de inicio (PWA).
- **Navegación real:** funcionan el botón atrás del navegador y del celular, y los enlaces directos como `/#/tu-ano`, `/#/movimientos` o `/?cliente=valentina`.

## Correr en local

Se necesita Python 3.12 o superior.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # en macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
python run.py                          # abre http://127.0.0.1:8000
```

`python run.py --reload` recarga el servidor al editar el código.

Pruebas:

```powershell
python -m pytest
```

## Publicar en Vercel (gratis)

El repositorio ya trae lo que Vercel necesita:
- `api/index.py`: la función de Python.
- `vercel.json`: rutas y caché.
- `public/`: los estáticos, servidos por la CDN.
- `requirements.txt`: dependencias de producción.

Opción 1, desde la web:
1. En [vercel.com/new](https://vercel.com/new), importa el repositorio y deja **Framework Preset: Other**.
2. Pulsa **Deploy**.

El proyecto `prototipo-iind` ya está conectado a este repositorio: cada `git push` a `main` publica la app en la misma URL.

Opción 2, desde la terminal:

```bash
npx vercel login
npx vercel --prod
```

## Estructura

```
api/index.py              entrada serverless para Vercel
lulo_app/
  simulator.py            clientes simulados y su año de movimientos
  signals.py              paso 1: reglas de detección con umbral y evidencia
  year.py                 capítulos de Tu año según las señales
  offers.py               ofertas con «Por qué lo ves» personalizado
  engine.py               paso 2: decisión del motor
  clients.py              vista por cliente, extracto, detalle y acciones
  catalog.py              tipos de evento, prioridades y precio del SOAT
  report.py               métricas y CSV del registro
  main.py                 app FastAPI: página y API
  templates/index.html    estructura de la página
public/static/
  js/app.js               navegación, flujos, motor, panel y demo
  js/screens.js           pantallas del teléfono
  js/content.js           desplegables y ficha «Estás viendo»
  css, fuentes e imágenes
tests/                    pruebas del simulador, el motor y el API
```

## API

La documentación interactiva está en `/docs`.

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/clients` | Clientes simulados |
| GET | `/api/clients/{id}` | Todo lo que la app necesita para un cliente |
| GET | `/api/clients/{id}/movements?q=&group=&offset=&limit=` | Extracto con búsqueda, filtro y páginas |
| GET | `/api/clients/{id}/movements/{tx}` | Detalle de un movimiento y la señal que alimenta |
| GET | `/api/clients/{id}/signals` | Señales detectadas, con regla y evidencia |
| GET | `/api/clients/{id}/year` | Capítulos de Tu año |
| POST | `/api/clients/{id}/actions` | Transferencia, abono, cuota o desembolso → movimiento y evento |
| POST | `/api/engine/event` | Decisión del motor (`shown`, `queued`, `ineligible`, `weak`, `control`, `optout`, `noconsent`) |
| GET | `/api/soat/quote?days=30&cliente=sebastian` | Cotización del SOAT según la anticipación |
| POST | `/api/report/metrics` · `/api/report/csv` | Métricas y CSV del registro |

Todos los datos, precios, placas, nombres y reglas son ilustrativos.

## Equipo

Julián Ordoñez, Nicolás Ramírez, Sebastián Socarrás y Tomás Carrillo.
