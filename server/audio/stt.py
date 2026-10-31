"""Voz a texto con Whisper local (faster-whisper): el "oído" de Muyu.

Solo convierte sonido en texto; no entiende, no decide y no genera nada por
Muyu. El modelo se descarga una sola vez a ``models/whisper/`` y después
funciona sin internet. Se le quitan los signos de pregunta y exclamación: si
algo es una pregunta lo decide Muyu por la entonación (prosodia propia), no
Whisper.
"""

from __future__ import annotations

import logging
import re
import threading

import numpy as np

from server import config

log = logging.getLogger("muyu.oido")

# Frases que Whisper suele "oír" en el silencio o el ruido.
ALUCINACIONES = (
    "subtítulos", "gracias por ver", "suscríbete", "amara.org", "¡gracias!", "gracias.",
)


def limpiar(texto: str) -> str:
    texto = re.sub(r"[¿?¡!…]", "", texto)
    texto = re.sub(r"\s+", " ", texto).strip()
    return texto


class Oido:
    def __init__(self, modelo: str = config.WHISPER_MODELO, dispositivo: str = config.WHISPER_DISPOSITIVO) -> None:
        self.modelo_nombre = modelo
        self.dispositivo = dispositivo
        self.estado = "apagado"         # apagado | cargando | listo | no disponible
        self.detalle = ""
        self._modelo = None
        self._cerrojo = threading.Lock()

    def cargar(self) -> bool:
        """Carga (y la primera vez descarga) el modelo. Se puede llamar desde un hilo."""
        with self._cerrojo:
            if self._modelo is not None:
                return True
            if self.estado == "no disponible":
                return False
            self.estado = "cargando"
            try:
                from faster_whisper import WhisperModel
            except ImportError:
                self.estado, self.detalle = "no disponible", "falta instalar faster-whisper"
                log.warning("Whisper no disponible: %s", self.detalle)
                return False
            try:
                config.DIR_WHISPER.mkdir(parents=True, exist_ok=True)
                self._modelo = WhisperModel(self.modelo_nombre, device=self.dispositivo, compute_type="int8",
                                            download_root=str(config.DIR_WHISPER))
            except Exception as error:      # sin internet la primera vez, modelo dañado, etc.
                self.estado, self.detalle = "no disponible", str(error)[:200]
                log.warning("No se pudo cargar Whisper: %s", error)
                return False
            self.estado, self.detalle = "listo", f"modelo «{self.modelo_nombre}» en {self.dispositivo}"
            log.info("Whisper listo (%s)", self.modelo_nombre)
            return True

    def transcribir(self, muestras: np.ndarray) -> str:
        """Texto de un audio mono a 16 kHz (float32 entre -1 y 1). Vacío si no entiende."""
        if not self.cargar():
            return ""
        try:
            partes = self._transcribir(muestras)
        except RuntimeError as error:
            if self.dispositivo == "cpu":
                raise
            # La GPU no tiene sus librerías (cuBLAS, cuDNN…): se sigue en la CPU.
            log.warning("Whisper no pudo usar %s (%s); sigue en la CPU", self.dispositivo, error)
            with self._cerrojo:
                self._modelo, self.dispositivo, self.estado = None, "cpu", "apagado"
            if not self.cargar():
                return ""
            partes = self._transcribir(muestras)
        texto = " ".join(partes).strip()
        if texto.lower() in ALUCINACIONES or any(a in texto.lower() for a in ALUCINACIONES[:4]):
            return ""
        return limpiar(texto)

    def _transcribir(self, muestras: np.ndarray) -> list[str]:
        segmentos, _ = self._modelo.transcribe(
            np.asarray(muestras, dtype=np.float32), language="es", beam_size=1,
            condition_on_previous_text=False, no_speech_threshold=0.6,
        )
        return [s.text for s in segmentos if s.no_speech_prob < 0.7 and s.avg_logprob > -1.2]

    def a_publico(self) -> dict:
        return {"estado": self.estado, "detalle": self.detalle, "modelo": self.modelo_nombre,
                "dispositivo": self.dispositivo}
