import pytest

from server import config
from server.brain.importance import ACTIVO, LATENTE, TENUE, Huella, estado_de

HORA = 3600


def exposiciones_hasta_activa(huella: Huella, ahora: float) -> int:
    veces = 0
    while huella.estado(ahora) != ACTIVO:
        huella.reforzar(ahora)
        veces += 1
    return veces


def test_lo_nuevo_entra_con_importancia_baja():
    huella = Huella.nueva(0)
    assert huella.valor(0) == config.IMPORTANCIA_INICIAL
    assert huella.estado(0) == TENUE


def test_estados_segun_importancia():
    assert estado_de(0.7) == ACTIVO
    assert estado_de(0.3) == TENUE
    assert estado_de(0.05) == LATENTE


def test_sube_con_el_uso_sin_pasar_de_uno():
    huella = Huella.nueva(0)
    valores = []
    for _ in range(40):
        huella.reforzar(0)
        valores.append(huella.valor(0))
    assert all(b >= a for a, b in zip(valores, valores[1:]))
    assert valores[0] > config.IMPORTANCIA_INICIAL
    assert valores[-1] <= 1.0


def test_baja_con_el_tiempo_pero_nunca_cruza_el_minimo():
    huella = Huella.nueva(0, 0.9)
    assert huella.valor(24 * HORA) < 0.9
    lejos = huella.valor(100_000 * HORA)
    assert lejos >= config.IMPORTANCIA_MINIMA
    assert lejos == pytest.approx(config.IMPORTANCIA_MINIMA, abs=1e-6)


def test_atenuar_nunca_borra():
    huella = Huella.nueva(0, 0.8)
    huella.atenuar(0, 0.0)
    assert huella.valor(0) == pytest.approx(config.IMPORTANCIA_MINIMA)


def test_lo_muy_repetido_se_atenua_mas_despacio():
    poco = Huella.nueva(0, 0.8)
    mucho = Huella.nueva(0, 0.8)
    mucho.usos = 30
    assert mucho.valor(48 * HORA) > poco.valor(48 * HORA)


def test_veces_aprendida_no_cuenta_oscilaciones():
    huella = Huella.nueva(0)
    exposiciones_hasta_activa(huella, 0)
    assert huella.veces_aprendida == 1
    huella.atenuar(0, 0.8)                  # baja a tenue, sin pasar por latente
    assert huella.estado(0) == TENUE
    exposiciones_hasta_activa(huella, 0)
    assert huella.veces_aprendida == 1


def test_efecto_de_ahorro_reaprende_mas_rapido():
    huella = Huella.nueva(0)
    primera_vez = 1 + exposiciones_hasta_activa(huella, 0)   # oírla por primera vez también cuenta
    ahora = 0
    while huella.estado(ahora) != LATENTE:
        ahora += 6 * HORA
    reaprender = exposiciones_hasta_activa(huella, ahora)
    assert reaprender < primera_vez
    assert huella.veces_aprendida == 2


def test_fila_ida_y_vuelta():
    huella = Huella.nueva(10, 0.4)
    huella.reforzar(20)
    assert Huella.desde_fila(huella.a_fila()) == huella
