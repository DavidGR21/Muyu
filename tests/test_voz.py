"""Fase 3: prosodia propia y voz. El audio se sintetiza; el texto de Whisper se simula."""

import base64

import numpy as np
import pytest
from fastapi.testclient import TestClient

import server.main as main
from server.audio.prosody import FRECUENCIA, Calibracion, analizar
from server.audio.stt import limpiar

HABLAR = -26.0      # dBFS de una voz normal


def voz(tono_inicio=200.0, tono_fin=200.0, segundos=1.6, db=HABLAR, silabas_por_segundo=4.0):
    """Una "voz" sintética: armónicos con el tono que se pide y pulsos silábicos."""
    t = np.arange(int(segundos * FRECUENCIA)) / FRECUENCIA
    tono = np.linspace(tono_inicio, tono_fin, len(t))
    fase = 2 * np.pi * np.cumsum(tono) / FRECUENCIA
    senal = sum(np.sin(k * fase) / k for k in range(1, 6))
    envolvente = 0.35 + 0.65 * np.clip(np.sin(2 * np.pi * silabas_por_segundo * t), 0, 1)
    senal = senal * envolvente
    rms = np.sqrt(np.mean(senal ** 2))
    return (senal / rms * 10 ** (db / 20)).astype(np.float32)


# ── Prosodia ─────────────────────────────────────────────────────────

def test_mide_el_tono():
    assert analizar(voz(200, 200)).tono_hz == pytest.approx(200, abs=8)
    assert analizar(voz(320, 320)).tono_hz == pytest.approx(320, abs=12)


def test_reconoce_la_entonacion_de_pregunta():
    assert analizar(voz(180, 270)).entonacion == "ascendente"
    assert analizar(voz(230, 160)).entonacion == "descendente"
    assert analizar(voz(200, 202)).entonacion == "plana"


def test_mide_volumen_y_distingue_el_silencio():
    fuerte, normal, suave = analizar(voz(db=-8)), analizar(voz()), analizar(voz(db=-42))
    assert fuerte.volumen_db > normal.volumen_db > suave.volumen_db
    assert normal.volumen_db == pytest.approx(HABLAR, abs=3)
    assert not analizar(np.random.default_rng(1).normal(0, 1e-4, FRECUENCIA).astype(np.float32)).con_voz


def test_estima_la_velocidad():
    lenta, rapida = analizar(voz(silabas_por_segundo=2.5)), analizar(voz(silabas_por_segundo=5))
    assert rapida.velocidad > lenta.velocidad


def test_percibe_grito_suavidad_y_firmeza_respecto_de_la_voz_habitual():
    calibracion = Calibracion()
    for _ in range(5):
        calibracion.aprender(analizar(voz(200, 200)))
    assert calibracion.percibir(analizar(voz(db=-6))).grito
    assert calibracion.percibir(analizar(voz(240, 240, db=-40))).suave
    assert calibracion.percibir(analizar(voz(160, 160, db=-19))).firme
    normal = calibracion.percibir(analizar(voz(200, 200)))
    assert not (normal.grito or normal.suave or normal.firme)


def test_un_grito_no_cambia_lo_que_considera_habitual():
    calibracion = Calibracion()
    calibracion.aprender(analizar(voz()))
    antes = calibracion.volumen_db
    calibracion.aprender(analizar(voz(db=-4)))
    assert calibracion.volumen_db == antes


def test_el_texto_de_whisper_llega_sin_signos_de_pregunta():
    assert limpiar("¿El fuego quema?") == "El fuego quema"


# ── La criatura y la voz ─────────────────────────────────────────────

def actividades(salidas):
    return [s["datos"]["nombre"] for s in salidas if s["tipo"] == "actividad"]


def hablas(salidas):
    return [s for s in salidas if s["tipo"] == "habla"]


def test_si_le_hablas_suave_se_acerca(muyu, reloj):
    reloj.avanzar(2)
    salidas = muyu.oir_voz("hola Muyu", analizar(voz(240, 250, db=-40)))
    assert salidas[0]["tipo"] == "oido" and "voz suave" in salidas[0]["datos"]["percepcion"]
    assert "acercarse" in actividades(salidas)
    assert any(c["causa"] == "voz_suave" for c in muyu.emociones.causas)
    assert muyu.emociones.actual(reloj())[0] > 0


def test_si_le_gritas_se_asusta_aunque_digas_algo_amable(muyu, reloj):
    reloj.avanzar(2)
    salidas = muyu.oir_voz("te quiero mucho", analizar(voz(db=-5)))
    assert "esconderse" in actividades(salidas)
    respuesta = hablas(salidas)[-1]
    assert respuesta["intencion"] == "gemido" and respuesta["gesto"] == "sobresalto"
    assert muyu.emociones.etiqueta(reloj()) in ("miedo", "sorpresa", "confusión")
    assert muyu.lexico.valencia("quiero") < 0      # esas palabras quedaron teñidas de susto


def test_si_pregunta_con_entonacion_lo_trata_como_pregunta(muyu, reloj):
    reloj.avanzar(2)
    muyu.oir("el fuego quema")
    reloj.avanzar(3)
    afirmacion = hablas(muyu.oir_voz("el fuego quema", analizar(voz(200, 198))))[-1]
    assert afirmacion["intencion"] != "afirmar"
    reloj.avanzar(3)
    pregunta = hablas(muyu.oir_voz("el fuego quema", analizar(voz(180, 270))))[-1]
    assert pregunta["intencion"] == "afirmar"            # respondió a la pregunta: sí, quema


def test_sin_entender_palabras_reacciona_al_tono(muyu, reloj):
    reloj.avanzar(2)
    salidas = muyu.oir_voz("", analizar(voz(240, 240, db=-40)))
    assert "acercarse" in actividades(salidas)
    assert hablas(salidas)[-1]["gesto"] == "carino"


def test_el_silencio_no_hace_nada(muyu):
    salidas = muyu.oir_voz("", analizar(np.zeros(FRECUENCIA, dtype=np.float32)))
    assert [s["tipo"] for s in salidas] == ["oido"]


def test_recuerda_como_suena_su_dueno(tmp_path, reloj, muyu):
    from server.brain.creature import Muyu

    for _ in range(3):
        reloj.avanzar(2)
        muyu.oir_voz("hola", analizar(voz(210, 210)))
    escuchadas, identificador = muyu.calibracion.escuchadas, muyu.id
    muyu.cerrar()
    cargada = Muyu.cargar(identificador, tmp_path, reloj_real=reloj)
    assert cargada.calibracion.escuchadas == escuchadas
    assert cargada.calibracion.tono_hz == pytest.approx(210, abs=10)
    cargada.cerrar()


# ── El servidor recibe el audio del micrófono ────────────────────────

def test_el_servidor_procesa_la_voz(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "vivero", main.Vivero(tmp_path))
    monkeypatch.setattr(main.oido, "transcribir", lambda muestras: "hola Muyu")
    monkeypatch.setattr(main.oido, "estado", "listo")
    audio = base64.b64encode((voz(240, 250, db=-40) * 32767).astype("<i2").tobytes()).decode()
    with TestClient(main.app) as cliente, cliente.websocket_connect("/ws") as ws:
        ws.send_json({"tipo": "conectar"})
        ws.send_json({"tipo": "voz", "audio": audio})
        while (mensaje := ws.receive_json())["tipo"] != "oido":
            pass
        assert mensaje["datos"]["texto"] == "hola Muyu"
        assert "voz suave" in mensaje["datos"]["percepcion"]
        while not ((mensaje := ws.receive_json())["tipo"] == "habla" and mensaje["origen"] == "respuesta"):
            pass
        ws.send_json({"tipo": "voz", "audio": "esto no es base64!"})
        while (mensaje := ws.receive_json())["tipo"] != "aviso":
            pass
        assert "audio" in mensaje["texto"]
