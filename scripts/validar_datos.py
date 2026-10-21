"""Valida una carpeta con la base en el esquema canónico y le escribe su manifest.json.

    python scripts/validar_datos.py CARPETA [--inicio AAAA-MM-DD] [--corte AAAA-MM-DD]

Sirve para correr el motor con otra base (por ejemplo, datos reales de Lulo en su propio equipo; ver
docs/DATOS_REALES.md). Comprueba que estén los archivos y las columnas que lee el motor, que las fechas sean ISO,
que los montos sean enteros, que los clientes de cada tabla existan en clientes.csv y que los valores cerrados
(Sí/No, rangos de edad, ramos) sean los que el motor entiende. No modifica los CSV: si algo falla, lo lista y
termina con código 1. Si todo pasa, escribe manifest.json con el periodo, las filas y el sha256 de los archivos.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from lulo_app.core.schema import AGE_BANDS, RAMOS  # noqa: E402

# Columnas que lee el motor (core/store.py, core/catalog.py, ml/) por archivo.
ESQUEMA = {
    "clientes.csv": ["cliente_id", "rango_edad", "ocupacion", "antiguedad_meses", "segmento", "saldo_promedio_cop",
                     "ingreso_mensual_cop", "credito_activo", "cajitas_activas", "cdt_activo", "seguros_vigentes",
                     "autoriza_ofertas"],
    "movimientos.csv": ["mov_id", "cliente_id", "fecha", "monto_cop", "canal", "categoria", "mcc", "tipo_movimiento"],
    "cajitas.csv": ["abono_id", "cliente_id", "fecha_abono", "tipo_cajita", "monto_abono_cop"],
    "pagos_seguros.csv": ["pago_id", "cliente_id", "fecha_pago", "ramo", "monto_cop", "fecha_vencimiento", "proveedor"],
    "uso_app.csv": ["cliente_id", "sesiones_30d", "visitas_seguros_30d", "notificaciones_enviadas_30d", "abiertas_30d",
                    "ignoradas_30d", "max_contactos_mes", "latencia_eventos"],
    "seguros_mensual.csv": ["mes", "ramo", "polizas_emitidas", "renovaciones", "prima_promedio_cop", "comision_pct",
                            "persistencia_6m", "persistencia_12m", "cancelacion_pct"],
    "campanas_previas.csv": ["campana", "canal", "elegibles", "impactados", "interesados", "ventas"],
    "elegibilidad.csv": ["ramo", "edad", "ocupacion", "requisito_simulado", "periodicidad"],
}
FECHAS = {"movimientos.csv": ["fecha"], "cajitas.csv": ["fecha_abono"], "pagos_seguros.csv": ["fecha_pago", "fecha_vencimiento"]}
ENTEROS = {"movimientos.csv": ["monto_cop"], "cajitas.csv": ["monto_abono_cop"], "pagos_seguros.csv": ["monto_cop"],
           "clientes.csv": ["antiguedad_meses", "saldo_promedio_cop", "ingreso_mensual_cop"],
           "campanas_previas.csv": ["elegibles", "impactados", "interesados", "ventas"]}
SI_NO = ["credito_activo", "cajitas_activas", "cdt_activo", "autoriza_ofertas"]


def leer(p: Path) -> list[dict]:
    with open(p, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def validar(carpeta: Path) -> tuple[list[str], dict]:
    err, tablas = [], {}
    for nombre, cols in ESQUEMA.items():
        p = carpeta / nombre
        if not p.exists():
            err.append(f"falta {nombre}")
            continue
        filas = leer(p)
        falta = [c for c in cols if filas and c not in filas[0]]
        if falta:
            err.append(f"{nombre}: faltan columnas {falta}")
        tablas[nombre] = filas
    if err:
        return err, tablas
    ids = {r["cliente_id"] for r in tablas["clientes.csv"]}
    for nombre in ("movimientos.csv", "cajitas.csv", "pagos_seguros.csv", "uso_app.csv"):
        otros = {r["cliente_id"] for r in tablas[nombre]} - ids
        if otros:
            err.append(f"{nombre}: {len(otros)} clientes que no están en clientes.csv (por ejemplo {sorted(otros)[:3]})")
    for nombre, cols in FECHAS.items():
        for c in cols:
            malas = [r[c] for r in tablas[nombre] if not _iso(r[c])]
            if malas:
                err.append(f"{nombre}.{c}: {len(malas)} fechas que no son AAAA-MM-DD (por ejemplo {malas[:2]})")
    for nombre, cols in ENTEROS.items():
        for c in cols:
            malas = [r[c] for r in tablas[nombre] if not r[c].lstrip("-").isdigit()]
            if malas:
                err.append(f"{nombre}.{c}: {len(malas)} valores que no son enteros (por ejemplo {malas[:2]})")
    for c in SI_NO:
        malas = {r[c] for r in tablas["clientes.csv"]} - {"Sí", "No"}
        if malas:
            err.append(f"clientes.csv.{c}: valores {sorted(malas)}; se esperan «Sí» o «No»")
    edades = {r["rango_edad"] for r in tablas["clientes.csv"]} - set(AGE_BANDS)
    if edades:
        err.append(f"clientes.csv.rango_edad: rangos {sorted(edades)}; se esperan {list(AGE_BANDS)}")
    for nombre, col in (("pagos_seguros.csv", "ramo"), ("seguros_mensual.csv", "ramo"), ("elegibilidad.csv", "ramo")):
        malas = {r[col] for r in tablas[nombre]} - set(RAMOS)
        if malas:
            err.append(f"{nombre}.{col}: ramos {sorted(malas)}; se esperan {list(RAMOS)}")
    sin_ramo = set(RAMOS) - {r["ramo"] for r in tablas["seguros_mensual.csv"]}
    if sin_ramo:
        err.append(f"seguros_mensual.csv: faltan los ramos {sorted(sin_ramo)}")
    pol = {x for r in tablas["clientes.csv"] for x in r["seguros_vigentes"].split("|") if x} - set(RAMOS)
    if pol:
        err.append(f"clientes.csv.seguros_vigentes: ramos {sorted(pol)}; se esperan {list(RAMOS)} separados por «|»")
    return err, tablas


def _iso(s: str) -> bool:
    try:
        date.fromisoformat(s)
        return True
    except ValueError:
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("carpeta", type=Path)
    ap.add_argument("--inicio", help="inicio del periodo (por defecto, la primera fecha de movimientos)")
    ap.add_argument("--corte", help="fecha de corte (por defecto, la última fecha de movimientos)")
    a = ap.parse_args()
    err, tablas = validar(a.carpeta)
    if err:
        print(f"{a.carpeta}: {len(err)} problemas", file=sys.stderr)
        for e in err:
            print(f"  ✗ {e}", file=sys.stderr)
        sys.exit(1)
    fechas = sorted(r["fecha"] for r in tablas["movimientos.csv"])
    inicio, corte = a.inicio or fechas[0], a.corte or fechas[-1]
    posteriores = sum(1 for f in fechas if f > corte)
    h = hashlib.sha256()
    for nombre in sorted(ESQUEMA):
        h.update((a.carpeta / nombre).read_bytes())
    previo = a.carpeta / "manifest.json"
    man = json.loads(previo.read_text(encoding="utf-8")) if previo.exists() else {}
    man.update({"fuente": {"archivo": f"carpeta {a.carpeta.name}", "sha256": h.hexdigest()},
                "periodo": {"inicio": inicio, "corte": corte},
                "uso": man.get("uso", "Pruebas internas"),
                "restriccion": man.get("restriccion", "Datos de clientes: no salen del equipo de Lulo ni se suben a este repositorio."),
                "filas": {n.removesuffix(".csv"): len(t) for n, t in tablas.items()}})
    previo.write_text(json.dumps(man, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{a.carpeta}: esquema correcto · {len(tablas['clientes.csv'])} clientes · {len(fechas)} movimientos · "
          f"periodo {inicio} a {corte}" + (f" · {posteriores} movimientos después del corte (el motor no los lee)"
                                          if posteriores else ""))
    print(f"Escrito {previo}")


if __name__ == "__main__":
    main()
