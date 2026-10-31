"""Memoria episódica: cada interacción queda guardada con la emoción del momento.

Los recuerdos más emocionales nacen más importantes; como todo lo demás, se
atenúan sin uso pero nunca se borran.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from server import config
from server.brain.importance import Huella


@dataclass
class Episodio:
    id: int
    momento: float
    momento_real: float
    evento: dict
    emocion: list[float]
    huella: Huella

    @property
    def intensidad(self) -> float:
        return min(1.0, (abs(self.emocion[0]) + max(0.0, self.emocion[1])) / 2)

    @property
    def conceptos(self) -> list[str]:
        return self.evento.get("conceptos", [])

    def resumen(self) -> str:
        if self.evento.get("accion"):
            return self.evento["accion"]
        return f"«{self.evento.get('texto', '')[:40]}»"

    def a_fila(self) -> dict:
        return {
            "id": self.id,
            "momento": self.momento,
            "momento_real": self.momento_real,
            "evento": json.dumps(self.evento, ensure_ascii=False),
            "emocion": json.dumps(self.emocion),
            **self.huella.a_fila(),
        }

    @classmethod
    def desde_fila(cls, fila) -> Episodio:
        return cls(fila["id"], fila["momento"], fila["momento_real"], json.loads(fila["evento"]),
                   json.loads(fila["emocion"]), Huella.desde_fila(fila))


class MemoriaEpisodica:
    def __init__(self) -> None:
        self.episodios: list[Episodio] = []
        self.sucios: set[int] = set()

    def registrar(self, evento: dict, emocion, ahora: float, ahora_real: float) -> Episodio:
        emocion = [round(float(x), 3) for x in emocion]
        intensidad = min(1.0, (abs(emocion[0]) + max(0.0, emocion[1])) / 2)
        identificador = self.episodios[-1].id + 1 if self.episodios else 1
        episodio = Episodio(identificador, ahora, ahora_real, evento, emocion,
                            Huella.nueva(ahora, config.IMPORTANCIA_INICIAL + 0.5 * intensidad))
        self.episodios.append(episodio)
        self.sucios.add(identificador)
        return episodio

    def desde(self, momento: float) -> list[Episodio]:
        return [e for e in self.episodios if e.momento >= momento]

    def recientes(self, cantidad: int = 10) -> list[Episodio]:
        return self.episodios[-cantidad:]

    def elegir_recuerdo(self, ahora: float, rng) -> Episodio | None:
        """Un recuerdo al azar: pesan la importancia, la emoción y lo reciente."""
        candidatos = [e for e in self.episodios[-200:] if e.conceptos]
        if not candidatos:
            return None
        ultimo = candidatos[-1].momento
        pesos = [
            e.huella.valor(ahora) * (0.5 + e.intensidad) * (1.5 if ultimo - e.momento < 3600 else 1.0)
            for e in candidatos
        ]
        return rng.choices(candidatos, weights=pesos)[0]
