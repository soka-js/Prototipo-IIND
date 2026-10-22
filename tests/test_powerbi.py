"""Dashboard de Power BI: datos reproducibles, piloto simulado coherente con el motor y proyecto bien armado."""

import csv
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

import pytest

from lulo_app.core import experiment
from lulo_app.core.store import store

ROOT = Path(__file__).resolve().parent.parent
PBI = ROOT / "powerbi"
sys.path.insert(0, str(ROOT / "scripts"))

import exportar_powerbi as ex  # noqa: E402
import powerbi_modelo as pm  # noqa: E402
import powerbi_vista as pv  # noqa: E402


def tabla(nombre: str) -> list[dict]:
    with open(PBI / "datos" / f"{nombre}.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


@pytest.fixture(scope="module")
def model():
    return json.loads((PBI / "Lulo.SemanticModel" / "model.bim").read_text(encoding="utf-8"))["model"]


# --------------------------------------------------------------------------- reproducible
def test_export_is_reproducible():
    """Como train_motor.py --check: lo que está en powerbi/ es exactamente lo que genera el exportador hoy."""
    todo = ex.archivos(verbose=False)
    distintos = [n for n, t in todo.items() if (PBI / n).read_text(encoding="utf-8") != t]
    assert not distintos, f"correr python scripts/exportar_powerbi.py: {distintos}"
    assert {p.name for p in (PBI / "datos").glob("*.csv")} == {n[6:] for n in todo if n.startswith("datos/")}


def test_meta_points_to_this_base_and_keeps_the_prototype_label():
    meta = {r["clave"]: r for r in tabla("meta")}
    assert meta["base_sha256"]["valor"] == store().manifest["fuente"]["sha256"]
    assert meta["etiqueta"]["valor"] == "Prototipo académico · datos simulados"
    assert "no son métricas de Lulo Bank" in meta["aviso_base"]["valor"]
    html = (PBI / "vista_previa.html").read_text(encoding="utf-8")
    assert "Prototipo académico · datos simulados" in html and 'name="robots" content="noindex"' in html


def test_tables_never_carry_merchant_or_counterparty_names():
    for p in (PBI / "datos").glob("*.csv"):
        cab = p.read_text(encoding="utf-8").splitlines()[0].lower()
        assert not re.search(r"comercio|merchant|contraparte|counterparty|tercero", cab), p.name


# --------------------------------------------------------------------------- piloto simulado
def test_pilot_follows_the_engine_groups_and_never_shows_offers_to_control():
    dec = tabla("piloto_decisiones")
    assert {r["resultado"] for r in dec} <= {"aceptada", "rechazada", "ignorada", "control"}
    for r in dec:
        g = experiment.group(r["cliente_id"], "reto")["group"]
        assert r["grupo"] == g
        assert (r["resultado"] == "control") == (g == "control") == (r["canal"] == "ninguno")
    assert {r["escenario"] for r in dec} == set(ex.ESCENARIOS)


def test_pilot_sales_match_accepted_offers_and_client_rows():
    dec, ven, cli = tabla("piloto_decisiones"), tabla("piloto_ventas"), tabla("piloto_clientes")
    for esc in ex.ESCENARIOS:
        acept = {(r["cliente_id"], r["fecha"], r["ramo"]) for r in dec if r["escenario"] == esc and r["resultado"] == "aceptada"}
        por_oferta = {(r["cliente_id"], r["fecha"], r["ramo"]) for r in ven if r["escenario"] == esc and r["origen"] == "oferta"}
        assert acept == por_oferta                                   # cada venta por oferta es una aceptación
        c = {r["cliente_id"]: r for r in cli if r["escenario"] == esc}
        assert c.keys() == {r["cliente_id"] for r in dec if r["escenario"] == esc}   # entra quien tuvo una decisión
        n = defaultdict(int)
        for v in ven:
            if v["escenario"] == esc:
                assert v["fecha"] >= c[v["cliente_id"]]["primera_decision"]          # cuentan desde la primera decisión
                n[v["cliente_id"]] += 1
                if v["origen"] == "oferta":
                    assert c[v["cliente_id"]]["grupo"] == "tratamiento"
        assert all(int(r["ventas"]) == n[cid] and int(r["compro"]) == (n[cid] > 0) for cid, r in c.items())


def test_control_group_is_identical_in_both_worlds():
    """Sorteos comunes: lo que pasa sin ofertas no depende de la verdad que se simula."""
    cli = tabla("piloto_clientes")
    ctrl = {e: sorted((r["cliente_id"], r["compro"]) for r in cli if r["escenario"] == e and r["grupo"] == "control")
            for e in ex.ESCENARIOS}
    a, b = ctrl.values()
    assert a == b and len(a) > 30


def test_pilot_file_has_the_real_data_format():
    import train_motor
    rows = train_motor.cargar_respuestas(PBI / "datos" / "piloto_decisiones.csv")
    assert {"grupo", "politica", "p_motor", "version_reglas"} <= rows[0].keys()
    assert {r["version_reglas"] for r in rows} == {"v2.1"}


def test_preview_and_exporter_read_the_pilot_the_same_way():
    """Dos cuentas independientes de la diferencia frente al control (la del exportador y la de las medidas)."""
    cli = tabla("piloto_clientes")
    for esc in ex.ESCENARIOS:
        rows = [r for r in cli if r["escenario"] == esc]
        a = ex.lectura([{"grupo": r["grupo"], "compro": r["compro"] == "1"} for r in rows])
        b = pv.lectura_itt(rows)
        assert abs(a["uplift"] * 100 - b["dif_pp"]) < 1e-9 and abs(a["p"] - b["p"]) < 1e-12
        assert b["ic"][0] < b["dif_pp"] < b["ic"][1]


# --------------------------------------------------------------------------- proyecto de Power BI
def test_model_tables_match_the_csv_files(model):
    for t in model["tables"]:
        cab = (PBI / "datos" / f"{t['name']}.csv").read_text(encoding="utf-8").splitlines()[0].split(",")
        assert [c["name"] for c in t["columns"]] == cab, t["name"]
        assert f'LeerCsv("{t["name"]}.csv")' in "\n".join(t["partitions"][0]["source"]["expression"])
    assert {p.stem for p in (PBI / "datos").glob("*.csv")} == {t["name"] for t in model["tables"]}


def test_relationships_and_sort_columns_exist(model):
    cols = {t["name"]: {c["name"]: c for c in t["columns"]} for t in model["tables"]}
    for r in model["relationships"]:
        assert r["fromColumn"] in cols[r["fromTable"]] and r["toColumn"] in cols[r["toTable"]]
        clave = [row[r["toColumn"]] for row in tabla(r["toTable"])]
        assert len(clave) == len(set(clave)), f"{r['toTable']}[{r['toColumn']}] debe ser única"
    for t, c in cols.items():
        for col in c.values():
            if "sortByColumn" in col:
                assert col["sortByColumn"] in c


def test_every_measure_reference_resolves(model):
    medidas = {m["name"] for t in model["tables"] for m in t.get("measures", [])}
    cols = {(t["name"], c["name"]) for t in model["tables"] for c in t["columns"]}
    assert len(medidas) == sum(len(t.get("measures", [])) for t in model["tables"])      # nombres únicos
    for t in model["tables"]:
        for m in t.get("measures", []):
            e = m["expression"] if isinstance(m["expression"], str) else "\n".join(m["expression"])
            e = re.sub(r'"[^"]*"', '""', e)
            for tab, col in re.findall(r"(\w+)\[([^\]]+)\]", e):
                assert (tab, col) in cols, f"{m['name']}: {tab}[{col}]"
            for ref in re.findall(r"(?<![\w\]])\[([^\]]+)\]", e):
                assert ref in medidas, f"{m['name']}: [{ref}]"
            assert e.count("(") == e.count(")"), m["name"]
            # CALCULATE no puede ir dentro de un filtro booleano: se calcula antes en una variable
            assert not re.search(r"\w+\[\w+\]\s*[=<>]+\s*CALCULATE", e), m["name"]


def test_report_fields_exist_in_the_model(model):
    medidas = {(t["name"], m["name"]) for t in model["tables"] for m in t.get("measures", [])}
    cols = {(t["name"], c["name"]) for t in model["tables"] for c in t["columns"]}
    rep = json.loads((PBI / "Lulo.Report" / "report.json").read_text(encoding="utf-8"))
    assert [s["displayName"] for s in rep["sections"]] == [p[0] for p in pm.PAGINAS]
    for s in rep["sections"]:
        for v in s["visualContainers"]:
            sv = json.loads(v["config"])["singleVisual"]
            if sv["visualType"] == "textbox":
                continue
            alias = {f["Name"]: f["Entity"] for f in sv["prototypeQuery"]["From"]}
            for sel in sv["prototypeQuery"]["Select"]:
                k = "Measure" if "Measure" in sel else "Column"
                par = (alias[sel[k]["Expression"]["SourceRef"]["Source"]], sel[k]["Property"])
                assert par in (medidas if k == "Measure" else cols), (s["displayName"], par)
    etiqueta = [s for s in rep["sections"] if not any("meta.Etiqueta" in v["config"] for v in s["visualContainers"])]
    assert not etiqueta                                                  # la etiqueta del prototipo en todas las páginas


def test_theme_series_are_the_validated_palette():
    tema = json.loads((PBI / "tema-lulo.json").read_text(encoding="utf-8"))
    assert tema["dataColors"] == pm.SERIES and tema["background"] == "#0B1430"
    assert (PBI / "Lulo.Report/StaticResources/RegisteredResources/tema-lulo.json").read_text(encoding="utf-8") == \
        (PBI / "tema-lulo.json").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- casos reales
def test_cases_have_a_source_and_a_known_result():
    casos = tabla("casos")
    assert len(casos) == 20
    for c in casos:
        assert c["url"].startswith("https://") and c["fuente"] and c["cifra"] and c["leccion"]
        assert c["resultado"] in ("éxito", "fracaso", "sin efecto", "mixto") and c["confianza"] in ("alta", "media")
    assert {c["resultado"] for c in casos} == {"éxito", "fracaso", "sin efecto", "mixto"}
