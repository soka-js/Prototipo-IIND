// Pantallas del teléfono. Cada una es una función pura: recibe el estado y devuelve HTML.
import { I } from "./icons.js";
import { addDays, dateLong, dateShort, dayLabel, esc, initials, money, num } from "./util.js";

/* ---------- modelo compartido ---------- */
export const hasPolicy = (S, k) => S.policies.some(p => p.offer === k);
export const acceptedOffers = S => S.policies.filter(p => p.id.endsWith("-new")).map(p => p.offer);
export const unreadCount = S => S.notifs.filter(n => n.unread).length;
export const chapters = S => S.B.chapters;
export const allMovs = S => [...S.sessionMovs, ...S.B.recent];
export const quote = S => S.B.car.quotes[S.alertDays];
export function protections(S) {
  return S.policies.filter(p => p.status === "ok").map(p => p.title.replace(/ · [A-Z]{3}-\d{3}$/, ""));
}
export function creditCuota(amount, n, rate = 0.0179) {
  return Math.round(amount * rate / (1 - Math.pow(1 + rate, -n)));
}

/* ---------- piezas ---------- */
const topbar = (title, opts = {}) => `<div class="topbar"><button class="back" data-a="back" aria-label="Volver">${opts.close ? I.close : I.back}</button><h2>${title}</h2>${opts.right || ""}</div>`;
const anno = (title, body) => `<div class="anno"><div class="anno-k">${I.info} ${title}</div>${body}</div>`;
export const avatar = (name, color, cls = "") => `<span class="av ${cls}" style="background:${color || "var(--navy-3)"};${color ? "color:var(--ink)" : ""}">${esc(initials(name))}</span>`;

export function movRow(m, today, withTime = false) {
  return `<button class="mov${m.flash ? " flash" : ""}" data-a="mov" data-id="${m.id}"><span class="ic">${m.ic}</span><span class="t"><span>${esc(m.n)}</span><span>${esc(m.c)} · ${withTime ? m.time : dayLabel(m.date, today)}</span></span><span class="a ${m.a > 0 ? "in" : ""}">${m.a > 0 ? "+" : ""}${money(m.a)}</span></button>`;
}
export function movListHTML(items, today) {
  let out = "", last = "";
  for (const m of items) {
    if (m.date !== last) { out += `<div class="day-h">${dayLabel(m.date, today)}</div>`; last = m.date; }
    out += movRow(m, today, true);
  }
  return out;
}
export const skeletonRows = n => Array.from({length: n}, () => `<div class="mov sk"><span class="ic"></span><span class="t"><span></span><span></span></span><span class="a"></span></div>`).join("");

export function cardHTML(S, big = false) {
  const c = S.B.client;
  return `<div class="lcard${big ? " big" : ""}${S.cardFrozen ? " frozen" : ""}">
    <span class="lc-top">debit <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M8 8a6 6 0 0 1 0 8M12 5.5a10 10 0 0 1 0 13M16 3a14 14 0 0 1 0 18"/></svg></span>
    <span class="lc-chip"></span><span class="lc-logo" role="img" aria-label="Lulo Bank"></span>
    <span class="lc-name">${esc(c.card_name)}</span>${big ? `<span class="lc-num">•••• •••• •••• ${c.card_last4}</span>` : ""}
    <span class="lc-mc"><i></i><i></i></span>${S.cardFrozen ? `<span class="lc-frozen">${I.snow} Congelada</span>` : ""}
  </div>`;
}

function keypad() {
  const keys = ["1","2","3","4","5","6","7","8","9","000","0","del"];
  return `<div class="keypad">${keys.map(k => `<button data-a="key" data-k="${k}" aria-label="${k === "del" ? "Borrar" : k}">${k === "del" ? I.del : k}</button>`).join("")}</div>`;
}

function soatReminder(S) {
  const car = S.B.car;
  if (!car || S.soatRenewed || !S.remind) return "";
  const [, m, d] = car.soat_expiry.split("-");
  const mon = ["ENE","FEB","MAR","ABR","MAY","JUN","JUL","AGO","SEP","OCT","NOV","DIC"][+m - 1];
  if (car.days <= S.alertDays) {
    return `<button class="reminder${car.days <= 10 ? " urgent" : ""}" data-a="go" data-s="renew">
      <span class="cal"><b>${+d}</b><small>${mon}</small></span>
      <span style="flex:1"><span class="rm-t">Tu SOAT vence en ${car.days} días</span><span class="rm-d">${car.plate} · ${car.days <= 10 ? "Evita la multa: renuévalo hoy aquí" : "Renuévalo aquí con descuento por anticipación"}</span></span>
    </button>`;
  }
  return `<button class="reminder soft" data-a="go" data-s="renew">
      <span class="cal"><b>${+d}</b><small>${mon}</small></span>
      <span style="flex:1"><span class="rm-t">Tu SOAT vence el ${dateShort(car.soat_expiry)}</span><span class="rm-d">Te avisaremos el ${dateShort(addDays(car.soat_expiry, -S.alertDays))}, ${S.alertDays} días antes.</span></span>
    </button>`;
}

function protectBlock(S, c) {
  if (c.soat) {
    if (S.soatRenewed) return `<div class="st-protect"><div class="st-pk">Momento de protección</div><div class="st-pt">Tu SOAT ya está al día</div><div class="st-pd">Vigente hasta el ${S.B.car.new_to_long}.</div></div>`;
    if (S.control || !S.sugg) return "";
    return `<div class="st-protect"><div class="st-pk">Momento de protección</div><div class="st-pt">Tu SOAT vence el ${dateShort(S.B.car.soat_expiry)}</div><div class="st-pd">Renuévalo aquí sin salir de Lulo, con descuento por anticipación.</div><div class="st-pb"><button class="btn primary" data-a="st-soat">Renovar ahora</button></div></div>`;
  }
  if (c.ask) {
    if (S.known[c.ask]) return `<div class="st-protect"><div class="st-pd">Gracias por responder.</div></div>`;
    return `<div class="st-protect"><div class="st-pt">¿Sabías que tenías esta protección?</div><div class="q-btns"><button data-a="known" data-v="Sí">Sí, lo sabía</button><button data-a="known" data-v="No">No sabía</button></div></div>`;
  }
  if (!c.protect) return "";
  const k = c.protect.key, O = S.B.offers[k];
  if (hasPolicy(S, k)) return `<div class="st-protect"><div class="st-pk">${I.shield} Momento de protección</div><div class="st-pt">Ya lo tienes activo</div><div class="st-pd">${O.title} con ${O.aliado}.</div></div>`;
  if (S.control || !S.sugg) return "";
  if (S.declined[k]) return `<div class="st-protect"><div class="st-pd">Entendido. No te lo mostraremos en este resumen.</div></div>`;
  return `<div class="st-protect"><div class="st-pk">Momento de protección${c.protect.concept ? ` <span class="pill hyp">Producto por negociar</span>` : ""}</div><div class="st-pt">${c.protect.t}</div><div class="st-pd">${c.protect.d}</div><div class="st-pb"><button class="btn primary" data-a="st-yes" data-k="${k}">Activar</button><button class="btn ghost" data-a="st-no" data-k="${k}">Ahora no</button></div></div>`;
}

function storyBody(S, c) {
  if (c.id === "cierre") {
    const has = protections(S);
    const left = chapters(S).filter(x => x.protect && !hasPolicy(S, x.protect.key)).map(x => S.B.offers[x.protect.key].title);
    return `<div class="st-kick">${c.kicker}</div><div class="st-big">${has.length}</div><div class="st-line">${has.length === 1 ? "protección activa" : "protecciones activas"} al cerrar tu año</div>
      <div class="st-list">${has.map(h => `<span>${h}</span>`).join("")}</div>
      ${left.length ? `<p class="st-sub">Te quedan por revisar: ${left.join(", ")}.</p>` : `<p class="st-sub">Cubriste todos los momentos que encontramos este año.</p>`}
      <div class="st-acts"><button class="btn primary dark" data-a="st-share">Compartir mi año</button><button class="btn ghost" data-a="st-close">Cerrar</button></div>`;
  }
  const v = c.viz || {};
  let out = `<div class="st-kick">${c.kicker}</div>`;
  if (v.type === "dots") out += `<div class="st-dots${v.n > 6 ? " sm" : ""}">${"<i></i>".repeat(v.n)}</div>`;
  out += c.stats.length > 1
    ? `<div class="st-two">${c.stats.map(s => `<div><div class="st-big">${s.big}</div><div class="st-line">${s.line}</div></div>`).join("")}</div>`
    : `<div class="st-big${c.stats[0].big.length > 6 ? " md" : ""}">${c.stats[0].big}</div><div class="st-line">${c.stats[0].line}</div>`;
  if (v.type === "bars") out += `<div class="st-bars">${v.items.map(b => `<div><i style="height:${Math.max(3, b.v)}%;${b.hi ? "background:var(--lime)" : ""}"></i><span>${b.l}</span></div>`).join("")}</div>`;
  if (v.type === "rank") out += `<ol class="st-rank">${v.items.map(r => `<li><span>${esc(r.l)}</span><b>${r.v}</b></li>`).join("")}</ol>`;
  if (v.type === "chips") out += `<div class="st-list">${v.items.map(x => `<span>${esc(x)}</span>`).join("")}</div>`;
  if (c.sub) out += `<p class="st-sub">${c.sub}</p>`;
  if (c.hint) out += `<div class="st-hint">${c.hint}</div>`;
  return out;
}

const lowerFirst = s => s.charAt(0).toLowerCase() + s.slice(1);
const flowTitle = {transfer: "Enviar dinero", cajita: "Abonar a tu cajita", cuota: "Pagar cuota", desembolso: "Solicitar crédito"};

/* ---------- pantallas ---------- */
export const SCREENS = {
  lock(S) {
    const c = S.B.client;
    return `<div class="lock">
      ${avatar(c.full, c.color, "xl")}
      <div class="lock-hi">Hola, ${esc(c.first)}</div>
      <div class="lock-sub">Ingresa tu clave de 4 dígitos</div>
      <div class="pin">${[0,1,2,3].map(i => `<i class="${i < S.pin.length ? "on" : ""}"></i>`).join("")}</div>
      ${keypad().replace('data-k="000"', 'data-k="bio"').replace('>000<', `>${I.face}<`).replace('aria-label="000"', 'aria-label="Ingresar con Face ID"')}
      <button class="btn text" data-a="unlock">Ingresar con Face ID</button>
      <div class="lock-foot">Prototipo: cualquier clave funciona</div>
    </div>`;
  },

  home(S) {
    const c = S.B.client, n = unreadCount(S), movs = allMovs(S).slice(0, 4);
    return `
    <div class="hello"><div><div class="sub" style="margin:0">Buenos días</div><div class="hi">Hola, ${esc(c.first)}</div></div>
      <div class="hello-r"><button class="icon-btn" data-a="go" data-s="notifs" aria-label="Notificaciones">${I.bell}${n ? `<b class="badge">${n}</b>` : ""}</button>
      <button class="av-btn" data-a="tab" data-t="perfil" aria-label="Perfil">${avatar(c.full, c.color)}</button></div></div>
    <div class="balance"><div class="sub row-i">Saldo disponible <button class="eye" data-a="hide" aria-label="${S.hide ? "Mostrar saldo" : "Ocultar saldo"}">${S.hide ? I.eyeOff : I.eye}</button></div>
      <div class="n">${S.hide ? "$ ••••••" : money(S.balance)}</div></div>
    <button class="card-btn" data-a="go" data-s="card" aria-label="Ver tarjeta">${cardHTML(S)}</button>
    <div class="quick">
      <button data-a="go" data-s="transfer" data-p="enviar"><span class="ic">${I.send}</span>Enviar</button>
      <button data-a="go" data-s="transfer" data-p="breb"><span class="ic">${I.bre}</span>Bre-B</button>
      <button data-a="go" data-s="cajitas"><span class="ic">${I.box}</span>Cajitas</button>
      <button data-a="go" data-s="credito"><span class="ic">${I.coin}</span>Crédito</button>
    </div>
    ${soatReminder(S)}
    <button class="home-year" data-a="tab" data-t="anio"><span class="yy">12m</span><span style="flex:1"><span class="rm-t">Tu año en Lulo ya está listo</span><span class="rm-d" style="color:var(--mist)">${num(S.B.movCount)} movimientos contados en ${chapters(S).length} capítulos</span></span>${I.chev}</button>
    <div class="sec-row"><span>Últimos movimientos</span><button data-a="tab" data-t="movs">Ver todos</button></div>
    ${movs.map(m => movRow(m, S.B.today)).join("")}
    <div style="height:18px"></div>`;
  },

  movs(S) {
    return `<div class="pad" style="padding-top:8px"><h2 class="h-big">Movimientos</h2></div>
    <label class="searchbox">${I.search}<input data-in="search" type="search" placeholder="Busca un comercio o categoría" value="${esc(S.mq)}" autocomplete="off"></label>
    <div class="chips" role="group" aria-label="Filtrar por tipo">${S.B.groups.map(([k, l]) => `<button data-a="grp" data-g="${k}" aria-pressed="${S.mg === k}">${l}</button>`).join("")}</div>
    <div class="mov-sum" id="movSum"></div>
    <div id="movList">${skeletonRows(8)}</div>
    <div id="movMore" class="mov-more"></div>`;
  },

  mov(S) {
    const D = S.detail;
    if (!D || D.loading) return `${topbar("Detalle")}<div class="det-hero"><span class="det-ic sk"></span><div class="sk-line w60"></div><div class="sk-line w40"></div></div>`;
    const t = D.tx, sig = D.signal;
    return `${topbar("Detalle")}
    <div class="det-hero"><span class="det-ic">${t.ic}</span><div class="det-amt ${t.a > 0 ? "in" : ""}">${t.a > 0 ? "+" : ""}${money(t.a)}</div><div class="det-n">${esc(t.n)}</div><span class="pill ok">Aprobado</span></div>
    <div class="pad"><div class="card" style="padding:4px 16px">
      <div class="kv"><span>Fecha</span><span>${dateLong(t.date)}</span></div>
      <div class="kv"><span>Hora</span><span>${t.time}</span></div>
      <div class="kv"><span>Categoría</span><span>${esc(t.c)}</span></div>
      <div class="kv"><span>Medio</span><span>${esc(t.ch)}</span></div>
      <div class="kv"><span>Referencia</span><span class="mono">${t.ref || "—"}</span></div>
    </div></div>
    ${D.same_count > 1 ? `<div class="pad" style="margin-top:12px"><div class="card mini-stat"><span>Este año en <b>${esc(t.n)}</b></span><span>${D.same_count} veces · ${money(Math.abs(D.same_total))}</span></div></div>` : ""}
    <div class="pad" style="margin-top:14px">${sig
      ? anno("Lo que lee el motor", `<div class="anno-t">Alimenta la señal «${sig.name}»</div><div>${sig.headline}. Regla: ${lowerFirst(sig.rule)}.</div><div class="anno-f">Señal ${sig.strength} · oferta asociada: ${sig.offer}</div>`)
      : anno("Lo que lee el motor", `<div>Este movimiento no alimenta ninguna señal de seguros. El motor lo usa solo para el resumen de Tu año.</div>`)}</div>
    <div class="actions"><button class="btn ghost" data-a="toast" data-m="Reporte enviado. Te contactaremos en 24 horas">Reportar un problema</button></div>`;
  },

  notifs(S) {
    return `${topbar("Notificaciones", {right: S.notifs.some(n => n.unread) ? `<button class="tb-r" data-a="read-all">Leer todo</button>` : ""})}
    <div class="nlist">${S.notifs.map(n => `<button class="nitem${n.unread ? " unread" : ""}" data-a="notif" data-id="${n.id}">
      <span class="n-ic"><img src="/static/img/logo-lulo.png" alt=""></span>
      <span class="n-t"><b>${esc(n.t)}</b><span>${esc(n.b)}</span></span><span class="n-w">${esc(n.when)}</span></button>`).join("")}</div>
    <div style="height:18px"></div>`;
  },

  card(S) {
    const card = allMovs(S).filter(m => m.ch && m.ch.startsWith("Tarjeta")).slice(0, 5);
    return `${topbar("Tarjeta débito")}
    <div class="pad">${cardHTML(S, true)}</div>
    <div class="stack" style="margin-top:18px">
      <div class="card"><div class="row"><div><div class="ttl" style="font-size:14px">Congelar tarjeta</div><div class="meta">Bloquea compras mientras la encuentras</div></div><button class="switch" role="switch" aria-checked="${S.cardFrozen}" aria-label="Congelar tarjeta" data-a="freeze"></button></div></div>
      <div class="card" style="padding:4px 16px"><div class="kv"><span>Número</span><span class="mono">•••• ${S.B.client.card_last4}</span></div><div class="kv"><span>Vence</span><span class="mono">08/29</span></div><div class="kv"><span>Cupo diario de compras</span><span>${money(3000000)}</span></div></div>
    </div>
    <div class="sec-title">Compras recientes con tarjeta</div>${card.map(m => movRow(m, S.B.today)).join("")}<div style="height:18px"></div>`;
  },

  transfer(S) {
    const breb = S.params.mode === "breb";
    return `${topbar(breb ? "Bre-B" : "Enviar dinero")}
    ${breb ? `<div class="pad"><p class="sub" style="margin:0 0 12px">Envía al instante a cualquier banco con una llave: celular, correo o @alias.</p></div>` : ""}
    <label class="searchbox"><span style="opacity:.7">${breb ? "@" : I.search}</span><input placeholder="${breb ? "Escribe la llave" : "Nombre, celular o llave"}" data-a="noop"></label>
    <div class="sec-title">Frecuentes</div>
    <div class="clist">${S.B.contacts.map(c => `<button class="crow" data-a="pick-contact" data-id="${c.id}">${avatar(c.name)}<span class="t"><b>${esc(c.name)}</b><span>${esc(c.key)} · ${esc(c.bank)}</span></span>${I.chev}</button>`).join("")}</div>
    <div style="height:18px"></div>`;
  },

  amount(S) {
    const F = S.flow;
    const who = F.kind === "transfer" ? `Para <b>${esc(F.contact.name)}</b> · ${esc(F.contact.key)}` : `A tu cajita <b>${esc(F.cajita.emoji)} ${esc(F.cajita.name)}</b>`;
    const last = F.suggest || [];
    return `${topbar(flowTitle[F.kind])}
    <div class="amt-wrap"><div class="amt-to">${who}</div>
      <div class="amt" id="amtDisplay">${money(F.amount || 0)}</div>
      <div class="amt-sub" id="amtSub">Disponible ${money(S.balance)}</div>
      ${last.length ? `<div class="amt-chips">${last.map(v => `<button data-a="amt-set" data-v="${v}">${money(v)}</button>`).join("")}</div>` : ""}
    </div>
    ${keypad()}
    <div class="sticky-actions"><button class="btn primary" data-a="amt-next" id="amtNext" ${F.amount > 0 && F.amount <= S.balance ? "" : "disabled"}>Continuar</button></div>`;
  },

  confirm(S) {
    const F = S.flow;
    const rows = {
      transfer: [["Para", F.contact?.name], ["Llave", F.contact?.key], ["Banco", F.contact?.bank], ["Costo", "$0"], ["Sale de", "Cuenta Lulo"]],
      cajita: [["Cajita", `${F.cajita?.emoji} ${F.cajita?.name}`], ["Lleva ahorrado", money(F.cajita?.saved || 0)], ["Sale de", "Cuenta Lulo"]],
      cuota: [["Crédito", "Lulo Crédito"], ["Cuota", `${(S.credit?.paid || 0) + 1} de ${S.credit?.cuotas}`], ["Sale de", "Cuenta Lulo"]],
      desembolso: [["Plazo", `${F.cuotas} cuotas`], ["Cuota aproximada", money(F.cuota || 0)], ["Tasa", "1,79% M.V."], ["Llega a", "Cuenta Lulo"]],
    }[F.kind];
    const verb = {transfer: "Enviar", cajita: "Abonar", cuota: "Pagar", desembolso: "Solicitar"}[F.kind];
    return `${topbar("Revisa y confirma")}
    <div class="det-hero"><div class="sub" style="margin:0">${{transfer: "Vas a enviar", cajita: "Vas a abonar", cuota: "Vas a pagar", desembolso: "Vas a recibir"}[F.kind]}</div><div class="det-amt">${money(F.amount)}</div></div>
    <div class="pad"><div class="card" style="padding:4px 16px">${rows.map(([k, v]) => `<div class="kv"><span>${k}</span><span>${esc(v)}</span></div>`).join("")}</div></div>
    ${F.kind === "desembolso" && !hasPolicy(S, "pago") ? `<div class="pad" style="margin-top:12px"><div class="why">Este crédito todavía no tiene pago protegido.</div></div>` : ""}
    <div class="actions"><button class="btn primary" data-a="confirm">${verb} ${money(F.amount)}</button><button class="btn ghost" data-a="back">Cambiar</button></div>`;
  },

  processing(S) {
    const t = {transfer: "Enviando por Bre-B…", cajita: "Moviendo tu plata a la cajita…", cuota: "Pagando tu cuota…", desembolso: "Aprobando tu crédito…"}[S.flow.kind];
    return `<div class="spinner"></div><p class="sub" style="text-align:center">${t}</p>`;
  },

  success(S) {
    const F = S.flow, R = F.result || {};
    const title = {
      transfer: `Enviaste ${money(F.amount)}`, cajita: `Abonaste ${money(F.amount)}`,
      cuota: "Pagaste tu cuota", desembolso: "Tu crédito ya está en tu cuenta",
    }[F.kind];
    const sub = {
      transfer: `A ${esc(F.contact?.name)}${F.contact?.name.endsWith(".") ? "" : "."} Le llega en segundos.`,
      cajita: `Tu cajita «${esc(F.cajita?.name)}» ya lleva ${money((F.cajita?.saved || 0))}.`,
      cuota: `Cuota ${S.credit?.paid} de ${S.credit?.cuotas} de Lulo Crédito.`,
      desembolso: `${money(F.amount)} a ${F.cuotas} cuotas de ${money(F.cuota)}.`,
    }[F.kind];
    return `<div class="success"><div class="ring">${I.check}</div><h2 class="h-big" style="margin-top:22px">${title}</h2><p class="sub">${sub}</p></div>
    <div class="pad" style="margin-top:18px"><div class="card receipt" style="padding:4px 16px">
      <div class="kv"><span>Referencia</span><span class="mono">${R.movement?.ref || "—"}</span></div>
      <div class="kv"><span>Fecha</span><span>${dateLong(S.B.today)}</span></div>
      <div class="kv"><span>Medio</span><span>${esc(R.movement?.ch || "Cuenta Lulo")}</span></div>
    </div></div>
    ${R.note ? `<div class="pad" style="margin-top:14px">${anno("Lo que lee el motor", `<div>${R.note}</div>${R.event ? `<div class="anno-f">El motor revisa este evento ahora mismo.</div>` : ""}`)}</div>` : ""}
    <div class="actions"><button class="btn primary" data-a="flow-done">Listo</button><button class="btn ghost" data-a="toast" data-m="Comprobante listo para compartir">${I.share} Compartir comprobante</button></div>`;
  },

  cajitas(S) {
    const total = S.cajitas.reduce((a, c) => a + c.saved, 0);
    return `${topbar("Cajitas")}
    <div class="pad"><div class="sub" style="margin:0">Tienes ahorrado</div><div class="figure">${S.hide ? "$ ••••••" : money(total)}</div></div>
    <div class="stack" style="margin-top:16px">${S.cajitas.map(c => {
      const pct = Math.min(100, Math.round(c.saved / c.goal * 100));
      return `<button class="card caj" data-a="go" data-s="cajita" data-p="${c.id}"><div class="row"><span class="caj-e">${c.emoji}</span><span style="flex:1"><span class="ttl">${esc(c.name)}</span><span class="meta" style="display:block;margin-top:2px">${esc(c.note)}</span></span><span class="caj-p">${pct}%</span></div>
        <div class="bar lime"><i style="width:${pct}%"></i></div><div class="meta">${money(c.saved)} de ${money(c.goal)}</div></button>`;
    }).join("")}
    <button class="card dashed" data-a="toast" data-m="Crear cajitas queda fuera de este prototipo"><span class="row" style="justify-content:flex-start;gap:10px">${I.plus} Crear una cajita</span></button></div><div style="height:18px"></div>`;
  },

  cajita(S) {
    const c = S.cajitas.find(x => x.id === S.params.id);
    const pct = Math.min(100, Math.round(c.saved / c.goal * 100));
    return `${topbar(esc(c.name))}
    <div class="det-hero"><span class="det-ic big">${c.emoji}</span><div class="det-amt">${money(c.saved)}</div><div class="det-n">de ${money(c.goal)} · ${esc(c.note)}</div></div>
    <div class="pad"><div class="bar lime thick"><i style="width:${pct}%"></i></div><div class="meta" style="text-align:right">${pct}% de tu meta</div></div>
    <div class="actions" style="padding-bottom:6px"><button class="btn primary" data-a="cajita-abonar" data-id="${c.id}">Abonar</button></div>
    ${c.travel ? `<div class="pad">${anno("Lo que lee el motor", "<div>Es una cajita de viaje: cada abono alimenta la señal «Viaje en preparación» y puede disparar el seguro de viaje.</div>")}</div>` : ""}
    <div class="sec-title">Últimos abonos</div>
    <div class="stack">${c.history.slice(0, 6).map(h => `<div class="kv" style="padding:8px 0"><span>${dateShort(h.date)}</span><span>+${money(h.a)}</span></div>`).join("") || `<p class="meta">Todavía no hay abonos.</p>`}</div>
    <div style="height:18px"></div>`;
  },

  credito(S) {
    const C = S.credit, pre = S.B.client.preapproved;
    if (!C) {
      return `${topbar("Lulo Crédito")}
      <div class="pad"><div class="credit-hero"><div class="k">Preaprobado para ti</div><div class="v">${money(pre)}</div><p>Libre inversión, sin papeleo y con la plata en tu cuenta en minutos.</p><button class="btn primary dark" data-a="go" data-s="creditReq">Solicitar</button></div></div>
      <div class="pad" style="margin-top:14px">${anno("Lo que lee el motor", "<div>Un desembolso es una nueva obligación mensual: el motor revisa si el crédito tiene pago protegido y, si no, lo ofrece.</div>")}</div>`;
    }
    const pct = Math.round(C.paid / C.cuotas * 100);
    return `${topbar("Lulo Crédito")}
    <div class="pad"><div class="card"><div class="meta" style="margin:0">Te falta pagar</div><div class="figure">${money(C.remaining)}</div>
      <div class="bar lime"><i style="width:${pct}%"></i></div><div class="row meta"><span>${C.paid} de ${C.cuotas} cuotas</span><span>${pct}%</span></div></div></div>
    <div class="pad" style="margin-top:12px"><div class="card" style="padding:4px 16px">
      <div class="kv"><span>Cuota mensual</span><span>${money(C.cuota)}</span></div>
      <div class="kv"><span>Próximo pago</span><span>${dateShort(C.next_date)}</span></div>
      <div class="kv"><span>Monto desembolsado</span><span>${money(C.amount)}</span></div>
      <div class="kv"><span>Tasa</span><span>${C.rate}</span></div>
    </div></div>
    <div class="sec-title">Tu protección</div>
    <div class="pad"><div class="card ${C.protected ? "fresh" : ""}"><div class="row"><span class="ttl">${I.shield} Pago protegido</span><span class="pill ${C.protected ? "ok" : "warn"}">${C.protected ? "Incluido" : "Sin protección"}</span></div>
      <div class="meta">${C.protected ? `Si pierdes el empleo, SBS Seguros cubre hasta 6 cuotas de ${money(C.cuota)}.` : "Tus cuotas no están protegidas si pierdes tus ingresos."}</div>
      ${C.protected && S.B.credit?.protected && !S.known.pago ? `<div class="q-btns"><button data-a="known" data-v="Sí">Sí, lo sabía</button><button data-a="known" data-v="No">No sabía</button></div><div class="hint">¿Sabías que tenías esta protección?</div>` : ""}
    </div></div>
    <div class="actions"><button class="btn primary" data-a="pay-cuota">Pagar cuota de ${money(C.cuota)}</button><button class="btn ghost" data-a="go" data-s="creditReq">Pedir más dinero</button></div>`;
  },

  creditReq(S) {
    const max = S.credit ? 9000000 : S.B.client.preapproved;
    const opts = [2000000, Math.round(max / 2 / 1e5) * 1e5, max];
    const F = S.flow;
    return `${topbar("Solicitar crédito")}
    <div class="pad"><div class="sub" style="margin:0">¿Cuánto necesitas?</div><div class="figure">${money(F.amount)}</div></div>
    <div class="pad" style="margin-top:12px"><div class="seg">${opts.map(v => `<button aria-pressed="${F.amount === v}" data-a="cr-amt" data-v="${v}">${(v / 1e6).toFixed(1).replace(".0", "").replace(".", ",")} M</button>`).join("")}</div></div>
    <div class="sec-title">¿A cuántas cuotas?</div>
    <div class="pad"><div class="seg">${[12, 18, 24].map(n => `<button aria-pressed="${F.cuotas === n}" data-a="cr-n" data-v="${n}">${n} meses</button>`).join("")}</div></div>
    <div class="pad" style="margin-top:16px"><div class="card" style="padding:4px 16px">
      <div class="kv"><span>Cuota aproximada</span><span style="font-weight:700">${money(creditCuota(F.amount, F.cuotas))}</span></div>
      <div class="kv"><span>Tasa</span><span>1,79% M.V.</span></div>
      <div class="kv"><span>Llega a</span><span>Cuenta Lulo</span></div></div></div>
    <div class="actions"><button class="btn primary" data-a="cr-next">Continuar</button></div>`;
  },

  anio(S) {
    if (!S.consent) {
      return `<div class="yr-hero off"><div class="k">Tu año en Lulo</div><div class="y">2026</div><p>Para armar tu resumen necesitamos tu autorización para usar tus movimientos.</p><button class="btn" data-a="consent-on">Autorizar y ver mi año</button></div>
      <div class="pad" style="margin-top:14px"><div class="card" style="font-size:12.5px;color:#C9D0DE;line-height:1.5">Tratamos tus datos según la Ley 1581 de 2012. Puedes retirar la autorización cuando quieras desde Perfil.</div></div>`;
    }
    const sw = {lime: "background:var(--lime);color:var(--ink)", navy: "background:var(--navy-3)", ink: "background:var(--ink);border:1px solid var(--line)", pink: "background:var(--pink);color:var(--ink)"};
    const st = c => c.soat ? (S.soatRenewed ? "Al día" : "Por renovar") : c.ask ? (S.known[c.ask] ? "Respondido" : "") : c.protect && hasPolicy(S, c.protect.key) ? "Activo" : "";
    const kind = c => c.soat || c.protect ? "Incluye un momento de protección" : c.ask ? "Incluye una pregunta" : c.id === "cierre" ? "Lo que tienes cubierto" : "Resumen";
    return `<div class="yr-hero"><div class="k">Tu año en Lulo</div><div class="y">2026</div><p>Lo que viviste con Lulo de octubre a septiembre, contado con tus movimientos.</p><button class="btn" data-a="st-open" data-i="0">Ver mi año</button></div>
    <div class="sec-title">${chapters(S).length - 1} capítulos</div>
    ${chapters(S).slice(1).map((c, i) => `<button class="chap" data-a="st-open" data-i="${i + 1}"><span class="sw" style="${sw[c.theme]}">${i + 1}</span><span class="tx"><b>${c.name}</b><span>${kind(c)}</span></span><span class="ok" style="${st(c) === "Por renovar" ? "color:var(--warn)" : ""}">${st(c)}</span></button>`).join("")}
    <div class="pad" style="margin-top:14px"><div class="card" style="font-size:12.5px;color:#C9D0DE;line-height:1.5">Lo armamos solo con tus movimientos en Lulo. Puedes apagar las sugerencias de seguros en Perfil.</div></div>
    <div style="height:20px"></div>`;
  },

  yearLoading(S) {
    return `<div class="yr-load"><div class="yr-load-y">2026</div><div class="yr-load-t">Armando tu año…</div>
      <div class="yr-load-bar"><i></i></div>
      <div class="yr-load-s" id="yrLoadS">Leyendo ${num(S.B.movCount)} movimientos</div></div>`;
  },

  story(S) {
    const list = chapters(S), c = list[S.story], last = S.story === list.length - 1;
    return `<div class="story t-${c.theme}">
      <div class="st-prog">${list.map((_, i) => `<i class="${i <= S.story ? "on" : ""}"></i>`).join("")}</div>
      <div class="st-head"><span>Tu año en Lulo · ${S.story + 1} de ${list.length}</span><button class="st-x" data-a="st-close" aria-label="Cerrar">✕</button></div>
      <button class="st-zone prev" data-a="st-prev" aria-label="Capítulo anterior"></button><button class="st-zone next" data-a="st-next" aria-label="Siguiente capítulo"></button>
      <div class="st-body">${storyBody(S, c)}</div>
      ${protectBlock(S, c)}
      <div class="st-nav"><button data-a="st-prev" ${S.story === 0 ? "disabled" : ""}>Anterior</button><button data-a="st-next">${last ? "Terminar" : "Siguiente"}</button></div>
    </div>`;
  },

  offer(S) {
    const O = S.B.offers[S.offer];
    return `${topbar("Recomendado para ti")}
    <div class="pad"><div class="row" style="justify-content:flex-start;gap:8px;flex-wrap:wrap"><span class="pill new">Sugerencia</span>${O.concept ? `<span class="pill hyp">Producto por negociar con la aseguradora</span>` : ""}</div>
      <h2 class="h-big" style="margin-top:12px">${O.title}</h2><p class="sub">Con ${O.aliado}</p></div>
    <div class="pad" style="margin-top:16px"><div class="why"><b>Por qué lo ves:</b> ${O.why}</div></div>
    <div class="pad" style="margin-top:16px"><div class="card"><div class="figure">${O.figure}</div><div class="meta" style="margin-top:2px">${O.figLabel}</div></div></div>
    <div class="sec-title">Qué cubre</div>
    <div class="pad"><ul class="list-check">${O.covers.map(c => `<li>${c}</li>`).join("")}</ul></div>
    <div class="pad" style="margin-top:18px"><div class="card" style="padding:4px 16px"><div class="kv"><span>Valor</span><span style="font-weight:700">${O.price}</span></div><div class="kv"><span>Se paga desde</span><span>Cuenta Lulo</span></div></div></div>
    <div class="actions">
      <button class="btn primary" data-a="accept">Activar seguro</button>
      <button class="btn ghost" data-a="later">Ahora no</button>
      <button class="btn text" data-a="optout">No quiero sugerencias de este tipo</button>
    </div>`;
  },

  renew(S) {
    const car = S.B.car, Q = quote(S);
    const pct = Math.max(4, Math.min(100, Math.round((365 - car.days) / 365 * 100)));
    return `${topbar("Renovar SOAT")}
    <div class="pad"><div class="card"><div class="row"><span class="ttl">${car.plate}</span><span class="pill ${car.days <= 10 ? "bad" : "warn"}">Vence en ${car.days} días</span></div><div class="meta">${car.model} · ${car.insurer}</div><div class="bar"><i style="width:${pct}%"></i></div></div></div>
    <div class="sec-title">Nueva vigencia</div>
    <div class="pad"><div class="card" style="padding:4px 16px">
      <div class="kv"><span>Desde</span><span>${car.new_from}</span></div>
      <div class="kv"><span>Hasta</span><span>${car.new_to}</span></div>
    </div></div>
    <div class="sec-title">Resumen de pago</div>
    <div class="pad"><div class="card" style="padding:4px 16px">
      <div class="kv"><span>Valor SOAT</span><span>${money(Q.base)}</span></div>
      <div class="kv"><span>Descuento por renovar antes</span><span style="color:var(--lime)">${money(-Q.discount)}</span></div>
      <div class="kv"><span style="color:#fff;font-weight:600">Total</span><span style="font-weight:700;font-size:16px">${money(Q.total)}</span></div>
      <div class="kv"><span>Se paga desde</span><span>Cuenta Lulo · ${money(S.balance)}</span></div>
    </div></div>
    <div class="pad" style="margin-top:12px"><div class="why">El descuento por anticipación es una hipótesis a validar: cuánta anticipación hace que cambie la decisión.</div></div>
    <div class="actions">
      <button class="btn primary" data-a="pay" ${S.balance < Q.total ? "disabled" : ""}>Pagar ${money(Q.total)}</button>
      <button class="btn ghost" data-a="postpone">Recuérdamelo después</button>
    </div>`;
  },

  paying(S) { return `<div class="spinner"></div><p class="sub" style="text-align:center">Procesando el pago con ${S.B.car.insurer}…</p>`; },

  done(S) {
    return `<div class="success"><div class="ring">${I.check}</div>
      <h2 class="h-big" style="margin-top:22px">Tu SOAT quedó renovado</h2>
      <p class="sub">${S.B.car.plate} está cubierto hasta el ${S.B.car.new_to_long}. Te avisaremos ${S.alertDays} días antes del próximo vencimiento.</p></div>
      <div class="actions" style="margin-top:20px"><button class="btn primary" data-a="tab" data-t="home">Volver al inicio</button><button class="btn ghost" data-a="tab" data-t="anio">Ver Tu año en Lulo</button></div>`;
  },

  perfil(S) {
    const c = S.B.client;
    return `<div class="prof">${avatar(c.full, c.color, "lg")}<div><div class="hi">${esc(c.full)}</div><div class="meta" style="margin-top:2px">Cliente Lulo desde ${c.since} · ${esc(c.city)}</div></div></div>
    <div class="sec-title">Notificaciones</div>
    <div class="stack">
      <div class="card"><div class="row"><div><div class="ttl" style="font-size:14px">Sugerencias de seguros</div><div class="meta">Según lo que haces en la app</div></div><button class="switch" role="switch" aria-checked="${S.sugg}" aria-label="Sugerencias de seguros" data-a="sugg"></button></div></div>
      <div class="card"><div class="row"><div><div class="ttl" style="font-size:14px">Avisos de vencimiento</div><div class="meta">SOAT, tecnomecánica y pólizas</div></div><button class="switch" role="switch" aria-checked="${S.remind}" aria-label="Avisos de vencimiento" data-a="remind"></button></div>
        <div class="meta" style="margin:14px 0 8px">Avísame con</div>
        <div class="seg">${[30, 15, 7].map(d => `<button aria-pressed="${S.alertDays === d}" data-a="days" data-d="${d}">${d} días</button>`).join("")}</div>
      </div>
    </div>
    <div class="sec-title">Privacidad</div>
    <div class="stack"><div class="card"><div class="row"><div><div class="ttl" style="font-size:14px">Usar mis movimientos</div><div class="meta">Para Tu año en Lulo y las sugerencias · Ley 1581 de 2012</div></div><button class="switch" role="switch" aria-checked="${S.consent}" aria-label="Usar mis movimientos" data-a="consent"></button></div></div></div>
    <div class="sec-title">Mis productos</div>
    <div class="plist">
      <div class="prow"><span>Cuenta de ahorros</span><b>${S.hide ? "$ ••••••" : money(S.balance)}</b></div>
      <button class="prow" data-a="go" data-s="card"><span>Tarjeta débito ••${c.card_last4}</span>${I.chev}</button>
      <button class="prow" data-a="go" data-s="credito"><span>${S.credit ? "Lulo Crédito" : "Crédito preaprobado"}</span>${I.chev}</button>
      <button class="prow" data-a="go" data-s="cajitas"><span>Cajitas (${S.cajitas.length})</span>${I.chev}</button>
    </div>
    <div class="actions"><button class="btn ghost" data-a="logout">${I.lock} Cerrar sesión</button></div>`;
  },
};

export const ROOTS = ["home", "movs", "anio", "perfil"];
export { topbar };
