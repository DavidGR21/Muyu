/* Muyu en 3D: una semilla con un brote que crece con su lenguaje.
 * Su forma (postura), sus ojos, su boca, su color y su velocidad salen de su
 * emoción (PAD); lo que hace su cuerpo sale de la actividad que eligió el servidor. */
import * as THREE from "three";

const mezclar = (a, b, t) => a + (b - a) * t;
const acotar = (v, min, max) => Math.max(min, Math.min(max, v));
const ALTO = 0.95;                    // altura del cuerpo (unidades de la habitación)

// Perfil de la semilla: base plana, panza ancha y punta arriba.
function perfilSemilla() {
  const puntos = [];
  for (let i = 0; i <= 24; i++) {
    const v = i / 24;                                      // 0 abajo, 1 arriba
    let radio = 0.42 * Math.sin(Math.PI * Math.pow(v, 0.78)) * (1.05 - 0.35 * v);
    if (v < 0.08) radio = Math.max(radio, 0.3 * (v / 0.08));
    puntos.push(new THREE.Vector2(Math.max(0.001, radio), v * ALTO));
  }
  return puntos;
}

// Texturas para partículas, dibujadas a mano (sin emoticonos).
function texturaParticula(tipo, color) {
  const lienzo = document.createElement("canvas");
  lienzo.width = lienzo.height = 64;
  const ctx = lienzo.getContext("2d");
  ctx.fillStyle = color;
  ctx.strokeStyle = color;
  ctx.lineWidth = 7;
  ctx.lineCap = "round";
  ctx.font = "bold 50px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  if (tipo === "corazon") {
    ctx.beginPath();
    ctx.moveTo(32, 52);
    ctx.bezierCurveTo(2, 30, 14, 6, 32, 22);
    ctx.bezierCurveTo(50, 6, 62, 30, 32, 52);
    ctx.fill();
  } else if (tipo === "estrella") {
    ctx.beginPath();
    for (let i = 0; i < 10; i++) {
      const r = i % 2 ? 11 : 26;
      const a = (i / 10) * Math.PI * 2 - Math.PI / 2;
      ctx.lineTo(32 + Math.cos(a) * r, 32 + Math.sin(a) * r);
    }
    ctx.fill();
  } else if (tipo === "nota") {
    ctx.beginPath();
    ctx.ellipse(24, 46, 10, 8, -0.4, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillRect(31, 12, 5, 36);
    ctx.fillRect(31, 12, 18, 6);
  } else if (tipo === "puntos") {
    for (const x of [14, 32, 50]) { ctx.beginPath(); ctx.arc(x, 34, 5, 0, Math.PI * 2); ctx.fill(); }
  } else if (tipo === "nube") {
    for (const [x, y, r] of [[22, 38, 13], [36, 30, 16], [48, 40, 11]]) { ctx.beginPath(); ctx.arc(x, y, r, 0, Math.PI * 2); ctx.fill(); }
  } else if (tipo === "miga") {
    ctx.beginPath(); ctx.arc(32, 32, 9, 0, Math.PI * 2); ctx.fill();
  } else {
    ctx.fillText({ pregunta: "?", exclamacion: "!", z: "z", enojo: "#" }[tipo] || "?", 32, 36);
  }
  const textura = new THREE.CanvasTexture(lienzo);
  textura.colorSpace = THREE.SRGBColorSpace;
  return textura;
}

const PARTICULAS_DE_GESTO = {
  carino: ["corazon", "#e2607a", 4], alegria: ["estrella", "#e0a32e", 3], saludo: ["estrella", "#e0a32e", 2],
  confusion: ["pregunta", "#7a5fc0", 1], duda: ["pregunta", "#7a5fc0", 1], curiosidad: ["pregunta", "#7a5fc0", 1],
  reconocer: ["puntos", "#7a5fc0", 1], sonar: ["nube", "#9a8fc4", 2], enojo: ["enojo", "#c8553d", 1],
  miedo: ["exclamacion", "#c8553d", 1], sobresalto: ["exclamacion", "#c8553d", 1], pedir: ["exclamacion", "#e0a32e", 1],
  tristeza: ["puntos", "#7d86b8", 1], dormir: ["z", "#7d86b8", 1],
};

export class Criatura {
  constructor() {
    this.grupo = new THREE.Group();
    this.grupo.userData.objeto = "criatura";
    this.x = 0;
    this.z = 0.6;
    this.rumbo = 0;                     // hacia dónde mira (radianes, 0 = hacia la cámara)
    this.pad = { p: 0, a: 0, d: 0 };
    this.objetivoPad = { p: 0, a: 0, d: 0 };
    this.etiqueta = "neutral";
    this.ambivalencia = 0;
    this.despierta = true;
    this.etapa = 0;
    this.tono = 150;
    this.actividad = { nombre: "quieta", objeto: null, ambivalente: false };
    this.inicioActividad = 0;
    this.gestoActual = null;
    this.hablaHasta = 0;
    this.parpadeoHasta = 0;
    this.proximoParpadeo = 2500;
    this.paso = 0;
    this.ubicada = false;
    this.habitacion = null;
    this.particulas = [];
    this._texturas = {};
    this._construir();
  }

  _construir() {
    // Cuerpo (postura): un grupo que se estira, aplasta e inclina.
    this.cuerpo = new THREE.Group();
    this.grupo.add(this.cuerpo);
    this.material = new THREE.MeshStandardMaterial({ color: 0x6bc4a6, roughness: 0.55, metalness: 0.0 });
    const semilla = new THREE.Mesh(new THREE.LatheGeometry(perfilSemilla(), 48), this.material);
    semilla.castShadow = true;
    semilla.receiveShadow = true;
    semilla.userData.objeto = "criatura";
    this.cuerpo.add(semilla);

    // Cara.
    this.cara = new THREE.Group();
    this.cara.position.set(0, 0.5, 0);
    this.cuerpo.add(this.cara);
    const blanco = new THREE.MeshStandardMaterial({ color: 0xfffdf6, roughness: 0.3 });
    const negro = new THREE.MeshStandardMaterial({ color: 0x241a17, roughness: 0.25 });
    this.parpado = new THREE.MeshStandardMaterial({ color: 0x6bc4a6, roughness: 0.55 });
    this.ojos = [-1, 1].map((lado) => {
      const ojo = new THREE.Group();
      ojo.position.set(lado * 0.13, 0.06, 0.33);
      const globo = new THREE.Mesh(new THREE.SphereGeometry(0.075, 20, 16), blanco);
      globo.scale.set(1, 1.2, 0.55);
      const pupila = new THREE.Mesh(new THREE.SphereGeometry(0.042, 16, 12), negro);
      pupila.position.z = 0.035;
      pupila.scale.set(1, 1.15, 0.6);
      const brillo = new THREE.Mesh(new THREE.SphereGeometry(0.013, 8, 6), blanco);
      brillo.position.set(-0.014, 0.02, 0.022);
      pupila.add(brillo);
      // Párpado: media esfera del color del cuerpo que baja para cerrar el ojo.
      const parpado = new THREE.Mesh(new THREE.SphereGeometry(0.082, 20, 12, 0, Math.PI * 2, 0, Math.PI / 2), this.parpado);
      parpado.scale.set(1.05, 1.25, 0.65);
      ojo.add(globo, pupila, parpado);
      this.cara.add(ojo);
      return { ojo, globo, pupila, parpado, lado };
    });
    this.mejillas = [-1, 1].map((lado) => {
      const mejilla = new THREE.Mesh(new THREE.CircleGeometry(0.04, 16),
        new THREE.MeshBasicMaterial({ color: 0xf0909c, transparent: true, opacity: 0 }));
      mejilla.position.set(lado * 0.22, -0.05, 0.34);
      mejilla.rotation.y = lado * 0.45;
      this.cara.add(mejilla);
      return mejilla;
    });
    this.materialBoca = new THREE.MeshStandardMaterial({ color: 0x3b2a26, roughness: 0.5 });
    this.boca = new THREE.Mesh(new THREE.BufferGeometry(), this.materialBoca);
    this.cara.add(this.boca);
    this._formaBoca = null;

    // Brote.
    this.brote = new THREE.Group();
    this.brote.position.y = ALTO - 0.02;
    this.cuerpo.add(this.brote);
    const verde = new THREE.MeshStandardMaterial({ color: 0x4f8f37, roughness: 0.6 });
    this.tallo = new THREE.Mesh(new THREE.CylinderGeometry(0.018, 0.024, 1, 8), verde);
    this.tallo.castShadow = true;
    this.brote.add(this.tallo);
    const hojaGeo = new THREE.SphereGeometry(0.09, 16, 8);
    const hojaMat = new THREE.MeshStandardMaterial({ color: 0x6fb54d, roughness: 0.5, side: THREE.DoubleSide });
    this.hojas = [-1, 1].map((lado) => {
      const pivote = new THREE.Group();
      const hoja = new THREE.Mesh(hojaGeo, hojaMat);
      hoja.scale.set(1.3, 0.22, 0.7);
      hoja.position.x = lado * 0.1;
      hoja.castShadow = true;
      pivote.add(hoja);
      this.brote.add(pivote);
      return { pivote, lado };
    });

    // Sombra de contacto suave (además de la sombra real).
    const sombra = new THREE.Mesh(new THREE.CircleGeometry(0.42, 32),
      new THREE.MeshBasicMaterial({ color: 0x3a2814, transparent: true, opacity: 0.18, depthWrite: false }));
    sombra.rotation.x = -Math.PI / 2;
    sombra.position.y = 0.005;
    this.grupo.add(sombra);
  }

  // ── Entradas desde el servidor ──────────────────────────────────────
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
      const destino = this.habitacion.punto(actividad.nombre === "dormir" ? "cama" : actividad.objeto, this);
      if (destino) { this.x = destino.x; this.z = destino.z; }
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

  particula(tipo, color, desde) {
    const clave = `${tipo}|${color}`;
    if (!this._texturas[clave]) this._texturas[clave] = texturaParticula(tipo, color);
    const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: this._texturas[clave], transparent: true, depthWrite: false }));
    sprite.scale.setScalar(0.18);
    sprite.visible = false;
    const cabeza = this.cabeza();
    sprite.position.set(cabeza.x + (Math.random() - 0.5) * 0.4, cabeza.y, cabeza.z + (Math.random() - 0.5) * 0.2);
    this.habitacion.escena.add(sprite);
    this.particulas.push({ sprite, nace: desde, vida: 1, vx: (Math.random() - 0.5) * 0.2, vy: 0.45 + Math.random() * 0.25 });
  }

  /** Punto sobre la cabeza (coordenadas del mundo) para la burbuja de habla. */
  cabeza() {
    const punto = new THREE.Vector3(0, ALTO + 0.25 + 0.06 * this.etapa, 0);
    this.cuerpo.localToWorld(punto);
    return punto;
  }

  // ── Movimiento y pose ───────────────────────────────────────────────
  actualizar(dt, ahora, camara) {
    for (const eje of ["p", "a", "d"]) this.pad[eje] = mezclar(this.pad[eje], this.objetivoPad[eje], Math.min(1, dt * 2.5));
    const { p, a } = this.pad;
    const nombre = this.despierta ? this.actividad.nombre : "dormir";
    const enActividad = (ahora - this.inicioActividad) / 1000;
    let destino = this.habitacion.punto(this.despierta ? this.actividad.objeto : "cama", this);

    // Ambivalencia: se acerca y retrocede (curiosidad y miedo a la vez).
    if (this.despierta && destino && (this.actividad.ambivalente || this.ambivalencia > 0.3)) {
      if (Math.sin(enActividad * 2.4) > 0.2) destino = { x: destino.x * 0.6, z: destino.z - 0.9 };
    }

    let velocidad = 0.9 * (0.7 + 0.8 * Math.max(0, a));
    if (p < -0.3 && a < 0) velocidad *= 0.6;
    if (nombre === "ir_a_dormir" || nombre === "dormir") velocidad *= 0.7;
    if (nombre === "pedir_comida" || nombre === "buscarte") velocidad *= 1.2;

    let caminando = false;
    let rumboObjetivo = this.rumbo;
    if (destino) {
      const dx = destino.x - this.x;
      const dz = destino.z - this.z;
      const distancia = Math.hypot(dx, dz);
      if (distancia > 0.05) {
        const avance = Math.min(distancia, velocidad * dt);
        this.x += (dx / distancia) * avance;
        this.z += (dz / distancia) * avance;
        rumboObjetivo = Math.atan2(dx, dz);
        caminando = true;
      }
    }
    if (!caminando) rumboObjetivo = this._mirarA(nombre, camara);
    let diferencia = rumboObjetivo - this.rumbo;
    diferencia = Math.atan2(Math.sin(diferencia), Math.cos(diferencia));
    this.rumbo += diferencia * Math.min(1, dt * 6);
    this.paso += dt * (caminando ? 9 + 6 * Math.max(0, a) : 0);

    const pose = this._pose(nombre, ahora, enActividad, caminando);
    this._aplicarPose(pose, ahora);
    this._efectosDeActividad(nombre, ahora, caminando, dt);
    this._actualizarParticulas(dt, ahora);
  }

  _mirarA(nombre, camara) {
    const objeto = this.despierta ? this.actividad.objeto : "cama";
    if (["atenderte", "acercarse", "buscarte", "pedir_comida", "quieta", "aburrirse", "esconderse", "dormir"].includes(nombre) || !objeto) {
      return Math.atan2(camara.position.x - this.x, camara.position.z - this.z);
    }
    const centro = this.habitacion.centroDe(objeto);
    return centro ? Math.atan2(centro.x - this.x, centro.z - this.z) : this.rumbo;
  }

  _pose(nombre, ahora, enActividad, caminando) {
    const { p, a, d } = this.pad;
    const t = ahora / 1000;
    const pose = { sx: 1 + 0.03 * -d, sy: 1 + 0.06 * d, dy: 0, dx: 0, inclinar: 0, cabeceo: 0, ojos: null, boca: null, mira: { x: 0, y: 0 } };
    if (!this.despierta && !caminando) {
      // Acurrucada en su camita: más baja y redonda, la cabeza apenas inclinada, respirando lento.
      const respiro = Math.sin(t * 1.4);
      return { ...pose, sx: 1.1 + 0.025 * respiro, sy: 0.8 + 0.03 * respiro, cabeceo: 0.14,
        inclinar: 0.05 * Math.sin(t * 0.35), ojos: "cerrados", boca: "plana", acostada: true };
    }
    if (!this.despierta) pose.ojos = "medio";
    if (caminando) {
      const salto = Math.abs(Math.sin(this.paso));
      pose.dy = salto * (0.04 + 0.06 * Math.max(0, a));
      pose.sy *= 1 + 0.05 * salto;
      pose.cabeceo = 0.08;
    } else {
      pose.sy *= 1 + 0.02 * Math.sin(t * (1.4 + 2 * Math.max(0, a)));
      if (p > 0.35 && a > 0.25) pose.dy = Math.abs(Math.sin(t * (3 + 3 * a))) * 0.08 * a;
    }
    if (this.etiqueta === "miedo") { pose.dx = (Math.random() - 0.5) * 0.02; pose.sx *= 0.93; pose.sy *= 0.9; }
    if (this.etiqueta === "tristeza" || this.etiqueta === "aburrimiento") { pose.sy *= 0.94; pose.cabeceo += 0.12; }

    if (!caminando) {
      switch (nombre) {
        case "atenderte": case "acercarse": case "buscarte":
          pose.mira = { x: 0, y: 0.3 };
          if (nombre === "buscarte" && Math.sin(t * 3) > 0.7) pose.dy += 0.08;
          break;
        case "explorar": pose.cabeceo = 0.25 + 0.05 * Math.sin(t * 6); pose.mira = { x: 0, y: -0.6 }; break;
        case "mirar_ventana": pose.cabeceo = -0.2; pose.mira = { x: 0, y: 1 }; pose.inclinar = 0.05 * Math.sin(t * 0.8); break;
        case "descansar": pose.sx *= 1.12; pose.sy *= 0.82; pose.ojos = "medio"; break;
        case "pedir_comida": if (Math.sin(t * 5) > 0.6) pose.dy += 0.1; break;
        case "comer": pose.sy *= 1 + 0.06 * Math.sin(t * 12); pose.cabeceo = 0.3; pose.ojos = "felices"; break;
        case "esconderse": pose.sx *= 1.05; pose.sy *= 0.78; pose.dx = (Math.random() - 0.5) * 0.015; break;
        case "aburrirse": pose.sx *= 1.25; pose.sy *= 0.68; pose.ojos = "medio"; pose.boca = "plana"; break;
        case "ir_a_dormir": pose.ojos = "medio"; pose.boca = enActividad > 1 && enActividad < 3 ? "bostezo" : null; break;
        case "quieta": pose.mira = { x: Math.sin(t * 0.7), y: Math.cos(t * 0.5) * 0.4 }; break;
        default: break;
      }
    }

    const gesto = this.gestoActual;
    if (gesto) {
      const avance = (ahora - gesto.inicio) / gesto.duracion;
      if (avance >= 1) {
        this.gestoActual = null;
      } else if (avance >= 0) {
        const curva = Math.sin(avance * Math.PI);
        switch (gesto.nombre) {
          case "asentir": pose.cabeceo += Math.sin(avance * Math.PI * 4) * 0.25 * (1 - avance); break;
          case "negar": pose.giro = Math.sin(avance * Math.PI * 6) * 0.45 * (1 - avance); break;
          case "duda": case "curiosidad": case "confusion": pose.inclinar += 0.3 * curva; break;
          case "alegria": case "saludo": case "sobresalto": pose.dy += 0.25 * Math.abs(Math.sin(avance * Math.PI * 2)); break;
          case "carino": pose.sx *= 1 + 0.08 * curva; pose.sy *= 1 - 0.08 * curva; pose.ojos = "felices"; break;
          case "reconocer": pose.ojos = "entrecerrados"; pose.inclinar += 0.2 * curva; break;
          case "miedo": pose.sx *= 1 - 0.08 * curva; pose.sy *= 1 - 0.1 * curva; pose.dx += (Math.random() - 0.5) * 0.04; break;
          case "tristeza": pose.cabeceo += 0.2 * curva; break;
          default: break;
        }
      }
    }
    return pose;
  }

  _aplicarPose(pose, ahora) {
    const { p, a } = this.pad;
    const cama = this.habitacion.centroDe("cama");
    // Dentro de su camita queda sobre el colchón (sube con suavidad al entrar).
    const enCama = cama && Math.hypot(this.x - cama.x, this.z - cama.z) < 0.35;
    this._altura = mezclar(this._altura || 0, enCama ? cama.alto : 0, 0.15);
    this.grupo.position.set(this.x + (pose.dx || 0), this._altura, this.z);
    this.grupo.rotation.set(0, this.rumbo + (pose.giro || 0), 0);
    const escala = 0.9 + 0.08 * (this.pad.d || 0);
    this.cuerpo.scale.set(pose.sx * escala, pose.sy * escala, pose.sx * escala);
    this.cuerpo.position.y = pose.dy;
    this.cuerpo.rotation.set(pose.cabeceo, 0, pose.inclinar);

    // Color: saturado y luminoso si está contenta; apagado si está triste.
    const saturacion = 0.3 + 0.28 * (p + 1) / 2;
    const luz = 0.5 + 0.06 * a;
    this.material.color.setHSL(this.tono / 360, saturacion, luz, THREE.SRGBColorSpace);
    this.parpado.color.copy(this.material.color).offsetHSL(0, 0, -0.05);

    this._ojos(pose, ahora);
    this._boca(pose, ahora);
    for (const mejilla of this.mejillas) mejilla.material.opacity = this.despierta && p > 0.3 ? Math.min(0.75, p) : 0;

    // Brote: crece con la etapa; hojas arriba si está contenta, caídas si no.
    const alto = 0.08 + 0.06 * this.etapa;
    this.tallo.scale.y = alto;
    this.tallo.position.y = alto / 2;
    const elevacion = this.despierta ? 0.45 + 0.55 * p : -0.3;
    const vaiven = Math.sin(ahora / 900) * 0.08;
    const tamano = 0.8 + 0.15 * this.etapa;
    for (const { pivote, lado } of this.hojas) {
      pivote.position.y = alto;
      pivote.rotation.z = lado * (elevacion + vaiven);
      pivote.scale.setScalar(tamano);
    }
  }

  _ojos(pose, ahora) {
    const { p } = this.pad;
    const etiqueta = this.etiqueta;
    if (ahora > this.proximoParpadeo) {
      this.parpadeoHasta = ahora + 140;
      this.proximoParpadeo = ahora + 2200 + Math.random() * 3500;
    }
    let ojos = pose.ojos;
    if (!ojos) {
      if (!this.despierta || ahora < this.parpadeoHasta) ojos = "cerrados";
      else if (p > 0.45 && (etiqueta === "alegría" || etiqueta === "contento")) ojos = "felices";
      else if (etiqueta === "miedo" || etiqueta === "sorpresa") ojos = "grandes";
      else if (etiqueta === "tristeza") ojos = "tristes";
      else if (etiqueta === "enojo") ojos = "enojados";
      else if (etiqueta === "aburrimiento" || etiqueta === "calma") ojos = "medio";
      else if (etiqueta === "confusión") ojos = "confusos";
      else ojos = "normales";
    }
    for (const { globo, pupila, parpado, lado } of this.ojos) {
      let tipo = ojos === "confusos" ? (lado === 1 ? "medio" : "normales") : ojos;
      const cierre = { cerrados: 1, felices: 0.85, medio: 0.55, entrecerrados: 0.7, tristes: 0.35, enojados: 0.4 }[tipo] || 0;
      // El párpado gira hacia abajo para cubrir el ojo.
      parpado.rotation.x = -Math.PI / 2 + Math.PI * 0.5 * cierre + 0.05;
      parpado.rotation.z = tipo === "tristes" ? lado * 0.35 : tipo === "enojados" ? -lado * 0.4 : 0;
      parpado.visible = cierre > 0;
      const grande = tipo === "grandes" ? 1.25 : 1;
      globo.scale.set(grande, 1.2 * grande, 0.55);
      pupila.scale.setScalar(etiqueta === "miedo" ? 0.6 : etiqueta === "curiosidad" ? 1.15 : 1);
      pupila.scale.y *= 1.15;
      pupila.visible = tipo !== "cerrados" && tipo !== "felices";
      const mira = pose.mira || { x: 0, y: 0 };
      pupila.position.set(acotar(mira.x, -1, 1) * 0.022, acotar(mira.y, -1, 1) * 0.025, 0.035);
    }
  }

  _boca(pose, ahora) {
    const { p } = this.pad;
    const etiqueta = this.etiqueta;
    let forma = pose.boca;
    if (!forma) {
      if (ahora < this.hablaHasta) forma = Math.sin(ahora / 70) > 0 ? "o" : "plana";
      else if (!this.despierta) forma = "plana";
      else if (etiqueta === "miedo") forma = "ondulada";
      else if (etiqueta === "sorpresa") forma = "o";
      else if (p > 0.55) forma = "risa";
      else if (p > 0.15) forma = "sonrisa";
      else if (p < -0.25) forma = "triste";
      else forma = "plana";
    }
    if (forma === this._formaBoca) return;
    this._formaBoca = forma;
    this.boca.geometry.dispose();
    const z = 0.355;
    if (forma === "o" || forma === "bostezo") {
      this.boca.geometry = new THREE.TorusGeometry(forma === "o" ? 0.028 : 0.04, 0.011, 8, 20);
      this.boca.position.set(0, -0.11, z);
      this.boca.scale.set(1, forma === "o" ? 1.2 : 1.5, 0.6);
      return;
    }
    const curvas = { sonrisa: 0.04, risa: 0.07, triste: -0.035, plana: 0.0, ondulada: 0.0 };
    const curva = curvas[forma] ?? 0;
    const puntos = [];
    for (let i = 0; i <= 12; i++) {
      const u = i / 12 - 0.5;
      const ondula = forma === "ondulada" ? Math.sin(u * Math.PI * 6) * 0.01 : 0;
      puntos.push(new THREE.Vector3(u * 0.14, -curva * (1 - 4 * u * u) + ondula, 0));
    }
    this.boca.geometry = new THREE.TubeGeometry(new THREE.CatmullRomCurve3(puntos), 16, forma === "risa" ? 0.014 : 0.01, 6);
    this.boca.position.set(0, -0.1, z);
    this.boca.scale.set(1, 1, 1);
  }

  _efectosDeActividad(nombre, ahora, caminando, dt) {
    const prob = (por) => Math.random() < dt * por;
    if (!this.despierta) { if (prob(0.6)) this.particula("z", "#8b93c9", ahora); return; }
    if (caminando) return;
    if (nombre === "explorar" && prob(0.35)) this.particula("pregunta", "#7a5fc0", ahora);
    if (nombre === "jugar" && prob(0.6)) this.particula("nota", "#e0a32e", ahora);
    if (nombre === "pedir_comida" && prob(0.5)) this.particula("exclamacion", "#e0a32e", ahora);
    if (nombre === "buscarte" && prob(0.4)) this.particula("pregunta", "#e2607a", ahora);
    if (nombre === "aburrirse" && prob(0.3)) this.particula("puntos", "#8b93c9", ahora);
    if (nombre === "comer" && prob(1)) this.particula("miga", "#9b6a3c", ahora);
  }

  _actualizarParticulas(dt, ahora) {
    for (const p of this.particulas) {
      if (ahora < p.nace) continue;
      p.sprite.visible = true;
      p.sprite.position.x += p.vx * dt;
      p.sprite.position.y += p.vy * dt;
      p.vida -= dt * 0.55;
      p.sprite.material.opacity = Math.max(0, Math.min(1, p.vida * 1.4));
    }
    for (const p of this.particulas.filter((q) => q.vida <= 0)) {
      this.habitacion.escena.remove(p.sprite);
      p.sprite.material.dispose();
    }
    this.particulas = this.particulas.filter((p) => p.vida > 0);
  }
}
