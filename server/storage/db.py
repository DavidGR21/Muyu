"""Acceso a SQLite: un archivo ``<id>.sqlite`` por criatura.

Todas las tablas de conocimiento comparten los campos de memoria de
:class:`~server.brain.importance.Huella`. Cada módulo del cerebro sabe
convertir sus objetos en filas; aquí solo se guardan y se leen.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable
from pathlib import Path

from server.brain.importance import COLUMNAS_MEMORIA

ESQUEMA = f"""
CREATE TABLE IF NOT EXISTS criatura (
    id TEXT PRIMARY KEY,
    nombre TEXT NOT NULL,
    nacimiento REAL NOT NULL,
    etapa INTEGER NOT NULL,
    semilla INTEGER NOT NULL,
    rasgos TEXT NOT NULL,
    tiempo REAL NOT NULL,
    guardada_real REAL NOT NULL,
    ultima_interaccion_real REAL NOT NULL,
    total_frases INTEGER NOT NULL,
    ultimo_sueno REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS estado (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    emocion TEXT NOT NULL,
    emocion_real REAL NOT NULL,
    animo TEXT NOT NULL,
    necesidades TEXT NOT NULL,
    despierta INTEGER NOT NULL,
    causas TEXT NOT NULL,
    extra TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS relacion (
    sujeto TEXT PRIMARY KEY,
    confianza REAL NOT NULL,
    afecto REAL NOT NULL,
    familiaridad REAL NOT NULL DEFAULT 0,
    experiencia REAL NOT NULL DEFAULT 0,
    actualizada REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS lexico (
    palabra TEXT PRIMARY KEY,
    grafia TEXT,
    frecuencia INTEGER NOT NULL,
    en_frases INTEGER NOT NULL,
    en_preguntas INTEGER NOT NULL,
    al_inicio_pregunta INTEGER NOT NULL,
    en_respuestas INTEGER NOT NULL,
    en_saludos INTEGER NOT NULL,
    informatividad REAL NOT NULL,
    valencia REAL NOT NULL,
    polaridad REAL NOT NULL,
    acciones TEXT NOT NULL,
    {COLUMNAS_MEMORIA}
);
CREATE TABLE IF NOT EXISTS conceptos (
    nodo TEXT PRIMARY KEY,
    activacion REAL NOT NULL,
    activada_real REAL NOT NULL,
    valencia REAL NOT NULL,
    categoria TEXT,
    {COLUMNAS_MEMORIA}
);
CREATE TABLE IF NOT EXISTS relaciones_conceptos (
    origen TEXT NOT NULL,
    destino TEXT NOT NULL,
    etiqueta TEXT,
    etiquetas TEXT NOT NULL,
    peso REAL NOT NULL,
    origen_dato TEXT NOT NULL,
    negaciones INTEGER NOT NULL,
    {COLUMNAS_MEMORIA},
    PRIMARY KEY (origen, destino)
);
CREATE TABLE IF NOT EXISTS hipotesis (
    id INTEGER PRIMARY KEY,
    origen TEXT NOT NULL,
    destino TEXT NOT NULL,
    camino TEXT NOT NULL,
    confianza REAL NOT NULL,
    estado TEXT NOT NULL,
    preguntada INTEGER NOT NULL,
    creada REAL NOT NULL,
    resuelta REAL,
    motivo TEXT,
    fuente TEXT,
    {COLUMNAS_MEMORIA}
);
CREATE TABLE IF NOT EXISTS episodios (
    id INTEGER PRIMARY KEY,
    momento REAL NOT NULL,
    momento_real REAL NOT NULL,
    evento TEXT NOT NULL,
    emocion TEXT NOT NULL,
    {COLUMNAS_MEMORIA}
);
CREATE TABLE IF NOT EXISTS pensamientos (
    id INTEGER PRIMARY KEY,
    momento REAL NOT NULL,
    momento_real REAL NOT NULL,
    tipo TEXT NOT NULL,
    contenido TEXT NOT NULL,
    texto TEXT NOT NULL,
    explicacion TEXT NOT NULL,
    en_voz_alta INTEGER NOT NULL,
    dicho TEXT
);
CREATE TABLE IF NOT EXISTS ngramas (
    contexto TEXT NOT NULL,
    siguiente TEXT NOT NULL,
    conteo INTEGER NOT NULL,
    PRIMARY KEY (contexto, siguiente)
);
CREATE TABLE IF NOT EXISTS suenos (
    id INTEGER PRIMARY KEY,
    inicio REAL NOT NULL,
    fin REAL,
    reforzados TEXT NOT NULL,
    atenuados TEXT NOT NULL,
    sueno TEXT NOT NULL,
    tono TEXT NOT NULL,
    contado INTEGER NOT NULL
);
"""

# Columnas agregadas después de la fase 1: se añaden a las bases existentes al abrirlas.
MIGRACIONES = (
    ("relacion", "familiaridad", "REAL NOT NULL DEFAULT 0"),
    ("relacion", "experiencia", "REAL NOT NULL DEFAULT 0"),
)

TABLAS = ("criatura", "estado", "relacion", "lexico", "conceptos", "relaciones_conceptos", "hipotesis",
          "episodios", "pensamientos", "ngramas", "suenos")


def ruta_de(directorio: Path, identificador: str) -> Path:
    return Path(directorio) / f"{identificador}.sqlite"


class BaseCriatura:
    def __init__(self, ruta: Path) -> None:
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta = ruta
        self.conexion = sqlite3.connect(ruta)
        self.conexion.row_factory = sqlite3.Row
        self.conexion.executescript(ESQUEMA)
        self._migrar()

    def _migrar(self) -> None:
        for tabla, columna, definicion in MIGRACIONES:
            existentes = {fila["name"] for fila in self.conexion.execute(f"PRAGMA table_info({tabla})")}
            if columna not in existentes:
                self.conexion.execute(f"ALTER TABLE {tabla} ADD COLUMN {columna} {definicion}")
        self.conexion.commit()

    def guardar(self, tabla: str, filas: Iterable[dict]) -> None:
        filas = list(filas)
        if not filas:
            return
        assert tabla in TABLAS, tabla
        columnas = list(filas[0])
        consulta = (f"INSERT OR REPLACE INTO {tabla} ({', '.join(columnas)}) "
                    f"VALUES ({', '.join('?' for _ in columnas)})")
        self.conexion.executemany(consulta, [[fila[c] for c in columnas] for fila in filas])

    def leer(self, tabla: str, orden: str | None = None, limite: int | None = None) -> list[sqlite3.Row]:
        assert tabla in TABLAS, tabla
        consulta = f"SELECT * FROM {tabla}"
        if orden:
            consulta += f" ORDER BY {orden}"
        if limite:
            consulta += f" LIMIT {int(limite)}"
        return self.conexion.execute(consulta).fetchall()

    def leer_uno(self, tabla: str) -> sqlite3.Row | None:
        filas = self.leer(tabla, limite=1)
        return filas[0] if filas else None

    def confirmar(self) -> None:
        self.conexion.commit()

    def cerrar(self) -> None:
        self.conexion.commit()
        self.conexion.close()
