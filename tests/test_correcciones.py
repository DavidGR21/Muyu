"""Enseñarle cuándo algo está bien y cuándo no: gestos de asentir y negar, palabras sí/no y negaciones."""

from server.brain.reasoning import CONFIRMADA, PENDIENTE, RECHAZADA
from tests.conftest import hablas


def conversar(muyu, reloj):
    def decir(texto, espera=4):
        reloj.avanzar(espera)
        return hablas(muyu.oir(texto))[-1]

    def hacer(accion, espera=3):
        reloj.avanzar(espera)
        return hablas(muyu.actuar(accion))[-1]

    return decir, hacer


def preguntar_fuego_duele(muyu, decir):
    decir("el fuego quema")
    decir("quemar duele")
    hipotesis = muyu.razonador.por_par("fuego", "duele")
    assert hipotesis.preguntada and hipotesis.estado == PENDIENTE
    return hipotesis


def test_no_une_conceptos_lejanos_en_la_frase(muyu, reloj):
    decir, _ = conversar(muyu, reloj)
    decir("yo soy David y él es Muyu")
    decir("el fuego, la mano")
    for a, b in (("david", "muyu"), ("fuego", "mano")):
        assert muyu.red.relacion(a, b) is None and muyu.red.relacion(b, a) is None


def test_una_respuesta_que_no_entiende_no_la_adivina(muyu, reloj):
    decir, hacer = conversar(muyu, reloj)
    hipotesis = preguntar_fuego_duele(muyu, decir)
    respuesta = decir("no")
    assert hipotesis.estado == PENDIENTE
    assert respuesta["intencion"] == "preguntar" and "niega" in respuesta["detalle"]
    hacer("negar")
    assert hipotesis.estado == RECHAZADA
    assert muyu.lexico.polar(-1, muyu.reloj.tiempo) == "no"


def test_aprendido_el_no_basta_con_decirlo(muyu, reloj):
    decir, hacer = conversar(muyu, reloj)
    preguntar_fuego_duele(muyu, decir)
    decir("no")
    hacer("negar")
    decir("el agua moja")
    decir("mojar enfría")
    otra = muyu.razonador.por_par("agua", "enfría")
    assert otra and otra.estado == PENDIENTE
    decir("no")
    assert otra.estado == RECHAZADA


def test_asentir_confirma_y_ensena_si(muyu, reloj):
    decir, hacer = conversar(muyu, reloj)
    hipotesis = preguntar_fuego_duele(muyu, decir)
    hacer("asentir")                 # primero el gesto…
    decir("sí")                      # …y enseguida la palabra
    assert hipotesis.estado == CONFIRMADA
    assert muyu.lexico.polar(1, muyu.reloj.tiempo) == "sí"


def test_negar_lo_ultimo_que_dijo_debilita_la_relacion(muyu, reloj):
    decir, hacer = conversar(muyu, reloj)
    for _ in range(3):
        decir("el perro come")
    antes = muyu.red.relacion("perro", "come").peso(muyu.reloj.tiempo)
    respuesta = decir("¿qué es perro?")
    assert respuesta["intencion"] == "describir"
    hacer("negar")
    relacion = muyu.red.relacion("perro", "come")
    assert relacion.peso(muyu.reloj.tiempo) < antes and relacion.negaciones == 1
    assert not muyu.lexico.es_polar("qué")   # una pregunta no le enseña qué significa el gesto


def test_negar_debilita_tambien_lo_que_se_apoyaba_en_eso(muyu, reloj):
    decir, hacer = conversar(muyu, reloj)
    hipotesis = preguntar_fuego_duele(muyu, decir)
    decir("¿qué es fuego?")          # responde «quema»: lo último que dijo ya no es la pregunta
    hacer("negar")
    assert muyu.red.relacion("fuego", "quema").negaciones == 1
    assert hipotesis.estado == RECHAZADA


def test_la_negacion_vale_en_ambos_sentidos(muyu, reloj):
    decir, hacer = conversar(muyu, reloj)
    preguntar_fuego_duele(muyu, decir)
    decir("no")
    hacer("negar")
    decir("papá Muyu")
    assert muyu.red.relacion("papá", "muyu")
    respuesta = decir("Muyu no es papá")
    assert respuesta["intencion"] == "negar"
    assert muyu.red.relacion("papá", "muyu").negaciones == 1
    assert muyu.red.relacion("muyu", "papá") is None
