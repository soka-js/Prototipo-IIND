"""Vista previa web del dashboard: las mismas páginas del proyecto de Power BI en un HTML que se abre sin nada más.

La genera scripts/exportar_powerbi.py con los mismos CSV. Cada cifra se calcula aquí con la misma definición que
la medida DAX del mismo nombre (scripts/powerbi_modelo.py): sirve para ver el dashboard sin Power BI y para
comprobar las medidas (tests/test_powerbi.py compara esta cuenta con la del exportador).
"""

from __future__ import annotations

import csv
import io
import json
import math
from collections import defaultdict
from datetime import date, timedelta

import powerbi_modelo as pm


def leer(texto: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(texto)))


def _f(v: str) -> float | None:
    return float(v) if v not in ("", None) else None


def lectura_itt(clientes: list[dict]) -> dict:
    """Las medidas de «1 · Resultado del piloto» (intención de tratar, un cliente por fila)."""
    g = {k: [c for c in clientes if c["grupo"] == k] for k in ("tratamiento", "control")}
    n = {k: len(v) for k, v in g.items()}
    x = {k: sum(int(c["compro"]) for c in v) for k, v in g.items()}
    com = {k: sum(int(c["comision_12m_cop"]) for c in v) for k, v in g.items()}
    if not n["tratamiento"] or not n["control"]:
        return {"n": n, "x": x, "veredicto": "Sin grupo de control no se puede saber si las ofertas venden"}
    pt, pc = x["tratamiento"] / n["tratamiento"], x["control"] / n["control"]
    d = pt - pc
    se = math.sqrt(pt * (1 - pt) / n["tratamiento"] + pc * (1 - pc) / n["control"])
    p0 = (x["tratamiento"] + x["control"]) / (n["tratamiento"] + n["control"])
    se0 = math.sqrt(p0 * (1 - p0) * (1 / n["tratamiento"] + 1 / n["control"]))
    z = d / se0 if se0 else 0.0
    lo, hi = (d - 1.96 * se) * 100, (d + 1.96 * se) * 100
    m = min(x["tratamiento"], n["tratamiento"] - x["tratamiento"], x["control"], n["control"] - x["control"])
    return {
        "n": n, "x": x, "conv": {"tratamiento": pt, "control": pc}, "dif_pp": d * 100, "ic": [lo, hi],
        "p": math.erfc(abs(z) / math.sqrt(2)), "ventas_incrementales": d * n["tratamiento"],
        "comision_incremental": (com["tratamiento"] / n["tratamiento"] - com["control"] / n["control"]) * n["tratamiento"],
        "mde_pp": (1.96 + 0.8416) * se0 * 100,
        "veredicto": ("Sí: con las ofertas compran más clientes que sin ellas" if lo > 0 else
                      "No: con las ofertas compran menos clientes que sin ellas" if hi < 0 else
                      "Todavía no se sabe: la diferencia cabe en el azar"),
        "muestra": ("Muestra chica: con menos de 5 casos en un grupo la lectura es frágil. El piloto real necesita la "
                    "base completa de Lulo (M6)." if m < 5 else "Muestra suficiente para la prueba de dos proporciones."),
    }


def _ofertas(dec: list[dict], previa: dict[str, float]) -> dict:
    vistas = [r for r in dec if r["resultado"] in ("aceptada", "rechazada")]
    acep = sum(r["resultado"] == "aceptada" for r in vistas)
    mostradas = sum(r["canal"] != "ninguno" for r in dec)
    pm_ = sum(float(r["p_motor"]) for r in vistas) / len(vistas) if vistas else None
    conv = acep / len(vistas) if vistas else None
    prev = sum(previa[r["ramo"]] for r in vistas) / len(vistas) if vistas else None
    return {"decisiones": len(dec), "mostradas": mostradas, "vistas": len(vistas), "aceptadas": acep,
            "ignoradas": sum(r["resultado"] == "ignorada" for r in dec),
            "control": sum(r["resultado"] == "control" for r in dec), "conv": conv, "p_motor": pm_,
            "observado_motor": conv / pm_ if conv is not None and pm_ else None, "previa": prev,
            "frente_previa": conv / prev - 1 if conv is not None and prev else None,
            "alcance": len(vistas) / mostradas if mostradas else None}


def datos(csvs: dict[str, str]) -> dict:
    T = {k[:-4]: leer(v) for k, v in csvs.items()}
    meta = {r["clave"]: r["valor"] for r in T["meta"]}
    ramos = [r["ramo"] for r in sorted(T["dim_ramo"], key=lambda r: int(r["orden"]))]
    previa = {r["ramo"]: float(r["conversion_previa"]) for r in T["dim_ramo"]}
    corte = date.fromisoformat(meta["base_corte"])
    out = {"meta": meta, "ramos": ramos, "colores": {"series": pm.SERIES, **pm.COLOR},
           "escenarios": [{"id": r["escenario"], "nombre": r["nombre"], "descripcion": r["descripcion"]}
                          for r in sorted(T["dim_escenario"], key=lambda r: int(r["orden"]))],
           "piloto": {}}
    for e in out["escenarios"]:
        k = e["id"]
        cli = [r for r in T["piloto_clientes"] if r["escenario"] == k]
        dec = [r for r in T["piloto_decisiones"] if r["escenario"] == k]
        ven = [r for r in T["piloto_ventas"] if r["escenario"] == k]
        grupo = {r["cliente_id"]: r["grupo"] for r in cli}
        inicio = min(date.fromisoformat(r["primera_decision"]) for r in cli)
        # Conversión acumulada por semana (lunes a domingo, la última hasta el corte), como la medida DAX.
        semanas, d = [], inicio - timedelta(days=inicio.weekday())
        while d <= corte:
            fin = min(d + timedelta(days=6), corte)
            fila = {"semana": d.isoformat()}
            for g in ("tratamiento", "control"):
                n = sum(1 for c in cli if c["grupo"] == g)
                compr = {v["cliente_id"] for v in ven if grupo.get(v["cliente_id"]) == g and date.fromisoformat(v["fecha"]) <= fin}
                fila[g] = len(compr) / n if n and fin >= inicio else None
            semanas.append(fila)
            d += timedelta(days=7)
        por_ramo = []
        for ramo in ramos:
            o = _ofertas([r for r in dec if r["ramo"] == ramo], previa)
            por_ramo.append({"ramo": ramo, "vistas": o["vistas"], "conv": o["conv"], "previa": previa[ramo]})
        tramos = []
        for i, (_, nombre) in enumerate(pm.TRAMOS_P):
            o = _ofertas([r for r in dec if r["tramo_orden"] == str(i + 1)], previa)
            tramos.append({"tramo": nombre, "vistas": o["vistas"], "p_motor": o["p_motor"], "conv": o["conv"]})
        momento = []
        for t in ("con evento reciente", "sin evento reciente"):
            o = _ofertas([r for r in dec if r["momento_texto"] == t], previa)
            momento.append({"momento": t, "vistas": o["vistas"], "p_motor": o["p_motor"], "conv": o["conv"]})
        sim_m = sum(float(r["p_verdad"]) * int(r["comision_12m_cop"]) for r in dec)
        sim_r = sum(float(r["p_verdad_regla"]) * int(r["comision_12m_regla_cop"]) for r in dec)
        res = defaultdict(int)
        for r in dec:
            res[r["resultado"]] += 1
        out["piloto"][k] = {
            "itt": lectura_itt(cli), "ofertas": _ofertas(dec, previa), "semanas": semanas,
            "por_ramo": por_ramo, "tramos": tramos, "momento": momento,
            "resultados": [{"resultado": r, "n": res[r]} for r in ("aceptada", "rechazada", "ignorada", "control")],
            "coinciden_regla": sum(r["coincide_regla"] == "1" for r in dec) / len(dec),
            "motor_frente_regla": sim_m / sim_r - 1 if sim_r else None,
            "ventas": {o: sum(v["origen"] == o for v in ven) for o in ("oferta", "por su cuenta")},
            "inicio": inicio.isoformat()}
    plan = T["motor_plan"]
    cuenta = defaultdict(int)
    for r in plan:
        cuenta[r["resultado_texto"]] += 1
    motivos = defaultdict(int)
    for r in plan:
        if r["resultado"] in ("shown", "banner"):
            motivos[r["motivo_canal"] or "(sin motivo)"] += 1
    bt = {r["metrica"]: r["valor"] for r in T["motor_backtest"]}
    oferta_plan = [r for r in plan if r["resultado"] in ("shown", "banner")]
    out["plan"] = {
        "clientes": len(T["dim_cliente"]), "autorizan": sum(r["autoriza_ofertas"] == "Sí" for r in T["dim_cliente"]),
        "ofertas": len(oferta_plan), "control": sum(r["resultado"] == "control" for r in plan),
        "ventas_esperadas": sum(_f(r["ventas_esperadas"]) or 0 for r in plan),
        "comision_esperada": sum(_f(r["comision_esperada_cop"]) or 0 for r in plan),
        "p_media": sum(float(r["p_motor"]) for r in oferta_plan) / len(oferta_plan) if oferta_plan else None,
        "resultados": sorted(({"resultado": k, "n": v} for k, v in cuenta.items()), key=lambda x: -x["n"]),
        "motivos": sorted(({"motivo": k, "n": v} for k, v in motivos.items()), key=lambda x: -x["n"]),
        "backtest": bt, "invariantes": T["motor_invariantes"],
        "violaciones": sum(int(r["violaciones"]) for r in T["motor_invariantes"])}
    out["m6"] = [{"ramo": r["ramo"], "base": float(r["conversion_previa"]), "n20": int(r["piloto_n_20"]),
                  "n50": int(r["piloto_n_50"]), "n100": int(r["piloto_n_100"])}
                 for r in sorted(T["dim_ramo"], key=lambda r: int(r["orden"]))]
    lab = {}
    for e in sorted(T["dim_lab_escenario"], key=lambda r: int(r["orden"])):
        k = e["escenario"]
        series = defaultdict(list)
        for r in T["lab_series"]:
            if r["escenario"] == k:
                series[(int(r["politica_orden"]), r["politica_nombre"])].append(float(r["comision_por_oferta"]))
        cal = defaultdict(list)
        for r in T["lab_calibracion"]:
            if r["escenario"] == k:
                cal[r["modelo"]].append(float(r["error_medio"]))
        ronda_final = max(int(r["ronda"]) for r in T["lab_pesos"])
        pesos = [{"efecto": r["etiqueta"], "aprendido": float(r["estimado"]), "verdad": float(r["verdad"])}
                 for r in T["lab_pesos"] if r["escenario"] == k and int(r["ronda"]) == ronda_final]
        tau = [{"ronda": int(r["ronda"]), "tau": float(r["tau"]), "lo": float(r["ic95_bajo"]), "hi": float(r["ic95_alto"]),
                "verdad": float(r["verdad"])} for r in T["lab_apetito"] if r["escenario"] == k and r["politica"] == "motor"]
        res = next(r for r in T["lab_resumen"] if r["escenario"] == k)
        lab[k] = {"descripcion": e["descripcion"],
                  "series": [{"nombre": n, "valores": v} for (_, n), v in sorted(series.items())],
                  "calibracion": [{"nombre": m, "valores": v} for m, v in sorted(cal.items())],
                  "pesos": pesos, "tau": tau,
                  "resumen": {c: _f(res[c]) for c in ("motor_frente_a_regla", "motor_del_techo", "regla_del_techo")}}
    out["lab"] = lab
    out["casos"] = T["casos"]
    mens = defaultdict(lambda: defaultdict(int))
    for r in T["base_seguros_mensual"]:
        mens[r["mes"][:7]][r["ramo"]] += int(r["polizas_emitidas"])
    out["base"] = {
        "meses": sorted(mens), "polizas": {ramo: [mens[m][ramo] for m in sorted(mens)] for ramo in ramos},
        "polizas_total": sum(int(r["polizas_emitidas"]) for r in T["base_seguros_mensual"]),
        "comision_primas": sum(int(r["polizas_emitidas"]) * int(r["prima_promedio_cop"]) * float(r["comision_pct"])
                               for r in T["base_seguros_mensual"]),
        "pagado_externo": sum(int(r["monto_cop"]) for r in T["base_pagos_externos"]),
        "campanas": T["base_campanas"],
        "conv_campanas": sum(int(r["ventas"]) for r in T["base_campanas"]) / sum(int(r["impactados"]) for r in T["base_campanas"]),
        "catalogo": [{k: r[k] for k in ("ramo", "prima_cop", "comision_pct", "persistencia_12m", "cancelacion_pct",
                                        "comision_12m_cop", "compras_por_su_cuenta")}
                     for r in sorted(T["dim_ramo"], key=lambda r: int(r["orden"]))]}
    return out


def html(csvs: dict[str, str]) -> str:
    d = json.dumps(datos(csvs), ensure_ascii=False, separators=(",", ":"))
    return PLANTILLA.replace("__DATOS__", d.replace("</", "<\\/"))


PLANTILLA = r"""<!doctype html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<title>Resultados del motor · Lulo</title>
<style>
:root{--pagina:#0B1430;--tarjeta:#131E3D;--linea:#1E2B50;--texto:#FFFFFF;--texto-2:#AFB8CC;--texto-3:#92A0BD;
--lima:#E8FF00;--bien:#62E3A0;--alerta:#FFB547;--mal:#EA6E66;--s1:#8A9E00;--s2:#3987e5;--s3:#d95926;--s4:#9085e9;--s5:#199e70;--s6:#c98500;
color-scheme:dark;font-family:'Segoe UI',system-ui,-apple-system,sans-serif}
*{box-sizing:border-box}body{margin:0;background:var(--pagina);color:var(--texto);font-size:14px;line-height:1.4}
header{display:flex;flex-wrap:wrap;gap:12px 24px;align-items:center;justify-content:space-between;padding:16px 24px 8px}
header h1{font-size:20px;margin:0;font-weight:600}header h1 b{color:var(--lima);font-weight:600}
.tag{border:1px solid var(--lima);color:var(--lima);border-radius:999px;padding:3px 12px;font-size:12px;white-space:nowrap}
nav{display:flex;gap:4px;overflow-x:auto;padding:0 24px;border-bottom:1px solid var(--linea)}
nav button{background:none;border:0;border-bottom:2px solid transparent;color:var(--texto-2);padding:10px 12px;font:inherit;cursor:pointer;white-space:nowrap}
nav button[aria-selected=true]{color:var(--texto);border-bottom-color:var(--lima)}
nav button:focus-visible,.seg button:focus-visible{outline:2px solid var(--lima);outline-offset:2px}
main{padding:16px 24px 32px;max-width:1320px;margin:0 auto}
.page{display:none}.page.on{display:block}
.sub{color:var(--texto-2);margin:0 0 14px;font-size:15px}
.fila{display:grid;gap:12px;margin-bottom:12px}
.c4{grid-template-columns:repeat(4,minmax(0,1fr))}.c2{grid-template-columns:repeat(2,minmax(0,1fr))}.c3{grid-template-columns:repeat(3,minmax(0,1fr))}
@media (max-width:900px){.c4,.c3{grid-template-columns:repeat(2,minmax(0,1fr))}.c2{grid-template-columns:1fr}}
@media (max-width:520px){.c4,.c3{grid-template-columns:1fr}main,header,nav{padding-left:16px;padding-right:16px}}
.card{background:var(--tarjeta);border-radius:12px;padding:14px 16px;min-width:0}
.card h3{margin:0 0 6px;font-size:13px;font-weight:600;color:var(--texto-2)}
.kpi .v{font-size:30px;font-weight:600;letter-spacing:-.5px}.kpi .n{color:var(--texto-3);font-size:12px;margin-top:2px}
.veredicto{display:flex;gap:12px;align-items:center;font-size:17px;font-weight:600}
.veredicto .ico{width:28px;height:28px;border-radius:50%;display:grid;place-items:center;flex:none;color:var(--pagina);font-weight:700}
.aviso{color:var(--texto-3);font-size:12.5px}
.seg{display:inline-flex;background:var(--tarjeta);border-radius:999px;padding:3px;gap:2px;flex-wrap:wrap}
.seg button{background:none;border:0;color:var(--texto-2);border-radius:999px;padding:6px 14px;font:inherit;font-size:13px;cursor:pointer}
.seg button[aria-pressed=true]{background:var(--linea);color:var(--texto)}
.ctrl{display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;margin-bottom:12px}
.ctrl .desc{color:var(--texto-3);font-size:12.5px;flex:1;min-width:240px}
svg{display:block;width:100%;height:auto;overflow:visible}
svg text{fill:var(--texto-2);font-size:11px;font-family:inherit}
.leyenda{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:12px;color:var(--texto-2);margin:2px 0 6px}
.leyenda i{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px;vertical-align:-1px}
.tip{position:fixed;pointer-events:none;background:#0B1430;border:1px solid var(--linea);border-radius:8px;padding:8px 10px;font-size:12px;
color:var(--texto);box-shadow:0 6px 18px rgba(0,0,0,.4);z-index:10;display:none;max-width:280px}
.tip b{display:block;margin-bottom:2px}.tip span{color:var(--texto-2)}
table{width:100%;border-collapse:collapse;font-size:13px}
th{text-align:left;color:var(--texto-2);font-weight:600;border-bottom:1px solid var(--linea);padding:6px 8px;white-space:nowrap}
td{border-bottom:1px solid var(--linea);padding:7px 8px;vertical-align:top}
td.num,th.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.tabla{overflow-x:auto}
.pill{display:inline-block;border-radius:999px;padding:1px 8px;font-size:11.5px;border:1px solid currentColor;white-space:nowrap}
.ok{color:var(--bien)}.warn{color:var(--alerta)}.bad{color:var(--mal)}.mut{color:var(--texto-3)}
a{color:#7FB2FF}
footer{color:var(--texto-3);font-size:12px;padding:0 24px 24px;max-width:1320px;margin:0 auto}
</style>
</head>
<body>
<header><h1>Lulo · <b>¿El motor convierte ofertas en ventas?</b></h1><span class="tag">Prototipo académico · datos simulados</span></header>
<nav role="tablist" id="tabs"></nav>
<main id="main"></main>
<footer id="pie"></footer>
<div class="tip" id="tip" role="status"></div>
<script>
const D = __DATOS__;
const C = D.colores, S = C.series;
const nf = (d=0) => new Intl.NumberFormat('es-CO',{minimumFractionDigits:d,maximumFractionDigits:d});
const n0 = v => v==null?'—':nf(0).format(v);
const pct = (v,d=1) => v==null?'—':nf(d).format(v*100)+' %';
const pp = (v,d=1) => v==null?'—':(v>=0?'+':'−')+nf(d).format(Math.abs(v))+' pp';
const cop = v => v==null?'—':'$'+nf(0).format(v);
const esc = s => String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const tip = document.getElementById('tip');
function showTip(e, html){tip.innerHTML=html;tip.style.display='block';const r=tip.getBoundingClientRect();
  let x=e.clientX+14,y=e.clientY+14;if(x+r.width>innerWidth-8)x=e.clientX-r.width-14;if(y+r.height>innerHeight-8)y=e.clientY-r.height-14;
  tip.style.left=x+'px';tip.style.top=y+'px'}
function hideTip(){tip.style.display='none'}
const st = {pagina:0, esc:D.escenarios[0].id, lab:'señal'};
try{const h=new URLSearchParams(location.hash.slice(1));if(h.get('p'))st.pagina=+h.get('p')||0}catch(e){}

// ---------- gráficos (SVG): líneas finas, barras con punta redondeada, rejilla tenue, tooltip
function ticks(max, n=4){if(!(max>0))return [0];const raw=max/n,p=Math.pow(10,Math.floor(Math.log10(raw)));
  const step=[1,2,2.5,5,10].map(m=>m*p).find(s=>s>=raw);const t=[];for(let v=0;v<=max+1e-9;v+=step)t.push(v);if(t[t.length-1]<max)t.push(t[t.length-1]+step);return t}
function leyenda(items){return '<div class="leyenda">'+items.map(i=>`<span><i style="background:${i.color}"></i>${esc(i.nombre)}</span>`).join('')+'</div>'}
const ancho=el=>Math.max(300,Math.round(el.clientWidth||640));
function marcas(n,maxN){const paso=Math.max(1,Math.ceil(n/maxN)),out=[];for(let i=0;i<n;i+=paso)out.push(i);
  if(out[out.length-1]!==n-1){if(n-1-out[out.length-1]<paso*0.6)out.pop();out.push(n-1)}return out}
function lineas(el, {x, series, fy, fx=(v=>v), alto=240, min0=true, etiquetas=true}){
  const W=ancho(el),H=alto,m={l:52,r:etiquetas?(W<480?84:140):16,t:10,b:26};const iw=W-m.l-m.r,ih=H-m.t-m.b;
  const vals=series.flatMap(s=>s.valores.filter(v=>v!=null));let lo=min0?0:Math.min(...vals),hi=Math.max(...vals);
  const t0=ticks(hi-lo),paso=t0[1]||1;lo=min0?0:Math.floor(lo/paso)*paso;const tk=[];for(let v=lo;v<hi+paso*.999;v+=paso)tk.push(v);if(tk.length<2)tk.push(lo+paso);const top=tk[tk.length-1];
  const X=i=>m.l+(x.length<2?iw/2:i*iw/(x.length-1)),Y=v=>m.t+ih-(v-lo)/(top-lo||1)*ih;
  let g='';tk.forEach(v=>{const y=Y(v);g+=`<line x1="${m.l}" x2="${m.l+iw}" y1="${y}" y2="${y}" stroke="${C.linea}" stroke-width="1"/><text x="${m.l-8}" y="${y+4}" text-anchor="end">${fy(v)}</text>`});
  marcas(x.length,Math.max(3,Math.floor(iw/110))).forEach(i=>{g+=`<text x="${X(i)}" y="${H-6}" text-anchor="middle">${esc(fx(x[i]))}</text>`});
  const fin=[];
  series.forEach(s=>{let dd='',on=false;s.valores.forEach((v,i)=>{if(v==null){on=false;return}dd+=(on?'L':'M')+X(i).toFixed(1)+' '+Y(v).toFixed(1);on=true});
    g+=`<path d="${dd}" fill="none" stroke="${s.color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>`;
    if(etiquetas){const k=s.valores.map((v,i)=>v==null?-1:i).filter(i=>i>=0).pop();if(k!=null){g+=`<circle cx="${X(k)}" cy="${Y(s.valores[k])}" r="4" fill="${s.color}" stroke="${C.tarjeta}" stroke-width="2"/>`;
      fin.push({x:X(k)+8,y:Y(s.valores[k])+4,t:`${s.corto||s.nombre} ${fy(s.valores[k])}`})}}});
  fin.sort((a,b)=>a.y-b.y);for(let i=1;i<fin.length;i++)if(fin[i].y-fin[i-1].y<13)fin[i].y=fin[i-1].y+13;
  fin.forEach(f=>{g+=`<text x="${f.x}" y="${f.y}" style="fill:${C.texto}">${esc(f.t)}</text>`});
  g+=`<line class="cruz" x1="0" x2="0" y1="${m.t}" y2="${m.t+ih}" stroke="${C.texto_3}" stroke-width="1" visibility="hidden"/><rect x="${m.l}" y="${m.t}" width="${iw}" height="${ih}" fill="transparent"/>`;
  el.innerHTML=(series.length>1?leyenda(series):'')+`<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(series.map(s=>s.nombre).join(', '))}">${g}</svg>`;
  const svg=el.querySelector('svg'),cr=svg.querySelector('.cruz');
  svg.querySelector('rect').addEventListener('mousemove',e=>{const b=svg.getBoundingClientRect();const px=(e.clientX-b.left)*W/b.width;
    const i=Math.max(0,Math.min(x.length-1,Math.round((px-m.l)/(iw/(Math.max(1,x.length-1))))));cr.setAttribute('x1',X(i));cr.setAttribute('x2',X(i));cr.setAttribute('visibility','visible');
    showTip(e,`<b>${esc(fx(x[i]))}</b>`+series.map(s=>`<span><i style="display:inline-block;width:8px;height:8px;border-radius:2px;background:${s.color};margin-right:6px"></i>${esc(s.nombre)}: </span>${fy(s.valores[i])}`).join('<br>'))});
  svg.querySelector('rect').addEventListener('mouseleave',()=>{cr.setAttribute('visibility','hidden');hideTip()});
}
function barras(el,{cats,valores,f,color=S[0],detalle}){ // horizontales, una serie
  const W=ancho(el),fila=30,m={l:Math.min(190,W*.36),r:60,t:4,b:4},H=m.t+m.b+cats.length*fila,iw=W-m.l-m.r,mx=Math.max(...valores,1e-9);let g='';
  cats.forEach((c,i)=>{const y=m.t+i*fila,w=Math.max(2,valores[i]/mx*iw);
    g+=`<text x="${m.l-8}" y="${y+fila/2+4}" text-anchor="end">${esc(c)}</text><path data-i="${i}" d="M${m.l} ${y+7}h${w-4}a4 4 0 0 1 4 4v${fila-22}a4 4 0 0 1-4 4h-${w-4}z" fill="${color}"/><text x="${m.l+w+6}" y="${y+fila/2+4}" style="fill:${C.texto}">${f(valores[i])}</text>`});
  el.innerHTML=`<svg viewBox="0 0 ${W} ${H}" role="img">${g}</svg>`;
  el.querySelectorAll('path').forEach(p=>{p.addEventListener('mousemove',e=>{const i=+p.dataset.i;showTip(e,`<b>${esc(cats[i])}</b>${f(valores[i])}${detalle?'<br><span>'+detalle(i)+'</span>':''}`)});p.addEventListener('mouseleave',hideTip)});
}
function columnas(el,{cats,series,f,alto=230}){ // agrupadas, de 1 a 3 series
  const W=ancho(el),H=alto,m={l:52,r:10,t:10,b:30},iw=W-m.l-m.r,ih=H-m.t-m.b;const mx=Math.max(...series.flatMap(s=>s.valores.filter(v=>v!=null)),1e-9);
  const tk=ticks(mx),top=tk[tk.length-1],gw=iw/cats.length,bw=Math.min(34,(gw-14)/series.length-2);let g='';
  tk.forEach(t=>{const y=m.t+ih-t/top*ih;g+=`<line x1="${m.l}" x2="${m.l+iw}" y1="${y}" y2="${y}" stroke="${C.linea}"/><text x="${m.l-8}" y="${y+4}" text-anchor="end">${f(t)}</text>`});
  cats.forEach((c,i)=>{const x0=m.l+i*gw+(gw-series.length*(bw+2))/2;g+=`<text x="${m.l+i*gw+gw/2}" y="${H-10}" text-anchor="middle">${esc(c)}</text>`;
    series.forEach((s,j)=>{const v=s.valores[i];if(v==null)return;const h=Math.max(2,v/top*ih),x=x0+j*(bw+2),y=m.t+ih-h;
      g+=`<path data-i="${i}" data-j="${j}" d="M${x} ${m.t+ih}v-${h-4}a4 4 0 0 1 4-4h${bw-8}a4 4 0 0 1 4 4v${h-4}z" fill="${s.color}"/>`})});
  el.innerHTML=(series.length>1?leyenda(series):'')+`<svg viewBox="0 0 ${W} ${H}" role="img">${g}</svg>`;
  el.querySelectorAll('path').forEach(p=>{p.addEventListener('mousemove',e=>{const i=+p.dataset.i;showTip(e,`<b>${esc(cats[i])}</b>`+series.map(s=>`<span>${esc(s.nombre)}: </span>${f(s.valores[i])}`).join('<br>'))});p.addEventListener('mouseleave',hideTip)});
}
function barrasGrupo(el,{cats,series,f}){ // horizontales agrupadas, admite negativos (línea en cero)
  const W=ancho(el),fila=18*series.length+14,m={l:Math.min(210,W*.42),r:16,t:4,b:4},H=m.t+m.b+cats.length*fila,iw=W-m.l-m.r;
  const vs=series.flatMap(s=>s.valores),lo=Math.min(0,...vs),hi=Math.max(0,...vs),X=v=>m.l+(v-lo)/((hi-lo)||1)*iw;let g='';
  cats.forEach((c,i)=>{const y=m.t+i*fila;g+=`<text x="${m.l-8}" y="${y+fila/2+4}" text-anchor="end">${esc(c)}</text>`;
    series.forEach((s,j)=>{const v=s.valores[i],x0=Math.min(X(0),X(v)),w=Math.max(2,Math.abs(X(v)-X(0))),yy=y+5+j*18;
      g+=`<rect data-i="${i}" x="${x0}" y="${yy}" width="${w}" height="14" rx="3" fill="${s.color}"/>`})});
  g+=`<line x1="${X(0)}" x2="${X(0)}" y1="${m.t}" y2="${H-m.b}" stroke="${C.texto_3}"/>`;
  el.innerHTML=leyenda(series)+`<svg viewBox="0 0 ${W} ${H}" role="img">${g}</svg>`;
  el.querySelectorAll('rect').forEach(p=>{p.addEventListener('mousemove',e=>{const i=+p.dataset.i;showTip(e,`<b>${esc(cats[i])}</b>`+series.map(s=>`<span>${esc(s.nombre)}: </span>${f(s.valores[i])}`).join('<br>'))});p.addEventListener('mouseleave',hideTip)});
}
function tabla(cols, filas){return '<div class="tabla"><table><thead><tr>'+cols.map(c=>`<th class="${c.num?'num':''}">${esc(c.t)}</th>`).join('')+'</tr></thead><tbody>'+
  filas.map(f=>'<tr>'+cols.map(c=>`<td class="${c.num?'num':''}">${c.html?c.f(f):esc(c.f(f))}</td>`).join('')+'</tr>').join('')+'</tbody></table></div>'}
const kpi=(t,v,n='')=>`<div class="card kpi"><h3>${esc(t)}</h3><div class="v">${v}</div>${n?`<div class="n">${n}</div>`:''}</div>`;
function segEsc(){return `<div class="ctrl"><div class="seg" role="group" aria-label="Escenario simulado">${D.escenarios.map(e=>`<button data-esc="${e.id}" aria-pressed="${st.esc===e.id}">${esc(e.nombre)}</button>`).join('')}</div><div class="desc">${esc(D.escenarios.find(e=>e.id===st.esc).descripcion)}</div></div>`}
function segLab(){return `<div class="ctrl"><div class="seg" role="group" aria-label="Escenario del laboratorio">${Object.keys(D.lab).map(k=>`<button data-lab="${k}" aria-pressed="${st.lab===k}">${esc(k)}</button>`).join('')}</div><div class="desc">${esc(D.lab[st.lab].descripcion)}</div></div>`}
const fechaCorta=s=>{const d=new Date(s+'T00:00:00');return d.toLocaleDateString('es-CO',{day:'numeric',month:'short'})};

// ---------- páginas
const PAGINAS=[
 ['Resumen',()=>{const P=D.piloto[st.esc],I=P.itt,ok=I.ic&&I.ic[0]>0,no=I.ic&&I.ic[1]<0;
  const col=ok?C.bien:no?C.mal:C.alerta,ico=ok?'✓':no?'✕':'?';
  return `<p class="sub">¿Las ofertas del motor venden? Diferencia entre quienes reciben ofertas y el grupo de control · piloto simulado</p>${segEsc()}
  <div class="fila c4">${kpi('Diferencia frente al control',pp(I.dif_pp),`Compran ${pct(I.conv.tratamiento)} con ofertas y ${pct(I.conv.control)} sin ellas`)}
  ${kpi('Intervalo de 95 %',`${pp(I.ic[0])} a ${pp(I.ic[1])}`,`Valor p ${nf(4).format(I.p)}`)}
  ${kpi('Clientes que compran por las ofertas',n0(I.ventas_incrementales),`De ${n0(I.n.tratamiento)} clientes con ofertas`)}
  ${kpi('Comisión incremental a 12 meses',cop(I.comision_incremental),'Comisión esperada del catálogo')}</div>
  <div class="card veredicto" style="margin-bottom:12px"><span class="ico" style="background:${col}" aria-hidden="true">${ico}</span><span>${esc(I.veredicto)}</span></div>
  <div class="fila c2"><div class="card"><h3>Clientes que ya compraron, tratamiento frente a control</h3><div id="g1"></div></div>
  <div class="card"><h3>De dónde salen las ventas del piloto</h3><div id="g2"></div><p class="aviso">Las compras por su cuenta ocurren en los dos grupos: por eso la cifra que importa es la diferencia frente al control, no las ventas por oferta.</p></div></div>
  <p class="aviso">${esc(D.meta.aviso_piloto)} ${esc(I.muestra)}</p>`},
  ()=>{const P=D.piloto[st.esc];lineas(g1,{x:P.semanas.map(s=>s.semana),fx:fechaCorta,fy:v=>v==null?'—':pct(v,0),
     series:[{nombre:'Tratamiento (con ofertas)',corto:'Tratamiento',color:S[0],valores:P.semanas.map(s=>s.tratamiento)},{nombre:'Control (sin ofertas)',corto:'Control',color:S[1],valores:P.semanas.map(s=>s.control)}]});
   barras(g2,{cats:['Por la oferta','Por su cuenta'],valores:[P.ventas.oferta,P.ventas['por su cuenta']],f:n0})}],
 ['Embudo',()=>{const P=D.piloto[st.esc],O=P.ofertas;return `<p class="sub">De 600 clientes a una venta: dónde se queda cada uno</p>${segEsc()}
  <div class="fila c4">${kpi('Clientes de la base',n0(D.plan.clientes),`${n0(D.plan.autorizan)} autorizan ofertas (Ley 1581)`)}${kpi('Ofertas mostradas',n0(O.mostradas),`${n0(O.control)} decisiones en control`)}
  ${kpi('Ofertas vistas',n0(O.vistas),`Alcance ${pct(O.alcance)}`)}${kpi('Ofertas aceptadas',n0(O.aceptadas),`${pct(O.conv)} de las vistas`)}</div>
  <div class="fila c2"><div class="card"><h3>Decisiones del piloto por resultado</h3><div id="g1"></div></div>
  <div class="card"><h3>Conversión por oferta vista frente a la campaña previa, por ramo</h3><div id="g2"></div></div></div>
  <div class="card"><h3>Base del reto: embudo de las campañas previas</h3>${tabla([{t:'Campaña',f:r=>r.campana},{t:'Canal',f:r=>r.canal},{t:'Elegibles',num:1,f:r=>n0(+r.elegibles)},{t:'Impactados',num:1,f:r=>n0(+r.impactados)},{t:'Interesados',num:1,f:r=>n0(+r.interesados)},{t:'Ventas',num:1,f:r=>n0(+r.ventas)},{t:'Ventas / impactados',num:1,f:r=>pct(+r.conv_ventas_impactados)}],D.base.campanas)}</div>`},
  ()=>{const P=D.piloto[st.esc];barras(g1,{cats:P.resultados.map(r=>r.resultado),valores:P.resultados.map(r=>r.n),f:n0});
   columnas(g2,{cats:P.por_ramo.map(r=>r.ramo),f:v=>pct(v,0),series:[{nombre:'Piloto: aceptadas / vistas',color:S[0],valores:P.por_ramo.map(r=>r.vistas?r.conv:null)},{nombre:'Campaña previa: ventas / impactados',color:S[1],valores:P.por_ramo.map(r=>r.previa)}]})}],
 ['¿El modelo acierta?',()=>{const P=D.piloto[st.esc],O=P.ofertas;return `<p class="sub">Lo que el motor esperaba frente a lo que pasó</p>${segEsc()}
  <div class="fila c3">${kpi('Observado / esperado por el motor',O.observado_motor==null?'—':nf(2).format(O.observado_motor),'1 = calibrado · más de 1 = el motor subestima')}
  ${kpi('Coinciden con la regla v1.3',pct(P.coinciden_regla),'Sin reentrenar con las respuestas, el motor elige casi lo mismo que la regla')}
  ${kpi('Motor frente a la regla',P.motor_frente_regla==null?'—':(P.motor_frente_regla>=0?'+':'−')+nf(1).format(Math.abs(P.motor_frente_regla*100))+' %','Comisión esperada con la verdad simulada (solo existe en la simulación)')}</div>
  <div class="fila c2"><div class="card"><h3>Calibración: P(acepta) del motor frente a la aceptación observada</h3><div id="g1"></div></div>
  <div class="card"><h3>Aceptación con evento reciente (momento) y sin él</h3><div id="g2"></div></div></div>
  <p class="aviso" style="margin-top:-2px">En el piloto, el motor de la población no se reentrena: aprende solo de cada cliente dentro de su sesión. Lo que gana al aprender de todas las respuestas (abajo, el laboratorio) entra con <code>train_motor.py --respuestas</code> y solo si gana el campeón/retador.</p>
  <div class="fila c2"><div class="card"><h3>Laboratorio («señal»): comisión por oferta en 40 rondas</h3><div id="g3"></div></div>
  <div class="card"><h3>Laboratorio («señal»): error de calibración</h3><div id="g4"></div></div></div>`},
  ()=>{const P=D.piloto[st.esc];columnas(g1,{cats:P.tramos.map(t=>t.tramo),f:v=>pct(v,0),series:[{nombre:'P(acepta) del motor',color:S[0],valores:P.tramos.map(t=>t.p_motor)},{nombre:'Aceptación observada',color:S[1],valores:P.tramos.map(t=>t.conv)}]});
   columnas(g2,{cats:P.momento.map(t=>t.momento),f:v=>pct(v,0),series:[{nombre:'P(acepta) del motor',color:S[0],valores:P.momento.map(t=>t.p_motor)},{nombre:'Aceptación observada',color:S[1],valores:P.momento.map(t=>t.conv)}]});
   const L=D.lab['señal'];const r=L.series[0].valores.map((_,i)=>i+1);
   lineas(g3,{x:r,fx:v=>'Ronda '+v,fy:v=>v==null?'—':cop(v),min0:false,series:L.series.filter(s=>!/sin /.test(s.nombre)).map((s,i)=>({nombre:s.nombre,corto:s.nombre.split(' ')[0],color:S[i],valores:s.valores}))});
   lineas(g4,{x:r,fx:v=>'Ronda '+v,fy:v=>v==null?'—':nf(3).format(v),series:L.calibracion.map((s,i)=>({nombre:s.nombre==='motor'?'Motor':'Regla v1.3',corto:s.nombre==='motor'?'Motor':'Regla',color:S[i],valores:s.valores}))})}],
 ['Contacto',()=>{const B=D.plan;return `<p class="sub">Contactar sin cansar: canal, tope y reglas que nunca se rompen</p>
  <div class="fila c4">${kpi('Violaciones de las reglas',`<span class="${B.violaciones?'bad':'ok'}">${n0(B.violaciones)}</span>`,'Backtest de todo el año: debe ser 0')}${kpi('Push máximo a un cliente en 30 días',n0(+B.backtest.max_push_30d),'Tope por cliente según su uso de la app')}
  ${kpi('Ofertas en el backtest',n0(+B.backtest.ofertas),`${n0(+B.backtest.push)} push y ${n0(+B.backtest.banner)} banner`)}${kpi('Clientes alcanzados',n0(+B.backtest.clientes_alcanzados),`${n0(+B.backtest.evaluaciones)} evaluaciones`)}</div>
  <div class="fila c2"><div class="card"><h3>Invariantes del backtest</h3>${tabla([{t:'Regla',f:r=>r.invariante},{t:'Violaciones',num:1,html:1,f:r=>`<span class="pill ${+r.violaciones?'bad':'ok'}">${+r.violaciones?'✕ ':'✓ '}${n0(+r.violaciones)}</span>`}],B.invariantes)}</div>
  <div class="card"><h3>Plan al corte: resultado del motor para los 600 clientes</h3><div id="g1"></div></div></div>`},
  ()=>{barras(g1,{cats:D.plan.resultados.map(r=>r.resultado),valores:D.plan.resultados.map(r=>r.n),f:n0})}],
 ['Piloto real',()=>{const I=D.piloto[st.esc].itt;return `<p class="sub">Cuántos clientes necesita el piloto real para saber</p>${segEsc()}
  <div class="fila c3">${kpi('Clientes en control hoy',n0(I.n.control),`Con ${n0(I.n.tratamiento)} en tratamiento`)}${kpi('Efecto mínimo detectable',nf(1).format(I.mde_pp)+' pp','Con 95 % de confianza y 80 % de potencia, con este tamaño')}${kpi('Valor p',nf(4).format(I.p),'Prueba z de dos proporciones')}</div>
  <div class="card" style="margin-bottom:12px"><h3>M6: clientes por grupo para detectar el aumento (α 5 %, potencia 80 %)</h3>${tabla([{t:'Ramo',f:r=>r.ramo},{t:'Conversión de hoy',num:1,f:r=>pct(r.base)},{t:'+20 %',num:1,f:r=>n0(r.n20)},{t:'+50 %',num:1,f:r=>n0(r.n50)},{t:'+100 %',num:1,f:r=>n0(r.n100)}],D.m6)}</div>
  <div class="card"><p style="margin:0">${esc(I.muestra)}</p><p class="aviso">La base del reto tiene 600 clientes y un control del 10 %. Para ver un aumento de 50 % en el SOAT hacen falta ${n0(D.m6[0].n50)} clientes en control y otros tantos en tratamiento: el piloto real se corre con la base completa de Lulo, con el mismo grupo de control por hash.</p></div>`},()=>{}],
 ['Laboratorio',()=>{const L=D.lab[st.lab],R=L.resumen;return `<p class="sub">¿El motor aprende? Verdad simulada sobre los clientes de la base</p>${segLab()}
  <div class="fila c3">${kpi('Motor frente a la regla',(R.motor_frente_a_regla>=0?'+':'−')+nf(1).format(Math.abs(R.motor_frente_a_regla*100))+' %','Comisión por oferta, últimas 10 de 40 rondas')}${kpi('Camino al techo: motor',pct(R.motor_del_techo,0),'0 % = azar · 100 % = oráculo')}${kpi('Camino al techo: regla',pct(R.regla_del_techo,0),'')}</div>
  <div class="card" style="margin-bottom:12px"><h3>Comisión por oferta de cada política</h3><div id="g1"></div></div>
  <div class="fila c2"><div class="card"><h3>Lo que aprendió el motor de cada efecto frente a la verdad</h3><div id="g2"></div></div>
  <div class="card"><h3>Dispersión del apetito entre clientes (τ, Bayes empírico)</h3><div id="g3"></div></div></div>`},
  ()=>{const L=D.lab[st.lab];const r=L.series[0].valores.map((_,i)=>i+1);
   lineas(g1,{x:r,fx:v=>'Ronda '+v,fy:v=>v==null?'—':cop(v),min0:false,series:L.series.map((s,i)=>({nombre:s.nombre,corto:s.nombre.split(' (')[0].replace('Motor bayesiano v2.0','Motor').replace('Regla v1.3','Regla'),color:S[i],valores:s.valores}))});
   const P=L.pesos;barrasGrupo(g2,{cats:P.map(p=>p.efecto.replace('Todos los ramos','Todos')),f:v=>nf(2).format(v),series:[{nombre:'Aprendido por el motor',color:S[0],valores:P.map(p=>p.aprendido)},{nombre:'Verdad sembrada',color:S[1],valores:P.map(p=>p.verdad)}]});
   lineas(g3,{x:L.tau.map(t=>t.ronda),fx:v=>'Ronda '+v,fy:v=>v==null?'—':nf(2).format(v),series:[{nombre:'τ estimado por el motor',corto:'Estimado',color:S[0],valores:L.tau.map(t=>t.tau)},{nombre:'τ verdadero',corto:'Verdad',color:S[1],valores:L.tau.map(t=>t.verdad)}]})}],
 ['Casos reales',()=>{const cs=D.casos,cuenta=k=>cs.filter(c=>c.resultado===k).length;const cls={'éxito':'ok','fracaso':'bad','mixto':'warn','sin efecto':'mut'};
  return `<p class="sub">Quién usó métodos como estos y qué pasó · ${cs.length} casos con fuente (docs/CASOS.md)</p>
  <div class="fila c4">${kpi('Éxitos',n0(cuenta('éxito')))}${kpi('Mixtos',n0(cuenta('mixto')))}${kpi('Sin efecto',n0(cuenta('sin efecto')))}${kpi('Fracasos',n0(cuenta('fracaso')))}</div>
  <div class="card">${tabla([{t:'Empresa',f:c=>c.empresa+' ('+c.anio+')'},{t:'Parte del prototipo',f:c=>c.conexion},{t:'Resultado',html:1,f:c=>`<span class="pill ${cls[c.resultado]}">${esc(c.resultado)}</span>`},{t:'Cifra',f:c=>c.cifra},{t:'Lección',f:c=>c.leccion},{t:'Fuente',html:1,f:c=>`<a href="${esc(c.url)}" target="_blank" rel="noopener">${esc(c.fuente)}</a> · ${esc(c.confianza)}`}],cs)}</div>`},()=>{}],
 ['Base del reto',()=>{const B=D.base;return `<p class="sub">La base del reto: lo que hay hoy (sintética y académica)</p>
  <div class="fila c4">${kpi('Pólizas emitidas en el año',n0(B.polizas_total))}${kpi('Comisión de las primas emitidas',cop(B.comision_primas),'Primera prima × comisión')}${kpi('Pagado a otras aseguradoras',cop(B.pagado_externo),'Clientes de la base, en el año')}${kpi('Conversión de las campañas previas',pct(B.conv_campanas),'Ventas / impactados')}</div>
  <div class="card" style="margin-bottom:12px"><h3>Pólizas emitidas por mes y ramo</h3><div id="g1"></div></div>
  <div class="card"><h3>Catálogo: prima, comisión y persistencia</h3>${tabla([{t:'Ramo',f:r=>r.ramo},{t:'Prima',num:1,f:r=>cop(+r.prima_cop)},{t:'Comisión',num:1,f:r=>pct(+r.comision_pct,0)},{t:'Persistencia 12 m',num:1,f:r=>r.persistencia_12m?pct(+r.persistencia_12m,0):'—'},{t:'Cancelación',num:1,f:r=>pct(+r.cancelacion_pct,0)},{t:'Comisión a 12 meses',num:1,f:r=>cop(+r.comision_12m_cop)},{t:'Compras por fuera',num:1,f:r=>n0(+r.compras_por_su_cuenta)}],B.catalogo)}</div>
  <p class="aviso">${esc(D.meta.aviso_base)}</p>`},
  ()=>{const B=D.base;lineas(g1,{x:B.meses,fx:m=>{const d=new Date(m+'-01T00:00:00');return d.toLocaleDateString('es-CO',{month:'short',year:'2-digit'})},fy:v=>v==null?'—':n0(v),etiquetas:false,
    series:D.ramos.map((r,i)=>({nombre:r,color:S[i],valores:B.polizas[r]}))})}],
];
const tabs=document.getElementById('tabs'),main=document.getElementById('main');
tabs.innerHTML=PAGINAS.map((p,i)=>`<button role="tab" data-p="${i}">${i+1} · ${esc(p[0])}</button>`).join('');
function pintar(){hideTip();tabs.querySelectorAll('button').forEach(b=>b.setAttribute('aria-selected',+b.dataset.p===st.pagina));
  main.innerHTML=`<section class="page on" role="tabpanel">${PAGINAS[st.pagina][1]()}</section>`;
  const g=id=>main.querySelector('#'+id);window.g1=g('g1');window.g2=g('g2');window.g3=g('g3');window.g4=g('g4');PAGINAS[st.pagina][2]();
  try{history.replaceState(null,'','#p='+st.pagina)}catch(e){}}
let espera;addEventListener('resize',()=>{clearTimeout(espera);espera=setTimeout(pintar,150)});
tabs.addEventListener('click',e=>{const b=e.target.closest('button');if(b){st.pagina=+b.dataset.p;pintar()}});
main.addEventListener('click',e=>{const b=e.target.closest('button');if(!b)return;if(b.dataset.esc){st.esc=b.dataset.esc;pintar()}if(b.dataset.lab){st.lab=b.dataset.lab;pintar()}});
document.getElementById('pie').innerHTML=`${esc(D.meta.etiqueta)} · reglas ${esc(D.meta.reglas)} · ${esc(D.meta.motor)} · ${esc(D.meta.laboratorio)} · base al ${esc(D.meta.base_corte)} · exportador ${esc(D.meta.exportador)}. Vista previa del dashboard de Power BI (powerbi/Lulo.pbip): mismas cifras y mismas definiciones que las medidas DAX.`;
pintar();
</script>
</body>
</html>
"""
