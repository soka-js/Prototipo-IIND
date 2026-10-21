// Recorrido guiado: once pasos con Sebastián que muestran qué es nuevo, qué tocar y por qué le sirve a Lulo.
// Cada paso prepara el teléfono, resalta lo que hay que tocar, avanza solo cuando el cliente lo hace y tiene
// «Hazlo por mí». Lo usa app.js con un objeto A que expone el estado y las acciones de la app. La tarjeta del paso
// va en la guía al lado del teléfono (A.card) y, en el celular, una versión corta dentro del teléfono (#coach).
// Opción automática: el recorrido se reproduce solo (lee, hace el paso y sigue), con pausa; nadie tiene que tocar
// nada. ?ritmo=0.5 lo acelera y ?ritmo=1.5 lo hace más lento (las pruebas usan un ritmo rápido).
import { esc, money, wait } from "./util.js";
import { pc, probSteps } from "./aprende.js";

const has = (S, ramo, results) => S.history.some(h => h.ramo === ramo && results.includes(h.result));
const RITMO = Math.min(3, Math.max(0.05, +new URLSearchParams(location.search).get("ritmo") || 1));
const pausa = ms => Math.max(350, ms * RITMO);
const ICO = {
  pausa: '<svg viewBox="0 0 12 12" width="11" height="11" aria-hidden="true"><rect x="2" y="1.5" width="2.8" height="9" rx=".6" fill="currentColor"/><rect x="7.2" y="1.5" width="2.8" height="9" rx=".6" fill="currentColor"/></svg>',
  play: '<svg viewBox="0 0 12 12" width="11" height="11" aria-hidden="true"><path d="M3 1.5v9l7.5-4.5z" fill="currentColor"/></svg>',
};
const probs = ev => Object.fromEntries(((ev && ev.candidates) || []).filter(c => c.prob).map(c => [c.ramo, c.prob.p]));

export function createTour(A) {
  let i = -1, active = false, busy = false, advancing = false;
  let play = false, paused = false, seq = 0, timer = null, sched = null;   // modo automático
  const memo = {};
  const STEPS = [
    {k: "Igual a la app de Lulo", t: "Esta es la app de Lulo, con datos simulados",
      d: () => { const c = A.S().B.client; return `${esc(c.first)} tiene ${c.age} años, es ${esc(c.occupation.toLowerCase())} y vive en ${esc(c.city)}. Su Home es el de la app real: saldo, carrusel, Bolsillos Flex y mapa de cajeros. <b>Lo que el prototipo agrega está resaltado en lima</b>; lo demás es igual a la app.`; },
      lulo: "Nada cambia en la navegación: las ideas viven dentro de pantallas que el cliente ya usa.",
      hint: "Mira el Home y sigue cuando quieras.",
      setup: async () => { await A.fresh("sebastian"); A.setHighlight(true); A.gotoTarget("home"); }},
    {k: "Nuevo · Futuro", t: "Un aviso antes de que venza el SOAT",
      d: () => `El SOAT de Sebastián vence en ${A.S().B.car?.days ?? 27} días. Lulo se lo recuerda con la fecha y el valor. Si lo tuviera con otra aseguradora y lo pagara desde Lulo, también lo vería.`,
      lulo: "Captura de canal: el SOAT se compra hoy fuera del banco; este aviso lo trae a la app.",
      hint: "Toca el aviso «Tu SOAT vence…» en el Home.",
      target: ".reminder", done: S => S.screen === "renew" || S.renewed.includes("SOAT"),
      auto: async () => A.openRenew()},
    {k: "Nuevo · Futuro", t: "Renovar en dos toques",
      d: () => "Nueva vigencia, descuento por renovar antes (hipótesis por validar: la tarifa del SOAT es regulada) y pago desde la Lulo Cuenta. Al pagar, el motor registra la renovación y agenda el aviso del próximo año.",
      lulo: "Una venta de seguro sin papeleo, dentro de la app y con la comisión para Lulo.",
      hint: "Toca «Pagar».",
      target: '[data-a="pay"]', done: S => S.screen === "done" || S.renewed.includes("SOAT"),
      auto: async () => { if (A.S().screen !== "renew") A.openRenew(); await wait(500); A.pay(); }},
    {k: "Nuevo · Presente", t: "Una transferencia de todos los meses…",
      d: () => "Sebastián le transfiere a Laura cada mes. Para el motor eso es una señal: alguien depende de él. Haz la transferencia como en la app real y mira qué pasa después del comprobante.",
      lulo: "El momento lo da lo que el cliente hace, no un calendario de campañas.",
      hint: "Transferir plata → Laura (marcada «fija») → monto → Transferir.",
      setup: async () => { A.gotoTarget("home"); await wait(250); A.go("transfer", {mode: "enviar"}); },
      target: S => ({transfer: '[data-a="pick-contact"][data-id="laura"]', amount: '[data-a="amt-next"]', confirm: '[data-a="confirm"]'}[S.screen] || null),
      done: S => (S.shown && S.shown.ramo === "Vida") || (S.banner && S.banner.ramo === "Vida") || has(S, "Vida", ["control"]),
      auto: async () => {
        const S = A.S();
        if (S.screen !== "transfer" && S.screen !== "amount" && S.screen !== "confirm") { A.go("transfer", {mode: "enviar"}); await wait(400); }
        if (A.S().screen === "transfer") { A.pickContact("laura"); await wait(450); }
        if (A.S().screen === "amount") { A.setAmount(450000); await wait(450); A.go("confirm"); await wait(450); }
        if (A.S().screen === "confirm") await A.confirmFlow();
      }},
    {k: "Nuevo · Presente", t: "…dispara una oferta justo a tiempo",
      d: () => {
        const ev = A.S().lastTrace, d = ev && ev.decision;
        if (!d) return "El motor está decidiendo…";
        return `El motor leyó la transferencia y calculó la probabilidad de que Sebastián acepte un seguro de vida si ve la oferta: <b>${pc(d.prob.p)}</b> (entre ${pc(d.prob.ic90[0])} y ${pc(d.prob.ic90[1])}). Así sale ese número:${probSteps(d.prob, {compact: true})}Como le quedaban contactos y no había fatiga, la envió por ${ev.outcome === "shown" ? "push" : "banner"}. Valor esperado: ${money(d.ev)}.`;
      },
      lulo: "Cada decisión queda registrada con su probabilidad, su versión de reglas y su grupo: así se mide qué momento vende.",
      hint: "Toca la notificación de Lulo (o búscala en Alertas).",
      target: S => S.shown ? "#notif" : ".promo.offer", done: S => S.screen === "offer" && S.offer === "Vida",
      auto: async () => { const S = A.S(); A.openDecision(S.shown || S.banner || {ramo: "Vida", kind: "nuevo"}); }},
    {k: "Nuevo · Presente", t: "«Por qué lo ves», con sus datos",
      d: () => "La oferta explica de dónde sale, con los datos del cliente; si no aplica, dice por qué y no se puede activar. El cliente decide: activar, «Ahora no» (espera 30 días) o pedir no ver más sugerencias de ese tipo, que también se mide.",
      lulo: "Transparencia y control del cliente (Ley 1581): más confianza y menos quejas.",
      hint: "Elige «Activar seguro» o «Ahora no».",
      setup: async () => { memo.before = probs(A.S().evaluation); memo.apetito = (A.S().evaluation?.motor?.sesion?.posterior || [0])[0]; },
      target: ".why", done: S => has(S, "Vida", ["aceptada", "rechazada"]),
      auto: async () => A.acceptOffer()},
    {k: "Nuevo · Motor", t: "El motor aprende de cada respuesta",
      d: () => {
        const S = A.S(), ses = S.evaluation?.motor?.sesion, after = probs(S.evaluation);
        const yes = has(S, "Vida", ["aceptada"]);
        const r = Object.keys(after).find(k => memo.before && k in memo.before && k !== "Vida");
        const cambio = r ? ` Su probabilidad para ${esc(A.title(r))} pasó de ${pc(memo.before[r])} a <b>${pc(after[r])}</b>.` : "";
        const ap = ses ? `de ${(memo.apetito ?? 0).toFixed(2).replace(".", ",")} a <b>${ses.posterior[0] >= 0 ? "+" : ""}${ses.posterior[0].toFixed(2).replace(".", ",")}</b>` : "";
        if (!has(S, "Vida", ["aceptada", "rechazada"])) return "La oferta quedó sin respuesta. Cuando el cliente acepta o dice «ahora no», el motor actualiza su apetito por seguros y las probabilidades de los demás seguros: vuelve al paso anterior y pruébalo.";
        return yes ? `Sebastián aceptó. El motor subió su apetito por seguros ${ap}.${cambio} Aceptar enseña bastante porque casi todos rechazan.`
          : `Sebastián dijo «ahora no». El motor bajó su apetito por seguros ${ap}: un rechazo enseña poco cuando casi todos rechazan.${cambio} Y no le repetirá Vida en 30 días.`;
      },
      lulo: "Con respuestas de miles de clientes aprende todo el modelo, no solo a la persona: el laboratorio de la documentación del motor muestra cuánto mejora.",
      hint: "Sigue cuando quieras.",
      setup: async () => { await A.refreshEval(); }},
    {k: "Nuevo", t: "Tu protección: todo en un lugar",
      d: () => "Lo que tiene con Lulo (separando lo voluntario de lo que viene con el crédito), lo que le sugiere el motor con su porqué, lo que vence, lo que paga por fuera, lo que está agendado y por qué no le ofrecemos lo demás. Sebastián ve, por ejemplo, que el seguro de desempleo llega cuando complete 6 abonos de nómina.",
      lulo: "Una pestaña que vende sin presionar: el cliente ve que cada sugerencia tiene razones.",
      hint: "Recorre la pestaña Protección (desliza hacia abajo).",
      setup: async () => { A.tabTo("proteccion"); },
      target: () => '[data-new="agendados"]'},
    {k: "Nuevo · Pasado", t: "Tu año en Lulo",
      d: () => "Doce meses contados como una historia con los movimientos del cliente. Cada capítulo tiene un momento de protección que decide el mismo motor: para ti, activo, pronto («te faltan 3 abonos») o no aplica.",
      lulo: "Una razón para abrir la app que termina en una oferta oportuna, y se mide qué capítulo convierte.",
      hint: "Toca «Ver mi año» y avanza tocando a la derecha.",
      setup: async () => { A.tabTo("anio"); },
      target: S => S.screen === "anio" ? ".yr-hero .btn" : null, done: S => S.screen === "story" || S.screen === "yearLoading",
      auto: async () => A.openStory(0), stay: true,
      // En automático, además pasa unos capítulos para que se vea la historia.
      play: async sigue => { for (let k = 0; k < 3; k++) { await wait(pausa(2800)); if (!sigue()) return; A.storyNext(); } await wait(pausa(2000)); }},
    {k: "Detrás de cámaras", t: "Cómo decide el motor (no es una regla fija)",
      d: () => {
        const L = A.motor()?.laboratorio, s = L && L.escenarios["señal"], b = L && L.escenarios["regla correcta"];
        return `Para cada seguro que las reglas permiten (autorización, elegibilidad, capacidad de pago, tope de contactos), el motor calcula P(acepta) con lo que dicen los datos de la base: campañas previas, compras externas después de cada evento y las señales del cliente. Ofrece el de mayor valor esperado y aprende de cada respuesta.${s ? ` En un laboratorio con verdad simulada sobre los clientes de la base, con respuestas el motor gana <b>${s.frente_a_regla_final >= 0 ? "+" : "−"}${Math.abs(s.frente_a_regla_final * 100).toFixed(0)} %</b> de comisión por oferta frente a la regla, y si la regla tenía razón queda a ${(b.frente_a_regla_final * 100).toFixed(1).replace(".", ",")} %.` : ""}`;
      },
      lulo: "Con los datos reales de Lulo se reentrena con un comando, en su propio equipo, y solo cambia lo que mejora fuera de muestra.",
      hint: "El detalle (datos, fórmulas y laboratorio) está en la documentación del motor.",
      links: [["https://github.com/soka-js/Prototipo-IIND/blob/main/docs/MOTOR.md", "Cómo funciona el motor"]]},
    {k: "Cómo se mide", t: "Grupo de control y siguiente paso",
      d: () => {
        const p = A.META.models?.piloto?.SOAT;
        return `El 10 % de los clientes no ve ofertas: es el grupo de control, y la diferencia con el resto es el efecto real del motor. Otro 10 % explora opciones en las que el motor todavía duda.${p ? ` Para el piloto con la base completa del banco, ${p.lift_50.toLocaleString("es-CO")} clientes por grupo bastan para detectar un aumento de 50 % en el SOAT (modelo M6).` : ""} Ahora explora tú: cambia de personaje arriba o prueba un escenario rápido.`;
      },
      lulo: "Un piloto medible: si el motor no supera al control, se sabe rápido y sin riesgo.",
      hint: "Fin del recorrido: lo resaltado en lima sigue marcando lo nuevo."},
  ];

  const step = () => STEPS[i];
  // Un paso está pendiente mientras espera que el cliente haga algo en el teléfono.
  const pending = st => !!(st.done && st.auto && !memo[`ok${i}`] && !st.done(A.S()));
  const targetOf = st => typeof st.target === "function" ? st.target(A.S()) : st.target;
  // En automático la pista dice qué está pasando; paso a paso, qué tocar.
  const hintOf = st => !play ? st.hint : paused ? "En pausa: toca «Seguir» para continuar."
    : busy ? "Automático: haciendo el paso en el teléfono…" : "Automático: sigue solo en unos segundos.";

  async function goTo(k) {
    if (busy) return;
    busy = true; advancing = false; seq++; clearTimeout(timer); sched = null;
    i = k; const st = step();
    delete memo[`ok${i}`];
    paint();
    try { if (st.setup) await st.setup(); } catch (e) { console.error(e); }
    busy = false;
    paint(); decorate(); tick();
    if (play && !paused && active) schedule();
  }
  /** `auto`: se reproduce solo (lee, hace el paso y sigue). Sin él, el cliente avanza a su ritmo. */
  function start(auto = false) {
    play = auto; paused = false;
    active = true; document.body.classList.add("touring"); A.showTour(); goTo(0);
  }
  /** `next`: al terminar se abren los escenarios rápidos (al salir a mitad del recorrido, no). */
  function finish(next = true) {
    play = false; paused = false; clearTimeout(timer); sched = null;
    active = false; i = -1; document.body.classList.remove("touring"); decorate(); A.setHighlight(true); paint();
    A.endTour(next);
    A.toast("Recorrido terminado: ahora explora a tu ritmo");
  }

  /* ---------- modo automático ---------- */
  // Tiempo de lectura del paso: ~35 ms por carácter del texto, entre 5,5 y 15 s (por el ritmo).
  const lectura = st => pausa(Math.min(15000, Math.max(5500, 2500 + (st.d() + st.lulo).replace(/<[^>]+>/g, "").length * 35)));
  function schedule() {
    clearTimeout(timer);
    const s = seq, ms = lectura(step());
    sched = {start: Date.now(), ms};
    paint();
    timer = setTimeout(() => autoAdvance(s), ms);
  }
  const vigente = s => s === seq && active && play && !paused;
  async function autoAdvance(s) {
    if (!vigente(s)) return;
    if (busy) { timer = setTimeout(() => autoAdvance(s), 500); return; }   // espera a que termine lo que está haciendo
    sched = null;
    const st = step();
    if (pending(st)) { await doIt(); await wait(pausa(1500)); if (!vigente(s)) return; }
    if (st.play) { await st.play(() => vigente(s)); if (!vigente(s)) return; }
    if (!advancing) next();
  }
  function autoplay() { if (!active) { start(true); return; } play = true; paused = false; schedule(); }
  function pause() { paused = true; clearTimeout(timer); sched = null; paint(); }
  function resume() { paused = false; if (active && play) schedule(); }
  function manual() { play = false; paused = false; clearTimeout(timer); sched = null; paint(); }
  function next() { if (!active || busy) return; if (i < STEPS.length - 1) goTo(i + 1); else finish(true); }
  function prev() { if (!active || busy || i <= 0) return; goTo(i - 1); }
  async function doIt() {
    const st = step(); if (!st || !st.auto || busy) return;
    busy = true; paint();
    try { await st.auto(); } catch (e) { console.error(e); A.toast("No se pudo hacer este paso"); }
    busy = false; paint(); tick();
  }
  /** Después de cada render: resalta el objetivo del paso dentro del teléfono. */
  function decorate() {
    document.querySelectorAll(".tour-target").forEach(e => e.classList.remove("tour-target"));
    if (!active || i < 0) return;
    const sel = targetOf(step());
    const el = sel && document.querySelector(`#phone ${sel}`);
    if (!el) return;
    el.classList.add("tour-target");
    const sc = document.querySelector("#scroll");
    if (sc && sc.contains(el)) {
      const r = el.getBoundingClientRect(), s = sc.getBoundingClientRect();
      if (r.top < s.top + 40 || r.bottom > s.bottom - 90) sc.scrollTo({top: sc.scrollTop + r.top - s.top - s.height / 3, behavior: "smooth"});
    }
  }
  /** Avanza solo cuando el cliente hizo lo que pedía el paso. */
  function tick() {
    if (!active || busy || advancing || i < 0) return;
    const st = step();
    paint();
    if (st.done && !memo[`ok${i}`] && st.done(A.S())) {
      if (st.stay) { memo[`ok${i}`] = true; paint(); return; }
      advancing = true;
      setTimeout(() => { if (active && step() === st) next(); }, 900);
    }
  }

  function card(st) {
    const tgt = targetOf(st);
    return `<div class="tour-card" aria-busy="${busy}"><div class="tour-top"><span class="tour-k">${esc(st.k)}</span><span class="tour-n">Paso ${i + 1} de ${STEPS.length}</span><button class="g-x g-hide" data-sheet="close" aria-label="Ocultar la explicación">✕</button></div>
      <div class="tour-prog">${STEPS.map((_, k) => `<i class="${k < i ? "done" : k === i ? "on" : ""}"></i>`).join("")}</div>
      <h3>${esc(st.t)}</h3><div class="tour-d">${st.d()}</div>
      <div class="tour-lulo"><b>Por qué le sirve a Lulo</b>${esc(st.lulo)}</div>
      <div class="tour-hint">${!play && (tgt || st.done) ? "👉 " : ""}${esc(hintOf(st))}</div>
      ${play && sched ? `<div class="tour-timer" aria-hidden="true"><i style="animation-duration:${sched.ms}ms;animation-delay:-${Date.now() - sched.start}ms"></i></div>` : ""}
      ${st.links ? `<div class="ctrls">${st.links.map(([h, l]) => `<a class="pbtn" href="${h}" target="_blank" rel="noopener">${esc(l)} ↗</a>`).join("")}</div>` : ""}
      <div class="tour-acts">${play ? `<button class="pbtn" data-tour="${paused ? "resume" : "pause"}">${paused ? `${ICO.play} Seguir` : `${ICO.pausa} Pausar`}</button>`
          : pending(st) ? `<button class="pbtn" data-tour="auto">Hazlo por mí</button>` : ""}
        <button class="pbtn lime" data-tour="next">${i === STEPS.length - 1 ? "Terminar" : pending(st) && !play ? "Saltar" : "Siguiente"}</button></div>
      <div class="tour-sub"><button data-tour="prev" ${i === 0 ? "disabled" : ""}>Anterior</button>
        ${play ? `<button data-tour="manual">Paso a paso</button>` : `<button data-tour="play">${ICO.play} Que se reproduzca solo</button>`}
        <button data-tour="stop">Salir</button></div></div>`;
  }
  function paint() {
    const v = A.card();
    if (v) v.innerHTML = active && i >= 0 ? card(step()) : "";
    const m = document.querySelector("#coach");
    if (m) {
      m.hidden = !(active && i >= 0);
      if (!m.hidden) {
        const st = step();
        m.innerHTML = `<div class="tour-top"><span class="tour-k">${esc(st.k)} · ${i + 1}/${STEPS.length}</span><button class="coach-x" data-tour="stop" aria-label="Salir del recorrido">✕</button></div>
          <b>${esc(st.t)}</b><p>${esc(hintOf(st))}</p><div class="tour-acts"><button class="pbtn sm" data-tour="more">Ver explicación</button>${play ? `<button class="pbtn sm" data-tour="${paused ? "resume" : "pause"}">${paused ? `${ICO.play} Seguir` : `${ICO.pausa} Pausar`}</button>` : pending(st) ? `<button class="pbtn sm" data-tour="auto">Hazlo por mí</button>` : ""}<button class="pbtn sm lime" data-tour="next">${i === STEPS.length - 1 ? "Terminar" : pending(st) && !play ? "Saltar" : "Siguiente"}</button></div>`;
      }
    }
    const how = document.querySelector("#how");
    if (how) how.innerHTML = active && i >= 0 ? `<b>Paso ${i + 1} de ${STEPS.length}:</b> ${esc(hintOf(step()))}` : how.dataset.base;
  }
  function onClick(e) {
    const b = e.target.closest("[data-tour]");
    if (b) {
      const a = b.dataset.tour;
      if (a === "start") start(false); else if (a === "play") autoplay(); else if (a === "next") next(); else if (a === "prev") prev();
      else if (a === "auto") doIt(); else if (a === "stop") finish(false); else if (a === "more") A.showTour(true);
      else if (a === "pause") pause(); else if (a === "resume") resume(); else if (a === "manual") manual();
      return true;
    }
    return false;
  }
  return {start, autoplay, next, prev, finish, decorate, tick, paint, onClick, active: () => active};
}
