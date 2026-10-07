"""Punto de entrada de Vercel: la función serverless expone la app ASGI.

vercel.json reescribe todas las rutas a /api/index?__path=/<ruta original>, porque
la función recibe la ruta de destino y no la original. Aquí se restaura la ruta
(y se quita el parámetro) antes de pasarle la petición a FastAPI.
"""

from urllib.parse import parse_qsl, quote, urlencode

from lulo_app.main import app as fastapi_app

PARAM = "__path"


async def app(scope, receive, send):
    if scope["type"] in ("http", "websocket") and scope.get("path") == "/api/index":
        query = parse_qsl(scope.get("query_string", b"").decode("latin-1"), keep_blank_values=True)
        original = next((v for k, v in query if k == PARAM), None)
        if original is not None:
            path = "/" + original.lstrip("/")
            rest = urlencode([(k, v) for k, v in query if k != PARAM])
            scope = {**scope, "path": path, "raw_path": quote(path).encode(), "query_string": rest.encode()}
    await fastapi_app(scope, receive, send)
