(() => {
const IMG_CARD = "/static/img/tarjeta-lulo.png";
const IMG_LOGO = "/static/img/logo-lulo.png";
const $ = s => document.querySelector(s);
const money = n => (n < 0 ? "−" : "") + "$" + Math.abs(n).toLocaleString("es-CO");
const now = () => new Date().toLocaleTimeString("es-CO",{hour:"2-digit",minute:"2-digit",second:"2-digit",hour12:false});

/* ---------- catálogo: lo entrega el backend en Python (lulo_app/catalog.py) ---------- */
const BOOT = JSON.parse(document.getElementById("bootstrap").textContent);
const EVENTS = BOOT.events;
const OFFERS = BOOT.offers;
const clone = o => JSON.parse(JSON.stringify(o));

/* ---------- cliente del API ---------- */
async function api(path, body){
  const r = await fetch(path, body===undefined ? {} : {method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(body)});
  if(!r.ok) throw new Error(`${path} respondió ${r.status}`);
  return r;
}
function apiStatus(state, html){ const el=$("#apiStatus"); if(!el) return; el.className="api-status "+state; el.querySelector("span").innerHTML=html; }
async function checkApi(){
  const t0=performance.now();
  try{
    const h=await (await api("/api/health")).json();
    apiStatus("ok",`<b>Motor en Python conectado</b> · v${h.version} · ${Math.round(performance.now()-t0)} ms`);
  }catch(e){ apiStatus("err","<b>Sin conexión con el motor.</b> Revisa que el servidor esté corriendo."); }
}
/* ---------- Tu año en Lulo: capítulos armados con un año de movimientos ---------- */
const MONTHS=["oct","nov","dic","ene","feb","mar","abr","may","jun","jul","ago","sep"];
const FLOW=[1.8,2.1,3.4,1.6,1.9,2.0,2.2,2.4,2.6,4.1,4.3,4.6];
const CHAPTERS=[
  {id:"intro",theme:"lime",name:"Portada",
    spec:"La portada resume el periodo y la cantidad de movimientos leídos. Invita a recorrer el año como una historia.",
    html:()=>`<div class="st-kick">Tus últimos 12 meses</div><div class="st-big">1.284</div><div class="st-line">movimientos en Lulo</div><p class="st-sub">De octubre de 2025 a septiembre de 2026. Esto es lo que contaron de ti.</p><div class="st-hint">Toca a la derecha para seguir</div>`},
  {id:"dinero",theme:"navy",name:"Tu dinero",
    spec:"Capítulo de contexto: muestra el flujo mensual de la cuenta. No ofrece nada, construye confianza en que los datos son del cliente.",
    html:()=>{const mx=Math.max(...FLOW);return `<div class="st-kick">Tu dinero</div><div class="st-big">$33 M</div><div class="st-line">pasaron por tu cuenta este año</div>
      <div class="st-bars">${FLOW.map((v,i)=>`<div><i style="height:${Math.round(v/mx*100)}%;${i>=9?"background:var(--lime)":""}"></i><span>${MONTHS[i]}</span></div>`).join("")}</div>
      <p class="st-sub">Desde julio, cuando tu nómina empezó a llegar a Lulo, tu movimiento mensual subió más de 50%.</p>`}},
  {id:"nomina",theme:"ink",name:"Tu ingreso",key:"nomina",
    spec:"El dato son los abonos del mismo originador. El momento de protección ofrece el seguro de nómina de Chubb.",
    html:()=>`<div class="st-kick">Tu ingreso</div><div class="st-dots">${[1,2,3].map(()=>`<i></i>`).join("")}</div><div class="st-big">3 de 3</div><div class="st-line">nóminas de ACME S.A.S. llegaron a tiempo</div><p class="st-sub">Desde julio Lulo es la cuenta donde recibes tu sueldo.</p>`,
    protect:{t:"Si un mes no llega, que no se note",d:"Seguro de nómina con Chubb: hasta 3 meses de tu ingreso si pierdes el empleo. Desde $14.500 al mes."}},
  {id:"carro",theme:"lime",name:"Tu carro",key:"soat",
    spec:"El dato son peajes, combustible y parqueaderos. El momento de protección conecta con el recordatorio de vencimiento: renovar el SOAT antes de que venza.",
    html:()=>`<div class="st-kick">Tu carro</div><div class="st-two"><div><div class="st-big">46</div><div class="st-line">peajes</div></div><div><div class="st-big">31</div><div class="st-line">tanqueadas</div></div></div><p class="st-sub">Casi $3 millones en combustible. Tu ruta más repetida fue la Autopista Norte.</p>`},
  {id:"viajes",theme:"navy",name:"Tus viajes",key:"viaje",
    spec:"El dato son los abonos a la cajita «Viajes». El momento de protección ofrece seguro de viaje con IGS.",
    html:()=>`<div class="st-kick">Tus viajes</div><div class="st-big">$1,2 M</div><div class="st-line">ahorrados en tu cajita «Viajes»</div><p class="st-sub">4 abonos de $300.000. Parece que se viene un viaje.</p>`,
    protect:{t:"Que el viaje sea solo de buenos recuerdos",d:"Seguro de viaje con IGS: asistencia médica en el exterior hasta USD 30.000. $18.900 por viaje."}},
  {id:"personas",theme:"pink",name:"Tu gente",key:"vida",
    spec:"El dato son transferencias fijas a un mismo tercero. El momento de protección ofrece vida voluntario, que todavía es un producto por negociar.",
    html:()=>`<div class="st-kick">Tu gente</div><div class="st-big">$1,8 M</div><div class="st-line">enviados a Laura M.</div><p class="st-sub">Le transferiste todos los meses desde junio, sin fallar uno. Alguien cuenta contigo.</p>`,
    protect:{t:"Que Laura siga contando contigo",d:"Vida voluntario con AXA Colpatria: tú eliges a quién proteger. Desde $22.000 al mes.",concept:true}},
  {id:"credito",theme:"navy",name:"Tu crédito",ask:"pago",
    spec:"Muestra un beneficio que el cliente ya tiene y no percibe: el pago protegido de su crédito. Pregunta si lo sabía.",
    html:()=>`<div class="st-kick">Tu crédito</div><div class="st-big">3 de 18</div><div class="st-line">cuotas de Lulo Crédito pagadas a tiempo</div><p class="st-sub">Y estuvieron protegidas: con pago protegido de SBS, si pierdes el empleo se cubren hasta 6 cuotas de $275.192.</p>`},
  {id:"cierre",theme:"lime",name:"Tu año, protegido",
    spec:"Cierre del resumen: lo que el cliente tiene cubierto, lo que activó en el recorrido y lo que queda sugerido. Permite compartir el año.",
    html:()=>{
      const has=S.policies.map(p=>p.title.replace(" · WGY-482",""));
      const left=["nomina","viaje","vida"].filter(k=>!hasPolicy(k)).map(k=>OFFERS[k].title);
      return `<div class="st-kick">Tu año, protegido</div><div class="st-big">${S.policies.length}</div><div class="st-line">protecciones activas al cerrar tu año</div>
      <div class="st-list">${has.map(h=>`<span>${h}</span>`).join("")}</div>
      ${left.length?`<p class="st-sub">Te quedan por revisar: ${left.join(", ")}.</p>`:`<p class="st-sub">Cubriste todos los momentos que encontramos este año.</p>`}
      <div class="st-acts"><button class="btn primary dark" data-a="st-share">Compartir mi año</button><button class="btn ghost" data-a="st-close">Cerrar</button></div>`}}
];
function hasPolicy(k){ return !!S.policies.find(p=>p.id===k+"-new"); }
function protectBlock(c){
  if(c.key==="soat"){
    if(S.soatRenewed) return `<div class="st-protect"><div class="st-pk">Momento de protección</div><div class="st-pt">Tu SOAT ya está al día</div><div class="st-pd">Vigente hasta el 13 de octubre de 2027.</div></div>`;
    if(S.control||!S.sugg) return "";
    return `<div class="st-protect"><div class="st-pk">Momento de protección</div><div class="st-pt">Tu SOAT vence el 14 de octubre</div><div class="st-pd">Renuévalo aquí sin salir de Lulo, con descuento por anticipación.</div><div class="st-pb"><button class="btn primary" data-a="st-soat">Renovar ahora</button></div></div>`;
  }
  if(c.ask){
    if(S.known[c.ask]) return `<div class="st-protect"><div class="st-pd">Gracias por responder.</div></div>`;
    return `<div class="st-protect"><div class="st-pt">¿Sabías que tenías esta protección?</div><div class="q-btns"><button data-a="st-known" data-v="Sí">Sí, lo sabía</button><button data-a="st-known" data-v="No">No sabía</button></div></div>`;
  }
  if(!c.protect) return "";
  if(hasPolicy(c.key)) return `<div class="st-protect"><div class="st-pk">Momento de protección</div><div class="st-pt">Ya lo tienes activo</div><div class="st-pd">${OFFERS[c.key].title} con ${OFFERS[c.key].aliado}.</div></div>`;
  if(S.control||!S.sugg) return "";
  if(S.declined[c.key]) return `<div class="st-protect"><div class="st-pd">Entendido. No te lo mostraremos en este resumen.</div></div>`;
  return `<div class="st-protect"><div class="st-pk">Momento de protección${c.protect.concept?` <span class="pill hyp">Producto por negociar</span>`:""}</div><div class="st-pt">${c.protect.t}</div><div class="st-pd">${c.protect.d}</div><div class="st-pb"><button class="btn primary" data-a="st-yes" data-k="${c.key}">Activar</button><button class="btn ghost" data-a="st-no" data-k="${c.key}">Ahora no</button></div></div>`;
}
function openStory(i){
  if(!S.storyOpened){
    S.storyOpened=true;
    msg("<b>Tu año en Lulo:</b> el motor leyó 12 meses de movimientos y armó un capítulo por cada momento. Mira el teléfono.");
    runChain(2);
    addLog("Tu año en Lulo","Resumen anual","Abrió el resumen","info");
    if(S.control) addLog("Tu año en Lulo","Momentos de protección","Grupo de control: resumen sin ofertas","ctrl");
  }
  if(S.screen!=="story") S.stack.push(S.screen==="story"?"anio":S.screen);
  S.story=i; S.screen="story"; render(); $("#scroll").scrollTop=0; storySeen();
}
function storySeen(){
  if(S.story===CHAPTERS.length-1 && !S.storyDone){ S.storyDone=true; addLog("Tu año en Lulo","Resumen anual","Completó el resumen","info"); }
}
function storyStep(d){
  const n=S.story+d;
  if(n<0) return;
  if(n>=CHAPTERS.length){ closeStory(); return; }
  S.story=n; render(); storySeen();
}
function closeStory(){ S.screen=S.stack.pop()||"anio"; if(S.screen==="story") S.screen="anio"; render(); }
function activate(k,src){
  const O=OFFERS[k]; if(!O) return false;
  if(!hasPolicy(k)) S.policies.push({id:k+"-new",title:O.title,aliado:O.aliado,status:"ok",sub:O.sub});
  addLog(src,O.title,"Aceptó","ok"); return true;
}

/* ---------- estado ---------- */
let S;
function initState(){
  S = {
    screen:"home", stack:[], offer:null, story:0, storyOpened:false, storyDone:false, declined:{},
    policies:clone(BOOT.policies),
    movs:clone(BOOT.movs),
    balance:BOOT.balance, log:[], queue:[], shown:null, control:false, sugg:true, remind:true, alertDays:30,
    soatRenewed:false, known:{}
  };
}

/* ---------- log & motor ---------- */
function addLog(ev, offer, res, tipo){
  S.log.unshift({t:now(),ev,offer,res,tipo});
  if(["ok","no","harm","info","val"].includes(tipo)) lightStep(3);
  renderPanel();
}
let chainTimer=[];
function lightStep(i){ const el=$(`.step[data-step="${i}"]`); el.classList.add("on"); if(i===3){el.classList.remove("missing")} setTimeout(()=>el.classList.remove("on"),1400); }
function runChain(upTo, done){
  chainTimer.forEach(clearTimeout); chainTimer=[];
  document.querySelectorAll(".step").forEach(s=>s.classList.remove("on"));
  for(let i=0;i<=upTo;i++){ chainTimer.push(setTimeout(()=>lightStep(i), i*380)); }
  chainTimer.push(setTimeout(done||(()=>{}), upTo*380+320));
}

/* El paso 2 (decidir) lo resuelve el motor en Python: POST /api/engine/event */
let busy=Promise.resolve();
function fire(key){
  // Los eventos se procesan en orden, uno detrás de otro, como llegarían al motor.
  busy = busy.then(()=>fireNow(key)).catch(()=>{});
  return busy;
}
async function fireNow(key){
  const E = EVENTS[key];
  S.movs.unshift({...E.mov,d:"Ahora",flash:true});
  S.balance += E.mov.a;
  if(S.screen==="home"||S.screen==="movs") render();
  runChain(0);
  const ctx = {event:key, control:S.control, suggestions:S.sugg, soat_renewed:S.soatRenewed,
    soat_days:S.policies[0].days, active:S.policies.filter(p=>p.id.endsWith("-new")).map(p=>p.id.slice(0,-4)),
    window:S.shown?{key:S.shown.key||"vehiculo",prio:S.shown.prio||EVENTS.vehiculo.prio,kind:S.shown.kind==="renew"?"renew":"offer",offerName:S.shown.offerName,ev:S.shown.ev,text:S.shown.text||""}:null,
    queue:S.queue};
  let R;
  try{ const t0=performance.now(); R = await (await api("/api/engine/event", ctx)).json();
    apiStatus("ok",`<b>Motor en Python conectado</b> · última decisión en ${Math.round(performance.now()-t0)} ms`); }
  catch(e){ apiStatus("err","<b>El motor no respondió.</b> El movimiento quedó, pero no hubo decisión."); msg("<b>Error:</b> no se pudo consultar el motor."); return; }
  S.queue = R.queue;
  if(R.outcome==="shown"){ show(R.decision); await wait(3*380+400); return; }
  msg(R.message); runChain(R.chain);
  if(R.log) addLog(R.log.ev,R.log.offer,R.log.res,R.log.tipo);
}
function show(d){
  S.shown = d; msg(`<b>Se muestra:</b> ${d.offerName}. ${d.kind==="info"?"Ya tiene la cobertura, así que se le explica en vez de venderle otra.":d.kind==="renew"?"El SOAT está por vencer: se ofrece renovar.":"Es elegible y la ventana está libre."} Mira el teléfono.`);
  runChain(2, ()=>{
    const n=$("#notif");
    n.innerHTML=`<span class="ic"><img src="${IMG_LOGO}" alt=""></span><span style="flex:1"><span class="t"><span>Lulo Bank</span><span>ahora</span></span><span class="b">${d.text}</span></span>`;
    n.classList.add("show"); $("#notifX").classList.add("show");
    addLog(d.ev,d.offerName,"Mostrada en la app","info");
  });
  renderPanel();
}
function hideNotif(){ $("#notif").classList.remove("show"); $("#notifX").classList.remove("show"); }
function closeWindow(){ S.shown=null; renderPanel(); }

$("#notif").addEventListener("click",()=>{
  const d=S.shown; if(!d) return; hideNotif();
  if(d.kind==="renew") go("renew");
  else { S.offer=d.key; go("offer"); }
});
$("#notifX").addEventListener("click",()=>{ const d=S.shown; hideNotif(); if(d){addLog(d.ev,d.offerName,"Descartó la notificación","no"); closeWindow();} });

/* ---------- navegación ---------- */
function go(screen, push=true){
  if(push && S.screen!==screen) S.stack.push(S.screen);
  S.screen=screen; render(); $("#scroll").scrollTop=0;
}
function back(){
  if(S.screen==="offer" && S.shown){ addLog(S.shown.ev,S.shown.offerName,"Cerró sin decidir","no"); closeWindow(); }
  if(S.screen==="renew" && S.shown){ addLog(S.shown.ev,S.shown.offerName,"Cerró sin decidir","no"); closeWindow(); }
  S.screen=S.stack.pop()||"home"; render();
}
function tabTo(t){ S.stack=[]; S.screen=t; render(); $("#scroll").scrollTop=0; }
function toast(msg){ const t=$("#toast"); t.textContent=msg; t.classList.add("show"); clearTimeout(t._h); t._h=setTimeout(()=>t.classList.remove("show"),2200); }

/* ---------- iconos ---------- */
const I = {
  home:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M4 10.5 12 4l8 6.5V20H4z"/><path d="M10 20v-5h4v5"/></svg>',
  movs:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M5 8h14M5 12h14M5 16h9"/></svg>',
  year:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M12 3l2.2 5.3L20 9l-4.4 3.8L17 18.5 12 15.6 7 18.5l1.4-5.7L4 9l5.8-.7z"/></svg>',
  shield:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linejoin="round"><path d="M12 3 5 6v5.5c0 4.2 3 7.8 7 9.5 4-1.7 7-5.3 7-9.5V6z"/><path d="m9 12 2.2 2.2L15.5 10" stroke-linecap="round"/></svg>',
  user:'<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="8.5" r="3.5"/><path d="M5 20c.8-3.6 3.6-5.5 7-5.5s6.2 1.9 7 5.5" stroke-linecap="round"/></svg>',
  back:'<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"><path d="M15 5l-7 7 7 7"/></svg>',
  send:'<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#E5FF00" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h13M13 6l6 6-6 6"/></svg>',
  box:'<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#E5FF00" stroke-width="2" stroke-linejoin="round"><path d="M4 8h16v11H4zM3 5h18v3H3zM10 12h4"/></svg>',
  coin:'<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#E5FF00" stroke-width="2"><circle cx="12" cy="12" r="8"/><path d="M12 8v8M9.5 10.5h4a1.5 1.5 0 0 1 0 3h-3" stroke-linecap="round"/></svg>',
  bre:'<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#E5FF00" stroke-width="2" stroke-linecap="round"><path d="M13 3 6 13h6l-1 8 7-10h-6z" stroke-linejoin="round"/></svg>',
  check:'<svg width="46" height="46" viewBox="0 0 24 24" fill="none" stroke="#061232" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5 10 17 19 7.5"/></svg>'
};

/* ---------- pantallas ---------- */
function topbar(title){ return `<div class="topbar"><button class="back" data-a="back" aria-label="Volver">${I.back}</button><h2>${title}</h2></div>`; }
function movRow(m){ return `<div class="mov${m.flash?" flash":""}"><span class="ic">${m.ic}</span><div class="t"><div>${m.n}</div><div>${m.c} · ${m.d}</div></div><span class="a ${m.a>0?"in":""}">${m.a>0?"+":""}${money(m.a)}</span></div>`; }

const SCREENS = {
  home(){
    const soat=S.policies[0];
    return `
    <div class="hello"><div><div class="sub" style="margin:0">Buenos días</div><div style="font-size:18px;font-weight:700">Hola, Sebas</div></div><div class="avatar" aria-hidden="true">S</div></div>
    <div class="balance"><div class="sub" style="margin:0">Saldo disponible</div><div class="n">${money(S.balance)}</div></div>
    <div class="bank-card"><img src="${IMG_CARD}" alt="Tarjeta débito Lulo Bank"></div>
    <div class="quick">
      <button><span class="ic">${I.send}</span>Enviar</button>
      <button><span class="ic">${I.bre}</span>Bre-B</button>
      <button><span class="ic">${I.box}</span>Cajitas</button>
      <button><span class="ic">${I.coin}</span>Crédito</button>
    </div>
    ${!S.soatRenewed && S.remind ? `
    <button class="reminder" data-a="renew-direct">
      <span class="cal"><b>14</b><small>OCT</small></span>
      <span style="flex:1"><span style="display:block;font-weight:700;font-size:14.5px">Tu SOAT vence en ${soat.days} días</span><span style="display:block;font-size:12.5px;margin-top:3px">WGY-482 · Renuévalo aquí con descuento por anticipación</span></span>
    </button>` : ``}
    <button class="home-year" data-a="tab" data-t="anio"><span class="yy">12m</span><span style="flex:1"><span style="display:block;font-weight:700;font-size:14.5px">Tu año en Lulo ya está listo</span><span style="display:block;font-size:12.5px;margin-top:3px;color:var(--mist)">1.284 movimientos contados en 8 capítulos</span></span></button>
    <div class="sec-title">Últimos movimientos</div>
    ${S.movs.slice(0,3).map(movRow).join("")}
    <div style="height:18px"></div>`;
  },
  movs(){
    return `<div class="pad" style="padding-top:8px"><h2 class="h-big">Movimientos</h2><p class="sub">Cada movimiento es una señal que el motor puede leer.</p></div>
    <div style="height:10px"></div>${S.movs.map(movRow).join("")}<div style="height:18px"></div>`;
  },
  anio(){
    const sw={lime:"background:var(--lime);color:var(--ink)",navy:"background:var(--navy-3)",ink:"background:var(--ink);border:1px solid var(--line)",pink:"background:var(--pink);color:var(--ink)"};
    const st=c=> c.key==="soat"?(S.soatRenewed?"Al día":"Por renovar"):c.ask?(S.known[c.ask]?"Respondido":""):c.key&&hasPolicy(c.key)?"Activo":"";
    return `<div class="yr-hero"><div class="k">Tu año en Lulo</div><div class="y">2026</div><p>Lo que viviste con Lulo de octubre a septiembre, contado con tus movimientos.</p><button class="btn" data-a="st-open" data-i="0">Ver mi año</button></div>
    <div class="sec-title">Capítulos</div>
    ${CHAPTERS.slice(1).map((c,i)=>`<button class="chap" data-a="st-open" data-i="${i+1}"><span class="sw" style="${sw[c.theme]}">${i+1}</span><span class="tx"><b>${c.name}</b><span>${c.key?"Incluye un momento de protección":c.ask?"Incluye una pregunta":"Resumen"}</span></span><span class="ok" style="${st(c)==="Por renovar"?"color:var(--warn)":""}">${st(c)}</span></button>`).join("")}
    <div class="pad" style="margin-top:14px"><div class="card" style="font-size:12.5px;color:#C9D0DE;line-height:1.5">Lo armamos solo con tus movimientos en Lulo. Puedes apagar las sugerencias de seguros en Perfil.</div></div>
    <div style="height:20px"></div>`;
  },
  story(){
    const c=CHAPTERS[S.story], last=S.story===CHAPTERS.length-1;
    return `<div class="story t-${c.theme}">
      <div class="st-prog">${CHAPTERS.map((_,i)=>`<i class="${i<=S.story?"on":""}"></i>`).join("")}</div>
      <div class="st-head"><span>Tu año en Lulo · ${S.story+1} de ${CHAPTERS.length}</span><button class="st-x" data-a="st-close" aria-label="Cerrar">✕</button></div>
      <button class="st-zone prev" data-a="st-prev" aria-label="Capítulo anterior"></button><button class="st-zone next" data-a="st-next" aria-label="Siguiente capítulo"></button>
      <div class="st-body" key="${S.story}">${c.html()}</div>
      ${protectBlock(c)}
      <div class="st-nav"><button data-a="st-prev" ${S.story===0?"disabled":""}>Anterior</button><button data-a="st-next">${last?"Terminar":"Siguiente"}</button></div>
    </div>`;
  },
  offer(){
    const k=S.offer, O=OFFERS[k];
    return `${topbar("Recomendado para ti")}
    <div class="pad"><div class="row" style="justify-content:flex-start;gap:8px"><span class="pill new">Sugerencia</span>${O.concept?`<span class="pill hyp">Producto por negociar con la aseguradora</span>`:""}</div>
      <h2 class="h-big" style="margin-top:12px">${O.title}</h2><p class="sub">Con ${O.aliado}</p></div>
    <div class="pad" style="margin-top:16px"><div class="why"><b>Por qué lo ves:</b> ${O.why}</div></div>
    <div class="pad" style="margin-top:16px"><div class="card"><div class="figure">${O.figure}</div><div class="meta" style="margin-top:2px">${O.figLabel}</div></div></div>
    <div class="sec-title">Qué cubre</div>
    <div class="pad"><ul class="list-check">${O.covers.map(c=>`<li>${c}</li>`).join("")}</ul></div>
    <div class="pad" style="margin-top:18px"><div class="card" style="padding:4px 16px"><div class="kv"><span>Valor</span><span style="font-weight:700">${O.price}</span></div><div class="kv"><span>Se paga desde</span><span>Cuenta Lulo</span></div></div></div>
    <div class="actions">
      <button class="btn primary" data-a="accept">Activar seguro</button>
      <button class="btn ghost" data-a="later">Ahora no</button>
      <button class="btn text" data-a="optout">No quiero sugerencias de este tipo</button>
    </div>`;
  },
  renew(){
    const Q=BOOT.soatQuotes[S.alertDays], base=Q.base, disc=Q.discount, total=Q.total;
    S._total=total;
    return `${topbar("Renovar SOAT")}
    <div class="pad"><div class="card"><div class="row"><span class="ttl">WGY-482</span><span class="pill warn">Vence en 27 días</span></div><div class="meta">Chevrolet Onix 2021 · Seguros Mundial</div><div class="bar"><i style="width:92%"></i></div></div></div>
    <div class="sec-title">Nueva vigencia</div>
    <div class="pad"><div class="card" style="padding:4px 16px">
      <div class="kv"><span>Desde</span><span>14 oct 2026</span></div>
      <div class="kv"><span>Hasta</span><span>13 oct 2027</span></div>
    </div></div>
    <div class="sec-title">Resumen de pago</div>
    <div class="pad"><div class="card" style="padding:4px 16px">
      <div class="kv"><span>Valor SOAT</span><span>${money(base)}</span></div>
      <div class="kv"><span>Descuento por renovar antes</span><span style="color:var(--lime)">${money(-disc)}</span></div>
      <div class="kv"><span style="color:#fff;font-weight:600">Total</span><span style="font-weight:700;font-size:16px">${money(total)}</span></div>
      <div class="kv"><span>Se paga desde</span><span>Cuenta Lulo · ${money(S.balance)}</span></div>
    </div></div>
    <div class="pad" style="margin-top:12px"><div class="why">El descuento por anticipación es una hipótesis a validar: cuánta anticipación hace que cambie la decisión.</div></div>
    <div class="actions">
      <button class="btn primary" data-a="pay">Pagar ${money(total)}</button>
      <button class="btn ghost" data-a="postpone">Recuérdamelo después</button>
    </div>`;
  },
  paying(){ return `<div class="spinner"></div><p class="sub" style="text-align:center">Procesando el pago con Seguros Mundial…</p>`; },
  done(){
    return `<div class="success"><div class="ring">${I.check}</div>
      <h2 class="h-big" style="margin-top:22px">Tu SOAT quedó renovado</h2>
      <p class="sub">WGY-482 está cubierto hasta el 13 de octubre de 2027. Te avisaremos ${S.alertDays} días antes del próximo vencimiento.</p></div>
      <div class="actions" style="margin-top:20px"><button class="btn primary" data-a="tab" data-t="home">Volver al inicio</button><button class="btn ghost" data-a="tab" data-t="anio">Ver Tu año en Lulo</button></div>`;
  },
  perfil(){
    return `<div class="pad" style="padding-top:8px"><h2 class="h-big">Perfil</h2><p class="sub">Sebastián · Cliente Lulo desde 2023</p></div>
    <div class="sec-title">Notificaciones</div>
    <div class="stack">
      <div class="card"><div class="row"><div><div class="ttl" style="font-size:14px">Sugerencias de seguros</div><div class="meta">Según lo que haces en la app</div></div><button class="switch" role="switch" aria-checked="${S.sugg}" aria-label="Sugerencias de seguros" data-a="sugg"></button></div></div>
      <div class="card"><div class="row"><div><div class="ttl" style="font-size:14px">Avisos de vencimiento</div><div class="meta">SOAT, tecnomecánica y pólizas</div></div><button class="switch" role="switch" aria-checked="${S.remind}" aria-label="Avisos de vencimiento" data-a="remind"></button></div>
        <div class="meta" style="margin:14px 0 8px">Avísame con</div>
        <div class="seg">${[30,15,7].map(d=>`<button aria-pressed="${S.alertDays===d}" data-a="days" data-d="${d}">${d} días</button>`).join("")}</div>
      </div>
    </div>`;
  }
};

function render(){
  $("#scroll").innerHTML = SCREENS[S.screen]();
  const tabs=[["home","Inicio",I.home],["movs","Movimientos",I.movs],["anio","Tu año",I.year],["perfil","Perfil",I.user]];
  const cur = S.screen==="story" ? "anio" : ["renew","offer","paying","done"].includes(S.screen) ? (S.stack.find(s=>tabs.some(t=>t[0]===s)) || "home") : S.screen;
  const th = S.screen==="story" ? CHAPTERS[S.story].theme : null;
  const bg={lime:["var(--lime)","var(--ink)"],navy:["var(--navy)","#fff"],ink:["var(--ink)","#fff"],pink:["var(--pink)","var(--ink)"]};
  const stb=document.querySelector(".status"); stb.style.background=th?bg[th][0]:""; stb.style.color=th?bg[th][1]:"";
  stb.querySelectorAll(".sig i").forEach(x=>x.style.background=th?bg[th][1]:"");
  $("#tabbar").style.display = S.screen==="story" ? "none" : "flex";
  $("#tabbar").innerHTML = tabs.map(([k,l,ic])=>`<button class="tab" data-a="tab" data-t="${k}" ${cur===k?'aria-current="page"':""}>${ic}${l}</button>`).join("");
  S.movs.forEach(m=>m.flash=false);
  updateNow();
}


function acceptOffer(){
  const k=S.offer; if(!OFFERS[k]) return;
  activate(k, S.shown?S.shown.ev:"Entrada directa"); closeWindow();
  S.stack=[]; S.screen="home"; render(); $("#scroll").scrollTop=0; toast("Activado. Aparecerá al cierre de Tu año");
}
function pay(){
  if(S.soatRenewed||S.screen!=="renew") return;
  const src=S.shown&&S.shown.kind==="renew"?S.shown.ev:"Recordatorio en la app";
  go("paying",false);
  setTimeout(()=>{
    S.soatRenewed=true; S.balance-=S._total;
    Object.assign(S.policies[0],{status:"ok",sub:"vigente hasta el 13 oct 2027",days:392});
    S.movs.unshift({n:"SOAT WGY-482 · Seguros Mundial",c:"Seguros",a:-S._total,ic:"🛡️",d:"Ahora",flash:true});
    addLog(src,"Renovar SOAT","Renovó en Lulo (captura de canal)","ok"); closeWindow();
    S.stack=[]; go("done",false);
  },1300);
}
function setKnown(id,v){ S.known[id]=v; const p=S.policies.find(x=>x.id===id); addLog("Tu año en Lulo · Tu crédito",p?p.title:id,`¿Sabía que lo tenía? ${v}`,"val"); render(); toast("Gracias por responder"); }
function toggleSugg(){ S.sugg=!S.sugg; if(!S.sugg) addLog("Perfil","Sugerencias de seguros","Desactivó sugerencias","harm"); else addLog("Perfil","Sugerencias de seguros","Reactivó sugerencias","info"); render(); }
function msg(h){ const m=$("#chainMsg"); if(m) m.innerHTML=h; }
/* ---------- acciones en el teléfono ---------- */
$("#phone").addEventListener("click",e=>{
  const b=e.target.closest("[data-a]"); if(!b) return;
  const a=b.dataset.a;
  if(a==="back") back();
  else if(a==="tab"){ if(S.screen==="offer"&&S.shown){addLog(S.shown.ev,S.shown.offerName,"Cerró sin decidir","no");closeWindow();} tabTo(b.dataset.t); }
  else if(a==="st-open") openStory(+b.dataset.i);
  else if(a==="st-next") storyStep(1);
  else if(a==="st-prev") storyStep(-1);
  else if(a==="st-close") closeStory();
  else if(a==="st-yes"){ const c=CHAPTERS[S.story]; activate(b.dataset.k,"Tu año en Lulo · "+c.name); render(); toast("Activado"); }
  else if(a==="st-no"){ const c=CHAPTERS[S.story]; S.declined[b.dataset.k]=true; addLog("Tu año en Lulo · "+c.name,OFFERS[b.dataset.k].title,"Rechazó: ahora no","no"); render(); }
  else if(a==="st-soat"){ if(S.shown){ hideNotif(); addLog(S.shown.ev,S.shown.offerName,"Ventana cerrada sin respuesta","no"); } S.shown={kind:"renew",ev:"Tu año en Lulo · Tu carro",offerName:"Renovar SOAT"}; go("renew"); }
  else if(a==="st-known"){ setKnown("pago",b.dataset.v); }
  else if(a==="st-share"){ addLog("Tu año en Lulo","Resumen anual","Compartió su año","info"); toast("Imagen lista para compartir"); }
  else if(a==="renew-direct"){ if(!S.soatRenewed) go("renew"); }
  else if(a==="accept") acceptOffer();
  else if(a==="later"){ addLog(S.shown?S.shown.ev:"Entrada directa",OFFERS[S.offer].title,"Rechazó: ahora no","no"); closeWindow(); back(); toast("Listo, no te lo volveremos a mostrar pronto"); }
  else if(a==="optout"){ addLog(S.shown?S.shown.ev:"Entrada directa",OFFERS[S.offer].title,"Pidió no ver este tipo de sugerencias","harm"); closeWindow(); back(); toast("No verás más sugerencias de este tipo"); }
  else if(a==="pay") pay();
  else if(a==="postpone"){ const src=S.shown&&S.shown.kind==="renew"?S.shown.ev:"Recordatorio en la app"; addLog(src,"Renovar SOAT","Pospuso la renovación","no"); closeWindow(); S.screen=S.stack.pop()||"home"; render(); toast("Te lo recordaremos en 7 días"); }
  else if(a==="sugg") toggleSugg();
  else if(a==="remind"){ S.remind=!S.remind; if(!S.remind) addLog("Perfil","Avisos de vencimiento","Desactivó avisos","harm"); render(); }
  else if(a==="days"){ S.alertDays=+b.dataset.d; addLog("Perfil","Anticipación del aviso",`Prefiere ${S.alertDays} días`,"val"); render(); }
});

document.addEventListener("keydown",e=>{ if(S.screen!=="story") return; if(e.key==="ArrowRight") storyStep(1); if(e.key==="ArrowLeft") storyStep(-1); if(e.key==="Escape") closeStory(); });
/* ---------- panel ---------- */
function renderEvents(){
  $("#events").innerHTML = Object.entries(EVENTS).map(([k,E])=>`<button class="ev" data-ev="${k}"><span class="n">${E.label}</span><span class="h">${E.habit} · prioridad ${E.prio}</span><span class="o">${E.offer}</span></button>`).join("");
}
function renderPanel(){
  const L=S.log;
  const shown=L.filter(l=>l.res==="Mostrada en la app").length;
  const ok=L.filter(l=>l.tipo==="ok").length;
  const no=L.filter(l=>l.tipo==="no").length;
  const harm=L.filter(l=>l.tipo==="harm").length;
  $("#metrics").innerHTML=[
    [shown,"Ofertas mostradas"],[ok,"Aceptadas o renovadas"],[no,"Rechazadas o pospuestas"],[harm,"Señales de daño",true]
  ].map(([v,l,h])=>`<div class="metric ${h?"harm":""}"><div class="v">${v}</div><div class="l">${l}</div></div>`).join("");
  $("#queue").innerHTML = S.queue.length ? S.queue.map(q=>`<span class="qitem"><b>P${q.prio}</b> ${q.offerName}</span>`).join("") : `<span class="empty">${S.shown?"Ventana ocupada: "+S.shown.offerName+". La cola está vacía.":"Ventana de contacto libre. La cola está vacía."}</span>`;
  $("#nextWin").disabled = !S.queue.length;
  const dl=$("#demoLast"); if(dl) dl.innerHTML = L.length?`<b style="color:#fff">Último registro</b>${L[0].offer}: ${L[0].res}`:`<b style="color:#fff">Último registro</b>Todavía no hay respuestas.`;
  $("#ctrlBtn").setAttribute("aria-pressed",S.control);
  $("#log").innerHTML = L.length ? L.map(l=>`<div class="log-row"><time>${l.t}</time><span class="e"><b>${l.offer}</b><br>${l.ev} · ${l.res}</span><span class="tag ${l.tipo}">${({ok:"Acepta",no:"Rechaza",hold:"Cola",ctrl:"Sin contacto",harm:"No daño",info:"Contacto",val:"Validación"})[l.tipo]}</span></div>`).join("") : `<span class="empty">Todavía no hay respuestas. Este es el paso que hoy no existe en Lulo Bank.</span>`;
}
$("#events").addEventListener("click",e=>{ const b=e.target.closest("[data-ev]"); if(b) fire(b.dataset.ev); });
$("#nextWin").addEventListener("click",()=>{
  if(S.shown){ hideNotif(); addLog(S.shown.ev,S.shown.offerName,"Ventana cerrada sin respuesta","no"); closeWindow(); }
  const d=S.queue.shift(); if(d) show(d);
});
$("#ctrlBtn").addEventListener("click",()=>{ S.control=!S.control; renderPanel(); });
function resetAll(){ hideNotif(); initState(); demoDone.clear(); renderDemo(); msg("Dispara un evento para ver cómo decide el motor."); document.querySelectorAll(".step")[3].classList.add("missing"); render(); renderPanel(); toast("Demo reiniciada"); }
$("#resetBtn").addEventListener("click",resetAll); $("#resetBtn2").addEventListener("click",resetAll);

/* =================== v2: especificación, pestañas, demo =================== */
const NOW = {
  home:{n:"Inicio",tag:"Futuro · Recordatorio del SOAT",
    what:"La primera pantalla del cliente: saldo, tarjeta, accesos rápidos y el aviso del SOAT en lima, que es el punto de entrada de la idea 3.",
    how:["Toca el aviso «Tu SOAT vence en 27 días» para ir directo a renovar.","La tarjeta «Tu año en Lulo» abre el resumen de los últimos 12 meses.","Los movimientos se actualizan cuando disparas eventos en el motor."],
    val:"Si el cliente espera comprar el SOAT en una app bancaria y si el aviso en Inicio basta sin notificación push."},
  movs:{n:"Movimientos",tag:"Materia prima del motor",
    what:"El extracto del cliente. Cada fila es una señal: peajes y combustible anticipan el SOAT, abonos del mismo originador anticipan nómina, transferencias fijas anticipan vida.",
    how:["Dispara un evento en «Motor en vivo» y verás aparecer el movimiento resaltado arriba.","El saldo de Inicio cambia con cada abono o pago."],
    val:"Qué eventos están instrumentados hoy en la app y con qué latencia llegan (sesión con Analítica)."},
  anio:{n:"Tu año en Lulo",tag:"Pasado · Tu año en Lulo",
    what:"La portada del resumen anual. El cliente ve su año contado en 8 capítulos armados con sus propios movimientos, y cuáles traen un momento de protección.",
    how:["«Ver mi año» abre la historia desde el principio.","Cada capítulo de la lista abre la historia en ese punto.","La columna de la derecha muestra lo que ya activó, renovó o respondió."],
    val:"Si los clientes abren el resumen y qué capítulos les parecen útiles o invasivos."},
  story:{n:"Tu año en Lulo",tag:"Pasado · Tu año en Lulo",what:"",
    how:["Toca a la derecha para avanzar y a la izquierda para volver. En computador también sirven las flechas del teclado.","«Activar» registra la aceptación desde el capítulo que la generó.","«Ahora no» registra el rechazo y el capítulo no insiste.","La X cierra la historia."],
    val:"Finalización del resumen y aceptación por capítulo frente al grupo de control."},
  offer:{n:"Oferta recomendada",tag:"Presente · Motor de disparadores",
    what:"Lo que ve el cliente cuando el motor detecta un momento. Muestra por qué se le ofrece, qué cubre, cuánto cuesta y desde dónde se paga.",
    how:["«Activar seguro» registra la aceptación y la protección aparece al cierre de Tu año.","«Ahora no» registra un rechazo sin castigar al cliente.","«No quiero sugerencias de este tipo» cuenta como señal de daño."],
    val:"La aceptación incremental por evento frente al grupo de control, no la tasa bruta."},
  renew:{n:"Renovación del SOAT",tag:"Futuro · Recordatorio del SOAT",
    what:"La compra ya estaba decidida: el cliente la iba a hacer de todos modos. Esta pantalla compite solo por el canal, con vigencia clara, descuento por anticipación y pago desde la cuenta Lulo.",
    how:["«Pagar» renueva, descuenta el saldo y agrega el movimiento.","«Recuérdamelo después» registra que pospuso.","El descuento cambia si en Perfil eliges avisos con 15 o 7 días."],
    val:"Cuánta anticipación hace que el descuento cambie la decisión."},
  paying:{n:"Procesando el pago",tag:"Futuro · Recordatorio del SOAT",what:"Estado intermedio mientras se confirma con la aseguradora.",how:["Espera un segundo."],val:"Nada, es un estado de espera."},
  done:{n:"Renovación confirmada",tag:"Futuro · Recordatorio del SOAT",
    what:"Cierra el ciclo: confirma la nueva vigencia y deja programado el próximo aviso. El capítulo «Tu carro» de Tu año pasa a mostrar el SOAT al día.",
    how:["«Volver al inicio» muestra que el aviso del SOAT ya no aparece.","«Ver Tu año en Lulo» muestra el capítulo del carro actualizado."],
    val:"Captura de canal: cuántos renuevan en Lulo y no por fuera."},
  perfil:{n:"Perfil y preferencias",tag:"Medición y no daño",
    what:"El cliente controla lo que recibe: sugerencias de seguros, avisos de vencimiento y anticipación del aviso.",
    how:["Apagar sugerencias hace que el motor deje de mostrar ofertas y queda como señal de daño.","Elegir 30, 15 o 7 días queda como dato de validación."],
    val:"Desactivación de notificaciones, uno de los cuatro indicadores de no daño."}
};
function updateNow(){
  const N=NOW[S.screen]; if(!N) return;
  let name=N.n;
  let what=N.what;
  if(S.screen==="story"){ const c=CHAPTERS[S.story]; name+=": "+c.name+" ("+(S.story+1)+" de "+CHAPTERS.length+")"; what=c.spec; }
  if(S.screen==="offer" && S.offer) name+=": "+OFFERS[S.offer].title;
  $("#nowName").textContent=name;
  $("#nowBody").innerHTML=`<span class="idea-tag">${N.tag}</span><div>${what}</div><h5>Qué puedes hacer aquí</h5><ul>${N.how.map(h=>`<li>${h}</li>`).join("")}</ul><h5>Qué valida o mide</h5><div>${N.val}</div>`;
}

const G = (t,label)=>`<button class="goto" data-goto="${t}">${label}</button>`;
const TBL = (head,rows)=>`<div class="tbl-w"><table class="tbl"><thead><tr>${head.map(h=>`<th>${h}</th>`).join("")}</tr></thead><tbody>${rows.map(r=>`<tr>${r.map(c=>`<td>${c}</td>`).join("")}</tr>`).join("")}</tbody></table></div>`;
const SUB = (t,body,open)=>`<details class="acc"${open?" open":""}><summary><span class="s-t">${t}</span></summary><div class="acc-b">${body}</div></details>`;
const UL = a=>`<ul>${a.map(x=>`<li>${x}</li>`).join("")}</ul>`;

const ACCS = [
 {g:"La propuesta"},
 {id:"acc-resumen",k:"Resumen",t:"La propuesta en una frase",d:"Tres ideas, un mismo mecanismo, sin producto nuevo",open:true,b:`
  <p>Leer lo que el cliente ya hace en la app, ofrecerle el seguro correcto en el momento en que lo necesita y <b>registrar su respuesta</b>. Las tres ideas se montan sobre ramos ya habilitados, así que se pueden probar sin esperar una negociación con la aseguradora.</p>
  <h5>El recorrido completo</h5>
  <div class="flow"><span>Algo pasa en la cuenta</span><i>→</i><span>El motor lo detecta</span><i>→</i><span>Una regla de prioridad escoge</span><i>→</i><span>El cliente decide</span><i>→</i><span>Queda registrado y aparece en Tu año</span></div>
  <div class="two" style="margin-top:10px">
   <div class="box"><b>Pasado</b>Lo que el cliente ya vivió: Tu año en Lulo.</div>
   <div class="box"><b>Presente</b>Lo que acaba de hacer: motor de disparadores.</div>
   <div class="box"><b>Futuro</b>Lo que se le viene: recordatorio de vencimiento.</div>
   <div class="box"><b>Siempre</b>Registrar la respuesta: el paso que hoy no existe.</div>
  </div>`},
 {id:"acc-cliente",k:"Retroalimentación",t:"Lo que dijo el cliente",d:"Lo que valoraron y lo que les preocupó del prototipo",b:`
  <div class="two">
   <div class="box"><b>Lo que valoraron</b>${UL(["El prototipo es interactivo: se puede recorrer como la app real.","Las tres soluciones responden al desafío.","Las ofertas aparecen en momentos reales del cliente."])}</div>
   <div class="box"><b>Lo que les preocupó</b>${UL(["Refinar el prototipo con los datos reales de Lulo Bank.","Construir los modelos con esos datos, que llegan en los próximos días.","Confirmar qué momentos tienen más impacto."])}</div>
  </div>
  <h5>Cómo lo recoge esta versión</h5>${UL(["Cada cifra de Tu año sale de una regla sobre movimientos, así que se puede recalcular con los datos reales sin cambiar el diseño.","El registro guarda la respuesta por capítulo y por evento: es la base para saber qué momento tiene más impacto.","El grupo de control aplica a Tu año y al motor, para medir efecto y no solo actividad."])}`},
 {id:"acc-problemas",k:"Contexto",t:"Dos problemáticas, no una",d:"Se parecen, pero se miden distinto",b:`
  <div class="two">
   <div class="box"><b>1. Ampliar la oferta de seguros</b>${UL(["Hay productos, pero nadie los ofrece: el modelo es de tirón.","Faltan ramos: vida solo existe atado al crédito y nómina no tiene un momento propio.","La comisión de seguros no consume capital regulatorio ni requiere fondeo, y la meta es el punto de equilibrio en 2026."])}<p style="margin-top:6px"><b>Se mide en</b> pólizas por cliente y tasa de renovación.</p></div>
   <div class="box"><b>2. Ampliar el mercado de Lulo Bank</b>${UL(["650.000 clientes activos, saldo promedio de $1,7 millones: es cuenta de movimiento, no la principal.","La tasa (7,84% E.A.) dejó de diferenciar frente a Nu, Ban100, Finandina y Contactar.","El SOAT responde a una necesidad que el cliente ya tiene fuera del banco: sirve de puerta de entrada."])}<p style="margin-top:6px"><b>Se mide en</b> clientes nuevos y profundidad de la relación.</p></div>
  </div>
  <h5>Lo que encontramos</h5><p>Lulo ya distribuye cinco seguros: vida grupo deudor (AXA Colpatria), SOAT (Seguros Mundial), desempleo (Chubb), pago protegido (SBS) y asistencias (IGS). Nunca ha habido una recomendación proactiva, así que no hay ninguna respuesta del cliente atribuible a un momento.</p>`},
 {id:"acc-brecha",k:"Contexto",t:"La brecha entre el cliente que hay y el que se quiere",d:"El perfil juega en contra, el comportamiento a favor",b:`
  ${TBL(["El cliente de hoy","El cliente que se busca"],[
   ["Joven, digital, relación corta con el banco","Con la nómina domiciliada en Lulo"],
   ["Saldo promedio de $1,7 millones: usa Lulo para mover","Ve a Lulo como su banco principal"],
   ["Cero seguros voluntarios contratados por recomendación","Con al menos un seguro voluntario vigente y renovado"],
   ["Alta frecuencia transaccional (Bre-B: más de 110 millones de operaciones en un mes)","Deja un registro de decisión: aceptó o rechazó, y en qué momento"]])}
  <h5>Por qué no basta con campañas por perfil</h5>
  ${UL(["El tenedor típico de seguro de vida es mayor y lleva más años con su banco: 44,5 frente a 41,4 años de edad y 11,98 frente a 9,11 años de relación (Boustani et al., 2024).","Los mismos autores muestran que la conducta supera al perfil: el poder predictivo pasa de 0,847 con demografía sola a 0,908 con datos transaccionales.","Conclusión de diseño: la brecha se cierra con lo que el cliente hace, no con lo que el cliente es."])}`},
 {id:"acc-ramos",k:"Contexto",t:"Los cuatro ramos del prototipo",d:"Tres existen y no se ofrecen, uno no existe en versión voluntaria",b:`
  ${TBL(["Ramo","Aliado","Hoy","Lo que falta"],[
   ["SOAT","Seguros Mundial","Disponible, compra activa","Nadie avisa cuándo vence"],
   ["Pago protegido","SBS Seguros","Ligado al crédito","No se ofrece en el desembolso"],
   ["Nómina (desempleo)","Chubb","Disponible, compra activa","No hay un momento ligado al ingreso"],
   ["Vida","AXA Colpatria","Solo grupo deudor","No existe versión voluntaria"]])}
  <p><b>El patrón:</b> en tres de los cuatro ramos el problema es de descubrimiento, no de conversión. Por eso el prototipo trabaja visibilidad y momento, no precio.</p>`},
 {id:"acc-habitos",k:"Contexto",t:"Los hábitos de consumo son la materia prima",d:"Qué señal anticipa cada ramo y qué momento dispara la oferta",b:`
  ${TBL(["Ramo","Hábito que lo anticipa","Momento que dispara"],[
   ["SOAT","Pago del SOAT anterior, peajes, combustible, parqueaderos, impuesto vehicular","30 días antes del vencimiento"],
   ["Pago protegido","Desembolso, uso del cupo, pago recurrente de cuota","Desembolso y primer pago de cuota"],
   ["Nómina","Abonos periódicos del mismo originador, gastos fijos","Tercer abono consecutivo o salto a Lulo Pro"],
   ["Vida","Nómina domiciliada, transferencias fijas a un tercero, cajita de largo plazo","Consolidación de la nómina en Lulo"]])}
  <p>Es la única ventaja en la que Lulo no arranca en desventaja frente a un banco con veinte años de relación: por ser 100% digital, todo queda registrado punta a punta.</p>
  ${G("movs","Ver movimientos")}`},

 {g:"Las tres ideas en el prototipo"},
 {id:"acc-idea1",k:"Pasado",t:"Tu año en Lulo",d:"Lo que el cliente ya vivió, contado con un año de movimientos",b:`
  ${SUB("Qué hace",UL(["Convierte 12 meses de movimientos en un resumen tipo historia, con un capítulo por cada momento de la vida del cliente.","Algunos capítulos traen un momento de protección: el seguro que corresponde a lo que el cliente ya vivió.","Muestra beneficios que el cliente tiene y no percibe, como el pago protegido de su crédito.","Cierra con lo que el cliente tiene cubierto y lo que queda por revisar."]),true)}
  ${SUB("Qué cambia frente a la versión anterior",`<p>La pestaña «Mis seguros» se retira del prototipo. Su lógica de mostrar lo que el cliente tiene queda dentro del cierre de Tu año y del capítulo del crédito. El dato que activa la idea pasa de la tenencia de pólizas a <b>un año de movimientos</b>, y el formato pasa de un listado que el cliente debe visitar a un contenido que quiere abrir.</p>`)}
  ${SUB("Capítulos modelados",TBL(["Capítulo","Dato que lo arma","Momento de protección"],[
   ["Portada","Total de movimientos del periodo","Ninguno"],
   ["Tu dinero","Flujo mensual de la cuenta","Ninguno, construye confianza"],
   ["Tu ingreso","Abonos del mismo originador","Seguro de nómina (Chubb)"],
   ["Tu carro","Peajes, combustible, parqueaderos","Renovar SOAT (recordatorio)"],
   ["Tus viajes","Abonos a la cajita «Viajes»","Seguro de viaje (IGS)"],
   ["Tu gente","Transferencias fijas a un tercero","Vida voluntario (por negociar)"],
   ["Tu crédito","Cuotas de Lulo Crédito","Beneficio no percibido: pago protegido"],
   ["Tu año, protegido","Pólizas activas y aceptadas","Resumen y compartir"]]))}
  ${SUB("Funcionalidades modeladas",UL([
   "<b>Entrada propia:</b> pestaña «Tu año» en la barra inferior y tarjeta en Inicio.",
   "<b>Portada con índice:</b> el cliente puede ver el año completo o saltar a un capítulo.",
   "<b>Historia navegable:</b> barra de progreso, toque a la derecha o izquierda, flechas del teclado y botón de cerrar.",
   "<b>Momento de protección</b> dentro del capítulo, con «Activar» y «Ahora no».",
   "<b>Elegibilidad:</b> si ya lo tiene, el capítulo dice «Ya lo tienes activo» en vez de ofrecer.",
   "<b>Conexión con el recordatorio:</b> el capítulo del carro lleva a renovar el SOAT y se actualiza al pagar.",
   "<b>Validación integrada:</b> «¿Sabías que tenías esta protección?» en el capítulo del crédito.",
   "<b>Cierre dinámico:</b> cuenta las protecciones activas, incluidas las aceptadas en el motor.",
   "<b>Respeto a preferencias:</b> con sugerencias apagadas o en grupo de control, el resumen se ve sin ofertas."]))}
  ${SUB("Qué hay que validar",UL(["Si los clientes abren el resumen y lo terminan.","Qué capítulos se sienten útiles y cuáles invasivos.","Si una oferta dentro de un contenido personal se recibe mejor que una notificación.","Qué cifras se pueden calcular con los datos reales de cada cliente."]))}
  ${SUB("Cómo se mide",UL(["Apertura y finalización del resumen.","Aceptación por capítulo frente al grupo de control, que ve el resumen sin ofertas.","Respuestas a «¿Sabías que tenías esta protección?».","Veces que el cliente comparte su año."]))}
  ${SUB("Cómo se generaliza",`<p>No es un resumen de seguros: es una forma de devolverle al cliente lo que sus datos dicen de él, con un momento de acción en cada capítulo. Sirve para CDT, Lulo Pro, cashback o crédito, y se puede repetir por semestre o en fechas propias del cliente, como el aniversario con Lulo.</p>`)}
  ${G("anio","Ver Tu año")}${G("story:0","Abrir la historia")}`},
 {id:"acc-idea2",k:"Presente",t:"Motor de disparadores preventa",d:"Ofrecer el seguro correcto cuando el cliente lo necesita",b:`
  ${SUB("Cómo funciona",`<p>Cada acción relevante en la app se convierte en un evento. El evento pasa por reglas de elegibilidad y prioridad y, si gana, se convierte en una notificación y una oferta en la app.</p><div class="flow"><span>Evento</span><i>→</i><span>Elegibilidad</span><i>→</i><span>Prioridad</span><i>→</i><span>Notificación</span><i>→</i><span>Oferta</span><i>→</i><span>Respuesta registrada</span></div>`,true)}
  ${SUB("Catálogo de eventos",TBL(["Evento","Qué revela","Oferta","Prioridad"],Object.values(EVENTS).map(e=>[e.label,e.habit,e.offer,e.prio])))}
  ${SUB("Reglas de decisión",UL([
   "<b>Elegibilidad:</b> si el cliente ya tiene la cobertura, no se le vende otra. Un nuevo desembolso con pago protegido vigente no dispara oferta: ese beneficio se cuenta en Tu año.",
   "<b>Una ventana, un contacto:</b> si hay una oferta abierta, las demás esperan en cola ordenadas por prioridad (1 = mayor).",
   "<b>Grupo de control:</b> clientes que generan el evento pero no reciben la oferta, para medir el efecto real.",
   "<b>Respeto a preferencias:</b> si el cliente apagó las sugerencias, el motor no muestra nada.",
   "<b>SOAT al día:</b> los eventos de vehículo con SOAT vigente no disparan nada en esta fase. Todo riesgo queda para la fase 2.",
   "<b>Procesamiento asíncrono:</b> el motor debe soportar eventos masivos sin frenar la app (supuesto técnico)."]))}
  ${SUB("La oferta en pantalla",UL(["<b>«Por qué lo ves»:</b> transparencia sobre el hábito que la disparó.","Una cifra clave, lo que cubre, el precio y la cuenta de pago.","Tres respuestas: aceptar, «Ahora no» y no volver a ver ese tipo de sugerencia.","Vida voluntario se marca como producto por negociar con la aseguradora."]))}
  ${SUB("Cómo se mide",`<p><b>Aceptación incremental por evento</b>, no la tasa bruta: aceptación del grupo tratado menos la del grupo de control, evento por evento.</p>`)}
  ${SUB("Cómo se generaliza",`<p>Es una capa que decide la próxima mejor acción para cualquier producto: crédito, CDT, Lulo X o Lulo Pro. En otros sectores es el mismo mecanismo: un evento observable, una regla de elegibilidad y una oferta pertinente.</p>`)}
  ${G("motor","Abrir el motor en vivo")}${G("offer:nomina","Ver una oferta")}`},
 {id:"acc-idea3",k:"Futuro",t:"Recordatorio de vencimiento del SOAT",d:"Usar un seguro obligatorio para abrir la conversación",b:`
  ${SUB("Por qué este ramo primero",UL(["La decisión de compra ya está tomada: solo se disputa el canal.","El momento es una fecha, no una conducta: es el más barato de predecir.","Tiene el menor riesgo de fricción: nadie se molesta porque le recuerden una obligación legal."]),true)}
  ${SUB("Flujo modelado",`<div class="flow"><span>Aviso lima en Inicio</span><i>→</i><span>Renovación</span><i>→</i><span>Descuento</span><i>→</i><span>Pago desde Lulo</span><i>→</i><span>Confirmación</span><i>→</i><span>Calendario 2027</span></div>${UL(["También se entra desde el capítulo «Tu carro» de Tu año o desde una notificación del motor por peajes y combustible.","Al pagar se descuenta el saldo, aparece el movimiento y la póliza pasa a vigente.","«Recuérdamelo después» queda registrado como pospuesto."])}`)}
  ${SUB("Configuración del aviso",`<p>En Perfil el cliente elige 30, 15 o 7 días de anticipación. En el prototipo el descuento se escala con la anticipación para poder conversar la hipótesis con usuarios.</p>`)}
  ${SUB("Cómo crece",UL(["Abre la puerta a los demás seguros del vehículo.","El mismo mecanismo sirve para la revisión tecnomecánica y el impuesto vehicular.","Y para la renovación de cualquier otra póliza del cliente."]))}
  ${SUB("Qué hay que validar",UL(["Si los clientes esperan comprar el SOAT en una app bancaria.","Con cuánta anticipación quieren el aviso.","Cuántos clientes de Lulo tienen vehículo y son detectables por su gasto."]))}
  ${SUB("Cómo se mide",`<p><b>Captura de canal:</b> cuántos renuevan en Lulo y no por fuera. Se reporta separado de los otros tres ramos: como la compra iba a ocurrir de todos modos, mezclarlo en un solo indicador de conversión escondería el resultado.</p>`)}
  ${G("home","Ver el aviso en Inicio")}${G("renew","Ir a renovar")}`},

 {g:"Cómo se sostiene"},
 {id:"acc-nucleo",k:"Mecanismo",t:"El núcleo común: cuatro pasos",d:"Una sola capa sirve para las tres ideas",b:`
  <div class="flow"><span>1. Detectar la señal</span><i>→</i><span>2. Decidir qué y a quién</span><i>→</i><span>3. Mostrarlo en la app</span><i>→</i><span>4. Registrar la respuesta</span></div>
  <p>El cuarto paso no existe hoy en Lulo Bank. Es el que convierte cualquiera de las tres ideas en un activo que la competencia no puede copiar: con el tiempo, Lulo sabe qué momento funciona para qué cliente.</p>
  <p>En el panel «Motor en vivo» los cuatro pasos se encienden uno a uno con cada evento.</p>${G("motor","Verlo en vivo")}`},
 {id:"acc-arquitectura",k:"Tecnología",t:"Cómo está construida esta app",d:"El motor corre en Python y la app se publica en Vercel",b:`
  <p>El teléfono y el panel son la interfaz. <b>Las decisiones las toma un servicio en Python</b> (FastAPI), igual que lo haría el motor real dentro de Lulo Bank.</p>
  ${TBL(["Pieza","Qué hace","Dónde está"],[
   ["Catálogo","Eventos, ofertas, pólizas y movimientos del cliente de ejemplo","<code>lulo_app/catalog.py</code>"],
   ["Motor de disparadores","Paso 2: grupo de control, preferencias, elegibilidad y cola por prioridad","<code>lulo_app/engine.py</code> · <code>POST /api/engine/event</code>"],
   ["Cotización del SOAT","Descuento según la anticipación del aviso (30, 15 o 7 días)","<code>GET /api/soat/quote</code>"],
   ["Medición","Métricas por oferta y exportación del registro a CSV","<code>lulo_app/report.py</code> · <code>POST /api/report/csv</code>"]])}
  <h5>Por qué el motor es «sin estado»</h5>
  <p>Cada evento viaja con su contexto (coberturas, ventana de contacto y cola) y el motor responde con la decisión. Así escala en funciones serverless y se puede probar con pruebas automáticas, sin base de datos.</p>
  <h5>Para pasar a datos reales</h5>${UL(["Reemplazar el catálogo por los eventos instrumentados en la app.","Guardar el registro de respuestas en una base de datos para medir contra el grupo de control.","La documentación interactiva del API está en <code>/docs</code>."])}`},
 {id:"acc-medicion",k:"Medición",t:"Qué se mide y cómo se evita el daño",d:"Métricas por idea, indicadores de no daño y grupo de control",b:`
  ${TBL(["Idea","Métrica principal"],[["Tu año en Lulo","Finalización del resumen y aceptación por capítulo frente a control"],["Motor","Aceptación incremental por evento"],["Recordatorio","Captura de canal: renuevan en Lulo y no por fuera"]])}
  <h5>Indicadores de no daño (transversales)</h5>
  ${UL(["Desactivación de notificaciones: en el prototipo, apagar sugerencias o avisos en Perfil.","Rechazo explícito: «No quiero sugerencias de este tipo».","Caída de transacciones después del contacto.","Quejas y desinstalaciones."])}
  <h5>En el prototipo</h5>${UL(["Cada respuesta queda en el registro con hora, evento, oferta y resultado.","El botón «Exportar CSV» descarga el registro para analizarlo en Excel.","El grupo de control se activa con un botón y deja trazado que el evento ocurrió pero no se mostró."])}`},
 {id:"acc-pantallas",k:"Prototipo",t:"Mapa de pantallas",d:"Salta a cualquier pantalla",b:`
  ${TBL(["Pantalla","Idea","Ir"],[
 ["Inicio","Futuro",G("home","Abrir")],["Movimientos","Materia prima",G("movs","Abrir")],["Tu año: portada","Pasado",G("anio","Abrir")],
   ["Tu año: Tu ingreso","Pasado",G("story:2","Abrir")],["Tu año: Tu carro","Pasado y futuro",G("story:3","Abrir")],["Tu año: Tu crédito","Pasado",G("story:6","Abrir")],["Tu año: cierre","Pasado",G("story:7","Abrir")],
   ["Renovación del SOAT (P3)","Futuro",G("renew","Abrir")],["Oferta: nómina","Presente",G("offer:nomina","Abrir")],["Oferta: viaje","Presente",G("offer:viaje","Abrir")],
   ["Oferta: vida voluntario","Presente",G("offer:vida","Abrir")],["Perfil y preferencias","No daño",G("perfil","Abrir")]])}`},
 {id:"acc-plan",k:"Plan",t:"Pasos a seguir",d:"Validar, prototipar y medir hasta La Muestra",b:`
  ${TBL(["Idea","Validar (hasta 23 sep)","Prototipar (7–31 oct)","Medir (4–28 nov)"],[
   ["Tu año en Lulo","Con los datos reales: qué capítulos se pueden calcular por cliente","Historia navegable con 8 capítulos y sus momentos de protección","Finalización y aceptación por capítulo frente a control"],
   ["Motor","Con Analítica: qué eventos están instrumentados y con qué latencia","Reglas evento a oferta para dos eventos y su prioridad","Aceptación incremental por evento"],
   ["Recordatorio","Con Alex: cuántos clientes tienen SOAT y cuándo vence","Flujo de aviso y renovación en la app","Captura de canal"]])}
  <h5>Qué necesitamos de la organización</h5>
  <ol><li>Los datos ya solicitados: ventas mensuales por ramo, comisión, ticket y requisitos de elegibilidad.</li><li>Una sesión con Analítica y UX sobre eventos instrumentados y espacio en la interfaz.</li><li>La postura de Jurídico sobre si una recomendación in-app cuenta como contacto bajo la Ley 2300.</li></ol>
  <p style="margin-top:8px">IDEAR hasta el 23 de septiembre, prototipo en octubre, La Muestra el 18 de noviembre.</p>`},
 {id:"acc-supuestos",k:"Supuestos",kp:true,t:"Supuestos, límites y fase 2",d:"Lo que es ilustrativo y lo que queda por fuera",b:`
  <h5>Datos ilustrativos</h5>${UL(["Nombres, placa, vehículo, saldos, precios, porcentajes de descuento y las cifras de Tu año son de ejemplo.","Las prioridades del motor son una propuesta del equipo para discutir."])}
  <h5>Supuestos por confirmar</h5>${UL(["Las señales de hábito son hipótesis: hay que confirmar cuáles están instrumentadas.","Vida voluntario no existe hoy: requiere negociar producto con AXA Colpatria.","La tarifa del SOAT es regulada: el descuento tendría que venir como beneficio de Lulo y debe revisarlo Jurídico.","Si una notificación in-app cuenta como contacto comercial bajo la Ley 2300.","Mostrar cifras personales en Tu año exige revisar la autorización de tratamiento de datos (Ley 1581 de 2012)."])}
  <h5>Fase 2 (fuera de este prototipo)</h5>${UL(["Seguros premium, mascotas y alianza con aerolíneas: exigen negociar producto nuevo.","Seguro todo riesgo del vehículo.","Modelo predictivo sobre datos transaccionales en lugar de reglas fijas."])}`}
];
function renderAccs(){
  $("#accs").innerHTML = ACCS.map(a=>a.g?`<div class="grp-t">${a.g}</div>`:
    `<details class="acc" id="${a.id}"${a.open?" open":""}><summary><span class="s-k${a.kp?" pk":""}">${a.k}</span><span class="s-t">${a.t}</span><span class="s-d">${a.d}</span></summary><div class="acc-b">${a.b}</div></details>`).join("");
}

/* pestañas del panel */
function setTab(t){
  document.querySelectorAll(".ptabs button").forEach(b=>b.setAttribute("aria-selected",b.dataset.tab===t));
  document.querySelectorAll(".pview").forEach(v=>v.hidden = v.id!=="view-"+t);
}
document.querySelector(".ptabs").addEventListener("click",e=>{const b=e.target.closest("[data-tab]"); if(b) setTab(b.dataset.tab);});
$("#openAll").addEventListener("click",()=>document.querySelectorAll("#accs details").forEach(d=>d.open=true));
$("#closeAll").addEventListener("click",()=>document.querySelectorAll("#accs details").forEach(d=>d.open=false));

/* saltos al prototipo */
function flashPhone(){ const p=document.querySelector(".phone"); p.classList.remove("flashbox"); void p.offsetWidth; p.classList.add("flashbox"); if(window.innerWidth<980) p.scrollIntoView({behavior:"smooth",block:"center"}); }
function abandonOpen(){ if(S.shown && (S.screen==="offer"||S.screen==="renew"||S.shown.ev==="Tu año en Lulo · Tu carro")){ addLog(S.shown.ev,S.shown.offerName,"Cerró sin decidir","no"); closeWindow(); } }
function gotoTarget(t){
  if(t==="motor"){ setTab("motor"); return; }
  abandonOpen();
  const [scr,arg]=t.split(":");
  if(scr==="story"){ S.stack=[]; S.screen="anio"; openStory(+arg||0); flashPhone(); return; }
  else if(scr==="offer"){ S.stack=["home"]; S.offer=arg; S.screen="offer"; }
  else if(scr==="renew"){ if(S.soatRenewed){ S.stack=[]; S.screen="home"; toast("El SOAT ya está renovado. Reinicia la demo para verlo otra vez"); } else { S.stack=["home"]; S.screen="renew"; } }
  else { S.stack=[]; S.screen=scr; }
  render(); $("#scroll").scrollTop=0; flashPhone();
}
document.addEventListener("click",e=>{
  const b=e.target.closest("[data-goto]"); if(!b) return;
  gotoTarget(b.dataset.goto);
  if(b.dataset.acc){ setTab("func"); const d=document.getElementById(b.dataset.acc); if(d){ d.open=true; d.scrollIntoView({behavior:"smooth",block:"start"}); } }
});

/* exportar registro */
$("#csvBtn").addEventListener("click",async()=>{
  if(!S.log.length){ toast("El registro está vacío"); return; }
  try{
    const blob = await (await api("/api/report/csv", S.log.slice().reverse())).blob();
    const a=document.createElement("a"); a.href=URL.createObjectURL(blob);
    a.download="registro-respuestas-lulo-grupo14.csv"; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(()=>URL.revokeObjectURL(a.href),1000);
  }catch(e){ toast("No se pudo generar el CSV"); }
});

/* demo guiada */
const wait = ms => new Promise(r=>setTimeout(r,ms));
const DEMO = [
 {k:"Contexto",t:"Arranca en Inicio",d:"El cliente ve su saldo, el aviso del SOAT y la tarjeta de Tu año en Lulo.",run:async()=>gotoTarget("home")},
 {k:"Futuro",t:"Abre el aviso del SOAT",d:"Llega a la renovación con vigencia, descuento y pago desde Lulo.",run:async()=>gotoTarget("renew")},
 {k:"Futuro",t:"Paga la renovación",d:"Se mide como captura de canal: la compra iba a pasar igual.",run:async()=>{ if(S.soatRenewed){toast("El SOAT ya estaba renovado");return;} if(S.screen!=="renew") gotoTarget("renew"); await wait(500); pay(); await wait(1500); }},
 {k:"Pasado",t:"Abre Tu año en Lulo",d:"El motor lee 12 meses de movimientos y arma la historia.",run:async()=>gotoTarget("story:0")},
 {k:"Pasado",t:"Activa el seguro de nómina",d:"En el capítulo «Tu ingreso» la protección nace de lo que el cliente ya vivió.",run:async()=>{ gotoTarget("story:2"); await wait(700); if(!hasPolicy("nomina")){ activate("nomina","Tu año en Lulo · Tu ingreso"); render(); toast("Activado"); } }},
 {k:"Pasado",t:"Responde la validación del crédito",d:"«No sabía que tenía pago protegido» queda en el registro.",run:async()=>{ gotoTarget("story:6"); await wait(700); if(!S.known.pago) setKnown("pago","No"); }},
 {k:"Pasado",t:"Llega al cierre y comparte",d:"El cierre cuenta las protecciones activas, incluida la nueva.",run:async()=>{ gotoTarget("story:7"); await wait(700); addLog("Tu año en Lulo","Resumen anual","Compartió su año","info"); toast("Imagen lista para compartir"); }},
 {k:"Prioridad",t:"Dispara dos eventos seguidos",d:"Viaje y vida llegan juntos: gana el de mayor prioridad y el otro espera en cola.",run:async()=>{ gotoTarget("home"); await wait(200); await fire("viaje"); await fire("vida"); }},
 {k:"Presente",t:"Abre la notificación y activa",d:"La oferta explica por qué aparece. Al activar, se suma al cierre de Tu año.",run:async()=>{ if(!S.shown||S.shown.kind!=="offer"){ await fire(hasPolicy("viaje")?"vida":"viaje");} if(S.shown&&S.shown.kind==="offer"){ $("#notif").click(); await wait(1200); acceptOffer(); } }},
 {k:"Elegibilidad",t:"Dispara el abono de nómina",d:"No se muestra nada: el cliente ya lo activó en Tu año. Las tres soluciones comparten la misma regla.",run:async()=>{ await fire("nomina"); }},
 {k:"Control",t:"Activa el grupo de control",d:"El evento ocurre, pero la oferta no se muestra: así se mide el efecto real.",run:async()=>{ if(!S.control){ S.control=true; renderPanel(); } await wait(300); await fire("vida"); await wait(600); S.control=false; renderPanel(); }},
 {k:"No daño",t:"Apaga las sugerencias en Perfil",d:"Queda como señal de daño. Tu año se sigue viendo, pero sin ofertas.",run:async()=>{ gotoTarget("perfil"); await wait(500); if(S.sugg) toggleSugg(); }}
];
const demoDone=new Set();
function renderDemo(){
  $("#demo").innerHTML=DEMO.map((s,i)=>`<li class="${demoDone.has(i)?"done":""}"><div><div class="dk">${s.k}</div><div class="dt">${s.t}</div><div class="dd">${s.d}</div></div><button data-demo="${i}">${demoDone.has(i)?"Repetir":"Ejecutar"}</button></li>`).join("");
}
$("#demo").addEventListener("click",async e=>{ const b=e.target.closest("[data-demo]"); if(!b) return; const i=+b.dataset.demo; b.disabled=true; try{ await DEMO[i].run(); demoDone.add(i); } finally { renderDemo(); } });

/* ---------- inicio ---------- */
initState(); renderEvents(); renderAccs(); renderDemo(); render(); renderPanel(); checkApi();
setTimeout(()=>$("#splash").classList.add("hide"),1300);
})();
