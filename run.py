"""Arranca el prototipo en local y abre el navegador.

    python run.py              # http://127.0.0.1:8000
    python run.py --port 9000 --no-browser
"""

import argparse
import threading
import webbrowser

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Prototipo Lulo Bank · Grupo 14")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true", help="no abrir el navegador")
    parser.add_argument("--reload", action="store_true", help="recargar al editar el código")
    args = parser.parse_args()

    url = f"http://{args.host}:{args.port}"
    if not args.no_browser:
        threading.Timer(1.2, webbrowser.open, args=(url,)).start()
    print(f"Prototipo corriendo en {url}  (Ctrl+C para detener)")
    uvicorn.run("lulo_app.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
