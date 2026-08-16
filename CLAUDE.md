# CLAUDE.md

Guía del proyecto para Claude Code. Escrita en español porque el proyecto, los prompts y los scripts están en español.

## Qué es este proyecto

Fábrica automatizada de contenido histórico viral para redes sociales. A partir de una lista de temas
(`temas.csv`) genera, por cada tema y de punta a punta:

- un guion de **65-75 palabras** (`gpt-5.4`) auditado por `claude-opus-5`, que **aborta el tema**
  si no lo aprueba,
- narración en voz (ElevenLabs), acelerada ×1.10,
- **6 imágenes** ilustradas por IA (fal.ai / Flux dev),
- un video vertical 9:16 con subtítulos animados palabra por palabra + música a −14 LUFS,
- `descripcion.txt`: título de YouTube, pie del reel, hashtags, descripción larga, tags y comentario,
- un carrusel de Instagram (imágenes reales de Wikimedia/DuckDuckGo + texto quemado).

La cuenta destino es `@chistoricas3` (la marca de agua está hardcodeada en el generador de carrusel).

**Es un repositorio git** (inicializado en agosto 2026, historial completo desde el estado que tenía
el pipeline antes de la auditoría). `.gitignore` excluye el `.env`, las salidas pesadas (`videos/`,
`videos_no_music/`, `proyectos/`, `music/`) y el estado del tema en curso. Hay `requirements.txt`
(con `moviepy==1.0.3` fijado). El pipeline se corre a mano desde bash; lo que **sí** tiene tests es
`herramientas/` (`python -m unittest discover tests`, ver [§ Tests](#tests)).

### Las cuatro notas, y para qué sirve cada una

| Nota | Responde a | Cuándo se lee |
|---|---|---|
| **[README.md](README.md)** | ¿Cómo se opera? El paso a paso de la semana: elegir temas, generar, empaquetar, programar en Metricool, recoger métricas | Cada semana, al usar el pipeline |
| **CLAUDE.md** (este) | ¿Cómo está hecho? Arquitectura, contratos entre pasos, mapa del repositorio y trampas | Antes de tocar código |
| **[TODO.md](TODO.md)** | ¿Qué queda por hacer? Solo pendientes vivos, con prioridad | Al decidir en qué trabajar |
| **[HISTORIAL.md](HISTORIAL.md)** | ¿Por qué está esto así? La auditoría de 18 bugs, las 5 fases y todo lo medido | Antes de "arreglar" algo que parece arbitrario |

⚠️ **Si un valor del código parece caprichoso, está explicado en HISTORIAL.md** — el `−14 LUFS`, el
`to_mask(canal=3)`, los 65-75 palabras, el `atempo=1.10`, el recorte del 8 % del borde. Ninguno es
una preferencia: todos salen de un fallo medido.

(**[INSTRUCCIONES_CHATGPT.md](INSTRUCCIONES_CHATGPT.md)** no es documentación del proyecto: es el
prompt que se le pega a ChatGPT para que proponga temas.)

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
PROYECTO=Prueba01 TEMA="Pelé" python pipeline/01_script_generator.py
```

⚠️ **Siempre desde la raíz del proyecto, nunca desde `pipeline/`.** Los scripts viven en
`pipeline/` pero todas sus rutas de datos (`script.txt`, `images_IA/`, `videos/`…) son relativas
al directorio de trabajo, y ese tiene que ser la raíz. `cd pipeline && python 07_…` escribiría el
video dentro de `pipeline/videos/`.

Los scripts tienen celdas `#%%` — están pensados también para ejecución interactiva en VS Code.
⚠️ En ese modo, los 6 pasos que importan `estado` necesitan que `pipeline/` esté en el path;
ejecuta esto una vez en la sesión interactiva antes de la primera celda:

```python
import sys; sys.path.insert(0, "pipeline")
```

(Ejecutando el archivo entero con `python pipeline/0N_….py` no hace falta: Python pone en
`sys.path` el directorio **del script**.)

## Arquitectura del pipeline

`run_all.sh` lee `temas.csv` → por cada fila escribe `PROYECTO`/`TEMA` en `.env`, los exporta y llama a
`run_pipeline.sh`, que corre los 8 pasos en orden con `set -e` (cualquier fallo aborta el tema).
Cada paso es un proceso Python independiente que se comunica con los demás **solo a través de archivos
en la raíz del proyecto**.

**Único módulo compartido: [estado.py](pipeline/estado.py).** No es un paso del pipeline, es una biblioteca:
- `sellar_estado()` / `verificar_estado()` — el paso 01 escribe `.estado_actual` con el `PROYECTO` en
  curso y los pasos 02, 03, 04 y 07 abortan si los archivos de la raíz son de otro tema. Sin esto, un
  fallo a mitad del pipeline dejaba que los pasos siguientes trabajaran con los datos del tema anterior.
- `registrar_openai()` / `registrar_imagen_fal()` / `registrar_elevenlabs()` / `resumen_costo()` —
  contador de costo por tema en `.costo_actual.json`.
- `con_reintentos()` — backoff exponencial para las llamadas de API.

| Paso | Script | Entrada | Salida | Servicio |
|---|---|---|---|---|
| 01 | [01_script_generator.py](pipeline/01_script_generator.py) | `$TEMA` | `script.txt`, `.estado_actual` | OpenAI `gpt-5.4` + Anthropic `claude-opus-5` |
| 02 | [02_social_media_generator.py](pipeline/02_social_media_generator.py) | `script.txt` | `social_posts/descripcion.txt` + insumos internos, `TITULO_VIDEO` en `.env` | OpenAI `gpt-4.1` |
| 03 | [03_voice_generator.py](pipeline/03_voice_generator.py) | `script.txt` | `voice.mp3` (acelerado ×1.10) | ElevenLabs `eleven_multilingual_v2` + ffmpeg |
| 04 | [04_image_generator.py](pipeline/04_image_generator.py) | `script.txt` | `images_IA/scene_0..5.png` | OpenAI + fal.ai `fal-ai/flux/dev` |
| 05 | [05_download_images.py](pipeline/05_download_images.py) | `social_posts/images_to_download.txt` | `source_images/img_N.jpg` | Wikimedia Commons → DuckDuckGo |
| 06 | [06_carrusel_generator.py](pipeline/06_carrusel_generator.py) | `social_posts/carrusel.txt` + `source_images/` | `carousel_slides/slide_NN_*.jpg` | Pillow (local) |
| 07 | [07_video_generator.py](pipeline/07_video_generator.py) | `images_IA/` + `source_images/` + `voice.mp3` | `videos_no_music/video_$PROYECTO.mp4` + `.srt` | faster-whisper + moviepy (local) |
| 08 | [08_music_mixer.py](pipeline/08_music_mixer.py) | video sin música + `music/` | `videos/video_$PROYECTO.mp4` | **ffmpeg** (local) |

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

  Si no pasa, **reescribe pasándole los fallos concretos** hasta `intentos_max` (3).

  ⚠️ **Si ninguno pasa, el tema se ABORTA** (`abortar_si_ninguno_pasa: True`, desde el 15 ago), y
  eso convierte a `cumple_la_puerta()` en el filtro de publicación, no solo en el freno de los
  reintentos. El motivo es de operación, no de código: **el flujo es automático y nadie lee los
  guiones antes de programarlos**, así que la alternativa —usar el mejor con un aviso ruidoso— es
  publicar el aviso junto al video. `Historia09` habría salido diciendo *"lujo romano"* de una
  carga que era griega.
  No corta el lote: `run_pipeline.sh` aborta **ese** tema, `run_all.sh` lo anota en
  `logs/failed.csv` —que se reusa tal cual como `temas.csv`— y sigue con el siguiente; `--solo`
  hace que el paso 09 empaquete únicamente los que terminaron. Y aborta en el **paso 01**, el
  primero: se tiran ~$0.09 de control de calidad, no los $0.18 de imágenes ni la voz.
  Simulado sobre `Historia09`-`Historia15`: **5 videos y 2 a `failed.csv`**, que son justo los dos
  con afirmaciones falsas.

  **Aprendizaje entre temas** (`lecciones_de_guiones_previos()`): destila los
  `proyectos/*/calidad_guion.json` acumulados en ~200 tokens que se inyectan **solo en el primer
  intento** (en una reescritura ya hay feedback específico, que vale más y no conviene diluir).
  ⚠️ **Lleva frecuencias y ejemplos POSITIVOS, nunca las frases rechazadas.** Un ejemplo concreto
  es la señal más fuerte de un prompt —el modelo imita tono, longitud y estructura—, así que
  enseñarle "no escribas *como si pescaran sardinas*" es enseñarle a escribir símiles. Y el prompt
  **ya prohíbe** en prosa casi todo lo que el crítico objeta: lo que faltaba no eran más reglas
  sino saber **cuáles de las suyas rompe más**, con la cuenta al lado.
  El guion se guarda dentro de `calidad_guion.json` porque `script.txt` vive en la raíz y lo pisa
  el tema siguiente — sin eso los guiones **aprobados** se perdían, que son la mitad útil.
  `ABSOLUTOS`, `SIMILES` y `VERBOS_MENTE` en `verificar_reglas_mecanicas()` salen de los mismos
  datos y cuestan **cero**: cazan en Python lo que el crítico cobraría por señalar. Van como
  **leves**, no graves — "nunca robó a los ricos" estaba en el único guion aprobado.

  ⚠️ **La puerta está calibrada con datos reales (Historia09-15, 15 ago): `nota >= 6` y
  `dudosas <= 3`.** No la muevas a ojo — la distribución medida sobre esos 7 temas fue
  `nota 5,6,6,6,6,7,8` y `dudosas 0,2,2,3,3,4,4`, y de ahí salen dos cosas que no son obvias:

  **1. `nota_minima` no filtra nada.** Cinco de siete empatan en 6; con `dudosas <= 3` salen los
  mismos aprobados se mire la nota o no. Se deja como suelo barato, pero **quien decide es
  `dudosas_max`**. Afinar la nota es perder el tiempo.

  **2. `dudosas_max` vale 3 y no 2 porque el crítico tiene sesgo al rechazo por diseño** —
  `SYSTEM_CRITICO` le ordena literalmente *"ante la duda, marca la afirmación como dudosa"*. A 2 se
  caían `Historia12` y `Historia15`, cuyas dudosas son **datos documentados** (la panadería de
  Modestus con sus 81 panes carbonizados; las colonias militares agrícolas Ming). Los que fallan de
  verdad traen 4: `Historia09` decía *"lujo romano"* de una carga que era griega. Con 3 aprueban
  5 de 7 y ninguno de los dos falsos pasa.

  ⚠️ **Historial, para que nadie repita el diagnóstico:** con `gpt-4.1` escribiendo, Opus comprimía
  todas las notas entre **2 y 3** y encontraba dudosas en todos, así que la puerta original
  (`nota >= 7` + cero dudosas) **no aprobaba nunca**. Parecía un umbral mal puesto y era el
  guionista: al cambiar a `gpt-5.4` el rango subió a 5-8 sin tocar el umbral. Por eso `nota_final`
  resta `0.1 × dudosas` como desempate — cuando las notas empatan, las dudosas son lo único que
  discrimina.
  Costo real medido: **~$0.029 por crítica a `effort: "low"`** (vs $0.040 a `medium`, misma nota).

  **El guionista es `gpt-5.4`, y la elección está medida.** Sobre el mismo tema, juzgados por el
  crítico de Opus 5: `gpt-4.1` 2/10 con 6 dudosas ($0.0026); `claude-opus-5` escribiendo 5/10 con 4
  ($0.0123, y pierde la independencia de proveedor); **`gpt-5.4` 6/10 con 2 ($0.0040)** — gana a los
  dos por $0.0014 más y mantiene OpenAI-escribe / Anthropic-critica.
  ⚠️ **`gpt-5.5` no**: razona antes de responder y esos tokens se facturan como **salida**. Medido,
  2560 tokens de razonamiento para un guion de 70 palabras: **$0.085, 33× `gpt-4.1`**, más caro que
  escribirlo con Opus, y 35 s en vez de 2. Es la misma trampa que el thinking de Opus.
  Los pasos 02, 04 y 05 siguen en `gpt-4.1` a propósito: son extracción mecánica (queries, contexto,
  validación visual), no criterio.
  ⚠️ **Antes de cambiar de modelo en cualquier paso, añádelo a `PRECIOS_OPENAI` en
  [estado.py](pipeline/estado.py).** `registrar_openai()` hace `if not precio: return`, así que un
  modelo desconocido **no se cobra y el contador miente en silencio**.
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

  **`LIMITE_TITULO = 70`** funciona igual, pero al revés de lo que uno esperaría: aquí **sí** se
  vuelve a llamar al modelo. `acortar_titulo()` le pide que reescriba (hasta 2 intentos, el segundo
  diciéndole cuánto se pasó) y solo si aun así no cabe trunca con `_truncar_titulo()`. Es que un
  título recortado a machete pierde el gancho, que es justo lo que hace que lo cliqueen; reescribir
  es lo único que lo conserva. **Python sigue siendo el que garantiza el límite.**
  Solo cuesta cuando hace falta: si el título ya cabe, no llama a nada. Medido sobre los 8 primeros
  temas, se pasaban 4 (entre 1 y 12 caracteres).
  ⚠️ **Se acorta en `guardar_descripciones()`, no al escribir el archivo.** El título sale por dos
  caminos —`descripcion.txt` y `metadata.json`— y acortarlo solo en uno dejaba el mismo video con
  dos títulos distintos según dónde miraras. El paso 09 lee el de `metadata.json` y el paso 10
  empareja métricas por ese texto.

  El resto de `social_posts/` son **insumos internos, no textos para copiar y pegar**:
  `carrusel.txt` (paso 06), `images_to_download.txt` (paso 05, formato `img_N.jpg → query`),
  `00_investigacion.txt` y `metadata.json` (de ahí saca el paso 09 el título sin parsear prosa).
  ⚠️ El formato de `carrusel.txt` (párrafos separados por línea en blanco, sin etiquetas "Slide N")
  es un contrato con el paso 06: si cambia el prompt, se rompe el parseo del carrusel. **`generate_title()` NO resume el guion**: genera un gancho que abre la pregunta
  sin responderla (un resumen equivale al spoiler, y ese texto va quemado en el frame 0 del video).
  ⚠️ **`save_to_env()` pasa el título por `sanear_valor_env()` antes de escribirlo, y no es
  opcional.** `run_pipeline.sh` hace `source .env`: ese archivo lo lee **bash**, y el título lo
  escribe un LLM. Un salto de línea partía la entrada en varias líneas del `.env`; como el bucle de
  `save_to_env()` solo reemplaza la **primera** que empieza por `TITULO_VIDEO=`, las demás quedaban
  sueltas y bash intentaba ejecutarlas como comandos (con `set -e`, abortando el pipeline). Pasó de
  verdad con `Historia07`. Por eso se quitan también `"`, `$`, `` ` `` y `\`: dentro de comillas
  dobles, un título con `$(...)` se **ejecutaría**. Ninguno de esos caracteres tiene sentido en un
  texto que va quemado en el frame 0, así que se eliminan en vez de escaparse.
- **03** — `voice_id = "l1zE9xgNpUTaQCZzpNJa"` hardcodeado. **Aborta con código != 0 si ElevenLabs
  falla**: si no, los pasos siguientes usarían el `voice.mp3` del tema anterior. Después acelera el
  audio con `atempo=VELOCIDAD` (1.10) porque ElevenLabs entrega ~143 palabras/minuto y la narración
  que retiene va a 170-190. El resto del archivo (Google TTS) está comentado.
  `desuso/03_voice_generator_free.py` es una alternativa con OpenAI TTS (`tts-1-hd`, voz `onyx`) y un modo
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
  (⚠ posibles derechos de autor). Cada imagen se recorta a 1080×1080 sobrescribiendo el original.
  Vacía `source_images/` (jpg, jpeg, png, webp) antes de descargar.
  ⚠️ **La espera está separada por fuente y no es lo mismo una que otra** (P-19, 15 ago):
  `DELAY_WIKIMEDIA = 1.5` y `DELAY_DDG = 7.0`. Wikimedia es una API pública documentada —lo que
  pide su política es identificarse (el `User-Agent` lleva contacto) y no paralelizar, no ir
  lento— y además `search_commons()` / `get_image_url()` ya reintentan con backoff de 10/20/30 s
  ante un 429, así que si se queja el paso se frena solo. DuckDuckGo es scraping tolerado y es el
  que bloquea de verdad: ahí siguen los 7 s.
  ⚠️ **La pausa del final del bucle es entre IMÁGENES, no de DuckDuckGo**, y corre se haya usado
  DDG o no — era donde más tiempo se perdía. Por eso mira `uso_ddg` para elegir cuál aplicar.
  Medido sobre los 7 temas de agosto (26 esperas de Wikimedia y 6 imágenes de media): el paso
  pasa de **3.7 a 1.0 minutos dormido**, o sea **−2.7 min por tema y −19 min por lote de 7**.
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
  - **`dispersar_planos()` decide el ORDEN**, y es lo que hace que esos cortes se noten. Antes la
    secuencia era `A1 A2 B1 B2`: dos encuadres seguidos de la misma imagen, que el ojo lee como
    zoom y no como corte. Medido sobre un reparto real, **8 de 13 transiciones eran la misma
    imagen; ahora son 0**. Cuesta cero: no genera más imágenes.
    ⚠️ **No baraja, intercala dentro de una ventana** (`ventana_dispersion`, 2). Las imágenes
    vienen en orden narrativo del paso 04 —la 1 ilustra la primera frase y la última el
    desenlace—, así que un barajado global pondría el final en el segundo 3. Con 2, una imagen se
    adelanta o atrasa un plano (~1.8s). Subirlo a 3 lleva el desfase a ~4s.
    El primer plano del video es **siempre** la imagen 1: el voraz abriría por la segunda si
    esa tiene más planos, y el frame 0 es el que lleva el título. Se apaga con
    `dispersar_planos: False`, que restaura el orden clásico — útil para comparar (P-12).
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

## Mapa del repositorio

Todo vive en un solo nivel, pero **hay cuatro ciclos de vida distintos mezclados** en la raíz.
Distinguirlos es lo que hace entendible el proyecto; el orden en que están escritos en disco, no:

1. **Código** — se edita, está en git.
2. **Entradas** — las pones tú (claves, temas, música, fuentes).
3. **Estado del tema EN CURSO** — se sobrescribe en cada tema; **solo existe el último**.
4. **Salidas y archivo** — se acumulan para siempre; nada está en git (pesan 1.6 GB).

### 1 · Código

| | Qué es |
|---|---|
El código está repartido en tres carpetas según **quién lo ejecuta**, que es lo único que hace
falta saber para orientarse:

| | Qué es |
|---|---|
| `run_all.sh` | El lote, en la raíz. Lee `temas.csv`, escribe `PROYECTO`/`TEMA` en `.env`, llama a `run_pipeline.sh` por tema y al terminar empaqueta con el paso 09 |
| `run_pipeline.sh` | Un tema, en la raíz: los 8 pasos en orden con `set -e` |
| **`pipeline/01…08_*.py`** | Los 8 pasos, **lo único que corre `run_pipeline.sh`**. Ninguno importa a otro: se comunican solo por archivos |
| **`pipeline/`**[`estado.py`](pipeline/estado.py) | La **única** biblioteca compartida: sello del tema, contador de costo, reintentos. Vive con los pasos porque Python pone en `sys.path` el directorio del script, no el de trabajo |
| **`herramientas/`**[`09_paquete_publicacion.py`](herramientas/09_paquete_publicacion.py) | Se corre una vez por lote, no por tema (lo llama `run_all.sh` al final) |
| **`herramientas/`**[`10_metricas.py`](herramientas/10_metricas.py) | Se corre cuando hay exports nuevos. No lo llama nadie automáticamente |
| **`herramientas/`**[`11_reporte.py`](herramientas/11_reporte.py) | Convierte `metricas.csv` en `reportes/ultimo.html`. Se corre después del 10 |
| **`herramientas/`**[`12_recordatorio.py`](herramientas/12_recordatorio.py) | Recordatorio semanal por Telegram. Lo llama `cron`, no un `.sh` |
| **`herramientas/`**[`13_youtube_api.py`](herramientas/13_youtube_api.py) | Métricas de YouTube por API (OAuth). La **curva de retención** no la exporta ningún CSV |
| **`herramientas/`**[`14_meta_api.py`](herramientas/14_meta_api.py) | Instagram y Facebook por API: métricas hoy, publicación (P-10) después |
| **`desuso/`** | Código que **no ejecuta nadie**: `03_voice_generator_free.py`, `publisher.py`, `ink_filter.py`, `imagen_generator_source.py`. Sigue en git como referencia. Ver [§ Código en desuso](#código-en-desuso-está-en-git-no-lo-ejecuta-nadie) |
| `requirements.txt` | `moviepy==1.0.3` fijado; ffmpeg va aparte (apt) |

⚠️ **La carpeta manda sobre el número.** `01`–`08` son el orden dentro de `pipeline/`; `09` y `10`
conservan su número por historia, pero al estar en `herramientas/` no son pasos y no entran en
`run_pipeline.sh`. Y `desuso/03_voice_generator_free.py` lleva un `03` que no significa nada.

⚠️ **Todo se ejecuta desde la raíz**, aunque el `.py` viva en `pipeline/`. Las rutas de datos son
relativas al directorio de trabajo; el movimiento de carpetas no cambió ni una.

### 2 · Entradas

| | Git | Qué es |
|---|:--:|---|
| `.env` | ❌ | Claves **y** estado mutable (`PROYECTO`, `TEMA`, `TITULO_VIDEO`). Nunca se commitea |
| `.env.example` | ✅ | Plantilla del anterior |
| `temas.csv` | ✅ | Entrada del lote: `PROYECTO,TEMA`, con encabezado y 2 campos exactos |
| `fonts/` | ✅ | BungeeSpice (subtítulos y carrusel), Cossette_Texte |
| `perfil/` | ✅ | Imagen de perfil y banner para el slide CTA del carrusel |
| `music/` | ❌ | mp3 royalty-free de fondo (45 MB, ignorada) |
| `metricas_export/*.csv`, `*.zip` | ❌ | Los exports que descargas de cada red, **tal cual vienen** |
| `metricas_export/manual.csv`, `mapa_manual.csv` | ❌ | Lo que tecleas a mano. **Irrecuperables**: el paso 10 nunca los borra |

### 3 · Estado del tema EN CURSO

Se sobrescribe en cada tema y **nada de esto está en git**. Si el pipeline aborta a mitad, aquí
queda el tema anterior — de ahí el sello de `estado.py` (trampa 1).

| | Lo escribe | Lo lee |
|---|---|---|
| `script.txt` | 01 | 02, 03, 04 |
| `voice.mp3` | 03 | 07 |
| `social_posts/` | 02 | 05 (`images_to_download.txt`), 06 (`carrusel.txt`), 09 (`descripcion.txt`, `metadata.json`) |
| `images_IA/` | 04 | 07 |
| `source_images/` | 05 | 06, 07 |
| `carousel_slides/` | 06 | 09 |
| `.estado_actual` | 01 | 02, 03, 04, 07 |
| `.costo_actual.json` | 01 (reinicia), 01-05 (suman) | 02, 04 (lo imprimen) |
| `.cache_fotos_reales/` | 07 | 07 |

### 4 · Salidas y archivo

| | Qué es |
|---|---|
| `videos_no_music/video_$PROYECTO.mp4` | Intermedio del paso 07. **No se borra nunca**: hoy son ~700 MB (P-07) |
| `videos/video_$PROYECTO.mp4` | **El entregable.** Lo escribe el paso 08 |
| `proyectos/$PROYECTO/` | Respaldo permanente por tema: mp3, srt, `calidad_guion.json`, `images_IA/`, `source_images/`, `social_posts/`, `carousel_slides/` |
| `publicar/$PROYECTO/` | Paquete listo para programar (video por hardlink + srt + `descripcion.txt` + carrusel) + `calendario.csv` |
| `logs/` | `{PROYECTO}_{TEMA}.log` por tema + `failed.csv`, que sirve tal cual como `temas.csv` |
| `metricas.csv` | ✅ **en git.** Una fila por `(id_plataforma, plataforma, fecha_snapshot)` |
| `metricas_export/_normalizado/`, `_procesados/` | Trabajo interno del paso 10: los 5 formatos ya uniformados, y los crudos ya consumidos |

**`T1/` es el archivo de la tanda anterior al pipeline.** Aparece dentro de `videos/`,
`videos_no_music/` y `proyectos/` con la misma forma: 22-27 temas viejos (Messi01, Tupac01,
Venecia01, Douglas_Bader…). No es basura — **son el `baseline` con el que se compara todo en
`metricas.csv`**. ⚠️ Pero al estar un nivel más abajo, `proyectos/T1/<TEMA>/social_posts` queda
fuera del glob del paso 10 y esos videos no emparejan solos (P-14 en TODO.md).

### `PROYECTO` no es `TEMA`

Se confunden todo el tiempo y no son lo mismo:

- **`PROYECTO`** (`Historia04`) es el **identificador**: da nombre al video, a la carpeta de
  respaldo, al log y a la carpeta de `publicar/`. Sin espacios ni acentos.
- **`TEMA`** (`Robin Hood`) es **el asunto del guion**: solo lo usan el paso 01 (para escribir) y
  el nombre del log.

Todo lo que se nombra en disco usa `PROYECTO`. En el código del paso 09 la variable se llama
`tema` pero contiene el `PROYECTO` — no te fíes del nombre de la variable, mira de dónde sale
(`videos/video_*.mp4`).

**[09_paquete_publicacion.py](herramientas/09_paquete_publicacion.py)** no es un paso por tema: **`run_all.sh` lo
llama UNA vez al final**, pasándole con `--solo` los `PROYECTO` que terminaron (sin eso empaquetaría
también los lotes viejos). Junta en `publicar/<PROYECTO>/` el video (con hardlink, cero espacio
extra), el `.srt`, `descripcion.txt` y el carrusel, y escribe `publicar/calendario.csv` con
las fechas repartidas. Marca los temas incompletos y los guiones que **no** pasaron el control de
calidad del paso 01 (que deja su veredicto en `proyectos/$PROYECTO/calidad_guion.json`).
Acepta `descripcion_general.txt` + `descripcion_detallada.txt` como alternativa (`textos_legado`)
para no marcar como incompletos los respaldos anteriores a la fusión, y **borra los dos formatos del
destino antes de copiar**, para que rehacer un paquete no deje el archivo viejo al lado del nuevo.
Sin `--solo` empaqueta **todo** lo que haya en `videos/`, incluidos los lotes viejos.

**[10_metricas.py](herramientas/10_metricas.py)** tampoco es un paso del pipeline: consolida en `metricas.csv`
los exports de YouTube, TikTok, Instagram y Facebook **tal cual se descargan** (zips sin
descomprimir incluidos) y que se dejan en `metricas_export/` con el nombre empezando por la
plataforma. Ver **[README.md](README.md)** (bloque 5) para de dónde sale cada uno y qué métrica
trae cada red.
- **Normaliza primero, empareja después**: descomprime, elige el csv bueno de cada zip y escribe un
  csv por plataforma con columnas uniformes en `metricas_export/_normalizado/`.
- **El mapeo de columnas es explícito** (`FUENTES`), con los nombres reales en español de esta
  cuenta. No hay adivinanza: si cambia el idioma o Meta/Google renombran algo, se toca ahí.
- **Empareja por texto** contra `metadata.json`, `descripcion.txt` y **los legados
  `04_facebook.txt` / `03_instagram.txt`** — sin estos, los 16 Mundial no emparejarían ninguno,
  porque son anteriores a `metadata.json`. Combina solapamiento de palabras (salva los títulos
  cortos: "Memo Ochoa al PSG" → Mundial16) con similitud de secuencia (captions largos).
- ⚠️ **La asignación es uno-a-uno** (`asignar_uno_a_uno()`). Sin exclusividad, "Árbitro polémico",
  "Árbitro de mundial" y "La mano de Dios" caían los tres en `Mundial01` y el último pisaba a los
  otros dos en silencio, porque `metricas.csv` se indexa por `(PROYECTO, plataforma, fecha)`.
- ⚠️ **`CAMPOS_DECIMALES` no es un detalle**: Facebook exporta los segundos medios vistos como
  `9.378`, y la regla genérica de "3 dígitos detrás = separador de miles" lo leía como 9378,
  dando retenciones del 17.000 %. El tipo se decide por campo, no por heurística.
- **Facebook son DOS archivos** que se fusionan por `Identificador de la publicación`: el de Meta
  Business trae el título generado (empareja perfecto) y el alcance; el de Facebook trae guardados,
  impresiones y seguimientos netos. Hay que descargar los dos.
- Lo que no empareja se acumula en `metricas_export/mapa_manual.csv` con `PROYECTO` vacío: se
  rellena una vez y el script lo respeta siempre.
- **`lote`** es la única columna con la que se compara. Sale de los `PROYECTO` de `temas.csv` más
  `lote_nuevo_extra`; todo lo demás es `baseline`.
  ⚠️ **Es pegajoso, y tiene que serlo** (`lotes_ya_asignados()`): `temas.csv` cambia cada semana,
  así que recalcularlo sin más **degrada la tanda anterior a `baseline` en silencio**. Pasó el
  15 ago: al cargar `Historia09`-`Historia15`, los `Historia01`-`Historia08` cayeron de 23 filas de
  `v2-mas-cortes` a 4 y el informe pasó de comparar n=6 vs 34 a **n=1 vs 44** sin decir nada. La
  regla es asimétrica: **nunca degrada** un lote con nombre, pero **sí promueve** desde `baseline`
  (un video que entró sin emparejar y luego reconoce su `PROYECTO` sube a su lote de verdad).
  Un video pertenece a la tanda que lo produjo, no a la que esté cargada hoy.
  ⚠️ **Sube `lote_nuevo` en el `CONFIG` al cargar un `temas.csv` con cambios de pipeline detrás**,
  o dos tandas distintas comparten nombre y dejan de distinguirse. Hoy:
  `v2-mas-cortes` (Historia01-08) y `v3-guion-y-dispersion` (Historia09-15).
- ⚠️ **Entran TODOS los videos publicados, con `PROYECTO` reconocido o sin él.** Los anteriores al
  pipeline casi nunca emparejan —su respaldo está en `proyectos/T1/<TEMA>/`, un nivel por debajo
  del glob `proyectos/*/social_posts` (P-14)— pero son el baseline: descartarlos dejaba la
  referencia en 7 videos en vez de 34. Por eso la clave de fusión es **`id_plataforma`** (el id
  nativo de cada red), no el `PROYECTO` — con `PROYECTO` como clave todos los desconocidos habrían
  colisionado en la misma fila vacía.
- **`ventanas_youtube()`** saca `vistas_24h` y `vistas_7d` del tercer csv del zip ("Datos del
  gráfico", una fila por video y día) sumando desde la publicación — sin esperar al snapshot de la
  semana siguiente. ⚠️ Solo cubre los videos dibujados en la gráfica al exportar, y YouTube limita
  cuántos se marcan a la vez: el histórico se baja **en varias tandas** (`youtube_tanda1.zip`…).
  Por eso **cada zip se descomprime en su propia subcarpeta** — los tres csv se llaman igual en
  todas las tandas y con una carpeta por plataforma la última pisaba a las anteriores.
- **La duración del video se presta entre plataformas** cuando comparten `PROYECTO`: el export de
  TikTok no la trae, así que sin esto su retención no se podía calcular. Es el mismo mp4 en las
  cuatro redes.
- `normalizar_porcentaje()` convierte los porcentajes tecleados como fracción (`0.21` → `21`) y
  **avisa de cada conversión**: mezclar las dos formas en la misma columna la deja inservible.
- **`metricas_export/manual.csv`** recoge lo que ningún export trae, y `CAMPOS_MANUALES` dice qué
  pedir **por plataforma** (TikTok: alcance, segundos medios, % que vio completo · Instagram:
  segundos medios · YouTube y Facebook: nada). ⚠️ Es el **almacén** de esos números, no una lista
  de tareas: las filas ya rellenadas se conservan aunque estén completas, porque borrarlas perdería
  el dato. Las celdas con `—` son las que esa red sí exporta.
- `calcular_retencion()` deriva `retencion_pct` de los segundos medios y la duración, y **se llama
  otra vez después de fusionar lo manual**, para que teclear los segundos baste.
- ⚠️ **TikTok exporta los caption sin escapar las comillas internas.** Una fila que cite algo
  ("Living With Michael Jackson") sale con 15 campos en vez de 8 y todas las métricas corridas.
  `leer_csv()` la rehace apoyándose en que la URL del video marca dónde vuelve a alinearse.
- **Limpia solo tras consolidar**: los exports crudos se **mueven** a `_procesados/<fecha>/`.
  ⚠️ No es orden, es correctitud: si se quedan en `metricas_export/`, la corrida siguiente los
  relee y los sella con la `fecha_snapshot` nueva, afirmando que los números viejos son los de hoy.
  `protegidos` (`manual.csv`, `mapa_manual.csv`) **no se tocan jamás** — son irrecuperables. Lo
  único que se borra de verdad es `_crudo/`, que se regenera desde los zip.
- **Sin descargas nuevas, `origen_y_fecha()` reprocesa la tanda archivada más reciente con SU
  fecha**, no con la de hoy. Es el caso de teclear más datos en `manual.csv` y volver a correr:
  así es idempotente (tres corridas seguidas dejan `metricas.csv` idéntico) en vez de crear una
  foto nueva con números viejos.
- `fecha_snapshot`: un export trae vistas ACUMULADAS, así que los deltas de 24 h y 7 d salen de
  restar dos fotos. Fusiona por `(plataforma, id_plataforma, fecha_snapshot)` y nunca pisa un valor
  lleno con uno vacío.

**[11_reporte.py](herramientas/11_reporte.py)** lee `metricas.csv` y escribe un HTML autocontenido
en `reportes/` (fechado + `ultimo.html`, nombre fijo para adjuntarlo sin adivinar). Solo stdlib y
CSS incrustado. `reportes/` está en `.gitignore`: es derivado y `metricas.csv`, que sí está en git,
guarda todas las fotos.
- **`COLUMNAS_POR_PLATAFORMA` es explícito**, igual que `FUENTES` en el paso 10: cada red muestra
  solo lo que exporta. TikTok no da `alcance`; ni YouTube ni TikTok dan `guardados`; `ctr_pct` es
  solo de YouTube. Una tabla común sería un mar de celdas vacías.
- ⚠️ **`TIPO_METRICA` es lo que hace que el informe no mienta, y no es cosmético.** Los videos del
  lote nuevo llevan **4 días** publicados y los del baseline **66**. Clasifica cada métrica en:
  `acumulativa` (crece mientras el video siga online → NO comparable con esas edades), `ventana`
  (`vistas_24h`, `vistas_7d`: la edad ya está igualada por construcción → sí), `tasa` (un cociente
  cuyas dos partes crecen juntas → sí) e `interna` (`retencion_relativa`, normalizada dentro de su
  propio lote → comparar daría 0 % siempre). `comparar_lotes()` aparta lo no comparable a un bloque
  "fuera del veredicto" en vez de esconderlo, para que nadie lo recalcule a mano.
- ⚠️ **`vistas_por_dia` es `acumulativa`, no `tasa`, y ese es el punto.** Parece que corrige la
  antigüedad y hace lo contrario: supone acumulación lineal, pero en video social casi todas las
  vistas llegan en las primeras 48 h. Dividir entre 4 días en vez de entre 66 **invierte** el sesgo
  y lo amplifica — daba «+5591 % en Instagram» sobre unos datos cuya diferencia real de vistas era
  3.4×. Sirve para ordenar videos de edad parecida, nunca para comparar lotes.
- Todo se compara **por mediana y con la n al lado** (`n_minimo_fiable`, 5). Con n=6, un promedio lo
  decide un solo video viral y una mediana sin la n invita a concluir de más.
- `retencion_pct` **puede pasar de 100 %** en YouTube (44 s de media sobre un video de 38 s): son
  los bucles de Shorts, no un error de cálculo. Por lo mismo, `audienceWatchRatio` de la curva de
  retención pasa de 1.0.
- ⚠️ **`se_quedaron_pct` y `retencion_pct` NO miden lo mismo y pueden moverse en sentidos
  opuestos sin que ninguna esté mal.** «Se quedaron para mirar» se normaliza sobre todos los que
  el Short **empezó a reproducirse en el feed** —incluye a quien deslizó en menos de un segundo—
  y `retencion_pct` sobre los que **se quedaron a verlo**. Medido el 15 ago: v2 sale −16 % en la
  primera y +32 % en la segunda. La lectura correcta es «para el scroll menos gente, pero la que
  para ve mucho más», no «una de las dos miente». Ver [P-12](TODO.md#p-12).

**[13_youtube_api.py](herramientas/13_youtube_api.py)** saca las métricas de YouTube por API.
- **Requiere OAuth, no una API key**, porque son datos privados del canal. Dos archivos, los dos
  secretos y los dos en `.gitignore`: `credenciales/client_secret*.json` (lo descargas de Google
  Cloud Console) y `credenciales/token_youtube.json` (lo escribe el flujo, se guarda con permisos
  `600` y **da acceso de lectura al canal hasta que se revoque**).
- ⚠️ **La app tiene que estar publicada "En producción" en la consola.** En estado *Prueba* Google
  caduca el refresh token a los **7 días**, o sea reautorizar cada semana — justo el trabajo manual
  que esto viene a quitar. El montaje completo está en [README.md](README.md).
- ⚠️ **`comprobar_canal()` no es un adorno: llámalo antes de fiarte de ningún número.** Si se
  autoriza con una cuenta que no es dueña de `@chistoricas3`, la API responde **200 con datos
  vacíos** en vez de dar error, y un informe de ceros parece un mal mes.
- **Lo que justifica el archivo es `curva_de_retencion()`** (`dimensions=elapsedVideoTimeRatio`):
  es el único dato que **ningún export masivo trae**, y el que responde a [P-12](TODO.md#p-12).
  `resumir_curva()` lo reduce a la pregunta real —¿se van en el gancho (0-10 % del video) o en el
  primer corte (10-25 %)?— porque las dos respuestas mandan a sitios opuestos: reescribir el texto
  del guion, o cambiar el ritmo del montaje.
  ⚠️ Un punto sin dato es `None`, **no cero**: contarlo como 0 hundiría la media y haría creer que
  el gancho falla. `relativeRetentionPerformance` puede venir vacío si el video tiene pocas vistas;
  no es un error.

**[12_recordatorio.py](herramientas/12_recordatorio.py)** es el recordatorio semanal por Telegram.
Lo llama `cron` (no `run_all.sh`: no tiene nada que ver con generar videos).
- **No es una alarma de calendario: mira el estado real del repo y por defecto calla si no hay nada
  que decir.** Sin avisos y sin `--siempre` no envía — un bot que escribe todos los lunes aunque no
  pase nada se acaba silenciando, y entonces tampoco avisa el día que importa.
- Todo lo que comprueba son archivos que ya existen: `logs/failed.csv`, los
  `proyectos/*/calidad_guion.json`, `publicar/calendario.csv`, la `fecha_snapshot` máxima de
  `metricas.csv` y si los `PROYECTO` de `temas.csv` ya tienen video. Ninguna API salvo la de enviar.
- **Importa `11_reporte.py` con `importlib` en vez de recalcular** (el nombre empieza por dígito, no
  se puede `import` normal). A propósito: el informe ya descarta lo no comparable, y un resumen que
  rehiciera las cuentas por su cuenta mandaría cada lunes un "+2493 % en vistas por día" que solo
  mide la antigüedad de los videos.
- Degrada sin romperse si faltan `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`: imprime y no envía,
  igual que el paso 01 sin `ANTHROPIC_API_KEY`. `--dry-run` nunca envía.
- **Tres entradas de cron, no tres mensajes**: domingo 10:00 y 16:00, y `--si-falta` de lunes a
  sábado. Esta última no hace nada si ya se envió algo esa semana; cubre el domingo con el equipo
  apagado, que si no se perdería sin más. La semana empieza el domingo (`dia_inicio_semana`, 6):
  **si mueves el cron a otro día, mueve eso con él** o la recuperación cuenta mal la semana.
- ⚠️ `anotar_envio()` se llama **solo cuando Telegram confirma**, no al intentarlo. Si se anotara
  antes, una caída de red el domingo marcaría la semana como avisada y la recuperación de los días
  siguientes no dispararía — justo el caso para el que existe. La marca es `.ultimo_recordatorio`
  (en `.gitignore`: es estado de esta máquina).
- ⚠️ Al fallar el envío **imprime solo `description`, nunca la URL**: el token va dentro de la ruta
  y esto corre bajo cron, cuya salida acaba en un log o en un correo.

### Código en desuso (está en git, no lo ejecuta nadie)

Cuatro archivos que **no forman parte de ningún flujo**. Ninguno se ejecuta desde `run_pipeline.sh`
ni desde `run_all.sh`, y todos referencian cosas que ya no existen:

| Archivo | Qué era | Por qué no funciona hoy |
|---|---|---|
| `desuso/03_voice_generator_free.py` | Voz con OpenAI TTS (`tts-1-hd`, voz `onyx`) + modo `--test-voices` | Alternativa nunca adoptada; la primera mitad del archivo es edge-tts comentado |
| `desuso/publisher.py` | Publicación automática a Meta/Threads | Le faltan 4 credenciales, apunta a `post_images/` (no existe) y lee `03_instagram.txt` / `04_facebook.txt`, que el paso 02 dejó de generar |
| `desuso/ink_filter.py` | Convertir fotos reales a tinta/pergamino en local, sin fal | Funciona, pero nadie lo llama: el paso 04 genera con fal |
| `desuso/imagen_generator_source.py` | Generador de imágenes con Leonardo | Leonardo se abandonó por fal.ai. Es quien escribía `images_IA_guidance/` |

Están todos en `desuso/` justamente para que no se confundan con código vivo. Si abres uno pensando
que forma parte del pipeline, no lo forma.

## Convenciones del código

- Todo en español: nombres de funciones en inglés a veces, pero prints, comentarios y prompts en español,
  con emojis como marcadores de estado (✅ ❌ 🎬 ⏱️).
- Cada script define un dict `CONFIG` al inicio con todos los parámetros ajustables y comentarios
  explicando los rangos. **Si agregas un parámetro, va en `CONFIG`, no disperso en el código.**
- **Las rutas de datos son relativas a la RAÍZ, no a la carpeta del script.** Los `.py` están en
  `pipeline/` y `herramientas/`, pero el directorio de trabajo siempre es
  `/home/juanb/video_generator` (los dos `.sh` hacen `cd` ahí). Un `open("script.txt")` dentro de
  `pipeline/04_…` abre el de la raíz, que es lo que se quiere.
- Cada script es standalone con `if __name__ == "__main__"` y `load_dotenv()` al inicio.
- Separadores visuales con `═` / `─` para dividir secciones dentro de un archivo.
- Los scripts tienen celdas `#%%`: se corren enteros desde bash y por partes desde VS Code.

**Dónde va un archivo nuevo**, para que la raíz no vuelva a llenarse:

| Si es… | Va como | Y además |
|---|---|---|
| Un paso más del pipeline | `pipeline/NN_nombre.py`, con el número siguiente | se agrega a `run_pipeline.sh` **en su posición** (`run_step NN_nombre.py`, sin la carpeta: la pone la función) y se documenta en la tabla de pasos de arriba |
| Una herramienta que se corre aparte | `herramientas/nombre.py` | se documenta como herramienta, **no** se mete en `run_pipeline.sh`. El número ya no hace falta: la carpeta dice lo que es |
| Lógica que necesitan varios pasos | dentro de [pipeline/estado.py](pipeline/estado.py) | es el único módulo importable de `pipeline/`: los pasos empiezan por dígito y no se pueden `import` |
| Un experimento | fuera del repositorio | si se queda y deja de usarse, a `desuso/` y a la tabla de código en desuso |
| Un test | `tests/test_<modulo>.py` | solo `unittest` de la stdlib; ver [§ Tests](#tests) |

<a id="tests"></a>
### Tests

```bash
python -m unittest discover tests      # desde la raíz, 98 tests, ~0.1 s
```

Solo `unittest` de la stdlib, sin dependencias nuevas y **sin red**. Cubren
[herramientas/10_metricas.py](herramientas/10_metricas.py),
[herramientas/11_reporte.py](herramientas/11_reporte.py),
[pipeline/estado.py](pipeline/estado.py) y las funciones puras de los pasos
**01**, **02** y **07** ([tests/test_pipeline.py](tests/test_pipeline.py)).

⚠️ **Los pasos trabajan al importarse, y aun así se prueban sin tocarlos.** Hacen `SystemExit` si
falta `PROYECTO`, instancian clientes de API y llaman a `verificar_estado()`. No hace falta mover
esas guardas a `main()`: `cargar_paso()` les prepara el entorno desde fuera y con eso basta —
`chdir` a un temporal (sin sello, `verificar_estado()` vuelve sin abortar y ningún `open()`
relativo toca el tema en curso), claves de API **falsas** (los clientes se instancian pero no
llaman a nadie) y `pipeline/` en `sys.path` (por el `from estado import ...`). Se pueden correr
**con un lote en marcha**.

⚠️ **`estado.py` escribe `.estado_actual` y `.costo_actual.json` relativos al directorio de
trabajo**, o sea el estado del tema EN CURSO. `EnTmpDir` en
[tests/test_estado.py](tests/test_estado.py) hace `chdir` a un temporal y **comprueba que no es la
raíz** antes de nada: sin esa guarda, correr los tests con un lote en marcha le borraría el sello
y los pasos siguientes trabajarían con el tema anterior. Si añades tests que toquen la raíz,
heredan de `EnTmpDir`.

⚠️ **La elección de qué probar no es por cobertura, es por tipo de fallo.** En el pipeline un error
se nota: el tema aborta, o el video sale mal y se ve. En estos dos archivos **no se nota nada** —
el informe se genera igual, se ve bien y afirma lo contrario de lo que pasó. Los dos casos reales
del 15 ago están congelados como test: `vistas_por_dia` clasificada como tasa («+5591 %») y el lote
degradándose solo al cambiar `temas.csv` (`se_quedaron_pct` de −16 % a +33 %).

`cargar()` en [tests/test_reporte.py](tests/test_reporte.py) importa los módulos con `importlib`
porque su nombre empieza por dígito — el mismo truco que usa el paso 12. Funciona porque los dos
son importables sin efectos: **los pasos de `pipeline/` no lo son** (trabajan al importarse), que
es el obstáculo real de [P-11](TODO.md#p-11), no los prefijos numéricos.

⚠️ **Un paso nuevo que use ffmpeg necesita `-nostdin`** (trampa 10), y si trabaja sobre los
archivos de la raíz debe llamar a `verificar_estado()` (trampa 1).

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
   ⚠️ La cabecera del paso 06 dice que lee `03_instagram.txt`, pero su `CONFIG` apunta a
   `carrusel.txt`. **Manda el CONFIG**; el comentario es de antes de la reestructuración del paso 02.
3. **A pesar del nombre del proyecto, las imágenes ya NO salen de Leonardo**, sino de fal.ai (Flux dev).
4. El contexto del paso 04 depende de que GPT devuelva json con `personaje`, `epoca` y `estilo_visual`.
   Si falla, verás `⚠️ Contexto incompleto` en el log y las imágenes de ese tema saldrán sin anclaje
   (menos coherentes entre sí, pero el tema no aborta).
5. **No todo lo que hay en `proyectos/` es un tema.** `proyectos/social_posts`,
   `proyectos/carousel_slides` y `proyectos/source_images` son basura de corridas viejas con
   `PROYECTO` vacío (ya no se pueden volver a crear: hay guardas en los pasos y en
   `run_pipeline.sh`), y `proyectos/T1/` es el **archivo de la tanda anterior al pipeline**, con
   otros 27 temas un nivel más abajo. Un `glob("proyectos/*")` te devuelve las tres cosas
   mezcladas. Inventario y limpieza: P-07 y P-14 en [TODO.md](TODO.md).
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
9. **Los `.sh` se re-ejecutan solos con bash.** En Ubuntu `/bin/sh` es `dash`, que no tiene `source`
   ni `[[ ]]`: con `sh run_all.sh` el shebang se ignora, el `source` de conda falla en silencio y
   `conda activate` responde `CondaError: Run 'conda init' before 'conda activate'`. La guarda
   `if [ -z "$BASH_VERSION" ]; then exec bash "$0" "$@"; fi` va **antes de cualquier sintaxis de
   bash** y tiene que ser POSIX puro. `run_all.sh` y `run_pipeline.sh` la llevan.
10. **El lote lee `temas.csv` por el descriptor 9, nunca por stdin.** Si el `while read` toma la
    lista por stdin, cualquier proceso hijo que lea de ahí se **come bytes de la lista de temas**.
    `ffmpeg` lo hace: sondea stdin buscando teclas interactivas (`q` para abortar). En un lote real
    esto mutiló casi todos los `PROYECTO` — `Historia02`→`a02`, `Historia04`→`04`,
    `Historia07`→`oria07` — y con ellos los nombres de video, respaldo y log. El síntoma engaña:
    parece que alguien editó el CSV a mitad de corrida. Tres defensas, todas puestas:
    `done 9< <(tail ...)` con `read <&9`, `run_pipeline.sh </dev/null`, y **`-nostdin` en las dos
    llamadas a ffmpeg** (pasos 03 y 08). Si agregas otra llamada a ffmpeg, ponle `-nostdin`.
    ⚠️ De la misma familia: **`logs/failed.csv` se escribe CON encabezado**. El bucle salta la
    primera línea (`tail -n +2`), así que sin él, reusarlo como `temas.csv` para reintentar perdía
    el primer tema caído en silencio — con `Historia07` y `Historia08` dentro, solo reintentaba
    Einstein. Si tocas cómo se escribe ese archivo, mantén el encabezado.
11. **Los cuatro `.py` de `desuso/` no los ejecuta nadie** — `publisher.py`, `ink_filter.py`,
    `imagen_generator_source.py` y `03_voice_generator_free.py` (ese `03` no significa nada: no es
    un paso). Qué era cada uno y por qué no funciona hoy:
    [§ Código en desuso](#código-en-desuso-está-en-git-no-lo-ejecuta-nadie).
    La publicación sigue siendo manual.
12. Cada tema cuesta **~$0.29 real** (mediana medida sobre `Historia09`-`Historia15`; eran ~$0.24
    antes del crítico de Opus y `gpt-5.4`): ~15 llamadas a OpenAI, la crítica en Anthropic, 1
    síntesis de ElevenLabs y 6 imágenes de
    fal.ai a 832×1472 (el 74 % del coste son las imágenes) (fal cobra por megapíxel: subir la resolución sube el costo proporcionalmente).
    `estado.py` lleva la cuenta en `.costo_actual.json` y los pasos 02 y 04 la imprimen al terminar.
    **No corras `run_all.sh` para probar un cambio** — usa un solo tema.

## Al hacer cambios

- Prueba con un tema aislado (`PROYECTO=Test01 TEMA="..." bash run_pipeline.sh`) antes del lote.
- Para iterar solo en el video sin regenerar guion, voz e imágenes, corre
  `python pipeline/07_video_generator.py` **desde la raíz**, con `TITULO_VIDEO` y `PROYECTO`
  exportados: reusa `images_IA/` y `voice.mp3` existentes.
- El paso 07 con Whisper `medium` es lento (minutos). Para pruebas rápidas de layout, baja
  `whisper_model` a `"tiny"` o descomenta el `final.subclip(0, 3)` de la línea 663.
- Los logs por tema quedan en `logs/`; los temas que fallan se acumulan en `logs/failed.csv` con el mismo
  formato de `temas.csv`, así que ese archivo se puede reusar directo como entrada para reintentar.
