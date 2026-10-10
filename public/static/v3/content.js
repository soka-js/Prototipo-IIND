// Contenido del panel: ficha «Estás viendo» y desplegables de funcionalidades (v3).
import { esc, money, num, pct } from "./util.js";

export const G = (t, label) => `<button class="goto" data-goto="${t}">${label}</button>`;
export const TBL = (head, rows) => `<div class="tbl-w"><table class="tbl"><thead><tr>${head.map(h => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
export const SUB = (t, body, open) => `<details class="acc"${open ? " open" : ""}><summary><span class="s-t">${t}</span></summary><div class="acc-b">${body}</div></details>`;
export const UL = a => `<ul>${a.map(x => `<li>${x}</li>`).join("")}</ul>`;

/* ---------- ficha «Estás viendo» ---------- */
export const NOW = {
  lock: {n: "Ingreso a la app", tag: "Navegación real", what: "La puerta de entrada. Al cambiar de cliente, la app vuelve aquí.",
    how: ["Escribe cualquier clave de 4 dígitos o usa el reconocimiento facial.", "La clave no se guarda ni sale del navegador."], val: "Nada: es la entrada al recorrido."},
  home: {n: "Home", tag: "Look real + capas del motor",
    what: "La pantalla de inicio con la estructura de la app real: saludo, campana, (i), carrusel de banners, Bolsillos Flex y mapa de cajeros. Se suman tres cosas del prototipo: la Lulo Cuenta con saldo, el aviso del SOAT y los últimos movimientos. Si el motor decide «banner pasivo», la oferta aparece aquí como un banner más del carrusel y no cuenta como contacto.",
    how: ["El (+) abre las acciones de la cuenta, como en la app real.", "La campana abre Alertas; el punto rojo indica que hay sin leer.", "El carrusel se desliza; el primer banner puede ser la oferta del motor."],
    val: "Si un banner pasivo convierte sin el costo de un contacto (Ley 2300) y si el aviso del SOAT en Home basta sin push."},
  explora: {n: "Explora tus productos", tag: "Look real",
    what: "Igual a la app real: Ahorro, Inversión, Crédito y Seguros. En Seguros están los cuatro productos que hoy muestra Lulo y debajo los ramos de la base del reto, marcados «Para ti» o «Activo» según lo que decide el motor.",
    how: ["Soat abre el flujo real con Seguros Mundial.", "Cada seguro abre su ficha con «Por qué lo ves» si el motor lo recomienda."],
    val: "Qué tan visibles deben ser los seguros dentro de Explora frente a una recomendación contextual."},
  cuenta: {n: "Cuenta de ahorros", tag: "Materia prima del motor",
    what: "El extracto completo, servido por el API en páginas. Los movimientos con punto rosado alimentan una señal (nómina, transferencia fija, peaje, aerolínea, hotel, mascotas). Para los clientes de la base solo hay categoría, canal y MCC: no hay nombre de comercio.",
    how: ["Filtra con Todos, Ingresos, Gastos y Pendientes, como en la app real.", "Busca por categoría o comercio.", "Toca un movimiento para ver qué señal alimenta."],
    val: "Qué eventos están instrumentados en la app y con qué latencia (Uso_App trae la latencia por cliente)."},
  ajustes: {n: "Ajustes de cuenta", tag: "Look real", what: "Las opciones de la app real. Están para conservar la navegación; no hacen nada en el prototipo.", how: ["Toca cualquiera: muestra un aviso."], val: "Nada."},
  mov: {n: "Detalle del movimiento", tag: "Paso 1 · Detectar", what: "El detalle que ve el cliente más una anotación del prototipo con lo que lee el motor: la señal que alimenta, su regla y su fuerza.", how: ["Compara un abono de nómina, un peaje y una compra en supermercado."], val: "Qué tan explicable es cada regla para negocio y Jurídico."},
  alertas: {n: "Alertas", tag: "Paso 3 · Mostrar", what: "La bandeja con el formato real: agrupada por fecha, punto rojo para lo no leído y hora. Arriba, el banner: si el motor decidió banner pasivo, la oferta va ahí.", how: ["Toca una alerta para ir a su pantalla.", "Dispara eventos desde el panel y mira cómo llegan."], val: "Apertura por tipo de momento."},
  ayuda: {n: "Centro de ayuda", tag: "Look real", what: "La pantalla real de ayuda. Se conserva para la navegación.", how: ["Las opciones muestran un aviso."], val: "Nada."},
  perfil: {n: "Perfil y preferencias", tag: "Medición y no daño", what: "El cliente controla lo que recibe: sugerencias, avisos, anticipación y la autorización para usar sus movimientos (Ley 1581).", how: ["Apagar sugerencias deja de mostrar ofertas y cuenta como señal de daño.", "Quitar la autorización apaga Tu año y el motor deja de leer eventos."], val: "Desactivaciones y retiro de autorización: indicadores de no daño."},
  card: {n: "Tarjeta de débito", tag: "Navegación real", what: "La tarjeta con sus compras recientes.", how: ["Congela y descongela la tarjeta."], val: "Nada."},
  bolsillos: {n: "Bolsillos Flex", tag: "Señales de ahorro", what: "Los bolsillos del cliente. El tipo de bolsillo de la base (Viajes, Mascotas, Vivienda) alimenta las señales de viaje, mascotas y hogar.", how: ["Abre un bolsillo de viajes y abona."], val: "Si las metas de ahorro anticipan bien una compra de seguro."},
  bolsillo: {n: "Detalle del bolsillo", tag: "Presente · Acción real", what: "Progreso, historial y el botón para abonar. Un abono es un evento: el motor decide en el momento.", how: ["«Abonar» abre el teclado; al terminar, el motor evalúa la señal del bolsillo."], val: "Aceptación por tipo de bolsillo frente al grupo de control."},
  transfer: {n: "Transferir plata", tag: "Presente · Acción real", what: "Contactos frecuentes. Los marcados «fija» reciben transferencias fijas: transferirles es el evento que alimenta la señal de dependientes (Vida).", how: ["Elige el contacto «fija» para ver el disparo de Vida.", "Elige otro para ver que no pasa nada."], val: "Si la oferta justo después de transferir se siente oportuna o invasiva."},
  amount: {n: "Monto", tag: "Navegación real", what: "Teclado con montos sugeridos según el historial.", how: ["No deja continuar si el monto supera el saldo."], val: "Nada."},
  confirm: {n: "Confirmación", tag: "Navegación real", what: "Resumen antes de mover la plata.", how: ["«Cambiar» vuelve al paso anterior."], val: "Nada."},
  processing: {n: "Procesando", tag: "Navegación real", what: "El API convierte la acción en un movimiento y el motor decide.", how: ["Espera un segundo."], val: "Nada."},
  success: {n: "Comprobante", tag: "Paso 1 → 2", what: "La operación quedó hecha. La anotación dice lo que leyó el motor; si hay oferta llega como push o como banner según la política de contacto.", how: ["«Listo» vuelve a donde empezaste."], val: "Tiempo entre la acción y la oferta."},
  credito: {n: "Crédito", tag: "Presente · Momento único", what: "El crédito del cliente. Para los clientes de la base solo se sabe si tiene crédito activo. Un desembolso sin pago protegido es un momento único: gana la ventana por fecha límite.", how: ["Con Valentina, pide un crédito: el motor ofrece pago protegido.", "Con Sebastián o Andrés, que ya lo tienen, no es elegible."], val: "Aceptación del pago protegido en el desembolso."},
  creditReq: {n: "Solicitar crédito", tag: "Presente · Acción real", what: "Monto, plazo y cuota aproximada (tasa ilustrativa).", how: ["Continúa y confirma para disparar el evento de desembolso."], val: "Nada."},
  tcredito: {n: "Tarjeta de crédito", tag: "Look real", what: "Banner real de la tarjeta de crédito.", how: ["«Empezar» muestra un aviso."], val: "Nada."},
  cdt: {n: "CDT", tag: "Look real", what: "Los beneficios tal como aparecen en la app (captura del 2026-10-10): desde $100,000, hasta 13% E.A., renovación automática y Fogafin.", how: ["«Abrir CDT» muestra un aviso."], val: "Nada: contexto del portafolio."},
  lulox: {n: "Billetera digital", tag: "Look real", what: "Lulo X vive en Explora › Inversión, como en la app real.", how: ["Solo navegación."], val: "Nada."},
  info: {n: "Seguro Nómina Protegida", tag: "Look real", what: "Producto que ya aparece en la app. La base no trae sus datos, así que el motor no lo ofrece.", how: ["Solo informativo."], val: "Nada."},
  mapa: {n: "Mapa de cajeros", tag: "Look real", what: "Mapa ilustrativo con cajeros sin costo y con costo ($6.850, según la app real). No usa la ubicación del cliente.", how: ["Solo navegación."], val: "Nada."},
  soatIntro: {n: "SOAT con Seguros Mundial", tag: "Futuro · Recordatorio del SOAT", what: "La entrada real del SOAT en la app: aliado, beneficios y aviso de producto de un tercero.", how: ["«Cotizar seguro» abre el formulario real (propietario, placa y autorización)."], val: "Si el cliente espera comprar el SOAT en una app bancaria."},
  soatForm: {n: "Datos para la cotización", tag: "Futuro · Recordatorio del SOAT", what: "El formulario real: propietario, placa y aceptación del tratamiento de datos de Seguros Mundial. «Continuar» se habilita solo con una placa válida y la casilla marcada.", how: ["Los personajes traen su placa; para los clientes de la base escríbela (ejemplo: ABC123)."], val: "Fricción del formulario."},
  renew: {n: "Renovación o cotización", tag: "Futuro · Captura de canal", what: "Si el SOAT tiene vencimiento conocido se renueva con nueva vigencia y descuento por anticipación (hipótesis). Si es nuevo, se cotiza con la prima de referencia de la base. Si el SOAT actual es con otra aseguradora, renovarlo aquí es captura de canal.", how: ["«Pagar» descuenta el saldo y registra la renovación.", "«Recuérdamelo después» queda como pospuesto."], val: "Captura de canal: cuántos renuevan en Lulo y no por fuera."},
  paying: {n: "Procesando el pago", tag: "Futuro", what: "Estado intermedio.", how: ["Espera un segundo."], val: "Nada."},
  done: {n: "SOAT al día", tag: "Futuro", what: "Cierra el ciclo y agenda el próximo aviso.", how: ["«Ver mi protección» muestra el SOAT renovado."], val: "Nada."},
  offer: {n: "Oferta", tag: "Presente · Motor de disparadores", what: "«Por qué lo ves» sale de la evidencia del cliente que leyó el motor. El precio es la prima promedio de la base. Si el cliente no es elegible, se dice por qué y no se puede activar.", how: ["«Activar» registra la aceptación.", "«Ahora no» registra el rechazo y activa la espera de 30 días.", "«No quiero sugerencias de este tipo» cuenta como señal de daño."], val: "Aceptación incremental frente al grupo de control."},
  proteccion: {n: "Tu protección", tag: "Pestaña nueva", what: "Todo lo del cliente en un solo lugar: seguros con Lulo (voluntarios e inducidos por el crédito, por separado), lo que debe renovar, lo que el motor le sugiere con su porqué, lo que tiene con otra aseguradora, los próximos disparos agendados y por qué no se le ofrece lo demás.", how: ["Toca una sugerencia para ver la oferta.", "«Próximamente» muestra los disparos que el motor ya agendó."], val: "Si la transparencia («por qué no te ofrecemos…») sube la confianza."},
  anio: {n: "Tu año en Lulo", tag: "Pasado · Tu año en Lulo", what: "La portada del resumen. El backend calcula los capítulos con los datos del cliente y el estado de cada momento de protección lo decide el motor: para ti, activo, con otra aseguradora, pronto («te faltan N») o no aplica.", how: ["«Ver mi año» abre la historia.", "Cambia de cliente para ver otro año."], val: "Apertura, finalización y aceptación por capítulo frente a control."},
  yearLoading: {n: "Tu año en Lulo", tag: "Pasado", what: "La primera vez, la app muestra que está leyendo los movimientos.", how: ["Espera un segundo."], val: "Nada."},
  story: {n: "Tu año en Lulo", tag: "Pasado · Tu año en Lulo", what: "", how: ["Toca a la derecha para avanzar y a la izquierda para volver; en computador sirven las flechas.", "«Activar» registra la aceptación desde el capítulo."], val: "Finalización y aceptación por capítulo frente a control."},
};

/* ---------- desplegables ---------- */
export function buildAccs(S, meta) {
  const cat = meta.catalog, R = meta.rules;
  const ramosRows = cat.map(p => [`<b>${esc(p.title)}</b>`, p.partner ? esc(p.partner) : "Por definir", esc(p.price),
    p.commission_12m ? money(p.commission_12m) : "n/d", p.prior ? pct(p.prior) : "n/d", p.ev_fuerte ? money(p.ev_fuerte) : "n/d", esc(p.prior_source)]);
  return [
    {g: "La propuesta"},
    {id: "acc-resumen", k: "Resumen", t: "La propuesta en una frase", d: "Tres ideas, un motor real sobre la base del reto", open: true, b: `
      <p>Leer lo que el cliente ya hace en la app, ofrecerle el seguro correcto en el momento en que lo necesita y <b>registrar su respuesta</b>. En esta versión el motor corre de verdad sobre la base sintética del reto (600 clientes, ${num(meta.dataset.filas.movimientos)} movimientos) y sobre los tres personajes, con las mismas reglas.</p>
      <div class="flow"><span>Algo pasa en la cuenta</span><i>→</i><span>El motor lo detecta</span><i>→</i><span>Decide (elegibilidad, valor, fecha límite)</span><i>→</i><span>Push o banner</span><i>→</i><span>Queda registrado</span></div>
      <div class="two" style="margin-top:10px"><div class="box"><b>Pasado</b>Tu año en Lulo, calculado con los datos.</div><div class="box"><b>Presente</b>Motor de disparadores en tiempo real.</div><div class="box"><b>Futuro</b>SOAT y disparos agendados.</div><div class="box"><b>Siempre</b>Registro con versión de reglas y grupo de control.</div></div>`},
    {id: "acc-v3", k: "Novedades", t: "Qué cambió frente a la versión que vio el cliente", d: "Look real, motor real y datos reales del reto", open: true, b: `
      ${UL(["<b>Look de la app real</b>: navegación Home · Explora · (+), colores tomados de las capturas, Explora con Ahorro, Inversión, Crédito y Seguros, Alertas, Ayuda, mapa de cajeros y el flujo real del SOAT con Seguros Mundial.",
        "<b>Pestañas que suman</b>: Tu año y Tu protección en la barra inferior.",
        "<b>Motor real</b>: lee la base del reto, valida la calidad, decide con valor esperado y fecha límite, respeta el tope de contactos, la fatiga, la latencia y 7 días entre push, y asigna un grupo de control por hash.",
        "<b>600 clientes más los 3 personajes</b>, con el mismo motor. Una prueba demuestra que el motor no usa nombres de comercios para decidir.",
        "<b>La versión anterior sigue disponible</b> en <a href=\"/v2\" target=\"_blank\" rel=\"noopener\">/v2</a>."])}`},
    {id: "acc-navegar", k: "Prototipo", t: "Cómo navegar", d: "Todo lo que tocas funciona y lo lee el motor", b: `
      ${TBL(["Flujo", "Dónde", "Qué hace el motor"], [
        ["Transferir a un contacto «fija»", "(+) → Transferir plata", "Señal de dependientes → Vida"],
        ["Abonar a un bolsillo de viajes, mascotas o vivienda", "Home → Bolsillos Flex", "Señal de viaje, mascotas u hogar"],
        ["Pedir un crédito", "Explora → Crédito", "Sin pago protegido lo ofrece (momento único)"],
        ["Renovar o cotizar el SOAT", "Explora → Seguros → Soat", "Renovación o captura de canal"],
        ["Ver por qué no te ofrecen algo", "Tu protección", "Muestra señal débil, no elegible o en espera"],
        ["Revisar un movimiento", "Lulo Cuenta → movimiento", "Muestra la señal que alimenta"]])}
      <p>Enlaces directos: <code>/#/tu-ano</code>, <code>/#/proteccion</code>, <code>/#/explora/seguros</code>, <code>/?cliente=C00002</code>.</p>
      ${G("home", "Ir al inicio")}${G("explora:seguros", "Ver Seguros")}`},
    {id: "acc-ramos", k: "Datos", t: "Los ramos y su valor esperado", d: "Cada cifra sale de la base; lo que no, se marca como supuesto", b: `
      ${TBL(["Ramo", "Aliado", "Prima", "Comisión 12 m", "Conv. previa", "VE fuerte", "Origen"], ramosRows)}
      <p>Valor esperado = conversión previa (ventas / impactados de Campanas_Previas) × comisión a 12 meses (prima × comisión × meses esperados por persistencia) × fuerza de la señal (${Object.entries(R.STRENGTH_MULT).map(([k, v]) => `${k} ${String(v).replace(".", ",")}`).join(", ")}).</p>`},
    {id: "acc-habitos", k: "Datos", t: "Las señales que lee el motor", d: "Qué movimiento anticipa cada ramo en la base", b: `
      ${TBL(["Ramo", "Señal en la base", "Regla v1.1"], [
        ["Desempleo", "Abono recurrente (MCC 0000)", `Empleado con ${R.DESEMPLEO_MIN_STREAK}+ abonos seguidos; fuerte con crédito activo`],
        ["Vida", "Transferencia fija a tercero (MCC 0001)", `${R.VIDA_MIN_MONTHS}+ meses distintos; fuerte con ingreso recurrente`],
        ["Viajes", "Aerolíneas (4511), hoteles (7011), bolsillo Viajes", `Compra en ${R.VIAJES_PURCHASE_DAYS} días o ${R.VIAJES_POCKET_MIN}+ abonos; fuerte con ambas`],
        ["Mascotas", "Tiendas de mascotas (5995), bolsillo Mascotas", `${R.MASCOTAS_SPEND_MIN}+ compras o bolsillo; fuerte con ambas`],
        ["Hogar", "Bolsillo Vivienda", `${R.HOGAR_POCKET_MIN}+ abonos`],
        ["SOAT", "Peajes (4784) y vencimiento del SOAT", `Vence en ${R.SOAT_REMINDER_DAYS} días o ${R.SOAT_TOLLS_MEDIA}+ peajes (fuerte ${R.SOAT_TOLLS_FUERTE}+)`],
        ["Pago protegido", "Desembolso de crédito", "Momento único, sin pago protegido"]])}
      <p>La base no trae combustible, nombre de comercio ni a quién se transfiere: las reglas solo usan fecha, monto, canal, categoría y MCC.</p>`},
    {id: "acc-cliente", k: "Retroalimentación", t: "Lo que dijo el cliente y cómo lo recoge esta versión", d: "Datos reales, modelos con esos datos e impacto por momento", b: `
      <div class="two"><div class="box"><b>Lo que valoraron</b>${UL(["El prototipo es interactivo.", "Las tres soluciones responden al desafío.", "Las ofertas aparecen en momentos reales del cliente."])}</div>
      <div class="box"><b>Lo que les preocupó</b>${UL(["Refinar con los datos de Lulo Bank.", "Construir los modelos con esos datos.", "Confirmar qué momentos tienen más impacto."])}</div></div>
      <h5>Cómo lo recoge v3</h5>${UL(["El motor corre sobre la base que entregaron, con su calidad validada y documentada.", "Se probó si tener un seguro se relaciona con su señal: no (AUC de 0,435 a 0,512). Por eso el motor usa reglas explícitas y valor esperado, y el grupo de control produce las etiquetas para entrenar un modelo después.", "El registro guarda cada decisión con versión de reglas, grupo y canal: es la base para medir qué momento tiene más impacto."])}`},
    {id: "acc-problemas", k: "Contexto", t: "Dos problemáticas, no una", d: "Se parecen, pero se miden distinto", b: `
      <div class="two"><div class="box"><b>1. Ampliar la oferta de seguros</b>${UL(["Hay productos, pero nadie los ofrece: el modelo es de tirón.", "Vida solo existe atado al crédito y desempleo no tiene un momento propio.", "La comisión no consume capital regulatorio ni requiere fondeo."])}<p style="margin-top:6px"><b>Se mide en</b> pólizas por cliente y renovación.</p></div>
      <div class="box"><b>2. Ampliar el mercado de Lulo Bank</b>${UL(["650.000 clientes activos, saldo promedio de $1,7 millones: es cuenta de movimiento, no la principal.", "La tasa (7,84% E.A.) dejó de diferenciar frente a Nu, Ban100, Finandina y Contactar.", "El SOAT responde a una necesidad que el cliente ya tiene fuera del banco."])}<p style="margin-top:6px"><b>Se mide en</b> clientes nuevos y profundidad de la relación.</p></div></div>`},
    {id: "acc-brecha", k: "Contexto", t: "La brecha entre el cliente que hay y el que se quiere", d: "El perfil juega en contra, el comportamiento a favor", b: `
      ${UL(["El tenedor típico de seguro de vida es mayor y lleva más años con su banco: 44,5 frente a 41,4 años de edad y 11,98 frente a 9,11 años de relación (Boustani et al., 2024).", "Los mismos autores muestran que la conducta supera al perfil: el poder predictivo pasa de 0,847 con demografía sola a 0,908 con datos transaccionales.", "Conclusión de diseño: la brecha se cierra con lo que el cliente hace, no con lo que el cliente es."])}`},

    {g: "Las tres ideas"},
    {id: "acc-idea1", k: "Pasado", t: "Tu año en Lulo", d: "Calculado con los datos de cada cliente", b: `
      ${SUB("Qué hace", UL(["Convierte 12 meses de movimientos en una historia con un capítulo por momento.", "Cada momento de protección muestra lo que decidió el motor: para ti, activo, con otra aseguradora, pronto («te faltan N abonos») o no aplica.", "Corre para los 600 clientes: si un cliente no recibe ingresos en Lulo, «Tu dinero» cuenta lo que salió."]), true)}
      ${SUB("Capítulos de este cliente", TBL(["Capítulo", "Cifra", "Momento"], (S.chapters || []).map(c => [c.name, c.stats ? c.stats.map(s => `${esc(s.big)} ${esc(s.line)}`).join(" · ") : "Se calcula en vivo", c.protect ? `${esc(c.protect.title)} · ${c.protect.state}` : c.ask ? "Pregunta" : "—"])))}
      ${SUB("Cómo se mide", UL(["Apertura y finalización.", "Aceptación por capítulo frente al grupo de control.", "Respuestas a «¿Sabías que tenías esta protección?»."]))}
      ${G("anio", "Ver Tu año")}${G("story:intro", "Abrir la historia")}`},
    {id: "acc-idea2", k: "Presente", t: "Motor de disparadores", d: `Reglas ${meta.rules_version}: valor esperado, fecha límite y política de contacto`, b: `
      ${SUB("Compuertas, en orden", `<div class="flow"><span>Autorización</span><i>→</i><span>Señal</span><i>→</i><span>Elegibilidad y exclusiones</span><i>→</i><span>Fecha límite y valor esperado</span><i>→</i><span>Control</span><i>→</i><span>Preferencias</span><i>→</i><span>Canal</span><i>→</i><span>Ventana</span></div>`, true)}
      ${SUB("Política de contacto", UL(["Tope: 4 contactos en 30 días (Uso_App).", `Mínimo ${R.MIN_DAYS_BETWEEN_PUSH} días entre dos push.`, `Fatiga: ${R.FATIGUE_MIN_IGNORED}+ notificaciones ignoradas y el doble de las abiertas.`, "Latencia «Mismo día»: no sirve para disparo inmediato.", "En cualquiera de esos casos la oferta va como banner pasivo, que según el supuesto de la hoja Jurídico no es contacto comercial."]))}
      ${SUB("Elegibilidad", UL(["Edad y ocupación de la hoja Elegibilidad; el rango «56+» se excluye de Desempleo (≤60) y Vida (≤65).", `Desempleo pide antigüedad laboral: se aproxima con ${R.DESEMPLEO_MIN_STREAK} abonos seguidos en Lulo.`, "Seguros externos vigentes no se ofrecen como nuevos; el SOAT externo por vencer se ofrece para renovar en Lulo (captura de canal). Si el externo venció, cuenta como interés fuerte.", `Lo mostrado o rechazado espera ${R.COOLDOWN_DAYS} días.`]))}
      ${SUB("Cómo se mide", `<p><b>Aceptación incremental</b>: tratamiento menos control, por ramo y por momento. El control (${R.CONTROL_PCT} %) se asigna por hash del id, así que siempre es el mismo cliente.</p>`)}
      ${G("motor", "Abrir el motor en vivo")}`},
    {id: "acc-idea3", k: "Futuro", t: "SOAT y disparos agendados", d: "Usar una fecha conocida para abrir la conversación", b: `
      ${UL(["El flujo es el de la app real con Seguros Mundial: cotizar, placa, autorización y pago.", "Con vencimiento conocido: renovación con descuento por anticipación (hipótesis). Si el SOAT es con otra aseguradora: captura de canal.", "El motor agenda: el aviso del SOAT, el seguro de desempleo al sexto abono, Vida al tercer mes de transferencias y los externos que vencen.", "Usa el «viaje en el tiempo» del panel para ver cómo se abren las ventanas de SOAT de los clientes de la base."])}
      ${G("explora:seguros", "Ver Seguros")}`},

    {g: "Cómo se sostiene"},
    {id: "acc-arquitectura", k: "Tecnología", t: "Cómo está construido", d: "Python (FastAPI), datos validados y despliegue en Vercel", b: `
      ${TBL(["Pieza", "Qué hace", "Dónde"], [
        ["Ingesta", "Valida el Excel y escribe CSV con manifiesto y hashes", "<code>scripts/ingest_reto.py</code>"],
        ["Esquema y carga", "Base y personajes en el mismo esquema", "<code>core/schema.py</code> · <code>core/store.py</code>"],
        ["Catálogo", "Prima, comisión, persistencia y conversión de la base", "<code>core/catalog.py</code>"],
        ["Reglas", `Parámetros versionados (${meta.rules_version})`, "<code>core/rules.py</code>"],
        ["Señales y elegibilidad", "Fuerza, evidencia y requisitos", "<code>core/signals.py</code> · <code>core/eligibility.py</code>"],
        ["Decisión", "Compuertas, control, canal y cola", "<code>core/engine.py</code>"],
        ["Backtest", "Recorre el año y verifica invariantes", "<code>core/backtest.py</code>"],
        ["API", "Rutas v3 para la app y el panel", "<code>/api/v3</code> · <a href=\"/docs\" target=\"_blank\" rel=\"noopener\">/docs</a>"]])}
      <p>CLI: <code>python -m lulo_app.core campana</code>, <code>cliente C00002</code>, <code>backtest</code>, <code>catalogo</code>, <code>reglas</code>.</p>`},
    {id: "acc-supuestos", k: "Supuestos", kp: true, t: "Supuestos y límites", d: "Lo que es sintético o hipótesis", b: `
      ${UL(["La base es 100% sintética y académica: sus cifras no son métricas de Lulo Bank.", "La fuerza de la señal (1,0 / 0,6 / 0) es una hipótesis: no hay resultados por cliente para estimarla; se mide con el grupo de control.", "Hogar no tiene campaña previa: se usa la menor conversión observada.", "Pago protegido no está en la base: se ofrece solo al desembolsar, sin valor esperado.", "El uso de la app de los personajes es supuesto (la base no lo trae).", "El descuento del SOAT es una hipótesis: la tarifa es regulada.", "Si una recomendación in-app es contacto bajo la Ley 2300 se tomó del supuesto de la hoja Jurídico; hay que validarlo."])}`},
  ];
}
