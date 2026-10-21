"""De punta a punta en un navegador real (Playwright): lo que ve quien abre el prototipo.

Se saltan si Playwright o su navegador no están instalados:
    pip install -r requirements-dev.txt && python -m playwright install chromium
"""

import socket
import sys
import threading
import time
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
uvicorn = pytest.importorskip("uvicorn")

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def base():
    """La app en un puerto libre, en un hilo, mientras corren las pruebas del módulo."""
    from lulo_app.main import app

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    t = threading.Thread(target=server.run, daemon=True)
    t.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/"
    server.should_exit = True
    t.join(timeout=5)


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch()
        except Exception as e:   # sin navegador instalado
            pytest.skip(f"Playwright sin Chromium ({e.__class__.__name__}): python -m playwright install chromium")
        yield b
        b.close()


def _page(browser, **kw):
    ctx = browser.new_context(accept_downloads=True, **kw)
    page = ctx.new_page()
    page.set_default_timeout(15000)
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
    return ctx, page, errors


def _step(page) -> str:
    return page.text_content("#guide .tour-n") or ""


def test_first_visit_explains_the_prototype_and_offers_three_paths(base, browser):
    ctx, page, errors = _page(browser, viewport={"width": 1440, "height": 900})
    page.goto(base, wait_until="networkidle")
    w = page.locator("#welcome")
    assert w.is_visible() and "Prototipo académico · datos simulados" in w.inner_text()
    assert page.locator("#wGrid .w-c").count() == 4
    assert {page.get_attribute(f'[data-w="{k}"]', "data-w") for k in ("tour", "free", "scen")} == {"tour", "free", "scen"}
    assert page.locator("#wPersonas [data-client]").count() == 3
    # solo la app: ni panel ni pestañas; la guía está escondida hasta que se pide
    assert page.locator(".panel, [data-tab]").count() == 0 and page.locator("#guide").is_hidden()
    page.click('[data-w="free"]')
    assert page.locator("body.show-new").count() == 1 and page.locator("#welcome").is_hidden()
    assert not errors
    ctx.close()


def test_guided_tour_runs_to_the_end_and_leaves_the_scenarios_open(base, browser, tmp_path):
    ctx, page, errors = _page(browser, viewport={"width": 1440, "height": 900})
    page.goto(base, wait_until="networkidle")
    page.click('[data-w="tour"]')
    page.wait_for_selector("#guide .tour-card")
    seen = set()
    for _ in range(40):
        page.wait_for_selector('#guide .tour-card[aria-busy="false"], #guide .scen')
        n = _step(page)
        if not n:
            break
        seen.add(n)
        if page.locator('#guide [data-tour="auto"]').count():
            page.click('#guide [data-tour="auto"]')
            page.wait_for_function("s => !document.querySelector('#guide [data-tour=\"auto\"]') || "
                                   "(document.querySelector('#guide .tour-n') || {}).textContent !== s", arg=n)
            continue
        last = "Terminar" in page.text_content('#guide [data-tour="next"]')
        page.click('#guide [data-tour="next"]')
        if last:
            break
        page.wait_for_function("s => (document.querySelector('#guide .tour-n') || {}).textContent !== s", arg=n)
    assert len(seen) == 11, sorted(seen)
    page.wait_for_selector("#guide .scen")                       # al terminar quedan los escenarios
    # el recorrido aceptó Vida por push: queda en el CSV con el formato de datos reales
    with page.expect_download() as dl:
        page.click("#csvBtn")
    f = tmp_path / "respuestas.csv"
    dl.value.save_as(f)
    text = f.read_text(encoding="utf-8")
    assert text.splitlines()[0] == "cliente_id,fecha,ramo,canal,resultado,grupo,politica,p_motor,version_reglas"
    assert "sebastian,2026-10-08,Vida,push,aceptada,tratamiento," in text
    sys.path.insert(0, str(ROOT / "scripts"))
    import train_motor
    rows = train_motor.cargar_respuestas(f)                      # el entrenamiento lo lee tal cual
    assert any(r["ramo"] == "Vida" and r["resultado"] == "aceptada" for r in rows)
    assert not errors
    ctx.close()


def test_automatic_tour_is_the_prototype_explaining_itself(base, browser, tmp_path):
    """Recorrido automático como un video: un cursor usa la app de verdad, con subtítulos y globos; se pausa, se
    cambia de capítulo y termina solo (?ritmo=0.1 lo acelera para la prueba)."""
    ctx, page, errors = _page(browser, viewport={"width": 1440, "height": 900})
    page.goto(base + "?ritmo=0.1", wait_until="networkidle")
    page.click('[data-w="auto"]')
    page.wait_for_selector("body.filming #fSubs:not(:empty)")
    assert page.locator(".f-tag").is_visible()                    # la etiqueta del prototipo sigue a la vista
    page.click('[data-f="toggle"]')                               # pausa: el subtítulo no cambia
    sub = page.inner_text("#fSubs")
    page.wait_for_timeout(2000)
    assert page.inner_text("#fSubs") == sub and page.locator("#film.paused").count() == 1
    page.click('[data-f="toggle"]')
    page.wait_for_selector(".f-end", timeout=150000)              # llega solo al final, con los clics del cursor
    assert page.locator("#fChaps button.done").count() == 11
    page.click('.f-end [data-f="scen"]')                          # al salir, los escenarios rápidos
    page.wait_for_selector("#guide .scen")
    assert page.locator("body.filming").count() == 0
    with page.expect_download() as dl:                            # el cursor aceptó Vida en la app: queda en el CSV
        page.click("#csvBtn")
    f = tmp_path / "respuestas.csv"
    dl.value.save_as(f)
    assert "sebastian,2026-10-08,Vida,push,aceptada,tratamiento," in f.read_text(encoding="utf-8")
    # desde el recorrido paso a paso se puede pasar a la película y volver
    page.click('header [data-tour="start"]')
    page.wait_for_selector('#guide .tour-card[aria-busy="false"]')
    page.click("#guide [data-film]")
    page.wait_for_selector("body.filming")
    page.click('[data-f="manual"]')
    page.wait_for_selector("#guide .tour-card")
    assert page.locator("body.filming").count() == 0
    assert not errors
    ctx.close()


def test_scenarios_say_what_the_engine_decided(base, browser):
    ctx, page, errors = _page(browser, viewport={"width": 1440, "height": 900})
    page.goto(base + "?cliente=andres", wait_until="networkidle")    # con cliente en la URL no sale la bienvenida
    page.click('[data-guide="scen"]')
    page.click('#guide [data-scen="2"]')                             # grupo de control
    page.wait_for_selector("#guide .g-dec")
    assert "grupo de control" in page.inner_text("#guide .g-dec")
    page.wait_for_selector('#guide [data-scen="1"]:not([disabled])')
    page.click('#guide [data-scen="1"]')                             # Andrés: el SOAT gana por fecha límite
    page.wait_for_function("() => (document.querySelector('#guide .g-dec') || {}).innerText?.includes('evaluación de hoy')")
    dec = page.inner_text("#guide .g-dec")
    assert dec.startswith("Andrés") and "SOAT" in dec and "grupo de control" not in dec
    assert not errors
    ctx.close()


def test_phone_shows_only_the_app_and_the_guide_opens_as_a_sheet(base, browser):
    ctx, page, errors = _page(browser, viewport={"width": 390, "height": 844}, is_mobile=True, has_touch=True)
    page.goto(base, wait_until="networkidle")
    assert page.evaluate("document.documentElement.scrollWidth - document.documentElement.clientWidth") == 0
    assert page.locator("#guideFab").is_hidden()                     # escondido mientras está la bienvenida
    page.click('[data-w="tour"]')
    page.wait_for_selector("#coach:not([hidden])")
    page.click('#coach [data-tour="more"]')
    page.wait_for_selector("body.guide-open")
    page.click('#guide [data-sheet="close"]')
    page.wait_for_function("() => !document.body.classList.contains('guide-open')")
    page.click('#coach [data-tour="stop"]')
    page.wait_for_function("() => !document.body.classList.contains('touring')")
    assert page.locator("#guideFab").is_visible()
    page.click("#guideFab")                                         # sin guía abierta, «Guía» lleva a la bienvenida
    assert page.locator("#welcome").is_visible()
    assert not errors
    ctx.close()


def test_client_version_v2_still_loads(base, browser):
    ctx, page, errors = _page(browser, viewport={"width": 1440, "height": 900})
    page.goto(base + "v2", wait_until="networkidle")
    assert page.locator("#welcome").count() == 0 and not errors
    ctx.close()


def test_lulo_console_tracks_decisions_plans_the_campaign_and_sizes_the_pilot(base, browser):
    ctx, page, errors = _page(browser, viewport={"width": 1440, "height": 1000})
    page.goto(base + "?cliente=sebastian", wait_until="networkidle")
    # en vivo: un evento disparado desde la consola queda con su decisión y su probabilidad
    page.click('#console [data-c-ev="transferencia_fija"]')
    page.wait_for_selector("#console .feed li")
    li = page.inner_text("#console .feed li")
    assert "Sebastián · Seguro de vida" in li and "P(acepta)" in li and "Push" in li
    # campaña: el plan de los 600 con el motor y con la regla v1.3 (mismas compuertas)
    page.click('#console [data-ctab="campana"]')
    page.wait_for_selector("#console .kpi")
    assert "402" in page.inner_text("#console .kpis") and "Frente a la regla v1.3" in page.inner_text("#cBody")
    page.click('#console [data-c-motor="regla"]')
    page.wait_for_function("() => document.querySelector('[data-c-motor=\"regla\"]').getAttribute('aria-pressed') === 'true' && !document.querySelector('#cBody').innerText.includes('recalculando')")
    assert "402" in page.inner_text("#console .kpis") and "Frente a la regla v1.3" not in page.inner_text("#cBody")
    # piloto: el mismo cálculo que M6 (510 por grupo para +50 % en el SOAT)
    page.click('#console [data-ctab="piloto"]')
    assert page.inner_text("#pRes .kpi b") == "510"
    page.fill('#console [data-p="lift"]', "100")
    assert page.inner_text("#pRes .kpi b") == "147"
    # clientes: buscar en la base y abrir la app como ese cliente
    page.click('#console [data-ctab="clientes"]')
    page.fill('#console [data-x="q"]', "C00002")
    page.wait_for_selector('#console .xr[data-client="C00002"]')
    page.click('#console .xr[data-client="C00002"]')
    page.wait_for_selector('#personas .pchip.on >> text=C00002')
    assert not errors
    ctx.close()
