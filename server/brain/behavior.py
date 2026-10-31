"""Comportamiento autónomo: lo que Muyu hace con su cuerpo cuando nadie le dice nada.

Cada actividad posible recibe un puntaje a partir de su estado (necesidades,
emoción, rasgos y hora del día). Elige entre las mejores con algo de azar, para
no ser predecible; si una necesidad se vuelve urgente interrumpe lo que esté
haciendo. Cada elección guarda su motivo para mostrarlo en el panel.

El servidor decide qué hace y por qué; el navegador la hace caminar hasta el
objeto y la anima. Los objetos de la habitación se llaman igual en los dos lados.
"""

from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass

import numpy as np

from server import config
from server.brain.instincts import Necesidades, es_de_noche

OBJETOS = ("cama", "plato", "pelota", "cojin", "caja", "ventana", "planta")
NOMBRES_OBJETO = {
    "cama": "su cama", "plato": "su plato", "pelota": "la pelota", "cojin": "el cojín", "caja": "la caja",
    "ventana": "la ventana", "planta": "la planta", "frente": "ti",
}
DESCRIPCIONES = {
    "quieta": "Se queda tranquila", "explorar": "Explora", "jugar": "Juega con la pelota",
    "mirar_ventana": "Mira por la ventana", "descansar": "Descansa en el cojín", "pedir_comida": "Te pide comida",
    "buscarte": "Te busca", "esconderse": "Se esconde", "aburrirse": "Se aburre", "ir_a_dormir": "Se va a dormir",
    "atenderte": "Te presta atención", "comer": "Come", "dormir": "Duerme",
}
DURACIONES = {
    "quieta": (6, 12), "explorar": (8, 14), "jugar": (12, 20), "mirar_ventana": (8, 14), "descansar": (12, 22),
    "pedir_comida": (10, 14), "buscarte": (10, 16), "esconderse": (12, 24), "aburrirse": (10, 16),
    "ir_a_dormir": (5, 5), "comer": (7, 7), "atenderte": (config.ATENCION_S, config.ATENCION_S),
    "dormir": (10**9, 10**9),
}
URGENTES = {"pedir_comida", "esconderse", "ir_a_dormir"}
# Cuánto le quita el aburrimiento cada segundo de actividad.
ESTIMULO = {"jugar": 0.03, "explorar": 0.02, "mirar_ventana": 0.008, "comer": 0.01, "atenderte": 0.0}


@dataclass
class Actividad:
    nombre: str
    objeto: str | None
    inicio: float           # tiempo real
    duracion: float         # segundos reales
    motivo: str
    ambivalente: bool = False
    iniciativa: str = "propia"      # propia | dueño

    def termino(self, ahora_real: float) -> bool:
        return ahora_real - self.inicio >= self.duracion

    def a_publico(self) -> dict:
        return {
            "nombre": self.nombre,
            "descripcion": DESCRIPCIONES.get(self.nombre, self.nombre),
            "objeto": self.objeto,
            "inicio": self.inicio,
            "duracion": min(self.duracion, 10**6),
            "motivo": self.motivo,
            "ambivalente": self.ambivalente,
            "iniciativa": self.iniciativa,
        }


@dataclass(frozen=True)
class Opcion:
    nombre: str
    objeto: str | None
    puntaje: float
    motivo: str


@dataclass
class EstadoCorporal:
    """Lo que el cuerpo sabe de sí mismo para decidir qué hacer."""

    necesidades: Necesidades
    pad: np.ndarray
    ambivalencia: float
    rasgos: dict[str, float]
    hora: float
    ignorada: float = 0.0       # 0..1: cuánto hace que nadie le hace caso estando tú ahí
    afecto: float = 0.3


class Comportamiento:
    def __init__(self, rng: random.Random, ahora_real: float) -> None:
        self.rng = rng
        self.actual = Actividad("quieta", None, ahora_real, 5, "acaba de llegar")
        self.historial: deque[Actividad] = deque(maxlen=12)
        self.habituacion: dict[str, float] = {}     # objeto → qué tan visto lo tiene (0..1)
        self.frustracion = 0.0                     # te buscó y no le hiciste caso

    # ── Elegir qué hacer ─────────────────────────────────────────────────

    def opciones(self, e: EstadoCorporal) -> list[Opcion]:
        n, r = e.necesidades, e.rasgos
        placer, activacion, dominancia = (float(x) for x in e.pad)
        noche = es_de_noche(e.hora)
        somnolencia = (1 - n.energia) + (0.35 if noche else 0.0)
        miedo = 3 * max(0.0, -placer) * max(0.0, activacion) * max(0.0, -dominancia)
        tristeza = max(0.0, -placer) * max(0.0, -activacion)
        activa = 1 - n.cansancio
        objeto, novedad = self._mas_novedoso()

        opciones = [Opcion("quieta", None, 0.25 + 0.15 * max(0.0, -activacion),
                           "está tranquila y mira alrededor")]
        if somnolencia >= 0.45:
            opciones.append(Opcion("ir_a_dormir", "cama", 0.3 + somnolencia,
                                   f"tiene sueño (energía {n.energia:.0%}{', es de noche' if noche else ''})"))
        if n.saciedad < 0.5:
            opciones.append(Opcion("pedir_comida", "plato", 0.3 + 1.4 * n.hambre,
                                   f"tiene hambre (saciedad {n.saciedad:.0%})"))
        if n.inseguridad > 0 or miedo > 0.2:
            opciones.append(Opcion("esconderse", "caja", 0.2 + 1.2 * n.inseguridad + 0.6 * miedo,
                                   f"se siente insegura (seguridad {n.seguridad:.0%})"))
        opciones += [
            Opcion("buscarte", "frente",
                   0.1 + 1.1 * n.soledad + 0.6 * e.ignorada * e.afecto - 0.5 * self.frustracion,
                   "se siente sola" if n.soledad > 0.3 else "quiere que le hagas caso"),
            Opcion("jugar", "pelota",
                   0.1 + 0.9 * n.aburrimiento * activa + 0.3 * max(0.0, placer) + 0.15 * max(0.0, activacion)
                   - 0.6 * n.hambre - 0.8 * n.inseguridad,
                   "se aburre y tiene ganas de jugar" if n.aburrimiento > 0.4 else "está de buen humor"),
            Opcion("explorar", objeto,
                   0.1 + 0.5 * r["curiosidad"] * novedad + 0.4 * n.aburrimiento * activa - 0.6 * n.inseguridad,
                   f"siente curiosidad por {NOMBRES_OBJETO[objeto]}"),
            Opcion("mirar_ventana", "ventana", 0.12 + 0.3 * n.aburrimiento + 0.25 * n.soledad + (0.15 if noche else 0),
                   "mira las estrellas" if noche else "mira qué pasa afuera"),
            Opcion("descansar", "cojin", 0.08 + 0.9 * n.cansancio + 0.25 * max(0.0, -activacion),
                   "está cansada" if n.cansancio > 0.2 else "quiere descansar un rato"),
            Opcion("aburrirse", None,
                   (0.7 * n.aburrimiento + 0.3 * tristeza) * (1 - max(0.0, placer)) * (1.0 if activacion < 0 else 0.5),
                   "se aburre y no sabe qué hacer"),
        ]
        return opciones

    def elegir(self, estado: EstadoCorporal, ahora_real: float) -> Actividad:
        opciones = self.opciones(estado)
        pesos = []
        for opcion in opciones:
            peso = max(0.0, opcion.puntaje) ** 3
            if opcion.nombre == self.actual.nombre and opcion.nombre not in URGENTES:
                peso *= 0.4        # variar: no repetir lo mismo una y otra vez
            pesos.append(peso)
        if not any(pesos):
            return self.iniciar("quieta", None, "no tiene ganas de nada", ahora_real)
        opcion = self.rng.choices(opciones, weights=pesos)[0]
        return self.iniciar(opcion.nombre, opcion.objeto, opcion.motivo, ahora_real,
                            ambivalente=estado.ambivalencia > 0)

    def urgente(self, estado: EstadoCorporal) -> Opcion | None:
        """Una necesidad tan fuerte que interrumpe lo que esté haciendo por su cuenta.
        Si ya atiende algo urgente, solo la interrumpe otra urgencia mucho mayor."""
        if self.actual.iniciativa == "dueño" or self.actual.nombre == "dormir":
            return None
        opciones = self.opciones(estado)
        urgentes = [o for o in opciones if o.nombre in URGENTES and o.puntaje >= config.UMBRAL_URGENCIA]
        mejor = max(urgentes, key=lambda o: o.puntaje, default=None)
        if mejor is None or self.actual.nombre not in URGENTES:
            return mejor
        actual = next((o.puntaje for o in opciones if o.nombre == self.actual.nombre), 0.0)
        return mejor if mejor.nombre != self.actual.nombre and mejor.puntaje >= actual + 0.5 else None

    # ── Iniciar y llevar la cuenta ───────────────────────────────────────

    def iniciar(self, nombre: str, objeto: str | None, motivo: str, ahora_real: float,
                iniciativa: str = "propia", ambivalente: bool = False, duracion: float | None = None) -> Actividad:
        if duracion is None:
            minimo, maximo = DURACIONES.get(nombre, (8, 12))
            duracion = self.rng.uniform(minimo, maximo)
        if self.actual.nombre not in ("atenderte", "dormir"):
            self.historial.appendleft(self.actual)
        self.actual = Actividad(nombre, objeto, ahora_real, duracion, motivo, ambivalente, iniciativa)
        if nombre == "explorar" and objeto:
            self.habituacion[objeto] = min(1.0, self.habituacion.get(objeto, 0.0) + 0.5)
        return self.actual

    def atender(self, ahora_real: float, motivo: str, ambivalente: bool = False) -> Actividad:
        """El dueño interactúa: deja lo que hace y lo mira (por un rato)."""
        self.frustracion = 0.0
        return self.iniciar("atenderte", "frente", motivo, ahora_real, "dueño", ambivalente)

    def frustrar(self) -> None:
        self.frustracion = min(1.0, self.frustracion + 0.5)

    def pasar(self, segundos_reales: float) -> None:
        """Lo explorado vuelve a ser novedoso con el tiempo; la frustración se olvida."""
        olvido = 0.5 ** (segundos_reales / 600)
        for objeto in self.habituacion:
            self.habituacion[objeto] *= olvido
        self.frustracion *= 0.5 ** (segundos_reales / 180)

    def _mas_novedoso(self) -> tuple[str, float]:
        novedades = {objeto: 1 - self.habituacion.get(objeto, 0.0) for objeto in OBJETOS}
        maximo = max(novedades.values())
        candidatos = [o for o, n in novedades.items() if n >= maximo - 0.05]
        objeto = self.rng.choice(candidatos)
        return objeto, novedades[objeto]

    def a_publico(self) -> dict:
        return {"actual": self.actual.a_publico(), "historial": [a.a_publico() for a in self.historial]}
