"""Red de conceptos: el conocimiento de Muyu, un grafo dirigido que nace vacío.

* Los nodos son palabras informativas.
* Las aristas se crean y fortalecen por aprendizaje hebbiano: lo que aparece
  junto se conecta. La etiqueta es la palabra que suele unirlos
  ("el fuego quema la mano" → fuego ─[quema]→ mano).
* El peso de una arista es su importancia: se atenúa sin usarse, nunca se borra.
* El parecido de forma (quema ≈ quemar) no se guarda: es un instinto perceptivo
  que se calcula al vuelo.
"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field

from server import config
from server.brain import instincts
from server.brain.importance import Huella, LATENTE

ENSENADO = "enseñado"
DEDUCIDO = "deducido"


@dataclass
class Concepto:
    nodo: str
    huella: Huella
    activacion: float = 0.0
    activada_real: float = 0.0
    valencia: float = 0.0           # última valencia efectiva calculada (para el panel)
    categoria: str | None = None    # categorías emergentes: fase 4

    def activacion_en(self, ahora_real: float) -> float:
        transcurrido = max(0.0, ahora_real - self.activada_real)
        return self.activacion * 0.5 ** (transcurrido / config.VIDA_MEDIA_ACTIVACION_S)

    def a_fila(self) -> dict:
        return {
            "nodo": self.nodo,
            "activacion": self.activacion,
            "activada_real": self.activada_real,
            "valencia": self.valencia,
            "categoria": self.categoria,
            **self.huella.a_fila(),
        }

    @classmethod
    def desde_fila(cls, fila) -> Concepto:
        return cls(fila["nodo"], Huella.desde_fila(fila), fila["activacion"], fila["activada_real"],
                   fila["valencia"], fila["categoria"])


@dataclass
class Relacion:
    origen: str
    destino: str
    huella: Huella
    etiquetas: dict[str, int] = field(default_factory=dict)
    origen_dato: str = ENSENADO
    negaciones: int = 0

    @property
    def etiqueta(self) -> str | None:
        return max(self.etiquetas, key=self.etiquetas.get) if self.etiquetas else None

    def peso(self, ahora: float) -> float:
        return self.huella.valor(ahora)

    def a_fila(self, ahora: float) -> dict:
        return {
            "origen": self.origen,
            "destino": self.destino,
            "etiqueta": self.etiqueta,
            "etiquetas": json.dumps(self.etiquetas),
            "peso": round(self.peso(ahora), 4),
            "origen_dato": self.origen_dato,
            "negaciones": self.negaciones,
            **self.huella.a_fila(),
        }

    @classmethod
    def desde_fila(cls, fila) -> Relacion:
        return cls(fila["origen"], fila["destino"], Huella.desde_fila(fila), json.loads(fila["etiquetas"] or "{}"),
                   fila["origen_dato"], fila["negaciones"])


@dataclass
class Aprendizaje:
    nuevas: list[Relacion] = field(default_factory=list)
    reforzadas: list[Relacion] = field(default_factory=list)
    contradichas: list[Relacion] = field(default_factory=list)
    negadas: list[tuple[str, str]] = field(default_factory=list)
    nodos_nuevos: list[str] = field(default_factory=list)


class RedConceptos:
    def __init__(self) -> None:
        self.nodos: dict[str, Concepto] = {}
        self.relaciones: dict[tuple[str, str], Relacion] = {}
        self.salientes: dict[str, set[str]] = defaultdict(set)
        self.entrantes: dict[str, set[str]] = defaultdict(set)
        self._por_prefijo: dict[str, set[str]] = defaultdict(set)
        self.sucios_nodos: set[str] = set()
        self.sucias_relaciones: set[tuple[str, str]] = set()

    # ── Nodos ────────────────────────────────────────────────────────────

    def asegurar(self, nodo: str, ahora: float, intensidad: float = 1.0) -> tuple[Concepto, bool]:
        concepto = self.nodos.get(nodo)
        if concepto is None:
            concepto = Concepto(nodo, Huella.nueva(ahora))
            self.agregar_nodo(concepto)
            return concepto, True
        concepto.huella.reforzar(ahora, intensidad)
        self.sucios_nodos.add(nodo)
        return concepto, False

    def agregar_nodo(self, concepto: Concepto) -> None:
        self.nodos[concepto.nodo] = concepto
        self._por_prefijo[concepto.nodo[: config.PREFIJO_FORMA_MIN]].add(concepto.nodo)
        self.sucios_nodos.add(concepto.nodo)

    def reforzar_nodo(self, nodo: str, ahora: float, intensidad: float) -> None:
        concepto = self.nodos.get(nodo)
        if concepto:
            concepto.huella.reforzar(ahora, intensidad)
            self.sucios_nodos.add(nodo)

    def parecidos(self, nodo: str) -> dict[str, float]:
        """Conceptos que suenan parecido a ``nodo`` (instinto, no conocimiento)."""
        if len(nodo) < config.PREFIJO_FORMA_MIN:
            return {}
        resultado = {}
        for otro in self._por_prefijo.get(nodo[: config.PREFIJO_FORMA_MIN], ()):
            similitud = instincts.parecido_de_forma(nodo, otro)
            if similitud:
                resultado[otro] = similitud
        return resultado

    # ── Relaciones ───────────────────────────────────────────────────────

    def relacion(self, origen: str, destino: str) -> Relacion | None:
        return self.relaciones.get((origen, destino))

    def agregar_relacion(self, relacion: Relacion) -> None:
        clave = (relacion.origen, relacion.destino)
        self.relaciones[clave] = relacion
        self.salientes[relacion.origen].add(relacion.destino)
        self.entrantes[relacion.destino].add(relacion.origen)
        self.sucias_relaciones.add(clave)

    def asociar(self, origen: str, destino: str, ahora: float, intensidad: float = 1.0,
                etiqueta: str | None = None, origen_dato: str = ENSENADO) -> tuple[Relacion, bool]:
        relacion = self.relaciones.get((origen, destino))
        nueva = relacion is None
        if nueva:
            for nodo in (origen, destino):
                if nodo not in self.nodos:
                    self.asegurar(nodo, ahora)
            relacion = Relacion(origen, destino, Huella.nueva(ahora), origen_dato=origen_dato)
            self.agregar_relacion(relacion)
        else:
            relacion.huella.reforzar(ahora, intensidad)
        if etiqueta:
            relacion.etiquetas[etiqueta] = relacion.etiquetas.get(etiqueta, 0) + 1
        self.sucias_relaciones.add((origen, destino))
        return relacion, nueva

    def aprender(self, conceptos: list[str], ahora: float, intensidad: float = 1.0,
                 negadas: set[tuple[int, int]] | frozenset = frozenset(),
                 posiciones: list[int] | None = None) -> Aprendizaje:
        """Aprendizaje hebbiano sobre los conceptos de una frase, en orden.

        Solo se conecta lo que estuvo realmente cerca: ``posiciones`` es la
        distancia en palabras (con las pausas) de cada concepto al inicio de la
        frase. En "yo soy David y él es Muyu" David y Muyu quedan lejos.
        """
        posiciones = list(range(len(conceptos))) if posiciones is None else posiciones
        resultado = Aprendizaje()
        for nodo in conceptos:
            _, nuevo = self.asegurar(nodo, ahora, intensidad)
            if nuevo:
                resultado.nodos_nuevos.append(nodo)
        for i, origen in enumerate(conceptos):
            for j in range(i + 1, len(conceptos)):
                if posiciones[j] - posiciones[i] > config.DISTANCIA_HEBBIANA:
                    break
                destino = conceptos[j]
                if destino == origen:
                    continue
                if (i, j) in negadas:
                    resultado.negadas.append((origen, destino))
                    resultado.contradichas += self.contradecir_par(origen, destino, ahora)
                    continue
                etiqueta = conceptos[i + 1] if j - i == 2 else None
                relacion, nueva = self.asociar(origen, destino, ahora, intensidad, etiqueta)
                (resultado.nuevas if nueva else resultado.reforzadas).append(relacion)
        return resultado

    def contradecir(self, origen: str, destino: str, ahora: float) -> Relacion | None:
        """Le dicen lo contrario de algo que sabía: baja su peso (sin borrarlo)."""
        relacion = self.relaciones.get((origen, destino))
        if relacion is None:
            return None
        sabia = relacion.huella.estado(ahora) != LATENTE
        relacion.huella.atenuar(ahora, config.FACTOR_CONTRADICCION)
        relacion.negaciones += 1
        self.sucias_relaciones.add((origen, destino))
        return relacion if sabia else None

    def contradecir_par(self, a: str, b: str, ahora: float) -> list[Relacion]:
        """Negar que dos conceptos van juntos debilita la relación en ambos sentidos."""
        return [r for r in (self.contradecir(a, b, ahora), self.contradecir(b, a, ahora)) if r]

    def salientes_de(self, nodo: str, ahora: float, minimo: float = 0.0) -> list[tuple[Relacion, float]]:
        """Relaciones que salen de ``nodo``, de la más fuerte a la más débil."""
        resultado = []
        for destino in self.salientes.get(nodo, ()):
            relacion = self.relaciones[(nodo, destino)]
            peso = relacion.peso(ahora)
            if peso >= minimo:
                resultado.append((relacion, peso))
        resultado.sort(key=lambda par: -par[1])
        return resultado

    def entrantes_de(self, nodo: str, ahora: float, minimo: float = 0.0) -> list[tuple[Relacion, float]]:
        resultado = []
        for origen in self.entrantes.get(nodo, ()):
            relacion = self.relaciones[(origen, nodo)]
            peso = relacion.peso(ahora)
            if peso >= minimo:
                resultado.append((relacion, peso))
        resultado.sort(key=lambda par: -par[1])
        return resultado

    def vecinos(self, nodo: str, ahora: float) -> list[tuple[str, float]]:
        """Todo lo conectado a ``nodo`` en ambos sentidos (hacia atrás pesa la mitad)."""
        vecinos = [(r.destino, p) for r, p in self.salientes_de(nodo, ahora)]
        vecinos += [(r.origen, p * 0.5) for r, p in self.entrantes_de(nodo, ahora)]
        return vecinos

    # ── Valencia y activación ────────────────────────────────────────────

    def valencia(self, nodo: str, valencias: Callable[[str], float], ahora: float) -> float:
        """Carga emocional del concepto: la suya y un poco la de sus vecinos."""
        propia = valencias(nodo)
        total = peso_total = 0.0
        for vecino, peso in self.vecinos(nodo, ahora):
            total += valencias(vecino) * peso
            peso_total += peso
        vecinal = total / peso_total if peso_total else 0.0
        valor = max(-1.0, min(1.0, 0.75 * propia + 0.25 * vecinal))
        if nodo in self.nodos:
            self.nodos[nodo].valencia = valor
        return valor

    def activar(self, semillas: dict[str, float], ahora: float, ahora_real: float) -> dict[str, float]:
        """Activación propagada: lo que oye despierta también lo relacionado."""
        alcanzados = {n: a for n, a in semillas.items() if n in self.nodos}
        frente = dict(alcanzados)
        for _ in range(2):
            siguiente: dict[str, float] = {}
            for nodo, activacion in frente.items():
                for vecino, peso in self.vecinos(nodo, ahora):
                    valor = activacion * config.PERDIDA_ACTIVACION * math.sqrt(peso)
                    if valor > max(alcanzados.get(vecino, 0.0), siguiente.get(vecino, 0.0)):
                        siguiente[vecino] = valor
            alcanzados.update(siguiente)
            frente = siguiente
        for nodo, activacion in alcanzados.items():
            concepto = self.nodos[nodo]
            if activacion > concepto.activacion_en(ahora_real):
                concepto.activacion = round(activacion, 4)
                concepto.activada_real = ahora_real
                self.sucios_nodos.add(nodo)
        return alcanzados

    def paseo(self, inicio: str, ahora: float, rng, pasos: int = 2) -> list[str]:
        """Caminata al azar por relaciones vivas, guiada por su peso."""
        camino = [inicio]
        for _ in range(pasos):
            opciones = [(r.destino, p) for r, p in self.salientes_de(camino[-1], ahora, config.UMBRAL_TENUE)
                        if r.destino not in camino]
            if not opciones:
                break
            destinos, pesos = zip(*opciones)
            camino.append(rng.choices(destinos, weights=pesos)[0])
        return camino

    # ── Panel ────────────────────────────────────────────────────────────

    def a_publico(self, ahora: float, ahora_real: float) -> dict:
        conceptos = [{
            "nodo": c.nodo,
            **c.huella.a_publico(ahora),
            "valencia": round(c.valencia, 3),
            "activacion": round(c.activacion_en(ahora_real), 3),
        } for c in self.nodos.values()]
        relaciones = [{
            "origen": r.origen,
            "destino": r.destino,
            "etiqueta": r.etiqueta,
            "peso": round(r.peso(ahora), 3),
            "estado": r.huella.estado(ahora),
            "origen_dato": r.origen_dato,
            "usos": r.huella.usos + 1,
            "negaciones": r.negaciones,
        } for r in self.relaciones.values()]
        forma = []
        for nodo in self.nodos:
            for otro, similitud in self.parecidos(nodo).items():
                if nodo < otro:
                    forma.append({"a": nodo, "b": otro, "similitud": similitud})
        return {"conceptos": conceptos, "relaciones": relaciones, "forma": forma}
