# Dashboard de resultados · Power BI

**Prototipo académico · datos simulados.** Este dashboard responde una pregunta: **¿las ofertas del motor convierten seguros en ventas?** La respuesta honesta de hoy es que nadie lo sabe todavía, porque la base del reto no trae respuestas a ofertas. El dashboard muestra tres cosas:

- **Qué dice la base del reto:**
  - campañas previas;
  - pólizas por mes;
  - pagos a otras aseguradoras.
- **Qué decide el motor sobre esa base:**
  - el plan al corte;
  - el backtest con 0 violaciones.
- **Cómo se va a saber si vende:**
  - un piloto **simulado** con grupo de control, en el mismo formato que tendrá el piloto real;
  - el laboratorio, que mide si el motor aprende.

Cuando Lulo corra el piloto real, se cambian tres archivos y el mismo dashboard da la respuesta de verdad (sección 6). Los casos reales de otras empresas están en la página 7 y en [`docs/CASOS.md`](../docs/CASOS.md).

## 1. Abrirlo

### En Power BI Desktop (Windows)

1. Abrir `powerbi/Lulo.pbip` (Archivo → Abrir).
   - Si Power BI no reconoce el formato, activar en Archivo → Opciones → Características en versión preliminar la opción «Guardar como proyecto de Power BI (.pbip)» y reiniciar.
2. **Configurar el origen de los datos.** El parámetro **Origen** apunta por defecto a `powerbi/datos` en la rama `main` de GitHub (el repositorio es público).
   - **Antes de pasar a `main`, o sin internet:** Inicio → Transformar datos → Editar parámetros → Origen. Poner la carpeta local terminada en `\`, por ejemplo `C:\Users\yo\Prototipo-IIND\powerbi\datos\`.
   - **Si pide credenciales para `raw.githubusercontent.com`:** elegir **Anónimo**.
3. Inicio → **Actualizar**.

El modelo incluye las tablas, las relaciones, las 88 medidas, las 8 páginas y el tema Lulo. Todo lo genera `scripts/exportar_powerbi.py`.

> **Importante:** el proyecto se armó en Linux y no se ha abierto todavía en Power BI Desktop.
> - Si una página sale con un visual roto, se arregla en el panel de campos con lo que dice la sección 4.
> - Si el proyecto no abre, está el **plan B** (sección 7): el mismo dashboard a mano en unos 40 minutos, con `medidas.dax` y `tema-lulo.json`.

### Sin Power BI

Abrir `powerbi/vista_previa.html` en el navegador: son las mismas 8 páginas con las mismas cifras. Cada cifra se calcula con la misma definición que la medida DAX del mismo nombre. Sirve para:
- revisar el dashboard desde cualquier computador;
- comparar con lo que muestra Power BI: si una cifra no coincide, la medida quedó mal.

## 2. Los datos: qué es real y qué es simulado

| Tablas | Tipo | Qué tienen |
|---|---|---|
| `base_campanas`, `base_seguros_mensual`, `base_pagos_externos`, `dim_cliente`, `dim_ramo` | **Base del reto** | Tal cual la base. Es 100 % sintética y académica: sus cifras no son métricas de Lulo Bank. |
| `motor_plan`, `motor_backtest`, `motor_invariantes` | **Motor** | Lo que decide el motor real (reglas v2.1) sobre la base. |
| `piloto_decisiones`, `piloto_ventas`, `piloto_clientes`, `dim_escenario` | **Simulado** | El motor y sus decisiones son reales; las respuestas de los clientes son inventadas (sección 5). |
| `lab_*`, `dim_lab_escenario` | **Laboratorio** | `lulo_app/ml/laboratorio.json` en tablas. |
| `casos` | **Casos reales** | 20 empresas con fuente (`powerbi/casos.csv`, curado a mano). |
| `dim_fecha`, `meta` | Apoyo | Calendario de la base; versiones, semilla, hash de la base y avisos. |

**Relaciones:**
- Las dimensiones filtran a los hechos, en una sola dirección:
  - `dim_cliente` → hechos por `cliente_id`;
  - `dim_ramo` → hechos por `ramo`;
  - `dim_fecha` → hechos por `fecha` o `mes`.
- `dim_escenario` filtra las tablas del piloto.
- `dim_lab_escenario` filtra las tablas del laboratorio.
- El grupo (tratamiento o control) es una columna de `dim_cliente`: lo asigna el hash del motor, igual que en producción.

**Escenario por defecto.** Las medidas del piloto filtran un solo escenario a la vez, para que nunca se sumen dos mundos:
- en el piloto, el que se elija en la segmentación o, si no hay uno solo, el de orden 1 en `dim_escenario`;
- en el laboratorio, «señal».

## 3. Resultado del piloto simulado

Los dos mundos usan el mismo motor y los mismos sorteos. El grupo de control queda idéntico en ambos.

| | El motor ve más que la regla («señal») | La regla tenía razón («regla correcta») |
|---|---|---|
| Clientes en el piloto: tratamiento / control | 437 / 45 | 437 / 45 |
| Compran durante el piloto: tratamiento / control | 25,4 % / 4,4 % | 19,5 % / 4,4 % |
| **Diferencia frente al control** | **+21,0 pp** (IC 95 %: +13,7 a +28,2; p = 0,0016) | **+15,0 pp** (IC 95 %: +7,9 a +22,1; p = 0,0127) |
| Clientes que compran por las ofertas | 92 | 66 |
| Comisión incremental a 12 meses | $6.919.020 | $4.913.935 |
| Ofertas vistas / aceptadas | 968 / 99 (10,2 %) | 987 / 70 (7,1 %) |
| Aceptación observada / P(acepta) del motor | 1,42 (el motor subestima) | 0,98 (calibrado) |
| Frente a la campaña previa del mismo ramo | +9 % | −25 % |
| El motor elige lo mismo que la regla v1.3 | 99,6 % | 99,6 % |

**Cómo se lee:**

1. **Las ofertas suman ventas en los dos mundos.** Con ofertas compran más clientes que en el control, y el intervalo no toca el cero. Pero el control tiene 45 clientes y solo 2 compran, así que la lectura es frágil: el dashboard lo dice con «Muestra chica». El efecto mínimo que se puede detectar con este tamaño es de unos 17 a 19 pp.
2. **La calibración separa los dos mundos.**
   - **En «señal»:** las ofertas en las que el motor confía más venden más (de 5,1 % a 32 % por tramo). Eso es señal real que el motor todavía subestima.
   - **En «regla correcta»:** la curva queda plana, y el momento convierte peor (5,8 % frente a 8,8 %). El motor esperaba más y los datos lo desmienten.

   Esta página es la que dirá en cuál de los dos mundos está Lulo.
3. **El motor del piloto decide casi como la regla (99,6 %).** No es un error. Durante el piloto, el motor de la población no se reentrena: solo aprende de cada cliente dentro de su sesión.
   - La ganancia frente a la regla viene de aprender de todas las respuestas. El laboratorio la mide: +10 % de comisión por oferta en «señal» y −1 % si la regla tenía razón.
   - Esa ganancia entra con `python scripts/train_motor.py --respuestas <archivo>`, y solo si gana el campeón/retador.
4. **Lo que no dice:** el piloto simulado no dice si el motor vende. Dice cómo se va a saber, y qué se vería en cada caso.

## 4. Las páginas

Todas llevan arriba la etiqueta «Prototipo académico · datos simulados».

| Página | Pregunta | Visuales (campos) |
|---|---|---|
| **1 · Resumen** | ¿Las ofertas venden? | Segmentación `dim_escenario[nombre]`. Tarjetas: [Diferencia frente al control (pp)], [Intervalo de la diferencia], [Ventas incrementales], [Comisión incremental 12 m], [Veredicto]. Líneas: eje `dim_fecha[semana_inicio]`, valor [Conversión acumulada], leyenda `dim_cliente[grupo]`. Columnas: `dim_cliente[grupo]` × [Conversión por cliente]. Tarjeta [Aviso del piloto]. |
| **2 · Embudo** | ¿Dónde se queda cada cliente? | Tarjetas: [Clientes de la base], [Autorizan ofertas], [Ofertas vistas], [Ofertas aceptadas]. Barras: `piloto_decisiones[resultado]` × [Decisiones]. Columnas: `dim_ramo[ramo]` × [Conversión por oferta vista] y [Conversión de la campaña previa]. Tabla de `base_campanas`. |
| **3 · ¿El modelo acierta?** | ¿Lo que esperaba el motor se cumple? | Tarjetas: [Observado frente al motor], [Coinciden con la regla], [Motor frente a la regla (simulación)]. Columnas: `piloto_decisiones[tramo_p_motor]` × [P(acepta) del motor] y [Conversión por oferta vista]. Columnas: `piloto_decisiones[momento_texto]` × las mismas dos. Líneas del laboratorio: `lab_series[ronda]` × [Comisión por oferta (lab)] por `lab_series[politica_nombre]`; `lab_calibracion[ronda]` × [Error de calibración (lab)] por `lab_calibracion[modelo]`. |
| **4 · Contacto** | ¿Se contacta sin cansar y sin romper reglas? | Tarjetas: [Violaciones] (debe ser 0), [Push máximo en 30 días], [Alcance], [Ofertas ignoradas]. Tabla de `motor_invariantes`. Barras: `motor_plan[motivo_canal]` y `motor_plan[resultado_texto]`. |
| **5 · Piloto real** | ¿Cuántos clientes hacen falta? | Tarjetas: [Clientes control], [Efecto mínimo detectable (pp)], [Valor p], [Lectura de la muestra]. Tabla M6 de `dim_ramo` (`piloto_n_20`, `piloto_n_50`, `piloto_n_100`). |
| **6 · Laboratorio** | ¿El motor aprende? | Segmentación `dim_lab_escenario[escenario]`. Tarjetas: [Motor frente a la regla (lab)], [Camino al techo del motor (lab)], [Camino al techo de la regla (lab)]. Líneas por política. Barras: `lab_pesos[etiqueta]` × [Peso aprendido al final (lab)] y [Peso verdadero (lab)]. Líneas: [τ estimado por el motor (lab)] y [τ verdadero (lab)]. |
| **7 · Casos reales** | ¿A quién le funcionó algo así? | Tarjetas: [Casos], [Éxitos], [Fracasos]. Segmentación `casos[conexion]`. Tabla de `casos`. |
| **8 · Base del reto** | ¿Qué hay hoy? | Tarjetas: [Pólizas emitidas], [Comisión de las primas emitidas], [Pagado a otras aseguradoras], [Conversión de las campañas]. Líneas: `dim_fecha[mes_nombre]` × [Pólizas emitidas] por `dim_ramo[ramo]`. Tabla de `dim_ramo`. |

**Colores (tema Lulo):**
- **Fondo:** `#0B1430`; **tarjetas:** `#131E3D`.
- **Series:** `#8A9E00` (motor y tratamiento), `#3987e5` (regla y control), luego `#d95926`, `#9085e9`, `#199e70` y `#c98500`.
- **Validación:** la paleta pasa el validador de la guía de visualización en modo oscuro (banda de luminosidad, croma, separación para daltonismo y contraste).
- **Lima `#E8FF00`:** es el acento de Lulo. Va en la etiqueta y en los bordes, no en series de datos, porque es demasiado clara para separarse de otros colores.
- **Orden de las series:** lo fijan columnas de orden (`grupo_orden`, `politica_orden`, `orden`), así que el tratamiento siempre lleva el color del motor.

## 5. Cómo se simuló el piloto (supuestos)

- **Periodo:** la base se recorre semana a semana, del 30-ene-2026 (tres meses de historia, como el backtest) al corte del 8-oct-2026: 36 evaluaciones de los 600 clientes.
- **Motor:** el de la app, sin cambios. Autorización, elegibilidad, capacidad de pago, espera de 30 días por ramo, tope de push, 7 días entre push, control del 10 % por hash y exploración del 10 %.
  - Lo que el cliente compró deja de ofrecerse.
  - Sus respuestas alimentan el aprendizaje dentro de la sesión.
  - El motor de la población no se reentrena.
- **Si el cliente ve la oferta:** con el alcance que el motor calcula para el canal. Para push, la apertura del cliente (M3); para banner, impactados / elegibles de la campaña de banner.
- **Si la acepta:** con la verdad del laboratorio (`scripts/laboratorio.py`, `verdad()` y `p_verdad()`):
  - **«señal»:** efectos que la regla no ve, momento × 1,6, señal media × 0,45 y apetito por cliente con desviación 0,20;
  - **«regla correcta»:** conversión de la campaña previa × 0,6 si la señal es media.
- **Compras por su cuenta**, sin oferta y en los dos grupos:
  - **Cálculo:** cada semana, con probabilidad igual al ritmo con que estos clientes le compraron a otras aseguradoras en el año de la base. Son los pares cliente-ramo distintos de Pagos_Seguros sobre 600 clientes × 48,7 semanas.
  - **Ritmo semanal por ramo:** SOAT 0,17 %, Vida 0,092 %, Hogar 0,082 %, Mascotas 0,041 %. Desempleo y Viajes quedan en 0 porque la base no trae pagos externos de esos ramos.
  - **Excepción:** no compra por su cuenta un ramo que ya tiene o que ya pagó por fuera.
- **Quién entra al piloto (intención de tratar):** todo cliente con al menos una decisión del motor, sea oferta o control. Sus compras cuentan desde esa primera decisión, igual en los dos grupos.
- **Comisión:** la comisión esperada a 12 meses del catálogo (`dim_ramo[comision_12m_cop]`).
- **Sorteos:** son deterministas por cliente, día y ramo (`bayes.rng`, semilla 19), así que `--check` reproduce todo byte a byte.

## 6. Con el piloto real

Los datos reales de Lulo **nunca** entran a este repositorio (`docs/DATOS_REALES.md`). Para usarlos:

1. **Ubicación:** poner los tres archivos del piloto real en una carpeta local fuera del repo, junto con una copia de los demás CSV de `powerbi/datos/`.
2. **Los tres archivos**, con las mismas columnas y `escenario = real`:
   - **`piloto_decisiones.csv`:** sale del registro del motor (cada decisión, con su `p_motor`, `grupo`, `politica`, `version_reglas`, `momento` y `ramo_regla`). `resultado` es `aceptada`, `rechazada`, `ignorada` o `control`. `p_verdad` y `p_verdad_regla` quedan vacías: solo existen en la simulación.
   - **`piloto_ventas.csv`:** las pólizas emitidas durante el piloto. `origen` es `oferta` si se compró desde la oferta y `por su cuenta` si no.
   - **`piloto_clientes.csv`:** un cliente por fila, con su primera decisión y si compró.
3. **Escenario:** en `dim_escenario.csv`, agregar la fila `real` con orden 1.
4. **Origen:** apuntar el parámetro Origen a esa carpeta y Actualizar.

Las páginas 1 a 5 muestran entonces el resultado real. Las tarjetas que solo existen en la simulación quedan en blanco.

El mismo archivo de decisiones, con `aceptada` y `rechazada`, entrena el motor: `python scripts/train_motor.py --respuestas piloto_decisiones.csv`.

## 7. Plan B: armarlo a mano

1. **Cargar los datos:** Obtener datos → Texto/CSV para cada archivo de `powerbi/datos/`. Para que los decimales con punto no se lean mal en un equipo en español, en Transformar datos usar Cambiar tipo → Usando configuración regional → Inglés (Estados Unidos) en las columnas numéricas y de fecha.
2. **Relaciones:** crearlas como en la sección 2. En Vista de modelo, arrastrar `cliente_id`, `ramo`, `fecha` y `escenario` desde las dimensiones.
3. **Medidas:** crearlas desde `powerbi/medidas.dax`. Cada una dice en qué tabla va; se pega desde el nombre.
4. **Tema:** Vista → Temas → Buscar temas → `powerbi/tema-lulo.json`.
5. **Páginas:** armarlas como en la sección 4 (lienzo de 1280 × 720) y comparar cada cifra con `vista_previa.html`.

## 8. Regenerar

```powershell
python scripts/exportar_powerbi.py           # escribe powerbi/datos, el proyecto, medidas.dax, el tema y la vista previa
python scripts/exportar_powerbi.py --check   # falla si algo de powerbi/ no coincide (como train_motor.py --check)
```

Hay que regenerar si cambian la base, las reglas, el motor, el laboratorio o `powerbi/casos.csv`.
