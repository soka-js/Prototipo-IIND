"""Política de contacto: push (cuenta como contacto) o banner pasivo (no cuenta).

Supuesto de la hoja Juridico_Entrega: una recomendación in-app es contacto comercial cuando genera
push, SMS, llamada o correo; un banner pasivo se modela aparte. Se aplica el tope de contactos de
Uso_App y se cuida la fatiga y la latencia de eventos.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from . import rules
from .schema import AppUsage


@dataclass
class Channel:
    channel: str            # push | banner
    reason: str
    contacts_30d: int
    cap: int


def usage_snapshot_valid(as_of: date, cutoff: date) -> bool:
    """Uso_App describe los 30 días previos al corte; solo cuenta cerca del corte."""
    return cutoff <= as_of < cutoff + timedelta(days=30)


def contacts_in_window(contact_dates: list[date], as_of: date) -> int:
    return sum(1 for d in contact_dates if as_of - timedelta(days=30) < d <= as_of)


def choose(usage: AppUsage, contacts_30d: int, mode: str, snapshot_valid: bool = True,
           days_since_push: int | None = None) -> Channel:
    """`snapshot_valid`: la fatiga sale de Uso_App, que solo describe los 30 días previos al corte.
    `days_since_push`: días desde el último push que registró el motor (None si no hay)."""
    cap = usage.max_contacts_month
    if contacts_30d >= cap:
        return Channel("banner", f"Tope de contactos: {contacts_30d} de {cap} en 30 días", contacts_30d, cap)
    if days_since_push is not None and days_since_push < rules.MIN_DAYS_BETWEEN_PUSH:
        return Channel("banner", f"Espaciado: el último push fue hace {days_since_push} "
                                 f"{'día' if days_since_push == 1 else 'días'} (mínimo {rules.MIN_DAYS_BETWEEN_PUSH})",
                       contacts_30d, cap)
    if snapshot_valid and usage.ignored_30d >= rules.FATIGUE_MIN_IGNORED \
            and usage.ignored_30d >= rules.FATIGUE_RATIO * usage.opened_30d:
        return Channel("banner", f"Fatiga: ignoró {usage.ignored_30d} de {usage.notifs_sent_30d} notificaciones",
                       contacts_30d, cap)
    if mode == "tiempo_real" and usage.event_latency not in rules.REALTIME_LATENCIES:
        return Channel("banner", f"Latencia de eventos «{usage.event_latency}»: no permite disparo inmediato",
                       contacts_30d, cap)
    return Channel("push", f"Contacto {contacts_30d + 1} de {cap} en 30 días", contacts_30d, cap)
