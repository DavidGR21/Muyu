import random

from server import config
from server.brain.concepts import DEDUCIDO, RedConceptos
from server.brain.importance import ACTIVO
from server.brain.lexicon import Lexico
from server.brain.reasoning import CONFIRMADA, PENDIENTE, RECHAZADA, Razonador
from tests.conftest import frase


def ensenar(textos, deducir=True):
    lexico, red = Lexico(), RedConceptos()
    razonador = Razonador(red, lexico)
    hipotesis = []
    for texto in textos:
        f = frase(texto)
        lexico.oir(f, 0)
        resultado = red.aprender([p for p in f.palabras if lexico.es_concepto(p)], 0)
        if deducir:
            hipotesis += razonador.deducir(resultado.nuevas + resultado.reforzadas, 0)
    return lexico, red, razonador, hipotesis


def test_deduce_fuego_duele_sin_que_se_lo_ensenen():
    _, _, _, hipotesis = ensenar(["el fuego quema", "quemar duele"])
    assert [(h.origen, h.destino) for h in hipotesis] == [("fuego", "duele")]
    h = hipotesis[0]
    assert h.camino.texto() == "fuego → quema ≈ quemar → duele"
    assert h.estado == PENDIENTE
    assert 0 < h.confianza < config.UMBRAL_AFIRMAR   # poca confianza: lo pregunta


def test_el_parecido_de_forma_solo_no_es_una_deduccion():
    _, _, razonador, _ = ensenar(["el fuego quema", "quemar duele"])
    assert razonador.por_par("quema", "duele") is None


def test_no_vuelve_a_proponer_lo_mismo():
    _, red, razonador, _ = ensenar(["el fuego quema", "quemar duele"])
    assert razonador.deducir(list(red.relaciones.values()), 0) == []


def test_confirmar_vuelve_conocimiento_la_deduccion():
    _, red, razonador, (h,) = ensenar(["el fuego quema", "quemar duele"])
    relacion = razonador.confirmar(h, 0, "el dueño dijo que sí")
    assert h.estado == CONFIRMADA
    assert relacion.origen_dato == DEDUCIDO
    assert red.relacion("fuego", "duele").huella.estado(0) == ACTIVO


def test_rechazar_la_atenua_pero_la_recuerda():
    _, _, razonador, (h,) = ensenar(["el fuego quema", "quemar duele"])
    antes = h.huella.valor(0)
    razonador.rechazar(h, 0, "el dueño dijo que no")
    assert h.estado == RECHAZADA
    assert h.huella.valor(0) < antes
    assert razonador.por_par("fuego", "duele") is h


def test_al_pensar_sola_descubre_cadenas():
    _, _, razonador, hipotesis = ensenar(["el fuego quema", "quemar duele"], deducir=False)
    assert hipotesis == []
    nueva = razonador.explorar("fuego", 0, random.Random(1))
    assert (nueva.origen, nueva.destino, nueva.fuente) == ("fuego", "duele", "pensamiento")
