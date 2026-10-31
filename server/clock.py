"""Reloj interno: el paso del tiempo para cada criatura y el latido del servidor.

Cada criatura tiene su propio tiempo de vida (en segundos), que avanza con el
tiempo real multiplicado por ``VELOCIDAD_TIEMPO`` y que puede adelantarse a
mano para probar la atenuación o el sueño.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import TYPE_CHECKING

from server import config

if TYPE_CHECKING:
    from server.main import Vivero

log = logging.getLogger("muyu.reloj")


class Reloj:
    def __init__(self, tiempo: float = 0.0, velocidad: float | None = None, reloj_real=time.time) -> None:
        self.tiempo = tiempo
        self.velocidad = config.VELOCIDAD_TIEMPO if velocidad is None else velocidad
        self._real = reloj_real
        self._ultimo_real = reloj_real()

    def transcurrido(self) -> float:
        """Segundos de criatura desde la última consulta (sin sumarlos todavía)."""
        ahora = self._real()
        segundos = max(0.0, ahora - self._ultimo_real) * self.velocidad
        self._ultimo_real = ahora
        return segundos

    def sumar(self, segundos: float) -> None:
        self.tiempo += segundos


async def latir_siempre(vivero: Vivero, intervalo: float = config.TICK_S) -> None:
    """Cada latido, las criaturas con alguien conectado viven un poco: piensan,
    se cansan y se duermen aunque nadie les hable."""
    latido = 0
    while True:
        await asyncio.sleep(intervalo)
        latido += 1
        for criatura in vivero.conectadas():
            try:
                salidas = criatura.latir()
                if salidas or latido % 2 == 0:
                    cerebro = bool(salidas) or latido % 10 == 0
                    await vivero.enviar(criatura.id, salidas + criatura.instantanea(cerebro))
                if salidas or latido % 5 == 0:
                    criatura.guardar()
            except Exception:
                log.exception("Falló el latido de %s", criatura.id)
