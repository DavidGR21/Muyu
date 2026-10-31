"""Razonamiento sobre la red de conceptos: encadenar, deducir, confirmar y corregir.

Si sabe ``A → B`` y ``B → C`` propone ``A → C`` como hipótesis. El parecido de
forma sirve de puente (fuego → quema ≈ quemar → duele), pero un camino necesita
al menos dos asociaciones aprendidas: lo de la forma solo no es una deducción.
La confianza es el producto de los pesos del camino; si es baja, pregunta.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from server import config
from server.brain.concepts import DEDUCIDO, RedConceptos, Relacion
from server.brain.importance import Huella
from server.brain.lexicon import Lexico

PENDIENTE = "pendiente"
CONFIRMADA = "confirmada"
RECHAZADA = "rechazada"

ASOCIACION = "asoc"
FORMA = "forma"


@dataclass
class Camino:
    nodos: list[str]
    enlaces: list[str]
    fuerza: float
    latente: bool = False

    @property
    def asociaciones(self) -> int:
        return self.enlaces.count(ASOCIACION)

    def pares(self) -> list[tuple[str, str]]:
        return [(a, b) for a, b, tipo in zip(self.nodos, self.nodos[1:], self.enlaces) if tipo == ASOCIACION]

    def texto(self) -> str:
        partes = [self.nodos[0]]
        for nodo, tipo in zip(self.nodos[1:], self.enlaces):
            partes.append(("→ " if tipo == ASOCIACION else "≈ ") + nodo)
        return " ".join(partes)


@dataclass
class Hipotesis:
    id: int
    origen: str
    destino: str
    camino: Camino
    confianza: float
    huella: Huella
    creada: float
    estado: str = PENDIENTE
    preguntada: bool = False
    resuelta: float | None = None
    motivo: str = ""
    fuente: str = "conversacion"    # conversacion | pensamiento

    def a_fila(self) -> dict:
        return {
            "id": self.id,
            "origen": self.origen,
            "destino": self.destino,
            "camino": json.dumps({"nodos": self.camino.nodos, "enlaces": self.camino.enlaces}),
            "confianza": self.confianza,
            "estado": self.estado,
            "preguntada": int(self.preguntada),
            "creada": self.creada,
            "resuelta": self.resuelta,
            "motivo": self.motivo,
            "fuente": self.fuente,
            **self.huella.a_fila(),
        }

    @classmethod
    def desde_fila(cls, fila) -> Hipotesis:
        datos = json.loads(fila["camino"])
        camino = Camino(datos["nodos"], datos["enlaces"], fila["confianza"])
        return cls(fila["id"], fila["origen"], fila["destino"], camino, fila["confianza"], Huella.desde_fila(fila),
                   fila["creada"], fila["estado"], bool(fila["preguntada"]), fila["resuelta"], fila["motivo"] or "",
                   fila["fuente"] or "conversacion")

    def a_publico(self, ahora: float) -> dict:
        return {
            "id": self.id,
            "origen": self.origen,
            "destino": self.destino,
            "camino": self.camino.texto(),
            "confianza": round(self.confianza, 3),
            "estado": self.estado,
            "preguntada": self.preguntada,
            "motivo": self.motivo,
            "fuente": self.fuente,
            **self.huella.a_publico(ahora),
        }


@dataclass
class Razonador:
    red: RedConceptos
    lexico: Lexico
    hipotesis: dict[int, Hipotesis] = field(default_factory=dict)
    sucias: set[int] = field(default_factory=set)

    # ── Caminos ──────────────────────────────────────────────────────────

    def _expandir(self, nodo: str, ahora: float, minimo: float):
        for relacion, peso in self.red.salientes_de(nodo, ahora, minimo)[: config.RAMAS_MAXIMAS]:
            yield relacion.destino, peso, ASOCIACION
        for otro, similitud in self.red.parecidos(nodo).items():
            yield otro, similitud, FORMA

    def caminos(self, inicio: str, ahora: float, max_asociaciones: int = 2,
                minimo: float = config.UMBRAL_TENUE, destino: str | None = None) -> list[Camino]:
        """Caminos simples desde ``inicio``. Un parecido de forma no cuenta como paso,
        pero no puede haber dos seguidos ni más de dos por camino."""
        resultados: list[Camino] = []
        destinos = {destino} | set(self.red.parecidos(destino)) if destino else None

        def explorar(nodos: list[str], enlaces: list[str], fuerza: float, asociaciones: int) -> None:
            for siguiente, peso, tipo in self._expandir(nodos[-1], ahora, minimo):
                if siguiente in nodos:
                    continue
                if tipo == FORMA:
                    if (enlaces and enlaces[-1] == FORMA) or enlaces.count(FORMA) >= 2:
                        continue
                    explorar(nodos + [siguiente], enlaces + [FORMA], fuerza * peso, asociaciones)
                    continue
                camino = Camino(nodos + [siguiente], enlaces + [ASOCIACION], fuerza * peso)
                llega = destinos is None or siguiente in destinos
                if llega:
                    if destino and siguiente != destino:
                        camino.fuerza *= self.red.parecidos(destino).get(siguiente, 1.0)
                    resultados.append(camino)
                if asociaciones + 1 < max_asociaciones and not (destino and llega):
                    explorar(camino.nodos, camino.enlaces, camino.fuerza, asociaciones + 1)

        explorar([inicio], [], 1.0, 0)
        for camino in resultados:
            camino.latente = any(
                self.red.relacion(a, b).peso(ahora) < config.UMBRAL_TENUE for a, b in camino.pares()
            )
        return resultados

    def mejor_camino(self, origen: str, destino: str, ahora: float, max_asociaciones: int = 3) -> Camino | None:
        """Para verificar ("¿el fuego quema?"): incluye lo latente, marcado como tal."""
        caminos = self.caminos(origen, ahora, max_asociaciones, config.IMPORTANCIA_MINIMA, destino)
        return max(caminos, key=lambda c: c.fuerza, default=None)

    # ── Deducción ────────────────────────────────────────────────────────

    def deducir(self, relaciones: list[Relacion], ahora: float, fuente: str = "conversacion",
                limite: int = 2) -> list[Hipotesis]:
        """Busca cadenas nuevas que pasen por las relaciones recién aprendidas."""
        candidatos: dict[tuple[str, str], Camino] = {}
        for relacion in relaciones:
            if relacion.peso(ahora) < config.UMBRAL_TENUE:
                continue
            clave = (relacion.origen, relacion.destino)
            inicios = {relacion.origen}
            for alias in [relacion.origen, *self.red.parecidos(relacion.origen)]:
                inicios.update(r.origen for r, _ in self.red.entrantes_de(alias, ahora, config.UMBRAL_TENUE))
            for inicio in inicios:
                for camino in self.caminos(inicio, ahora):
                    if camino.asociaciones == 2 and clave in camino.pares():
                        self._considerar(camino, ahora, candidatos)
        mejores = sorted(candidatos.values(), key=lambda c: -c.fuerza)[:limite]
        return [self._crear(camino, ahora, fuente) for camino in mejores]

    def explorar(self, inicio: str, ahora: float, rng) -> Hipotesis | None:
        """Al pensar sola: recorre la red desde ``inicio`` buscando algo que nadie le enseñó."""
        candidatos: dict[tuple[str, str], Camino] = {}
        for camino in self.caminos(inicio, ahora):
            if camino.asociaciones == 2:
                self._considerar(camino, ahora, candidatos)
        if not candidatos:
            return None
        caminos = list(candidatos.values())
        elegido = rng.choices(caminos, weights=[c.fuerza for c in caminos])[0]
        return self._crear(elegido, ahora, "pensamiento")

    def _considerar(self, camino: Camino, ahora: float, candidatos: dict) -> None:
        origen, destino = camino.nodos[0], camino.nodos[-1]
        if origen == destino or destino in self.red.parecidos(origen):
            return
        if self.red.relacion(origen, destino) or self.por_par(origen, destino):
            return
        if not (self.lexico.es_concepto(origen) and self.lexico.es_concepto(destino)):
            return
        if camino.fuerza < config.UMBRAL_HIPOTESIS:
            return
        actual = candidatos.get((origen, destino))
        if actual is None or camino.fuerza > actual.fuerza:
            candidatos[(origen, destino)] = camino

    def _crear(self, camino: Camino, ahora: float, fuente: str) -> Hipotesis:
        identificador = max(self.hipotesis, default=0) + 1
        hipotesis = Hipotesis(identificador, camino.nodos[0], camino.nodos[-1], camino, camino.fuerza,
                              Huella.nueva(ahora), ahora, fuente=fuente)
        self.hipotesis[identificador] = hipotesis
        self.sucias.add(identificador)
        return hipotesis

    # ── Confirmación y corrección ────────────────────────────────────────

    def por_par(self, origen: str, destino: str) -> Hipotesis | None:
        for hipotesis in self.hipotesis.values():
            if hipotesis.origen == origen and hipotesis.destino == destino:
                return hipotesis
        return None

    def pendientes(self) -> list[Hipotesis]:
        return [h for h in self.hipotesis.values() if h.estado == PENDIENTE]

    def confirmar(self, hipotesis: Hipotesis, ahora: float, motivo: str) -> Relacion:
        """La deducción se vuelve conocimiento."""
        hipotesis.estado, hipotesis.resuelta, hipotesis.motivo = CONFIRMADA, ahora, motivo
        hipotesis.huella.elevar(ahora, 0.6)
        relacion, _ = self.red.asociar(hipotesis.origen, hipotesis.destino, ahora, origen_dato=DEDUCIDO)
        relacion.huella.elevar(ahora, 0.55)
        for origen, destino in hipotesis.camino.pares():
            enlace = self.red.relacion(origen, destino)
            if enlace:
                enlace.huella.reforzar(ahora, 0.5)
                self.red.sucias_relaciones.add((origen, destino))
        self.sucias.add(hipotesis.id)
        return relacion

    def rechazar(self, hipotesis: Hipotesis, ahora: float, motivo: str) -> None:
        """Baja su importancia, pero recuerda que alguna vez lo creyó."""
        hipotesis.estado, hipotesis.resuelta, hipotesis.motivo = RECHAZADA, ahora, motivo
        hipotesis.huella.atenuar(ahora, 0.5)
        relacion = self.red.relacion(hipotesis.origen, hipotesis.destino)
        if relacion and relacion.origen_dato == DEDUCIDO:
            relacion.huella.atenuar(ahora, 0.2)
            relacion.negaciones += 1
            self.red.sucias_relaciones.add((relacion.origen, relacion.destino))
        self.sucias.add(hipotesis.id)

    def invalidar(self, origen: str, destino: str, ahora: float) -> list[Hipotesis]:
        """Descarta las deducciones pendientes que se apoyaban en una relación desmentida."""
        caidas = []
        for hipotesis in self.pendientes():
            if (origen, destino) in hipotesis.camino.pares():
                self.rechazar(hipotesis, ahora, f"se apoyaba en {origen} → {destino}, que no es así")
                caidas.append(hipotesis)
        return caidas

    def a_publico(self, ahora: float) -> list[dict]:
        return [h.a_publico(ahora) for h in sorted(self.hipotesis.values(), key=lambda h: -h.id)]
