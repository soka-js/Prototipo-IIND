"""CLI del motor v3.

    python -m lulo_app.core catalogo
    python -m lulo_app.core reglas
    python -m lulo_app.core cliente C00002 [--fecha 2026-10-08]
    python -m lulo_app.core campana [--fecha 2026-10-08] [--csv plan.csv]
    python -m lulo_app.core backtest [--desde 2026-01-30] [--hasta 2026-10-08] [--cada 7]
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date

from . import backtest, catalog, engine, rules
from .store import store
from .text import cop, pct


def _date(s: str) -> date:
    return date.fromisoformat(s)


def cmd_catalogo(_a) -> int:
    print(f"{'Ramo':15}{'Precio':>20}{'Comisión 12m':>14}{'Conv. previa':>14}{'VE fuerte':>11}  Origen de la conversión")
    for r in catalog.summary():
        print(f"{r['ramo']:15}{r['price']:>20}{cop(r['commission_12m']) if r['commission_12m'] else 'n/d':>14}"
              f"{pct(r['prior']) if r['prior'] else 'n/d':>14}{cop(r['ev_fuerte']) if r['ev_fuerte'] else 'n/d':>11}  "
              f"{r['prior_source']}")
    return 0


def cmd_reglas(_a) -> int:
    print(json.dumps(rules.as_dict(), ensure_ascii=False, indent=2, default=str))
    return 0


def cmd_cliente(a) -> int:
    r = engine.evaluate(a.id, engine.Context(as_of=a.fecha, mode="lote"))
    c = store().client(a.id)
    print(f"{a.id} · {c.age_band} · {c.occupation} · {c.segment} · autoriza={'sí' if c.consent else 'no'} · "
          f"seguros con Lulo: {', '.join(p.ramo for p in c.lulo_policies) or 'ninguno'}")
    print(f"Fecha {r['as_of']} (datos hasta {r['data_until']}) · reglas {r['rules_version']}")
    for st in r["steps"]:
        print(f"  [{'✓' if st['ok'] else '✗'}] {st['step']}: {st['detail']}")
    for x in r["candidates"]:
        ev = cop(x["ev"]) if x["ev"] is not None else "—"
        print(f"    {x['ramo']:15} {x['status']:10} {x['strength']:8} VE {ev:>9}  {x['signal']['headline']}"
              + (f"  ({x['reason']})" if x["reason"] and x["status"] != "ofrecer" else ""))
    print(f"→ {r['label']}" + (f": {r['decision']['title']}" if r["decision"] else ""))
    if r["decision"]:
        print(f"  Por qué lo ves: {r['decision']['why'].replace('<b>', '').replace('</b>', '')}")
    return 0


def cmd_campana(a) -> int:
    out = engine.campaign(a.fecha, include_personas=a.personajes)
    s = out["summary"]
    print(f"Plan de campaña · fecha {out['as_of']} (datos hasta {out['data_until']}) · reglas {out['rules_version']}")
    print(f"  clientes {s['clients']}: " + ", ".join(f"{k} {v}" for k, v in s["by_outcome"].items()))
    print("  ofertas por ramo: " + ", ".join(f"{k} {v}" for k, v in s["shown_by_ramo"].items()))
    print("  banner en vez de push por: " + ", ".join(f"{k} {v}" for k, v in s["reasons_banner"].items()))
    print(f"  grupo de control: {s['control']} · valor esperado de lo mostrado: {cop(s['ev_total'])}")
    if a.csv:
        with open(a.csv, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=";")
            cols = ["client_id", "outcome", "ramo", "kind", "strength", "ev", "channel", "channel_reason", "group",
                    "offerable", "message"]
            w.writerow(cols)
            for r in out["rows"]:
                w.writerow([("|".join(r[c]) if c == "offerable" else r[c]) for c in cols])
        print(f"  CSV: {a.csv}")
    return 0


def cmd_backtest(a) -> int:
    r = backtest.run(a.desde, a.hasta, a.cada, include_personas=a.personajes)
    print(f"Backtest {r['start']} → {r['end']} cada {r['every_days']} días · reglas {r['rules_version']}")
    print(f"  {r['clients']} clientes · {r['evaluations']:,} evaluaciones".replace(",", "."))
    print(f"  ofertas {r['offers']} (push {r['push']}, banner {r['banner']}) · control {r['control']} · "
          f"clientes alcanzados {r['clients_reached']}")
    print("  por ramo: " + ", ".join(f"{k} {v}" for k, v in r["by_ramo"].items()))
    for m, c in r["by_month"].items():
        print(f"    {m}: " + ", ".join(f"{k} {v}" for k, v in sorted(c.items())))
    print(f"  máximo de push a un cliente en 30 días: {r['max_push_30d']}")
    print(f"  valor esperado de lo mostrado: {cop(r['ev_total'])}")
    print(f"  violaciones de las invariantes: {len(r['violations'])}")
    for v in r["violations"][:20]:
        print(f"    ✗ {v}")
    return 1 if r["violations"] else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m lulo_app.core", description="Motor v3 · Reto 19 Lulo Bank")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("catalogo").set_defaults(fn=cmd_catalogo)
    sub.add_parser("reglas").set_defaults(fn=cmd_reglas)
    p = sub.add_parser("cliente"); p.add_argument("id"); p.add_argument("--fecha", type=_date); p.set_defaults(fn=cmd_cliente)
    p = sub.add_parser("campana"); p.add_argument("--fecha", type=_date); p.add_argument("--csv")
    p.add_argument("--personajes", action="store_true"); p.set_defaults(fn=cmd_campana)
    p = sub.add_parser("backtest"); p.add_argument("--desde", type=_date); p.add_argument("--hasta", type=_date)
    p.add_argument("--cada", type=int, default=7); p.add_argument("--personajes", action="store_true")
    p.set_defaults(fn=cmd_backtest)
    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except (engine.UnknownClient, ValueError) as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
