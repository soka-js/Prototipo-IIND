// Motor bayesiano en lenguaje claro: la probabilidad de cada decisión explicada por pasos (recorrido guiado) y
// la tarjeta de lo que acaba de decidir el motor (escenarios rápidos).
import { esc, money } from "./util.js";

export const pc = (x, d = 1) => x == null ? "—" : `${(x * 100).toFixed(d).replace(".", ",")} %`;
const dec = (x, d = 2) => x == null ? "—" : Number(x).toFixed(d).replace(".", ",");

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

const OUT_RT = {shown: "se mostró por push", banner: "va como banner pasivo (no cuenta como contacto)", queued: "espera en cola: la ventana está ocupada",
  control: "grupo de control: el motor decide pero no se muestra", optout: "el cliente apagó las sugerencias", noconsent: "sin autorización de datos: el motor no lee nada",
  weak: "señal débil: no se ofrece", ineligible: "no es elegible", has: "ya lo tiene", cooldown: "en espera: se le ofreció hace poco",
  external: "lo tiene con otra aseguradora", none: "no alimenta ningún seguro"};
const DATA_OF = {base: "Campanas_Previas", momento: "Pagos_Seguros", senal_media: "Movimientos", afinidad: "Clientes", rasgos: "Movimientos", cliente: "respuestas de la sesión"};

/** Tarjeta «Lo que acaba de decidir el motor», en lenguaje claro. */
export function decisionHTML(ev, src, title = (n) => n) {
  if (!ev) return "";
  const d = ev.decision, o = ev.outcome;
  // En lote (la evaluación del día) nada se mostró todavía: se dice lo que haría el motor.
  const OUT = ev.mode === "lote" ? {...OUT_RT, shown: "hoy iría por push", banner: "hoy iría como banner pasivo (no cuenta como contacto)"} : OUT_RT;
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
