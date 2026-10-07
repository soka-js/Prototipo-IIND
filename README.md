# Prototipo Lulo Bank · Grupo 14

**Más seguros, mejor ofrecidos, dentro de la app de Lulo Bank.** Este prototipo interactivo de fidelidad media tiene tres ideas que comparten un mismo mecanismo:

| Idea | Qué es |
|---|---|
| **Pasado**: Tu año en Lulo | Un resumen tipo historia de 12 meses, con un momento de protección en cada capítulo. |
| **Presente**: Motor de disparadores | Lee eventos de la cuenta, decide qué ofrecer y registra la respuesta. |
| **Futuro**: Recordatorio del SOAT | Aviso de vencimiento, renovación con descuento y pago desde la cuenta Lulo. |

La interfaz (teléfono, panel de funcionalidades, motor en vivo y demo guiada de 12 pasos) es HTML, CSS y JS. **El motor de decisiones, el catálogo, la cotización del SOAT y la exportación del registro corren en Python** (FastAPI).

Todos los datos, precios, placas y nombres son ilustrativos.

## Correr en local

Se necesita Python 3.12 o superior.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1          # en macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
python run.py                          # abre http://127.0.0.1:8000
```

`python run.py --reload` recarga el servidor al editar el código, y `--port 9000` cambia el puerto.

Pruebas:

```powershell
python -m pytest
```

## Publicar gratis en Vercel

Con el plan Hobby es gratis y no hace falta tarjeta.

1. Sube este repositorio a GitHub.
2. Entra a [vercel.com/new](https://vercel.com/new), importa el repositorio y deja **Framework Preset: Other**. No hay que configurar comandos.
3. Pulsa **Deploy**. Vercel te da una URL `https://<proyecto>.vercel.app` que puedes compartir.

Cada `git push` a `main` vuelve a publicar la app automáticamente.

También se puede publicar desde la terminal con `npx vercel` (vista previa) y `npx vercel --prod` (producción).

Cómo lo resuelve Vercel:
- `public/` se sirve desde la CDN: CSS, JS, fuentes Sora e imágenes.
- `api/index.py` es una función serverless de Python que expone la app FastAPI. `vercel.json` le redirige todas las demás rutas.
- `requirements.txt` solo contiene lo que necesita producción.

## Estructura

```
api/index.py            entrada serverless para Vercel
lulo_app/
  catalog.py            eventos, ofertas, pólizas, movimientos y precios
  engine.py             motor: control, preferencias, elegibilidad y cola por prioridad
  report.py             métricas y CSV del registro de respuestas
  main.py               app FastAPI: página y API
  templates/index.html  estructura de la página
public/static/          css, js, fuentes e imágenes
tests/                  pruebas del motor y del API
run.py                  servidor local
vercel.json             configuración del despliegue
```

## API

La documentación interactiva está en `/docs`.

| Método | Ruta | Qué hace |
|---|---|---|
| GET | `/api/health` | Estado y versión |
| GET | `/api/catalog` | Catálogo y estado inicial |
| POST | `/api/engine/event` | Decide qué hacer con un evento (`shown`, `queued`, `ineligible`, `control`, `optout`) |
| GET | `/api/soat/quote?days=30` | Cotización del SOAT según la anticipación |
| POST | `/api/report/metrics` | Métricas del registro, por oferta |
| POST | `/api/report/csv` | Descarga el registro en CSV (listo para Excel) |

Ejemplo:

```bash
curl -X POST http://127.0.0.1:8000/api/engine/event \
  -H "Content-Type: application/json" \
  -d '{"event":"nomina","active":["nomina"]}'
# → {"outcome":"ineligible", ...}
```

## Equipo

Julián Ordoñez, Nicolás Ramírez, Sebastián Socarrás y Tomás Carrillo.
