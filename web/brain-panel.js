/* Panel del cerebro: emoción PAD, léxico por estado, grafo en vivo, pensamientos e hipótesis.
 * Todo lo que se muestra viene del servidor; aquí solo se dibuja. */
(function () {
  "use strict";

  const $ = (selector) => document.querySelector(selector);
  const icono = window.icono;
  const escapar = (texto) =>
    String(texto ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  const firmado = (valor, decimales = 2) => (valor >= 0 ? "+" : "") + Number(valor).toFixed(decimales);
  const porcentaje = (valor) => `${Math.round(Math.max(0, Math.min(1, valor)) * 100)}%`;

  const ICONOS = {
    recuerdo: "message-circle", deduccion: "lightbulb", duda: "circle-help", opinion: "hand-heart", reencuentro: "repeat",
    sueno: "moon-star", correccion: "pencil",
  };
  const NOMBRES_TIPO = {
    recuerdo: "recuerdo", deduccion: "deducción", duda: "duda", opinion: "opinión", reencuentro: "reencuentro", sueno: "sueño",
    correccion: "corrección",
  };
  const NOMBRES_PAD = { p: "Placer", a: "Activación", d: "Dominancia" };
  const NOMBRES_NECESIDAD = {
    energia: ["zap", "Energía"], saciedad: ["utensils", "Saciedad"], compania: ["users", "Compañía"],
    seguridad: ["shield", "Seguridad"], aburrimiento: ["hourglass", "Aburrimiento"],
  };
  const NOMBRES_EVALUACION = { inesperado: "inesperado", agrado: "agrado", amenaza: "amenaza", control: "control", relevancia: "relevancia" };
  const formatoHora = (hora) => `${String(Math.floor(hora)).padStart(2, "0")}:${String(Math.floor((hora % 1) * 60)).padStart(2, "0")}`;
  const NOMBRES_RASGO = {
    curiosidad: "curiosidad", timidez: "timidez", terquedad: "terquedad", sensibilidad: "sensibilidad", locuacidad: "habla sola",
  };

  function barraPad(valor) {
    const ancho = Math.abs(valor) * 50;
    const izquierda = valor >= 0 ? 50 : 50 - ancho;
    return `<div class="barra-pad"><span class="${valor >= 0 ? "pos" : "neg"}" style="left:${izquierda}%;width:${ancho}%"></span></div>`;
  }

  function barra01(valor, clase = "") {
    return `<div class="barra-01 ${clase}"><span style="width:${porcentaje(valor)}"></span></div>`;
  }

  function hace(segundos) {
    segundos = Math.max(0, Math.round(segundos));
    if (segundos < 60) return `hace ${segundos} s`;
    if (segundos < 3600) return `hace ${Math.round(segundos / 60)} min`;
    return `hace ${Math.round(segundos / 3600)} h`;
  }

  // ── Grafo de conceptos (disposición por fuerzas, sin librerías) ─────
  class Grafo {
    constructor(lienzo) {
      this.lienzo = lienzo;
      this.ctx = lienzo.getContext("2d");
      this.nodos = new Map();
      this.aristas = [];
      this.visible = false;
      this.calor = 1;
      this.arrastrado = null;
      this._ajustar();
      new ResizeObserver(() => this._ajustar()).observe(lienzo);
      lienzo.addEventListener("pointerdown", (e) => this._presionar(e));
      lienzo.addEventListener("pointermove", (e) => this._mover(e));
      window.addEventListener("pointerup", () => (this.arrastrado = null));
      requestAnimationFrame(() => this._bucle());
    }

    datos(cerebro) {
      // Si la pestaña está oculta el lienzo mide 0: se usa un tamaño provisional.
      const centro = { x: (this.ancho || 400) / 2, y: (this.alto || 400) / 2 };
      for (const concepto of cerebro.conceptos) {
        let nodo = this.nodos.get(concepto.nodo);
        if (!nodo) {
          const vecino = cerebro.relaciones.find((r) => r.destino === concepto.nodo && this.nodos.has(r.origen));
          const base = vecino ? this.nodos.get(vecino.origen) : centro;
          nodo = { id: concepto.nodo, x: base.x + (Math.random() - 0.5) * 90, y: base.y + (Math.random() - 0.5) * 90, vx: 0, vy: 0 };
          this.nodos.set(concepto.nodo, nodo);
        }
        Object.assign(nodo, concepto);
      }
      this.aristas = [
        ...cerebro.relaciones.map((r) => ({ a: r.origen, b: r.destino, tipo: r.origen_dato, peso: r.peso, estado: r.estado, etiqueta: r.etiqueta })),
        ...cerebro.forma.map((f) => ({ a: f.a, b: f.b, tipo: "forma", peso: f.similitud, estado: "activo" })),
        ...cerebro.hipotesis
          .filter((h) => h.estado === "pendiente")
          .map((h) => ({ a: h.origen, b: h.destino, tipo: "hipotesis", peso: 0.5, estado: "activo" })),
      ].filter((arista) => this.nodos.has(arista.a) && this.nodos.has(arista.b));
      this.calor = Math.max(this.calor, 0.6);
    }

    _ajustar() {
      const dpr = window.devicePixelRatio || 1;
      const { width, height } = this.lienzo.getBoundingClientRect();
      if (!width || !height) return;
      this.ancho = width;
      this.alto = height;
      for (const nodo of this.nodos.values()) {
        if (!Number.isFinite(nodo.x) || !Number.isFinite(nodo.y)) {
          nodo.x = width / 2 + (Math.random() - 0.5) * 90;
          nodo.y = height / 2 + (Math.random() - 0.5) * 90;
          nodo.vx = nodo.vy = 0;
        }
      }
      this.lienzo.width = Math.round(width * dpr);
      this.lienzo.height = Math.round(height * dpr);
      this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    }

    _coordenadas(evento) {
      const caja = this.lienzo.getBoundingClientRect();
      return { x: evento.clientX - caja.left, y: evento.clientY - caja.top };
    }

    _presionar(evento) {
      const { x, y } = this._coordenadas(evento);
      for (const nodo of this.nodos.values()) {
        if (Math.hypot(nodo.x - x, nodo.y - y) < this._radio(nodo) + 6) {
          this.arrastrado = nodo;
          this.calor = 1;
          return;
        }
      }
    }

    _mover(evento) {
      if (!this.arrastrado) return;
      const { x, y } = this._coordenadas(evento);
      this.arrastrado.x = x;
      this.arrastrado.y = y;
      this.arrastrado.vx = this.arrastrado.vy = 0;
    }

    _radio(nodo) {
      return 6 + 12 * (nodo.importancia || 0);
    }

    _paso() {
      const nodos = [...this.nodos.values()];
      const centroX = this.ancho / 2;
      const centroY = this.alto / 2;
      for (let i = 0; i < nodos.length; i++) {
        for (let j = i + 1; j < nodos.length; j++) {
          const a = nodos[i];
          const b = nodos[j];
          let dx = b.x - a.x;
          let dy = b.y - a.y;
          const distancia2 = Math.max(dx * dx + dy * dy, 30);
          const fuerza = 2200 / distancia2;
          const distancia = Math.sqrt(distancia2);
          dx /= distancia;
          dy /= distancia;
          a.vx -= dx * fuerza; a.vy -= dy * fuerza;
          b.vx += dx * fuerza; b.vy += dy * fuerza;
        }
      }
      for (const arista of this.aristas) {
        const a = this.nodos.get(arista.a);
        const b = this.nodos.get(arista.b);
        const dx = b.x - a.x;
        const dy = b.y - a.y;
        const distancia = Math.max(Math.hypot(dx, dy), 1);
        const largo = arista.tipo === "forma" ? 60 : 110;
        const fuerza = (distancia - largo) * 0.012;
        a.vx += (dx / distancia) * fuerza; a.vy += (dy / distancia) * fuerza;
        b.vx -= (dx / distancia) * fuerza; b.vy -= (dy / distancia) * fuerza;
      }
      for (const nodo of nodos) {
        if (nodo === this.arrastrado) continue;
        nodo.vx += (centroX - nodo.x) * 0.003;
        nodo.vy += (centroY - nodo.y) * 0.003;
        nodo.vx *= 0.82;
        nodo.vy *= 0.82;
        nodo.x += nodo.vx * this.calor;
        nodo.y += nodo.vy * this.calor;
        const margen = this._radio(nodo) + 4;
        nodo.x = Math.max(margen, Math.min(this.ancho - margen, nodo.x));
        nodo.y = Math.max(margen, Math.min(this.alto - margen - 14, nodo.y));   // deja lugar a la etiqueta
      }
      this.calor = Math.max(0.05, this.calor * 0.995);
    }

    _dibujar() {
      const ctx = this.ctx;
      ctx.clearRect(0, 0, this.ancho, this.alto);
      if (!this.nodos.size) {
        ctx.fillStyle = "#9a9286";
        ctx.font = "italic 12px system-ui";
        ctx.textAlign = "center";
        ctx.fillText("La red nace vacía.", this.ancho / 2, this.alto / 2 - 10);
        ctx.fillText("Enséñale frases como «el fuego quema».", this.ancho / 2, this.alto / 2 + 10);
        return;
      }
      const alfa = { activo: 0.9, tenue: 0.55, latente: 0.2 };
      for (const arista of this.aristas) {
        const a = this.nodos.get(arista.a);
        const b = this.nodos.get(arista.b);
        const color = { "enseñado": "107, 143, 78", deducido: "122, 95, 192", hipotesis: "122, 95, 192", forma: "168, 159, 146" }[arista.tipo];
        ctx.strokeStyle = `rgba(${color}, ${alfa[arista.estado] ?? 0.6})`;
        ctx.lineWidth = arista.tipo === "forma" ? 1.5 : 1 + 3 * arista.peso;
        ctx.setLineDash(arista.tipo === "hipotesis" ? [6, 5] : arista.tipo === "forma" ? [2, 4] : []);
        const angulo = Math.atan2(b.y - a.y, b.x - a.x);
        const inicioX = a.x + Math.cos(angulo) * this._radio(a);
        const inicioY = a.y + Math.sin(angulo) * this._radio(a);
        const finX = b.x - Math.cos(angulo) * (this._radio(b) + 3);
        const finY = b.y - Math.sin(angulo) * (this._radio(b) + 3);
        ctx.beginPath();
        ctx.moveTo(inicioX, inicioY);
        ctx.lineTo(finX, finY);
        ctx.stroke();
        ctx.setLineDash([]);
        if (arista.tipo !== "forma") {
          ctx.fillStyle = ctx.strokeStyle;
          ctx.beginPath();
          ctx.moveTo(finX, finY);
          ctx.lineTo(finX - Math.cos(angulo - 0.4) * 9, finY - Math.sin(angulo - 0.4) * 9);
          ctx.lineTo(finX - Math.cos(angulo + 0.4) * 9, finY - Math.sin(angulo + 0.4) * 9);
          ctx.fill();
        }
        if (arista.etiqueta) {
          ctx.fillStyle = "#7a7064";
          ctx.font = "italic 11px system-ui";
          ctx.textAlign = "center";
          ctx.fillText(`[${arista.etiqueta}]`, (a.x + b.x) / 2, (a.y + b.y) / 2 - 5);
        }
      }
      const colores = { activo: "#5b8c3a", tenue: "#d9a33b", latente: "#c9c2b6" };
      for (const nodo of this.nodos.values()) {
        const radio = this._radio(nodo);
        ctx.save();
        if (nodo.activacion > 0.05) {
          ctx.shadowColor = "rgba(240, 190, 60, 0.9)";
          ctx.shadowBlur = 28 * nodo.activacion;
        }
        ctx.fillStyle = colores[nodo.estado] || colores.tenue;
        ctx.beginPath();
        ctx.arc(nodo.x, nodo.y, radio, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
        if (Math.abs(nodo.valencia) > 0.15) {
          ctx.strokeStyle = nodo.valencia > 0 ? "#3f9a62" : "#c8553d";
          ctx.lineWidth = 2 + 2 * Math.abs(nodo.valencia);
          ctx.beginPath();
          ctx.arc(nodo.x, nodo.y, radio + 2, 0, Math.PI * 2);
          ctx.stroke();
        }
        ctx.fillStyle = nodo.estado === "latente" ? "#9a9286" : "#2f2a24";
        ctx.font = `${nodo.estado === "activo" ? "600 " : ""}13px system-ui`;
        ctx.textAlign = "center";
        ctx.fillText(nodo.nodo, nodo.x, nodo.y + radio + 14);
      }
    }

    _bucle() {
      if (this.visible) {
        if (!this.ancho) this._ajustar();
        this._paso();
        this._dibujar();
      }
      requestAnimationFrame(() => this._bucle());
    }
  }

  // ── Panel ───────────────────────────────────────────────────────────
  class PanelCerebro {
    constructor({ onAdelantar, onNuevaCriatura }) {
      this.onAdelantar = onAdelantar;
      this.onNuevaCriatura = onNuevaCriatura;
      this.ultimoEstado = null;
      this.ultimoCerebro = null;
      this.criatura = null;
      this.pensamientosVistos = new Set();
      this.grafo = new Grafo($("#lienzo-grafo"));
      this.grafo.visible = true;
      document.querySelectorAll(".pestanas button").forEach((boton) =>
        boton.addEventListener("click", () => this.mostrar(boton.dataset.vista)));
      this._vistaTiempo();
    }

    mostrar(vista) {
      if (vista === "cuerpo") this._vistaCuerpo();
      document.querySelectorAll(".pestanas button").forEach((b) => b.classList.toggle("activa", b.dataset.vista === vista));
      document.querySelectorAll(".vista").forEach((v) => v.classList.toggle("activa", v.id === `vista-${vista}`));
    }

    identidad(datos) {
      this.criatura = datos;
      this.pensamientosVistos.clear();
      this._vistaTiempo();
    }

    estado(estado) {
      this.ultimoEstado = estado;
      const e = estado.emocion;
      const filasPad = ["p", "a", "d"].map((eje) =>
        `<div class="fila"><span>${NOMBRES_PAD[eje]}</span>${barraPad(e[eje])}<span class="valor">${firmado(e[eje])}</span></div>`).join("");
      const animo = ["p", "a", "d"].map((eje) =>
        `<div class="fila"><span>${NOMBRES_PAD[eje]}</span>${barraPad(estado.animo[eje])}<span class="valor">${firmado(estado.animo[eje])}</span></div>`).join("");
      const causas = estado.causas.length
        ? estado.causas.slice(0, 8).map((c) => {
            const evaluacion = c.evaluacion
              ? Object.entries(c.evaluacion).map(([k, v]) => `${NOMBRES_EVALUACION[k]} ${v.toFixed(2)}`).join(" · ")
              : "";
            return `
            <li><span><b>${escapar(c.causa)}</b> ${c.detalle ? `<span class="apagado">· ${escapar(c.detalle)}</span>` : ""}
              ${evaluacion ? `<br><span class="evaluacion">${evaluacion}</span>` : ""}
              <br><span class="apagado">${hace(estado.ahora_real - c.momento_real)}</span></span>
              <span class="delta">P ${firmado(c.delta[0])} · A ${firmado(c.delta[1])} · D ${firmado(c.delta[2])}</span></li>`;
          }).join("")
        : `<li class="vacio">Todavía no ha sentido nada.</li>`;
      const impulsos = estado.impulsos || { acercarse: 0, alejarse: 0 };
      const relacion = estado.relacion;
      const rasgos = Object.entries(estado.rasgos)
        .map(([rasgo, valor]) => `<span class="chip">${NOMBRES_RASGO[rasgo] || rasgo} ${valor.toFixed(2)}</span>`).join("");
      $("#vista-emocion").innerHTML = `
        <section class="tarjeta">
          <h3>Emoción <span class="chip grande">${escapar(e.etiqueta)}</span>${estado.despierta ? "" : `<span class="chip">${icono("moon")}dormida</span>`}</h3>
          ${filasPad}
          <p class="nota">Espacio PAD (Mehrabian). Cambia en segundos y vuelve sola a su línea base.</p>
        </section>
        <section class="tarjeta">
          <h3>Estado de ánimo <span class="chip">${escapar(estado.animo.etiqueta)}</span></h3>
          ${animo}
          <p class="nota">Sigue a las emociones durante horas de su tiempo.</p>
        </section>
        <section class="tarjeta">
          <h3>Impulsos ${e.ambivalencia > 0 ? `<span class="chip">${icono("scale")}ambivalente</span>` : ""}</h3>
          <div class="fila"><span>Acercarse</span>${barra01(impulsos.acercarse)}<span class="valor">${impulsos.acercarse.toFixed(2)}</span></div>
          <div class="fila"><span>Alejarse</span>${barra01(impulsos.alejarse, "tierra")}<span class="valor">${impulsos.alejarse.toFixed(2)}</span></div>
          <p class="nota">Puede querer acercarse y alejarse a la vez (curiosidad y miedo): entonces se acerca y retrocede.</p>
        </section>
        <section class="tarjeta">
          <h3>Relación con su dueño</h3>
          <div class="fila"><span>Confianza</span>${barra01(relacion.confianza, "tierra")}<span class="valor">${relacion.confianza.toFixed(2)}</span></div>
          <div class="fila"><span>Afecto</span>${barra01(relacion.afecto, "tierra")}<span class="valor">${relacion.afecto.toFixed(2)}</span></div>
          <div class="fila"><span>Familiaridad</span>${barra01(relacion.familiaridad || 0, "tierra")}<span class="valor">${(relacion.familiaridad || 0).toFixed(2)}</span></div>
          <div class="fila"><span>Experiencia</span>${barraPad(relacion.experiencia || 0)}<span class="valor">${firmado(relacion.experiencia || 0)}</span></div>
          <p class="nota">La capa más lenta: con los días, la confianza sigue al balance de lo vivido contigo.</p>
        </section>
        <section class="tarjeta">
          <h3>Rastro causal</h3>
          <ul class="causas">${causas}</ul>
        </section>
        <section class="tarjeta">
          <h3>Rasgos innatos</h3>
          <div class="rasgos">${rasgos}</div>
          <p class="nota">Salen de su semilla al nacer: dos criaturas criadas igual no terminan idénticas.</p>
        </section>`;
      this._vistaCuerpo();
      this._vistaTiempo();
    }

    actividad(actividad) {
      this.ultimaActividad = actividad;
      this._vistaCuerpo();
    }

    _vistaCuerpo() {
      const estado = this.ultimoEstado;
      if (!estado) return;
      const comportamiento = estado.comportamiento || { actual: null, historial: [] };
      const actual = this.ultimaActividad || comportamiento.actual;
      const necesidades = Object.entries(NOMBRES_NECESIDAD).map(([clave, [emoji, nombre]]) => {
        const valor = estado.necesidades[clave] || 0;
        return `<div class="fila"><span>${icono(emoji)}${nombre}</span>${barra01(valor, clave === "aburrimiento" ? "tierra" : "")}<span class="valor">${porcentaje(valor)}</span></div>`;
      }).join("");
      const historial = (comportamiento.historial || []).slice(0, 8).map((a) => `
        <li><span class="marca-lista">${icono("activity")}</span><div><b>${escapar(a.descripcion)}</b><small>${hace(estado.ahora_real - a.inicio)}</small>
          <p>${escapar(a.motivo)}</p></div></li>`).join("");
      $("#vista-cuerpo").innerHTML = `
        <section class="tarjeta">
          <h3>Ahora ${actual && actual.ambivalente ? `<span class="chip">${icono("scale")}ambivalente</span>` : ""}</h3>
          ${actual ? `<p><b>${escapar(actual.descripcion)}</b> — ${escapar(actual.motivo)}</p>
            <p class="nota">${actual.iniciativa === "dueño" ? "Lo hace porque interactuaste con ella." : "Lo eligió ella según cómo se siente."}</p>` : "<p class='vacio'>…</p>"}
        </section>
        <section class="tarjeta">
          <h3>Necesidades</h3>
          ${necesidades}
          <p class="nota">Energía, saciedad y compañía bajan con su tiempo; la seguridad cae con los sustos; el aburrimiento crece si nada pasa.</p>
        </section>
        <section class="tarjeta">
          <h3>Su día</h3>
          <p>${icono("clock")} ${formatoHora(estado.hora)} · ${estado.noche ? `${icono("moon")} es de noche` : `${icono("sun")} es de día`} · somnolencia ${porcentaje(Math.min(1, estado.somnolencia))}</p>
          <p class="nota">Su reloj del día empezó a la hora en que nació. De noche le da sueño y se va sola a la cama.</p>
        </section>
        ${historial ? `<section class="tarjeta"><h3>Lo que hizo antes</h3><ul class="lista">${historial}</ul></section>` : ""}`;
    }

    cerebro(cerebro) {
      this.ultimoCerebro = cerebro;
      this._vistaLexico(cerebro);
      this.grafo.datos(cerebro);
      this._vistaPensamientos(cerebro.pensamientos);
      this._vistaHipotesis(cerebro.hipotesis);
      this._vistaTiempo();
    }

    pensamiento(pensamiento) {
      if (!this.ultimoCerebro) return;
      const lista = this.ultimoCerebro.pensamientos.filter((p) => p.id !== pensamiento.id);
      this.ultimoCerebro.pensamientos = [pensamiento, ...lista].slice(0, 60);
      this._vistaPensamientos(this.ultimoCerebro.pensamientos);
    }

    _vistaLexico(cerebro) {
      const estado = this.ultimoEstado;
      const grupos = { activo: [], tenue: [], latente: [] };
      for (const palabra of cerebro.lexico) grupos[palabra.estado].push(palabra);
      const chip = (p) => {
        const valencia = p.valencia > 0.15 ? "pos" : p.valencia < -0.15 ? "neg" : "neutra";
        const titulo = [
          `importancia ${p.importancia.toFixed(2)} (${p.estado})`,
          `valencia ${firmado(p.valencia)}`,
          `informatividad ${p.informatividad.toFixed(2)}${p.concepto ? " · concepto" : ""}`,
          `oída ${p.frecuencia} ${p.frecuencia === 1 ? "vez" : "veces"} · usos ${p.usos}`,
          `aprendida ${p.veces_aprendida} ${p.veces_aprendida === 1 ? "vez" : "veces"}`,
          Math.abs(p.polaridad) >= 0.3 ? `significa «${p.polaridad > 0 ? "sí" : "no"}» (${firmado(p.polaridad)})` : "",
          p.interrogativa ? "abre preguntas" : "",
        ].filter(Boolean).join("\n");
        const marca = Math.abs(p.polaridad) >= 0.3 ? (p.polaridad > 0 ? " <small>sí</small>" : " <small>no</small>") : p.interrogativa ? " ¿" : "";
        return `<span class="palabra ${p.estado}" title="${escapar(titulo)}"><i class="val ${valencia}"></i>${escapar(p.palabra)}${marca}${p.veces_aprendida > 1 ? `<sup>↺${p.veces_aprendida}</sup>` : ""}<span class="imp" style="width:${porcentaje(p.importancia)}"></span></span>`;
      };
      const grupo = (clave, titulo, vacio) => `
        <section class="tarjeta">
          <h3>${titulo} <span class="chip">${grupos[clave].length}</span></h3>
          <div class="chips">${grupos[clave].map(chip).join("") || `<span class="vacio">${vacio}</span>`}</div>
        </section>`;
      let etapa = "";
      if (estado) {
        const { numero, nombre, activas, siguiente } = estado.etapa;
        const progreso = siguiente ? Math.min(1, activas / siguiente) : 1;
        etapa = `
          <section class="tarjeta">
            <h3>Etapa ${numero} · ${escapar(nombre)}</h3>
            <div class="progreso"><span style="width:${porcentaje(progreso)}"></span></div>
            <p class="nota">${activas} palabra(s) activa(s)${siguiente ? ` · la etapa ${numero + 1} llega con ${siguiente}` : " · última etapa de la fase 1"}.
            Pasa el cursor sobre una palabra para ver por qué está ahí.</p>
          </section>`;
      }
      $("#vista-lexico").innerHTML = etapa
        + grupo("activo", '<i class="punto activo"></i>Activas', "Ninguna todavía: repítele palabras.")
        + grupo("tenue", '<i class="punto tenue"></i>Tenues', "—")
        + grupo("latente", '<i class="punto latente"></i>Latentes', "Nada latente: nunca olvida, solo atenúa.");
    }

    _vistaPensamientos(pensamientos) {
      const ahora = this.ultimoEstado ? this.ultimoEstado.ahora_real : Date.now() / 1000;
      const items = pensamientos.map((p) => {
        const nuevo = !this.pensamientosVistos.has(p.id);
        this.pensamientosVistos.add(p.id);
        return `<li class="${nuevo ? "nuevo" : ""}"><span class="marca-lista ${p.tipo}">${icono(ICONOS[p.tipo] || "message-circle")}</span><div>
          <b>${escapar(p.texto)}</b><small>${NOMBRES_TIPO[p.tipo] || escapar(p.tipo)} · ${hace(ahora - p.momento_real)}</small>
          <p>${escapar(p.explicacion)}</p>
          ${p.en_voz_alta ? `<p class="dicho">Lo dijo en voz alta: «${escapar(p.dicho)}»</p>` : ""}
        </div></li>`;
      }).join("");
      $("#vista-pensamientos").innerHTML = items
        ? `<p class="nota">Lo que piensa, lo diga o no. El texto en negrita es la idea; lo que dice depende de su etapa.</p><ul class="lista">${items}</ul>`
        : `<p class="vacio">Todavía no ha pensado nada. Cuando dejes de escribirle un rato, piensa sola.</p>`;
    }

    _vistaHipotesis(hipotesis) {
      const items = hipotesis.map((h) => `
        <li class="hip"><span class="marca-lista ${h.estado}">${icono(h.estado === "confirmada" ? "circle-check" : h.estado === "rechazada" ? "circle-x" : "lightbulb")}</span><div>
          <b>${escapar(h.origen)} → ${escapar(h.destino)}</b>
          <span class="estado-chip ${h.estado}">${h.estado}</span>
          <div class="cadena">${escapar(h.camino)}</div>
          <p>confianza ${h.confianza.toFixed(3)} · ${h.fuente === "pensamiento" ? "la pensó sola" : "durante una conversación"}${h.preguntada ? " · te la preguntó" : ""}${h.motivo ? ` · ${escapar(h.motivo)}` : ""}</p>
        </div></li>`).join("");
      $("#vista-hipotesis").innerHTML = items
        ? `<p class="nota">Si sabe A → B y B → C, propone A → C. «≈» es el parecido de forma (quema ≈ quemar).</p><ul class="lista">${items}</ul>`
        : `<p class="vacio">Sin hipótesis aún. Prueba enseñarle «el fuego quema» y luego «quemar duele».</p>`;
    }

    _vistaTiempo() {
      const estado = this.ultimoEstado;
      const cerebro = this.ultimoCerebro;
      const suenos = cerebro && cerebro.suenos.length
        ? cerebro.suenos.map((s) => `<li><span class="marca-lista sueno">${icono("moon-star")}</span><div><b>${escapar(s.conceptos.join("… ") || "(sin sueño)")}</b>
            <p>Reforzó ${s.total_reforzados}: ${escapar(s.reforzados.join(", ") || "—")}</p>
            <p>Atenuó ${s.total_atenuados}: ${escapar(s.atenuados.join(", ") || "—")}</p></div></li>`).join("")
        : "";
      const vista = $("#vista-tiempo");
      const confirmando = vista.dataset.confirmando === "1";
      vista.innerHTML = `
        <section class="tarjeta">
          <h3>Su tiempo</h3>
          <p>Edad: <b>${estado ? escapar(estado.edad_texto) : "—"}</b> · velocidad ×${estado ? estado.velocidad : 1}
          ${cerebro ? ` · ${cerebro.episodios} recuerdos guardados` : ""}</p>
          <p class="nota">La velocidad se cambia con la variable de entorno <code>MUYU_VELOCIDAD_TIEMPO</code> (60 = un minuto real es una hora suya).</p>
        </section>
        <section class="tarjeta">
          <h3>Adelantar el tiempo</h3>
          <div class="botones">
            ${[[1, "+1 h"], [12, "+12 h"], [24, "+1 día"], [72, "+3 días"], [168, "+1 semana"]]
              .map(([horas, texto]) => `<button class="boton" data-horas="${horas}">${texto}</button>`).join("")}
          </div>
          <p class="nota">Para probar la atenuación, las necesidades y la memoria sin olvido: lo que no se usa pasa a tenue y luego a latente, pero nunca se borra.</p>
        </section>
        ${suenos ? `<section class="tarjeta"><h3>Últimos sueños</h3><ul class="lista">${suenos}</ul></section>` : ""}
        <section class="tarjeta">
          <h3>Criatura</h3>
          <p class="nota">Id: <code>${escapar(this.criatura ? this.criatura.id : "—")}</code></p>
          <div class="botones" style="margin-top:8px">
            <button class="boton ${confirmando ? "confirmar" : "peligro"}" id="boton-nueva">${confirmando ? "¿Seguro? Pulsa otra vez" : `${icono("sprout")} Criar una criatura nueva`}</button>
          </div>
          <p class="nota">La criatura actual no se borra: su archivo queda en <code>data/creatures/</code>.</p>
        </section>`;
      vista.querySelectorAll("[data-horas]").forEach((boton) =>
        boton.addEventListener("click", () => this.onAdelantar(Number(boton.dataset.horas))));
      vista.querySelector("#boton-nueva").addEventListener("click", () => {
        if (vista.dataset.confirmando === "1") {
          vista.dataset.confirmando = "0";
          this.onNuevaCriatura();
        } else {
          vista.dataset.confirmando = "1";
          setTimeout(() => { vista.dataset.confirmando = "0"; this._vistaTiempo(); }, 4000);
        }
        this._vistaTiempo();
      });
    }
  }

  window.PanelCerebro = PanelCerebro;
})();
