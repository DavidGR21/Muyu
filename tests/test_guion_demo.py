"""El guion de aceptación de la fase 1 (README, sección 10), de principio a fin."""

from server.brain.concepts import DEDUCIDO
from server.brain.creature import Muyu
from server.brain.importance import ACTIVO, LATENTE
from server.brain.reasoning import CONFIRMADA, PENDIENTE
from tests.conftest import hablas, pensamientos


def test_guion_de_aceptacion_fase_1(muyu, reloj, tmp_path):
    def decir(texto, espera=4):
        reloj.avanzar(espera)
        return muyu.oir(texto)

    def hacer(accion, espera=3):
        reloj.avanzar(espera)
        return muyu.actuar(accion)

    # 1. Nacimiento: aparece una criatura nueva que solo balbucea.
    (nacimiento,) = hablas(muyu.conectar())
    assert nacimiento["origen"] == "nacimiento"
    assert nacimiento["palabras"] == [] and muyu.etapa == 0

    # 2. Primeras palabras: «hola Muyu» y caricias → dice «hola», que toma valencia positiva.
    dichas = set()
    for _ in range(5):
        dichas.update(hablas(decir("hola Muyu"))[-1]["palabras"])
        hacer("acariciar")
    assert "hola" in dichas
    assert muyu.lexico.valencia("hola") > 0.3
    assert muyu.etapa >= 1

    # 3. Aprendizaje de relaciones.
    exposiciones_fuego = 1
    decir("el fuego quema")
    salidas = decir("quemar duele")
    assert muyu.red.relacion("fuego", "quema")
    assert muyu.red.relacion("quemar", "duele")

    # 4. Deducción propia: «¿fuego… duele?» aparece como hipótesis y como pensamiento.
    hipotesis = muyu.razonador.por_par("fuego", "duele")
    assert hipotesis and hipotesis.estado == PENDIENTE and hipotesis.preguntada
    assert any(p["texto"] == "¿Fuego… duele?" for p in pensamientos(salidas))

    # 5. Confirmación: «sí» la vuelve conocimiento. La primera vez no sabe qué significa
    #    «sí»: vuelve a preguntar hasta que lo acompañas con el gesto de asentir.
    respuesta = hablas(decir("sí"))[-1]
    assert hipotesis.estado == PENDIENTE and respuesta["intencion"] == "preguntar"
    hacer("asentir")
    assert hipotesis.estado == CONFIRMADA
    assert muyu.red.relacion("fuego", "duele").origen_dato == DEDUCIDO
    assert muyu.lexico.polar(1, muyu.reloj.tiempo) == "sí"

    # 6. Pregunta sí/no.
    respuesta = hablas(decir("¿el fuego quema?"))[-1]
    exposiciones_fuego += 1
    assert respuesta["intencion"] == "afirmar" and respuesta["gesto"] == "asentir"

    # 7. Pregunta abierta: responde con sus relaciones.
    respuesta = hablas(decir("¿qué es fuego?"))[-1]
    exposiciones_fuego += 1
    assert respuesta["intencion"] == "describir"
    assert {"quema", "duele"} <= set(respuesta["palabras"])

    # 8. Pregunta sin respuesta: confusión y devuelve la pregunta.
    respuesta = hablas(decir("¿qué es agua?"))[-1]
    assert respuesta["intencion"] == "confusion"
    assert "agua" in respuesta["texto"].lower()

    # 9. Pensamiento propio: si nadie le habla, piensa sola y a veces habla.
    pensados, dichos = [], []
    for _ in range(40):
        reloj.avanzar(10)
        salidas = muyu.latir()
        pensados += pensamientos(salidas)
        dichos += [s for s in hablas(salidas) if s["origen"] == "pensamiento"]
    assert len(pensados) >= 5
    assert dichos

    # 10. Emoción: varios regaños cambian su expresión y bajan su confianza.
    confianza = muyu.emociones.confianza
    for _ in range(3):
        hacer("regañar", 2)
    assert muyu.emociones.confianza < confianza - 0.1
    assert muyu.emociones.etiqueta(reloj()) in ("miedo", "tristeza", "enojo")

    # 11. Persistencia: al volver es la misma criatura, con todo lo aprendido.
    palabras, identificador = set(muyu.lexico.palabras), muyu.id
    muyu.cerrar()
    reloj.avanzar(120)
    otra = Muyu.cargar(identificador, tmp_path, reloj_real=reloj)
    assert set(otra.lexico.palabras) == palabras
    assert otra.razonador.por_par("fuego", "duele").estado == CONFIRMADA
    assert hablas(otra.conectar())[-1]["origen"] == "saludo"

    # 12. Memoria sin olvido: tras una semana «fuego» está latente; lo reconoce y lo recupera rápido.
    otra.adelantar(24 * 7)
    if not otra.despierta:
        otra.actuar("despertar")
    assert otra.lexico.estado("fuego", otra.reloj.tiempo) == LATENTE
    reloj.avanzar(5)
    respuesta = hablas(otra.oir("el fuego"))[-1]
    assert respuesta["intencion"] == "reconocer"
    assert respuesta["texto"].startswith("¿Mm")
    assert otra.lexico.estado("fuego", otra.reloj.tiempo) == ACTIVO
    assert exposiciones_fuego > 1   # la primera vez necesitó varias

    # 13. Sueño: al despertar cuenta un sueño con conceptos que conoce.
    otra.actuar("dormir")
    assert not otra.despierta
    reloj.avanzar(30)
    (sueno,) = [s for s in hablas(otra.actuar("despertar")) if s["intencion"] == "sueno"]
    assert sueno["palabras"]
    assert all(p in otra.red.nodos for p in sueno["palabras"])
    otra.cerrar()
