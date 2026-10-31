/* Conexión con el servidor, chat, acciones, voz y escena 3D. El navegador guarda
 * el id de su criatura para retomarla al volver. */
import { Criatura } from "./creature.js";
import { Habitacion } from "./room.js";
import { Escucha } from "./mic.js";

const $ = (selector) => document.querySelector(selector);
const icono = window.icono;
const CLAVE_ID = "muyu.id";
const ICONO_ACTIVIDAD = {
  quieta: "sprout", explorar: "search", jugar: "volleyball", mirar_ventana: "eye", descansar: "sofa",
  pedir_comida: "utensils", buscarte: "users", esconderse: "box", aburrirse: "hourglass", ir_a_dormir: "bed",
  atenderte: "message-square-text", acercarse: "hand-heart", comer: "apple", dormir: "moon",
};

// Iconos declarados en el HTML con data-icono.
document.querySelectorAll("[data-icono]").forEach((elemento) => {
  elemento.insertAdjacentHTML("afterbegin", icono(elemento.dataset.icono));
});

const criatura = new Criatura();
const habitacion = new Habitacion($("#escena"), criatura, { onTocar: tocar });
const voz = new window.Voz();
const panel = new window.PanelCerebro({
  onAdelantar: (horas) => enviar({ tipo: "adelantar", horas }),
  onNuevaCriatura: () => {
    localStorage.removeItem(CLAVE_ID);
    $("#chat").innerHTML = "";
    criatura.ubicada = false;
    if (ws) ws.close();
  },
});

let ws = null;
let reintentos = 0;
let nombre = "Muyu";
let despierta = true;
let temporizadorBurbuja = null;
let hablando = 0;                 // cuántas frases suyas están sonando
let esperandoRespuesta = false;   // le hablaste y todavía no contesta

// ── Conexión ────────────────────────────────────────────────────────
function conectar() {
  const protocolo = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${protocolo}://${location.host}/ws`);
  ws.addEventListener("open", () => {
    reintentos = 0;
    marcarConexion(true);
    ws.send(JSON.stringify({ tipo: "conectar", id: localStorage.getItem(CLAVE_ID) }));
  });
  ws.addEventListener("message", (evento) => recibir(JSON.parse(evento.data)));
  ws.addEventListener("close", () => {
    marcarConexion(false);
    setTimeout(conectar, Math.min(8000, 500 * 2 ** reintentos++));
  });
}

function enviar(mensaje) {
  if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(mensaje));
}

function marcarConexion(conectada) {
  const elemento = $("#conexion");
  elemento.className = `conexion ${conectada ? "conectada" : "desconectada"}`;
  elemento.innerHTML = `${icono(conectada ? "wifi" : "wifi-off")}<span>${conectada ? "Conectada" : "Reconectando…"}</span>`;
}

function recibir(mensaje) {
  switch (mensaje.tipo) {
    case "criatura":
      localStorage.setItem(CLAVE_ID, mensaje.datos.id);
      nombre = mensaje.datos.nombre;
      criatura.tono = mensaje.datos.tono;
      voz.configurar(mensaje.datos.voz);
      $("#nombre").textContent = nombre;
      panel.identidad(mensaje.datos);
      break;
    case "habla": hablar(mensaje); break;
    case "oido": mostrarLoOido(mensaje.datos); break;
    case "actividad": mostrarActividad(mensaje.datos); break;
    case "pensamiento": panel.pensamiento(mensaje.datos); break;
    case "aviso": agregarAlChat("aviso", mensaje.texto); break;
    case "estado": actualizarEstado(mensaje.datos); break;
    case "cerebro": panel.cerebro(mensaje.datos); break;
    default: break;
  }
}

// ── Lo que dice ─────────────────────────────────────────────────────
function hablar(mensaje) {
  const ahora = performance.now();
  const pensando = mensaje.origen === "pensamiento" || mensaje.origen === "actividad";
  if (mensaje.emocion) criatura.estado({ emocion: mensaje.emocion });
  criatura.gesto(mensaje.gesto, ahora);
  if (mensaje.gesto === "carino") voz.sonido("risa");
  if (mensaje.intencion !== "dormida") {
    // Mientras habla no escucha: así no se oye a sí misma.
    const conPalabras = (mensaje.palabras || []).length > 0;
    hablando += 1;
    escucha.pausar();
    criatura.hablar(500 + mensaje.texto.length * 75, ahora);
    voz.hablar(mensaje.texto, mensaje.emocion, mensaje.pregunta, conPalabras).then(() => {
      hablando -= 1;
      if (["respuesta", "reaccion", "saludo"].includes(mensaje.origen)) esperandoRespuesta = false;
      reanudarEscucha();
    });
  } else if (["respuesta", "reaccion"].includes(mensaje.origen)) {
    esperandoRespuesta = false;
    reanudarEscucha();
  }
  const burbuja = $("#burbuja");
  burbuja.textContent = mensaje.texto;
  burbuja.className = `burbuja${pensando ? " pensando" : ""}`;
  clearTimeout(temporizadorBurbuja);
  temporizadorBurbuja = setTimeout(() => burbuja.classList.add("oculta"), 2500 + mensaje.texto.length * 80);
  agregarAlChat(pensando ? "pensando" : "muyu", mensaje.texto, mensaje);
}

// La burbuja sigue la cabeza de Muyu en la escena.
habitacion.alDibujar = ({ x, y, visible }) => {
  const burbuja = $("#burbuja");
  if (burbuja.classList.contains("oculta") || !visible) return;
  const ancho = $("#escena").clientWidth;
  const mitad = burbuja.offsetWidth / 2 + 8;
  burbuja.style.left = `${Math.max(mitad, Math.min(ancho - mitad, x))}px`;
  burbuja.style.top = `${Math.max(burbuja.offsetHeight + 60, y)}px`;
};

function agregarAlChat(clase, texto, mensaje = null) {
  const chat = $("#chat");
  const elemento = document.createElement("div");
  elemento.className = `mensaje ${clase}`;
  if (clase === "aviso") {
    elemento.innerHTML = icono("info");
    elemento.append(document.createTextNode(texto));
  } else {
    if (mensaje) {
      const quien = document.createElement("span");
      quien.className = "quien";
      const sentir = mensaje.emocion ? ` · siente ${mensaje.emocion.etiqueta}` : "";
      const origen = { pensamiento: " piensa en voz alta", actividad: ", por su cuenta" }[mensaje.origen] || "";
      quien.textContent = `${nombre}${origen}${sentir}`;
      elemento.append(quien);
    }
    elemento.append(document.createTextNode(texto));
    if (mensaje && mensaje.detalle) {
      const porQue = document.createElement("span");
      porQue.className = "por-que";
      porQue.innerHTML = icono("lightbulb");
      porQue.append(document.createTextNode(mensaje.detalle));
      elemento.append(porQue);
    }
  }
  chat.append(elemento);
  while (chat.children.length > 200) chat.firstChild.remove();
  chat.scrollTop = chat.scrollHeight;
}

// ── Lo que hace su cuerpo ───────────────────────────────────────────
function mostrarActividad(actividad) {
  const anterior = criatura.actividad;
  criatura.hacer(actividad, performance.now());
  if (actividad.nombre === "comer" && anterior.nombre !== "comer") {
    habitacion.servirComida();
    setTimeout(() => voz.sonido("nam"), 1200);
  }
  if (actividad.nombre === "jugar" && actividad.iniciativa === "dueño" && anterior.nombre !== "jugar") {
    habitacion.lanzarPelota();
  }
  const contenedor = $("#actividad");
  contenedor.innerHTML = icono(ICONO_ACTIVIDAD[actividad.nombre] || "sprout");
  const descripcion = document.createElement("b");
  descripcion.textContent = actividad.descripcion;
  const motivo = document.createElement("span");
  motivo.className = "motivo";
  motivo.textContent = actividad.motivo;
  contenedor.append(descripcion, motivo);
  panel.actividad(actividad);
}

function actualizarEstado(estado) {
  despierta = estado.despierta;
  criatura.estado({ emocion: estado.emocion, despierta: estado.despierta, etapa: estado.etapa.numero });
  const actual = estado.comportamiento && estado.comportamiento.actual;
  if (actual && actual.inicio !== criatura.actividad.inicio) mostrarActividad(actual);
  habitacion.hora = estado.hora;
  panel.estado(estado);
  $("#edad").textContent = `${estado.edad_texto} de vida`;
  $("#etapa").textContent = `Etapa ${estado.etapa.numero} · ${estado.etapa.nombre}`;
  $("#emocion-actual").textContent = estado.despierta ? estado.emocion.etiqueta : "dormida";
  for (const necesidad of ["energia", "saciedad", "compania", "seguridad"]) {
    $(`#mini-${necesidad}`).style.width = `${Math.round(estado.necesidades[necesidad] * 100)}%`;
  }
  $("#esperando").classList.toggle("oculta", !estado.esperando_respuesta);
  const botonDormir = $("#boton-dormir");
  botonDormir.dataset.accion = despierta ? "dormir" : "despertar";
  botonDormir.innerHTML = `${icono(despierta ? "moon" : "sun")}<span>${despierta ? "Dormir" : "Despertar"}</span>`;
}

// ── Acciones ────────────────────────────────────────────────────────
const NOMBRES_ACCION = {
  acariciar: "la acaricias", alimentar: "le das de comer", jugar: "le lanzas la pelota", dormir: "la acuestas",
  despertar: "la despiertas", asentir: "asientes", negar: "niegas", "regañar": "la regañas",
};

function accionar(accion) {
  voz.desbloquear();
  enviar({ tipo: "accion", accion });
  agregarAlChat("aviso", `Tú ${NOMBRES_ACCION[accion] || accion}`);
}

function tocar(objeto) {
  const ahora = performance.now();
  if (objeto === "criatura") {
    criatura.gesto("carino", ahora);
    accionar("acariciar");
  } else if (objeto === "pelota") {
    habitacion.lanzarPelota();
    accionar("jugar");
  } else if (objeto === "plato") {
    accionar("alimentar");
  } else if (objeto === "cama") {
    accionar(despierta ? "dormir" : "despertar");
  }
}

document.querySelectorAll(".menu-acciones button").forEach((boton) =>
  boton.addEventListener("click", () => {
    if (boton.dataset.accion === "jugar") habitacion.lanzarPelota();
    accionar(boton.dataset.accion);
  }));

$("#formulario").addEventListener("submit", (evento) => {
  evento.preventDefault();
  voz.desbloquear();
  const entrada = $("#entrada");
  const texto = entrada.value.trim();
  if (!texto) return;
  agregarAlChat("tu", texto);
  enviar({ tipo: "mensaje", texto });
  entrada.value = "";
});

// ── Micrófono siempre atento: detecta solo cuándo le hablas ─────────
const ETIQUETAS_ESCUCHA = {
  escuchando: "Te escucha", oyendo: "Te está oyendo…", enviando: "Pensando lo que oyó…",
  pausada: "No escucha mientras habla", apagada: "Micrófono apagado",
};
const botonMic = $("#boton-mic");
const escucha = new Escucha({
  alFrase: (audio) => {
    esperandoRespuesta = true;
    escucha.pausar(15);                           // hasta que conteste (o 15 s como máximo)
    enviar({ tipo: "voz", audio });
  },
  alEstado: (estado) => pintarEscucha(estado),
  alNivel: (nivel) => { $("#nivel-mic").style.width = `${Math.round(nivel * 100)}%`; },
});

function reanudarEscucha() {
  if (hablando <= 0 && !esperandoRespuesta) escucha.reanudar();
}

function pintarEscucha(estado = escucha.activa ? "escuchando" : "apagada") {
  const encendida = escucha.activa;
  botonMic.classList.toggle("escuchando", encendida && estado === "escuchando");
  botonMic.classList.toggle("grabando", encendida && estado === "oyendo");
  botonMic.classList.toggle("procesando", encendida && (estado === "enviando" || estado === "pausada"));
  botonMic.innerHTML = icono(encendida ? "mic" : "mic-off");
  botonMic.title = encendida ? `${ETIQUETAS_ESCUCHA[estado] || "Te escucha"} · toca para apagar el micrófono`
    : "Micrófono apagado · toca para que te escuche siempre";
  const indicador = $("#grabacion");
  indicador.classList.toggle("oculta", !encendida || !["oyendo", "enviando"].includes(estado));
  $("#estado-mic").textContent = ETIQUETAS_ESCUCHA[estado] || "";
  indicador.dataset.estado = estado;
}

async function encenderEscucha() {
  try {
    voz.desbloquear();
    await escucha.iniciar();
    localStorage.setItem("muyu.escucha", "si");
  } catch (error) {
    agregarAlChat("aviso", `No se pudo usar el micrófono: ${error.message}`);
    localStorage.setItem("muyu.escucha", "no");
  }
  pintarEscucha();
}

if (!escucha.disponible) {
  botonMic.disabled = true;
  botonMic.innerHTML = icono("mic-off");
  botonMic.title = "El micrófono necesita HTTPS (o abrir la página como localhost en esta PC). Ver README, sección 8.4.";
} else {
  botonMic.addEventListener("click", async () => {
    if (escucha.activa) {
      await escucha.detener();
      localStorage.setItem("muyu.escucha", "no");
      pintarEscucha();
    } else {
      encenderEscucha();
    }
  });
  // Siempre atento: se enciende con tu primer toque en la página (el navegador lo exige).
  if (localStorage.getItem("muyu.escucha") !== "no") {
    const alPrimerToque = () => {
      document.removeEventListener("pointerdown", alPrimerToque);
      document.removeEventListener("keydown", alPrimerToque);
      if (!escucha.activa) encenderEscucha();
    };
    document.addEventListener("pointerdown", alPrimerToque);
    document.addEventListener("keydown", alPrimerToque);
  }
  pintarEscucha();
}

function mostrarLoOido(datos) {
  if (!datos.prosodia || !datos.prosodia.con_voz) {
    // Era ruido, no una voz: no contesta, así que vuelve a escuchar enseguida.
    esperandoRespuesta = false;
    reanudarEscucha();
    return;
  }
  const elemento = document.createElement("div");
  elemento.className = "mensaje tu";
  elemento.append(document.createTextNode(datos.texto || "(no entendió palabras)"));
  const detalle = document.createElement("span");
  detalle.className = "voz";
  const prosodia = datos.prosodia || {};
  const partes = [...(datos.percepcion || [])];
  if (prosodia.con_voz) {
    partes.push(`${Math.round(prosodia.volumen_db)} dB`);
    if (prosodia.tono_hz) partes.push(`${Math.round(prosodia.tono_hz)} Hz`);
  } else {
    partes.push("no oyó ninguna voz");
  }
  detalle.innerHTML = icono("mic");
  detalle.append(document.createTextNode(partes.join(" · ")));
  elemento.append(detalle);
  $("#chat").append(elemento);
  $("#chat").scrollTop = $("#chat").scrollHeight;
}

// ── Voz: los navegadores solo dejan sonar después de un toque ───────
const botonVoz = $("#boton-voz");
const pintarVoz = () => {
  botonVoz.innerHTML = icono(voz.activa ? "volume-2" : "volume-x");
  botonVoz.classList.toggle("apagada", !voz.activa);
  botonVoz.title = voz.activa ? "Silenciar su voz" : "Activar su voz";
};
botonVoz.addEventListener("click", () => { voz.alternar(); pintarVoz(); });
["pointerdown", "keydown"].forEach((evento) => document.addEventListener(evento, () => voz.desbloquear(), { passive: true }));
pintarVoz();

// ── Barra lateral en el celular ─────────────────────────────────────
$("#boton-panel").addEventListener("click", () => $("#panel").classList.add("abierto"));
$("#boton-cerrar-panel").addEventListener("click", () => $("#panel").classList.remove("abierto"));

conectar();
