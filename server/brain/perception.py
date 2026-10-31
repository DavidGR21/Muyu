"""Percepción: convierte lo que llega (texto o acciones) en eventos.

Separar el texto en unidades y notar el signo de pregunta son instintos: Muyu
divide lo que oye en palabras sin saber qué significan.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from server import config
from server.brain import instincts

LARGO_MAXIMO = 500
_PALABRA = re.compile(r"[^\W\d_]+")
_CORTES = ".!?\n"
_PAUSAS = ",;:—–()"


@dataclass
class Frase:
    texto: str
    palabras: list[str]
    es_pregunta: bool
    # forma → grafía con mayúscula si apareció como nombre propio en mitad de la
    # frase, o "" si apareció en minúscula (deja de considerarse nombre propio).
    grafias: dict[str, str] = field(default_factory=dict)
    # Distancia percibida de cada palabra al inicio: las pausas (comas) alejan.
    posiciones: list[int] = field(default_factory=list)

    def posicion(self, forma: str) -> int:
        indice = self.palabras.index(forma)
        return self.posiciones[indice] if self.posiciones else indice


@dataclass
class Evento:
    tipo: str                       # "mensaje" o "accion"
    momento: float                  # tiempo real (s)
    texto: str = ""
    frases: list[Frase] = field(default_factory=list)
    accion: str | None = None
    prosodia: dict = field(default_factory=dict)

    @property
    def palabras(self) -> list[str]:
        return [p for frase in self.frases for p in frase.palabras]

    @property
    def es_pregunta(self) -> bool:
        return any(frase.es_pregunta for frase in self.frases)

    @property
    def es_grito(self) -> bool:
        return self.prosodia.get("volumen", 0.0) >= instincts.UMBRAL_GRITO

    def a_dict(self) -> dict:
        return {
            "palabras": self.palabras,
            "es_pregunta": self.es_pregunta,
            "prosodia": self.prosodia,
            "accion": self.accion,
            "momento": datetime.fromtimestamp(self.momento).isoformat(timespec="seconds"),
        }


def _partir_frases(texto: str) -> list[str]:
    frases, actual = [], ""
    for caracter in texto:
        if caracter in _CORTES:
            if caracter != "\n":
                actual += caracter
            if actual.strip():
                frases.append(actual.strip())
            actual = ""
        else:
            actual += caracter
    if actual.strip():
        frases.append(actual.strip())
    return frases


def _frase(texto: str) -> Frase | None:
    palabras, grafias, posiciones = [], {}, []
    fin_anterior = pausas = 0
    for indice, coincidencia in enumerate(_PALABRA.finditer(texto)):
        original = coincidencia.group()
        forma = original.lower()
        palabras.append(forma)
        pausas += sum(texto[fin_anterior:coincidencia.start()].count(p) for p in _PAUSAS)
        posiciones.append(indice + pausas * config.PAUSA_EN_PALABRAS)
        fin_anterior = coincidencia.end()
        if indice > 0 and not original.isupper():
            grafias[forma] = original if original[0].isupper() else ""
    if not palabras:
        return None
    es_pregunta = "?" in texto or texto.lstrip().startswith("¿")
    return Frase(texto, palabras, es_pregunta, grafias, posiciones)


def percibir_texto(texto: str, ahora_real: float) -> Evento:
    texto = texto.strip()[:LARGO_MAXIMO]
    frases = [f for f in (_frase(t) for t in _partir_frases(texto)) if f]
    prosodia = {"volumen": instincts.volumen_de_texto(texto), "tono": "neutro", "velocidad": None}
    return Evento("mensaje", ahora_real, texto=texto, frases=frases, prosodia=prosodia)


def percibir_voz(texto: str, prosodia: dict, pregunta: bool, grito: bool, ahora_real: float) -> Evento:
    """Lo que oyó con el micrófono: el texto viene de Whisper (sin signos de pregunta);
    la pregunta y el grito los decide su propia prosodia."""
    evento = percibir_texto(texto, ahora_real)
    evento.tipo = "voz"
    evento.prosodia = {**prosodia, "volumen": 0.95 if grito else 0.5, "fuente": "voz"}
    if pregunta and evento.frases:
        evento.frases[-1].es_pregunta = True
    return evento


def percibir_accion(accion: str, ahora_real: float) -> Evento:
    return Evento("accion", ahora_real, accion=accion)
