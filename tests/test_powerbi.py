"""Dashboard de impacto en Power BI: reproducible, cifras recontadas desde el detalle y proyecto bien armado."""

import base64
import csv
import io
import json
import re
import sys
import zlib
from collections import defaultdict
from pathlib import Path

import pytest

from lulo_app.core import experiment, rules
from lulo_app.core.store import store

ROOT = Path(__file__).resolve().parent.parent
PBI = ROOT / "powerbi"
sys.path.insert(0, str(ROOT / "scripts"))

import exportar_powerbi as ex  # noqa: E402
import powerbi_modelo as pm  # noqa: E402
import powerbi_vista as pv  # noqa: E402


def tabla(nombre: str, carpeta: str = "datos") -> list[dict]:
    with open(PBI / carpeta / f"{nombre}.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def chica(nombre: str) -> list[dict]:
    return tabla(nombre, "tablas")


@pytest.fixture(scope="module")
def model():
    return json.loads((PBI / "Lulo_Impacto.SemanticModel" / "model.bim").read_text(encoding="utf-8"))["model"]


@pytest.fixture(scope="module")
def generado():
    tablas = {p.name: p.read_text(encoding="utf-8") for p in (PBI / "datos").glob("*.csv")}
    return pm.agregar(tablas)


# --------------------------------------------------------------------------- reproducible
def test_export_is_reproducible():
    """Como train_motor.py --check: lo que está en powerbi/ es exactamente lo que genera el exportador hoy."""
    todo = ex.archivos(verbose=False)
    distintos = [n for n, t in todo.items() if not (PBI / n).exists() or (PBI / n).read_text(encoding="utf-8") != t]
    assert not distintos, f"correr python scripts/exportar_powerbi.py: {distintos}"
    assert not ex.en_disco() - set(todo), "quedan archivos de un dashboard anterior en powerbi/"


def test_meta_points_to_this_base_and_keeps_the_prototype_label():
    meta = {r["clave"]: r for r in tabla("meta")}
    assert meta["base_sha256"]["valor"] == store().manifest["fuente"]["sha256"]
    assert "no son métricas de Lulo Bank" in meta["aviso_base"]["valor"]
    html = (PBI / "vista_previa.html").read_text(encoding="utf-8")
    assert pm.ETIQUETA in html and 'name="robots" content="noindex"' in html and "no son métricas de Lulo Bank" in html


def test_tables_never_carry_merchant_or_counterparty_names():
    for p in [*(PBI / "datos").glob("*.csv"), *(PBI / "tablas").glob("*.csv")]:
        cab = p.read_text(encoding="utf-8").splitlines()[0].lower()
        assert not re.search(r"comercio|merchant|contraparte|counterparty|tercero", cab), p.name


# --------------------------------------------------------------------------- piloto simulado (detalle)
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
    assert {r["version_reglas"] for r in rows} == {rules.VERSION}


# --------------------------------------------------------------------------- tablas del dashboard
def test_dashboard_tables_recount_the_detail():
    """Cuenta independiente, desde las tablas de detalle, de cada número de indicadores, ramo, segmento y origen."""
    dec, ven, cli = tabla("piloto_decisiones"), tabla("piloto_ventas"), tabla("piloto_clientes")
    seg = {r["cliente_id"]: r["segmento_motor"] for r in tabla("dim_cliente")}
    for ind in chica("indicadores"):
        e = ind["escenario"]
        c = [r for r in cli if r["escenario"] == e]
        d = [r for r in dec if r["escenario"] == e]
        v = [r for r in ven if r["escenario"] == e]
        trat = [r for r in c if r["grupo"] == "tratamiento"]
        assert int(ind["clientes_trat"]) == len(trat) and int(ind["clientes_ctrl"]) == len(c) - len(trat)
        assert int(ind["compran_trat"]) == sum(r["compro"] == "1" for r in trat)
        assert int(ind["comision_trat"]) == sum(int(r["comision_12m_cop"]) for r in trat)
        vistas = [r for r in d if r["resultado"] in ("aceptada", "rechazada")]
        assert int(ind["ofertas_vistas"]) == len(vistas)
        assert int(ind["ofertas_aceptadas"]) == sum(r["resultado"] == "aceptada" for r in d)
        assert int(ind["ventas"]) == len(v) and int(ind["ventas_oferta"]) == sum(r["origen"] == "oferta" for r in v)
        ramo = [r for r in chica("ramo") if r["escenario"] == e]
        assert sum(int(r["ventas_oferta"]) for r in ramo) == int(ind["ventas_oferta"])
        assert sum(int(r["vistas"]) for r in ramo) == len(vistas)
        assert all(int(r["comision_oferta"]) == int(r["ventas_oferta"]) * int(r["comision_por_venta"]) for r in ramo)
        segm = [r for r in chica("segmento") if r["escenario"] == e]
        assert sum(int(r["vistas"]) for r in segm) == len(vistas)
        for r in segm:
            assert int(r["aceptadas"]) == sum(x["resultado"] == "aceptada" for x in d if seg[x["cliente_id"]] == r["segmento"])
        assert sum(int(r["ventas"]) for r in chica("origen") if r["escenario"] == e) == len(v)
        fin = {r["grupo"]: float(r["conversion"]) for r in chica("curva") if r["escenario"] == e}   # la última semana
        assert fin["Con ofertas"] == round(int(ind["compran_trat"]) / len(trat), 5)


def test_rules_and_lab_tables_come_from_the_backtest_and_the_lab():
    assert [(r["regla"], r["violaciones"]) for r in chica("reglas")] == \
        [(r["invariante"], r["violaciones"]) for r in tabla("motor_invariantes")]
    assert sum(int(r["violaciones"]) for r in chica("reglas")) == 0
    control = {r["indicador"]: r["valor"] for r in chica("control")}
    bt = {r["metrica"]: r["valor"] for r in tabla("motor_backtest")}
    assert control["evaluaciones"] == bt["evaluaciones"] and control["push_max_30d"] == bt["max_push_30d"]
    assert int(control["sin_autorizacion"]) == sum(r["autoriza_ofertas"] == "No" for r in tabla("dim_cliente"))
    res = {r["escenario"]: r["motor_frente_a_regla"] for r in tabla("lab_resumen")}
    assert all(res[r["escenario"]] == r["motor_frente_a_regla"] for r in chica("laboratorio_resumen"))
    assert {r["politica"] for r in chica("laboratorio")} == \
        {r["politica_nombre"] for r in tabla("lab_series") if int(r["politica_orden"]) <= pm.LAB_POLITICAS}


def test_texts_with_figures_are_written_from_the_data(generado):
    """Los subtítulos y notas al pie con cifras salen de las tablas, no de un teclado."""
    _, notas = generado
    tx = pm.textos(notas)
    ind = chica("indicadores")[0]
    assert f"tiene {ind['clientes_ctrl']} clientes y {ind['compran_ctrl']} compran" in tx["pie_impacto"]
    assert f"un {rules.CONTROL_PCT} %" in tx["sub_impacto"]
    mascota = [r for r in tabla("dim_cliente") if r["segmento_motor"] == "Con mascota"]
    assert f"solo {sum('Mascotas' in r['seguros_lulo'] for r in mascota)} de {len(mascota)}" in tx["pie_valor"]
    bt = {r["metrica"]: r["valor"] for r in tabla("motor_backtest")}
    assert pm.miles(int(bt["evaluaciones"])) in tx["titulo_reglas"]
    assert "Ley 2300" in tx["pie_control"] and "de la base" in tx["pie_control"]      # el tope es de la base, no de la ley


def test_preview_and_exporter_read_the_pilot_the_same_way():
    """Dos cuentas independientes de la diferencia frente al grupo sin ofertas: la del exportador y la de la vista."""
    cli = tabla("piloto_clientes")
    tablas = {n: (PBI / "tablas" / f"{n}.csv").read_text(encoding="utf-8") for n in
              ("escenario", "indicadores", "curva", "ramo", "segmento", "origen", "laboratorio", "laboratorio_resumen",
               "reglas", "control")}
    vista = {c["escenario"]: c for c in pv.cifras(tablas)}
    for esc in ex.ESCENARIOS:
        rows = [r for r in cli if r["escenario"] == esc]
        a = ex.lectura([{"grupo": r["grupo"], "compro": r["compro"] == "1"} for r in rows])
        b = vista[esc]
        assert abs(a["uplift"] * 100 - b["dif"]) < 1e-9
        assert abs(a["ic95"][0] * 100 - b["ic"][0]) < 1e-9 and abs(a["ic95"][1] * 100 - b["ic"][1]) < 1e-9
        assert b["ic"][0] > 0 and b["veredicto"].startswith("Sí")                 # en los dos mundos el IC no toca el 0
        assert abs(a["ventas_incrementales"] - b["nuevos"]) < 1e-9


# --------------------------------------------------------------------------- proyecto de Power BI
def test_model_carries_exactly_the_dashboard_tables(model):
    """Los datos van dentro del modelo (no piden origen ni credenciales) y son los mismos de powerbi/tablas."""
    assert [t["name"] for t in model["tables"]] == sorted((p.stem for p in (PBI / "tablas").glob("*.csv")),
                                                          key=[t["name"] for t in model["tables"]].index)
    assert {p.stem for p in (PBI / "tablas").glob("*.csv")} == {t["name"] for t in model["tables"]}
    assert "expressions" not in model and "relationships" not in model
    for t in model["tables"]:
        texto = (PBI / "tablas" / f"{t['name']}.csv").read_text(encoding="utf-8")
        filas = list(csv.reader(io.StringIO(texto)))
        assert [c["name"] for c in t["columns"]] == filas[0], t["name"]
        m = "\n".join(t["partitions"][0]["source"]["expression"])
        b64 = re.search(r'Binary\.FromText\("([^"]+)"', m).group(1)
        assert json.loads(zlib.decompress(base64.b64decode(b64), -15)) == filas[1:], t["name"]
        assert m.rstrip().endswith("Tipos") and '"en-US")' in m                  # punto decimal en cualquier equipo
        for c in t["columns"]:
            if "sortByColumn" in c:
                assert c["sortByColumn"] in filas[0]


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
            # una medida no puede ir dentro de un filtro booleano de CALCULATE: se lee antes en una variable
            assert not re.search(r"\w+\[\w+\]\s*[=<>]+\s*(\[|CALCULATE)", e), m["name"]


def test_report_fields_exist_and_every_page_has_label_and_selector(model, generado):
    medidas = {(t["name"], m["name"]) for t in model["tables"] for m in t.get("measures", [])}
    cols = {(t["name"], c["name"]) for t in model["tables"] for c in t["columns"]}
    rep = json.loads((PBI / "Lulo_Impacto.Report" / "report.json").read_text(encoding="utf-8"))
    assert [s["displayName"] for s in rep["sections"]] == [p[0] for p in pm.paginas(pm.textos(generado[1]))]
    assert len(rep["sections"]) == 3
    for s in rep["sections"]:
        tipos = []
        for v in s["visualContainers"]:
            cfg = json.loads(v["config"])
            sv = cfg["singleVisual"]
            tipos.append(sv["visualType"])
            assert 0 <= v["x"] and v["x"] + v["width"] <= 1280 and 0 <= v["y"] and v["y"] + v["height"] <= 720
            if sv["visualType"] == "textbox":
                continue
            alias = {f["Name"]: f["Entity"] for f in sv["prototypeQuery"]["From"]}
            for sel in sv["prototypeQuery"]["Select"]:
                k = "Measure" if "Measure" in sel else "Column"
                par = (alias[sel[k]["Expression"]["SourceRef"]["Source"]], sel[k]["Property"])
                assert par in (medidas if k == "Measure" else cols), (s["displayName"], par)
        assert pm.ETIQUETA in json.dumps(s, ensure_ascii=False), s["displayName"]    # la etiqueta del prototipo
        assert tipos.count("slicer") == 1, s["displayName"]                         # el selector de escenario


def test_theme_is_the_same_in_the_project():
    tema = json.loads((PBI / "tema-lulo-impacto.json").read_text(encoding="utf-8"))
    assert tema["dataColors"] == pm.SERIES and tema["background"] == "#0B1430"
    assert (PBI / "Lulo_Impacto.Report/StaticResources/RegisteredResources/tema-lulo-impacto.json").read_text(
        encoding="utf-8") == (PBI / "tema-lulo-impacto.json").read_text(encoding="utf-8")


def test_measures_file_matches_the_model(model):
    dax = (PBI / "medidas.dax").read_text(encoding="utf-8")
    for t in model["tables"]:
        for m in t.get("measures", []):
            assert f"[{m['name']}] =" in dax, m["name"]


# --------------------------------------------------------------------------- casos reales (docs/CASOS.md)
def test_cases_have_a_source_and_a_known_result():
    casos = tabla("casos")
    assert len(casos) == 20
    for c in casos:
        assert c["url"].startswith("https://") and c["fuente"] and c["cifra"] and c["leccion"]
        assert c["resultado"] in ("éxito", "fracaso", "sin efecto", "mixto") and c["confianza"] in ("alta", "media")
    assert {c["resultado"] for c in casos} == {"éxito", "fracaso", "sin efecto", "mixto"}
