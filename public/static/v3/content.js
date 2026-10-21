// Lo nuevo del prototipo frente a la app real de Lulo: lo usan «Resaltar lo nuevo», la bienvenida y el recorrido.

/* ---------- lo nuevo frente a la app real ---------- */
// Cada elemento del teléfono con data-new="clave" es algo que la app de Lulo no tiene hoy. «Resaltar lo nuevo»
// los marca y, al pasar el mouse, muestra qué es.
export const NEW = {
  "soat-aviso": {t: "Aviso del SOAT", d: "Recuerda el vencimiento con fecha y valor, también si el SOAT es con otra aseguradora (captura de canal)."},
  "soat-renovar": {t: "Renovación con descuento", d: "Renovar antes con descuento por anticipación: hipótesis por validar (la tarifa del SOAT es regulada)."},
  "banner-oferta": {t: "Oferta como banner", d: "Si el cliente llegó al tope de contactos, hay fatiga o la latencia no deja disparar al instante, la oferta no va por push: aparece aquí y no cuenta como contacto (Ley 2300)."},
  "anio-promo": {t: "Tu año en Lulo", d: "El resumen de 12 meses calculado con los movimientos del cliente."},
  "tab-anio": {t: "Pestaña Tu año", d: "Nueva en la barra inferior: el resumen del año con sus momentos de protección."},
  "tab-proteccion": {t: "Pestaña Protección", d: "Nueva en la barra inferior: todo lo del cliente en seguros, con lo que el motor sugiere y por qué."},
  "ramos-nuevos": {t: "Ramos de la propuesta", d: "Vida, Viajes, Mascotas y Hogar no están hoy en la app: son la propuesta del Grupo 14, con precio de la base."},
  "chip-motor": {t: "«Para ti» y «Activo»", d: "Lo marca el motor con lo que sabe del cliente."},
  "por-que": {t: "Por qué lo ves", d: "Cada oferta dice de dónde sale, con los datos del cliente. Si no aplica, dice por qué."},
  "no-dano": {t: "Control del cliente", d: "«No quiero sugerencias de este tipo» apaga ese tipo de oferta y queda medido como señal de daño."},
  "proteccion": {t: "Tu protección", d: "Seguros voluntarios separados de lo que viene con el crédito (Vida grupo deudor no es Vida voluntario)."},
  "para-ti": {t: "Sugerencias del motor", d: "Lo que el motor ofrecería hoy, ordenado por fecha límite y valor esperado."},
  "por-que-no": {t: "Por qué no te ofrecemos…", d: "Transparencia: señal débil, no elegible, en espera o con otra aseguradora."},
  "agendados": {t: "Disparos agendados", d: "El motor ya sabe cuándo vendrá la próxima oferta (por ejemplo, desempleo al sexto abono de nómina)."},
  "anio": {t: "Tu año en Lulo", d: "Una historia de 12 meses; el momento de protección de cada capítulo lo decide el motor."},
  "segmento": {t: "Tu forma de usar Lulo", d: "Segmento de comportamiento del modelo M2 (descriptivo: no decide ofertas)."},
  "momento-proteccion": {t: "Momento de protección", d: "Dentro de la historia: activar, «ahora no» o «te faltan N abonos»."},
  "anotacion": {t: "Anotación del prototipo", d: "El recuadro punteado rosado no es parte de la app: explica qué lee el motor en ese momento."},
  "control-cliente": {t: "Preferencias y autorización", d: "El cliente apaga sugerencias o retira la autorización de datos (Ley 1581): el motor deja de leer sus movimientos."},
  "push": {t: "Push del motor", d: "Notificación que decide el motor: solo si quedan contactos, no hay fatiga y pasaron 7 días desde el último push."},
  "pago-protegido": {t: "Pago protegido en el desembolso", d: "Momento único: al recibir el crédito, el motor revisa si tiene pago protegido y lo ofrece en ese instante."},
};
// Lo nuevo en una lista para la bienvenida y el recorrido: [clave, título, descripción, destino].
export const NEW_LIST = [
  ["soat-aviso", "Aviso y renovación del SOAT", "Antes de que venza, en dos toques y pagando desde la cuenta.", "renew"],
  ["push", "Ofertas en el momento justo", "Una acción normal (transferir, abonar, pedir un crédito) dispara el seguro que tiene sentido, con su porqué.", "motor"],
  ["anio", "Tu año en Lulo", "Doce meses como una historia, con un momento de protección por capítulo.", "story:intro"],
  ["proteccion", "Tu protección", "Lo que tiene, lo que le sugerimos, lo agendado y por qué no le ofrecemos lo demás.", "proteccion"],
  ["motor", "Un motor que aprende", "Calcula la probabilidad de aceptar con los datos y aprende de cada respuesta; el grupo de control mide el efecto real.", null],
];
