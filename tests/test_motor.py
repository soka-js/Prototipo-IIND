"""Motor bayesiano (reglas v2.1): matemática, calibración, invariantes, aprendizaje y laboratorio."""

import csv
import json
import math
import sys
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from lulo_app.core import engine, experiment, rules
from lulo_app.core.engine import Context, Event, OfferLog, evaluate, on_event
from lulo_app.core.schema import RAMOS, History
from lulo_app.core.store import store
from lulo_app.main import app
from lulo_app.ml import bayes, motor, rasgos

ROOT = Path(__file__).resolve().parent.parent
CUTOFF = date(2026, 10, 8)
SP = motor.spec()


def cand(r, ramo):
    return next(x for x in r["candidates"] if x["ramo"] == ramo)


# --------------------------------------------------------------------------- matemática
def test_normal_and_beta_functions():
    assert bayes.Phi(0) == pytest.approx(0.5) and bayes.Phi_inv(0.975) == pytest.approx(1.959964, abs=1e-6)
    assert bayes.Phi(bayes.Phi_inv(0.123)) == pytest.approx(0.123, abs=1e-9)
    assert bayes.digamma(1) == pytest.approx(-0.5772156649, abs=1e-9)
    assert bayes.trigamma(1) == pytest.approx(math.pi ** 2 / 6, abs=1e-9)
    assert bayes.betainc(3, 3, 0.5) == pytest.approx(0.5, abs=1e-12)
    assert bayes.beta_quantile(2, 5, bayes.betainc(2, 5, 0.3)) == pytest.approx(0.3, abs=1e-9)
    assert bayes.mills(-40) == pytest.approx(40.025, rel=1e-3)          # estable lejos en la cola


def test_hierarchical_funnel_shrinks_and_widens_new_groups():
    rows = [(178, 1380), (84, 910), (61, 760), (73, 690), (59, 580)]
    h = bayes.beta_binomial_bayes(rows)
    raw = [y / n for y, n in rows]
    post = [g["media"] for g in h["grupos"]]
    assert max(post) - min(post) < max(raw) - min(raw)                                     # se encogen hacia el promedio
    assert all(abs(p - q) < 0.01 for p, q in zip(post, raw))                               # sin perder su evidencia
    assert h["nuevo"]["sd"] > 3 * max(g["sd"] for g in h["grupos"])                        # sin datos, más duda


def test_adf_update_moves_toward_the_evidence_and_reduces_doubt():
    cr = bayes.Creencias(default=lambda k: (0.0, 1.0))
    x = {"a": 1.0, "b": 1.0}
    for _ in range(30):
        cr.actualizar(x, 1)
    m, v = cr.get("a")
    assert m > 0.3 and v < 1.0
    cr2 = bayes.Creencias(default=lambda k: (0.0, 1.0))
    cr2.actualizar(x, 1, solo={"a"})
    assert cr2.get("b") == (0.0, 1.0) and cr2.get("a")[0] > 0


def test_changing_a_prior_keeps_what_the_data_said():
    """Previa N(0, 1) y datos con precisión 3 y media 0,5 → posterior; cambiar la previa a N(0, 0,5²) da lo mismo
    que combinar la previa nueva con esos datos desde el principio."""
    lam, mu = 3.0, 0.5
    cr = bayes.Creencias({"u": lam * mu / (1 + lam)}, {"u": 1 / (1 + lam)})
    cr.cambiar_previa("u", 1.0, 0.5)
    v = 1 / (4 + lam)
    assert cr.get("u") == pytest.approx((lam * mu * v, v))
    cr.cambiar_previa("u", 0.5, 0.0)
    assert cr.get("u") == (0.0, 0.0)


@pytest.mark.parametrize("tau", [0.0, 0.3])
def test_empirical_bayes_recovers_the_spread_between_clients(tau):
    g = bayes.rng("test-eb", tau)
    eb = bayes.ApetitoEB()
    for i in range(300):
        u = g.gauss(0.0, tau)
        for _ in range(15):
            m = bayes.Phi_inv(g.uniform(0.05, 0.25))
            eb.agregar(f"c{i}", m, 1.0, int(g.random() < bayes.Phi(m + u)))
    est = eb.estimar()
    assert est["ic95"][0] <= tau <= est["ic95"][1] and est["respuestas"] == 4500   # el intervalo cubre la verdad
    assert (est["ic95"][0] > 0) == (tau > 0)                                         # y separa «hay» de «no hay»


# --------------------------------------------------------------------------- entrenamiento
def test_engine_was_trained_on_this_dataset_with_current_rules():
    e = SP["entrenado_con"]
    assert e["sha256_base"] == store().manifest["fuente"]["sha256"] and e["reglas"] == rules.VERSION == "v2.1"
    assert e["respuestas"] == 0 and SP["pesos"] == {} and SP["clientes"] == {}


def test_funnel_and_moment_come_from_the_base():
    e = SP["embudo"]["por_ramo"]
    assert e["SOAT"]["ventas"] == 178 and e["SOAT"]["impactados"] == 1380
    assert e["Hogar"]["campana"] is None and e["Hogar"]["posterior"]["sd"] > 2 * e["Vida"]["posterior"]["sd"]
    m = SP["momento"]
    assert m["total"]["en_ventana"] == 12 and m["total"]["esperados"] == pytest.approx(8.05, abs=0.01)   # igual a M5b
    assert sum(v["pagos"] for v in m["por_ramo"].values()) == 113
    assert not m["por_ramo"]["Desempleo"]["con_datos"] and not m["por_ramo"]["Viajes"]["con_datos"]


def test_priors_keep_the_campaign_average():
    """La conversión de la campaña es el promedio entre clientes en el momento y fuera de él."""
    pv = SP["previas"]
    for ramo in RAMOS:
        pi = SP["momento"]["exposicion"][ramo]["fraccion"]
        b = bayes.Phi(pv["base"][ramo][0])
        en = bayes.Phi(pv["base"][ramo][0] + pv["momento"][ramo][0])
        assert pi * en + (1 - pi) * b == pytest.approx(SP["embudo"]["por_ramo"][ramo]["posterior"]["media"], abs=1e-4), ramo
        media = bayes.Phi(pv["base"][ramo][0] + pv["senal_media"][ramo][0])
        assert media / b == pytest.approx(rules.PRIOR_SENAL_MEDIA_RATIO, abs=1e-4), ramo


def test_prior_predictive_is_plausible_and_scales_with_the_number_of_features():
    ch = SP["previas"]["chequeo"]["p_sorteada"]
    assert 0.001 < ch["p05"] and ch["p95"] < 0.5
    d = len(SP["rasgos"]["vocabulario"])
    tot = math.sqrt(d * (SP["previas"]["global_sd"] ** 2 + SP["previas"]["ramo_sd"] ** 2))
    assert tot == pytest.approx(rules.PRIOR_SD_RASGOS_TOTAL, abs=1e-4)


def test_vocabulary_is_discovered_and_excludes_consequence_and_names():
    voc = SP["rasgos"]["vocabulario"]
    assert "mov:Peajes" in voc and "bolsillo:Vivienda" in voc and "ocupacion:Empleado" in voc
    assert not any("visitas" in k for k in voc)                       # consecuencia de tener seguro (2026-10-20)


def test_training_is_reproducible():
    sys.path.insert(0, str(ROOT / "scripts"))
    import train_motor
    assert train_motor.dump(train_motor.build(None)) == (ROOT / "lulo_app/ml/motor.json").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- invariantes
def test_features_never_read_merchant_names_and_skip_induced_policies():
    s = store()
    for pid in ("sebastian", "valentina", "andres"):
        h = s.history(pid)
        bare = History(client=h.client, deposits=[replace(d, pocket_name=None) for d in h.deposits],
                       external=list(h.external),
                       movements=[replace(m, merchant=None, counterparty=None, channel_label=None) for m in h.movements])
        assert rasgos.crudos(h, CUTOFF, CUTOFF) == rasgos.crudos(bare, CUTOFF, CUTOFF), pid
        a, b = evaluate(pid, Context(mode="lote")), None
        s.histories[pid] = bare
        try:
            b = evaluate(pid, Context(mode="lote"))
        finally:
            s.histories[pid] = h
        assert [(x["ramo"], x["ev"], (x["prob"] or {}).get("p")) for x in a["candidates"]] == \
               [(x["ramo"], x["ev"], (x["prob"] or {}).get("p")) for x in b["candidates"]], pid
    # Sebastián tiene Vida grupo deudor y asistencias (inducidos por el crédito): no cuentan como seguros.
    assert rasgos.crudos(s.history("sebastian"), CUTOFF, CUTOFF)["seguros:n"] == 1          # solo el SOAT


def test_without_responses_features_do_not_move_any_probability():
    r = evaluate("C00002", Context(mode="lote"))
    p = cand(r, "Desempleo")["prob"]
    assert p["rasgos_aprendidos"] == [] and p["rasgos_en_espera"] == len(SP["rasgos"]["vocabulario"])
    assert {s["k"] for s in p["pasos"]} <= {"base", "senal_media", "momento", "afinidad"}


def test_gates_are_the_same_with_both_engines_and_regla_reproduces_v13():
    b = engine.campaign()
    a = engine.campaign(motor="regla")
    ob = {r["client_id"]: r for r in b["rows"]}
    for r in a["rows"]:
        assert r["outcome"] == ob[r["client_id"]]["outcome"]
        assert r["ramo"] == r["ramo_regla"] == ob[r["client_id"]]["ramo_regla"]
    g = b["summary"]["regla"]
    assert g["coinciden"] + g["cambian"] == g["decisiones"] and g["coinciden"] > 0.85 * g["decisiones"]


def test_ev_is_probability_times_commission():
    r = evaluate("C00002", Context(mode="lote"))
    d = r["decision"]
    assert d["ev"] == round(d["prob"]["p"] * d["valor"])
    assert d["ev_contacto"] == round(d["alcance"]["p"] * d["ev"])
    assert r["record"]["p"] == d["prob"]["p"] and r["record"]["motor"] == "bayesiano"


def test_moment_raises_the_probability_right_after_the_event():
    quiet = evaluate("sebastian", Context(mode="lote", as_of=date(2026, 11, 20)))
    assert cand(quiet, "Vida")["momento_dias"] is None                 # la última transferencia pasó hace > 30 días
    now = on_event("sebastian", Event(type="transferencia_fija", amount=450_000),
                   Context(as_of=date(2026, 11, 20)))["evaluation"]
    assert cand(now, "Vida")["momento_dias"] == 0
    assert cand(now, "Vida")["prob"]["p"] > cand(quiet, "Vida")["prob"]["p"]


# --------------------------------------------------------------------------- aprendizaje y exploración
def test_session_responses_teach_the_client_appetite_only():
    d = CUTOFF
    base = evaluate("sebastian", Context(mode="lote"))
    no = evaluate("sebastian", Context(mode="lote", history=[OfferLog(ramo="Vida", date=d, result="rechazada")]))
    si = evaluate("sebastian", Context(mode="lote", history=[OfferLog(ramo="SOAT", date=d, result="aceptada")]))
    assert no["motor"]["sesion"]["posterior"][0] < 0 < si["motor"]["sesion"]["posterior"][0]
    for ramo in ("SOAT", "Viajes"):
        assert cand(no, ramo)["prob"]["p"] < cand(base, ramo)["prob"]["p"] < cand(si, ramo)["prob"]["p"]
    assert engine._poblacion().medias == {}                            # la población no aprende de una sesión


def test_exploration_is_deterministic_disjoint_from_control_and_about_ten_percent():
    ids = store().ids("reto")
    g = [experiment.group(c, "reto") for c in ids]
    assert all(x["policy"] is None for x in g if x["group"] == "control")
    n = sum(1 for x in g if x["policy"] == "explorar")
    assert 40 <= n <= 80
    ctx = Context(mode="lote", policy="explorar")
    a, b = evaluate("C00002", ctx), evaluate("C00002", ctx)
    assert [x["muestra"] for x in a["candidates"]] == [x["muestra"] for x in b["candidates"]]
    assert a["motor"]["politica"] == "explorar"


def test_training_with_responses_learns_and_validates(tmp_path):
    """Con respuestas sembradas (el crédito sube la aceptación de Desempleo), el retador mejora y se promueve."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import train_motor
    s = store()
    g = bayes.rng("test-respuestas")
    rows = []
    for i, cid in enumerate(sorted(s.ids("reto"))):
        c = s.client(cid)
        if not c.consent:
            continue
        for k in range(4):
            p = 0.35 if c.has_credit else 0.04
            rows.append({"cliente_id": cid, "fecha": f"2026-0{6 + k % 4}-15", "ramo": "Desempleo", "canal": "push",
                         "resultado": "aceptada" if g.random() < p else "rechazada"})
    f = tmp_path / "respuestas.csv"
    with open(f, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    m = train_motor.build(f)
    v = m["validacion"]
    assert v["promovido"] and v["logloss_retador"] < v["logloss_campeon"]
    assert m["pesos"]["Desempleo|perfil:credito"][0] > 0.1 and m["clientes"]
    # la verdad sembrada no tiene apetito propio por cliente: Bayes empírico baja la previa de 0,25
    assert v["apetito"]["tau"] < rules.PRIOR_SD_CLIENTE and m["previas"]["cliente_sd"] == v["apetito"]["usado"]
    assert "Bayes empírico" in m["previas"]["origen"]["cliente"]
    assert train_motor.reporte(json.loads(train_motor.dump(m))).startswith("# Motor bayesiano")


# --------------------------------------------------------------------------- laboratorio y API
def test_laboratory_shows_learning_without_harm():
    lab = json.loads((ROOT / "lulo_app/ml/laboratorio.json").read_text(encoding="utf-8"))
    e = lab["escenarios"]
    assert e["señal"]["final"]["motor"] > e["señal"]["final"]["regla"] * 1.05
    assert e["señal"]["calibracion"]["motor"][-1] < e["señal"]["calibracion"]["motor"][0]
    assert e["regla correcta"]["final"]["motor"] > e["regla correcta"]["final"]["regla"] * 0.97     # casi no cuesta
    assert abs(e["ruido"]["final"]["motor"] / e["señal"]["final"]["motor"] - 1) < 0.02            # el ruido no confunde
    for esc in e.values():
        assert esc["final"]["azar"] <= esc["final"]["motor"] <= esc["final"]["oraculo"] * 1.001
    assert "no son resultados" in lab["aviso"]
    # más tipos de datos: la columna nueva entra con peso 0, se aprende y suma frente al motor sin ella
    n = e["dato nuevo"]
    assert n["valor_del_dato"] > 0 and n["final"]["motor_sin_dato"] < n["final"]["motor"] <= n["final"]["oraculo"]
    for k, w in n["pesos"].items():
        if "nuevo:dato" in k:
            assert w["estimado"][0] == 0 and 0 < w["estimado"][-1] <= w["verdad"] * 1.5
    # Bayes empírico: sin diferencias entre clientes, τ̂ = 0; con ellas (verdad 0,20), τ̂ > 0
    assert e["regla correcta"]["apetito"]["estimado"][-1]["motor"]["tau"] == 0
    assert 0.05 < e["señal"]["apetito"]["estimado"][-1]["motor"]["tau"] < 0.3


def test_motor_api_and_campaign_csv():
    c = TestClient(app)
    m = c.get("/api/v3/motor").json()
    assert m["version"] == SP["version"] and m["laboratorio"]["escenarios"] and m["rasgos"]["n"] == len(SP["rasgos"]["vocabulario"])
    head = c.get("/api/v3/campaign.csv").content.decode("utf-8-sig").splitlines()[0].split(";")
    assert {"p", "ev_regla", "ramo_regla", "policy"} <= set(head)
    ev = c.post("/api/v3/clients/sebastian/events",
                json={"event": {"type": "transferencia_fija", "amount": 450000}, "context": {}}).json()
    assert ev["evaluation"]["decision"]["prob"]["p"] > 0


def test_page_keeps_prototype_label_and_guides_the_visitor():
    """La página v3 sigue marcada como prototipo (etiqueta visible y noindex) y trae la bienvenida y el recorrido."""
    html = TestClient(app).get("/").text
    assert "Prototipo académico · datos simulados" in html and 'content="noindex, nofollow"' in html
    assert 'id="welcome"' in html and 'data-tab="tour"' in html and 'data-tab="aprende"' in html
    assert 'data-new="push"' in html and "/static/v3/tour.js" not in html          # los módulos los importa app.js
    v2 = TestClient(app).get("/v2").text
    assert 'id="welcome"' not in v2                                                 # /v2 no se toca


def test_page_form_controls_have_accessible_names():
    """Cada campo y lista del panel tiene nombre para lectores de pantalla (aria-label o <label for>)."""
    import re
    html = TestClient(app).get("/").text
    def con_nombre(campo):
        ident = re.search(r'id="([^"]+)"', campo)
        return "aria-label=" in campo or (ident and f'for="{ident.group(1)}"' in html)
    campos = re.findall(r"<(?:input|select)\b[^>]*>", html)
    assert campos and all(con_nombre(c) for c in campos), [c for c in campos if not con_nombre(c)]


def test_real_data_path_validates_and_trains_outside_the_repo(tmp_path):
    """El camino para datos reales: validar la carpeta, escribir su manifiesto y entrenar sin tocar el repo."""
    import shutil
    import subprocess

    for f in (ROOT / "lulo_app/dataset").glob("*.csv"):
        shutil.copy(f, tmp_path / f.name)
    run = lambda *a: subprocess.run([sys.executable, *a], cwd=ROOT, capture_output=True, text=True)  # noqa: E731
    ok = run("scripts/validar_datos.py", str(tmp_path), "--inicio", "2025-11-01", "--corte", "2026-10-08")
    assert ok.returncode == 0, ok.stderr
    out = run("scripts/train_motor.py", "--datos", str(tmp_path), "--salida", str(tmp_path / "m.json"), "--sin-clientes")
    assert out.returncode == 0, out.stderr
    m = json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))
    assert m["embudo"] == SP["embudo"] and m["momento"] == SP["momento"] and m["clientes"] == {}
    rows = (tmp_path / "clientes.csv").read_text(encoding="utf-8").replace("autoriza_ofertas", "autoriza")
    (tmp_path / "clientes.csv").write_text(rows, encoding="utf-8")
    bad = run("scripts/validar_datos.py", str(tmp_path))
    assert bad.returncode == 1 and "autoriza_ofertas" in bad.stderr
