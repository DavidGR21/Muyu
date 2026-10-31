/* La habitación de Muyu en 3D (three.js, archivos locales: sin servicios externos).
 * La ventana muestra su hora del día; de noche la lámpara ilumina el cuarto.
 * Los objetos tienen el mismo nombre que usa el servidor para sus actividades. */
import * as THREE from "three";
import { OrbitControls } from "three/addons/OrbitControls.js";

const ANCHO = 8;          // x: de -4 a 4
const FONDO = 6;          // z: de -3 a 3
// A dónde camina Muyu para cada objeto (sobre el piso).
const PUNTOS = {
  cama: { x: -2.75, z: -1.95 },
  plato: { x: -0.55, z: 1.5 },
  cojin: { x: 0.7, z: -0.5 },
  caja: { x: 2.8, z: -2.05 },
  ventana: { x: 0.9, z: -2.2 },
  planta: { x: 2.55, z: -2.35 },
  frente: { x: 0.4, z: 2.2 },
};

function madera(colorBase, vetas) {
  const lienzo = document.createElement("canvas");
  lienzo.width = lienzo.height = 256;
  const ctx = lienzo.getContext("2d");
  ctx.fillStyle = colorBase;
  ctx.fillRect(0, 0, 256, 256);
  for (let i = 0; i < 8; i++) {
    ctx.fillStyle = i % 2 ? "rgba(0,0,0,0.035)" : "rgba(255,255,255,0.03)";
    ctx.fillRect(0, i * 32, 256, 32);
    ctx.fillStyle = vetas;
    ctx.fillRect(0, i * 32, 256, 1.5);
    ctx.fillRect(((i * 97) % 200) + 20, i * 32, 1.5, 32);
  }
  const textura = new THREE.CanvasTexture(lienzo);
  textura.colorSpace = THREE.SRGBColorSpace;
  textura.wrapS = textura.wrapT = THREE.RepeatWrapping;
  return textura;
}

function rayas(color, linea) {
  const lienzo = document.createElement("canvas");
  lienzo.width = lienzo.height = 128;
  const ctx = lienzo.getContext("2d");
  ctx.fillStyle = color;
  ctx.fillRect(0, 0, 128, 128);
  ctx.fillStyle = linea;
  for (let x = 0; x < 128; x += 32) ctx.fillRect(x, 0, 10, 128);
  const textura = new THREE.CanvasTexture(lienzo);
  textura.colorSpace = THREE.SRGBColorSpace;
  textura.wrapS = textura.wrapT = THREE.RepeatWrapping;
  return textura;
}

export class Habitacion {
  constructor(contenedor, criatura, { onTocar } = {}) {
    this.contenedor = contenedor;
    this.criatura = criatura;
    criatura.habitacion = this;
    this.onTocar = onTocar;
    this.alDibujar = null;
    this.hora = 12;
    this.comida = 0;
    this._momento = null;

    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    contenedor.prepend(this.renderer.domElement);

    this.escena = new THREE.Scene();
    this.escena.background = new THREE.Color(0xe9e2d6);
    this.camara = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
    this.camara.position.set(4.6, 4.4, 7.8);
    this.controles = new OrbitControls(this.camara, this.renderer.domElement);
    this.controles.target.set(0, 0.7, -0.3);
    this.controles.enablePan = false;
    this.controles.enableDamping = true;
    this.controles.minDistance = 5;
    this.controles.maxDistance = 12;
    this.controles.minPolarAngle = 0.55;
    this.controles.maxPolarAngle = 1.35;
    this.controles.minAzimuthAngle = -0.35;
    this.controles.maxAzimuthAngle = 1.1;

    this._luces();
    this._cuarto();
    this._muebles();
    this.escena.add(criatura.grupo);

    this.raycaster = new THREE.Raycaster();
    this._tocables = [];
    for (const objeto of [this.pelota, this.plato, this.cama, criatura.grupo]) this._tocables.push(objeto);
    const lienzo = this.renderer.domElement;
    let inicio = null;
    lienzo.addEventListener("pointerdown", (e) => { inicio = { x: e.clientX, y: e.clientY }; });
    lienzo.addEventListener("pointerup", (e) => {
      if (inicio && Math.hypot(e.clientX - inicio.x, e.clientY - inicio.y) < 6) this._tocar(e);
      inicio = null;
    });
    lienzo.addEventListener("pointermove", (e) => { lienzo.style.cursor = this._objetoEn(e) ? "pointer" : "grab"; });

    new ResizeObserver(() => this._ajustar()).observe(contenedor);
    this._ajustar();
    this._reloj = new THREE.Clock();
    this.renderer.setAnimationLoop(() => this._cuadro());
  }

  // ── Construcción ──────────────────────────────────────────────────
  _luces() {
    this.hemisferio = new THREE.HemisphereLight(0xfff3e0, 0x8a6a4a, 1.2);
    this.escena.add(this.hemisferio);
    this.sol = new THREE.DirectionalLight(0xfff1d6, 2.2);
    this.sol.position.set(1.5, 6, 4);
    this.sol.castShadow = true;
    this.sol.shadow.mapSize.set(2048, 2048);
    Object.assign(this.sol.shadow.camera, { left: -5, right: 5, top: 5, bottom: -5 });
    this.sol.shadow.radius = 4;
    this.sol.shadow.bias = -0.0005;
    this.escena.add(this.sol);
    this.lampara = new THREE.PointLight(0xffc977, 0, 7, 1.6);
    this.lampara.position.set(-2.75, 2.1, -2.6);
    this.lampara.castShadow = true;
    this.escena.add(this.lampara);
    this.luzLuna = new THREE.SpotLight(0x9fb4ff, 0, 9, 0.6, 0.6);
    this.luzLuna.position.set(0.9, 2.4, -3.4);
    this.luzLuna.target.position.set(0.9, 0, 0);
    this.escena.add(this.luzLuna, this.luzLuna.target);
  }

  _cuarto() {
    const piso = madera("#c99d6b", "rgba(80,50,20,0.35)");
    piso.repeat.set(2, 2);
    const suelo = new THREE.Mesh(new THREE.PlaneGeometry(ANCHO, FONDO),
      new THREE.MeshStandardMaterial({ map: piso, roughness: 0.75 }));
    suelo.rotation.x = -Math.PI / 2;
    suelo.receiveShadow = true;
    this.escena.add(suelo);

    const papel = rayas("#efdcc0", "#e8d1ae");
    papel.repeat.set(4, 1.5);
    const pared = new THREE.MeshStandardMaterial({ map: papel, roughness: 0.9 });
    const fondo = new THREE.Mesh(new THREE.PlaneGeometry(ANCHO, 3.2), pared);
    fondo.position.set(0, 1.6, -FONDO / 2);
    fondo.receiveShadow = true;
    const izquierda = new THREE.Mesh(new THREE.PlaneGeometry(FONDO, 3.2), pared);
    izquierda.position.set(-ANCHO / 2, 1.6, 0);
    izquierda.rotation.y = Math.PI / 2;
    izquierda.receiveShadow = true;
    this.escena.add(fondo, izquierda);

    const zocalo = new THREE.MeshStandardMaterial({ color: 0xb8915f, roughness: 0.6 });
    const z1 = new THREE.Mesh(new THREE.BoxGeometry(ANCHO, 0.16, 0.05), zocalo);
    z1.position.set(0, 0.08, -FONDO / 2 + 0.025);
    const z2 = new THREE.Mesh(new THREE.BoxGeometry(0.05, 0.16, FONDO), zocalo);
    z2.position.set(-ANCHO / 2 + 0.025, 0.08, 0);
    this.escena.add(z1, z2);

    // Ventana con cielo dibujado según su hora.
    this.lienzoCielo = document.createElement("canvas");
    this.lienzoCielo.width = 256;
    this.lienzoCielo.height = 192;
    this.texturaCielo = new THREE.CanvasTexture(this.lienzoCielo);
    this.texturaCielo.colorSpace = THREE.SRGBColorSpace;
    const cielo = new THREE.Mesh(new THREE.PlaneGeometry(1.7, 1.25), new THREE.MeshBasicMaterial({ map: this.texturaCielo }));
    cielo.position.set(0.9, 1.95, -FONDO / 2 + 0.01);
    this.escena.add(cielo);
    const marco = new THREE.MeshStandardMaterial({ color: 0x8b6a47, roughness: 0.6 });
    for (const [w, h, x, y] of [[1.86, 0.08, 0.9, 2.6], [1.86, 0.08, 0.9, 1.3], [0.08, 1.38, 0.0, 1.95],
      [0.08, 1.38, 1.8, 1.95], [0.05, 1.25, 0.9, 1.95], [1.7, 0.05, 0.9, 1.95]]) {
      const pieza = new THREE.Mesh(new THREE.BoxGeometry(w, h, 0.07), marco);
      pieza.position.set(x, y, -FONDO / 2 + 0.04);
      this.escena.add(pieza);
    }
    const alfeizar = new THREE.Mesh(new THREE.BoxGeometry(2.0, 0.06, 0.22), marco);
    alfeizar.position.set(0.9, 1.25, -FONDO / 2 + 0.11);
    alfeizar.castShadow = true;
    this.escena.add(alfeizar);

    // Cuadro en la pared izquierda con un sol pintado.
    const lienzoCuadro = document.createElement("canvas");
    lienzoCuadro.width = 128;
    lienzoCuadro.height = 96;
    const c = lienzoCuadro.getContext("2d");
    c.fillStyle = "#fbf3df"; c.fillRect(0, 0, 128, 96);
    c.fillStyle = "#9ccf7a"; c.fillRect(0, 68, 128, 28);
    c.fillStyle = "#f2b632"; c.beginPath(); c.arc(64, 40, 16, 0, Math.PI * 2); c.fill();
    const texturaCuadro = new THREE.CanvasTexture(lienzoCuadro);
    texturaCuadro.colorSpace = THREE.SRGBColorSpace;
    // La cara +x de la caja (índice 0) mira hacia el cuarto: ahí va la pintura.
    const lienzoPintado = new THREE.MeshStandardMaterial({ map: texturaCuadro });
    const cuadro = new THREE.Mesh(new THREE.BoxGeometry(0.06, 0.62, 0.82),
      [lienzoPintado, marco, marco, marco, marco, marco]);
    cuadro.position.set(-ANCHO / 2 + 0.04, 1.9, 0.6);
    this.escena.add(cuadro);
  }

  _caja(w, h, d, color, x, y, z, opciones = {}) {
    const malla = new THREE.Mesh(new THREE.BoxGeometry(w, h, d),
      new THREE.MeshStandardMaterial({ color, roughness: opciones.rugosidad ?? 0.7 }));
    malla.position.set(x, y, z);
    malla.castShadow = true;
    malla.receiveShadow = true;
    return malla;
  }

  _muebles() {
    // Camita redonda de mascota: base acolchada, borde mullido y una mantita doblada.
    this.cama = new THREE.Group();
    const tela = (color) => new THREE.MeshStandardMaterial({ color, roughness: 0.95 });
    const fondoCama = new THREE.Mesh(new THREE.CylinderGeometry(0.82, 0.86, 0.1, 40), tela(0x6e86b8));
    fondoCama.position.y = 0.05;
    // Borde mullido con una abertura al frente (hacia la cámara), como las camitas de perro.
    const abertura = THREE.MathUtils.degToRad(80);
    const aro = new THREE.Group();
    const tubo = new THREE.Mesh(new THREE.TorusGeometry(0.68, 0.14, 16, 48, Math.PI * 2 - abertura), tela(0x7f98cc));
    tubo.rotation.x = Math.PI / 2;
    tubo.castShadow = tubo.receiveShadow = true;
    aro.add(tubo);
    for (const angulo of [0, Math.PI * 2 - abertura]) {
      const punta = new THREE.Mesh(new THREE.SphereGeometry(0.14, 16, 12), tela(0x7f98cc));
      punta.position.set(Math.cos(angulo) * 0.68, 0, Math.sin(angulo) * 0.68);
      punta.castShadow = true;
      aro.add(punta);
    }
    // El hueco queda centrado en el ángulo -40° del aro; se gira para que mire a la cámara (53° en el piso).
    aro.rotation.y = -THREE.MathUtils.degToRad(93);
    aro.position.y = 0.16;
    const colchon = new THREE.Mesh(new THREE.CylinderGeometry(0.56, 0.58, 0.1, 40), tela(0xf2e6d4));
    colchon.position.y = 0.12;
    const costura = new THREE.Mesh(new THREE.TorusGeometry(0.56, 0.012, 6, 48), tela(0xd9c8ae));
    costura.rotation.x = Math.PI / 2;
    costura.position.y = 0.175;
    const mantita = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.05, 0.32), tela(0xe7a6a1));
    mantita.position.set(-0.3, 0.32, -0.6);
    mantita.rotation.set(0.35, 0.6, 0.12);
    for (const pieza of [fondoCama, colchon, mantita]) {
      pieza.castShadow = true;
      pieza.receiveShadow = true;
    }
    this.cama.add(fondoCama, aro, colchon, costura, mantita);
    this.cama.position.set(-2.75, 0, -1.95);
    this.cama.traverse((m) => { m.userData.objeto = "cama"; });
    this.escena.add(this.cama);

    // Lámpara de pared sobre su camita.
    const pantalla = new THREE.Mesh(new THREE.CylinderGeometry(0.14, 0.24, 0.24, 20, 1, true),
      new THREE.MeshStandardMaterial({ color: 0xe8c170, side: THREE.DoubleSide, emissive: 0x000000 }));
    pantalla.position.set(-2.75, 2.2, -2.8);
    this.pantalla = pantalla;
    this.escena.add(pantalla, this._caja(0.04, 0.3, 0.2, 0x8b6a47, -2.75, 2.0, -2.93));

    // Alfombra y cojín.
    const alfombra = new THREE.Mesh(new THREE.CircleGeometry(1.15, 40),
      new THREE.MeshStandardMaterial({ color: 0xdcb995, roughness: 1 }));
    alfombra.rotation.x = -Math.PI / 2;
    alfombra.scale.set(1.3, 0.85, 1);
    alfombra.position.set(0.7, 0.006, -0.5);
    alfombra.receiveShadow = true;
    const borde = new THREE.Mesh(new THREE.RingGeometry(1.08, 1.15, 40),
      new THREE.MeshStandardMaterial({ color: 0xc58f6b, roughness: 1 }));
    borde.rotation.x = -Math.PI / 2;
    borde.scale.set(1.3, 0.85, 1);
    borde.position.set(0.7, 0.008, -0.5);
    const cojin = new THREE.Mesh(new THREE.CylinderGeometry(0.5, 0.55, 0.16, 28),
      new THREE.MeshStandardMaterial({ color: 0xc97c9a, roughness: 0.85 }));
    cojin.position.set(0.7, 0.08, -0.5);
    cojin.castShadow = cojin.receiveShadow = true;
    this.escena.add(alfombra, borde, cojin);

    // Caja de cartón (su escondite).
    const caja = new THREE.Group();
    caja.add(this._caja(0.95, 0.7, 0.8, 0xc89b5e, 0, 0.35, 0));
    const solapa1 = this._caja(0.95, 0.03, 0.4, 0xd7ad72, 0, 0.72, 0.55);
    solapa1.rotation.x = -0.6;
    const solapa2 = this._caja(0.95, 0.03, 0.4, 0xd7ad72, 0, 0.72, -0.55);
    solapa2.rotation.x = 0.6;
    caja.add(solapa1, solapa2, this._caja(0.97, 0.12, 0.82, 0xe2c08a, 0, 0.45, 0));
    caja.position.set(2.75, 0, -1.25);
    this.escena.add(caja);

    // Planta.
    const planta = new THREE.Group();
    const maceta = new THREE.Mesh(new THREE.CylinderGeometry(0.28, 0.22, 0.5, 20),
      new THREE.MeshStandardMaterial({ color: 0xb5653a, roughness: 0.8 }));
    maceta.position.y = 0.25;
    maceta.castShadow = true;
    planta.add(maceta);
    const verde = new THREE.MeshStandardMaterial({ color: 0x5ea343, roughness: 0.7 });
    for (let i = 0; i < 7; i++) {
      const hoja = new THREE.Mesh(new THREE.SphereGeometry(0.16, 12, 8), verde);
      const angulo = (i / 7) * Math.PI * 2;
      hoja.scale.set(0.45, 1.6 + (i % 3) * 0.4, 0.25);
      hoja.position.set(Math.cos(angulo) * 0.12, 0.75 + (i % 3) * 0.12, Math.sin(angulo) * 0.12);
      hoja.rotation.set(Math.sin(angulo) * 0.4, 0, -Math.cos(angulo) * 0.4);
      hoja.castShadow = true;
      planta.add(hoja);
    }
    planta.position.set(3.45, 0, -2.55);
    this.escena.add(planta);

    // Plato y comida.
    this.plato = new THREE.Group();
    const cuenco = new THREE.Mesh(new THREE.CylinderGeometry(0.3, 0.22, 0.14, 24, 1, true),
      new THREE.MeshStandardMaterial({ color: 0xd4574b, roughness: 0.4, side: THREE.DoubleSide }));
    cuenco.position.y = 0.07;
    cuenco.castShadow = true;
    const base = new THREE.Mesh(new THREE.CircleGeometry(0.22, 24), new THREE.MeshStandardMaterial({ color: 0xa8423a }));
    base.rotation.x = -Math.PI / 2;
    base.position.y = 0.01;
    this.comidaMalla = new THREE.Mesh(new THREE.SphereGeometry(0.24, 20, 10, 0, Math.PI * 2, 0, Math.PI / 2),
      new THREE.MeshStandardMaterial({ color: 0xb07a45, roughness: 0.95 }));
    this.comidaMalla.scale.y = 0.35;
    this.comidaMalla.position.y = 0.07;
    this.comidaMalla.visible = false;
    this.plato.add(cuenco, base, this.comidaMalla);
    this.plato.position.set(-1.15, 0, 1.5);
    this.plato.traverse((m) => { m.userData.objeto = "plato"; });
    this.escena.add(this.plato);

    // Pelota con física simple.
    const lienzo = document.createElement("canvas");
    lienzo.width = 128;
    lienzo.height = 64;
    const ctx = lienzo.getContext("2d");
    ctx.fillStyle = "#e04e4e"; ctx.fillRect(0, 0, 128, 64);
    ctx.fillStyle = "#fff4f0"; ctx.fillRect(0, 28, 128, 8); ctx.fillRect(60, 0, 8, 64);
    const texturaPelota = new THREE.CanvasTexture(lienzo);
    texturaPelota.colorSpace = THREE.SRGBColorSpace;
    this.pelota = new THREE.Mesh(new THREE.SphereGeometry(0.18, 24, 16),
      new THREE.MeshStandardMaterial({ map: texturaPelota, roughness: 0.4 }));
    this.pelota.position.set(1.6, 0.18, 1.0);
    this.pelota.castShadow = true;
    this.pelota.userData.objeto = "pelota";
    this.pelota.userData.v = new THREE.Vector2(0, 0);
    this.escena.add(this.pelota);
  }

  // ── Lo que usa la criatura ──────────────────────────────────────────
  punto(objeto, criatura) {
    if (!objeto) return null;
    if (objeto === "pelota") {
      const p = this.pelota.position;
      const lado = criatura.x < p.x ? -0.42 : 0.42;
      return { x: p.x + lado, z: p.z };
    }
    return PUNTOS[objeto] || null;
  }

  centroDe(objeto) {
    if (objeto === "pelota") return { x: this.pelota.position.x, z: this.pelota.position.z };
    if (objeto === "cama") return { x: -2.75, z: -1.95, alto: 0.16 };
    if (objeto === "plato") return { x: this.plato.position.x, z: this.plato.position.z };
    if (objeto === "ventana") return { x: 0.9, z: -3 };
    if (objeto === "caja") return { x: 2.75, z: -1.25 };
    if (objeto === "planta") return { x: 3.45, z: -2.55 };
    if (objeto === "cojin") return { x: 0.7, z: 0.5 };
    return null;
  }

  lanzarPelota() {
    const v = this.pelota.userData.v;
    v.set((this.pelota.position.x > 0.5 ? -1 : 1) * (2.2 + Math.random()), (Math.random() - 0.5) * 1.8);
  }

  servirComida() {
    this.comida = 7;
  }

  aPantalla(vector) {
    const proyectado = vector.clone().project(this.camara);
    const caja = this.renderer.domElement.getBoundingClientRect();
    return { x: (proyectado.x + 1) / 2 * caja.width, y: (1 - proyectado.y) / 2 * caja.height, visible: proyectado.z < 1 };
  }

  // ── Bucle ───────────────────────────────────────────────────────────
  _ajustar() {
    const { clientWidth: ancho, clientHeight: alto } = this.contenedor;
    if (!ancho || !alto) return;
    this.renderer.setSize(ancho, alto);
    this.camara.aspect = ancho / alto;
    // En pantallas verticales (celular) abre el campo de visión para que se vea el cuarto entero.
    this.camara.fov = this.camara.aspect < 1 ? 58 : this.camara.aspect < 1.4 ? 46 : 38;
    this.camara.updateProjectionMatrix();
  }

  _cuadro() {
    const dt = Math.min(0.05, this._reloj.getDelta());
    const ahora = performance.now();
    this._fisica(dt);
    this.criatura.actualizar(dt, ahora, this.camara);
    this._jugarYComer(dt, ahora);
    this._diaYNoche(ahora);
    this.controles.update();
    this.renderer.render(this.escena, this.camara);
    if (this.alDibujar) this.alDibujar(this.aPantalla(this.criatura.cabeza()));
  }

  _fisica(dt) {
    const p = this.pelota.position;
    const v = this.pelota.userData.v;
    p.x += v.x * dt;
    p.z += v.y * dt;
    v.multiplyScalar(Math.pow(0.4, dt));
    if (v.length() < 0.05) v.set(0, 0);
    const limite = { x0: -1.6, x1: 3.6, z0: -1.4, z1: 2.6 };
    if (p.x < limite.x0) { p.x = limite.x0; v.x = Math.abs(v.x) * 0.7; }
    if (p.x > limite.x1) { p.x = limite.x1; v.x = -Math.abs(v.x) * 0.7; }
    if (p.z < limite.z0) { p.z = limite.z0; v.y = Math.abs(v.y) * 0.7; }
    if (p.z > limite.z1) { p.z = limite.z1; v.y = -Math.abs(v.y) * 0.7; }
    this.pelota.rotation.z -= (v.x * dt) / 0.18;
    this.pelota.rotation.x += (v.y * dt) / 0.18;
  }

  _jugarYComer(dt, ahora) {
    const c = this.criatura;
    this.comidaMalla.visible = this.comida > 0;
    this.comidaMalla.scale.setScalar(Math.max(0.3, this.comida / 7));
    this.comidaMalla.scale.y = 0.35 * Math.max(0.3, this.comida / 7);
    if (!c.despierta) return;
    const nombre = c.actividad.nombre;
    const p = this.pelota.position;
    if (nombre === "jugar" && Math.hypot(c.x - p.x, c.z - p.z) < 0.5 && this.pelota.userData.v.length() < 0.4) {
      const dx = p.x - c.x || 0.1;
      const dz = p.z - c.z;
      const d = Math.hypot(dx, dz) || 1;
      this.pelota.userData.v.set((dx / d) * (1.8 + Math.random()), (dz / d) * (1.8 + Math.random()) + (Math.random() - 0.5));
      c.particula("nota", "#e0a32e", ahora);
    }
    if (nombre === "comer" && Math.hypot(c.x - PUNTOS.plato.x, c.z - PUNTOS.plato.z) < 0.2) {
      this.comida = Math.max(0, this.comida - dt);
    }
  }

  _cielo() {
    const h = this.hora;
    if (h < 5 || h >= 21) return ["#141c44", "#2c3a6e", "noche"];
    if (h < 7) return ["#f2a07b", "#f7d29a", "amanecer"];
    if (h < 17.5) return ["#6fb9ec", "#c4e8fb", "dia"];
    if (h < 19.5) return ["#f08a5d", "#f6c177", "atardecer"];
    return ["#5b4b8a", "#c47ba2", "anochecer"];
  }

  _diaYNoche(ahora) {
    const [arriba, abajo, momento] = this._cielo();
    const ctx = this.lienzoCielo.getContext("2d");
    const gradiente = ctx.createLinearGradient(0, 0, 0, 192);
    gradiente.addColorStop(0, arriba);
    gradiente.addColorStop(1, abajo);
    ctx.fillStyle = gradiente;
    ctx.fillRect(0, 0, 256, 192);
    if (momento === "noche" || momento === "anochecer") {
      for (let i = 0; i < 24; i++) {
        if (Math.sin(ahora / 500 + i * 2.1) > -0.3) {
          ctx.fillStyle = "#fff7d6";
          ctx.fillRect((i * 67) % 250, (i * 41) % 130, 2, 2);
        }
      }
      ctx.fillStyle = "#f4ecc9";
      ctx.beginPath(); ctx.arc(190, 50, 20, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = arriba;
      ctx.beginPath(); ctx.arc(200, 44, 18, 0, Math.PI * 2); ctx.fill();
    } else {
      const avance = Math.max(0, Math.min(1, (this.hora - 6) / 13));
      ctx.fillStyle = momento === "dia" ? "#ffe066" : "#ffb347";
      ctx.beginPath();
      ctx.arc(20 + avance * 216, 30 + Math.abs(avance - 0.5) * 220, 16, 0, Math.PI * 2);
      ctx.fill();
      if (momento === "dia") {
        ctx.fillStyle = "rgba(255,255,255,0.9)";
        const nube = (ahora / 60) % 320 - 40;
        for (const [dx, dy, r] of [[0, 0, 14], [16, -6, 16], [32, 0, 12], [120, 50, 10], [134, 46, 12]]) {
          ctx.beginPath(); ctx.arc((nube + dx + 320) % 320 - 30, 100 + dy, r, 0, Math.PI * 2); ctx.fill();
        }
      }
    }
    this.texturaCielo.needsUpdate = true;

    if (momento === this._momento) return;
    this._momento = momento;
    const luz = { dia: 1, atardecer: 0.75, amanecer: 0.6, anochecer: 0.4, noche: 0.18 }[momento];
    const colorSol = { dia: 0xfff1d6, atardecer: 0xffb27a, amanecer: 0xffc59a, anochecer: 0xb48ad0, noche: 0x7d8dd6 }[momento];
    this.sol.intensity = 2.4 * luz;
    this.sol.color.setHex(colorSol);
    this.hemisferio.intensity = 0.35 + 0.9 * luz;
    const encendida = momento === "noche" || momento === "anochecer";
    this.lampara.intensity = encendida ? 9 : 0;
    this.pantalla.material.emissive.setHex(encendida ? 0xffb347 : 0x000000);
    this.pantalla.material.emissiveIntensity = encendida ? 1.2 : 0;
    this.luzLuna.intensity = momento === "noche" ? 6 : 0;
    this.escena.background.set(luz > 0.5 ? 0xe9e2d6 : 0x272842);
  }

  // ── Tocar ───────────────────────────────────────────────────────────
  _objetoEn(evento) {
    const caja = this.renderer.domElement.getBoundingClientRect();
    const puntero = new THREE.Vector2(((evento.clientX - caja.left) / caja.width) * 2 - 1,
      -((evento.clientY - caja.top) / caja.height) * 2 + 1);
    this.raycaster.setFromCamera(puntero, this.camara);
    const impacto = this.raycaster.intersectObjects(this._tocables, true)[0];
    if (!impacto) return null;
    let objeto = impacto.object;
    while (objeto && !objeto.userData.objeto) objeto = objeto.parent;
    return objeto ? objeto.userData.objeto : null;
  }

  _tocar(evento) {
    const objeto = this._objetoEn(evento);
    if (objeto && this.onTocar) this.onTocar(objeto);
  }
}
