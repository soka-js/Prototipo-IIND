# Casos reales: quién usó métodos como los del prototipo y qué pasó

El prototipo todavía no puede decir si el motor convierte ofertas en ventas: la base del reto no trae respuestas a ofertas, y eso solo lo dirá un piloto con grupo de control (M6, `docs/MODELOS.md`). Lo que sí se puede mostrar es qué les pasó a empresas reales que usaron los mismos métodos. Este documento reúne 20 casos con cifras de fuentes públicas: 7 éxitos, 1 sin efecto, 6 mixtos y 6 fracasos; 15 con confianza alta y 5 con confianza media. Cada caso aparece en la página «Casos reales» del dashboard (`powerbi/casos.csv`).

**Cómo se verificó.** Las cifras salen de la fuente enlazada: regulador, documento ante la SEC, informe de la empresa o artículo académico. Desde el entorno donde se armó no se podían abrir las páginas completas, así que cada cifra se confirmó con el texto de la fuente que devuelve el buscador. Además, cuatro cifras se revisaron una segunda vez por separado: el PPI de la FCA, la revisión de la Superfinanciera, LinUCB de Yahoo! y Zillow. La FCA dice «más del 80 %» de reclamos aceptados, no «87 %», así que esa cifra no se usa. Antes de citar un caso en la entrega, conviene abrir el enlace.

**Confianza.**
- **Alta:** la cifra sale de la fuente primaria.
- **Media:** prensa o un resumen que cita la fuente, o una cifra que reporta un proveedor.
- Lo que no se pudo confirmar quedó fuera (lista al final).

## Los 20 casos

| # | Empresa | Método | Qué parte del prototipo respalda | Resultado | Cifra | Confianza |
|---|---|---|---|---|---|---|
| 1 | Commonwealth Bank of Australia (2019–2023) | Próxima mejor conversación en tiempo real | Eventos y próxima mejor oferta | Éxito | Benefits finder conectó a los clientes con A$1.000 millones en subsidios y descuentos; más de 2,2 millones de reclamaciones | Alta |
| 2 | DBS Bank (2024) | Nudges personalizados con IA | Eventos y próxima mejor oferta | Mixto | Más de 1.200 millones de nudges y S$750 millones de valor de la IA; los usuarios estaban casi 3 veces más asegurados que los no usuarios (comparación sin control) | Alta |
| 3 | Nubank · Nu Vida (2020–2024) | Seguro simple dentro de la app | Seguro embebido | Éxito | 2 millones de pólizas activas (jun-2024); cerca de la mitad compraba su primer seguro de vida | Alta |
| 4 | Lemonade (2020–2024) | Aseguradora 100 % digital | Seguro embebido | Mixto | Pérdidas netas de US$122 a 298 millones por año | Alta |
| 5 | Tesla Insurance (2023) | Seguro en el momento de la compra | Seguro embebido | Mixto | Primas de US$517,6 millones en 2023 (255,5 en 2022) | Media |
| 6 | Netflix (2015) | Recomendador validado con A/B | Grupo de control | Éxito | Más de US$1.000 millones al año ahorrados en retención | Media |
| 7 | Booking.com (2019) | 150 modelos probados con experimentos | Grupo de control | Mixto | «El rendimiento del modelo no es el rendimiento del negocio» | Media |
| 8 | Yahoo! · LinUCB (2010) | Bandido contextual | Aprendizaje con exploración | Éxito | 12,5 % más clics que un bandido sin contexto | Alta |
| 9 | Microsoft Bing · AdPredictor (2009) | Probit bayesiano en línea | Aprendizaje con exploración | Éxito | Atendía el 100 % del tráfico de anuncios patrocinados | Alta |
| 10 | Microsoft Decision Service (2016) | Bandidos con registro de exploración | Aprendizaje con exploración | Mixto | 25 a 30 % más clics; el servicio comercial se retiró en 2026 | Alta |
| 11 | eBay (2012–2015) | Apagar anuncios de marca, con control | Grupo de control | Sin efecto | Sin beneficio medible a corto plazo | Alta |
| 12 | Facebook (2019) | Experimentos frente a métodos observacionales | Grupo de control | Mixto | 15 experimentos: lo observacional no reproduce el efecto | Alta |
| 13 | Microsoft Bing · titular (2012) | Prueba A/B de un texto | Grupo de control | Éxito | +12 % de ingresos, más de US$100 millones al año | Alta |
| 14 | U.S. Bank (2007–2010) | Modelos de uplift | Grupo de control | Éxito | Hasta la mitad de una campaña llegaba a quien compraría igual | Media |
| 15 | Wells Fargo (2002–2020) | Metas agresivas de venta cruzada | Autorización y contacto | Fracaso | US$100 millones de multa (2016) y US$3.000 millones (2020) | Alta |
| 16 | PPI, Reino Unido (1990–2020) | Seguro vendido con el crédito | Autorización y contacto | Fracaso | Más de 32,4 millones de reclamos y £38.000 millones pagados | Alta |
| 17 | Bancaseguros en Colombia (2022–2025) | Revisión de la Superfinanciera | Autorización y contacto | Fracaso | Cobros y renovaciones de pólizas sin autorización | Alta |
| 18 | Target (2012) | Puntaje de un evento de vida | Eventos y próxima mejor oferta | Fracaso | Unos 25 productos bastaban para estimar un embarazo | Media |
| 19 | Zillow Offers (2018–2021) | Un modelo de precios decidía las compras | El modelo solo ordena | Fracaso | Rebaja de US$304,4 millones y cierre del negocio | Alta |
| 20 | Google Flu Trends (2008–2015) | Predicción con búsquedas | El modelo solo ordena | Fracaso | Más del doble de lo que midieron los CDC | Alta |

Enlaces, cifras completas y lección de cada caso: `powerbi/casos.csv`.

## Seis lecciones y dónde están en el prototipo

1. **La diferencia frente al control es la única prueba de que una oferta vende.**
   - **Casos:** eBay, Facebook, Booking y DBS.
   - **Qué enseñan:** comparar usuarios con no usuarios, o confiar en un buen backtest, sobreestima el efecto.
   - **En el prototipo:** el grupo de control del 10 % no depende del modelo (`experiment.py`).
   - **En el dashboard:** la cifra principal es la diferencia entre tratamiento y control, con su intervalo de 95 %, y no la conversión de las ofertas.
2. **Incrementalidad no es conversión.**
   - **Casos:** U.S. Bank y eBay. Ofrecer a quien compraría igual gasta contactos sin efecto.
   - **En el dashboard:** la página Resumen separa las ventas por oferta de las compras por su cuenta, que existen en los dos grupos.
   - **Pendiente:** con respuestas reales se puede estimar el efecto por segmento. Usarlo para decidir es un cambio grande que se consulta con SOKA.
3. **Consentimiento, transparencia y salida fácil, sobre todo con el seguro atado al crédito.**
   - **Casos:** Wells Fargo, el PPI y la revisión de la Superfinanciera fallaron justo ahí.
   - **Lo que ya cumple el prototipo:**
     - no lee movimientos sin autorización (Ley 1581);
     - respeta el tope de contactos y la espera entre push (Ley 2300);
     - separa Vida grupo deudor de Vida voluntario.
   - **En el dashboard:** la página Contacto muestra las invariantes del backtest en 0 violaciones.
4. **El momento justo tiene un límite.**
   - **Caso:** Target muestra que un evento sensible se percibe como vigilancia.
   - **En el prototipo:** el motor solo usa campos canónicos (fecha, monto, canal, categoría y MCC), nunca nombres de comercios, y le dice al cliente por qué ve la oferta.
5. **Explorar sí, pero acotado y registrado.**
   - **Casos:** Yahoo!, AdPredictor y Decision Service muestran que el aprendizaje en línea con exploración funciona, sobre todo con pocos datos.
   - **En el prototipo:**
     - el motor es un probit bayesiano en línea, la misma familia que AdPredictor;
     - explora con Thompson solo en el 10 % del tratamiento;
     - guarda la probabilidad con la que decidió (`p_motor`).
   - **En el dashboard:** la página «¿El modelo acierta?» vigila la calibración, porque el valor esperado es P × comisión.
6. **Los modelos fallan cuando cambia el entorno, y vender no es ganar.**
   - **Casos:** Zillow y Google Flu Trends cayeron por cambios del entorno y sobreajuste. Lemonade y Tesla muestran que el volumen no asegura rentabilidad.
   - **En el prototipo:** el modelo solo ordena lo que las compuertas permiten, y el reentrenamiento es reproducible (`train_motor.py --check`).
   - **Pendiente para el piloto real:** medir también cancelaciones y persistencia, no solo aceptación.

## Lo que quedó fuera por no poder confirmarlo

- El «35 % de las ventas de Amazon viene de recomendaciones»: no apareció en una fuente primaria.
- El «−63 %» de retorno de eBay y el coeficiente exacto de Booking que a veces se citan.
- Las cifras de la campaña de Obama en 2012.
- El porcentaje de clientes que pagan más con Progressive Snapshot.
- Las cifras de pólizas de Nequi, Bancolombia y Mercado Pago: no se encontró una fuente con fecha.
- Las cifras de proveedor sobre U.S. Bank y Telenor (300 % de venta cruzada, ROI 11 veces): las fuentes no coinciden.
- La multa de COP 150 millones al Banco de Bogotá por Vida grupo deudor: solo prensa, sin la resolución publicada.
