// Orquestador: estado, navegación, flujos, motor, panel y demo guiada.
import { $, $$, addDays, clone, debounce, money, num, nowTime, store, wait } from "./util.js";
import { I as ICONS } from "./icons.js";
import {
  ROOTS, SCREENS, acceptedOffers, chapters, creditCuota, hasPolicy, movListHTML, quote, skeletonRows,
} from "./screens.js";
import { NOW, buildAccs, clientPicker, signalsHTML } from "./content.js";

const BOOT = JSON.parse($("#bootstrap").textContent);
const CLIENTS = BOOT.clients;
const CACHE = {[BOOT.current.client.id]: BOOT.current};
const KEY = "lulo:v2";
const IMG_LOGO = "/static/img/logo-lulo.png";
let S;

/* =================== API =================== */
async function call(path, body) {
  const r = await fetch(path, body === undefined ? {} : {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
  if (!r.ok) throw new Error(`${path} respondió ${r.status}`);
  return r;
}
const API = {
  health: () => call("/api/health").then(r => r.json()),
  client: id => call(`/api/clients/${id}`).then(r => r.json()),
  movements: (id, p) => call(`/api/clients/${id}/movements?${new URLSearchParams(p)}`).then(r => r.json()),
  movement: (id, tx) => call(`/api/clients/${id}/movements/${tx}`).then(r => r.json()),
  action: (id, body) => call(`/api/clients/${id}/actions`, body).then(r => r.json()),
  event: body => call("/api/engine/event", body).then(r => r.json()),
  csv: log => call("/api/report/csv", log).then(r => r.blob()),
};
function apiStatus(state, html) { const el = $("#apiStatus"); if (!el) return; el.className = "api-status " + state; el.querySelector("span").innerHTML = html; }

/* =================== estado =================== */
function freshState(B) {
  return {
    cid: B.client.id, B, screen: "lock", params: {}, stack: [], unlocked: false, pin: "",
    hide: false, cardFrozen: false, balance: B.balance, sessionMovs: [], seq: 0,
    policies: clone(B.policies), cajitas: clone(B.cajitas), credit: clone(B.credit), notifs: clone(B.notifications),
    log: [], queue: [], shown: null, control: false, sugg: true, remind: true, alertDays: 30, consent: true,
    soatRenewed: false, known: {}, declined: {}, story: 0, storyOpened: false, storyDone: false, yearLoaded: false,
    offer: null, flow: {}, detail: null, mq: "", mg: "todos",
  };
}
function loadState(B) {
  const saved = store.get(`${KEY}:state:${B.client.id}`);
  S = {...freshState(B), ...(saved || {}), B, tok: Math.random(), shown: null, flow: {}, detail: null, stack: [], params: {}};
  if (!ROOTS.includes(S.screen)) S.screen = S.unlocked ? "home" : "lock";
}
function snapshot() {
  const {B, tok, detail, flow, stack, params, shown, ...rest} = S;
  return {...rest, screen: ROOTS.includes(S.screen) ? S.screen : (S.unlocked ? "home" : "lock")};
}
const persist = debounce(() => {
  if (!S) return;
  store.set(`${KEY}:state:${S.cid}`, snapshot());
  store.set(`${KEY}:client`, S.cid);
}, 150);

/* =================== navegación =================== */
const sc = () => $("#scroll");
const entry = () => ({screen: S.screen, params: S.params, scroll: sc().scrollTop});
function go(screen, params = {}) {
  S.stack.push(entry());
  S.screen = screen; S.params = params;
  render("push"); sc().scrollTop = 0; armHistory();
}
function replace(screen, params = S.params) { S.screen = screen; S.params = params; render("fade"); sc().scrollTop = 0; }
function back() {
  if (["processing", "paying", "lock", "yearLoading"].includes(S.screen)) return false;
  if (S.screen === "success") { flowDone(); return true; }
  abandonOpen();
  const prev = S.stack.pop();
  if (!prev) {
    if (ROOTS.includes(S.screen)) { if (S.screen !== "home") { tabTo("home"); return true; } return false; }
    S.screen = "home"; S.params = {}; render("pop"); return true;
  }
  S.screen = prev.screen; S.params = prev.params;
  render("pop"); sc().scrollTop = prev.scroll || 0;
  return true;
}
function tabTo(t) { abandonOpen(); S.stack = []; S.screen = t; S.params = {}; render("fade"); sc().scrollTop = 0; }

// El botón atrás del navegador o del celular navega dentro de la app.
function armHistory() { if (history.state?.lulo !== "trap") history.pushState({lulo: "trap"}, "", location.href); }
// Un cambio de #ruta también dispara popstate pero sin estado propio: de ese caso se encarga hashchange.
addEventListener("popstate", e => { if (e.state?.lulo && S.unlocked && back()) armHistory(); });
// Un enlace con otro #/ruta en la misma pestaña también navega.
addEventListener("hashchange", () => { const r = routeFromHash(location.hash); if (r && location.hash !== hashFor()) gotoTarget(r); });
const HASH = {home: "#/inicio", movs: "#/movimientos", anio: "#/tu-ano", perfil: "#/perfil", renew: "#/soat", notifs: "#/notificaciones",
  transfer: "#/enviar", cajitas: "#/cajitas", credito: "#/credito", card: "#/tarjeta"};
function hashOf(e) {
  if (e.screen === "story") return `#/tu-ano/${chapters(S)[S.story].id}`;
  if (e.screen === "offer") return `#/oferta/${S.offer}`;
  if (e.screen === "mov") return `#/movimientos/${e.params.id}`;
  if (e.screen === "cajita") return `#/cajitas/${e.params.id}`;
  return HASH[e.screen] || null;
}
// Las pantallas de paso (monto, comprobante…) conservan el enlace de la pantalla desde la que se abrieron.
function hashFor() {
  let h = hashOf(S);
  for (let i = S.stack.length - 1; !h && i >= 0; i--) h = hashOf(S.stack[i]);
  return h || "#/inicio";
}
function routeFromHash(h) {
  const p = h.replace(/^#\/?/, "").split("/").filter(Boolean);
  const m = {inicio: "home", movimientos: "movs", "tu-ano": "anio", perfil: "perfil", soat: "renew", notificaciones: "notifs",
    enviar: "transfer", cajitas: "cajitas", credito: "credito", tarjeta: "card"};
  if (!p.length) return null;
  if (p[0] === "tu-ano" && p[1]) return `story:${p[1]}`;
  if (p[0] === "movimientos" && p[1]) return `mov:${p[1]}`;
  if (p[0] === "cajitas" && p[1]) return `cajita:${p[1]}`;
  if (p[0] === "oferta" && p[1]) return `offer:${p[1]}`;
  return m[p[0]] || null;
}

/* =================== render =================== */
const STATUS_BG = {lime: ["var(--lime)", "var(--ink)"], navy: ["var(--navy)", "#fff"], ink: ["var(--ink)", "#fff"], pink: ["var(--pink)", "var(--ink)"]};
const TABS = [["home", "Inicio", "home"], ["movs", "Movimientos", "movs"], ["anio", "Tu año", "year"], ["perfil", "Perfil", "user"]];
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
  if (showTabs) tb.innerHTML = TABS.map(([k, l, ic]) => `<button class="tab" data-a="tab" data-t="${k}" ${S.screen === k ? 'aria-current="page"' : ""}>${ICONS[ic]}${l}</button>`).join("");
  S.sessionMovs.forEach(m => m.flash = false);
  MOUNT[S.screen]?.();
  updateNow();
  const h = S.unlocked && hashFor();
  if (h && location.hash !== h) history.replaceState(history.state, "", h);
  persist();
}
function toast(m) { const t = $("#toast"); t.textContent = m; t.classList.add("show"); clearTimeout(t._h); t._h = setTimeout(() => t.classList.remove("show"), 2300); }
function flashPhone() { const p = $(".phone"); p.classList.remove("flashbox"); void p.offsetWidth; p.classList.add("flashbox"); }

/* =================== montaje por pantalla =================== */
const MC = {};
const movKey = () => `${S.cid}|${S.mg}|${S.mq.trim().toLowerCase()}`;
const MOUNT = {
  movs() { loadMovs(); },
  mov() { ensureDetail(); },
  yearLoading() {
    const tok = S.tok;
    const steps = [`Leyendo ${num(S.B.movCount)} movimientos`, "Buscando tus momentos del año", `Armando ${chapters(S).length} capítulos`];
    steps.forEach((t, i) => setTimeout(() => { const s = $("#yrLoadS"); if (s && tok === S.tok) s.textContent = t; }, i * 480));
    setTimeout(() => { if (tok === S.tok && S.screen === "yearLoading") { replace("story"); storyOpenedHooks(); } }, 1500);
  },
};
const fold = s => s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
function matches(m) {
  if (S.mg !== "todos" && m.g !== S.mg) return false;
  const q = fold(S.mq.trim());
  return !q || fold(m.n + " " + m.c).includes(q);
}
async function loadMovs() {
  const key = movKey();
  let st = MC[key];
  if (!st) {
    st = MC[key] = {items: [], total: null, in: null, out: null, loading: false};
    if (S.mg === "todos" && !S.mq.trim()) { st.items = S.B.recent.slice(); st.total = S.B.movCount; }
  }
  paintMovs();
  if (st.loading || (st.total !== null && st.items.length >= st.total && st.in !== null)) return;
  st.loading = true; paintMovs();
  try {
    const r = await API.movements(S.cid, {q: S.mq.trim(), group: S.mg, offset: st.items.length, limit: 60});
    st.items.push(...r.items); st.total = r.total; st.in = r.in; st.out = r.out;
  } catch { toast("No se pudieron cargar los movimientos"); }
  st.loading = false;
  if (S.screen === "movs" && movKey() === key) paintMovs();
}
function paintMovs() {
  const st = MC[movKey()], list = $("#movList");
  if (!list || !st) return;
  const sess = S.sessionMovs.filter(matches);
  const items = [...sess, ...st.items];
  if (!items.length) list.innerHTML = st.loading || st.total === null ? skeletonRows(8) : `<div class="empty-st">No encontramos movimientos${S.mq ? ` con «${S.mq.replace(/[<>&"]/g, "")}»` : ""}.</div>`;
  else list.innerHTML = movListHTML(items, S.B.today);
  const total = st.total === null ? null : st.total + sess.length;
  const sIn = sess.filter(m => m.a > 0).reduce((a, m) => a + m.a, 0), sOut = -sess.filter(m => m.a < 0).reduce((a, m) => a + m.a, 0);
  $("#movSum").innerHTML = total === null ? "&nbsp;" : `${num(total)} ${total === 1 ? "movimiento" : "movimientos"}` +
    (st.in !== null ? ` · <span class="in">+${money(st.in + sIn)}</span> · −${money(st.out + sOut)}` : "");
  $("#movMore").innerHTML = st.loading && items.length ? skeletonRows(3) : (st.total !== null && st.items.length >= st.total && items.length > 8 ? `<div class="end">Esos son todos los movimientos del año.</div>` : "");
}
async function ensureDetail() {
  const id = S.params.id;
  if (S.detail && (S.detail.tx?.id === id || S.detail.id === id)) return;
  const local = S.sessionMovs.find(m => m.id === id);
  if (local) { S.detail = {tx: local, signal: local.sig || null, same_count: 0}; render("none"); return; }
  S.detail = {loading: true, id};
  try {
    const d = await API.movement(S.cid, id);
    if (S.screen === "mov" && S.params.id === id) { S.detail = d; render("none"); }
  } catch { toast("No se pudo cargar el movimiento"); }
}
sc().addEventListener("scroll", () => {
  if (S.screen !== "movs") return;
  const el = sc();
  if (el.scrollTop + el.clientHeight > el.scrollHeight - 320) loadMovs();
});

/* =================== movimientos nuevos y registro =================== */
function addMovement(m) {
  const mv = {ref: "LB" + String(Math.floor(Math.random() * 1e8)).padStart(8, "0"), ...m, id: `s${++S.seq}`,
    date: S.B.today, time: new Date().toTimeString().slice(0, 5), flash: true};
  S.sessionMovs.unshift(mv);
  S.balance += mv.a;
  if (S.screen === "home") render("none");
  if (S.screen === "movs") paintMovs();
  return mv;
}
function addNotif(n) { S.notifs.unshift({id: `n${++S.seq}`, when: "Ahora", unread: true, ...n}); }
function addLog(ev, offer, res, tipo) {
  S.log.unshift({t: nowTime(), client: S.B.client.first, ev, offer, res, tipo});
  if (["ok", "no", "harm", "info", "val"].includes(tipo)) lightStep(3);
  renderPanel(); persist();
}

/* =================== motor =================== */
let chainTimer = [];
function lightStep(i) { const el = $(`.step[data-step="${i}"]`); if (!el) return; el.classList.add("on"); if (i === 3) el.classList.remove("missing"); setTimeout(() => el.classList.remove("on"), 1400); }
function runChain(upTo, done) {
  chainTimer.forEach(clearTimeout); chainTimer = [];
  $$(".step").forEach(s => s.classList.remove("on"));
  for (let i = 0; i <= upTo; i++) chainTimer.push(setTimeout(() => lightStep(i), i * 380));
  chainTimer.push(setTimeout(done || (() => {}), upTo * 380 + 320));
}
function msg(h) { const m = $("#chainMsg"); if (m) m.innerHTML = h; }
function windowDecision() {
  const w = S.shown;
  return w ? {key: w.key || "vehiculo", prio: w.prio || 2, kind: w.kind === "renew" ? "renew" : "offer", offer: w.offer || "", offerName: w.offerName, ev: w.ev, text: w.text || ""} : null;
}
let busy = Promise.resolve();
function fire(key, opts = {}) { busy = busy.then(() => fireNow(key, opts)).catch(() => {}); return busy; }
async function fireNow(key, {mov = true} = {}) {
  const tok = S.tok, E = S.B.events[key];
  const mv = mov ? addMovement({...E.mov, tag: key}) : null;
  runChain(0);
  const ctx = {client_id: S.cid, event: key, control: S.control, suggestions: S.sugg, consent: S.consent,
    soat_renewed: S.soatRenewed, active: acceptedOffers(S), window: windowDecision(), queue: S.queue};
  let R;
  try {
    const t0 = performance.now();
    R = await API.event(ctx);
    apiStatus("ok", `<b>Motor en Python conectado</b> · última decisión en ${Math.round(performance.now() - t0)} ms`);
  } catch {
    apiStatus("err", "<b>El motor no respondió.</b> El movimiento quedó, pero no hubo decisión.");
    msg("<b>Error:</b> no se pudo consultar el motor."); return;
  }
  if (tok !== S.tok) return;
  if (mv) { const s = R.signal; mv.sig = {key: s.key, name: s.name, headline: s.headline, rule: s.rule, strength: s.strength, offer: s.offer}; }
  S.queue = R.queue;
  const sg = $(`.sig[data-sig="${key}"]`); if (sg) { sg.classList.remove("flash"); void sg.offsetWidth; sg.classList.add("flash"); }
  if (R.outcome === "shown") { show(R.decision); await wait(3 * 380 + 400); return; }
  msg(R.message); runChain(R.chain);
  if (R.log) addLog(R.log.ev, R.log.offer, R.log.res, R.log.tipo);
}
function show(d) {
  S.shown = d;
  msg(`<b>Se muestra:</b> ${d.offerName}. ${d.kind === "renew" ? "El SOAT está por vencer: se ofrece renovar." : "La señal es fuerte, es elegible y la ventana está libre."} Mira el teléfono.`);
  const tok = S.tok;
  runChain(2, () => {
    if (tok !== S.tok) return;
    const n = $("#notif");
    n.innerHTML = `<span class="ic"><img src="${IMG_LOGO}" alt=""></span><span style="flex:1"><span class="t"><span>Lulo Bank</span><span>ahora</span></span><span class="b">${d.text}</span></span>`;
    n.classList.add("show"); $("#notifX").classList.add("show");
    // Como en el celular, el aviso se va solo y queda en la bandeja; la ventana de contacto sigue abierta.
    setTimeout(() => { if (S.shown === d) hideNotif(); }, 9000);
    addNotif({t: d.text.match(/<b>(.*?)<\/b>/)?.[1] || d.offerName, b: d.text.replace(/<b>.*?<\/b>/, ""), go: d.kind === "renew" ? "renew" : `offer:${d.offer}`, dk: d.key});
    if (S.screen === "home" || S.screen === "notifs") render("none");
    addLog(d.ev, d.offerName, "Mostrada en la app", "info");
  });
  renderPanel();
}
function hideNotif() { $("#notif").classList.remove("show"); $("#notifX").classList.remove("show"); }
function closeWindow() { S.shown = null; renderPanel(); }
function abandonOpen() {
  if (S.shown && (S.screen === "offer" || S.screen === "renew")) { addLog(S.shown.ev, S.shown.offerName, "Cerró sin decidir", "no"); closeWindow(); }
}
function openFromWindow(d) {
  hideNotif();
  if (!S.unlocked) unlock();
  const n = S.notifs.find(x => x.dk === d.key && x.unread); if (n) n.unread = false;
  if (d.kind === "renew") openRenew(); else { S.offer = d.offer; go("offer"); }
}
$("#notif").addEventListener("click", () => { if (S.shown) openFromWindow(S.shown); });
$("#notifX").addEventListener("click", () => { const d = S.shown; hideNotif(); if (d) { addLog(d.ev, d.offerName, "Descartó la notificación", "no"); closeWindow(); } });

function activate(k, src) {
  const O = S.B.offers[k];
  if (!O) return;
  if (!hasPolicy(S, k)) S.policies.push({id: k + "-new", offer: k, title: O.title, aliado: O.aliado, status: "ok", sub: O.sub});
  if (k === "pago" && S.credit) S.credit.protected = true;
  addLog(src, O.title, "Aceptó", "ok");
}
function acceptOffer() {
  const k = S.offer; if (!S.B.offers[k]) return;
  activate(k, S.shown ? S.shown.ev : "Entrada directa"); closeWindow();
  back(); toast("Activado. Aparecerá al cierre de Tu año");
}
function openRenew() {
  if (!S.B.car) { toast("Este cliente no tiene vehículo registrado"); return; }
  if (S.soatRenewed) { toast("El SOAT ya está renovado"); return; }
  if (S.screen !== "renew") go("renew");
}
function pay() {
  if (S.soatRenewed || S.screen !== "renew") return;
  const Q = quote(S), car = S.B.car;
  if (S.balance < Q.total) { toast("Saldo insuficiente"); return; }
  const src = S.shown && S.shown.kind === "renew" ? S.shown.ev : "Recordatorio en la app";
  const tok = S.tok;
  replace("paying");
  setTimeout(() => {
    if (tok !== S.tok) return;
    S.soatRenewed = true;
    Object.assign(S.policies.find(p => p.offer === "soat"), {status: "ok", sub: `vigente hasta el ${car.new_to}`});
    addMovement({n: `SOAT ${car.plate} · ${car.insurer}`, c: "Seguros", cat: "seguros", g: "pagos", a: -Q.total, ic: "🛡️", ch: "Cuenta Lulo"});
    S.notifs = S.notifs.filter(n => n.id !== "n-soat");
    addNotif({t: "Tu SOAT quedó renovado", b: `${car.plate} · vigente hasta el ${car.new_to}`, go: "home", unread: false});
    addLog(src, "Renovar SOAT", "Renovó en Lulo (captura de canal)", "ok"); closeWindow();
    S.stack = []; replace("done");
  }, 1300);
}
function setKnown(v) { S.known.pago = v; addLog("Tu año en Lulo · Tu crédito", "Pago protegido", `¿Sabía que lo tenía? ${v}`, "val"); render("none"); toast("Gracias por responder"); }
function toggleSugg() { S.sugg = !S.sugg; addLog("Perfil", "Sugerencias de seguros", S.sugg ? "Reactivó sugerencias" : "Desactivó sugerencias", S.sugg ? "info" : "harm"); render("none"); }
function setConsent(v) { S.consent = v; addLog("Perfil", "Autorización de datos", v ? "Autorizó usar sus movimientos" : "Retiró la autorización de datos", v ? "val" : "harm"); render("none"); }

/* =================== Tu año =================== */
function storyIndex(arg) {
  const list = chapters(S);
  if (arg === undefined || arg === "") return 0;
  if (/^\d+$/.test(arg)) return Math.min(+arg, list.length - 1);
  if (arg === "protect") return Math.max(0, list.findIndex(c => c.protect || c.soat));
  const i = list.findIndex(c => c.id === arg);
  return i < 0 ? 0 : i;
}
function openStory(i) {
  if (!S.consent) { if (S.screen !== "anio") tabTo("anio"); toast("Primero autoriza el uso de tus movimientos"); return; }
  S.story = i;
  if (S.screen === "story") { render("fade"); storySeen(); return; }
  S.stack.push(entry()); armHistory();
  if (!S.yearLoaded) { S.yearLoaded = true; S.screen = "yearLoading"; render("fade"); return; }
  S.screen = "story"; render("push"); sc().scrollTop = 0; storyOpenedHooks();
}
function storyOpenedHooks() {
  if (!S.storyOpened) {
    S.storyOpened = true;
    msg(`<b>Tu año en Lulo:</b> el backend leyó ${num(S.B.movCount)} movimientos y armó ${chapters(S).length} capítulos para ${S.B.client.first}. Mira el teléfono.`);
    runChain(2);
    addLog("Tu año en Lulo", "Resumen anual", "Abrió el resumen", "info");
    if (S.control) addLog("Tu año en Lulo", "Momentos de protección", "Grupo de control: resumen sin ofertas", "ctrl");
  }
  storySeen();
}
function storySeen() { if (S.story === chapters(S).length - 1 && !S.storyDone) { S.storyDone = true; addLog("Tu año en Lulo", "Resumen anual", "Completó el resumen", "info"); } }
function storyStep(d) {
  const n = S.story + d;
  if (n < 0) return;
  if (n >= chapters(S).length) { back(); return; }
  S.story = n; render("fade"); storySeen();
}

/* =================== flujos de acciones =================== */
// `base` es la posición de la pila a la que vuelve «Listo» al terminar el flujo.
function startFlow(f, base = S.stack.length) { S.flow = {base, amount: 0, ...f}; }
function pickContact(id) {
  const c = S.B.contacts.find(x => x.id === id);
  const ben = S.B.signals.vida.metrics.beneficiaries.find(b => b.id === id);
  startFlow({kind: "transfer", contact: c, suggest: [...new Set([ben?.amount, 50000, 100000, 200000].filter(Boolean))].slice(0, 3)},
    S.screen === "transfer" ? S.stack.length - 1 : S.stack.length);
  go("amount");
}
function startCajita(id) {
  const c = S.cajitas.find(x => x.id === id);
  startFlow({kind: "cajita", cajita: c, suggest: [...new Set([c.history[0]?.a, 100000, 200000].filter(Boolean))].slice(0, 3)});
  go("amount");
}
function startCreditReq() {
  const max = S.credit ? 9000000 : S.B.client.preapproved;
  startFlow({kind: "desembolso", amount: Math.round(max / 2 / 1e5) * 1e5, cuotas: 18});
  go("creditReq");
}
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
  const F = S.flow, tok = S.tok;
  replace("processing");
  let R;
  try {
    [R] = await Promise.all([API.action(S.cid, {type: F.kind, target: F.contact?.id || F.cajita?.id || null, amount: F.amount}), wait(1100)]);
  } catch { if (tok === S.tok) { toast("No se pudo completar la operación"); replace("confirm"); } return; }
  if (tok !== S.tok) return;
  const mv = addMovement({...R.movement, sig: R.signal});
  F.result = {...R, movement: mv};
  if (F.kind === "transfer") addNotif({t: `Enviaste ${money(F.amount)}`, b: `A ${F.contact.name} por Bre-B`, go: `mov:${mv.id}`, unread: false});
  if (F.kind === "cajita") { F.cajita.saved += F.amount; F.cajita.deposits += 1; F.cajita.history.unshift({date: S.B.today, a: F.amount}); }
  if (F.kind === "cuota") {
    S.credit.paid += 1; S.credit.remaining = Math.max(0, S.credit.remaining - S.credit.cuota); S.credit.next_date = addDays(S.credit.next_date, 30);
    addLog("Crédito", "Pago de cuota", `Pagó la cuota ${S.credit.paid} de ${S.credit.cuotas}`, "info");
  }
  if (F.kind === "desembolso") {
    if (!S.credit) S.credit = {name: "Lulo Crédito", amount: F.amount, cuotas: F.cuotas, cuota: F.cuota, paid: 0, protected: hasPolicy(S, "pago"), rate: "1,79% M.V.", remaining: F.cuotas * F.cuota, next_date: addDays(S.B.today, 30)};
    else { S.credit.amount += F.amount; S.credit.remaining += F.cuotas * F.cuota; }
  }
  replace("success");
  if (R.event) { await wait(1400); if (tok === S.tok) return fire(R.event, {mov: false}); }
}
function flowDone() {
  const base = S.flow.base ?? 0;
  const e = S.stack[base];
  S.stack.length = Math.min(S.stack.length, base);
  if (e) { S.screen = e.screen; S.params = e.params; } else { S.screen = "home"; S.params = {}; }
  render("pop");
}

/* =================== ingreso =================== */
function unlock() {
  S.unlocked = true; S.pin = "";
  if (S.screen === "lock") { S.screen = "home"; S.stack = []; S.params = {}; }
  render("fade"); armHistory();
}
function lock() { abandonOpen(); hideNotif(); S.unlocked = false; S.pin = ""; S.stack = []; S.screen = "lock"; S.params = {}; render("fade"); }

/* =================== acciones en el teléfono =================== */
$("#phone").addEventListener("click", e => {
  const b = e.target.closest("[data-a]"); if (!b || b.disabled) return;
  const a = b.dataset.a, F = S.flow;
  switch (a) {
    case "back": back(); break;
    case "tab": tabTo(b.dataset.t); break;
    case "go":
      if (b.dataset.s === "creditReq") startCreditReq();
      else if (b.dataset.s === "renew") openRenew();
      else if (b.dataset.s === "transfer") go("transfer", {mode: b.dataset.p});
      else go(b.dataset.s, b.dataset.p ? {id: b.dataset.p} : {});
      break;
    case "key":
      if (S.screen === "lock") {
        if (b.dataset.k === "bio") { unlock(); break; }
        if (b.dataset.k === "del") S.pin = S.pin.slice(0, -1);
        else if (/^\d$/.test(b.dataset.k) && S.pin.length < 4) S.pin += b.dataset.k;
        render("none");
        if (S.pin.length >= 4) setTimeout(() => S.screen === "lock" && unlock(), 220);
      } else {
        const k = b.dataset.k, cur = F.amount || 0;
        setAmount(k === "del" ? Math.floor(cur / 10) : k === "000" ? cur * 1000 : cur * 10 + +k);
      }
      break;
    case "unlock": unlock(); break;
    case "logout": lock(); break;
    case "hide": S.hide = !S.hide; render("none"); break;
    case "freeze": S.cardFrozen = !S.cardFrozen; render("none"); toast(S.cardFrozen ? "Tarjeta congelada" : "Tarjeta activa de nuevo"); break;
    case "toast": toast(b.dataset.m); break;
    case "mov": S.detail = null; go("mov", {id: b.dataset.id}); break;
    case "grp": S.mg = b.dataset.g; $$(".chips [data-g]").forEach(x => x.setAttribute("aria-pressed", x.dataset.g === S.mg)); sc().scrollTop = 0; loadMovs(); persist(); break;
    case "notif": {
      const n = S.notifs.find(x => x.id === b.dataset.id); if (!n) break;
      n.unread = false;
      const [t, arg] = (n.go || "").split(":");
      if (ROOTS.includes(t)) tabTo(t);
      else if (t === "renew") openRenew();
      else if (t === "mov") { S.detail = null; go("mov", {id: arg}); }
      else if (t === "cajita") go("cajita", {id: arg});
      else if (t === "offer") { if (S.shown && S.shown.offer === arg) openFromWindow(S.shown); else { S.offer = arg; go("offer"); } }
      else if (t && SCREENS[t]) go(t);
      else render("none");
      break;
    }
    case "read-all": S.notifs.forEach(n => n.unread = false); render("none"); break;
    case "pick-contact": pickContact(b.dataset.id); break;
    case "amt-set": setAmount(+b.dataset.v); break;
    case "amt-next": if (F.amount > 0 && F.amount <= S.balance) go("confirm"); break;
    case "confirm": confirmFlow(); break;
    case "flow-done": flowDone(); break;
    case "cajita-abonar": startCajita(b.dataset.id); break;
    case "pay-cuota":
      if (S.balance < S.credit.cuota) { toast("Saldo insuficiente"); break; }
      startFlow({kind: "cuota", amount: S.credit.cuota}); go("confirm"); break;
    case "cr-amt": F.amount = +b.dataset.v; render("none"); break;
    case "cr-n": F.cuotas = +b.dataset.v; render("none"); break;
    case "cr-next": F.cuota = creditCuota(F.amount, F.cuotas); go("confirm"); break;
    case "st-open": openStory(+b.dataset.i); break;
    case "st-next": storyStep(1); break;
    case "st-prev": storyStep(-1); break;
    case "st-close": back(); break;
    case "st-yes": activate(b.dataset.k, "Tu año en Lulo · " + chapters(S)[S.story].name); render("none"); toast("Activado"); break;
    case "st-no": S.declined[b.dataset.k] = true; addLog("Tu año en Lulo · " + chapters(S)[S.story].name, S.B.offers[b.dataset.k].title, "Rechazó: ahora no", "no"); render("none"); break;
    case "st-soat":
      if (S.shown) { hideNotif(); addLog(S.shown.ev, S.shown.offerName, "Ventana cerrada sin respuesta", "no"); }
      S.shown = {kind: "renew", key: "vehiculo", prio: 2, offer: "soat", ev: "Tu año en Lulo · Tu carro", offerName: "Renovar SOAT"};
      renderPanel(); go("renew"); break;
    case "st-share": addLog("Tu año en Lulo", "Resumen anual", "Compartió su año", "info"); toast("Imagen lista para compartir"); break;
    case "known": setKnown(b.dataset.v); break;
    case "accept": acceptOffer(); break;
    case "later": addLog(S.shown ? S.shown.ev : "Entrada directa", S.B.offers[S.offer].title, "Rechazó: ahora no", "no"); closeWindow(); back(); toast("Listo, no te lo volveremos a mostrar pronto"); break;
    case "optout": addLog(S.shown ? S.shown.ev : "Entrada directa", S.B.offers[S.offer].title, "Pidió no ver este tipo de sugerencias", "harm"); closeWindow(); back(); toast("No verás más sugerencias de este tipo"); break;
    case "pay": pay(); break;
    case "postpone": { const src = S.shown && S.shown.kind === "renew" ? S.shown.ev : "Recordatorio en la app"; addLog(src, "Renovar SOAT", "Pospuso la renovación", "no"); closeWindow(); back(); toast("Te lo recordaremos en 7 días"); break; }
    case "sugg": toggleSugg(); break;
    case "remind": S.remind = !S.remind; if (!S.remind) addLog("Perfil", "Avisos de vencimiento", "Desactivó avisos", "harm"); render("none"); break;
    case "days": S.alertDays = +b.dataset.d; addLog("Perfil", "Anticipación del aviso", `Prefiere ${S.alertDays} días`, "val"); render("none"); break;
    case "consent": setConsent(!S.consent); break;
    case "consent-on": setConsent(true); break;
  }
});
const onSearch = debounce(v => { S.mq = v; loadMovs(); persist(); }, 250);
$("#phone").addEventListener("input", e => { if (e.target.matches('[data-in="search"]')) onSearch(e.target.value); });
document.addEventListener("keydown", e => {
  if (e.target.matches("input, textarea")) return;
  if (S.screen === "story") {
    if (e.key === "ArrowRight") storyStep(1);
    if (e.key === "ArrowLeft") storyStep(-1);
    if (e.key === "Escape") back();
  }
});

/* =================== panel =================== */
function renderEvents() {
  $("#events").innerHTML = Object.values(S.B.events).map(E => `<button class="ev" data-ev="${E.key}"><span class="n">${E.label}</span><span class="h">${E.habit} · prioridad ${E.prio}</span><span class="o">${E.offer}</span></button>`).join("");
}
function renderPanel() {
  const L = S.log;
  const shown = L.filter(l => l.res === "Mostrada en la app").length;
  const ok = L.filter(l => l.tipo === "ok").length, no = L.filter(l => l.tipo === "no").length, harm = L.filter(l => l.tipo === "harm").length;
  $("#metrics").innerHTML = [[shown, "Ofertas mostradas"], [ok, "Aceptadas o renovadas"], [no, "Rechazadas o pospuestas"], [harm, "Señales de daño", true]]
    .map(([v, l, h]) => `<div class="metric ${h ? "harm" : ""}"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("");
  $("#queue").innerHTML = S.queue.length ? S.queue.map(q => `<span class="qitem"><b>P${q.prio}</b> ${q.offerName}</span>`).join("") : `<span class="empty">${S.shown ? "Ventana ocupada: " + S.shown.offerName + ". La cola está vacía." : "Ventana de contacto libre. La cola está vacía."}</span>`;
  $("#nextWin").disabled = !S.queue.length;
  const dl = $("#demoLast"); if (dl) dl.innerHTML = L.length ? `<b style="color:#fff">Último registro · ${L[0].client}</b>${L[0].offer}: ${L[0].res}` : `<b style="color:#fff">Último registro</b>Todavía no hay respuestas.`;
  $("#ctrlBtn").setAttribute("aria-pressed", S.control);
  const LABEL = {ok: "Acepta", no: "Rechaza", hold: "Cola", ctrl: "Sin contacto", harm: "No daño", info: "Contacto", val: "Validación"};
  $("#log").innerHTML = L.length ? L.map(l => `<div class="log-row"><time>${l.t}</time><span class="e"><b>${l.offer}</b><br>${l.ev} · ${l.res}</span><span class="tag ${l.tipo}">${LABEL[l.tipo]}</span></div>`).join("") : `<span class="empty">Todavía no hay respuestas. Este es el paso que hoy no existe en Lulo Bank.</span>`;
}
function renderAccs() {
  const open = new Set($$("#accs details[open]").map(d => d.id).filter(Boolean));
  const A = buildAccs(S, CLIENTS, S.B.events);
  $("#accs").innerHTML = A.map(a => a.g ? `<div class="grp-t">${a.g}</div>` :
    `<details class="acc" id="${a.id}"${(open.size ? open.has(a.id) : a.open) ? " open" : ""}><summary><span class="s-k${a.kp ? " pk" : ""}">${a.k}</span><span class="s-t">${a.t}</span><span class="s-d">${a.d}</span></summary><div class="acc-b">${a.b}</div></details>`).join("");
}
function renderClientPanel() {
  $("#clients").innerHTML = clientPicker(CLIENTS, S.cid);
  $("#sigTitle").textContent = `Lo que el motor ve de ${S.B.client.first}`;
  $("#signals").innerHTML = signalsHTML(S);
}
function renderAllPanel() { renderClientPanel(); renderEvents(); renderAccs(); renderPanel(); renderDemo(); }
function updateNow() {
  const N = NOW[S.screen]; if (!N) return;
  let name = N.n, what = N.what;
  if (S.screen === "story") { const c = chapters(S)[S.story]; name += `: ${c.name} (${S.story + 1} de ${chapters(S).length})`; what = c.spec; }
  if (S.screen === "offer" && S.offer) name += ": " + S.B.offers[S.offer].title;
  $("#nowName").textContent = name;
  $("#nowWho").textContent = S.B.client.full;
  $("#nowBody").innerHTML = `<span class="idea-tag">${N.tag}</span><div>${what}</div><h5>Qué puedes hacer aquí</h5><ul>${N.how.map(h => `<li>${h}</li>`).join("")}</ul><h5>Qué valida o mide</h5><div>${N.val}</div>`;
}
function setTab(t) {
  $$(".ptabs button").forEach(b => b.setAttribute("aria-selected", b.dataset.tab === t));
  $$(".pview").forEach(v => v.hidden = v.id !== "view-" + t);
}
$(".ptabs").addEventListener("click", e => { const b = e.target.closest("[data-tab]"); if (b) setTab(b.dataset.tab); });
$("#openAll").addEventListener("click", () => $$("#accs details").forEach(d => d.open = true));
$("#closeAll").addEventListener("click", () => $$("#accs details").forEach(d => d.open = false));
$("#events").addEventListener("click", e => { const b = e.target.closest("[data-ev]"); if (b) { if (!S.unlocked) unlock(); fire(b.dataset.ev); } });
$("#nextWin").addEventListener("click", () => {
  if (S.shown) { hideNotif(); addLog(S.shown.ev, S.shown.offerName, "Ventana cerrada sin respuesta", "no"); closeWindow(); }
  const d = S.queue.shift(); if (d) show(d);
});
$("#ctrlBtn").addEventListener("click", () => { S.control = !S.control; renderPanel(); persist(); });
$("#csvBtn").addEventListener("click", async () => {
  if (!S.log.length) { toast("El registro está vacío"); return; }
  try {
    const blob = await API.csv(S.log.slice().reverse());
    const a = document.createElement("a"); a.href = URL.createObjectURL(blob);
    a.download = `registro-respuestas-${S.cid}.csv`; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  } catch { toast("No se pudo generar el CSV"); }
});
function resetAll() {
  CLIENTS.forEach(c => store.del(`${KEY}:state:${c.id}`));
  Object.keys(MC).forEach(k => delete MC[k]);
  hideNotif(); busy = Promise.resolve(); chainTimer.forEach(clearTimeout);
  loadState(S.B); S.unlocked = true; S.screen = "home";
  demoDone.clear(); msg("Dispara un evento o usa la app para ver cómo decide el motor.");
  $$(".step")[3].classList.add("missing");
  render("fade"); renderAllPanel(); toast("Demo reiniciada");
}
$("#resetBtn").addEventListener("click", resetAll); $("#resetBtn2").addEventListener("click", resetAll);

async function switchClient(id) {
  if (id === S.cid) return;
  store.set(`${KEY}:state:${S.cid}`, snapshot());
  let NB = CACHE[id];
  if (!NB) {
    $("#splash").classList.remove("hide");
    try { NB = CACHE[id] = await API.client(id); } catch { $("#splash").classList.add("hide"); toast("No se pudo cargar el cliente"); return; }
  }
  hideNotif(); busy = Promise.resolve(); chainTimer.forEach(clearTimeout);
  loadState(NB); S.unlocked = false; S.screen = "lock";
  store.set(`${KEY}:client`, id);
  const u = new URL(location.href); u.searchParams.set("cliente", id); u.hash = ""; history.replaceState(history.state, "", u);
  msg(`Cliente: <b>${NB.client.full}</b>. Dispara un evento o usa la app para ver cómo decide el motor.`);
  render("fade"); renderAllPanel();
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
  S.unlocked = true;
  abandonOpen();
  const [scr, arg] = t.split(":");
  S.stack = []; S.params = {};
  const home = {screen: "home", params: {}, scroll: 0};
  if (scr === "story") { S.screen = "anio"; render("none"); openStory(storyIndex(arg)); flashPhone(); closeSheet(); return; }
  if (scr === "offer" && S.B.offers[arg]) { S.stack = [home]; S.offer = arg; S.screen = "offer"; }
  else if (scr === "renew") {
    if (!S.B.car) { S.screen = "home"; toast("Este cliente no tiene vehículo registrado"); }
    else if (S.soatRenewed) { S.screen = "home"; toast("El SOAT ya está renovado. Reinicia la demo para verlo otra vez"); }
    else { S.stack = [home]; S.screen = "renew"; }
  } else if (scr === "mov") { S.stack = [{screen: "movs", params: {}, scroll: 0}]; S.detail = null; S.screen = "mov"; S.params = {id: arg}; }
  else if (scr === "cajita" && S.cajitas.some(c => c.id === arg)) { S.stack = [home, {screen: "cajitas", params: {}, scroll: 0}]; S.screen = "cajita"; S.params = {id: arg}; }
  else if (scr === "transfer") { S.stack = [home]; S.screen = "transfer"; S.params = {mode: "enviar"}; }
  else if (["cajitas", "credito", "card", "notifs"].includes(scr)) { S.stack = [home]; S.screen = scr; }
  else S.screen = ROOTS.includes(scr) ? scr : "home";
  render("fade"); sc().scrollTop = 0; armHistory(); flashPhone(); closeSheet();
}

/* =================== panel en el celular =================== */
const mobile = () => matchMedia("(max-width: 760px)").matches;
function closeSheet() { document.body.classList.remove("sheet-open"); }
$("#panelFab").addEventListener("click", () => document.body.classList.toggle("sheet-open"));
$("#sheetClose").addEventListener("click", closeSheet);

/* =================== demo guiada =================== */
const waitFor = async (fn, ms = 4000) => { const t0 = Date.now(); while (!fn() && Date.now() - t0 < ms) await wait(60); };
async function ensureClient(id) { if (S.cid !== id) { await switchClient(id); await wait(450); } if (!S.unlocked) unlock(); }
async function inStory(id) { gotoTarget(`story:${id}`); await waitFor(() => S.screen === "story"); await wait(500); }
const DEMO = [
  {k: "Contexto", t: "Arranca como Sebastián", d: "Ingresa con su clave. Saldo, aviso del SOAT y la tarjeta de Tu año salen de su año de movimientos.", run: async () => { await ensureClient("sebastian"); gotoTarget("home"); }},
  {k: "Futuro", t: "Abre el aviso del SOAT", d: "Llega a la renovación con vigencia, descuento y pago desde Lulo.", run: async () => { await ensureClient("sebastian"); gotoTarget("renew"); }},
  {k: "Futuro", t: "Paga la renovación", d: "Se mide como captura de canal: la compra iba a pasar igual.", run: async () => { await ensureClient("sebastian"); if (S.soatRenewed) { toast("El SOAT ya estaba renovado"); return; } if (S.screen !== "renew") gotoTarget("renew"); await wait(500); pay(); await wait(1500); }},
  {k: "Pasado", t: "Abre Tu año en Lulo", d: "El backend lee 1.284 movimientos y arma la historia.", run: async () => { await ensureClient("sebastian"); await inStory("intro"); }},
  {k: "Pasado", t: "Activa el seguro de nómina", d: "En «Tu ingreso» la protección nace de lo que el cliente ya vivió.", run: async () => { await ensureClient("sebastian"); await inStory("ingreso"); if (!hasPolicy(S, "nomina")) { activate("nomina", "Tu año en Lulo · Tu ingreso"); render("none"); toast("Activado"); } }},
  {k: "Pasado", t: "Responde la validación del crédito", d: "«No sabía que tenía pago protegido» queda en el registro.", run: async () => { await ensureClient("sebastian"); await inStory("credito"); if (!S.known.pago) setKnown("No"); }},
  {k: "Pasado", t: "Llega al cierre y comparte", d: "El cierre cuenta las protecciones activas, incluida la nueva.", run: async () => { await ensureClient("sebastian"); await inStory("cierre"); addLog("Tu año en Lulo", "Resumen anual", "Compartió su año", "info"); toast("Imagen lista para compartir"); }},
  {k: "Presente", t: "Transfiere a Laura desde la app", d: "Una acción real: el API la lee como señal de dependientes y el motor muestra la oferta de vida.", run: async () => {
    await ensureClient("sebastian"); gotoTarget("home"); await wait(500);
    go("transfer", {mode: "enviar"}); await wait(700); pickContact("laura"); await wait(600);
    setAmount(450000); await wait(700); go("confirm"); await wait(800); await confirmFlow(); }},
  {k: "Prioridad", t: "Llega otra señal con la ventana ocupada", d: "Un abono a la cajita «Viajes» mientras la oferta de vida sigue abierta: queda en cola por prioridad.", run: async () => { await ensureClient("sebastian"); await fire("viaje"); }},
  {k: "Presente", t: "Abre la notificación y activa", d: "La oferta explica por qué aparece. Al activar, se suma al cierre de Tu año.", run: async () => {
    await ensureClient("sebastian");
    if (!S.shown || S.shown.kind !== "offer") { if (S.queue.length) { $("#nextWin").click(); await wait(1600); } else { await fire(hasPolicy(S, "vida") ? "viaje" : "vida"); } }
    if (S.shown && S.shown.kind === "offer") { openFromWindow(S.shown); await wait(1300); acceptOffer(); } }},
  {k: "Elegibilidad", t: "Dispara el abono de nómina", d: "No se muestra nada: el cliente ya lo activó en Tu año. Las tres ideas comparten la misma regla.", run: async () => { await ensureClient("sebastian"); await fire("nomina"); }},
  {k: "Control", t: "Activa el grupo de control", d: "El evento ocurre, pero la oferta no se muestra: así se mide el efecto real.", run: async () => { await ensureClient("sebastian"); if (!S.control) { S.control = true; renderPanel(); } await wait(300); await fire("vida"); await wait(600); S.control = false; renderPanel(); }},
  {k: "No daño", t: "Apaga las sugerencias en Perfil", d: "Queda como señal de daño. Tu año se sigue viendo, pero sin ofertas.", run: async () => { await ensureClient("sebastian"); gotoTarget("perfil"); await wait(500); if (S.sugg) toggleSugg(); }},
  {k: "Personalización", t: "Cambia a Valentina", d: "Sin carro ni crédito, esos capítulos no aparecen. Su pago freelance no alcanza la regla de nómina: señal débil.", run: async () => { await ensureClient("valentina"); gotoTarget("anio"); await wait(900); await fire("nomina"); }},
  {k: "Personalización", t: "Cambia a Andrés", d: "SOAT a 9 días con aviso urgente. Ya tiene seguro de nómina: el evento no es elegible.", run: async () => { await ensureClient("andres"); gotoTarget("home"); await wait(900); await fire("nomina"); }},
];
const demoDone = new Set();
function renderDemo() {
  $("#demoLead").textContent = `${DEMO.length} pasos para contar la propuesta de principio a fin, con los tres clientes. Cada botón ejecuta el paso en el teléfono; también puedes hacerlo a mano.`;
  $("#demo").innerHTML = DEMO.map((s, i) => `<li class="${demoDone.has(i) ? "done" : ""}"><div><div class="dk">${s.k}</div><div class="dt">${s.t}</div><div class="dd">${s.d}</div></div><button data-demo="${i}">${demoDone.has(i) ? "Repetir" : "Ejecutar"}</button></li>`).join("");
}
$("#demo").addEventListener("click", async e => {
  const b = e.target.closest("[data-demo]"); if (!b) return;
  const i = +b.dataset.demo; b.disabled = true;
  if (mobile()) closeSheet();
  try { await DEMO[i].run(); demoDone.add(i); } finally { renderDemo(); renderPanel(); }
});

/* =================== inicio =================== */
async function boot() {
  const url = new URL(location.href);
  const wanted = url.searchParams.get("cliente") || store.get(`${KEY}:client`) || BOOT.current.client.id;
  let B = CACHE[wanted];
  if (!B) { try { B = CACHE[wanted] = await API.client(wanted); } catch { B = BOOT.current; } }
  loadState(B);
  const route = location.hash ? routeFromHash(location.hash) : null;
  history.replaceState({lulo: "base"}, "", location.href);
  render("none"); renderAllPanel();
  if (route) gotoTarget(route); else if (S.unlocked) armHistory();
  setTimeout(() => $("#splash").classList.add("hide"), 1100);
  const t0 = performance.now();
  try { const h = await API.health(); apiStatus("ok", `<b>Motor en Python conectado</b> · v${h.version} · ${Math.round(performance.now() - t0)} ms`); }
  catch { apiStatus("err", "<b>Sin conexión con el motor.</b> Revisa que el servidor esté corriendo."); }
}
boot();
