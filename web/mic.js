/* Escucha continua: el micrófono queda abierto y detecta solo cuándo le hablas.
 * Cada frase (desde que empiezas a hablar hasta un silencio) se envía a 16 kHz.
 * Mientras Muyu habla, o mientras espera su respuesta, deja de escuchar: así no
 * se oye a sí misma. Se desactiva el control automático de ganancia: si el
 * navegador igualara el volumen, no podría distinguir una voz suave de un grito.
 * Los navegadores solo dan el micrófono en HTTPS o en localhost. */

const FRECUENCIA = 16000;
export const SEGUNDOS_MAXIMOS = 15;
const SOBRE_EL_RUIDO_DB = 11;       // tanto por encima del ruido de fondo = alguien habla
const SILENCIO_PARA_CORTAR_S = 0.8; // este silencio cierra la frase
const PREVIO_S = 0.35;              // se guarda un poco de antes, para no cortar el inicio
const MINIMO_S = 0.35;              // más corto que esto es un ruido, no una frase

export class Escucha {
  constructor({ alFrase, alEstado, alNivel } = {}) {
    this.alFrase = alFrase;
    this.alEstado = alEstado;
    this.alNivel = alNivel;
    this.activa = false;
    this._pausaHasta = 0;
    this._pausada = false;
  }

  get disponible() {
    return Boolean(window.isSecureContext && navigator.mediaDevices && navigator.mediaDevices.getUserMedia);
  }

  async iniciar() {
    if (this.activa) return;
    this.flujo = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: false, autoGainControl: false },
    });
    this.contexto = new (window.AudioContext || window.webkitAudioContext)();
    await this.contexto.resume();
    const fuente = this.contexto.createMediaStreamSource(this.flujo);
    this.procesador = this.contexto.createScriptProcessor(2048, 1, 1);
    this.procesador.onaudioprocess = (evento) => this._procesar(evento.inputBuffer.getChannelData(0));
    fuente.connect(this.procesador);
    this.procesador.connect(this.contexto.destination);   // necesario para que procese (la salida es silencio)
    this.ruidoDb = -60;
    this._reiniciar();
    this.activa = true;
    this._estado("escuchando");
  }

  async detener() {
    if (!this.activa) return;
    this.activa = false;
    this.procesador.disconnect();
    this.flujo.getTracks().forEach((pista) => pista.stop());
    await this.contexto.close();
    this._estado("apagada");
  }

  /** Deja de escuchar (mientras Muyu habla o piensa su respuesta). */
  pausar(segundos = 30) {
    this._pausada = true;
    this._pausaHasta = performance.now() + segundos * 1000;
    if (this.activa) {
      this._reiniciar();
      this._estado("pausada");
    }
  }

  /** Vuelve a escuchar después de un pequeño margen (la sala todavía resuena). */
  reanudar(margenSegundos = 0.4) {
    this._pausaHasta = performance.now() + margenSegundos * 1000;
    this._pausada = false;
  }

  _reiniciar() {
    this.previo = [];
    this.frase = null;
    this.silencio = 0;
    this.seguidos = 0;
  }

  _estado(estado) {
    if (this.estado === estado) return;
    this.estado = estado;
    if (this.alEstado) this.alEstado(estado);
  }

  _procesar(datos) {
    if (!this.activa) return;
    const trozo = new Float32Array(datos);
    const segundos = trozo.length / this.contexto.sampleRate;
    let suma = 0;
    for (let i = 0; i < trozo.length; i++) suma += trozo[i] * trozo[i];
    const db = 10 * Math.log10(suma / trozo.length + 1e-12);
    if (this.alNivel) this.alNivel(Math.max(0, Math.min(1, (db + 60) / 45)));

    if (this._pausada || performance.now() < this._pausaHasta) {
      this._estado("pausada");
      return;
    }
    const hablando = db > Math.max(-55, this.ruidoDb + SOBRE_EL_RUIDO_DB);

    if (!this.frase) {
      // Esperando: aprende el ruido de fondo y guarda un poco de audio previo.
      if (!hablando) this.ruidoDb += (db - this.ruidoDb) * (db < this.ruidoDb ? 0.3 : 0.02);
      this.previo.push(trozo);
      while (this.previo.length * segundos > PREVIO_S) this.previo.shift();
      this.seguidos = hablando ? this.seguidos + 1 : 0;
      if (this.seguidos >= 2) {
        this.frase = [...this.previo];
        this.voz = 0;
        this.silencio = 0;
        this._estado("oyendo");
      } else {
        this._estado("escuchando");
      }
      return;
    }

    // Grabando una frase: termina con un silencio o al llegar al máximo.
    this.frase.push(trozo);
    if (hablando) { this.voz += segundos; this.silencio = 0; } else { this.silencio += segundos; }
    const duracion = this.frase.length * segundos;
    if (this.silencio >= SILENCIO_PARA_CORTAR_S || duracion >= SEGUNDOS_MAXIMOS) {
      const frase = this.frase;
      const voz = this.voz;
      this._reiniciar();
      if (voz >= MINIMO_S) {
        this._estado("enviando");
        if (this.alFrase) this.alFrase(this._codificar(frase), duracion);
      } else {
        this._estado("escuchando");
      }
    }
  }

  /** PCM de 16 bits, mono, 16 kHz, en base64. */
  _codificar(trozos) {
    const origen = this.contexto.sampleRate;
    const largo = trozos.reduce((total, trozo) => total + trozo.length, 0);
    const todo = new Float32Array(largo);
    let desde = 0;
    for (const trozo of trozos) { todo.set(trozo, desde); desde += trozo.length; }
    const razon = origen / FRECUENCIA;
    const salida = new Int16Array(Math.floor(largo / razon));
    for (let i = 0; i < salida.length; i++) {
      const inicio = Math.floor(i * razon);
      const fin = Math.min(largo, Math.floor((i + 1) * razon));
      let suma = 0;
      for (let j = inicio; j < fin; j++) suma += todo[j];
      const valor = Math.max(-1, Math.min(1, suma / Math.max(1, fin - inicio)));
      salida[i] = valor < 0 ? valor * 32768 : valor * 32767;
    }
    const bytes = new Uint8Array(salida.buffer);
    let binario = "";
    for (let i = 0; i < bytes.length; i += 0x8000) binario += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    return btoa(binario);
  }
}
