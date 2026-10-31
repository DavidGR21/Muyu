"""La criatura: une percepción, memoria, emociones, razonamiento y lenguaje.

Cada entrada (un mensaje, una acción o el paso del tiempo) recorre el mismo
camino: percepción → memoria → evaluación emocional → razonamiento → decisión
→ lenguaje. Todo lo que cambia deja una explicación para el panel del cerebro.

Además tiene un cuerpo: cuando nadie le habla elige qué hacer (jugar, explorar,
pedir comida, buscarte, esconderse, dormir…) según sus necesidades y su emoción.

Las salidas son diccionarios listos para enviar al navegador: ``habla`` (lo que
dice, su gesto y la emoción con que lo dice), ``actividad`` (qué hace su cuerpo y
por qué), ``pensamiento`` (para el panel) y ``aviso``.
"""

from __future__ import annotations

import json
import random
import secrets
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from server import config
from server.brain import instincts
from server.brain.behavior import ESTIMULO, Actividad, Comportamiento, EstadoCorporal
from server.brain.concepts import Concepto, RedConceptos, Relacion
from server.brain.emotions import Emociones, Evaluacion
from server.brain.language.babble import inventario_fonetico
from server.brain.language.ngram import INICIO, ModeloNgramas
from server.brain.language.speaker import Hablante, Intencion
from server.brain.lexicon import Lexico, Palabra
from server.brain.memory import Episodio, MemoriaEpisodica
from server.brain.perception import Evento, Frase, percibir_texto
from server.brain.questions import responder
from server.brain.reasoning import PENDIENTE, RECHAZADA, Hipotesis, Razonador
from server.brain.sleep import Sueno, consolidar
from server.brain.thoughts import RECUERDO, ContextoPensamiento, Pensador, Pensamiento, texto_conceptual
from server.clock import Reloj
from server.storage.db import BaseCriatura, ruta_de

GESTOS_DE_ACCION = {"acariciar": "carino", "alimentar": "alegria", "jugar": "alegria", "regañar": "miedo"}
# Lo que dice con estas intenciones no afirma nada que se pueda corregir con 👍/👎.
SIN_CONTENIDO = {"balbuceo", "dormida", "emocion", "imitar", "saludo", "confusion", "reconocer"}


def duracion(segundos: float) -> str:
    segundos = int(segundos)
    if segundos < 60:
        return f"{segundos} s"
    minutos = segundos // 60
    if minutos < 60:
        return f"{minutos} min"
    horas, minutos = divmod(minutos, 60)
    if horas < 24:
        return f"{horas} h {minutos} min" if minutos else f"{horas} h"
    dias, horas = divmod(horas, 24)
    return f"{dias} día{'s' if dias > 1 else ''} {horas} h" if horas else f"{dias} día{'s' if dias > 1 else ''}"


@dataclass
class _Resumen:
    """Lo que dejó un mensaje, para decidir qué responder."""

    nuevas: list[str] = field(default_factory=list)
    reconocidas: list[str] = field(default_factory=list)
    conceptos: list[str] = field(default_factory=list)
    hipotesis: list[Hipotesis] = field(default_factory=list)
    confirmadas: list[Hipotesis] = field(default_factory=list)
    rechazadas: list[Hipotesis] = field(default_factory=list)
    contradichas: list[Relacion] = field(default_factory=list)
    negadas: list[tuple[str, str]] = field(default_factory=list)  # entendió "a no es b"
    respuesta: dict | None = None       # cómo resolvió la pregunta que había hecho
    ambigua: tuple[Hipotesis, str] | None = None   # le respondieron con palabras que aún no entiende


class Muyu:
    def __init__(self, identificador: str, nombre: str, semilla: int, nacimiento: float,
                 reloj_real=time.time, tiempo: float = 0.0, db: BaseCriatura | None = None) -> None:
        self.id = identificador
        self.nombre = nombre
        self.semilla = semilla
        self.nacimiento = nacimiento
        self.reloj_real = reloj_real
        self.reloj = Reloj(tiempo, reloj_real=reloj_real)
        self.db = db
        self.rasgos = instincts.rasgos_innatos(semilla)
        self.rng = random.Random(semilla)
        ahora_real = reloj_real()

        self.lexico = Lexico()
        self.red = RedConceptos()
        self.razonador = Razonador(self.red, self.lexico)
        self.memoria = MemoriaEpisodica()
        self.necesidades = instincts.Necesidades()
        self.emociones = Emociones(self.rasgos, ahora_real, self.necesidades)
        self.comportamiento = Comportamiento(self.rng, ahora_real)
        self.ngramas = ModeloNgramas()
        self.hablante = Hablante(self.lexico, self.ngramas, inventario_fonetico(semilla), self.rng)
        self.pensador = Pensador(self.rng)
        self.pensamientos: list[Pensamiento] = []
        self.suenos: list[Sueno] = []
        self._pensamientos_sucios: set[int] = set()
        self._suenos_sucios: set[int] = set()

        self.etapa = 0
        self.despierta = True
        self.es_nueva = False
        self.ultimo_sueno = 0.0
        self.sueno_por_contar: int | None = None
        self.pregunta_pendiente: dict | None = None     # {"hipotesis": id, "real": t}
        self.ultima_resolucion: dict | None = None      # para corregir un "sí" que era un "no"
        self.ultimo_dicho: dict | None = None           # lo último que dijo, por si le dicen que está mal
        self._ultimo_mensaje: dict | None = None        # lo último que le escribiste
        self._gesto_pendiente: dict | None = None       # un 👍/👎 que espera las palabras que lo acompañan
        self.ultima_interaccion_real = ahora_real
        self.guardada_real = ahora_real
        self._ultimo_latido_real = ahora_real
        self._dormida_desde = 0.0

        self._palabras_recientes: deque[tuple[float, str]] = deque(maxlen=60)
        self._senales_recientes: deque[tuple[float, instincts.Senal]] = deque(maxlen=20)
        self._inicio_sesion = True
        self._proximo_pensamiento = ahora_real + config.PERIODO_PENSAMIENTO_S

    # ── Nacimiento, carga y guardado ─────────────────────────────────────

    @classmethod
    def nacer(cls, directorio: Path | None = None, nombre: str = "Muyu", semilla: int | None = None,
              reloj_real=time.time) -> Muyu:
        identificador = uuid.uuid4().hex
        semilla = secrets.randbits(31) if semilla is None else semilla
        db = BaseCriatura(ruta_de(directorio, identificador)) if directorio else None
        criatura = cls(identificador, nombre, semilla, reloj_real(), reloj_real, db=db)
        criatura.es_nueva = True
        criatura.guardar()
        return criatura

    @staticmethod
    def existe(directorio: Path, identificador: str) -> bool:
        return ruta_de(directorio, identificador).exists()

    @classmethod
    def cargar(cls, identificador: str, directorio: Path, reloj_real=time.time) -> Muyu:
        db = BaseCriatura(ruta_de(directorio, identificador))
        fila = db.leer_uno("criatura")
        if fila is None:
            db.cerrar()
            raise FileNotFoundError(identificador)
        criatura = cls(fila["id"], fila["nombre"], fila["semilla"], fila["nacimiento"], reloj_real, fila["tiempo"], db)
        criatura.etapa = fila["etapa"]
        criatura.guardada_real = fila["guardada_real"]
        criatura.ultima_interaccion_real = fila["ultima_interaccion_real"]
        criatura.ultimo_sueno = fila["ultimo_sueno"]
        criatura.lexico.total_frases = fila["total_frases"]

        estado = db.leer_uno("estado")
        if estado:
            criatura.emociones.cargar_estado(estado)
            for nombre, valor in json.loads(estado["necesidades"]).items():
                setattr(criatura.necesidades, nombre, valor)
            criatura.emociones.base_necesidades = criatura.necesidades.efecto_emocional()
            criatura.despierta = bool(estado["despierta"])
            if not criatura.despierta:
                criatura.comportamiento.iniciar("dormir", "cama", "está dormida", reloj_real(), duracion=10**9)
            extra = json.loads(estado["extra"])
            criatura.sueno_por_contar = extra.get("sueno_por_contar")
            criatura.pregunta_pendiente = extra.get("pregunta_pendiente")
            criatura.ultima_resolucion = extra.get("ultima_resolucion")
        relacion = db.leer_uno("relacion")
        if relacion:
            criatura.emociones.cargar_relacion(relacion)

        for fila in db.leer("lexico"):
            palabra = Palabra.desde_fila(fila)
            criatura.lexico.palabras[palabra.forma] = palabra
        for fila in db.leer("conceptos"):
            criatura.red.agregar_nodo(Concepto.desde_fila(fila))
        for fila in db.leer("relaciones_conceptos"):
            criatura.red.agregar_relacion(Relacion.desde_fila(fila))
        for fila in db.leer("hipotesis"):
            hipotesis = Hipotesis.desde_fila(fila)
            criatura.razonador.hipotesis[hipotesis.id] = hipotesis
        criatura.memoria.episodios = [Episodio.desde_fila(f) for f in db.leer("episodios", "id")]
        criatura.pensamientos = [Pensamiento.desde_fila(f) for f in reversed(db.leer("pensamientos", "id DESC", 200))]
        criatura.suenos = [Sueno.desde_fila(f) for f in db.leer("suenos", "id")]
        criatura.ngramas.cargar(db.leer("ngramas"))

        for sucios in (criatura.lexico.sucias, criatura.red.sucios_nodos, criatura.red.sucias_relaciones,
                       criatura.razonador.sucias, criatura.memoria.sucios, criatura.ngramas.sucios):
            sucios.clear()
        return criatura

    def guardar(self) -> None:
        if self.db is None:
            return
        ahora = self.reloj.tiempo
        self.guardada_real = self.reloj_real()
        db = self.db
        db.guardar("criatura", [{
            "id": self.id,
            "nombre": self.nombre,
            "nacimiento": self.nacimiento,
            "etapa": self.etapa,
            "semilla": self.semilla,
            "rasgos": json.dumps(self.rasgos),
            "tiempo": ahora,
            "guardada_real": self.guardada_real,
            "ultima_interaccion_real": self.ultima_interaccion_real,
            "total_frases": self.lexico.total_frases,
            "ultimo_sueno": self.ultimo_sueno,
        }])
        db.guardar("estado", [{
            "id": 1,
            **self.emociones.a_fila_estado(),
            "necesidades": json.dumps(self.necesidades.a_dict()),
            "despierta": int(self.despierta),
            "extra": json.dumps({
                "sueno_por_contar": self.sueno_por_contar,
                "pregunta_pendiente": self.pregunta_pendiente,
                "ultima_resolucion": self.ultima_resolucion,
            }),
        }])
        db.guardar("relacion", [self.emociones.a_fila_relacion(ahora)])
        db.guardar("lexico", [self.lexico.palabras[f].a_fila(self.lexico.informatividad(f)) for f in self.lexico.sucias])
        db.guardar("conceptos", [self.red.nodos[n].a_fila() for n in self.red.sucios_nodos])
        db.guardar("relaciones_conceptos", [self.red.relaciones[k].a_fila(ahora) for k in self.red.sucias_relaciones])
        db.guardar("hipotesis", [self.razonador.hipotesis[i].a_fila() for i in self.razonador.sucias])
        episodios = {e.id: e for e in self.memoria.episodios[-500:] if e.id in self.memoria.sucios}
        db.guardar("episodios", [e.a_fila() for e in episodios.values()])
        db.guardar("pensamientos", [p.a_fila() for p in self.pensamientos if p.id in self._pensamientos_sucios])
        db.guardar("suenos", [s.a_fila() for s in self.suenos if s.id in self._suenos_sucios])
        db.guardar("ngramas", self.ngramas.filas_sucias())
        db.confirmar()
        for sucios in (self.lexico.sucias, self.red.sucios_nodos, self.red.sucias_relaciones, self.razonador.sucias,
                       self.memoria.sucios, self._pensamientos_sucios, self._suenos_sucios):
            sucios.clear()
        if len(self.pensamientos) > 300:
            del self.pensamientos[:-200]

    def cerrar(self) -> None:
        self.guardar()
        if self.db:
            self.db.cerrar()
            self.db = None

    # ── Entradas ─────────────────────────────────────────────────────────

    def oir(self, texto: str) -> list[dict]:
        """El dueño le escribe algo."""
        salidas = self._sincronizar()
        ahora, ahora_real = self.reloj.tiempo, self.reloj_real()
        evento = percibir_texto(texto, ahora_real)
        if not evento.frases:
            return salidas
        if not self.despierta:
            return salidas + [self._decir(Intencion("dormida", detalle="Está dormida: no escucha"), "respuesta")]

        saludo = self._inicio_sesion
        self._inicio_sesion = False
        self._contacto(ahora_real, 0.05)
        self.necesidades.estimular(0.2)
        salidas += self._atender(ahora_real, "te escucha")
        intensidad = self._intensidad(ahora_real)
        resumen = _Resumen()
        pregunta: Frase | None = None

        for frase in evento.frases:
            respondida = None if frase.es_pregunta else self._hipotesis_respondida(frase, ahora_real)
            oido = self.lexico.oir(frase, ahora, intensidad, saludo=saludo, respuesta=respondida is not None)
            self.ngramas.aprender(frase.palabras)
            resumen.nuevas += oido.nuevas
            resumen.reconocidas += oido.reconocidas
            self._palabras_recientes.extend((ahora_real, p) for p in dict.fromkeys(frase.palabras))
            conceptos = [p for p in dict.fromkeys(frase.palabras) if self.lexico.es_concepto(p)]
            resumen.conceptos += conceptos

            if frase.es_pregunta:
                # Una pregunta no enseña nada, pero la hace pensar en esos conceptos.
                pregunta = frase
                for concepto in conceptos:
                    self.red.reforzar_nodo(concepto, ahora, 0.5 * intensidad)
                continue

            if respondida:
                resolucion = self._resolver(respondida, frase, ahora, ahora_real)
                if resolucion:
                    resumen.respuesta = resolucion
                else:
                    resumen.ambigua = (respondida, " ".join(frase.palabras))
                    self.pregunta_pendiente = {"hipotesis": respondida.id, "real": ahora_real}
            aprendizaje = self.red.aprender(conceptos, ahora, intensidad, self._negaciones(frase, conceptos),
                                            [frase.posicion(c) for c in conceptos])
            relaciones = aprendizaje.nuevas + aprendizaje.reforzadas
            resumen.contradichas += aprendizaje.contradichas
            for relacion in relaciones:
                hipotesis = self.razonador.por_par(relacion.origen, relacion.destino)
                if hipotesis and hipotesis.estado == PENDIENTE:
                    self.razonador.confirmar(hipotesis, ahora, "se lo enseñaron directamente")
                    resumen.confirmadas.append(hipotesis)
            resumen.negadas += aprendizaje.negadas
            for a, b in aprendizaje.negadas:
                for hipotesis in (self.razonador.por_par(a, b), self.razonador.por_par(b, a)):
                    if hipotesis and hipotesis.estado != RECHAZADA:
                        self.razonador.rechazar(hipotesis, ahora, "le dijeron que no es así")
                        resumen.rechazadas.append(hipotesis)
                for origen, destino in ((a, b), (b, a)):
                    resumen.rechazadas += self.razonador.invalidar(origen, destino, ahora)
            resumen.hipotesis += self.razonador.deducir(relaciones, ahora)

        self._asociar_con_senales_previas(evento.palabras, ahora_real)
        self._ultimo_mensaje = {"real": ahora_real, "palabras": evento.palabras, "pregunta": evento.es_pregunta,
                                "respuesta": bool(resumen.respuesta or resumen.ambigua)}
        self._anclar_gesto_pendiente(ahora_real)
        if evento.es_grito:
            self._aplicar_senal(instincts.SENALES["grito"], ahora, ahora_real)
        self.red.activar({c: 1.0 for c in resumen.conceptos}, ahora, ahora_real)
        self.emociones.sentir(self._evaluar_mensaje(evento, resumen), ahora_real, ahora)

        pensamientos = {h.id: self._pensamiento_de_hipotesis(h) for h in resumen.hipotesis}
        avisos = self._revisar_etapa()
        intencion, preguntada = self._elegir_respuesta(evento, pregunta, resumen, ahora, ahora_real)
        habla = self._decir(intencion, "respuesta")
        if preguntada and preguntada.id in pensamientos:
            pensamientos[preguntada.id].en_voz_alta = True
            pensamientos[preguntada.id].dicho = habla["texto"]
        if intencion.tipo == "confusion":
            self.emociones.sentir(Evaluacion("no sabe la respuesta", novedad=0.3, agrado=-0.1, control=0.1,
                                             detalle=intencion.detalle), ahora_real, ahora)

        self.memoria.registrar({
            "tipo": "mensaje",
            **evento.a_dict(),
            "texto": evento.texto,
            "conceptos": list(dict.fromkeys(resumen.conceptos)),
            "respuesta": habla["texto"],
        }, self.emociones.actual(ahora_real), ahora, ahora_real)

        salidas += [self._salida_pensamiento(p) for p in pensamientos.values()]
        return salidas + avisos + [habla] + self._revisar_etapa()

    def actuar(self, accion: str) -> list[dict]:
        """El dueño la acaricia, la alimenta, juega con ella, la regaña o la acuesta."""
        salidas = self._sincronizar()
        if accion == "dormir":
            return salidas + self._dormir("su dueño la acostó")
        if accion == "despertar":
            return salidas + self._despertar("se despertó porque su dueño la llamó")
        if accion in ("asentir", "negar"):
            return salidas + self._gesto_del_dueno(1 if accion == "asentir" else -1)
        senal = instincts.SENALES.get(accion)
        if senal is None or accion == "grito":
            return salidas
        ahora, ahora_real = self.reloj.tiempo, self.reloj_real()
        if not self.despierta:
            if accion != "regañar":
                if accion == "acariciar":
                    self.emociones.ajustar_relacion(0.01, 0.02)
                detalle = "Está dormida; sonríe entre sueños" if accion == "acariciar" else "Está dormida"
                return salidas + [self._decir(Intencion("dormida", detalle=detalle), "reaccion")]
            salidas += self._despertar("se despertó asustada por un regaño", brusco=True)

        if accion == "alimentar" and self.necesidades.saciedad >= 0.92:
            return salidas + self._rechazar_comida(ahora, ahora_real)
        self._contacto(ahora_real, 0)
        self.necesidades.recibir(senal)
        correccion = self._corregir_con_senal(senal, ahora, ahora_real)
        contexto = [p for _, p in self._palabras_recientes_en(ahora_real) if self.lexico.es_concepto(p)]
        self._aplicar_senal(senal, ahora, ahora_real)
        salidas += self._actividad_por_accion(accion, ahora_real)
        avisos = self._revisar_etapa()
        habla = self._decir(self._reaccion(senal, correccion, ahora), "reaccion")
        self.memoria.registrar({
            "tipo": "accion",
            "accion": accion,
            "palabras": [],
            "conceptos": list(dict.fromkeys(contexto)),
            "respuesta": habla["texto"],
            "momento": datetime.fromtimestamp(ahora_real).isoformat(timespec="seconds"),
        }, self.emociones.actual(ahora_real), ahora, ahora_real)
        return salidas + avisos + [habla] + self._revisar_etapa()

    def conectar(self) -> list[dict]:
        """Alguien abrió la página: si hacía rato que no la veía, te saluda y te recuerda."""
        salidas = self._sincronizar()
        ahora, ahora_real = self.reloj.tiempo, self.reloj_real()
        self._inicio_sesion = True
        if self.es_nueva:
            self.es_nueva = False
            self.ultima_interaccion_real = ahora_real
            intencion = Intencion("balbuceo", gesto="curiosidad", detalle="Acaba de nacer: no sabe ninguna palabra")
            return salidas + [self._decir(intencion, "nacimiento")]
        ausencia = ahora_real - self.ultima_interaccion_real
        if not self.despierta:
            return salidas
        salidas += self._atender(ahora_real, "te ve llegar")
        if ausencia < config.AUSENCIA_SALUDO_S:
            return salidas

        extrano = 1 - self.necesidades.compania
        agrado = (self.emociones.afecto - 0.15) * (0.8 + extrano)
        amenaza = 0.4 if self.emociones.confianza < 0.3 else 0.0
        self.emociones.sentir(Evaluacion("volviste", novedad=0.3, agrado=agrado, amenaza=amenaza, control=0.6,
                                         del_dueno=True, detalle=f"Pasaron {duracion(ausencia)} sin verte"),
                              ahora_real, ahora)
        self._contacto(ahora_real, 0.2)
        palabra = self.lexico.de_saludo(ahora) or (self.lexico.valorativa(+1, ahora) if not amenaza else None)
        intencion = Intencion("saludo", [palabra] if palabra else [], gesto="saludo" if not amenaza else "miedo",
                              detalle=f"Te reconoce al volver (confianza {self.emociones.confianza:.2f})")
        return salidas + self._recuerdo_de_bienvenida() + [self._decir(intencion, "saludo")]

    def latir(self) -> list[dict]:
        """Un latido del reloj interno: pasa el tiempo, su cuerpo hace cosas y, si está
        tranquila, piensa."""
        salidas = self._sincronizar()
        ahora_real = self.reloj_real()
        segundos = min(5.0, max(0.0, ahora_real - self._ultimo_latido_real))
        self._ultimo_latido_real = ahora_real
        if self.despierta:
            salidas += self._vivir_cuerpo(segundos, ahora_real)
        if self.despierta and ahora_real >= self._proximo_pensamiento:
            if ahora_real - self.ultima_interaccion_real >= config.SILENCIO_PARA_PENSAR_S:
                salidas += self._pensar()
            espera = config.PERIODO_PENSAMIENTO_S * self.rng.uniform(0.7, 1.4) / (0.6 + 0.8 * self.rasgos["curiosidad"])
            self._proximo_pensamiento = ahora_real + espera
        return salidas

    def adelantar(self, horas: float) -> list[dict]:
        """Herramienta de desarrollo: hace pasar tiempo de criatura de golpe."""
        salidas = self._sincronizar()
        vivido = self._vivir(horas * 3600, simulado=True)
        suenos = sum(1 for s in vivido if s["tipo"] == "habla" and s["intencion"] == "dormida")
        resumen = f"⏩ Pasaron {duracion(horas * 3600)} para {self.nombre}"
        if suenos:
            resumen += f"; durmió {suenos} {'vez' if suenos == 1 else 'veces'}"
        resumen += "." if self.despierta else " y ahora está dormida."
        pensamientos = [s for s in vivido if s["tipo"] == "pensamiento"]
        return salidas + [self._aviso(resumen)] + pensamientos[-1:]

    def ponerse_al_dia(self, desde_real: float) -> list[dict]:
        """Al cargarla, vive el tiempo que pasó con el servidor encendido."""
        self.reloj.transcurrido()
        segundos = max(0.0, self.reloj_real() - desde_real) * self.reloj.velocidad
        return self._vivir(segundos, simulado=True)

    # ── Paso del tiempo ──────────────────────────────────────────────────

    def _sincronizar(self) -> list[dict]:
        return self._vivir(self.reloj.transcurrido())

    def _vivir(self, segundos: float, simulado: bool = False) -> list[dict]:
        salidas = []
        acompanada = not simulado and self.reloj_real() - self.ultima_interaccion_real < 600
        while segundos > 1e-9:
            paso = min(segundos, config.PASO_VIDA_S)
            segundos -= paso
            self.reloj.sumar(paso)
            if simulado:
                self.emociones.dejar_pasar(paso)
            horas = paso / 3600
            protegida = 1.0 if self.comportamiento.actual.nombre == "esconderse" else 0.0
            if acompanada:
                protegida += self.emociones.confianza * self.emociones.vinculo.familiaridad
            self.necesidades.pasar(horas, self.despierta, protegida)
            self.emociones.vivir(horas, self.reloj_real(), acompanada)
            if self.despierta and self.necesidades.energia <= config.UMBRAL_DORMIRSE:
                salidas += self._dormir("se quedó dormida de cansancio")
            elif self.despierta and simulado and self.somnolencia() >= config.UMBRAL_SOMNOLENCIA:
                salidas += self._dormir("se fue a dormir")
            elif not self.despierta and self._descansada():
                salidas += self._despertar("despertó descansada")
        return salidas

    def hora_del_dia(self) -> float:
        """Su reloj del día: nació a la hora en que nació y sus horas pasan con su tiempo de vida."""
        nacio = datetime.fromtimestamp(self.nacimiento)
        return (nacio.hour + nacio.minute / 60 + self.reloj.tiempo / 3600) % 24

    def somnolencia(self) -> float:
        noche = 0.35 if instincts.es_de_noche(self.hora_del_dia()) else 0.0
        return (1 - self.necesidades.energia) + noche

    def _descansada(self) -> bool:
        """De noche sigue durmiendo; por la mañana despierta si ya descansó lo suficiente."""
        hora, energia = self.hora_del_dia(), self.necesidades.energia
        if self.reloj.tiempo - self._dormida_desde < 3600:
            return False
        if config.HORA_MANANA <= hora < config.HORA_MANANA + 3:
            return energia >= 0.75
        return energia >= config.UMBRAL_DESPERTARSE and not instincts.es_de_noche(hora)

    def _dormir(self, motivo: str) -> list[dict]:
        if not self.despierta:
            return []
        ahora = self.reloj.tiempo
        self.despierta = False
        identificador = self.suenos[-1].id + 1 if self.suenos else 1
        sueno = consolidar(identificador, self.lexico, self.red, self.memoria, self.ultimo_sueno, ahora, self.rng)
        self.suenos.append(sueno)
        self._suenos_sucios.add(sueno.id)
        self.ultimo_sueno = ahora
        self._dormida_desde = ahora
        self.sueno_por_contar = sueno.id
        self.pregunta_pendiente = None
        actividad = self.comportamiento.iniciar("dormir", "cama", motivo, self.reloj_real(), duracion=10**9)
        aviso = (f"🌙 {self.nombre} se durmió ({motivo}). Repasó {len(sueno.reforzados)} conceptos "
                 f"y atenuó {len(sueno.atenuados)} recuerdos poco usados.")
        return [self._salida_actividad(actividad), self._aviso(aviso),
                self._decir(Intencion("dormida", detalle="Consolida lo aprendido"), "sueno")]

    def _despertar(self, motivo: str, brusco: bool = False) -> list[dict]:
        if self.despierta:
            return []
        ahora, ahora_real = self.reloj.tiempo, self.reloj_real()
        self.despierta = True
        sueno = next((s for s in self.suenos if s.id == self.sueno_por_contar), None)
        if brusco:
            evaluacion = Evaluacion("despertar brusco", novedad=0.6, agrado=-0.3, amenaza=0.5, control=0.3)
        elif self.necesidades.energia < 0.6:
            evaluacion = Evaluacion("despertó cansada", agrado=-0.25, control=0.4,
                                    detalle=f"energía {self.necesidades.energia:.0%}")
        else:
            evaluacion = Evaluacion("despertó descansada", novedad=0.1, agrado=0.3, control=0.6)
        self.emociones.sentir(evaluacion, ahora_real, ahora)
        actividad = self.comportamiento.iniciar("quieta", None, "se está despertando", ahora_real, duracion=6)
        salidas = [self._salida_actividad(actividad), self._aviso(f"☀️ {self.nombre} {motivo}.")]
        if sueno:
            sueno.fin = ahora
            self._suenos_sucios.add(sueno.id)
            if not sueno.contado and sueno.conceptos:
                sueno.contado = True
                detalle = f"Soñó con {', '.join(sueno.conceptos)}: una mezcla de lo que repasó al dormir"
                pensamiento = self._registrar_pensamiento("sueno", sueno.conceptos, detalle)
                habla = self._decir(Intencion("sueno", sueno.conceptos, gesto="sonar", detalle=detalle), "sueno")
                pensamiento.en_voz_alta, pensamiento.dicho = True, habla["texto"]
                salidas += [self._salida_pensamiento(pensamiento), habla]
        self.sueno_por_contar = None
        return salidas

    # ── Pensamiento propio ───────────────────────────────────────────────

    def _pensar(self) -> list[dict]:
        ahora, ahora_real = self.reloj.tiempo, self.reloj_real()
        contexto = ContextoPensamiento(self.lexico, self.red, self.razonador, self.memoria, self.rasgos, ahora,
                                       self.necesidades.soledad, self.necesidades.aburrimiento,
                                       float(self.emociones.actual(ahora_real)[0]))
        idea = self.pensador.idear(contexto)
        if idea is None:
            if self.rng.random() < 0.2 + 0.4 * self.rasgos["locuacidad"]:
                return [self._decir(Intencion("balbuceo", detalle="Juega sola con sonidos"), "pensamiento")]
            return []
        for concepto in idea.contenido:
            self.red.reforzar_nodo(concepto, ahora, 0.1)
        if idea.tipo == "deduccion":
            self.emociones.sentir(Evaluacion("se le ocurrió algo", novedad=0.4, agrado=0.15, control=0.6,
                                             detalle=idea.explicacion), ahora_real, ahora)
        pensamiento = self._registrar_pensamiento(idea.tipo, idea.contenido, idea.explicacion, idea.pregunta)
        if not self.pensador.en_voz_alta(idea, contexto):
            return [self._salida_pensamiento(pensamiento)]
        if idea.hipotesis:
            self._marcar_preguntada(idea.hipotesis, ahora_real)
        habla = self._decir(idea.intencion(), "pensamiento")
        pensamiento.en_voz_alta, pensamiento.dicho = True, habla["texto"]
        return [self._salida_pensamiento(pensamiento), habla]

    def _registrar_pensamiento(self, tipo: str, contenido: list[str], explicacion: str,
                               pregunta: bool = False) -> Pensamiento:
        identificador = self.pensamientos[-1].id + 1 if self.pensamientos else 1
        pensamiento = Pensamiento(identificador, self.reloj.tiempo, self.reloj_real(), tipo, list(contenido),
                                  texto_conceptual(contenido, pregunta, tipo), explicacion)
        self.pensamientos.append(pensamiento)
        self._pensamientos_sucios.add(identificador)
        return pensamiento

    def _pensamiento_de_hipotesis(self, hipotesis: Hipotesis) -> Pensamiento:
        pregunta = hipotesis.confianza < config.UMBRAL_AFIRMAR
        explicacion = (f"Dedujo {hipotesis.camino.texto()} sin que se lo enseñaran "
                       f"(confianza {hipotesis.confianza:.2f})")
        return self._registrar_pensamiento("deduccion", [hipotesis.origen, hipotesis.destino], explicacion, pregunta)

    def _recuerdo_de_bienvenida(self) -> list[dict]:
        ahora = self.reloj.tiempo
        recientes = [e for e in self.memoria.recientes(30) if e.conceptos]
        if not recientes:
            return []
        episodio = max(recientes, key=lambda e: e.huella.valor(ahora) * (0.5 + e.intensidad))
        contenido = [c for c in dict.fromkeys(episodio.conceptos) if c in self.red.nodos][:3]
        if not contenido:
            return []
        pensamiento = self._registrar_pensamiento(
            RECUERDO, contenido, f"Al verte recordó el episodio #{episodio.id} ({episodio.resumen()})")
        return [self._salida_pensamiento(pensamiento)]

    # ── Cuerpo: comportamiento autónomo ──────────────────────────────────

    def _estado_corporal(self, ahora_real: float) -> EstadoCorporal:
        return EstadoCorporal(
            necesidades=self.necesidades,
            pad=self.emociones.actual(ahora_real),
            ambivalencia=self.emociones.ambivalencia(ahora_real),
            rasgos=self.rasgos,
            hora=self.hora_del_dia(),
            ignorada=min(1.0, (ahora_real - self.ultima_interaccion_real) / 120),
            afecto=self.emociones.afecto,
        )

    def _vivir_cuerpo(self, segundos: float, ahora_real: float) -> list[dict]:
        """Lo que hace su cuerpo cada latido: sigue con su actividad, la siente y,
        cuando termina (o algo urgente la interrumpe), elige otra."""
        actividad = self.comportamiento.actual
        self.comportamiento.pasar(segundos)
        if actividad.nombre in ESTIMULO:
            self.necesidades.estimular(ESTIMULO[actividad.nombre] * segundos)
        else:
            self.necesidades.aburrirse(segundos)
        if actividad.nombre == "esconderse":
            self.necesidades.tranquilizar(0.004 * segundos)
        elif actividad.nombre == "descansar":
            self.necesidades.energia = min(1.0, self.necesidades.energia + 0.0015 * segundos)

        estado = self._estado_corporal(ahora_real)
        urgente = self.comportamiento.urgente(estado)
        if urgente is None and not actividad.termino(ahora_real):
            return []
        salidas = self._terminar_actividad(actividad, ahora_real)
        if not self.despierta:
            return salidas
        if urgente:
            nueva = self.comportamiento.iniciar(urgente.nombre, urgente.objeto, urgente.motivo, ahora_real,
                                                ambivalente=estado.ambivalencia > 0)
        else:
            nueva = self.comportamiento.elegir(estado, ahora_real)
        return salidas + self._empezar_actividad(nueva, ahora_real)

    def _empezar_actividad(self, actividad: Actividad, ahora_real: float) -> list[dict]:
        """Lo que siente y dice al empezar algo por su cuenta."""
        ahora = self.reloj.tiempo
        nombre = actividad.nombre
        evaluacion = {
            "jugar": Evaluacion("juega sola", agrado=0.25, novedad=0.2, necesidad="aburrimiento"),
            "explorar": Evaluacion(f"explora {actividad.objeto}", agrado=0.1,
                                   novedad=0.4 * (1 - self.comportamiento.habituacion.get(actividad.objeto, 0) / 2),
                                   necesidad="aburrimiento"),
            "mirar_ventana": Evaluacion("mira por la ventana", agrado=0.1, novedad=0.15,
                                        calma=0.3 if instincts.es_de_noche(self.hora_del_dia()) else 0.0),
            "descansar": Evaluacion("descansa", agrado=0.1, control=0.6, calma=0.5),
            "esconderse": Evaluacion("se esconde", control=0.6, calma=0.3),
            "aburrirse": Evaluacion("se aburre", agrado=-0.1, calma=0.3),
        }.get(nombre)
        if evaluacion:
            evaluacion.detalle = actividad.motivo
            self.emociones.sentir(evaluacion, ahora_real, ahora)

        intencion = None
        if nombre == "pedir_comida":
            palabra = self.lexico.de_accion("alimentar", ahora)
            intencion = Intencion("pedir", [palabra] if palabra else [], detalle=actividad.motivo)
        elif nombre == "buscarte":
            palabra = self.lexico.para_llamar(ahora, self.ngramas.conteos.get(INICIO, {}))
            intencion = Intencion("llamar", [palabra] if palabra else [], detalle=actividad.motivo)
        elif nombre == "jugar" and self.rng.random() < 0.4 + 0.4 * self.rasgos["locuacidad"]:
            palabra = self.lexico.de_accion("jugar", ahora)
            intencion = Intencion("emocion", [palabra] if palabra else [], gesto="alegria", detalle=actividad.motivo)
        elif nombre == "explorar" and self.rng.random() < 0.3:
            intencion = Intencion("curiosear", detalle=actividad.motivo)
        elif nombre in ("esconderse", "aburrirse", "ir_a_dormir"):
            vocalizacion = {"esconderse": "gemido", "aburrirse": "suspiro", "ir_a_dormir": "bostezo"}[nombre]
            intencion = Intencion(vocalizacion, detalle=actividad.motivo)
        salidas = [self._salida_actividad(actividad)]
        if intencion:
            salidas.append(self._decir(intencion, "actividad"))
        return salidas

    def _terminar_actividad(self, actividad: Actividad, ahora_real: float) -> list[dict]:
        """Al terminar: se duerme si iba a la cama; se frustra si te buscó o pidió comida y nadie respondió."""
        ahora = self.reloj.tiempo
        ignorada = self.ultima_interaccion_real < actividad.inicio
        if actividad.nombre == "ir_a_dormir":
            return self._dormir(f"se fue a dormir sola: {actividad.motivo}")
        if actividad.nombre == "buscarte" and ignorada:
            self.comportamiento.frustrar()
            self.emociones.sentir(Evaluacion("no le hiciste caso", agrado=-0.25, necesidad="compania",
                                             detalle="te buscó y no respondiste"), ahora_real, ahora)
        elif actividad.nombre == "pedir_comida" and ignorada and self.necesidades.hambre > 0:
            self.emociones.sentir(Evaluacion("nadie le da de comer", agrado=-0.2, amenaza=0.05,
                                             detalle=actividad.motivo), ahora_real, ahora)
        return []

    def _atender(self, ahora_real: float, motivo: str) -> list[dict]:
        """El dueño interactúa: deja lo que hacía y lo mira (si duerme, no)."""
        if not self.despierta:
            return []
        actividad = self.comportamiento.atender(ahora_real, motivo, self.emociones.ambivalencia(ahora_real) > 0)
        return [self._salida_actividad(actividad)]

    def _actividad_por_accion(self, accion: str, ahora_real: float) -> list[dict]:
        if accion == "alimentar":
            actividad = self.comportamiento.iniciar("comer", "plato", "come lo que le diste", ahora_real, "dueño")
        elif accion == "jugar":
            actividad = self.comportamiento.iniciar("jugar", "pelota", "juega contigo", ahora_real, "dueño",
                                                    duracion=12)
        elif accion == "regañar" and self.necesidades.inseguridad >= 0.4:
            actividad = self.comportamiento.iniciar(
                "esconderse", "caja", f"el regaño la asustó (seguridad {self.necesidades.seguridad:.0%})", ahora_real)
        else:
            return self._atender(ahora_real, {"acariciar": "disfruta tu caricia",
                                              "regañar": "te mira asustada"}.get(accion, "te mira"))
        return [self._salida_actividad(actividad)]

    def _rechazar_comida(self, ahora: float, ahora_real: float) -> list[dict]:
        saciedad = self.necesidades.saciedad
        self._contacto(ahora_real, 0.02)
        self.emociones.sentir(Evaluacion("no tiene hambre", agrado=-0.05, control=0.6, del_dueno=True,
                                         detalle=f"saciedad {saciedad:.0%}"), ahora_real, ahora)
        salidas = self._atender(ahora_real, "no quiere comer")
        intencion = Intencion("negar", gesto="negar", detalle=f"No tiene hambre (saciedad {saciedad:.0%}): no quiere comer")
        return salidas + [self._decir(intencion, "reaccion")]

    @staticmethod
    def _salida_actividad(actividad: Actividad) -> dict:
        return {"tipo": "actividad", "datos": actividad.a_publico()}

    # ── Decisión de qué responder ────────────────────────────────────────

    def _elegir_respuesta(self, evento: Evento, pregunta: Frase | None, resumen: _Resumen, ahora: float,
                          ahora_real: float) -> tuple[Intencion, Hipotesis | None]:
        if pregunta:
            return responder(pregunta, self.lexico, self.red, self.razonador, ahora), None
        if resumen.respuesta:
            hipotesis, motivo = resumen.respuesta["hipotesis"], resumen.respuesta["motivo"]
            if resumen.respuesta["confirmada"]:
                return Intencion("celebrar", [hipotesis.origen, hipotesis.destino], tema=hipotesis.origen,
                                 detalle=f"Ahora sabe que {hipotesis.origen} → {hipotesis.destino} ({motivo})"), None
            return Intencion("negar", [hipotesis.destino], gesto="negar", tema=hipotesis.origen,
                             detalle=f"Ya no cree que {hipotesis.origen} → {hipotesis.destino} ({motivo})"), None
        if resumen.ambigua:
            hipotesis, respuesta = resumen.ambigua
            return Intencion("preguntar", [hipotesis.origen, hipotesis.destino], gesto="duda", tema=hipotesis.origen,
                             detalle=f"No sabe si «{respuesta}» quiere decir sí o no. "
                                     f"Asiente 👍 o niega 👎 para enseñárselo"), hipotesis
        if resumen.confirmadas:
            hipotesis = resumen.confirmadas[0]
            return Intencion("celebrar", [hipotesis.origen, hipotesis.destino], tema=hipotesis.origen,
                             detalle=f"¡Lo había deducido! Se lo confirmaron al enseñárselo: "
                                     f"{hipotesis.origen} → {hipotesis.destino}"), None
        reconocidas = [p for p in resumen.reconocidas if self.lexico.informatividad(p) >= config.UMBRAL_CONCEPTO]
        if reconocidas:
            forma = max(reconocidas, key=self.lexico.informatividad)
            veces = self.lexico.get(forma).huella.veces_aprendida
            return Intencion("reconocer", [forma], detalle=(
                f"«{forma}» estaba latente: lo reconoce a medias (lo había aprendido {veces} "
                f"{'vez' if veces == 1 else 'veces'}) y lo recupera más rápido que la primera vez")), None
        if resumen.hipotesis:
            hipotesis = max(resumen.hipotesis, key=lambda h: h.confianza)
            return self._preguntar_hipotesis(hipotesis, ahora_real), hipotesis
        if resumen.contradichas:
            relacion = resumen.contradichas[0]
            return Intencion("negar", [relacion.destino], gesto="confusion", tema=relacion.origen, detalle=(
                f"Contradicción: había aprendido {relacion.origen} → {relacion.destino} y ahora le dicen que no; "
                f"lo debilita (sin olvidar que alguna vez lo creyó)")), None
        if resumen.negadas:
            a, b = resumen.negadas[0]
            return Intencion("negar", [b], gesto="negar", tema=a,
                             detalle=f"Entendió que «{a}» y «{b}» no van juntos"), None
        pendiente = self._hipotesis_por_preguntar()
        if pendiente and self.rng.random() < 0.7:
            return self._preguntar_hipotesis(pendiente, ahora_real), pendiente
        forma = self._palabra_saliente(evento, ahora)
        if forma:
            return Intencion("imitar", [forma], detalle=f"Repite «{forma}», lo que más le llamó la atención"), None
        return Intencion("balbuceo", oidas=evento.palabras,
                         detalle="Todavía no domina ninguna palabra: balbucea imitando los sonidos"), None

    def _preguntar_hipotesis(self, hipotesis: Hipotesis, ahora_real: float) -> Intencion:
        self._marcar_preguntada(hipotesis, ahora_real)
        tipo = "deducir" if hipotesis.confianza >= config.UMBRAL_AFIRMAR else "preguntar"
        return Intencion(tipo, [hipotesis.origen, hipotesis.destino], tema=hipotesis.origen, detalle=(
            f"Dedujo {hipotesis.camino.texto()} (confianza {hipotesis.confianza:.2f}) y te lo pregunta"))

    def _marcar_preguntada(self, hipotesis: Hipotesis, ahora_real: float) -> None:
        hipotesis.preguntada = True
        self.razonador.sucias.add(hipotesis.id)
        self.pregunta_pendiente = {"hipotesis": hipotesis.id, "real": ahora_real}

    def _hipotesis_por_preguntar(self) -> Hipotesis | None:
        pendientes = [h for h in self.razonador.pendientes() if not h.preguntada]
        return max(pendientes, key=lambda h: h.confianza, default=None)

    def _palabra_saliente(self, evento: Evento, ahora: float) -> str | None:
        mejor, puntaje_mejor = None, 0.0
        for indice, forma in enumerate(dict.fromkeys(evento.palabras)):
            if not self.hablante.puede_usar(forma, self.etapa, ahora):
                continue
            palabra = self.lexico.get(forma)
            puntaje = (palabra.huella.valor(ahora) * (0.4 + self.lexico.informatividad(forma))
                       * (1 + 0.5 * max(0.0, palabra.valencia)) * (1.15 if indice == 0 else 1.0)
                       * self.rng.uniform(0.9, 1.1))
            if puntaje > puntaje_mejor:
                mejor, puntaje_mejor = forma, puntaje
        return mejor

    def _reaccion(self, senal: instincts.Senal, correccion: dict | None, ahora: float) -> Intencion:
        if correccion:
            hipotesis = correccion["hipotesis"]
            return Intencion("negar", [hipotesis.destino], gesto="negar", tema=hipotesis.origen,
                             detalle=f"Ya no cree que {hipotesis.origen} → {hipotesis.destino}: {correccion['motivo']}")
        signo = 1 if senal.valencia > 0 else -1
        palabra = self.lexico.de_accion(senal.nombre, ahora) or self.lexico.valorativa(signo, ahora)
        detalle = f"Reacción instintiva a «{senal.nombre}»"
        if palabra:
            detalle += f"; lo asocia con «{palabra}»"
        return Intencion("emocion", [palabra] if palabra else [], gesto=GESTOS_DE_ACCION.get(senal.nombre),
                         detalle=detalle)

    # ── Respuestas a sus preguntas (sí / no) ─────────────────────────────

    def _hipotesis_respondida(self, frase: Frase, ahora_real: float) -> Hipotesis | None:
        """¿Esta frase responde a la pregunta que acaba de hacer?"""
        pendiente = self.pregunta_pendiente
        if not pendiente or ahora_real - pendiente["real"] > config.VENTANA_RESPUESTA_S:
            return None
        hipotesis = self.razonador.hipotesis.get(pendiente["hipotesis"])
        if hipotesis is None or hipotesis.estado != PENDIENTE:
            return None
        palabras = frase.palabras
        if self.lexico.polaridad_de(palabras):
            return hipotesis
        if any(p == hipotesis.destino or p in self.red.parecidos(hipotesis.destino) for p in palabras):
            return hipotesis
        ajenas = [p for p in palabras if p not in (hipotesis.origen, hipotesis.destino) and self.lexico.es_concepto(p)]
        return hipotesis if len(palabras) <= 3 and not ajenas else None

    def _resolver(self, hipotesis: Hipotesis, frase: Frase, ahora: float, ahora_real: float) -> dict | None:
        """Interpreta la respuesta con lo que ya sabe: palabras de sí/no aprendidas, el tono
        emocional o que repitas la idea. Si no entiende la respuesta devuelve None: no adivina,
        espera que asientas 👍 o niegues 👎 y así aprende qué significan esas palabras."""
        palabras = frase.palabras
        polaridad = self.lexico.polaridad_de(palabras)
        tono = self._tono(palabras)
        eco = any(p == hipotesis.destino or p in self.red.parecidos(hipotesis.destino) for p in palabras)
        if polaridad >= config.UMBRAL_POLARIDAD:
            confirmada, motivo = True, "usó una palabra que significa que sí"
        elif polaridad <= -config.UMBRAL_POLARIDAD:
            confirmada, motivo = False, "usó una palabra que significa que no"
        elif tono <= -config.UMBRAL_VALORATIVA:
            confirmada, motivo = False, "le respondió en tono negativo"
        elif eco or tono >= config.UMBRAL_VALORATIVA:
            confirmada, motivo = True, "repitió la idea" if eco else "le respondió en tono positivo"
        else:
            return None

        if confirmada:
            self.razonador.confirmar(hipotesis, ahora, motivo)
            self.emociones.sentir(Evaluacion("aprendió algo que había deducido", novedad=0.2, agrado=0.35, control=0.8,
                                             detalle=f"{hipotesis.origen} → {hipotesis.destino}"), ahora_real, ahora)
            self.emociones.ajustar_relacion(0.01, 0.0)
        else:
            self.razonador.rechazar(hipotesis, ahora, motivo)
            self.emociones.sentir(Evaluacion("se equivocó", novedad=0.2, agrado=-0.15, control=0.4,
                                             detalle=f"{hipotesis.origen} → {hipotesis.destino}"), ahora_real, ahora)
        respuesta = [p for p in dict.fromkeys(palabras)
                     if not self.lexico.es_concepto(p) and p not in (hipotesis.origen, hipotesis.destino)]
        self.lexico.asociar_polaridad(respuesta, 1 if confirmada else -1)
        self.pregunta_pendiente = None
        self.ultima_resolucion = {"hipotesis": hipotesis.id, "real": ahora_real, "palabras": respuesta,
                                  "por_palabras": True, "confirmada": confirmada}
        return {"hipotesis": hipotesis, "confirmada": confirmada, "motivo": motivo}

    def _corregir_con_senal(self, senal: instincts.Senal, ahora: float, ahora_real: float) -> dict | None:
        """Un regaño justo después de una respuesta (o de su pregunta) significa "no"."""
        if senal.valencia >= 0:
            return None
        resolucion = self.ultima_resolucion
        if (resolucion and resolucion["confirmada"] and resolucion.get("por_palabras")
                and ahora_real - resolucion["real"] <= config.VENTANA_CORRECCION_S):
            hipotesis = self.razonador.hipotesis.get(resolucion["hipotesis"])
            self.ultima_resolucion = None
            if hipotesis:
                self.razonador.rechazar(hipotesis, ahora, "la regañaron justo después de aceptarlo")
                self.lexico.asociar_polaridad(resolucion["palabras"], -1, fuerza=1.6)
                return {"hipotesis": hipotesis, "motivo": "entendió que la respuesta era un no"}
        pendiente = self.pregunta_pendiente
        if pendiente and ahora_real - pendiente["real"] <= config.VENTANA_RESPUESTA_S:
            hipotesis = self.razonador.hipotesis.get(pendiente["hipotesis"])
            self.pregunta_pendiente = None
            if hipotesis and hipotesis.estado == PENDIENTE:
                self.razonador.rechazar(hipotesis, ahora, "la regañaron cuando lo preguntó")
                return {"hipotesis": hipotesis, "motivo": "la regañaron cuando lo preguntó"}
        return None

    # ── Gestos del dueño: 👍 asentir y 👎 negar ─────────────────────────

    def _gesto_del_dueno(self, signo: int) -> list[dict]:
        """Entender un gesto de sí o de no es innato, como sentir una caricia. Las palabras
        no: las aprende porque acompañan al gesto ("no" + 👎 → "no" significa no)."""
        ahora, ahora_real = self.reloj.tiempo, self.reloj_real()
        nombre = "asentiste" if signo > 0 else "negaste"
        if not self.despierta:
            return [self._decir(Intencion("dormida", detalle="Está dormida: no ve tu gesto"), "reaccion")]
        self._contacto(ahora_real, 0.02)
        correccion = self._corregir_con_gesto(signo, ahora, ahora_real)
        aprendidas = self._anclar_gesto(signo, ahora_real, correccion) if correccion else []

        if signo > 0:
            evaluacion = Evaluacion(nombre, agrado=0.25, novedad=0.05, control=0.7, del_dueno=True)
        else:
            evaluacion = Evaluacion(nombre, agrado=-0.1, novedad=0.15, control=0.35, del_dueno=True)
        evaluacion.detalle = correccion["explicacion"] if correccion else "no sabe a qué te refieres"
        self.emociones.sentir(evaluacion, ahora_real, ahora)

        salidas = self._atender(ahora_real, f"{nombre} y te mira")
        if correccion:
            intencion = correccion["intencion"]
            pensamiento = self._registrar_pensamiento("correccion", correccion["conceptos"], correccion["explicacion"])
            salidas.append(self._salida_pensamiento(pensamiento))
        else:
            intencion = Intencion("emocion", gesto="duda" if signo < 0 else "alegria",
                                  detalle=f"{nombre.capitalize()}, pero no dijo nada que puedas corregir ahora")
        if aprendidas:
            significado = "sí" if signo > 0 else "no"
            intencion.detalle += f". Asoció «{' '.join(aprendidas)}» con «{significado}»"
        habla = self._decir(intencion, "reaccion")
        self.memoria.registrar({
            "tipo": "accion",
            "accion": "asentir" if signo > 0 else "negar",
            "palabras": aprendidas,
            "conceptos": correccion["conceptos"] if correccion else [],
            "respuesta": habla["texto"],
            "momento": datetime.fromtimestamp(ahora_real).isoformat(timespec="seconds"),
        }, self.emociones.actual(ahora_real), ahora, ahora_real)
        return salidas + [habla]

    def _corregir_con_gesto(self, signo: int, ahora: float, ahora_real: float) -> dict | None:
        """Aplica el gesto a lo que estaba en juego, de lo más reciente a lo más general:
        una respuesta que acaba de interpretar, la pregunta que hizo o lo último que dijo."""
        nombre = "asentiste" if signo > 0 else "negaste"

        resolucion = self.ultima_resolucion
        if resolucion and ahora_real - resolucion["real"] <= config.VENTANA_CORRECCION_S:
            self.ultima_resolucion = None
            hipotesis = self.razonador.hipotesis.get(resolucion["hipotesis"])
            if hipotesis and resolucion["confirmada"] != (signo > 0):
                # Esas palabras significaban lo contrario de lo que creyó: se corrigen con fuerza.
                self.lexico.asociar_polaridad(resolucion["palabras"], signo, fuerza=1.6)
                if self._ultimo_mensaje:
                    self._ultimo_mensaje["anclado"] = True
                return self._resolver_con_gesto(hipotesis, signo, ahora, resolucion["real"],
                                                f"{nombre} justo después de que interpretara tu respuesta al revés")

        pendiente = self.pregunta_pendiente
        if pendiente and ahora_real - pendiente["real"] <= config.VENTANA_RESPUESTA_S:
            hipotesis = self.razonador.hipotesis.get(pendiente["hipotesis"])
            if hipotesis and hipotesis.estado == PENDIENTE:
                self.pregunta_pendiente = None
                self.ultima_resolucion = {"hipotesis": hipotesis.id, "real": ahora_real, "palabras": [],
                                          "por_palabras": False, "confirmada": signo > 0}
                return self._resolver_con_gesto(hipotesis, signo, ahora, pendiente["real"],
                                                f"{nombre} cuando te lo preguntó")

        dicho = self.ultimo_dicho
        if not dicho or ahora_real - dicho["real"] > config.VENTANA_RESPUESTA_S:
            return None
        self.ultimo_dicho = None
        tema, conceptos = dicho["tema"], dicho["conceptos"]
        if tema:
            pares = [(tema, c) for c in conceptos if c != tema]
        else:
            pares = list(zip(conceptos, conceptos[1:]))
        pares = [(a, b) for a, b in pares if a in self.red.nodos and b in self.red.nodos]
        if not pares:
            return None
        cambios = []
        for a, b in pares:
            hipotesis = [h for h in (self.razonador.por_par(a, b), self.razonador.por_par(b, a)) if h]
            if signo < 0:
                cambios += [f"{r.origen} → {r.destino}" for r in self.red.contradecir_par(a, b, ahora)]
                for origen, destino in ((a, b), (b, a)):
                    cambios += [f"hipótesis {h.origen} → {h.destino}"
                                for h in self.razonador.invalidar(origen, destino, ahora)]
                for h in hipotesis:
                    if h.estado != RECHAZADA:
                        self.razonador.rechazar(h, ahora, f"{nombre} cuando lo dijo")
                        cambios.append(f"hipótesis {h.origen} → {h.destino}")
            else:
                for origen, destino in ((a, b), (b, a)):
                    relacion = self.red.relacion(origen, destino)
                    if relacion:
                        relacion.huella.reforzar(ahora, 1.5)
                        self.red.sucias_relaciones.add((origen, destino))
                        cambios.append(f"{origen} → {destino}")
                for h in hipotesis:
                    if h.estado == PENDIENTE:
                        self.razonador.confirmar(h, ahora, f"{nombre} cuando lo dijo")
                        cambios.append(f"hipótesis {h.origen} → {h.destino}")
        a, b = pares[-1]
        involucrados = list(dict.fromkeys(c for par in pares for c in par))
        if signo < 0:
            explicacion = (f"Negaste lo que dijo sobre {', '.join(involucrados)}: debilitó "
                           f"{', '.join(cambios) if cambios else 'nada (no lo tenía guardado)'}")
            intencion = Intencion("negar", [b], gesto="negar", tema=a, detalle=explicacion)
        else:
            explicacion = (f"Asentiste a lo que dijo sobre {', '.join(involucrados)}: reforzó "
                           f"{', '.join(cambios) if cambios else 'nada nuevo'}")
            intencion = Intencion("celebrar", [a, b], tema=a, detalle=explicacion)
        return {"intencion": intencion, "explicacion": explicacion, "conceptos": involucrados, "desde": dicho["real"]}

    def _resolver_con_gesto(self, hipotesis: Hipotesis, signo: int, ahora: float, desde: float,
                            motivo: str) -> dict:
        origen, destino = hipotesis.origen, hipotesis.destino
        if signo > 0:
            self.razonador.confirmar(hipotesis, ahora, motivo)
            explicacion = f"Ahora sabe que {origen} → {destino} ({motivo})"
            intencion = Intencion("celebrar", [origen, destino], tema=origen, detalle=explicacion)
        else:
            self.razonador.rechazar(hipotesis, ahora, motivo)
            explicacion = f"Ya no cree que {origen} → {destino} ({motivo})"
            intencion = Intencion("negar", [destino], gesto="negar", tema=origen, detalle=explicacion)
        return {"intencion": intencion, "explicacion": explicacion, "conceptos": [origen, destino], "desde": desde}

    def _anclar_gesto(self, signo: int, ahora_real: float, correccion: dict) -> list[str]:
        """Las palabras de tu respuesta corta junto al gesto aprenden su significado. Solo
        cuenta lo que le respondiste a lo corregido (no lo que la hizo decirlo); si todavía no
        le respondiste nada, espera a lo que escribas enseguida."""
        mensaje, contenido = self._ultimo_mensaje, correccion["conceptos"]
        respondia = mensaje and (mensaje["respuesta"] or mensaje["real"] > correccion["desde"])
        if (respondia and not mensaje.get("anclado") and not mensaje["pregunta"] and len(mensaje["palabras"]) <= 3
                and 0 <= ahora_real - mensaje["real"] <= config.VENTANA_GESTO_S):
            mensaje["anclado"] = True
            palabras = [p for p in dict.fromkeys(mensaje["palabras"]) if p not in contenido]
            self.lexico.asociar_polaridad(palabras, signo, respuesta=not mensaje["respuesta"])
            return palabras
        self._gesto_pendiente = {"real": ahora_real, "signo": signo, "contenido": contenido}
        return []

    def _anclar_gesto_pendiente(self, ahora_real: float) -> None:
        gesto, mensaje = self._gesto_pendiente, self._ultimo_mensaje
        if not gesto or ahora_real - gesto["real"] > config.VENTANA_GESTO_S:
            self._gesto_pendiente = None
            return
        self._gesto_pendiente = None
        if not mensaje["pregunta"] and len(mensaje["palabras"]) <= 3:
            mensaje["anclado"] = True
            palabras = [p for p in dict.fromkeys(mensaje["palabras"]) if p not in gesto["contenido"]]
            self.lexico.asociar_polaridad(palabras, gesto["signo"], respuesta=not mensaje["respuesta"])

    def _negaciones(self, frase: Frase, conceptos: list[str]) -> frozenset[tuple[int, int]]:
        """Pares de conceptos separados por una palabra que aprendió que niega ("no")."""
        negadoras = [frase.posicion(p) for p in frase.palabras
                     if self.lexico.es_polar(p) and self.lexico.get(p).polaridad < 0]
        if not negadoras:
            return frozenset()
        posiciones = [frase.posicion(c) for c in conceptos]
        pares = set()
        for i in range(len(conceptos)):
            for j in range(i + 1, len(conceptos)):
                if posiciones[j] - posiciones[i] > config.DISTANCIA_HEBBIANA:
                    break
                if any(posiciones[i] < k < posiciones[j] for k in negadoras):
                    pares.add((i, j))
        return frozenset(pares)

    # ── Señales primarias y emoción ──────────────────────────────────────

    def _palabras_recientes_en(self, ahora_real: float, ventana: float = config.VENTANA_ASOCIACION_S):
        return [(ahora_real - t, p) for t, p in self._palabras_recientes if 0 <= ahora_real - t <= ventana]

    def _aplicar_senal(self, senal: instincts.Senal, ahora: float, ahora_real: float) -> None:
        # Anclaje: las palabras oídas hace poco se tiñen de la emoción de la señal.
        pesos: dict[str, float] = {}
        for edad, forma in self._palabras_recientes_en(ahora_real):
            peso = (1 - edad / config.VENTANA_ASOCIACION_S) * (0.3 + 0.7 * self.lexico.informatividad(forma))
            pesos[forma] = max(pesos.get(forma, 0.0), peso)
        self.lexico.asociar_senal(pesos, senal.valencia, senal.nombre)
        detalle = f"asoció {', '.join(sorted(pesos)) or 'nada'} con «{senal.nombre}»"
        self.emociones.sentir(Evaluacion(senal.nombre, novedad=senal.novedad, agrado=senal.agrado,
                                         amenaza=senal.amenaza, detalle=detalle, necesidad=senal.necesidad,
                                         del_dueno=True), ahora_real, ahora)
        self.emociones.ajustar_relacion(senal.confianza, senal.afecto)
        self._senales_recientes.append((ahora_real, senal))

    def _asociar_con_senales_previas(self, palabras: list[str], ahora_real: float) -> None:
        ventana = config.VENTANA_ASOCIACION_POSTERIOR_S
        for momento, senal in self._senales_recientes:
            edad = ahora_real - momento
            if 0 <= edad <= ventana:
                cercania = config.PESO_ASOCIACION_POSTERIOR * (1 - edad / ventana)
                pesos = {p: cercania * (0.3 + 0.7 * self.lexico.informatividad(p)) for p in set(palabras)}
                self.lexico.asociar_senal(pesos, senal.valencia, senal.nombre)

    def _tono(self, palabras: list[str]) -> float:
        fuertes = [v for v in (self.lexico.valencia(p) for p in dict.fromkeys(palabras)) if abs(v) >= 0.15]
        if not fuertes:
            return 0.0
        peso = sum(abs(v) for v in fuertes)
        return sum(v * abs(v) for v in fuertes) / peso * min(1.0, peso)

    def _evaluar_mensaje(self, evento: Evento, resumen: _Resumen) -> Evaluacion:
        total = max(1, len(evento.palabras))
        nuevas = len(resumen.nuevas) / total
        tono = self._tono(evento.palabras)
        novedad = nuevas + 0.4 * bool(resumen.hipotesis) + 0.3 * bool(resumen.reconocidas)
        control = 0.4 + 0.4 * (1 - nuevas)
        if resumen.contradichas:
            novedad += 0.2
            control -= 0.4
        return Evaluacion("le hablaron", novedad=min(1.0, novedad), agrado=0.5 * tono + 0.15,
                          control=max(0.0, control), necesidad="compania", del_dueno=True,
                          detalle=f"«{evento.texto[:40]}»: {len(resumen.nuevas)} palabra(s) nueva(s), tono {tono:+.2f}")

    def _intensidad(self, ahora_real: float) -> float:
        """Lo emocionante se aprende más rápido; el cansancio distrae."""
        pad = self.emociones.actual(ahora_real)
        emocion = (abs(pad[0]) + max(0.0, pad[1])) / 2
        return float((1 + 0.8 * emocion) * (0.6 + 0.4 * self.necesidades.energia))

    def _contacto(self, ahora_real: float, cantidad: float) -> None:
        self.necesidades.contacto(cantidad)
        self.ultima_interaccion_real = ahora_real

    # ── Salidas ──────────────────────────────────────────────────────────

    def _decir(self, intencion: Intencion, origen: str) -> dict:
        ahora, ahora_real = self.reloj.tiempo, self.reloj_real()
        emocion = self.emociones.instantanea(ahora_real)
        enunciado = self.hablante.decir(intencion, self.etapa, self.emociones.actual(ahora_real), ahora)
        for forma in enunciado.palabras:
            self.lexico.reforzar(forma, ahora, 0.3)
        conceptos = [c for c in intencion.conceptos if c in self.red.nodos]
        if intencion.tipo not in SIN_CONTENIDO and (len(conceptos) >= 2 or (conceptos and intencion.tema)):
            self.ultimo_dicho = {"tema": intencion.tema, "conceptos": conceptos, "real": ahora_real}
            pendiente = self.pregunta_pendiente
            hipotesis = self.razonador.hipotesis.get(pendiente["hipotesis"]) if pendiente else None
            if hipotesis and (intencion.tema, conceptos[-1]) != (hipotesis.origen, hipotesis.destino):
                self.pregunta_pendiente = None   # dijo otra cosa después: la pregunta quedó atrás
        return {"tipo": "habla", "origen": origen, **enunciado.a_dict(), "emocion": emocion,
                "pregunta": enunciado.texto.endswith("?")}

    def _aviso(self, texto: str) -> dict:
        return {"tipo": "aviso", "texto": texto}

    @staticmethod
    def _salida_pensamiento(pensamiento: Pensamiento) -> dict:
        return {"tipo": "pensamiento", "datos": pensamiento.a_publico()}

    def _revisar_etapa(self) -> list[dict]:
        activas = self.lexico.activas(self.reloj.tiempo)
        nueva = max((e for e, umbral in config.UMBRALES_ETAPA.items() if activas >= umbral), default=0)
        if nueva <= self.etapa:
            return []
        self.etapa = nueva
        return [self._aviso(f"🌱 ¡{self.nombre} pasó a la etapa {nueva}: {config.NOMBRES_ETAPA[nueva]}! "
                            f"({activas} palabras activas)")]

    # ── Vista pública ────────────────────────────────────────────────────

    def identidad(self) -> dict:
        return {
            "id": self.id,
            "nombre": self.nombre,
            "nacimiento": self.nacimiento,
            "rasgos": self.rasgos,
            "tono": instincts.tono_de_piel(self.semilla),
            "voz": instincts.voz_innata(self.semilla),
        }

    def estado_publico(self) -> dict:
        ahora, ahora_real = self.reloj.tiempo, self.reloj_real()
        activas = self.lexico.activas(ahora)
        return {
            "id": self.id,
            "nombre": self.nombre,
            "edad": ahora,
            "edad_texto": duracion(ahora),
            "ahora_real": ahora_real,
            "velocidad": self.reloj.velocidad,
            "despierta": self.despierta,
            **self.emociones.a_publico(ahora_real),
            "necesidades": self.necesidades.a_dict(),
            "etapa": {
                "numero": self.etapa,
                "nombre": config.NOMBRES_ETAPA[self.etapa],
                "activas": activas,
                "siguiente": config.UMBRALES_ETAPA.get(self.etapa + 1),
            },
            "rasgos": self.rasgos,
            "esperando_respuesta": bool(self.pregunta_pendiente),
            "hora": round(self.hora_del_dia(), 2),
            "noche": instincts.es_de_noche(self.hora_del_dia()),
            "somnolencia": round(self.somnolencia(), 3),
            "comportamiento": self.comportamiento.a_publico(),
        }

    def cerebro_publico(self) -> dict:
        ahora, ahora_real = self.reloj.tiempo, self.reloj_real()
        for nodo in self.red.nodos:
            self.red.valencia(nodo, self.lexico.valencia, ahora)
        return {
            "lexico": self.lexico.a_publico(ahora),
            **self.red.a_publico(ahora, ahora_real),
            "hipotesis": self.razonador.a_publico(ahora),
            "pensamientos": [p.a_publico() for p in self.pensamientos[-60:]][::-1],
            "suenos": [s.a_publico() for s in self.suenos[-5:]][::-1],
            "episodios": len(self.memoria.episodios),
        }

    def instantanea(self, cerebro: bool = False) -> list[dict]:
        mensajes = [{"tipo": "estado", "datos": self.estado_publico()}]
        if cerebro:
            mensajes.append({"tipo": "cerebro", "datos": self.cerebro_publico()})
        return mensajes
