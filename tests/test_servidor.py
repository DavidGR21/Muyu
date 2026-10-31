import pytest
from fastapi.testclient import TestClient

import server.main as main


@pytest.fixture
def cliente(tmp_path, monkeypatch):
    monkeypatch.setattr(main, "vivero", main.Vivero(tmp_path))
    with TestClient(main.app) as cliente:
        yield cliente


def recibir_hasta(ws, tipo, origen=None):
    """El latido también envía actividades y hablas propias: se esperan las buscadas."""
    while True:
        mensaje = ws.receive_json()
        if mensaje["tipo"] == tipo and (origen is None or mensaje.get("origen") == origen):
            return mensaje


def test_sirve_la_interfaz(cliente):
    respuesta = cliente.get("/")
    assert respuesta.status_code == 200
    assert "Muyu" in respuesta.text
    assert cliente.get("/app.js").headers["content-type"].startswith(("application/javascript", "text/javascript"))


def test_nace_aprende_y_se_retoma_con_su_id(cliente):
    with cliente.websocket_connect("/ws") as ws:
        ws.send_json({"tipo": "conectar", "id": None})
        criatura = recibir_hasta(ws, "criatura")["datos"]
        assert recibir_hasta(ws, "habla")["origen"] == "nacimiento"
        ws.send_json({"tipo": "mensaje", "texto": "hola Muyu"})
        respuesta = recibir_hasta(ws, "habla", "respuesta")
        assert respuesta["emocion"]["etiqueta"]
        cerebro = recibir_hasta(ws, "cerebro")["datos"]
        assert any(p["forma"] == "hola" for p in cerebro["lexico"])
        ws.send_json({"tipo": "accion", "accion": "acariciar"})
        assert recibir_hasta(ws, "habla", "reaccion")
        estado = recibir_hasta(ws, "estado")["datos"]
        assert {"saciedad", "seguridad", "aburrimiento"} <= set(estado["necesidades"])
        assert estado["comportamiento"]["actual"]["nombre"]

    with cliente.websocket_connect("/ws") as ws:
        ws.send_json({"tipo": "conectar", "id": criatura["id"]})
        assert recibir_hasta(ws, "criatura")["datos"]["id"] == criatura["id"]
        cerebro = recibir_hasta(ws, "cerebro")["datos"]
        assert any(p["forma"] == "hola" for p in cerebro["lexico"])

    assert cliente.get(f"/api/criaturas/{criatura['id']}").status_code == 200


def test_un_id_invalido_no_toca_el_disco_y_crea_otra(cliente):
    with cliente.websocket_connect("/ws") as ws:
        ws.send_json({"tipo": "conectar", "id": "../../etc/passwd"})
        criatura = recibir_hasta(ws, "criatura")["datos"]
        assert main.ID_VALIDO.match(criatura["id"])
    assert cliente.get("/api/criaturas/no-existe").status_code == 404


def test_adelantar_el_tiempo(cliente):
    with cliente.websocket_connect("/ws") as ws:
        ws.send_json({"tipo": "conectar"})
        recibir_hasta(ws, "criatura")
        edad = recibir_hasta(ws, "estado")["datos"]["edad"]
        ws.send_json({"tipo": "adelantar", "horas": 2})
        assert "Pasaron" in recibir_hasta(ws, "aviso")["texto"]
        assert recibir_hasta(ws, "estado")["datos"]["edad"] >= edad + 2 * 3600
