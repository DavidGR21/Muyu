"""Pensamiento propio: cuando nadie le habla, Muyu recorre lo que sabe.

Cada ciclo elige un punto de partida, camina por la red y produce un
pensamiento: un recuerdo, una deducción nueva, una duda, una opinión o el
reencuentro con algo latente. Pensar también es aprender: repasa lo que
recorre y puede descubrir conexiones que nadie le enseñó.
"""

from __future__ import annotations

import json
import random
from dataclasses import dataclass, field

import numpy as np

from server import config
from server.brain.concepts import RedConceptos
from server.brain.emotions import etiqueta_de
from server.brain.importance import LATENTE
from server.brain.language.speaker import Intencion
from server.brain.lexicon import Lexico
from server.brain.memory import MemoriaEpisodica
from server.brain.reasoning import Hipotesis, Razonador

RECUERDO = "recuerdo"
DEDUCCION = "deduccion"
DUDA = "duda"
OPINION = "opinion"
REENCUENTRO = "reencuentro"

NOVEDAD = {DEDUCCION: 1.6, REENCUENTRO: 1.3, DUDA: 1.2, OPINION: 1.0, RECUERDO: 0.8}
HABLA = {DUDA: "preguntar", OPINION: "opinar", REENCUENTRO: "reencuentro", RECUERDO: "recordar", "sueno": "sueno"}


def texto_conceptual(contenido: list[str], pregunta: bool = False, tipo: str | None = None) -> str:
    """Cómo se ve el pensamiento en el panel, sin los límites de su etapa de habla."""
    if not contenido:
        return "…"
    if tipo == REENCUENTRO:
        palabra = contenido[0]
        return f"¿{palabra}…? {palabra.capitalize()}…"
    if tipo == "correccion":
        return " ↔ ".join(contenido)
    texto = "… ".join(contenido)
    texto = f"¿{texto}?" if pregunta else texto
    for indice, caracter in enumerate(texto):
        if caracter.isalpha():
            return texto[:indice] + caracter.upper() + texto[indice + 1:]
    return texto


@dataclass
class Idea:
    tipo: str
    contenido: list[str]
    explicacion: str
    pregunta: bool = False
    hipotesis: Hipotesis | None = None
    valencia: float = 0.0

    def intencion(self) -> Intencion:
        if self.tipo == DEDUCCION:
            tipo = "preguntar" if self.pregunta else "deducir"
        else:
            tipo = HABLA[self.tipo]
        # Sin gesto propio: el cuerpo muestra lo que siente ahora, no lo que recuerda.
        tema = self.hipotesis.origen if self.hipotesis else None
        return Intencion(tipo, list(self.contenido), detalle=self.explicacion, tema=tema)


@dataclass
class Pensamiento:
    id: int
    momento: float
    momento_real: float
    tipo: str
    contenido: list[str]
    texto: str
    explicacion: str
    en_voz_alta: bool = False
    dicho: str = ""

    def a_fila(self) -> dict:
        return {
            "id": self.id,
            "momento": self.momento,
            "momento_real": self.momento_real,
            "tipo": self.tipo,
            "contenido": json.dumps(self.contenido, ensure_ascii=False),
            "texto": self.texto,
            "explicacion": self.explicacion,
            "en_voz_alta": int(self.en_voz_alta),
            "dicho": self.dicho,
        }

    @classmethod
    def desde_fila(cls, fila) -> Pensamiento:
        return cls(fila["id"], fila["momento"], fila["momento_real"], fila["tipo"], json.loads(fila["contenido"]),
                   fila["texto"], fila["explicacion"], bool(fila["en_voz_alta"]), fila["dicho"] or "")

    def a_publico(self) -> dict:
        return {
            "id": self.id,
            "momento": self.momento,
            "momento_real": self.momento_real,
            "tipo": self.tipo,
            "contenido": self.contenido,
            "texto": self.texto,
            "explicacion": self.explicacion,
            "en_voz_alta": self.en_voz_alta,
            "dicho": self.dicho,
        }


@dataclass
class ContextoPensamiento:
    lexico: Lexico
    red: RedConceptos
    razonador: Razonador
    memoria: MemoriaEpisodica
    rasgos: dict[str, float]
    ahora: float
    soledad: float = 0.0
    aburrimiento: float = 0.0
    placer: float = 0.0
    excluir: set[str] = field(default_factory=set)


class Pensador:
    def __init__(self, rng: random.Random) -> None:
        self.rng = rng

    def idear(self, ctx: ContextoPensamiento) -> Idea | None:
        vivos = self._conceptos_vivos(ctx)
        latentes = [n for n, c in ctx.red.nodos.items()
                    if c.huella.estado(ctx.ahora) == LATENTE and ctx.lexico.es_concepto(n)]
        valorados = [n for n in vivos if abs(ctx.red.valencia(n, ctx.lexico.valencia, ctx.ahora)) >= 0.3]
        curiosidad = ctx.rasgos["curiosidad"]
        modos = {
            RECUERDO: 1.0 if any(e.conceptos for e in ctx.memoria.recientes(50)) else 0.0,
            DEDUCCION: (0.8 + curiosidad) if ctx.red.relaciones else 0.0,
            DUDA: 1.3 if ctx.razonador.pendientes() else 0.0,
            OPINION: 0.7 if valorados else 0.0,
            REENCUENTRO: 0.5 * (0.5 + curiosidad) if latentes else 0.0,
        }
        if not any(modos.values()):
            return None
        modo = self.rng.choices(list(modos), weights=list(modos.values()))[0]
        idea = None
        if modo == DEDUCCION:
            idea = self._deducir(ctx, vivos)
        elif modo == DUDA:
            idea = self._dudar(ctx)
        elif modo == OPINION:
            idea = self._opinar(ctx, valorados)
        elif modo == REENCUENTRO:
            idea = self._reencontrar(ctx, latentes)
        return idea or self._recordar(ctx) or (self._pasear(ctx, vivos) if vivos else None)

    def en_voz_alta(self, idea: Idea, ctx: ContextoPensamiento) -> bool:
        """Las criaturas locuaces, solas o aburridas piensan más en voz alta; asustadas
        o tristes se callan."""
        probabilidad = 0.1 + 0.45 * ctx.rasgos["locuacidad"]
        probabilidad *= (1 + 0.8 * ctx.soledad + 0.6 * ctx.aburrimiento) * NOVEDAD.get(idea.tipo, 1.0)
        if ctx.placer < -0.3:
            probabilidad *= 0.35
        return self.rng.random() < min(0.9, probabilidad)

    # ── Modos ────────────────────────────────────────────────────────────

    def _conceptos_vivos(self, ctx: ContextoPensamiento) -> list[str]:
        return [n for n, c in ctx.red.nodos.items()
                if c.huella.estado(ctx.ahora) != LATENTE and ctx.lexico.es_concepto(n)]

    def _elegir_inicio(self, ctx: ContextoPensamiento, vivos: list[str]) -> str | None:
        if not vivos:
            return None
        pesos = [ctx.red.nodos[n].huella.valor(ctx.ahora) + 2 * ctx.red.nodos[n].activacion for n in vivos]
        return self.rng.choices(vivos, weights=pesos)[0]

    def _deducir(self, ctx: ContextoPensamiento, vivos: list[str]) -> Idea | None:
        inicio = self._elegir_inicio(ctx, vivos)
        if inicio is None:
            return None
        hipotesis = ctx.razonador.explorar(inicio, ctx.ahora, self.rng)
        if hipotesis is None:
            return self._pasear(ctx, [inicio])
        pregunta = hipotesis.confianza < config.UMBRAL_AFIRMAR
        return Idea(DEDUCCION, [hipotesis.origen, hipotesis.destino],
                    f"Encadenó {hipotesis.camino.texto()} sin que nadie se lo enseñara "
                    f"(confianza {hipotesis.confianza:.2f})", pregunta=pregunta, hipotesis=hipotesis)

    def _dudar(self, ctx: ContextoPensamiento) -> Idea | None:
        pendientes = ctx.razonador.pendientes()
        if not pendientes:
            return None
        hipotesis = self.rng.choice(pendientes)
        return Idea(DUDA, [hipotesis.origen, hipotesis.destino],
                    f"Sigue sin saber si {hipotesis.camino.texto()} es cierto", pregunta=True, hipotesis=hipotesis)

    def _opinar(self, ctx: ContextoPensamiento, valorados: list[str]) -> Idea | None:
        valencias = {n: ctx.red.valencia(n, ctx.lexico.valencia, ctx.ahora) for n in valorados}
        nodo = self.rng.choices(list(valencias), weights=[abs(v) for v in valencias.values()])[0]
        valencia = valencias[nodo]
        expresion = ctx.lexico.valorativa(1 if valencia > 0 else -1, ctx.ahora, excluir=(nodo,))
        contenido = [nodo] + ([expresion] if expresion else [])
        sentimiento = "le gusta" if valencia > 0 else "no le gusta"
        return Idea(OPINION, contenido, f"«{nodo}» {sentimiento} (valencia {valencia:+.2f})", valencia=valencia)

    def _reencontrar(self, ctx: ContextoPensamiento, latentes: list[str]) -> Idea:
        nodo = self.rng.choice(latentes)
        antes = ctx.red.nodos[nodo].huella.valor(ctx.ahora)
        ctx.red.reforzar_nodo(nodo, ctx.ahora, 0.6)
        ctx.lexico.reforzar(nodo, ctx.ahora, 0.5)
        despues = ctx.red.nodos[nodo].huella.valor(ctx.ahora)
        return Idea(REENCUENTRO, [nodo, nodo],
                    f"Pasó por «{nodo}», que estaba latente, y lo reactivó un poco ({antes:.2f} → {despues:.2f})")

    def _recordar(self, ctx: ContextoPensamiento) -> Idea | None:
        episodio = ctx.memoria.elegir_recuerdo(ctx.ahora, self.rng)
        if episodio is None:
            return None
        contenido = [c for c in dict.fromkeys(episodio.conceptos) if c in ctx.red.nodos][:3]
        if not contenido:
            return None
        placer = episodio.emocion[0]
        if episodio.evento.get("accion") and abs(placer) >= 0.3:
            # De una caricia o un regaño recuerda también cómo se sintió ("comida… bien").
            expresion = ctx.lexico.valorativa(1 if placer > 0 else -1, ctx.ahora, excluir=tuple(contenido))
            if expresion:
                contenido.append(expresion)
        episodio.huella.reforzar(ctx.ahora, 0.2)
        ctx.memoria.sucios.add(episodio.id)
        emocion = etiqueta_de(np.array(episodio.emocion))
        return Idea(RECUERDO, contenido, f"Recordó el episodio #{episodio.id} ({episodio.resumen()}), "
                                         f"cuando sintió {emocion}", valencia=placer)

    def _pasear(self, ctx: ContextoPensamiento, vivos: list[str]) -> Idea | None:
        inicio = self._elegir_inicio(ctx, vivos)
        if inicio is None:
            return None
        camino = ctx.red.paseo(inicio, ctx.ahora, self.rng)
        if len(camino) < 2:
            return None
        return Idea(RECUERDO, camino, f"Recorrió su red: {' → '.join(camino)}")
