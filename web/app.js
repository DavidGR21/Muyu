/* Conexión con el servidor, chat, acciones, voz y habitación. El navegador guarda
 * el id de su criatura para retomarla al volver. */
(function () {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const CLAVE_ID = "muyu.id";
  const EMOJI_GESTO = {
    asentir: "👍", negar: "🙅", duda: "🤔", confusion: "😵‍💫", reconocer: "🧐", alegria: "😄", carino: "🥰",
    miedo: "😨", tristeza: "😢", curiosidad: "👀", sonar: "💭", saludo: "👋", dormir: "😴", sobresalto: "😲",
    enojo: "😠", pedir: "🍽️",
  };
  const EMOJI_ACTIVIDAD = {
    quieta: "🌱", explorar: "🔍", jugar: "⚽", mirar_ventana: "🪟", descansar: "🛋️", pedir_comida: "🍽️",
    buscarte: "👀", esconderse: "📦", aburrirse: "😑", ir_a_dormir: "🥱", atenderte: "💬", comer: "🍎", dormir: "😴",
  };

  const criatura = new window.Criatura();
  const habitacion = new window.Habitacion($("#lienzo"), criatura, { onTocar: tocar });
  const voz = new window.Voz();
  const panel = new window.PanelCerebro({
    onAdelantar: (horas) => enviar({ tipo: "adelantar", horas }),
    onNuevaCriatura: () => {
      localStorage.removeItem(CLAVE_ID);
      $("#chat").innerHTML = "";
      if (ws) ws.close();
    },
  });

  let ws = null;
  let reintentos = 0;
  let nombre = "Muyu";
  let despierta = true;
  let temporizadorBurbuja = null;

  // ── Conexión ────────────────────────────────────────────────────────
  function conectar() {
    const protocolo = location.protocol === "https:" ? "wss" : "ws";
    ws = new WebSocket(`${protocolo}://${location.host}/ws`);
    ws.addEventListener("open", () => {
      reintentos = 0;
      marcarConexion("conectada");
      ws.send(JSON.stringify({ tipo: "conectar", id: localStorage.getItem(CLAVE_ID) }));
    });
    ws.addEventListener("message", (evento) => recibir(JSON.parse(evento.data)));
    ws.addEventListener("close", () => {
      marcarConexion("desconectada");
      setTimeout(conectar, Math.min(8000, 500 * 2 ** reintentos++));
    });
  }

  function enviar(mensaje) {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(mensaje));
  }

  function marcarConexion(estado) {
    const elemento = $("#conexion");
    elemento.className = `conexion ${estado}`;
    elemento.textContent = estado === "conectada" ? "conectada" : "reconectando…";
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
    const pensando = mensaje.origen === "pensamiento";
    if (mensaje.emocion) criatura.estado({ emocion: mensaje.emocion });
    criatura.gesto(mensaje.gesto, ahora);
    if (mensaje.gesto === "carino") voz.sonido("risa");
    const duracionVoz = voz.decir(mensaje.texto, mensaje.emocion, mensaje.pregunta);
    if (mensaje.intencion !== "dormida") {
      criatura.hablar(duracionVoz ? duracionVoz * 1000 : 300 + mensaje.texto.length * 60, ahora);
    }
    const burbuja = $("#burbuja");
    burbuja.textContent = mensaje.texto;
    burbuja.className = `burbuja${pensando ? " pensando" : ""}`;
    clearTimeout(temporizadorBurbuja);
    temporizadorBurbuja = setTimeout(() => burbuja.classList.add("oculta"), 2500 + mensaje.texto.length * 80);
    const clase = pensando ? "pensando" : mensaje.origen === "actividad" ? "sola" : "muyu";
    agregarAlChat(clase, mensaje.texto, mensaje);
  }

  // La burbuja sigue a Muyu por la habitación.
  habitacion.alDibujar = (cabeza) => {
    const burbuja = $("#burbuja");
    if (burbuja.classList.contains("oculta")) return;
    const { x, y } = habitacion.aPantalla(cabeza.x, cabeza.y);
    const ancho = $("#lienzo").clientWidth;
    const mitad = burbuja.offsetWidth / 2 + 6;
    burbuja.style.left = `${Math.max(mitad, Math.min(ancho - mitad, x))}px`;
    burbuja.style.top = `${Math.max(burbuja.offsetHeight + 6, y)}px`;
  };

  function agregarAlChat(clase, texto, mensaje = null) {
    const chat = $("#chat");
    const elemento = document.createElement("div");
    elemento.className = `mensaje ${clase === "sola" ? "pensando" : clase}`;
    if (mensaje) {
      const quien = document.createElement("span");
      quien.className = "quien";
      const emoji = EMOJI_GESTO[mensaje.gesto] ? ` ${EMOJI_GESTO[mensaje.gesto]}` : "";
      const sentir = mensaje.emocion ? ` · siente ${mensaje.emocion.etiqueta}` : "";
      quien.textContent = {
        pensando: `${nombre} piensa en voz alta${emoji}`,
        sola: `${nombre}, por su cuenta${emoji}`,
      }[clase] || `${nombre}${emoji}${sentir}`;
      elemento.append(quien);
    }
    elemento.append(document.createTextNode(texto));
    if (mensaje && mensaje.detalle) {
      const porQue = document.createElement("span");
      porQue.className = "por-que";
      porQue.textContent = `💡 ${mensaje.detalle}`;
      elemento.append(porQue);
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
    const emoji = EMOJI_ACTIVIDAD[actividad.nombre] || "🌱";
    $("#actividad").innerHTML = "";
    const descripcion = document.createElement("b");
    descripcion.textContent = `${emoji} ${actividad.descripcion}`;
    $("#actividad").append(descripcion, document.createTextNode(` · ${actividad.motivo}`));
    panel.actividad(actividad);
  }

  function actualizarEstado(estado) {
    despierta = estado.despierta;
    criatura.estado({ emocion: estado.emocion, despierta: estado.despierta, etapa: estado.etapa.numero });
    const actual = estado.comportamiento && estado.comportamiento.actual;
    if (actual && actual.inicio !== criatura.actividad.inicio) mostrarActividad(actual);
    habitacion.hora = estado.hora;
    panel.estado(estado);
    $("#edad").textContent = `· ${estado.edad_texto} de vida`;
    $("#etapa").textContent = `Etapa ${estado.etapa.numero} · ${estado.etapa.nombre}`;
    $("#emocion-actual").textContent = estado.despierta ? estado.emocion.etiqueta : "dormida";
    for (const necesidad of ["energia", "saciedad", "compania", "seguridad"]) {
      $(`#mini-${necesidad}`).style.width = `${Math.round(estado.necesidades[necesidad] * 100)}%`;
    }
    $("#esperando").classList.toggle("oculta", !estado.esperando_respuesta);
    const botonDormir = $("#boton-dormir");
    botonDormir.dataset.accion = despierta ? "dormir" : "despertar";
    botonDormir.innerHTML = despierta ? "🌙 <span>Dormir</span>" : "☀️ <span>Despertar</span>";
  }

  // ── Acciones ────────────────────────────────────────────────────────
  function accionar(accion, etiqueta) {
    voz.desbloquear();
    enviar({ tipo: "accion", accion });
    agregarAlChat("aviso", `Tú: ${etiqueta}`);
  }

  function tocar(objeto) {
    const ahora = performance.now();
    if (objeto === "criatura") {
      criatura.gesto("carino", ahora);
      accionar("acariciar", "🤲 la acaricias");
    } else if (objeto === "pelota") {
      habitacion.lanzarPelota();
      accionar("jugar", "⚽ le lanzas la pelota");
    } else if (objeto === "plato") {
      accionar("alimentar", "🍎 le sirves comida");
    } else if (objeto === "cama") {
      accionar(despierta ? "dormir" : "despertar", despierta ? "🌙 la acuestas" : "☀️ la despiertas");
    }
  }

  document.querySelectorAll(".acciones button").forEach((boton) =>
    boton.addEventListener("click", () => {
      if (boton.dataset.accion === "jugar") habitacion.lanzarPelota();
      accionar(boton.dataset.accion, boton.textContent.trim().toLowerCase());
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

  // ── Voz: los navegadores solo dejan sonar después de un toque ───────
  const botonVoz = $("#boton-voz");
  const pintarVoz = () => {
    botonVoz.textContent = voz.activa ? "🔊" : "🔇";
    botonVoz.classList.toggle("apagada", !voz.activa);
    $("#sonido-aviso").classList.toggle("oculta", !voz.activa || (voz.ctx && voz.ctx.state === "running"));
  };
  botonVoz.addEventListener("click", () => { voz.alternar(); pintarVoz(); });
  const desbloquear = () => { voz.desbloquear(); setTimeout(pintarVoz, 100); };
  ["pointerdown", "keydown"].forEach((evento) => document.addEventListener(evento, desbloquear, { passive: true }));
  pintarVoz();

  // ── Panel en el celular ─────────────────────────────────────────────
  $("#boton-panel").addEventListener("click", () => $("#panel").classList.toggle("abierto"));

  conectar();
})();
