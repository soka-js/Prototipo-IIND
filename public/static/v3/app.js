// Orquestador v3: estado, navegación, flujos, llamadas al motor real, recorrido guiado y escenarios rápidos.
// La página es solo la app: lo que explica vive en la guía al lado del teléfono (recorrido y escenarios).
import { $, $$, addDays, clone, debounce, esc, money, num, nowTime, store, wait } from "./util.js";
import { I } from "./icons.js";
import { PLUS_SHEET, ROOTS, SCREENS, cands, chapters, creditCuota, hasRamo, movListHTML, product, quote, skeletonRows } from "./screens.js";
import { NEW, NEW_LIST } from "./content.js";
import { decisionHTML } from "./aprende.js";
import { createTour } from "./tour.js";

const BOOT = JSON.parse($("#bootstrap").textContent);
const META = BOOT.meta;
const PERSONAS = BOOT.personas;
const CACHE = {[`${BOOT.current.client.id}|${BOOT.current.as_of}`]: BOOT.current};
const KEY = "lulo:v3";
const IMG_LOGO = "/static/img/logo-lulo.png";
let S;
let TOUR = null;   // recorrido guiado: se crea al final, antes de boot()

/* =================== API =================== */
async function call(path, body) {
  const r = await fetch(path, body === undefined ? {} : {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  if (!r.ok) { let d = ""; try { d = (await r.json()).detail; } catch { /* sin cuerpo */ } throw new Error(`${path} respondió ${r.status} ${typeof d === "string" ? d : ""}`); }
  return r;
}
const V3 = "/api/v3";
const API = {
  client: (id, asOf) => call(`${V3}/clients/${id}${asOf ? `?as_of=${asOf}` : ""}`).then(r => r.json()),
  explorer: p => call(`${V3}/clients?${new URLSearchParams(p)}`).then(r => r.json()),
  movements: (id, p) => call(`${V3}/clients/${id}/movements?${new URLSearchParams(p)}`).then(r => r.json()),
  movement: (id, rid) => call(`${V3}/clients/${id}/movements/${rid}`).then(r => r.json()),
  event: (id, event, context) => call(`${V3}/clients/${id}/events`, {event, context}).then(r => r.json()),
  evaluate: (id, ctx, focus) => call(`${V3}/clients/${id}/evaluate${focus ? `?focus=${encodeURIComponent(focus)}` : ""}`, ctx).then(r => r.json()),
  year: (id, ctx) => call(`${V3}/clients/${id}/year`, ctx).then(r => r.json()),
  upcoming: (id, ctx) => call(`${V3}/clients/${id}/upcoming`, ctx).then(r => r.json()),
  motor: () => call(`${V3}/motor`).then(r => r.json()),
};

/* =================== estado =================== */
function fresh(B) {
  return {
    cid: B.client.id, B, asOf: B.as_of, screen: "lock", params: {}, stack: [], unlocked: false, pin: 0, xt: "ahorro",
    hide: false, cardFrozen: false, balance: B.balance, sessionRows: [], sessionMovs: [], sessionDeps: [], seq: 0,
    pockets: clone(B.pockets), credit: clone(B.credit), notifs: clone(B.notifications), catalog: B.catalog,
    evaluation: B.evaluation, chapters: B.chapters, upcoming: B.upcoming,
    accepted: [], renewed: [], history: [], log: [], queue: [], shown: null, banner: null, topBannerClosed: false,
    control: null, sugg: true, remind: true, alertDays: 30, consent: B.client.consent,
    known: {}, declined: {}, story: 0, storyOpened: false, storyDone: false, yearLoaded: false,
    offer: null, flow: {}, soat: {owner: "tu", placa: (B.car && B.car.plate || "").replace("-", ""), accept: false},
    detail: null, mq: "", mg: "todos", lastTrace: null, expo: [],
  };
}
const SAVE = ["screen", "unlocked", "xt", "hide", "cardFrozen", "balance", "sessionRows", "sessionMovs", "sessionDeps", "seq", "pockets", "credit",
  "notifs", "accepted", "renewed", "history", "log", "queue", "banner", "control", "sugg", "remind", "alertDays", "consent", "known", "declined",
  "story", "storyOpened", "storyDone", "yearLoaded", "mq", "mg", "evaluation", "chapters", "upcoming", "soat", "topBannerClosed", "expo"];
function loadState(B) {
  const saved = store.get(`${KEY}:state:${B.client.id}:${B.as_of}`);
  S = fresh(B);
  if (saved) for (const k of SAVE) if (k in saved) S[k] = saved[k];
  if (!ROOTS.includes(S.screen)) S.screen = S.unlocked ? "home" : "lock";
}
function snapshot() { const o = {}; for (const k of SAVE) o[k] = S[k]; o.screen = ROOTS.includes(S.screen) ? S.screen : (S.unlocked ? "home" : "lock"); return o; }
const persist = debounce(() => { if (!S) return; store.set(`${KEY}:state:${S.cid}:${S.asOf}`, snapshot()); store.set(`${KEY}:client`, S.cid); }, 200);

/** Contexto que viaja con cada llamada: el motor no guarda estado. */
function ctx(mode = "tiempo_real") {
  return {as_of: S.asOf, mode, consent: S.consent, suggestions: S.sugg, alert_days: S.alertDays, control: S.control,
    accepted: S.accepted, renewed: S.renewed, history: S.history, session_movements: S.sessionMovs, session_deposits: S.sessionDeps,
    window: mode === "tiempo_real" && S.shown ? {ramo: S.shown.ramo, title: S.shown.title} : null, queue: S.queue};
}
const today = () => S.asOf;

/* =================== navegación =================== */
const sc = () => $("#scroll");
const entry = () => ({screen: S.screen, params: S.params, scroll: sc().scrollTop});
function go(screen, params = {}) { closeSheetPlus(); S.stack.push(entry()); S.screen = screen; S.params = params; render("push"); sc().scrollTop = 0; armHistory(); }
function replace(screen, params = S.params) { S.screen = screen; S.params = params; render("fade"); sc().scrollTop = 0; }
function back() {
  if (["processing", "paying", "lock", "yearLoading"].includes(S.screen)) return false;
  if ($("#plusSheet")) { closeSheetPlus(); return true; }
  if (S.screen === "success") { flowDone(); return true; }
  abandonOpen();
  const prev = S.stack.pop();
  if (!prev) {
    if (ROOTS.includes(S.screen)) { if (S.screen !== "home") { tabTo("home"); return true; } return false; }
    S.screen = "home"; S.params = {}; render("pop"); return true;
  }
  S.screen = prev.screen; S.params = prev.params; render("pop"); sc().scrollTop = prev.scroll || 0; return true;
}
function tabTo(t) { closeSheetPlus(); abandonOpen(); S.stack = []; S.screen = t; S.params = {}; render("fade"); sc().scrollTop = 0; onEnterRoot(t); }
function onEnterRoot(t) { if (t === "anio") refreshYear(); if (t === "proteccion") refreshEval(); }
function armHistory() { if (history.state?.lulo !== "trap") history.pushState({lulo: "trap"}, "", location.href); }
addEventListener("popstate", e => { if (e.state?.lulo && S.unlocked && back()) armHistory(); });
addEventListener("hashchange", () => { const r = routeFromHash(location.hash); if (r && location.hash !== hashFor()) gotoTarget(r); });
const HASH = {home: "#/inicio", explora: "#/explora", anio: "#/tu-ano", proteccion: "#/proteccion", alertas: "#/alertas", cuenta: "#/cuenta",
  perfil: "#/perfil", ayuda: "#/ayuda", soatIntro: "#/soat", renew: "#/soat/renovar", bolsillos: "#/bolsillos", credito: "#/credito", card: "#/tarjeta", mapa: "#/cajeros"};
function hashOf(e) {
  if (e.screen === "story") return `#/tu-ano/${chapters(S)[S.story]?.id || ""}`;
  if (e.screen === "offer") return `#/oferta/${encodeURIComponent(S.offer)}`;
  if (e.screen === "mov") return `#/movimientos/${e.params.id}`;
  if (e.screen === "explora") return `#/explora/${S.xt}`;
  return HASH[e.screen] || null;
}
function hashFor() { let h = hashOf(S); for (let i = S.stack.length - 1; !h && i >= 0; i--) h = hashOf(S.stack[i]); return h || "#/inicio"; }
function routeFromHash(h) {
  const p = h.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  if (!p.length) return null;
  const m = {inicio: "home", explora: "explora", "tu-ano": "anio", proteccion: "proteccion", alertas: "alertas", cuenta: "cuenta", movimientos: "cuenta",
    perfil: "perfil", ayuda: "ayuda", soat: "soatIntro", bolsillos: "bolsillos", credito: "credito", tarjeta: "card", cajeros: "mapa"};
  if (p[0] === "tu-ano" && p[1]) return `story:${p[1]}`;
  if (p[0] === "movimientos" && p[1]) return `mov:${p[1]}`;
  if (p[0] === "oferta" && p[1]) return `offer:${p[1]}`;
  if (p[0] === "explora" && p[1]) return `explora:${p[1]}`;
  if (p[0] === "soat" && p[1] === "renovar") return "renew";
  return m[p[0]] || null;
}

/* =================== render =================== */
const STATUS_BG = {lime: ["var(--lime)", "#101500"], navy: ["var(--card)", "#fff"], ink: ["#0E1426", "#fff"], pink: ["var(--pink)", "var(--ink)"]};
const TABS = [["home", "Home", "home"], ["explora", "Explora", "explora"], ["plus", "", "plus"], ["anio", "Tu año", "year"], ["proteccion", "Protección", "protect"]];
function render(anim = "none") {
  const el = sc();
  el.innerHTML = SCREENS[S.screen](S);
  el.classList.remove("anim-push", "anim-pop", "anim-fade");
  if (anim !== "none") { void el.offsetWidth; el.classList.add("anim-" + anim); }
  const th = S.screen === "story" ? chapters(S)[S.story].theme : S.screen === "yearLoading" ? "lime" : null;
  const stb = $(".status"); stb.style.background = th ? STATUS_BG[th][0] : ""; stb.style.color = th ? STATUS_BG[th][1] : "";
  stb.querySelectorAll(".sig i").forEach(x => x.style.background = th ? STATUS_BG[th][1] : "");
  const showTabs = S.unlocked && ROOTS.includes(S.screen);
  const tb = $("#tabbar"); tb.hidden = !showTabs;
  if (showTabs) {
    const sugg = Object.values(cands(S)).some(c => c.status === "ofrecer" && !hasRamo(S, c.ramo)) && S.sugg && S.consent;
    tb.innerHTML = TABS.map(([k, l, ic]) => k === "plus" ? `<button class="tab-plus" data-a="plus" aria-label="Acciones de la cuenta">${I.plus}</button>`
      : `<button class="tab" data-a="tab" data-t="${k}" ${S.screen === k ? 'aria-current="page"' : ""}${k === "anio" ? ' data-new="tab-anio"' : k === "proteccion" ? ' data-new="tab-proteccion"' : ""}>${I[ic]}${l}${k === "proteccion" && sugg ? `<i class="dot"></i>` : ""}</button>`).join("");
  }
  S.sessionRows.forEach(m => m.flash = false);
  MOUNT[S.screen]?.();
  if (document.body.classList.contains("show-new")) tipNew(true);
  const h = S.unlocked && hashFor();
  if (h && location.hash !== h) history.replaceState(history.state, "", h);
  persist();
  if (TOUR) { TOUR.decorate(); TOUR.tick(); }
}
function toast(m) { const t = $("#toast"); t.textContent = m; t.classList.add("show"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), 2400); }
function flashPhone() { const p = $(".phone"); p.classList.remove("flashbox"); void p.offsetWidth; p.classList.add("flashbox"); }
function openSheetPlus() { if ($("#plusSheet")) return; $("#phone").insertAdjacentHTML("beforeend", PLUS_SHEET(S)); }
function closeSheetPlus() { $("#plusSheet")?.remove(); }

/* =================== montaje =================== */
const MC = {};
const movKey = () => `${S.cid}|${S.mg}|${S.mq.trim().toLowerCase()}`;
const MOUNT = {
  cuenta() { loadMovs(); },
  mov() { ensureDetail(); },
  home() {
    const car = $("#carousel"); if (!car) return;
    car.addEventListener("scroll", debounce(() => {
      const i = Math.round(car.scrollLeft / 312); $$(".dots i").forEach((d, j) => d.classList.toggle("on", j === i));
    }, 60));
  },
  yearLoading() {
    const steps = [`Leyendo ${num(S.B.movCount)} movimientos`, "Buscando tus momentos del año", `Armando ${chapters(S).length} capítulos`];
    steps.forEach((t, i) => setTimeout(() => { const s = $("#yrLoadS"); if (s) s.textContent = t; }, i * 480));
    setTimeout(() => { if (S.screen === "yearLoading") { replace("story"); storyOpenedHooks(); } }, 1500);
  },
};
const fold = s => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
function matches(m) {
  if (S.mg === "pendientes") return false;
  if (S.mg !== "todos" && m.group !== S.mg) return false;
  const q = fold(S.mq.trim());
  return !q || fold(`${m.label} ${m.cat_label} ${m.channel}`).includes(q);
}
async function loadMovs() {
  const key = movKey();
  let st = MC[key];
  if (!st) { st = MC[key] = {items: [], total: null, in: null, out: null, loading: false}; if (S.mg === "todos" && !S.mq.trim()) { st.items = S.B.recent.slice(); st.total = S.B.movCount; } }
  paintMovs();
  if (st.loading || (st.total !== null && st.items.length >= st.total && st.in !== null)) return;
  st.loading = true; paintMovs();
  try { const r = await API.movements(S.cid, {q: S.mq.trim(), group: S.mg, offset: st.items.length, limit: 60}); st.items.push(...r.items); st.total = r.total; st.in = r.in; st.out = r.out; }
  catch { toast("No se pudieron cargar los movimientos"); }
  st.loading = false;
  if (S.screen === "cuenta" && movKey() === key) paintMovs();
}
function paintMovs() {
  const st = MC[movKey()], list = $("#movList");
  if (!list || !st) return;
  const sess = S.sessionRows.filter(matches), items = [...sess, ...st.items];
  if (S.mg === "pendientes") list.innerHTML = `<div class="empty-st">Aún no tienes movimientos pendientes.</div>`;
  else if (!items.length) list.innerHTML = st.loading || st.total === null ? skeletonRows(8) : `<div class="empty-st">No encontramos movimientos${S.mq ? ` con «${esc(S.mq)}»` : ""}.</div>`;
  else list.innerHTML = movListHTML(items, today());
  const total = st.total === null ? null : st.total + sess.length;
  const sIn = sess.filter(m => m.amount > 0).reduce((a, m) => a + m.amount, 0), sOut = -sess.filter(m => m.amount < 0).reduce((a, m) => a + m.amount, 0);
  $("#movSum").innerHTML = total === null || S.mg === "pendientes" ? "&nbsp;" : `${num(total)} ${total === 1 ? "movimiento" : "movimientos"}` + (st.in !== null ? ` · <span class="in">+${money(st.in + sIn)}</span> · −${money(st.out + sOut)}` : "");
  $("#movMore").innerHTML = st.loading && items.length ? skeletonRows(3) : (st.total !== null && st.items.length >= st.total && items.length > 8 ? `<div class="end">Esos son todos los movimientos de los últimos 12 meses.</div>` : "");
}
async function ensureDetail() {
  const id = S.params.id;
  if (S.detail && (S.detail.row?.id === id || S.detail.id === id)) return;
  const local = S.sessionRows.find(m => m.id === id);
  if (local) { S.detail = {row: local, signal: local.sig || null, same_count: 0}; render("none"); return; }
  S.detail = {loading: true, id};
  try { const d = await API.movement(S.cid, id); if (S.screen === "mov" && S.params.id === id) { S.detail = d; render("none"); } }
  catch { toast("No se pudo cargar el movimiento"); }
}
sc().addEventListener("scroll", () => { if (S.screen !== "cuenta") return; const el = sc(); if (el.scrollTop + el.clientHeight > el.scrollHeight - 320) loadMovs(); });

/* =================== movimientos de la sesión y registro =================== */
const ICON_CAT = {"Abono recurrente": "income", "Transferencia fija tercero": "send", Transferencia: "send", Aerolineas: "plane", Hoteles: "bed",
  Mascotas: "paw", Peajes: "road", "Desembolso crédito": "coin", "Cuota crédito": "coin", Seguros: "shield"};
const LABEL_CAT = {"Abono recurrente": "Abono de nómina", "Transferencia fija tercero": "Transferencia a tercero", Transferencia: "Transferencia",
  Aerolineas: "Aerolínea", Hoteles: "Hotel", Mascotas: "Tienda de mascotas", Peajes: "Peaje", "Desembolso crédito": "Desembolso Lulo Crédito", "Cuota crédito": "Cuota Lulo Crédito", Seguros: "Seguro"};
const FEEDS = {"Abono recurrente": "Desempleo", "Transferencia fija tercero": "Vida", Peajes: "SOAT", Aerolineas: "Viajes", Hoteles: "Viajes", Mascotas: "Mascotas", "Desembolso crédito": "Pago protegido"};
function addRow(created, label) {
  const id = `s${++S.seq}`;
  let row;
  if (created.kind === "deposit") {
    row = {id, kind: "dep", date: today(), label: label || `Bolsillo ${created.pocket_name || created.pocket_type}`, category: "Bolsillo", cat_label: `Abono a bolsillo · ${created.pocket_type}`,
      icon: "pocket", channel: "Bolsillos", mcc: "", amount: -created.amount, group: "gastos", feeds: {Viajes: "Viajes", Mascotas: "Mascotas", Vivienda: "Hogar"}[created.pocket_type] || null, flash: true};
  } else {
    row = {id, kind: "mov", date: today(), label: label || created.merchant || created.counterparty && `Transferencia a ${created.counterparty}` || LABEL_CAT[created.category] || created.category,
      category: created.category, cat_label: LABEL_CAT[created.category] || created.category, icon: ICON_CAT[created.category] || "dots", channel: created.channel || "Transferencia",
      mcc: "", amount: created.amount, group: created.amount > 0 ? "ingresos" : "gastos", feeds: FEEDS[created.category] || null, flash: true};
  }
  S.sessionRows.unshift(row);
  S.balance += row.amount;
  if (S.screen === "cuenta") paintMovs();
  return row;
}
function addNotif(n) { S.notifs.unshift({id: `n${++S.seq}`, date: today(), time: nowTime().slice(0, 5), unread: true, icon: "shield", ...n}); }
function addLog(ev, offer, res, tipo, ramo) {
  S.log.unshift({t: nowTime(), client: S.B.client.first, ev, offer, res, tipo, ramo: ramo || ""});
  persist();
}
function hist(ramo, result, channel) { S.history.push({ramo, date: today(), result, channel}); }
/** Registro de respuestas (formato de docs/DATOS_REALES.md): cada oferta que el motor mostró y lo que hizo el cliente. */
function expose(d, canal) {
  S.expo.push({cliente_id: S.cid, fecha: today(), ramo: d.ramo, canal, resultado: null, grupo: "tratamiento",
    politica: d.policy || "", p_motor: d.prob ? d.prob.p : "", version_reglas: META.rules_version});
}
function respond(ramo, resultado) {
  const e = [...S.expo].reverse().find(x => x.ramo === ramo && !x.resultado);
  if (e) { e.resultado = resultado; persist(); }
}

/* =================== motor =================== */
let busy = Promise.resolve();
function fire(type, extra = {}, src) { busy = busy.then(() => fireNow(type, extra, src)).catch(e => { console.error(e); toast("El motor no respondió"); }); return busy; }
async function fireNow(type, extra = {}, src) {
  const def = S.B.events.find(e => e.type === type) || {};
  const event = {type, amount: extra.amount || def.amount, merchant: extra.merchant ?? def.merchant ?? null, counterparty: extra.counterparty ?? def.counterparty ?? null,
    pocket_type: extra.pocket_type ?? def.pocket_type ?? null, pocket_name: extra.pocket_name ?? def.pocket_name ?? null};
  const R = await API.event(S.cid, event, ctx());
  if (R.created) {
    if (R.created.kind === "deposit") S.sessionDeps.push({pocket_type: R.created.pocket_type, amount: R.created.amount, pocket_name: R.created.pocket_name, date: R.created.date});
    else S.sessionMovs.push({category: R.created.category, amount: R.created.amount, date: R.created.date, merchant: R.created.merchant, counterparty: R.created.counterparty, channel: "Transferencia"});
    if (!extra.noRow) { const row = addRow(R.created, extra.label); if (R.signal) row.sig = {ramo: R.signal.ramo, name: R.signal.name, headline: R.signal.headline, rule: R.signal.rule, strength: R.signal.strength}; }
  }
  if (R.evaluation) { S.lastTrace = R.evaluation; S.queue = R.evaluation.queue || S.queue; }
  await handleOutcome(R.outcome, R.evaluation && R.evaluation.decision, src || R.label, R.message, R.evaluation);
  refreshEval();
  return R;
}
async function handleOutcome(outcome, d, src, message, ev) {
  const title = d ? d.title : "";
  noteDecision(ev || {outcome, message, label: message, decision: null}, src);
  if (outcome === "shown") { show(d, src); await wait(1480); return; }
  if (outcome === "banner") { setBanner(d, src, ev && ev.channel ? ev.channel.reason : ""); return; }
  const L = {queued: ["En cola: ventana ocupada", "hold"], control: ["Grupo de control: no se muestra", "ctrl"], optout: ["Sugerencias apagadas por el cliente", "ctrl"],
    noconsent: ["Sin autorización de datos", "ctrl"], weak: ["Señal débil", "ctrl"], ineligible: ["No elegible", "ctrl"], has: ["Ya tiene el seguro", "ctrl"],
    cooldown: ["En espera: ofrecido hace poco", "ctrl"], external: ["Lo tiene con otra aseguradora", "ctrl"], none: ["No alimenta ninguna señal", "info"]}[outcome];
  if (outcome === "control" && d) hist(d.ramo, "control", "ninguno");
  addLog(src, title || (ev && ev.focus) || "—", `${L[0]}${message && outcome !== "none" ? ` · ${message}` : ""}`, L[1], d && d.ramo);
}
function show(d, src) {
  S.shown = {...d, src};
  hist(d.ramo, "mostrada", "push");
  expose(d, "push");
  setTimeout(() => {
    const n = $("#notif");
    n.innerHTML = `<span class="ic"><img src="${IMG_LOGO}" alt=""></span><span style="flex:1"><span class="t"><span>Lulo Bank</span><span>ahora</span></span><span class="b"><b>${esc(d.notif.t)}</b>${esc(d.notif.b)}</span></span>`;
    n.classList.add("show"); $("#notifX").classList.add("show");
    setTimeout(() => { if (S.shown && S.shown.ramo === d.ramo && !(TOUR && TOUR.active())) hideNotif(); }, 9000);
    addNotif({t: d.notif.t, b: d.notif.b, go: d.ramo === "SOAT" && ["renovacion", "captura"].includes(d.kind) ? "renew" : `offer:${d.ramo}`, ramo: d.ramo});
    if (["home", "alertas"].includes(S.screen)) render("none");
    addLog(src, d.title, "Mostrada por push", "info", d.ramo);
  }, 1000);
}
function setBanner(d, src, reason) {
  S.banner = {...d, src};
  S.topBannerClosed = false;
  hist(d.ramo, "banner", "banner");
  expose(d, "banner");
  addLog(src, d.title, `Banner pasivo · ${reason || ""}`, "ban", d.ramo);
  if (["home", "alertas"].includes(S.screen)) render("none");
  toast("Oferta como banner (sin push)");
}
function hideNotif() { $("#notif").classList.remove("show"); $("#notifX").classList.remove("show"); }
// Al cerrarse la ventana (el cliente respondió o la descartó), la siguiente oferta de la cola pasa por el motor.
function closeWindow() { S.shown = null; if (S.queue.length) setTimeout(nextWindow, 1200); }
function abandonOpen() { if (S.shown && (S.screen === "offer" || S.screen === "renew") ) { addLog(S.shown.src, S.shown.title, "Cerró sin decidir", "no", S.shown.ramo); closeWindow(); } }
function openDecision(d) {
  hideNotif(); if (!S.unlocked) unlock();
  const n = S.notifs.find(x => x.ramo === d.ramo && x.unread); if (n) n.unread = false;
  if (d.ramo === "SOAT" && ["renovacion", "captura"].includes(d.kind)) openRenew(); else { S.offer = d.ramo; go("offer"); }
}
$("#notif").addEventListener("click", () => { if (S.shown) openDecision(S.shown); });
$("#notifX").addEventListener("click", () => { const d = S.shown; hideNotif(); if (d) { addLog(d.src, d.title, "Descartó la notificación", "no", d.ramo); hist(d.ramo, "rechazada", "ninguno"); respond(d.ramo, "rechazada"); closeWindow(); } });

async function refreshEval() {
  try {
    const [ev, up] = await Promise.all([API.evaluate(S.cid, ctx("lote")), API.upcoming(S.cid, ctx("lote"))]);
    S.evaluation = ev; S.upcoming = up; if (!S.lastTrace) S.lastTrace = ev;
    if (ROOTS.includes(S.screen)) render("none");
    persist();
    if (TOUR) TOUR.tick();
  } catch (e) { console.error(e); }
}
async function refreshYear() {
  try { S.chapters = await API.year(S.cid, ctx("lote")); if (["anio", "story"].includes(S.screen)) render("none"); persist(); }
  catch (e) { console.error(e); }
}

function srcOf() { return S.shown ? S.shown.src : S.banner && S.banner.ramo === S.offer ? S.banner.src : "Entrada directa"; }
function activate(ramo, src) {
  if (!S.accepted.includes(ramo)) S.accepted.push(ramo);
  hist(ramo, "aceptada", "ninguno");
  respond(ramo, "aceptada");
  if (ramo === "Pago protegido" && S.credit) S.credit.protected = true;
  if (S.banner && S.banner.ramo === ramo) S.banner = null;
  addLog(src, product(S, ramo).title, "Aceptó", "ok", ramo);
  refreshEval(); refreshYear();
}
function acceptOffer() { const r = S.offer; activate(r, srcOf()); if (S.shown && S.shown.ramo === r) closeWindow(); back(); toast("Activado. Lo verás en Tu protección"); }
function openRenew() {
  if (S.renewed.includes("SOAT")) { toast("El SOAT ya está al día"); return; }
  if (!S.B.car || S.B.car.days == null) { if (S.screen !== "soatIntro") go("soatIntro"); return; }
  if (S.screen !== "renew") go("renew");
}
function pay() {
  if (S.renewed.includes("SOAT") || S.screen !== "renew") return;
  const Q = quote(S), total = Q ? Q.total : product(S, "SOAT").premium;
  if (S.balance < total) { toast("Saldo insuficiente"); return; }
  const src = S.shown && S.shown.ramo === "SOAT" ? S.shown.src : "Explora › Seguros › Soat";
  replace("paying");
  setTimeout(() => {
    S.renewed.push("SOAT");
    respond("SOAT", "aceptada");
    S.sessionMovs.push({category: "Seguros", amount: -total, date: today(), merchant: "SOAT · Seguros Mundial", channel: "Transferencia"});
    addRow({kind: "movement", category: "Seguros", amount: -total, merchant: `SOAT ${S.B.car?.plate || (S.soat.placa || "").toUpperCase()} · Seguros Mundial`});
    S.notifs = S.notifs.filter(n => n.ramo !== "SOAT");
    addNotif({t: "Tu SOAT quedó al día", b: "Seguros Mundial · póliza enviada a tu correo", go: "proteccion", unread: false});
    hist("SOAT", "aceptada", "ninguno");
    addLog(src, "SOAT", S.B.car && S.B.car.source === "externa" ? "Renovó en Lulo (captura de canal)" : S.B.car ? "Renovó en Lulo" : "Compró en Lulo", "ok", "SOAT");
    if (S.shown && S.shown.ramo === "SOAT") closeWindow();
    S.stack = []; replace("done"); refreshEval(); refreshYear();
  }, 1300);
}
function setKnown(v) { S.known["Pago protegido"] = v; addLog("Tu año en Lulo · Tu crédito", "Pago protegido", `¿Sabía que lo tenía? ${v}`, "val"); render("none"); toast("Gracias por responder"); }
function toggleSugg() { S.sugg = !S.sugg; addLog("Perfil", "Sugerencias de seguros", S.sugg ? "Reactivó sugerencias" : "Desactivó sugerencias", S.sugg ? "info" : "harm"); render("none"); refreshEval(); }
function setConsent(v) { S.consent = v; addLog("Perfil", "Autorización de datos", v ? "Autorizó usar sus movimientos" : "Retiró la autorización de datos", v ? "val" : "harm"); render("none"); refreshEval(); if (v) refreshYear(); }

/* =================== Tu año =================== */
function storyIndex(arg) {
  const list = chapters(S);
  if (arg === undefined || arg === "") return 0;
  if (/^\d+$/.test(arg)) return Math.min(+arg, list.length - 1);
  if (arg === "protect") return Math.max(0, list.findIndex(c => c.protect && c.protect.state === "offer"));
  const i = list.findIndex(c => c.id === arg); return i < 0 ? 0 : i;
}
function openStory(i) {
  if (!S.consent) { if (S.screen !== "anio") tabTo("anio"); toast("Primero autoriza el uso de tus movimientos"); return; }
  if (!chapters(S).length) { toast("No hay capítulos para este cliente"); return; }
  S.story = i;
  if (S.screen === "story") { render("fade"); storySeen(); return; }
  S.stack.push(entry()); armHistory();
  if (!S.yearLoaded) { S.yearLoaded = true; S.screen = "yearLoading"; render("fade"); return; }
  S.screen = "story"; render("push"); sc().scrollTop = 0; storyOpenedHooks();
}
function storyOpenedHooks() {
  if (!S.storyOpened) {
    S.storyOpened = true;
    addLog("Tu año en Lulo", "Resumen anual", "Abrió el resumen", "info");
  }
  storySeen();
}
function storySeen() { if (S.story === chapters(S).length - 1 && !S.storyDone) { S.storyDone = true; addLog("Tu año en Lulo", "Resumen anual", "Completó el resumen", "info"); } }
function storyStep(d) { const n = S.story + d; if (n < 0) return; if (n >= chapters(S).length) { back(); return; } S.story = n; render("fade"); storySeen(); }

/* =================== flujos =================== */
function startFlow(f, base = S.stack.length) { S.flow = {base, amount: 0, ...f}; }
function pickContact(id) {
  const c = S.B.contacts.find(x => x.id === id);
  startFlow({kind: "transfer", contact: c, suggest: [...new Set([c.amount, 50000, 100000, 200000].filter(Boolean))].slice(0, 3)}, S.screen === "transfer" ? S.stack.length - 1 : S.stack.length);
  go("amount");
}
function startCajita(id) { const c = S.pockets.find(x => x.id === id); startFlow({kind: "cajita", cajita: c, suggest: [...new Set([c.history[0]?.a, 100000, 200000].filter(Boolean))].slice(0, 3)}); go("amount"); }
function startCreditReq() { const max = S.credit ? 9000000 : (S.B.client.preapproved || 10000000); startFlow({kind: "desembolso", amount: Math.round(max / 2 / 1e5) * 1e5, cuotas: 18}); go("creditReq"); }
function setAmount(v) {
  const F = S.flow; F.amount = Math.max(0, Math.min(50000000, v));
  const d = $("#amtDisplay"); if (!d) return;
  d.textContent = money(F.amount);
  const over = F.amount > S.balance;
  $("#amtSub").textContent = over ? "Supera tu saldo disponible" : `Disponible ${money(S.balance)}`;
  $("#amtSub").classList.toggle("bad", over);
  $("#amtNext").disabled = !(F.amount > 0) || over;
}
async function confirmFlow() {
  const F = S.flow;
  replace("processing");
  const spec = {transfer: () => F.contact.dependent ? ["transferencia_fija", {counterparty: F.contact.name === "Tercero frecuente" ? null : F.contact.name, label: `Transferencia a ${F.contact.name}`}] : ["transferencia", {counterparty: F.contact.name, label: `Transferencia a ${F.contact.name}`}],
    cajita: () => ["abono_bolsillo", {pocket_type: F.cajita.type, pocket_name: F.cajita.name}], cuota: () => ["cuota", {label: "Pago de cuota Lulo Crédito"}],
    desembolso: () => ["desembolso", {label: "Desembolso Lulo Crédito"}]}[F.kind]();
  const [type, extra] = spec;
  let R;
  try {
    // El evento sale después del comprobante: primero se muestra «Listo», luego el motor decide.
    await wait(900);
    const event = {type, amount: F.amount, merchant: null, counterparty: extra.counterparty || null, pocket_type: extra.pocket_type || null, pocket_name: extra.pocket_name || null};
    R = await API.event(S.cid, event, ctx());
  } catch { toast("No se pudo completar la operación"); replace("confirm"); return; }
  if (R.created.kind === "deposit") S.sessionDeps.push({pocket_type: R.created.pocket_type, amount: R.created.amount, pocket_name: R.created.pocket_name, date: R.created.date});
  else S.sessionMovs.push({category: R.created.category, amount: R.created.amount, date: R.created.date, merchant: R.created.merchant, counterparty: R.created.counterparty, channel: "Transferencia"});
  const row = addRow(R.created, extra.label);
  if (R.signal) row.sig = {ramo: R.signal.ramo, name: R.signal.name, headline: R.signal.headline, rule: R.signal.rule, strength: R.signal.strength};
  const notes = {transfer: () => F.contact.dependent ? "Transferencia fija: alimenta la señal «Dependientes económicos» (Vida)." : "Transferencia ocasional: no alimenta ninguna señal de seguros.",
    cajita: () => R.focus ? `Abono a un bolsillo de ${esc(F.cajita.type)}: alimenta la señal de ${esc(R.focus)}.` : "Ahorro sin una señal de seguros asociada.",
    cuota: () => "Pago de cuota: cuenta en Tu crédito, no dispara una oferta.", desembolso: () => "Desembolso: momento único. El motor revisa si tienes pago protegido."};
  F.result = {ref: `LB${String(Math.floor(Math.random() * 1e8)).padStart(8, "0")}`, note: notes[F.kind](), focus: R.focus};
  if (F.kind === "transfer") addNotif({t: `Transferiste ${money(F.amount)}`, b: `A ${F.contact.name}`, go: `mov:${row.id}`, unread: false, icon: "info"});
  if (F.kind === "cajita") { F.cajita.saved += F.amount; F.cajita.deposits += 1; F.cajita.history.unshift({date: today(), a: F.amount}); }
  if (F.kind === "cuota" && S.credit && S.credit.details) { S.credit.paid += 1; S.credit.remaining = Math.max(0, S.credit.remaining - S.credit.cuota); S.credit.next_date = addDays(S.credit.next_date, 30); }
  if (F.kind === "desembolso") {
    if (!S.credit) S.credit = {name: "Lulo Crédito", details: true, amount: F.amount, cuotas: F.cuotas, cuota: F.cuota, paid: 0, protected: hasRamo(S, "Pago protegido"), rate: "1,79% M.V.", remaining: F.cuotas * F.cuota, next_date: addDays(today(), 30)};
    else if (S.credit.details) { S.credit.amount += F.amount; S.credit.remaining += F.cuotas * F.cuota; }
  }
  replace("success");
  if (R.evaluation) { S.lastTrace = R.evaluation; S.queue = R.evaluation.queue || S.queue; }
  await wait(1200);
  await handleOutcome(R.outcome, R.evaluation && R.evaluation.decision, R.label, R.message, R.evaluation);
  refreshEval();
}
function flowDone() {
  const base = S.flow.base ?? 0, e = S.stack[base];
  S.stack.length = Math.min(S.stack.length, base);
  if (e) { S.screen = e.screen; S.params = e.params; } else { S.screen = "home"; S.params = {}; }
  render("pop");
}

/* =================== ingreso =================== */
function unlock() { S.unlocked = true; S.pin = 0; if (S.screen === "lock") { S.screen = "home"; S.stack = []; S.params = {}; } render("fade"); armHistory(); }
function lock() { abandonOpen(); hideNotif(); closeSheetPlus(); S.unlocked = false; S.pin = 0; S.stack = []; S.screen = "lock"; S.params = {}; render("fade"); }

/* =================== acciones en el teléfono =================== */
$("#phone").addEventListener("click", e => {
  const b = e.target.closest("[data-a]"); if (!b || b.disabled) return;
  const a = b.dataset.a, F = S.flow;
  if (a !== "hide") e.stopPropagation();
  switch (a) {
    case "back": back(); break;
    case "tab": tabTo(b.dataset.t); break;
    case "plus": openSheetPlus(); break;
    case "sheet-close": closeSheetPlus(); break;
    case "sheet-go": closeSheetPlus(); if (b.dataset.s === "creditReq") startCreditReq(); else go(b.dataset.s, b.dataset.p ? {mode: b.dataset.p} : {}); break;
    case "xt": S.xt = b.dataset.t; render("none"); break;
    case "go":
      if (b.dataset.s === "creditReq") startCreditReq();
      else if (b.dataset.s === "renew") openRenew();
      else if (b.dataset.s === "transfer") go("transfer", {mode: b.dataset.p});
      else go(b.dataset.s, b.dataset.p ? {id: b.dataset.p} : {});
      break;
    case "offer": S.offer = b.dataset.r; go("offer"); break;
    case "banner-open": if (e.target.closest('[data-a="top-close"]')) break; if (S.banner) { S.offer = S.banner.ramo; if (S.banner.ramo === "SOAT" && ["renovacion", "captura"].includes(S.banner.kind)) openRenew(); else go("offer"); } break;
    case "top-close": S.topBannerClosed = true; render("none"); break;
    case "key":
      if (S.screen === "lock") {
        if (b.dataset.k === "bio") { unlock(); break; }
        if (b.dataset.k === "del") S.pin = Math.max(0, S.pin - 1); else if (/^\d$/.test(b.dataset.k) && S.pin < 4) S.pin += 1;
        render("none"); if (S.pin >= 4) setTimeout(() => S.screen === "lock" && unlock(), 220);
      } else { const k = b.dataset.k, cur = F.amount || 0; setAmount(k === "del" ? Math.floor(cur / 10) : k === "000" ? cur * 1000 : cur * 10 + +k); }
      break;
    case "unlock": unlock(); break;
    case "logout": lock(); break;
    case "hide": e.stopPropagation(); e.preventDefault(); S.hide = !S.hide; render("none"); break;
    case "freeze": S.cardFrozen = !S.cardFrozen; render("none"); toast(S.cardFrozen ? "Tarjeta congelada" : "Tarjeta activa de nuevo"); break;
    case "toast": toast(b.dataset.m); break;
    case "mov": S.detail = null; go("mov", {id: b.dataset.id}); break;
    case "grp": S.mg = b.dataset.g; $$(".chips [data-g]").forEach(x => x.setAttribute("aria-pressed", x.dataset.g === S.mg)); loadMovs(); persist(); break;
    case "notif": {
      const n = S.notifs.find(x => x.id === b.dataset.id); if (!n) break;
      n.unread = false;
      const [t, arg] = (n.go || "").split(":");
      if (ROOTS.includes(t)) tabTo(t);
      else if (t === "renew") openRenew();
      else if (t === "mov") { S.detail = null; go("mov", {id: arg}); }
      else if (t === "offer") { if (S.shown && S.shown.ramo === arg) openDecision(S.shown); else { S.offer = arg; go("offer"); } }
      else if (t && SCREENS[t]) go(t); else render("none");
      break;
    }
    case "read-all": S.notifs.forEach(n => n.unread = false); render("none"); toast("Todo marcado como leído"); break;
    case "pick-contact": pickContact(b.dataset.id); break;
    case "amt-set": setAmount(+b.dataset.v); break;
    case "amt-next": if (F.amount > 0 && F.amount <= S.balance) go("confirm"); break;
    case "confirm": confirmFlow(); break;
    case "flow-done": flowDone(); break;
    case "cajita-abonar": startCajita(b.dataset.id); break;
    case "pay-cuota": { const c = S.credit && S.credit.cuota || 250000; if (S.balance < c) { toast("Saldo insuficiente"); break; } startFlow({kind: "cuota", amount: c}); go("confirm"); break; }
    case "cr-amt": F.amount = +b.dataset.v; render("none"); break;
    case "cr-n": F.cuotas = +b.dataset.v; render("none"); break;
    case "cr-next": F.cuota = creditCuota(F.amount, F.cuotas); go("confirm"); break;
    case "st-open": openStory(+b.dataset.i); break;
    case "st-next": storyStep(1); break;
    case "st-prev": storyStep(-1); break;
    case "st-close": back(); break;
    case "st-yes": activate(b.dataset.k, "Tu año en Lulo · " + chapters(S)[S.story].name); render("none"); toast("Activado"); break;
    case "st-no": S.declined[b.dataset.k] = true; hist(b.dataset.k, "rechazada", "ninguno"); respond(b.dataset.k, "rechazada"); addLog("Tu año en Lulo · " + chapters(S)[S.story].name, product(S, b.dataset.k).title, "Rechazó: ahora no", "no", b.dataset.k); render("none"); break;
    case "st-soat": { const p = chapters(S)[S.story].protect; if (p && ["renovacion", "captura"].includes(p.kind)) openRenew(); else go("soatIntro"); break; }
    case "st-share": addLog("Tu año en Lulo", "Resumen anual", "Compartió su año", "info"); toast("Imagen lista para compartir"); break;
    case "known": setKnown(b.dataset.v); break;
    case "accept": acceptOffer(); break;
    case "later": { const r = S.offer; hist(r, "rechazada", "ninguno"); respond(r, "rechazada"); addLog(srcOf(), product(S, r).title, "Rechazó: ahora no", "no", r); if (S.shown && S.shown.ramo === r) closeWindow(); if (S.banner && S.banner.ramo === r) S.banner = null; back(); toast("Listo, no te lo mostraremos en 30 días"); refreshEval(); break; }
    case "optout": { const r = S.offer; hist(r, "rechazada", "ninguno"); respond(r, "rechazada"); addLog(srcOf(), product(S, r).title, "Pidió no ver este tipo de sugerencias", "harm", r); if (S.shown && S.shown.ramo === r) closeWindow(); if (S.banner && S.banner.ramo === r) S.banner = null; back(); toast("No verás más sugerencias de este tipo"); refreshEval(); break; }
    case "pay": pay(); break;
    case "postpone": hist("SOAT", "pospuesta", "ninguno"); respond("SOAT", "rechazada"); addLog(S.shown && S.shown.ramo === "SOAT" ? S.shown.src : "Explora › Seguros", "SOAT", "Pospuso la renovación", "no", "SOAT"); if (S.shown && S.shown.ramo === "SOAT") closeWindow(); back(); toast("Te lo recordaremos más adelante"); break;
    case "soat-owner": S.soat.owner = b.dataset.v; render("none"); break;
    case "soat-accept": S.soat.accept = !S.soat.accept; render("none"); { const i = $("#placa"); if (i) { i.focus(); i.setSelectionRange(i.value.length, i.value.length); } } break;
    case "soat-continue": openRenewFromForm(); break;
    case "sugg": toggleSugg(); break;
    case "remind": S.remind = !S.remind; if (!S.remind) addLog("Perfil", "Avisos de vencimiento", "Desactivó avisos", "harm"); render("none"); break;
    case "days": S.alertDays = +b.dataset.d; addLog("Perfil", "Anticipación del aviso", `Prefiere ${S.alertDays} días`, "val"); render("none"); refreshEval(); break;
    case "consent": setConsent(!S.consent); break;
    case "consent-on": setConsent(true); break;
  }
});
function openRenewFromForm() {
  const ok = /^[A-Z]{3}-?\d{2}[0-9A-Z]$/.test((S.soat.placa || "").toUpperCase()) && S.soat.accept;
  if (!ok) return;
  addLog("Explora › Seguros › Soat", "SOAT", `Cotizó la placa ${(S.soat.placa || "").toUpperCase()}`, "info", "SOAT");
  go("renew");
}
const onSearch = debounce(v => { S.mq = v; loadMovs(); persist(); }, 250);
$("#phone").addEventListener("input", e => {
  if (e.target.matches('[data-in="search"]')) onSearch(e.target.value);
  if (e.target.matches('[data-in="placa"]')) {
    S.soat.placa = e.target.value.toUpperCase().replace(/[^A-Z0-9-]/g, "");
    if (e.target.value !== S.soat.placa) e.target.value = S.soat.placa;
    const ok = /^[A-Z]{3}-?\d{2}[0-9A-Z]$/.test(S.soat.placa) && S.soat.accept; const g = $("#soatGo"); if (g) g.disabled = !ok;
  }
});
document.addEventListener("keydown", e => {
  if (e.target.matches("input, textarea, select")) return;
  if (S.screen === "story") { if (e.key === "ArrowRight") storyStep(1); if (e.key === "ArrowLeft") storyStep(-1); if (e.key === "Escape") back(); }
});

/* =================== cola de ofertas =================== */
async function nextWindow() {
  if (S.shown) return;
  const d = S.queue.shift(); if (!d) return;
  try {
    const ev = await API.evaluate(S.cid, {...ctx(), window: null, queue: S.queue}, d.ramo);
    S.lastTrace = ev;
    await handleOutcome(ev.outcome, ev.decision || d, "Cola · siguiente ventana", ev.message, ev);
  } catch { toast("El motor no respondió"); }
}

/* =================== encabezado: personajes, lo nuevo, bienvenida y respuestas =================== */
function renderPersonas() {
  const base = S.B.client.source === "reto" ? `<span class="pchip on" aria-current="true">${esc(S.cid)} · cliente de la base</span>` : "";
  const html = PERSONAS.map(c => `<button class="pchip${c.id === S.cid ? " on" : ""}" data-client="${c.id}" aria-pressed="${c.id === S.cid}"><span class="av" style="background:${c.color}">${esc(c.first[0])}</span>${esc(c.first)}</button>`).join("") + base;
  $("#personas").innerHTML = html; $("#wPersonas").innerHTML = html;
}
function renderChrome() { renderPersonas(); paintGuide(); }
const UI = "lulo:ui";
const TIP = "Nuevo en el prototipo · ";
/** Con «Resaltar lo nuevo», cada elemento nuevo dice qué es al pasar el mouse. */
function tipNew(on) {
  $$("#phone [data-new]").forEach(e => {
    const n = NEW[e.dataset.new];
    if (on && n && !e.title) e.title = `${TIP}${n.t}: ${n.d}`;
    if (!on && e.title.startsWith(TIP)) e.removeAttribute("title");
  });
}
function setHighlight(on) {
  document.body.classList.toggle("show-new", on);
  $("#hlBtn").setAttribute("aria-pressed", on);
  store.set(`${UI}:resaltar`, on);
  tipNew(on);
}
function openWelcome() {
  const w = $("#welcome"); w.hidden = false; document.body.classList.add("welcome-open");
  setTimeout(() => { w.scrollTop = 0; w.querySelector(".w-in").focus({preventScroll: true}); }, 30);
}
function closeWelcome() { $("#welcome").hidden = true; document.body.classList.remove("welcome-open"); store.set(`${UI}:bienvenida`, true); }

const EXPO_COLS = ["cliente_id", "fecha", "ramo", "canal", "resultado", "grupo", "politica", "p_motor", "version_reglas"];
/** Todas las ofertas mostradas en la sesión (todos los clientes que se abrieron) con su resultado; sin respuesta = ignorada. */
function exportResponses() {
  const rows = [], mine = `${KEY}:state:${S.cid}:${S.asOf}`;
  try { Object.keys(sessionStorage).filter(k => k.startsWith(`${KEY}:state:`) && k !== mine).forEach(k => rows.push(...(store.get(k)?.expo || []))); } catch { /* sin almacenamiento */ }
  rows.push(...S.expo);
  if (!rows.length) { toast("Todavía no hay ofertas mostradas"); return; }
  const cell = v => /[",\n]/.test(String(v)) ? `"${String(v).replace(/"/g, '""')}"` : String(v);
  const text = [EXPO_COLS.join(","), ...rows.map(r => EXPO_COLS.map(c => cell(c === "resultado" ? r[c] || "ignorada" : r[c] ?? "")).join(","))].join("\n") + "\n";
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([text], {type: "text/csv;charset=utf-8"}));
  a.download = "respuestas-prototipo.csv"; document.body.appendChild(a); a.click(); a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  toast(`${rows.length} ${rows.length === 1 ? "oferta" : "ofertas"} en el CSV`);
}
$("#csvBtn").addEventListener("click", exportResponses);
$("#hlBtn").addEventListener("click", () => setHighlight(!document.body.classList.contains("show-new")));
$("#welcomeBtn").addEventListener("click", openWelcome);
// En el celular el encabezado no se ve: «Guía» abre los escenarios o el recorrido si están abiertos y, si no, la bienvenida.
$("#guideFab").addEventListener("click", () => { if (GUIDE) openGuide(GUIDE); else openWelcome(); });
$("#welcome").addEventListener("click", e => { if (e.target.id === "welcome") closeWelcome(); });
document.addEventListener("keydown", e => { if (e.key === "Escape" && !$("#welcome").hidden) closeWelcome(); });

/* =================== guía al lado del teléfono: recorrido y escenarios =================== */
// En el escritorio es una tarjeta junto al teléfono; en el celular, una hoja que se abre sobre la app.
const mobile = () => matchMedia("(max-width: 760px)").matches;
let GUIDE = null;          // "tour" | "scen" | null
let LAST = null;           // lo último que decidió el motor en un escenario: {ev, src}
let SCEN_ON = null;        // escenario corriendo
function openGuide(mode, sheet = true) { GUIDE = mode; paintGuide(); if (mobile() && sheet) document.body.classList.add("guide-open"); }
function closeGuide() { GUIDE = null; paintGuide(); document.body.classList.remove("guide-open"); }
function closeGuideSheet() { document.body.classList.remove("guide-open"); }
function paintGuide() {
  const g = $("#guide");
  g.hidden = !GUIDE;
  if (GUIDE === "tour" && TOUR) TOUR.paint();
  else if (GUIDE === "scen") g.innerHTML = scenHTML();
}
function scenHTML() {
  return `<div class="g-head"><b>Escenarios rápidos</b><button class="g-x" data-guide="close" aria-label="Cerrar los escenarios">✕</button></div>
    <p class="g-lead">Un toque y el teléfono muestra el caso; aquí abajo, lo que decidió el motor y por qué.</p>
    <div class="scen">${SCEN.map((s, k) => `<button data-scen="${k}"${SCEN_ON === k ? ' aria-busy="true"' : ""}${SCEN_ON !== null ? " disabled" : ""}><b>${esc(s.t)}</b><span>${esc(s.d)}</span></button>`).join("")}</div>
    ${LAST ? `<div class="g-dec">${decisionHTML(LAST.ev, LAST.src, r => product(S, r).title)}</div>` : ""}
    <p class="g-foot">También puedes usar la app libremente: cada transferencia, abono, crédito o renovación pasa por el mismo motor.</p>`;
}
function noteDecision(ev, src) { LAST = {ev, src}; if (GUIDE === "scen") paintGuide(); }

/* =================== cambio de cliente =================== */
/** Deja a un cliente como recién abierto en la fecha de corte (lo usa el recorrido guiado). */
async function freshClient(id) {
  try { sessionStorage.removeItem(`${KEY}:state:${id}:${META.cutoff}`); } catch { /* sin almacenamiento */ }
  if (S.cid !== id || S.asOf !== META.cutoff) { await switchClient(id, META.cutoff); await wait(400); }
  else {
    Object.keys(MC).forEach(k => delete MC[k]);
    hideNotif(); busy = Promise.resolve();
    loadState(S.B); S.lastTrace = null; render("fade"); renderChrome();
  }
  try { sessionStorage.removeItem(`${KEY}:state:${id}:${META.cutoff}`); } catch { /* sin almacenamiento */ }
  loadState(S.B); S.lastTrace = null;
  unlock();
}
async function switchClient(id, asOf = S.asOf) {
  if (id === S.cid && asOf === S.asOf) return;
  store.set(`${KEY}:state:${S.cid}:${S.asOf}`, snapshot());
  const key = `${id}|${asOf}`;
  let NB = CACHE[key];
  if (!NB) {
    $("#splash").classList.remove("hide");
    try { NB = CACHE[key] = await API.client(id, asOf); } catch { $("#splash").classList.add("hide"); toast("No se pudo cargar el cliente"); return; }
  }
  hideNotif(); closeSheetPlus(); busy = Promise.resolve();
  Object.keys(MC).forEach(k => delete MC[k]);
  const keepUnlocked = id === S.cid;
  loadState(NB); if (keepUnlocked) { S.unlocked = true; S.screen = "home"; } else { S.unlocked = false; S.screen = "lock"; }
  store.set(`${KEY}:client`, id);
  const u = new URL(location.href); u.searchParams.set("cliente", id); if (asOf !== META.cutoff) u.searchParams.set("fecha", asOf); else u.searchParams.delete("fecha"); u.hash = ""; history.replaceState(history.state, "", u);
  render("fade"); renderChrome();
  setTimeout(() => $("#splash").classList.add("hide"), 350);
  flashPhone();
}
document.addEventListener("click", e => {
  if (TOUR && TOUR.onClick(e)) return;
  const w = e.target.closest("[data-w]");
  if (w) {
    const a = w.dataset.w; closeWelcome();
    if (a === "tour") TOUR.start();
    else if (a === "free") { setHighlight(true); if (!S.unlocked) unlock(); gotoTarget("home"); toast("Lo resaltado en lima es nuevo"); }
    else if (a === "scen") openGuide("scen");
    return;
  }
  if (e.target.closest('[data-sheet="close"]')) { closeGuideSheet(); return; }
  const g = e.target.closest("[data-guide]");
  if (g) {
    if (TOUR && TOUR.active()) TOUR.finish(false);
    if (g.dataset.guide === "close") closeGuide(); else openGuide(g.dataset.guide);
    return;
  }
  const sc = e.target.closest("[data-scen]"); if (sc) { runScen(+sc.dataset.scen); return; }
  const c = e.target.closest("[data-client]"); if (c) { if (c.closest("#welcome")) closeWelcome(); switchClient(c.dataset.client); return; }
  const b = e.target.closest("[data-goto]"); if (b) gotoTarget(b.dataset.goto);
});
function gotoTarget(t) {
  if (t === "lock") { lock(); flashPhone(); return; }
  S.unlocked = true; abandonOpen(); closeSheetPlus();
  const [scr, arg] = t.split(":");
  S.stack = []; S.params = {};
  const home = {screen: "home", params: {}, scroll: 0};
  if (scr === "story") { S.screen = "anio"; render("none"); openStory(storyIndex(arg)); flashPhone(); return; }
  if (scr === "offer") { S.stack = [home]; S.offer = arg; S.screen = "offer"; }
  else if (scr === "explora") { S.xt = arg || "ahorro"; S.screen = "explora"; }
  else if (scr === "renew") { S.stack = [home]; if (S.B.car && S.B.car.days != null && !S.renewed.includes("SOAT")) S.screen = "renew"; else S.screen = "soatIntro"; }
  else if (scr === "mov") { S.stack = [home, {screen: "cuenta", params: {}, scroll: 0}]; S.detail = null; S.screen = "mov"; S.params = {id: arg}; }
  else if (["alertas", "cuenta", "perfil", "ayuda", "soatIntro", "bolsillos", "credito", "card", "mapa"].includes(scr)) { S.stack = [home]; S.screen = scr; }
  else S.screen = ROOTS.includes(scr) ? scr : "home";
  render("fade"); sc().scrollTop = 0; armHistory(); flashPhone();
  if (ROOTS.includes(S.screen)) onEnterRoot(S.screen);
}

/* =================== escenarios rápidos =================== */
async function ensureClient(id) { if (S.cid !== id || S.asOf !== META.cutoff) { await switchClient(id, META.cutoff); await wait(450); } if (!S.unlocked) unlock(); }
/** Lo que decide el motor hoy para el cliente abierto (evaluación en lote, recién pedida), para mostrarlo en la guía. */
async function todayDecision(src) { await refreshEval(); if (S.evaluation) noteDecision(S.evaluation, src); }
const SCEN = [
  {t: "Valentina pide un crédito", d: "Sin pago protegido, el desembolso dispara la oferta en ese instante.",
    run: async () => { await ensureClient("valentina"); await fire("desembolso", {amount: 5000000, label: "Desembolso Lulo Crédito"}, "Valentina · desembolso de Lulo Crédito"); }},
  {t: "Andrés: el SOAT vence en 9 días", d: "Gana la ventana aunque el seguro de vida valga más: tiene fecha límite.",
    run: async () => { await ensureClient("andres"); gotoTarget("proteccion"); await todayDecision("Andrés · evaluación de hoy"); }},
  {t: "Grupo de control", d: "El motor detecta y decide, pero no muestra: así se mide el efecto real.",
    run: async () => {
      await ensureClient("andres"); S.control = true;
      try { await fire("transferencia_fija", {}, "Andrés · transferencia a Martha G. (grupo de control)"); }
      finally { S.control = null; persist(); refreshEval(); }   // el control forzado es solo para esta transferencia
    }},
  {t: "Un cliente de la base: C00002", d: "11 abonos de nómina y crédito activo: desempleo, con su probabilidad.",
    run: async () => { await ensureClient("C00002"); unlock(); gotoTarget("proteccion"); await todayDecision("C00002 · evaluación de hoy"); }},
  {t: "Viaje en el tiempo: +30 días", d: "Se abren las ventanas de SOAT de los clientes de la base.",
    run: async () => { await switchClient("C00210", addDays(META.cutoff, 30)); if (!S.unlocked) unlock(); gotoTarget("home"); await todayDecision(`C00210 · ${addDays(META.cutoff, 30)} (+30 días)`); }},
];
async function runScen(k) {
  if (SCEN_ON !== null) return;
  SCEN_ON = k; LAST = null; paintGuide();
  if (mobile()) closeGuideSheet();
  try { await SCEN[k].run(); } catch (err) { console.error(err); toast("No se pudo ejecutar el escenario"); }
  SCEN_ON = null; paintGuide();
  if (mobile()) setTimeout(() => toast("Toca «Guía» para ver qué decidió el motor"), 2600);
}

/* =================== recorrido guiado =================== */
let MOTOR = null;
TOUR = createTour({
  S: () => S, META, NEW_LIST, go, tabTo, gotoTarget, toast,
  openRenew, pay, pickContact, setAmount, confirmFlow,
  openDecision, acceptOffer, refreshEval, setHighlight, motor: () => MOTOR,
  fresh: freshClient, title: r => product(S, r).title,
  openStory: i => openStory(i),
  card: () => GUIDE === "tour" ? $("#guide") : null,
  showTour(sheet) { openGuide("tour", !!sheet); if (!MOTOR) API.motor().then(m => { MOTOR = m; }).catch(() => {}); },
  endTour(next) { if (next) openGuide("scen", false); else closeGuide(); },
});

/* =================== inicio =================== */
async function boot() {
  const url = new URL(location.href);
  const wanted = url.searchParams.get("cliente") || store.get(`${KEY}:client`) || BOOT.current.client.id;
  const asOf = url.searchParams.get("fecha") || META.cutoff;
  let B = CACHE[`${wanted}|${asOf}`];
  if (!B) { try { B = CACHE[`${wanted}|${asOf}`] = await API.client(wanted, asOf); } catch { B = BOOT.current; } }
  loadState(B);
  const route = location.hash ? routeFromHash(location.hash) : null;
  history.replaceState({lulo: "base"}, "", location.href);
  render("none"); renderChrome();
  if (route) gotoTarget(route); else if (S.unlocked) armHistory();
  setTimeout(() => $("#splash").classList.add("hide"), 1000);
  $("#wGrid").innerHTML = NEW_LIST.slice(0, 4).map(([k, t, d], i) => `<div class="w-c"><span class="w-n">${i + 1}</span><b>${esc(t)}</b><span>${esc(d)}</span></div>`).join("");
  if (store.get(`${UI}:resaltar`)) setHighlight(true);
  if (!store.get(`${UI}:bienvenida`) && !url.searchParams.get("cliente") && !route) openWelcome();
}
boot();
