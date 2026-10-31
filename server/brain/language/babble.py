"""Etapa 0: balbuceo. Sílabas sin sentido teñidas por la emoción.

Cada criatura nace con su propio inventario de sílabas (según su semilla) y,
a medida que oye palabras, empieza a mezclar en su balbuceo sílabas de ellas.
"""

from __future__ import annotations

import random
import re

VOCALES = "aeiou"
CONSONANTES = "mbpntdlk"
_SILABA = re.compile(r"[^aeiouáéíóúü]*[aeiouáéíóúü]+")


def inventario_fonetico(semilla: int) -> list[str]:
    rng = random.Random(semilla * 7919 + 13)
    consonantes = rng.sample(CONSONANTES, 4)
    vocales = rng.sample(VOCALES, 3)
    return [c + v for c in consonantes for v in vocales] + vocales[:1]


# Sonidos innatos que no son palabras: como el llanto o el bostezo de un bebé.
VOCALIZACIONES = {
    "gemido": ("nnn… uu…", "mm-mm… nu…", "uuu… nn…"),
    "suspiro": ("haaa…", "mm… uuh…", "fff… haa…"),
    "bostezo": ("aaaam… zz", "aaah… mm", "ñaaa… zz"),
}


def vocalizar(tipo: str, rng: random.Random) -> str:
    return rng.choice(VOCALIZACIONES[tipo])


def silabas_de(palabra: str) -> list[str]:
    return [s for s in _SILABA.findall(palabra.lower()) if len(s) <= 3]


def balbucear(rng: random.Random, inventario: list[str], pad=(0.0, 0.0, 0.0),
              pregunta: bool = False, oidas: list[str] | tuple = ()) -> str:
    placer, activacion = float(pad[0]), float(pad[1])
    prestadas = [s for palabra in oidas for s in silabas_de(palabra)]
    trozos = []
    for _ in range(1 + (activacion > 0.25) + (rng.random() < 0.3)):
        silabas = [
            rng.choice(prestadas) if prestadas and rng.random() < 0.6 else rng.choice(inventario)
            for _ in range(rng.choice((1, 2, 2)))
        ]
        if placer < -0.3:
            silabas = [s[:-1] + "u" if s[-1] in VOCALES and rng.random() < 0.5 else s for s in silabas]
        trozo = "".join(silabas)
        if placer > 0.4 and rng.random() < 0.5:
            trozo = f"{trozo}-{trozo}"
        trozos.append(trozo)
    texto = "… ".join(trozos)
    if pregunta:
        return f"¿{texto}?"
    if placer > 0.35 and activacion > 0.15:
        return f"¡{texto}!"
    if placer < -0.3:
        return f"{texto}…"
    return texto
