// Utilidades sin dependencias: formato, fechas, DOM y tiempos.
export const $ = s => document.querySelector(s);
export const $$ = s => [...document.querySelectorAll(s)];
export const wait = ms => new Promise(r => setTimeout(r, ms));
export const clone = o => JSON.parse(JSON.stringify(o));
export const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

export const num = n => Math.round(n).toLocaleString("es-CO");
export const money = n => (n < 0 ? "−" : "") + "$" + Math.abs(Math.round(n)).toLocaleString("es-CO");
export const signed = n => (n > 0 ? "+" : "") + money(n);
export const millions = n => "$" + (Math.abs(n) / 1e6).toFixed(1).replace(/\.0$/, "").replace(".", ",") + " M";
export const nowTime = () => new Date().toLocaleTimeString("es-CO", {hour:"2-digit", minute:"2-digit", second:"2-digit", hour12:false});

const M = ["ene","feb","mar","abr","may","jun","jul","ago","sep","oct","nov","dic"];
const ML = ["enero","febrero","marzo","abril","mayo","junio","julio","agosto","septiembre","octubre","noviembre","diciembre"];
const WD = ["domingo","lunes","martes","miércoles","jueves","viernes","sábado"];
const parse = iso => { const [y, m, d] = iso.split("-").map(Number); return new Date(y, m - 1, d); };

export function dayLabel(iso, today) {
  if (iso === today) return "Hoy";
  const diff = Math.round((parse(today) - parse(iso)) / 864e5);
  if (diff === 1) return "Ayer";
  const d = parse(iso);
  const t = parse(today);
  return `${d.getDate()} ${M[d.getMonth()]}` + (d.getFullYear() !== t.getFullYear() ? ` ${d.getFullYear()}` : "");
}
export const dateShort = iso => { const d = parse(iso); return `${d.getDate()} ${M[d.getMonth()]}`; };
export const dateLong = (iso, year = true) => { const d = parse(iso); return `${WD[d.getDay()]} ${d.getDate()} de ${ML[d.getMonth()]}` + (year ? ` de ${d.getFullYear()}` : ""); };
export const addDays = (iso, n) => { const d = parse(iso); d.setDate(d.getDate() + n); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}-${String(d.getDate()).padStart(2,"0")}`; };

export const initials = name => name.replace(/\(.*?\)/g, "").split(/[\s·.]+/).filter(Boolean).slice(0, 2).map(w => w[0]).join("").toUpperCase();

export function debounce(fn, ms) { let h; return (...a) => { clearTimeout(h); h = setTimeout(() => fn(...a), ms); }; }

export const store = {
  get(k) { try { const v = sessionStorage.getItem(k); return v ? JSON.parse(v) : null; } catch { return null; } },
  set(k, v) { try { sessionStorage.setItem(k, JSON.stringify(v)); } catch { /* sin almacenamiento */ } },
  del(k) { try { sessionStorage.removeItem(k); } catch { /* sin almacenamiento */ } },
};

// Encabezado de fecha como en Alertas de la app real: «2 de septiembre 2026».
export const dateHeader = iso => { const d = parse(iso); return `${d.getDate()} de ${ML[d.getMonth()]} ${d.getFullYear()}`; };
export const monthShortUpper = iso => M[parse(iso).getMonth()].toUpperCase();
export const dayOf = iso => parse(iso).getDate();
export const daysBetween = (a, b) => Math.round((parse(b) - parse(a)) / 864e5);
export const pct = (x, d = 1) => (x * 100).toFixed(d).replace(".", ",") + " %";
export const strip = h => String(h || "").replace(/<[^>]+>/g, "");
