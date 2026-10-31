"""Etapas 1 a 4: modelo de n-gramas a nivel de palabra, aprendido en tiempo real.

Se actualiza con cada frase del dueño. En la fase 1 decide el orden de las
palabras y completa las combinaciones que oyó mucho ("hola" → "hola Muyu"):
Muyu habla como le hablan.
"""

from __future__ import annotations

from collections import Counter, defaultdict

INICIO = "<s>"
K_SUAVIZADO = 0.1


class ModeloNgramas:
    def __init__(self) -> None:
        self.conteos: dict[str, Counter] = defaultdict(Counter)
        self.unigramas: Counter = Counter()
        self.sucios: set[tuple[str, str]] = set()

    def aprender(self, palabras: list[str]) -> None:
        previa, anterior = INICIO, None
        for palabra in palabras:
            self._sumar(previa, palabra)
            self.unigramas[palabra] += 1
            if anterior is not None:
                self._sumar(f"{anterior} {previa}", palabra)
            anterior, previa = previa, palabra

    def _sumar(self, contexto: str, palabra: str) -> None:
        self.conteos[contexto][palabra] += 1
        self.sucios.add((contexto, palabra))

    def probabilidad(self, palabra: str, previas: list[str] | tuple = ()) -> float:
        """Interpolación de trigrama, bigrama y unigrama con suavizado aditivo."""
        vocabulario = len(self.unigramas) + 1
        total = sum(self.unigramas.values())
        p_uni = (self.unigramas[palabra] + K_SUAVIZADO) / (total + K_SUAVIZADO * vocabulario)
        p_bi = self._condicional(previas[-1], palabra, vocabulario) if previas else None
        p_tri = self._condicional(" ".join(previas[-2:]), palabra, vocabulario) if len(previas) >= 2 else None
        p_bi = p_uni if p_bi is None else p_bi
        p_tri = p_bi if p_tri is None else p_tri
        return 0.5 * p_tri + 0.35 * p_bi + 0.15 * p_uni

    def _condicional(self, contexto: str, palabra: str, vocabulario: int) -> float | None:
        siguientes = self.conteos.get(contexto)
        if not siguientes:
            return None
        return (siguientes[palabra] + K_SUAVIZADO) / (sum(siguientes.values()) + K_SUAVIZADO * vocabulario)

    def ordenar(self, a: str, b: str) -> tuple[str, str]:
        """El orden en que suele oír dos palabras juntas."""
        if self.probabilidad(b, [a]) >= self.probabilidad(a, [b]):
            return a, b
        return b, a

    def continuacion(self, previa: str, candidatas: set[str], minimo: float = 0.5) -> str | None:
        """La palabra que casi siempre sigue a ``previa``, si es una de ``candidatas``."""
        siguientes = self.conteos.get(previa)
        if not siguientes:
            return None
        total = sum(siguientes.values())
        palabra, conteo = max(
            ((p, c) for p, c in siguientes.items() if p in candidatas), key=lambda par: par[1], default=(None, 0)
        )
        return palabra if palabra and total >= 2 and conteo / total >= minimo else None

    def filas_sucias(self) -> list[dict]:
        filas = [{"contexto": c, "siguiente": s, "conteo": self.conteos[c][s]} for c, s in self.sucios]
        self.sucios.clear()
        return filas

    def cargar(self, filas) -> None:
        for fila in filas:
            self.conteos[fila["contexto"]][fila["siguiente"]] = fila["conteo"]
            if " " not in fila["contexto"]:
                self.unigramas[fila["siguiente"]] += fila["conteo"]
