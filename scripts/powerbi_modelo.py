"""Proyecto de Power BI (PBIP) del dashboard: modelo semántico, medidas DAX, páginas y tema Lulo.

Lo genera scripts/exportar_powerbi.py junto con los CSV, para que el modelo y los datos no se separen nunca:
los tipos de cada columna salen de los mismos CSV y `--check` verifica todo.

  powerbi/Lulo.pbip                         abre el proyecto en Power BI Desktop
  powerbi/Lulo.SemanticModel/model.bim      tablas, relaciones, medidas y el parámetro «Origen»
  powerbi/Lulo.Report/report.json           las páginas y sus visuales
  powerbi/medidas.dax                       las mismas medidas, para leerlas o pegarlas a mano
  powerbi/tema-lulo.json                    colores de la app (public/static/v3/app.css), validados para gráficos

El parámetro «Origen» dice de dónde leer los CSV: por defecto la carpeta powerbi/datos de la rama main en GitHub
(el repositorio es público), o una carpeta local terminada en «\\».
"""

from __future__ import annotations

import csv
import io
import json
import re
import uuid

REPO_RAW = "https://raw.githubusercontent.com/soka-js/Prototipo-IIND/main/powerbi/datos/"
NS = uuid.UUID("6f1c3a52-0b7e-4f0a-9d7e-1a2b3c4d5e6f")

# Colores: tokens de public/static/v3/app.css. Las series pasan el validador de la guía de visualización
# (modo oscuro sobre #131E3D: banda de luminosidad, croma, separación para daltonismo y contraste).
COLOR = {
    "pagina": "#0B1430", "tarjeta": "#131E3D", "linea": "#1E2B50", "texto": "#FFFFFF", "texto_2": "#AFB8CC",
    "texto_3": "#92A0BD", "lima": "#E8FF00", "bien": "#62E3A0", "alerta": "#FFB547", "mal": "#EA6E66",
}
# Tramos de P(acepta) del motor para la curva de calibración: lo que predijo frente a lo que pasó.
TRAMOS_P = ((0.06, "menos de 6 %"), (0.08, "6 a 8 %"), (0.10, "8 a 10 %"), (0.13, "10 a 13 %"), (9.0, "13 % o más"))
SERIES = ["#8A9E00", "#3987e5", "#d95926", "#9085e9", "#199e70", "#c98500"]   # motor/tratamiento, regla/control, …

# ------------------------------------------------------------------ tablas
TABLAS = {
    "dim_fecha": "Calendario de la base (1-nov-2025 al corte, 8-oct-2026).",
    "dim_ramo": "Los 6 ramos: prima, comisión, persistencia, conversión de la campaña previa y tamaño del piloto (M6).",
    "dim_cliente": "Los 600 clientes de la base con su grupo del experimento (control o tratamiento, por hash).",
    "dim_escenario": "Mundos del piloto simulado. Con el piloto real se agrega «real» con orden 1.",
    "base_campanas": "Base del reto: las 5 campañas previas (elegibles, impactados, interesados y ventas).",
    "base_seguros_mensual": "Base del reto: pólizas emitidas por mes y ramo.",
    "base_pagos_externos": "Base del reto: pagos de los clientes a otras aseguradoras.",
    "motor_plan": "Lo que el motor ofrecería a cada cliente al corte, con su alcance y lo que se espera vender.",
    "motor_backtest": "Backtest del motor sobre el año: ofertas, push, banner y violaciones.",
    "motor_invariantes": "Las reglas que nunca se rompen y cuántas veces se rompieron (debe ser 0).",
    "piloto_decisiones": "SIMULADO · cada decisión del motor en el piloto (formato de docs/DATOS_REALES.md).",
    "piloto_ventas": "SIMULADO · ventas del piloto: por la oferta o por su cuenta.",
    "piloto_clientes": "SIMULADO · un cliente por fila: grupo, decisiones, ofertas vistas y si compró.",
    "dim_lab_escenario": "Escenarios del laboratorio (scripts/laboratorio.py).",
    "lab_series": "Laboratorio: comisión por oferta de cada política en 40 rondas.",
    "lab_calibracion": "Laboratorio: error entre la probabilidad del motor (o de la regla) y la verdadera.",
    "lab_pesos": "Laboratorio: lo que el motor aprende de cada efecto frente a la verdad sembrada.",
    "lab_resumen": "Laboratorio: resultado final de cada escenario.",
    "lab_apetito": "Laboratorio: dispersión del apetito estimada con Bayes empírico (τ).",
    "casos": "Casos reales de otras empresas con métodos como los del prototipo (docs/CASOS.md).",
    "meta": "Versiones, semilla, hash de la base y avisos.",
}

RELACIONES = [
    ("piloto_decisiones", "cliente_id", "dim_cliente", "cliente_id"),
    ("piloto_ventas", "cliente_id", "dim_cliente", "cliente_id"),
    ("piloto_clientes", "cliente_id", "dim_cliente", "cliente_id"),
    ("motor_plan", "cliente_id", "dim_cliente", "cliente_id"),
    ("base_pagos_externos", "cliente_id", "dim_cliente", "cliente_id"),
    ("piloto_decisiones", "ramo", "dim_ramo", "ramo"),
    ("piloto_ventas", "ramo", "dim_ramo", "ramo"),
    ("motor_plan", "ramo", "dim_ramo", "ramo"),
    ("base_campanas", "ramo", "dim_ramo", "ramo"),
    ("base_seguros_mensual", "ramo", "dim_ramo", "ramo"),
    ("base_pagos_externos", "ramo", "dim_ramo", "ramo"),
    ("piloto_decisiones", "fecha", "dim_fecha", "fecha"),
    ("piloto_ventas", "fecha", "dim_fecha", "fecha"),
    ("base_seguros_mensual", "mes", "dim_fecha", "fecha"),
    ("base_pagos_externos", "fecha", "dim_fecha", "fecha"),
    ("piloto_decisiones", "escenario", "dim_escenario", "escenario"),
    ("piloto_ventas", "escenario", "dim_escenario", "escenario"),
    ("piloto_clientes", "escenario", "dim_escenario", "escenario"),
    ("lab_series", "escenario", "dim_lab_escenario", "escenario"),
    ("lab_calibracion", "escenario", "dim_lab_escenario", "escenario"),
    ("lab_pesos", "escenario", "dim_lab_escenario", "escenario"),
    ("lab_resumen", "escenario", "dim_lab_escenario", "escenario"),
    ("lab_apetito", "escenario", "dim_lab_escenario", "escenario"),
]

ORDENAR_POR = {("dim_fecha", "mes_nombre"): "orden_mes", ("dim_ramo", "ramo"): "orden",
               ("dim_ramo", "titulo"): "orden", ("dim_escenario", "nombre"): "orden",
               ("piloto_decisiones", "tramo_p_motor"): "tramo_orden", ("dim_cliente", "grupo"): "grupo_orden",
               ("lab_series", "politica_nombre"): "politica_orden", ("dim_lab_escenario", "escenario"): "orden"}

# ------------------------------------------------------------------ medidas
# (tabla, nombre, expresión DAX, formato, carpeta, descripción). Las del piloto filtran el escenario elegido
# (por defecto el de orden 1) para que nunca se sumen dos mundos.
PCT, PP, ENT, COP, DEC = "0.0 %", '+0.0 "pp";-0.0 "pp";0.0 "pp"', "#,0", '"$"#,0', "0.000"
ESC = "VAR e = [Escenario elegido]\nRETURN\n    "
LAB = "VAR e = [Escenario del laboratorio]\nRETURN\n    "
VISTAS = 'piloto_decisiones[resultado] IN { "aceptada", "rechazada" }'
TRAT, CTRL = 'dim_cliente[grupo] = "tratamiento"', 'dim_cliente[grupo] = "control"'
MEDIDAS = [
    # 0 · escenario
    ("dim_escenario", "Escenario elegido",
     'IF (\n    HASONEVALUE ( dim_escenario[escenario] ),\n    VALUES ( dim_escenario[escenario] ),\n'
     '    CALCULATE ( LOOKUPVALUE ( dim_escenario[escenario], dim_escenario[orden], 1 ), REMOVEFILTERS ( dim_escenario ) )\n)',
     None, "0 · Escenario", "El escenario de la segmentación; si no hay uno solo, el de orden 1."),
    ("dim_escenario", "Nombre del escenario",
     'VAR e = [Escenario elegido]\nRETURN\n    CALCULATE ( LOOKUPVALUE ( dim_escenario[nombre], dim_escenario[escenario], e ), '
     'REMOVEFILTERS ( dim_escenario ) )', None, "0 · Escenario", ""),
    ("dim_escenario", "Descripción del escenario",
     'VAR e = [Escenario elegido]\nRETURN\n    CALCULATE ( LOOKUPVALUE ( dim_escenario[descripcion], dim_escenario[escenario], e ), '
     'REMOVEFILTERS ( dim_escenario ) )', None, "0 · Escenario", ""),
    # 1 · resultado del piloto (intención de tratar: un cliente por fila)
    ("piloto_clientes", "Clientes en el piloto",
     ESC + "CALCULATE ( COUNTROWS ( piloto_clientes ), dim_escenario[escenario] = e )", ENT, "1 · Resultado del piloto",
     "Clientes con al menos una decisión del motor (oferta o control) en el piloto."),
    ("piloto_clientes", "Clientes que compraron",
     ESC + "CALCULATE ( COUNTROWS ( piloto_clientes ), dim_escenario[escenario] = e, piloto_clientes[compro] = 1 )",
     ENT, "1 · Resultado del piloto", "Compraron al menos un seguro desde su primera decisión (por la oferta o por su cuenta)."),
    ("piloto_clientes", "Conversión por cliente", "DIVIDE ( [Clientes que compraron], [Clientes en el piloto] )", PCT,
     "1 · Resultado del piloto", ""),
    ("piloto_clientes", "Clientes tratamiento", f"CALCULATE ( [Clientes en el piloto], {TRAT} )", ENT,
     "1 · Resultado del piloto", ""),
    ("piloto_clientes", "Clientes control", f"CALCULATE ( [Clientes en el piloto], {CTRL} )", ENT,
     "1 · Resultado del piloto", "El 10 % por hash: el motor decide pero no muestra la oferta."),
    ("piloto_clientes", "Compraron tratamiento", f"CALCULATE ( [Clientes que compraron], {TRAT} )", ENT,
     "1 · Resultado del piloto", ""),
    ("piloto_clientes", "Compraron control", f"CALCULATE ( [Clientes que compraron], {CTRL} )", ENT,
     "1 · Resultado del piloto", ""),
    ("piloto_clientes", "Conversión tratamiento", "DIVIDE ( [Compraron tratamiento], [Clientes tratamiento] )", PCT,
     "1 · Resultado del piloto", ""),
    ("piloto_clientes", "Conversión control", "DIVIDE ( [Compraron control], [Clientes control] )", PCT,
     "1 · Resultado del piloto", "Compran por su cuenta, sin ofertas."),
    ("piloto_clientes", "Diferencia frente al control (pp)",
     "( [Conversión tratamiento] - [Conversión control] ) * 100", PP, "1 · Resultado del piloto",
     "Puntos porcentuales de clientes que compran de más con las ofertas: la cifra que dice si el motor vende."),
    ("piloto_clientes", "Error estándar de la diferencia",
     "VAR pt = [Conversión tratamiento]\nVAR pc = [Conversión control]\nRETURN\n"
     "    SQRT ( DIVIDE ( pt * ( 1 - pt ), [Clientes tratamiento] ) + DIVIDE ( pc * ( 1 - pc ), [Clientes control] ) )",
     "0.0000", "1 · Resultado del piloto", ""),
    ("piloto_clientes", "Diferencia IC 95 % bajo (pp)",
     "[Diferencia frente al control (pp)] - 1.96 * [Error estándar de la diferencia] * 100", PP, "1 · Resultado del piloto", ""),
    ("piloto_clientes", "Diferencia IC 95 % alto (pp)",
     "[Diferencia frente al control (pp)] + 1.96 * [Error estándar de la diferencia] * 100", PP, "1 · Resultado del piloto", ""),
    ("piloto_clientes", "Intervalo de la diferencia",
     'FORMAT ( [Diferencia IC 95 % bajo (pp)], "+0.0;-0.0" ) & " a " & FORMAT ( [Diferencia IC 95 % alto (pp)], "+0.0;-0.0" ) & " pp"',
     None, "1 · Resultado del piloto", "Intervalo de 95 % de la diferencia frente al control."),
    ("piloto_clientes", "Valor p",
     "VAR nt = [Clientes tratamiento]\nVAR nc = [Clientes control]\n"
     "VAR p = DIVIDE ( [Compraron tratamiento] + [Compraron control], nt + nc )\n"
     "VAR se = SQRT ( p * ( 1 - p ) * ( DIVIDE ( 1, nt ) + DIVIDE ( 1, nc ) ) )\n"
     "VAR z = DIVIDE ( [Conversión tratamiento] - [Conversión control], se )\nRETURN\n"
     "    IF ( nt > 0 && nc > 0, 2 * ( 1 - NORM.S.DIST ( ABS ( z ), TRUE ) ) )",
     "0.0000", "1 · Resultado del piloto", "Prueba z de dos proporciones (dos colas)."),
    ("piloto_clientes", "Ventas incrementales",
     "( [Conversión tratamiento] - [Conversión control] ) * [Clientes tratamiento]", ENT, "1 · Resultado del piloto",
     "Clientes que compraron gracias a las ofertas: la diferencia frente al control por el tamaño del tratamiento."),
    ("piloto_clientes", "Comisión por cliente tratamiento",
     ESC + f"DIVIDE ( CALCULATE ( SUM ( piloto_clientes[comision_12m_cop] ), dim_escenario[escenario] = e, {TRAT} ), "
     "[Clientes tratamiento] )", COP, "1 · Resultado del piloto", ""),
    ("piloto_clientes", "Comisión por cliente control",
     ESC + f"DIVIDE ( CALCULATE ( SUM ( piloto_clientes[comision_12m_cop] ), dim_escenario[escenario] = e, {CTRL} ), "
     "[Clientes control] )", COP, "1 · Resultado del piloto", ""),
    ("piloto_clientes", "Comisión incremental 12 m",
     "( [Comisión por cliente tratamiento] - [Comisión por cliente control] ) * [Clientes tratamiento]", COP,
     "1 · Resultado del piloto", "Comisión esperada a 12 meses (catálogo) que se gana de más con las ofertas."),
    ("piloto_clientes", "Efecto mínimo detectable (pp)",
     "VAR p = DIVIDE ( [Compraron tratamiento] + [Compraron control], [Clientes tratamiento] + [Clientes control] )\n"
     "RETURN\n    ( 1.96 + 0.8416 ) * SQRT ( p * ( 1 - p ) * ( DIVIDE ( 1, [Clientes tratamiento] ) + DIVIDE ( 1, [Clientes control] ) ) ) * 100",
     '0.0 "pp"', "1 · Resultado del piloto", "Con estos tamaños, la menor diferencia que se detecta con 95 % de confianza y 80 % de potencia."),
    ("piloto_clientes", "Veredicto",
     'VAR nc = [Clientes control]\nVAR nt = [Clientes tratamiento]\nRETURN\n    SWITCH (\n        TRUE (),\n'
     '        nc = 0 || nt = 0, "Sin grupo de control no se puede saber si las ofertas venden",\n'
     '        [Diferencia IC 95 % bajo (pp)] > 0, "Sí: con las ofertas compran más clientes que sin ellas",\n'
     '        [Diferencia IC 95 % alto (pp)] < 0, "No: con las ofertas compran menos clientes que sin ellas",\n'
     '        "Todavía no se sabe: la diferencia cabe en el azar"\n    )',
     None, "1 · Resultado del piloto", "Lectura del intervalo de 95 % de la diferencia frente al control."),
    ("piloto_clientes", "Lectura de la muestra",
     "VAR xt = [Compraron tratamiento]\nVAR xc = [Compraron control]\n"
     "VAR m = MIN ( MIN ( xt, [Clientes tratamiento] - xt ), MIN ( xc, [Clientes control] - xc ) )\nRETURN\n"
     '    IF ( m < 5, "Muestra chica: con menos de 5 casos en un grupo la lectura es frágil. El piloto real necesita '
     'la base completa de Lulo (M6).", "Muestra suficiente para la prueba de dos proporciones." )',
     None, "1 · Resultado del piloto", ""),
    # 2 · ofertas del piloto
    ("piloto_decisiones", "Decisiones",
     ESC + "CALCULATE ( COUNTROWS ( piloto_decisiones ), dim_escenario[escenario] = e )", ENT, "2 · Ofertas", ""),
    ("piloto_decisiones", "Ofertas mostradas",
     'CALCULATE ( [Decisiones], piloto_decisiones[canal] <> "ninguno" )', ENT, "2 · Ofertas", "Push o banner al tratamiento."),
    ("piloto_decisiones", "Ofertas vistas", f"CALCULATE ( [Decisiones], {VISTAS} )", ENT, "2 · Ofertas",
     "El cliente vio la oferta (aceptó o rechazó)."),
    ("piloto_decisiones", "Ofertas aceptadas", 'CALCULATE ( [Decisiones], piloto_decisiones[resultado] = "aceptada" )', ENT,
     "2 · Ofertas", ""),
    ("piloto_decisiones", "Ofertas ignoradas", 'CALCULATE ( [Decisiones], piloto_decisiones[resultado] = "ignorada" )', ENT,
     "2 · Ofertas", "Se mostró y no hubo respuesta."),
    ("piloto_decisiones", "Decisiones en control", 'CALCULATE ( [Decisiones], piloto_decisiones[resultado] = "control" )',
     ENT, "2 · Ofertas", "El motor decidió y no mostró: así se mide lo que pasa sin ofertas."),
    ("piloto_decisiones", "Conversión por oferta vista", "DIVIDE ( [Ofertas aceptadas], [Ofertas vistas] )", PCT,
     "2 · Ofertas", "Aceptadas sobre vistas: comparable con ventas / impactados de las campañas previas."),
    ("piloto_decisiones", "Alcance", "DIVIDE ( [Ofertas vistas], [Ofertas mostradas] )", PCT, "2 · Ofertas",
     "Vistas sobre mostradas."),
    ("piloto_decisiones", "P(acepta) del motor",
     ESC + f"CALCULATE ( AVERAGE ( piloto_decisiones[p_motor] ), dim_escenario[escenario] = e, {VISTAS} )", PCT,
     "2 · Ofertas", "Lo que el motor esperaba de las ofertas vistas."),
    ("piloto_decisiones", "Observado frente al motor",
     "DIVIDE ( [Conversión por oferta vista], [P(acepta) del motor] )", "0.00", "2 · Ofertas",
     "1 = el motor está calibrado; más de 1 = subestima; menos de 1 = sobrestima."),
    ("piloto_decisiones", "Conversión de la campaña previa",
     "DIVIDE (\n    SUMX ( VALUES ( dim_ramo[ramo] ), [Ofertas vistas] * CALCULATE ( MAX ( dim_ramo[conversion_previa] ) ) ),\n"
     "    [Ofertas vistas]\n)", PCT, "2 · Ofertas",
     "Ventas / impactados de la campaña previa de cada ramo, ponderada por las ofertas vistas."),
    ("piloto_decisiones", "Frente a la campaña previa",
     "DIVIDE ( [Conversión por oferta vista], [Conversión de la campaña previa] ) - 1", '+0 %;-0 %;0 %', "2 · Ofertas", ""),
    ("piloto_decisiones", "Coinciden con la regla",
     "DIVIDE ( CALCULATE ( [Decisiones], piloto_decisiones[coincide_regla] = 1 ), [Decisiones] )", PCT, "2 · Ofertas",
     "Decisiones en las que el motor eligió el mismo ramo que la regla v1.3."),
    ("piloto_decisiones", "Comisión esperada del motor (simulación)",
     ESC + "CALCULATE ( SUMX ( piloto_decisiones, piloto_decisiones[p_verdad] * piloto_decisiones[comision_12m_cop] ), "
     "dim_escenario[escenario] = e )", COP, "2 · Ofertas", "Solo existe en la simulación: con la verdad simulada."),
    ("piloto_decisiones", "Comisión esperada de la regla (simulación)",
     ESC + "CALCULATE ( SUMX ( piloto_decisiones, piloto_decisiones[p_verdad_regla] * piloto_decisiones[comision_12m_regla_cop] ), "
     "dim_escenario[escenario] = e )", COP, "2 · Ofertas", "Lo mismo si se hubiera ofrecido lo que elegía la regla."),
    ("piloto_decisiones", "Motor frente a la regla (simulación)",
     "DIVIDE ( [Comisión esperada del motor (simulación)], [Comisión esperada de la regla (simulación)] ) - 1",
     '+0.0 %;-0.0 %;0.0 %', "2 · Ofertas", ""),
    # 3 · ventas
    ("piloto_ventas", "Ventas", ESC + "CALCULATE ( COUNTROWS ( piloto_ventas ), dim_escenario[escenario] = e )", ENT,
     "3 · Ventas", ""),
    ("piloto_ventas", "Ventas por oferta", 'CALCULATE ( [Ventas], piloto_ventas[origen] = "oferta" )', ENT, "3 · Ventas", ""),
    ("piloto_ventas", "Compras por su cuenta", 'CALCULATE ( [Ventas], piloto_ventas[origen] = "por su cuenta" )', ENT,
     "3 · Ventas", "Sin oferta, en los dos grupos."),
    ("piloto_ventas", "Comisión 12 m de las ventas",
     ESC + "CALCULATE ( SUM ( piloto_ventas[comision_12m_cop] ), dim_escenario[escenario] = e )", COP, "3 · Ventas", ""),
    ("piloto_ventas", "Conversión acumulada",
     "VAR e = [Escenario elegido]\nVAR f = MAX ( dim_fecha[fecha] )\n"
     "VAR inicio = CALCULATE ( MIN ( piloto_clientes[primera_decision] ), REMOVEFILTERS ( dim_cliente ), "
     "dim_escenario[escenario] = e )\n"
     "VAR c = CALCULATE ( DISTINCTCOUNT ( piloto_ventas[cliente_id] ), REMOVEFILTERS ( dim_fecha ), dim_fecha[fecha] <= f, "
     "dim_escenario[escenario] = e )\nRETURN\n    IF ( f >= inicio, DIVIDE ( c, [Clientes en el piloto] ) )", PCT, "3 · Ventas",
     "Clientes que ya compraron a esa fecha sobre los clientes del piloto, por grupo."),
    # 4 · plan del motor al corte
    ("motor_plan", "Clientes de la base", "COUNTROWS ( dim_cliente )", ENT, "4 · Plan del motor", ""),
    ("motor_plan", "Autorizan ofertas", 'CALCULATE ( COUNTROWS ( dim_cliente ), dim_cliente[autoriza_ofertas] = "Sí" )', ENT,
     "4 · Plan del motor", "Ley 1581: sin autorización el motor no lee sus movimientos."),
    ("motor_plan", "Ofertas del plan", 'CALCULATE ( COUNTROWS ( motor_plan ), motor_plan[resultado] IN { "shown", "banner" } )',
     ENT, "4 · Plan del motor", ""),
    ("motor_plan", "Push del plan", 'CALCULATE ( COUNTROWS ( motor_plan ), motor_plan[resultado] = "shown" )', ENT,
     "4 · Plan del motor", ""),
    ("motor_plan", "Banner del plan", 'CALCULATE ( COUNTROWS ( motor_plan ), motor_plan[resultado] = "banner" )', ENT,
     "4 · Plan del motor", ""),
    ("motor_plan", "Control del plan", 'CALCULATE ( COUNTROWS ( motor_plan ), motor_plan[resultado] = "control" )', ENT,
     "4 · Plan del motor", ""),
    ("motor_plan", "Ventas esperadas del plan", "SUM ( motor_plan[ventas_esperadas] )", "#,0.0", "4 · Plan del motor",
     "Σ alcance × P(acepta) de las ofertas de hoy."),
    ("motor_plan", "Comisión esperada del plan", "SUM ( motor_plan[comision_esperada_cop] )", COP, "4 · Plan del motor",
     "Σ alcance × P(acepta) × comisión a 12 meses."),
    ("motor_plan", "P(acepta) media del plan",
     'CALCULATE ( AVERAGE ( motor_plan[p_motor] ), motor_plan[resultado] IN { "shown", "banner" } )', PCT,
     "4 · Plan del motor", ""),
    ("motor_plan", "Plan coincide con la regla",
     "DIVIDE ( CALCULATE ( COUNTROWS ( motor_plan ), motor_plan[coincide_regla] = 1 ), "
     "CALCULATE ( COUNTROWS ( motor_plan ), NOT ISBLANK ( motor_plan[ramo] ) ) )", PCT, "4 · Plan del motor", ""),
    ("motor_invariantes", "Violaciones", "SUM ( motor_invariantes[violaciones] )", ENT, "4 · Plan del motor",
     "Debe ser 0."),
    ("motor_backtest", "Push máximo en 30 días",
     'VALUE ( LOOKUPVALUE ( motor_backtest[valor], motor_backtest[metrica], "max_push_30d" ) )', ENT,
     "4 · Plan del motor", ""),
    # 5 · base del reto
    ("base_seguros_mensual", "Pólizas emitidas", "SUM ( base_seguros_mensual[polizas_emitidas] )", ENT, "5 · Base del reto", ""),
    ("base_seguros_mensual", "Renovaciones", "SUM ( base_seguros_mensual[renovaciones] )", ENT, "5 · Base del reto", ""),
    ("base_seguros_mensual", "Primas emitidas",
     "SUMX ( base_seguros_mensual, base_seguros_mensual[polizas_emitidas] * base_seguros_mensual[prima_promedio_cop] )",
     COP, "5 · Base del reto", ""),
    ("base_seguros_mensual", "Comisión de las primas emitidas",
     "SUMX ( base_seguros_mensual, base_seguros_mensual[polizas_emitidas] * base_seguros_mensual[prima_promedio_cop] "
     "* base_seguros_mensual[comision_pct] )", COP, "5 · Base del reto", "Primera prima de cada póliza por la comisión."),
    ("base_campanas", "Elegibles campañas", "SUM ( base_campanas[elegibles] )", ENT, "5 · Base del reto", ""),
    ("base_campanas", "Impactados campañas", "SUM ( base_campanas[impactados] )", ENT, "5 · Base del reto", ""),
    ("base_campanas", "Interesados campañas", "SUM ( base_campanas[interesados] )", ENT, "5 · Base del reto", ""),
    ("base_campanas", "Ventas campañas", "SUM ( base_campanas[ventas] )", ENT, "5 · Base del reto", ""),
    ("base_campanas", "Conversión de las campañas",
     "DIVIDE ( [Ventas campañas], [Impactados campañas] )", PCT, "5 · Base del reto", "Ventas / impactados."),
    ("base_pagos_externos", "Compras a otras aseguradoras", "COUNTROWS ( base_pagos_externos )", ENT, "5 · Base del reto", ""),
    ("base_pagos_externos", "Pagado a otras aseguradoras", "SUM ( base_pagos_externos[monto_cop] )", COP,
     "5 · Base del reto", "Lo que estos clientes ya pagan por fuera: el mercado que Lulo puede capturar."),
    # 6 · laboratorio
    ("dim_lab_escenario", "Escenario del laboratorio",
     'IF ( HASONEVALUE ( dim_lab_escenario[escenario] ), VALUES ( dim_lab_escenario[escenario] ), "señal" )', None,
     "6 · Laboratorio", "El de la segmentación; si no hay uno solo, «señal»."),
    ("dim_lab_escenario", "Descripción del escenario del laboratorio",
     LAB + "CALCULATE ( LOOKUPVALUE ( dim_lab_escenario[descripcion], dim_lab_escenario[escenario], e ), "
     "REMOVEFILTERS ( dim_lab_escenario ) )",
     None, "6 · Laboratorio", ""),
    ("lab_series", "Comisión por oferta (lab)",
     LAB + "CALCULATE ( AVERAGE ( lab_series[comision_por_oferta] ), dim_lab_escenario[escenario] = e )", COP, "6 · Laboratorio",
     "Comisión esperada por oferta con la verdad simulada."),
    ("lab_series", "Aceptación (lab)",
     LAB + "CALCULATE ( AVERAGE ( lab_series[aceptacion] ), dim_lab_escenario[escenario] = e )", PCT, "6 · Laboratorio", ""),
    ("lab_calibracion", "Error de calibración (lab)",
     LAB + "CALCULATE ( AVERAGE ( lab_calibracion[error_medio] ), dim_lab_escenario[escenario] = e )", "0.0000",
     "6 · Laboratorio", "Distancia media entre la probabilidad estimada y la verdadera."),
    ("lab_pesos", "Peso aprendido al final (lab)",
     "VAR e = [Escenario del laboratorio]\nVAR r = CALCULATE ( MAX ( lab_pesos[ronda] ), REMOVEFILTERS ( lab_pesos ) )\n"
     "RETURN\n    CALCULATE ( AVERAGE ( lab_pesos[estimado] ), dim_lab_escenario[escenario] = e, lab_pesos[ronda] = r )",
     "0.000", "6 · Laboratorio",
     "Lo que el motor cree de cada efecto después de la última ronda (escala probit)."),
    ("lab_pesos", "Peso verdadero (lab)",
     LAB + "CALCULATE ( AVERAGE ( lab_pesos[verdad] ), dim_lab_escenario[escenario] = e )", "0.000", "6 · Laboratorio",
     "El efecto sembrado en la verdad simulada."),
    ("lab_resumen", "Motor frente a la regla (lab)",
     LAB + "CALCULATE ( AVERAGE ( lab_resumen[motor_frente_a_regla] ), dim_lab_escenario[escenario] = e )",
     '+0.0 %;-0.0 %;0.0 %', "6 · Laboratorio", "Comisión por oferta de las últimas 10 rondas."),
    ("lab_resumen", "Camino al techo del motor (lab)",
     LAB + "CALCULATE ( AVERAGE ( lab_resumen[motor_del_techo] ), dim_lab_escenario[escenario] = e )", PCT,
     "6 · Laboratorio", "0 % = azar, 100 % = oráculo."),
    ("lab_resumen", "Camino al techo de la regla (lab)",
     LAB + "CALCULATE ( AVERAGE ( lab_resumen[regla_del_techo] ), dim_lab_escenario[escenario] = e )", PCT,
     "6 · Laboratorio", ""),
    ("lab_apetito", "τ estimado por el motor (lab)",
     LAB + 'CALCULATE ( AVERAGE ( lab_apetito[tau] ), dim_lab_escenario[escenario] = e, lab_apetito[politica] = "motor" )',
     "0.00", "6 · Laboratorio", "Dispersión del apetito entre clientes estimada con Bayes empírico."),
    ("lab_apetito", "τ verdadero (lab)",
     LAB + "CALCULATE ( AVERAGE ( lab_apetito[verdad] ), dim_lab_escenario[escenario] = e )", "0.00", "6 · Laboratorio", ""),
    # 7 · casos
    ("casos", "Casos", "COUNTROWS ( casos )", ENT, "7 · Casos", ""),
    ("casos", "Éxitos", 'CALCULATE ( COUNTROWS ( casos ), casos[resultado] = "éxito" )', ENT, "7 · Casos", ""),
    ("casos", "Fracasos", 'CALCULATE ( COUNTROWS ( casos ), casos[resultado] = "fracaso" )', ENT, "7 · Casos", ""),
    ("meta", "Etiqueta", 'LOOKUPVALUE ( meta[valor], meta[clave], "etiqueta" )', None, "8 · Avisos",
     "«Prototipo académico · datos simulados»: siempre a la vista."),
    ("meta", "Aviso del piloto", 'LOOKUPVALUE ( meta[valor], meta[clave], "aviso_piloto" )', None, "8 · Avisos", ""),
    ("meta", "Aviso de la base", 'LOOKUPVALUE ( meta[valor], meta[clave], "aviso_base" )', None, "8 · Avisos", ""),
    ("meta", "Versiones",
     '"Reglas " & LOOKUPVALUE ( meta[valor], meta[clave], "reglas" ) & " · " & '
     'LOOKUPVALUE ( meta[valor], meta[clave], "motor" ) & " · base al " & '
     'LOOKUPVALUE ( meta[valor], meta[clave], "base_corte" )', None, "8 · Avisos", ""),
]

# ------------------------------------------------------------------ páginas (1280 × 720)
# Cada visual: (tipo, x, y, ancho, alto, título, campos). Campos: "Tabla[Columna]" o "Tabla.[Medida]".
# Tipos: texto, tarjeta, segmentacion, lineas, columnas, barras, tabla. Para gráficos: categoría | valores | series.
ENCABEZADO = [("texto", 24, 12, 900, 44, None, "{titulo}"),
              ("tarjeta", 1010, 12, 246, 44, None, ["meta.[Etiqueta]"])]
PAGINAS = [
    ("1 · Resumen", "¿Las ofertas del motor venden? · Piloto simulado", [
        ("segmentacion", 24, 64, 300, 56, "Escenario", ["dim_escenario[nombre]"]),
        ("tarjeta", 340, 64, 916, 56, None, ["dim_escenario.[Descripción del escenario]"]),
        ("tarjeta", 24, 132, 300, 130, "Diferencia frente al control", ["piloto_clientes.[Diferencia frente al control (pp)]"]),
        ("tarjeta", 340, 132, 300, 130, "Intervalo de 95 %", ["piloto_clientes.[Intervalo de la diferencia]"]),
        ("tarjeta", 656, 132, 290, 130, "Clientes que compran por las ofertas", ["piloto_clientes.[Ventas incrementales]"]),
        ("tarjeta", 962, 132, 294, 130, "Comisión incremental a 12 meses", ["piloto_clientes.[Comisión incremental 12 m]"]),
        ("tarjeta", 24, 274, 1232, 52, None, ["piloto_clientes.[Veredicto]"]),
        ("lineas", 24, 338, 760, 300, "Clientes que ya compraron, tratamiento frente a control",
         ("dim_fecha[semana_inicio]", ["piloto_ventas.[Conversión acumulada]"], "dim_cliente[grupo]")),
        ("columnas", 800, 338, 456, 300, "Compran en el piloto, por grupo",
         ("dim_cliente[grupo]", ["piloto_clientes.[Conversión por cliente]"], None)),
        ("tarjeta", 24, 650, 1232, 58, None, ["meta.[Aviso del piloto]"]),
    ]),
    ("2 · Embudo", "De 600 clientes a una venta: dónde se queda cada uno", [
        ("segmentacion", 24, 64, 300, 56, "Escenario", ["dim_escenario[nombre]"]),
        ("tarjeta", 340, 64, 220, 56, "Clientes de la base", ["motor_plan.[Clientes de la base]"]),
        ("tarjeta", 576, 64, 220, 56, "Autorizan ofertas", ["motor_plan.[Autorizan ofertas]"]),
        ("tarjeta", 812, 64, 220, 56, "Ofertas vistas", ["piloto_decisiones.[Ofertas vistas]"]),
        ("tarjeta", 1048, 64, 208, 56, "Ofertas aceptadas", ["piloto_decisiones.[Ofertas aceptadas]"]),
        ("barras", 24, 132, 610, 280, "Piloto: decisiones por resultado",
         ("piloto_decisiones[resultado]", ["piloto_decisiones.[Decisiones]"], None)),
        ("columnas", 650, 132, 606, 280, "Conversión por oferta vista frente a la campaña previa, por ramo",
         ("dim_ramo[ramo]", ["piloto_decisiones.[Conversión por oferta vista]", "piloto_decisiones.[Conversión de la campaña previa]"], None)),
        ("tabla", 24, 424, 1232, 284, "Base del reto: embudo de las campañas previas",
         ["base_campanas[campana]", "base_campanas[canal]", "base_campanas[elegibles]", "base_campanas[impactados]",
          "base_campanas[interesados]", "base_campanas[ventas]", "base_campanas.[Conversión de las campañas]"]),
    ]),
    ("3 · ¿El modelo acierta?", "Lo que el motor esperaba frente a lo que pasó", [
        ("segmentacion", 24, 64, 300, 56, "Escenario", ["dim_escenario[nombre]"]),
        ("tarjeta", 340, 64, 300, 56, "Observado / esperado por el motor", ["piloto_decisiones.[Observado frente al motor]"]),
        ("tarjeta", 656, 64, 290, 56, "Coinciden con la regla v1.3", ["piloto_decisiones.[Coinciden con la regla]"]),
        ("tarjeta", 962, 64, 294, 56, "Motor frente a la regla (verdad simulada)",
         ["piloto_decisiones.[Motor frente a la regla (simulación)]"]),
        ("columnas", 24, 132, 610, 280, "Calibración: P(acepta) del motor frente a la aceptación observada",
         ("piloto_decisiones[tramo_p_motor]", ["piloto_decisiones.[P(acepta) del motor]", "piloto_decisiones.[Conversión por oferta vista]"], None)),
        ("columnas", 650, 132, 606, 280, "Aceptación con evento reciente (momento) y sin él",
         ("piloto_decisiones[momento_texto]", ["piloto_decisiones.[P(acepta) del motor]", "piloto_decisiones.[Conversión por oferta vista]"], None)),
        ("lineas", 24, 424, 610, 284, "Laboratorio: comisión por oferta en 40 rondas («señal»)",
         ("lab_series[ronda]", ["lab_series.[Comisión por oferta (lab)]"], "lab_series[politica_nombre]")),
        ("lineas", 650, 424, 606, 284, "Laboratorio: error de calibración, motor frente a regla",
         ("lab_calibracion[ronda]", ["lab_calibracion.[Error de calibración (lab)]"], "lab_calibracion[modelo]")),
    ]),
    ("4 · Contacto", "Contactar sin cansar: canal, tope y reglas que nunca se rompen", [
        ("tarjeta", 24, 64, 300, 80, "Violaciones de las reglas", ["motor_invariantes.[Violaciones]"]),
        ("tarjeta", 340, 64, 300, 80, "Push máximo a un cliente en 30 días", ["motor_backtest.[Push máximo en 30 días]"]),
        ("tarjeta", 656, 64, 290, 80, "Alcance de las ofertas (vistas / mostradas)", ["piloto_decisiones.[Alcance]"]),
        ("tarjeta", 962, 64, 294, 80, "Ofertas ignoradas", ["piloto_decisiones.[Ofertas ignoradas]"]),
        ("tabla", 24, 156, 610, 300, "Invariantes del backtest",
         ["motor_invariantes[invariante]", "motor_invariantes[violaciones]", "motor_invariantes[fuente]"]),
        ("barras", 650, 156, 606, 300, "Plan al corte: por qué va por push o por banner",
         ("motor_plan[motivo_canal]", ["motor_plan.[Ofertas del plan]"], None)),
        ("barras", 24, 468, 1232, 240, "Plan al corte: resultado del motor para los 600 clientes",
         ("motor_plan[resultado_texto]", ["motor_plan.[Clientes de la base]"], None)),
    ]),
    ("5 · Piloto real", "Cuántos clientes necesita el piloto real para saber", [
        ("segmentacion", 24, 64, 300, 56, "Escenario", ["dim_escenario[nombre]"]),
        ("tarjeta", 340, 64, 300, 56, "Clientes en control hoy", ["piloto_clientes.[Clientes control]"]),
        ("tarjeta", 656, 64, 290, 56, "Efecto mínimo detectable con este tamaño", ["piloto_clientes.[Efecto mínimo detectable (pp)]"]),
        ("tarjeta", 962, 64, 294, 56, "Valor p", ["piloto_clientes.[Valor p]"]),
        ("tabla", 24, 132, 1232, 260, "M6: clientes por grupo para detectar el aumento (α 5 %, potencia 80 %)",
         ["dim_ramo[ramo]", "dim_ramo[conversion_previa]", "dim_ramo[piloto_n_20]", "dim_ramo[piloto_n_50]",
          "dim_ramo[piloto_n_100]"]),
        ("tarjeta", 24, 404, 1232, 70, None, ["piloto_clientes.[Lectura de la muestra]"]),
        ("columnas", 24, 486, 1232, 222, "Ofertas vistas por ramo en el piloto simulado",
         ("dim_ramo[ramo]", ["piloto_decisiones.[Ofertas vistas]"], None)),
    ]),
    ("6 · Laboratorio", "¿El motor aprende? Verdad simulada sobre los clientes de la base", [
        ("segmentacion", 24, 64, 300, 56, "Escenario del laboratorio", ["dim_lab_escenario[escenario]"]),
        ("tarjeta", 340, 64, 300, 56, "Motor frente a la regla", ["lab_resumen.[Motor frente a la regla (lab)]"]),
        ("tarjeta", 656, 64, 290, 56, "Camino al techo: motor", ["lab_resumen.[Camino al techo del motor (lab)]"]),
        ("tarjeta", 962, 64, 294, 56, "Camino al techo: regla", ["lab_resumen.[Camino al techo de la regla (lab)]"]),
        ("lineas", 24, 132, 1232, 290, "Comisión por oferta de cada política",
         ("lab_series[ronda]", ["lab_series.[Comisión por oferta (lab)]"], "lab_series[politica_nombre]")),
        ("barras", 24, 434, 610, 274, "Lo que aprendió el motor de cada efecto frente a la verdad",
         ("lab_pesos[etiqueta]", ["lab_pesos.[Peso aprendido al final (lab)]", "lab_pesos.[Peso verdadero (lab)]"], None)),
        ("lineas", 650, 434, 606, 274, "Dispersión del apetito entre clientes (τ, Bayes empírico)",
         ("lab_apetito[ronda]", ["lab_apetito.[τ estimado por el motor (lab)]", "lab_apetito.[τ verdadero (lab)]"], None)),
    ]),
    ("7 · Casos reales", "Quién usó métodos como estos y qué pasó", [
        ("tarjeta", 24, 64, 300, 56, "Casos", ["casos.[Casos]"]),
        ("tarjeta", 340, 64, 300, 56, "Éxitos", ["casos.[Éxitos]"]),
        ("tarjeta", 656, 64, 290, 56, "Fracasos", ["casos.[Fracasos]"]),
        ("segmentacion", 962, 64, 294, 56, "Parte del prototipo", ["casos[conexion]"]),
        ("tabla", 24, 132, 1232, 576, None,
         ["casos[empresa]", "casos[anio]", "casos[resultado]", "casos[cifra]", "casos[leccion]", "casos[fuente]",
          "casos[confianza]"]),
    ]),
    ("8 · Base del reto", "La base del reto: lo que hay hoy (sintética y académica)", [
        ("tarjeta", 24, 64, 300, 56, "Pólizas emitidas en el año", ["base_seguros_mensual.[Pólizas emitidas]"]),
        ("tarjeta", 340, 64, 300, 56, "Comisión de las primas emitidas", ["base_seguros_mensual.[Comisión de las primas emitidas]"]),
        ("tarjeta", 656, 64, 290, 56, "Pagado a otras aseguradoras", ["base_pagos_externos.[Pagado a otras aseguradoras]"]),
        ("tarjeta", 962, 64, 294, 56, "Conversión de las campañas previas", ["base_campanas.[Conversión de las campañas]"]),
        ("lineas", 24, 132, 1232, 300, "Pólizas emitidas por mes y ramo",
         ("dim_fecha[mes_nombre]", ["base_seguros_mensual.[Pólizas emitidas]"], "dim_ramo[ramo]")),
        ("tabla", 24, 444, 1232, 200, "Catálogo: prima, comisión y persistencia por ramo",
         ["dim_ramo[ramo]", "dim_ramo[prima_cop]", "dim_ramo[comision_pct]", "dim_ramo[persistencia_12m]",
          "dim_ramo[cancelacion_pct]", "dim_ramo[comision_12m_cop]", "dim_ramo[compras_por_su_cuenta]"]),
        ("tarjeta", 24, 656, 1232, 52, None, ["meta.[Aviso de la base]"]),
    ]),
]


# ------------------------------------------------------------------ utilidades
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


def _m_tabla(nombre: str, cols: dict[str, str]) -> list[str]:
    t = ", ".join(f'{{"{c}", {M_TIPO[k]}}}' for c, k in cols.items())
    return ["let", f'    Tabla = LeerCsv("{nombre}.csv"),',
            f'    Tipos = Table.TransformColumnTypes(Tabla, {{{t}}}, "en-US")', "in", "    Tipos"]


def _formato(dt: str, col: str) -> str | None:
    if dt == "dateTime":
        return "yyyy-mm-dd"
    if col.endswith("_cop"):
        return '"$"#,0'
    if dt == "double" and (col.startswith(("p_", "conversion", "comision_pct", "persistencia", "cancelacion"))
                           or col in ("alcance", "aceptacion")):
        return "0.0 %"
    return None


def model_bim(csvs: dict[str, str]) -> str:
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
    for nombre, desc in TABLAS.items():
        cols = tipos(csvs[f"{nombre}.csv"])
        cdefs = []
        for c, dt in cols.items():
            cd = {"name": c, "dataType": dt, "sourceColumn": c, "lineageTag": tag("c", nombre, c),
                  "summarizeBy": "none", "annotations": [{"name": "SummarizationSetBy", "value": "Automatic"}]}
            f = _formato(dt, c)
            if f:
                cd["formatString"] = f
            if (nombre, c) in ORDENAR_POR:
                cd["sortByColumn"] = ORDENAR_POR[(nombre, c)]
            cdefs.append(cd)
        t = {"name": nombre, "description": desc, "lineageTag": tag("t", nombre), "columns": cdefs,
             "partitions": [{"name": nombre, "mode": "import", "source": {"type": "m", "expression": _m_tabla(nombre, cols)}}]}
        if nombre in por_tabla:
            t["measures"] = por_tabla[nombre]
        tablas.append(t)
    rels = [{"name": tag("r", a, b, c, d), "fromTable": a, "fromColumn": b, "toTable": c, "toColumn": d}
            for a, b, c, d in RELACIONES]
    leer = ["(archivo as text) as table =>", "let",
            '    Fuente = if Text.StartsWith(Origen, "http") then Web.Contents(Origen, [RelativePath = archivo])'
            ' else File.Contents(Origen & archivo),',
            '    Csv = Csv.Document(Fuente, [Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv]),',
            "    Encabezados = Table.PromoteHeaders(Csv, [PromoteAllScalars = true]),",
            '    Vacios = Table.ReplaceValue(Encabezados, "", null, Replacer.ReplaceValue, Table.ColumnNames(Encabezados))',
            "in", "    Vacios"]
    model = {
        "name": "Lulo", "compatibilityLevel": 1567,
        "model": {
            "culture": "es-CO", "sourceQueryCulture": "es-CO", "defaultPowerBIDataSourceVersion": "powerBI_V3",
            "dataAccessOptions": {"legacyRedirects": True, "returnErrorValuesAsNull": True},
            "tables": tablas, "relationships": rels,
            "expressions": [
                {"name": "Origen", "kind": "m", "lineageTag": tag("e", "Origen"),
                 "description": "Carpeta de los CSV: la URL de GitHub (por defecto) o una carpeta local terminada en \\",
                 "expression": f'"{REPO_RAW}" meta [IsParameterQuery = true, Type = "Text", IsParameterQueryRequired = true]'},
                {"name": "LeerCsv", "kind": "m", "lineageTag": tag("e", "LeerCsv"), "expression": leer},
            ],
            "annotations": [{"name": "__PBI_TimeIntelligenceEnabled", "value": "0"},
                            {"name": "PBI_QueryOrder", "value": json.dumps(["Origen", "LeerCsv", *TABLAS], ensure_ascii=False)}],
        },
    }
    return json.dumps(model, ensure_ascii=False, indent=2) + "\n"


def medidas_dax() -> str:
    out = ["// Medidas del dashboard de Lulo (generado por scripts/exportar_powerbi.py; no se edita a mano).",
           "// Ya vienen en powerbi/Lulo.SemanticModel/model.bim. Para crearlas a mano: Modelado → Nueva medida,",
           "// en la tabla indicada, y pegar desde el nombre. Las del piloto filtran el escenario elegido.", ""]
    carpeta = None
    for t, n, e, f, c, d in MEDIDAS:
        if c != carpeta:
            out += ["", f"// ===== {c} " + "=" * max(0, 70 - len(c)), ""]
            carpeta = c
        if d:
            out.append(f"// {d}")
        out.append(f"// Tabla: {t}" + (f" · Formato: {f}" if f else ""))
        out.append(f"{n} =")
        out += ["    " + x for x in e.split("\n")]
        out.append("")
    return "\n".join(out).rstrip() + "\n"


def tema() -> str:
    C = COLOR
    fill = lambda c: {"solid": {"color": c}}  # noqa: E731
    t = {
        "name": "Lulo · prototipo", "dataColors": SERIES, "background": C["pagina"], "foreground": C["texto"],
        "tableAccent": C["lima"], "good": C["bien"], "neutral": C["alerta"], "bad": C["mal"],
        "maximum": SERIES[0], "center": "#647B9A", "minimum": C["tarjeta"],
        "textClasses": {
            "callout": {"fontSize": 30, "fontFace": "Segoe UI Semibold", "color": C["texto"]},
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
            "card": {"*": {"labels": [{"color": fill(C["texto"]), "fontSize": 28}],
                           "categoryLabels": [{"show": False}],
                           "background": [{"show": True, "color": fill(C["tarjeta"]), "transparency": 0}]}},
            "tableEx": {"*": {"columnHeaders": [{"fontColor": fill(C["texto"]), "backColor": fill(C["linea"])}],
                              "values": [{"fontColorPrimary": fill(C["texto"]), "backColorPrimary": fill(C["tarjeta"]),
                                          "fontColorSecondary": fill(C["texto"]), "backColorSecondary": fill("#18244A")}]}},
            "slicer": {"*": {"items": [{"fontColor": fill(C["texto"]), "background": fill(C["tarjeta"])}],
                             "header": [{"fontColor": fill(C["texto_2"])}]}},
        },
    }
    return json.dumps(t, ensure_ascii=False, indent=2) + "\n"


# ------------------------------------------------------------------ informe (PBIR heredado: report.json)
def _lit(v) -> dict:
    if isinstance(v, bool):
        return {"expr": {"Literal": {"Value": "true" if v else "false"}}}
    if isinstance(v, (int, float)):
        return {"expr": {"Literal": {"Value": f"{v}D"}}}
    return {"expr": {"Literal": {"Value": "'" + str(v).replace("'", "''") + "'"}}}


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
    sel = {("Measure" if medida else "Column"): expr, "Name": q}
    return sel, q


def _visual(pag: int, i: int, v: tuple, titulo_pagina: str) -> dict:
    tipo, x, y, w, h, titulo, campos = v
    nombre = tag("v", str(pag), str(i))[:20].replace("-", "")
    alias: dict[str, str] = {}
    vc: dict = {}
    objects: dict = {}
    if tipo == "texto":
        texto = campos.format(titulo=titulo_pagina)
        sv = {"visualType": "textbox", "drillFilterOtherVisuals": True,
              "objects": {"general": [{"properties": {"paragraphs": [{"textRuns": [
                  {"value": texto, "textStyle": {"fontWeight": "bold", "fontSize": "20pt", "color": COLOR["texto"]}}]}]}}]}}
        vc["background"] = [{"properties": {"show": _lit(False)}}]
    else:
        if tipo in ("tarjeta", "segmentacion", "tabla"):
            refs = campos
            sels = [_campo(r, alias) for r in refs]
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
        vt = {"tarjeta": "card", "segmentacion": "slicer", "tabla": "tableEx", "lineas": "lineChart",
              "columnas": "clusteredColumnChart", "barras": "clusteredBarChart"}[tipo]
        sv = {"visualType": vt, "projections": proj,
              "prototypeQuery": {"Version": 2, "From": [{"Name": a, "Entity": t, "Type": 0} for t, a in alias.items()],
                                 "Select": [s for s, _ in sels]},
              "drillFilterOtherVisuals": True}
        if tipo == "segmentacion":
            objects["data"] = [{"properties": {"mode": _lit("Dropdown")}}]
        if tipo == "tarjeta":
            texto = any(q.endswith(("Veredicto", "Lectura de la muestra", "Etiqueta", "Aviso del piloto",
                                    "Aviso de la base", "Descripción del escenario", "Intervalo de la diferencia"))
                        for _, q in sels)
            objects["categoryLabels"] = [{"properties": {"show": _lit(False)}}]
            if texto:
                objects["labels"] = [{"properties": {"fontSize": _lit(12 if h < 60 else 14),
                                                     "color": {"solid": {"color": _lit(COLOR["texto_2"])}}}}]
            if any(q.endswith("Etiqueta") for _, q in sels):
                objects["labels"] = [{"properties": {"fontSize": _lit(10),
                                                     "color": {"solid": {"color": _lit(COLOR["lima"])}}}}]
        if tipo in ("lineas", "columnas", "barras"):
            objects["legend"] = [{"properties": {"show": _lit(True), "position": _lit("Top")}}]
        if objects:
            sv["objects"] = objects
        if titulo:
            vc["title"] = [{"properties": {"show": _lit(True), "text": _lit(titulo)}}]
        else:
            vc["title"] = [{"properties": {"show": _lit(False)}}]
    if vc:
        sv["vcObjects"] = vc
    config = {"name": nombre, "layouts": [{"id": 0, "position": {"x": x, "y": y, "z": i, "width": w, "height": h}}],
              "singleVisual": sv}
    return {"x": x, "y": y, "z": i, "width": w, "height": h, "config": json.dumps(config, ensure_ascii=False),
            "filters": "[]"}


def report_json() -> str:
    secciones = []
    for p, (nombre, titulo, visuales) in enumerate(PAGINAS):
        vs = [*ENCABEZADO, *visuales]
        secciones.append({"name": "Seccion" + tag("p", str(p))[:12].replace("-", ""), "displayName": nombre,
                          "displayOption": 1, "width": 1280, "height": 720, "ordinal": p, "filters": "[]",
                          "config": "{}", "visualContainers": [_visual(p, i, v, titulo) for i, v in enumerate(vs)]})
    config = {"version": "5.43", "themeCollection": {"customTheme": {"name": "tema-lulo.json", "version": "5.43", "type": 1}},
              "activeSectionIndex": 0, "defaultDrillFilterOtherVisuals": True,
              "settings": {"useNewFilterPaneExperience": True, "allowChangeFilterTypes": True, "useStylableVisualContainerHeader": True}}
    rep = {"config": json.dumps(config, ensure_ascii=False), "layoutOptimization": 0,
           "resourcePackages": [{"resourcePackage": {"name": "RegisteredResources", "type": 1, "disabled": False,
                                                     "items": [{"name": "tema-lulo.json", "path": "tema-lulo.json", "type": 202}]}}],
           "sections": secciones}
    return json.dumps(rep, ensure_ascii=False, indent=2) + "\n"


def proyecto(csvs: dict[str, str]) -> dict[str, str]:
    """Archivos del proyecto de Power BI, por ruta relativa a powerbi/."""
    th = tema()
    return {
        "Lulo.pbip": json.dumps({"version": "1.0", "artifacts": [{"report": {"path": "Lulo.Report"}}],
                                 "settings": {"enableAutoRecovery": True}}, indent=2) + "\n",
        "Lulo.SemanticModel/definition.pbism": json.dumps({"version": "1.0", "settings": {}}, indent=2) + "\n",
        "Lulo.SemanticModel/model.bim": model_bim(csvs),
        "Lulo.Report/definition.pbir": json.dumps({"version": "1.0", "datasetReference": {
            "byPath": {"path": "../Lulo.SemanticModel"}, "byConnection": None}}, indent=2) + "\n",
        "Lulo.Report/report.json": report_json(),
        "Lulo.Report/StaticResources/RegisteredResources/tema-lulo.json": th,
        "tema-lulo.json": th,
        "medidas.dax": medidas_dax(),
    }
