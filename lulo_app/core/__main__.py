"""CLI del motor v3.

    python -m lulo_app.core catalogo
    python -m lulo_app.core reglas
    python -m lulo_app.core cliente C00002 [--fecha 2026-10-08]
    python -m lulo_app.core explicar C00002 [--fecha 2026-10-08]    # de dónde sale cada probabilidad
    python -m lulo_app.core motor                                   # piezas del motor bayesiano y sus datos
    python -m lulo_app.core campana [--fecha 2026-10-08] [--csv plan.csv] [--motor regla]
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


def _d(x: float, n: int = 2) -> str:
    return f"{x:.{n}f}".replace(".", ",")


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


PASO = {"base": "Base fuera del momento (campaña previa)", "senal_media": "Señal media frente a fuerte",
        "momento": "Momento: el evento pasó hace poco", "afinidad": "Afinidad del modelo M1",
        "rasgos": "Rasgos aprendidos de respuestas", "cliente": "Apetito del cliente (sus respuestas)"}


def cmd_explicar(a) -> int:
    r = engine.evaluate(a.id, engine.Context(as_of=a.fecha, mode="lote"))
    if r["outcome"] == "noconsent":
        print(f"{a.id}: no autoriza el uso de sus datos; el motor no lee sus movimientos (Ley 1581).")
        return 0
    mo = r["motor"]
    print(f"{a.id} · motor {mo['tipo']} ({mo['version']}) · política {mo['politica'] or '—'} · reglas {r['rules_version']}")
    for x in r["candidates"]:
        pr = x["prob"]
        if not pr:
            continue
        print(f"\n  {x['title']} · {x['status']} · señal {x['strength']}"
              + (f" · evento hace {x['momento_dias']} días" if x["momento_dias"] is not None else ""))
        for st in pr["pasos"]:
            f = f"× {st['factor']:.2f}".replace(".", ",") if st["factor"] else ""
            print(f"    {PASO[st['k']]:42} {f:>8}  → {pct(st['p'])}")
        print(f"    P(acepta si la ve) {pct(pr['p'])} (90 %: {pct(pr['ic90'][0])} a {pct(pr['ic90'][1])}) × comisión "
              f"{cop(x['valor'])} = {cop(x['ev'])}   (regla v1.3: {cop(x['ev_regla']) if x['ev_regla'] is not None else '—'})")
        if pr["rasgos_en_espera"]:
            print(f"    {pr['rasgos_en_espera']} rasgos esperan respuestas para tener peso")
    d = r["decision"]
    print(f"\n→ {r['label']}" + (f": {d['title']}" if d else "")
          + ("" if not d or r["regla"]["coincide"] else f" (la regla v1.3 habría elegido {r['regla']['ramo']})"))
    return 0


def cmd_motor(_a) -> int:
    from ..ml import motor as mot
    m = mot.resumen()
    e, t, v = m["embudo"], m["momento"], m["validacion"]
    print(f"Motor bayesiano {m['version']} · base {m['entrenado_con']['sha256_base'][:12]}… · "
          f"{m['entrenado_con']['respuestas']} respuestas")
    print(f"\nB1 embudo · {e['lectura']}")
    for k, x in e["por_ramo"].items():
        p = x["posterior"]
        print(f"  {k:10} campaña {pct(x['cruda']) if x['cruda'] is not None else 'sin campaña':>11} → {pct(p['media'])} "
              f"(90 %: {pct(p['ic90'][0])} a {pct(p['ic90'][1])})")
    print(f"\nB2 momento · {t['ventana_dias']} días · {t['total']['en_ventana']} compras externas tras el evento frente "
          f"a {_d(t['total']['esperados'], 1)} esperadas")
    for k, x in t["por_ramo"].items():
        print(f"  {k:10} razón de tasas {_d(x['rr']['media'])} (90 %: {_d(x['rr']['ic90'][0])} a {_d(x['rr']['ic90'][1])})"
              f" · {x['pagos']} pagos, {x['en_ventana']} tras el evento · en el momento {pct(t['exposicion'][k]['fraccion'])}")
    print(f"\nB3 rasgos · {m['rasgos']['n']} variables: " + ", ".join(f"{k} {n}" for k, n in m["rasgos"]["familias"].items()))
    print(f"\nValidación · {v['motivo']}")
    if m.get("laboratorio"):
        lab = m["laboratorio"]
        print(f"\nLaboratorio (verdad simulada) · {lab['resumen']}")
    return 0


def cmd_campana(a) -> int:
    out = engine.campaign(a.fecha, include_personas=a.personajes, motor=a.motor)
    s = out["summary"]
    print(f"Plan de campaña · fecha {out['as_of']} (datos hasta {out['data_until']}) · reglas {out['rules_version']} "
          f"· motor {out['motor']}")
    print(f"  clientes {s['clients']}: " + ", ".join(f"{k} {v}" for k, v in s["by_outcome"].items()))
    print("  ofertas por ramo: " + ", ".join(f"{k} {v}" for k, v in s["shown_by_ramo"].items()))
    print("  banner en vez de push por: " + ", ".join(f"{k} {v}" for k, v in s["reasons_banner"].items()))
    print(f"  grupo de control: {s['control']} · valor esperado de lo mostrado: {cop(s['ev_total'])}")
    g = s["regla"]
    print(f"  frente a la regla v1.3: {g['coinciden']} de {g['decisiones']} decisiones iguales; {g['cambian']} cambian "
          f"({g['cambian_por_exploracion']} por exploración)" + (": " + ", ".join(f"{k} {v}" for k, v in g["cambios"].items())
                                                               if g["cambios"] else ""))
    if a.csv:
        with open(a.csv, "w", encoding="utf-8-sig", newline="") as f:
            w = csv.writer(f, delimiter=";")
            cols = ["client_id", "outcome", "ramo", "kind", "strength", "p", "ev", "ev_regla", "ramo_regla", "channel",
                    "channel_reason", "group", "policy", "offerable", "message"]
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
    ap = argparse.ArgumentParser(prog="python -m lulo_app.core", description="Motor v3 (reglas v2.0) · Reto 19 Lulo Bank")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("catalogo").set_defaults(fn=cmd_catalogo)
    sub.add_parser("reglas").set_defaults(fn=cmd_reglas)
    p = sub.add_parser("cliente"); p.add_argument("id"); p.add_argument("--fecha", type=_date); p.set_defaults(fn=cmd_cliente)
    p = sub.add_parser("explicar"); p.add_argument("id"); p.add_argument("--fecha", type=_date); p.set_defaults(fn=cmd_explicar)
    sub.add_parser("motor").set_defaults(fn=cmd_motor)
    p = sub.add_parser("campana"); p.add_argument("--fecha", type=_date); p.add_argument("--csv")
    p.add_argument("--motor", choices=("bayesiano", "regla"))
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
