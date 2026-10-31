"""Prosodia propia: cómo suena lo que le dicen, calculado con NumPy.

* **Volumen**: energía (RMS, en dBFS) de los tramos con voz y cuánto satura.
* **Tono**: frecuencia fundamental por autocorrelación, cuadro a cuadro.
* **Entonación**: si el tono sube al final, es una pregunta (instinto).
* **Velocidad**: núcleos silábicos (picos de energía) por segundo.

Son señales instintivas: llegan directo al modelo emocional sin pasar por el
lenguaje. Un grito asusta aunque las palabras sean amables.

Cada criatura además se acostumbra a la voz de su dueño (:class:`Calibracion`):
lo suave o lo fuerte se juzga respecto de cómo habla él normalmente.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np

from server import config

FRECUENCIA = 16000
CUADRO = 640            # 40 ms: alcanza para tonos de hasta ~70 Hz
SALTO = 160             # 10 ms
TONO_MIN, TONO_MAX = 70.0, 500.0


@dataclass
class Prosodia:
    duracion: float = 0.0           # segundos
    con_voz: bool = False           # hay voz o es silencio/ruido
    volumen_db: float = -90.0       # energía media de los tramos con voz (dBFS)
    saturacion: float = 0.0         # fracción de muestras recortadas (los gritos saturan)
    tono_hz: float | None = None    # mediana de la frecuencia fundamental
    entonacion: str = "desconocida"  # ascendente | descendente | plana | desconocida
    subida: float = 1.0             # tono del final / tono del resto
    velocidad: float = 0.0          # sílabas por segundo

    def a_dict(self) -> dict:
        datos = asdict(self)
        for clave in ("duracion", "volumen_db", "saturacion", "subida", "velocidad"):
            datos[clave] = round(float(datos[clave]), 3)
        datos["tono_hz"] = round(float(self.tono_hz), 1) if self.tono_hz else None
        return datos


def _cuadros(muestras: np.ndarray) -> np.ndarray:
    if len(muestras) < CUADRO:
        muestras = np.pad(muestras, (0, CUADRO - len(muestras)))
    cantidad = 1 + (len(muestras) - CUADRO) // SALTO
    indices = np.arange(CUADRO)[None, :] + SALTO * np.arange(cantidad)[:, None]
    return muestras[indices]


def _tono(cuadro: np.ndarray, frecuencia: int) -> float | None:
    """Frecuencia fundamental por autocorrelación normalizada (None si no es sonoro)."""
    cuadro = (cuadro - cuadro.mean()) * np.hanning(len(cuadro))
    espectro = np.fft.rfft(cuadro, n=2 * len(cuadro))
    autocorrelacion = np.fft.irfft(np.abs(espectro) ** 2)[: len(cuadro)]
    if autocorrelacion[0] <= 0:
        return None
    autocorrelacion = autocorrelacion / autocorrelacion[0]
    desde, hasta = int(frecuencia / TONO_MAX), int(frecuencia / TONO_MIN)
    tramo = autocorrelacion[desde:hasta]
    if len(tramo) < 3:
        return None
    retardo = int(np.argmax(tramo))
    if tramo[retardo] < 0.45 or retardo in (0, len(tramo) - 1):
        return None
    # Interpolación parabólica para afinar el pico.
    a, b, c = tramo[retardo - 1], tramo[retardo], tramo[retardo + 1]
    ajuste = 0.5 * (a - c) / (a - 2 * b + c) if (a - 2 * b + c) != 0 else 0.0
    return frecuencia / (desde + retardo + ajuste)


def analizar(muestras: np.ndarray, frecuencia: int = FRECUENCIA) -> Prosodia:
    muestras = np.asarray(muestras, dtype=np.float32)
    prosodia = Prosodia(duracion=len(muestras) / frecuencia)
    if len(muestras) < frecuencia * 0.2:
        return prosodia
    prosodia.saturacion = float(np.mean(np.abs(muestras) >= 0.98))
    muestras = muestras - float(np.mean(muestras))
    cuadros = _cuadros(muestras)
    potencia = np.mean(cuadros ** 2, axis=1) + 1e-12
    db = 10 * np.log10(potencia)

    # Tramos con voz: bien por encima del ruido de fondo.
    umbral = max(config.PROSODIA_PISO_DB, float(np.percentile(db, 90)) - 25)
    con_voz = db > umbral
    if con_voz.sum() * SALTO / frecuencia < 0.15:
        return prosodia
    prosodia.con_voz = True
    prosodia.volumen_db = float(10 * np.log10(np.mean(potencia[con_voz])))

    # Tono cuadro a cuadro y entonación del final.
    tonos = []
    for indice in np.flatnonzero(con_voz):
        tono = _tono(cuadros[indice], frecuencia)
        if tono:
            tonos.append(tono)
    if len(tonos) >= 6:
        tonos = np.array(tonos)
        mediana = float(np.median(tonos))
        tonos = tonos[(tonos > 0.55 * mediana) & (tonos < 1.8 * mediana)]   # descarta saltos de octava
        prosodia.tono_hz = float(np.median(tonos))
        corte = max(3, len(tonos) // 4)
        if len(tonos) >= corte + 3:
            final, resto = np.median(tonos[-corte:]), np.median(tonos[:-corte])
            prosodia.subida = float(final / resto)
            if prosodia.subida >= config.SUBIDA_PREGUNTA:
                prosodia.entonacion = "ascendente"
            elif prosodia.subida <= 0.92:
                prosodia.entonacion = "descendente"
            else:
                prosodia.entonacion = "plana"

    # Velocidad: picos de energía (núcleos silábicos) separados al menos 100 ms.
    envolvente = np.convolve(db, np.ones(5) / 5, mode="same")
    picos, ultimo = 0, -100
    for i in range(1, len(envolvente) - 1):
        if (con_voz[i] and envolvente[i] >= envolvente[i - 1] and envolvente[i] > envolvente[i + 1]
                and envolvente[i] - min(envolvente[max(0, i - 8):i + 9]) > 3 and i - ultimo >= 10):
            picos += 1
            ultimo = i
    duracion_voz = con_voz.sum() * SALTO / frecuencia
    prosodia.velocidad = picos / duracion_voz if duracion_voz else 0.0
    return prosodia


@dataclass
class Percepcion:
    """Lo que la prosodia le hace sentir, antes de entender ninguna palabra."""

    grito: bool = False
    suave: bool = False
    firme: bool = False             # fuerte y grave: suena a regaño
    pregunta: bool = False

    def descripcion(self) -> list[str]:
        partes = []
        if self.grito:
            partes.append("gritaste")
        elif self.suave:
            partes.append("voz suave")
        elif self.firme:
            partes.append("voz firme")
        if self.pregunta:
            partes.append("pregunta por entonación")
        return partes


@dataclass
class Calibracion:
    """Cómo habla su dueño normalmente: se acostumbra a su voz."""

    volumen_db: float = config.PROSODIA_VOLUMEN_HABITUAL_DB
    tono_hz: float | None = None
    escuchadas: int = 0

    def percibir(self, p: Prosodia) -> Percepcion:
        if not p.con_voz:
            return Percepcion()
        alto = p.volumen_db - self.volumen_db
        agudo = (p.tono_hz / self.tono_hz) if (p.tono_hz and self.tono_hz) else 1.0
        grito = p.saturacion > 0.005 or p.volumen_db >= max(config.PROSODIA_GRITO_DB, self.volumen_db + 9)
        suave = not grito and (p.volumen_db <= min(config.PROSODIA_SUAVE_DB, self.volumen_db - 7)
                               or (alto <= -4 and agudo >= 1.1))
        firme = not grito and not suave and alto >= 4 and agudo <= 0.9
        return Percepcion(grito=grito, suave=suave, firme=firme, pregunta=p.entonacion == "ascendente")

    def aprender(self, p: Prosodia) -> None:
        """Lo habitual se aprende de su voz normal (un grito no cuenta como habitual)."""
        if not p.con_voz or self.percibir(p).grito:
            return
        peso = 1 / min(self.escuchadas + 2, 12)
        self.volumen_db += peso * (p.volumen_db - self.volumen_db)
        if p.tono_hz:
            self.tono_hz = p.tono_hz if self.tono_hz is None else self.tono_hz + peso * (p.tono_hz - self.tono_hz)
        self.escuchadas += 1

    def a_dict(self) -> dict:
        return {"volumen_db": self.volumen_db, "tono_hz": self.tono_hz, "escuchadas": self.escuchadas}
