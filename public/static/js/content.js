// Contenido del panel: desplegables de funcionalidades y la ficha «Estás viendo».
import { esc } from "./util.js";

export const G = (t, label) => `<button class="goto" data-goto="${t}">${label}</button>`;
export const TBL = (head, rows) => `<div class="tbl-w"><table class="tbl"><thead><tr>${head.map(h => `<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.map(r => `<tr>${r.map(c => `<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
export const SUB = (t, body, open) => `<details class="acc"${open ? " open" : ""}><summary><span class="s-t">${t}</span></summary><div class="acc-b">${body}</div></details>`;
export const UL = a => `<ul>${a.map(x => `<li>${x}</li>`).join("")}</ul>`;

/* ---------- ficha «Estás viendo» ---------- */
export const NOW = {
  lock: {n: "Ingreso a la app", tag: "Navegación real",
    what: "Así abre el cliente su app: clave de 4 dígitos o Face ID. Al cambiar de cliente simulado, la app vuelve a esta pantalla.",
    how: ["Escribe cualquier clave de 4 dígitos.", "El ícono de cara o «Ingresar con Face ID» entra de una vez."],
    val: "Nada: es la puerta de entrada al recorrido."},
  home: {n: "Inicio", tag: "Futuro · Recordatorio del SOAT",
    what: "La primera pantalla del cliente: saldo, tarjeta, accesos rápidos, el aviso del SOAT y la tarjeta de Tu año. Todo sale del año de movimientos simulados del cliente.",
    how: ["La campana abre las notificaciones; el número son las no leídas.", "El ojo oculta el saldo.", "Enviar, Bre-B, Cajitas y Crédito abren flujos completos: lo que hagas ahí lo lee el motor.", "El aviso del SOAT cambia según los días de anticipación que elijas en Perfil."],
    val: "Si el cliente espera comprar el SOAT en una app bancaria y si el aviso en Inicio basta sin notificación push."},
  movs: {n: "Movimientos", tag: "Materia prima del motor",
    what: "El extracto completo del año, servido por el API en páginas. Cada fila es una señal posible: peajes y combustible anticipan el SOAT, abonos del mismo originador anticipan nómina, transferencias fijas anticipan vida.",
    how: ["Busca por comercio o categoría («peaje», «Rappi», «nómina»).", "Filtra por tipo con los chips.", "Baja hasta el final: la lista carga más movimientos sola.", "Toca un movimiento para ver qué señal alimenta."],
    val: "Qué eventos están instrumentados hoy en la app y con qué latencia llegan (sesión con Analítica)."},
  mov: {n: "Detalle del movimiento", tag: "Paso 1 · Detectar",
    what: "El detalle que ve el cliente, más una anotación del prototipo (en rosa) con lo que lee el motor: qué señal alimenta este movimiento, su fuerza y la regla que la define.",
    how: ["Compara un peaje, una cuota y una compra en Rappi: solo los dos primeros alimentan señales."],
    val: "Qué tan explicable resulta la regla para el equipo de negocio y para Jurídico."},
  notifs: {n: "Notificaciones", tag: "Paso 3 · Mostrar",
    what: "La bandeja del cliente. Aquí quedan los avisos del SOAT, Tu año y cada oferta que el motor decidió mostrar.",
    how: ["Toca una notificación para ir a su pantalla.", "Dispara eventos en el motor y mira cómo llegan aquí."],
    val: "Apertura de notificaciones por tipo de momento."},
  card: {n: "Tarjeta débito", tag: "Navegación real", what: "La tarjeta del cliente con sus compras recientes. Las compras con tarjeta (peajes, combustible) son las que alimentan la señal de vehículo.",
    how: ["Congela y descongela la tarjeta."], val: "Nada: da contexto al recorrido."},
  transfer: {n: "Enviar dinero", tag: "Presente · Acción real",
    what: "El primer paso de una transferencia por Bre-B. Los contactos frecuentes salen de los movimientos del cliente.",
    how: ["Elige a la persona que el cliente apoya cada mes (Laura M., Mamá o Martha G.) para ver cómo el motor lo lee como señal.", "Elige a otra persona para ver que una transferencia ocasional no dispara nada."],
    val: "Si la oferta inmediatamente después de transferir se siente oportuna o invasiva."},
  amount: {n: "Monto", tag: "Navegación real", what: "Teclado numérico con montos sugeridos según el historial.",
    how: ["Usa el teclado o un monto sugerido.", "No deja continuar si el monto supera el saldo."], val: "Nada: es parte del flujo."},
  confirm: {n: "Confirmación", tag: "Navegación real", what: "Resumen antes de mover la plata.", how: ["«Cambiar» vuelve al paso anterior."], val: "Nada: es parte del flujo."},
  processing: {n: "Procesando", tag: "Navegación real", what: "Mientras se procesa, el API convierte la acción en un movimiento y decide si es una señal.", how: ["Espera un segundo."], val: "Nada."},
  success: {n: "Comprobante", tag: "Paso 1 → 2", what: "La operación quedó hecha. La anotación rosa dice lo que leyó el motor; si la acción es una señal fuerte, la notificación llega unos segundos después.",
    how: ["Espera la notificación en la parte de arriba del teléfono.", "«Listo» vuelve a donde empezaste."], val: "Tiempo entre la acción y la oferta: ¿cuánto es oportuno?"},
  cajitas: {n: "Cajitas", tag: "Navegación real", what: "Los ahorros del cliente por meta. Una cajita de viaje es una de las señales más claras de la idea 2.",
    how: ["Abre la cajita de viaje y abona."], val: "Si las metas de ahorro anticipan bien una compra de seguro."},
  cajita: {n: "Detalle de la cajita", tag: "Presente · Acción real", what: "Progreso, historial de abonos y el botón para abonar.",
    how: ["«Abonar» abre el teclado; en la cajita de viaje, el motor ofrece seguro de viaje al terminar."], val: "Aceptación del seguro de viaje según el progreso de la meta."},
  credito: {n: "Lulo Crédito", tag: "Pasado y presente", what: "El crédito del cliente, con su pago protegido visible y la pregunta de validación. Si no tiene crédito, aparece el preaprobado.",
    how: ["Paga una cuota: queda en el extracto y en «Tu crédito».", "Pide más dinero: el motor revisa si el crédito tiene pago protegido."], val: "Cuántos clientes sabían que tenían pago protegido."},
  creditReq: {n: "Solicitar crédito", tag: "Presente · Acción real", what: "Monto, plazo y cuota aproximada. El desembolso es el evento de mayor prioridad del motor.",
    how: ["Con Valentina, que no tiene crédito, el motor ofrece pago protegido.", "Con Sebastián o Andrés, que ya lo tienen, no es elegible."], val: "Aceptación del pago protegido en el desembolso."},
  anio: {n: "Tu año en Lulo", tag: "Pasado · Tu año en Lulo",
    what: "La portada del resumen anual. Los capítulos los arma el API con los movimientos del cliente: solo aparece un capítulo si la señal que lo sostiene existe.",
    how: ["«Ver mi año» abre la historia desde el principio.", "Cada capítulo de la lista abre la historia en ese punto.", "Cambia de cliente para ver otro año con otros capítulos."],
    val: "Si los clientes abren el resumen y qué capítulos les parecen útiles o invasivos."},
  yearLoading: {n: "Tu año en Lulo", tag: "Pasado · Tu año en Lulo", what: "La primera vez, la app muestra que está leyendo el año de movimientos.", how: ["Espera un segundo."], val: "Nada."},
  story: {n: "Tu año en Lulo", tag: "Pasado · Tu año en Lulo", what: "",
    how: ["Toca a la derecha para avanzar y a la izquierda para volver. En computador también sirven las flechas del teclado.", "«Activar» registra la aceptación desde el capítulo que la generó.", "«Ahora no» registra el rechazo y el capítulo no insiste.", "La X cierra la historia."],
    val: "Finalización del resumen y aceptación por capítulo frente al grupo de control."},
  offer: {n: "Oferta recomendada", tag: "Presente · Motor de disparadores",
    what: "Lo que ve el cliente cuando el motor detecta un momento. «Por qué lo ves» se arma con la señal real del cliente: su empleador, su cajita o la persona que apoya.",
    how: ["«Activar seguro» registra la aceptación y la protección aparece al cierre de Tu año.", "«Ahora no» registra un rechazo sin castigar al cliente.", "«No quiero sugerencias de este tipo» cuenta como señal de daño."],
    val: "La aceptación incremental por evento frente al grupo de control, no la tasa bruta."},
  renew: {n: "Renovación del SOAT", tag: "Futuro · Recordatorio del SOAT",
    what: "La compra ya estaba decidida: el cliente la iba a hacer de todos modos. Esta pantalla compite solo por el canal, con vigencia clara, descuento por anticipación y pago desde la cuenta Lulo.",
    how: ["«Pagar» renueva, descuenta el saldo y agrega el movimiento.", "«Recuérdamelo después» registra que pospuso.", "El descuento lo calcula el API según los días de aviso que elijas en Perfil."],
    val: "Cuánta anticipación hace que el descuento cambie la decisión."},
  paying: {n: "Procesando el pago", tag: "Futuro · Recordatorio del SOAT", what: "Estado intermedio mientras se confirma con la aseguradora.", how: ["Espera un segundo."], val: "Nada, es un estado de espera."},
  done: {n: "Renovación confirmada", tag: "Futuro · Recordatorio del SOAT",
    what: "Cierra el ciclo: confirma la nueva vigencia y deja programado el próximo aviso. El capítulo «Tu carro» de Tu año pasa a mostrar el SOAT al día.",
    how: ["«Volver al inicio» muestra que el aviso del SOAT ya no aparece.", "«Ver Tu año en Lulo» muestra el capítulo del carro actualizado."],
    val: "Captura de canal: cuántos renuevan en Lulo y no por fuera."},
  perfil: {n: "Perfil y preferencias", tag: "Medición y no daño",
    what: "El cliente controla lo que recibe: sugerencias, avisos, anticipación del aviso y la autorización para usar sus movimientos (Ley 1581).",
    how: ["Apagar sugerencias hace que el motor deje de mostrar ofertas y queda como señal de daño.", "Quitar «Usar mis movimientos» apaga Tu año y el motor deja de leer eventos.", "«Cerrar sesión» vuelve a la pantalla de ingreso."],
    val: "Desactivación de notificaciones y retiro de la autorización: indicadores de no daño."},
};

/* ---------- desplegables de funcionalidades ---------- */
export function buildAccs(S, clients, events) {
  const sig = S.B.signals;
  const chs = S.B.chapters;
  const clientRows = clients.map(c => [`<b>${esc(c.full)}</b><br>${c.age} años · ${esc(c.city)}`, esc(c.summary), c.tags.map(t => `<span class="mini">${esc(t)}</span>`).join(" "), `<button class="goto" data-client="${c.id}">Usar</button>`]);
  return [
    {g: "La propuesta"},
    {id: "acc-resumen", k: "Resumen", t: "La propuesta en una frase", d: "Tres ideas, un mismo mecanismo, sin producto nuevo", open: true, b: `
      <p>Leer lo que el cliente ya hace en la app, ofrecerle el seguro correcto en el momento en que lo necesita y <b>registrar su respuesta</b>. Las tres ideas se montan sobre ramos ya habilitados, así que se pueden probar sin esperar una negociación con la aseguradora.</p>
      <h5>El recorrido completo</h5>
      <div class="flow"><span>Algo pasa en la cuenta</span><i>→</i><span>El motor lo detecta</span><i>→</i><span>Una regla de prioridad escoge</span><i>→</i><span>El cliente decide</span><i>→</i><span>Queda registrado y aparece en Tu año</span></div>
      <div class="two" style="margin-top:10px">
        <div class="box"><b>Pasado</b>Lo que el cliente ya vivió: Tu año en Lulo.</div>
        <div class="box"><b>Presente</b>Lo que acaba de hacer: motor de disparadores.</div>
        <div class="box"><b>Futuro</b>Lo que se le viene: recordatorio de vencimiento.</div>
        <div class="box"><b>Siempre</b>Registrar la respuesta: el paso que hoy no existe.</div>
      </div>`},
    {id: "acc-navegar", k: "Prototipo", t: "Cómo navegar la app", d: "Es una app completa con datos simulados: todo lo que tocas funciona", open: true, b: `
      <p>El teléfono se usa como la app real: ingreso con clave, saldo, extracto con búsqueda, transferencias, cajitas, crédito, notificaciones y perfil. <b>Lo que haces en la app lo lee el motor</b>, igual que los eventos del panel.</p>
      ${TBL(["Flujo", "Qué haces", "Qué hace el motor"], [
        ["Enviar a quien apoyas", "Inicio → Enviar → contacto frecuente → monto → Enviar", "Señal de dependientes → oferta de vida voluntario"],
        ["Abonar a la cajita de viaje", "Inicio → Cajitas → cajita de viaje → Abonar", "Señal de viaje → seguro de viaje"],
        ["Pedir crédito", "Inicio → Crédito → Solicitar o Pedir más dinero", "Sin pago protegido lo ofrece; con él, no es elegible"],
        ["Pagar una cuota", "Crédito → Pagar cuota", "Suma a «Tu crédito», no dispara oferta"],
        ["Renovar el SOAT", "Aviso de Inicio → Pagar", "Captura de canal; Tu año se actualiza"],
        ["Revisar un movimiento", "Movimientos → tocar una fila", "Muestra qué señal alimenta y su regla"]])}
      <h5>Atajos</h5>${UL(["El botón atrás del navegador o del celular funciona como el de la app.", "En el celular la app ocupa toda la pantalla y el panel se abre con el botón «Panel».", "Puedes compartir un enlace directo: <code>/#/tu-ano</code>, <code>/#/movimientos</code> o <code>/?cliente=valentina</code>."])}
      ${G("home", "Ir al inicio")}${G("transfer", "Hacer una transferencia")}`},
    {id: "acc-clientes", k: "Prototipo", t: "Tres clientes simulados", d: "Mismo motor, años distintos, decisiones distintas", b: `
      <p>Cada cliente tiene un año completo de movimientos generados con una semilla fija: siempre salen los mismos datos. Cambiar de cliente cambia los capítulos de Tu año, las señales y lo que el motor decide.</p>
      ${TBL(["Cliente", "Perfil", "Señales", ""], clientRows)}
      <h5>Qué mirar al cambiar</h5>${UL([
        "<b>Valentina</b> no tiene carro ni crédito: esos capítulos no aparecen. Su ingreso freelance no alcanza la regla de nómina, así que el motor no le ofrece ese seguro y lo explica en «Tu trabajo».",
        "<b>Andrés</b> ya tiene seguro de nómina: el capítulo dice «Ya lo tienes activo» y el evento de nómina no es elegible. Su SOAT vence en 9 días y el aviso sale como urgente.",
        "<b>Sebastián</b> es el caso de la presentación: 1.284 movimientos, nómina nueva desde julio y SOAT a 27 días."])}`},
    {id: "acc-cliente", k: "Retroalimentación", t: "Lo que dijo el cliente", d: "Lo que valoraron y lo que les preocupó del prototipo", b: `
      <div class="two">
        <div class="box"><b>Lo que valoraron</b>${UL(["El prototipo es interactivo: se puede recorrer como la app real.", "Las tres soluciones responden al desafío.", "Las ofertas aparecen en momentos reales del cliente."])}</div>
        <div class="box"><b>Lo que les preocupó</b>${UL(["Refinar el prototipo con los datos reales de Lulo Bank.", "Construir los modelos con esos datos, que llegan en los próximos días.", "Confirmar qué momentos tienen más impacto."])}</div>
      </div>
      <h5>Cómo lo recoge esta versión</h5>${UL(["Cada cifra de Tu año la calcula el backend con reglas sobre los movimientos: con los datos reales se recalcula sin cambiar el diseño.", "Las señales tienen umbrales explícitos y evidencia, listos para contrastar con los datos.", "El registro guarda la respuesta por capítulo, por evento y por cliente: es la base para saber qué momento tiene más impacto.", "El grupo de control aplica a Tu año y al motor, para medir efecto y no solo actividad."])}`},
    {id: "acc-problemas", k: "Contexto", t: "Dos problemáticas, no una", d: "Se parecen, pero se miden distinto", b: `
      <div class="two">
        <div class="box"><b>1. Ampliar la oferta de seguros</b>${UL(["Hay productos, pero nadie los ofrece: el modelo es de tirón.", "Faltan ramos: vida solo existe atado al crédito y nómina no tiene un momento propio.", "La comisión de seguros no consume capital regulatorio ni requiere fondeo, y la meta es el punto de equilibrio en 2026."])}<p style="margin-top:6px"><b>Se mide en</b> pólizas por cliente y tasa de renovación.</p></div>
        <div class="box"><b>2. Ampliar el mercado de Lulo Bank</b>${UL(["650.000 clientes activos, saldo promedio de $1,7 millones: es cuenta de movimiento, no la principal.", "La tasa (7,84% E.A.) dejó de diferenciar frente a Nu, Ban100, Finandina y Contactar.", "El SOAT responde a una necesidad que el cliente ya tiene fuera del banco: sirve de puerta de entrada."])}<p style="margin-top:6px"><b>Se mide en</b> clientes nuevos y profundidad de la relación.</p></div>
      </div>
      <h5>Lo que encontramos</h5><p>Lulo ya distribuye cinco seguros: vida grupo deudor (AXA Colpatria), SOAT (Seguros Mundial), desempleo (Chubb), pago protegido (SBS) y asistencias (IGS). Nunca ha habido una recomendación proactiva, así que no hay ninguna respuesta del cliente atribuible a un momento.</p>`},
    {id: "acc-brecha", k: "Contexto", t: "La brecha entre el cliente que hay y el que se quiere", d: "El perfil juega en contra, el comportamiento a favor", b: `
      ${TBL(["El cliente de hoy", "El cliente que se busca"], [
        ["Joven, digital, relación corta con el banco", "Con la nómina domiciliada en Lulo"],
        ["Saldo promedio de $1,7 millones: usa Lulo para mover", "Ve a Lulo como su banco principal"],
        ["Cero seguros voluntarios contratados por recomendación", "Con al menos un seguro voluntario vigente y renovado"],
        ["Alta frecuencia transaccional (Bre-B: más de 110 millones de operaciones en un mes)", "Deja un registro de decisión: aceptó o rechazó, y en qué momento"]])}
      <h5>Por qué no basta con campañas por perfil</h5>
      ${UL(["El tenedor típico de seguro de vida es mayor y lleva más años con su banco: 44,5 frente a 41,4 años de edad y 11,98 frente a 9,11 años de relación (Boustani et al., 2024).", "Los mismos autores muestran que la conducta supera al perfil: el poder predictivo pasa de 0,847 con demografía sola a 0,908 con datos transaccionales.", "Conclusión de diseño: la brecha se cierra con lo que el cliente hace, no con lo que el cliente es."])}`},
    {id: "acc-ramos", k: "Contexto", t: "Los cuatro ramos del prototipo", d: "Tres existen y no se ofrecen, uno no existe en versión voluntaria", b: `
      ${TBL(["Ramo", "Aliado", "Hoy", "Lo que falta"], [
        ["SOAT", "Seguros Mundial", "Disponible, compra activa", "Nadie avisa cuándo vence"],
        ["Pago protegido", "SBS Seguros", "Ligado al crédito", "No se ofrece en el desembolso"],
        ["Nómina (desempleo)", "Chubb", "Disponible, compra activa", "No hay un momento ligado al ingreso"],
        ["Vida", "AXA Colpatria", "Solo grupo deudor", "No existe versión voluntaria"]])}
      <p><b>El patrón:</b> en tres de los cuatro ramos el problema es de descubrimiento, no de conversión. Por eso el prototipo trabaja visibilidad y momento, no precio.</p>`},
    {id: "acc-habitos", k: "Contexto", t: "Los hábitos de consumo son la materia prima", d: "Qué señal anticipa cada ramo y qué momento dispara la oferta", b: `
      ${TBL(["Ramo", "Hábito que lo anticipa", "Momento que dispara"], [
        ["SOAT", "Pago del SOAT anterior, peajes, combustible, parqueaderos, impuesto vehicular", "30 días antes del vencimiento"],
        ["Pago protegido", "Desembolso, uso del cupo, pago recurrente de cuota", "Desembolso y primer pago de cuota"],
        ["Nómina", "Abonos periódicos del mismo originador, gastos fijos", "Tercer abono consecutivo o salto a Lulo Pro"],
        ["Vida", "Nómina domiciliada, transferencias fijas a un tercero, cajita de largo plazo", "Consolidación de la nómina en Lulo"]])}
      <p>Es la única ventaja en la que Lulo no arranca en desventaja frente a un banco con veinte años de relación: por ser 100% digital, todo queda registrado punta a punta.</p>
      ${G("movs", "Ver movimientos")}`},

    {g: "Las tres ideas en el prototipo"},
    {id: "acc-idea1", k: "Pasado", t: "Tu año en Lulo", d: "Lo que el cliente ya vivió, contado con un año de movimientos", b: `
      ${SUB("Qué hace", UL(["Convierte 12 meses de movimientos en un resumen tipo historia, con un capítulo por cada momento de la vida del cliente.", "Algunos capítulos traen un momento de protección: el seguro que corresponde a lo que el cliente ya vivió.", "Muestra beneficios que el cliente tiene y no percibe, como el pago protegido de su crédito.", "Cierra con lo que el cliente tiene cubierto y lo que queda por revisar."]), true)}
      ${SUB("Qué cambia frente a la versión anterior", `<p>La pestaña «Mis seguros» se retira del prototipo. Su lógica de mostrar lo que el cliente tiene queda dentro del cierre de Tu año y del capítulo del crédito. El dato que activa la idea pasa de la tenencia de pólizas a <b>un año de movimientos</b>, y el formato pasa de un listado que el cliente debe visitar a un contenido que quiere abrir.</p>`)}
      ${SUB(`Capítulos de ${esc(S.B.client.first)} (${chs.length})`, TBL(["Capítulo", "Cifra principal", "Momento de protección"], chs.map(c => [c.name, c.stats ? c.stats.map(s => `${s.big} ${s.line}`).join(" · ") : "Se calcula en vivo", c.protect ? S.B.offers[c.protect.key].title : c.soat ? "Renovar SOAT" : c.ask ? "Pregunta: ¿sabías que lo tenías?" : "Ninguno"])))}
      ${SUB("Funcionalidades modeladas", UL([
        "<b>Capítulos calculados:</b> el backend arma cada capítulo con los movimientos; si la señal no existe, el capítulo no aparece.",
        "<b>Entrada propia:</b> pestaña «Tu año» en la barra inferior, tarjeta en Inicio y notificación.",
        "<b>Carga honesta:</b> la primera vez muestra que está leyendo el año de movimientos.",
        "<b>Historia navegable:</b> barra de progreso, toque a la derecha o izquierda, flechas del teclado y botón de cerrar.",
        "<b>Momento de protección</b> dentro del capítulo, con «Activar» y «Ahora no».",
        "<b>Elegibilidad:</b> si ya lo tiene, el capítulo dice «Ya lo tienes activo» en vez de ofrecer.",
        "<b>Explicación cuando no hay oferta:</b> «Tu trabajo» le dice a un independiente por qué no le ofrecemos seguro de nómina.",
        "<b>Validación integrada:</b> «¿Sabías que tenías esta protección?» en el capítulo del crédito.",
        "<b>Cierre dinámico:</b> cuenta las protecciones activas, incluidas las aceptadas en el motor.",
        "<b>Autorización de datos:</b> sin ella, Tu año pide permiso antes de mostrarse."]))}
      ${SUB("Qué hay que validar", UL(["Si los clientes abren el resumen y lo terminan.", "Qué capítulos se sienten útiles y cuáles invasivos.", "Si una oferta dentro de un contenido personal se recibe mejor que una notificación.", "Qué cifras se pueden calcular con los datos reales de cada cliente."]))}
      ${SUB("Cómo se mide", UL(["Apertura y finalización del resumen.", "Aceptación por capítulo frente al grupo de control, que ve el resumen sin ofertas.", "Respuestas a «¿Sabías que tenías esta protección?».", "Veces que el cliente comparte su año."]))}
      ${SUB("Cómo se generaliza", `<p>No es un resumen de seguros: es una forma de devolverle al cliente lo que sus datos dicen de él, con un momento de acción en cada capítulo. Sirve para CDT, Lulo Pro, cashback o crédito, y se puede repetir por semestre o en fechas propias del cliente, como el aniversario con Lulo.</p>`)}
      ${G("anio", "Ver Tu año")}${G("story:intro", "Abrir la historia")}`},
    {id: "acc-idea2", k: "Presente", t: "Motor de disparadores preventa", d: "Ofrecer el seguro correcto cuando el cliente lo necesita", b: `
      ${SUB("Cómo funciona", `<p>Cada acción relevante en la app se convierte en un evento. El evento pasa por la fuerza de la señal, las reglas de elegibilidad y la prioridad y, si gana, se convierte en una notificación y una oferta en la app.</p><div class="flow"><span>Acción o evento</span><i>→</i><span>Señal</span><i>→</i><span>Elegibilidad</span><i>→</i><span>Prioridad</span><i>→</i><span>Notificación</span><i>→</i><span>Oferta</span><i>→</i><span>Respuesta registrada</span></div>`, true)}
      ${SUB("Reglas de detección (paso 1)", TBL(["Señal", "Regla", `Resultado con ${esc(S.B.client.first)}`], Object.values(sig).map(s => [s.name, s.rule, `<b>${s.strength}</b> · ${esc(s.headline)}`])))}
      ${SUB("Catálogo de eventos", TBL(["Evento", "Qué revela", "Oferta", "Prioridad"], Object.values(events).map(e => [esc(e.label), e.habit, e.offer, e.prio])))}
      ${SUB("Reglas de decisión (paso 2)", UL([
        "<b>Autorización:</b> sin autorización de datos (Ley 1581) el motor no lee el evento.",
        "<b>Grupo de control:</b> clientes que generan el evento pero no reciben la oferta, para medir el efecto real.",
        "<b>Respeto a preferencias:</b> si el cliente apagó las sugerencias, el motor no muestra nada.",
        "<b>Fuerza de la señal:</b> un evento aislado no basta si el hábito no existe. Un peaje suelto de quien no tiene carro es señal débil.",
        "<b>Elegibilidad:</b> si el cliente ya tiene la cobertura, no se le vende otra. Un nuevo desembolso con pago protegido vigente no dispara oferta.",
        "<b>Una ventana, un contacto:</b> si hay una oferta abierta, las demás esperan en cola ordenadas por prioridad (1 = mayor).",
        "<b>SOAT al día:</b> los eventos de vehículo con SOAT vigente no disparan nada en esta fase. Todo riesgo queda para la fase 2."]))}
      ${SUB("La oferta en pantalla", UL(["<b>«Por qué lo ves»:</b> se arma con la señal real: el empleador, la cajita o la persona que el cliente apoya.", "Una cifra clave, lo que cubre, el precio y la cuenta de pago.", "Tres respuestas: aceptar, «Ahora no» y no volver a ver ese tipo de sugerencia.", "Vida voluntario se marca como producto por negociar con la aseguradora."]))}
      ${SUB("Cómo se mide", `<p><b>Aceptación incremental por evento</b>, no la tasa bruta: aceptación del grupo tratado menos la del grupo de control, evento por evento.</p>`)}
      ${SUB("Cómo se generaliza", `<p>Es una capa que decide la próxima mejor acción para cualquier producto: crédito, CDT, Lulo X o Lulo Pro. En otros sectores es el mismo mecanismo: un evento observable, una regla de elegibilidad y una oferta pertinente.</p>`)}
      ${G("motor", "Abrir el motor en vivo")}${G("transfer", "Probar con una transferencia")}`},
    {id: "acc-idea3", k: "Futuro", t: "Recordatorio de vencimiento del SOAT", d: "Usar un seguro obligatorio para abrir la conversación", b: `
      ${SUB("Por qué este ramo primero", UL(["La decisión de compra ya está tomada: solo se disputa el canal.", "El momento es una fecha, no una conducta: es el más barato de predecir.", "Tiene el menor riesgo de fricción: nadie se molesta porque le recuerden una obligación legal."]), true)}
      ${SUB("Flujo modelado", `<div class="flow"><span>Aviso en Inicio</span><i>→</i><span>Renovación</span><i>→</i><span>Descuento</span><i>→</i><span>Pago desde Lulo</span><i>→</i><span>Confirmación</span><i>→</i><span>Próximo aviso</span></div>${UL(["También se entra desde el capítulo «Tu carro» de Tu año, desde la bandeja de notificaciones o desde una notificación del motor por peajes y combustible.", "Al pagar se descuenta el saldo, aparece el movimiento y la póliza pasa a vigente.", "«Recuérdamelo después» queda registrado como pospuesto.", "Con 10 días o menos el aviso sale como urgente (caso de Andrés)."])}`)}
      ${SUB("Configuración del aviso", `<p>En Perfil el cliente elige 30, 15 o 7 días de anticipación. El aviso de Inicio aparece solo dentro de esa ventana; antes, Inicio dice cuándo llegará. El descuento se escala con la anticipación para poder conversar la hipótesis con usuarios.</p>`)}
      ${SUB("Cómo crece", UL(["Abre la puerta a los demás seguros del vehículo.", "El mismo mecanismo sirve para la revisión tecnomecánica y el impuesto vehicular.", "Y para la renovación de cualquier otra póliza del cliente."]))}
      ${SUB("Qué hay que validar", UL(["Si los clientes esperan comprar el SOAT en una app bancaria.", "Con cuánta anticipación quieren el aviso.", "Cuántos clientes de Lulo tienen vehículo y son detectables por su gasto."]))}
      ${SUB("Cómo se mide", `<p><b>Captura de canal:</b> cuántos renuevan en Lulo y no por fuera. Se reporta separado de los otros tres ramos: como la compra iba a ocurrir de todos modos, mezclarlo en un solo indicador de conversión escondería el resultado.</p>`)}
      ${S.B.car ? G("home", "Ver el aviso en Inicio") + G("renew", "Ir a renovar") : `<p class="meta">Este cliente no tiene vehículo: cambia a Sebastián o Andrés para ver el flujo.</p>`}`},

    {g: "Cómo se sostiene"},
    {id: "acc-nucleo", k: "Mecanismo", t: "El núcleo común: cuatro pasos", d: "Una sola capa sirve para las tres ideas", b: `
      <div class="flow"><span>1. Detectar la señal</span><i>→</i><span>2. Decidir qué y a quién</span><i>→</i><span>3. Mostrarlo en la app</span><i>→</i><span>4. Registrar la respuesta</span></div>
      <p>El cuarto paso no existe hoy en Lulo Bank. Es el que convierte cualquiera de las tres ideas en un activo que la competencia no puede copiar: con el tiempo, Lulo sabe qué momento funciona para qué cliente.</p>
      <p>En el panel «Motor en vivo» los cuatro pasos se encienden uno a uno con cada evento, y la sección «Lo que el motor ve» muestra el paso 1 con su evidencia.</p>${G("motor", "Verlo en vivo")}`},
    {id: "acc-medicion", k: "Medición", t: "Qué se mide y cómo se evita el daño", d: "Métricas por idea, indicadores de no daño y grupo de control", b: `
      ${TBL(["Idea", "Métrica principal"], [["Tu año en Lulo", "Finalización del resumen y aceptación por capítulo frente a control"], ["Motor", "Aceptación incremental por evento"], ["Recordatorio", "Captura de canal: renuevan en Lulo y no por fuera"]])}
      <h5>Indicadores de no daño (transversales)</h5>
      ${UL(["Desactivación de notificaciones: en el prototipo, apagar sugerencias o avisos en Perfil.", "Rechazo explícito: «No quiero sugerencias de este tipo».", "Retiro de la autorización de datos.", "Caída de transacciones después del contacto.", "Quejas y desinstalaciones."])}
      <h5>En el prototipo</h5>${UL(["Cada respuesta queda en el registro con hora, cliente, evento, oferta y resultado.", "El botón «Exportar CSV» descarga el registro, generado por el backend, para analizarlo en Excel.", "El grupo de control se activa con un botón y deja trazado que el evento ocurrió pero no se mostró."])}`},
    {id: "acc-pantallas", k: "Prototipo", t: "Mapa de pantallas", d: "Salta a cualquier pantalla", b: `
      ${TBL(["Pantalla", "Idea", "Ir"], [
        ["Inicio", "Futuro", G("home", "Abrir")], ["Notificaciones", "Mostrar", G("notifs", "Abrir")], ["Movimientos", "Materia prima", G("movs", "Abrir")],
        ["Tu año: portada", "Pasado", G("anio", "Abrir")], ["Tu año: primer capítulo con oferta", "Pasado", G("story:protect", "Abrir")], ["Tu año: cierre", "Pasado", G("story:cierre", "Abrir")],
        ["Renovación del SOAT", "Futuro", S.B.car ? G("renew", "Abrir") : "Sin vehículo"], ["Oferta: nómina", "Presente", G("offer:nomina", "Abrir")], ["Oferta: viaje", "Presente", G("offer:viaje", "Abrir")],
        ["Oferta: vida voluntario", "Presente", G("offer:vida", "Abrir")], ["Oferta: pago protegido", "Presente", G("offer:pago", "Abrir")],
        ["Enviar dinero", "Acción real", G("transfer", "Abrir")], ["Cajitas", "Acción real", G("cajitas", "Abrir")], ["Crédito", "Acción real", G("credito", "Abrir")],
        ["Tarjeta", "Contexto", G("card", "Abrir")], ["Perfil y preferencias", "No daño", G("perfil", "Abrir")], ["Ingreso", "Contexto", G("lock", "Abrir")]])}`},
    {id: "acc-arquitectura", k: "Tecnología", t: "Cómo está construida esta app", d: "Backend en Python, interfaz web y despliegue en Vercel", b: `
      <p>El teléfono y el panel son la interfaz. <b>Los datos, las señales, Tu año y las decisiones salen de un servicio en Python</b> (FastAPI), igual que lo haría el motor real dentro de Lulo Bank.</p>
      ${TBL(["Pieza", "Qué hace", "Dónde está"], [
        ["Simulador", "Genera un año de movimientos por cliente con una semilla fija", "<code>simulator.py</code>"],
        ["Señales (paso 1)", "Reglas con umbral y evidencia sobre los movimientos", "<code>signals.py</code> · <code>GET /api/clients/{id}/signals</code>"],
        ["Tu año", "Arma los capítulos que aplican a cada cliente", "<code>year.py</code> · <code>GET /api/clients/{id}/year</code>"],
        ["Acciones", "Convierte una transferencia, abono o crédito en movimiento y evento", "<code>POST /api/clients/{id}/actions</code>"],
        ["Motor (paso 2)", "Autorización, control, preferencias, fuerza, elegibilidad y cola", "<code>engine.py</code> · <code>POST /api/engine/event</code>"],
        ["Extracto", "Búsqueda, filtros y paginación del año completo", "<code>GET /api/clients/{id}/movements</code>"],
        ["Medición (paso 4)", "Métricas por oferta y exportación del registro a CSV", "<code>report.py</code> · <code>POST /api/report/csv</code>"]])}
      <h5>Por qué el motor es «sin estado»</h5>
      <p>Cada evento viaja con su contexto (coberturas aceptadas, ventana de contacto y cola) y el motor responde con la decisión. Así escala en funciones serverless y se prueba con pruebas automáticas, sin base de datos. La sesión de la demo se guarda en el navegador mientras la pestaña está abierta.</p>
      <h5>Para pasar a datos reales</h5>${UL(["Reemplazar el simulador por los eventos instrumentados en la app.", "Guardar el registro de respuestas en una base de datos para medir contra el grupo de control.", "La documentación interactiva del API está en <a href=\"/docs\" target=\"_blank\" rel=\"noopener\">/docs</a>."])}`},
    {id: "acc-plan", k: "Plan", t: "Pasos a seguir", d: "Validar, prototipar y medir hasta La Muestra", b: `
      ${TBL(["Idea", "Validar (hasta 23 sep)", "Prototipar (7–31 oct)", "Medir (4–28 nov)"], [
        ["Tu año en Lulo", "Con los datos reales: qué capítulos se pueden calcular por cliente", "Historia navegable con capítulos calculados y sus momentos de protección", "Finalización y aceptación por capítulo frente a control"],
        ["Motor", "Con Analítica: qué eventos están instrumentados y con qué latencia", "Reglas evento a oferta para dos eventos y su prioridad", "Aceptación incremental por evento"],
        ["Recordatorio", "Con Alex: cuántos clientes tienen SOAT y cuándo vence", "Flujo de aviso y renovación en la app", "Captura de canal"]])}
      <h5>Qué necesitamos de la organización</h5>
      <ol><li>Los datos ya solicitados: ventas mensuales por ramo, comisión, ticket y requisitos de elegibilidad.</li><li>Una sesión con Analítica y UX sobre eventos instrumentados y espacio en la interfaz.</li><li>La postura de Jurídico sobre si una recomendación in-app cuenta como contacto bajo la Ley 2300.</li></ol>
      <p style="margin-top:8px">IDEAR hasta el 23 de septiembre, prototipo en octubre, La Muestra el 18 de noviembre.</p>`},
    {id: "acc-supuestos", k: "Supuestos", kp: true, t: "Supuestos, límites y fase 2", d: "Lo que es ilustrativo y lo que queda por fuera", b: `
      <h5>Datos ilustrativos</h5>${UL(["Los tres clientes y sus movimientos son simulados con una semilla fija; nombres, placas, saldos y comercios son de ejemplo.", "Precios, porcentajes de descuento y tasas son de ejemplo.", "Las prioridades del motor y los umbrales de las señales son una propuesta del equipo para discutir."])}
      <h5>Supuestos por confirmar</h5>${UL(["Las señales de hábito son hipótesis: hay que confirmar cuáles están instrumentadas.", "Vida voluntario no existe hoy: requiere negociar producto con AXA Colpatria.", "La tarifa del SOAT es regulada: el descuento tendría que venir como beneficio de Lulo y debe revisarlo Jurídico.", "Si una notificación in-app cuenta como contacto comercial bajo la Ley 2300.", "Mostrar cifras personales en Tu año exige revisar la autorización de tratamiento de datos (Ley 1581 de 2012)."])}
      <h5>Fase 2 (fuera de este prototipo)</h5>${UL(["Seguros premium, mascotas y alianza con aerolíneas: exigen negociar producto nuevo.", "Seguro todo riesgo del vehículo y compra de SOAT para quien no lo tiene registrado.", "Modelo predictivo sobre datos transaccionales en lugar de reglas fijas."])}`},
  ];
}

export function signalsHTML(S) {
  const tag = {fuerte: "ok", "débil": "hold", ninguna: "no"};
  return Object.values(S.B.signals).map(s => `<details class="sig" data-sig="${s.key}"><summary><span class="sig-n">${s.name}</span><span class="tag ${tag[s.strength]}">${s.strength}</span><span class="sig-h">${esc(s.headline)}</span></summary>
    <div class="sig-b"><ul>${s.evidence.map(e => `<li>${esc(e)}</li>`).join("")}</ul><div class="sig-r"><b>Regla:</b> ${s.rule}</div><div class="sig-r"><b>Oferta asociada:</b> ${s.offer}</div></div></details>`).join("");
}

export function clientPicker(clients, current) {
  return clients.map(c => `<button class="cl${c.id === current ? " on" : ""}" data-client="${c.id}" aria-pressed="${c.id === current}"><span class="av" style="background:${c.color};color:var(--ink)">${c.first[0]}</span><span class="cl-t"><b>${esc(c.first)}</b><span>${c.tags.slice(0, 2).join(" · ")}</span></span></button>`).join("");
}


