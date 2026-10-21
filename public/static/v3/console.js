// Consola de Lulo: lo que ve el banco mientras el cliente usa la app. Herramientas, no explicaciones:
//   En vivo   cada decisión del motor con su probabilidad y lo que hizo el cliente; disparar eventos
//   Campaña   el plan de los 600 a una fecha, con el motor o con la regla v1.3, y el año recorrido
//   Piloto    cuántos clientes hacen falta para medir el efecto contra el grupo de control (mismo cálculo que M6)
//   Clientes  buscar en los 600 de la base y abrir la app como cualquiera de ellos
// La usa app.js con un objeto A que expone el estado, el API y las acciones de la app.
import { $, $$, debounce, esc, money, num, store } from "./util.js";
import { pc } from "./aprende.js";

const OUT = {shown: ["Push", "info"], banner: ["Banner", "ban"], control: ["Control", "ctrl"], noconsent: ["Sin autorización", "ctrl"],
  none: ["Nada", "no"], queued: ["En cola", "hold"], weak: ["Señal débil", "no"], ineligible: ["No elegible", "no"], has: ["Ya lo tiene", "no"],
  cooldown: ["En espera", "hold"], external: ["Con otra aseguradora", "no"], optout: ["Sin sugerencias", "ctrl"]};
const RES = {aceptada: ["Aceptó", "ok"], rechazada: ["Rechazó", "no"]};
const FEED = "lulo:ui:feed";
const FECHAS = [[0, "Corte"], [30, "+30 días"], [60, "+60 días"], [90, "+90 días"]];
// Tamaño de muestra por grupo para comparar dos proporciones (bilateral): el mismo de scripts/train_models.py (M6).
const Z = {alpha: 1.959964, 80: 0.841621, 90: 1.281552};
function porGrupo(p, lift, power) {
  const p2 = p * (1 + lift), pbar = (p + p2) / 2;
  const n = (Z.alpha * Math.sqrt(2 * pbar * (1 - pbar)) + Z[power] * Math.sqrt(p * (1 - p) + p2 * (1 - p2))) ** 2;
  return Math.ceil(n / (p2 - p) ** 2);
}
const kpi = (v, l, cls = "") => `<div class="kpi ${cls}"><b>${v}</b><span>${l}</span></div>`;
const bars = (rows, fmt = num) => { const mx = Math.max(1, ...rows.map(r => r[1]));
  return `<div class="cbars">${rows.map(([k, v]) => `<div class="cbar"><span>${esc(k)}</span><i style="--w:${(v / mx * 100).toFixed(1)}%"></i><b>${fmt(v)}</b></div>`).join("")}</div>`; };

export function createConsole(A) {
  let tab = "vivo";
  let feed = store.get(FEED) || [];
  const camp = {dias: 0, motor: "bayesiano", data: null, loading: false, bt: null, btLoading: false};
  const pil = {ramo: "SOAT", lift: 50, power: 80, control: 10, flujo: ""};
  const xq = {q: "", outcome: "", ramo: ""};

  const save = () => store.set(FEED, feed.slice(0, 60));

  /* ---------- en vivo ---------- */
  function record(ev, src) {
    if (!ev) return;
    const d = ev.decision, S = A.S();
    feed.unshift({t: new Date().toLocaleTimeString("es-CO", {hour: "2-digit", minute: "2-digit", hour12: false}), cid: S.cid, who: S.B.client.first,
      src: src || "", outcome: ev.outcome, ramo: d ? d.ramo : (ev.focus || ""), title: d ? d.title : "", p: d && d.prob ? d.prob.p : null,
      ev: d ? d.ev : null, valor: d ? d.valor : null, explora: !!(d && d.explora), resultado: null, optout: false});
    save(); if (tab === "vivo") paint();
  }
  function respond(cid, ramo, resultado, optout = false) {
    const e = feed.find(x => x.cid === cid && x.ramo === ramo && ["shown", "banner"].includes(x.outcome) && !x.resultado);
    if (!e) return;
    e.resultado = resultado; e.optout = optout; save(); if (tab === "vivo") paint();
  }
  function vivoHTML() {
    const shown = feed.filter(x => ["shown", "banner"].includes(x.outcome)), ok = feed.filter(x => x.resultado === "aceptada");
    const gan = ok.reduce((a, x) => a + (x.valor || 0), 0);
    const S = A.S();
    return `<div class="kpis">${kpi(num(shown.length), "ofertas mostradas")}${kpi(num(ok.length), "aceptadas", "lime")}${kpi(shown.length ? pc(ok.length / shown.length, 0) : "—", "tasa de aceptación")}
        ${kpi(money(gan), "comisión a 12 meses")}${kpi(num(feed.filter(x => x.outcome === "control").length), "en control")}${kpi(num(feed.filter(x => x.optout).length), "pidieron no ver más", "harm")}</div>
      <div class="c-sec"><div class="c-h"><b>Decisiones del motor</b>${feed.length ? `<button class="lnk2" data-c="clear">Borrar</button>` : ""}</div>
        ${feed.length ? `<ol class="feed">${feed.slice(0, 30).map(x => { const [l, c] = OUT[x.outcome] || [x.outcome, "no"], r = x.resultado && RES[x.resultado];
          return `<li><time>${x.t}</time><span class="f-m"><b>${esc(x.who)} · ${esc(x.title || x.ramo || "—")}</b><small>${esc(x.src)}${x.p != null ? ` · P(acepta) ${pc(x.p)}` : ""}${x.ev != null ? ` · VE ${money(x.ev)}` : ""}${x.explora ? " · explora" : ""}</small></span>
            <span class="f-t"><span class="tag ${c}">${l}</span>${r ? `<span class="tag ${r[1]}">${x.optout ? "No quiere más" : r[0]}</span>` : ["shown", "banner"].includes(x.outcome) ? `<span class="tag hold">Sin respuesta</span>` : ""}</span></li>`; }).join("")}</ol>`
          : `<p class="c-empty">Todavía no hay decisiones. Usa la app (transfiere, abona, pide un crédito) o dispara un evento.</p>`}</div>
      <div class="c-sec"><div class="c-h"><b>Disparar un evento para ${esc(S.B.client.first)}</b></div>
        <div class="evs">${S.B.events.map(e => `<button data-c-ev="${e.type}"><b>${esc(e.label)}</b><small>${e.ramo ? `→ ${esc(e.ramo)}` : e.type === "abono_bolsillo" ? `→ según el bolsillo` : "→ ningún seguro"} · ${money(e.amount)}</small></button>`).join("")}</div></div>`;
  }

  /* ---------- campaña ---------- */
  async function loadCamp() {
    camp.loading = true; paint();
    try { camp.data = await A.API.campaign(A.addDays(A.META.cutoff, camp.dias), camp.motor); } catch { camp.data = null; A.toast("No se pudo calcular el plan"); }
    camp.loading = false; paint();
  }
  async function runBacktest() {
    camp.btLoading = true; paint();
    try { camp.bt = await A.API.backtest(14); } catch { A.toast("No se pudo recorrer el año"); }
    camp.btLoading = false; paint();
  }
  function campHTML() {
    const C = camp.data, s = C && C.summary;
    const ctrl = `<div class="c-ctrls"><div class="seg" role="group" aria-label="Fecha del plan">${FECHAS.map(([d, l]) => `<button data-c-dias="${d}" aria-pressed="${camp.dias === d}">${l}</button>`).join("")}</div>
      <div class="seg" role="group" aria-label="Cómo se ordenan las ofertas"><button data-c-motor="bayesiano" aria-pressed="${camp.motor === "bayesiano"}">Motor v2</button><button data-c-motor="regla" aria-pressed="${camp.motor === "regla"}">Regla v1.3</button></div></div>`;
    if (!s) return ctrl + `<p class="c-empty">${camp.loading ? "Calculando el plan de los 600 clientes…" : "Elige la fecha para calcular el plan."}</p>`;
    const r = s.regla, ch = s.shown_by_channel;
    return ctrl + `<p class="c-sub">${C.as_of} · datos hasta ${C.data_until} · reglas ${C.rules_version}${camp.loading ? " · recalculando…" : ""}</p>
      <div class="kpis">${kpi(num((ch.shown || 0) + (ch.banner || 0)), `con oferta (${num(ch.shown || 0)} push, ${num(ch.banner || 0)} banner)`, "lime")}${kpi(num(s.control), "en grupo de control")}
        ${kpi(num(s.by_outcome.noconsent || 0), "sin autorización")}${kpi(s.ventas_esperadas.toLocaleString("es-CO", {maximumFractionDigits: 1}), "ventas esperadas*")}${kpi(money(s.comision_esperada), "comisión esperada*")}${kpi(pc(s.p_media), "P(acepta) media")}</div>
      <div class="c-sec"><div class="c-h"><b>Ofertas por seguro</b></div>${bars(Object.entries(s.shown_by_ramo))}</div>
      ${camp.motor === "bayesiano" ? `<div class="c-sec"><div class="c-h"><b>Frente a la regla v1.3</b></div><p class="c-p">${num(r.coinciden)} de ${num(r.decisiones)} decisiones iguales; cambian ${num(r.cambian)} (${num(r.cambian_por_exploracion)} por exploración).</p>
        ${bars(Object.entries(r.cambios).slice(0, 5))}</div>` : ""}
      <div class="c-ctrls"><a class="pbtn lime" href="/api/v3/campaign.csv?as_of=${C.as_of}${camp.motor === "regla" ? "&motor=regla" : ""}" download>Descargar el plan (CSV)</a><button class="pbtn" data-c="bt" ${camp.btLoading ? "disabled" : ""}>${camp.btLoading ? "Recorriendo el año…" : "Recorrer el año (backtest)"}</button></div>
      ${camp.bt ? `<div class="kpis three">${kpi(num(camp.bt.offers), `ofertas en el año (${num(camp.bt.clients_reached)} clientes)`)}${kpi(camp.bt.max_push_30d, "máximo de push a un cliente en 30 días")}${kpi(camp.bt.violations.length, "violaciones de las reglas", camp.bt.violations.length ? "harm" : "lime")}</div>` : ""}
      <p class="c-foot">* Si las probabilidades del motor son correctas: Σ P(la ve) × P(acepta), con la comisión de la base. Base sintética: no son ventas de Lulo.</p>`;
  }

  /* ---------- piloto ---------- */
  // El formulario se pinta una vez; al moverlo solo cambian los resultados (así no se corta el gesto del control).
  function pilotoHTML() {
    const P = A.META.models.piloto;
    return `<div class="c-form">
        <label>Seguro<select data-p="ramo">${Object.keys(P).map(k => `<option ${k === pil.ramo ? "selected" : ""}>${esc(k)}</option>`).join("")}</select></label>
        <label>Aumento a detectar: <b id="pLift">+${pil.lift} %</b><input type="range" min="10" max="100" step="5" value="${pil.lift}" data-p="lift" aria-label="Aumento a detectar en la conversión"></label>
        <label>Potencia<select data-p="power"><option value="80" ${pil.power === 80 ? "selected" : ""}>80 %</option><option value="90" ${pil.power === 90 ? "selected" : ""}>90 %</option></select></label>
        <label>Grupo de control<select data-p="control">${[5, 10, 20, 50].map(c => `<option value="${c}" ${pil.control === c ? "selected" : ""}>${c} %</option>`).join("")}</select></label>
        <label>Clientes por mes que reciben una oferta<input type="number" min="0" step="100" inputmode="numeric" placeholder="por ejemplo, el dato de Lulo" value="${esc(pil.flujo)}" data-p="flujo"></label>
      </div>
      <div id="pRes">${pilotoRes()}</div>`;
  }
  function pilotoRes() {
    const base = A.META.models.piloto[pil.ramo].conversion_base;
    const n = porGrupo(base, pil.lift / 100, pil.power);
    const total = Math.ceil(n / Math.min(pil.control, 100 - pil.control) * 100);
    const flujo = +pil.flujo || 0;
    return `<div class="kpis three">${kpi(num(n), "clientes por grupo", "lime")}${kpi(num(total), `clientes en total con ${pil.control} % de control`)}${kpi(flujo ? `${Math.ceil(total / flujo)}` : "—", flujo ? "meses de piloto" : "escribe el flujo mensual")}</div>
      <p class="c-p">Conversión de partida de ${esc(pil.ramo)}: ${pc(base)} (campaña previa de la base). Para ver un aumento de ${pil.lift} % (de ${pc(base)} a ${pc(base * (1 + pil.lift / 100))}) con α = 5 % y potencia ${pil.power} % hacen falta ${num(n)} clientes en el grupo de control y otros tantos con el motor.</p>
      <p class="c-foot">Prueba de dos proporciones, bilateral; el mismo cálculo del modelo M6 (<code>scripts/train_models.py</code>). Con la base del reto (600 clientes y 10 % de control) no se detecta ningún aumento: el piloto necesita la base del banco.</p>`;
  }

  /* ---------- clientes ---------- */
  let XL = {items: [], total: 0, loading: false};
  async function loadClients() {
    XL.loading = true; paintClients();
    try { const r = await A.API.explorer({...xq, source: "reto", limit: 60}); XL = {items: r.items, total: r.total, loading: false}; }
    catch { XL.loading = false; A.toast("No se pudo cargar la lista"); }
    paintClients();
  }
  const reloadClients = debounce(loadClients, 250);
  function paintClients() { const r = $("#xRes"); if (r && tab === "clientes") r.innerHTML = clientesRes(); else if (tab === "clientes") paint(); }
  function clientesHTML() {
    return `<div class="c-form row">
        <input type="search" placeholder="Busca por id (C00002)" value="${esc(xq.q)}" data-x="q" aria-label="Buscar cliente por id">
        <select data-x="outcome" aria-label="Filtrar por decisión"><option value="">Toda decisión</option>${["shown", "banner", "control", "noconsent", "none"].map(k => `<option value="${k}" ${xq.outcome === k ? "selected" : ""}>${OUT[k][0]}</option>`).join("")}</select>
        <select data-x="ramo" aria-label="Filtrar por seguro"><option value="">Todo seguro</option>${["Desempleo", "Vida", "Viajes", "Mascotas", "Hogar", "SOAT"].map(k => `<option ${xq.ramo === k ? "selected" : ""}>${k}</option>`).join("")}</select></div>
      <div id="xRes">${clientesRes()}</div>`;
  }
  function clientesRes() {
    const S = A.S();
    return `<p class="c-sub">${XL.loading ? "Cargando…" : `${num(XL.total)} clientes de la base · toca uno para ver la app como él o ella`}</p>
      <div class="xl">${XL.items.map(x => { const [l, c] = OUT[x.outcome] || [x.outcome, "no"];
        return `<button class="xr${x.client_id === S.cid ? " on" : ""}" data-client="${x.client_id}"><code>${esc(x.client_id)}</code><span><b>${esc(x.title || x.ramo || "Sin oferta hoy")}</b><small>${esc(x.age_band)} · ${esc(x.occupation)}${x.offerable.length ? ` · ofrecibles: ${esc(x.offerable.join(", "))}` : ""}</small></span><span class="tag ${c}">${l}</span></button>`; }).join("")}</div>`;
  }

  /* ---------- pintar y eventos ---------- */
  const VIEWS = {vivo: vivoHTML, campana: campHTML, piloto: pilotoHTML, clientes: clientesHTML};
  function paint() {
    const el = $("#cBody"); if (!el) return;
    $$("#console [data-ctab]").forEach(b => b.setAttribute("aria-selected", b.dataset.ctab === tab));
    el.innerHTML = VIEWS[tab]();
  }
  function setTab(t) {
    tab = t; paint();
    if (t === "campana" && !camp.data && !camp.loading) loadCamp();
    if (t === "clientes" && !XL.items.length && !XL.loading) loadClients();
  }
  const root = $("#console");
  root.addEventListener("click", e => {
    const t = e.target.closest("[data-ctab]"); if (t) { setTab(t.dataset.ctab); return; }
    const c = e.target.closest("[data-c]");
    if (c) { if (c.dataset.c === "clear") { feed = []; save(); paint(); } else if (c.dataset.c === "bt") runBacktest(); return; }
    const ev = e.target.closest("[data-c-ev]"); if (ev) { A.fireEvent(ev.dataset.cEv); return; }
    const d = e.target.closest("[data-c-dias]"); if (d) { camp.dias = +d.dataset.cDias; loadCamp(); return; }
    const m = e.target.closest("[data-c-motor]"); if (m) { camp.motor = m.dataset.cMotor; loadCamp(); }
  });
  root.addEventListener("input", e => {
    const p = e.target.dataset.p, x = e.target.dataset.x;
    if (p) {
      pil[p] = ["lift", "power", "control"].includes(p) ? +e.target.value : e.target.value;
      $("#pRes").innerHTML = pilotoRes(); $("#pLift").textContent = `+${pil.lift} %`;
    }
    if (x === "q") { xq.q = e.target.value; reloadClients(); }
  });
  root.addEventListener("change", e => { const x = e.target.dataset.x; if (x && x !== "q") { xq[x] = e.target.value; loadClients(); } });
  return {record, respond, paint, setTab, refreshClient() { if (tab === "vivo") paint(); else if (tab === "clientes") paintClients(); }};
}
