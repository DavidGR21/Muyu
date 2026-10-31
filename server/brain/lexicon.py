"""Léxico: las palabras que Muyu oyó, cuánto le informan y qué le hacen sentir.

Nada viene de fábrica. La informatividad sale de cuántas frases contienen la
palabra (al estilo IDF), la valencia de las señales primarias que la acompañan,
la polaridad (sí/no) de cómo el dueño responde a sus preguntas y las palabras
interrogativas de dónde suelen aparecer.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field

from server import config
from server.brain import instincts
from server.brain.importance import ACTIVO, LATENTE, TENUE, Huella
from server.brain.perception import Frase


@dataclass
class Palabra:
    forma: str
    huella: Huella
    grafia: str = ""                # mayúsculas si es nombre propio ("Muyu")
    frecuencia: int = 0             # veces oída en total
    en_frases: int = 0              # frases del dueño que la contienen
    en_preguntas: int = 0
    al_inicio_pregunta: int = 0     # dentro de las dos primeras palabras de una pregunta
    en_respuestas: int = 0          # en respuestas a preguntas de Muyu
    en_saludos: int = 0             # en el primer mensaje al volver
    valencia: float = 0.0           # −1 (malo) … +1 (bueno)
    polaridad: float = 0.0          # −1 (corrige) … +1 (confirma)
    acciones: dict[str, float] = field(default_factory=dict)

    def a_fila(self, informatividad: float) -> dict:
        return {
            "palabra": self.forma,
            "grafia": self.grafia,
            "frecuencia": self.frecuencia,
            "en_frases": self.en_frases,
            "en_preguntas": self.en_preguntas,
            "al_inicio_pregunta": self.al_inicio_pregunta,
            "en_respuestas": self.en_respuestas,
            "en_saludos": self.en_saludos,
            "informatividad": round(informatividad, 4),
            "valencia": self.valencia,
            "polaridad": self.polaridad,
            "acciones": json.dumps(self.acciones),
            **self.huella.a_fila(),
        }

    @classmethod
    def desde_fila(cls, fila) -> Palabra:
        return cls(
            forma=fila["palabra"],
            huella=Huella.desde_fila(fila),
            grafia=fila["grafia"] or "",
            frecuencia=fila["frecuencia"],
            en_frases=fila["en_frases"],
            en_preguntas=fila["en_preguntas"],
            al_inicio_pregunta=fila["al_inicio_pregunta"],
            en_respuestas=fila["en_respuestas"],
            en_saludos=fila["en_saludos"],
            valencia=fila["valencia"],
            polaridad=fila["polaridad"],
            acciones=json.loads(fila["acciones"] or "{}"),
        )


@dataclass
class Oido:
    """Resultado de oír una frase."""

    nuevas: list[str] = field(default_factory=list)
    reconocidas: list[str] = field(default_factory=list)   # estaban latentes
    activadas: list[str] = field(default_factory=list)     # acaban de volverse activas


def _acotar(valor: float, minimo: float = -1.0, maximo: float = 1.0) -> float:
    return min(maximo, max(minimo, valor))


class Lexico:
    def __init__(self) -> None:
        self.palabras: dict[str, Palabra] = {}
        self.total_frases = 0
        self.sucias: set[str] = set()

    def __contains__(self, forma: str) -> bool:
        return forma in self.palabras

    def __len__(self) -> int:
        return len(self.palabras)

    def get(self, forma: str) -> Palabra | None:
        return self.palabras.get(forma)

    # ── Oír ──────────────────────────────────────────────────────────────

    def oir(self, frase: Frase, ahora: float, intensidad: float = 1.0,
            saludo: bool = False, respuesta: bool = False) -> Oido:
        self.total_frases += 1
        oido = Oido()
        vistas: list[str] = []
        for forma in frase.palabras:
            palabra = self.palabras.get(forma)
            if palabra is None:
                palabra = self.palabras[forma] = Palabra(forma, Huella.nueva(ahora))
                oido.nuevas.append(forma)
            elif forma not in vistas:
                if palabra.huella.estado(ahora) == LATENTE:
                    oido.reconocidas.append(forma)
                if palabra.huella.reforzar(ahora, intensidad):
                    oido.activadas.append(forma)
            if forma not in vistas:
                vistas.append(forma)
            palabra.frecuencia += 1
            if forma in frase.grafias:
                palabra.grafia = frase.grafias[forma]
            self.sucias.add(forma)

        for forma in vistas:
            palabra = self.palabras[forma]
            palabra.en_frases += 1
            palabra.en_saludos += saludo
            palabra.en_respuestas += respuesta
            if frase.es_pregunta:
                palabra.en_preguntas += 1
                palabra.al_inicio_pregunta += frase.palabras.index(forma) < 2
        self._contagiar(vistas)
        return oido

    def reforzar(self, forma: str, ahora: float, intensidad: float) -> bool:
        palabra = self.palabras.get(forma)
        if palabra is None:
            return False
        self.sucias.add(forma)
        return palabra.huella.reforzar(ahora, intensidad)

    # ── Informatividad ───────────────────────────────────────────────────

    def informatividad(self, forma: str) -> float:
        """Qué tanto informa una palabra: mezcla saliencia innata y frecuencia aprendida.

        Las que aparecen en casi todas las frases ("el", "de", "que") terminan
        siendo poco informativas sin ninguna lista de palabras vacías.
        """
        previa = instincts.saliencia(forma)
        palabra = self.palabras.get(forma)
        if palabra is None or self.total_frases == 0:
            return previa
        n = self.total_frases
        idf = math.log((n + 1) / (palabra.en_frases + 0.5)) / math.log(config.IDF_REFERENCIA)
        idf = _acotar(idf, 0.0, 1.0)
        evidencia = n / (n + config.K_EVIDENCIA)
        return (1 - evidencia) * previa + evidencia * idf

    def es_concepto(self, forma: str, tolerancia: float = 1.0) -> bool:
        """``tolerancia`` < 1 sirve para reconocer un concepto que le nombran directamente
        aunque, de tanto oírlo (como su propio nombre), ya no le parezca muy informativo."""
        return (
            self.informatividad(forma) >= config.UMBRAL_CONCEPTO * tolerancia
            and not self.es_polar(forma)
            and not self.es_interrogativa(forma)
        )

    def es_interrogativa(self, forma: str) -> bool:
        """Aprendido: palabras que casi siempre abren una pregunta ("qué", "cómo")."""
        palabra = self.palabras.get(forma)
        return bool(palabra) and palabra.en_frases >= 2 and palabra.al_inicio_pregunta / palabra.en_frases >= 0.6

    # ── Estado de memoria ────────────────────────────────────────────────

    def estado(self, forma: str, ahora: float) -> str | None:
        palabra = self.palabras.get(forma)
        return palabra.huella.estado(ahora) if palabra else None

    def importancia(self, forma: str, ahora: float) -> float:
        palabra = self.palabras.get(forma)
        return palabra.huella.valor(ahora) if palabra else 0.0

    def usable(self, forma: str, ahora: float) -> bool:
        return self.estado(forma, ahora) in (ACTIVO, TENUE)

    def activas(self, ahora: float) -> int:
        return sum(p.huella.estado(ahora) == ACTIVO for p in self.palabras.values())

    # ── Valencia (anclaje emocional) ─────────────────────────────────────

    def valencia(self, forma: str) -> float:
        palabra = self.palabras.get(forma)
        return palabra.valencia if palabra else 0.0

    def asociar_senal(self, pesos: dict[str, float], valencia: float, accion: str | None = None) -> None:
        """Las palabras oídas cerca de una caricia o un regaño se tiñen de esa emoción."""
        for forma, peso in pesos.items():
            palabra = self.palabras.get(forma)
            if palabra is None or peso <= 0:
                continue
            tasa = config.TASA_VALENCIA * peso
            palabra.valencia = _acotar(palabra.valencia + tasa * (valencia - palabra.valencia))
            if accion:
                palabra.acciones[accion] = round(palabra.acciones.get(accion, 0.0) + peso, 3)
            self.sucias.add(forma)

    def _contagiar(self, formas: list[str]) -> None:
        """Condicionamiento de segundo orden: se pega un poco la emoción de las palabras vecinas."""
        for forma in formas:
            otras = [self.palabras[o].valencia for o in formas if o != forma]
            peso = sum(abs(v) for v in otras)
            if peso < 0.2:
                continue
            objetivo = sum(v * abs(v) for v in otras) / peso
            palabra = self.palabras[forma]
            if abs(palabra.valencia) < abs(objetivo) or palabra.valencia * objetivo < 0:
                palabra.valencia += config.TASA_CONTAGIO * min(1.0, peso) * (objetivo - palabra.valencia)

    # ── Sí / no ──────────────────────────────────────────────────────────

    def es_polar(self, forma: str) -> bool:
        palabra = self.palabras.get(forma)
        return (
            bool(palabra)
            and abs(palabra.polaridad) >= config.UMBRAL_POLARIDAD
            and palabra.en_respuestas / max(1, palabra.en_frases) >= 0.3
        )

    def polaridad_de(self, formas: list[str]) -> float:
        return sum(self.palabras[f].polaridad for f in set(formas) if self.es_polar(f))

    def asociar_polaridad(self, formas: list[str], signo: float, fuerza: float = 1.0,
                          respuesta: bool = False) -> None:
        """Las palabras con que se confirma (+1) o se corrige (−1) aprenden a significar sí o no.
        ``respuesta`` cuenta la frase como respuesta si al oírla no se supo que lo era."""
        for forma in set(formas):
            palabra = self.palabras.get(forma)
            if palabra is None:
                continue
            tasa = min(1.0, config.TASA_POLARIDAD * fuerza)
            palabra.polaridad = _acotar(palabra.polaridad + tasa * (signo - palabra.polaridad))
            palabra.en_respuestas += respuesta
            self.sucias.add(forma)

    # ── Palabras para expresarse ─────────────────────────────────────────

    def polar(self, signo: int, ahora: float) -> str | None:
        """La palabra que usa para decir sí (signo +1) o no (signo −1)."""
        candidatas = [
            p for p in self.palabras.values()
            if self.es_polar(p.forma) and p.polaridad * signo > 0 and self.usable(p.forma, ahora)
        ]
        mejor = max(candidatas, key=lambda p: abs(p.polaridad) * p.huella.valor(ahora), default=None)
        return mejor.forma if mejor else None

    def valorativa(self, signo: int, ahora: float, excluir: tuple[str, ...] = ()) -> str | None:
        """La palabra con la que expresa que algo es bueno (+1) o malo (−1)."""
        candidatas = [
            p for p in self.palabras.values()
            if p.valencia * signo >= config.UMBRAL_VALORATIVA and p.forma not in excluir
            and self.usable(p.forma, ahora) and not self.es_polar(p.forma)
            and self.informatividad(p.forma) >= config.UMBRAL_CONCEPTO * 0.8
        ]
        mejor = max(candidatas, key=lambda p: abs(p.valencia) * p.huella.valor(ahora), default=None)
        return mejor.forma if mejor else None

    def de_accion(self, accion: str, ahora: float) -> str | None:
        """La palabra que más acompaña a una acción ("comida" al alimentarla)."""
        candidatas = []
        for p in self.palabras.values():
            asociacion = p.acciones.get(accion, 0.0)
            if asociacion >= 1.0 and self.usable(p.forma, ahora) and not self.es_polar(p.forma):
                especificidad = asociacion / max(1.0, sum(p.acciones.values()))
                if especificidad >= 0.5:
                    candidatas.append((asociacion * especificidad * self.informatividad(p.forma), p.forma))
        return max(candidatas)[1] if candidatas else None

    def de_saludo(self, ahora: float) -> str | None:
        """La palabra con la que su dueño suele llegar ("hola")."""
        candidatas = [
            (p.en_saludos ** 2 / p.en_frases, p.forma) for p in self.palabras.values()
            if p.en_saludos >= 2 and self.usable(p.forma, ahora)
        ]
        return max(candidatas)[1] if candidatas else None

    def para_llamar(self, ahora: float, inicios: dict[str, int]) -> str | None:
        """Con qué palabra te llama cuando te busca: la de tus saludos o, si aún no la
        aprendió, la que más usas para empezar a hablarle (``inicios``: veces que cada
        palabra abrió una frase tuya)."""
        saludo = self.de_saludo(ahora)
        if saludo:
            return saludo
        candidatas = [
            (conteo * (1 + self.palabras[forma].en_saludos), forma) for forma, conteo in inicios.items()
            if forma in self.palabras and conteo >= 2 and self.usable(forma, ahora)
            and self.informatividad(forma) >= 0.4 and not self.es_interrogativa(forma) and not self.es_polar(forma)
        ]
        return max(candidatas)[1] if candidatas else None

    # ── Panel ────────────────────────────────────────────────────────────

    def a_publico(self, ahora: float) -> list[dict]:
        filas = []
        for p in self.palabras.values():
            filas.append({
                "palabra": p.grafia or p.forma,
                "forma": p.forma,
                **p.huella.a_publico(ahora),
                "frecuencia": p.frecuencia,
                "informatividad": round(self.informatividad(p.forma), 3),
                "valencia": round(p.valencia, 3),
                "polaridad": round(p.polaridad, 3),
                "concepto": self.es_concepto(p.forma),
                "interrogativa": self.es_interrogativa(p.forma),
            })
        filas.sort(key=lambda f: -f["importancia"])
        return filas
