"""Modelo emocional propio: PAD + evaluación cognitiva + ánimo + relación.

Tres capas, cada una con su velocidad, que se influyen entre sí:

* **Emoción** (segundos reales): reacciona a cada evento y vuelve sola a su línea base.
* **Ánimo** (horas de criatura): sigue lentamente a las emociones y tiñe cómo
  evalúa lo que le pasa (con mal ánimo todo parece un poco peor).
* **Relación** (días): confianza, afecto, familiaridad y experiencia con el dueño.
  Cambia un poco con cada trato y, despacio, sigue al balance de lo vivido.

Las emociones no salen del lenguaje. Cada evento se evalúa (appraisal): qué tan
inesperado, agradable, peligroso y controlable es, y qué tan relevante para sus
necesidades. De ahí sale el cambio en el espacio PAD y dos impulsos que pueden
convivir: acercarse y alejarse (ambivalencia: curiosidad y miedo a la vez).
Cada cambio guarda su causa y su evaluación para mostrarlas en el panel.
"""

from __future__ import annotations

import json
import math
from collections import deque
from dataclasses import dataclass

import numpy as np

from server import config
from server.brain.instincts import Necesidades

PROTOTIPOS = {
    "alegría": (0.75, 0.55, 0.35),
    "contento": (0.45, 0.05, 0.15),
    "calma": (0.35, -0.45, 0.15),
    "curiosidad": (0.2, 0.5, 0.05),
    "sorpresa": (0.05, 0.8, -0.15),
    "miedo": (-0.6, 0.6, -0.55),
    "enojo": (-0.6, 0.6, 0.4),
    "tristeza": (-0.6, -0.35, -0.4),
    "aburrimiento": (-0.25, -0.55, -0.1),
    "confusión": (-0.2, 0.3, -0.4),
    "neutral": (0.0, 0.0, 0.0),
}


def etiqueta_de(pad: np.ndarray) -> str:
    return min(PROTOTIPOS, key=lambda nombre: float(np.sum((pad - np.array(PROTOTIPOS[nombre])) ** 2)))


def _acotar(valor: float, minimo: float = 0.0, maximo: float = 1.0) -> float:
    return min(maximo, max(minimo, valor))


def _redondear(vector) -> list[float]:
    return [round(float(x), 3) for x in vector]


@dataclass
class Evaluacion:
    """Appraisal de un evento. Quien lo crea describe el evento en bruto; el
    :class:`Evaluador` lo completa con el contexto (expectativas, necesidades,
    relación, ánimo y seguridad) antes de convertirlo en emoción."""

    causa: str
    novedad: float = 0.0
    agrado: float = 0.0
    amenaza: float = 0.0
    control: float = 0.5
    detalle: str = ""
    necesidad: str | None = None    # la necesidad a la que responde
    del_dueno: bool = False         # lo causó su dueño (cuenta para la relación)
    calma: float = 0.0              # cuánto la serena (baja la activación)
    # Calculados por el Evaluador:
    inesperado: float = 0.0
    relevancia: float = 1.0
    acercamiento: float = 0.0
    evitacion: float = 0.0

    def resumen(self) -> dict:
        return {
            "inesperado": round(self.inesperado, 2),
            "agrado": round(self.agrado, 2),
            "amenaza": round(self.amenaza, 2),
            "control": round(self.control, 2),
            "relevancia": round(self.relevancia, 2),
        }


class Evaluador:
    """Completa cada evaluación con el contexto: el appraisal completo."""

    def __init__(self, rasgos: dict[str, float]) -> None:
        self.rasgos = rasgos
        self._vistas: dict[str, tuple[float, float]] = {}    # causa → (recuento que decae, momento real)
        self._tono_reciente = (0.0, 0.0)                    # (agrado medio reciente, momento real)

    def _recuento(self, causa: str, ahora_real: float) -> float:
        recuento, momento = self._vistas.get(causa, (0.0, ahora_real))
        return recuento * 0.5 ** ((ahora_real - momento) / 60)

    def completar(self, ev: Evaluacion, animo: np.ndarray, vinculo: Vinculo, necesidades: Necesidades,
                  ahora_real: float) -> Evaluacion:
        r = self.rasgos

        # 1. Expectativa: lo repetido se vuelve predecible (habituación); lo que rompe
        #    el tono de lo que venía pasando sorprende.
        vistas = self._recuento(ev.causa, ahora_real)
        habituacion = 1 / (1 + 0.35 * vistas)
        tono, momento = self._tono_reciente
        tono *= 0.5 ** ((ahora_real - momento) / 45)
        contraste = max(0.0, -np.sign(ev.agrado - ev.amenaza) * tono) if abs(ev.agrado - ev.amenaza) > 0.1 else 0.0
        ev.inesperado = _acotar(ev.novedad * habituacion + 0.5 * contraste)
        if ev.agrado > 0:
            ev.agrado *= 0.5 + 0.5 * habituacion

        # 2. Relevancia: lo que responde a algo que le falta importa más (comer con hambre).
        if ev.necesidad:
            deficit = necesidades.deficit(ev.necesidad)
            ev.relevancia = 0.4 + 1.2 * deficit
            if ev.agrado > 0:
                ev.agrado *= ev.relevancia

        # 3. Relación: lo bueno de alguien en quien no confía también le da un poco de miedo;
        #    un regaño de alguien en quien confía duele más y asusta menos.
        if ev.del_dueno:
            confianza = vinculo.confianza
            if ev.agrado > 0:
                ev.agrado *= 0.6 + 0.8 * vinculo.afecto
                ev.evitacion += 1.2 * max(0.0, 0.45 - confianza)
            if ev.amenaza > 0:
                ev.agrado -= 0.4 * confianza
                ev.amenaza *= 1.2 - 0.5 * confianza
            ev.control += 0.25 * (confianza - 0.5) + 0.1 * vinculo.familiaridad

        # 4. Seguridad: si se siente insegura, todo parece más amenazante y menos controlable.
        inseguridad = 1 - necesidades.seguridad
        ev.amenaza *= 1 + 0.8 * inseguridad
        ev.control -= 0.2 * inseguridad

        # 5. Ánimo: el estado de ánimo tiñe lo que siente (sesgo congruente).
        ev.agrado += 0.15 * float(animo[0])

        # 6. Impulsos: acercarse a lo agradable y nuevo; alejarse de lo amenazante.
        ev.acercamiento += max(0.0, ev.agrado) + 0.5 * ev.inesperado * r["curiosidad"]
        ev.evitacion += ev.amenaza * (0.5 + r["timidez"]) + 0.4 * ev.inesperado * r["timidez"] * inseguridad
        ev.control = _acotar(ev.control)

        self._vistas[ev.causa] = (vistas + 1, ahora_real)
        self._tono_reciente = (0.7 * tono + 0.3 * _acotar(ev.agrado - ev.amenaza, -1, 1), ahora_real)
        return ev


@dataclass
class Vinculo:
    """La relación con el dueño, la capa más lenta (días)."""

    confianza: float = config.CONFIANZA_INICIAL
    afecto: float = config.AFECTO_INICIAL
    familiaridad: float = 0.0
    experiencia: float = 0.0        # balance reciente de buenas (+) y malas (−) experiencias

    def ajustar(self, confianza: float, afecto: float, sensibilidad: float) -> None:
        """Efecto inmediato de un trato (pequeño)."""
        if confianza < 0:
            confianza *= 0.6 + 0.8 * sensibilidad
        self.confianza = _acotar(self.confianza + confianza)
        self.afecto = _acotar(self.afecto + afecto)

    def experimentar(self, valor: float) -> None:
        self.experiencia = _acotar(self.experiencia + 0.1 * (_acotar(valor, -1, 1) - self.experiencia), -1, 1)

    def vivir(self, horas: float, acompanada: bool) -> None:
        """Con los días, la confianza sigue al balance de lo vivido; la familiaridad crece
        con el tiempo juntos y el afecto sin contacto se enfría muy despacio."""
        if horas <= 0:
            return
        k = 1 - math.exp(-horas / config.TAU_VINCULO_HORAS)
        objetivo = _acotar(0.5 + 0.45 * self.experiencia, 0.05, 0.95)
        self.confianza += (objetivo - self.confianza) * 0.5 * k
        self.experiencia *= 0.5 ** (horas / config.VIDA_MEDIA_EXPERIENCIA_HORAS)
        if acompanada:
            self.familiaridad += (1 - self.familiaridad) * (1 - math.exp(-horas / config.HORAS_FAMILIARIDAD))
        else:
            base = 0.15 + 0.4 * self.familiaridad
            if self.afecto > base:
                self.afecto += (base - self.afecto) * (1 - math.exp(-horas / 240))

    def a_publico(self) -> dict:
        return {
            "confianza": round(self.confianza, 3),
            "afecto": round(self.afecto, 3),
            "familiaridad": round(self.familiaridad, 3),
            "experiencia": round(self.experiencia, 3),
        }


class Emociones:
    def __init__(self, rasgos: dict[str, float], ahora_real: float, necesidades: Necesidades | None = None) -> None:
        self.rasgos = rasgos
        self.necesidades = necesidades or Necesidades()
        self.evaluador = Evaluador(rasgos)
        self.vinculo = Vinculo()
        self._emocion = np.zeros(3)
        self._emocion_real = ahora_real
        self.animo = np.zeros(3)
        self.base_necesidades = np.zeros(3)
        self._impulsos = np.zeros(2)       # (acercarse, alejarse)
        self._impulsos_real = ahora_real
        self.causas: deque[dict] = deque(maxlen=30)

    # Compatibilidad: la relación vive en el vínculo.
    @property
    def confianza(self) -> float:
        return self.vinculo.confianza

    @property
    def afecto(self) -> float:
        return self.vinculo.afecto

    def ajustar_relacion(self, confianza: float, afecto: float) -> None:
        self.vinculo.ajustar(confianza, afecto, self.rasgos["sensibilidad"])

    # ── Emoción ──────────────────────────────────────────────────────────

    def linea_base(self) -> np.ndarray:
        return np.clip(self.animo + self.base_necesidades, -1, 1)

    def actual(self, ahora_real: float) -> np.ndarray:
        """La emoción decae con suavidad hacia la línea base (ánimo + necesidades)."""
        transcurrido = max(0.0, ahora_real - self._emocion_real)
        factor = 0.5 ** (transcurrido / config.VIDA_MEDIA_EMOCION_S)
        base = self.linea_base()
        return base + (self._emocion - base) * factor

    def impulsos(self, ahora_real: float) -> np.ndarray:
        transcurrido = max(0.0, ahora_real - self._impulsos_real)
        return self._impulsos * 0.5 ** (transcurrido / config.VIDA_MEDIA_IMPULSO_S)

    def ambivalencia(self, ahora_real: float) -> float:
        """Quiere acercarse y alejarse a la vez: el menor de los dos impulsos."""
        acercarse, alejarse = self.impulsos(ahora_real)
        valor = min(acercarse, alejarse)
        return float(valor) if valor >= config.UMBRAL_AMBIVALENCIA else 0.0

    def a_pad(self, ev: Evaluacion) -> np.ndarray:
        r = self.rasgos
        amplitud = 0.6 + 0.8 * r["sensibilidad"]
        sorpresa = max(ev.inesperado, ev.novedad * 0.5)
        placer = (0.6 * ev.agrado - 0.35 * ev.amenaza
                  + 0.2 * sorpresa * (r["curiosidad"] - 0.35) + 0.2 * (ev.control - 0.5))
        activacion = (0.45 * sorpresa * (0.5 + r["curiosidad"])
                      + 0.6 * ev.amenaza * (0.5 + r["timidez"]) + 0.2 * abs(ev.agrado) - 0.4 * ev.calma)
        dominancia = 0.5 * (ev.control - 0.5) - 0.5 * ev.amenaza * (0.5 + r["timidez"])
        return np.array([placer, activacion, dominancia]) * amplitud

    def sentir(self, evaluacion: Evaluacion, ahora_real: float, ahora: float) -> np.ndarray:
        ev = self.evaluador.completar(evaluacion, self.animo, self.vinculo, self.necesidades, ahora_real)
        delta = self.a_pad(ev)
        self._emocion = np.clip(self.actual(ahora_real) + delta, -1, 1)
        self._emocion_real = ahora_real
        self._impulsos = np.clip(self.impulsos(ahora_real) + [ev.acercamiento, ev.evitacion], 0, 1)
        self._impulsos_real = ahora_real
        if ev.amenaza > 0:
            self.necesidades.asustar(ev.amenaza)
        if ev.del_dueno:
            self.vinculo.experimentar(ev.agrado - ev.amenaza)
        if np.abs(delta).max() >= 0.02:
            self.causas.appendleft({
                "causa": ev.causa,
                "detalle": ev.detalle,
                "delta": _redondear(delta),
                "evaluacion": ev.resumen(),
                "momento": ahora,
                "momento_real": ahora_real,
            })
        return delta

    def dejar_pasar(self, segundos: float) -> None:
        """Al simular tiempo de golpe, la emoción del momento también se apaga."""
        self._emocion_real -= segundos
        self._impulsos_real -= segundos

    # ── Ánimo y relación ─────────────────────────────────────────────────

    def vivir(self, horas: float, ahora_real: float, acompanada: bool) -> None:
        self.base_necesidades = self.necesidades.efecto_emocional()
        self.actualizar_animo(horas, ahora_real)
        self.vinculo.vivir(horas, acompanada)

    def actualizar_animo(self, horas: float, ahora_real: float) -> None:
        if horas <= 0:
            return
        k = 1 - math.exp(-horas / config.TAU_ANIMO_HORAS)
        self.animo = np.clip(self.animo + (self.actual(ahora_real) - self.animo) * 0.5 * k, -0.8, 0.8)

    # ── Lectura ──────────────────────────────────────────────────────────

    def etiqueta(self, ahora_real: float) -> str:
        return etiqueta_de(self.actual(ahora_real))

    def instantanea(self, ahora_real: float) -> dict:
        """La emoción de este instante, para que cuerpo, voz y palabras la expresen igual."""
        emocion = self.actual(ahora_real)
        return {
            "p": round(float(emocion[0]), 3),
            "a": round(float(emocion[1]), 3),
            "d": round(float(emocion[2]), 3),
            "etiqueta": etiqueta_de(emocion),
            "intensidad": round(float(np.linalg.norm(emocion)), 3),
            "ambivalencia": round(self.ambivalencia(ahora_real), 3),
        }

    def a_publico(self, ahora_real: float) -> dict:
        acercarse, alejarse = self.impulsos(ahora_real)
        return {
            "emocion": self.instantanea(ahora_real),
            "impulsos": {"acercarse": round(float(acercarse), 3), "alejarse": round(float(alejarse), 3)},
            "animo": dict(zip("pad", _redondear(self.animo))) | {"etiqueta": etiqueta_de(self.animo)},
            "relacion": self.vinculo.a_publico(),
            "causas": list(self.causas)[:12],
        }

    # ── Persistencia ─────────────────────────────────────────────────────

    def a_fila_estado(self) -> dict:
        return {
            "emocion": json.dumps(_redondear(self._emocion)),
            "emocion_real": self._emocion_real,
            "animo": json.dumps(_redondear(self.animo)),
            "causas": json.dumps(list(self.causas)),
        }

    def cargar_estado(self, fila) -> None:
        self._emocion = np.array(json.loads(fila["emocion"]))
        self._emocion_real = fila["emocion_real"]
        self.animo = np.array(json.loads(fila["animo"]))
        self.causas = deque(json.loads(fila["causas"]), maxlen=30)

    def a_fila_relacion(self, ahora: float) -> dict:
        v = self.vinculo
        return {"sujeto": "dueño", "confianza": v.confianza, "afecto": v.afecto, "familiaridad": v.familiaridad,
                "experiencia": v.experiencia, "actualizada": ahora}

    def cargar_relacion(self, fila) -> None:
        claves = fila.keys()
        self.vinculo = Vinculo(
            confianza=fila["confianza"],
            afecto=fila["afecto"],
            familiaridad=fila["familiaridad"] if "familiaridad" in claves and fila["familiaridad"] is not None else 0.0,
            experiencia=fila["experiencia"] if "experiencia" in claves and fila["experiencia"] is not None else 0.0,
        )
