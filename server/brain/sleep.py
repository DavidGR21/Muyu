"""Sueño básico: consolidación de lo vivido desde el último sueño.

1. Repaso: recorre las experiencias priorizando las más emocionales.
2. Refuerzo: fortalece sus palabras, conceptos y relaciones.
3. Atenuación: baja lo que no se usó desde el último sueño (sin borrarlo nunca).
4. Sueño: mezcla conceptos de lo repasado para contarlo al despertar.

La generalización en categorías y el entrenamiento neuronal llegan en la fase 4.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field

import numpy as np

from server import config
from server.brain.concepts import RedConceptos
from server.brain.importance import LATENTE
from server.brain.lexicon import Lexico
from server.brain.memory import MemoriaEpisodica


@dataclass
class Sueno:
    id: int
    inicio: float
    fin: float | None = None
    reforzados: list[str] = field(default_factory=list)
    atenuados: list[str] = field(default_factory=list)
    conceptos: list[str] = field(default_factory=list)
    tono: list[float] = field(default_factory=lambda: [0.0, 0.0, 0.0])
    contado: bool = False

    def a_fila(self) -> dict:
        return {
            "id": self.id,
            "inicio": self.inicio,
            "fin": self.fin,
            "reforzados": json.dumps(self.reforzados, ensure_ascii=False),
            "atenuados": json.dumps(self.atenuados, ensure_ascii=False),
            "sueno": json.dumps(self.conceptos, ensure_ascii=False),
            "tono": json.dumps(self.tono),
            "contado": int(self.contado),
        }

    @classmethod
    def desde_fila(cls, fila) -> Sueno:
        return cls(fila["id"], fila["inicio"], fila["fin"], json.loads(fila["reforzados"]),
                   json.loads(fila["atenuados"]), json.loads(fila["sueno"]), json.loads(fila["tono"]),
                   bool(fila["contado"]))

    def a_publico(self) -> dict:
        return {
            "id": self.id,
            "inicio": self.inicio,
            "fin": self.fin,
            "reforzados": self.reforzados[:20],
            "atenuados": self.atenuados[:20],
            "total_reforzados": len(self.reforzados),
            "total_atenuados": len(self.atenuados),
            "conceptos": self.conceptos,
            "tono": self.tono,
            "contado": self.contado,
        }


def consolidar(identificador: int, lexico: Lexico, red: RedConceptos, memoria: MemoriaEpisodica,
               desde: float, ahora: float, rng: random.Random) -> Sueno:
    sueno = Sueno(identificador, ahora)

    # 1. Repaso: lo más emocional e importante primero.
    vividos = memoria.desde(desde)
    repasados = sorted(vividos, key=lambda e: -(e.intensidad + e.huella.valor(ahora)))[: config.EPISODIOS_REPASO]

    # 2. Refuerzo.
    reforzados: dict[str, None] = {}
    for episodio in repasados:
        fuerza = 0.3 + 0.7 * episodio.intensidad
        episodio.huella.reforzar(ahora, fuerza)
        memoria.sucios.add(episodio.id)
        conceptos = [c for c in dict.fromkeys(episodio.conceptos) if c in red.nodos]
        for concepto in conceptos:
            red.reforzar_nodo(concepto, ahora, 0.5 * fuerza)
            lexico.reforzar(concepto, ahora, 0.4 * fuerza)
            reforzados[concepto] = None
        for a, b in zip(conceptos, conceptos[1:]):
            relacion = red.relacion(a, b)
            if relacion:
                relacion.huella.reforzar(ahora, 0.5 * fuerza)
                red.sucias_relaciones.add((a, b))
    sueno.reforzados = list(reforzados)

    # 3. Atenuación de lo que no se usó desde el último sueño.
    factor = config.FACTOR_ATENUACION_SUENO
    for palabra in lexico.palabras.values():
        if palabra.huella.ultima_vez < desde and palabra.huella.estado(ahora) != LATENTE:
            palabra.huella.atenuar(ahora, factor)
            lexico.sucias.add(palabra.forma)
            sueno.atenuados.append(palabra.forma)
    for concepto in red.nodos.values():
        if concepto.huella.ultima_vez < desde and concepto.huella.estado(ahora) != LATENTE:
            concepto.huella.atenuar(ahora, factor)
            red.sucios_nodos.add(concepto.nodo)
    for clave, relacion in red.relaciones.items():
        if relacion.huella.ultima_vez < desde and relacion.huella.estado(ahora) != LATENTE:
            relacion.huella.atenuar(ahora, factor)
            red.sucias_relaciones.add(clave)
            sueno.atenuados.append(f"{relacion.origen}→{relacion.destino}")

    # 4. El sueño: una mezcla de lo repasado y un paseo por la red.
    candidatos = [c for c in reforzados if red.nodos[c].huella.estado(ahora) != LATENTE]
    if candidatos:
        inicio = rng.choice(candidatos)
        mezcla = list(dict.fromkeys(red.paseo(inicio, ahora, rng, pasos=2) + rng.sample(candidatos, min(2, len(candidatos)))))
        rng.shuffle(mezcla)
        sueno.conceptos = mezcla[: rng.randint(2, 4)] if len(mezcla) > 1 else mezcla
    if repasados:
        sueno.tono = [round(float(x), 3) for x in np.mean([e.emocion for e in repasados], axis=0)]
    return sueno
