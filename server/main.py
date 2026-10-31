"""Servidor de Muyu: sirve la interfaz web y conecta cada navegador con su criatura.

Ejecutar desde la raíz del proyecto::

    uvicorn server.main:app --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import asyncio
import json
import logging
import mimetypes
import re
import time
from collections import defaultdict
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles

from server import config
from server.brain.creature import Muyu
from server.clock import latir_siempre

# En algunos Windows el registro asocia .js a text/plain y el navegador no lo ejecuta.
mimetypes.add_type("application/javascript", ".js")
mimetypes.add_type("text/css", ".css")

log = logging.getLogger("muyu")
ID_VALIDO = re.compile(r"^[0-9a-f]{32}$")
HORAS_MAXIMAS_ADELANTO = 24 * 30


class Vivero:
    """Las criaturas vivas en este servidor y quién está conectado a cada una."""

    def __init__(self, directorio: Path, reloj_real=time.time) -> None:
        self.directorio = Path(directorio)
        self.reloj_real = reloj_real
        self.inicio = reloj_real()
        self.criaturas: dict[str, Muyu] = {}
        self.conexiones: dict[str, set[WebSocket]] = defaultdict(set)

    def obtener(self, identificador: str | None) -> Muyu:
        """La criatura de ese id (cargándola si hace falta) o una recién nacida."""
        if isinstance(identificador, str) and ID_VALIDO.match(identificador):
            if identificador in self.criaturas:
                return self.criaturas[identificador]
            if Muyu.existe(self.directorio, identificador):
                criatura = Muyu.cargar(identificador, self.directorio, self.reloj_real)
                # Solo vive mientras el servidor está encendido.
                criatura.ponerse_al_dia(max(criatura.guardada_real, self.inicio))
                self.criaturas[identificador] = criatura
                return criatura
        criatura = Muyu.nacer(self.directorio, reloj_real=self.reloj_real)
        self.criaturas[criatura.id] = criatura
        log.info("Nació una criatura nueva: %s", criatura.id)
        return criatura

    def unir(self, criatura: Muyu, ws: WebSocket) -> None:
        self.conexiones[criatura.id].add(ws)

    def separar(self, criatura: Muyu, ws: WebSocket) -> None:
        conexiones = self.conexiones[criatura.id]
        conexiones.discard(ws)
        if not conexiones:
            criatura.cerrar()
            self.criaturas.pop(criatura.id, None)
            self.conexiones.pop(criatura.id, None)

    def conectadas(self) -> list[Muyu]:
        return [c for i, c in list(self.criaturas.items()) if self.conexiones.get(i)]

    async def enviar(self, identificador: str, mensajes: list[dict]) -> None:
        for ws in list(self.conexiones.get(identificador, ())):
            try:
                for mensaje in mensajes:
                    await ws.send_json(mensaje)
            except Exception:
                self.conexiones[identificador].discard(ws)

    def procesar(self, criatura: Muyu, mensaje: dict) -> list[dict]:
        tipo = mensaje.get("tipo")
        if tipo == "mensaje":
            return criatura.oir(str(mensaje.get("texto", "")))
        if tipo == "accion":
            return criatura.actuar(str(mensaje.get("accion", "")))
        if tipo == "adelantar":
            try:
                horas = float(mensaje.get("horas", 0))
            except (TypeError, ValueError):
                return []
            return criatura.adelantar(min(max(horas, 0.0), HORAS_MAXIMAS_ADELANTO))
        return []

    def guardar_todo(self) -> None:
        for criatura in self.criaturas.values():
            criatura.cerrar()
        self.criaturas.clear()


vivero = Vivero(config.DIR_CRIATURAS)


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    tarea = asyncio.create_task(latir_siempre(vivero))
    try:
        yield
    finally:
        tarea.cancel()
        vivero.guardar_todo()


app = FastAPI(title="Muyu", lifespan=ciclo_de_vida)


async def _recibir(ws: WebSocket) -> dict | None:
    texto = await ws.receive_text()
    try:
        mensaje = json.loads(texto)
    except json.JSONDecodeError:
        return None
    return mensaje if isinstance(mensaje, dict) else None


@app.websocket("/ws")
async def conexion(ws: WebSocket) -> None:
    await ws.accept()
    try:
        saludo = await _recibir(ws) or {}
    except WebSocketDisconnect:
        return
    criatura = vivero.obtener(saludo.get("id"))
    vivero.unir(criatura, ws)
    try:
        await ws.send_json({"tipo": "criatura", "datos": criatura.identidad()})
        salidas = criatura.conectar()
        criatura.guardar()
        await vivero.enviar(criatura.id, salidas + criatura.instantanea(cerebro=True))
        while True:
            mensaje = await _recibir(ws)
            if mensaje is None:
                continue
            salidas = vivero.procesar(criatura, mensaje)
            criatura.guardar()
            await vivero.enviar(criatura.id, salidas + criatura.instantanea(cerebro=True))
    except WebSocketDisconnect:
        pass
    finally:
        vivero.separar(criatura, ws)


@app.get("/api/salud")
def salud() -> dict:
    return {"ok": True, "criaturas_vivas": len(vivero.criaturas), "velocidad_tiempo": config.VELOCIDAD_TIEMPO}


@app.get("/api/criaturas/{identificador}")
def ver_criatura(identificador: str) -> dict:
    """El estado y el cerebro de una criatura, para depurar o analizar."""
    if not ID_VALIDO.match(identificador):
        raise HTTPException(404, "Criatura no encontrada")
    criatura = vivero.criaturas.get(identificador)
    if criatura:
        return {"estado": criatura.estado_publico(), "cerebro": criatura.cerebro_publico()}
    if not Muyu.existe(vivero.directorio, identificador):
        raise HTTPException(404, "Criatura no encontrada")
    criatura = Muyu.cargar(identificador, vivero.directorio)
    try:
        return {"estado": criatura.estado_publico(), "cerebro": criatura.cerebro_publico()}
    finally:
        criatura.db.cerrar()


app.mount("/", StaticFiles(directory=config.DIR_WEB, html=True), name="web")
