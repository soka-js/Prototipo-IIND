"""Dashboard de impacto en Power BI: 3 páginas que responden «¿qué podría generar el motor?».

Lo genera scripts/exportar_powerbi.py a partir de las tablas de detalle (powerbi/datos), en dos pasos:

  agregar(tablas)   las 10 tablas chicas del dashboard (powerbi/tablas/*.csv): cada cifra que se ve sale de aquí
  proyecto(chicas)  powerbi/Lulo_Impacto.pbip con los datos DENTRO del modelo (no pide origen ni credenciales),
                    powerbi/medidas.dax y powerbi/tema-lulo-impacto.json

Las páginas (todas con selector de escenario y la etiqueta del prototipo):
  1 Impacto        ¿más clientes compran con las ofertas? diferencia frente al grupo sin ofertas, su intervalo de
                   95 %, clientes nuevos con seguro y comisión adicional
  2 Qué y a quién  qué seguros dejan comisión, qué clientes aceptan y cuánto de lo vendido vino de una oferta
  3 Bajo control   reglas que el motor nunca rompe (backtest) y si aprende (laboratorio)

Los textos que llevan cifras (subtítulos y notas al pie) se escriben con los mismos datos, nunca a mano.
"""

from __future__ import annotations

import base64
import csv
import io
import json
import re
import uuid
import zlib

from lulo_app.core import rules

NS = uuid.UUID("3b8e0f6a-6c2d-4e57-9a0b-5d1c7e2f4a91")
ETIQUETA = "Prototipo académico · base sintética · resultados simulados"

# Colores de la app (public/static/v3/app.css). Lima = el motor y lo que se quiere mirar; gris azulado = la
# comparación (sin ofertas, la regla). Es foco y contexto, no una paleta de categorías.
COLOR = {"pagina": "#0B1430", "tarjeta": "#131E3D", "linea": "#1E2B50", "texto": "#FFFFFF", "texto_2": "#AFB8CC",
         "texto_3": "#92A0BD", "lima": "#E8FF00", "gris": "#647B9A", "verde": "#62E3A0", "azul": "#3987E5",
         "naranja": "#FFB547", "morado": "#9085E9", "mal": "#EA6E66"}
SERIES = [COLOR[k] for k in ("lima", "gris", "verde", "azul", "naranja", "morado")]

# Nombres que se ven en el selector. Un escenario que no esté aquí (por ejemplo «real») usa el de dim_escenario.
NOMBRE_ESCENARIO = {"señal": "Optimista: el motor ve más que la regla",
                    "regla correcta": "Conservador: la regla ya era la correcta"}
SEGMENTOS = ["Con mascota", "Gasto contenido", "Gasta lo que entra"]
ORIGEN = (("oferta", "Oferta del motor"), ("por su cuenta", "Por su cuenta"))
LAB_POLITICAS = 4          # politica_orden 1 a 4: motor, regla, oráculo y al azar (las demás son variantes del motor)


# ------------------------------------------------------------------ 1 · tablas del dashboard
def _leer(texto: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(texto)))


def _num(v: float, d: int = 5) -> str:
    if isinstance(v, int):
        return str(v)
    s = f"{v:.{d}f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _csv(cols: list[str], filas: list[dict]) -> str:
    out = io.StringIO()
    w = csv.writer(out, lineterminator="\n")
    w.writerow(cols)
    for f in filas:
        w.writerow([_num(f[c]) if isinstance(f[c], (int, float)) else f[c] for c in cols])
    return out.getvalue()


def agregar(tablas: dict[str, str]) -> tuple[dict[str, str], dict]:
    """De las tablas de detalle (powerbi/datos) a las 10 tablas del dashboard y los números de sus textos."""
    T = {n[:-4]: _leer(t) for n, t in tablas.items()}
    cli_dim = {r["cliente_id"]: r for r in T["dim_cliente"]}
    esc_dim = sorted(T["dim_escenario"], key=lambda r: int(r["orden"]))
    escenarios = [r["escenario"] for r in esc_dim]
    vista = ("aceptada", "rechazada")

    escenario, indicadores, curva, ramo, segmento, origen = [], [], [], [], [], []
    controles = set()
    for i, e in enumerate(esc_dim, 1):
        k = e["escenario"]
        escenario.append({"escenario": k, "nombre": NOMBRE_ESCENARIO.get(k, e["nombre"]), "orden": i})
        cli = [r for r in T["piloto_clientes"] if r["escenario"] == k]
        dec = [r for r in T["piloto_decisiones"] if r["escenario"] == k]
        ven = [r for r in T["piloto_ventas"] if r["escenario"] == k]
        grupo = {g: [r for r in cli if r["grupo"] == g] for g in ("tratamiento", "control")}
        indicadores.append({
            "escenario": k,
            "clientes_trat": len(grupo["tratamiento"]), "clientes_ctrl": len(grupo["control"]),
            "compran_trat": sum(r["compro"] == "1" for r in grupo["tratamiento"]),
            "compran_ctrl": sum(r["compro"] == "1" for r in grupo["control"]),
            "comision_trat": sum(int(r["comision_12m_cop"]) for r in grupo["tratamiento"]),
            "comision_ctrl": sum(int(r["comision_12m_cop"]) for r in grupo["control"]),
            "ofertas_mostradas": sum(r["canal"] != "ninguno" for r in dec),
            "ofertas_vistas": sum(r["resultado"] in vista for r in dec),
            "ofertas_aceptadas": sum(r["resultado"] == "aceptada" for r in dec),
            "ventas": len(ven), "ventas_oferta": sum(r["origen"] == "oferta" for r in ven)})
        controles.add(tuple(sorted((r["cliente_id"], r["compro"]) for r in grupo["control"])))
        # Clientes que ya compraron a cada fecha de evaluación del piloto, sobre los clientes de su grupo.
        for semana in sorted({r["fecha"] for r in dec}):
            for orden, (g, nombre) in enumerate((("tratamiento", "Con ofertas"), ("control", "Sin ofertas")), 1):
                ids = {r["cliente_id"] for r in grupo[g]}
                n = len({r["cliente_id"] for r in ven if r["cliente_id"] in ids and r["fecha"] <= semana})
                curva.append({"escenario": k, "semana": semana, "grupo": nombre, "grupo_orden": orden,
                              "conversion": round(n / len(ids), 5) if ids else 0.0})
        for r in sorted(T["dim_ramo"], key=lambda r: int(r["orden"])):
            d = [x for x in dec if x["ramo"] == r["ramo"]]
            v = [x for x in ven if x["ramo"] == r["ramo"] and x["origen"] == "oferta"]
            ramo.append({"escenario": k, "seguro": r["ramo"], "orden": int(r["orden"]),
                         "vistas": sum(x["resultado"] in vista for x in d),
                         "aceptadas": sum(x["resultado"] == "aceptada" for x in d), "ventas_oferta": len(v),
                         "comision_oferta": sum(int(x["comision_12m_cop"]) for x in v),
                         "comision_por_venta": int(r["comision_12m_cop"])})
        nombres = SEGMENTOS + sorted({c["segmento_motor"] for c in cli_dim.values()} - set(SEGMENTOS) - {""})
        for orden, s in enumerate(nombres, 1):
            d = [x for x in dec if cli_dim[x["cliente_id"]]["segmento_motor"] == s]
            segmento.append({"escenario": k, "segmento": s, "orden": orden,
                             "vistas": sum(x["resultado"] in vista for x in d),
                             "aceptadas": sum(x["resultado"] == "aceptada" for x in d)})
        for orden, (o, nombre) in enumerate(ORIGEN, 1):
            origen.append({"escenario": k, "origen": nombre, "orden": orden,
                           "ventas": sum(x["origen"] == o for x in ven)})
    if len(controles) != 1:
        raise ValueError("El grupo sin ofertas debe ser el mismo en todos los escenarios (sorteos comunes).")

    laboratorio = [{"escenario": r["escenario"], "politica": r["politica_nombre"],
                    "politica_orden": int(r["politica_orden"]), "ronda": int(r["ronda"]),
                    "comision_por_oferta": float(r["comision_por_oferta"])}
                   for r in T["lab_series"] if r["escenario"] in escenarios and int(r["politica_orden"]) <= LAB_POLITICAS]
    lab_resumen = [{"escenario": r["escenario"], "motor_frente_a_regla": float(r["motor_frente_a_regla"])}
                   for r in T["lab_resumen"] if r["escenario"] in escenarios]
    reglas = [{"regla": r["invariante"], "violaciones": int(r["violaciones"])} for r in T["motor_invariantes"]]
    bt = {r["metrica"]: r["valor"] for r in T["motor_backtest"]}
    topes = {int(c["max_contactos_mes"]) for c in cli_dim.values()}
    control = [{"indicador": "evaluaciones", "valor": int(bt["evaluaciones"])},
               {"indicador": "push_max_30d", "valor": int(bt["max_push_30d"])},
               {"indicador": "sin_autorizacion", "valor": sum(c["autoriza_ofertas"] == "No" for c in cli_dim.values())},
               {"indicador": "tope_contactos_30d", "valor": max(topes)}]

    mascota = [c for c in cli_dim.values() if c["segmento_motor"] == "Con mascota"]
    ind0 = indicadores[0]
    notas = {
        "clientes": len(cli_dim), "semanas": len({r["semana"] for r in curva}),
        "control_clientes": ind0["clientes_ctrl"], "control_compran": ind0["compran_ctrl"],
        "control_pct": rules.CONTROL_PCT,
        "mascota_clientes": len(mascota), "mascota_con_seguro": sum("Mascotas" in c["seguros_lulo"] for c in mascota),
        "evaluaciones": int(bt["evaluaciones"]), "tope": max(topes), "topes_distintos": len(topes),
        "rondas": max(r["ronda"] for r in laboratorio),
    }
    chicas = {
        "escenario": _csv(["escenario", "nombre", "orden"], escenario),
        "indicadores": _csv(list(indicadores[0]), indicadores),
        "curva": _csv(["escenario", "semana", "grupo", "grupo_orden", "conversion"], curva),
        "ramo": _csv(["escenario", "seguro", "orden", "vistas", "aceptadas", "ventas_oferta", "comision_oferta",
                      "comision_por_venta"], ramo),
        "segmento": _csv(["escenario", "segmento", "orden", "vistas", "aceptadas"], segmento),
        "origen": _csv(["escenario", "origen", "orden", "ventas"], origen),
        "laboratorio": _csv(["escenario", "politica", "politica_orden", "ronda", "comision_por_oferta"], laboratorio),
        "laboratorio_resumen": _csv(["escenario", "motor_frente_a_regla"], lab_resumen),
        "reglas": _csv(["regla", "violaciones"], reglas),
        "control": _csv(["indicador", "valor"], control),
    }
    return chicas, notas


def miles(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def textos(n: dict) -> dict[str, str]:
    """Subtítulos y notas al pie, con las cifras de agregar()."""
    pct_m = round(100 * n["mascota_con_seguro"] / n["mascota_clientes"]) if n["mascota_clientes"] else 0
    tope = (f"Tope de contactos de la base: {n['tope']} en 30 días por cliente" if n["topes_distintos"] == 1
            else f"Tope de contactos de la base: hasta {n['tope']} en 30 días según el cliente")
    return {
        "sub_impacto": (f"Simulación de {n['semanas']} semanas: el motor real decide sobre los {n['clientes']} clientes; "
                        f"un {n['control_pct']} % sorteado no recibe ofertas y sirve de comparación"),
        "pie_impacto": (f"Base sintética del reto ({n['clientes']} clientes) y respuestas simuladas con la verdad del "
                        f"laboratorio; no son métricas de Lulo Bank. Muestra chica: el grupo sin ofertas tiene "
                        f"{n['control_clientes']} clientes y {n['control_compran']} compran. Por eso se muestran el "
                        f"intervalo de 95 % y el escenario conservador."),
        "pie_valor": (f"Comisión a 12 meses del catálogo de la base. «Con mascota»: clientes que ahorran para su mascota "
                      f"(solo {n['mascota_con_seguro']} de {n['mascota_clientes']}, el {pct_m} %, tiene el seguro). "
                      f"Resultados simulados sobre la base sintética."),
        "pie_control": (f"Laboratorio: verdad simulada sobre los clientes de la base; muestra que el método aprende, no "
                        f"cuánto venderá Lulo. {tope}; el push cuenta como contacto (Ley 2300). Sin autorización de "
                        f"datos no se leen sus movimientos (Ley 1581)."),
        "titulo_reglas": f"Reglas que el motor nunca rompe (backtest de {miles(n['evaluaciones'])} decisiones)",
        "titulo_lab": f"Laboratorio: comisión por oferta en {n['rondas']} rondas de aprendizaje",
    }


# ------------------------------------------------------------------ 2 · medidas
ESC = "VAR e = [Escenario elegido]\nRETURN\n    "


def _suma(tabla: str, col: str) -> str:
    return ESC + f"CALCULATE ( SUM ( {tabla}[{col}] ), {tabla}[escenario] = e )"


# (tabla, nombre, expresión, formato, carpeta, descripción). El nombre es lo que la tarjeta muestra debajo de la cifra.
MEDIDAS = [
    ("escenario", "Escenario elegido",
     "IF (\n    HASONEVALUE ( escenario[escenario] ),\n    VALUES ( escenario[escenario] ),\n"
     "    CALCULATE ( MIN ( escenario[escenario] ), REMOVEFILTERS ( escenario ), escenario[orden] = 1 )\n)",
     None, "1 · Escenario", "El escenario del selector; si no hay uno solo, el primero (optimista)."),
    ("escenario", "Nombre del escenario",
     ESC + "LOOKUPVALUE ( escenario[nombre], escenario[escenario], e )", None, "1 · Escenario", None),

    # Conteos del piloto simulado: todo lo demás sale de estos seis.
    ("indicadores", "Clientes con ofertas", _suma("indicadores", "clientes_trat"), "#,0", "2 · Conteos",
     "Clientes que recibieron decisiones del motor con ofertas (el 90 %)."),
    ("indicadores", "Clientes sin ofertas", _suma("indicadores", "clientes_ctrl"), "#,0", "2 · Conteos",
     "El grupo de comparación: el motor decide pero no muestra (10 % por hash)."),
    ("indicadores", "Compran con ofertas", _suma("indicadores", "compran_trat"), "#,0", "2 · Conteos", None),
    ("indicadores", "Compran sin ofertas", _suma("indicadores", "compran_ctrl"), "#,0", "2 · Conteos",
     "Compran por su cuenta, sin ofertas."),
    ("indicadores", "Comisión con ofertas", _suma("indicadores", "comision_trat"), '"$"#,0', "2 · Conteos",
     "Comisión a 12 meses de lo que compraron los clientes con ofertas."),
    ("indicadores", "Comisión sin ofertas", _suma("indicadores", "comision_ctrl"), '"$"#,0', "2 · Conteos", None),

    ("indicadores", "Conversión con ofertas", "DIVIDE ( [Compran con ofertas], [Clientes con ofertas] )", "0.0 %",
     "3 · Impacto", None),
    ("indicadores", "Conversión sin ofertas", "DIVIDE ( [Compran sin ofertas], [Clientes sin ofertas] )", "0.0 %",
     "3 · Impacto", None),
    ("indicadores", "más clientes compran con las ofertas",
     "( [Conversión con ofertas] - [Conversión sin ofertas] ) * 100", '+0.0 "pp";-0.0 "pp";0.0 "pp"', "3 · Impacto",
     "Diferencia en puntos porcentuales frente al grupo sin ofertas: la cifra que dice si las ofertas venden."),
    ("indicadores", "Error estándar de la diferencia",
     "VAR ct = [Conversión con ofertas]\nVAR cc = [Conversión sin ofertas]\nRETURN\n"
     "    SQRT ( DIVIDE ( ct * ( 1 - ct ), [Clientes con ofertas] ) + DIVIDE ( cc * ( 1 - cc ), [Clientes sin ofertas] ) )",
     "0.0000", "3 · Impacto", None),
    ("indicadores", "Diferencia IC 95 % bajo",
     "[más clientes compran con las ofertas] - 1.96 * [Error estándar de la diferencia] * 100",
     '+0.0 "pp";-0.0 "pp";0.0 "pp"', "3 · Impacto", None),
    ("indicadores", "Diferencia IC 95 % alto",
     "[más clientes compran con las ofertas] + 1.96 * [Error estándar de la diferencia] * 100",
     '+0.0 "pp";-0.0 "pp";0.0 "pp"', "3 · Impacto", None),
    ("indicadores", "intervalo de 95 % de la diferencia",
     'FORMAT ( [Diferencia IC 95 % bajo], "+0.0;-0.0" ) & " a " & FORMAT ( [Diferencia IC 95 % alto], "+0.0;-0.0" ) & " pp"',
     None, "3 · Impacto",
     "Con 95 % de confianza la diferencia real está en este rango. Si no toca el cero, no es azar."),
    ("indicadores", "¿Las ofertas venden?",
     "SWITCH (\n    TRUE (),\n    [Clientes sin ofertas] = 0, \"Sin grupo sin ofertas no se puede saber\",\n"
     "    [Diferencia IC 95 % bajo] > 0, \"Sí: con ofertas compran más clientes\",\n"
     "    [Diferencia IC 95 % alto] < 0, \"No: con ofertas compran menos\",\n"
     "    \"Todavía no se sabe: cabe en el azar\"\n)",
     None, "3 · Impacto", "Lectura del intervalo de 95 %."),
    ("indicadores", "clientes nuevos con seguro gracias a las ofertas",
     "( [Conversión con ofertas] - [Conversión sin ofertas] ) * [Clientes con ofertas]", "#,0", "3 · Impacto",
     "Ventas incrementales: la diferencia frente al grupo sin ofertas por los clientes con ofertas."),
    ("indicadores", "comisión por cliente contactado",
     "DIVIDE ( [Comisión con ofertas], [Clientes con ofertas] ) - DIVIDE ( [Comisión sin ofertas], [Clientes sin ofertas] )",
     '"$"#,0', "3 · Impacto", "Comisión a 12 meses que se gana de más por cada cliente que recibe ofertas."),
    ("indicadores", "comisión adicional a 12 meses",
     "[comisión por cliente contactado] * [Clientes con ofertas] / 1000000", '"$"#,0.0" M"', "3 · Impacto",
     "En millones de pesos, sobre los clientes de la base sintética que recibieron ofertas."),
    ("indicadores", "por cada 1.000 clientes contactados (proyección lineal)",
     "[comisión por cliente contactado] * 1000 / 1000000", '"$"#,0.0" M"', "3 · Impacto",
     "Ilustrativo, no una meta: la comisión por cliente contactado × 1.000, en millones de pesos."),

    ("indicadores", "pólizas vendidas por las ofertas", _suma("indicadores", "ventas_oferta"), "#,0", "4 · Valor", None),
    ("indicadores", "de las ventas vino de una oferta",
     ESC + "DIVIDE ( [pólizas vendidas por las ofertas], CALCULATE ( SUM ( indicadores[ventas] ), indicadores[escenario] = e ) )",
     "0.0 %", "4 · Valor", "Incluye las compras por su cuenta de los dos grupos."),
    ("indicadores", "aceptan la oferta que ven",
     ESC + "DIVIDE (\n        CALCULATE ( SUM ( indicadores[ofertas_aceptadas] ), indicadores[escenario] = e ),\n"
     "        CALCULATE ( SUM ( indicadores[ofertas_vistas] ), indicadores[escenario] = e )\n    )",
     "0.0 %", "4 · Valor", "Aceptadas sobre vistas: comparable con ventas / impactados de las campañas previas."),
    ("curva", "Clientes que ya compraron", _suma("curva", "conversion"), "0.0 %", "4 · Valor",
     "Clientes que ya compraron un seguro a esa semana, sobre los clientes de su grupo."),
    ("ramo", "Comisión de las ofertas", ESC + "CALCULATE ( SUM ( ramo[comision_oferta] ), ramo[escenario] = e ) / 1000000",
     '"$"#,0.0" M"', "4 · Valor", "Comisión a 12 meses de las pólizas vendidas por las ofertas, en millones."),
    ("segmento", "Aceptación por segmento",
     ESC + "DIVIDE (\n        CALCULATE ( SUM ( segmento[aceptadas] ), segmento[escenario] = e ),\n"
     "        CALCULATE ( SUM ( segmento[vistas] ), segmento[escenario] = e )\n    )", "0.0 %", "4 · Valor", None),
    ("origen", "Pólizas", _suma("origen", "ventas"), "#,0", "4 · Valor", None),

    ("reglas", "violaciones de las reglas", "SUM ( reglas[violaciones] ) + 0", "#,0", "5 · Control",
     "Debe ser 0: backtest de todas las decisiones del motor sobre la base."),
    ("control", "push máximo a un cliente en 30 días",
     'LOOKUPVALUE ( control[valor], control[indicador], "push_max_30d" )', "#,0", "5 · Control", None),
    ("control", "clientes sin autorización: nunca contactados",
     'LOOKUPVALUE ( control[valor], control[indicador], "sin_autorizacion" )', "#,0", "5 · Control",
     "Ley 1581: sin autorización el motor no lee sus movimientos ni les ofrece nada."),
    ("laboratorio_resumen", "más comisión por oferta que la regla (laboratorio)",
     ESC + "CALCULATE ( SUM ( laboratorio_resumen[motor_frente_a_regla] ), laboratorio_resumen[escenario] = e )",
     "+0.0 %;-0.0 %;0.0 %", "5 · Control", "Laboratorio: últimas 10 rondas, con verdad simulada."),
    ("laboratorio", "Comisión por oferta",
     ESC + "CALCULATE ( AVERAGE ( laboratorio[comision_por_oferta] ), laboratorio[escenario] = e )", '"$"#,0',
     "5 · Control", None),
]
# DAX no deja una medida dentro de un filtro booleano de CALCULATE: el escenario se lee antes en la variable «e».


# ------------------------------------------------------------------ 3 · modelo semántico
def tag(*parts) -> str:
    return str(uuid.uuid5(NS, "|".join(parts)))


def tipos(texto_csv: str) -> dict[str, str]:
    """Tipo de cada columna según sus valores: entero, decimal, fecha ISO o texto."""
    rows = list(csv.reader(io.StringIO(texto_csv)))
    cols, vals = rows[0], rows[1:]
    out = {}
    for i, c in enumerate(cols):
        v = [r[i] for r in vals if i < len(r) and r[i] != ""]
        if v and all(re.fullmatch(r"-?\d+", x) for x in v):
            out[c] = "int64"
        elif v and all(re.fullmatch(r"-?\d+(\.\d+)?", x) for x in v):
            out[c] = "double"
        elif v and all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", x) for x in v):
            out[c] = "dateTime"
        else:
            out[c] = "string"
    return out


M_TIPO = {"int64": "Int64.Type", "double": "type number", "dateTime": "type date", "string": "type text"}
FORMATO = {("curva", "semana"): "d mmm yyyy", ("curva", "conversion"): "0.0 %",
           ("laboratorio", "comision_por_oferta"): '"$"#,0', ("laboratorio_resumen", "motor_frente_a_regla"): "0.0 %"}
ORDENAR_POR = {("escenario", "nombre"): "orden", ("curva", "grupo"): "grupo_orden", ("ramo", "seguro"): "orden",
               ("segmento", "segmento"): "orden", ("origen", "origen"): "orden",
               ("laboratorio", "politica"): "politica_orden"}
OCULTAS = {"escenario", "orden", "grupo_orden", "politica_orden"}


def datos_m(texto_csv: str, cols: dict[str, str]) -> list[str]:
    """La tabla dentro del modelo, como «Escribir datos» de Power BI: filas en JSON, comprimidas y en base64."""
    rows = list(csv.reader(io.StringIO(texto_csv)))[1:]
    z = zlib.compressobj(9, zlib.DEFLATED, -15)
    crudo = z.compress(json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode("utf-8")) + z.flush()
    b64 = base64.b64encode(crudo).decode("ascii")
    tipo = ", ".join(f"{c} = _t" for c in cols)
    conv = ", ".join(f'{{"{c}", {M_TIPO[k]}}}' for c, k in cols.items())
    return ["let",
            f'    Fuente = Table.FromRows(Json.Document(Binary.Decompress(Binary.FromText("{b64}", BinaryEncoding.Base64), '
            f'Compression.Deflate)), let _t = ((type nullable text) meta [Serialized.Text = true]) in type table [{tipo}]),',
            f'    Tipos = Table.TransformColumnTypes(Fuente, {{{conv}}}, "en-US")',
            "in", "    Tipos"]


def model_bim(chicas: dict[str, str]) -> str:
    por_tabla: dict[str, list] = {}
    for t, n, e, f, carpeta, d in MEDIDAS:
        m = {"name": n, "expression": e.split("\n") if "\n" in e else e, "lineageTag": tag("m", t, n),
             "displayFolder": carpeta}
        if f:
            m["formatString"] = f
        if d:
            m["description"] = d
        por_tabla.setdefault(t, []).append(m)
    tablas = []
    for nombre, texto in chicas.items():
        cols = tipos(texto)
        cdefs = []
        for c, dt in cols.items():
            cd = {"name": c, "dataType": dt, "sourceColumn": c, "lineageTag": tag("c", nombre, c),
                  "summarizeBy": "none", "annotations": [{"name": "SummarizationSetBy", "value": "Automatic"}]}
            if (nombre, c) in FORMATO:
                cd["formatString"] = FORMATO[(nombre, c)]
            if (nombre, c) in ORDENAR_POR:
                cd["sortByColumn"] = ORDENAR_POR[(nombre, c)]
            if c in OCULTAS:
                cd["isHidden"] = True
            cdefs.append(cd)
        t = {"name": nombre, "lineageTag": tag("t", nombre), "columns": cdefs,
             "partitions": [{"name": nombre, "mode": "import", "source": {"type": "m", "expression": datos_m(texto, cols)}}]}
        if nombre in por_tabla:
            t["measures"] = por_tabla[nombre]
        tablas.append(t)
    model = {
        "name": "Lulo_Impacto", "compatibilityLevel": 1567,
        "model": {
            "culture": "es-CO", "sourceQueryCulture": "es-CO", "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": True},
            "tables": tablas,
            "annotations": [{"name": "__PBI_TimeIntelligenceEnabled", "value": "0"},
                            {"name": "PBI_QueryOrder", "value": json.dumps(list(chicas), ensure_ascii=False)}],
        },
    }
    return json.dumps(model, ensure_ascii=False, indent=2) + "\n"


def medidas_dax() -> str:
    out = ["// Medidas del dashboard de impacto (las genera scripts/exportar_powerbi.py; no se editan a mano).",
           "// Ya vienen en Lulo_Impacto.SemanticModel/model.bim. Para crearlas a mano: Modelado → Nueva medida, en la",
           "// tabla indicada, y pegar desde el nombre. Las del piloto filtran el escenario elegido; no hacen falta relaciones.",
           ""]
    carpeta = None
    for t, n, e, f, c, d in MEDIDAS:
        if c != carpeta:
            out += ["", f"// ===== {c} " + "=" * max(0, 70 - len(c)), ""]
            carpeta = c
        if d:
            out.append(f"// {d}")
        out.append(f"// Tabla: {t}" + (f" · Formato: {f}" if f else ""))
        out.append(f"[{n}] =")
        out += ["    " + x for x in e.split("\n")]
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def tema() -> str:
    C = COLOR
    fill = lambda c: {"solid": {"color": c}}  # noqa: E731
    t = {
        "name": "Lulo impacto", "dataColors": SERIES, "background": C["pagina"], "foreground": C["texto"],
        "tableAccent": C["lima"], "good": C["verde"], "neutral": C["naranja"], "bad": C["mal"],
        "textClasses": {
            "callout": {"fontSize": 36, "fontFace": "Segoe UI Semibold", "color": C["texto"]},
            "title": {"fontSize": 12, "fontFace": "Segoe UI Semibold", "color": C["texto"]},
            "header": {"fontSize": 12, "fontFace": "Segoe UI Semibold", "color": C["texto"]},
            "label": {"fontSize": 10, "fontFace": "Segoe UI", "color": C["texto_2"]},
        },
        "visualStyles": {
            "*": {"*": {
                "background": [{"show": True, "color": fill(C["tarjeta"]), "transparency": 0}],
                "border": [{"show": False}],
                "title": [{"show": True, "fontColor": fill(C["texto"]), "fontSize": 12}],
                "categoryAxis": [{"labelColor": fill(C["texto_2"]), "gridlineColor": fill(C["linea"])}],
                "valueAxis": [{"labelColor": fill(C["texto_2"]), "gridlineColor": fill(C["linea"]), "gridlineStyle": "solid"}],
                "legend": [{"labelColor": fill(C["texto_2"])}],
                "labels": [{"color": fill(C["texto"])}],
                "dropShadow": [{"show": False}],
            }},
            "page": {"*": {"background": [{"color": fill(C["pagina"]), "transparency": 0}],
                           "outspace": [{"color": fill(C["pagina"]), "transparency": 0}]}},
            "tableEx": {"*": {"columnHeaders": [{"fontColor": fill(C["texto"]), "backColor": fill(C["linea"])}],
                              "values": [{"fontColorPrimary": fill(C["texto"]), "backColorPrimary": fill(C["tarjeta"]),
                                          "fontColorSecondary": fill(C["texto"]), "backColorSecondary": fill("#18244A")}]}},
            "slicer": {"*": {"items": [{"fontColor": fill(C["texto"]), "background": fill(C["linea"])}],
                             "header": [{"show": False}]}},
        },
    }
    return json.dumps(t, ensure_ascii=False, indent=2) + "\n"


# ------------------------------------------------------------------ 4 · páginas
def paginas(tx: dict[str, str]) -> list[tuple]:
    """(nombre de la pestaña, título, subtítulo, visuales). Visual: (tipo, x, y, ancho, alto, título, campos)."""
    fila = [24, 336, 648, 960]
    encabezado_y, tarjetas_y, cuerpo_y, cuerpo_h = 86, 138, 282, 372
    sel = ("segmentacion", 24, encabezado_y, 1232, 40, None, ["escenario[nombre]"])
    return [
        ("Impacto", "Lo que el motor puede generar", tx["sub_impacto"], [
            sel,
            ("tarjeta_lima", fila[0], tarjetas_y, 296, 128, None, ["indicadores.[más clientes compran con las ofertas]"]),
            ("tarjeta_chica", fila[1], tarjetas_y, 296, 128, None, ["indicadores.[intervalo de 95 % de la diferencia]"]),
            ("tarjeta", fila[2], tarjetas_y, 296, 128, None, ["indicadores.[clientes nuevos con seguro gracias a las ofertas]"]),
            ("tarjeta", fila[3], tarjetas_y, 296, 128, None, ["indicadores.[comisión adicional a 12 meses]"]),
            ("lineas", 24, cuerpo_y, 800, cuerpo_h, "Clientes que ya compraron un seguro, semana a semana",
             ("curva[semana]", ["curva.[Clientes que ya compraron]"], "curva[grupo]")),
            ("tarjeta_texto", 840, cuerpo_y, 416, 116, None, ["indicadores.[¿Las ofertas venden?]"]),
            ("tarjeta_blanca", 840, cuerpo_y + 128, 416, 116, None, ["indicadores.[comisión por cliente contactado]"]),
            ("tarjeta_blanca", 840, cuerpo_y + 256, 416, 116, None,
             ["indicadores.[por cada 1.000 clientes contactados (proyección lineal)]"]),
            ("pie", 24, 664, 1232, 48, None, tx["pie_impacto"]),
        ]),
        ("Qué y a quién", "Dónde está el valor", "Qué seguros venden, a qué clientes y cuánto viene de las ofertas", [
            sel,
            ("tarjeta", fila[0], tarjetas_y, 296, 128, None, ["indicadores.[pólizas vendidas por las ofertas]"]),
            ("tarjeta", fila[1], tarjetas_y, 296, 128, None, ["indicadores.[de las ventas vino de una oferta]"]),
            ("tarjeta", fila[2], tarjetas_y, 296, 128, None, ["indicadores.[aceptan la oferta que ven]"]),
            ("tarjeta", fila[3], tarjetas_y, 296, 128, None, ["indicadores.[comisión por cliente contactado]"]),
            ("barras", 24, cuerpo_y, 610, cuerpo_h,
             "Comisión a 12 meses de las pólizas vendidas por las ofertas, por seguro",
             ("ramo[seguro]", ["ramo.[Comisión de las ofertas]"], None)),
            ("columnas", 650, cuerpo_y, 300, cuerpo_h, "Aceptan la oferta, por tipo de cliente",
             ("segmento[segmento]", ["segmento.[Aceptación por segmento]"], None)),
            ("dona", 966, cuerpo_y, 290, cuerpo_h, "Cómo se vendieron las pólizas",
             ("origen[origen]", ["origen.[Pólizas]"], None)),
            ("pie", 24, 664, 1232, 48, None, tx["pie_valor"]),
        ]),
        ("Bajo control", "Crece sin cansar al cliente ni romper reglas",
         "Lo que el motor nunca hace y por qué se puede confiar en que aprende", [
            sel,
            ("tarjeta_lima", fila[0], tarjetas_y, 296, 128, None, ["reglas.[violaciones de las reglas]"]),
            ("tarjeta", fila[1], tarjetas_y, 296, 128, None, ["control.[push máximo a un cliente en 30 días]"]),
            ("tarjeta", fila[2], tarjetas_y, 296, 128, None, ["control.[clientes sin autorización: nunca contactados]"]),
            ("tarjeta", fila[3], tarjetas_y, 296, 128, None,
             ["laboratorio_resumen.[más comisión por oferta que la regla (laboratorio)]"]),
            ("tabla", 24, cuerpo_y, 520, cuerpo_h, tx["titulo_reglas"], ["reglas[regla]", "reglas[violaciones]"]),
            ("lineas", 560, cuerpo_y, 696, cuerpo_h, tx["titulo_lab"],
             ("laboratorio[ronda]", ["laboratorio.[Comisión por oferta]"], "laboratorio[politica]")),
            ("pie", 24, 664, 1232, 48, None, tx["pie_control"]),
        ]),
    ]


def _lit(v) -> dict:
    if isinstance(v, bool):
        return {"expr": {"Literal": {"Value": "true" if v else "false"}}}
    if isinstance(v, (int, float)):
        return {"expr": {"Literal": {"Value": f"{v}D"}}}
    return {"expr": {"Literal": {"Value": "'" + str(v).replace("'", "''") + "'"}}}


def _color(c: str) -> dict:
    return {"solid": {"color": _lit(c)}}


def _campo(ref: str, alias: dict) -> tuple[dict, str]:
    """«tabla[col]» o «tabla.[medida]» → (Select del prototypeQuery, queryRef)."""
    m = re.fullmatch(r"(\w+)\.\[(.+)\]", ref)
    if m:
        t, n, medida = m.group(1), m.group(2), True
    else:
        m = re.fullmatch(r"(\w+)\[(.+)\]", ref)
        t, n, medida = m.group(1), m.group(2), False
    a = alias.setdefault(t, f"t{len(alias)}")
    q = f"{t}.{n}"
    expr = {"Expression": {"SourceRef": {"Source": a}}, "Property": n}
    return {("Measure" if medida else "Column"): expr, "Name": q}, q


def _texto(parrafos: list[tuple[str, str, str, bool]]) -> dict:
    return {"visualType": "textbox", "drillFilterOtherVisuals": True,
            "objects": {"general": [{"properties": {"paragraphs": [
                {"textRuns": [{"value": v, "textStyle": {"fontSize": tam, "color": col, **({"fontWeight": "bold"} if b else {})}}]}
                for v, tam, col, b in parrafos]}}]}}


def _visual(pag: int, i: int, v: tuple) -> dict:
    tipo, x, y, w, h, titulo, campos = v
    nombre = tag("v", str(pag), str(i))[:20].replace("-", "")
    vc: dict = {"title": [{"properties": {"show": _lit(bool(titulo)), **({"text": _lit(titulo), "fontColor": _color(COLOR["texto"]),
                                                                              "fontSize": _lit(12)} if titulo else {})}}]}
    if tipo in ("titulo", "etiqueta", "pie"):
        sv = _texto(campos)
        vc = {"background": [{"properties": {"show": _lit(False)}}]}
    else:
        alias: dict[str, str] = {}
        if tipo.startswith("tarjeta") or tipo in ("segmentacion", "tabla"):
            sels = [_campo(r, alias) for r in campos]
            proj = {"Values": [{"queryRef": q} for _, q in sels]}
        else:
            cat, vals, serie = campos
            sc = _campo(cat, alias)
            sv_ = [_campo(r, alias) for r in vals]
            sels = [sc, *sv_]
            proj = {"Category": [{"queryRef": sc[1], "active": True}], "Y": [{"queryRef": q} for _, q in sv_]}
            if serie:
                ss = _campo(serie, alias)
                sels.append(ss)
                proj["Series"] = [{"queryRef": ss[1]}]
        vt = {"tarjeta": "card", "tarjeta_lima": "card", "tarjeta_chica": "card", "tarjeta_texto": "card",
              "tarjeta_blanca": "card", "segmentacion": "slicer", "tabla": "tableEx", "lineas": "lineChart", "columnas": "clusteredColumnChart",
              "barras": "clusteredBarChart", "dona": "donutChart"}[tipo]
        sv = {"visualType": vt, "projections": proj,
              "prototypeQuery": {"Version": 2, "From": [{"Name": a, "Entity": t, "Type": 0} for t, a in alias.items()],
                                 "Select": [s for s, _ in sels]},
              "drillFilterOtherVisuals": True}
        o: dict = {}
        if tipo == "segmentacion":
            o = {"data": [{"properties": {"mode": _lit("Basic")}}],
                 "general": [{"properties": {"orientation": {"expr": {"Literal": {"Value": "1D"}}}}}],
                 "header": [{"properties": {"show": _lit(False)}}],
                 "items": [{"properties": {"fontColor": _color(COLOR["texto"]), "background": _color(COLOR["linea"]),
                                           "textSize": _lit(11)}}]}
        elif tipo.startswith("tarjeta"):
            fondo, cifra, etiqueta, tam = {
                "tarjeta_lima": (COLOR["lima"], COLOR["pagina"], COLOR["pagina"], 40),
                "tarjeta": (COLOR["tarjeta"], COLOR["lima"], COLOR["texto"], 36),
                "tarjeta_chica": (COLOR["tarjeta"], COLOR["lima"], COLOR["texto"], 22),
                "tarjeta_texto": (COLOR["tarjeta"], COLOR["texto"], COLOR["texto_2"], 16),
                "tarjeta_blanca": (COLOR["tarjeta"], COLOR["texto"], COLOR["texto_2"], 28)}[tipo]
            o = {"labels": [{"properties": {"color": _color(cifra), "fontSize": _lit(tam)}}],
                 "categoryLabels": [{"properties": {"show": _lit(True), "color": _color(etiqueta), "fontSize": _lit(12)}}]}
            if tipo == "tarjeta_texto":
                o["wordWrap"] = [{"properties": {"show": _lit(True)}}]
            vc["background"] = [{"properties": {"show": _lit(True), "color": _color(fondo), "transparency": _lit(0)}}]
        elif tipo in ("lineas", "barras", "columnas", "dona"):
            o = {"legend": [{"properties": {"show": _lit(tipo in ("lineas", "dona")), "position": _lit("Top")}}],
                 "labels": [{"properties": {"show": _lit(tipo != "lineas"), "color": _color(COLOR["texto"]),
                                            "fontSize": _lit(10)}}]}
            if tipo == "lineas":
                o["lineStyles"] = [{"properties": {"strokeWidth": _lit(3)}}]
                o["valueAxis"] = [{"properties": {"show": _lit(True), "gridlineShow": _lit(True)}}]
            elif tipo != "dona":
                o["valueAxis"] = [{"properties": {"show": _lit(False), "gridlineShow": _lit(False)}}]
        if o:
            sv["objects"] = o
    sv["vcObjects"] = vc
    config = {"name": nombre, "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": i, "width": w, "height": h}}],
              "singleVisual": sv}
    return {"x": x, "y": y, "z": i, "width": w, "height": h, "config": json.dumps(config, ensure_ascii=False),
            "filters": "[]"}


def report_json(tx: dict[str, str]) -> str:
    secciones = []
    for p, (pestana, titulo, subtitulo, visuales) in enumerate(paginas(tx)):
        vs = [("titulo", 24, 10, 900, 70, None, [(titulo, "22pt", COLOR["texto"], True),
                                                   (subtitulo, "11pt", COLOR["texto_3"], False)]),
              ("etiqueta", 856, 16, 400, 30, None, [(ETIQUETA, "9pt", COLOR["lima"], False)])]
        for v in visuales:
            if v[0] == "pie":
                v = (*v[:6], [(v[6], "9pt", COLOR["texto_3"], False)])
            vs.append(v)
        secciones.append({"name": "Seccion" + tag("p", str(p))[:12].replace("-", ""), "displayName": pestana,
                          "displayOption": 1, "width": 1280, "height": 720, "ordinal": p, "filters": "[]",
                          "config": "{}", "visualContainers": [_visual(p, i, v) for i, v in enumerate(vs)]})
    config = {"version": "5.43", "themeCollection": {"customTheme": {"name": "tema-lulo-impacto.json", "version": "5.43", "type": 1}},
              "activeSectionIndex": 0, "defaultDrillFilterOtherVisuals": True,
              "settings": {"useNewFilterPaneExperience": True, "allowChangeFilterTypes": True, "useStylableVisualContainerHeader": True}}
    rep = {"config": json.dumps(config, ensure_ascii=False), "layoutOptimization": 0,
           "resourcePackages": [{"resourcePackage": {"name": "RegisteredResources", "type": 1, "disabled": False,
                                                     "items": [{"name": "tema-lulo-impacto.json", "path": "tema-lulo-impacto.json",
                                                                "type": 202}]}}],
           "sections": secciones}
    return json.dumps(rep, ensure_ascii=False, indent=2) + "\n"


def proyecto(chicas: dict[str, str], notas: dict) -> dict[str, str]:
    """Archivos del dashboard, por ruta relativa a powerbi/."""
    th = tema()
    tx = textos(notas)
    return {
        **{f"tablas/{n}.csv": t for n, t in chicas.items()},
        "Lulo_Impacto.pbip": json.dumps({"version": "1.0", "artifacts": [{"report": {"path": "Lulo_Impacto.Report"}}],
                                         "settings": {"enableAutoRecovery": True}}, indent=2) + "\n",
        "Lulo_Impacto.SemanticModel/definition.pbism": json.dumps({"version": "1.0", "settings": {}}, indent=2) + "\n",
        "Lulo_Impacto.SemanticModel/model.bim": model_bim(chicas),
        "Lulo_Impacto.Report/definition.pbir": json.dumps({"version": "1.0", "datasetReference": {
            "byPath": {"path": "../Lulo_Impacto.SemanticModel"}, "byConnection": None}}, indent=2) + "\n",
        "Lulo_Impacto.Report/report.json": report_json(tx),
        "Lulo_Impacto.Report/StaticResources/RegisteredResources/tema-lulo-impacto.json": th,
        "tema-lulo-impacto.json": th,
        "medidas.dax": medidas_dax(),
    }
