import pytest

from server.brain.creature import Muyu
from server.storage.db import ruta_de


def test_crea_un_archivo_por_criatura(tmp_path, reloj):
    a = Muyu.nacer(tmp_path, reloj_real=reloj)
    b = Muyu.nacer(tmp_path, reloj_real=reloj)
    assert a.id != b.id
    assert ruta_de(tmp_path, a.id).exists() and ruta_de(tmp_path, b.id).exists()
    assert a.rasgos != b.rasgos or a.semilla != b.semilla
    a.cerrar()
    b.cerrar()


def test_guardar_y_cargar_conserva_todo(tmp_path, reloj, muyu):
    for texto in ["hola Muyu", "el fuego quema", "quemar duele", "sí", "¿qué es fuego?"]:
        reloj.avanzar(3)
        muyu.oir(texto)
    muyu.actuar("acariciar")
    for _ in range(3):
        reloj.avanzar(10)
        muyu.latir()
    original = muyu.cerebro_publico()
    confianza = muyu.emociones.confianza
    identificador = muyu.id
    muyu.cerrar()

    cargada = Muyu.cargar(identificador, tmp_path, reloj_real=reloj)
    copia = cargada.cerebro_publico()
    def ordenar(filas, *claves):
        return sorted(filas, key=lambda f: tuple(f[c] for c in claves))

    assert ordenar(copia["lexico"], "forma") == ordenar(original["lexico"], "forma")
    assert ordenar(copia["relaciones"], "origen", "destino") == ordenar(original["relaciones"], "origen", "destino")
    assert copia["hipotesis"] == original["hipotesis"]
    assert [p["id"] for p in copia["pensamientos"]] == [p["id"] for p in original["pensamientos"]]
    assert copia["episodios"] == original["episodios"]
    assert cargada.emociones.confianza == pytest.approx(confianza)
    assert cargada.ngramas.conteos == muyu.ngramas.conteos
    assert cargada.lexico.total_frases == muyu.lexico.total_frases
    cargada.cerrar()


def test_cargar_un_id_inexistente_falla(tmp_path):
    with pytest.raises(FileNotFoundError):
        Muyu.cargar("0" * 32, tmp_path)


def test_una_criatura_de_la_fase_1_carga_sin_problemas(tmp_path, reloj):
    import sqlite3

    vieja = Muyu.nacer(tmp_path, reloj_real=reloj)
    vieja.oir("hola Muyu")
    identificador = vieja.id
    vieja.cerrar()
    # La tabla «relacion» tal como la creaba la fase 1, sin familiaridad ni experiencia.
    conexion = sqlite3.connect(ruta_de(tmp_path, identificador))
    conexion.executescript("""
        DROP TABLE relacion;
        CREATE TABLE relacion (sujeto TEXT PRIMARY KEY, confianza REAL NOT NULL, afecto REAL NOT NULL,
                               actualizada REAL NOT NULL);
        INSERT INTO relacion VALUES ('dueño', 0.7, 0.4, 0);
    """)
    conexion.close()

    cargada = Muyu.cargar(identificador, tmp_path, reloj_real=reloj)
    assert cargada.emociones.vinculo.confianza == pytest.approx(0.7)
    assert cargada.emociones.vinculo.familiaridad == 0.0
    assert "hola" in cargada.lexico.palabras
    cargada.cerrar()
