"""Importancia de lo aprendido: sube con el uso, baja con el tiempo y nunca se borra.

Todo lo que Muyu guarda (palabras, conceptos, relaciones, hipótesis y recuerdos)
lleva una :class:`Huella`. La importancia va de 0 a 1 y nunca cae por debajo de
``IMPORTANCIA_MINIMA``: siempre queda un rastro que permite reconocer lo olvidado
y volver a aprenderlo más rápido (efecto de ahorro de Ebbinghaus).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from server import config

ACTIVO = "activo"
TENUE = "tenue"
LATENTE = "latente"

COLUMNAS_MEMORIA = (
    "importancia REAL NOT NULL, actualizada REAL NOT NULL, veces_aprendida INTEGER NOT NULL, "
    "primera_vez REAL NOT NULL, ultima_vez REAL NOT NULL, usos INTEGER NOT NULL, recayo INTEGER NOT NULL"
)


def estado_de(importancia: float) -> str:
    if importancia >= config.UMBRAL_ACTIVO:
        return ACTIVO
    if importancia >= config.UMBRAL_TENUE:
        return TENUE
    return LATENTE


def _acotar(valor: float) -> float:
    return min(1.0, max(config.IMPORTANCIA_MINIMA, valor))


@dataclass
class Huella:
    """Rastro de memoria de cualquier elemento.

    ``importancia`` es el valor fijado en el instante ``actualizada`` (tiempo de
    la criatura, en segundos). El valor de hoy se calcula aplicando la atenuación
    desde entonces, así no hace falta recorrer toda la memoria en cada latido.

    ``veces_aprendida`` cuenta la primera vez que se volvió activo y cada vez que
    volvió a activo desde latente; es lo que alimenta el efecto de ahorro.
    ``usos`` cuenta los refuerzos: lo muy repetido se atenúa más despacio.
    """

    importancia: float
    actualizada: float
    primera_vez: float
    ultima_vez: float
    veces_aprendida: int = 0
    usos: int = 0
    recayo: bool = False            # pasó por latente desde la última vez que fue activo

    @classmethod
    def nueva(cls, ahora: float, importancia: float | None = None) -> Huella:
        valor = config.IMPORTANCIA_INICIAL if importancia is None else importancia
        return cls(_acotar(valor), ahora, ahora, ahora)

    def vida_media_horas(self) -> float:
        """Lo que se aprendió varias veces, o se repitió mucho, se atenúa más despacio."""
        return (config.VIDA_MEDIA_HORAS
                * (1 + config.ESTABILIDAD_POR_APRENDIZAJE * self.veces_aprendida)
                * (1 + config.ESTABILIDAD_POR_USO * math.log1p(self.usos)))

    def valor(self, ahora: float) -> float:
        horas = max(0.0, ahora - self.actualizada) / 3600
        minimo = config.IMPORTANCIA_MINIMA
        return minimo + (self.importancia - minimo) * 0.5 ** (horas / self.vida_media_horas())

    def estado(self, ahora: float) -> str:
        return estado_de(self.valor(ahora))

    def reforzar(self, ahora: float, intensidad: float = 1.0) -> bool:
        """Sube la importancia por uso. Devuelve True si acaba de volverse activa.

        importancia_nueva = importancia + tasa × (1 − importancia) × (1 + bono_ahorro × veces_aprendida)
        """
        antes = self.valor(ahora)
        if antes < config.UMBRAL_TENUE:
            self.recayo = True
        tasa = config.TASA_APRENDIZAJE * intensidad
        ahorro = 1 + config.BONO_AHORRO * self.veces_aprendida
        despues = _acotar(antes + tasa * (1 - antes) * ahorro)
        self._fijar(ahora, despues)
        self.ultima_vez = ahora
        self.usos += 1
        return self._quizas_aprendida(antes, despues)

    def atenuar(self, ahora: float, factor: float) -> None:
        """Acerca la importancia al mínimo sin cruzarlo (no cuenta como uso)."""
        minimo = config.IMPORTANCIA_MINIMA
        self._fijar(ahora, minimo + (self.valor(ahora) - minimo) * factor)

    def elevar(self, ahora: float, minimo: float) -> None:
        """Garantiza una importancia mínima, por ejemplo al confirmar una deducción."""
        actual = self.valor(ahora)
        if actual < minimo:
            self._quizas_aprendida(actual, minimo)
            self._fijar(ahora, minimo)
        self.ultima_vez = ahora

    def _quizas_aprendida(self, antes: float, despues: float) -> bool:
        """Cuenta una vez aprendida al volverse activo por primera vez o al volver desde latente."""
        if antes < config.UMBRAL_ACTIVO <= despues and (self.veces_aprendida == 0 or self.recayo):
            self.veces_aprendida += 1
            self.recayo = False
            return True
        return False

    def _fijar(self, ahora: float, valor: float) -> None:
        self.importancia = _acotar(valor)
        self.actualizada = ahora

    def a_fila(self) -> dict:
        return {
            "importancia": self.importancia,
            "actualizada": self.actualizada,
            "veces_aprendida": self.veces_aprendida,
            "primera_vez": self.primera_vez,
            "ultima_vez": self.ultima_vez,
            "usos": self.usos,
            "recayo": int(self.recayo),
        }

    @classmethod
    def desde_fila(cls, fila) -> Huella:
        return cls(
            importancia=fila["importancia"],
            actualizada=fila["actualizada"],
            primera_vez=fila["primera_vez"],
            ultima_vez=fila["ultima_vez"],
            veces_aprendida=fila["veces_aprendida"],
            usos=fila["usos"],
            recayo=bool(fila["recayo"]),
        )

    def a_publico(self, ahora: float) -> dict:
        valor = self.valor(ahora)
        return {
            "importancia": round(valor, 3),
            "estado": estado_de(valor),
            "veces_aprendida": self.veces_aprendida,
            "usos": self.usos,
            "primera_vez": self.primera_vez,
            "ultima_vez": self.ultima_vez,
        }
