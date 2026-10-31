from server import config
from server.brain.lexicon import Lexico
from tests.conftest import frase

MES = 3600 * 24 * 30


def test_registra_palabras_frecuencia_y_nombres_propios():
    lexico = Lexico()
    lexico.oir(frase("hola Muyu"), 0)
    lexico.oir(frase("hola"), 0)
    assert lexico.get("hola").frecuencia == 2
    assert lexico.get("muyu").frecuencia == 1
    assert lexico.get("muyu").grafia == "Muyu"
    assert lexico.total_frases == 2


def test_distingue_palabras_nuevas_de_latentes_que_reconoce():
    lexico = Lexico()
    assert lexico.oir(frase("lluvia"), 0).nuevas == ["lluvia"]
    oido = lexico.oir(frase("lluvia"), MES)
    assert oido.nuevas == []
    assert oido.reconocidas == ["lluvia"]


def test_informatividad_aprendida_sin_lista_de_palabras_vacias():
    lexico = Lexico()
    frases = [
        "el perro come", "el gato duerme", "el sol brilla", "el agua moja", "la casa es grande",
        "el niño juega", "el pan sabe rico", "el árbol crece", "el río suena", "la luna sale",
        "el viento sopla", "el fuego quema", "el pez nada", "la flor huele", "el tren pasa",
        "el bebé ríe", "el gallo canta", "el carro corre", "la lluvia cae", "el libro enseña",
    ]
    for texto in frases:
        lexico.oir(frase(texto), 0)
    assert lexico.informatividad("el") < config.UMBRAL_CONCEPTO <= lexico.informatividad("perro")
    assert not lexico.es_concepto("el")
    assert lexico.es_concepto("perro")


def test_valencia_sale_de_las_senales_primarias():
    lexico = Lexico()
    lexico.oir(frase("bien"), 0)
    lexico.oir(frase("malo"), 0)
    for _ in range(3):
        lexico.asociar_senal({"bien": 1.0}, 1.0, "acariciar")
        lexico.asociar_senal({"malo": 1.0}, -1.0, "regañar")
    assert lexico.valencia("bien") > 0.5
    assert lexico.valencia("malo") < -0.5
    assert lexico.de_accion("acariciar", 0) == "bien"
    assert lexico.valorativa(-1, 0) == "malo"


def test_aprende_que_palabras_abren_preguntas():
    lexico = Lexico()
    for texto in ["¿qué es fuego?", "¿qué es agua?", "el fuego quema"]:
        lexico.oir(frase(texto), 0)
    assert lexico.es_interrogativa("qué")
    assert not lexico.es_interrogativa("fuego")
    assert not lexico.es_concepto("qué")


def test_aprende_si_y_no_de_las_respuestas():
    lexico = Lexico()
    lexico.oir(frase("sí"), 0, respuesta=True)
    lexico.oir(frase("no"), 0, respuesta=True)
    lexico.asociar_polaridad(["sí"], 1)
    lexico.asociar_polaridad(["no"], -1)
    assert lexico.polar(1, 0) == "sí"
    assert lexico.polar(-1, 0) == "no"
    assert lexico.polaridad_de(["sí", "claro"]) > 0
