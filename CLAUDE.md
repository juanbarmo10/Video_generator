# CLAUDE.md

Guía del proyecto para Claude Code. Escrita en español porque el proyecto, los prompts y los scripts están en español.

## Qué es este proyecto

Fábrica automatizada de contenido histórico viral para redes sociales. A partir de una lista de temas
(`temas.csv`) genera, por cada tema y de punta a punta:

- un guion de ~90-100 palabras (GPT-4.1),
- narración en voz (ElevenLabs),
- 8 imágenes ilustradas por IA (fal.ai / Flux dev),
- un video vertical 9:16 con subtítulos animados palabra por palabra + música de fondo,
- posts para Twitter/X, Threads, Instagram y Facebook,
- un carrusel de Instagram (imágenes reales descargadas de Wikimedia/DuckDuckGo + texto quemado).

La cuenta destino es `@chistoricas3` (la marca de agua está hardcodeada en el generador de carrusel).

**Es un repositorio git** (inicializado en agosto 2026, historial completo desde el estado que tenía
el pipeline antes de la auditoría). `.gitignore` excluye el `.env`, las salidas pesadas (`videos/`,
`videos_no_music/`, `proyectos/`, `music/`) y el estado del tema en curso. Hay `requirements.txt`
(con `moviepy==1.0.3` fijado) pero **no hay tests**. Todo se corre a mano desde bash.

📋 **[TODO.md](TODO.md) es el documento de trabajo**: auditoría de 18 bugs, diagnóstico de contenido
y plan de crecimiento en 4 fases. Las fases 1-3 están aplicadas; léelo antes de tocar el pipeline.

## Cómo se ejecuta

```bash
# Lote completo: procesa todas las filas de temas.csv
bash run_all.sh

# Un solo tema (usa PROYECTO y TEMA del .env, o del entorno)
bash run_pipeline.sh
```

El entorno es conda: `ai_video_bot` (Python 3.11). `run_all.sh` y `run_pipeline.sh` lo activan solos.
Para correr un script suelto:

```bash
source /home/juanb/miniforge3/etc/profile.d/conda.sh && conda activate ai_video_bot
PROYECTO=Prueba01 TEMA="Pelé" python 01_script_generator.py
```

Los scripts tienen celdas `#%%` — están pensados también para ejecución interactiva en VS Code.

## Arquitectura del pipeline

`run_all.sh` lee `temas.csv` → por cada fila escribe `PROYECTO`/`TEMA` en `.env`, los exporta y llama a
`run_pipeline.sh`, que corre los 8 pasos en orden con `set -e` (cualquier fallo aborta el tema).
Cada paso es un proceso Python independiente que se comunica con los demás **solo a través de archivos
en la raíz del proyecto**.

**Único módulo compartido: [estado.py](estado.py).** No es un paso del pipeline, es una biblioteca:
- `sellar_estado()` / `verificar_estado()` — el paso 01 escribe `.estado_actual` con el `PROYECTO` en
  curso y los pasos 02, 03, 04 y 07 abortan si los archivos de la raíz son de otro tema. Sin esto, un
  fallo a mitad del pipeline dejaba que los pasos siguientes trabajaran con los datos del tema anterior.
- `registrar_openai()` / `registrar_imagen_fal()` / `registrar_elevenlabs()` / `resumen_costo()` —
  contador de costo por tema en `.costo_actual.json`.
- `con_reintentos()` — backoff exponencial para las llamadas de API.

| Paso | Script | Entrada | Salida | Servicio |
|---|---|---|---|---|
| 01 | [01_script_generator.py](01_script_generator.py) | `$TEMA` | `script.txt`, `.estado_actual` | OpenAI `gpt-4.1` |
| 02 | [02_social_media_generator.py](02_social_media_generator.py) | `script.txt` | `social_posts/descripcion.txt` + insumos internos, `TITULO_VIDEO` en `.env` | OpenAI `gpt-4.1` |
| 03 | [03_voice_generator.py](03_voice_generator.py) | `script.txt` | `voice.mp3` (acelerado ×1.10) | ElevenLabs `eleven_multilingual_v2` + ffmpeg |
| 04 | [04_image_generator.py](04_image_generator.py) | `script.txt` | `images_IA/scene_0..7.png` | OpenAI + fal.ai `fal-ai/flux/dev` |
| 05 | [05_download_images.py](05_download_images.py) | `social_posts/images_to_download.txt` | `source_images/img_N.jpg` | Wikimedia Commons → DuckDuckGo |
| 06 | [06_carrusel_generator.py](06_carrusel_generator.py) | `social_posts/03_instagram.txt` + `source_images/` | `carousel_slides/slide_NN_*.jpg` | Pillow (local) |
| 07 | [07_video_generator.py](07_video_generator.py) | `images_IA/` + `source_images/` + `voice.mp3` | `videos_no_music/video_$PROYECTO.mp4` + `.srt` | faster-whisper + moviepy (local) |
| 08 | [08_music_mixer.py](08_music_mixer.py) | video sin música + `music/` | `videos/video_$PROYECTO.mp4` | **ffmpeg** (local) |

Los pasos 02, 06 y 07 además copian sus artefactos a `proyectos/$PROYECTO/` como respaldo permanente.

### Detalles por paso que importan al editar

- **01** — El prompt es el corazón del producto: reglas estrictas (**65-75 palabras**, nada de fechas,
  frases ≤12 palabras, **la primera ≤8 y sin revelar el desenlace**, prohibido empezar con
  "En/Cuando/Fue/Era/Hubo", verificabilidad obligatoria). El system prompt insiste en rigor
  periodístico. Si se toca, se cambia el tono de todos los videos. También sella `.estado_actual` y
  reinicia el contador de costo.
  **Control de calidad en dos capas** (`escribir_guion_con_control()`), porque el generador no se
  audita bien a sí mismo:
  1. `verificar_reglas_mecanicas()` — Python puro, gratis: cuenta palabras, mide la primera frase,
     busca fechas, inicios prohibidos y muletillas (`se dice`, `al parecer`…). **A un LLM no se le
     pide que cuente palabras**: lo hace mal y cobra por hacerlo mal.
  2. `evaluar_con_critico()` — segundo modelo con rol adversarial que solo juzga lo que necesita
     criterio: verificabilidad de cada afirmación, spoiler en la primera frase, línea narrativa
     única. Devuelve `nota` 0-10 + `afirmaciones_dudosas`.
     **Corre en OTRO proveedor a propósito** (`claude-opus-5` vía el SDK `anthropic`): un modelo de
     la misma familia que el generador comparte sus puntos ciegos. `critico_proveedor: "auto"` usa
     Anthropic si hay `ANTHROPIC_API_KEY` y **cae a `gpt-4.1` si no**, así que la clave es opcional
     y el pipeline nunca se rompe por su ausencia. En el lado Anthropic el JSON se fuerza con
     structured outputs (`output_config.format`), no por prompt.
     ⚠️ En Opus 5 el thinking está **on por defecto** y `critico_max_tokens` limita
     thinking + respuesta *juntos*: si se queda corto, el JSON sale truncado. `critico_effort`
     (`medium`) es la palanca de costo real.

  Si no pasa, **reescribe pasándole los fallos concretos** hasta `intentos_max` (3). Si ninguno pasa,
  usa el mejor con un aviso ruidoso (`abortar_si_ninguno_pasa` lo cambia a abortar).
  Cuesta 2 llamadas por intento: **~$0.019 en el peor caso frente a $0.003 sin control**.
- **02** — Hace 6 llamadas a OpenAI. Produce **UN solo texto publicable**, `descripcion.txt`, porque
  el mismo reel se sube a Facebook, Instagram, TikTok y YouTube con la misma descripción y programar
  una semana en Metricool tiene que ser abrir un archivo por video, no dos. Cinco secciones:
  título de YouTube (≤70 chars), pie del reel para las 4 redes, descripción larga tipo Facebook,
  12 tags de YouTube y comentario para fijar.
  ⚠️ El pie del reel **no puede nombrar ninguna red ni función que no exista en todas** ("desliza",
  "link en bio", "guarda este post"). Máx. 600 chars contando hashtags.
  **Los hashtags van repetidos bajo CADA una de las dos descripciones y sin encabezado propio**, a
  propósito: así se selecciona descripción + hashtags de una pasada y se pegan juntos. No es
  duplicación por descuido.
  Siguen siendo **dos llamadas distintas** a GPT (`generar_descripcion_general()` y
  `generar_descripcion_detallada()`); la fusión ocurre al escribir, en `escribir_descripcion()`.
  Los hashtags se separan del pie con `separar_hashtags()`, en Python: recorre las líneas desde el
  final y toma las que solo tienen tokens que empiezan por `#`. Si no hay, avisa y deja la sección
  vacía en vez de romperse.
  **`LIMITE_DESCRIPCION_LARGA = 1999`** es un tope duro del bloque *descripción larga + hashtags*.
  El prompt pide ≤1700 chars para que casi nunca haga falta recortar, pero **el que garantiza el
  límite es `recortar_a_limite()`, en Python** — a un LLM no se le pide que cuente caracteres.
  Recorta conservando **siempre el último párrafo** (ahí está la pregunta que invita a comentar) y
  salvando del resto las frases que quepan. A nivel de párrafo entero se perdían 490 chars para
  ahorrar 53; por frases se pierden ~150.

  El resto de `social_posts/` son **insumos internos, no textos para copiar y pegar**:
  `carrusel.txt` (paso 06), `images_to_download.txt` (paso 05, formato `img_N.jpg → query`),
  `00_investigacion.txt` y `metadata.json` (de ahí saca el paso 09 el título sin parsear prosa).
  ⚠️ El formato de `carrusel.txt` (párrafos separados por línea en blanco, sin etiquetas "Slide N")
  es un contrato con el paso 06: si cambia el prompt, se rompe el parseo del carrusel. **`generate_title()` NO resume el guion**: genera un gancho que abre la pregunta
  sin responderla (un resumen equivale al spoiler, y ese texto va quemado en el frame 0 del video).
- **03** — `voice_id = "l1zE9xgNpUTaQCZzpNJa"` hardcodeado. **Aborta con código != 0 si ElevenLabs
  falla**: si no, los pasos siguientes usarían el `voice.mp3` del tema anterior. Después acelera el
  audio con `atempo=VELOCIDAD` (1.10) porque ElevenLabs entrega ~143 palabras/minuto y la narración
  que retiene va a 170-190. El resto del archivo (Google TTS) está comentado.
  `03_voice_generator_free.py` es una alternativa con OpenAI TTS (`tts-1-hd`, voz `onyx`) y un modo
  `--test-voices`; **no está en el pipeline**.
- **04** — ⚠️ **Pedirle a Flux "no paper border, no frame" NO funciona**: los modelos de difusión
  ignoran las instrucciones negativas y el marco de pergamino sale igual. Se recorta en el paso 07
  con `recorte_borde_pct` (8 %), que es determinista. No pierdas tiempo peleándote con el prompt.
  `extract_context()` saca personaje/época/apariencia del guion y ese contexto **sí** ancla tanto
  las escenas como cada prompt de imagen (si el modelo no devuelve json usable, degrada a `None` y sigue
  sin anclaje). Genera 8 escenas visuales en JSON con GPT y las manda a fal.ai en paralelo (3 workers,
  seed fijo 12345). Tiene un bloque grande de moderación: `BANNED_WORDS` + `REPLACEMENTS` +
  `sanitize_prompt()` reescriben palabras que disparan filtros (muerte, violencia, sangre). El
  `BASE_PROMPT` activo es el segundo — *vintage editorial illustration* sobre pergamino. `PROMPT_MAX_CHARS`
  (900) limita el prompt recortando **solo la escena**: el estilo base y el contexto van siempre completos.
  Limpia `images_IA/*.png` antes de generar.
- **05** — Busca primero en Wikimedia Commons (libre), y si falla cae a DuckDuckGo Images
  (⚠ posibles derechos de autor). `DELAY = 7.0s` entre requests para no ser bloqueado, así que este paso
  es el más lento del pipeline. Cada imagen se recorta a 1080×1080 sobrescribiendo el original. Vacía
  `source_images/` (jpg, jpeg, png, webp) antes de descargar.
  **`validar_con_vision()`** mira cada imagen descargada con `gpt-4.1` y la descarta si no corresponde
  a la query, probando con la siguiente candidata (`is_relevant()` solo miraba título y URL, y dejaba
  pasar fotos sin ninguna relación). Ante cualquier fallo acepta la foto: es filtro de calidad, no
  guarda de seguridad. Se desactiva con `VALIDAR_CON_VISION = False`.
  ⚠️ **No dejes archivos a mano en `source_images/`**: el paso 06 la lee entera para el carrusel de
  Instagram. El paso 07 sí filtra por el patrón `img_N.ext`, pero el 06 no.
- **06** — Slide 1 = portada (hook), slides intermedios = cuerpo, slide final = CTA sobre
  `perfil/historia_profile.png` (obligatorio, se pasa con `--profile`). Filtros de imagen y borde
  configurables en `CONFIG`. Marca de agua `@chistoricas3` arriba a la izquierda. Limpia
  `carousel_slides/` antes de generar.
- **07** — El más complejo. Transcribe `voice.mp3` con faster-whisper (`medium`, español) para obtener
  timestamps **por palabra**, y renderiza los subtítulos como `VideoClip` dinámico: pares fijos de 2
  palabras, la que se está pronunciando en amarillo (255,220,0). Todo el ajuste visual vive en `CONFIG`.
  Cosas que hay que saber antes de tocarlo:
  - **`rgba_a_clip()` es obligatorio para cualquier overlay.** `to_mask()` de moviepy 1.0.3 usa
    `canal=0` (ROJO) por defecto, no el alfa: con el default, el contorno negro del texto queda
    transparente y no se dibuja. El helper pide `canal=3`.
  - **`repartir_planos()` decide los cortes**, no un número fijo: cada imagen se parte en varios
    encuadres (`crear_planos_de_imagen()` + `ENCUADRES`) hasta acercarse a `duracion_plano_objetivo`
    (1.8s). Ojo: la cantidad de imágenes varía porque las fotos reales suman a la secuencia.
  - **Mezcla fotos reales** de `source_images/` (`preparar_fotos_reales()` las convierte de 1080×1080
    a 9:16 con fondo desenfocado, cacheadas en `.cache_fotos_reales/`).
  - El título dura `title_duration` (2.5s) y se va con fade; el CTA va **encima** de la última frase.
  - Exporta `.srt` a `proyectos/$PROYECTO/`.
- **08** — **Ya no usa moviepy: es un mux con ffmpeg.** Copia el stream de video bit a bit
  (`-c:v copy`), así que no hay pérdida de calidad ni se pierde el `+faststart` del paso 07. Elige un
  mp3 aleatorio de `music/`, lo loopea con `-stream_loop -1`, aplica ducking por `sidechaincompress`
  (la música baja sola cuando habla el narrador) y normaliza a **−14 LUFS** con `loudnorm`, que es el
  estándar de redes. Tarda ~3s en vez de ~1 minuto.

## Variables de entorno (`.env`)

Claves de API: `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`, `FAL_KEY`, `ANTHROPIC_API_KEY` (**opcional** —
si está, el crítico del paso 01 corre en Claude; si no, cae a `gpt-4.1`), `LEONARDO_API_KEY` (ya no se
usa), `FISH_API_KEY` (no se usa), `GOOGLE_TTS_API_KEY` (solo para el código comentado del paso 03).

Parámetros de ejecución, **escritos por los scripts, no a mano**:
- `PROYECTO` — nombre corto que da nombre a video y carpeta de respaldo. Lo escribe `run_all.sh`.
- `TEMA` — tema del guion. Lo escribe `run_all.sh`.
- `TITULO_VIDEO` — lo escribe el paso 02, lo consume el paso 07 como título en pantalla.

`.env` es estado mutable del pipeline, no solo configuración. Nunca lo commitees ni lo publiques: tiene
claves reales en texto plano.

Los pasos 02, 06, 07 y 08 abortan de entrada si `PROYECTO` viene vacío (y el 07 también si falta
`TITULO_VIDEO`), y `run_pipeline.sh` falla si no tiene `PROYECTO` y `TEMA`. Es intencional: correr sin
esas variables ensucia el árbol de proyectos con rutas tipo `proyectos//` y `video_None.mp4`.

## Estructura de archivos

```
TODO.md                # auditoría de bugs + plan de crecimiento (documento de trabajo)
INSTRUCCIONES_CHATGPT.md  # prompt para que ChatGPT proponga temas que el pipeline aguante
METRICAS.md            # de dónde sacar las métricas de las 4 redes y cómo agilizarlo
metricas.csv           # una fila por (PROYECTO, plataforma, fecha_snapshot)
metricas_export/       # ← CSV crudos descargados de cada plataforma (ignorado por git)
estado.py              # módulo compartido: sello de tema, costo, reintentos
requirements.txt       # moviepy==1.0.3 fijado; ffmpeg va aparte (apt)
.env.example           # plantilla del .env (el .env real NO se commitea)

temas.csv              # entrada del lote: PROYECTO,TEMA (con encabezado, 2 campos exactos)
script.txt             # ← guion del tema EN CURSO (se sobrescribe cada run)
voice.mp3              # ← narración del tema EN CURSO (ya acelerada ×1.10)
social_posts/          # ← descripcion.txt del tema EN CURSO + insumos internos
images_IA/             # ← 8 imágenes IA del tema EN CURSO (scene_N.png, 832×1472)
source_images/         # ← fotos reales descargadas del tema EN CURSO (img_N.jpg)
carousel_slides/       # ← slides del tema EN CURSO
.estado_actual         # ← sello: qué PROYECTO/TEMA son los archivos de la raíz
.costo_actual.json     # ← costo acumulado del tema EN CURSO
.cache_fotos_reales/   # ← fotos reales convertidas a 9:16 para el video
videos_no_music/       # video_$PROYECTO.mp4 sin música
videos/                # video_$PROYECTO.mp4 FINAL (entregable)
proyectos/$PROYECTO/   # respaldo por tema: mp3, srt, images_IA, source_images, social_posts, carousel_slides
logs/                  # {PROYECTO}_{TEMA}.log por tema + failed.csv
music/                 # mp3 royalty-free de fondo
fonts/                 # BungeeSpice (subtítulos y carrusel), Cossette_Texte
perfil/                # imagen de perfil y banner para el slide CTA
```

**[09_paquete_publicacion.py](09_paquete_publicacion.py)** no es un paso del pipeline: se corre
UNA VEZ después de `run_all.sh`. Junta en `publicar/<TEMA>/` el video (con hardlink, cero espacio
extra), el `.srt`, `descripcion.txt` y el carrusel, y escribe `publicar/calendario.csv` con
las fechas repartidas. Marca los temas incompletos y los guiones que **no** pasaron el control de
calidad del paso 01 (que deja su veredicto en `proyectos/$PROYECTO/calidad_guion.json`).
Acepta `descripcion_general.txt` + `descripcion_detallada.txt` como alternativa (`textos_legado`)
para no marcar como incompletos los respaldos anteriores a la fusión, y **borra los dos formatos del
destino antes de copiar**, para que rehacer un paquete no deje el archivo viejo al lado del nuevo.
Sin `--solo` empaqueta **todo** lo que haya en `videos/`, incluidos los lotes viejos.

**[10_metricas.py](10_metricas.py)** tampoco es un paso del pipeline: consolida en `metricas.csv`
los CSV que se descargan de YouTube, TikTok, Instagram y Facebook y se dejan en `metricas_export/`
(el nombre del archivo tiene que empezar por la plataforma). Ver **[METRICAS.md](METRICAS.md)** para
de dónde sale cada export.
- **Empareja por texto, no por id**: las plataformas no conocen el `PROYECTO`, así que compara el
  título/caption contra el `titulo` de `metadata.json` y el pie del reel de `descripcion.txt`. Lo
  que no llega a `umbral_match` (0.60) **se reporta, no se adivina**.
- **Los nombres de columna cambian con el idioma de la cuenta.** El mapeo va por el diccionario
  `ALIAS` y ⚠️ **el orden dentro de cada lista es la prioridad**: sin eso, el export de YouTube
  emparejaba `Contenido` (que es el id del video) como título y no encajaba ni una fila. Al terminar
  imprime las columnas que no reconoció, para poder añadirlas al alias.
- **`fecha_snapshot` es la clave del diseño**: un export trae vistas ACUMULADAS, no "vistas a 24 h".
  Guardando una foto por fecha, los deltas salen de restar dos filas. Fusiona por
  `(PROYECTO, plataforma, fecha_snapshot)` y nunca pisa un valor lleno con uno vacío.
- `pct_llega_3s` **no sale de ningún export**: se lee a mano de la curva de retención de YouTube
  Studio. Es la métrica que dice si el gancho funciona.

Scripts fuera del pipeline: `publisher.py` (publicación a Meta/Threads), `ink_filter.py` (convierte fotos
reales a estilo tinta/pergamino, alternativa local al paso 04), `imagen_generator_source.py` (versión
vieja del generador con Leonardo).

## Convenciones del código

- Todo en español: nombres de funciones en inglés a veces, pero prints, comentarios y prompts en español,
  con emojis como marcadores de estado (✅ ❌ 🎬 ⏱️).
- Cada script define un dict `CONFIG` al inicio con todos los parámetros ajustables y comentarios
  explicando los rangos. **Si agregas un parámetro, va en `CONFIG`, no disperso en el código.**
- Rutas relativas al directorio del proyecto: todos los scripts asumen que se corren desde
  `/home/juanb/video_generator`.
- Cada script es standalone con `if __name__ == "__main__"` y `load_dotenv()` al inicio.
- Separadores visuales con `═` / `─` para dividir secciones dentro de un archivo.

## Trampas conocidas (leer antes de tocar nada)

1. **Los archivos de la raíz son estado global compartido.** `script.txt`, `voice.mp3`, `images_IA/`,
   `source_images/`, `carousel_slides/` y `social_posts/` se sobrescriben en cada tema — solo existe el
   tema en curso. Los pasos 02, 04, 05 y 06 vacían su carpeta de salida antes de escribir, y
   `.estado_actual` (ver `estado.py`) hace que los pasos 02/03/04/07 aborten si los archivos son de otro
   `PROYECTO`. Los respaldos viejos en `proyectos/` conservan la basura previa a estos arreglos (p. ej.
   `proyectos/Mundial16/carousel_slides/` tiene `slide_06_cta.jpg` y `slide_07_cta.jpg`); limpiarlos es
   manual. Los respaldos usan `copytree(dirs_exist_ok=True)`, o sea que **rehacer un `PROYECTO` existente
   fusiona en vez de reemplazar**: borra la carpeta destino a mano si vas a reintentar un tema.
2. **Funciones duplicadas: gana la segunda definición de Python.** En `04_image_generator.py` hay dos
   `generate_image()` — la activa es la de fal.ai; la de Leonardo (líneas ~212-280) es código muerto. Igual
   con `BASE_PROMPT` (gana el segundo) y con `parse_instagram_file()` en `06_carrusel_generator.py`.
   Editar la primera copia no tiene ningún efecto.
3. **A pesar del nombre del proyecto, las imágenes ya NO salen de Leonardo**, sino de fal.ai (Flux dev).
4. El contexto del paso 04 depende de que GPT devuelva json con `personaje`, `epoca` y `estilo_visual`.
   Si falla, verás `⚠️ Contexto incompleto` en el log y las imágenes de ese tema saldrán sin anclaje
   (menos coherentes entre sí, pero el tema no aborta).
5. Las carpetas sueltas `proyectos/social_posts`, `proyectos/carousel_slides` y `proyectos/source_images`
   son basura de corridas viejas con `PROYECTO` vacío. Ya no se pueden volver a crear (hay guardas en los
   pasos y en `run_pipeline.sh`), pero nadie las borró todavía.
6. **moviepy está clavado en 1.0.3** (API `from moviepy.editor import ...`). Actualizar a 2.x rompe el
   paso 07 completo. El paso 08 ya no depende de moviepy.
   ⚠️ En esa versión **`to_mask()` usa el canal ROJO por defecto (`canal=0`), no el alfa**. Cualquier
   overlay nuevo del paso 07 debe pasar por `rgba_a_clip()`, que pide `canal=3`. Si dibujas texto con
   contorno negro y usas `to_mask()` sin argumento, el contorno sale invisible.
7. El paso 07 lee `.png` de `images_IA/` **y** (vía `preparar_fotos_reales()`) `.jpg/.jpeg/.png/.webp`
   de `source_images/`; el 06 lee las mismas extensiones de `source_images/`.
8. `temas.csv` debe tener encabezado `PROYECTO,TEMA` y exactamente 2 campos por fila. `run_all.sh`
   salta la primera línea, ignora las vacías, **rechaza las filas con más de 2 campos** (antes una
   coma extra como `Mundial11,Maradona,` ensuciaba `$TEMA`, porque `read` mete los campos sobrantes en
   la última variable) y **salta los encabezados repetidos** (`tail -n +2` solo quita el primero, así
   que un `PROYECTO,TEMA` pegado dos veces se procesaba como un tema real).
11. **Los `.sh` se re-ejecutan solos con bash.** En Ubuntu `/bin/sh` es `dash`, que no tiene `source`
    ni `[[ ]]`: con `sh run_all.sh` el shebang se ignora, el `source` de conda falla en silencio y
    `conda activate` responde `CondaError: Run 'conda init' before 'conda activate'`. La guarda
    `if [ -z "$BASH_VERSION" ]; then exec bash "$0" "$@"; fi` va **antes de cualquier sintaxis de
    bash** y tiene que ser POSIX puro. `run_all.sh` y `run_pipeline.sh` la llevan.
12. **El lote lee `temas.csv` por el descriptor 9, nunca por stdin.** Si el `while read` toma la
    lista por stdin, cualquier proceso hijo que lea de ahí se **come bytes de la lista de temas**.
    `ffmpeg` lo hace: sondea stdin buscando teclas interactivas (`q` para abortar). En un lote real
    esto mutiló casi todos los `PROYECTO` — `Historia02`→`a02`, `Historia04`→`04`,
    `Historia07`→`oria07` — y con ellos los nombres de video, respaldo y log. El síntoma engaña:
    parece que alguien editó el CSV a mitad de corrida. Tres defensas, todas puestas:
    `done 9< <(tail ...)` con `read <&9`, `run_pipeline.sh </dev/null`, y **`-nostdin` en las dos
    llamadas a ffmpeg** (pasos 03 y 08). Si agregas otra llamada a ffmpeg, ponle `-nostdin`.
9. `publisher.py` está incompleto respecto al resto: necesita `META_ACCESS_TOKEN`, `FACEBOOK_PAGE_ID`,
   `INSTAGRAM_ACCOUNT_ID` y `THREADS_USER_ID` (no están en `.env`) y apunta a una carpeta `post_images/`
   que no existe. La publicación hoy es manual.
10. Cada tema cuesta dinero real: ~10 llamadas a GPT-4.1, 1 síntesis de ElevenLabs y 8 imágenes de
    fal.ai a 832×1472 (fal cobra por megapíxel: subir la resolución sube el costo proporcionalmente).
    `estado.py` lleva la cuenta en `.costo_actual.json` y los pasos 02 y 04 la imprimen al terminar.
    **No corras `run_all.sh` para probar un cambio** — usa un solo tema.

## Al hacer cambios

- Prueba con un tema aislado (`PROYECTO=Test01 TEMA="..." bash run_pipeline.sh`) antes del lote.
- Para iterar solo en el video sin regenerar guion, voz e imágenes, corre `python 07_video_generator.py`
  directamente con `TITULO_VIDEO` y `PROYECTO` exportados: reusa `images_IA/` y `voice.mp3` existentes.
- El paso 07 con Whisper `medium` es lento (minutos). Para pruebas rápidas de layout, baja
  `whisper_model` a `"tiny"` o descomenta el `final.subclip(0, 3)` de la línea 663.
- Los logs por tema quedan en `logs/`; los temas que fallan se acumulan en `logs/failed.csv` con el mismo
  formato de `temas.csv`, así que ese archivo se puede reusar directo como entrada para reintentar.
