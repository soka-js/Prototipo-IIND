// Recorrido automático como una película: el prototipo se explica solo. Un cursor hace los clics de verdad en la
// app, los subtítulos cuentan lo que pasa y un globo señala lo nuevo al lado de cada cosa. Once capítulos, los
// mismos del recorrido paso a paso. Se pausa con la barra, con la barra espaciadora o tocando la pantalla; ← y →
// cambian de capítulo; Esc sale. ?ritmo=0.5 lo acelera y ?ritmo=1.5 lo hace más lento.
// Lo usa app.js con un objeto A que expone el estado y las acciones de la app.
import { $, esc, money, wait } from "./util.js";
import { NEW } from "./content.js";
import { pc } from "./aprende.js";

const RITMO = Math.min(3, Math.max(0.05, +new URLSearchParams(location.search).get("ritmo") || 1));
const t = ms => Math.max(120, ms * RITMO);
// Tiempo de lectura de un subtítulo: ~60 ms por carácter, entre 2,6 y 10 s (por el ritmo).
const lectura = s => t(Math.min(10000, Math.max(2600, 900 + s.length * 60)));
const ICO = {
  pausa: '<svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true"><rect x="2" y="1.5" width="2.8" height="9" rx=".6" fill="currentColor"/><rect x="7.2" y="1.5" width="2.8" height="9" rx=".6" fill="currentColor"/></svg>',
  play: '<svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true"><path d="M3 1.5v9l7.5-4.5z" fill="currentColor"/></svg>',
  prev: '<svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true"><path d="M2 1.5h1.6v9H2zM10.5 1.5v9L4.2 6z" fill="currentColor"/></svg>',
  next: '<svg viewBox="0 0 12 12" width="12" height="12" aria-hidden="true"><path d="M8.4 1.5H10v9H8.4zM1.5 1.5v9L7.8 6z" fill="currentColor"/></svg>',
  cursor: '<svg viewBox="0 0 24 24" width="28" height="28" aria-hidden="true"><path d="M4 2.5l15.5 10.2-6.9 1.2 3.9 7.1-2.9 1.5-3.9-7.1-4.9 4.9z" fill="#fff" stroke="#0B1430" stroke-width="1.6" stroke-linejoin="round"/></svg>',
};
class Corte extends Error {}

export function createFilm(A) {
  let on = false, paused = false, token = 0, ch = -1, voz = false, fin = false;
  const memo = {};
  const S = () => A.S();
  const nuevo = k => NEW[k] ? [`Nuevo · ${NEW[k].t}`, NEW[k].d] : ["Nuevo", ""];

  /* ---------- piezas en pantalla ---------- */
  const el = {};
  function montar() {
    if (el.root) return;
    document.body.insertAdjacentHTML("beforeend", `<div class="film" id="film" aria-live="polite">
      <div class="f-shield" id="fShield" title="Pausar o seguir"></div>
      <div class="f-tag">Prototipo académico · datos simulados</div>
      <div class="f-link" id="fLink"></div><div class="f-dot" id="fDot"></div>
      <div class="f-bubble" id="fBubble" hidden></div>
      <div class="f-cursor" id="fCursor">${ICO.cursor}<i></i></div>
      <div class="f-bottom"><div class="f-subs" id="fSubs"></div>
        <div class="f-bar" role="group" aria-label="Controles del recorrido automático">
          <button data-f="prev" aria-label="Capítulo anterior">${ICO.prev}</button>
          <button data-f="toggle" id="fToggle" aria-label="Pausar">${ICO.pausa}</button>
          <button data-f="next" aria-label="Capítulo siguiente">${ICO.next}</button>
          <div class="f-chaps" id="fChaps"></div>
          <button data-f="voz" id="fVoz" aria-pressed="false" class="f-txt f-desk">Voz</button>
          <button data-f="manual" class="f-txt f-desk">Paso a paso</button>
          <button data-f="salir" class="f-txt">Salir</button>
        </div></div></div>`);
    for (const k of ["root:#film", "shield:#fShield", "link:#fLink", "dot:#fDot", "bubble:#fBubble", "cursor:#fCursor", "subs:#fSubs", "chaps:#fChaps", "toggle:#fToggle", "voz:#fVoz"]) {
      const [n, sel] = k.split(":"); el[n] = $(sel);
    }
    el.root.addEventListener("click", onClick);
    el.voz.hidden = !("speechSynthesis" in window);
  }
  function pintarBarra() {
    el.chaps.innerHTML = CAPS.map((c, k) => `<button class="${k < ch ? "done" : k === ch ? "on" : ""}" data-f-ch="${k}" aria-label="Capítulo ${k + 1}: ${esc(c.t)}" title="${k + 1}. ${esc(c.t)}"></button>`).join("");
    el.toggle.innerHTML = paused ? ICO.play : ICO.pausa;
    el.toggle.setAttribute("aria-label", paused ? "Seguir" : "Pausar");
    el.voz.setAttribute("aria-pressed", voz);
    el.root.classList.toggle("paused", paused);
  }
  // En el escritorio el teléfono se achica para que quepan los subtítulos debajo.
  function encajar() {
    const ph = $(".phone"); if (!ph) return;
    document.body.style.setProperty("--fz", Math.min(1, (innerHeight - 190) / 866).toFixed(3));
  }

  /* ---------- tiempo, pausa y corte ---------- */
  const vivo = k => on && k === token;
  async function puerta(k) {
    while (paused && vivo(k)) await wait(80);
    if (!vivo(k)) throw new Corte();
  }
  async function dormir(ms, k) {
    let falta = ms;
    while (falta > 0) { await puerta(k); const p = Math.min(falta, 100); await wait(p); falta -= p; }
    await puerta(k);
  }
  async function hasta(fn, k, ms = 15000) {
    const t0 = Date.now();
    while (!fn() && Date.now() - t0 < ms) await dormir(80, k);
  }

  /* ---------- voz (opcional) ---------- */
  let hablando = null;
  function decir(texto) {
    if (!voz || !("speechSynthesis" in window)) return null;
    speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(texto.replace(/<[^>]+>/g, ""));
    const v = speechSynthesis.getVoices().find(x => /^es(-|_)(CO|419|MX|US)/i.test(x.lang)) || speechSynthesis.getVoices().find(x => /^es/i.test(x.lang));
    if (v) u.voice = v;
    u.lang = v ? v.lang : "es-CO"; u.rate = 1.04;
    const fin = new Promise(r => { u.onend = r; u.onerror = r; });
    speechSynthesis.speak(u);
    return fin;
  }

  /* ---------- acciones de la película ---------- */
  function enVista(sel) {
    const e = document.querySelector(sel); if (!e) return null;
    const sc = $("#scroll");
    if (sc && sc.contains(e)) {
      const r = e.getBoundingClientRect(), s = sc.getBoundingClientRect();
      if (r.top < s.top + 30 || r.bottom > s.bottom - 90) sc.scrollTo({top: sc.scrollTop + (r.top - s.top) / (s.height / sc.clientHeight) - sc.clientHeight / 3, behavior: "smooth"});
    }
    return e;
  }
  let cx = innerWidth / 2, cy = innerHeight - 160;
  async function mover(x, y, k) {
    const d = Math.hypot(x - cx, y - cy);
    const ms = t(Math.min(1000, 380 + d * 0.9));
    el.cursor.style.transitionDuration = `${ms}ms`;
    el.cursor.style.transform = `translate(${x}px, ${y}px)`;
    cx = x; cy = y;
    await dormir(ms + 60, k);
  }
  function soltarGlobo() {
    el.bubble.hidden = true; el.link.style.opacity = 0; el.dot.style.opacity = 0;
    document.querySelectorAll(".film-target").forEach(e => e.classList.remove("film-target"));
  }
  /** Globo junto al elemento (o, sin elemento, una tarjeta al lado del teléfono). */
  async function globo(sel, titulo, texto, k, extra = "") {
    soltarGlobo();
    let e = sel ? enVista(sel) : null;
    if (sel && !e) return;
    if (e && !e.getClientRects().length) e = null;   // oculto: el globo va como tarjeta
    if (e) { await dormir(t(420), k); e.classList.add("film-target"); }
    el.bubble.innerHTML = `<b>${esc(titulo)}</b>${texto ? `<span>${texto}</span>` : ""}${extra}`;
    el.bubble.hidden = false;
    el.bubble.classList.toggle("card", !e);
    const ph = $(".phone").getBoundingClientRect(), b = el.bubble.getBoundingClientRect();
    const movil = innerWidth <= 760;
    if (!e) {
      const left = movil ? 16 : Math.min(ph.right + 32, innerWidth - b.width - 16);
      const top = movil ? 70 : Math.max(16, ph.top + ph.height * 0.28);
      Object.assign(el.bubble.style, {left: `${left}px`, top: `${top}px`});
      return;
    }
    const r = e.getBoundingClientRect(), mid = r.top + r.height / 2;
    let left, top;
    if (movil) {
      left = 16;
      top = mid < innerHeight / 2 ? Math.min(r.bottom + 14, innerHeight - b.height - 170) : Math.max(60, r.top - b.height - 14);
    } else {
      left = Math.min(ph.right + 36, innerWidth - b.width - 16);
      top = Math.min(Math.max(16, mid - b.height / 2), innerHeight - b.height - 170);
    }
    Object.assign(el.bubble.style, {left: `${left}px`, top: `${top}px`});
    if (!movil) {   // línea del elemento al globo
      const x1 = r.right + 4, y1 = mid, x2 = left, y2 = Math.min(Math.max(top + 22, mid), top + b.height - 22);
      const len = Math.hypot(x2 - x1, y2 - y1), ang = Math.atan2(y2 - y1, x2 - x1);
      Object.assign(el.link.style, {left: `${x1}px`, top: `${y1}px`, width: `${len}px`, transform: `rotate(${ang}rad)`, opacity: 1});
      Object.assign(el.dot.style, {left: `${x1 - 5}px`, top: `${y1 - 5}px`, opacity: 1});
    }
  }
  async function sub(texto, k) {
    el.subs.innerHTML = texto;
    el.subs.classList.remove("in"); void el.subs.offsetWidth; el.subs.classList.add("in");
    const habla = decir(texto);
    const t0 = Date.now();
    await dormir(lectura(texto.replace(/<[^>]+>/g, "")), k);
    if (habla) { while (voz && speechSynthesis.speaking && vivo(k) && Date.now() - t0 < 30000) await dormir(100, k); }
  }
  async function clic(sel, k) {
    const e = enVista(sel); if (!e) throw new Error(`no está ${sel}`);
    await dormir(t(350), k);
    const r = e.getBoundingClientRect();
    await mover(r.left + Math.min(r.width / 2, 120), r.top + r.height / 2, k);
    el.cursor.classList.remove("tap"); void el.cursor.offsetWidth; el.cursor.classList.add("tap");
    await dormir(t(220), k);
    (document.querySelector(sel) || e).click();
    await dormir(t(450), k);
  }

  /* ---------- capítulos (los mismos del recorrido paso a paso) ---------- */
  const has = (ramo, rs) => S().history.some(h => h.ramo === ramo && rs.includes(h.result));
  const probs = ev => Object.fromEntries(((ev && ev.candidates) || []).filter(c => c.prob).map(c => [c.ramo, c.prob.p]));
  const enRaiz = async () => { if (!["home", "explora", "anio", "proteccion"].includes(S().screen)) A.gotoTarget("home"); await wait(200); };
  async function transferirRapido() {   // para entrar directo a los capítulos 5 a 7
    A.gotoTarget("home"); await wait(250); A.go("transfer", {mode: "enviar"}); await wait(300);
    A.pickContact("laura"); await wait(300); A.setAmount(450000); A.go("confirm"); await wait(250); await A.confirmFlow();
  }
  const CAPS = [
    {t: "La app de Lulo, con datos simulados",
      prep: async () => { await A.fresh("sebastian"); A.setHighlight(true); A.gotoTarget("home"); },
      run: async k => {
        const c = S().B.client;
        await sub(`Esta es la app de Lulo, con los datos simulados de ${esc(c.first)}: ${c.age} años, ${esc(c.occupation.toLowerCase())}, en ${esc(c.city)}.`, k);
        await globo('#tabbar [data-t="anio"]', "Lo resaltado en lima es nuevo", "Lo demás es igual a la app real: la navegación no cambia.", k);
        await sub("Lo que agrega el prototipo está resaltado en lima; lo demás es igual a la app de hoy.", k);
      }},
    {t: "Un aviso antes de que venza el SOAT",
      prep: async () => { if (S().cid !== "sebastian" || S().renewed.includes("SOAT")) await A.fresh("sebastian"); A.gotoTarget("home"); },
      run: async k => {
        const days = S().B.car?.days;
        await globo('[data-new="soat-aviso"]', ...nuevo("soat-aviso"), k);
        await sub(`El SOAT de Sebastián vence en ${days} días. Lulo se lo recuerda con la fecha y el valor, también si lo tiene con otra aseguradora.`, k);
        await clic('[data-new="soat-aviso"]', k);
        await hasta(() => S().screen === "renew", k);
      }},
    {t: "Renovar en dos toques",
      prep: async () => { if (S().renewed.includes("SOAT")) await A.fresh("sebastian"); if (S().screen !== "renew") A.openRenew(); await wait(300); },
      run: async k => {
        await globo('[data-a="pay"]', ...nuevo("soat-renovar"), k);
        await sub("Renueva en dos toques y paga desde su Lulo Cuenta: una venta de seguro sin papeleo, con comisión para Lulo.", k);
        await clic('[data-a="pay"]', k);
        await hasta(() => S().screen === "done", k);
        soltarGlobo();
        await sub("Listo. El motor registra la renovación y agenda el aviso del próximo año.", k);
        await clic('[data-a="tab"][data-t="home"]', k);
      }},
    {t: "Una transferencia de todos los meses…",
      prep: async () => { if (S().screen !== "home") A.gotoTarget("home"); await wait(200); },
      run: async k => {
        soltarGlobo();
        await sub("Ahora algo de todos los días: Sebastián le transfiere a Laura, como cada mes.", k);
        await clic('#tabbar [data-a="plus"]', k);
        await hasta(() => $("#plusSheet"), k, 3000);
        await clic('#plusSheet [data-s="transfer"]', k);
        await hasta(() => S().screen === "transfer", k);
        await globo('[data-a="pick-contact"][data-id="laura"]', "Lo que lee el motor", "Transferencias fijas a la misma persona: alguien depende de él.", k);
        await sub("Para el motor esa transferencia fija es una señal: alguien depende de Sebastián.", k);
        await clic('[data-a="pick-contact"][data-id="laura"]', k);
        await hasta(() => S().screen === "amount", k);
        soltarGlobo();
        await clic('[data-a="amt-set"]', k);
        await clic('[data-a="amt-next"]', k);
        await hasta(() => S().screen === "confirm", k);
        await clic('[data-a="confirm"]', k);
        await sub("La transferencia sale como en la app real. Justo después, el motor revisa el evento.", k);
        await hasta(() => (S().shown && S().shown.ramo === "Vida") || has("Vida", ["control", "banner"]), k, 15000);
      }},
    {t: "…dispara una oferta justo a tiempo",
      prep: async () => { if (!(S().shown && S().shown.ramo === "Vida")) await transferirRapido(); await wait(1500); },
      run: async k => {
        await hasta(() => $("#notif").classList.contains("show"), k, 4000);
        const d = S().lastTrace?.decision, pr = d?.prob;
        memo.antes = probs(S().evaluation); memo.apetito = (S().evaluation?.motor?.sesion?.posterior || [0])[0];
        if (!pr) { await sub("El motor decidió ofrecer un seguro de vida.", k); }
        else {
          const base = pr.pasos.find(s => s.k === "base"), mom = pr.pasos.find(s => s.k === "momento");
          await globo("#notif", ...nuevo("push"), k, `<div class="f-num"><em>${pc(pr.p)}</em><small>P(acepta si la ve)<br>valor esperado ${money(d.ev)}</small></div>`);
          await sub(`El motor calculó que Sebastián aceptaría un seguro de vida con <b>${pc(pr.p)}</b> de probabilidad`
            + (mom && base ? `: la transferencia acaba de pasar y el momento la sube de ${pc(base.p)} a ${pc(mom.p)}.` : "."), k);
          await sub(`Le quedaban contactos y no había fatiga, así que va por push. Valor esperado: ${money(d.ev)}.`, k);
        }
        await clic("#notif", k);
        await hasta(() => S().screen === "offer", k);
      }},
    {t: "«Por qué lo ves», con sus datos",
      prep: async () => { if (S().screen !== "offer" || S().offer !== "Vida") { if (S().shown && S().shown.ramo === "Vida") A.openDecision(S().shown); else A.gotoTarget("offer:Vida"); } await wait(500); },
      run: async k => {
        memo.antes = memo.antes || probs(S().evaluation);
        if (memo.apetito === undefined) memo.apetito = (S().evaluation?.motor?.sesion?.posterior || [0])[0];
        await globo(".why", ...nuevo("por-que"), k);
        await sub("La oferta dice de dónde sale, con los datos del cliente. Si no aplica, dice por qué y no se puede activar.", k);
        await sub("Él decide: activar, «ahora no» o no ver más sugerencias de este tipo. Todo queda medido.", k);
        await clic('[data-a="accept"]', k);
        await hasta(() => has("Vida", ["aceptada"]), k, 5000);
      }},
    {t: "El motor aprende de cada respuesta",
      prep: async () => { if (!has("Vida", ["aceptada", "rechazada"])) { if (!(S().shown && S().shown.ramo === "Vida")) await transferirRapido(); A.openDecision(S().shown || {ramo: "Vida"}); await wait(600); A.acceptOffer(); } },
      run: async k => {
        soltarGlobo();
        await A.refreshEval();
        const ses = S().evaluation?.motor?.sesion, despues = probs(S().evaluation);
        const r = Object.keys(despues).find(x => memo.antes && x in memo.antes && x !== "Vida");
        await sub(`Sebastián aceptó. El motor subió su apetito por seguros${ses ? ` de ${(memo.apetito ?? 0).toFixed(2).replace(".", ",")} a ${ses.posterior[0].toFixed(2).replace(".", ",")}` : ""}.`, k);
        if (r) await sub(`Por eso su probabilidad para ${esc(A.title(r))} pasó de ${pc(memo.antes[r])} a <b>${pc(despues[r])}</b>. Con miles de clientes aprende todo el modelo, no solo a la persona.`, k);
      }},
    {t: "Tu protección: todo en un lugar",
      prep: enRaiz,
      run: async k => {
        await clic('#tabbar [data-t="proteccion"]', k);
        await hasta(() => S().screen === "proteccion", k);
        await sub("Una pestaña nueva con todo lo suyo en seguros: lo voluntario aparte de lo que viene con el crédito.", k);
        await globo('[data-new="agendados"]', ...nuevo("agendados"), k);
        await sub("Lo que el motor le sugiere con su porqué, lo que vence y lo agendado: el seguro de desempleo llega cuando complete 6 abonos de nómina.", k);
      }},
    {t: "Tu año en Lulo",
      prep: enRaiz,
      run: async k => {
        soltarGlobo();
        await clic('#tabbar [data-t="anio"]', k);
        await hasta(() => S().screen === "anio", k);
        await globo(".yr-hero", ...nuevo("anio"), k);
        await sub("Doce meses contados como una historia, con los movimientos del cliente.", k);
        await clic('.yr-hero [data-a="st-open"]', k);
        await hasta(() => S().screen === "story", k, 6000);
        soltarGlobo();
        await sub("Cada capítulo tiene un momento de protección que decide el mismo motor: para ti, activo, pronto o no aplica.", k);
        for (let n = 0; n < 3; n++) { await dormir(t(1600), k); if (S().screen === "story") await clic('.st-nav [data-a="st-next"]', k); }
      }},
    {t: "Cómo decide el motor",
      prep: enRaiz,
      run: async k => {
        const L = A.motor()?.laboratorio, s = L && L.escenarios["señal"], b = L && L.escenarios["regla correcta"];
        // El teléfono muestra Explora › Seguros: los ramos marcados «Para ti» por el mismo motor.
        if (S().screen === "story") { await clic('.st-head [data-a="st-close"]', k); await hasta(() => S().screen !== "story", k, 3000); }
        await clic('#tabbar [data-t="explora"]', k);
        await hasta(() => S().screen === "explora", k, 3000);
        if (S().xt !== "seguros") await clic('[data-a="xt"][data-t="seguros"]', k);
        await globo(null, "Cómo decide el motor", "", k, `<div class="f-formula">Valor esperado = <em>P(acepta)</em> × comisión</div><small class="f-src">P sale de los datos de la base: campañas previas, compras después de cada evento y las señales del cliente.</small>`);
        await sub("Para cada seguro que las reglas permiten, el motor calcula la probabilidad de que el cliente acepte y ofrece el de mayor valor esperado.", k);
        if (s && b) await sub(`En un laboratorio con verdad simulada, con respuestas el motor gana <b>${s.frente_a_regla_final >= 0 ? "+" : "−"}${Math.abs(s.frente_a_regla_final * 100).toFixed(0)} %</b> de comisión por oferta frente a la regla; si la regla tenía razón, queda a ${(b.frente_a_regla_final * 100).toFixed(1).replace(".", ",")} %.`, k);
        await sub("Con los datos reales de Lulo se reentrena con un comando, en su propio equipo, y solo cambia lo que mejora fuera de muestra.", k);
      }},
    {t: "Cómo se mide",
      prep: enRaiz,
      run: async k => {
        const p = A.META.models?.piloto?.SOAT;
        await globo(null, "Grupo de control", "", k, `<div class="f-formula">10 % <small>no ve ofertas</small></div><small class="f-src">La diferencia con el resto es el efecto real del motor.</small>`);
        await sub("El 10 % de los clientes no ve ofertas: es el grupo de control, y la diferencia con el resto es el efecto real.", k);
        if (p) await sub(`Para el piloto con la base del banco, ${p.lift_50.toLocaleString("es-CO")} clientes por grupo bastan para detectar un aumento de 50 % en el SOAT.`, k);
      }},
  ];

  /* ---------- reproducir ---------- */
  async function correr(desde, saltando) {
    const k = ++token; fin = false;
    try {
      for (let i = desde; i < CAPS.length; i++) {
        ch = i; pintarBarra();
        const c = CAPS[i];
        if (c.prep && (i === 0 || saltando)) { el.subs.innerHTML = "Preparando…"; await c.prep(); await puerta(k); }
        saltando = false;
        await c.run(k);
        await dormir(t(500), k);
      }
      final(k);
    } catch (e) {
      if (!(e instanceof Corte)) { console.error(e); if (vivo(k)) { A.toast("No se pudo seguir con el recorrido"); salir(); } }
    }
  }
  function final(k) {
    if (!vivo(k)) return;
    fin = true; ch = CAPS.length; pintarBarra(); soltarGlobo();
    el.cursor.style.opacity = 0;
    el.subs.innerHTML = "Fin del recorrido. Ahora explora tú: lo resaltado en lima sigue marcando lo nuevo.";
    globo(null, "¿Y ahora?", "", k, `<div class="f-end"><button data-f="otra">Ver de nuevo</button><button data-f="libre">Explorar por mi cuenta</button><button data-f="scen">Escenarios rápidos</button></div>`).catch(() => {});
  }
  function start(desde = 0) {
    montar(); on = true; paused = false; fin = false;
    document.body.classList.add("filming"); encajar();
    cx = innerWidth / 2; cy = innerHeight - 170;
    el.cursor.style.transitionDuration = "0ms"; el.cursor.style.transform = `translate(${cx}px, ${cy}px)`;
    el.cursor.style.opacity = 1;
    A.onStart();
    correr(desde, desde > 0);
  }
  function salir(despues) {
    if (!on) return;
    on = false; token++; paused = false;
    if ("speechSynthesis" in window) speechSynthesis.cancel();
    soltarGlobo(); el.cursor.style.opacity = 0;
    document.body.classList.remove("filming", "film-paused");
    A.onEnd(despues);
  }
  function togglePausa() {
    if (fin) return;
    paused = !paused;
    if ("speechSynthesis" in window) { if (paused) speechSynthesis.pause(); else speechSynthesis.resume(); }
    document.body.classList.toggle("film-paused", paused);
    pintarBarra();
  }
  function ir(i) {
    if (i < 0 || i >= CAPS.length) return;
    if ("speechSynthesis" in window) speechSynthesis.cancel();
    paused = false; document.body.classList.remove("film-paused"); soltarGlobo();
    correr(i, true);
  }
  function onClick(e) {
    const b = e.target.closest("[data-f], [data-f-ch]");
    if (!b) { if (e.target === el.shield) togglePausa(); return; }
    e.stopPropagation();
    if (b.dataset.fCh) { ir(+b.dataset.fCh); return; }
    const a = b.dataset.f;
    if (a === "toggle") togglePausa();
    else if (a === "prev") ir(Math.max(0, Math.min(ch, CAPS.length) - 1));
    else if (a === "next") ir(ch + 1);
    else if (a === "voz") { voz = !voz; if (!voz && "speechSynthesis" in window) speechSynthesis.cancel(); pintarBarra(); }
    else if (a === "manual") { const i = Math.min(ch, CAPS.length - 1); salir({manual: i}); }
    else if (a === "salir") salir();
    else if (a === "otra") ir(0);
    else if (a === "libre") salir({libre: true});
    else if (a === "scen") salir({scen: true});
  }
  addEventListener("keydown", e => {
    if (!on || e.target.matches("input, textarea, select")) return;
    const accion = {" ": togglePausa, Escape: () => salir(), ArrowRight: () => ir(ch + 1), ArrowLeft: () => ir(Math.max(0, ch - 1))}[e.key];
    if (accion) { e.preventDefault(); e.stopPropagation(); accion(); }   // que no llegue también a la app (Tu año usa ← →)
  }, true);
  addEventListener("resize", () => { if (on) encajar(); });
  return {start, salir, active: () => on, chapters: CAPS.length};
}
