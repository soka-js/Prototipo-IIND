"""Motor de disparadores: detectar → decidir → mostrar → registrar.

El motor no guarda estado entre llamadas: el cliente envía el contexto de la
sesión (preferencias, coberturas aceptadas, ventana de contacto y cola) y el
motor responde con la decisión. Las señales y las pólizas de cada cliente salen
de sus datos simulados. Así funciona igual en local y en funciones serverless.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .catalog import events_for
from .offers import for_persona as offers_for
from .signals import for_persona as signals_for
from .simulator import DEFAULT_ID, TODAY, get
from . import fmt

EventKey = Literal["credito", "vehiculo", "nomina", "viaje", "vida"]
Outcome = Literal["shown", "queued", "ineligible", "weak", "control", "optout", "noconsent"]
LogType = Literal["ok", "no", "hold", "ctrl", "harm", "info", "val"]


def _lower_first(s: str) -> str:
    return s[:1].lower() + s[1:]


class UnknownClient(LookupError):
    pass


class Decision(BaseModel):
    """Una oferta que ganó la elegibilidad y espera mostrarse."""

    key: str
    prio: int
    kind: Literal["offer", "renew"]
    offer: str = Field("", description="Clave de la oferta (credito → pago)")
    offerName: str
    ev: str
    text: str


class LogEntry(BaseModel):
    ev: str
    offer: str
    res: str
    tipo: LogType


class EngineContext(BaseModel):
    client_id: str = DEFAULT_ID
    control: bool = False
    suggestions: bool = True
    consent: bool = Field(True, description="Autorización de tratamiento de datos (Ley 1581)")
    soat_renewed: bool = False
    active: list[str] = Field(default_factory=list, description="Ofertas aceptadas en la sesión, p. ej. ['nomina']")
    window: Decision | None = Field(None, description="Oferta que ocupa la ventana de contacto")
    queue: list[Decision] = Field(default_factory=list)


class EventRequest(EngineContext):
    event: EventKey


class EngineResult(BaseModel):
    outcome: Outcome
    message: str
    chain: int = Field(description="Último paso del núcleo que se enciende (0-3)")
    decision: Decision | None = None
    queue: list[Decision]
    log: LogEntry | None = Field(None, description="Registro inmediato (los 'shown' se registran al mostrarse)")
    movement: dict
    signal: dict = Field(description="Señal que el evento alimenta, con su evidencia")


def handle_event(req: EventRequest) -> EngineResult:
    """Recorre los cuatro pasos para un evento y devuelve la decisión."""
    p = get(req.client_id)
    if p is None:
        raise UnknownClient(req.client_id)
    ev = events_for(p)[req.event]
    sig = signals_for(p.id)[req.event]
    offers = offers_for(p.id)
    queue = list(req.queue)
    base = {"movement": ev["mov"], "queue": queue, "signal": sig}

    def stop(outcome: Outcome, message: str, res: str, offer: str | None = None, tipo: LogType = "ctrl",
             chain: int = 1) -> EngineResult:
        return EngineResult(outcome=outcome, chain=chain, message=message,
                            log=LogEntry(ev=ev["label"], offer=offer or ev["offer"], res=res, tipo=tipo), **base)

    # Paso 1: sin autorización de datos el motor no puede leer el evento.
    if not req.consent:
        return stop("noconsent", "<b>Sin autorización de datos:</b> el cliente no autorizó usar sus movimientos "
                                 "(Ley 1581). El motor no lee el evento.", "Sin autorización de datos", chain=0)
    # Paso 2: decidir. Primero el diseño experimental y las preferencias del cliente.
    if req.control:
        return stop("control", "<b>Grupo de control:</b> el evento se detectó, pero no se muestra. Sirve de línea base.",
                    "Grupo de control: no se muestra")
    if not req.suggestions:
        return stop("optout", "<b>Preferencia del cliente:</b> apagó las sugerencias, así que el motor no muestra nada.",
                    "Sugerencias desactivadas por el cliente")

    def has(offer_key: str) -> bool:
        return offer_key in req.active or any(pol.get("offer") == offer_key for pol in p.policies)

    # Fuerza de la señal: un evento aislado no basta si el hábito no existe.
    if not sig["detected"] and not ev["strong"]:
        return stop("weak", f"<b>Señal débil:</b> {_lower_first(sig['headline'])}. La regla pide {_lower_first(sig['rule'])}. "
                            f"No se ofrece nada.", "Señal débil: no alcanza la regla")

    if req.event == "credito":
        if has("pago"):
            return stop("ineligible", "<b>No elegible:</b> ya tiene pago protegido. Ese beneficio se le muestra en el "
                                      "capítulo «Tu crédito» de Tu año en Lulo.",
                        "No elegible: ya tiene la cobertura", "Pago protegido")
        o = offers["pago"]
        result = Decision(key="credito", prio=ev["prio"], kind="offer", offer="pago", offerName=o["title"],
                          ev=ev["label"], text=f"<b>{o['title']} para tu crédito</b>{o['notif']}")
    elif req.event == "vehiculo":
        if not p.car:
            return stop("weak", "<b>Sin vehículo registrado:</b> el hábito existe, pero no hay un SOAT que renovar en "
                                "Lulo. Comprar un SOAT nuevo queda para la fase 2.", "Sin vehículo registrado")
        if req.soat_renewed:
            return stop("ineligible", "<b>No elegible:</b> el SOAT está al día y todo riesgo queda para la fase 2.",
                        "No elegible: SOAT al día, todo riesgo queda para fase 2", "Seguros del carro")
        days = (fmt.d(p.car["soat_expiry"]) - TODAY).days
        result = Decision(key="vehiculo", prio=ev["prio"], kind="renew", offer="soat", offerName="Renovar SOAT",
                          ev=ev["label"], text=f"<b>Tu SOAT vence en {days} días</b>"
                                               f"Renuévalo aquí y págalo desde tu cuenta Lulo.")
    else:
        o = offers[req.event]
        if has(req.event):
            return stop("ineligible", "<b>No elegible:</b> ya tiene esa cobertura. Las tres ideas comparten la misma "
                                      "regla.", "No elegible: ya tiene la cobertura", o["title"])
        result = Decision(key=req.event, prio=ev["prio"], kind="offer", offer=req.event, offerName=o["title"],
                          ev=ev["label"], text=f"<b>{o['title']} para ti</b>{o['notif']}")

    # Regla de prioridad: un contacto por ventana; el resto espera ordenado.
    if req.window is not None:
        if not any(q.key == result.key for q in queue):
            queue.append(result)
        queue.sort(key=lambda d: d.prio)
        return EngineResult(
            outcome="queued", chain=1, decision=result,
            message=f"<b>Ventana ocupada:</b> {result.offerName} espera en cola con prioridad {result.prio}.",
            log=LogEntry(ev=result.ev, offer=result.offerName,
                         res=f"En cola: ventana ocupada (prioridad {result.prio})", tipo="hold"),
            **{**base, "queue": queue})

    reason = ("El SOAT está por vencer: se ofrece renovar." if result.kind == "renew"
              else "La señal es fuerte, es elegible y la ventana está libre.")
    return EngineResult(outcome="shown", chain=2, decision=result,
                        message=f"<b>Se muestra:</b> {result.offerName}. {reason} Mira el teléfono.", **base)
