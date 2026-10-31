/* La habitación de Muyu en pixel art (256 × 160 píxeles, escalada sin suavizar).
 * La ventana muestra su hora del día; de noche la lámpara ilumina el cuarto.
 * Los objetos tienen el mismo nombre que usa el servidor para sus actividades. */
(function () {
  "use strict";

  const W = 256;
  const H = 160;
  const PISO = 100;
  // A dónde camina Muyu para cada objeto (sus pies).
  const PUNTOS = {
    cama: { x: 36, y: 121 },
    plato: { x: 102, y: 147 },
    cojin: { x: 128, y: 130 },
    caja: { x: 219, y: 127 },
    ventana: { x: 180, y: 121 },
    planta: { x: 226, y: 122 },
    frente: { x: 128, y: 155 },
  };
  const ZONAS = {     // para tocar objetos
    plato: { x: 86, y: 141, w: 16, h: 8 },
    cama: { x: 6, y: 100, w: 54, h: 30 },
  };

  class Habitacion {
    constructor(lienzo, criatura, { onTocar } = {}) {
      this.lienzo = lienzo;
      lienzo.width = W;
      lienzo.height = H;
      this.ctx = lienzo.getContext("2d");
      this.ctx.imageSmoothingEnabled = false;
      this.criatura = criatura;
      criatura.habitacion = this;
      this.onTocar = onTocar;
      this.alDibujar = null;
      this.hora = 12;
      this.comida = 0;                         // segundos de comida que quedan en el plato
      this.pelota = { x: 158, y: 146, vx: 0, giro: 0 };
      this.sombra = document.createElement("canvas");
      this.sombra.width = W;
      this.sombra.height = H;
      lienzo.addEventListener("click", (e) => this._tocar(e));
      lienzo.addEventListener("pointermove", (e) => {
        lienzo.style.cursor = this._objetoEn(this._coordenadas(e)) ? "pointer" : "default";
      });
      this._ultimo = performance.now();
      requestAnimationFrame((t) => this._cuadro(t));
    }

    punto(objeto, criatura) {
      if (!objeto) return null;
      if (objeto === "pelota") {
        return { x: this.pelota.x + (criatura.x < this.pelota.x ? -10 : 10), y: this.pelota.y };
      }
      return PUNTOS[objeto] || null;
    }

    lanzarPelota() {
      this.pelota.vx = (this.pelota.x > 128 ? -1 : 1) * (70 + Math.random() * 40);
    }

    servirComida() {
      this.comida = 7;
    }

    aPantalla(x, y) {
      const caja = this.lienzo.getBoundingClientRect();
      return { x: (x / W) * caja.width, y: (y / H) * caja.height };
    }

    // ── Bucle ─────────────────────────────────────────────────────────
    _cuadro(ahora) {
      const dt = Math.min(0.05, (ahora - this._ultimo) / 1000);
      this._ultimo = ahora;
      this._fisica(dt);
      this.criatura.actualizar(dt, ahora);
      this._jugarYComer(dt, ahora);
      this._dibujar(ahora);
      if (this.alDibujar) this.alDibujar(this.criatura.cabeza());
      requestAnimationFrame((t) => this._cuadro(t));
    }

    _fisica(dt) {
      const pelota = this.pelota;
      pelota.x += pelota.vx * dt;
      pelota.vx *= Math.pow(0.35, dt);
      if (Math.abs(pelota.vx) < 2) pelota.vx = 0;
      if (pelota.x < 66) { pelota.x = 66; pelota.vx = Math.abs(pelota.vx) * 0.7; }
      if (pelota.x > 196) { pelota.x = 196; pelota.vx = -Math.abs(pelota.vx) * 0.7; }
      pelota.giro += pelota.vx * dt * 0.4;
    }

    _jugarYComer(dt, ahora) {
      const c = this.criatura;
      if (!c.despierta) return;
      const nombre = c.actividad.nombre;
      if (nombre === "jugar" && Math.abs(c.x - this.pelota.x) < 12 && Math.abs(c.y - this.pelota.y) < 6
          && Math.abs(this.pelota.vx) < 12) {
        this.pelota.vx = Math.sign(this.pelota.x - c.x || 1) * (55 + Math.random() * 45);
        c.particula("nota", "#e0a32e", ahora);
      }
      if (nombre === "comer" && Math.hypot(c.x - PUNTOS.plato.x, c.y - PUNTOS.plato.y) < 4) {
        this.comida = Math.max(0, this.comida - dt);
      }
    }

    // ── Dibujo ────────────────────────────────────────────────────────
    _dibujar(ahora) {
      const ctx = this.ctx;
      this._pared(ctx, ahora);
      this._piso(ctx);
      const c = this.criatura;
      const enCama = !c.despierta && Math.hypot(c.x - PUNTOS.cama.x, c.y - PUNTOS.cama.y) < 6;
      const capas = [
        { y: 128, dibujar: () => this._cama(ctx) },
        { y: 120, dibujar: () => this._planta(ctx) },
        { y: 132, dibujar: () => this._cojin(ctx) },
        { y: 138, dibujar: () => this._caja(ctx) },
        { y: 149, dibujar: () => this._plato(ctx) },
        { y: this.pelota.y + 3, dibujar: () => this._pelota(ctx) },
        { y: enCama ? 129 : c.y, dibujar: () => c.dibujar(ctx, ahora) },
      ].sort((a, b) => a.y - b.y);
      for (const capa of capas) capa.dibujar();
      if (enCama) this._manta(ctx, 22);
      this._luz(ctx, ahora);
      c.dibujarParticulas(ctx, ahora);
    }

    _rect(ctx, x, y, w, h, color) {
      ctx.fillStyle = color;
      ctx.fillRect(Math.round(x), Math.round(y), w, h);
    }

    _pared(ctx, ahora) {
      this._rect(ctx, 0, 0, W, PISO, "#f1dfbf");
      for (let x = 0; x < W; x += 8) this._rect(ctx, x, 0, 1, PISO, "#ead3ad");     // papel tapiz
      for (let x = 4; x < W; x += 16) for (let y = 10; y < PISO - 6; y += 16) this._rect(ctx, x, y, 1, 1, "#e2c697");
      this._rect(ctx, 0, PISO - 3, W, 3, "#c9a77a");                                  // zócalo
      this._rect(ctx, 0, PISO - 3, W, 1, "#dcbf93");
      this._ventana(ctx, ahora);
      // Cuadro con un sol dibujado.
      this._rect(ctx, 86, 26, 22, 18, "#8b6a47");
      this._rect(ctx, 88, 28, 18, 14, "#fbf3df");
      this._rect(ctx, 95, 32, 4, 4, "#f2b632");
      for (const [dx, dy] of [[-2, 1], [5, 1], [1, -2], [1, 5]]) this._rect(ctx, 95 + dx, 32 + dy, 2, 2, "#f6cf6a");
      this._rect(ctx, 89, 39, 16, 2, "#9ccf7a");
      // Lámpara de pared sobre la cama.
      this._rect(ctx, 38, 36, 1, 8, "#8b6a47");
      this._rect(ctx, 33, 30, 11, 6, "#e8c170");
      this._rect(ctx, 34, 31, 9, 1, "#f4dc9f");
      this._rect(ctx, 36, 36, 5, 2, this._esNoche() ? "#fff4c2" : "#d9cfa8");
    }

    _cielo() {
      const h = this.hora;
      if (h < 5 || h >= 21) return ["#1b2350", "#2c3a6e", "noche"];
      if (h < 7) return ["#f2a07b", "#f7d29a", "amanecer"];
      if (h < 17.5) return ["#7ec4ef", "#c4e8fb", "dia"];
      if (h < 19.5) return ["#f08a5d", "#f6c177", "atardecer"];
      return ["#5b4b8a", "#c47ba2", "anochecer"];
    }

    _esNoche() {
      return this.hora >= 20.5 || this.hora < 6;
    }

    _ventana(ctx, ahora) {
      const x0 = 156, y0 = 16, w = 48, h = 44;
      const [arriba, abajo, momento] = this._cielo();
      this._rect(ctx, x0 - 2, y0 - 2, w + 4, h + 4, "#8b6a47");
      for (let y = 0; y < h; y++) {
        const mezcla = y / h + (((y * 7) % 3) - 1) * 0.04;
        this._rect(ctx, x0, y0 + y, w, 1, mezcla < 0.5 ? arriba : abajo);
      }
      if (momento === "noche" || momento === "anochecer") {
        for (let i = 0; i < 12; i++) {
          const brillo = Math.sin(ahora / 500 + i * 2.1) > -0.3;
          if (brillo) this._rect(ctx, x0 + 2 + ((i * 17) % (w - 4)), y0 + 2 + ((i * 11) % (h - 12)), 1, 1, "#fff7d6");
        }
        this._rect(ctx, x0 + 32, y0 + 6, 7, 7, "#f4ecc9");
        this._rect(ctx, x0 + 34, y0 + 5, 7, 7, arriba);                    // luna menguante
      } else {
        const avance = Math.max(0, Math.min(1, (this.hora - 6) / 13));
        const sx = x0 + 4 + avance * (w - 12);
        const sy = y0 + 4 + Math.abs(avance - 0.5) * 2 * (h - 18);
        this._rect(ctx, sx, sy, 6, 6, momento === "dia" ? "#ffe066" : "#ffb347");
        if (momento === "dia") {
          const nube = ((ahora / 900) % (w + 20)) - 14;
          for (const [dx, dy, ancho] of [[0, 0, 10], [3, -2, 5], [16, 14, 8], [18, 12, 4]]) {
            const nx = x0 + ((nube + dx + w) % (w + 10)) - 4;
            if (nx > x0 && nx + ancho < x0 + w) this._rect(ctx, nx, y0 + 14 + dy, ancho, 2, "#ffffff");
          }
        }
      }
      this._rect(ctx, x0 + w / 2 - 1, y0, 2, h, "#8b6a47");                 // cruz del marco
      this._rect(ctx, x0, y0 + h / 2 - 1, w, 2, "#8b6a47");
      this._rect(ctx, x0 - 4, y0 + h + 2, w + 8, 3, "#a37d55");             // alféizar
    }

    _piso(ctx) {
      this._rect(ctx, 0, PISO, W, H - PISO, "#d9b382");
      for (let y = PISO + 6; y < H; y += 8) this._rect(ctx, 0, y, W, 1, "#c49a68");
      for (let fila = 0; fila * 8 + PISO < H; fila++) {
        for (let x = (fila % 2) * 24; x < W; x += 48) this._rect(ctx, x, PISO + fila * 8, 1, 7, "#c9a273");
      }
      // Alfombra bajo el cojín.
      for (let y = -7; y <= 7; y++) {
        const ancho = Math.round(34 * Math.sqrt(1 - (y / 8) ** 2));
        this._rect(ctx, 128 - ancho, 133 + y, ancho * 2, 1, Math.abs(y) > 5 ? "#c58f6b" : (y % 2 ? "#e2c3a1" : "#dcb995"));
      }
    }

    _cama(ctx) {
      this._rect(ctx, 6, 100, 5, 28, "#8f5f33");          // cabecera
      this._rect(ctx, 6, 100, 5, 2, "#a8743f");
      this._rect(ctx, 10, 113, 50, 11, "#f4efe6");        // colchón
      this._rect(ctx, 10, 122, 50, 2, "#ddd5c6");
      this._rect(ctx, 12, 109, 14, 6, "#ffffff");         // almohada
      this._rect(ctx, 12, 114, 14, 1, "#e6e0d6");
      this._rect(ctx, 8, 124, 54, 4, "#a8743f");          // marco y patas
      this._rect(ctx, 9, 128, 3, 2, "#8f5f33");
      this._rect(ctx, 57, 128, 3, 2, "#8f5f33");
      if (this.criatura.despierta) this._manta(ctx, 44);  // doblada a los pies
    }

    _manta(ctx, desde) {
      this._rect(ctx, desde, 112, 60 - desde, 12, "#7aa6d6");
      this._rect(ctx, desde, 112, 60 - desde, 2, "#9cc0e6");
      for (let x = desde + 3; x < 58; x += 6) this._rect(ctx, x, 115, 2, 8, "#6893c4");
    }

    _planta(ctx) {
      for (const [x, y, w, h, color] of [
        [232, 86, 3, 22, "#4f8f37"], [238, 80, 3, 28, "#5ea343"], [244, 88, 3, 20, "#4f8f37"],
        [229, 90, 5, 3, "#6fb54d"], [240, 82, 6, 3, "#6fb54d"], [245, 92, 5, 3, "#6fb54d"], [234, 96, 5, 3, "#5ea343"],
      ]) this._rect(ctx, x, y, w, h, color);
      this._rect(ctx, 230, 108, 20, 12, "#b5653a");       // maceta
      this._rect(ctx, 229, 106, 22, 3, "#c8774a");
      this._rect(ctx, 232, 116, 16, 1, "#9a522d");
    }

    _cojin(ctx) {
      this._rect(ctx, 114, 125, 28, 7, "#c97c9a");
      this._rect(ctx, 115, 124, 26, 2, "#e09ab4");
      this._rect(ctx, 127, 127, 2, 2, "#a85f7c");
    }

    _caja(ctx) {
      this._rect(ctx, 204, 117, 30, 21, "#c89b5e");
      this._rect(ctx, 204, 117, 30, 3, "#b2854a");
      this._rect(ctx, 201, 114, 10, 4, "#d7ad72");        // solapas abiertas
      this._rect(ctx, 227, 114, 10, 4, "#d7ad72");
      this._rect(ctx, 217, 120, 4, 18, "#e2c08a");        // cinta
      this._rect(ctx, 204, 136, 30, 2, "#a8763f");
    }

    _plato(ctx) {
      this._rect(ctx, 87, 144, 14, 4, "#d4574b");
      this._rect(ctx, 86, 143, 16, 2, "#e67b6f");
      this._rect(ctx, 89, 148, 10, 1, "#a8423a");
      if (this.comida > 0) {
        const cantidad = Math.ceil((this.comida / 7) * 5);
        for (let i = 0; i < cantidad; i++) this._rect(ctx, 89 + i * 2, 142 - (i % 2), 2, 2, i % 2 ? "#9b6a3c" : "#c08a4f");
      }
    }

    _pelota(ctx) {
      const { x, y, giro } = this.pelota;
      const bx = Math.round(x) - 4, by = Math.round(y) - 7;
      this._rect(ctx, bx + 1, by + 8, 7, 1, "rgba(70,45,20,0.25)");
      const filas = ["0011100", "0111110", "1111111", "1111111", "1111111", "0111110", "0011100"];
      const franja = Math.round(giro) % 7;
      filas.forEach((fila, j) => {
        for (let i = 0; i < 7; i++) {
          if (fila[i] !== "1") continue;
          const blanco = (i + franja + 7) % 7 === 3 || j === 3;
          this._rect(ctx, bx + i, by + j, 1, 1, blanco ? "#fff4f0" : "#e04e4e");
        }
      });
      this._rect(ctx, bx + 2, by + 1, 1, 1, "#ffffff");
    }

    _luz(ctx, ahora) {
      const [, , momento] = this._cielo();
      const oscuridad = { noche: 0.5, anochecer: 0.25, amanecer: 0.18, atardecer: 0.08, dia: 0 }[momento];
      if (!oscuridad) return;
      const sombra = this.sombra.getContext("2d");
      sombra.clearRect(0, 0, W, H);
      sombra.globalCompositeOperation = "source-over";
      sombra.fillStyle = `rgba(16, 20, 58, ${oscuridad})`;
      sombra.fillRect(0, 0, W, H);
      sombra.globalCompositeOperation = "destination-out";
      const luces = [[38, 40, 58, 1]];
      if (momento === "noche") luces.push([180, 70, 34, 0.5]);
      for (const [x, y, radio, fuerza] of luces) {
        const gradiente = sombra.createRadialGradient(x, y, 2, x, y, radio);
        gradiente.addColorStop(0, `rgba(0,0,0,${0.9 * fuerza})`);
        gradiente.addColorStop(1, "rgba(0,0,0,0)");
        sombra.fillStyle = gradiente;
        sombra.fillRect(0, 0, W, H);
      }
      ctx.drawImage(this.sombra, 0, 0);
      if (momento === "noche") {
        ctx.fillStyle = "rgba(255, 220, 140, 0.08)";
        ctx.fillRect(10, 30, 60, 100);
      }
    }

    // ── Tocar ─────────────────────────────────────────────────────────
    _coordenadas(evento) {
      const caja = this.lienzo.getBoundingClientRect();
      return { x: ((evento.clientX - caja.left) / caja.width) * W, y: ((evento.clientY - caja.top) / caja.height) * H };
    }

    _objetoEn({ x, y }) {
      if (this.criatura.contiene(x, y)) return "criatura";
      if (Math.hypot(x - this.pelota.x, y - (this.pelota.y - 4)) < 7) return "pelota";
      for (const [nombre, z] of Object.entries(ZONAS)) {
        if (x >= z.x && x <= z.x + z.w && y >= z.y && y <= z.y + z.h) return nombre;
      }
      return null;
    }

    _tocar(evento) {
      const objeto = this._objetoEn(this._coordenadas(evento));
      if (objeto && this.onTocar) this.onTocar(objeto);
    }
  }

  window.Habitacion = Habitacion;
})();
