"""Instintos: lo único que Muyu trae programado al nacer.

Son mecanismos, no conocimiento: cómo reaccionar a una caricia o a un grito,
cómo notar que dos palabras suenan parecido, a qué palabras prestar atención
antes de saber nada o cómo bajan sus necesidades. Ninguna palabra, hecho ni
opinión viene de aquí.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass

import numpy as np

from server import config

RASGOS = ("curiosidad", "timidez", "terquedad", "sensibilidad", "locuacidad")


def rasgos_innatos(semilla: int) -> dict[str, float]:
    """Temperamento base. Dos criaturas criadas igual no terminan idénticas."""
    rng = np.random.default_rng(semilla)
    return {rasgo: round(float(rng.beta(2.2, 2.2)), 3) for rasgo in RASGOS}


def tono_de_piel(semilla: int) -> int:
    """Color innato (tono HSL) con el que se dibuja a la criatura."""
    return int(np.random.default_rng(semilla + 1).integers(70, 200))


# ── Señales primarias ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class Senal:
    """Estímulo que se siente sin necesidad de entender palabras."""

    nombre: str
    valencia: float         # signo emocional: ancla el significado de las palabras cercanas
    agrado: float           # para la evaluación cognitiva
    amenaza: float
    novedad: float
    confianza: float        # cambio inmediato en la relación con el dueño
    afecto: float
    compania: float = 0.0   # cuánto llena cada necesidad
    energia: float = 0.0
    saciedad: float = 0.0
    seguridad: float = 0.0
    estimulo: float = 0.0
    necesidad: str | None = None    # la necesidad a la que responde (si la tiene, importa más)


SENALES = {
    "acariciar": Senal("acariciar", 1.0, 0.6, 0.0, 0.05, 0.03, 0.04, compania=0.15, seguridad=0.08,
                       necesidad="compania"),
    "alimentar": Senal("alimentar", 0.8, 0.5, 0.0, 0.10, 0.02, 0.03, compania=0.05, energia=0.05, saciedad=0.35,
                       necesidad="hambre"),
    "jugar": Senal("jugar", 0.7, 0.5, 0.0, 0.30, 0.02, 0.04, compania=0.15, energia=-0.05, estimulo=0.45,
                   necesidad="aburrimiento"),
    "regañar": Senal("regañar", -1.0, -0.6, 0.6, 0.20, -0.06, -0.03, seguridad=-0.1),
    # Un grito (en texto: escribir en mayúsculas) asusta aunque las palabras sean amables.
    "grito": Senal("grito", -0.6, -0.3, 0.7, 0.30, -0.03, -0.01, seguridad=-0.1),
    # Con voz (fase 3): una voz suave y aguda suena a cariño; fuerte y grave, a regaño.
    "voz_suave": Senal("voz_suave", 0.6, 0.35, 0.0, 0.05, 0.01, 0.03, compania=0.05, seguridad=0.06,
                       necesidad="compania"),
    "voz_firme": Senal("voz_firme", -0.5, -0.3, 0.3, 0.10, -0.02, -0.01, seguridad=-0.04),
}

# Asentir y negar son gestos del dueño que Muyu entiende sin palabras, como una
# caricia: así puede aprender qué palabras significan "sí" y "no".
ACCIONES = ("acariciar", "alimentar", "jugar", "regañar", "dormir", "despertar", "asentir", "negar")

UMBRAL_GRITO = 0.75


def volumen_de_texto(texto: str) -> float:
    """El "volumen" de un texto: mayúsculas y signos de exclamación."""
    letras = [c for c in texto if c.isalpha()]
    mayusculas = sum(c.isupper() for c in letras) / len(letras) if len(letras) >= 4 else 0.0
    exclamaciones = min(texto.count("!"), 3)
    return round(min(1.0, 0.3 + 0.5 * mayusculas + 0.1 * exclamaciones), 3)


# ── Percepción de palabras ────────────────────────────────────────────────

def saliencia(palabra: str) -> float:
    """Atención innata a una palabra antes de saber nada de ella.

    Como en los bebés, las palabras cortas (casi siempre átonas) llaman menos la
    atención que las largas. Con la experiencia manda la informatividad aprendida.
    """
    largo = len(palabra)
    if largo <= 2:
        return 0.25
    if largo == 3:
        return 0.45
    return 0.8


def parecido_de_forma(a: str, b: str) -> float:
    """Dos palabras que empiezan igual "suenan" parecido (quema ≈ quemar)."""
    if a == b:
        return 0.0
    prefijo = len(os.path.commonprefix([a, b]))
    if prefijo < config.PREFIJO_FORMA_MIN:
        return 0.0
    similitud = prefijo / max(len(a), len(b))
    return round(similitud, 3) if similitud >= config.SIMILITUD_FORMA_MIN else 0.0


# ── Necesidades ───────────────────────────────────────────────────────────

@dataclass
class Necesidades:
    """Lo que el cuerpo pide. Energía, saciedad y compañía bajan con el tiempo de la
    criatura; la seguridad cae con los sustos y vuelve sola, más rápido si se siente
    protegida; el aburrimiento (necesidad de estímulo) crece en tiempo real cuando
    no pasa nada interesante."""

    energia: float = 1.0
    compania: float = 0.7
    saciedad: float = 0.8
    seguridad: float = 0.85
    aburrimiento: float = 0.0

    def pasar(self, horas: float, despierta: bool, protegida: float = 0.0) -> None:
        if despierta:
            self.energia -= horas / config.HORAS_ENERGIA_DESPIERTA
            self.saciedad -= horas / config.HORAS_SACIEDAD
        else:
            self.energia += horas / config.HORAS_RECUPERAR_DURMIENDO
            self.saciedad -= horas / (2 * config.HORAS_SACIEDAD)
        self.compania -= horas / config.HORAS_COMPANIA
        recuperacion = 1 - math.exp(-horas * (1 + 2 * protegida) / config.HORAS_RECUPERAR_SEGURIDAD)
        self.seguridad += (config.SEGURIDAD_EN_CALMA - self.seguridad) * recuperacion
        self._acotar()

    def recibir(self, senal: Senal) -> None:
        self.compania += senal.compania
        self.energia += senal.energia
        self.saciedad += senal.saciedad
        self.seguridad += senal.seguridad
        self.aburrimiento -= senal.estimulo
        self._acotar()

    def contacto(self, cantidad: float) -> None:
        self.compania += cantidad
        self._acotar()

    def aburrirse(self, segundos_reales: float) -> None:
        self.aburrimiento += segundos_reales / config.SEGUNDOS_PARA_ABURRIRSE
        self._acotar()

    def estimular(self, cantidad: float) -> None:
        self.aburrimiento -= cantidad
        self._acotar()

    def asustar(self, amenaza: float) -> None:
        self.seguridad -= 0.22 * amenaza
        self._acotar()

    def tranquilizar(self, cantidad: float) -> None:
        self.seguridad += cantidad
        self._acotar()

    # ── Lecturas ─────────────────────────────────────────────────────────

    @property
    def soledad(self) -> float:
        return max(0.0, 0.5 - self.compania) / 0.5

    @property
    def cansancio(self) -> float:
        return max(0.0, 0.35 - self.energia) / 0.35

    @property
    def hambre(self) -> float:
        return max(0.0, 0.5 - self.saciedad) / 0.5

    @property
    def inseguridad(self) -> float:
        return max(0.0, 0.6 - self.seguridad) / 0.6

    def deficit(self, necesidad: str) -> float:
        """Cuánto le falta (0 = nada, 1 = todo): lo que sirve para eso le importa más."""
        return {
            "energia": 1 - self.energia,
            "compania": 1 - self.compania,
            "hambre": 1 - self.saciedad,
            "seguridad": 1 - self.seguridad,
            "aburrimiento": self.aburrimiento,
        }.get(necesidad, 0.0)

    def efecto_emocional(self) -> np.ndarray:
        """Desplazamiento de la línea base emocional (PAD) que producen las necesidades."""
        placer = (-0.35 * self.soledad - 0.1 * self.cansancio - 0.3 * self.hambre - 0.3 * self.inseguridad
                  - 0.15 * self.aburrimiento)
        activacion = -0.4 * self.cansancio + 0.2 * self.hambre + 0.25 * self.inseguridad - 0.2 * self.aburrimiento
        dominancia = -0.35 * self.inseguridad
        return np.array([placer, activacion, dominancia])

    def _acotar(self) -> None:
        for nombre in ("energia", "compania", "saciedad", "seguridad", "aburrimiento"):
            setattr(self, nombre, min(1.0, max(0.0, getattr(self, nombre))))

    def a_dict(self) -> dict:
        return {nombre: round(getattr(self, nombre), 4)
                for nombre in ("energia", "compania", "saciedad", "seguridad", "aburrimiento")}


# ── Reloj del día ─────────────────────────────────────────────────────────

def es_de_noche(hora: float) -> bool:
    return hora >= config.HORA_NOCHE or hora < config.HORA_MANANA


def voz_innata(semilla: int) -> dict:
    """Cada criatura nace con su propio timbre: tono base, brillo y ritmo."""
    rng = np.random.default_rng(semilla + 2)
    return {
        "tono": int(rng.integers(300, 520)),
        "brillo": round(float(rng.uniform(0.3, 0.9)), 3),
        "ritmo": round(float(rng.uniform(0.85, 1.2)), 3),
    }
