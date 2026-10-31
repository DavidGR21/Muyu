"""Parámetros de Muyu: tasas, umbrales y velocidad del tiempo.

Muyu vive en dos escalas de tiempo:

* **Tiempo real** (segundos de reloj): lo que pasa durante una conversación,
  como las emociones, las ventanas de asociación y los ciclos de pensamiento.
* **Tiempo de la criatura** (acelerable con ``VELOCIDAD_TIEMPO``): lo lento,
  como la atenuación de la memoria, las necesidades, el ánimo y el sueño.
"""

import os
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DIR_WEB = RAIZ / "web"
DIR_CRIATURAS = Path(os.getenv("MUYU_DIR_CRIATURAS", str(RAIZ / "data" / "creatures")))
DIR_WHISPER = Path(os.getenv("MUYU_DIR_WHISPER", str(RAIZ / "models" / "whisper")))

# ── Tiempo ────────────────────────────────────────────────────────────────
# 1 = tiempo real · 60 = un minuto real equivale a una hora de la criatura.
VELOCIDAD_TIEMPO = float(os.getenv("MUYU_VELOCIDAD_TIEMPO", "1"))
TICK_S = 1.0                        # cada cuánto late el reloj interno (s reales)
PASO_VIDA_S = 900.0                 # resolución al simular tiempo largo (s de criatura)

# ── Memoria sin olvido (importance.py) ────────────────────────────────────
IMPORTANCIA_INICIAL = 0.20
IMPORTANCIA_MINIMA = 0.02           # nunca se cruza: siempre queda un rastro
UMBRAL_ACTIVO = 0.50
UMBRAL_TENUE = 0.15
TASA_APRENDIZAJE = 0.20
BONO_AHORRO = 0.6                   # efecto de ahorro por cada vez que ya se aprendió
VIDA_MEDIA_HORAS = 24.0             # horas de criatura para perder la mitad de la importancia
ESTABILIDAD_POR_APRENDIZAJE = 0.5   # cada vez aprendida alarga la vida media un 50 %
ESTABILIDAD_POR_USO = 0.25          # y cada repetición la alarga un poco (logarítmico)

# ── Léxico (lexicon.py) ───────────────────────────────────────────────────
K_EVIDENCIA = 15                    # frases para que la informatividad aprendida pese la mitad
IDF_REFERENCIA = 20                 # aparecer en ≤ 1/20 de las frases = plenamente informativa
UMBRAL_CONCEPTO = 0.50              # informatividad mínima para tratar una palabra como concepto
TASA_VALENCIA = 0.35
TASA_CONTAGIO = 0.12
TASA_POLARIDAD = 0.5
UMBRAL_POLARIDAD = 0.30             # desde aquí una palabra significa "sí" o "no"
UMBRAL_VALORATIVA = 0.35            # desde aquí una palabra expresa algo bueno o malo

# ── Red de conceptos y razonamiento ──────────────────────────────────────
DISTANCIA_HEBBIANA = 3              # solo se conectan conceptos a 3 palabras o menos de distancia
PAUSA_EN_PALABRAS = 3               # una coma (pausa) separa como 3 palabras más
FACTOR_CONTRADICCION = 0.3          # cuánto queda de una relación cuando le dicen que no es así
PREFIJO_FORMA_MIN = 4
SIMILITUD_FORMA_MIN = 0.6
UMBRAL_HIPOTESIS = 0.02             # confianza mínima para proponer una deducción
UMBRAL_AFIRMAR = 0.35               # desde aquí afirma la deducción en vez de preguntarla
UMBRAL_SEGURO = 0.20                # fuerza mínima para responder "sí" con seguridad
VIDA_MEDIA_ACTIVACION_S = 30.0
PERDIDA_ACTIVACION = 0.5
RAMAS_MAXIMAS = 12                  # relaciones más fuertes que se exploran por nodo

# ── Emociones (emotions.py) ───────────────────────────────────────────────
VIDA_MEDIA_EMOCION_S = 25.0
TAU_ANIMO_HORAS = 3.0
CONFIANZA_INICIAL = 0.5
AFECTO_INICIAL = 0.3

VIDA_MEDIA_IMPULSO_S = 20.0         # acercarse / alejarse se apagan en segundos
UMBRAL_AMBIVALENCIA = 0.25          # desde aquí quiere acercarse y alejarse a la vez
TAU_VINCULO_HORAS = 48.0            # la confianza sigue a la experiencia en días
VIDA_MEDIA_EXPERIENCIA_HORAS = 72.0
HORAS_FAMILIARIDAD = 20.0           # horas juntos para que la familiaridad llegue a ~63 %

# ── Necesidades (instincts.py) ────────────────────────────────────────────
HORAS_ENERGIA_DESPIERTA = 20.0      # de llena a vacía estando despierta (despierta ~14 h al día)
HORAS_RECUPERAR_DURMIENDO = 7.0     # de vacía a llena durmiendo
HORAS_COMPANIA = 8.0                # de acompañada a sola sin interacción
HORAS_SACIEDAD = 8.0                # de llena a vacía estando despierta (dormida, el doble)
HORAS_RECUPERAR_SEGURIDAD = 0.75    # constante de tiempo para volver a sentirse segura
SEGURIDAD_EN_CALMA = 0.85
SEGUNDOS_PARA_ABURRIRSE = 240.0     # segundos reales sin estímulo para aburrirse del todo
UMBRAL_DORMIRSE = 0.10              # con tan poca energía se duerme donde esté
UMBRAL_DESPERTARSE = 0.98
UMBRAL_SOMNOLENCIA = 0.75           # desde aquí se va sola a la cama
HORA_NOCHE = 21                     # su noche (según su reloj del día) va de 21 h a 7 h
HORA_MANANA = 7

# ── Comportamiento autónomo (behavior.py) ─────────────────────────────────
ATENCION_S = 14.0                   # segundos que te presta atención después de cada interacción
UMBRAL_URGENCIA = 1.0               # una necesidad así de urgente interrumpe lo que esté haciendo

# ── Interacción (segundos reales) ─────────────────────────────────────────
VENTANA_ASOCIACION_S = 20.0         # palabra y luego señal: se asocian si están así de cerca
VENTANA_ASOCIACION_POSTERIOR_S = 5.0  # señal y luego palabra (condicionamiento hacia atrás)…
PESO_ASOCIACION_POSTERIOR = 0.4       # …que es mucho más débil
VENTANA_RESPUESTA_S = 120.0         # tiempo en que espera respuesta a su pregunta
VENTANA_CORRECCION_S = 25.0         # un regaño o un gesto así de rápido corrige lo que aceptó
VENTANA_GESTO_S = 20.0              # las palabras así de cerca de un gesto de asentir o negar aprenden si significan sí o no
AUSENCIA_SALUDO_S = 30.0            # ausencia mínima para saludar al volver

# ── Pensamiento propio (thoughts.py) ──────────────────────────────────────
PERIODO_PENSAMIENTO_S = 9.0
SILENCIO_PARA_PENSAR_S = 6.0

# ── Sueño (sleep.py) ──────────────────────────────────────────────────────
EPISODIOS_REPASO = 12
FACTOR_ATENUACION_SUENO = 0.85

# ── Lenguaje (language/) ──────────────────────────────────────────────────
# Palabras activas necesarias para cada etapa del habla. El README propone
# ~10 / ~30 / ~80; aquí son bajas para poder recorrer el guion de demo de la
# fase 1 en una sola sesión. Súbelas para una crianza más realista.
UMBRALES_ETAPA = {1: 1, 2: 3, 3: 8}
NOMBRES_ETAPA = {0: "Balbuceo", 1: "Imitación", 2: "Palabra-frase", 3: "Dos palabras"}
FRECUENCIA_IMITACION = 3            # en la etapa 1 solo repite lo que oyó mucho

# ── Voz (fase 3) ──────────────────────────────────────────────────────────
WHISPER_MODELO = os.getenv("MUYU_WHISPER_MODELO", "base")    # tiny · base · small
# cpu funciona en cualquier PC; cuda acelera si están instaladas las librerías de NVIDIA (cuBLAS, cuDNN).
WHISPER_DISPOSITIVO = os.getenv("MUYU_WHISPER_DISPOSITIVO", "cpu")
SEGUNDOS_VOZ_MAXIMOS = 20.0
PROSODIA_PISO_DB = -50.0            # por debajo es silencio
PROSODIA_VOLUMEN_HABITUAL_DB = -26.0  # volumen de voz normal hasta que conozca la de su dueño
PROSODIA_GRITO_DB = -12.0           # desde aquí (o saturando el micrófono) es un grito
PROSODIA_SUAVE_DB = -33.0           # hasta aquí es una voz suave
SUBIDA_PREGUNTA = 1.12              # el tono del final sube un 12 %: pregunta
