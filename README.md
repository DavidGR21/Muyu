# 🌱 Muyu

> *Muyu* significa **semilla** en kichwa.
> Una criatura que nace sin memoria, sin lenguaje y sin ideas, y se convierte en quien tú la ayudes a ser… o en alguien que ni tú esperabas.

Muyu es una criatura virtual que **aprende desde cero**. No usa APIs de IA ni modelos de lenguaje preentrenados para pensar o hablar: su lenguaje, su conocimiento y su razonamiento se construyen **únicamente** a partir de lo que su dueño le dice, le muestra y de cómo la trata.

Cada usuario tiene su propia criatura. Dos Muyus criados por personas distintas terminan hablando, pensando y sintiendo de forma distinta.

---

## Índice

1. [Principios del proyecto](#1-principios-del-proyecto)
2. [Qué es propio y qué es abierto](#2-qué-es-propio-y-qué-es-abierto)
3. [Arquitectura general](#3-arquitectura-general)
4. [El cerebro de Muyu](#4-el-cerebro-de-muyu)
5. [Audio](#5-audio)
6. [Stack tecnológico](#6-stack-tecnológico)
7. [Estructura del proyecto](#7-estructura-del-proyecto)
8. [Instalación y ejecución](#8-instalación-y-ejecución)
9. [Modelo de datos](#9-modelo-de-datos)
10. [Desarrollo por fases](#10-desarrollo-por-fases)
11. [Métricas de evaluación](#11-métricas-de-evaluación)
12. [Limitaciones conocidas](#12-limitaciones-conocidas)

---

## 1. Principios del proyecto

1. **Conocimiento vacío al nacer.** Muyu no trae vocabulario, gramática, hechos ni opiniones. Todo lo aprende de su dueño.
2. **Instintos programados, conocimiento aprendido.** El código define *cómo* aprende (los mecanismos, como un cerebro de bebé). *Qué* sabe sale solo de la experiencia.
3. **Nunca borra lo aprendido.** Lo que no se usa pierde importancia, pero queda guardado. Si vuelve a aparecer, Muyu lo reconoce vagamente y lo recupera más rápido que la primera vez.
4. **Sin servicios externos.** Nada de APIs de IA. Todo corre en un servidor propio (por ahora, mi computadora).
5. **Lenguaje y razonamiento entrenados desde cero.** No se usan LLMs preentrenados ni se hace fine-tuning de modelos de terceros.
6. **Piensa por sí misma.** Responde preguntas con lo que sabe y, cuando nadie le habla, piensa en voz alta, se hace preguntas y saca conclusiones propias.
7. **Las emociones no salen del lenguaje.** Lo que siente Muyu lo calcula un modelo emocional propio. El lenguaje solo lo expresa.
8. **Todo es explicable.** Cada emoción, respuesta o deducción tiene una causa que se puede rastrear y mostrar.
9. **Cada criatura es única.** Cada una tiene su propia base de datos, su propio grafo de conceptos y sus propios modelos entrenados.

---

## 2. Qué es propio y qué es abierto

| Componente | Origen | Detalle |
|---|---|---|
| Segmentación y vocabulario | 🟢 Propio, desde cero | Aprende las palabras a partir de lo que escucha |
| Red de conceptos (conocimiento) | 🟢 Propio, desde cero | Grafo que nace vacío |
| Razonamiento e inferencia | 🟢 Propio, desde cero | Encadena lo que sabe para deducir cosas nuevas |
| Respuesta a preguntas | 🟢 Propio, desde cero | Busca la respuesta en su propia red de conceptos |
| Pensamiento propio (monólogo) | 🟢 Propio, desde cero | Recorre sus recuerdos y conceptos cuando está sola |
| Modelo emocional | 🟢 Propio | PAD + evaluación cognitiva + memoria |
| Modelo de lenguaje (habla) | 🟢 Propio, desde cero | N-gramas → red neuronal pequeña entrenada durante el sueño |
| Análisis prosódico (volumen, tono) | 🟢 Propio | Señales de audio calculadas con DSP |
| Voz "de criatura" (balbuceo) | 🟢 Propio | Sintetizador procedural |
| **Voz a texto (STT)** | 🔵 Modelo abierto local | Whisper (vía `faster-whisper`), sin internet |
| **Texto a voz (TTS) avanzado** | 🔵 Modelo abierto local *(opcional)* | Piper, para fases avanzadas |

> **Regla:** los modelos abiertos solo se usan para **convertir audio ↔ texto**. No entienden, no deciden y no generan nada por Muyu. Whisper funciona como un "oído": transforma sonido en texto, y es Muyu quien tiene que aprender qué significa ese texto.

---

## 3. Arquitectura general

```
┌──────────────────────────── Cliente (navegador: PC o celular) ─────────────────────────────┐
│  Habitación + criatura (Canvas)   ·   Chat de texto / botón de voz   ·   Panel del cerebro  │
│  Acciones: acariciar · alimentar · jugar · regañar · dormir                                 │
└───────────────────────────────────────────┬────────────────────────────────────────────────┘
                                            │ WebSocket (red local)
┌───────────────────────────────────────────▼────────────────────────────────────────────────┐
│                         Servidor propio (mi PC) — Python + FastAPI                          │
│                                                                                            │
│   Audio ─► [STT Whisper local] ─► texto ──┐                                                │
│   Audio ─► [Prosodia propia] ─► volumen, tono ──┐                                          │
│                                           ▼     ▼                                          │
│                              ┌──────── PERCEPCIÓN ─────────┐                               │
│                              │ palabras · señales · acción │                               │
│                              └─────────────┬───────────────┘                               │
│                                            ▼                                               │
│   ┌──────────── MEMORIA ───────────┐   EVALUACIÓN   ┌────────── EMOCIONES ──────────┐      │
│   │ episódica · léxico · conceptos │◄──────────────►│ emoción · ánimo · necesidades │      │
│   │ (nada se borra: solo se atenúa)│       │        │ confianza en el dueño         │      │
│   └───────────────┬────────────────┘       ▼        └───────────────────────────────┘      │
│                   ▼                                                                        │
│      RAZONAMIENTO ──► respuesta a preguntas · deducciones · pensamiento propio             │
│                   ▼                                                                        │
│              DECISIÓN ──► LENGUAJE (habla propia)                                          │
│                                                                                            │
│   RELOJ INTERNO: cada pocos segundos Muyu "piensa" aunque nadie le hable                   │
│   SUEÑO: consolidación (y desde la fase 4, entrenamiento neuronal con PyTorch)             │
│                                                                                            │
│   Almacenamiento: SQLite, una base por criatura                                            │
└────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 4. El cerebro de Muyu

### 4.1 Instintos (lo único programado)

Igual que un bebé nace sabiendo llorar y buscar contacto, Muyu nace con **mecanismos**, no con conocimiento:

| Instinto | Qué hace |
|---|---|
| Separar el texto en unidades | Divide la entrada en palabras, sin saber qué significan |
| Detectar repetición | Nota qué aparece seguido y qué aparece junto |
| Reaccionar a señales primarias | Caricia, comida y juego = positivo · regaño, grito = negativo |
| Detectar preguntas | El signo `?` (en texto) o la entonación ascendente (en voz) indican que le preguntan algo |
| Asentir y negar | Gestos innatos para responder sí o no antes de conocer esas palabras, y para entender los 👍/👎 de su dueño |
| Sentir necesidades | Energía y compañía bajan con el tiempo |
| Curiosidad | Le llama la atención lo nuevo y lo que no termina de entender |
| Pensar sola | Cuando no recibe estímulos, recorre lo que sabe |
| Dormir | Consolida lo aprendido |

Las **señales primarias** son la clave del aprendizaje. Muyu no sabe que "bien" es una palabra buena. Lo descubre porque "bien" suele aparecer cuando la acarician. Así se ancla el significado emocional del lenguaje (*grounding*). Del mismo modo aprende "sí" y "no": son las palabras que su dueño usa cuando confirma o corrige lo que ella dice. Como en texto no hay forma de saber al principio si una respuesta es un sí o un no, el dueño la acompaña las primeras veces con un gesto (👍 asentir / 👎 negar), que Muyu entiende por instinto; si no entiende una respuesta, no adivina: vuelve a preguntar.

### 4.2 Percepción

Cada entrada se convierte en un evento:

```json
{
  "palabras": ["el", "fuego", "quema"],
  "es_pregunta": false,
  "prosodia": { "volumen": 0.42, "tono": "neutro", "velocidad": 1.1 },
  "accion": null,
  "momento": "2026-10-31T21:14:00"
}
```

### 4.3 Memoria sin olvido: importancia y estados

Muyu **nunca borra** una palabra, un concepto, una relación ni un recuerdo. Lo que cambia es su **importancia** (de 0 a 1):

- Cada vez que algo se escucha o se usa, su importancia **sube**.
- Con el tiempo sin usarse, **baja lentamente**, pero nunca por debajo de un **mínimo** (por ejemplo, `0.02`). Siempre queda un rastro.

Según su importancia, cada elemento está en uno de tres estados:

| Estado | Importancia | Comportamiento de Muyu |
|---|---|---|
| 🟢 **Activo** | ≥ 0.50 | Lo usa con seguridad al hablar y razonar |
| 🟡 **Tenue** | 0.15 – 0.50 | Lo usa con duda: *"¿fuego… quema?"* |
| ⚪ **Latente** | < 0.15 | No lo usa por sí sola, pero sigue guardado |

**Reconocimiento vago:** cuando escucha algo que está **latente**, no lo trata como nuevo. Lo reconoce a medias y lo expresa:
> *"¿Mm… eso… ya escuché?"*

**Recuperación rápida (efecto de ahorro):** algo latente que vuelve a aparecer recupera importancia **más rápido** que algo aprendido por primera vez, porque Muyu ya lo había aprendido antes. Esto imita el "efecto de ahorro" descrito por Ebbinghaus en la memoria humana.

```
importancia_nueva = importancia + tasa × (1 − importancia) × (1 + bono_ahorro × veces_aprendida_antes)
```

Este mismo mecanismo aplica a palabras, conceptos, relaciones y recuerdos.

### 4.4 Léxico (aprende las palabras)

- Cada palabra nueva entra al léxico con **importancia baja**.
- **Informatividad aprendida:** las palabras que aparecen en casi todas las frases ("el", "de", "que") se vuelven poco informativas, al estilo de IDF. Muyu aprende sola a darles menos peso, sin una lista de *stopwords* programada.
- Cada palabra acumula una **valencia emocional** según el contexto en que suele aparecer.

### 4.5 Red de conceptos (su conocimiento)

Un grafo dirigido y con pesos que **nace vacío**:

```
(fuego) ──[quema]──► (mano)       peso 0.62   activo
(quemar) ─[duele]──► (yo)         peso 0.48   tenue
(agua) ───[apaga]──► (fuego)      peso 0.09   latente
```

- **Nodos:** conceptos (palabras informativas).
- **Aristas:** relaciones entre conceptos. La etiqueta de la relación es la palabra que suele unirlos. Muyu no conoce la gramática: aprende que "quema" conecta "fuego" con "mano".
- **Aprendizaje hebbiano:** lo que aparece junto se conecta y se fortalece.
- **Atenuación (no olvido):** las conexiones que no se usan bajan de importancia hasta el mínimo, pero no se eliminan.
- **Valencia:** cada nodo tiene una carga emocional (positiva o negativa) que se propaga a sus vecinos.

### 4.6 Razonamiento

Todo el razonamiento ocurre sobre la red de conceptos:

1. **Activación propagada:** lo que escucha activa conceptos, y la activación se extiende a los conceptos conectados (con pérdida por distancia). Así "recuerda" cosas relacionadas.
2. **Encadenamiento:** si `A → B` y `B → C` con suficiente fuerza, propone `A → C` como **hipótesis**.
   > Le enseñan *"el fuego quema"* y otro día *"quemar duele"*. Muyu deduce: *"¿fuego… duele?"*
3. **Confianza en la deducción:** el producto de los pesos del camino. Si es baja, **pregunta** en vez de afirmar.
4. **Confirmación o corrección:** si el dueño confirma, la hipótesis se vuelve conocimiento. Si la corrige, baja su importancia (sin borrarse: puede recordar que alguna vez lo creyó). Un 👎 también corrige lo último que *afirmó*, y una negación aprendida ("Muyu no es papá") debilita la relación en ambos sentidos y las deducciones que se apoyaban en ella.
5. **Generalización (durante el sueño):** agrupa los conceptos con conexiones parecidas en **categorías emergentes** (por ejemplo: cosas que se comen, cosas que asustan). Así puede razonar sobre cosas nuevas por parecido.
6. **Contradicciones:** si aprende dos cosas incompatibles, se confunde (sube la incertidumbre) y lo expresa.

### 4.7 Responder preguntas

Cuando la percepción detecta una pregunta, Muyu busca la respuesta **en su propia red de conceptos**:

| Tipo de pregunta | Cómo la resuelve | Ejemplo |
|---|---|---|
| **Sí / no** (*"¿el fuego quema?"*) | Busca un camino entre los conceptos y mide su fuerza | Fuerte → *"sí"* (o asiente) · débil → *"¿sí…?"* · no existe → duda |
| **¿Qué es X?** / **¿Qué hace X?** | Devuelve las relaciones más fuertes que salen de X | *"fuego… quema. Caliente."* |
| **¿Te gusta X?** | Consulta la valencia del concepto y su emoción asociada | *"No. Fuego malo."* |
| **¿Qué pasa si X?** | Encadena relaciones desde X | *"Fuego… mano… duele."* |
| **¿Quién / dónde…?** | Busca relaciones donde el concepto aparezca con esas palabras | Según lo que haya aprendido |

**Cómo identifica el tipo de pregunta:** tampoco viene programado. Al principio Muyu trata todas las preguntas igual (busca relaciones de los conceptos que oyó). Con el tiempo aprende que las preguntas que empiezan con "qué" suelen recibir una explicación y las que no, un sí o un no, observando cómo responde su dueño cuando ella pregunta.

**Si no sabe:** muestra confusión (gesto + balbuceo). Cuando ya ha aprendido la expresión, dice *"no sé"*. Y puede **devolver la pregunta**: *"¿Fuego… qué?"*, para que su dueño le enseñe.

**Si la respuesta está latente:** *"Mm… creo… quema?"*. Reconoce que lo sabía, pero con poca seguridad.

### 4.8 Pensamiento propio (habla consigo misma)

Muyu tiene un **reloj interno** que cada pocos segundos le permite pensar aunque nadie le hable. Cada ciclo de pensamiento:

1. **Elige un punto de partida:** un recuerdo reciente, un concepto con alta carga emocional, algo que no entiende o una hipótesis pendiente.
2. **Recorre la red:** una caminata por los conceptos conectados, guiada por la activación y la curiosidad.
3. **Produce un pensamiento**, que puede ser:
   - **Un recuerdo:** *"David… comida. Bien."*
   - **Una deducción nueva:** al recorrer la red encuentra cadenas que nadie le enseñó y crea hipótesis.
   - **Una duda:** *"¿Agua… apaga… fuego?"*
   - **Una opinión:** *"Pelota… me gusta."*
   - **Un reencuentro:** a veces pasa por algo latente y lo reactiva un poco (*"¿lluvia…? Lluvia…"*).
4. **Decide si lo dice en voz alta**, según su personalidad (las criaturas más extrovertidas hablan más solas), su estado (si está aburrida o sola, habla más) y la novedad del pensamiento.
5. **Si es una duda importante, se la pregunta a su dueño** cuando él vuelve a hablarle.

Todos los pensamientos (dichos o no) aparecen en el **panel del cerebro**, para ver qué está pensando.

> Este monólogo es también un **mecanismo de aprendizaje**: al pensar sola, Muyu descubre conexiones nuevas y repasa lo que sabe.

### 4.9 Modelo emocional

Funciona en tres capas, cada una con su velocidad:

| Capa | Velocidad | Ejemplo |
|---|---|---|
| **Emoción** | Segundos | Se sobresalta por un grito |
| **Estado de ánimo** | Horas | Después de muchos sustos queda ansiosa |
| **Relación** | Días | Confianza y afecto hacia su dueño |

- **Espacio PAD:** Placer, Activación y Dominancia (Mehrabian). Cada emoción es un punto en ese espacio.
- **Evaluación cognitiva (appraisal):** para cada evento, Muyu calcula qué tan inesperado, agradable, peligroso y controlable es. De ahí sale la emoción.
- **Inercia y decaimiento:** las emociones cambian con curvas suaves y vuelven poco a poco al estado de ánimo base.
- **Necesidades:** energía, hambre, compañía y seguridad modulan todo lo demás.
- **Ambivalencia:** puede sentir curiosidad y miedo a la vez (se acerca y retrocede).
- **Rastro causal:** cada cambio emocional guarda su causa, para mostrarla en el panel.

### 4.10 Lenguaje (habla propia, desde cero)

El habla evoluciona por etapas, según cuántas palabras **activas** tiene:

| Etapa | Condición aproximada | Cómo habla |
|---|---|---|
| 0. Balbuceo | Léxico vacío | Sílabas sin sentido: *"mu… ba?"* |
| 1. Imitación | ~10 palabras activas | Repite palabras sueltas que oyó mucho |
| 2. Palabra-frase | ~30 palabras activas | Una palabra con intención: *"¡comida!"* |
| 3. Dos palabras | ~80 palabras activas | *"fuego malo"*, *"David volvió"* |
| 4. Frases simples | ~200 palabras activas | *"No quiero fuego. Duele."* |
| 5. Frases propias | Modelo neuronal entrenado | Combinaciones que nunca le enseñaron |

> Los umbrales son configurables en `config.py` para poder probar cada etapa rápido durante el desarrollo.

**Cómo genera una respuesta:**
1. El razonamiento elige **qué quiere decir** (respuesta, pensamiento o reacción + emoción).
2. El modelo de lenguaje elige **cómo decirlo** con las palabras y combinaciones que aprendió.

**Modelos de lenguaje (todos entrenados desde cero):**
- **Etapas 1 a 4:** modelo de n-gramas a nivel de palabra, con suavizado, actualizado en tiempo real con cada frase del dueño.
- **Etapa 5:** red neuronal pequeña (GRU o un transformer diminuto, unos cientos de miles de parámetros) entrenada **desde pesos aleatorios** en la PC durante el sueño, solo con las conversaciones de esa criatura. Al ser tan pequeña, entrena en minutos.

Muyu habla **como le hablan**: si su dueño usa jerga ecuatoriana, ella también la usará.

### 4.11 El sueño (consolidación)

Cuando Muyu duerme (por la noche o cuando su dueño la acuesta), el servidor ejecuta su **consolidación**:

1. **Repaso:** recorre las experiencias del día priorizando las más emocionales.
2. **Refuerzo:** fortalece lo importante y lo repetido.
3. **Atenuación:** baja la importancia de lo poco usado (sin borrarlo nunca).
4. **Generalización:** agrupa conceptos en categorías.
5. **Entrenamiento neuronal** *(desde la fase 4)*: entrena su modelo de lenguaje propio con PyTorch.
6. **Sueños:** guarda una combinación de recuerdos activos para contarla al despertar (*"soñé… agua… fuego"*).

---

## 5. Audio

### 5.1 Voz a texto: Whisper local (modelo abierto)

- Librería: [`faster-whisper`](https://github.com/SYSTRAN/faster-whisper), en CPU o GPU.
- Modelos sugeridos: `tiny` o `base` para empezar (rápidos), `small` si la PC lo permite.
- Idioma fijo en español (`language="es"`) para mejorar la precisión.
- Se descarga **una sola vez** a `models/whisper/` y luego funciona sin internet.
- **Función única:** convertir el audio del usuario en texto. El texto entra a Muyu como si lo hubieran escrito.

### 5.2 Prosodia: propia

Del mismo audio se extraen señales con procesamiento propio (NumPy):
- **Volumen (RMS):** un grito asusta, aunque las palabras sean amables.
- **Tono (pitch):** voz aguda y suave = cariño; grave y fuerte = regaño. La **entonación ascendente al final** marca una pregunta.
- **Velocidad:** palabras por segundo.

Estas señales son **instintivas**: llegan directo al modelo emocional sin pasar por el lenguaje.

### 5.3 Voz de Muyu

- **Balbuceo (sin palabras):** sintetizador procedural propio en el navegador (Web Audio API). Sílabas generadas con tono y ritmo según su emoción. Suena a criatura, no a robot.
- **Palabras:** cuando lo que dice tiene palabras, las pronuncia con una voz del sistema **instalada en la PC** (síntesis de voz del navegador, solo voces locales: las voces en línea se descartan), aguda y con tono y velocidad según su emoción. Como Whisper, solo convierte texto en sonido: no decide qué decir.
- **Etapas 4 y 5 (opcional):** [Piper](https://github.com/rhasspy/piper) local para leer sus frases, con velocidad y tono ajustados a su estado emocional.

**Escucha continua:** el micrófono queda abierto y detecta solo cuándo le hablas (cada frase se envía al terminar un silencio). Mientras Muyu habla, o mientras piensa su respuesta, deja de escuchar para no oírse a sí misma. Se enciende con el primer toque en la página y se apaga con el botón del micrófono.

### 5.4 Micrófono en el celular

Los navegadores **solo permiten el micrófono en HTTPS** (o en `localhost`). Para usarlo desde el celular en la red local hay que servir con un certificado (ver la [sección 8.4](#84-https-local-desde-la-fase-3)).

---

## 6. Stack tecnológico

| Capa | Tecnología | Desde la fase |
|---|---|---|
| Servidor | Python 3.11+, FastAPI, Uvicorn, WebSockets | 1 |
| Cerebro | Python puro + NumPy | 1 |
| Almacenamiento | SQLite (un archivo por criatura) | 1 |
| Cliente | HTML, CSS y JavaScript, Canvas | 1 |
| Escena 3D | three.js (archivos locales) | 2 |
| Pruebas | pytest | 1 |
| Voz de criatura | Web Audio API | 2 |
| STT | faster-whisper (modelo abierto local) | 3 |
| Entrenamiento neuronal | PyTorch (CPU o GPU) | 4 |
| TTS opcional | Piper (modelo abierto local) | 4 |

---

## 7. Estructura del proyecto

```
muyu/
├── server/
│   ├── main.py                 # FastAPI: rutas HTTP y WebSocket
│   ├── config.py               # Parámetros: tasas, umbrales, velocidad del tiempo
│   ├── clock.py                # Reloj interno: ciclos de pensamiento y paso del tiempo
│   ├── brain/
│   │   ├── creature.py         # Clase Muyu: une todos los módulos
│   │   ├── instincts.py        # Señales primarias, necesidades, gestos innatos
│   │   ├── perception.py       # Texto + prosodia + acción → evento
│   │   ├── importance.py       # Importancia, estados (activo/tenue/latente), efecto de ahorro
│   │   ├── lexicon.py          # Léxico: informatividad, valencia
│   │   ├── concepts.py         # Red de conceptos (grafo con pesos)
│   │   ├── reasoning.py        # Activación, encadenamiento, hipótesis
│   │   ├── questions.py        # Respuesta a preguntas
│   │   ├── thoughts.py         # Pensamiento propio (monólogo)
│   │   ├── emotions.py         # PAD, appraisal, ánimo, relación
│   │   ├── behavior.py         # Comportamiento autónomo: qué hace su cuerpo y por qué (fase 2)
│   │   ├── memory.py           # Memoria episódica
│   │   ├── language/
│   │   │   ├── babble.py       # Etapa 0: balbuceo
│   │   │   ├── ngram.py        # Etapas 1-4: n-gramas en tiempo real
│   │   │   ├── speaker.py      # Convierte una intención en frase según su etapa
│   │   │   └── neural.py       # Etapa 5: red neuronal propia (fase 4)
│   │   └── sleep.py            # Consolidación
│   ├── audio/                  # Fase 3
│   │   ├── stt.py              # Whisper local
│   │   ├── prosody.py          # Volumen, tono, entonación, velocidad
│   │   └── tts.py              # Piper (opcional)
│   └── storage/
│       └── db.py               # Acceso a SQLite por criatura
├── web/
│   ├── index.html
│   ├── style.css
│   ├── app.js                  # Conexión WebSocket, chat, acciones
│   ├── creature.js             # Criatura 3D y sus expresiones (three.js)
│   ├── brain-panel.js          # Panel: emociones, léxico, grafo, pensamientos
│   ├── room.js                 # Habitación 3D: objetos, luz del día y de la noche (fase 2)
│   ├── voice.js                # Sintetizador de criatura (fase 2)
│   ├── mic.js                  # Micrófono: graba la voz y la envía a 16 kHz (fase 3)
│   ├── icons.js                # Iconos (Lucide, copiados localmente)
│   └── vendor/                 # three.js (MIT) y licencias, sin CDN
├── data/creatures/             # <id>.sqlite (no se sube al repo)
├── models/
│   ├── whisper/                # Modelo abierto descargado (fase 3, no se sube)
│   └── creatures/              # Pesos neuronales propios por criatura (fase 4)
├── certs/                      # Certificados HTTPS locales (fase 3, no se suben)
├── scripts/https.ps1           # Genera los certificados y sirve por HTTPS (fase 3)
├── tests/
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 8. Instalación y ejecución

### 8.1 Requisitos
- Python 3.11 o superior
- 8 GB de RAM como mínimo (16 GB recomendado desde la fase 4)
- GPU opcional (acelera Whisper y el entrenamiento)

### 8.2 Instalación

```bash
git clone <url-del-repo> muyu
cd muyu

python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux / macOS
source .venv/bin/activate

pip install -r requirements.txt
```

`requirements.txt` de la fase 1:

```
fastapi
uvicorn[standard]
numpy
pytest
```

Se agregan después: `faster-whisper` (fase 3) y `torch` (fase 4).

### 8.3 Ejecutar (fase 1 y 2)

```bash
uvicorn server.main:app --host 0.0.0.0 --port 8000
```

- Desde la PC: `http://localhost:8000`
- Desde el celular (misma red wifi): `http://<IP-local-de-tu-PC>:8000`

> Para ver la IP local: `ipconfig` (Windows) o `ip addr` (Linux).

### 8.4 HTTPS local (desde la fase 3)

Necesario para usar el micrófono desde el celular. Con [`mkcert`](https://github.com/FiloSottile/mkcert):

```bash
mkcert -install
mkcert -key-file certs/key.pem -cert-file certs/cert.pem localhost 127.0.0.1 <IP-local-de-tu-PC>

uvicorn server.main:app --host 0.0.0.0 --port 8443 \
  --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem
```

En Windows, `scripts/https.ps1` hace los dos últimos pasos: genera los certificados para `localhost` y la IP de la PC (los regenera si la IP cambia) y arranca el servidor en `https://<IP>:8443`.

En la PC no hace falta HTTPS: `http://localhost:8000` ya permite el micrófono. Whisper usa la CPU por defecto; con `MUYU_WHISPER_DISPOSITIVO=cuda` usa la GPU si están instaladas las librerías de NVIDIA (si fallan, vuelve solo a la CPU). El modelo se elige con `MUYU_WHISPER_MODELO` (`tiny`, `base` o `small`).

### 8.5 Modo de tiempo acelerado

Para probar la atenuación, el sueño y las necesidades sin esperar días:

```python
# server/config.py
VELOCIDAD_TIEMPO = 60   # 1 = tiempo real · 60 = un minuto real equivale a una hora
```

### 8.6 `.gitignore` recomendado

```
.venv/
__pycache__/
data/creatures/
models/whisper/
models/creatures/
certs/
```

---

## 9. Modelo de datos

Cada criatura tiene su propio archivo SQLite. Todas las tablas de conocimiento comparten estos campos de memoria:

| Campo común | Descripción |
|---|---|
| `importancia` | 0 a 1, con un mínimo que nunca se cruza |
| `veces_aprendida` | Cuántas veces volvió de latente a activa (para el efecto de ahorro) |
| `ultima_vez` | Última vez que se escuchó o usó |
| `primera_vez` | Cuándo la aprendió |

| Tabla | Contenido principal |
|---|---|
| `criatura` | id, nombre, fecha de nacimiento, etapa de lenguaje, rasgos innatos (semilla aleatoria) |
| `estado` | emoción PAD actual, ánimo, necesidades, despierta o dormida |
| `relacion` | confianza y afecto hacia el dueño (y luego hacia otras criaturas) |
| `lexico` | palabra, frecuencia, informatividad, valencia + campos comunes |
| `conceptos` | nodo, activación, valencia, categoría emergente + campos comunes |
| `relaciones_conceptos` | origen, destino, etiqueta, peso, origen del dato (enseñado / deducido) + campos comunes |
| `hipotesis` | cadena deducida, confianza, estado (pendiente / confirmada / rechazada), si ya la preguntó |
| `episodios` | evento completo, emoción en ese momento + campos comunes |
| `pensamientos` | contenido, tipo (recuerdo / deducción / duda / opinión / reencuentro), si lo dijo en voz alta |
| `ngramas` | contexto, siguiente palabra, conteo |
| `suenos` | fecha, qué se reforzó, qué se atenuó, sueño generado |

**Rasgos innatos:** al nacer, cada Muyu recibe una semilla aleatoria que define su temperamento base (curiosidad, timidez, terquedad, sensibilidad, cuánto habla sola). Por eso dos criaturas criadas igual no terminan idénticas.

---

## 10. Desarrollo por fases

Cada fase termina en algo **funcional y demostrable**. No se empieza una fase sin cumplir los criterios de aceptación de la anterior.

---

### 🟢 FASE 1: Prototipo completo de la mente (texto)

**Objetivo:** una criatura que nace vacía, aprende de lo que le escribes, deduce, responde preguntas, piensa sola y te recuerda al volver. Todo por chat de texto y con una representación visual simple.

**Incluye:** servidor, persistencia, instintos, percepción de texto, memoria sin olvido, léxico, red de conceptos, razonamiento, preguntas, pensamiento propio, emociones básicas, lenguaje de las etapas 0 a 3, sueño básico (sin red neuronal) y una interfaz web con panel del cerebro.

**No incluye:** voz, habitación pixel art, animaciones complejas, red neuronal ni gustos.

#### Orden de implementación

| # | Tarea | Archivos | Listo cuando… |
|---|---|---|---|
| 1 | Base del servidor | `main.py`, `config.py` | FastAPI sirve `web/` y acepta conexiones WebSocket |
| 2 | Persistencia | `storage/db.py` | Crea un `<id>.sqlite` por criatura con todas las tablas de la fase |
| 3 | Nacimiento | `creature.py`, `instincts.py` | Una criatura nueva recibe id, nombre y rasgos innatos aleatorios; el navegador guarda su id y la retoma al volver |
| 4 | Percepción | `perception.py` | El texto y las acciones (acariciar, alimentar, regañar, dormir) se convierten en eventos; detecta `?` |
| 5 | Importancia | `importance.py` | Sube con el uso, baja con el tiempo hasta un mínimo, calcula el estado y aplica el efecto de ahorro |
| 6 | Léxico | `lexicon.py` | Registra palabras, calcula informatividad y valencia a partir de las señales primarias |
| 7 | Red de conceptos | `concepts.py` | Crea nodos y relaciones con aprendizaje hebbiano y atenuación |
| 8 | Emociones | `emotions.py` | PAD con decaimiento, reacción a señales primarias y a la valencia de las palabras, confianza en el dueño |
| 9 | Memoria episódica | `memory.py` | Guarda cada interacción con su emoción e importancia |
| 10 | Razonamiento | `reasoning.py` | Activación propagada, encadenamiento, hipótesis con confianza, confirmación y corrección |
| 11 | Preguntas | `questions.py` | Responde sí/no, "qué es", "te gusta" y "qué pasa si" desde su red; muestra duda o confusión si no sabe |
| 12 | Lenguaje | `babble.py`, `ngram.py`, `speaker.py` | Habla según su etapa (0 a 3), usando solo palabras activas o tenues |
| 13 | Reloj interno | `clock.py` | Avanza el tiempo, baja necesidades, aplica atenuación y dispara ciclos de pensamiento |
| 14 | Pensamiento propio | `thoughts.py` | Genera recuerdos, deducciones, dudas, opiniones y reencuentros; decide si los dice en voz alta |
| 15 | Sueño básico | `sleep.py` | Al dormir: repaso, refuerzo, atenuación y un sueño para contar al despertar |
| 16 | Interfaz | `index.html`, `app.js`, `creature.js` | Chat, botones de acción y criatura simple (forma + ojos) que cambia de expresión según su emoción |
| 17 | Panel del cerebro | `brain-panel.js` | Muestra emoción PAD, etapa de lenguaje, léxico por estado (activo/tenue/latente), grafo en vivo, pensamientos e hipótesis |
| 18 | Pruebas | `tests/` | Pruebas unitarias de importancia, léxico, conceptos, razonamiento y preguntas |

#### Criterios de aceptación (guion de demo)

La fase 1 está **completa** cuando este guion funciona de principio a fin:

1. **Nacimiento:** abro la página → aparece una criatura nueva que solo balbucea.
2. **Primeras palabras:** le escribo varias veces *"hola Muyu"* y la acaricio → empieza a decir *"hola"* y la palabra "hola" toma valencia positiva.
3. **Aprendizaje de relaciones:** le escribo *"el fuego quema"* y *"quemar duele"* → ambas relaciones aparecen en el grafo.
4. **Deducción propia:** sin enseñárselo, Muyu dice o piensa *"¿fuego… duele?"* y la hipótesis aparece en el panel.
5. **Confirmación:** respondo *"sí"* (la primera vez, junto con 👍 para que aprenda qué significa) → la hipótesis pasa a conocimiento confirmado.
6. **Pregunta sí/no:** pregunto *"¿el fuego quema?"* → responde que sí (con palabra o gesto).
7. **Pregunta abierta:** pregunto *"¿qué es fuego?"* → responde con sus relaciones (*"quema… duele"*).
8. **Pregunta sin respuesta:** pregunto por algo que nunca le enseñé → muestra confusión o devuelve la pregunta.
9. **Pensamiento propio:** dejo de escribir un rato → piensa sola (se ve en el panel) y a veces habla en voz alta.
10. **Emoción:** la regaño varias veces → su expresión cambia y su confianza baja.
11. **Persistencia:** cierro el navegador, lo vuelvo a abrir → es la misma criatura, con todo lo aprendido.
12. **Memoria sin olvido:** con tiempo acelerado, dejo una palabra sin usar hasta que queda latente → al volver a escribirla dice *"¿mm… eso… ya escuché?"* y la recupera más rápido que la primera vez.
13. **Sueño:** la mando a dormir → al despertar cuenta un sueño con conceptos que conoce.

---

### 🟡 FASE 2: Cuerpo y vida

**Objetivo:** que Muyu se vea y se sienta viva.

- Habitación pixel art con objetos con los que puede interactuar
- Animaciones por emoción (postura, ojos, velocidad, ambivalencia)
- Comportamiento autónomo: explora, juega sola, se aburre, se duerme, te busca
- Necesidades completas (hambre, energía, compañía, seguridad)
- Appraisal completo, ánimo y relación con todas sus capas
- Sintetizador de voz de criatura (Web Audio API)
- Diseño adaptado al celular

**Criterio de aceptación:** dejada sola, Muyu hace cosas distintas según su estado, y su cuerpo, su voz y sus palabras expresan la misma emoción.

---

### 🟠 FASE 3: Voz

**Objetivo:** hablarle con la voz desde la PC o el celular.

- HTTPS local con `mkcert`
- Grabación de audio en el navegador
- STT con Whisper local (`faster-whisper`)
- Prosodia propia: volumen, tono, velocidad y entonación de pregunta, conectados al modelo emocional

**Criterio de aceptación:** si le hablo suave se acerca, si grito se asusta aunque diga algo amable, y si pregunto con entonación (sin decir "qué"), lo trata como pregunta.

---

### 🔴 FASE 4: Sueño neuronal

**Objetivo:** que su lenguaje deje de ser estadístico y se vuelva propio.

- Red neuronal pequeña de lenguaje entrenada desde pesos aleatorios con PyTorch
- Entrenamiento incremental durante cada sueño con las conversaciones de esa criatura
- Generalización en categorías emergentes
- Etapas de lenguaje 4 y 5
- TTS opcional con Piper

**Criterio de aceptación:** después de varios sueños, Muyu dice frases correctas que nadie le enseñó literalmente, y la perplejidad de su modelo baja de un sueño a otro.

---

### 🟣 FASE 5: Gustos propios

**Objetivo:** que tenga opiniones que no sean una copia de las de su dueño.

- Percepción visual propia (color, brillo, complejidad, simetría) calculada desde la imagen
- Juicio estético: rasgos innatos + novedad (curva de Berlyne) + contexto emocional + influencia del dueño según confianza y terquedad
- Rasgos de audio propios para música (tempo, energía, modo)
- Galería de obras que le gustan y que no, con sus razones

**Criterio de aceptación:** dos criaturas a las que se les muestran las mismas obras terminan con gustos distintos, y una criatura terca puede rechazar algo que su dueño insiste que es bonito.

---

### 🔵 FASE 6: Social

**Objetivo:** que las criaturas se influyan entre ellas.

- Visitas entre criaturas
- Intercambio de palabras, obras y opiniones
- Afinidad, influencia social y desacuerdos
- Recuerdos de las otras criaturas

**Criterio de aceptación:** una criatura vuelve de una visita usando una palabra que su dueño nunca le enseñó, y puede contar qué opinó de lo que le mostraron.

---

### ⚪ FASE 7: Publicación

- Exposición pública del servidor para el portafolio
- Modo PWA instalable
- Landing del proyecto con video de demo

---

## 11. Métricas de evaluación

Pensadas para medir el aprendizaje y para un posible artículo científico:

| Métrica | Qué mide |
|---|---|
| Palabras por estado en el tiempo | Adquisición de vocabulario y paso de activo a latente |
| Tiempo de recuperación de latentes | Efecto de ahorro frente al aprendizaje inicial |
| Densidad y crecimiento del grafo | Cuánto conocimiento estructura |
| Precisión de las deducciones | % de hipótesis que el dueño confirma |
| Precisión de las respuestas | % de preguntas respondidas correctamente según lo enseñado |
| Deducciones por pensamiento propio | Cuánto aprende sola, sin que le enseñen |
| Perplejidad del modelo de lenguaje | Calidad del modelo neuronal tras cada sueño (fase 4) |
| Diversidad entre criaturas | Qué tan distintas terminan criaturas con distintos dueños |
| Estabilidad emocional | Variabilidad del estado de ánimo ante el mismo trato |
| Percepción del usuario | Credibilidad y conexión (cuestionario Godspeed) |

---

## 12. Limitaciones conocidas

- **No es un asistente.** Muyu solo sabe lo que le enseñaron. Responde preguntas sobre lo que aprendió, no sobre el mundo en general.
- **Aprende despacio.** Necesita muchas conversaciones para hablar con fluidez.
- **Lenguaje limitado.** Al entrenarse solo con su dueño, su español será simple y parecido al de quien la cría.
- **Simula emociones, no las siente.** El modelo produce comportamientos emocionales coherentes, no experiencias subjetivas.
- **La memoria crece siempre.** Como nada se borra, la base de datos de cada criatura solo aumenta. En la práctica, el texto ocupa poco, pero el razonamiento debe consultar primero lo activo y tenue para mantenerse rápido.
- **Depende del servidor.** Mientras el servidor sea mi PC, Muyu solo "vive" cuando la PC está encendida.
- **Whisper puede equivocarse** al transcribir; Muyu aprendería esos errores como si fueran palabras reales.

---

## Autor

**David Giler**, estudiante de Ingeniería de Software.

## Licencia

Por definir.