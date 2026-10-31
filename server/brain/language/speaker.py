"""El hablante: convierte una intención (qué quiere decir) en una frase según su etapa.

El razonamiento decide el contenido; aquí solo se decide cómo decirlo con las
palabras que ya domina:

* Etapa 0: balbuceo.
* Etapa 1: imitación, una sola palabra que oyó mucho.
* Etapa 2: palabra-frase; puede encadenar palabras sueltas ("quema… duele").
* Etapa 3: combina dos palabras en una frase ("fuego duele").

Solo usa palabras activas o tenues; las tenues las dice con duda.
"""

from __future__ import annotations

import random
import re
from dataclasses import asdict, dataclass, field

import numpy as np

from server import config
from server.brain.emotions import etiqueta_de
from server.brain.importance import ACTIVO, LATENTE, TENUE
from server.brain.language.babble import VOCALIZACIONES, balbucear, vocalizar
from server.brain.language.ngram import ModeloNgramas
from server.brain.lexicon import Lexico

MAXIMO_PALABRAS = {1: 1, 2: 2, 3: 3}
TIPOS_PREGUNTA = {"preguntar", "dudar", "confusion", "reconocer", "recordar_dudoso", "llamar", "curiosear"}
TIPOS_DE_CONTENIDO = {"afirmar", "negar", "describir", "opinar", "recordar", "deducir", "sueno"}
TIPOS_EXCLAMATIVOS = {"celebrar", "saludo", "emocion", "imitar", "pedir"}
VOCALES_ALARGABLES = "aeiouáéíóú"
_PRIMERA_PALABRA = re.compile(r"[^\W\d_]+")
GESTOS = {
    "afirmar": "asentir",
    "celebrar": "asentir",
    "negar": "negar",
    "dudar": "duda",
    "preguntar": "duda",
    "confusion": "confusion",
    "reconocer": "reconocer",
    "recordar_dudoso": "reconocer",
    "reencuentro": "reconocer",
    "deducir": "curiosidad",
    "sueno": "sonar",
    "saludo": "saludo",
    "dormida": "dormir",
    "pedir": "pedir",
    "llamar": "saludo",
    "curiosear": "curiosidad",
    "gemido": "miedo",
    "suspiro": "tristeza",
    "bostezo": "dormir",
}
GESTOS_EMOCIONALES = {
    "alegría": "alegria",
    "contento": "alegria",
    "miedo": "miedo",
    "tristeza": "tristeza",
    "curiosidad": "curiosidad",
    "confusión": "confusion",
    "sorpresa": "sobresalto",
    "enojo": "enojo",
}


@dataclass
class Intencion:
    tipo: str
    conceptos: list[str] = field(default_factory=list)
    seguridad: float = 1.0
    gesto: str | None = None
    detalle: str = ""
    oidas: list[str] = field(default_factory=list)   # sonidos que imita al balbucear
    tema: str | None = None     # de qué concepto habla (para saber qué corregir si le dicen que no)


@dataclass
class Enunciado:
    texto: str
    gesto: str | None
    palabras: list[str]
    etapa: int
    intencion: str
    detalle: str

    def a_dict(self) -> dict:
        return asdict(self)


def _capitalizar(texto: str) -> str:
    for indice, caracter in enumerate(texto):
        if caracter.isalpha():
            return texto[:indice] + caracter.upper() + texto[indice + 1:]
    return texto


def gesto_emocional(pad) -> str | None:
    return GESTOS_EMOCIONALES.get(etiqueta_de(np.asarray(pad, dtype=float)))


def matizar(texto: str, pad) -> str:
    """Las palabras dicen la misma emoción que el cuerpo: con miedo tartamudea,
    con alegría alarga la última vocal y con tristeza o cansancio se apaga."""
    placer, activacion, dominancia = (float(x) for x in pad)
    if placer < -0.3 and activacion > 0.35 and dominancia < -0.15:
        primera = _PRIMERA_PALABRA.search(texto)
        if primera:
            letra = primera.group()[0]
            return texto[:primera.start()] + f"{letra}-{letra.lower()}" + texto[primera.start() + 1:]
        return texto
    if placer > 0.45 and activacion > 0.3 and texto.endswith("!"):
        for indice in range(len(texto) - 2, -1, -1):
            if texto[indice].lower() in VOCALES_ALARGABLES:
                return texto[:indice + 1] + texto[indice].lower() + texto[indice + 1:]
        return texto
    if placer < -0.25 and activacion < 0.1:
        texto = texto.replace("¡", "").replace("!", "")
        if not texto.endswith(("…", "?")):
            texto += "…"
    return texto


class Hablante:
    def __init__(self, lexico: Lexico, ngramas: ModeloNgramas, inventario: list[str], rng: random.Random) -> None:
        self.lexico = lexico
        self.ngramas = ngramas
        self.inventario = inventario
        self.rng = rng

    def puede_usar(self, forma: str | None, etapa: int, ahora: float) -> bool:
        if etapa <= 0 or not forma:
            return False
        palabra = self.lexico.get(forma)
        if palabra is None:
            return False
        estado = palabra.huella.estado(ahora)
        if estado == LATENTE:
            return False
        if etapa == 1:
            return estado == ACTIVO or palabra.frecuencia >= config.FRECUENCIA_IMITACION
        return True

    def decir(self, intencion: Intencion, etapa: int, pad, ahora: float) -> Enunciado:
        tipo = intencion.tipo
        if tipo == "dormida":
            return Enunciado("Zzz…", "dormir", [], etapa, tipo, intencion.detalle)
        gesto = intencion.gesto or GESTOS.get(tipo) or gesto_emocional(pad)
        if tipo in VOCALIZACIONES:
            return Enunciado(vocalizar(tipo, self.rng), gesto, [], etapa, tipo, intencion.detalle)
        pregunta = tipo in TIPOS_PREGUNTA or intencion.seguridad < 0.4
        palabras = self._elegir(intencion, etapa, ahora)
        if not palabras:
            if tipo in ("reconocer", "recordar_dudoso", "reencuentro"):
                texto = "¿Mm…?"
            else:
                texto = balbucear(self.rng, self.inventario, pad, pregunta, intencion.oidas or intencion.conceptos)
            return Enunciado(texto, gesto, [], etapa, tipo, intencion.detalle)
        texto = self._componer(palabras, intencion, etapa, pad, pregunta, ahora)
        if tipo not in ("reconocer", "recordar_dudoso", "reencuentro"):
            texto = matizar(texto, pad)
        return Enunciado(texto, gesto, palabras, etapa, tipo, intencion.detalle)

    def _elegir(self, intencion: Intencion, etapa: int, ahora: float) -> list[str]:
        candidatas = list(intencion.conceptos)
        if intencion.tipo == "afirmar":
            candidatas.insert(0, self.lexico.polar(+1, ahora))
        elif intencion.tipo == "negar":
            candidatas.insert(0, self.lexico.polar(-1, ahora))
        elegidas: list[str] = []
        for forma in candidatas:
            if forma and forma not in elegidas and self.puede_usar(forma, etapa, ahora):
                elegidas.append(forma)
        if intencion.tipo == "imitar" and len(elegidas) == 1 and etapa >= 2:
            usables = {f for f in self.lexico.palabras if f != elegidas[0] and self.puede_usar(f, etapa, ahora)}
            siguiente = self.ngramas.continuacion(elegidas[0], usables)
            if siguiente:
                elegidas.append(siguiente)
        return elegidas[: MAXIMO_PALABRAS.get(etapa, 3)]

    def _componer(self, palabras: list[str], intencion: Intencion, etapa: int, pad, pregunta: bool,
                  ahora: float) -> str:
        escritas = [self.lexico.get(p).grafia or p for p in palabras]
        if intencion.tipo == "reencuentro":
            return _capitalizar(f"¿{escritas[0]}…? {_capitalizar(escritas[0])}…")

        polar_al_inicio = intencion.tipo in ("afirmar", "negar") and self.lexico.es_polar(palabras[0])
        inicio = 1 if polar_al_inicio else 0
        unidades = escritas[:inicio]
        resto = escritas[inicio:]
        if etapa >= 3 and len(resto) >= 2:
            unidades += [" ".join(resto[:2]), *resto[2:]]
        else:
            unidades += resto
        texto = "… ".join(unidades)

        estados = [self.lexico.estado(p, ahora) for p in palabras]
        todas_tenues = all(e == TENUE for e in estados)
        alguna_tenue = any(e == TENUE for e in estados)
        if intencion.tipo in ("reconocer", "recordar_dudoso"):
            texto = f"Mm… {texto}…"
        if not pregunta and intencion.tipo in TIPOS_DE_CONTENIDO and todas_tenues:
            pregunta = True
        if pregunta:
            texto = f"¿{texto}?"
        elif intencion.tipo in TIPOS_EXCLAMATIVOS and (intencion.tipo == "celebrar" or float(pad[0]) > 0.3):
            texto = f"¡{texto}!"
        elif alguna_tenue:
            texto += "…"
        return _capitalizar(texto)
