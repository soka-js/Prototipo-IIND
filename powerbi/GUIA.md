# Dashboard de impacto · Power BI

**Prototipo académico · base sintética · resultados simulados.** Es un dashboard ejecutivo de 3 páginas que responde una pregunta: **¿qué podría generar el motor?**

La base del reto no trae respuestas a ofertas, así que nadie sabe todavía si el motor vende. Por eso el dashboard muestra un **piloto simulado**:
- el motor de verdad decide semana a semana sobre los 600 clientes, con su grupo sin ofertas (el 10 % sorteado);
- solo se inventan las respuestas de los clientes, con la verdad del laboratorio.

Todas las páginas tienen arriba un selector con dos escenarios. El rango entre los dos es lo honesto para presentar:
- **Optimista:** el motor ve más que la regla.
- **Conservador:** la regla ya era la correcta.

## 1. Abrirlo

**Para el cliente: https://prototipo-iind.vercel.app/dashboard.** Es el mismo dashboard, con las mismas 3 páginas, el mismo selector de escenario y las mismas cifras, como una página del prototipo. Se abre en el navegador o el celular, sin Power BI y sin cargar datos. El enlace puede abrir una página y un escenario concretos, por ejemplo `/dashboard#pagina=valor&escenario=conservador`. Lo genera `scripts/powerbi_web.py` desde las mismas tablas que el `.pbip`, así que las dos versiones no se pueden separar.

**En Power BI (para el equipo o quien tenga Power BI):**


1. En Power BI Desktop: Archivo → Abrir → `powerbi/Lulo_Impacto.pbip`.
   - Si no reconoce el formato: Archivo → Opciones → Características en versión preliminar → activar «Guardar como proyecto de Power BI (.pbip)» y reiniciar.
2. Inicio → **Actualizar**. Si la primera vez sale un error de «referencia cíclica», es porque el modelo todavía se estaba abriendo: cerrar el aviso y Actualizar otra vez.

Los datos vienen **dentro del modelo**: no hay que configurar ningún origen ni dar credenciales, y funciona sin internet.

**Para entregarlo como un solo archivo:** con el proyecto abierto y actualizado, Archivo → **Guardar como** → *Archivo de Power BI (.pbix)*. Ese `.pbix` lleva el diseño y los datos, y se abre en cualquier Power BI Desktop sin esta carpeta. Los `.pbix` no se suben al repositorio (`.gitignore`).

**Sin Power BI:** abrir `powerbi/vista_previa.html` en el navegador. Son las mismas 3 páginas, con el mismo selector, y cada cifra se calcula con la misma definición que la medida del mismo nombre. Si una cifra de Power BI no coincide con la vista previa, la medida quedó mal.

> El proyecto se genera con código y no se ha abierto todavía en Power BI Desktop. Si una página sale con un visual roto, se arregla en el panel de campos con lo que dice la sección 3. Si no abre, está el plan B (sección 6).

## 2. Qué dice cada página

| Página | Mensaje | Optimista | Conservador |
|---|---|---|---|
| **Impacto** | Más clientes compran con las ofertas | +21,0 pp (intervalo de 95 %: +13,7 a +28,2), 92 clientes nuevos con seguro, $6,9 M de comisión adicional a 12 meses | +15,0 pp (+7,9 a +22,1), 66 clientes, $4,9 M |
| | ¿Las ofertas venden? | Sí: el intervalo no toca el cero | Sí |
| | Comisión por cliente contactado | $15.833, o $15,8 M por cada 1.000 clientes contactados | $11.245, o $11,2 M |
| **Qué y a quién** | Qué seguros venden y a quién | 99 pólizas por las ofertas (77 % de las ventas); aceptan el 10,2 % de las ofertas que ven. Desempleo y Vida dejan más comisión. «Con mascota» acepta más (15,0 %) | 70 pólizas (70 %); aceptan el 7,1 %. «Con mascota» sigue arriba (8,8 %) |
| **Bajo control** | Crece sin romper reglas | 0 violaciones en 21.600 decisiones del backtest, máximo 4 push en 30 días, 84 clientes sin autorización nunca contactados. Laboratorio: +10,2 % de comisión por oferta frente a la regla | Laboratorio: −1,0 % (si la regla ya era la correcta, el motor casi no pierde) |

**Cómo defender cada cifra:**

1. **La cifra principal es la diferencia frente al grupo sin ofertas**, no la conversión de las ofertas. Los dos grupos compran también por su cuenta; solo la diferencia dice cuánto venden las ofertas.
2. **El intervalo de 95 % es la respuesta a «¿y si es suerte?».** Si no toca el cero, la diferencia no es azar. En los dos escenarios no lo toca.
3. **La muestra es chica, y lo decimos.** El grupo sin ofertas tiene 45 clientes y 2 compran. Por eso no se muestra «cuántas veces más» (con 3 compras en vez de 2 cambiaría mucho) y se presenta el rango entre los dos escenarios. El piloto real necesita la base completa de Lulo.
4. **«Por cada 1.000 clientes contactados» es una regla de tres, no una meta:** la comisión por cliente contactado × 1.000. No supone cuántos clientes tiene Lulo.
5. **El laboratorio muestra que el método aprende, no cuánto venderá Lulo.** Es una verdad simulada sobre los clientes de la base.
6. **Nada de esto son métricas de Lulo Bank:** la base es 100 % sintética y académica.

## 3. Las páginas por dentro

Todas llevan arriba el título, la etiqueta del prototipo y el selector `escenario[nombre]`. Las medidas leen el escenario elegido; no hacen falta relaciones entre tablas.

| Página | Visuales (campos) |
|---|---|
| **Impacto** | Tarjetas: [más clientes compran con las ofertas], [intervalo de 95 % de la diferencia], [clientes con seguro gracias a las ofertas], [comisión adicional a 12 meses]. Líneas: eje `curva[semana]`, valor [Clientes que ya compraron], leyenda `curva[grupo]`. Tarjetas: [¿Las ofertas venden?], [comisión por cliente contactado], [por cada 1.000 clientes contactados (proyección lineal)]. |
| **Qué y a quién** | Tarjetas: [pólizas vendidas por las ofertas], [de las ventas vino de una oferta], [aceptan la oferta que ven], [comisión por cliente contactado]. Barras: `ramo[seguro]` × [Comisión de las ofertas]. Columnas: `segmento[segmento]` × [Aceptación por segmento]. Anillo: `origen[origen]` × [Pólizas]. |
| **Bajo control** | Tarjetas: [violaciones de las reglas], [push máximo a un cliente en 30 días], [sin autorización: nunca contactados], [laboratorio: más comisión que la regla]. Tabla: `reglas[regla]`, `reglas[violaciones]`. Líneas: eje `laboratorio[ronda]`, valor [Comisión por oferta], leyenda `laboratorio[politica]`. |

**Colores:** los de la app. Lima `#E8FF00` para el motor y lo que se quiere mirar; gris azulado `#647B9A` para la comparación (sin ofertas, la regla). Fondo `#0B1430`, tarjetas `#131E3D`.

## 4. De dónde sale cada cifra

Las tablas del dashboard (`powerbi/tablas`, las mismas que van dentro del modelo) se calculan con `scripts/powerbi_modelo.py` a partir de las tablas de detalle de `powerbi/datos`:

| Tabla del dashboard | Sale de |
|---|---|
| `indicadores`, `curva`, `ramo`, `segmento`, `origen` | El piloto simulado: `piloto_clientes`, `piloto_decisiones` y `piloto_ventas` (con `dim_cliente` y `dim_ramo`). |
| `reglas`, `control` | El backtest del motor (`motor_invariantes`, `motor_backtest`) y la autorización de datos de `dim_cliente`. |
| `laboratorio`, `laboratorio_resumen` | `lulo_app/ml/laboratorio.json` (`lab_series`, `lab_resumen`): motor, regla, oráculo y al azar. |
| `escenario` | Los dos mundos del laboratorio (`dim_escenario`). |

Las fórmulas están en `medidas.dax`, con una línea que dice qué es cada una. Los textos con cifras (subtítulos y notas al pie) se escriben con los mismos datos. `tests/test_powerbi.py` vuelve a contar cada número desde el detalle por otro camino.

**Tipos de datos en `powerbi/datos`:**
- **Base del reto** (`base_*`, `dim_cliente`, `dim_ramo`): tal cual la base.
- **Motor** (`motor_*`): lo que decide el motor real (reglas v2.1).
- **Simulado** (`piloto_*`): el motor y sus decisiones son reales; las respuestas son inventadas. Tiene el formato de los datos reales (`docs/DATOS_REALES.md`).
- **Laboratorio** (`lab_*`) y **casos reales** (`casos`, 20 empresas con fuente, en `docs/CASOS.md`).

## 5. Cómo se simuló el piloto (supuestos)

- **Periodo:** la base se recorre semana a semana, del 30-ene-2026 (tres meses de historia, como el backtest) al corte del 8-oct-2026: 36 evaluaciones de los 600 clientes.
- **Motor:** el de la app, sin cambios. Autorización, elegibilidad, capacidad de pago, espera de 30 días por ramo, tope de push, 7 días entre push, grupo sin ofertas del 10 % por hash y exploración del 10 %. Lo que el cliente compró deja de ofrecerse.
- **Si el cliente ve la oferta:** con el alcance que el motor calcula para el canal (apertura del push del cliente, o alcance de la campaña de banner).
- **Si la acepta:** con la verdad del laboratorio (`scripts/laboratorio.py`):
  - **optimista («señal»):** efectos que la regla no ve, momento × 1,6, señal media × 0,45 y apetito propio por cliente;
  - **conservador («regla correcta»):** conversión de la campaña previa × 0,6 si la señal es media.
- **Compras por su cuenta**, sin oferta y en los dos grupos: cada semana, al ritmo con que estos clientes le compraron a otras aseguradoras en el año de la base (Pagos_Seguros). Desempleo y Viajes quedan en 0 porque la base no trae pagos externos de esos ramos.
- **Quién entra al piloto:** todo cliente con al menos una decisión del motor. Sus compras cuentan desde esa primera decisión, igual en los dos grupos.
- **Comisión:** la comisión esperada a 12 meses del catálogo de la base.
- **Sorteos:** deterministas (semilla 19). El grupo sin ofertas es idéntico en los dos escenarios, y `--check` reproduce todo byte a byte.

## 6. Plan B: armarlo a mano (unos 30 minutos)

1. **Cargar los datos:** Obtener datos → Texto/CSV con cada archivo de `powerbi/tablas/`. Para los números con punto: Transformar → Cambiar tipo → Usando configuración regional → Inglés (Estados Unidos).
2. **Medidas:** crearlas desde `medidas.dax`. Cada una dice en qué tabla va. No hacen falta relaciones: cada medida filtra el escenario elegido.
3. **Tema:** Vista → Temas → Buscar temas → `powerbi/tema-lulo-impacto.json`.
4. **Páginas:** armarlas como en la sección 3 y en la vista previa (lienzo de 1280 × 720), y comparar cada cifra con `vista_previa.html`.

## 7. Regenerar

```powershell
python scripts/exportar_powerbi.py           # escribe powerbi/: datos/, tablas/, el proyecto, medidas.dax, el tema y la vista previa
python scripts/exportar_powerbi.py --check   # falla si algo de powerbi/ no coincide con lo que se genera hoy
```

Hay que regenerar si cambian la base, las reglas, el motor, el laboratorio o `powerbi/casos.csv`. `GUIA.md` y `casos.csv` se escriben a mano; todo lo demás de `powerbi/` lo genera el script.
