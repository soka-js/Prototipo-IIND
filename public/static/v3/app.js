// Orquestador v3: estado, navegación, flujos, llamadas al motor real, panel y demo guiada.
import { $, $$, addDays, clone, debounce, esc, money, num, nowTime, pct, store, strip, wait } from "./util.js";
import { I } from "./icons.js";
import { PLUS_SHEET, ROOTS, SCREENS, cands, chapters, creditCuota, hasRamo, movListHTML, product, quote, skeletonRows } from "./screens.js";
import { NOW, buildAccs } from "./content.js";

const BOOT = JSON.parse($("#bootstrap").textContent);
const META = BOOT.meta;
const PERSONAS = BOOT.personas;
const CACHE = {[`${BOOT.current.client.id}|${BOOT.current.as_of}`]: BOOT.current};
const KEY = "lulo:v3";
const IMG_LOGO = "/static/img/logo-lulo.png";
let S;

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
  campaign: asOf => call(`${V3}/campaign?as_of=${asOf}`).then(r => r.json()),
  backtest: every => call(`${V3}/backtest?every=${every}`).then(r => r.json()),
  csv: log => call("/api/report/csv", log).then(r => r.blob()),
};
function apiStatus(state, html) { const el = $("#apiStatus"); if (!el) return; el.className = "api-status " + state; el.querySelector("span").innerHTML = html; }

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
    detail: null, mq: "", mg: "todos", lastTrace: null,
  };
}
const SAVE = ["screen", "unlocked", "xt", "hide", "cardFrozen", "balance", "sessionRows", "sessionMovs", "sessionDeps", "seq", "pockets", "credit",
  "notifs", "accepted", "renewed", "history", "log", "queue", "banner", "control", "sugg", "remind", "alertDays", "consent", "known", "declined",
  "story", "storyOpened", "storyDone", "yearLoaded", "mq", "mg", "evaluation", "chapters", "upcoming", "soat", "topBannerClosed"];
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
      : `<button class="tab" data-a="tab" data-t="${k}" ${S.screen === k ? 'aria-current="page"' : ""}>${I[ic]}${l}${k === "proteccion" && sugg ? `<i class="dot"></i>` : ""}</button>`).join("");
  }
  S.sessionRows.forEach(m => m.flash = false);
  MOUNT[S.screen]?.();
  updateNow();
  const h = S.unlocked && hashFor();
  if (h && location.hash !== h) history.replaceState(history.state, "", h);
  persist();
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
  if (["ok", "no", "harm", "info", "val", "ban"].includes(tipo)) lightStep(3);
  renderMotor(); persist();
}
function hist(ramo, result, channel) { S.history.push({ramo, date: today(), result, channel}); }

/* =================== motor =================== */
let chainTimer = [];
function lightStep(i) { const el = $(`.step[data-step="${i}"]`); if (!el) return; el.classList.add("on"); setTimeout(() => el.classList.remove("on"), 1400); }
function runChain(upTo, done) {
  chainTimer.forEach(clearTimeout); chainTimer = [];
  $$(".step").forEach(s => s.classList.remove("on"));
  for (let i = 0; i <= upTo; i++) chainTimer.push(setTimeout(() => lightStep(i), i * 360));
  chainTimer.push(setTimeout(done || (() => {}), upTo * 360 + 300));
}
function msg(h) { const m = $("#chainMsg"); if (m) m.innerHTML = h; }
let busy = Promise.resolve();
function fire(type, extra = {}, src) { busy = busy.then(() => fireNow(type, extra, src)).catch(e => { console.error(e); toast("El motor no respondió"); }); return busy; }
async function fireNow(type, extra = {}, src) {
  const def = S.B.events.find(e => e.type === type) || {};
  const event = {type, amount: extra.amount || def.amount, merchant: extra.merchant ?? def.merchant ?? null, counterparty: extra.counterparty ?? def.counterparty ?? null,
    pocket_type: extra.pocket_type ?? def.pocket_type ?? null, pocket_name: extra.pocket_name ?? def.pocket_name ?? null};
  runChain(0);
  const t0 = performance.now();
  let R;
  try { R = await API.event(S.cid, event, ctx()); apiStatus("ok", `<b>Motor v3 conectado</b> · reglas ${META.rules_version} · última decisión en ${Math.round(performance.now() - t0)} ms`); }
  catch (e) { apiStatus("err", "<b>El motor no respondió.</b> " + esc(e.message)); msg("<b>Error:</b> no se pudo consultar el motor."); throw e; }
  if (R.created) {
    if (R.created.kind === "deposit") S.sessionDeps.push({pocket_type: R.created.pocket_type, amount: R.created.amount, pocket_name: R.created.pocket_name, date: R.created.date});
    else S.sessionMovs.push({category: R.created.category, amount: R.created.amount, date: R.created.date, merchant: R.created.merchant, counterparty: R.created.counterparty, channel: "Transferencia"});
    if (!extra.noRow) { const row = addRow(R.created, extra.label); if (R.signal) row.sig = {ramo: R.signal.ramo, name: R.signal.name, headline: R.signal.headline, rule: R.signal.rule, strength: R.signal.strength}; }
  }
  if (R.evaluation) { S.lastTrace = R.evaluation; S.queue = R.evaluation.queue || S.queue; }
  const sg = $(`.sig[data-sig="${R.focus}"]`); if (sg) { sg.classList.remove("flash"); void sg.offsetWidth; sg.classList.add("flash"); }
  await handleOutcome(R.outcome, R.evaluation && R.evaluation.decision, src || R.label, R.message, R.evaluation);
  refreshEval();
  return R;
}
async function handleOutcome(outcome, d, src, message, ev) {
  const title = d ? d.title : "";
  if (outcome === "shown") { show(d, src); await wait(3 * 360 + 400); return; }
  if (outcome === "banner") { runChain(2); setBanner(d, src, ev && ev.channel ? ev.channel.reason : ""); return; }
  runChain(outcome === "noconsent" ? 0 : 1);
  msg(`<b>${esc(ev ? ev.label : outcome)}:</b> ${esc(message || "")}`);
  const L = {queued: ["En cola: ventana ocupada", "hold"], control: ["Grupo de control: no se muestra", "ctrl"], optout: ["Sugerencias apagadas por el cliente", "ctrl"],
    noconsent: ["Sin autorización de datos", "ctrl"], weak: ["Señal débil", "ctrl"], ineligible: ["No elegible", "ctrl"], has: ["Ya tiene el seguro", "ctrl"],
    cooldown: ["En espera: ofrecido hace poco", "ctrl"], external: ["Lo tiene con otra aseguradora", "ctrl"], none: ["No alimenta ninguna señal", "info"]}[outcome];
  if (outcome === "control" && d) hist(d.ramo, "control", "ninguno");
  addLog(src, title || (ev && ev.focus) || "—", `${L[0]}${message && outcome !== "none" ? ` · ${message}` : ""}`, L[1], d && d.ramo);
  renderMotor();
}
function show(d, src) {
  S.shown = {...d, src};
  hist(d.ramo, "mostrada", "push");
  msg(`<b>Se muestra por push:</b> ${esc(d.title)}. ${d.deadline ? "Tiene fecha límite." : `Valor esperado ${money(d.ev || 0)}.`} Mira el teléfono.`);
  runChain(2, () => {
    const n = $("#notif");
    n.innerHTML = `<span class="ic"><img src="${IMG_LOGO}" alt=""></span><span style="flex:1"><span class="t"><span>Lulo Bank</span><span>ahora</span></span><span class="b"><b>${esc(d.notif.t)}</b>${esc(d.notif.b)}</span></span>`;
    n.classList.add("show"); $("#notifX").classList.add("show");
    setTimeout(() => { if (S.shown && S.shown.ramo === d.ramo) hideNotif(); }, 9000);
    addNotif({t: d.notif.t, b: d.notif.b, go: d.ramo === "SOAT" && ["renovacion", "captura"].includes(d.kind) ? "renew" : `offer:${d.ramo}`, ramo: d.ramo});
    if (["home", "alertas"].includes(S.screen)) render("none");
    addLog(src, d.title, "Mostrada por push", "info", d.ramo);
  });
  renderMotor();
}
function setBanner(d, src, reason) {
  S.banner = {...d, src};
  S.topBannerClosed = false;
  hist(d.ramo, "banner", "banner");
  msg(`<b>Banner pasivo:</b> ${esc(d.title)} aparece en Home y en Alertas, sin notificación. ${esc(reason || "")}`);
  addLog(src, d.title, `Banner pasivo · ${reason || ""}`, "ban", d.ramo);
  if (["home", "alertas"].includes(S.screen)) render("none");
  toast("Oferta como banner (sin push)");
}
function hideNotif() { $("#notif").classList.remove("show"); $("#notifX").classList.remove("show"); }
function closeWindow() { S.shown = null; renderMotor(); }
function abandonOpen() { if (S.shown && (S.screen === "offer" || S.screen === "renew") ) { addLog(S.shown.src, S.shown.title, "Cerró sin decidir", "no", S.shown.ramo); closeWindow(); } }
function openDecision(d) {
  hideNotif(); if (!S.unlocked) unlock();
  const n = S.notifs.find(x => x.ramo === d.ramo && x.unread); if (n) n.unread = false;
  if (d.ramo === "SOAT" && ["renovacion", "captura"].includes(d.kind)) openRenew(); else { S.offer = d.ramo; go("offer"); }
}
$("#notif").addEventListener("click", () => { if (S.shown) openDecision(S.shown); });
$("#notifX").addEventListener("click", () => { const d = S.shown; hideNotif(); if (d) { addLog(d.src, d.title, "Descartó la notificación", "no", d.ramo); hist(d.ramo, "rechazada", "ninguno"); closeWindow(); } });

async function refreshEval() {
  try {
    const [ev, up] = await Promise.all([API.evaluate(S.cid, ctx("lote")), API.upcoming(S.cid, ctx("lote"))]);
    S.evaluation = ev; S.upcoming = up; if (!S.lastTrace) S.lastTrace = ev;
    if (S.screen === "proteccion" || S.screen === "explora") render("none"); else if (ROOTS.includes(S.screen)) render("none");
    renderMotor(); persist();
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
    msg(`<b>Tu año en Lulo:</b> el backend leyó ${num(S.B.movCount)} movimientos y armó ${chapters(S).length} capítulos. Mira el teléfono.`);
    runChain(2); addLog("Tu año en Lulo", "Resumen anual", "Abrió el resumen", "info");
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
    case "st-no": S.declined[b.dataset.k] = true; hist(b.dataset.k, "rechazada", "ninguno"); addLog("Tu año en Lulo · " + chapters(S)[S.story].name, product(S, b.dataset.k).title, "Rechazó: ahora no", "no", b.dataset.k); render("none"); break;
    case "st-soat": { const p = chapters(S)[S.story].protect; if (p && ["renovacion", "captura"].includes(p.kind)) openRenew(); else go("soatIntro"); break; }
    case "st-share": addLog("Tu año en Lulo", "Resumen anual", "Compartió su año", "info"); toast("Imagen lista para compartir"); break;
    case "known": setKnown(b.dataset.v); break;
    case "accept": acceptOffer(); break;
    case "later": { const r = S.offer; hist(r, "rechazada", "ninguno"); addLog(srcOf(), product(S, r).title, "Rechazó: ahora no", "no", r); if (S.shown && S.shown.ramo === r) closeWindow(); if (S.banner && S.banner.ramo === r) S.banner = null; back(); toast("Listo, no te lo mostraremos en 30 días"); refreshEval(); break; }
    case "optout": { const r = S.offer; hist(r, "rechazada", "ninguno"); addLog(srcOf(), product(S, r).title, "Pidió no ver este tipo de sugerencias", "harm", r); if (S.shown && S.shown.ramo === r) closeWindow(); if (S.banner && S.banner.ramo === r) S.banner = null; back(); toast("No verás más sugerencias de este tipo"); refreshEval(); break; }
    case "pay": pay(); break;
    case "postpone": hist("SOAT", "pospuesta", "ninguno"); addLog(S.shown && S.shown.ramo === "SOAT" ? S.shown.src : "Explora › Seguros", "SOAT", "Pospuso la renovación", "no", "SOAT"); if (S.shown && S.shown.ramo === "SOAT") closeWindow(); back(); toast("Te lo recordaremos más adelante"); break;
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

/* =================== panel =================== */
const OUT_TAG = {shown: ["Push", "info"], banner: ["Banner", "ban"], control: ["Control", "ctrl"], noconsent: ["Sin autorización", "ctrl"], none: ["Nada", "no"], queued: ["Cola", "hold"]};
const LABEL = {ok: "Acepta", no: "Rechaza", hold: "Cola", ctrl: "Sin contacto", harm: "No daño", info: "Contacto", val: "Validación", ban: "Banner"};
function personasHTML() {
  return PERSONAS.map(c => `<button class="cl${c.id === S.cid ? " on" : ""}" data-client="${c.id}" aria-pressed="${c.id === S.cid}"><span class="av" style="background:${c.color};color:var(--ink)">${esc(c.first[0])}</span><span class="cl-t"><b>${esc(c.first)}</b><span>${esc(c.tags.slice(0, 2).join(" · "))}</span></span></button>`).join("");
}
let XQ = {q: "", outcome: "", ramo: "", source: "reto"};
async function renderExplorer() {
  const box = $("#xlist"); if (!box) return;
  box.innerHTML = `<span class="empty">Cargando…</span>`;
  try {
    const r = await API.explorer({...XQ, limit: 120});
    $("#xcount").textContent = `${r.total} de ${META.clients.reto + META.clients.persona} clientes`;
    box.innerHTML = r.items.map(x => { const [l, t] = OUT_TAG[x.outcome] || [x.outcome, "no"];
      return `<button class="xrow${x.client_id === S.cid ? " on" : ""}" data-client="${x.client_id}"><span><code>${esc(x.client_id)}</code><small>${esc(x.age_band)} · ${esc(x.occupation)}</small></span><span>${x.ramo ? `<b>${esc(x.title || x.ramo)}</b>` : `<span style="color:#AFB8CC">${esc(x.message || "—").slice(0, 60)}</span>`}<small>${x.offerable.length ? `Ofrecibles: ${x.offerable.join(", ")}` : x.consent ? "Sin ofertas hoy" : "No autoriza ofertas"}</small></span><span class="tag ${t}">${l}</span></button>`; }).join("") || `<span class="empty">Ningún cliente con esos filtros.</span>`;
  } catch { box.innerHTML = `<span class="empty">No se pudo cargar el explorador.</span>`; }
}
function whoHTML() {
  const c = S.B.client, u = c.usage;
  return `<div class="who"><span class="av" style="background:${c.color};color:var(--ink)">${esc(c.first[0])}</span><span class="grow"><b>${esc(c.name)} ${c.source === "reto" ? `<span class="tag ctrl">base del reto</span>` : `<span class="tag val">personaje</span>`}</b><span>${esc(c.summary)}</span>
    <span>Autoriza ofertas: ${c.consent ? "sí" : "no"} · Uso de la app (30 días): ${u.sessions_30d} sesiones, ${u.notifs_sent_30d} notificaciones (${u.opened_30d} abiertas), latencia «${esc(u.event_latency)}»${u.assumed ? " · supuesto" : ""}</span></span></div>`;
}
function renderClientTab() {
  $("#personas").innerHTML = personasHTML();
  $("#who").innerHTML = whoHTML();
  const offs = [0, 2, 30, 60, 90];
  $("#timetravel").innerHTML = offs.map(d => { const iso = addDays(META.cutoff, d); return `<button data-asof="${iso}" aria-pressed="${S.asOf === iso}">${d === 0 ? "Corte · " : `+${d} días · `}${iso.slice(5)}</button>`; }).join("");
}
function gatesHTML(ev) {
  if (!ev) return `<span class="empty">Dispara un evento o usa la app.</span>`;
  return `<div class="gates">${ev.steps.map(s => `<div class="gate"><span class="${s.ok ? "ok" : "no"}">${s.ok ? "✓" : "✗"}</span><b>${esc(s.step)}</b><span>${esc(s.detail)}</span></div>`).join("")}</div>`;
}
function candTable(ev) {
  if (!ev || !ev.candidates || !ev.candidates.length) return "";
  const top = ev.decision && ev.decision.ramo;
  const ST = {ofrecer: "ofrecer", has: "ya tiene", weak: "débil", none: "sin señal", ineligible: "no elegible", cooldown: "en espera", external: "externo"};
  return `<div class="tbl-w"><table class="ctable"><thead><tr><th>Ramo</th><th>Estado</th><th>Fuerza</th><th>VE</th><th>Por qué</th></tr></thead><tbody>${ev.candidates.map(c => `<tr class="${c.ramo === top ? "win" : ""}"><td><b>${esc(c.ramo)}</b>${c.deadline ? " ⏱" : ""}</td><td><span class="st-k ${c.status}">${ST[c.status]}</span></td><td>${c.strength}</td><td class="num">${c.ev != null ? money(c.ev) : "—"}</td><td>${esc(c.status === "ofrecer" ? c.signal.headline : c.reason)}</td></tr>`).join("")}</tbody></table></div>`;
}
function signalsHTML(ev) {
  const sig = ev && ev.signals ? Object.values(ev.signals) : [];
  const tag = {fuerte: "ok", media: "hold", "débil": "no", ninguna: "no"};
  return sig.map(s => `<details class="sig" data-sig="${esc(s.ramo)}"><summary><span class="sig-n">${esc(s.ramo)} · ${esc(s.name)}</span><span class="tag ${tag[s.strength]}">${s.strength}</span><span class="sig-h">${esc(s.headline)}</span></summary>
    <div class="sig-b"><ul>${s.evidence.map(x => `<li>${esc(x)}</li>`).join("")}</ul><div class="sig-r"><b>Regla:</b> ${esc(s.rule)}</div><div class="sig-r"><b>Tipo:</b> ${esc(s.kind)}</div></div></details>`).join("") || `<span class="empty">Sin autorización: el motor no lee movimientos.</span>`;
}
function renderMotor() {
  if (!S || !$("#metrics")) return;
  const L = S.log;
  const m = [[L.filter(l => l.res === "Mostrada por push").length, "Push mostrados", "lime"], [L.filter(l => l.tipo === "ban").length, "Banners pasivos"], [L.filter(l => l.tipo === "ok").length, "Aceptadas o renovadas"], [L.filter(l => l.tipo === "harm").length, "Señales de daño", "harm"]];
  $("#metrics").innerHTML = m.map(([v, l, c]) => `<div class="metric ${c || ""}"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("");
  $("#queue").innerHTML = S.queue.length ? S.queue.map(q => `<span class="qitem"><b>${q.deadline ? "⏱" : money(q.ev || 0)}</b> ${esc(q.title)}</span>`).join("") : `<span class="empty">${S.shown ? "Ventana ocupada: " + esc(S.shown.title) + ". Cola vacía." : "Ventana libre. Cola vacía."}</span>`;
  $("#nextWin").disabled = !S.queue.length;
  $("#ctrlBtn").setAttribute("aria-pressed", S.control === true);
  $("#log").innerHTML = L.length ? L.map(l => `<div class="log-row"><time>${l.t}</time><span class="e"><b>${esc(l.offer)}</b><br>${esc(l.ev)} · ${esc(l.res)}</span><span class="tag ${l.tipo}">${LABEL[l.tipo]}</span></div>`).join("") : `<span class="empty">Todavía no hay respuestas. Es el paso que hoy no existe en Lulo Bank.</span>`;
  const ev = S.lastTrace || S.evaluation;
  $("#trace").innerHTML = gatesHTML(ev) + candTable(ev);
  $("#signals").innerHTML = signalsHTML(S.evaluation);
  $("#events").innerHTML = S.B.events.map(e => `<button class="ev" data-ev="${e.type}"><span class="n">${esc(e.label)}</span><span class="h">${e.ramo ? `→ ${esc(e.ramo)}` : e.type === "abono_bolsillo" ? `→ según el bolsillo (${esc(e.pocket_type)})` : "→ ningún ramo"} · ${money(e.amount)}</span></button>`).join("");
  const dl = $("#demoLast"); if (dl) dl.innerHTML = L.length ? `<b>Último registro · ${esc(L[0].client)}</b><br>${esc(L[0].offer)}: ${esc(L[0].res)}` : `<b>Último registro</b><br>Todavía no hay respuestas.`;
}
let CAMP = null, BT = null;
async function renderCampaign() {
  const box = $("#campaign"); if (!box) return;
  box.innerHTML = `<span class="empty">Calculando el plan de los 600 clientes…</span>`;
  try { CAMP = await API.campaign(S.asOf); } catch { box.innerHTML = `<span class="empty">No se pudo calcular el plan.</span>`; return; }
  const s = CAMP.summary, mx = Math.max(...Object.values(s.by_outcome), 1), mr = Math.max(...Object.values(s.shown_by_ramo), 1);
  const OL = {shown: "Push", banner: "Banner pasivo", noconsent: "Sin autorización", none: "Nada que ofrecer", control: "Grupo de control"};
  box.innerHTML = `<p class="lead" style="margin:0">Fecha ${CAMP.as_of} · datos hasta ${CAMP.data_until} · reglas ${CAMP.rules_version}</p>
    <div class="kpis"><div class="metric lime"><div class="v">${(s.shown_by_channel.shown || 0) + (s.shown_by_channel.banner || 0)}</div><div class="l">clientes con oferta</div></div><div class="metric"><div class="v">${s.control}</div><div class="l">en grupo de control</div></div><div class="metric"><div class="v">${money(s.ev_total)}</div><div class="l">valor esperado (hipótesis)</div></div></div>
    <h4 style="margin-top:6px">Decisión por cliente</h4><div class="hbars">${Object.entries(s.by_outcome).map(([k, v]) => `<div class="hbar"><span>${OL[k] || k}</span><span class="tr"><i class="${k === "banner" ? "b2" : ""}" style="width:${v / mx * 100}%"></i></span><span>${v}</span></div>`).join("")}</div>
    <h4>Ofertas por ramo</h4><div class="hbars">${Object.entries(s.shown_by_ramo).map(([k, v]) => `<div class="hbar"><span>${esc(k)}</span><span class="tr"><i style="width:${v / mr * 100}%"></i></span><span>${v}</span></div>`).join("")}</div>
    <div class="box">Banner en vez de push por: ${Object.entries(s.reasons_banner).map(([k, v]) => `${esc(k)} (${v})`).join(", ") || "—"}.</div>
    <div class="ctrls"><a class="pbtn lime" href="${V3}/campaign.csv?as_of=${CAMP.as_of}" download>Descargar plan (CSV)</a></div>`;
}
async function runBacktest() {
  const box = $("#backtest"); if (!box) return;
  box.innerHTML = `<span class="empty">Recorriendo el año cada 14 días… (unos segundos)</span>`;
  try { BT = await API.backtest(14); } catch { box.innerHTML = `<span class="empty">No se pudo correr el backtest.</span>`; return; }
  const months = Object.entries(BT.by_month), mx = Math.max(...months.map(([, c]) => (c.shown || 0) + (c.banner || 0)), 1);
  box.innerHTML = `<div class="kpis"><div class="metric lime"><div class="v">${num(BT.offers)}</div><div class="l">ofertas (${num(BT.push)} push, ${num(BT.banner)} banner)</div></div><div class="metric"><div class="v">${BT.max_push_30d}</div><div class="l">máx. push a un cliente en 30 días</div></div><div class="metric ${BT.violations.length ? "harm" : "lime"}"><div class="v">${BT.violations.length}</div><div class="l">violaciones de las invariantes</div></div></div>
    <div class="hbars">${months.map(([m, c]) => `<div class="hbar"><span>${m}</span><span class="tr"><i style="width:${((c.shown || 0) + (c.banner || 0)) / mx * 100}%"></i></span><span>${(c.shown || 0) + (c.banner || 0)}</span></div>`).join("")}</div>
    <div class="box">${num(BT.evaluations)} evaluaciones de ${BT.start} a ${BT.end}; ${BT.clients_reached} clientes alcanzados; ${num(BT.control)} decisiones en control. No simula aceptaciones: la base no trae resultados por cliente.</div>`;
}
function renderData() {
  const d = META.dataset, chk = d.chequeos;
  $("#dataQ").innerHTML = `<div class="box"><b>${esc(d.fuente.archivo)}</b> · sha256 ${esc(d.fuente.sha256.slice(0, 16))}… · ${esc(d.uso)}. ${esc(d.restriccion)}</div>
    ${`<div class="tbl-w"><table class="tbl"><thead><tr><th>Tabla</th><th>Filas</th></tr></thead><tbody>${Object.entries(d.filas).map(([k, v]) => `<tr><td>${k}</td><td class="num">${num(v)}</td></tr>`).join("")}</tbody></table></div>`}
    <div class="tbl-w"><table class="tbl"><thead><tr><th>Pestaña</th><th>Chequeo</th><th></th><th>Detalle</th></tr></thead><tbody>${chk.map(c => `<tr><td>${esc(c.pestana)}</td><td>${esc(c.chequeo)}</td><td><span class="chk ${c.estado}">${c.estado}</span></td><td>${esc(c.detalle)}</td></tr>`).join("")}</tbody></table></div>`;
  $("#dataCat").innerHTML = `<div class="tbl-w"><table class="tbl"><thead><tr><th>Ramo</th><th>Prima</th><th>Comisión 12 m</th><th>Conv.</th><th>VE fuerte</th><th>Edad</th><th>Origen</th></tr></thead><tbody>${META.catalog.map(p => `<tr><td><b>${esc(p.ramo)}</b></td><td>${esc(p.price)}</td><td class="num">${p.commission_12m ? money(p.commission_12m) : "n/d"}</td><td class="num">${p.prior ? pct(p.prior) : "n/d"}</td><td class="num">${p.ev_fuerte ? money(p.ev_fuerte) : "n/d"}</td><td>${esc(p.age)}</td><td>${esc(p.prior_source)}</td></tr>`).join("")}</tbody></table></div>`;
  const R = META.rules;
  const keys = ["VERSION", "APPROVED_ON", "STRENGTH_MULT", "DESEMPLEO_MIN_STREAK", "VIDA_MIN_MONTHS", "VIAJES_PURCHASE_DAYS", "VIAJES_POCKET_MIN", "MASCOTAS_SPEND_MIN", "HOGAR_POCKET_MIN", "SOAT_TOLLS_MEDIA", "SOAT_TOLLS_FUERTE", "SOAT_REMINDER_DAYS", "MIN_DAYS_BETWEEN_PUSH", "DEADLINE_FIRST", "COOLDOWN_DAYS", "FATIGUE_MIN_IGNORED", "CONTROL_PCT", "EXCLUDE_OPEN_AGE_BAND"];
  $("#dataRules").innerHTML = `<div class="tbl-w"><table class="tbl"><tbody>${keys.map(k => `<tr><td><code>${k}</code></td><td>${esc(typeof R[k] === "object" ? JSON.stringify(R[k]) : String(R[k]))}</td></tr>`).join("")}</tbody></table></div>
    <div class="box">${Object.entries(R.CHANGELOG).map(([v, t]) => `<b>${v}</b>: ${esc(t)}`).join("<br>")}</div>`;
}
function renderAccs() {
  const open = new Set($$("#accs details[open]").map(d => d.id).filter(Boolean));
  $("#accs").innerHTML = buildAccs(S, META).map(a => a.g ? `<div class="grp-t">${a.g}</div>` :
    `<details class="acc" id="${a.id}"${(open.size ? open.has(a.id) : a.open) ? " open" : ""}><summary><span class="s-k${a.kp ? " pk" : ""}">${a.k}</span><span class="s-t">${a.t}</span><span class="s-d">${a.d}</span></summary><div class="acc-b">${a.b}</div></details>`).join("");
}
function renderAllPanel() { renderClientTab(); renderMotor(); renderAccs(); renderDemo(); if (!$("#view-camp").hidden) renderCampaign(); }
function updateNow() {
  const N = NOW[S.screen]; if (!N) return;
  let name = N.n, what = N.what;
  if (S.screen === "story") { const c = chapters(S)[S.story]; name += `: ${c.name} (${S.story + 1} de ${chapters(S).length})`; what = c.spec; }
  if (S.screen === "offer" && S.offer) name += ": " + product(S, S.offer).title;
  $("#nowName").textContent = name;
  $("#nowWho").textContent = S.B.client.name;
  $("#nowBody").innerHTML = `<span class="idea-tag">${N.tag}</span><div>${what}</div><h5>Qué puedes hacer aquí</h5><ul>${N.how.map(h => `<li>${h}</li>`).join("")}</ul><h5>Qué valida o mide</h5><div>${N.val}</div>`;
}
function setTab(t) {
  $$(".ptabs button").forEach(b => b.setAttribute("aria-selected", b.dataset.tab === t));
  $$(".pview").forEach(v => v.hidden = v.id !== "view-" + t);
  if (t === "camp" && !CAMP) renderCampaign();
  if (t === "datos") renderData();
  if (t === "cliente") renderExplorer();
}
$(".ptabs").addEventListener("click", e => { const b = e.target.closest("[data-tab]"); if (b) setTab(b.dataset.tab); });
$("#openAll").addEventListener("click", () => $$("#accs details").forEach(d => d.open = true));
$("#closeAll").addEventListener("click", () => $$("#accs details").forEach(d => d.open = false));
$("#events").addEventListener("click", e => { const b = e.target.closest("[data-ev]"); if (b) { if (!S.unlocked) unlock(); fire(b.dataset.ev, {}, "Panel · " + (S.B.events.find(x => x.type === b.dataset.ev) || {}).label); } });
$("#nextWin").addEventListener("click", nextWindow);
async function nextWindow() {
  if (S.shown) { hideNotif(); addLog(S.shown.src, S.shown.title, "Ventana cerrada sin respuesta", "no", S.shown.ramo); closeWindow(); }
  const d = S.queue.shift(); if (!d) return;
  try {
    const ev = await API.evaluate(S.cid, {...ctx(), window: null, queue: S.queue}, d.ramo);
    S.lastTrace = ev;
    await handleOutcome(ev.outcome, ev.decision || d, "Cola · siguiente ventana", ev.message, ev);
  } catch { toast("El motor no respondió"); }
  renderMotor();
}
$("#ctrlBtn").addEventListener("click", () => { S.control = S.control === true ? null : true; renderMotor(); persist(); toast(S.control ? "Cliente en grupo de control" : "Asignación normal (hash o personaje)"); });
$("#csvBtn").addEventListener("click", async () => {
  if (!S.log.length) { toast("El registro está vacío"); return; }
  try { const blob = await API.csv(S.log.slice().reverse()); const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `registro-respuestas-${S.cid}.csv`; document.body.appendChild(a); a.click(); a.remove(); setTimeout(() => URL.revokeObjectURL(a.href), 1000); }
  catch { toast("No se pudo generar el CSV"); }
});
$("#btBtn").addEventListener("click", runBacktest);
$("#campBtn").addEventListener("click", renderCampaign);
const xfilter = debounce(() => renderExplorer(), 250);
$("#xq").addEventListener("input", e => { XQ.q = e.target.value; xfilter(); });
$("#xout").addEventListener("change", e => { XQ.outcome = e.target.value; renderExplorer(); });
$("#xramo").addEventListener("change", e => { XQ.ramo = e.target.value; renderExplorer(); });
$("#xsrc").addEventListener("change", e => { XQ.source = e.target.value; renderExplorer(); });
$("#timetravel").addEventListener("click", e => { const b = e.target.closest("[data-asof]"); if (b) switchClient(S.cid, b.dataset.asof); });
function resetAll() {
  try { Object.keys(sessionStorage).filter(k => k.startsWith(KEY)).forEach(k => sessionStorage.removeItem(k)); } catch { /* sin almacenamiento */ }
  Object.keys(MC).forEach(k => delete MC[k]);
  hideNotif(); busy = Promise.resolve(); chainTimer.forEach(clearTimeout);
  loadState(S.B); S.unlocked = true; S.screen = "home"; S.lastTrace = null;
  demoDone.clear(); msg("Dispara un evento o usa la app para ver cómo decide el motor.");
  render("fade"); renderAllPanel(); toast("Demo reiniciada");
}
$("#resetBtn").addEventListener("click", resetAll); $("#resetBtn2").addEventListener("click", resetAll);

async function switchClient(id, asOf = S.asOf) {
  if (id === S.cid && asOf === S.asOf) return;
  store.set(`${KEY}:state:${S.cid}:${S.asOf}`, snapshot());
  const key = `${id}|${asOf}`;
  let NB = CACHE[key];
  if (!NB) {
    $("#splash").classList.remove("hide");
    try { NB = CACHE[key] = await API.client(id, asOf); } catch { $("#splash").classList.add("hide"); toast("No se pudo cargar el cliente"); return; }
  }
  hideNotif(); closeSheetPlus(); busy = Promise.resolve(); chainTimer.forEach(clearTimeout);
  Object.keys(MC).forEach(k => delete MC[k]);
  const keepUnlocked = id === S.cid;
  loadState(NB); if (keepUnlocked) { S.unlocked = true; S.screen = "home"; } else { S.unlocked = false; S.screen = "lock"; }
  store.set(`${KEY}:client`, id);
  const u = new URL(location.href); u.searchParams.set("cliente", id); if (asOf !== META.cutoff) u.searchParams.set("fecha", asOf); else u.searchParams.delete("fecha"); u.hash = ""; history.replaceState(history.state, "", u);
  msg(`Cliente: <b>${esc(NB.client.name)}</b> · fecha ${asOf}. Dispara un evento o usa la app.`);
  render("fade"); renderAllPanel(); if (!$("#view-cliente").hidden) renderExplorer();
  CAMP = null; if (!$("#view-camp").hidden) renderCampaign();
  setTimeout(() => $("#splash").classList.add("hide"), 350);
  flashPhone();
}
document.addEventListener("click", e => {
  const c = e.target.closest("[data-client]");
  if (c) { switchClient(c.dataset.client); closeSheet(); return; }
  const b = e.target.closest("[data-goto]"); if (!b) return;
  gotoTarget(b.dataset.goto);
  if (b.dataset.acc) { setTab("func"); const d = document.getElementById(b.dataset.acc); if (d) { d.open = true; d.scrollIntoView({behavior: "smooth", block: "start"}); } }
});
function gotoTarget(t) {
  if (t === "motor") { setTab("motor"); return; }
  if (t === "lock") { lock(); flashPhone(); closeSheet(); return; }
  S.unlocked = true; abandonOpen(); closeSheetPlus();
  const [scr, arg] = t.split(":");
  S.stack = []; S.params = {};
  const home = {screen: "home", params: {}, scroll: 0};
  if (scr === "story") { S.screen = "anio"; render("none"); openStory(storyIndex(arg)); flashPhone(); closeSheet(); return; }
  if (scr === "offer") { S.stack = [home]; S.offer = arg; S.screen = "offer"; }
  else if (scr === "explora") { S.xt = arg || "ahorro"; S.screen = "explora"; }
  else if (scr === "renew") { S.stack = [home]; if (S.B.car && S.B.car.days != null && !S.renewed.includes("SOAT")) S.screen = "renew"; else S.screen = "soatIntro"; }
  else if (scr === "mov") { S.stack = [home, {screen: "cuenta", params: {}, scroll: 0}]; S.detail = null; S.screen = "mov"; S.params = {id: arg}; }
  else if (["alertas", "cuenta", "perfil", "ayuda", "soatIntro", "bolsillos", "credito", "card", "mapa"].includes(scr)) { S.stack = [home]; S.screen = scr; }
  else S.screen = ROOTS.includes(scr) ? scr : "home";
  render("fade"); sc().scrollTop = 0; armHistory(); flashPhone(); closeSheet();
  if (ROOTS.includes(S.screen)) onEnterRoot(S.screen);
}

/* =================== panel en el celular =================== */
const mobile = () => matchMedia("(max-width: 760px)").matches;
function closeSheet() { document.body.classList.remove("sheet-open"); }
$("#panelFab").addEventListener("click", () => document.body.classList.toggle("sheet-open"));
$("#sheetClose").addEventListener("click", closeSheet);

/* =================== demo guiada =================== */
const waitFor = async (fn, ms = 5000) => { const t0 = Date.now(); while (!fn() && Date.now() - t0 < ms) await wait(60); };
async function ensureClient(id) { if (S.cid !== id || S.asOf !== META.cutoff) { await switchClient(id, META.cutoff); await wait(450); } if (!S.unlocked) unlock(); }
async function inStory(id) { gotoTarget(`story:${id}`); await waitFor(() => S.screen === "story"); await wait(500); }
const DEMO = [
  {k: "Contexto", t: "Arranca como Sebastián", d: "Home con la estructura de la app real: carrusel, Bolsillos Flex y mapa de cajeros, más el aviso del SOAT.", run: async () => { await ensureClient("sebastian"); gotoTarget("home"); }},
  {k: "Look real", t: "Explora › Seguros", d: "Los cuatro seguros que hoy muestra Lulo y debajo los ramos de la base, marcados «Para ti» por el motor.", run: async () => { await ensureClient("sebastian"); gotoTarget("explora:seguros"); }},
  {k: "Futuro", t: "Renueva el SOAT con el flujo real", d: "Vence en 27 días: renovación con Seguros Mundial y pago desde la Lulo Cuenta.", run: async () => { await ensureClient("sebastian"); if (S.renewed.includes("SOAT")) { toast("El SOAT ya estaba renovado"); return; } gotoTarget("renew"); await wait(700); pay(); await wait(1500); }},
  {k: "Pasado", t: "Abre Tu año: «te faltan 3 abonos»", d: "Sebastián tiene 3 nóminas en Lulo y la regla pide 6: el seguro de desempleo queda agendado, no se ofrece.", run: async () => { await ensureClient("sebastian"); await refreshYear(); await inStory("ingreso"); }},
  {k: "Pasado", t: "Responde la validación del crédito", d: "«No sabía que tenía pago protegido» queda en el registro.", run: async () => { await ensureClient("sebastian"); await inStory("credito"); if (!S.known["Pago protegido"]) setKnown("No"); }},
  {k: "Presente", t: "Transfiere a Laura", d: "Una acción real: transferencia fija → señal de dependientes → Vida por push.", run: async () => {
    await ensureClient("sebastian"); gotoTarget("home"); await wait(400); go("transfer", {mode: "enviar"}); await wait(600); pickContact("laura"); await wait(500);
    setAmount(450000); await wait(600); go("confirm"); await wait(600); await confirmFlow(); }},
  {k: "Prioridad", t: "Abona a «Viajes» con la ventana ocupada", d: "La oferta de Vida sigue abierta: la de viaje espera en cola.", run: async () => { await ensureClient("sebastian"); if (!S.shown) toast("Primero muestra una oferta (paso anterior)"); await fire("abono_bolsillo", {pocket_type: "Viajes", pocket_name: "Viajes", amount: 300000}, "Abono al bolsillo Viajes"); }},
  {k: "Presente", t: "Abre la notificación y activa", d: "«Por qué lo ves» sale de su evidencia. Al activar, aparece en Tu protección.", run: async () => {
    await ensureClient("sebastian"); if (S.shown) { openDecision(S.shown); await wait(1100); acceptOffer(); } else toast("No hay una oferta abierta"); }},
  {k: "Espaciado", t: "Siguiente ventana: va como banner", d: "Ya hubo un push hoy: la oferta en cola se muestra como banner pasivo (7 días entre push, reglas v1.1).", run: async () => { await ensureClient("sebastian"); if (S.queue.length) await nextWindow(); else await fire("compra_aerolinea", {merchant: "Avianca · BOG–CTG", amount: 1200000}); }},
  {k: "Control", t: "Grupo de control", d: "El evento se detecta y se registra, pero no se muestra: así se mide el efecto real.", run: async () => { await ensureClient("andres"); S.control = true; renderMotor(); await fire("transferencia_fija", {}, "Transferencia a Martha G."); S.control = null; renderMotor(); }},
  {k: "Urgencia", t: "Andrés: el SOAT a 9 días gana", d: "Vida tiene más valor esperado, pero el SOAT tiene fecha límite (v1.1).", run: async () => { await ensureClient("andres"); gotoTarget("proteccion"); setTab("motor"); S.lastTrace = S.evaluation; renderMotor(); }},
  {k: "Momento único", t: "Valentina pide un crédito", d: "Sin pago protegido: el desembolso dispara la oferta en ese instante.", run: async () => { await ensureClient("valentina"); await fire("desembolso", {amount: 5000000, label: "Desembolso Lulo Crédito"}, "Desembolso Lulo Crédito"); }},
  {k: "No daño", t: "Apaga las sugerencias", d: "Queda como señal de daño y Tu protección explica por qué no hay sugerencias.", run: async () => { await ensureClient("valentina"); gotoTarget("perfil"); await wait(500); if (S.sugg) toggleSugg(); }},
  {k: "Base real", t: "Un cliente de la base: C00002", d: "11 abonos de nómina y crédito activo: Desempleo fuerte, con su porqué.", run: async () => { await ensureClient("C00002"); unlock(); gotoTarget("proteccion"); setTab("motor"); }},
  {k: "Campaña", t: "Plan de los 600 y backtest", d: "Qué se le ofrece a cada cliente hoy y el año recorrido con cero violaciones.", run: async () => { setTab("camp"); await renderCampaign(); await runBacktest(); }},
  {k: "Viaje en el tiempo", t: "+30 días: se abren ventanas de SOAT", d: "Los vencimientos de la base entran en la ventana de 30 días; el comportamiento queda congelado en el corte.", run: async () => { await switchClient("C00210", addDays(META.cutoff, 30)); if (!S.unlocked) unlock(); setTab("cliente"); }},
];
const demoDone = new Set();
function renderDemo() {
  $("#demoLead").textContent = `${DEMO.length} pasos para contar la propuesta con el motor real. Cada botón ejecuta el paso en el teléfono; también puedes hacerlo a mano.`;
  $("#demo").innerHTML = DEMO.map((s, i) => `<li class="${demoDone.has(i) ? "done" : ""}"><div><div class="dk">${s.k}</div><div class="dt">${s.t}</div><div class="dd">${s.d}</div></div><button data-demo="${i}">${demoDone.has(i) ? "Repetir" : "Ejecutar"}</button></li>`).join("");
}
$("#demo").addEventListener("click", async e => {
  const b = e.target.closest("[data-demo]"); if (!b) return;
  const i = +b.dataset.demo; b.disabled = true;
  if (mobile()) closeSheet();
  try { await DEMO[i].run(); demoDone.add(i); } catch (err) { console.error(err); toast("No se pudo ejecutar el paso"); } finally { renderDemo(); renderMotor(); }
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
  render("none"); renderAllPanel();
  if (route) gotoTarget(route); else if (S.unlocked) armHistory();
  setTimeout(() => $("#splash").classList.add("hide"), 1000);
  apiStatus("ok", `<b>Motor v3 conectado</b> · reglas ${META.rules_version} · ${META.clients.reto} clientes de la base + ${META.clients.persona} personajes`);
}
boot();
