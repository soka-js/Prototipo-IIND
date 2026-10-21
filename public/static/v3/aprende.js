// Motor bayesiano en el panel: la probabilidad de cada decisión explicada por pasos, la pestaña «Aprendizaje»
// (qué sabe el motor, qué aprendió en la sesión y el laboratorio) y un gráfico de líneas sin dependencias.
import { esc, money, num } from "./util.js";

export const pc = (x, d = 1) => x == null ? "—" : `${(x * 100).toFixed(d).replace(".", ",")} %`;
const dec = (x, d = 2) => x == null ? "—" : Number(x).toFixed(d).replace(".", ",");
const sgn = (x, d = 0) => (x >= 0 ? "+" : "−") + `${Math.abs(x * 100).toFixed(d).replace(".", ",")} %`;

/* =================== probabilidad por pasos =================== */
export const PASO = {
  base: ["Base fuera del momento", "Campañas previas de Lulo (Campanas_Previas), sin el empujón del momento"],
  senal_media: ["Señal media", "Hipótesis del equipo: × 0,6 frente a una señal fuerte"],
  momento: ["Momento", "El evento pasó hace poco: estimado con las compras externas (Pagos_Seguros)"],
  afinidad: ["Afinidad", "Modelo M1 de parecido con quien ya tiene el seguro"],
  rasgos: ["Rasgos aprendidos", "Perfil y hábitos que las respuestas mostraron que importan"],
  cliente: ["Sus respuestas", "Apetito del cliente aprendido de lo que aceptó o rechazó"],
};
/** Barras horizontales: probabilidad después de cada paso; la última, con su intervalo al 90 %. */
export function probSteps(pr, opts = {}) {
  if (!pr) return "";
  const steps = pr.pasos, mx = Math.max(pr.ic90[1], ...steps.map(s => s.p)) * 1.08;
  const w = p => `${Math.max(1.5, p / mx * 100).toFixed(2)}%`;
  const rows = steps.map((s, i) => {
    const last = i === steps.length - 1, [n, src] = PASO[s.k];
    return `<div class="pw-row${last ? " fin" : ""}"><span class="pw-l"><b>${n}</b>${opts.compact ? "" : `<small>${src}</small>`}</span>
      <span class="pw-tr"><i style="width:${w(s.p)}"></i>${last ? `<em style="left:${w(pr.ic90[0])};width:calc(${w(pr.ic90[1])} - ${w(pr.ic90[0])})" title="Intervalo al 90 %"></em>` : ""}</span>
      <span class="pw-v">${s.factor ? `<small>× ${dec(s.factor)}</small>` : ""}${pc(s.p)}</span></div>`;
  }).join("");
  return `<div class="pw">${rows}<div class="pw-ic">P(acepta si la ve) ${pc(pr.p)} · entre ${pc(pr.ic90[0])} y ${pc(pr.ic90[1])} con 90 % de probabilidad${pr.rasgos_en_espera ? ` · ${pr.rasgos_en_espera} rasgos esperan respuestas para pesar` : ""}</div></div>`;
}

const OUT = {shown: "se mostró por push", banner: "va como banner pasivo (no cuenta como contacto)", queued: "espera en cola: la ventana está ocupada",
  control: "grupo de control: el motor decide pero no se muestra", optout: "el cliente apagó las sugerencias", noconsent: "sin autorización de datos: el motor no lee nada",
  weak: "señal débil: no se ofrece", ineligible: "no es elegible", has: "ya lo tiene", cooldown: "en espera: se le ofreció hace poco",
  external: "lo tiene con otra aseguradora", none: "no alimenta ningún seguro"};
const DATA_OF = {base: "Campanas_Previas", momento: "Pagos_Seguros", senal_media: "Movimientos", afinidad: "Clientes", rasgos: "Movimientos", cliente: "respuestas de la sesión"};

/** Tarjeta «Lo que acaba de decidir el motor», en lenguaje claro. */
export function decisionHTML(ev, src, title = (n) => n) {
  if (!ev) return "";
  const d = ev.decision, o = ev.outcome;
  if (!d) {
    return `<div class="dc-h"><span class="dc-k">${esc(src || "Evaluación")}</span><b>${esc(OUT[o] ? OUT[o][0].toUpperCase() + OUT[o].slice(1) : ev.label)}</b></div>
      <p class="dc-p">${esc(ev.message || "")}</p>`;
  }
  const pr = d.prob, reg = ev.regla || {};
  const datos = new Set(["Movimientos", "Elegibilidad", "Seguros_Mensual"]);
  if (pr) pr.pasos.forEach(s => datos.add(DATA_OF[s.k]));
  if (ev.channel) datos.add("Uso_App");
  return `<div class="dc-h"><span class="dc-k">${esc(src || "Evaluación")}</span><b>${esc(d.title)} · ${esc(OUT[o] || ev.label)}</b></div>
    <p class="dc-p"><b>Qué vio:</b> ${esc(d.why.replace(/<[^>]+>/g, ""))}</p>
    ${pr ? probSteps(pr, {compact: true}) : `<p class="dc-p">Momento único: se ofrece al instante, sin cálculo de valor esperado (no está en la base).</p>`}
    ${d.ev != null ? `<p class="dc-p"><b>Valor esperado:</b> ${pc(pr ? pr.p : null)} × ${money(d.valor || 0)} de comisión a 12 meses = <b>${money(d.ev)}</b>${d.ev_regla != null ? ` · con la regla anterior (v1.3): ${money(d.ev_regla)}` : ""}.${reg.ramo && !reg.coincide ? ` La regla anterior habría ofrecido <b>${esc(title(reg.ramo))}</b>.` : ""}${d.explora ? " Este cliente explora: el sorteo eligió una opción en la que el motor todavía duda." : ""}</p>` : ""}
    ${ev.channel ? `<p class="dc-p"><b>Canal:</b> ${ev.channel.channel === "push" ? "push" : "banner"} · ${esc(ev.channel.reason)}${d.alcance ? ` · la ve con probabilidad ${pc(d.alcance.p, 0)}` : ""}</p>` : ""}
    <div class="dc-data">${[...datos].map(x => `<span>${esc(x)}</span>`).join("")}</div>`;
}

/* =================== gráfico de líneas =================== */
// Énfasis: el motor en lima (la historia), la regla en azul, el techo y el piso en grises.
function niceStep(range, n) {
  const raw = range / n, p = Math.pow(10, Math.floor(Math.log10(raw))), f = raw / p;
  return (f < 1.5 ? 1 : f < 3 ? 2 : f < 7 ? 5 : 10) * p;
}
/** Dibuja un gráfico de líneas con leyenda, etiquetas al final, cruz de lectura y tabla equivalente. */
export function lineChart(el, spec) {
  const {series, x, yFmt = v => num(v), yTitle} = spec;
  const W = Math.max(300, el.clientWidth || 520), H = spec.height || 210, L = 48, R = 112, T = 12, B = 30;
  const all = series.flatMap(s => s.values);
  let lo = Math.min(...all), hi = Math.max(...all);
  const pad = (hi - lo) * 0.08 || Math.abs(hi) * 0.1 || 1;
  lo -= pad; hi += pad;
  const step = niceStep(hi - lo, 4);
  lo = Math.floor(lo / step) * step; hi = Math.ceil(hi / step) * step;
  const X = i => L + (W - L - R) * (x.length === 1 ? 0.5 : i / (x.length - 1));
  const Y = v => T + (H - T - B) * (1 - (v - lo) / (hi - lo));
  const ticks = [];
  for (let v = lo; v <= hi + step / 2; v += step) ticks.push(v);
  const xt = [0, ...[0.25, 0.5, 0.75].map(f => Math.round(f * (x.length - 1))), x.length - 1];
  const svg = [`<svg class="lc-svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(spec.label || "")}" tabindex="0">`];
  ticks.forEach(v => svg.push(`<line class="lc-grid" x1="${L}" x2="${W - R + 6}" y1="${Y(v)}" y2="${Y(v)}"/><text class="lc-tk" x="${L - 8}" y="${Y(v) + 4}" text-anchor="end">${esc(yFmt(v))}</text>`));
  [...new Set(xt)].forEach(i => svg.push(`<text class="lc-tk" x="${X(i)}" y="${H - 10}" text-anchor="middle">${esc(String(x[i]))}</text>`));
  series.forEach(s => svg.push(`<path d="${s.values.map((v, i) => `${i ? "L" : "M"}${X(i).toFixed(1)} ${Y(v).toFixed(1)}`).join(" ")}" fill="none" stroke="${s.color}" stroke-width="${s.width || 2}" stroke-linejoin="round" stroke-linecap="round"/>`));
  // Etiquetas al final: si dos chocan, la de menor prioridad se deja a la leyenda y al lector.
  const ends = series.map((s, k) => ({s, k, y: Y(s.values[s.values.length - 1])})).sort((a, b) => a.y - b.y);
  const keep = [];
  for (const e of ends.slice().sort((a, b) => a.k - b.k)) if (keep.every(o => Math.abs(o.y - e.y) >= 14)) keep.push(e);
  series.forEach(s => { const i = s.values.length - 1; svg.push(`<circle cx="${X(i)}" cy="${Y(s.values[i])}" r="4" fill="${s.color}" class="lc-dot"/>`); });
  keep.forEach(({s, y}) => svg.push(`<text class="lc-end" x="${W - R + 10}" y="${y + 4}">${esc(s.name)} · ${esc(yFmt(s.values[s.values.length - 1]))}</text>`));
  svg.push(`<line class="lc-cross" x1="0" x2="0" y1="${T}" y2="${H - B}" visibility="hidden"/>`);
  svg.push(`<rect x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}" fill="transparent" class="lc-hit"/></svg>`);
  const legend = `<div class="lc-leg">${series.map(s => `<span><i style="background:${s.color}"></i>${esc(s.name)}</span>`).join("")}</div>`;
  const table = `<details class="lc-tab"><summary>Ver como tabla</summary><div class="tbl-w"><table class="tbl"><thead><tr><th>${esc(spec.xName || "x")}</th>${series.map(s => `<th>${esc(s.name)}</th>`).join("")}</tr></thead><tbody>${x.map((xv, i) => `<tr><td>${esc(String(xv))}</td>${series.map(s => `<td class="num">${esc(yFmt(s.values[i]))}</td>`).join("")}</tr>`).join("")}</tbody></table></div></details>`;
  el.innerHTML = `${yTitle ? `<div class="lc-yt">${esc(yTitle)}</div>` : ""}${legend}<div class="lc-box">${svg.join("")}<div class="lc-tip" hidden></div></div>${table}`;
  const box = el.querySelector(".lc-box"), sv = box.querySelector("svg"), tip = box.querySelector(".lc-tip"), cross = sv.querySelector(".lc-cross");
  let cur = null;
  function show(i) {
    cur = i;
    cross.setAttribute("x1", X(i)); cross.setAttribute("x2", X(i)); cross.setAttribute("visibility", "visible");
    tip.hidden = false;
    tip.replaceChildren();
    const h = document.createElement("div"); h.className = "lc-tip-h"; h.textContent = `${spec.xName || ""} ${x[i]}`; tip.appendChild(h);
    series.slice().sort((a, b) => b.values[i] - a.values[i]).forEach(s => {
      const r = document.createElement("div"); r.className = "lc-tip-r";
      const k = document.createElement("i"); k.style.background = s.color;
      const v = document.createElement("b"); v.textContent = yFmt(s.values[i]);
      const n = document.createElement("span"); n.textContent = s.name;
      r.append(k, v, n); tip.appendChild(r);
    });
    const left = X(i) + 12 + 170 > W ? X(i) - 182 : X(i) + 12;
    tip.style.left = `${Math.max(4, left)}px`; tip.style.top = `${T}px`;
  }
  function hide() { cross.setAttribute("visibility", "hidden"); tip.hidden = true; cur = null; }
  sv.addEventListener("pointermove", e => {
    const r = sv.getBoundingClientRect(), px = (e.clientX - r.left) * (W / r.width);
    const i = Math.round((px - L) / (W - L - R) * (x.length - 1));
    if (i >= 0 && i < x.length) show(i);
  });
  sv.addEventListener("pointerleave", hide);
  sv.addEventListener("blur", hide);
  sv.addEventListener("keydown", e => {
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") { e.preventDefault(); show(Math.max(0, Math.min(x.length - 1, (cur ?? (e.key === "ArrowRight" ? -1 : x.length)) + (e.key === "ArrowRight" ? 1 : -1)))); }
    if (e.key === "Escape") hide();
  });
}

/* =================== pestaña Aprendizaje =================== */
const COLORS = {motor: "#E8FF00", regla: "#8FB8FF", oraculo: "#C9D0DE", azar: "#6F7B97", motor_sin_explorar: "#FF9BB5"};
const ESC = {"señal": "Con señal", "regla correcta": "Regla correcta", "ruido": "Con ruido", "oportunidad oculta": "Hipótesis equivocada"};
const ESC_D = {
  "señal": "La verdad tiene efectos que la regla no ve: rasgos del cliente, el momento y una señal media más débil de lo que se creía.",
  "regla correcta": "La verdad es exactamente la regla v1.3. Aquí el motor no puede ganar: la prueba es que no empeore.",
  "ruido": "Igual a «con señal» pero con 20 variables de puro ruido. La prueba es que más datos sin señal no confundan al motor.",
  "oportunidad oculta": "La señal media vende tanto como la fuerte, aunque el motor empieza creyendo que vende × 0,6. La prueba es que corrija la hipótesis.",
};
let escSel = "señal";

export function aprendeHTML(M, ev, client, opts = {}) {
  if (!M) return `<span class="empty">Cargando el motor…</span>`;
  const E = M.embudo, Mo = M.momento, Lab = M.laboratorio, R = M.previas;
  const d = ev && ev.decision, me = ev && ev.motor;
  const ses = me && me.sesion;
  const est = (pr) => pr ? `${pc(pr.ic90[0], 0)} a ${pc(pr.ic90[1], 0)}` : "";
  const comps = [
    ["Base", "Campanas_Previas", `Conversión de cada campaña, encogida hacia el promedio de las 5 (Beta-Binomial jerárquico). Hogar no tiene campaña: recibe el promedio con más duda.`],
    ["Señal", "Movimientos + Cajitas", `Las reglas aprobadas detectan la señal (fuerte o media). Media vale × 0,6 de fuerte: hipótesis con su duda, que las respuestas corrigen.`],
    ["Momento", "Pagos_Seguros + Movimientos", `Las compras externas caen ${dec(Mo.promedio.rr)} veces más en los ${Mo.ventana_dias} días después del evento (${Mo.total.en_ventana} frente a ${dec(Mo.total.esperados, 1)} esperadas; 90 %: ${dec(Mo.promedio.ic90[0])} a ${dec(Mo.promedio.ic90[1])}).`],
    ["Afinidad", "Clientes + Movimientos (M1)", `Pesa 0: M1 no le gana al azar con esta base. Si con datos reales le gana, entra sola.`],
    ["Rasgos", "las 5 tablas de clientes", `${M.rasgos.n} variables descubiertas de los datos. Empiezan en «no sé» y no mueven nada hasta que haya respuestas.`],
    ["Cliente", "respuestas de la sesión", `El apetito de cada cliente por seguros: empieza en 0 y aprende con lo que acepta o rechaza.`],
  ];
  const ramos = Object.keys(E.por_ramo);
  const lab = Lab ? Lab.escenarios[escSel] : null;
  return `
    <div><h3>Cómo decide y aprende el motor</h3><p class="lead">Para cada seguro permitido calcula la probabilidad de que el cliente acepte si ve la oferta y ofrece el de mayor valor esperado. La probabilidad sale de los datos y se actualiza con cada respuesta: con más datos y más tipos de datos, decide igual o mejor.</p></div>
    <div class="formula">Valor esperado = <b>P(acepta | la ve)</b> × comisión a 12 meses<small>P = Φ(base + señal + momento + afinidad + rasgos + cliente): regresión probit bayesiana que aprende en línea</small></div>
    <div class="comps">${comps.map(([n, src, t]) => `<div class="comp"><b>${n}</b><span class="src">${esc(src)}</span><p>${t}</p></div>`).join("")}</div>
    <div><h4>Este cliente, ahora · ${esc(client || "")}</h4>
      ${d && d.prob ? `<div class="box">${probSteps(d.prob)}<p style="margin:8px 0 0">${esc(d.title)}: ${pc(d.prob.p)} × ${money(d.valor)} = <b>${money(d.ev)}</b> de valor esperado. Regla v1.3: ${money(d.ev_regla)}.</p></div>`
        : `<div class="box">${ev && ev.outcome === "noconsent" ? "Sin autorización de datos: el motor no calcula nada sobre este cliente (Ley 1581)." : "Hoy no hay una oferta con probabilidad para este cliente."}</div>`}
      ${ses ? `<div class="box" style="margin-top:8px"><b>Aprendizaje de esta sesión:</b> ${ses.respuestas ? `${ses.respuestas} ${ses.respuestas === 1 ? "respuesta" : "respuestas"} (${ses.aceptadas} ${ses.aceptadas === 1 ? "aceptada" : "aceptadas"}). Apetito por seguros: de ${dec(ses.previa[0])} a <b>${ses.posterior[0] >= 0 ? "+" : ""}${dec(ses.posterior[0])}</b> (duda ${dec(ses.previa[1])} → ${dec(ses.posterior[1])}). Un rechazo enseña poco cuando casi todos rechazan; una aceptación enseña más.` : "todavía no hay respuestas. Acepta o rechaza una oferta en el teléfono y mira cómo cambia el apetito del cliente y sus probabilidades."}${me.politica === "explorar" ? " Este cliente está en el 10 % que explora." : ""}</div>` : ""}</div>
    <div><h4>Lo que sabe hoy, con la base del reto</h4>
      <div class="tbl-w"><table class="tbl"><thead><tr><th>Ramo</th><th>Campaña</th><th>Creencia (90 %)</th><th>Momento</th><th>En el momento</th></tr></thead><tbody>${ramos.map(k => { const e = E.por_ramo[k], m = Mo.por_ramo[k]; return `<tr><td><b>${esc(k)}</b></td><td class="num">${e.cruda != null ? pc(e.cruda) : "sin campaña"}</td><td class="num">${pc(e.posterior.media)} <small>(${pc(e.posterior.ic90[0])} a ${pc(e.posterior.ic90[1])})</small></td><td class="num">× ${dec(m.rr.media)} <small>(${dec(m.rr.ic90[0])} a ${dec(m.rr.ic90[1])})</small>${m.con_datos ? "" : " <small>sin compras: promedio</small>"}</td><td class="num">${pc(Mo.exposicion[k].fraccion, 0)}</td></tr>`; }).join("")}</tbody></table></div>
      <p class="lead" style="margin:0">${esc(E.lectura)} Sin respuestas a ofertas en la base, ${M.rasgos.n} rasgos esperan datos para pesar; la duda total que pueden aportar está fija (${dec(R.chequeo.p_sorteada.p05 * 100, 1)} % a ${dec(R.chequeo.p_sorteada.p95 * 100, 1)} % de probabilidad antes de ver datos), así que sumar variables no agrega ruido.</p></div>
    ${Lab ? `<div><div class="row-h"><h4>Laboratorio: ¿mejora con más datos?</h4></div>
      <p class="lead" style="margin:-4px 0 8px">${esc(Lab.aviso)} ${Lab.config.clientes} clientes reales de la base, ${Lab.config.rondas} rondas de ofertas: después de cada ronda el motor aprende de las respuestas; la regla no.</p>
      <div class="seg-p" role="group" aria-label="Escenario">${Object.keys(Lab.escenarios).map(k => `<button data-esc="${esc(k)}" aria-pressed="${k === escSel}">${esc(ESC[k] || k)}</button>`).join("")}</div>
      <p class="lead" style="margin:8px 0">${esc(ESC_D[escSel] || "")}</p>
      <div class="kpis"><div class="metric lime"><div class="v">${sgn(lab.frente_a_regla_final, 1)}</div><div class="l">comisión por oferta frente a la regla (últimas 10 rondas)</div></div>
        <div class="metric"><div class="v">${pc(lab.del_techo_final, 0)}</div><div class="l">del camino entre el azar y el oráculo (regla: ${pc(lab.regla_del_techo, 0)})</div></div>
        <div class="metric"><div class="v">${dec(lab.calibracion.motor[0] * 100, 1)} → ${dec(lab.calibracion.motor.at(-1) * 100, 1)}</div><div class="l">error medio de la probabilidad, en puntos (regla: ${dec(lab.calibracion.regla.at(-1) * 100, 1)})</div></div></div>
      <div class="chart" id="labChart"></div>
      <div class="chart" id="labCalib"></div>
      <details class="lc-tab"><summary>Pesos que el motor descubrió (escenario «${esc(ESC[escSel] || escSel)}»)</summary><div class="tbl-w"><table class="tbl"><thead><tr><th>Peso</th><th>Verdad</th><th>Ronda 1</th><th>Ronda 10</th><th>Ronda ${Lab.config.rondas}</th></tr></thead><tbody>${Object.values(lab.pesos).map(w => `<tr><td>${esc(w.label)}</td><td class="num">${dec(w.verdad)}</td><td class="num">${dec(w.estimado[0])}</td><td class="num">${dec(w.estimado[9])}</td><td class="num">${dec(w.estimado.at(-1))}</td></tr>`).join("")}</tbody></table></div><p class="lead">Escala probit. El motor arranca en 0 en lo que no sabe y se acerca a la verdad con las respuestas, despacio a propósito: no persigue ruido.</p></details>
      <div class="box">${esc(Lab.resumen)}</div></div>` : ""}
    <div><h4>Con los datos reales de Lulo</h4>
      <ol class="steps"><li><b>Exportar</b> las tablas con el mismo esquema de la base (sin nombres: solo fecha, monto, canal, categoría y MCC) y, si existen, las respuestas a ofertas.</li>
      <li><b>Entrenar en su propio equipo</b>, sin subir datos a ningún lado: <code>python scripts/train_motor.py --datos CARPETA --respuestas respuestas.csv --salida motor.json --reporte reporte.md</code>.</li>
      <li><b>Solo cambia lo que mejora:</b> lo aprendido se usa si baja la log-pérdida en el 20 % más reciente de las respuestas (campeón contra retador); si no, se quedan las creencias previas.</li></ol>
      <p class="lead" style="margin:0">Método completo y preguntas difíciles: <a href="https://github.com/soka-js/Prototipo-IIND/blob/main/docs/MOTOR.md" target="_blank" rel="noopener">docs/MOTOR.md</a> · Guía para datos reales: <a href="https://github.com/soka-js/Prototipo-IIND/blob/main/docs/DATOS_REALES.md" target="_blank" rel="noopener">docs/DATOS_REALES.md</a></p></div>`;
}

export function mountAprende(root, M, rerender) {
  root.querySelectorAll("[data-esc]").forEach(b => b.addEventListener("click", () => { escSel = b.dataset.esc; rerender(); }));
  const Lab = M && M.laboratorio;
  if (!Lab) return;
  const e = Lab.escenarios[escSel], rondas = e.respuestas_acumuladas.map((_, i) => i + 1);
  const P = e.politicas;
  const ch = root.querySelector("#labChart"), cc = root.querySelector("#labCalib");
  if (ch) lineChart(ch, {label: "Comisión esperada por oferta en cada ronda", yTitle: "Comisión esperada por oferta ($), ronda a ronda", xName: "Ronda",
    x: rondas, yFmt: v => money(v), series: [
      {name: "Motor", color: COLORS.motor, values: P.motor.comision, width: 2.5},
      {name: "Regla v1.3", color: COLORS.regla, values: P.regla.comision},
      {name: "Oráculo", color: COLORS.oraculo, values: P.oraculo.comision, width: 1.5},
      {name: "Azar", color: COLORS.azar, values: P.azar.comision, width: 1.5}]});
  if (cc) lineChart(cc, {label: "Error de la probabilidad frente a la verdad", yTitle: "Error medio de la probabilidad frente a la verdad (puntos porcentuales)", xName: "Ronda", height: 170,
    x: rondas, yFmt: v => `${dec(v * 100, 1)}`, series: [
      {name: "Motor", color: COLORS.motor, values: e.calibracion.motor, width: 2.5},
      {name: "Regla v1.3", color: COLORS.regla, values: e.calibracion.regla}]});
}
