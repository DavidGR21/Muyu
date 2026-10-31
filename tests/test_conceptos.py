import pytest

from server import config
from server.brain.concepts import RedConceptos

ANIO = 3600 * 24 * 365


def test_hebbiano_conecta_lo_que_aparece_junto():
    red = RedConceptos()
    resultado = red.aprender(["fuego", "quema", "mano"], 0)
    assert red.relacion("fuego", "quema")
    assert red.relacion("quema", "mano")
    assert red.relacion("fuego", "mano").etiqueta == "quema"
    assert len(resultado.nuevas) == 3
    assert set(red.nodos) == {"fuego", "quema", "mano"}


def test_repetir_fortalece_la_relacion():
    red = RedConceptos()
    red.aprender(["fuego", "quema"], 0)
    antes = red.relacion("fuego", "quema").peso(0)
    red.aprender(["fuego", "quema"], 0)
    assert red.relacion("fuego", "quema").peso(0) > antes


def test_lo_que_no_se_usa_se_atenua_pero_no_se_borra():
    red = RedConceptos()
    red.aprender(["agua", "apaga"], 0)
    assert red.relacion("agua", "apaga").peso(ANIO) == pytest.approx(config.IMPORTANCIA_MINIMA, abs=1e-3)
    assert ("agua", "apaga") in red.relaciones


def test_parecido_de_forma_es_instintivo():
    red = RedConceptos()
    for nodo in ("quema", "quemar", "casa", "cama"):
        red.asegurar(nodo, 0)
    assert "quemar" in red.parecidos("quema")
    assert "cama" not in red.parecidos("casa")


def test_activacion_propagada_pierde_fuerza_con_la_distancia():
    red = RedConceptos()
    red.aprender(["fuego", "quema"], 0)
    red.aprender(["quema", "duele"], 0)
    activacion = red.activar({"fuego": 1.0}, 0, 0)
    assert activacion["fuego"] == 1.0
    assert 0 < activacion["duele"] < activacion["quema"] < 1.0


def test_contradecir_baja_el_peso_sin_borrar():
    red = RedConceptos()
    red.aprender(["fuego", "quema"], 0)
    antes = red.relacion("fuego", "quema").peso(0)
    assert red.contradecir("fuego", "quema", 0)
    assert red.relacion("fuego", "quema").peso(0) < antes
    assert red.relacion("fuego", "quema").negaciones == 1
