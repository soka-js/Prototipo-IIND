"""Vista previa web del dashboard de impacto (powerbi/vista_previa.html): las 3 páginas, sin Power BI.

Calcula cada cifra con la misma definición que la medida DAX del mismo nombre (scripts/powerbi_modelo.py), a partir de
las mismas tablas chicas. Sirve para revisar el dashboard desde cualquier computador y para comparar: si una cifra de
Power BI no coincide con esta, la medida quedó mal. El selector de escenario funciona igual que en Power BI.
"""

from __future__ import annotations

import csv
import html as _h
import io
import json
import math
from datetime import date

from powerbi_modelo import COLOR as C
from powerbi_modelo import ETIQUETA, SERIES, miles, paginas, textos

MESES = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"]


def _t(texto: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(texto)))


def num(v: float, d: int = 0) -> str:
    """Formato de Colombia: punto de miles y coma decimal."""
    s = f"{abs(v):,.{d}f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return ("-" if v < 0 and round(abs(v), d) else "") + s


def signo(v: float, d: int = 1) -> str:
    return ("+" if v >= 0 else "-") + num(abs(v), d)


def pesos(v: float) -> str:
    return "$" + num(v)


def millones(v: float) -> str:
    return "$" + num(v / 1e6, 1) + " M"


def fecha(iso: str) -> str:
    f = date.fromisoformat(iso)
    return f"{f.day} {MESES[f.month - 1]}"


# ------------------------------------------------------------------ cifras (mismas definiciones que las medidas)
def cifras(chicas: dict[str, str]) -> list[dict]:
    T = {n: _t(t) for n, t in chicas.items()}
    out = []
    control = {r["indicador"]: int(r["valor"]) for r in T["control"]}
    for e in sorted(T["escenario"], key=lambda r: int(r["orden"])):
        k = e["escenario"]
        i = next(r for r in T["indicadores"] if r["escenario"] == k)
        n = {c: int(v) for c, v in i.items() if c != "escenario"}
        ct, cc = n["compran_trat"] / n["clientes_trat"], n["compran_ctrl"] / n["clientes_ctrl"]
        dif = (ct - cc) * 100
        se = math.sqrt(ct * (1 - ct) / n["clientes_trat"] + cc * (1 - cc) / n["clientes_ctrl"])
        lo, hi = dif - 1.96 * se * 100, dif + 1.96 * se * 100
        veredicto = ("Sí: con ofertas compran más clientes" if lo > 0 else
                     "No: con ofertas compran menos" if hi < 0 else "Todavía no se sabe: cabe en el azar")
        pc = n["comision_trat"] / n["clientes_trat"] - n["comision_ctrl"] / n["clientes_ctrl"]
        lab = [r for r in T["laboratorio"] if r["escenario"] == k]
        res = next((float(r["motor_frente_a_regla"]) for r in T["laboratorio_resumen"] if r["escenario"] == k), None)
        out.append({
            "escenario": k, "nombre": e["nombre"],
            "dif": dif, "ic": (lo, hi), "veredicto": veredicto, "conv": (ct, cc),
            "nuevos": (ct - cc) * n["clientes_trat"], "pc": pc, "adicional": pc * n["clientes_trat"], "por_mil": pc * 1000,
            "polizas": n["ventas_oferta"], "de_oferta": n["ventas_oferta"] / n["ventas"],
            "aceptan": n["ofertas_aceptadas"] / n["ofertas_vistas"],
            "curva": {g: [(r["semana"], float(r["conversion"])) for r in T["curva"] if r["escenario"] == k and r["grupo"] == g]
                      for g in ("Con ofertas", "Sin ofertas")},
            "ramo": sorted(((r["seguro"], int(r["comision_oferta"])) for r in T["ramo"] if r["escenario"] == k),
                           key=lambda x: -x[1]),
            "segmento": sorted(((r["segmento"], int(r["aceptadas"]) / int(r["vistas"]) if int(r["vistas"]) else 0.0)
                                for r in T["segmento"] if r["escenario"] == k), key=lambda x: -x[1]),
            "origen": [(r["origen"], int(r["ventas"])) for r in sorted((r for r in T["origen"] if r["escenario"] == k),
                                                                       key=lambda r: int(r["orden"]))],
            "violaciones": sum(int(r["violaciones"]) for r in T["reglas"]),
            "push": control["push_max_30d"], "sin_aut": control["sin_autorizacion"], "lab": res,
            "lab_series": {p: [(int(r["ronda"]), float(r["comision_por_oferta"])) for r in lab if r["politica"] == p]
                           for p in sorted({r["politica"] for r in lab},
                                           key=lambda p: next(int(r["politica_orden"]) for r in lab if r["politica"] == p))},
            "reglas": [(r["regla"], int(r["violaciones"])) for r in T["reglas"]],
        })
    return out


# ------------------------------------------------------------------ piezas
def caja(x, y, w, h, contenido: str, fondo: str = C["tarjeta"], extra: str = "") -> str:
    return (f'<div class="b" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px;background:{fondo};{extra}">'
            f"{contenido}</div>")


def tarjeta(x, y, valor: str, etiqueta: str, estilo: str = "normal", w=296, h=128) -> str:
    fondo, cifra, et, tam = {"lima": (C["lima"], C["pagina"], C["pagina"], 40), "normal": (C["tarjeta"], C["lima"], C["texto"], 36),
                             "chica": (C["tarjeta"], C["lima"], C["texto"], 28),
                             "texto": (C["tarjeta"], C["texto"], C["texto_2"], 19),
                             "blanca": (C["tarjeta"], C["texto"], C["texto_2"], 30)}[estilo]
    return caja(x, y, w, h, f'<div class="v" style="color:{cifra};font-size:{tam}px">{_h.escape(valor)}</div>'
                            f'<div class="l" style="color:{et}">{_h.escape(etiqueta)}</div>', fondo, "padding:18px 22px")


def _y(v, lo, hi, top, alto):
    return top + alto - (v - lo) / (hi - lo) * alto if hi > lo else top + alto


def _separar(etiquetas: list[list], minimo: float = 15) -> None:
    """Corre hacia abajo las etiquetas del final que se pisan."""
    etiquetas.sort(key=lambda e: e[0])
    for a, b in zip(etiquetas, etiquetas[1:]):
        if b[0] - a[0] < minimo:
            b[0] = a[0] + minimo


def lineas(w, h, series: dict[str, list[tuple]], colores: list[str], fmt_y, fmt_x, titulo: str, desde_cero=True) -> str:
    izq, der, arriba, abajo = 56, 84, 58, 30
    ancho, alto = w - izq - der, h - arriba - abajo
    vals = [v for s in series.values() for _, v in s]
    lo = 0.0 if desde_cero else min(vals)
    hi = max(vals) * 1.1
    xs = [x for x, _ in next(iter(series.values()))]
    px = {x: izq + i / max(1, len(xs) - 1) * ancho for i, x in enumerate(xs)}
    svg = [f'<svg width="{w}" height="{h}" role="img" aria-label="{_h.escape(titulo)}">']
    for j in range(5):
        v = lo + (hi - lo) * j / 4
        yy = _y(v, lo, hi, arriba, alto)
        svg.append(f'<line x1="{izq}" x2="{izq + ancho}" y1="{yy:.1f}" y2="{yy:.1f}" stroke="{C["linea"]}"/>'
                   f'<text x="{izq - 8}" y="{yy + 4:.1f}" text-anchor="end" class="ax">{fmt_y(v)}</text>')
    for i in sorted({0, len(xs) // 3, 2 * len(xs) // 3, len(xs) - 1}):
        svg.append(f'<text x="{px[xs[i]]:.1f}" y="{h - 8}" text-anchor="middle" class="ax">{fmt_x(xs[i])}</text>')
    finales = []
    for (nombre, s), col in zip(series.items(), colores):
        pts = " ".join(f"{px[x]:.1f},{_y(v, lo, hi, arriba, alto):.1f}" for x, v in s)
        svg.append(f'<polyline points="{pts}" fill="none" stroke="{col}" stroke-width="2.5" stroke-linejoin="round">'
                   f"<title>{_h.escape(nombre)}</title></polyline>")
        for x, v in s:
            svg.append(f'<circle cx="{px[x]:.1f}" cy="{_y(v, lo, hi, arriba, alto):.1f}" r="7" fill="transparent">'
                       f"<title>{_h.escape(nombre)} · {fmt_x(x)}: {fmt_y(v, True)}</title></circle>")
        x, v = s[-1]
        finales.append([_y(v, lo, hi, arriba, alto), fmt_y(v, True), col])
    _separar(finales)
    for yy, txt, col in finales:
        svg.append(f'<text x="{izq + ancho + 6}" y="{yy + 4:.1f}" class="fin" fill="{col}">{txt}</text>')
    svg.append("</svg>")
    ley = "".join(f'<span><i style="background:{c}"></i>{_h.escape(n)}</span>' for n, c in zip(series, colores))
    return f'<div class="t">{_h.escape(titulo)}</div><div class="ley">{ley}</div><div class="svg">{"".join(svg)}</div>'


def barras(w, h, datos: list[tuple], fmt, titulo: str) -> str:
    izq, der, arriba = 110, 70, 56
    alto = (h - arriba - 20) / max(1, len(datos))
    hi = max(v for _, v in datos) or 1
    svg = [f'<svg width="{w}" height="{h}" role="img" aria-label="{_h.escape(titulo)}">']
    for i, (n, v) in enumerate(datos):
        y = arriba + i * alto
        largo = v / hi * (w - izq - der)
        svg.append(f'<text x="14" y="{y + alto / 2 + 4:.1f}" class="cat">{_h.escape(n)}</text>'
                   f'<rect x="{izq}" y="{y + alto * 0.2:.1f}" width="{max(largo, 1):.1f}" height="{alto * 0.6:.1f}" rx="3" '
                   f'fill="{C["lima"]}"><title>{_h.escape(n)}: {fmt(v)}</title></rect>'
                   f'<text x="{izq + largo + 6:.1f}" y="{y + alto / 2 + 4:.1f}" class="val">{fmt(v)}</text>')
    svg.append("</svg>")
    return f'<div class="t">{_h.escape(titulo)}</div><div class="svg">{"".join(svg)}</div>'


def columnas(w, h, datos: list[tuple], fmt, titulo: str) -> str:
    arriba, abajo = 76, 46
    hi = max(v for _, v in datos) or 1
    ancho = (w - 32) / max(1, len(datos))
    svg = [f'<svg width="{w}" height="{h}" role="img" aria-label="{_h.escape(titulo)}">']
    for i, (n, v) in enumerate(datos):
        x = 16 + i * ancho
        alto = v / hi * (h - arriba - abajo)
        y = h - abajo - alto
        palabras = n.split(" ", 1)
        svg.append(f'<rect x="{x + ancho * 0.18:.1f}" y="{y:.1f}" width="{ancho * 0.64:.1f}" height="{max(alto, 1):.1f}" rx="3" '
                   f'fill="{C["lima"]}"><title>{_h.escape(n)}: {fmt(v)}</title></rect>'
                   f'<text x="{x + ancho / 2:.1f}" y="{y - 8:.1f}" text-anchor="middle" class="val">{fmt(v)}</text>'
                   + "".join(f'<text x="{x + ancho / 2:.1f}" y="{h - abajo + 18 + 14 * j}" text-anchor="middle" class="cat">'
                             f"{_h.escape(p)}</text>" for j, p in enumerate(palabras)))
    svg.append("</svg>")
    return f'<div class="t">{_h.escape(titulo)}</div><div class="svg">{"".join(svg)}</div>'


def dona(w, h, datos: list[tuple], titulo: str) -> str:
    total = sum(v for _, v in datos) or 1
    cx, cy, r, grosor = w / 2, 150, 78, 30
    svg = [f'<svg width="{w}" height="{h}" role="img" aria-label="{_h.escape(titulo)}">']
    a0 = -math.pi / 2
    ley = []
    for (n, v), col in zip(datos, SERIES):
        a1 = a0 + 2 * math.pi * v / total
        grande = 1 if a1 - a0 > math.pi else 0
        p = lambda a, rr: (cx + rr * math.cos(a), cy + rr * math.sin(a))  # noqa: E731
        (x0, y0), (x1, y1) = p(a0, r), p(a1 - 0.001, r)
        (x2, y2), (x3, y3) = p(a1 - 0.001, r - grosor), p(a0, r - grosor)
        svg.append(f'<path d="M{x0:.1f},{y0:.1f} A{r},{r} 0 {grande} 1 {x1:.1f},{y1:.1f} L{x2:.1f},{y2:.1f} '
                   f'A{r - grosor},{r - grosor} 0 {grande} 0 {x3:.1f},{y3:.1f} Z" fill="{col}" stroke="{C["tarjeta"]}" '
                   f'stroke-width="2"><title>{_h.escape(n)}: {v} ({num(100 * v / total)} %)</title></path>')
        ley.append(f'<span><i style="background:{col}"></i>{_h.escape(n)}: {v} ({num(100 * v / total)} %)</span>')
        a0 = a1
    svg.append("</svg>")
    return (f'<div class="t">{_h.escape(titulo)}</div><div class="svg">{"".join(svg)}</div>'
            f'<div class="ley col">{"".join(ley)}</div>')


def tabla(filas: list[tuple]) -> str:
    cuerpo = "".join(f"<tr><td>{_h.escape(r)}</td><td class=\"n\">{v}</td></tr>" for r, v in filas)
    return f'<table><thead><tr><th>Regla</th><th class="n">Violaciones</th></tr></thead><tbody>{cuerpo}</tbody></table>'


# ------------------------------------------------------------------ páginas
def html(chicas: dict[str, str], notas: dict) -> str:
    tx = textos(notas)
    E = cifras(chicas)
    pags = paginas(tx)
    pct = lambda v, fino=False: num(100 * v, 1) + " %"  # noqa: E731

    def por_escenario(f) -> str:
        return "".join(f'<div class="esc" data-e="{i}">{f(e)}</div>' for i, e in enumerate(E))

    def selector() -> str:
        return ('<div class="sl">' + "".join(f'<button class="s" data-e="{i}" type="button">{_h.escape(e["nombre"])}</button>'
                                             for i, e in enumerate(E)) + "</div>")

    def p1(e):
        x = [24, 336, 648, 960]
        return (tarjeta(x[0], 138, signo(e["dif"]) + " pp", "más clientes compran con las ofertas", "lima")
                + tarjeta(x[1], 138, f"{signo(e['ic'][0])} a {signo(e['ic'][1])} pp", "intervalo de 95 % de la diferencia",
                          "chica")
                + tarjeta(x[2], 138, num(e["nuevos"]), "clientes con seguro gracias a las ofertas")
                + tarjeta(x[3], 138, millones(e["adicional"]), "comisión adicional a 12 meses")
                + caja(24, 282, 800, 372, lineas(800, 340, e["curva"], [C["lima"], C["gris"]],
                                                 lambda v, fino=False: num(100 * v, 1) + " %", fecha,
                                                 "Clientes que ya compraron un seguro, semana a semana"))
                + tarjeta(840, 282, e["veredicto"], "¿Las ofertas venden?", "texto", 416, 116)
                + tarjeta(840, 410, pesos(e["pc"]), "comisión por cliente contactado", "blanca", 416, 116)
                + tarjeta(840, 538, millones(e["por_mil"]), "por cada 1.000 clientes contactados (proyección lineal)",
                          "blanca", 416, 116))

    def p2(e):
        x = [24, 336, 648, 960]
        return (tarjeta(x[0], 138, num(e["polizas"]), "pólizas vendidas por las ofertas")
                + tarjeta(x[1], 138, pct(e["de_oferta"]), "de las ventas vino de una oferta")
                + tarjeta(x[2], 138, pct(e["aceptan"]), "aceptan la oferta que ven")
                + tarjeta(x[3], 138, pesos(e["pc"]), "comisión por cliente contactado")
                + caja(24, 282, 610, 372, barras(610, 340, e["ramo"], millones,
                                                 "Comisión a 12 meses de las pólizas vendidas por las ofertas, por seguro"))
                + caja(650, 282, 300, 372, columnas(300, 340, e["segmento"], pct, "Aceptan la oferta, por tipo de cliente"))
                + caja(966, 282, 290, 372, dona(290, 260, e["origen"], "Cómo se vendieron las pólizas")))

    def p3(e):
        x = [24, 336, 648, 960]
        lab = "—" if e["lab"] is None else signo(100 * e["lab"]) + " %"
        return (tarjeta(x[0], 138, num(e["violaciones"]), "violaciones de las reglas", "lima")
                + tarjeta(x[1], 138, num(e["push"]), "push máximo a un cliente en 30 días")
                + tarjeta(x[2], 138, num(e["sin_aut"]), "sin autorización: nunca contactados")
                + tarjeta(x[3], 138, lab, "laboratorio: más comisión que la regla")
                + caja(24, 282, 520, 372, f'<div class="t">{_h.escape(tx["titulo_reglas"])}</div>{tabla(e["reglas"])}')
                + caja(560, 282, 696, 372, lineas(696, 340, e["lab_series"], SERIES, lambda v, fino=False: pesos(v), str,
                                                  tx["titulo_lab"])))

    cuerpo = []
    for (pestana, titulo, sub, visuales), f in zip(pags, (p1, p2, p3)):
        pie = next(v[6] for v in visuales if v[0] == "pie")
        cuerpo.append(
            f'<section class="hoja"><h2 class="pest">{_h.escape(pestana)}</h2><div class="marco"><div class="p">'
            f'<div class="h1">{_h.escape(titulo)}</div><div class="h2">{_h.escape(sub)}</div>'
            f'<div class="tag">{_h.escape(ETIQUETA)}</div>{selector()}{por_escenario(f)}'
            f'<div class="pie">{_h.escape(pie)}</div></div></div></section>')
    css = f"""
*{{box-sizing:border-box}}
body{{margin:0;background:#05091a;font-family:'Segoe UI',system-ui,-apple-system,sans-serif;color:{C['texto']};padding:16px}}
.top{{max-width:1280px;margin:0 auto 12px;color:{C['texto_2']};font-size:13px;line-height:1.5}}
.top b{{color:{C['texto']}}}
.hoja{{max-width:1280px;margin:0 auto 28px}}
.pest{{font-size:13px;font-weight:600;color:{C['lima']};margin:0 0 6px;letter-spacing:.04em;text-transform:uppercase}}
.marco{{width:100%;height:calc(720px * var(--k,1));overflow:hidden}}
.p{{position:relative;width:1280px;height:720px;background:{C['pagina']};transform:scale(var(--k,1));transform-origin:0 0;border-radius:6px}}
.h1{{position:absolute;left:24px;top:14px;font-size:28px;font-weight:700}}
.h2{{position:absolute;left:24px;top:52px;font-size:14px;color:{C['texto_3']};width:900px}}
.tag{{position:absolute;left:856px;top:20px;width:400px;text-align:right;font-size:12px;color:{C['lima']};white-space:nowrap}}
.sl{{position:absolute;left:24px;top:86px;width:1232px;height:40px;display:flex;gap:8px}}
.s{{flex:1;background:{C['linea']};border:0;border-radius:6px;font:inherit;font-size:14px;color:{C['texto_2']};cursor:pointer}}
.s:focus-visible{{outline:2px solid {C['lima']};outline-offset:2px}}
.b{{position:absolute;border-radius:10px;overflow:hidden}}
.v{{font-weight:700;line-height:1.15}}
.l{{font-size:14px;margin-top:8px;line-height:1.3}}
.t{{font-size:15px;font-weight:600;padding:12px 14px 0}}
.ley{{display:flex;gap:14px;padding:6px 14px 0;font-size:12px;color:{C['texto_2']}}}
.ley.col{{flex-direction:column;gap:6px}}
.ley i{{display:inline-block;width:10px;height:10px;border-radius:50%;margin-right:6px;vertical-align:-1px}}
.svg{{position:absolute;left:0;bottom:0}}
.ax{{font-size:11px;fill:{C['texto_2']}}} .fin{{font-size:12px;font-weight:600}}
.cat{{font-size:13px;fill:{C['texto_2']}}} .val{{font-size:13px;fill:{C['texto']}}}
table{{width:100%;border-collapse:collapse;font-size:13px;margin-top:10px}}
th{{text-align:left;background:{C['linea']};font-weight:600}}
th,td{{padding:8px 14px;border-bottom:1px solid {C['linea']}}} td.n,th.n{{text-align:right}} td.n{{color:{C['lima']}}}
.pie{{position:absolute;left:24px;top:668px;width:1232px;font-size:12px;color:{C['texto_3']};line-height:1.4}}
.esc{{display:none}}
"""
    for i in range(len(E)):
        css += (f'body[data-e="{i}"] .esc[data-e="{i}"]{{display:block}}'
                f'body[data-e="{i}"] .s[data-e="{i}"]{{background:{C["lima"]};color:{C["pagina"]};font-weight:600}}\n')
    js = """
const k=()=>document.documentElement.style.setProperty('--k',Math.min(1,(document.querySelector('.hoja').clientWidth)/1280));
addEventListener('resize',k);k();
document.addEventListener('click',ev=>{const b=ev.target.closest('.s');if(b)document.body.dataset.e=b.dataset.e;});
"""
    datos = {"escenarios": [e["nombre"] for e in E], "cifras": [{c: e[c] for c in ("dif", "ic", "nuevos", "pc", "adicional")}
                                                                 for e in E]}
    return ("<!doctype html>\n<html lang=\"es\"><head><meta charset=\"utf-8\">"
            '<meta name="viewport" content="width=device-width, initial-scale=1"><meta name="robots" content="noindex">'
            f"<title>Dashboard de impacto · Lulo</title><style>{css}</style></head>"
            f'<body data-e="0"><div class="top"><b>Vista previa del dashboard de Power BI</b> '
            f"(powerbi/Lulo_Impacto.pbip): las mismas 3 páginas, con las mismas cifras y definiciones que las medidas. "
            f"{_h.escape(ETIQUETA)}. Base de {miles(notas['clientes'])} clientes sintéticos: no son métricas de Lulo Bank.</div>"
            + "".join(cuerpo)
            + f'<script type="application/json" id="cifras">{json.dumps(datos, ensure_ascii=False)}</script>'
            + f"<script>{js}</script></body></html>\n")
