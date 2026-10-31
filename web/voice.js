/* Voz de criatura (Web Audio API): canturrea lo que dice, sílaba por sílaba.
 * No pronuncia palabras: el tono, el ritmo y el volumen salen de su emoción, así
 * su voz dice lo mismo que su cuerpo. Cada criatura nace con su propio timbre.
 * Los navegadores solo permiten sonar después de que tocas la página. */
(function () {
  "use strict";

  // Formantes aproximados de cada vocal (Hz): le dan color de "a", "e", "i", "o", "u".
  const FORMANTES = { a: [800, 1250], e: [480, 1900], i: [320, 2500], o: [520, 950], u: [360, 720] };
  const SORDAS = "ptkcqfsjxzh";
  const NASALES = "mnñl";

  function silabear(texto) {
    const limpio = texto.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/ñ/g, "n");
    const unidades = [];
    for (const trozo of limpio.split(/(\s+|…|\.\.\.|[,.!?¿¡-])/)) {
      if (!trozo || /^\s+$/.test(trozo)) { unidades.push({ pausa: 0.05 }); continue; }
      if (trozo === "…" || trozo === "...") { unidades.push({ pausa: 0.22 }); continue; }
      if (/^[,.]$/.test(trozo)) { unidades.push({ pausa: 0.12 }); continue; }
      if (trozo === "-") { unidades.push({ pausa: 0.03 }); continue; }
      if (/^[!?¿¡]$/.test(trozo)) continue;
      const silabas = trozo.match(/[^aeiou]*[aeiou]+/g);
      if (!silabas) { unidades.push({ zumbido: trozo }); continue; }
      const resto = trozo.slice(silabas.join("").length);
      silabas.forEach((silaba, i) => {
        const vocales = silaba.match(/[aeiou]+/)[0];
        const consonante = silaba.slice(0, silaba.length - vocales.length);
        unidades.push({ consonante, vocal: vocales[0], largo: Math.min(3, vocales.length), final: i === silabas.length - 1 && !resto });
      });
      if (resto) unidades.push({ zumbido: resto });
    }
    return unidades;
  }

  class Voz {
    constructor() {
      this.ctx = null;
      this.activa = localStorage.getItem("muyu.voz") !== "no";
      this.tono = 400;
      this.brillo = 0.6;
      this.ritmo = 1;
    }

    configurar({ tono, brillo, ritmo } = {}) {
      if (tono) this.tono = tono;
      if (brillo !== undefined) this.brillo = brillo;
      if (ritmo) this.ritmo = ritmo;
    }

    desbloquear() {
      if (!this.activa) return;
      if (!this.ctx) {
        const Contexto = window.AudioContext || window.webkitAudioContext;
        if (!Contexto) return;
        this.ctx = new Contexto();
        const compresor = this.ctx.createDynamicsCompressor();
        this.salida = this.ctx.createGain();
        this.salida.gain.value = 0.55;
        this.salida.connect(compresor);
        compresor.connect(this.ctx.destination);
        const largo = this.ctx.sampleRate * 0.5;
        this.ruido = this.ctx.createBuffer(1, largo, this.ctx.sampleRate);
        const datos = this.ruido.getChannelData(0);
        for (let i = 0; i < largo; i++) datos[i] = Math.random() * 2 - 1;
      }
      if (this.ctx.state === "suspended") this.ctx.resume();
    }

    alternar() {
      this.activa = !this.activa;
      localStorage.setItem("muyu.voz", this.activa ? "si" : "no");
      if (this.activa) this.desbloquear();
      else if (this.ctx) this.ctx.suspend();
      return this.activa;
    }

    _listo() {
      return this.activa && this.ctx && this.ctx.state === "running";
    }

    /** Canturrea un texto con la emoción del instante en que lo dijo. */
    decir(texto, emocion = {}, pregunta = false) {
      if (!this._listo() || !texto) return 0;
      const p = emocion.p || 0, a = emocion.a || 0, d = emocion.d || 0;
      const etiqueta = emocion.etiqueta || "neutral";
      const miedo = etiqueta === "miedo" || (p < -0.3 && a > 0.35 && d < -0.15);
      const triste = p < -0.25 && a < 0.1;
      const base = this.tono * (1 + 0.28 * p + 0.18 * a) * (etiqueta === "enojo" ? 0.85 : 1);
      const duracion = Math.max(0.07, (0.13 - 0.035 * a) / this.ritmo) * (triste ? 1.3 : 1);
      const volumen = triste ? 0.16 : 0.22 + 0.12 * Math.max(0, a);
      const unidades = silabear(texto);
      const silabas = unidades.filter((u) => u.vocal);
      let t = this.ctx.currentTime + 0.03;
      let indice = 0;
      for (const unidad of unidades) {
        if (unidad.pausa) { t += unidad.pausa; continue; }
        if (unidad.zumbido) { t += this._zumbido(t, unidad.zumbido, base, volumen); continue; }
        indice += 1;
        const ultima = indice === silabas.length;
        let f0 = base * (1 + (Math.random() - 0.5) * 0.06);
        if (p > 0.3) f0 *= indice % 2 ? 1.07 : 0.95;           // alegría: saltarina
        if (triste) f0 *= 1 - 0.035 * indice;                  // tristeza: va cayendo
        let f1 = f0;
        if (ultima) f1 = f0 * (pregunta ? 1.38 : triste ? 0.82 : 0.9);
        const largo = duracion * (1 + 0.6 * (unidad.largo - 1)) * (ultima ? 1.35 : 1);
        this._silaba(t, largo, f0, f1, unidad, volumen, miedo);
        t += largo + 0.02;
      }
      return t - this.ctx.currentTime;
    }

    _silaba(t, largo, f0, f1, { consonante, vocal }, volumen, miedo) {
      const ctx = this.ctx;
      const primera = consonante ? consonante[consonante.length - 1] : "";
      let inicio = t;
      if (primera && SORDAS.includes(primera)) {
        this._soplo(t, 0.025, 2500 + 1500 * this.brillo, volumen * 0.5);
        inicio += 0.02;
      }
      const envolvente = ctx.createGain();
      envolvente.gain.setValueAtTime(0, inicio);
      envolvente.gain.linearRampToValueAtTime(volumen, inicio + 0.015);
      envolvente.gain.setValueAtTime(volumen * 0.85, inicio + largo * 0.6);
      envolvente.gain.linearRampToValueAtTime(0, inicio + largo);
      envolvente.connect(this.salida);

      const tonal = ctx.createOscillator();
      tonal.type = "triangle";
      const sierra = ctx.createOscillator();
      sierra.type = "sawtooth";
      for (const osc of [tonal, sierra]) {
        osc.frequency.setValueAtTime(NASALES.includes(primera) ? f0 * 0.92 : f0, inicio);
        osc.frequency.linearRampToValueAtTime(f1, inicio + largo);
      }
      if (miedo) {
        const temblor = ctx.createOscillator();
        const profundidad = ctx.createGain();
        temblor.frequency.value = 9;
        profundidad.gain.value = f0 * 0.04;
        temblor.connect(profundidad);
        profundidad.connect(tonal.frequency);
        profundidad.connect(sierra.frequency);
        temblor.start(inicio);
        temblor.stop(inicio + largo);
      }
      const [formante1, formante2] = FORMANTES[vocal] || FORMANTES.a;
      const mezclaTonal = ctx.createGain();
      mezclaTonal.gain.value = 0.7;
      tonal.connect(mezclaTonal);
      mezclaTonal.connect(envolvente);
      for (const [frecuencia, q, peso] of [[formante1, 6, 0.9], [formante2 * (0.8 + 0.4 * this.brillo), 9, 0.6]]) {
        const filtro = ctx.createBiquadFilter();
        filtro.type = "bandpass";
        filtro.frequency.value = frecuencia;
        filtro.Q.value = q;
        const ganancia = ctx.createGain();
        ganancia.gain.value = peso;
        sierra.connect(filtro);
        filtro.connect(ganancia);
        ganancia.connect(envolvente);
      }
      tonal.start(inicio);
      sierra.start(inicio);
      tonal.stop(inicio + largo + 0.02);
      sierra.stop(inicio + largo + 0.02);
    }

    _soplo(t, largo, frecuencia, volumen) {
      const ctx = this.ctx;
      const fuente = ctx.createBufferSource();
      fuente.buffer = this.ruido;
      const filtro = ctx.createBiquadFilter();
      filtro.type = "bandpass";
      filtro.frequency.value = frecuencia;
      filtro.Q.value = 1.5;
      const ganancia = ctx.createGain();
      ganancia.gain.setValueAtTime(volumen, t);
      ganancia.gain.exponentialRampToValueAtTime(0.001, t + largo);
      fuente.connect(filtro);
      filtro.connect(ganancia);
      ganancia.connect(this.salida);
      fuente.start(t);
      fuente.stop(t + largo + 0.01);
    }

    _zumbido(t, letras, base, volumen) {
      // "mm", "nn": tarareo; "zz": ronquido; "fff", "hh": soplido.
      const largo = Math.min(0.5, 0.12 * letras.length);
      if (/[zs]/.test(letras)) {
        this._soplo(t, largo, 300, volumen * 0.6);
      } else if (/[fh]/.test(letras)) {
        this._soplo(t, largo, 1800, volumen * 0.4);
      } else {
        const osc = this.ctx.createOscillator();
        const filtro = this.ctx.createBiquadFilter();
        const ganancia = this.ctx.createGain();
        osc.type = "triangle";
        osc.frequency.setValueAtTime(base * 0.8, t);
        osc.frequency.linearRampToValueAtTime(base * 0.75, t + largo);
        filtro.type = "lowpass";
        filtro.frequency.value = 500;
        ganancia.gain.setValueAtTime(0, t);
        ganancia.gain.linearRampToValueAtTime(volumen * 0.8, t + 0.03);
        ganancia.gain.linearRampToValueAtTime(0, t + largo);
        osc.connect(filtro);
        filtro.connect(ganancia);
        ganancia.connect(this.salida);
        osc.start(t);
        osc.stop(t + largo + 0.02);
      }
      return largo + 0.03;
    }

    /** Sonidos sin palabras que acompañan a algunos gestos. */
    sonido(nombre) {
      if (!this._listo()) return;
      const t = this.ctx.currentTime + 0.02;
      if (nombre === "risa") {
        for (let i = 0; i < 4; i++) {
          const f = this.tono * (1.3 + 0.12 * i);
          this._silaba(t + i * 0.09, 0.07, f, f * 1.1, { consonante: "h", vocal: "i" }, 0.18, false);
        }
      } else if (nombre === "nam") {
        for (let i = 0; i < 2; i++) {
          const f = this.tono * 0.75;
          this._silaba(t + i * 0.16, 0.1, f, f * 0.9, { consonante: "n", vocal: "a" }, 0.16, false);
        }
      } else if (nombre === "sorpresa") {
        this._silaba(t, 0.18, this.tono, this.tono * 1.6, { consonante: "", vocal: "o" }, 0.24, false);
      }
    }
  }

  window.Voz = Voz;
  window.silabear = silabear;
})();
