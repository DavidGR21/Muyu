"""Responder preguntas buscando la respuesta en su propia red de conceptos.

Los tipos de pregunta no vienen programados; salen de lo que sabe:

* Si la pregunta nombra dos conceptos que conoce, busca un camino entre ellos:
  es una verificación (sí / no).
* Si trae una palabra con carga emocional fuerte ("gusta", "malo") y otro
  concepto, compara sus valencias: es una pregunta de opinión.
* Si nombra un solo concepto, o empieza con una palabra que aprendió que abre
  preguntas ("qué"), describe lo que sabe de él encadenando relaciones.
* Si no conoce nada, muestra confusión y devuelve la pregunta ("¿agua… qué?").
"""

from __future__ import annotations

from server import config
from server.brain.concepts import RedConceptos
from server.brain.language.speaker import Intencion
from server.brain.lexicon import Lexico
from server.brain.perception import Frase
from server.brain.reasoning import RECHAZADA, Camino, Razonador


def responder(frase: Frase, lexico: Lexico, red: RedConceptos, razonador: Razonador, ahora: float) -> Intencion:
    palabras = frase.palabras
    marcadores = [p for p in palabras if lexico.es_interrogativa(p)]
    conocidos = [p for p in dict.fromkeys(palabras) if p in red.nodos and lexico.es_concepto(p, tolerancia=0.8)]

    if not conocidos:
        return _no_sabe(palabras, lexico, marcadores)

    if len(conocidos) >= 2 and not marcadores:
        camino = _mejor_camino_entre(conocidos, razonador, ahora)
        if camino:
            return _verificar(camino)

    valorativa = _palabra_valorativa(palabras, lexico)
    objetivo = next((c for c in conocidos if c != valorativa), None)
    if valorativa and objetivo:
        return _opinar(objetivo, valorativa, lexico, red, ahora)

    if len(conocidos) >= 2 and not marcadores:
        negada = _negada(conocidos, red, razonador)
        if negada:
            return negada
        a, b = conocidos[:2]
        return Intencion("dudar", [a, b], seguridad=0.2,
                         detalle=f"No encuentra ningún camino entre «{a}» y «{b}»")

    principal = max(conocidos, key=lambda c: sum(p for _, p in red.salientes_de(c, ahora)) + 0.01)
    return _describir(principal, lexico, red, razonador, ahora, marcadores)


def _no_sabe(palabras: list[str], lexico: Lexico, marcadores: list[str]) -> Intencion:
    desconocidas = [p for p in palabras if p not in marcadores] or palabras
    objetivo = max(desconocidas, key=lambda p: (lexico.informatividad(p), palabras.index(p)))
    if marcadores:
        marcador = marcadores[0]
    else:
        marcador = palabras[0] if palabras[0] != objetivo else None
    conceptos = [objetivo] + ([marcador] if marcador else [])
    return Intencion("confusion", conceptos, seguridad=0.1, gesto="confusion",
                     detalle=f"No sabe nada de «{objetivo}»: devuelve la pregunta para que le enseñen")


def _mejor_camino_entre(conocidos: list[str], razonador: Razonador, ahora: float) -> Camino | None:
    mejor: Camino | None = None
    for i, a in enumerate(conocidos):
        for b in conocidos[i + 1:]:
            for origen, destino, factor in ((a, b, 1.0), (b, a, 0.9)):
                camino = razonador.mejor_camino(origen, destino, ahora)
                if camino and (mejor is None or camino.fuerza * factor > mejor.fuerza):
                    camino.fuerza *= factor
                    mejor = camino
    return mejor


def _verificar(camino: Camino) -> Intencion:
    origen, destino, texto, fuerza = camino.nodos[0], camino.nodos[-1], camino.texto(), camino.fuerza
    if camino.latente:
        return Intencion("recordar_dudoso", [destino, origen], seguridad=0.3, tema=origen,
                         detalle=f"Lo sabía, pero está latente: {texto} (fuerza {fuerza:.2f})")
    if fuerza >= config.UMBRAL_SEGURO:
        return Intencion("afirmar", [destino], seguridad=0.9, tema=origen,
                         detalle=f"Encontró {texto} (fuerza {fuerza:.2f}): sí")
    return Intencion("afirmar", [destino], seguridad=0.35, tema=origen,
                     detalle=f"Encontró {texto}, pero es débil (fuerza {fuerza:.2f}): cree que sí")


def _negada(conocidos: list[str], red: RedConceptos, razonador: Razonador) -> Intencion | None:
    for i, a in enumerate(conocidos):
        for b in conocidos[i + 1:]:
            for origen, destino in ((a, b), (b, a)):
                relacion = red.relacion(origen, destino)
                hipotesis = razonador.por_par(origen, destino)
                if (relacion and relacion.negaciones) or (hipotesis and hipotesis.estado == RECHAZADA):
                    return Intencion("negar", [b], seguridad=0.7, gesto="negar", tema=a,
                                     detalle=f"Le enseñaron que «{origen}» y «{destino}» no van juntos")
    return None


def _palabra_valorativa(palabras: list[str], lexico: Lexico) -> str | None:
    candidatas = [
        p for p in palabras
        if abs(lexico.valencia(p)) >= config.UMBRAL_VALORATIVA and lexico.get(p) and lexico.get(p).frecuencia >= 2
    ]
    return max(candidatas, key=lambda p: abs(lexico.valencia(p)), default=None)


def _opinar(objetivo: str, valorativa: str, lexico: Lexico, red: RedConceptos, ahora: float) -> Intencion:
    propia = red.valencia(objetivo, lexico.valencia, ahora)
    referencia = lexico.valencia(valorativa)
    detalle = f"«{objetivo}» le provoca {propia:+.2f}; «{valorativa}» significa {referencia:+.2f}"
    if abs(propia) < 0.15:
        return Intencion("dudar", [objetivo], seguridad=0.3, tema=objetivo, detalle=detalle + ": todavía no tiene opinión")
    expresion = lexico.valorativa(1 if propia > 0 else -1, ahora, excluir=(objetivo,))
    if propia * referencia > 0:
        return Intencion("afirmar", [expresion or valorativa], seguridad=0.8, tema=objetivo,
                         detalle=detalle + ": coincide")
    return Intencion("negar", [objetivo] + ([expresion] if expresion else []), seguridad=0.8, tema=objetivo,
                     detalle=detalle + ": no coincide")


def _alcanza(a: str, b: str, razonador: Razonador, ahora: float) -> bool:
    return bool(razonador.caminos(a, ahora, 2, config.UMBRAL_TENUE, destino=b))


def _describir(nodo: str, lexico: Lexico, red: RedConceptos, razonador: Razonador, ahora: float,
               marcadores: list[str]) -> Intencion:
    relaciones = red.salientes_de(nodo, ahora, config.UMBRAL_TENUE)[:3]
    if not relaciones:
        latentes = [(r, p) for r, p in red.salientes_de(nodo, ahora) if not r.negaciones][:1]
        if latentes:
            relacion, peso = latentes[0]
            return Intencion("recordar_dudoso", [relacion.destino, nodo], seguridad=0.3, tema=nodo,
                             detalle=f"Sabía algo de «{nodo}», pero está latente: {nodo} → {relacion.destino} ({peso:.2f})")
        entrantes = red.entrantes_de(nodo, ahora, config.UMBRAL_TENUE)[:2]
        if entrantes:
            origenes = [r.origen for r, _ in entrantes]
            return Intencion("describir", origenes, seguridad=0.5, tema=nodo,
                             detalle=f"De «{nodo}» solo sabe qué lo acompaña: {', '.join(origenes)}")
        conceptos = [nodo] + marcadores[:1]
        return Intencion("confusion", conceptos, seguridad=0.1, gesto="confusion",
                         detalle=f"Conoce la palabra «{nodo}», pero no sabe nada de ella")

    partes: list[str] = []
    for relacion, _ in relaciones:
        for parte in (relacion.etiqueta, relacion.destino):
            if parte and parte != nodo and parte not in partes:
                partes.append(parte)

    ordenadas: list[str] = []
    for parte in partes:
        posicion = len(ordenadas)
        for indice, otra in enumerate(ordenadas):
            if _alcanza(parte, otra, razonador, ahora) and not _alcanza(otra, parte, razonador, ahora):
                posicion = indice
                break
        ordenadas.insert(posicion, parte)

    valencia = red.valencia(nodo, lexico.valencia, ahora)
    if abs(valencia) >= 0.3:
        opinion = lexico.valorativa(1 if valencia > 0 else -1, ahora, excluir=(nodo, *ordenadas))
        if opinion:
            ordenadas.append(opinion)

    explicacion = "; ".join(f"{nodo} → {r.destino} ({p:.2f})" for r, p in relaciones)
    return Intencion("describir", ordenadas, seguridad=0.7, tema=nodo, detalle=f"Lo que sabe de «{nodo}»: {explicacion}")
