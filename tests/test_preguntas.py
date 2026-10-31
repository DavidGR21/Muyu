from server.brain.questions import responder
from tests.conftest import frase
from tests.test_razonamiento import ensenar

SEMANA = 3600 * 24 * 7


def preguntar(contexto, texto, ahora=0):
    lexico, red, razonador, _ = contexto
    f = frase(texto)
    lexico.oir(f, ahora)
    return responder(f, lexico, red, razonador, ahora)


def test_si_no_encuentra_el_camino():
    contexto = ensenar(["el fuego quema"])
    intencion = preguntar(contexto, "¿el fuego quema?")
    assert intencion.tipo == "afirmar"
    assert intencion.conceptos[0] == "quema"


def test_si_no_sin_camino_duda():
    contexto = ensenar(["el fuego quema", "el agua moja"])
    assert preguntar(contexto, "¿el fuego moja?").tipo == "dudar"


def test_pregunta_abierta_describe_en_cadena():
    contexto = ensenar(["el fuego quema", "quemar duele"])
    _, _, razonador, (hipotesis,) = contexto
    razonador.confirmar(hipotesis, 0, "sí")
    intencion = preguntar(contexto, "¿qué es fuego?")
    assert intencion.tipo == "describir"
    assert intencion.conceptos[:2] == ["quema", "duele"]


def test_que_pasa_si_encadena_relaciones():
    contexto = ensenar(["el fuego quema la mano"])
    intencion = preguntar(contexto, "¿qué pasa si toco el fuego?")
    assert intencion.tipo == "describir"
    assert intencion.conceptos == ["quema", "mano"]


def test_sin_respuesta_muestra_confusion_y_devuelve_la_pregunta():
    contexto = ensenar(["el fuego quema"])
    intencion = preguntar(contexto, "¿qué es agua?")
    assert intencion.tipo == "confusion"
    assert intencion.conceptos == ["agua", "qué"]


def test_te_gusta_consulta_la_valencia():
    contexto = ensenar(["me gusta", "me gusta", "la pelota rebota", "el fuego quema"])
    lexico = contexto[0]
    for _ in range(3):
        lexico.asociar_senal({"gusta": 1.0, "pelota": 0.8}, 1.0)
        lexico.asociar_senal({"fuego": 0.8}, -1.0)
    assert preguntar(contexto, "¿te gusta la pelota?").tipo == "afirmar"
    assert preguntar(contexto, "¿te gusta el fuego?").tipo == "negar"


def test_si_lo_sabia_pero_esta_latente_responde_con_duda():
    contexto = ensenar(["el fuego quema"])
    intencion = preguntar(contexto, "¿el fuego quema?", ahora=SEMANA)
    assert intencion.tipo == "recordar_dudoso"
    assert intencion.seguridad < 0.5
