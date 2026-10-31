"""Comportamiento autónomo: qué hace su cuerpo según cómo está."""

import random

import numpy as np

from server.brain.behavior import Comportamiento, EstadoCorporal
from server.brain.instincts import Necesidades
from tests.conftest import hablas

RASGOS = {"curiosidad": 0.5, "timidez": 0.5, "terquedad": 0.5, "sensibilidad": 0.5, "locuacidad": 0.5}


def mejor(necesidades: Necesidades, pad=(0.0, 0.0, 0.0), hora=12.0, ignorada=0.0) -> str:
    estado = EstadoCorporal(necesidades, np.array(pad), 0.0, RASGOS, hora, ignorada)
    return max(Comportamiento(random.Random(1), 0).opciones(estado), key=lambda o: o.puntaje).nombre


def test_cada_necesidad_lleva_a_una_actividad_distinta():
    assert mejor(Necesidades(saciedad=0.1)) == "pedir_comida"
    assert mejor(Necesidades(energia=0.5), hora=23) == "ir_a_dormir"
    assert mejor(Necesidades(seguridad=0.1), pad=(-0.6, 0.6, -0.5)) == "esconderse"
    assert mejor(Necesidades(compania=0.05)) == "buscarte"
    assert mejor(Necesidades(aburrimiento=0.9), pad=(0.4, 0.3, 0.1)) == "jugar"
    assert mejor(Necesidades(energia=0.15)) in ("ir_a_dormir", "descansar")


def test_una_necesidad_urgente_interrumpe_lo_que_hace():
    comportamiento = Comportamiento(random.Random(1), 0)
    comportamiento.iniciar("jugar", "pelota", "juega", 0)
    estado = EstadoCorporal(Necesidades(saciedad=0.05), np.zeros(3), 0.0, RASGOS, 12.0)
    assert comportamiento.urgente(estado).nombre == "pedir_comida"


def test_contenta_y_sola_hace_cosas_variadas(muyu, reloj):
    muyu.conectar()
    vistas = set()
    for _ in range(400):
        reloj.avanzar(1)
        vistas |= {s["datos"]["nombre"] for s in muyu.latir() if s["tipo"] == "actividad"}
    assert len(vistas) >= 4


def test_cuando_le_hablas_te_atiende_y_despues_sigue_con_lo_suyo(muyu, reloj):
    muyu.conectar()
    reloj.avanzar(2)
    salidas = muyu.oir("hola Muyu")
    assert any(s["tipo"] == "actividad" and s["datos"]["nombre"] == "atenderte" for s in salidas)
    nombres = set()
    for _ in range(30):
        reloj.avanzar(1)
        nombres |= {s["datos"]["nombre"] for s in muyu.latir() if s["tipo"] == "actividad"}
    assert nombres - {"atenderte"}


def test_con_hambre_come_y_llena_no_quiere(muyu, reloj):
    muyu.necesidades.saciedad = 0.2
    salidas = muyu.actuar("alimentar")
    assert any(s["tipo"] == "actividad" and s["datos"]["nombre"] == "comer" for s in salidas)
    assert muyu.necesidades.saciedad > 0.5
    muyu.necesidades.saciedad = 0.97
    reloj.avanzar(3)
    respuesta = hablas(muyu.actuar("alimentar"))[-1]
    assert respuesta["gesto"] == "negar" and muyu.necesidades.saciedad <= 0.97


def test_si_la_asustan_mucho_corre_a_esconderse(muyu, reloj):
    actividades = []
    for _ in range(3):
        reloj.avanzar(2)
        actividades += [s["datos"]["nombre"] for s in muyu.actuar("regañar") if s["tipo"] == "actividad"]
    assert actividades[-1] == "esconderse"


def test_con_sueno_se_va_sola_a_la_cama_y_se_duerme(muyu, reloj):
    muyu.conectar()
    muyu.necesidades.energia = 0.15
    for _ in range(40):
        reloj.avanzar(1)
        muyu.latir()
        if not muyu.despierta:
            break
    assert not muyu.despierta
    assert muyu.comportamiento.actual.nombre == "dormir"


def test_si_te_busca_y_no_le_haces_caso_se_entristece(muyu, reloj):
    muyu.conectar()
    reloj.avanzar(1)
    muyu.comportamiento.iniciar("buscarte", "frente", "se siente sola", reloj(), duracion=5)
    placer = muyu.emociones.actual(reloj())[0]
    for _ in range(6):
        reloj.avanzar(1)
        muyu.latir()
    assert muyu.comportamiento.frustracion > 0
    assert any(c["causa"] == "no le hiciste caso" for c in muyu.emociones.causas)
    assert muyu.emociones.actual(reloj())[0] < placer


def test_una_urgencia_mucho_mayor_reemplaza_a_otra():
    comportamiento = Comportamiento(random.Random(1), 0)
    comportamiento.iniciar("ir_a_dormir", "cama", "tiene un poco de sueño", 0)
    estado = EstadoCorporal(Necesidades(energia=0.6, saciedad=0.0), np.zeros(3), 0.0, RASGOS, 22.0)
    assert comportamiento.urgente(estado).nombre == "pedir_comida"
