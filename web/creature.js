/* Muyu en pixel art: una semilla con un brote que crece con su lenguaje.
 * Se dibuja píxel a píxel en el lienzo de baja resolución de la habitación. Su
 * forma (postura), sus ojos, su boca, su color y su velocidad salen de su emoción
 * (PAD); lo que hace su cuerpo sale de la actividad que eligió el servidor. */
(function () {
  "use strict";

  const mezclar = (a, b, t) => a + (b - a) * t;
  const acotar = (v, min, max) => Math.max(min, Math.min(max, v));
  const BAYER = [[0, 8, 2, 10], [12, 4, 14, 6], [3, 11, 1, 9], [15, 7, 13, 5]];

  // Glifos de partículas (1 = píxel encendido).
  const GLIFOS = {
    corazon: ["01010", "11111", "11111", "01110", "00100"],
    pregunta: ["111", "001", "011", "000", "010"],
    exclamacion: ["1", "1", "1", "0", "1"],
    z: ["111", "001", "010", "100", "111"],
    nota: ["011", "010", "010", "110", "110"],
    puntos: ["10101"],
    estrella: ["010", "111", "010"],
    nube: ["0110", "1111"],
    enojo: ["101", "010", "101"],
    miga: ["11"],
  };
  const PARTICULAS_DE_GESTO = {
    carino: ["corazon", "#e2607a", 4], alegria: ["estrella", "#e0a32e", 3], saludo: ["estrella", "#e0a32e", 2],
    confusion: ["pregunta", "#7a5fc0", 1], duda: ["pregunta", "#7a5fc0", 1], curiosidad: ["pregunta", "#7a5fc0", 1],
    reconocer: ["puntos", "#7a5fc0", 1], sonar: ["nube", "#9a8fc4", 2], enojo: ["enojo", "#c8553d", 1],
    miedo: ["exclamacion", "#c8553d", 1], sobresalto: ["exclamacion", "#c8553d", 1], pedir: ["exclamacion", "#e0a32e", 1],
    tristeza: ["puntos", "#7d86b8", 1], dormir: ["z", "#7d86b8", 1],
  };

  class Criatura {
    constructor() {
      this.x = 128;
      this.y = 138;
      this.mirando = 1;               // -1 izquierda, 1 derecha
      this.pad = { p: 0, a: 0, d: 0 };
      this.objetivoPad = { p: 0, a: 0, d: 0 };
      this.etiqueta = "neutral";
      this.ambivalencia = 0;
      this.despierta = true;
      this.etapa = 0;
      this.tono = 110;
      this.actividad = { nombre: "quieta", objeto: null, ambivalente: false };
      this.inicioActividad = 0;
      this.gestoActual = null;
      this.particulas = [];
      this.hablaHasta = 0;
      this.parpadeoHasta = 0;
      this.proximoParpadeo = 2500;
      this.paso = 0;                  // fase del caminar
      this.pose = {};
      this.habitacion = null;         // la asigna la habitación
    }

    // ── Entradas desde el servidor ────────────────────────────────────
    estado({ emocion, despierta, etapa }) {
      if (emocion) {
        this.objetivoPad = { p: emocion.p, a: emocion.a, d: emocion.d };
        this.etiqueta = emocion.etiqueta;
        this.ambivalencia = emocion.ambivalencia || 0;
      }
      if (despierta !== undefined) this.despierta = despierta;
      if (etapa !== undefined) this.etapa = etapa;
    }

    hacer(actividad, ahora) {
      if (!actividad) return;
      const cambio = actividad.nombre !== this.actividad.nombre || actividad.inicio !== this.actividad.inicio;
      this.actividad = actividad;
      if (cambio) this.inicioActividad = ahora;
      if (!this.ubicada && this.habitacion) {
        // Al abrir la página aparece donde estaba, sin cruzar el cuarto.
        const destino = this.habitacion.punto(actividad.nombre === "dormir" ? "cama" : actividad.objeto, this);
        if (destino) { this.x = destino.x; this.y = destino.y; }
        this.ubicada = true;
      }
    }

    gesto(nombre, ahora) {
      if (!nombre) return;
      this.gestoActual = { nombre, inicio: ahora, duracion: nombre === "asentir" || nombre === "negar" ? 1000 : 1300 };
      const particula = PARTICULAS_DE_GESTO[nombre];
      if (particula) for (let i = 0; i < particula[2]; i++) this.particula(particula[0], particula[1], ahora + i * 140);
    }

    hablar(duracionMs, ahora) {
      this.hablaHasta = ahora + duracionMs;
    }

    particula(glifo, color, desde) {
      this.particulas.push({
        glifo, color, nace: desde,
        x: this.x + (Math.random() - 0.5) * 16, y: this.y - this.altoActual() - 4,
        vx: (Math.random() - 0.5) * 6, vy: -10 - Math.random() * 6, vida: 1,
      });
    }

    escala() {
      return acotar(0.82 + 0.33 * (this.y - 110) / 45, 0.75, 1.18);
    }

    altoActual() {
      return 2 * 15 * this.escala() * (this.pose.sy || 1);
    }

    cabeza() {
      return { x: this.x, y: this.y - this.altoActual() - 6 - 2 * this.etapa };
    }

    contiene(x, y) {
      const r = 15 * this.escala();
      return Math.abs(x - this.x) < r && y < this.y + 2 && y > this.y - this.altoActual() - 4;
    }

    // ── Movimiento y pose ─────────────────────────────────────────────
    actualizar(dt, ahora) {
      for (const eje of ["p", "a", "d"]) this.pad[eje] = mezclar(this.pad[eje], this.objetivoPad[eje], Math.min(1, dt * 2.5));
      const { p, a } = this.pad;
      const hab = this.habitacion;
      const nombre = this.despierta ? this.actividad.nombre : "dormir";
      const enActividad = (ahora - this.inicioActividad) / 1000;
      let destino = hab.punto(this.despierta ? this.actividad.objeto : "cama", this);

      // Ambivalencia: se acerca y retrocede (curiosidad y miedo a la vez).
      if (this.despierta && (this.actividad.ambivalente || this.ambivalencia > 0.3) && destino) {
        const retroceso = Math.sin(enActividad * 2.4) > 0.2;
        if (retroceso) destino = { x: destino.x + (this.x < 128 ? -22 : 22), y: destino.y - 10 };
      }

      let velocidad = 26 * (0.7 + 0.8 * Math.max(0, a));
      if (p < -0.3 && a < 0) velocidad *= 0.6;
      if (nombre === "ir_a_dormir" || nombre === "dormir") velocidad *= 0.7;
      if (nombre === "pedir_comida" || nombre === "buscarte") velocidad *= 1.2;

      let caminando = false;
      if (destino) {
        const dx = destino.x - this.x;
        const dy = destino.y - this.y;
        const distancia = Math.hypot(dx, dy);
        if (distancia > 1.5) {
          const avance = Math.min(distancia, velocidad * dt);
          this.x += (dx / distancia) * avance;
          this.y += (dy / distancia) * avance;
          if (Math.abs(dx) > 1) this.mirando = Math.sign(dx);
          caminando = true;
        }
      }
      this.paso += dt * (caminando ? 10 + 6 * Math.max(0, a) : 0);
      this.pose = this._pose(nombre, ahora, enActividad, caminando);
      this._efectosDeActividad(nombre, ahora, enActividad, caminando, dt);
      this._actualizarParticulas(dt, ahora);
    }

    _pose(nombre, ahora, enActividad, caminando) {
      const { p, a, d } = this.pad;
      const t = ahora / 1000;
      const pose = { sx: 1 + 0.03 * -d, sy: 1 + 0.06 * d, dx: 0, dy: 0, inclinar: 0, ojos: null, boca: null, mira: null };
      if (!this.despierta && !caminando) {
        const respiro = Math.sin(t * 1.6);
        return { ...pose, sx: 1.22 + 0.02 * respiro, sy: 0.66 - 0.02 * respiro, ojos: "cerrados", boca: "plana", acostada: true };
      }
      if (!this.despierta) pose.ojos = "medio";      // camina medio dormida hasta la cama
      if (caminando) {
        const salto = Math.abs(Math.sin(this.paso));
        pose.dy = -salto * (1.5 + 2.5 * Math.max(0, a));
        pose.sy *= 1 + 0.04 * salto;
        pose.inclinar = 0.06 * this.mirando;
      } else {
        const respiro = Math.sin(t * (1.4 + 2 * Math.max(0, a)));
        pose.sy *= 1 + 0.02 * respiro;
        if (p > 0.35 && a > 0.25) pose.dy = -Math.abs(Math.sin(t * (3 + 3 * a))) * 3 * a;   // brinca de alegría
      }
      if (this.etiqueta === "miedo") { pose.dx += (Math.random() - 0.5) * 1.5; pose.sx *= 0.93; pose.sy *= 0.9; }
      if (this.etiqueta === "tristeza" || this.etiqueta === "aburrimiento") pose.sy *= 0.94;

      if (!caminando) {
        switch (nombre) {
          case "atenderte": case "buscarte":
            pose.mira = { x: 0, y: 1 };
            if (nombre === "buscarte" && Math.sin(t * 3) > 0.7) pose.dy -= 3;
            break;
          case "explorar":
            pose.inclinar = 0.18 * this.mirando + 0.05 * Math.sin(t * 6);
            pose.mira = { x: this.mirando, y: 1 };
            break;
          case "mirar_ventana":
            pose.mira = { x: 0, y: -1 };
            pose.inclinar = 0.04 * Math.sin(t * 0.8);
            break;
          case "descansar":
            pose.sx *= 1.12; pose.sy *= 0.82; pose.ojos = "medio";
            break;
          case "pedir_comida":
            pose.mira = { x: 0, y: 1 };
            if (Math.sin(t * 5) > 0.6) pose.dy -= 4;
            break;
          case "comer":
            pose.sy *= 1 + 0.06 * Math.sin(t * 12); pose.inclinar = 0.15 * this.mirando; pose.ojos = "felices";
            pose.mira = { x: this.mirando, y: 1 };
            break;
          case "esconderse":
            pose.sx *= 1.05; pose.sy *= 0.8; pose.dx += (Math.random() - 0.5) * 1.2; pose.mira = { x: 0, y: 1 };
            break;
          case "aburrirse":
            pose.sx *= 1.28; pose.sy *= 0.66; pose.ojos = "medio"; pose.boca = "plana";
            break;
          case "ir_a_dormir":
            pose.ojos = "medio"; pose.boca = enActividad > 1 && enActividad < 3 ? "bostezo" : null;
            break;
          case "quieta":
            pose.mira = { x: Math.sin(t * 0.7), y: Math.cos(t * 0.5) * 0.5 };
            break;
          default:
            break;
        }
      }

      // Gestos que acompañan lo que dice.
      const gesto = this.gestoActual;
      if (gesto) {
        const avance = (ahora - gesto.inicio) / gesto.duracion;
        if (avance >= 1 || avance < 0) {
          if (avance >= 1) this.gestoActual = null;
        } else {
          const curva = Math.sin(avance * Math.PI);
          switch (gesto.nombre) {
            case "asentir": pose.dy += Math.sin(avance * Math.PI * 4) * 2 * (1 - avance); pose.mira = { x: 0, y: 1 }; break;
            case "negar": pose.dx += Math.sin(avance * Math.PI * 6) * 3 * (1 - avance); break;
            case "duda": case "curiosidad": case "confusion": pose.inclinar += 0.22 * curva; break;
            case "alegria": case "saludo": case "sobresalto": pose.dy -= 7 * Math.abs(Math.sin(avance * Math.PI * 2)); break;
            case "carino": pose.sx *= 1 + 0.08 * curva; pose.sy *= 1 - 0.07 * curva; pose.ojos = "felices"; break;
            case "reconocer": pose.ojos = "entrecerrados"; pose.inclinar += 0.15 * curva; break;
            case "miedo": pose.sx *= 1 - 0.08 * curva; pose.sy *= 1 - 0.1 * curva; pose.dx += (Math.random() - 0.5) * 3; break;
            case "tristeza": pose.dy += 2 * curva; break;
            default: break;
          }
        }
      }
      return pose;
    }

    _efectosDeActividad(nombre, ahora, enActividad, caminando, dt) {
      if (!this.despierta) {
        if (Math.random() < dt * 0.7) this.particula("z", "#8b93c9", ahora);
        return;
      }
      if (caminando) return;
      const prob = (por) => Math.random() < dt * por;
      if (nombre === "explorar" && prob(0.35)) this.particula("pregunta", "#7a5fc0", ahora);
      if (nombre === "jugar" && prob(0.6)) this.particula("nota", "#e0a32e", ahora);
      if (nombre === "pedir_comida" && prob(0.5)) this.particula("exclamacion", "#e0a32e", ahora);
      if (nombre === "buscarte" && prob(0.4)) this.particula("pregunta", "#e2607a", ahora);
      if (nombre === "aburrirse" && prob(0.3)) this.particula("puntos", "#8b93c9", ahora);
      if (nombre === "comer" && prob(1.2)) this.particula("miga", "#9b6a3c", ahora);
    }

    _actualizarParticulas(dt, ahora) {
      for (const p of this.particulas) {
        if (ahora < p.nace) continue;
        p.x += p.vx * dt;
        p.y += p.vy * dt;
        p.vida -= dt * 0.55;
      }
      this.particulas = this.particulas.filter((p) => p.vida > 0);
    }

    // ── Dibujo ────────────────────────────────────────────────────────
    _paleta() {
      const { p, a } = this.pad;
      const sat = Math.round(30 + 28 * (p + 1) / 2);
      const luz = Math.round(50 + 6 * a);
      const clave = `${this.tono}|${sat}|${luz}`;
      if (this._clavePaleta !== clave) {
        this._clavePaleta = clave;
        this._paletaCache = {
          borde: `hsl(${this.tono} ${Math.round(sat * 0.8)}% ${luz - 30}%)`,
          sombra: `hsl(${this.tono} ${sat}% ${luz - 11}%)`,
          medio: `hsl(${this.tono} ${sat}% ${luz}%)`,
          luz: `hsl(${this.tono} ${sat}% ${luz + 9}%)`,
          brillo: `hsl(${this.tono} ${Math.round(sat * 0.8)}% ${luz + 22}%)`,
        };
      }
      return this._paletaCache;
    }

    dibujar(ctx, ahora) {
      const pose = this.pose;
      const s = this.escala();
      const rx = Math.max(6, Math.round(13 * s * pose.sx));
      const ry = Math.max(5, Math.round(15 * s * pose.sy));
      const base = Math.round(this.y + (pose.dy || 0));
      const cx = Math.round(this.x + (pose.dx || 0));
      const cy = base - ry;
      const inclinar = pose.inclinar || 0;
      const paleta = this._paleta();

      // Sombra en el suelo.
      ctx.fillStyle = "rgba(70, 45, 20, 0.22)";
      const sombra = Math.round(rx * 0.9);
      ctx.fillRect(Math.round(this.x) - sombra, Math.round(this.y), sombra * 2, 2);
      ctx.fillRect(Math.round(this.x) - sombra + 2, Math.round(this.y) + 2, sombra * 2 - 4, 1);

      const dentro = (px, py) => {
        const v = py / ry;
        if (v < -1 || v > 1) return false;
        const u = (px - inclinar * py) / rx;
        let ancho = 0.86 + 0.14 * v;
        if (v < -0.55) ancho *= 1 - (-0.55 - v) * 0.9;            // punta de semilla
        const perfil = v < 0 ? Math.sqrt(1 - v * v) : Math.pow(1 - v ** 4, 0.25);   // base plana
        return Math.abs(u) <= ancho * perfil;
      };

      for (let py = -ry; py <= ry; py++) {
        for (let px = -rx - 3; px <= rx + 3; px++) {
          if (!dentro(px, py)) continue;
          const borde = !dentro(px + 1, py) || !dentro(px - 1, py) || !dentro(px, py + 1) || !dentro(px, py - 1);
          let color;
          if (borde) {
            color = paleta.borde;
          } else {
            const u = (px - inclinar * py) / rx;
            const v = py / ry;
            const luz = -0.55 * u - 0.6 * v + 0.1 + (BAYER[(py + 64) & 3][(px + 64) & 3] / 16 - 0.5) * 0.35;
            color = luz > 0.62 ? paleta.brillo : luz > 0.2 ? paleta.luz : luz > -0.35 ? paleta.medio : paleta.sombra;
          }
          ctx.fillStyle = color;
          ctx.fillRect(cx + px, cy + py, 1, 1);
        }
      }

      this._brote(ctx, ahora, cx + Math.round(inclinar * -ry), cy - ry);
      this._cara(ctx, ahora, cx, cy, rx, ry, inclinar);
    }

    _brote(ctx, ahora, x, y) {
      const p = this.pad.p;
      const alto = 2 + 2 * this.etapa;
      const vaiven = Math.round(Math.sin(ahora / 900));
      ctx.fillStyle = "#3f7a2c";
      for (let i = 1; i <= alto; i++) ctx.fillRect(x + (i > alto / 2 ? vaiven : 0), y - i, 1, 1);
      const punta = { x: x + vaiven, y: y - alto };
      const hojas = {
        arriba: [[1, 0], [2, -1], [3, -1], [3, -2], [2, -2]],
        plana: [[1, 0], [2, 0], [3, 0], [2, -1], [3, -1]],
        caida: [[1, 0], [2, 1], [3, 1], [2, 0], [3, 2]],
      };
      const forma = !this.despierta ? hojas.caida : p > 0.25 ? hojas.arriba : p < -0.2 ? hojas.caida : hojas.plana;
      const grande = this.etapa >= 2;
      for (const lado of [-1, 1]) {
        forma.forEach(([dx, dy], i) => {
          ctx.fillStyle = i < 3 ? "#5f9e3a" : "#86c25a";
          ctx.fillRect(punta.x + lado * dx, punta.y + dy, 1, 1);
          if (grande) ctx.fillRect(punta.x + lado * (dx + 1), punta.y + dy, 1, 1);
        });
      }
    }

    _cara(ctx, ahora, cx, cy, rx, ry, inclinar) {
      const pose = this.pose;
      const { p } = this.pad;
      const etiqueta = this.etiqueta;
      if (ahora > this.proximoParpadeo) {
        this.parpadeoHasta = ahora + 140;
        this.proximoParpadeo = ahora + 2200 + Math.random() * 3500;
      }
      const ojoY = Math.round(cy - ry * 0.18);
      const separacion = Math.max(3, Math.round(rx * 0.4));
      const desvio = Math.round(inclinar * ry * 0.2) + (this.pose.acostada ? 0 : Math.round(this.mirando * 0.6));
      let ojos = pose.ojos;
      if (!ojos) {
        if (!this.despierta) ojos = "cerrados";
        else if (ahora < this.parpadeoHasta) ojos = "cerrados";
        else if (p > 0.45 && (etiqueta === "alegría" || etiqueta === "contento")) ojos = "felices";
        else if (etiqueta === "miedo" || etiqueta === "sorpresa") ojos = "grandes";
        else if (etiqueta === "tristeza") ojos = "tristes";
        else if (etiqueta === "enojo") ojos = "enojados";
        else if (etiqueta === "aburrimiento" || etiqueta === "calma") ojos = "medio";
        else if (etiqueta === "confusión") ojos = "confusos";
        else ojos = "normales";
      }
      const mira = pose.mira || { x: this.mirando * 0.6, y: 0 };
      const pupilaX = Math.round(acotar(mira.x, -1, 1));
      const pupilaY = Math.round(acotar(mira.y, -1, 1) * 0.6);
      for (const lado of [-1, 1]) {
        const ex = cx + desvio + lado * separacion;
        let tipo = ojos;
        if (ojos === "confusos") tipo = lado === 1 ? "medio" : "normales";
        this._ojo(ctx, ex, ojoY, tipo, pupilaX, pupilaY, lado);
      }

      // Mejillas.
      if (this.despierta && p > 0.3) {
        ctx.fillStyle = "#ec8a95";
        for (const lado of [-1, 1]) ctx.fillRect(cx + desvio + lado * (separacion + 2) - (lado < 0 ? 1 : 0), ojoY + 3, 2, 1);
      }

      // Boca.
      const bx = cx + desvio;
      const by = ojoY + 5;
      let boca = pose.boca;
      if (!boca) {
        if (ahora < this.hablaHasta) boca = Math.sin(ahora / 70) > 0 ? "o" : "plana";
        else if (!this.despierta) boca = "plana";
        else if (etiqueta === "miedo") boca = "ondulada";
        else if (etiqueta === "sorpresa") boca = "o";
        else if (p > 0.55) boca = "risa";
        else if (p > 0.15) boca = "sonrisa";
        else if (p < -0.25) boca = "triste";
        else boca = "plana";
      }
      const oscuro = "#3b2a26";
      const pintar = (puntos, color = oscuro) => {
        ctx.fillStyle = color;
        for (const [x, y] of puntos) ctx.fillRect(bx + x, by + y, 1, 1);
      };
      switch (boca) {
        case "sonrisa": pintar([[-2, 0], [-1, 1], [0, 1], [1, 1], [2, 0]]); break;
        case "risa": pintar([[-2, 0], [-1, 0], [0, 0], [1, 0], [2, 0], [-1, 1], [1, 1]]); pintar([[0, 1]], "#c4505f"); break;
        case "triste": pintar([[-2, 1], [-1, 0], [0, 0], [1, 0], [2, 1]]); break;
        case "ondulada": pintar([[-2, 0], [-1, 1], [0, 0], [1, 1], [2, 0]]); break;
        case "o": pintar([[0, 0], [-1, 0], [0, 1], [-1, 1]]); break;
        case "bostezo": pintar([[-1, 0], [0, 0], [1, 0], [-1, 1], [1, 1], [-1, 2], [0, 2], [1, 2]]); pintar([[0, 1]], "#c4505f"); break;
        default: pintar([[-1, 0], [0, 0], [1, 0]]); break;
      }
    }

    _ojo(ctx, x, y, tipo, pupilaX, pupilaY, lado) {
      const oscuro = "#2a1f1c";
      const blanco = "#fffdf6";
      const px = (dx, dy, color) => { ctx.fillStyle = color; ctx.fillRect(x + dx, y + dy, 1, 1); };
      switch (tipo) {
        case "cerrados": px(-1, 0, oscuro); px(0, 1, oscuro); px(1, 0, oscuro); return;
        case "felices": px(-1, 0, oscuro); px(0, -1, oscuro); px(1, 0, oscuro); return;
        case "entrecerrados": for (let i = -1; i <= 1; i++) { px(i, 0, oscuro); px(i, 1, blanco); } return;
        case "medio":
          for (let i = -1; i <= 1; i++) { px(i, -1, oscuro); px(i, 0, blanco); px(i, 1, blanco); }
          px(pupilaX >= 0 ? 0 : -1, 1, oscuro); px(pupilaX >= 0 ? 1 : 0, 1, oscuro);
          return;
        case "grandes":
          for (let i = -2; i <= 1; i++) for (let j = -2; j <= 2; j++) px(i, j, blanco);
          px(pupilaX >= 0 ? 0 : -1, pupilaY, oscuro);
          return;
        default: {
          for (let i = -1; i <= 1; i++) for (let j = -2; j <= 1; j++) px(i, j, blanco);
          const ox = pupilaX > 0 ? 0 : -1;
          const oy = pupilaY > 0 ? 0 : -1;
          for (let i = 0; i <= 1; i++) for (let j = 0; j <= 1; j++) px(ox + i, oy + j, oscuro);
          px(ox, oy, blanco);
          if (tipo === "tristes") { px(lado === 1 ? 1 : -1, -2, oscuro); px(0, -2, oscuro); }
          if (tipo === "enojados") { px(lado === 1 ? -1 : 1, -2, oscuro); px(0, -2, oscuro); px(lado === 1 ? -1 : 1, -3, oscuro); }
        }
      }
    }

    dibujarParticulas(ctx, ahora) {
      for (const p of this.particulas) {
        if (ahora < p.nace) continue;
        const filas = GLIFOS[p.glifo];
        ctx.globalAlpha = Math.max(0, Math.min(1, p.vida * 1.4));
        ctx.fillStyle = p.color;
        filas.forEach((fila, j) => {
          for (let i = 0; i < fila.length; i++) if (fila[i] === "1") ctx.fillRect(Math.round(p.x) + i, Math.round(p.y) + j, 1, 1);
        });
      }
      ctx.globalAlpha = 1;
    }
  }

  window.Criatura = Criatura;
  window.GLIFOS = GLIFOS;
})();
