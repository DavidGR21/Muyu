"""Criterio de aceptación de la fase 2 (README, sección 10):

dejada sola, Muyu hace cosas distintas según su estado, y su cuerpo, su voz y sus
palabras expresan la misma emoción.
"""

from collections import Counter

from server.brain.creature import Muyu
from server.brain.language.speaker import matizar
from tests.conftest import RelojFalso

GESTOS_ALEGRES = {"alegria", "carino", "saludo"}
GESTOS_TRISTES = {"miedo", "tristeza"}
NEGATIVAS = {"miedo", "tristeza", "confusión", "enojo"}
POSITIVAS = {"alegría", "contento"}


def criar(tmp_path):
    reloj = RelojFalso()
    muyu = Muyu.nacer(tmp_path, semilla=11, reloj_real=reloj)
    muyu.conectar()
    for texto in ["hola Muyu", "hola Muyu", "hola Muyu", "la pelota rebota", "la comida rica", "la comida rica"]:
        reloj.avanzar(3)
        muyu.oir(texto)
        if "comida" in texto:
            muyu.necesidades.saciedad = 0.3
            muyu.actuar("alimentar")
    return muyu, reloj


def dejar_sola(muyu, reloj, segundos):
    actividades, hablas = Counter(), []
    muyu.ultima_interaccion_real = reloj()
    for _ in range(segundos):
        reloj.avanzar(1)
        for salida in muyu.latir():
            if salida["tipo"] == "actividad":
                actividades[salida["datos"]["nombre"]] += 1
            elif salida["tipo"] == "habla" and salida["origen"] in ("actividad", "pensamiento"):
                hablas.append(salida)
        if not muyu.despierta:
            break
    return actividades, hablas


def coherente(habla) -> bool:
    """El gesto (cuerpo) y la puntuación (palabras) dicen lo mismo que la emoción del instante.
    La voz del navegador se genera con esa misma emoción, que viaja en ``habla['emocion']``."""
    etiqueta, gesto, texto = habla["emocion"]["etiqueta"], habla["gesto"], habla["texto"]
    if etiqueta in NEGATIVAS:
        return gesto not in GESTOS_ALEGRES and "¡" not in texto
    if etiqueta in POSITIVAS:
        return gesto not in GESTOS_TRISTES
    return True


def test_sola_hace_cosas_distintas_segun_su_estado_y_todo_expresa_la_misma_emocion(tmp_path):
    estados = {
        "con hambre": dict(saciedad=0.08),
        "sola": dict(compania=0.05),
        "insegura": dict(seguridad=0.05),
        "con sueño": dict(energia=0.12),
        "aburrida": dict(aburrimiento=0.95),
    }
    esperado = {
        "con hambre": "pedir_comida", "sola": "buscarte", "insegura": "esconderse",
        "con sueño": "ir_a_dormir", "aburrida": "jugar",
    }
    principales = {}
    for nombre, necesidades in estados.items():
        muyu, reloj = criar(tmp_path / nombre)
        for clave, valor in necesidades.items():
            setattr(muyu.necesidades, clave, valor)
        reloj.avanzar(40)       # que se apague la alegría del trato previo
        actividades, hablas = dejar_sola(muyu, reloj, 45)
        principales[nombre] = actividades.most_common(1)[0][0]
        assert actividades[esperado[nombre]] >= 1, (nombre, actividades)
        incoherentes = [h for h in hablas if not coherente(h)]
        assert not incoherentes, (nombre, [(h["texto"], h["gesto"], h["emocion"]["etiqueta"]) for h in incoherentes])
        muyu.cerrar()
    assert len(set(principales.values())) >= 4      # estados distintos → conductas distintas


def test_las_palabras_se_tinen_de_la_emocion():
    assert matizar("¿Fuego… duele?", (-0.7, 0.7, -0.6)) == "¿F-fuego… duele?"     # miedo: tartamudea
    assert matizar("¡Hola!", (0.8, 0.6, 0.3)) == "¡Holaa!"                       # alegría: alarga
    assert matizar("¡Pelota!", (-0.6, -0.4, -0.3)) == "Pelota…"                  # tristeza: se apaga
    assert matizar("Hola", (0.0, 0.0, 0.0)) == "Hola"


def test_cada_habla_lleva_la_emocion_del_instante_para_la_voz(tmp_path):
    muyu, reloj = criar(tmp_path)
    reloj.avanzar(3)
    habla = [s for s in muyu.oir("hola Muyu") if s["tipo"] == "habla"][-1]
    assert {"p", "a", "d", "etiqueta", "ambivalencia"} <= set(habla["emocion"])
    assert "pregunta" in habla
    assert {"tono", "brillo", "ritmo"} == set(muyu.identidad()["voz"])
    muyu.cerrar()
