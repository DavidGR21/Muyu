import pytest

from server.brain.creature import Muyu
from server.brain.perception import percibir_texto


class RelojFalso:
    """Reloj real controlable: las pruebas deciden cuánto tiempo pasa."""

    def __init__(self, t: float = 1_000_000.0) -> None:
        self.t = t

    def __call__(self) -> float:
        return self.t

    def avanzar(self, segundos: float) -> None:
        self.t += segundos


@pytest.fixture
def reloj() -> RelojFalso:
    return RelojFalso()


@pytest.fixture
def muyu(tmp_path, reloj):
    criatura = Muyu.nacer(tmp_path, semilla=7, reloj_real=reloj)
    yield criatura
    if criatura.db:
        criatura.cerrar()


def frase(texto: str):
    return percibir_texto(texto, 0).frases[0]


def hablas(salidas: list[dict]) -> list[dict]:
    return [s for s in salidas if s["tipo"] == "habla"]


def pensamientos(salidas: list[dict]) -> list[dict]:
    return [s["datos"] for s in salidas if s["tipo"] == "pensamiento"]
