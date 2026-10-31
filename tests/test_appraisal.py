"""Appraisal completo, ánimo y relación: el mismo evento se siente distinto según el contexto."""

import numpy as np

from server.brain.emotions import Emociones, Evaluacion, Vinculo
from server.brain.instincts import Necesidades

RASGOS = {"curiosidad": 0.5, "timidez": 0.5, "terquedad": 0.5, "sensibilidad": 0.5, "locuacidad": 0.5}


def emociones(**necesidades) -> Emociones:
    return Emociones(RASGOS, 0.0, Necesidades(**necesidades))


def caricia():
    return Evaluacion("acariciar", agrado=0.6, novedad=0.05, necesidad="compania", del_dueno=True)


def regano():
    return Evaluacion("regañar", agrado=-0.6, amenaza=0.6, novedad=0.2, del_dueno=True)


def test_lo_que_responde_a_una_necesidad_importa_mas():
    con_hambre = emociones(saciedad=0.1).sentir(Evaluacion("alimentar", agrado=0.5, necesidad="hambre"), 0, 0)
    llena = emociones(saciedad=0.95).sentir(Evaluacion("alimentar", agrado=0.5, necesidad="hambre"), 0, 0)
    assert con_hambre[0] > llena[0] * 1.5


def test_lo_repetido_se_habitua():
    e = emociones()
    deltas = [e.sentir(caricia(), t, 0)[0] for t in range(0, 8, 2)]
    assert deltas[0] > deltas[1] > deltas[-1]


def test_lo_inesperado_sorprende():
    tras_caricias = emociones()
    for t in range(3):
        tras_caricias.sentir(caricia(), t, 0)
    tras_reganos = emociones()
    for t in range(3):
        tras_reganos.sentir(regano(), t, 0)
    sorpresa_contraste = tras_caricias.evaluador.completar(regano(), np.zeros(3), Vinculo(), Necesidades(), 4)
    sorpresa_rutina = tras_reganos.evaluador.completar(regano(), np.zeros(3), Vinculo(), Necesidades(), 4)
    assert sorpresa_contraste.inesperado > sorpresa_rutina.inesperado


def test_insegura_todo_asusta_mas():
    segura = emociones(seguridad=0.95).sentir(regano(), 0, 0)
    insegura = emociones(seguridad=0.1).sentir(regano(), 0, 0)
    assert insegura[1] > segura[1] and insegura[2] < segura[2]


def test_el_animo_tine_lo_que_siente():
    alegre, triste = emociones(), emociones()
    alegre.animo = np.array([0.6, 0.0, 0.0])
    triste.animo = np.array([-0.6, 0.0, 0.0])
    assert alegre.sentir(caricia(), 0, 0)[0] > triste.sentir(caricia(), 0, 0)[0]


def test_un_regano_de_alguien_en_quien_confia_duele_mas_y_asusta_menos():
    confia, desconfia = emociones(), emociones()
    confia.vinculo.confianza, desconfia.vinculo.confianza = 0.9, 0.1
    duele = confia.sentir(regano(), 0, 0)
    asusta = desconfia.sentir(regano(), 0, 0)
    assert duele[0] < asusta[0]            # más displacer
    assert duele[1] < asusta[1]            # menos activación (menos miedo)


def test_ambivalencia_carino_de_alguien_que_le_da_miedo():
    e = emociones()
    e.vinculo.confianza = 0.1
    e.sentir(caricia(), 0, 0)
    assert e.ambivalencia(0) > 0
    confiada = emociones()
    confiada.sentir(caricia(), 0, 0)
    assert confiada.ambivalencia(0) == 0


def test_la_relacion_cambia_en_dias_siguiendo_la_experiencia():
    v = Vinculo(confianza=0.3)
    for _ in range(20):
        v.experimentar(0.8)
    v.vivir(2, acompanada=True)
    casi_igual = v.confianza
    v.vivir(24 * 7, acompanada=True)
    assert casi_igual < 0.32 < v.confianza
    assert v.familiaridad > 0.9


def test_cada_cambio_guarda_su_evaluacion():
    e = emociones()
    e.sentir(regano(), 0, 0)
    causa = e.causas[0]
    assert causa["causa"] == "regañar"
    assert set(causa["evaluacion"]) == {"inesperado", "agrado", "amenaza", "control", "relevancia"}
