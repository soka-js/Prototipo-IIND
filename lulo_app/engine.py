"""Motor de disparadores: detectar → decidir → mostrar → registrar.

El motor es puro y sin estado: el cliente envía el contexto relevante
(preferencias, coberturas activas, ventana de contacto y cola) y el motor
devuelve la decisión. Así funciona igual en local y en funciones serverless.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .catalog import ALERT_DAYS_OPTIONS, EVENTS, OFFERS, SOAT_BASE_PRICE, SOAT_MAX_DISCOUNT

EventKey = Literal["credito", "vehiculo", "nomina", "viaje", "vida"]
Outcome = Literal["shown", "queued", "ineligible", "control", "optout"]
LogType = Literal["ok", "no", "hold", "ctrl", "harm", "info", "val"]


class Decision(BaseModel):
    """Una oferta que ganó la elegibilidad y espera mostrarse."""

    key: str
    prio: int
    kind: Literal["offer", "renew"]
    offerName: str
    ev: str
    text: str


class LogEntry(BaseModel):
    ev: str
    offer: str
    res: str
    tipo: LogType


class EngineContext(BaseModel):
    control: bool = False
    suggestions: bool = True
    soat_renewed: bool = False
    soat_days: int = 27
    active: list[str] = Field(default_factory=list, description="Coberturas aceptadas, p. ej. ['nomina']")
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


def _offer_decision(key: str, ctx: EngineContext) -> Decision | LogEntry:
    """Paso 2a: elegibilidad. Devuelve la oferta o el registro de por qué no aplica."""
    ev = EVENTS[key]
    if key == "credito":
        return LogEntry(ev=ev["label"], offer="Pago protegido",
                        res="No elegible: ya tiene la cobertura", tipo="ctrl")
    if key == "vehiculo":
        if ctx.soat_renewed:
            return LogEntry(ev=ev["label"], offer="Seguros del carro",
                            res="No elegible: SOAT al día, todo riesgo queda para fase 2", tipo="ctrl")
        return Decision(key=key, prio=ev["prio"], kind="renew", offerName="Renovar SOAT", ev=ev["label"],
                        text=f"<b>Tu SOAT vence en {ctx.soat_days} días</b>"
                             "Renuévalo aquí y págalo desde tu cuenta Lulo.")
    offer = OFFERS[key]
    if key in ctx.active:
        return LogEntry(ev=ev["label"], offer=offer["title"],
                        res="No elegible: ya tiene la cobertura", tipo="ctrl")
    return Decision(key=key, prio=ev["prio"], kind="offer", offerName=offer["title"], ev=ev["label"],
                    text=f"<b>{offer['title']} para ti</b>{offer['notif']}")


_INELIGIBLE_MSG = {
    "credito": "<b>No elegible:</b> ya tiene pago protegido. Ese beneficio se le muestra en el "
               "capítulo «Tu crédito» de Tu año en Lulo.",
    "vehiculo": "<b>No elegible:</b> el SOAT está al día y todo riesgo queda para la fase 2.",
}


def handle_event(req: EventRequest) -> EngineResult:
    """Recorre los cuatro pasos para un evento y devuelve la decisión."""
    ev = EVENTS[req.event]
    queue = list(req.queue)
    base = {"movement": ev["mov"], "queue": queue}

    # Paso 2: decidir. Primero el diseño experimental y las preferencias del cliente.
    if req.control:
        return EngineResult(
            outcome="control", chain=1,
            message="<b>Grupo de control:</b> el evento se detectó, pero no se muestra. Sirve de línea base.",
            log=LogEntry(ev=ev["label"], offer=ev["offer"], res="Grupo de control: no se muestra", tipo="ctrl"),
            **base)
    if not req.suggestions:
        return EngineResult(
            outcome="optout", chain=1,
            message="<b>Preferencia del cliente:</b> apagó las sugerencias, así que el motor no muestra nada.",
            log=LogEntry(ev=ev["label"], offer=ev["offer"], res="Sugerencias desactivadas por el cliente",
                         tipo="ctrl"),
            **base)

    result = _offer_decision(req.event, req)
    if isinstance(result, LogEntry):
        return EngineResult(
            outcome="ineligible", chain=1,
            message=_INELIGIBLE_MSG.get(req.event, "<b>No elegible:</b> ya tiene esa cobertura."),
            log=result, **base)

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
            movement=ev["mov"], queue=queue)

    reason = ("El SOAT está por vencer: se ofrece renovar." if result.kind == "renew"
              else "Es elegible y la ventana está libre.")
    return EngineResult(
        outcome="shown", chain=2, decision=result,
        message=f"<b>Se muestra:</b> {result.offerName}. {reason} Mira el teléfono.",
        **base)


def soat_quote(alert_days: int) -> dict:
    """Precio de renovación con descuento proporcional a la anticipación del aviso."""
    if alert_days not in ALERT_DAYS_OPTIONS:
        raise ValueError(f"alert_days debe ser uno de {ALERT_DAYS_OPTIONS}")
    discount = round(SOAT_BASE_PRICE * SOAT_MAX_DISCOUNT * (alert_days / 30))
    return {"days": alert_days, "base": SOAT_BASE_PRICE, "discount": discount,
            "total": SOAT_BASE_PRICE - discount}
