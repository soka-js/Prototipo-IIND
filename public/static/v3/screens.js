// Pantallas del teléfono con el look de la app real. Cada una es una función pura: estado → HTML.
import { I } from "./icons.js";
import { addDays, dateHeader, dateLong, dateShort, dayLabel, dayOf, esc, initials, money, monthShortUpper, num, strip } from "./util.js";

/* ---------- modelo compartido ---------- */
export const ROOTS = ["home", "explora", "anio", "proteccion"];
export const cands = S => Object.fromEntries(((S.evaluation && S.evaluation.candidates) || []).map(c => [c.ramo, c]));
export const product = (S, ramo) => S.catalog.find(p => p.ramo === ramo) || {ramo, title: ramo, price: "Por cotizar", covers: []};
export const luloRamos = S => [...S.B.policies.lulo.map(p => p.ramo), ...S.accepted, ...S.renewed];
export const hasRamo = (S, r) => luloRamos(S).includes(r);
export const unread = S => S.notifs.filter(n => n.unread).length;
export const allRows = S => [...S.sessionRows, ...S.B.recent];
export const chapters = S => S.chapters || [];
export const quote = S => (S.B.car && S.B.car.quotes && S.B.car.quotes[S.alertDays]) || null;
export function soatDue(S) {
  const car = S.B.car;
  return car && car.days != null && !S.renewed.includes("SOAT") && S.remind && car.days <= S.alertDays;
}
export function protections(S) {
  const out = S.B.policies.lulo.map(p => ({ramo: p.ramo, title: p.title, partner: p.partner, voluntary: p.voluntary,
    sub: p.ramo === "SOAT" && S.renewed.includes("SOAT") ? `Renovado hasta el ${dateShort(S.B.car.new_to)} ${S.B.car.new_to.slice(0, 4)}` :
      p.expires_on ? `Vence el ${dateShort(p.expires_on)} ${p.expires_on.slice(0, 4)}` : p.voluntary ? "Activo" :
      p.ramo === "Vida grupo deudor" ? "Ligado a tu crédito · beneficiario: el banco" : "Incluido con tus productos"}));
  for (const r of S.accepted) if (!out.some(p => p.ramo === r)) {
    const P = product(S, r);
    out.push({ramo: r, title: P.title, partner: P.partner, voluntary: true, sub: "Activado en esta sesión", fresh: true});
  }
  if (S.renewed.includes("SOAT") && !out.some(p => p.ramo === "SOAT")) out.push({ramo: "SOAT", title: "SOAT", partner: "Seguros Mundial", voluntary: true, sub: "Renovado en esta sesión", fresh: true});
  return out;
}
export function creditCuota(amount, n, rate = 0.0179) { return Math.round(amount * rate / (1 - Math.pow(1 + rate, -n))); }
const ICON_OF = {SOAT: "car", Vida: "heart", Desempleo: "briefcase", Hogar: "home2", Mascotas: "paw", Viajes: "plane", "Pago protegido": "shieldDollar"};
export const ramoIcon = r => I[ICON_OF[r]] || I.shield;

/* ---------- piezas ---------- */
const hdr = (title, opts = {}) => `<div class="hdr">${opts.noBack ? "" : `<button class="back" data-a="back" aria-label="Volver">${opts.close ? I.close : I.back}</button>`}<h2>${title}</h2>${opts.right || ""}</div>`;
const anno = (title, body) => `<div class="anno"><div class="anno-k">${I.info.replace(/width="24" height="24"/, 'width="14" height="14"')} ${title}</div>${body}</div>`;
export const av = (S, cls = "") => `<span class="av ${cls}">${esc(initials(S.B.client.name.replace(/^Cliente /, "")))}</span>`;
const wordmark = (cls = "") => `<span class="wordmark ${cls}">lulo<sup>®</sup></span>`;

export function movRow(r, today, withTime = false) {
  const tag = r.feeds ? `<span class="sigdot" title="Alimenta la señal de ${esc(r.feeds)}"></span>` : "";
  return `<button class="mov${r.flash ? " flash" : ""}" data-a="mov" data-id="${r.id}"><span class="ic">${I[r.icon] || I.dots}</span><span class="t"><span>${esc(r.label)}</span><span>${esc(r.cat_label)} · ${withTime ? esc(String(r.channel).replace(/\s*••\d+$/, "")) : dayLabel(r.date, today)}</span></span>${tag}<span class="a ${r.amount > 0 ? "in" : ""}">${r.amount > 0 ? "+" : ""}${money(r.amount)}</span></button>`;
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
  return `<div class="lcard${S.cardFrozen ? " frozen" : ""}">
    <span class="lc-top">debit <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M8 8a6 6 0 0 1 0 8M12 5.5a10 10 0 0 1 0 13M16 3a14 14 0 0 1 0 18"/></svg></span>
    <span class="lc-chip"></span><span class="lc-logo" role="img" aria-label="Lulo Bank"></span>
    <span class="lc-name">${esc(c.card_name)}</span>${big ? `<span class="lc-num">•••• •••• •••• ${c.card_last4}</span>` : ""}
    <span class="lc-mc"><i></i><i></i></span>${S.cardFrozen ? `<span class="lc-frozen">${I.snow} Congelada</span>` : ""}
  </div>`;
}
function keypad(lock = false) {
  const keys = ["1","2","3","4","5","6","7","8","9", lock ? "bio" : "000", "0", "del"];
  return `<div class="keypad">${keys.map(k => `<button data-a="key" data-k="${k}" aria-label="${k === "del" ? "Borrar" : k === "bio" ? "Ingresar con Face ID" : k}">${k === "del" ? I.del : k === "bio" ? I.face : k}</button>`).join("")}</div>`;
}
function mapSVG(full = false) {
  // Mapa ilustrativo (no es la ubicación del cliente): calles en retícula y cajeros.
  const W = 390, H = full ? 640 : 170, roads = [];
  for (let i = 0; i < 9; i++) roads.push(`<path d="M${-20 + i * 52} 0 L${10 + i * 52} ${H}" stroke="#3A4560" stroke-width="${i % 3 ? 2 : 6}"/>`);
  for (let j = 0; j < (full ? 13 : 4); j++) roads.push(`<path d="M0 ${30 + j * 48} L${W} ${12 + j * 48}" stroke="#3A4560" stroke-width="${j % 4 ? 2 : 7}"/>`);
  const pins = full ? [[60,90,1],[150,210,1],[205,260,1],[260,240,1],[300,330,1],[120,380,1],[330,120,0],[90,470,1],[240,520,0],[180,600,1],[320,560,1]] : [[60,30,1],[320,40,0],[40,140,0],[330,140,1]];
  const pin = ([x, y, free]) => `<g transform="translate(${x} ${y})"><rect x="-11" y="-16" width="22" height="30" rx="4" fill="${free ? "#E8FF00" : "#A9B4CC"}"/><rect x="-6" y="-11" width="12" height="7" rx="1.5" fill="#202539"/></g>`;
  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="xMidYMid slice"><rect width="${W}" height="${H}" fill="#232A40"/>${roads.join("")}${pins.map(pin).join("")}${full ? `<circle cx="195" cy="300" r="22" fill="rgba(143,184,255,.25)"/><circle cx="195" cy="300" r="7" fill="#8FB8FF" stroke="#fff" stroke-width="2"/>` : ""}</svg>`;
}

function soatReminder(S) {
  const car = S.B.car;
  if (!soatDue(S)) return "";
  const urgent = car.days <= 10;
  return `<button class="reminder${urgent ? " urgent" : ""}" data-a="go" data-s="renew">
    <span class="cal"><b>${dayOf(car.expiry)}</b><small>${monthShortUpper(car.expiry)}</small></span>
    <span style="flex:1"><span class="rm-t">Tu SOAT vence en ${car.days} días</span><span class="rm-d">${car.plate || "Tu vehículo"} · ${urgent ? "Evita la multa: renuévalo hoy aquí" : "Renuévalo aquí y págalo desde tu Lulo cuenta"}</span></span>${I.chev}
  </button>`;
}

function promos(S) {
  const out = [];
  const B = S.banner;
  if (B) out.push(`<button class="promo offer" data-a="banner-open"><span class="tagp">Para ti</span><span><b>${esc(B.title)}</b><p>${esc(strip(B.why)).slice(0, 92)}${strip(B.why).length > 92 ? "…" : ""}</p></span><span class="cta">Ver por qué</span></button>`);
  out.push(`<button class="promo" data-a="tab" data-t="proteccion"><span><b>¡Estar protegido es un estilo de vida!</b><p>Asegura lo que más te importa</p></span><span class="cta">Ver Seguros</span>${art("shield")}</button>`);
  if (chapters(S).length) out.push(`<button class="promo lime" data-a="tab" data-t="anio"><span><b>Tu año en Lulo ya está listo</b><p>${num(S.B.movCount)} movimientos contados en ${chapters(S).length} capítulos</p></span><span class="cta">Ver mi año</span>${art("star")}</button>`);
  out.push(`<button class="promo" data-a="go" data-s="credito"><span><b>¡Pide tu Lulo crédito cuando quieras!</b><p>Un crédito libre destino desde 2 hasta 50 millones.</p></span><span class="cta">Saber más</span>${art("coin")}</button>`);
  return `<div class="carousel" id="carousel">${out.join("")}</div><div class="dots">${out.map((_, i) => `<i class="${i === 0 ? "on" : ""}"></i>`).join("")}</div>`;
}
const art = k => `<svg class="art" viewBox="0 0 100 100"><circle cx="60" cy="60" r="44" fill="${k === "star" ? "#101500" : "#B9E3FF"}" opacity=".35"/><g transform="translate(36 36) scale(2)" stroke="${k === "star" ? "#101500" : "#061232"}" fill="none" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${{shield: '<path d="M12 3 5 6v5.5c0 4.2 3 7.8 7 9.5 4-1.7 7-5.3 7-9.5V6z"/><path d="m9 12 2.2 2.2L15.5 10"/>', star: '<path d="M12 3.5l2.4 5 5.4.6-4 3.7 1.1 5.4L12 15.5l-4.9 2.7 1.1-5.4-4-3.7 5.4-.6z"/>', coin: '<circle cx="12" cy="12" r="8"/><path d="M10 9.5h3a1.5 1.5 0 0 1 0 3h-2a1.5 1.5 0 0 0 0 3h3M12 8v1.5M12 15.5V17"/>'}[k]}</g></svg>`;

/* ---------- Tu año: momento de protección ---------- */
function protectBlock(S, c) {
  if (c.ask) {
    if (S.known[c.ask]) return `<div class="st-protect"><div class="st-pd">Gracias por responder.</div></div>`;
    return `<div class="st-protect"><div class="st-pt">¿Sabías que tenías esta protección?</div><div class="q-btns"><button data-a="known" data-v="Sí">Sí, lo sabía</button><button data-a="known" data-v="No">No sabía</button></div></div>`;
  }
  const p = c.protect;
  if (!p) return "";
  const k = p.ramo, pk = `<div class="st-pk">${I.shield.replace(/width="24" height="24"/, 'width="14" height="14"')} Momento de protección</div>`;
  const soatRenewal = k === "SOAT" && ["renovacion", "captura"].includes(p.kind) && p.state === "offer" && !S.renewed.includes("SOAT");
  if (!soatRenewal && (hasRamo(S, k) || p.state === "has")) {
    const renewed = k === "SOAT" && S.renewed.includes("SOAT");
    return `<div class="st-protect">${pk}<div class="st-pt">${renewed ? "Tu SOAT ya está al día" : "Ya lo tienes activo"}</div><div class="st-pd">${esc(p.title)}${p.partner ? ` con ${esc(p.partner)}` : ""}.</div></div>`;
  }
  if (["external", "soon", "ineligible"].includes(p.state)) return `<div class="st-protect">${pk}<div class="st-pt">${esc(p.t)}</div><div class="st-pd">${esc(p.d)}</div></div>`;
  if (p.state === "control" || S.control === true || !S.sugg) return "";
  if (S.declined[k]) return `<div class="st-protect"><div class="st-pd">Entendido. No te lo mostraremos en este resumen.</div></div>`;
  const P = product(S, k);
  if (k === "SOAT") {
    const renew = p.kind === "renovacion" || p.kind === "captura";
    return `<div class="st-protect">${pk}<div class="st-pt">${renew ? `Tu SOAT vence el ${dateShort(S.B.car.expiry)}` : "¿Tu carro es tuyo? Cotiza aquí el SOAT"}</div><div class="st-pd">${renew ? "Renuévalo aquí sin salir de Lulo y págalo desde tu cuenta." : "Compra o renueva el SOAT en minutos, sin filas ni papeleo."}</div><div class="st-pb"><button class="btn primary" data-a="st-soat">${renew ? "Renovar ahora" : "Cotizar SOAT"}</button></div></div>`;
  }
  return `<div class="st-protect"><div class="st-pk">Momento de protección${c.concept || P.concept ? ` <span class="pill hyp">Producto por negociar</span>` : ""}</div><div class="st-pt">${esc(p.t || P.title)}</div><div class="st-pd">${esc(P.title)}${P.partner ? ` con ${esc(P.partner)}` : ""}: ${esc(P.price)}.</div><div class="st-pb"><button class="btn primary" data-a="st-yes" data-k="${k}">Activar</button><button class="btn ghost" data-a="st-no" data-k="${k}">Ahora no</button></div></div>`;
}

function storyBody(S, c) {
  if (c.id === "cierre") {
    const has = protections(S).map(p => p.title);
    const left = chapters(S).filter(x => x.protect && x.protect.state === "offer" && !hasRamo(S, x.protect.ramo)).map(x => product(S, x.protect.ramo).title);
    return `<div class="st-kick">${c.kicker}</div><div class="st-big">${has.length}</div><div class="st-line">${has.length === 1 ? "protección activa" : "protecciones activas"} al cerrar tu año</div>
      <div class="st-list">${has.map(h => `<span>${esc(h)}</span>`).join("")}</div>
      ${left.length ? `<p class="st-sub">Te quedan por revisar: ${left.join(", ")}.</p>` : `<p class="st-sub">Cubriste los momentos que encontramos este año.</p>`}
      <div class="st-acts"><button class="btn dark" data-a="st-share">Compartir mi año</button><button class="btn ghost" data-a="st-close">Cerrar</button></div>`;
  }
  const v = c.viz || {};
  let out = `<div class="st-kick">${c.kicker}</div>`;
  if (v.type === "dots") out += `<div class="st-dots${v.n > 6 ? " sm" : ""}">${"<i></i>".repeat(v.n)}</div>`;
  out += c.stats.length > 1
    ? `<div class="st-two">${c.stats.map(s => `<div><div class="st-big">${s.big}</div><div class="st-line">${s.line}</div></div>`).join("")}</div>`
    : `<div class="st-big${c.stats[0].big.length > 6 ? " md" : ""}">${c.stats[0].big}</div><div class="st-line">${esc(c.stats[0].line)}</div>`;
  if (v.type === "bars") out += `<div class="st-bars">${v.items.map(b => `<div><i style="height:${Math.max(3, b.v)}%;${b.hi ? "background:var(--lime)" : ""}"></i><span>${b.l}</span></div>`).join("")}</div>`;
  if (v.type === "rank") out += `<ol class="st-rank">${v.items.map(r => `<li><span>${esc(r.l)}</span><b>${r.v}</b></li>`).join("")}</ol>`;
  if (v.type === "chips") out += `<div class="st-list">${v.items.map(x => `<span>${esc(x)}</span>`).join("")}</div>`;
  if (c.sub) out += `<p class="st-sub">${esc(c.sub)}</p>`;
  if (c.hint) out += `<div class="st-hint">${c.hint}</div>`;
  return out;
}

const flowTitle = {transfer: "Transferir plata", cajita: "Abonar a tu bolsillo", cuota: "Pagar cuota", desembolso: "Solicitar crédito"};
const STATUS_TXT = {weak: "Señal débil", none: "Sin señal", ineligible: "No elegible", cooldown: "En espera", external: "Con otra aseguradora", has: "Activo"};

/* ---------- pantallas ---------- */
export const SCREENS = {
  lock(S) {
    const c = S.B.client;
    return `<div class="lock">${wordmark()}
      ${av(S, "xl")}
      <div class="lock-hi">Hola, ${esc(c.first)}</div>
      <div class="lock-sub">Ingresa tu clave de 4 dígitos</div>
      <div class="pin">${[0,1,2,3].map(i => `<i class="${i < S.pin ? "on" : ""}"></i>`).join("")}</div>
      ${keypad(true)}
      <button class="btn text" data-a="unlock">Ingresar con reconocimiento facial</button>
      <div class="lock-foot">Prototipo con datos simulados: cualquier clave funciona y no sale de este navegador.</div>
    </div>`;
  },

  home(S) {
    const c = S.B.client, n = unread(S);
    const pockets = S.pockets;
    return `<div class="home-h">${`<button class="av" data-a="go" data-s="perfil" aria-label="Perfil">${esc(initials(c.name.replace(/^Cliente /, "")))}</button>`}
        <div class="home-hi">${wordmark()}<span>Hola, ${esc(c.first)}</span></div>
        <button class="circ" data-a="go" data-s="ayuda" aria-label="Ayuda">${I.info}</button>
        <button class="circ solid" data-a="go" data-s="alertas" aria-label="Alertas">${I.bell}${n ? `<i class="rd"></i>` : ""}</button></div>
      ${promos(S)}
      ${soatReminder(S)}
      <button class="acct-card" data-a="go" data-s="cuenta"><span class="k">Lulo Cuenta · Saldo disponible <span class="eye" data-a="hide" role="button" aria-label="${S.hide ? "Mostrar saldo" : "Ocultar saldo"}">${S.hide ? I.eyeOff : I.eye}</span></span>
        <span class="v">${S.hide ? "$ ••••••" : money(S.balance)}</span><span class="no">No. ${esc(c.account)}</span></button>
      <div class="sec"><h3>Bolsillos Flex</h3><button data-a="go" data-s="bolsillos" aria-label="Ver bolsillos">${I.chev}</button></div>
      ${pockets.length ? `<div class="pockets">${pockets.map(p => {
        const pct = p.goal ? Math.min(100, Math.round(p.saved / p.goal * 100)) : null;
        return `<button class="pocket" data-a="go" data-s="bolsillo" data-p="${p.id}"><span class="e">${p.emoji}</span><b>${esc(p.name)}</b><div class="m">${S.hide ? "$ ••••" : money(p.saved)}</div><div class="s">${p.goal ? `${pct}% de ${money(p.goal)}` : `${p.deposits} abonos`}</div>${p.goal ? `<div class="bar"><i style="width:${pct}%"></i></div>` : ""}</button>`;
      }).join("")}</div>` : `<div class="bigcard"><span class="ph"></span><b>Ordena tu plata, ahorra y cumple tus sueños</b><button class="pill-btn" data-a="toast" data-m="Crear bolsillos queda fuera de este prototipo">Crea tu primer bolsillo</button></div>`}
      <div class="sec"><h3>Mapa de cajeros</h3></div>
      <button class="mapcard" data-a="go" data-s="mapa">${mapSVG()}<span>Encuentra el más cercano aquí</span></button>
      <div class="sec"><h3>Últimos movimientos</h3><button data-a="go" data-s="cuenta" aria-label="Ver todos">${I.chev}</button></div>
      ${allRows(S).slice(0, 4).map(m => movRow(m, S.B.as_of)).join("")}
      <div style="height:20px"></div>`;
  },

  explora(S) {
    const t = S.xt || "ahorro", C = cands(S);
    const item = (icon, title, act, opts = {}) => `<button class="prod${opts.dim ? " dim" : ""}" ${act}><span class="r"><span class="ic">${icon}</span><span class="nb">${opts.chip || ""}${opts.nuevo ? `<span class="nuevo">Nuevo</span>` : ""}${I.chev}</span></span><b>${title}</b>${opts.sub ? `<small>${opts.sub}</small>` : ""}</button>`;
    const chip = r => r === "SOAT" && soatDue(S) ? `<span class="chip-ev due">Por renovar</span>` : hasRamo(S, r) ? `<span class="chip-ev">Activo</span>` : C[r] && C[r].status === "ofrecer" && S.sugg && S.consent ? `<span class="chip-ev pti">Para ti</span>` : "";
    const lists = {
      ahorro: [item(I.account, "Lulo Cuenta", 'data-a="go" data-s="cuenta"'), item(I.card, "Tarjeta de débito", 'data-a="go" data-s="card"'),
        item(I.pocket, "Bolsillos Flex", 'data-a="go" data-s="bolsillos"'), item(I.pocketClock, "Bolsillo Programados", 'data-a="toast" data-m="Bolsillos programados queda fuera de este prototipo"')],
      inversion: [item(I.cdt, "CDT", 'data-a="go" data-s="cdt"', {nuevo: true}), item(`<b style="font-size:15px;font-weight:800">lulo<sup style="font-size:9px">x</sup></b>`, `Billetera digital ${I.info.replace(/width="24" height="24"/, 'width="16" height="16"')}`, 'data-a="go" data-s="lulox"')],
      credito: [item(I.card, "Tarjeta de crédito", 'data-a="go" data-s="tcredito"'), item(I.moneybag, "Crédito de libre inversión", 'data-a="go" data-s="credito"')],
      seguros: [
        item(I.car, "Soat", 'data-a="go" data-s="soatIntro"', {nuevo: true, chip: chip("SOAT")}),
        item(I.shieldStar, "Seguro Pago Protegido", 'data-a="offer" data-r="Pago protegido"', {nuevo: true, chip: chip("Pago protegido")}),
        item(I.shieldDollar, "Seguro Nómina Protegida", 'data-a="go" data-s="info" data-p="nomina"', {nuevo: true, sub: "Respaldo para tu Familia"}),
        item(I.shieldPerson, "Seguro de desempleo", 'data-a="offer" data-r="Desempleo"', {nuevo: true, sub: "Lulo paga tu Vida", chip: chip("Desempleo")}),
        `<div class="sec-sm" style="margin:10px 0 0">Propuesta del Grupo 14 · ramos de la base del reto</div>`,
        ...["Vida", "Viajes", "Mascotas", "Hogar"].map(r => item(ramoIcon(r), product(S, r).title, `data-a="offer" data-r="${r}"`, {chip: chip(r), sub: `${product(S, r).price}${product(S, r).concept ? " · producto por negociar" : ""}`, dim: C[r] && C[r].status === "ineligible"})),
      ],
    };
    return `<div class="hdr-title">Explora tus productos</div>
      <div class="segtabs" role="tablist">${[["ahorro", "Ahorro"], ["inversion", "Inversión"], ["credito", "Crédito"], ["seguros", "Seguros"]].map(([k, l]) => `<button role="tab" aria-selected="${t === k}" data-a="xt" data-t="${k}">${l}</button>`).join("")}</div>
      <div class="plist">${lists[t].join("")}</div><div style="height:22px"></div>`;
  },

  cuenta(S) {
    const c = S.B.client;
    return `${hdr("Cuenta de ahorros", {right: `<button class="act" data-a="go" data-s="ajustes" aria-label="Ajustes">${I.gear}</button>`})}
      <div class="acct-no">No. ${esc(c.account)} <span style="color:var(--mist)">${I.share}</span></div>
      <div class="acct-bal"><div class="k">Saldo disponible</div><div class="v">${S.hide ? "••••••" : money(S.balance)} <button class="eye" data-a="hide" aria-label="Mostrar u ocultar saldo">${S.hide ? I.eye : I.eyeOff}</button></div><div class="t">Saldo total ${S.hide ? "••••••" : money(S.balance)}</div></div>
      <div class="tiles">
        <button class="tile" data-a="toast" data-m="Recargar cuenta queda fuera de este prototipo"><span class="sq">${I.up}</span>Recargar cuenta</button>
        <button class="tile" data-a="go" data-s="transfer" data-p="breb"><span class="sq"><span class="breb">Bre-B</span></span>Pagos inmediatos</button>
        <button class="tile" data-a="go" data-s="transfer" data-p="enviar"><span class="sq">${I.send}</span>Transferir plata</button>
        <button class="tile" data-a="toast" data-m="Pagos y recargas queda fuera de este prototipo"><span class="sq">${I.receipt}</span>Pagos y recargas</button>
        <button class="tile" data-a="go" data-s="mapa"><span class="sq">${I.down}</span>Retirar plata</button>
      </div>
      <div class="sec"><h3>Movimientos</h3></div>
      <div class="chips" role="group" aria-label="Filtrar">${[["todos", "Todos"], ["ingresos", "Ingresos"], ["gastos", "Gastos"], ["pendientes", "Pendientes"]].map(([k, l]) => `<button data-a="grp" data-g="${k}" aria-pressed="${S.mg === k}">${l}</button>`).join("")}</div>
      <label class="searchbox">${I.search}<input data-in="search" type="search" placeholder="Busca un comercio o categoría" value="${esc(S.mq)}" autocomplete="off"></label>
      <div class="mov-sum" id="movSum"></div>
      <div id="movList">${skeletonRows(6)}</div><div id="movMore"></div>`;
  },

  ajustes(S) {
    const rows = [["lock", "Bloquear cuenta"], ["gauge", "Editar límites diarios"], ["receipt", "GMF(4x1000)"], ["book", "Ver cuentas inscritas"], ["doc", "Extractos y documentos"], ["pie", "Rentabilidad y tarifas"], ["trash", "Eliminar cuenta de ahorros"]];
    return `${hdr("Ajustes de cuenta")}<div style="text-align:center;color:var(--mist);font-size:14px">Cuenta No.</div>
      <div class="acct-no" style="font-size:24px;font-weight:700">${esc(S.B.client.account)}</div>
      <div class="settings">${rows.map(([i, t]) => `<button class="srow" data-a="toast" data-m="${t}: fuera de este prototipo">${I[i]}<span>${t}</span>${I.chev}</button>`).join("")}</div><div style="height:22px"></div>`;
  },

  mov(S) {
    const D = S.detail;
    if (!D || D.loading) return `${hdr("Detalle")}<div class="det"><span class="ic" style="animation:pulse 1.2s infinite"></span></div>`;
    const t = D.row, sig = D.signal;
    return `${hdr("Detalle")}
      <div class="det"><span class="ic">${I[t.icon] || I.dots}</span><div class="amt ${t.amount > 0 ? "in" : ""}">${t.amount > 0 ? "+" : ""}${money(t.amount)}</div><div class="n">${esc(t.label)}</div><span class="pill ok">Aprobado</span></div>
      <div class="pad"><div class="card" style="padding:4px 16px">
        <div class="kv"><span>Fecha</span><span>${dateLong(t.date)}</span></div>
        <div class="kv"><span>Categoría</span><span>${esc(t.cat_label)}</span></div>
        <div class="kv"><span>Medio</span><span>${esc(t.channel)}</span></div>
        ${t.mcc ? `<div class="kv"><span>Código del comercio (MCC)</span><span>${esc(t.mcc)}</span></div>` : ""}
        <div class="kv"><span>Referencia</span><span>${esc(t.id)}</span></div>
      </div></div>
      ${D.same_count > 1 ? `<div class="pad" style="margin-top:12px"><div class="card row" style="font-size:13px"><span style="color:var(--mist)">Este año en <b style="color:#fff">${esc(t.label)}</b></span><span>${D.same_count} veces · ${money(Math.abs(D.same_total))}</span></div></div>` : ""}
      <div class="pad" style="margin-top:14px">${sig
        ? anno("Lo que lee el motor", `<div class="anno-t">Alimenta la señal «${esc(sig.name)}» (${esc(sig.ramo)})</div><div>${esc(sig.headline)}. Regla: ${esc(sig.rule)}.</div><div class="anno-f">Fuerza: ${sig.strength}</div>`)
        : anno("Lo que lee el motor", `<div>Este movimiento no alimenta ninguna señal de seguros. Solo cuenta para Tu año en Lulo.</div>`)}</div>
      <div class="actions"><button class="btn ghost" data-a="toast" data-m="Reporte enviado. Te contactaremos en 24 horas">Reportar un problema</button></div>`;
  },

  alertas(S) {
    const groups = {};
    for (const n of S.notifs) (groups[n.date] = groups[n.date] || []).push(n);
    const dates = Object.keys(groups).sort().reverse();
    const B = S.banner;
    const top = S.topBannerClosed ? "" : B
      ? `<div class="banner-top" role="button" data-a="banner-open"><b>Recomendado para ti: ${esc(B.title)}</b><p>${esc(strip(B.why))}</p><span class="src">Banner pasivo · no cuenta como contacto</span><button class="x" data-a="top-close" aria-label="Cerrar">${I.close}</button></div>`
      : `<div class="banner-top" role="button" data-a="go" data-s="credito"><b>¡Pide tu Lulo crédito cuando quieras!</b><p>Un crédito libre destino desde 2 hasta 50 millones.</p><button class="x" data-a="top-close" aria-label="Cerrar">${I.close}</button></div>`;
    return `${hdr("Alertas", {right: `<button class="act" data-a="read-all" aria-label="Buscar y marcar como leído">${I.search}</button>`})}${top}
      <div class="alist">${dates.map(d => `<div class="dh">${dateHeader(d)}</div>${groups[d].map(n => `<button class="arow${n.unread ? " unread" : ""}" data-a="notif" data-id="${n.id}"><i class="rd"></i><span class="ci">${I[n.icon] || I.shield}</span><span class="tx"><b>${esc(n.t)}</b><span>${esc(n.b)}</span></span><time>${esc(n.time)}</time></button>`).join("")}`).join("")}</div>
      <div class="nomore">No hay más notificaciones disponibles</div>`;
  },

  ayuda(S) {
    const rows = [["question", "Preguntas frecuentes"], ["clock", "Estado de tus casos"], ["person", "Chatea con nosotros"], ["chat", "Déjanos un mensaje (PQRS)"]];
    return `${hdr("Centro de ayuda")}
      <svg viewBox="0 0 390 230" style="width:100%;display:block"><rect x="-20" y="30" width="200" height="56" rx="14" fill="#2B3550" opacity=".5"/><rect x="240" y="60" width="180" height="56" rx="14" fill="#2B3550" opacity=".5"/><circle cx="150" cy="95" r="22" fill="#5A6A8C"/><rect x="185" y="72" width="110" height="44" rx="14" fill="#E6E9EF"/><circle cx="420" cy="140" r="0"/><rect x="150" y="150" width="110" height="44" rx="14" fill="#DFF2FF"/><circle cx="290" cy="172" r="22" fill="#C69C8A"/><circle cx="222" cy="94" r="3" fill="#8E93A6"/><circle cx="240" cy="94" r="3" fill="#8E93A6"/><circle cx="258" cy="94" r="3" fill="#8E93A6"/><circle cx="187" cy="172" r="3" fill="#8E93A6"/><circle cx="205" cy="172" r="3" fill="#8E93A6"/><circle cx="223" cy="172" r="3" fill="#8E93A6"/></svg>
      <div class="sec" style="margin-top:6px"><h3 style="font-size:20px">¿En qué te podemos ayudar?</h3></div>
      <div class="settings light">${rows.map(([i, t]) => `<button class="srow light" data-a="toast" data-m="${t}: fuera de este prototipo">${I[i]}<span>${t}</span>${I.chev}</button>`).join("")}</div><div style="height:22px"></div>`;
  },

  perfil(S) {
    const c = S.B.client;
    return `${hdr("Perfil")}
      <div class="pad row" style="justify-content:flex-start;gap:14px">${av(S, "lg")}<div><div class="ttl" style="font-size:17px">${esc(c.name)}</div><div class="meta" style="margin-top:2px">${c.source === "persona" ? `Cliente Lulo desde ${c.since} · ${esc(c.city)}` : `${esc(c.occupation)} · ${esc(c.age_band)} años · ${esc(c.segment)}`}</div></div></div>
      <div class="sec-sm">Notificaciones</div>
      <div class="stack">
        <div class="card"><div class="row"><div><div class="ttl">Sugerencias de seguros</div><div class="meta">Según lo que haces en la app</div></div><button class="switch" role="switch" aria-checked="${S.sugg}" aria-label="Sugerencias de seguros" data-a="sugg"></button></div></div>
        <div class="card"><div class="row"><div><div class="ttl">Avisos de vencimiento</div><div class="meta">SOAT y pólizas</div></div><button class="switch" role="switch" aria-checked="${S.remind}" aria-label="Avisos de vencimiento" data-a="remind"></button></div>
          <div class="meta" style="margin:14px 0 8px">Avísame con</div>
          <div class="seg">${[30, 15, 7].map(d => `<button aria-pressed="${S.alertDays === d}" data-a="days" data-d="${d}">${d} días</button>`).join("")}</div></div>
      </div>
      <div class="sec-sm">Privacidad</div>
      <div class="stack"><div class="card"><div class="row"><div><div class="ttl">Usar mis movimientos para ofertas</div><div class="meta">Tu año en Lulo y sugerencias · Ley 1581 de 2012</div></div><button class="switch" role="switch" aria-checked="${S.consent}" aria-label="Usar mis movimientos" data-a="consent"></button></div></div></div>
      <div class="sec-sm">Mis productos</div>
      <div class="settings">
        <button class="srow" data-a="go" data-s="cuenta">${I.account}<span>Lulo Cuenta</span>${I.chev}</button>
        <button class="srow" data-a="go" data-s="card">${I.card}<span>Tarjeta débito ••${c.card_last4}</span>${I.chev}</button>
        <button class="srow" data-a="go" data-s="credito">${I.moneybag}<span>${S.credit ? "Lulo Crédito" : "Crédito de libre inversión"}</span>${I.chev}</button>
        <button class="srow" data-a="go" data-s="bolsillos">${I.pocket}<span>Bolsillos Flex (${S.pockets.length})</span>${I.chev}</button>
      </div>
      <div class="actions"><button class="btn ghost" data-a="logout">${I.lock} Cerrar sesión</button></div>`;
  },

  card(S) {
    const cardMovs = allRows(S).filter(m => m.channel && m.channel.startsWith("Tarjeta")).slice(0, 5);
    return `${hdr("Tarjeta de débito")}<div class="pad">${cardHTML(S, true)}</div>
      <div class="stack" style="margin-top:18px">
        <div class="card"><div class="row"><div><div class="ttl">Congelar tarjeta</div><div class="meta">Bloquea compras mientras la encuentras</div></div><button class="switch" role="switch" aria-checked="${S.cardFrozen}" aria-label="Congelar tarjeta" data-a="freeze"></button></div></div>
        <div class="card" style="padding:4px 16px"><div class="kv"><span>Número</span><span>•••• ${S.B.client.card_last4}</span></div><div class="kv"><span>Tipo</span><span>Débito digital</span></div></div>
      </div>
      <div class="sec-sm">Compras recientes con tarjeta</div>${cardMovs.map(m => movRow(m, S.B.as_of)).join("") || `<div class="empty-st">Sin compras con tarjeta en los últimos movimientos.</div>`}<div style="height:18px"></div>`;
  },

  bolsillos(S) {
    const total = S.pockets.reduce((a, p) => a + p.saved, 0);
    return `${hdr("Bolsillos Flex")}<div class="pad"><div class="sub" style="margin:0">Tienes ahorrado</div><div class="figure">${S.hide ? "$ ••••••" : money(total)}</div></div>
      <div class="stack" style="margin-top:16px">${S.pockets.map(p => {
        const pct = p.goal ? Math.min(100, Math.round(p.saved / p.goal * 100)) : null;
        return `<button class="pcard" data-a="go" data-s="bolsillo" data-p="${p.id}"><span class="pi" style="font-size:20px">${p.emoji}</span><span class="pt"><b>${esc(p.name)}</b><span>${p.note ? esc(p.note) + " · " : ""}${p.deposits} abonos</span>${p.goal ? `<div class="bar"><i style="width:${pct}%"></i></div>` : ""}</span><span class="ttl">${money(p.saved)}</span></button>`;
      }).join("") || `<div class="bigcard"><span class="ph"></span><b>Ordena tu plata, ahorra y cumple tus sueños</b></div>`}
      <button class="pcard" data-a="toast" data-m="Crear bolsillos queda fuera de este prototipo" style="background:none;border:1.5px dashed #4A5674"><span class="pi">${I.plus.replace(/width="30" height="30"/, 'width="20" height="20"')}</span><span class="pt"><b>Crea un bolsillo</b></span></button></div><div style="height:18px"></div>`;
  },

  bolsillo(S) {
    const p = S.pockets.find(x => x.id === S.params.id);
    const pct = p.goal ? Math.min(100, Math.round(p.saved / p.goal * 100)) : null;
    const feeds = {Viajes: "Viajes", Mascotas: "Mascotas", Vivienda: "Hogar"}[p.type];
    return `${hdr(esc(p.name))}
      <div class="det"><span class="ic" style="font-size:30px">${p.emoji}</span><div class="amt">${money(p.saved)}</div><div class="n">${p.goal ? `de ${money(p.goal)}` : `${p.deposits} abonos`}${p.note ? ` · ${esc(p.note)}` : ""}</div></div>
      ${p.goal ? `<div class="pad"><div class="bar thick"><i style="width:${pct}%"></i></div><div class="meta" style="text-align:right">${pct}% de tu meta</div></div>` : ""}
      <div class="actions" style="padding-bottom:6px"><button class="btn primary" data-a="cajita-abonar" data-id="${p.id}">Abonar</button></div>
      <div class="pad">${feeds ? anno("Lo que lee el motor", `<div>Bolsillo de tipo «${esc(p.type)}»: cada abono alimenta la señal de ${esc(feeds)} y puede disparar ese seguro.</div>`) : anno("Lo que lee el motor", `<div>Bolsillo de tipo «${esc(p.type)}»: no alimenta ninguna señal de seguros.</div>`)}</div>
      <div class="sec-sm">Últimos abonos</div>
      <div class="stack">${p.history.slice(0, 6).map(h => `<div class="kv"><span>${dateShort(h.date)}</span><span>+${money(h.a)}</span></div>`).join("") || `<p class="meta">Todavía no hay abonos.</p>`}</div><div style="height:18px"></div>`;
  },

  transfer(S) {
    const breb = S.params.mode === "breb";
    return `${hdr(breb ? "Pagos inmediatos" : "Transferir plata")}
      ${breb ? `<div class="pad"><p class="sub" style="margin:0 0 4px">Envía al instante a cualquier banco con una llave Bre-B: celular, correo o @alias.</p></div>` : ""}
      <label class="searchbox"><span style="opacity:.7">${breb ? "@" : I.search}</span><input placeholder="${breb ? "Escribe la llave" : "Nombre, celular o llave"}"></label>
      <div class="sec-sm">Frecuentes</div>
      ${S.B.contacts.map(c => `<button class="crow" data-a="pick-contact" data-id="${c.id}"><span class="av sm" style="background:var(--card);color:#fff">${esc(initials(c.name))}</span><span class="t"><b>${esc(c.name)}</b><span>${esc(c.key)} · ${esc(c.bank)}</span></span>${c.dependent ? `<span class="dep">fija</span>` : ""}${I.chev}</button>`).join("")}
      <div style="height:18px"></div>`;
  },

  amount(S) {
    const F = S.flow;
    const who = F.kind === "transfer" ? `Para <b>${esc(F.contact.name)}</b> · ${esc(F.contact.key)}` : `A tu bolsillo <b>${esc(F.cajita.emoji)} ${esc(F.cajita.name)}</b>`;
    return `${hdr(flowTitle[F.kind])}
      <div class="amt-wrap"><div class="amt-to">${who}</div><div class="amt" id="amtDisplay">${money(F.amount || 0)}</div>
        <div class="amt-sub" id="amtSub">Disponible ${money(S.balance)}</div>
        ${(F.suggest || []).length ? `<div class="amt-chips">${F.suggest.map(v => `<button data-a="amt-set" data-v="${v}">${money(v)}</button>`).join("")}</div>` : ""}</div>
      ${keypad()}
      <div class="sticky"><button class="btn primary" data-a="amt-next" id="amtNext" ${F.amount > 0 && F.amount <= S.balance ? "" : "disabled"}>Continuar</button></div>`;
  },

  confirm(S) {
    const F = S.flow;
    const rows = {
      transfer: [["Para", F.contact?.name], ["Llave", F.contact?.key], ["Banco", F.contact?.bank], ["Costo", "$0"], ["Sale de", "Lulo Cuenta"]],
      cajita: [["Bolsillo", `${F.cajita?.emoji} ${F.cajita?.name}`], ["Lleva ahorrado", money(F.cajita?.saved || 0)], ["Sale de", "Lulo Cuenta"]],
      cuota: [["Crédito", "Lulo Crédito"], ["Cuota", S.credit?.details ? `${(S.credit?.paid || 0) + 1} de ${S.credit?.cuotas}` : "Próxima cuota"], ["Sale de", "Lulo Cuenta"]],
      desembolso: [["Plazo", `${F.cuotas} cuotas`], ["Cuota aproximada", money(F.cuota || 0)], ["Tasa", "1,79% M.V. (ilustrativa)"], ["Llega a", "Lulo Cuenta"]],
    }[F.kind];
    const verb = {transfer: "Transferir", cajita: "Abonar", cuota: "Pagar", desembolso: "Solicitar"}[F.kind];
    return `${hdr("Revisa y confirma")}
      <div class="det"><div class="sub" style="margin:0">${{transfer: "Vas a transferir", cajita: "Vas a abonar", cuota: "Vas a pagar", desembolso: "Vas a recibir"}[F.kind]}</div><div class="amt">${money(F.amount)}</div></div>
      <div class="pad"><div class="card" style="padding:4px 16px">${rows.map(([k, v]) => `<div class="kv"><span>${k}</span><span>${esc(v)}</span></div>`).join("")}</div></div>
      ${F.kind === "desembolso" && !hasRamo(S, "Pago protegido") ? `<div class="pad" style="margin-top:12px"><div class="why">Este crédito todavía no tiene pago protegido.</div></div>` : ""}
      <div class="actions"><button class="btn primary" data-a="confirm">${verb} ${money(F.amount)}</button><button class="btn ghost" data-a="back">Cambiar</button></div>`;
  },

  processing(S) {
    const t = {transfer: "Enviando tu plata…", cajita: "Moviendo tu plata al bolsillo…", cuota: "Pagando tu cuota…", desembolso: "Aprobando tu crédito…"}[S.flow.kind];
    return `<div class="spinner"></div><p class="sub" style="text-align:center">${t}</p>`;
  },

  success(S) {
    const F = S.flow, R = F.result || {};
    const title = {transfer: `Transferiste ${money(F.amount)}`, cajita: `Abonaste ${money(F.amount)}`, cuota: "Pagaste tu cuota", desembolso: "Tu crédito ya está en tu cuenta"}[F.kind];
    const sub = {transfer: `A ${esc(F.contact?.name)}. Le llega en segundos.`, cajita: `Tu bolsillo «${esc(F.cajita?.name)}» ya lleva ${money(F.cajita?.saved || 0)}.`,
      cuota: "Cuota de Lulo Crédito pagada.", desembolso: `${money(F.amount)} a ${F.cuotas} cuotas de ${money(F.cuota)}.`}[F.kind];
    return `<div class="success"><div class="ring">${I.check}</div><h2 class="h-big" style="margin-top:22px">${title}</h2><p class="sub">${sub}</p></div>
      <div class="pad" style="margin-top:18px"><div class="card" style="padding:4px 16px"><div class="kv"><span>Referencia</span><span>${esc(R.ref || "—")}</span></div><div class="kv"><span>Fecha</span><span>${dateLong(S.B.as_of)}</span></div></div></div>
      ${R.note ? `<div class="pad" style="margin-top:14px">${anno("Lo que lee el motor", `<div>${R.note}</div>${R.focus ? `<div class="anno-f">El motor revisa este evento ahora mismo.</div>` : ""}`)}</div>` : ""}
      <div class="actions"><button class="btn primary" data-a="flow-done">Listo</button><button class="btn ghost" data-a="toast" data-m="Comprobante listo para compartir">${I.share} Compartir comprobante</button></div>`;
  },

  credito(S) {
    const C = S.credit, pre = S.B.client.preapproved;
    if (!C) {
      return `${hdr("Crédito")}<div class="light-hero"><b style="max-width:14ch">¡Pide tu Lulo crédito cuando quieras!</b><p>Un crédito libre destino desde 2 hasta 50 millones.${pre ? ` Tienes ${money(pre)} preaprobados.` : ""}</p><button class="go" data-a="go" data-s="creditReq">Saber más</button>${art("coin")}</div>
        <div class="pad" style="margin-top:16px">${anno("Lo que lee el motor", "<div>Un desembolso es un momento único: el motor revisa si el crédito tiene pago protegido y, si no, lo ofrece en ese instante (fecha límite primero, reglas v1.1).</div>")}</div>`;
    }
    if (!C.details) {
      return `${hdr("Lulo Crédito")}<div class="stack"><div class="card"><div class="ttl">Tienes un crédito activo</div><div class="meta">La base del reto solo indica que el crédito está activo; no trae monto ni cuotas.</div></div>
        <div class="card ${C.protected ? "" : ""}"><div class="row"><span class="ttl">Pago protegido</span><span class="pill ${C.protected ? "ok" : "warn"}">${C.protected ? "Incluido" : "Sin protección"}</span></div></div></div>
        <div class="actions"><button class="btn primary" data-a="go" data-s="creditReq">Pedir más dinero</button><button class="btn ghost" data-a="pay-cuota">Pagar una cuota</button></div>`;
    }
    const pct = Math.round(C.paid / C.cuotas * 100);
    return `${hdr("Lulo Crédito")}
      <div class="pad"><div class="card"><div class="meta" style="margin:0">Te falta pagar</div><div class="figure">${money(C.remaining)}</div><div class="bar"><i style="width:${pct}%"></i></div><div class="row meta"><span>${C.paid} de ${C.cuotas} cuotas</span><span>${pct}%</span></div></div></div>
      <div class="pad" style="margin-top:12px"><div class="card" style="padding:4px 16px"><div class="kv"><span>Cuota mensual</span><span>${money(C.cuota)}</span></div><div class="kv"><span>Próximo pago</span><span>${dateShort(C.next_date)}</span></div><div class="kv"><span>Monto desembolsado</span><span>${money(C.amount)}</span></div><div class="kv"><span>Tasa</span><span>${C.rate}</span></div></div></div>
      <div class="sec-sm">Tu protección</div>
      <div class="pad"><div class="card"><div class="row"><span class="ttl">Pago protegido</span><span class="pill ${C.protected || hasRamo(S, "Pago protegido") ? "ok" : "warn"}">${C.protected || hasRamo(S, "Pago protegido") ? "Incluido" : "Sin protección"}</span></div>
        <div class="meta">${C.protected ? `Si pierdes el empleo, tus cuotas de ${money(C.cuota)} siguen cubiertas.` : "Tus cuotas no están protegidas si pierdes tus ingresos."}</div>
        ${C.protected && !S.known["Pago protegido"] ? `<div class="q-btns"><button data-a="known" data-v="Sí">Sí, lo sabía</button><button data-a="known" data-v="No">No sabía</button></div><div class="meta" style="color:var(--pink)">¿Sabías que tenías esta protección?</div>` : ""}</div></div>
      <div class="actions"><button class="btn primary" data-a="pay-cuota">Pagar cuota de ${money(C.cuota)}</button><button class="btn ghost" data-a="go" data-s="creditReq">Pedir más dinero</button></div>`;
  },

  creditReq(S) {
    const max = S.credit ? 9000000 : (S.B.client.preapproved || 10000000);
    const opts = [2000000, Math.round(max / 2 / 1e5) * 1e5, max];
    const F = S.flow;
    return `${hdr("Solicitar crédito")}
      <div class="pad"><div class="sub" style="margin:0">¿Cuánto necesitas?</div><div class="figure">${money(F.amount)}</div></div>
      <div class="pad" style="margin-top:12px"><div class="seg">${opts.map(v => `<button aria-pressed="${F.amount === v}" data-a="cr-amt" data-v="${v}">${(v / 1e6).toFixed(1).replace(".0", "").replace(".", ",")} M</button>`).join("")}</div></div>
      <div class="sec-sm">¿A cuántas cuotas?</div>
      <div class="pad"><div class="seg">${[12, 18, 24].map(n => `<button aria-pressed="${F.cuotas === n}" data-a="cr-n" data-v="${n}">${n} meses</button>`).join("")}</div></div>
      <div class="pad" style="margin-top:16px"><div class="card" style="padding:4px 16px"><div class="kv"><span>Cuota aproximada</span><span style="font-weight:700">${money(creditCuota(F.amount, F.cuotas))}</span></div><div class="kv"><span>Tasa</span><span>1,79% M.V. (ilustrativa)</span></div><div class="kv"><span>Llega a</span><span>Lulo Cuenta</span></div></div></div>
      <div class="actions"><button class="btn primary" data-a="cr-next">Continuar</button></div>`;
  },

  tcredito(S) {
    return `${hdr("Tarjeta de crédito")}<div class="light-hero"><div class="k">Tarjeta de Crédito Lulo</div><b>Pide tu Tarjeta de Crédito Lulo</b><p>Sin cuota de manejo y con beneficios para todos los días.</p><button class="go" data-a="toast" data-m="La tarjeta de crédito queda fuera de este prototipo">Empezar</button>${art("coin")}</div>`;
  },

  cdt(S) {
    const rows = [["payout", "Abre tu CDT desde $100,000 de forma 100% digital y sin papeleo."], ["gauge", "Gana rendimientos de hasta 13% E.A."], ["clock", "Aprovecha y activa la renovación automática mientras creas tu CDT."], ["lock", "Tu CDT está protegido por el Seguro de Depósitos de Fogafin."]];
    return `${hdr("Beneficios del CDT Lulo")}
      <svg viewBox="0 0 390 180" style="width:100%;display:block"><polygon points="195,20 265,60 265,140 195,180 125,140 125,60" fill="#2B3550"/><rect x="165" y="70" width="60" height="70" rx="10" fill="#C8B6FF" opacity=".5"/><rect x="160" y="60" width="70" height="14" rx="5" fill="#C8B6FF"/><rect x="175" y="105" width="40" height="8" rx="3" fill="#FFB547"/><rect x="175" y="118" width="40" height="8" rx="3" fill="#FFB547"/><circle cx="240" cy="62" r="10" fill="#FFB547"/><path d="M110 120V80l-8 10M110 80l8 10" stroke="#62E3A0" stroke-width="5" fill="none"/></svg>
      <h2 class="h-big" style="text-align:center;font-size:21px;padding:0 30px;margin-bottom:22px">Aquí tu plata crece libre de tentaciones</h2>
      <div class="bullets">${rows.map(([i, t]) => `<div><span class="bi">${I[i]}</span><span>${t}</span></div>`).join("")}</div>
      <div class="sticky" style="margin-top:20px"><button class="btn primary" data-a="toast" data-m="Abrir un CDT queda fuera de este prototipo">Abrir CDT</button></div>`;
  },

  lulox(S) {
    return `${hdr("Billetera digital")}<div class="bigcard" style="margin-top:10px"><b style="font-size:30px;font-weight:800">lulo<sup style="font-size:12px">x</sup></b><b>Tu billetera digital</b><p class="sub">Fuera del alcance de este prototipo: se muestra para conservar la navegación de la app real.</p></div>`;
  },

  info(S) {
    return `${hdr("Seguro Nómina Protegida")}<div class="stack"><div class="card"><div class="ttl">Respaldo para tu Familia</div><div class="meta">Producto que ya aparece en la app de Lulo. La base del reto no trae sus datos (prima, comisión ni conversión), así que el motor v3 no lo ofrece: se muestra para conservar la navegación real.</div></div></div>`;
  },

  mapa(S) {
    return `${hdr("Mapa de cajeros", {right: `<button class="act" data-a="toast" data-m="Mapa ilustrativo: no usa tu ubicación">${I.target}</button>`})}
      <div class="map-full">${mapSVG(true)}</div>
      <div class="map-legend"><div><svg width="22" height="28" viewBox="0 0 22 30"><rect width="22" height="30" rx="4" fill="#E8FF00"/></svg>Retirar sin costo</div><div><svg width="22" height="28" viewBox="0 0 22 30"><rect width="22" height="30" rx="4" fill="#A9B4CC"/></svg>Retirar te cuesta $6.850</div></div>`;
  },

  soatIntro(S) {
    return `${hdr("", {})}
      <div class="insurer"><span class="vig">VIGILADO · SUPERINTENDENCIA FINANCIERA DE COLOMBIA</span><span class="wm"><span><small>seguros</small>mundial</span></span></div>
      <h2 class="h-big" style="text-align:center;font-size:20px;margin-bottom:26px">¡Viaja tranqui con el SOAT al día!</h2>
      <div class="bullets"><div><span class="bi">${I.stopwatch}</span><span>Compra o renueva el SOAT en minutos, sin filas ni papeleo.</span></div><div><span class="bi">${I.payout}</span><span>Paga al toque desde tu Lulo cuenta.</span></div><div><span class="bi">${I.carsDoc}</span><span>Recibe la póliza directo en tu correo o teléfono en un parpadeo.</span></div></div>
      <div class="disclaimer">Este es un producto ofrecido por Seguros Mundial, una compañía de seguros independiente de Lulo bank.</div>
      <div class="sticky" style="margin-top:24px"><button class="btn primary" data-a="go" data-s="soatForm">Cotizar seguro</button></div>`;
  },

  soatForm(S) {
    const F = S.soat;
    const ok = /^[A-Z]{3}-?\d{2}[0-9A-Z]$/.test((F.placa || "").toUpperCase()) && F.accept;
    return `${hdr("Datos para la cotización", {right: `<button class="act" data-a="tab" data-t="home" aria-label="Cerrar">${I.close}</button>`})}
      <h3 style="font-size:19px;margin:6px 22px 16px">¿Quién es el propietario del vehículo?</h3>
      <div class="radio2"><button aria-pressed="${F.owner === "tu"}" data-a="soat-owner" data-v="tu"><i></i>Tú</button><button aria-pressed="${F.owner === "otro"}" data-a="soat-owner" data-v="otro"><i></i>Otra persona</button></div>
      <h3 style="font-size:19px;margin:28px 22px 14px">Ingresa los datos del vehículo</h3>
      <div class="field"><label for="placa">Placa</label><input id="placa" data-in="placa" maxlength="7" placeholder="XXX000" value="${esc(F.placa || "")}" autocomplete="off"></div>
      <div class="infobox">Usaremos estos datos para cualquier información relacionada con el SOAT.</div>
      <button class="check" aria-pressed="${!!F.accept}" data-a="soat-accept"><i>${F.accept ? I.check.replace(/width="46" height="46"/, 'width="16" height="16"') : ""}</i><span>He leído y acepto el tratamiento de datos personales de <u>Seguros Mundial.</u></span></button>
      <div class="sticky" style="margin-top:40px"><button class="btn primary" data-a="soat-continue" id="soatGo" ${ok ? "" : "disabled"}>Continuar</button></div>`;
  },

  renew(S) {
    const car = S.B.car, Q = quote(S);
    const P = product(S, "SOAT");
    if (!car || car.days == null || !Q) {
      return `${hdr("Tu cotización")}
        <div class="pad"><div class="card"><div class="row"><span class="ttl">${esc((S.soat.placa || "").toUpperCase() || "Tu vehículo")}</span><span class="pill mut">Nueva póliza</span></div><div class="meta">Seguros Mundial · vigencia de un año</div></div></div>
        <div class="sec-sm">Resumen de pago</div>
        <div class="pad"><div class="card" style="padding:4px 16px"><div class="kv"><span>Valor de referencia</span><span style="font-weight:700">${money(P.premium || 0)}</span></div><div class="kv"><span>Se paga desde</span><span>Lulo Cuenta · ${money(S.balance)}</span></div></div></div>
        <div class="pad" style="margin-top:12px"><div class="why">El valor es la prima promedio del SOAT en la base del reto. El valor real lo fija la tarifa regulada según el vehículo.</div></div>
        <div class="actions"><button class="btn primary" data-a="pay" ${S.balance < (P.premium || 0) ? "disabled" : ""}>Pagar ${money(P.premium || 0)}</button><button class="btn ghost" data-a="postpone">Recuérdamelo después</button></div>`;
    }
    const pct = Math.max(4, Math.min(100, Math.round((365 - car.days) / 365 * 100)));
    return `${hdr("Renovar SOAT")}
      <div class="pad"><div class="card"><div class="row"><span class="ttl">${esc(car.plate || (S.soat.placa || "").toUpperCase() || "Tu vehículo")}</span><span class="pill ${car.days <= 10 ? "bad" : "warn"}">Vence en ${car.days} días</span></div><div class="meta">${esc(car.model || "")}${car.model ? " · " : ""}${esc(car.insurer)}</div><div class="bar"><i style="width:${pct}%;background:var(--warn)"></i></div></div></div>
      <div class="sec-sm">Nueva vigencia</div>
      <div class="pad"><div class="card" style="padding:4px 16px"><div class="kv"><span>Desde</span><span>${dateShort(car.new_from)} ${car.new_from.slice(0, 4)}</span></div><div class="kv"><span>Hasta</span><span>${dateShort(car.new_to)} ${car.new_to.slice(0, 4)}</span></div></div></div>
      <div class="sec-sm">Resumen de pago</div>
      <div class="pad"><div class="card" style="padding:4px 16px">
        <div class="kv"><span>Valor SOAT</span><span>${money(Q.base)}</span></div>
        <div class="kv"><span>Descuento por renovar antes</span><span style="color:var(--lime)">${money(-Q.discount)}</span></div>
        <div class="kv"><span style="color:#fff;font-weight:600">Total</span><span style="font-weight:700;font-size:16px">${money(Q.total)}</span></div>
        <div class="kv"><span>Se paga desde</span><span>Lulo Cuenta · ${money(S.balance)}</span></div></div></div>
      <div class="pad" style="margin-top:12px"><div class="why">${car.source === "externa" ? "Tu SOAT actual es con otra aseguradora: renovarlo aquí es captura de canal. " : ""}El descuento por anticipación es una hipótesis a validar con Jurídico (la tarifa del SOAT es regulada).</div></div>
      <div class="actions"><button class="btn primary" data-a="pay" ${S.balance < Q.total ? "disabled" : ""}>Pagar ${money(Q.total)}</button><button class="btn ghost" data-a="postpone">Recuérdamelo después</button></div>`;
  },

  paying(S) { return `<div class="spinner"></div><p class="sub" style="text-align:center">Procesando el pago con Seguros Mundial…</p>`; },

  done(S) {
    const car = S.B.car;
    return `<div class="success"><div class="ring">${I.check}</div><h2 class="h-big" style="margin-top:22px">Tu SOAT quedó al día</h2>
      <p class="sub">${car && car.new_to_long ? `Cubierto hasta el ${car.new_to_long}.` : "Recibirás la póliza en tu correo."} Te avisaremos ${S.alertDays} días antes del próximo vencimiento.</p></div>
      <div class="actions" style="margin-top:20px"><button class="btn primary" data-a="tab" data-t="home">Volver al inicio</button><button class="btn ghost" data-a="tab" data-t="proteccion">Ver mi protección</button></div>`;
  },

  offer(S) {
    const r = S.offer, P = product(S, r), C = cands(S)[r] || null;
    const dec = (S.shown && S.shown.ramo === r && S.shown) || (S.banner && S.banner.ramo === r && S.banner) || (S.evaluation && S.evaluation.decision && S.evaluation.decision.ramo === r && S.evaluation.decision) || null;
    const has = hasRamo(S, r);
    const elig = !C || C.eligibility.ok;
    const why = dec ? dec.why : C && C.signal && C.signal.strength !== "ninguna" ? esc(C.signal.headline) + "." : null;
    return `${hdr(dec ? "Recomendado para ti" : esc(P.title))}
      <div class="pad"><div class="row" style="justify-content:flex-start;gap:8px;flex-wrap:wrap">${dec ? `<span class="pill new">Sugerencia</span>` : ""}${P.concept ? `<span class="pill hyp">Producto por negociar con la aseguradora</span>` : ""}${P.source === "prototipo" ? `<span class="pill mut">Fuera de la base: parámetros del prototipo</span>` : ""}${has ? `<span class="pill ok">Activo</span>` : ""}</div>
        <h2 class="h-big" style="margin-top:12px">${esc(P.title)}</h2><p class="sub">${P.partner ? `Con ${esc(P.partner)}` : "Aliado por definir"}</p></div>
      ${why ? `<div class="pad" style="margin-top:16px"><div class="why"><b>Por qué lo ves:</b> ${why}</div></div>` : ""}
      <div class="sec-sm">Qué cubre</div>
      <div class="pad"><ul class="list-check">${(P.covers || []).map(c => `<li>${esc(c)}</li>`).join("")}</ul></div>
      <div class="pad" style="margin-top:18px"><div class="card" style="padding:4px 16px"><div class="kv"><span>Valor</span><span style="font-weight:700">${esc(P.price)}</span></div><div class="kv"><span>Se paga desde</span><span>Lulo Cuenta</span></div>${P.requirement ? `<div class="kv"><span>Requisito</span><span>${esc(P.requirement)}</span></div>` : ""}</div></div>
      ${!elig && !has ? `<div class="pad" style="margin-top:12px"><div class="why"><b>No disponible para ti:</b> ${esc(C.eligibility.reasons.join("; "))}.</div></div>` : ""}
      <div class="actions">
        ${has ? `<button class="btn ghost" data-a="back">Ya lo tienes activo</button>` : `<button class="btn primary" data-a="accept" ${elig ? "" : "disabled"}>Activar seguro</button>
        <button class="btn ghost" data-a="later">Ahora no</button>
        ${dec ? `<button class="btn text" data-a="optout">No quiero sugerencias de este tipo</button>` : ""}`}
      </div>`;
  },

  proteccion(S) {
    const C = cands(S), prot = protections(S);
    const vol = prot.filter(p => p.voluntary);
    const ofr = Object.values(C).filter(c => c.status === "ofrecer" && !hasRamo(S, c.ramo) && c.ramo !== "Pago protegido")
      .sort((a, b) => (b.deadline - a.deadline) || ((b.ev || 0) - (a.ev || 0)));
    const dec = S.evaluation && S.evaluation.decision;
    const ext = S.B.policies.external;
    const no = Object.values(C).filter(c => ["weak", "ineligible", "cooldown", "external"].includes(c.status));
    const up = S.upcoming || [];
    const suggOff = !S.sugg || !S.consent;
    return `<div class="hdr-title">Tu protección</div>
      <div class="p-hero"><span class="n">${vol.length}</span><p>${vol.length === 1 ? "seguro voluntario activo" : "seguros voluntarios activos"}${prot.length > vol.length ? `, más ${prot.length - vol.length} ${prot.length - vol.length === 1 ? "protección incluida" : "protecciones incluidas"} con tus productos` : ""}.</p></div>
      ${prot.length ? `<div class="sec-sm">Con Lulo</div><div class="stack">${prot.map(p => `<div class="pcard${p.fresh ? " sug" : ""}"><span class="pi">${ramoIcon(p.ramo)}</span><span class="pt"><b>${esc(p.title)}</b><span>${p.partner ? esc(p.partner) + " · " : ""}${esc(p.sub)}${p.voluntary ? "" : " · no es un seguro voluntario"}</span></span></div>`).join("")}</div>` : ""}
      ${soatDue(S) ? `<div class="sec-sm">Por renovar</div><div class="stack"><button class="pcard sug" data-a="go" data-s="renew"><span class="pi">${I.car}</span><span class="pt"><b>SOAT ${esc(S.B.car.plate || "")}</b><span>Vence en ${S.B.car.days} días · ${S.B.car.source === "externa" ? "con otra aseguradora" : "con Lulo"}</span><span class="go">Renovar aquí</span></span></button></div>` : ""}
      ${suggOff ? `<div class="pad" style="margin-top:18px"><div class="why">${!S.consent ? "No autorizaste usar tus movimientos: no te sugerimos seguros. Puedes cambiarlo en Perfil." : "Apagaste las sugerencias de seguros en Perfil."}</div></div>` :
        ofr.length ? `<div class="sec-sm">Para ti</div><div class="stack">${ofr.map(c => `<button class="pcard sug" data-a="offer" data-r="${c.ramo}"><span class="pi">${ramoIcon(c.ramo)}</span><span class="pt"><b>${esc(c.title)}</b><span>${esc(c.price)}${c.deadline ? " · tiene fecha límite" : ""}</span><span class="why-s">${dec && dec.ramo === c.ramo ? dec.why : esc(c.signal.headline)}</span><span class="go">Ver más</span></span></button>`).join("")}</div>` : ""}
      ${ext.length ? `<div class="sec-sm">Con otra aseguradora</div><div class="stack">${ext.map(e => `<div class="pcard out"><span class="pi">${ramoIcon(e.ramo)}</span><span class="pt"><b>${esc(e.ramo)}</b><span>${e.status === "vigente" ? `Vigente hasta el ${dateShort(e.expires_on)} ${e.expires_on.slice(0, 4)}` : `Venció el ${dateShort(e.expires_on)} ${e.expires_on.slice(0, 4)}`} · ${money(e.amount)}</span></span></div>`).join("")}</div>` : ""}
      ${up.length ? `<div class="sec-sm">Próximamente</div><div class="stack">${up.map(u => `<div class="pcard"><span class="pi" style="color:var(--pink)">${I.clock}</span><span class="pt"><b>${esc(u.title)}</b><span>${esc(u.reason)}. Te avisamos el ${dateShort(u.date)} ${u.date.slice(0, 4)}.</span></span></div>`).join("")}</div>` : ""}
      ${no.length && !suggOff ? `<div class="sec-sm">Por qué no te ofrecemos…</div><div class="stack">${no.map(c => `<div class="pcard out"><span class="pi" style="color:var(--mist)">${ramoIcon(c.ramo)}</span><span class="pt"><b>${esc(c.title)} · ${STATUS_TXT[c.status]}</b><span>${esc(c.reason)}</span></span></div>`).join("")}</div>` : ""}
      <div style="height:24px"></div>`;
  },

  anio(S) {
    if (!S.consent) {
      return `<div class="hdr-title">Tu año en Lulo</div><div class="yr-hero off"><div class="k">Tu año en Lulo</div><div class="y">2026</div><p>Para armar tu resumen necesitamos tu autorización para usar tus movimientos.</p><button class="btn" data-a="consent-on">Autorizar y ver mi año</button></div>
        <div class="pad" style="margin-top:14px"><div class="card" style="font-size:12.5px;color:#C9D0DE;line-height:1.5">Tratamos tus datos según la Ley 1581 de 2012. Puedes retirar la autorización cuando quieras desde Perfil.</div></div>`;
    }
    const sw = {lime: "background:var(--lime);color:#101500", navy: "background:var(--card)", ink: "background:#0E1426;border:1px solid var(--line)", pink: "background:var(--pink);color:var(--ink)"};
    const st = c => {
      if (c.ask) return S.known[c.ask] ? ["Respondido", ""] : ["Pregunta", "soon"];
      const p = c.protect; if (!p) return ["", ""];
      if (p.ramo === "SOAT" && S.renewed.includes("SOAT")) return ["Al día", ""];
      if (p.ramo === "SOAT" && p.state === "offer" && ["renovacion", "captura"].includes(p.kind)) return ["Por renovar", "warn"];
      if (hasRamo(S, p.ramo) || p.state === "has") return ["Activo", ""];
      if (p.state === "soon") return ["Pronto", "soon"];
      if (p.state === "offer") return p.ramo === "SOAT" ? ["Por renovar", "warn"] : ["Para ti", "warn"];
      return ["", ""];
    };
    const kind = c => c.protect ? "Incluye un momento de protección" : c.ask ? "Incluye una pregunta" : c.id === "cierre" ? "Lo que tienes cubierto" : "Resumen";
    const chs = chapters(S);
    return `<div class="hdr-title">Tu año en Lulo</div><div class="yr-hero"><div class="k">Tus últimos 12 meses</div><div class="y">${S.B.as_of.slice(0, 4)}</div><p>Lo que viviste con Lulo, contado con tus movimientos.</p><button class="btn" data-a="st-open" data-i="0">Ver mi año</button></div>
      <div class="sec-sm">${chs.length - 1} capítulos</div>
      ${chs.slice(1).map((c, i) => { const [t, cl] = st(c); return `<button class="chap" data-a="st-open" data-i="${i + 1}"><span class="sw" style="${sw[c.theme]}">${i + 1}</span><span class="tx"><b>${c.name}</b><span>${kind(c)}</span></span><span class="st ${cl}">${t}</span></button>`; }).join("")}
      <div class="pad" style="margin-top:14px"><div class="card" style="font-size:12.5px;color:#C9D0DE;line-height:1.5">Lo armamos solo con tus movimientos en Lulo. Puedes apagar las sugerencias de seguros en Perfil.</div></div><div style="height:20px"></div>`;
  },

  yearLoading(S) {
    return `<div class="yr-load"><div class="yr-load-y">${S.B.as_of.slice(0, 4)}</div><div class="yr-load-t">Armando tu año…</div><div class="yr-load-bar"><i></i></div><div class="yr-load-s" id="yrLoadS">Leyendo ${num(S.B.movCount)} movimientos</div></div>`;
  },

  story(S) {
    const list = chapters(S), c = list[S.story], last = S.story === list.length - 1;
    return `<div class="story t-${c.theme}">
      <div class="st-prog">${list.map((_, i) => `<i class="${i <= S.story ? "on" : ""}"></i>`).join("")}</div>
      <div class="st-head"><span>Tu año en Lulo · ${S.story + 1} de ${list.length}</span><button class="st-x" data-a="st-close" aria-label="Cerrar">✕</button></div>
      <button class="st-zone prev" data-a="st-prev" aria-label="Capítulo anterior"></button><button class="st-zone next" data-a="st-next" aria-label="Siguiente capítulo"></button>
      <div class="st-body">${storyBody(S, c)}</div>${protectBlock(S, c)}
      <div class="st-nav"><button data-a="st-prev" ${S.story === 0 ? "disabled" : ""}>Anterior</button><button data-a="st-next">${last ? "Terminar" : "Siguiente"}</button></div>
    </div>`;
  },
};

export const PLUS_SHEET = S => `<div class="sheet" id="plusSheet"><h4>Lulo cuenta</h4><div class="tiles">
    <button class="tile" data-a="toast" data-m="Recargar cuenta queda fuera de este prototipo"><span class="sq">${I.up}</span>Recargar cuenta</button>
    <button class="tile" data-a="sheet-go" data-s="transfer" data-p="enviar"><span class="sq">${I.send}</span>Transferir plata</button>
    <button class="tile" data-a="toast" data-m="Pagos y recargas queda fuera de este prototipo"><span class="sq">${I.receipt}</span>Pagos y recargas</button>
    <button class="tile" data-a="sheet-go" data-s="mapa"><span class="sq">${I.down}</span>Retirar plata</button>
    <button class="tile" data-a="sheet-go" data-s="bolsillos"><span class="sq">${I.pocket}</span>Abonar a un bolsillo</button>
    <button class="tile" data-a="sheet-go" data-s="creditReq"><span class="sq">${I.moneybag}</span>Pedir crédito</button>
  </div><button class="close" data-a="sheet-close" aria-label="Cerrar">${I.close}</button></div>`;
