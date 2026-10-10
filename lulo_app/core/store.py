"""Carga la base ingerida (lulo_app/dataset) y los personajes, todo en el esquema canónico.

La carga es perezosa y se hace una sola vez por proceso: en Vercel ocurre en el arranque en frío.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

from .schema import AppUsage, Client, ExternalPolicy, History, LuloPolicy, Movement, PocketDeposit

DATASET = Path(__file__).resolve().parent.parent / "dataset"

# Los seguros que la base dice que el cliente ya tiene con Lulo no traen vencimiento ni aliado.
_LULO_TITLE = {"SOAT": "SOAT", "Vida": "Seguro de vida", "Desempleo": "Seguro de desempleo",
               "Hogar": "Seguro de hogar", "Mascotas": "Seguro de mascotas", "Viajes": "Seguro de viaje"}


@dataclass
class Store:
    cutoff: date
    start: date
    manifest: dict
    histories: dict[str, History]

    def client(self, cid: str) -> Client | None:
        h = self.histories.get(cid)
        return h.client if h else None

    def history(self, cid: str) -> History | None:
        return self.histories.get(cid)

    def ids(self, source: str | None = None) -> list[str]:
        return [k for k, h in self.histories.items() if source is None or h.client.source == source]


def _read(name: str) -> list[dict]:
    with open(DATASET / name, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _d(s: str) -> date:
    return date.fromisoformat(s)


def load_reto() -> tuple[dict, dict[str, History]]:
    manifest = json.loads((DATASET / "manifest.json").read_text(encoding="utf-8"))
    usage = {r["cliente_id"]: AppUsage(
        sessions_30d=int(r["sesiones_30d"]), insurance_visits_30d=int(r["visitas_seguros_30d"]),
        notifs_sent_30d=int(r["notificaciones_enviadas_30d"]), opened_30d=int(r["abiertas_30d"]),
        ignored_30d=int(r["ignoradas_30d"]), max_contacts_month=int(r["max_contactos_mes"]),
        event_latency=r["latencia_eventos"]) for r in _read("uso_app.csv")}
    hist: dict[str, History] = {}
    for r in _read("clientes.csv"):
        cid = r["cliente_id"]
        ramos = [x for x in r["seguros_vigentes"].split("|") if x]
        c = Client(
            id=cid, source="reto", age_band=r["rango_edad"], occupation=r["ocupacion"],
            tenure_months=int(r["antiguedad_meses"]), segment=r["segmento"], avg_balance=int(r["saldo_promedio_cop"]),
            monthly_income=int(r["ingreso_mensual_cop"]), has_credit=r["credito_activo"] == "Sí",
            has_pockets=r["cajitas_activas"] == "Sí", has_cdt=r["cdt_activo"] == "Sí",
            consent=r["autoriza_ofertas"] == "Sí",
            lulo_policies=tuple(LuloPolicy(ramo=x, title=_LULO_TITLE[x]) for x in ramos),
            usage=usage[cid])
        hist[cid] = History(client=c)
    for r in _read("movimientos.csv"):
        sign = 1 if r["tipo_movimiento"] == "Crédito" else -1
        hist[r["cliente_id"]].movements.append(Movement(
            id=r["mov_id"], client_id=r["cliente_id"], date=_d(r["fecha"]), amount=sign * int(r["monto_cop"]),
            channel=r["canal"], category=r["categoria"], mcc=r["mcc"]))
    for r in _read("cajitas.csv"):
        hist[r["cliente_id"]].deposits.append(PocketDeposit(
            id=r["abono_id"], client_id=r["cliente_id"], date=_d(r["fecha_abono"]), pocket_type=r["tipo_cajita"],
            amount=int(r["monto_abono_cop"])))
    for r in _read("pagos_seguros.csv"):
        hist[r["cliente_id"]].external.append(ExternalPolicy(
            id=r["pago_id"], client_id=r["cliente_id"], paid_on=_d(r["fecha_pago"]), ramo=r["ramo"],
            amount=int(r["monto_cop"]), expires_on=_d(r["fecha_vencimiento"]), provider=r["proveedor"]))
    for h in hist.values():
        h.movements.sort(key=lambda m: (m.date, m.id))
        h.deposits.sort(key=lambda d: (d.date, d.id))
        h.external.sort(key=lambda e: (e.paid_on, e.id))
    return manifest, hist


@lru_cache(maxsize=None)
def store() -> Store:
    from .personas import load_personas  # import tardío: los personajes dependen del corte de la base

    manifest, hist = load_reto()
    cutoff = date.fromisoformat(manifest["periodo"]["corte"])
    start = date.fromisoformat(manifest["periodo"]["inicio"])
    personas = load_personas(cutoff)
    overlap = set(personas) & set(hist)
    if overlap:
        raise ValueError(f"Ids de personajes chocan con la base: {sorted(overlap)}")
    return Store(cutoff=cutoff, start=start, manifest=manifest, histories={**personas, **hist})
