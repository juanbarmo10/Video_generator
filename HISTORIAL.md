# HISTORIAL — auditoría, decisiones y resultados medidos

> **Esto es el registro de lo ya resuelto, no una lista de tareas.** Todo lo que hay aquí está
> aplicado y medido. Lo que queda por hacer vive en **[TODO.md](TODO.md)**.
>
> Sirve para una sola pregunta, que es la que más se repite al tocar este pipeline:
> *¿por qué está esto así?* Cada valor raro del `CONFIG` (el −14 LUFS, el `to_mask(canal=3)`,
> los 65-75 palabras, el `atempo=1.10`, el recorte del 8 %) sale de un fallo concreto que está
> documentado abajo con su medición. Antes de "arreglar" algo que parece arbitrario, búscalo aquí.
>
> Arranca como auditoría del 2026-08-02 sobre los 8 pasos, los 16 videos de `videos/` y los
> respaldos de `proyectos/`, medido con `ffprobe`/`ffmpeg`; sigue con las cinco fases de
> implementación y las pruebas posteriores. Lo marcado **CONFIRMADO** tiene evidencia en el
> [Anexo](#anexo--evidencia-medida).

## Índice

| Sección | Qué contiene |
|---|---|
| [Resumen ejecutivo](#resumen-ejecutivo) | Los 3 hallazgos que dominaban todo lo demás |
| [Parte 1 — Bugs](#parte-1--bugs) | Los 18 bugs de la auditoría, con su fix. **Todos aplicados** |
| [Parte 2 — Mejoras de procesamiento](#parte-2--mejoras-de-procesamiento) | Cortes, fotos reales, SRT, metadata de YouTube |
| [Parte 3 — Diagnóstico de contenido](#parte-3--diagnóstico-de-contenido-por-qué-no-te-ven) | Por qué no retenían: gancho, ritmo, duración, empaque |
| [Parte 4 — Plan de implementación](#parte-4--plan-de-implementación) | Las 5 fases, con lo medido antes/después de cada una |
| [Prueba end-to-end (Test01)](#prueba-end-to-end--test01--zinedine-zidane-3-ago-2026) | Primera corrida completa con todo aplicado |
| [Control de calidad del guion](#-control-de-calidad-del-guion-3-ago-2026) | Las dos capas y por qué el crítico corre en otro proveedor |
| [Métricas](#-métricas--resuelto-15-ago-2026) | Cómo se montó el consolidador y la primera lectura baseline vs v2 |
| [Fusión de los textos publicables](#-fusión-de-los-textos-publicables-8-ago-2026) | Por qué hay UN `descripcion.txt` y no dos archivos |
| [ffmpeg se comía los nombres](#-ffmpeg-se-comía-los-nombres-de-los-temas-8-ago-2026) | El bug de stdin que mutiló un lote entero |
| [Reorganización del código](#-reorganización-del-código-15-ago-2026) | Por qué el código está en `pipeline/`, `herramientas/` y `desuso/`, y qué no se movió |
| [Informe de métricas](#-informe-de-métricas-y-la-trampa-de-la-antigüedad-15-ago-2026) | El HTML semanal, y por qué comparar acumulados entre lotes de 4 y 66 días miente |
| [El `.env` corrompido](#-el-env-corrompido-por-un-título-de-dos-líneas-15-ago-2026) | Un título con salto de línea dejaba prosa que bash ejecutaba, y `failed.csv` sin encabezado |
| [El veredicto acusaba a otro guion](#-el-veredicto-de-calidad-acusaba-a-otro-guion-15-ago-2026) | `calidad_guion.json` guardaba la crítica del último intento, no la del guion elegido |
| [El recordatorio de Telegram](#-el-recordatorio-semanal-por-telegram-15-ago-2026) | Por qué calla si no hay nada, y por qué hay una entrada de cron de recuperación |
| [Los planos dejan de salir en pares](#-los-planos-dejan-de-salir-en-pares-15-ago-2026) | De 8 de 13 transiciones repitiendo imagen a 0, y por qué no se baraja al azar |
| [Los títulos de YouTube caben](#-los-títulos-de-youtube-caben-15-ago-2026) | Por qué aquí sí se vuelve a llamar al modelo en vez de truncar |
| [El composite fantasma](#-el-composite-fantasma-del-paso-07--159-15-ago-2026) | Render ×1.59 con un argumento, y por qué solo hay que tocar uno de los dos |
| [Paralelizar: evaluado](#-paralelizar-los-temas-evaluado-y-descartado-por-ahora-15-ago-2026) | 203 % de CPU, la RAM justa, y el `.env` como bloqueo real |
| [El generador aprende](#-el-generador-aprende-de-los-veredictos-15-ago-2026) | Dos capas —una gratis— y por qué NO se le enseñan las frases rechazadas |
| [El guionista sube a gpt-5.4](#-el-guionista-sube-a-gpt-54-15-ago-2026) | Por qué no escribir con Opus, y por qué gpt-5.5 cuesta 33× |
| [La puerta calibrada](#-la-puerta-de-calidad-calibrada-con-datos-reales-15-ago-2026) | La distribución real de 7 temas: el problema no era el umbral, era el guionista |
| [El flujo se vuelve automático](#-el-flujo-se-vuelve-automático-la-puerta-aborta-15-ago-2026) | Dos guiones falsos publicados, y por qué un aviso no sirve si nadie lo lee |
| [Los primeros tests](#-los-primeros-tests-98-y-verificados-por-mutación-15-ago-2026) | 98 tests elegidos por tipo de fallo, y cómo se probó que sirven |
| [El lote se degradaba solo](#-el-lote-se-degradaba-solo-al-cambiar-temascsv-15-ago-2026) | Cambiar `temas.csv` hacía que el informe afirmara lo contrario de lo real |
| [`T1/` era invisible](#-el-archivo-t1-era-invisible-para-las-métricas-15-ago-2026) | 78 de 147 filas sin `PROYECTO` por un glob de un solo nivel |
| [El paso 05 dormía de más](#-el-paso-05-dormía-el-triple-de-lo-necesario-15-ago-2026) | `DELAY` por fuente: −2.7 min por tema |
| [La curva cierra P-12](#-la-curva-de-retención-cierra-p-12-15-ago-2026) | Ni el gancho ni los cortes: dos métricas con denominadores distintos |
| [Métricas por API](#-métricas-de-youtube-por-api-15-ago-2026) | OAuth, lo que la API no da, y los tres fallos que parecían de Google |
| [Métricas de IG y FB](#-métricas-de-instagram-y-facebook-por-api-15-ago-2026) | `plays` deprecado, milisegundos, y el id de video que no es el id del post |
| [Publicar en IG y FB](#-publicar-en-instagram-y-facebook-15-ago-2026) | La subida reanudable, el registro de publicado y el parseo que casi pega los tags |
| [Anexo — evidencia medida](#anexo--evidencia-medida) | Los comandos y los números crudos |

---

## Resumen ejecutivo

El pipeline funciona de punta a punta y la calidad de escritura (paso 01/02) es buena. El problema
no es que falle: es que **degrada silenciosamente** en los últimos dos pasos y que **el producto de
video está optimizado para verse bonito, no para retener**.

Tres hallazgos dominan todo lo demás:

1. **El contorno negro de los subtítulos nunca se dibuja** (bug de `to_mask()` en moviepy). Texto
   blanco plano sobre ilustraciones claras = ilegible en un teléfono al sol. Esto solo ya explica
   una parte del abandono en los primeros segundos.
2. **El paso 08 recomprime el video y le quita el `+faststart`**: el archivo que subes tiene 26 %
   menos bitrate que el que ya habías renderizado, y con el índice al final del archivo.
3. **El título quemado arriba spoilea la historia en el frame 0** y se queda los 40 segundos. Le
   estás contando el final a alguien antes de darle un motivo para quedarse.

Y una omisión de producto: **no generas absolutamente nada para YouTube** (ni título, ni
descripción, ni tags, ni SRT). Subir un Short sin metadata a un canal nuevo es subirlo a ciegas.

---

## PARTE 1 — Bugs

Prioridad: **P0** = rompe el producto o produce contenido incorrecto · **P1** = degrada calidad
medible · **P2** = falla en casos concretos · **P3** = deuda / limpieza.

---

### 🔴 BUG-01 (P0) — `to_mask()` usa el canal ROJO, no el alfa · CONFIRMADO

**Dónde:** [07_video_generator.py:439](pipeline/07_video_generator.py#L439),
[07_video_generator.py:551](pipeline/07_video_generator.py#L551),
[07_video_generator.py:592](pipeline/07_video_generator.py#L592).

En moviepy 1.0.3 la firma real es:

```python
def to_mask(self, canal=0):
    newclip = self.fl_image(lambda pic: 1.0 * pic[:, :, canal] / 255)
```

`canal=0` es **rojo**, no alfa. Es decir: la transparencia de subtítulos, título y CTA la está
gobernando el canal rojo del texto dibujado. Consecuencias reales, todas visibles en los videos:

| Elemento | Color RGBA | Alfa que debería tener | Alfa real (rojo/255) | Resultado |
|---|---|---|---|---|
| Contorno del texto | `(0,0,0,255)` | 1.00 | **0.00** | **El contorno negro no existe** |
| Texto blanco | `(255,255,255,255)` | 1.00 | 1.00 | OK por casualidad |
| Resaltado amarillo | `(255,220,0,255)` | 1.00 | 1.00 | OK por casualidad |
| Barra del título | `(193,89,57,10)` | 0.04 | **0.76** | Barra marrón casi opaca |

Por eso `"title_bg_opacity": 10` (que debería ser invisible) se ve como una banda marrón sólida, y
por eso los subtítulos se ven planos sin borde. Y explica por qué nunca podrías usar un color de
texto azul o verde: se volvería semitransparente.

**Fix** — un helper único que use el canal alfa, y reemplazar los tres bloques copiados:

```python
def rgba_a_clip(make_frame, duration: float, fps: int) -> VideoClip:
    """RGBA → clip RGB + máscara tomada del canal ALFA.

    OJO: to_mask() usa canal=0 (ROJO) por defecto en moviepy 1.0.3. Con el default,
    el contorno negro del texto queda 100% transparente y no se dibuja nunca.
    """
    clip_rgba = VideoClip(make_frame, duration=duration)
    mask      = clip_rgba.to_mask(canal=3)          # ← 3 = alfa
    clip_rgb  = clip_rgba.fl_image(lambda im: im[:, :, :3])
    return clip_rgb.set_mask(mask).set_fps(fps)
```

**Después de aplicarlo hay que reajustar `CONFIG`**, porque valores que hoy “funcionan” por el bug
van a cambiar de aspecto:

```python
"title_bg_opacity": 170,   # antes 10 — con el bug se veía como ~195, ahora sería invisible
"subtitle_bg_opacity": 0,  # se mantiene sin fondo; el contorno ya da el contraste
```

---

### 🔴 BUG-02 (P0) — Si ElevenLabs falla, el pipeline sigue con la voz del tema anterior · CONFIRMADO

**Dónde:** [03_voice_generator.py:42-51](pipeline/03_voice_generator.py#L42-L51).

```python
response = requests.post(url, json=data, headers=headers)
print(response.status_code)
print(response.text)          # ← con un 200 esto vuelca el MP3 binario al log

if response.status_code == 200:
    with open(output, "wb") as f:
        f.write(response.content)
else:
    print("Error en ElevenLabs:", response.text)   # ← y sale con código 0
```

El script **termina con exit code 0 aunque falle**. `set -e` de `run_pipeline.sh` no lo detecta, así
que el paso 07 usa el `voice.mp3` del tema anterior. Resultado: un video con la narración
equivocada, marcado como ✅ Completado, que ni siquiera aparece en `logs/failed.csv`.

Es el bug más peligroso del repo: no rompe nada, produce basura convincente.

**Fix:**

```python
if response.status_code != 200:
    raise SystemExit(f"❌ ElevenLabs falló ({response.status_code}): {response.text[:300]}")

if len(response.content) < 10_000:          # un mp3 real de ~90 palabras pesa ~500 KB
    raise SystemExit(f"❌ ElevenLabs devolvió {len(response.content)} bytes — audio inválido")

with open(output, "wb") as f:
    f.write(response.content)
print(f"✅ voice.mp3 generado ({len(response.content) // 1024} KB)")
```

Y borrar el `print(response.text)` incondicional: con un 200 escupe binario al log.

**Extra recomendado — sellar el estado.** Los archivos de la raíz son estado global (trampa 1 de
CLAUDE.md). Vale la pena que cada paso escriba `.estado_actual` con el `PROYECTO` y que los
siguientes lo verifiquen, para que ninguna corrida mezcle temas:

```python
# al final del paso 01
Path(".estado_actual").write_text(f"{PROYECTO}\n{TEMA}\n", encoding="utf-8")

# al inicio de los pasos 03/04/07
dueño = Path(".estado_actual").read_text(encoding="utf-8").splitlines()[0]
if dueño != PROYECTO:
    raise SystemExit(f"❌ script.txt/voice.mp3 son de '{dueño}', no de '{PROYECTO}'")
```

---

### 🟠 BUG-03 (P1) — El paso 08 recomprime y degrada el entregable · CONFIRMADO

**Dónde:** [08_music_mixer.py:77-83](pipeline/08_music_mixer.py#L77-L83).

Medido sobre `Mundial16`:

| | `videos_no_music/` | `videos/` (el que subes) |
|---|---|---|
| Bitrate | 3 270 kbps | **2 418 kbps** (−26 %) |
| Orden de átomos | `ftyp, moov, free, mdat` | `ftyp, free, mdat, **moov**` |

El `write_videofile` del paso 08 no pasa `-crf`, ni `-pix_fmt yuv420p`, ni `-profile:v high`, ni
`-movflags +faststart` — todo lo que el paso 07 sí configuraba con cuidado. Se pierde en la segunda
pasada. El `moov` al final significa que la plataforma tiene que leer el archivo entero antes de
empezar a procesarlo.

Además es un re-encode de video **completamente innecesario**: solo cambia el audio.

**Fix — reemplazar moviepy por un mux directo con ffmpeg.** Copia el video bit a bit (instantáneo,
sin pérdida) y de paso resuelve BUG-04 y BUG-05:

```python
import subprocess

def mezclar(cfg: dict) -> None:
    dur = float(subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", cfg["video_input"]
    ]).strip())

    fade_out_start = max(0.0, dur - cfg["fade_out"])
    musica = pick_music(cfg["music_dir"])

    filtro = (
        f"[1:a]volume={cfg['music_volume']},"
        f"afade=t=in:st=0:d={cfg['fade_in']},"
        f"afade=t=out:st={fade_out_start}:d={cfg['fade_out']}[bg];"
        # La música baja sola cuando habla el narrador (ducking automático)
        f"[bg][0:a]sidechaincompress=threshold=0.03:ratio=12:attack=5:release=350[duck];"
        f"[0:a][duck]amix=inputs=2:duration=first:dropout_transition=0[mix];"
        # Normalización al estándar de redes sociales
        f"[mix]loudnorm=I={cfg['lufs']}:TP=-1.5:LRA=11[out]"
    )

    subprocess.run([
        "ffmpeg", "-y",
        "-i", cfg["video_input"],
        "-stream_loop", "-1", "-i", musica,
        "-filter_complex", filtro,
        "-map", "0:v", "-map", "[out]",
        "-c:v", "copy",                      # ← sin recomprimir el video
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        "-shortest",
        cfg["video_output"],
    ], check=True)
```

Con `CONFIG` ampliado:

```python
CONFIG = {
    ...
    "music_volume": 0.22,   # antes 0.1 — ver BUG-05
    "lufs":        -14.0,   # objetivo de sonoridad de redes — ver BUG-04
}
```

Beneficio secundario: el paso 08 pasa de ~1 minuto a ~2 segundos por tema.

---

### 🟠 BUG-04 (P1) — El audio sale ~6 dB por debajo del estándar de redes · CONFIRMADO

Medido: `mean_volume: -20.2 dB`, `max_volume: -5.5 dB` en el entregable final.

YouTube, Instagram y TikTok normalizan a **≈ −14 LUFS**. Un video que llega a −20 se percibe
apagado y sin energía al lado del siguiente en el feed — y la energía percibida en los primeros 2
segundos es un factor directo de retención. No es un tema de gusto: es que compites contra videos
que sí están normalizados.

**Fix:** incluido en el filtro `loudnorm=I=-14:TP=-1.5:LRA=11` de BUG-03.
Si quieres precisión de mastering, hazlo en dos pasadas (medir → aplicar); una pasada ya te acerca
lo suficiente.

---

### 🟠 BUG-05 (P1) — La música de fondo es literalmente inaudible · CONFIRMADO

`"music_volume": 0.1` con la voz a 1.0. Medida del `mean_volume` con y sin música: **−20.2 dB en
ambos casos**. La música no aporta ni un decibel — solo te está costando un re-encode.

**Fix:** subir a `0.20–0.25` **y** aplicar ducking por sidechain (ya incluido arriba), para que baje
sola cuando habla el narrador. Así se oye en los silencios sin taparlo nunca.

---

### 🟠 BUG-06 (P1) — Las imágenes se generan a 720×1280 y se estiran a 1080×1920 · CONFIRMADO

**Dónde:** [04_image_generator.py:318-321](pipeline/04_image_generator.py#L318-L321).

Verificado: los 8 `scene_N.png` miden 720×1280. El paso 07 los escala a 1080×1920 (**+50 %**) y
encima les aplica zoom de hasta 1.15 → el pico real de ampliación es **~1.72×**. Detalle fino,
líneas de tinta y texturas de pergamino se van a papilla justo en los planos más cercanos.

**Fix:**

```python
"image_size": {"width": 1088, "height": 1920},   # múltiplo de 16, sin upscale
```

⚠️ **Ojo al costo:** fal cobra Flux dev por megapíxel. 1088×1920 = 2.09 MP vs 720×1280 = 0.92 MP →
**~2.3× más caro por imagen**. Opciones según presupuesto:

| Config | MP | Costo relativo | Upscale en el video |
|---|---|---|---|
| 720×1280 (hoy) | 0.92 | 1.0× | 1.50× (malo) |
| 832×1472 | 1.22 | 1.3× | 1.30× (aceptable) |
| **1088×1920** | 2.09 | 2.3× | **1.00× (ideal)** |

Recomendación: **832×1472 + bajar `zoom_max` a 1.10**. Ganas casi toda la nitidez por un 30 % más
de costo. Si vas a 1088×1920, baja `zoom_max` a 1.08 para no volver a ampliar.

---

### 🟠 BUG-07 (P1) — El título quemado spoilea la historia en el frame 0 · CONFIRMADO

**Dónde:** [07_video_generator.py:653-658](pipeline/07_video_generator.py#L653-L658) — `duration=video.duration`.

Frames reales del segundo 0:

- `Mundial16` → **“MEMO OCHOA PERDIÓ PSG POR VISA”**
- `Mundial12` → **“APAGÓN TOTAL POR UN BOTÓN INVERTIDO”**

Es el desenlace, escrito arriba, antes de que el narrador diga una palabra. Le quitas al espectador
el único motivo que tenía para quedarse: la curiosidad. Y encima la barra ocupa la pantalla los 40
segundos completos.

Esto es a la vez un bug de UX y el error de contenido más caro que tienes (ver
[Parte 3 § 1](#1-los-primeros-2-segundos-son-el-90--del-problema)).

**Fix mínimo:** que el título dure solo el arranque y se vaya con fade.

```python
TITULO_DURACION = 2.5
title_clip = create_title_clip(...).set_duration(TITULO_DURACION).crossfadeout(0.4)
```

**Fix bueno:** que el paso 02 genere un **gancho en forma de pregunta abierta**, no un resumen.
Ver [Parte 2 § A](#a-paso-02--generar-gancho-de-pantalla-y-metadata-de-youtube).

---

### 🟡 BUG-08 (P2) — El CTA cae dentro de la zona de UI de TikTok/Reels

**Dónde:** [07_video_generator.py:601](pipeline/07_video_generator.py#L601) — `int(height * 0.82)`.

`0.82 × 1920 = 1574 px`, y el clip mide 105 px → ocupa **1574–1679**. En Instagram Reels y TikTok
los últimos ~400 px los tapan el usuario, el caption, los botones y el disco de audio. Tu CTA queda
debajo de la interfaz en las dos plataformas donde dices tener menos alcance.

**Zonas seguras reales (sobre 1920 px de alto):**

| Plataforma | Margen superior | Margen inferior |
|---|---|---|
| YouTube Shorts | ~110 px | ~290 px |
| Instagram Reels | ~130 px | **~420 px** |
| TikTok | ~130 px | **~480 px** |

Todo lo importante debería vivir entre **y = 200** y **y = 1440**.

**Fix:** `int(height * 0.70)` → 1344 px, dentro de la zona segura de las tres.

---

### 🟡 BUG-09 (P2) — `generate_visual_scenes` se rompe si GPT devuelve el JSON con backticks

**Dónde:** [04_image_generator.py:162](pipeline/04_image_generator.py#L162).

```python
scenes_json = json.loads(response.choices[0].message.content)
```

Sin `response_format` y sin limpiar el markdown. Un ```` ```json ```` al inicio revienta el paso 04
y aborta el tema completo (con el guion, la voz y las 6 llamadas del paso 02 ya pagadas).

Fíjate en el contraste: `extract_context()` (unas líneas arriba) **sí** tiene `response_format` y
**sí** captura `JSONDecodeError`. Este quedó sin protección.

**Fix:**

```python
raw = response.choices[0].message.content.strip()
raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw).strip()
try:
    scenes_json = json.loads(raw)
except json.JSONDecodeError as e:
    raise SystemExit(f"❌ Escenas no vinieron en JSON válido: {e}\n{raw[:400]}")
```

---

### 🟡 BUG-10 (P2) — No se valida cuántas imágenes se generaron

**Dónde:** [04_image_generator.py:380-386](pipeline/04_image_generator.py#L380-L386).

`generate_image()` captura la excepción y devuelve `None`; `generate_images_from_script()` filtra los
`None` y devuelve lo que haya. Si 5 de 8 fallan, el paso 04 sale con éxito y el paso 07 arma un video
con **3 imágenes de ~13 segundos cada una**. Degradación total, cero avisos.

**Fix:**

```python
MIN_IMAGENES = 6

generadas = [p for p in image_paths if p]
if len(generadas) < MIN_IMAGENES:
    raise SystemExit(f"❌ Solo {len(generadas)}/{len(scenes)} imágenes — insuficiente para el video")
if len(generadas) < len(scenes):
    print(f"⚠️  {len(scenes) - len(generadas)} imágenes fallaron — el ritmo del video se resiente")
return generadas
```

Y mejor aún: reintentar las fallidas una vez antes de rendirse.

---

### 🟡 BUG-11 (P2) — Seed fija 12345 para las 8 imágenes

**Dónde:** [04_image_generator.py:372](pipeline/04_image_generator.py#L372).

Las 8 escenas comparten seed. Con Flux esto empuja composiciones y encuadres parecidos entre sí —
justo lo contrario de la variedad visual que necesitas para retener.

**Fix:** determinista pero distinta por escena.

```python
SEED_BASE = 12345
...
executor.submit(generate_image, prompt, SEED_BASE + i * 977, i, output)
```

---

### 🟡 BUG-12 (P2) — `negative_prompt` no hace nada en `fal-ai/flux/dev`

**Dónde:** [04_image_generator.py:317](pipeline/04_image_generator.py#L317).

Flux dev es un modelo destilado sin guidance clásico; el endpoint `fal-ai/flux/dev` no expone
`negative_prompt` en su schema, así que ese parámetro se ignora. Toda tu protección contra “deformed
hands, extra fingers, bad anatomy” **no se está aplicando**.

**Fix:** mover esas restricciones al prompt positivo (lo que Flux sí lee) y controlar la anatomía
evitando manos en primer plano desde el generador de escenas:

```python
BASE_PROMPT = """
vintage editorial illustration, colored ink drawing,
aged parchment paper background, warm beige paper texture,
bold flat colors on figures and objects,
hand-drawn outlines, minimal shading, no depth,
flat perspective, stylized figures, clean well-formed hands,
historic illustration style,
full-bleed edge-to-edge composition, no paper border, no frame,
9:16 vertical composition optimized for mobile,
no text, no letters, no numbers, no signage, no watermark
"""
```

(Verifica en la respuesta de `fal_client.run` si el parámetro aparece o no; si fal lo empezara a
soportar, mejor, pero hoy no cuentes con él.)

---

### 🟡 BUG-13 (P2) — Se le piden a Flux escenas con texto, y Flux no sabe escribir · CONFIRMADO

El frame 0 de `Mundial16` es una mano firmando un contrato lleno de **texto inventado ilegible**
(“Gorttay Ermacts”). Es el primer fotograma del video: lo primero que ve el usuario es un garabato.

El `BASE_PROMPT` dice `no text`, pero el paso 04 genera libremente escenas centradas en documentos,
cartas y periódicos, y ahí el `no text` no puede ganar. Hay que prohibirlo **en el generador de
escenas**, no solo en el estilo.

**Fix** — agregar a las reglas de `generate_visual_scenes()`:

```
🚫 REGLAS VISUALES (el modelo de imágenes no sabe escribir):
- PROHIBIDO centrar una escena en documentos, contratos, cartas, periódicos,
  pantallas, carteles, letreros, pizarras o cualquier superficie con texto legible.
- Si la historia gira sobre un documento, muestra la REACCIÓN humana, no el papel:
  ❌ "close-up of a contract being signed"
  ✅ "a man in a suit stares at an empty desk, shoulders slumped, office window behind him"
- Prioriza ROSTROS HUMANOS con emoción clara en al menos 4 de las 8 escenas.
- Al menos 2 escenas deben ser primer plano de rostro (close-up), no plano general.
```

Lo de los rostros no es cosmético: los primeros planos de caras son de lo que más sostiene la
retención en vertical, y hoy tus 8 escenas son casi todas planos generales de espaldas.

---

### 🟡 BUG-14 (P2) — Palabras largas se salen del clip de subtítulos

**Dónde:** [07_video_generator.py:390-407](pipeline/07_video_generator.py#L390-L407).

El salto a dos líneas solo se activa `if total_width > max_width and len(words_text) == 2`. Con
**una** palabra muy larga (`"INTERNACIONALIZACIÓN"`, `"CONSTANTINOPLA"` a 100 px), `x` se vuelve
negativo y el texto se recorta por los dos lados.

**Fix:** auto-reducir el cuerpo hasta que quepa.

```python
def fuente_que_quepa(texto: str, draw, ruta: str, size_max: int, ancho_max: int):
    """Baja el tamaño de fuente hasta que el texto entre en el ancho disponible."""
    for size in range(size_max, 40, -4):
        f = ImageFont.truetype(ruta, size)
        if draw.textlength(texto, font=f) <= ancho_max:
            return f
    return ImageFont.truetype(ruta, 40)
```

---

### 🟡 BUG-15 (P2) — Los subtítulos aparecen antes de la primera palabra

**Dónde:** [07_video_generator.py:289-333](pipeline/07_video_generator.py#L289-L333).

`get_active_word_window()` siempre devuelve un par, incluso en `t=0` cuando el narrador todavía no
empezó. El primer par se ve congelado durante el silencio inicial.

**Fix:** al inicio de la función,

```python
if t < words[0]["start"] - 0.15:
    return [], -1
```

---

### ⚪ BUG-16 (P3) — `resize_for_social()` asume la carpeta de salida

**Dónde:** [05_download_images.py:158](pipeline/05_download_images.py#L158) — `dest = out_dir / "source_images" / src.name`,
invocado como `resize_for_social(dest, out_dir.parent)`.

Funciona solo porque `--out` vale `source_images` y `.parent` es la raíz. Con cualquier otro `--out`
escribe en la carpeta equivocada. **Fix:** pasar la ruta de destino directa en vez de reconstruirla.

---

### ⚪ BUG-17 (P3) — `social_posts/` no se limpia entre temas

Ya documentado como trampa 1 en CLAUDE.md, sigue abierto. Los pasos 04, 05 y 06 sí limpian; el 02
no. **Fix:** replicar `clean_output_dir()` en el paso 02.

---

### ⚪ BUG-18 (P3) — `temas.csv` tiene una fila con coma extra

`Mundial11,Maradona,` → `$TEMA` queda como `"Maradona,"`. Trampa 8 de CLAUDE.md, sigue en el archivo.
**Fix:** limpiar la fila y validar en `run_all.sh` que no haya más de 2 campos.

---

## PARTE 2 — Mejoras de procesamiento

### A. Paso 02 — Generar gancho de pantalla y metadata de YouTube

**Hoy no produces nada para YouTube.** Ni título, ni descripción, ni tags, ni hashtags. Para un canal
nuevo, el título de un Short es la principal señal de clasificación temática y la única palanca de
búsqueda. Subir sin eso es apagar la mitad de la distribución.

Agrega dos funciones al paso 02:

```python
def generar_gancho_pantalla(script: str) -> str:
    """Texto grande de los primeros 2s. NO resume: abre un bucle de curiosidad."""
    r = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": (
                "Escribes ganchos para videos verticales. Máximo 7 palabras. "
                "PROHIBIDO revelar el desenlace: tu trabajo es crear la pregunta, no responderla. "
                "Debe generar una pregunta inevitable en la cabeza del espectador. "
                "Solo el texto, en MAYÚSCULAS, sin comillas ni punto final."
            )},
            {"role": "user", "content": script}
        ], max_tokens=30
    )
    return r.choices[0].message.content.strip()


def generar_metadata_youtube(script: str, research: str) -> dict:
    r = client.chat.completions.create(
        model="gpt-4.1",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": (
                "Eres experto en SEO de YouTube Shorts en español. Devuelve JSON con:\n"
                '- "titulo": máx 70 caracteres, con curiosidad, SIN spoilear el final, '
                'con la entidad principal al inicio (es la señal temática del algoritmo)\n'
                '- "descripcion": 2 frases + 3 hashtags de nicho + #Shorts\n'
                '- "tags": lista de 12 tags relevantes\n'
                '- "comentario_fijado": una pregunta que invite a responder'
            )},
            {"role": "user", "content": f"SCRIPT:\n{script}\n\nINVESTIGACIÓN:\n{research}"}
        ]
    )
    return json.loads(r.choices[0].message.content)
```

Guardar en `social_posts/05_youtube.txt` y `GANCHO_PANTALLA` en el `.env` (mismo mecanismo que
`TITULO_VIDEO`, con `save_to_env`).

---

### B. Paso 07 — Multiplicar los cortes (lo más importante de esta sección)

**Hoy:** 8 imágenes ÷ 38 s = **1 corte cada 4.7 segundos**. Un short que retiene cambia de plano cada
**1.5–2.5 s**. Estás a menos de la mitad del ritmo mínimo, y el zoom lento sobre un dibujo estático
se lee como presentación de diapositivas.

**No hace falta generar más imágenes** (eso duplicaría el costo). Con Ken Burns sobre regiones
distintas de la misma imagen conviertes 8 imágenes en 16–24 planos:

```python
def sub_planos(img_path: str, n: int, dur: float, cfg: dict) -> list:
    """Parte una imagen en N planos con encuadre y movimiento distintos.
    8 imágenes × 2-3 planos = 16-24 cortes → 1 corte cada ~1.8s."""
    RECORTES = [
        (0.50, 0.35, 1.00),   # (cx, cy, escala) — tercio superior
        (0.50, 0.50, 0.75),   # centro cerrado
        (0.50, 0.65, 1.00),   # tercio inferior
        (0.35, 0.45, 0.80),   # izquierda cerrado
        (0.65, 0.45, 0.80),   # derecha cerrado
    ]
    planos = []
    for k in range(n):
        cx, cy, escala = RECORTES[(hash(img_path) + k) % len(RECORTES)]
        c = (ImageClip(img_path)
             .set_duration(dur + cfg["crossfade_duration"])
             .resize(height=int(cfg["video_height"] / escala)))
        c = c.crop(
            x_center=c.size[0] * cx, y_center=c.size[1] * cy,
            width=cfg["video_width"], height=cfg["video_height"],
        )
        planos.append(add_smooth_zoom(c, zoom_factor=random.uniform(*cfg["zoom_rango"])))
    return planos
```

Agrega a `CONFIG`:

```python
"planos_por_imagen": 3,      # 8 imágenes × 3 = 24 planos ≈ 1 corte cada 1.6s
"zoom_rango": (1.05, 1.12),
```

⚠️ Combínalo con BUG-06: si generas a 832×1472, un recorte de `escala=0.75` implica ampliar. Con
`escala` mínima de 0.80 y origen 1088×1920 no hay upscale visible.

---

### C. Paso 07 — Meter las fotos reales en el video

Ya descargas 6 fotos reales de Wikimedia/DuckDuckGo en el paso 05… y **solo las usas en el carrusel**.
Para contenido histórico y deportivo, una foto real vale más que diez ilustraciones IA: da prueba y
credibilidad, y rompe la monotonía de estilo.

Mete 2–3 fotos reales en momentos clave (el dato duro, el desenlace). Requiere manejar `.jpg`
además de `.png` en `load_images()` (trampa 7 de CLAUDE.md) y recortar de 1080×1080 a 9:16 con
fondo desenfocado de la propia imagen.

---

### D. Paso 07 — Barra de progreso

Una barra fina arriba que se llena a lo largo del video le dice al espectador “esto es corto,
aguanta”. Es de las intervenciones con mejor relación esfuerzo/retención.

```python
def crear_barra_progreso(video_size, duration, cfg):
    w, h = video_size
    alto = 8
    def make_frame(t):
        img = Image.new("RGBA", (w, alto), (255, 255, 255, 40))
        ancho = int(w * (t / duration))
        ImageDraw.Draw(img).rectangle([0, 0, ancho, alto], fill=(255, 220, 0, 255))
        return np.array(img)
    return rgba_a_clip(make_frame, duration, cfg["fps"]).set_position(("center", 0))
```

(Usa el helper `rgba_a_clip` del BUG-01 — con `to_mask()` por defecto esto se vería mal.)

---

### E. Paso 07 — Exportar subtítulos SRT

Ya tienes los timestamps por palabra de Whisper. Exportar un `.srt` es gratis y sirve para que
YouTube indexe el contenido hablado (mejora la búsqueda) y para subir captions en Meta.

```python
def exportar_srt(words: list[dict], destino: str, palabras_por_linea: int = 6) -> None:
    def ts(s):
        h, m, seg = int(s // 3600), int(s % 3600 // 60), s % 60
        return f"{h:02d}:{m:02d}:{seg:06.3f}".replace(".", ",")

    with open(destino, "w", encoding="utf-8") as f:
        for i in range(0, len(words), palabras_por_linea):
            grupo = words[i:i + palabras_por_linea]
            f.write(f"{i // palabras_por_linea + 1}\n")
            f.write(f"{ts(grupo[0]['start'])} --> {ts(grupo[-1]['end'])}\n")
            f.write(" ".join(w["word"] for w in grupo) + "\n\n")
```

---

### F. Robustez general del pipeline

| Mejora | Por qué |
|---|---|
| `requirements.txt` con versiones fijas | `moviepy==1.0.3` es crítico (trampa 6); hoy no está escrito en ningún lado |
| `git init` | 8 scripts, ~110 KB de lógica, cero historial. Un `.gitignore` con `.env`, `videos/`, `proyectos/`, `*.mp3` |
| Reintentos con backoff en las llamadas OpenAI | Un 429 aborta el tema tras haber pagado los pasos anteriores |
| Contador de costo por tema en el log | Hoy no sabes cuánto te cuesta cada video (trampa 12 de CLAUDE.md) |
| `--skip-pasos` en `run_pipeline.sh` | Reiterar solo el video sin repagar guion, voz e imágenes |
| Cachear `WhisperModel` | Se recarga el modelo `medium` completo en cada tema |

---

## PARTE 3 — Diagnóstico de contenido: por qué no te ven

*(Revisión desde el punto de vista de creación de contenido, sobre los frames reales de
`Mundial01`, `Mundial12` y `Mundial16`.)*

Voy a ser directo: el contenido está **bien escrito y mal empaquetado**. Los guiones tienen buenos
datos y buen ritmo de lectura. El problema está en cómo se presentan los primeros segundos y en el
ritmo visual.

---

### 1. Los primeros 2 segundos son el 90 % del problema

En Shorts y Reels la métrica que decide todo es **cuánta gente NO desliza en los primeros 2
segundos**. Si el 70 % desliza, no importa lo bueno que sea el resto: el video no se distribuye.

Esto es lo que ve tu espectador en el frame 0 de `Mundial16`:

- Una **barra marrón con el spoiler completo**: “MEMO OCHOA PERDIÓ PSG POR VISA”. Ya sabe todo. No
  tiene ninguna razón para quedarse.
- Una ilustración IA de una mano firmando un papel con **texto ininteligible**. Señal instantánea de
  “esto es contenido generado en masa”.
- Un subtítulo blanco plano **sin contorno** (BUG-01), difícil de leer.
- Audio 6 dB por debajo del video anterior del feed (BUG-04): se siente apático.

Y el guion arranca con: *“Nadie más ha estado tan cerca de firmar con el París Saint-Germain y
perderlo por un pedazo de papel.”* — 18 palabras. Tu propia regla del paso 01 dice máximo 12, y el
modelo la incumplió. A 143 palabras por minuto, esa frase tarda **7.5 segundos** en terminar. Para
cuando llegas al gancho, la mitad de la audiencia ya se fue.

**Qué hacer, en orden de impacto:**

1. **Corta el spoiler.** El título en pantalla debe crear la pregunta, no responderla.
   - ❌ “MEMO OCHOA PERDIÓ PSG POR VISA”
   - ✅ “EL PSG YA LO HABÍA FICHADO”
   - ✅ “LE FALTÓ UN SOLO PAPEL”
2. **Primera frase de máximo 8 palabras**, con el sujeto concreto al inicio. Refuerza la regla en el
   paso 01: *“La PRIMERA frase debe tener máximo 8 palabras y terminar en un misterio sin resolver.
   Si tiene más de 8, reescríbela.”*
3. **Título en pantalla solo 0–2.5 s**, y que desaparezca (BUG-07).
4. **Que el frame 0 sea un rostro humano en primer plano con emoción**, no un objeto ni una espalda.
   Los tres frames que revisé son planos generales de personas de espaldas. Poner una cara con una
   emoción legible en el segundo 0 es de los cambios más rentables que puedes hacer.

---

### 2. El ritmo visual es de presentación, no de short

**1 corte cada 4.7 segundos.** El estándar de lo que funciona hoy es 1.5–2.5 s. El zoom sinusoidal
está bien hecho, pero un zoom lento sobre un dibujo estático no es movimiento: es un salvapantallas.

Solución sin costo extra en la [Parte 2 § B](#b-paso-07--multiplicar-los-cortes-lo-más-importante-de-esta-sección):
partir cada imagen en 2–3 encuadres. 8 imágenes → 24 planos → 1 corte cada 1.6 s.

---

### 3. La duración juega en tu contra

38–45 segundos, con voz a **143 palabras por minuto**. Dos problemas sumados:

- La narración viral en español va a **170–190 wpm**. La tuya se siente lenta, casi de documental.
- Para un canal sin audiencia, el **porcentaje de retención** pesa más que los segundos vistos. Un
  video de 25 s con 80 % de retención se distribuye mucho mejor que uno de 40 s con 45 %.

**Qué hacer:**

- Bajar el guion de 90–100 a **65–75 palabras** en el paso 01.
- Acelerar la voz un 10 %. ElevenLabs `eleven_multilingual_v2` no expone `speed` de forma fiable, así
  que hazlo en post con ffmpeg (no altera el tono):
  ```bash
  ffmpeg -i voice.mp3 -filter:a "atempo=1.10" -b:a 192k voice_fast.mp3
  ```
  Va como paso 03b, antes de que Whisper transcriba (los timestamps se recalculan sobre el audio
  final, así que no se desincroniza nada).
- Resultado: **~25 segundos**. Punto dulce para Shorts.

---

### 4. Estás matando el bucle al final

El CTA “Sígueme para más historias” ocupa los **últimos 3 segundos** — sobre la resolución de la
historia y, encima, debajo de la interfaz de Reels y TikTok (BUG-08). Tres segundos de nada al final
hunden el porcentaje de retención justo donde más se mide.

**Qué hacer:**

- Terminar **en la frase de impacto** y cortar. Sin colchón.
- El CTA, si va, que sea de 1.5 s **encima** de la última frase, no después.
- Mejor CTA que “sígueme”: una **pregunta que genere comentarios** (“¿Lo sabías?”, “¿Qué otro caso
  conoces?”). Los comentarios son señal de distribución; “sígueme” no lo es.
- Truco de bucle: que el último plano se parezca al primero. El espectador no percibe el corte, el
  video vuelve a empezar y sube el conteo de reproducciones.

---

### 5. El estilo visual te está identificando como contenido masivo IA

La ilustración vintage sobre pergamino está bien ejecutada, pero:

- **El borde de pergamino desperdicia ~8 % de pantalla** y hace que se vea como un póster metido
  dentro del teléfono en vez de video a sangre. Añade `full-bleed edge-to-edge composition, no paper
  border, no frame` al `BASE_PROMPT` (BUG-12).
- **Las 8 imágenes tienen el mismo estilo, la misma paleta y la misma distancia de cámara.** No hay
  contraste visual, y sin contraste el ojo se relaja y desliza.
- Para temas de fútbol y Mundiales, **la audiencia quiere ver la foto real**. Ochoa, Maradona, el
  Maracanazo — son eventos fotografiados. Ya descargas esas fotos y las tiras a la basura del video
  ([Parte 2 § C](#c-paso-07--meter-las-fotos-reales-en-el-video)). Mezclar foto real + ilustración es
  más creíble *y* más dinámico.

---

### 6. No hay metadata: estás publicando a ciegas

Es la brecha más grande del proyecto. Generas 4 posts para Twitter, Threads, Instagram y Facebook, y
**cero para YouTube**, que es donde te falta alcance.

Lo que le falta a cada Short que subes:

| Falta | Impacto |
|---|---|
| Título optimizado | Es la señal principal de clasificación temática y toda la búsqueda de Shorts |
| Descripción + hashtags de nicho | Contexto para el clasificador |
| Tags | Señal secundaria, gratis |
| Subtítulos SRT | YouTube indexa el contenido hablado |
| Comentario fijado con pregunta | Arranca la conversación, y los comentarios son señal de distribución |
| Miniatura personalizada | YouTube ya la soporta en Shorts |

Todo esto lo puede generar el paso 02 con **una sola llamada extra** a GPT-4.1
([Parte 2 § A](#a-paso-02--generar-gancho-de-pantalla-y-metadata-de-youtube)).

---

### 7. Instagram y Facebook: problemas propios

Meta se comporta distinto a YouTube, y ahí hay cosas específicas:

- **Estás compitiendo contigo mismo.** Publicas un carrusel *y* un reel del mismo tema. Meta no
  empuja dos piezas del mismo tema de la misma cuenta el mismo día: se canibalizan. Sepáralas
  **48–72 horas** y usa el carrusel como refuerzo de un reel que ya funcionó.
- **Meta penaliza el contenido que detecta como generado por IA** más que YouTube. Mezclar fotos
  reales (§ 5) ayuda directamente a esto.
- **El audio importa mucho más en Reels.** Con la música a volumen 0.1 (inaudible, BUG-05) el video
  no se asocia a ningún audio y pierde una vía de descubrimiento.
- **Publica como Reel, nunca como “Video”**, y desde una cuenta de Creador.
- **Cero marcas de agua de otras plataformas.** (Ya cumples: renderizas nativo).
- **Los primeros 3 segundos en Reels pesan aún más que en Shorts**, porque el feed va a pantalla
  completa desde el arranque.

---

### 8. Estrategia de publicación

Los 16 videos de `Mundial*` se renderizaron el mismo día (16:27 → 21:27 según las marcas de tiempo).
Si también se subieron en bloque, eso solo ya explica buena parte del bajo rendimiento:

- **1 video por día**, misma hora. La consistencia es una señal de canal.
- **Coherencia temática.** Tus logs mezclan Mundiales, Tupac, Jesús, Vikingos, la Mafia, la cerveza,
  el Dalai Lama y el internet. El clasificador no sabe a quién recomendarte. Serie de **20–30 videos
  del mismo nicho** (Mundiales está perfecto), luego pivotas.
- **Series numeradas** (“Historias del Mundial #7”): entrena a la audiencia a volver.
- **Prueba A/B de ganchos.** Genera 3 ganchos por tema y guárdalos en `social_posts/`. Cuando un
  video muera en 24 h, resúbelo en 10 días con otro gancho y otro frame 0. El guion es el mismo; solo
  cambias los primeros 2 segundos.
- **Lee YouTube Studio.** La curva de retención te dice el segundo exacto donde te abandonan. Si la
  caída está en 0–2 s → gancho. Si está en 5–10 s → ritmo visual. Sin mirar eso, todo esto son
  hipótesis.

---

## PARTE 4 — Plan de implementación

### ✅ Fase 1 — Arreglos críticos — APLICADA (commit `5cfac52`)

Se prueban regenerando solo el paso 07+08 sobre un tema existente, sin repagar nada:

```bash
export PROYECTO=Mundial16 TITULO_VIDEO="Memo Ochoa perdió PSG por visa"
python 07_video_generator.py && python 08_music_mixer.py
```

- [x] **BUG-01** — máscara desde el canal alfa (`to_mask(canal=3)`) + helper `rgba_a_clip`
- [x] **BUG-01b** — `title_bg_opacity` 10 → 170
- [x] **BUG-02** — el paso 03 aborta si ElevenLabs falla
- [x] **BUG-03** — paso 08 con mux ffmpeg `-c:v copy` + `+faststart`
- [x] **BUG-04** — `loudnorm=I=-14:TP=-1.5:LRA=11`
- [x] **BUG-05** — música 0.1 → 0.22 con ducking por sidechain
- [x] **BUG-07** — título en pantalla solo 2.5 s con fade
- [x] **BUG-08** — CTA a `height * 0.70`; título de `y=20` a `y=200`

**Resultados medidos sobre `Mundial16`:**

| Métrica | Antes | Después |
|---|---|---|
| Bitrate del entregable | 2 418 kbps | **3 343 kbps** (stream de video bit a bit idéntico al de `videos_no_music/`) |
| Sonoridad integrada | −17.5 LUFS | **−14.3 LUFS** |
| Orden de átomos | `ftyp, free, mdat, moov` | **`ftyp, moov, free, mdat`** (faststart) |
| Tiempo del paso 08 | ~60 s | **2.7 s** |
| Contorno del texto | no se dibujaba | **66 035 px opacos** en el par de subtítulo |

Extra aplicado fuera de la lista: `git init` con `.gitignore` que excluye el `.env`,
`.env.example` y `requirements.txt` con `moviepy==1.0.3` fijado.

---

### ✅ Fase 2 — Ritmo y empaque — APLICADA

- [x] **Parte 2 § B** — 3 planos por imagen: 8 imágenes → **24 cortes**, 1 cada ~1.1 s
      (`crear_planos_de_imagen()` + `ENCUADRES` + `planos_por_imagen` en `CONFIG`)
- [x] **Parte 2 § D** — barra de progreso (`crear_barra_progreso()`)
- [x] **Parte 2 § E** — exportar SRT a `proyectos/$PROYECTO/$PROYECTO.srt`
- [x] **Parte 3 § 3** — guion a 65–75 palabras (paso 01) + `atempo=1.10` (paso 03)
- [x] **Parte 3 § 4** — CTA de 2 s **encima** de la última frase, texto → `"¿Tú lo sabías?"`
- [x] **BUG-14** — `fuente_que_quepa()` con cache de fuentes; el layout usa el tamaño efectivo
- [x] **BUG-15** — nada en pantalla antes de la primera palabra

Extra: guarda si Whisper no transcribe nada, y aviso en consola si un plano dura más de 3 s.

**Efecto combinado sobre la duración:** 90 palabras a 143 wpm = 38 s →
65–75 palabras a 157 wpm = **~26 s**.

> ⚠️ `planos_por_imagen: 3` y `recorte_escala_min: 0.85` están calibrados para imágenes de
> 720×1280. Cuando apliques BUG-06 (generar a 832×1472 o más) puedes bajar `recorte_escala_min`
> a 0.75 y cerrar más los planos sin que se pixele.

---

### ✅ Fase 3 — Calidad de imagen y gancho — APLICADA

- [x] **BUG-06** — `IMAGE_WIDTH/HEIGHT` = 832×1472 (antes 720×1280). Sube el costo
      de fal ~1.3× por imagen; ver la tabla de BUG-06 si quieres 1088×1920
- [x] **BUG-09** — JSON de escenas tolerante a ```` ```json ```` + error claro
- [x] **BUG-10** — `MIN_IMAGENES = 6`; aborta en vez de entregar un video degradado
- [x] **BUG-11** — seed `SEED_BASE + i*977` por escena
- [x] **BUG-12** — fuera el `negative_prompt` (Flux dev lo ignoraba); anatomía al `BASE_PROMPT`
- [x] **BUG-13** — prohibido centrar escenas en texto; escena 1 obligatoriamente
      primer plano de rostro; mínimo 4 escenas con rostros
- [x] **BUG-17** — el paso 02 limpia `social_posts/` antes de escribir
- [x] **Parte 2 § A** — `generate_title()` reescrito para NO spoilear +
      `generate_youtube_metadata()` → `social_posts/05_youtube.txt`
- [x] **Parte 2 § C** — `preparar_fotos_reales()` + `intercalar_fotos_reales()`:
      las fotos del paso 05 entran al video convertidas a 9:16 con fondo
      desenfocado de la propia imagen y tinte cálido
- [x] **Ritmo adaptativo** — `repartir_planos()` calcula los cortes desde
      `duracion_plano_objetivo` (1.8 s) en vez de un número fijo

> ⚠️ **Lo de la Fase 3 que NO está verificado end-to-end:** los cambios del paso 04
> (resolución, seed, prompts) solo se pueden comprobar regenerando imágenes en fal,
> y eso cuesta dinero real. Compilan y la lógica está revisada, pero **el primer
> tema que corras completo es la prueba**. Córrelo con un `PROYECTO` de prueba
> aislado antes del lote, y revisa que la escena 1 salga con un rostro.

---

### ✅ Fase 4 — Robustez y operación — APLICADA (código)

- [x] **BUG-09 / BUG-10** — JSON robusto + mínimo de imágenes *(entró en Fase 3)*
- [x] **BUG-16** — `resize_for_social()` recibe la ruta destino en vez de reconstruirla
- [x] **BUG-17** — el paso 02 limpia `social_posts/` *(entró en Fase 3)*
- [x] **BUG-18** — fila `Mundial11,Maradona,` corregida en `temas.csv`, y `run_all.sh`
      ahora **rechaza** filas con más de 2 campos en vez de tragárselas
- [x] `git init` + `.gitignore` (excluye `.env`) + `.env.example` + `requirements.txt`
- [x] Sello `.estado_actual` — nuevo módulo [estado.py](pipeline/estado.py). El paso 01 sella el
      `PROYECTO`; los pasos 02, 03, 04 y 07 abortan si los archivos de la raíz son de otro tema
- [x] Contador de costo por tema en `.costo_actual.json` (OpenAI por tokens, fal por
      megapíxel, ElevenLabs por carácter). Los pasos 02 y 04 lo imprimen al terminar
- [x] `con_reintentos()` con backoff exponencial (aplicado al paso 01)
- [x] **Calendario de publicación 1/día + registro de métricas a 24 h y 7 días** — resuelto
      después, fuera de esta fase: el calendario lo escribe [09_paquete_publicacion.py](herramientas/09_paquete_publicacion.py)
      (`publicar/calendario.csv`) y las ventanas de 24 h / 7 d las saca [10_metricas.py](herramientas/10_metricas.py)
      de la serie diaria de YouTube

> Los precios de `PRECIOS_OPENAI`, `PRECIO_FAL_POR_MP` y `PRECIO_ELEVENLABS_POR_CHAR` en
> `estado.py` son de mayo 2026 y **están puestos a mano**: si cambian las tarifas, el contador
> miente. Trátalo como orden de magnitud, no como factura.
>
> `con_reintentos()` solo envuelve la llamada del paso 01. Extenderlo a las 7 llamadas del paso 02
> y las 2 del paso 04 es mecánico y queda pendiente.

---

### ✅ Fase 5 — Costo de fal y calidad de las fotos reales — APLICADA

**El costo de fal NO sube por los cortes.** `crear_planos_de_imagen()` recorta la *misma* imagen en
varios encuadres: 8 → 19 cortes se hizo con exactamente las mismas 8 imágenes. Lo que subió el costo
fue la resolución de BUG-06. Y como fal cobra por **megapíxel**, lo que importa es el total:

| Configuración | MP/tema | vs. original |
|---|---|---|
| 8 imgs @ 720×1280 (antes de todo) | 7.37 | 100 % |
| 8 imgs @ 832×1472 (Fase 3) | 9.80 | 133 % |
| **6 imgs @ 832×1472 (ahora)** | **7.35** | **100 %** |
| 6 imgs @ 1088×1920 | 12.53 | 170 % |
| 5 imgs @ 832×1472 | 6.12 | 83 % |

- [x] **`N_ESCENAS` 8 → 6** en el paso 04 (`MIN_IMAGENES` 6 → 5). Vuelve al gasto original
      conservando el +33 % de nitidez. **El ritmo no se resiente**: `repartir_planos()` calcula los
      cortes desde la duración del audio, no desde el número de imágenes — con 6 u 8 salen los
      mismos 14 cortes de 1.86 s.

**Palancas de costo, de mayor a menor efecto:** número de temas por mes ≫ `N_ESCENAS` ≈ resolución
≫ todo lo demás. `duracion_plano_objetivo`, `planos_por_imagen` y las fotos reales cuestan **cero**.

#### Fotos reales irrelevantes

- [x] **`fotos_reales_solo_extremos`** (paso 07) — solo entran al video las fotos de la primera y la
      última query, que son las únicas donde el paso 02 obliga a incluir al protagonista
- [x] **`validar_con_vision()`** (paso 05) — mira la imagen de verdad con `gpt-4.1` y, si no
      corresponde, la borra y prueba con la siguiente candidata. Se aplica también al fallback de
      DuckDuckGo, que es por donde entra casi toda la basura. La imagen se manda reescalada a 512 px
      con `detail: "low"` para abaratar la llamada. Si falla (sin API key, error de red) **acepta la
      foto**: es un filtro de calidad, no una guarda de seguridad, y no debe bloquear el pipeline.
- [x] **Filtro por patrón `img_N.ext`** (paso 07) — lo que se deje a mano en `source_images/` ya no
      puede llegar al video

Calibración verificada 4/4: acepta una foto de partido con el sujeto lejano y contexto correcto;
rechaza un retrato personal, un documento y una foto válida contra la query equivocada. El primer
prompt era demasiado estricto (rechazaba fotos buenas donde no se distinguía la cara).

> ⚠️ **`source_images/` tenía dos archivos personales** — `pasaporte_paula.jpeg` y un retrato
> familiar antiguo guardado como `img_5.jpg`. El segundo pasaba todos los filtros porque **usa el
> nombre que genera el pipeline**, y con `solo_extremos` habría entrado al video. Revisa esa carpeta:
> el paso 06 la lee para el carrusel de Instagram y el 07 para el video. Ninguno de los dos está en
> git (`source_images/` está en `.gitignore`), pero sí podían acabar publicados.
>
> **Ya rescatados** en `~/fotos_rescatadas_video_generator/` (movidos, no borrados).

---

## Prueba end-to-end — `Test01` / Zinedine Zidane (3 ago 2026)

Primera corrida completa de los 8 pasos con todo aplicado. **Exit 0.** Costó **$0.2329**
(estimado: $0.267 — el contador de `estado.py` es fiable). fal fue el 79 % del gasto.

| | Antes (`Mundial16`) | Después (`Test01`) |
|---|---|---|
| Duración | 34.3 s | **24.5 s** |
| Velocidad de habla | 143 wpm | **162 wpm** |
| Guion | 90 palabras | **66** |
| Cortes visuales | 8 (1 cada 4.9 s) | **14 (1 cada 1.75 s)** |
| Bitrate | 2 418 kbps (original) | **4 745 kbps** |
| Sonoridad | −17.5 LUFS | **−14.1 LUFS** |
| Metadata YouTube | no existía | título 67/70, 12 tags, comentario |

**Lo que se confirmó funcionando:**

- **El frame 0 cambió por completo.** Antes: un contrato con texto inventado ilegible. Ahora: primer
  plano de Zidane con emoción legible. La regla de BUG-13 (escena 1 = close-up de rostro) se cumplió.
- **El gancho ya no spoilea**: *"El insulto que detuvo al mejor del mundo"* abre la pregunta sin
  contar el cabezazo.
- **`validar_con_vision()` rechazó 3 fotos**: una de Zidane que no era del Mundial (se quedó con
  `zidane wcf 2006.jpg`, la correcta) y dos del árbitro Elizondo, una de ellas una foto suya con
  Kirchner. Sin el filtro, esas tres habrían entrado.
- **La foto real que entró al video es la buena**: Zidane con la 10 de Francia en la final (seg. 12).
- `repartir_planos()` con 6 ilustraciones + 2 fotos = 8 fuentes → 14 cortes de 1.75 s.

**Lo que salió mal:**

- ❌ **El borde de pergamino seguía ahí.** El `no paper border, no frame` que le puse al `BASE_PROMPT`
  en la Fase 3 **no funciona**: los modelos de difusión ignoran las instrucciones negativas.
  Corregido recortando 8 % en el paso 07 (`recorte_borde_pct`), que es determinista. Verificado.
- ⚠️ **El guion coló un dato no verificable**: *"Su propia madre nunca volvió a ver aquel momento en
  video"*. Las reglas del paso 01 lo prohíben explícitamente y el modelo se las saltó.
  → **RESUELTO**: ver la sección de control de calidad, abajo.
- ⚠️ Una escena salió con camiseta roja (ni Francia ni Italia). El anclaje de `extract_context()`
  funciona en general pero no es perfecto.

---

### Cómo medir si funcionó

Antes de tocar nada, anota de los 16 videos actuales: **retención media**, **% de espectadores que
llegan a los 3 s** y **vistas a las 24 h**. Publica 5 videos con Fase 1+2 aplicadas y compara los
mismos tres números.

Si la retención a 3 s sube y las vistas no, el problema es la metadata (Fase 3).
Si ni siquiera sube la retención a 3 s, el problema es el gancho escrito, no el video.

---

## ✅ Control de calidad del guion (3 ago 2026)

Respuesta al fallo de la prueba: un segundo modelo audita el guion y, si no pasa, se reescribe.
Dos capas a propósito:

1. **`verificar_reglas_mecanicas()`** — Python, gratis, infalible. Palabras, longitud de la primera
   frase, inicios prohibidos, fechas, muletillas (`se dice`, `al parecer`, `supuestamente`…),
   frases largas. Clasifica en **graves** (fuerzan reescritura) y **leves** (van como feedback).
   A un LLM no se le pide que cuente palabras: lo hace mal y cobra por hacerlo mal.
2. **`evaluar_con_critico()`** — segundo modelo con rol de verificador escéptico. Solo juzga lo que
   necesita criterio: verificabilidad de cada afirmación, spoiler en la primera frase, línea
   narrativa única, drama honesto. Devuelve `nota` 0-10 + `afirmaciones_dudosas` textuales.

El bucle reescribe pasándole **los fallos concretos**, no reintenta a ciegas. Configurable en
`CONFIG`: `intentos_max` (3), `nota_minima` (7), `modelo_critico`, `abortar_si_ninguno_pasa`.

**Verificado sobre el guion que falló.** El crítico le puso 4/10 y marcó 3 afirmaciones dudosas —
la de la madre y dos más que no había detectado a ojo (atribuirle estados mentales a Zidane).

**Bucle completo sobre el mismo tema**, 3 intentos hasta converger:

| Intento | Nota | Qué pasó |
|---|---|---|
| 1 | baja | **Se inventó una historia entera**: un tal Serge Chiesa expulsado de un Mundial juvenil por un cabezazo, y una relación causal con Zidane. Falso de principio a fin |
| 2 | 4/10 | 6 afirmaciones dudosas (que nunca fue capitán antes — falso; escenas privadas en el túnel) |
| 3 | **8/10** | ✅ Aprobado. Primera frase de 8 palabras, y se apoya en hechos documentados (el cuarto árbitro, la repetición televisiva) |

Sin este control, el intento 1 se habría publicado como historia real.

**Coste:** 2 llamadas por intento → **$0.0193** en el peor caso frente a $0.0030 sin control.
Sobre un tema de $0.23 es un 7 %.

> ⚠️ **No es infalible.** El guion aprobado dice *"Zidane se marchó sin medalla"* y el propio crítico
> anotó que sí recibió la de subcampeón — pero lo clasificó como `problema` (estilo) y no como
> `afirmacion_dudosa`, así que no bloqueó. Baja el listón de lo que bloquea subiendo `nota_minima`
> a 9, o **sigue leyendo el guion antes de publicar**. Esto reduce mucho el riesgo, no lo elimina.

### Crítico en otro proveedor (3 ago 2026)

El crítico ahora corre en **`claude-opus-5`** (SDK `anthropic`), no en GPT. La razón no es que un
modelo sea mejor: es que **un modelo de la misma familia que el generador comparte sus puntos
ciegos**. Si `gpt-4.1` se cree una afirmación inventada al escribirla, tiende a creérsela al
revisarla. Otro proveedor falla de otra forma, y ahí está el valor de la segunda opinión.

`critico_proveedor: "auto"` usa Anthropic si hay `ANTHROPIC_API_KEY` y **cae a `gpt-4.1` si no**,
así que la clave es opcional y el pipeline nunca se rompe por su ausencia.

**Costo por tema (3 intentos), medido sobre una crítica real de 626 tokens de entrada y 311 de salida:**

| Crítico | $/tema | vs. un tema de $0.23 |
|---|---|---|
| `claude-haiku-4-5` | $0.0065 | **más barato que el crítico anterior** |
| `gpt-4.1` (anterior) | $0.0112 | — |
| `claude-sonnet-5` (intro, hasta 31-ago-2026) | $0.0131 | +0.8 % |
| `claude-sonnet-5` | $0.0196 | +3.6 % |
| **`claude-opus-5`** (elegido) | **$0.0327** | **+9 %** |

Detalles que importan al tocarlo:

- El JSON se fuerza con **structured outputs** (`output_config.format`), no por prompt: el modelo no
  puede devolver otra forma.
- En Opus 5 el **thinking está on por defecto** y `critico_max_tokens` (4096) limita
  thinking + respuesta *juntos*. Si se queda corto, el JSON sale truncado.
- `critico_effort` (`medium`) es la palanca de costo real, no el modelo. Súbelo si ves fallos de
  criterio antes de cambiar de modelo.
- Los clasificadores de Anthropic pueden declinar una petición: devuelve HTTP 200 con
  `stop_reason: "refusal"` y `content` vacío. Se comprueba **antes** de leer `content`.

> ⚠️ **Sin verificar contra la API.** No hay `ANTHROPIC_API_KEY` en este entorno, así que la ruta
> Anthropic **no se ha ejecutado ni una vez**: compila, el despacho por proveedor está probado y el
> respaldo a OpenAI está verificado (sigue cazando el dato de la madre, nota 5/10). Pero la primera
> corrida con clave es la prueba real — mira que el JSON no venga truncado y ajusta
> `critico_max_tokens` si hiciera falta.

---

## ✅ Métricas — resuelto (15 ago 2026)

La guía de dónde exportar, qué trae cada red y el paso a paso semanal vive en
**[README.md](README.md)**; los internos del consolidador, en **[CLAUDE.md](CLAUDE.md)**.
Lo que se montó:

- **[10_metricas.py](herramientas/10_metricas.py)** lee los exports **tal cual se descargan** (zips incluidos),
  normaliza los 5 formatos, empareja cada video con su `PROYECTO` por texto y consolida en
  `metricas.csv`. Al terminar archiva los crudos en `_procesados/<fecha>/`.
- **147 filas de 4 plataformas**, 42 videos de YouTube, 45 de Meta, 15 de TikTok.
- `lote` separa `baseline` de `v2-mas-cortes`. **Entran todos los videos publicados**, con
  `PROYECTO` reconocido o sin él: los anteriores al pipeline son justo la referencia, y
  descartarlos dejaba el baseline en 7 videos en vez de 36.
- `vistas_24h` / `vistas_7d` salen de la serie diaria del zip de YouTube, sin esperar a comparar
  dos snapshots.
- Lo que ninguna red exporta (retención de TikTok e Instagram) se teclea en `manual.csv`, que el
  script deja ya identificado. ~5 min por semana.

### Primera lectura (15 ago 2026)

| | lote | n | vistas | 24 h | retención | se quedaron | CTR |
|---|---|--:|--:|--:|--:|--:|--:|
| **YouTube** | baseline | 36 | 282 | 84 | 69.0 % | 48.5 % | 0.3 % |
| | **v2** | 6 | **1436** | **512** | **91.2 %** | 40.7 % | **2.3 %** |
| **Instagram** | baseline | 38 | 144 | | 31.6 % | | |
| | **v2** | 7 | **486** | | **38.7 %** | | |
| **Facebook** | baseline | 38 | 650 | | 19.9 % | | |
| | **v2** | 7 | **970** | | 21.9 % | | |
| **TikTok** | baseline | 12 | 669 | | 23.1 % | 13 % | |
| | v2 | 3 | 644 | | 28.0 % | 9 % | |

**Con las ventanas de 24 h la comparación ya no depende de cuántos días lleve publicado cada
video: 512 vistas contra 84 es 6×.** El CTR sube casi 8× (0.3 % → 2.3 %), y eso no es el video
sino los títulos que genera el paso 02.

⚠️ **`se_quedaron_pct` es la única métrica que va en contra** (48.5 % → 40.7 % en YouTube, 13 % →
9 % en TikTok) y ya no se explica por tiempo de exposición. Con n=6 puede ser ruido, pero apunta a
que los primeros 2 segundos empeoraron aunque quien se queda vea mucho más.
→ Es lo único de esta lectura que sigue abierto: **P-12** en [TODO.md](TODO.md).

---

## ✅ Fusión de los textos publicables (8 ago 2026)

`descripcion_general.txt` + `descripcion_detallada.txt` → **`descripcion.txt`**, un solo archivo.
Programar una semana en Metricool tiene que ser abrir un archivo por video, no dos.

Cinco secciones, con el pie del reel arriba porque es lo que más se copia:

```
TÍTULO (58/70 caracteres)
DESCRIPCIÓN GENERAL (pie del reel — las 4 redes)   ← + hashtags debajo
DESCRIPCIÓN LARGA (YouTube y Facebook) — n/1999    ← + hashtags debajo
TAGS DE YOUTUBE (separados por coma)
COMENTARIO A FIJAR
```

**Los hashtags van repetidos bajo cada descripción y sin encabezado propio.** Así se selecciona
descripción + hashtags de una pasada y se pegan juntos, con la que se vaya a usar ese día.

**Tope de 1999 caracteres** en el bloque *descripción larga + hashtags*. El prompt pide ≤1700 para
que casi nunca haga falta recortar, pero el que garantiza el límite es `recortar_a_limite()`, en
Python. Conserva **siempre el último párrafo** — ahí está la pregunta que invita a comentar — y del
resto salva las frases que quepan. Recortando párrafos enteros se perdían 490 caracteres para
ahorrar 53; por frases se pierden ~150. De los 8 temas del lote, 4 cabían tal cual y 4 se
recortaron entre 147 y 236 caracteres.

Siguen siendo **dos llamadas distintas** a GPT: la fusión ocurre al escribir, en
`escribir_descripcion()`. Los hashtags se separan del pie con `separar_hashtags()` — Python puro,
recorre las líneas desde el final y toma las que solo tienen tokens que empiezan por `#`. Probado
contra los 4 textos reales del lote y contra los casos límite (sin hashtags, repartidos en dos
líneas, texto vacío).

El paso 09 acepta los dos archivos viejos como alternativa (`textos_legado`) para no marcar
incompletos los respaldos anteriores, y **borra ambos formatos del destino antes de copiar**, para
que rehacer un paquete no deje el archivo viejo al lado del nuevo.

Los 9 respaldos ya producidos se migraron sin gastar una sola llamada, reconstruyendo el archivo
desde `metadata.json` + `descripcion_general.txt` con la misma función del paso 02.

---

## ✅ ffmpeg se comía los nombres de los temas (8 ago 2026)

Del primer lote real salieron `proyectos/a02/`, `proyectos/04/`, `proyectos/oria07/`. De 8 temas,
6 perdieron las primeras letras del `PROYECTO`, y con ellas los nombres de video, respaldo y log.

**Causa:** `run_all.sh` leía `temas.csv` por **stdin**, y ese stdin lo heredan todos los procesos
hijos. **ffmpeg lee stdin por defecto**, byte a byte, buscando teclas interactivas (la `q` para
abortar). Cada video terminado se comía unos bytes de la lista, y el siguiente `read` arrancaba a
media palabra. Reproducido en aislado:

```
── sin redirigir stdin        ── con stdin redirigido
  P='Historia01'                P='Historia01'
  P='ria02'                     P='Historia02'
  P='ria03'                     P='Historia03'
```

Engaña mucho: el síntoma parece que alguien editó el CSV a mitad de corrida.

**Tres defensas, todas puestas:**
1. El CSV se lee por el descriptor `9` (`done 9< <(tail ...)` con `read <&9`) — inalcanzable para
   los hijos.
2. `run_pipeline.sh` se invoca con `</dev/null`.
3. **`-nostdin` en las dos llamadas a ffmpeg** (pasos 03 y 08). Si se añade otra, ponerle `-nostdin`.

Los 6 proyectos afectados se renombraron (carpeta, mp3, srt, video sin música, video final, log) y
se corrigió `logs/failed.csv`, que tenía `oria07,Galeón` y así no servía para reintentar.

---

## ✅ Reorganización del código (15 ago 2026)

La raíz tenía 40 entradas en un solo nivel: 13 `.py`, 2 `.sh`, 5 notas, 2 csv, 6 archivos de estado
y 12 carpetas, desde fuentes tipográficas hasta 1.6 GB de video. Nada distinguía un paso del
pipeline de una herramienta suelta o de un script que ya no ejecuta nadie.

**Lo que se movió** — el código, y solo el código:

```
pipeline/       01…08 + estado.py                     ← lo que corre run_pipeline.sh
herramientas/   09_paquete_publicacion, 10_metricas   ← se corren aparte, no por tema
desuso/         03_voice_generator_free, publisher,
                ink_filter, imagen_generator_source   ← no los ejecuta nadie
```

Salió barato porque **ningún script referencia a otro**: se comunican solo por archivos. El cambio
completo fueron 11 líneas de código —8 en `run_pipeline.sh` (el prefijo lo pone ahora `run_step`),
2 en `run_all.sh` y 8 líneas de uso en los docstrings de 08, 09 y 10— más los enlaces de las notas.

Tres decisiones que conviene no revisitar:

- **`estado.py` vive en `pipeline/`, no en la raíz.** Al ejecutar `python pipeline/04_….py`, Python
  pone en `sys.path` el directorio **del script**, no el de trabajo. En la raíz sería invisible para
  los 6 pasos que lo importan.
- **El directorio de trabajo sigue siendo la raíz** (los dos `.sh` hacen `cd`), así que no cambió
  ni una ruta de datos: `script.txt`, `images_IA/`, `videos/` se resuelven igual que antes.
- **Los prefijos numéricos se quedan.** `01_`…`08_` codifican el orden de ejecución, que es el dato
  más útil del repositorio. No se pueden importar con la sentencia `import` (`SyntaxError`), pero sí
  con `importlib.import_module("02_social_media_generator")` — verificado. Los números **no son** lo
  que bloquea los tests; eso es el trabajo a nivel de módulo (P-11 en TODO.md).

**Lo que deliberadamente NO se movió: las carpetas de datos y salidas** (`images_IA/`,
`source_images/`, `social_posts/`, `videos*/`, `proyectos/`, `publicar/`, `logs/`). Están escritas
a mano en los `CONFIG` de los 11 scripts, en `.gitignore` y —lo caro— en los 30 respaldos ya
generados y en los hardlinks de `publicar/`. Sería tocar todo el pipeline para ganar estética.
**La comunicación por archivos en la raíz *es* la arquitectura.** Si algún día molesta de verdad,
la salida buena es el directorio de trabajo por tema (P-06), no un cambio de nombres.

**Verificado tras el movimiento:** `bash -n` sobre los dos `.sh`, `py_compile` sobre los 15 `.py`,
y una sonda ejecutada como en producción (`python pipeline/_sonda.py` desde la raíz) confirmando
que `from estado import …` resuelve a `pipeline/estado.py` y que `script.txt` sigue viéndose desde
el directorio de trabajo.

⚠️ **Efecto secundario en las celdas `#%%`.** En ejecución interactiva de VS Code el kernel arranca
con la raíz como cwd, así que `from estado import …` ya no resuelve solo. Antes de la primera celda:
`import sys; sys.path.insert(0, "pipeline")`. Ejecutando el archivo entero no hace falta.

---

## ✅ Informe de métricas y la trampa de la antigüedad (15 ago 2026)

`metricas.csv` tenía 147 filas × 28 columnas y nadie las miraba: los datos que costó consolidar no
decidían nada. [11_reporte.py](herramientas/11_reporte.py) los convierte en un HTML autocontenido
(stdlib, CSS incrustado) con el veredicto por lote, rankings, el seguimiento de `se_quedaron_pct` y
una tabla por red con **solo las columnas que esa red exporta**.

### El primer informe estaba mal, y el error era de método

La primera versión anunciaba esto:

```
facebook    📈 Vistas/día: +2493%   (n=7 vs 38)
instagram   📈 Vistas/día: +5591%   (n=7 vs 38)
```

Ningún cambio de pipeline multiplica por 56 nada. La causa:

| | v2-mas-cortes | baseline |
|---|---:|---:|
| Edad mediana | **4 días** | **66 días** |
| Vistas medianas (Instagram) | 486 | 144 |

La diferencia real de vistas es **3.4×**. `vistas_por_dia` dividía entre 4 en un lado y entre 66 en
el otro, regalando un factor 16× al lote nuevo por pura aritmética.

**La derivada partía de una premisa falsa: que las vistas se acumulan de forma lineal.** En video
social llegan casi todas en las primeras 48 h. Así que `vistas_por_dia` no quita el sesgo de
antigüedad —que era justo para lo que se diseñó— sino que **lo invierte y lo amplifica**.

### El arreglo: clasificar cada métrica por cómo se comporta con el tiempo

`TIPO_METRICA` decide qué entra en el veredicto:

| Tipo | Qué es | ¿Comparable entre lotes? |
|---|---|:--:|
| `ventana` | medida en una ventana fija (`vistas_24h`, `vistas_7d`) | ✅ la edad ya está igualada |
| `tasa` | cociente cuyas dos partes crecen juntas (retención, CTR, engagement) | ✅ se estabiliza pronto |
| `acumulativa` | crece mientras el video siga online (vistas, alcance, guardados) | ❌ con 4 d vs 66 d |
| `interna` | normalizada dentro de su propio lote (`retencion_relativa`) | ❌ daría 0 % por construcción |

Lo no comparable **no se esconde**: va a un bloque "fuera del veredicto" con el motivo escrito. Un
número que se oculta acaba recalculándose a mano y peor.

### Lo que queda cuando se aplica la disciplina

```
youtube    📈 Vistas 24 h     +513%   (n=6 vs 34)      ← ventana fija: comparación limpia
youtube    📈 CTR %           +785%   (n=6 vs 36)
youtube    📈 Retención %      +32%   (n=6 vs 34)
youtube    📉 Se quedaron %    -16%   (n=6 vs 34)
tiktok     📉 Se quedaron %    -31%   (n=3 vs 8)   ⚠ n baja
facebook   📈 Engagement %     +27%   (n=7 vs 38)
instagram  📉 Engagement %      -8%   (n=7 vs 38)
```

Sigue siendo una mejora grande y ahora es defendible. Y **P-12 queda confirmado en las dos redes
que exportan `se_quedaron_pct`**, no solo en YouTube: es el único indicador que va en contra.

⚠️ Que YouTube sea la red que más dice no es casualidad: es la única que da ventanas fijas. En las
demás, comparar acumulados exige **dos fotos** (`fecha_snapshot`) y restar el mismo periodo.

---

## ✅ El `.env` corrompido por un título de dos líneas (15 ago 2026)

Al preparar el reintento de `Historia07`/`Historia08` apareció esto al final del `.env`:

```
TITULO_VIDEO="El cerebro de Einstein desapareció tras su muerte"

Buscaban comida y hallaron gigantes caníbales

La flota entera fue aniquil"
```

`save_to_env()` escribía `f'{key}="{value}"'` sin sanear. El título de `Historia07` (Galeón) traía
saltos de línea, así que la entrada ocupó tres líneas del archivo. En la corrida siguiente
(`Historia08`), el bucle —que corta en el **primer** `startswith`— reemplazó solo la primera y dejó
las otras dos sueltas.

**Por qué importa: `run_pipeline.sh` hace `source .env`, o sea que ese archivo lo lee bash.** Esas
líneas sueltas son comandos. Hoy fallaban con "command not found" y, con `set -e`, abortaban el
pipeline en modo standalone; pero dentro de comillas dobles bash interpreta `$`, `` ` `` y `\`, así
que **un título con `$(...)` se habría ejecutado**. Es una ruta por la que la salida de un LLM llega
a un shell.

Arreglo: `sanear_valor_env()` colapsa los saltos de línea a espacios y **elimina** `"`, `$`,
`` ` `` y `\`. Se eliminan en vez de escaparse porque ninguno tiene sentido en un texto que va
quemado en el frame 0 de un video, y así no hay regla de escapado que pueda estar mal puesta.

### Y de paso: `logs/failed.csv` se comía el primer tema

Las notas decían que `failed.csv` "sirve tal cual como `temas.csv`" para reintentar. No era verdad:
se escribía **sin encabezado**, y el bucle de `run_all.sh` salta la primera línea (`tail -n +2`).

```
$ tail -n +2 logs/failed.csv        # lo que run_all.sh habría leído
Historia08,Einstein                 # Historia07 desaparecido en silencio
```

Con los dos temas caídos dentro, `cp logs/failed.csv temas.csv && bash run_all.sh` solo habría
reintentado Einstein — y sin avisar. Se arregló escribiendo el encabezado al crear el archivo, que
hace verdadera la frase de las notas en vez de documentar la trampa.

---

## ✅ El veredicto de calidad acusaba a otro guion (15 ago 2026)

Al reintentar `Historia08` (Einstein), `proyectos/Historia08/calidad_guion.json` decía:

```json
"nota": 6,
"afirmaciones_dudosas": [
  "Einstein ofreció su cerebro... por correo.",
  "accidió a que su cerebro fuera preservado tras su muerte."
]
```

Pero `script.txt` no habla del cerebro de Einstein: habla de que suspendió el examen de ingreso de
la escuela técnica de Zúrich. **El veredicto describía un guion que nunca se usó.**

`escribir_guion_con_control()` guarda el mejor intento…

```python
if nota_final > mejor_nota:
    mejor, mejor_nota = script, nota_final     # el guion sí
```

…pero registraba el veredicto de la variable `veredicto`, que al salir del bucle contiene el del
**último** intento:

```python
registrar_calidad(False, cfg["intentos_max"], veredicto)   # ← el del intento 3
return mejor                                               # ← puede ser el del 1
```

Cuando el mejor guion no era el último probado —que es el caso normal, porque el bucle reescribe
hasta 3 veces y la nota no siempre sube— los dos archivos se contradecían.

**Por qué importa más de lo que parece:** el paso 09 imprime esas `afirmaciones_dudosas` al
empaquetar, para que se revisen antes de publicar. Así que mandaba a comprobar frases que el video
no dice, y **callaba los problemas reales del guion que sí se publica**. Un veredicto equivocado es
peor que ninguno: se revisa lo que no toca y se aprueba lo que sí.

Arreglo: el veredicto viaja con el guion (`mejor_veredicto`, `mejor_intento`), y el aviso de
consola imprime lo que se le objetó **a ese** guion. De paso, el campo `intento` del JSON pasa a
significar "de qué intento salió el texto que se publica" en vez de "cuántos se hicieron", que es
la pregunta que uno se hace al abrir el archivo.

⚠️ Los `calidad_guion.json` de `Historia07` y `Historia08` se escribieron **antes** del arreglo, así
que siguen acusando al guion equivocado. Regenerarlos exigiría volver a correr el paso 01, que
escribiría un guion distinto: no compensa. Léelos contra el `script.txt` de su carpeta.

---

## ✅ El recordatorio semanal por Telegram (15 ago 2026)

El pipeline es semanal pero no avisaba de nada: si se pasaba un domingo, la semana se caía sola.
[12_recordatorio.py](herramientas/12_recordatorio.py) lo cubre. Bot `@CHvideo_bot`, primer mensaje
enviado el 15 ago.

**No es una alarma de calendario.** Mira el estado real del repositorio —`logs/failed.csv`, los
`calidad_guion.json`, `publicar/calendario.csv`, la `fecha_snapshot` máxima de `metricas.csv`— y
**calla si no hay nada que decir**. Un bot que escribe todos los domingos aunque no pase nada se
silencia a la tercera semana, y entonces tampoco avisa el día que importa. Ninguna API salvo la de
enviar: todo lo que consulta son archivos que ya existen.

**Importa `11_reporte.py` con `importlib` en vez de recalcular.** El nombre empieza por dígito, así
que no se puede `import` normal. Es deliberado: el informe ya descarta lo no comparable, y un
resumen que rehiciera las cuentas mandaría cada domingo un "+2493 % en vistas por día" que solo
mide la antigüedad de los videos.

### Tres entradas de cron que no son tres mensajes

```
0 10 * * 0    → domingo 10:00, el aviso principal
0 16 * * 0    → domingo 16:00, segundo toque
0 10 * * 1-6  → lunes a sábado, con --si-falta
```

Como el script calla cuando no hay pendientes, en una semana limpia no llega ninguno.

La tercera existe porque **cron no dispara con el equipo apagado**, y ese aviso se perdería sin
dejar rastro. `--si-falta` no hace nada si ya se envió algo esa semana, así que solo salta cuando
el domingo no hubo máquina.

⚠️ Dos detalles de los que depende que la recuperación funcione:
- **`anotar_envio()` se llama solo cuando Telegram confirma**, no al intentarlo. Si se anotara
  antes, una caída de red el domingo marcaría la semana como avisada y la recuperación no
  dispararía — justo el caso para el que existe.
- **La semana empieza el domingo** (`dia_inicio_semana`, 6), igual que el cron. Si se mueve el
  horario a otro día hay que mover eso con él, o la recuperación cuenta mal la semana.

Se verificó ejecutando la orden con el entorno pelado de cron (`env -i` con solo `PATH` y `HOME`),
que es donde fallan estas cosas: cron no hereda tu shell, así que sin `PATH` explícito no encuentra
el python del entorno conda.

`herramientas/obtener_chat_id.sh` saca el `chat_id` leyendo el token del `.env`, para no tener que
abrir en el navegador una URL que lleva el token dentro y leer el JSON a mano.

---

## ✅ Los planos dejan de salir en pares (15 ago 2026)

`create_video()` recorría las imágenes en orden y encadenaba todos los sub-planos de cada una
seguidos. Sobre un reparto real de 6 imágenes y 14 planos:

```
A1 A2 A3  B1 B2  C1 C2  D1 D2 D3  E1 E2  F1 F2     ← 8 de 13 transiciones repiten imagen
A1 B1 A2 B2 A3  D1 C1 D2 C2 D3  E1 F1 E2 F2        ← 0 de 13
```

**El problema no era el número de cortes, era que no se percibían.** Dos encuadres seguidos de la
misma ilustración se leen como un zoom, no como un corte nuevo, así que más de la mitad de los
cortes que contaba `repartir_planos()` no contaban para el espectador. Cuesta cero: no genera más
imágenes ni cambia la duración, solo el orden en que se colocan los clips.

### Por qué no se baraja

Las imágenes las genera el paso 04 **en orden narrativo** a partir de las escenas del guion: la 1
ilustra la primera frase y la última el desenlace. Un barajado global pondría el final en el
segundo 3 y rompería la sincronía entre lo que se oye y lo que se ve — peor que el problema que
resuelve.

`dispersar_planos()` intercala **solo entre imágenes vecinas** (`ventana_dispersion`, 2), así que
una imagen se adelanta o atrasa un plano (~1.8 s) y nada más. Dentro de cada ventana usa el voraz
clásico "el que más planos le quedan, distinto del anterior", que evita el `A1 B1 A2 B2 B3` que
deja un round-robin simple cuando una imagen tiene más planos que su vecina.

⚠️ **El primer plano del video es siempre la imagen 1.** El voraz, si esa imagen tiene menos planos
que su vecina, abriría por la segunda — y el frame 0 es el que lleva el título quemado y el que
decide si te quedas.

Se apaga con `dispersar_planos: False`, que restaura el orden clásico exacto. No es decorativo:
es lo que permite aislar el efecto al medir P-12.

**Dos fallos que encontró la prueba antes que un render:**
- `grupos[-2] += grupos.pop()` para fusionar una ventana suelta. Python evalúa el `pop()` **antes**
  de asignar, así que el índice `-2` ya apunta a otro grupo y el resultado se escribía encima del
  anterior: con 5 imágenes se comía las dos primeras y duplicaba las últimas. En dos sentencias.
- El voraz abría el video por la imagen 2 cuando el reparto era desigual.

---

## ✅ Los títulos de YouTube caben (15 ago 2026)

4 de los 8 primeros temas pasaban de 70 caracteres, entre 1 y 12 de más:

| Tema | Chars | Título |
|---|---:|---|
| Historia07 | 82 | Santísima Trinidad y Nuestra Señora del Buen Fin: el gabinete oculto del naufragio |
| Historia01 | 77 | Samsung y el Vuelo CZ3539: La Explosión en las Alturas que Cambió la Aviación |
| Historia05 | 74 | San Lorenzo: el tesoro de Roma que desapareció ante los ojos del emperador |
| Historia03 | 71 | Ulises y los Lestrigones: el naufragio olvidado tras la guerra de Troya |

El paso 02 avisaba y escribía el título largo igual, así que YouTube lo cortaba en la búsqueda: lo
que sobra no se ve feo, **no se ve**.

**Aquí sí se vuelve a llamar al modelo**, al revés que en `recortar_a_limite()`. Un título truncado
a machete pierde el gancho, que es exactamente lo que hace que lo cliqueen; reescribir es lo único
que lo conserva. `acortar_titulo()` pide una reescritura (hasta 2 intentos; el segundo le dice
cuánto se pasó el primero) y **Python sigue garantizando el límite** con `_truncar_titulo()` si aun
así no cabe. Solo cuesta cuando hace falta: si el título ya cabe, no llama a nada.

Resultado sobre los cuatro reales:

```
82 → 58  Santísima Trinidad y Buen Fin: el enigma tras su naufragio
77 → 64  Samsung y el Vuelo CZ3539: El Misterioso Incidente en Pleno Aire
74 → 66  San Lorenzo: el tesoro de Roma que se desvaneció ante el emperador
71 → 62  Ulises y los Lestrigones: el naufragio tras la guerra de Troya
```

El de 82 necesitó el segundo intento: el nombre del galeón ocupa 47 caracteres él solo, y sin
permiso explícito para acortar el nombre propio no hay forma de que quepa.

⚠️ **Se acorta en `guardar_descripciones()`, no al escribir el archivo.** El título sale por dos
caminos —`descripcion.txt`, que es lo que copias, y `metadata.json`, de donde lo lee el paso 09— y
acortarlo solo al escribir el primero dejaba el mismo video con **dos títulos distintos** según
dónde miraras. El paso 10 además empareja las métricas por ese texto.

`_truncar_titulo()`, el último recurso, corta en un límite de cláusula (`:`, `—`, `,`) antes que por
longitud, y quita las palabras vacías del final: un corte a pelo dejaba títulos que acaban en
*"que Cambió la"* o *"ante los ojos del"*, y eso se lee como un error, no como un título corto.

---

## ✅ El composite fantasma del paso 07 — ×1.59 (15 ago 2026)

Estaba anotado como **hallazgo sin confirmar**: "medí hasta 2× de mejora, y solo aparece si se
corrigen los dos composites a la vez, pero no me fío del número". Re-medido con la máquina quieta,
**las dos afirmaciones eran falsas** — el efecto es 1.59×, no 2×, y **solo hay que corregir uno**.

### El mecanismo, leído en la fuente de moviepy

```python
transparent = (bg_color is None)          # ← el default
...
if transparent:
    maskclips = [...]
    self.mask = CompositeVideoClip(maskclips, self.size, ismask=True, bg_color=0.0)
```

Con `bg_color=None`, moviepy 1.0.3 monta **un segundo composite entero solo para la máscara alfa**.

Lo que decide si eso cuesta o no es `blit_on()`:

```python
mask = self.mask.get_frame(ct) if self.mask else None
```

O sea: la máscara de una capa se evalúa **cuando alguien pega esa capa encima de otra cosa**. Por
eso solo importa el composite **interior** (el de los planos, línea ~651): el composite final lo
pega como capa, y en cada frame se compone dos veces — una la imagen y otra una máscara que el mp4
tira igual, porque libx264 no lleva canal alfa.

El composite **exterior** (línea ~1124) también construye su máscara, pero **nadie la consume**:
`final` no se pega sobre nada, se exporta. Construirla es gratis; evaluarla es lo que cuesta, y no
se evalúa nunca. **Tocarlo no habría hecho nada.**

### Lo medido

Máquina quieta, 5 rondas intercaladas para cancelar deriva:

```
ronda 1:  actual 3.29 fps   con bg_color 5.37 fps
ronda 2:  actual 3.29 fps   con bg_color 5.25 fps
ronda 3:  actual 3.23 fps   con bg_color 5.07 fps
ronda 4:  actual 3.19 fps   con bg_color 5.11 fps
ronda 5:  actual 3.20 fps   con bg_color 5.12 fps
MEDIANA   3.23 → 5.12 fps   ×1.59
```

La varianza es mínima (±0.05 y ±0.15), al contrario que la medición vieja, que corrió peleando por
los mismos 4 hilos que un render de producción y por eso se contradecía consigo misma.

**Corrección verificada píxel a píxel**: la máscara vale exactamente 1.0 en todos los píxeles
—los planos cubren siempre el cuadro completo, así que el fondo no se ve nunca— y la salida es
idéntica. En tiempo de pared, el paso 07 pasa de ~7m 34s a ~5m 50s: **~14 minutos por lote de 8.**

⚠️ **La primera comparación de píxeles dio "difieren hasta 255/255"**, y era falsa alarma del
método, no del cambio: [07_video_generator.py:590](pipeline/07_video_generator.py#L590) sortea el
zoom de cada plano con `random.uniform()` **sin semilla**, así que dos llamadas a `create_video()`
dan encuadres distintos. Con `random.seed()` fijado, la diferencia es cero. Si algún día hace falta
comparar dos renders, hay que sembrar la semilla o no se compara nada.

---

## ✅ Paralelizar los temas: evaluado y descartado por ahora (15 ago 2026)

La nota decía que el lote pasaría de ~1h50m a ~50 min. Medido, no sale:

| Medición | Resultado |
|---|---|
| CPU del paso 07 | **203 % de 400 %** — dos renders saturan la máquina |
| RAM pico del render | **1.35 GB**, más ~1.5 GB del modelo whisper `medium` |
| RAM libre con el escritorio abierto | ~5 GB de 11 GB |
| Recursos de la raíz en colisión | 5 |

Con 203 % por render, dos temas en paralelo no dan 2×; y en RAM van justos.

**Y el bloqueo real no era el que decía la nota.** No son las carpetas —eso se arregla con un
directorio de trabajo por tema, y sale barato porque *todas* las rutas del pipeline son relativas
al directorio de trabajo—, sino que **`.env` es el transporte entre pasos**: el 02 escribe
`TITULO_VIDEO` y el 07 lo lee. Dos temas a la vez y el 02 del segundo pisa el título antes de que
el 07 del primero lo lea; ese texto va quemado en el frame 0.

⚠️ Y un directorio por tema **no lo arregla**, porque `load_dotenv()` busca el `.env` subiendo
desde la carpeta del script, no desde el directorio de trabajo.

El requisito previo es barato y vale por sí solo: que el título viaje por
`social_posts/metadata.json`, donde el paso 02 **ya lo escribe**, en vez de por un archivo que lee
`bash` — el mismo que ya dio el susto de la prosa ejecutable.

**Veredicto:** techo real ~25-35 %, a cambio de reescribir `run_all.sh`, que es la pieza con más
historial de bugs sutiles. P-19 (partir el `DELAY` del paso 05 por fuente) da un tercio de esa
ganancia tocando una constante.

---

## ✅ El generador aprende de los veredictos (15 ago 2026)

Con el crítico de Anthropic ya funcionando, la pregunta pasó a ser cómo hacer que el generador
aprenda de sus aciertos y rechazos **sin gastar más**. Leer los 8 `calidad_guion.json` acumulados
dio el diagnóstico:

| Patrón que objeta el crítico | Ejemplos reales | Temas |
|---|---|---|
| Atribuir mentes y actos privados | *"Nadie había imaginado…"*, *"aprovechar el temor colectivo"* | 01, 02, 07 |
| Superlativos y absolutos | *"el más popular de Roma"*, *"ninguna escapó"*, *"siguen extraviados"* | 03, 05, 07, 08 |
| Cifras concretas sin respaldo | *"veinte sirvientas"*, *"millones en plata"* | 03, 07 |
| Dramatización poética | *"como si pescaran sardinas"*, *"como un secreto incómodo"* | 02, 06, 07, 08 |
| El gancho adelanta el desenlace | — | 05, 08 |

**El hallazgo que decidió el diseño: el prompt YA prohíbe todo eso en prosa** —«prohibido atribuir
pensamientos», «prohibido exagerar», «la primera frase no revela el desenlace»— y el generador lo
incumple igual. Añadir más reglas no arregla nada. Así que se hicieron dos capas distintas:

### Capa 1 — gratis, en Python

`"Nadie esperaba"` aparece en tres guiones distintos y el crítico lo objeta las tres veces. Eso no
necesita contexto: es una expresión regular. `ABSOLUTOS`, `SIMILES` y `VERBOS_MENTE` se comprueban
en `verificar_reglas_mecanicas()` — **cero tokens, y antes de pagar la crítica**.

⚠️ Van como **leves**, no graves: *"nunca robó a los ricos"* estaba en el único guion aprobado, así
que un absoluto puede ser perfectamente verificable. Como leve entra en la reescritura sin bloquear;
como grave habría tirado el mejor guion del lote.

Validado contra los guiones reales: `Historia07` (4/10) dispara los tres patrones y caza justo lo
que objetó el crítico; el aprobado saca un único aviso leve.

### Capa 2 — ~200 tokens, solo en el primer intento

`lecciones_de_guiones_previos()` destila el histórico en frecuencias («afirmaciones sin fuente — 14
veces») más **un guion propio que sí pasó**.

⚠️ **No se le pasan las frases rechazadas, y es deliberado.** Un ejemplo concreto es la señal más
fuerte de un prompt: el modelo imita su tono, su longitud y su estructura. Enseñarle "no escribas
*como si pescaran sardinas*" es enseñarle a escribir símiles. Por eso van frecuencias —que
reorientan la atención hacia reglas que ya tiene— y ejemplos **positivos**, que sí se pueden imitar.

Va solo en el intento 1: en una reescritura ya hay feedback específico sobre ese guion, que vale
más que una estadística y no conviene diluir.

**Requisito previo:** `script.txt` vive en la raíz y lo pisa el tema siguiente, así que los guiones
**aprobados** se perdían — la mitad útil del histórico. Ahora el texto se guarda dentro de
`calidad_guion.json`, junto a su nota. Los 8 anteriores se recuperaron de `logs/`, tomando de cada
log el intento que dice el propio json (el guion aprobado de `Historia04` era el intento 3, no el 1).

### El coste, medido y no estimado

| | Antes | Ahora |
|---|---:|---:|
| Bloque de lecciones | — | 209 tokens = **$0.00042** por tema |
| Crítica (`effort: low`) | $0.003 (gpt-4.1) | **$0.029** (Opus 5) |
| Control de calidad por tema | ~$0.019 | **~$0.10** |

La capa 1 es gratis y ahorra dinero (cada reintento evitado son $0.029). La capa 2 cuesta cuatro
diezmilésimas. **Lo que subió el costo no fue el aprendizaje: fue cambiar de crítico**, y `effort:
"low"` recorta un 26 % sobre `medium` con la misma nota y las mismas objeciones.

### Lo que rompió el cambio de crítico

Opus comprime **todas** las notas entre 2 y 3, así que la nota dejó de distinguir un intento de
otro y «el mejor de 3» se volvía casi aleatorio. El número de afirmaciones dudosas sí discrimina en
esos datos (3 en el mejor guion, 7 en el peor), así que `nota_final` le resta `0.1 × dudosas` como
desempate — un peso lo bastante bajo para no invertir nunca una diferencia real de nota.

Y el umbral quedó inalcanzable: ver [P-04](TODO.md#p-04).

---

## ✅ El guionista sube a gpt-5.4 (15 ago 2026)

El proyecto llevaba 16 meses escribiendo con `gpt-4.1` (abril 2025) sin que nadie mirara si había
algo mejor. La cuenta tiene acceso hasta `gpt-5.6`.

La pregunta de partida era otra —«¿y si escribimos directamente con Opus?»— y midiendo salió que
no. Todo sobre el mismo tema (*el faro de Eddystone*), juzgado por el mismo crítico de Opus 5:

| Escritor | Nota | Dudosas | $/guion | Proveedores distintos |
|---|---:|---:|---:|:--:|
| `gpt-4.1` | 2/10 | 6 | $0.0026 | ✅ |
| `claude-opus-5` | 5/10 | 4 | $0.0123 | ❌ |
| **`gpt-5.4`** | **6/10** | **2** | **$0.0040** | ✅ |
| `gpt-5.5` | — | — | **$0.0854** | ✅ |

`gpt-5.4` gana a los dos, incluido Opus, por $0.0014 más que el modelo viejo — y mantiene la
independencia de proveedor que P-04 acababa de comprar.

**Por qué NO escribir con Opus, que era la idea original:** la generación es solo el **9 %** del
costo del control de calidad ($0.009 de $0.096); el 91 % es el crítico. Cambiar el generador para
ahorrar ataca el lado pequeño de la cuenta, y Opus escribiendo cuesta 3× lo que `gpt-5.4`. Tampoco
puede recuperarlo evitando reintentos, porque **la puerta de aprobación es inalcanzable** y el bucle
corre los 3 intentos escriba quien escriba.

⚠️ **`gpt-5.5` es la misma trampa que el thinking de Opus**: razona antes de responder y esos tokens
se facturan como salida. Medido, **2560 tokens de razonamiento para 137 de texto** — $0.085 por
guion, 33× `gpt-4.1`, más caro que escribirlo con Opus, y 35 s frente a 2. Un modelo «más
inteligente» puede salir carísimo por dónde factura, no por lo que cobra el token.

**El calibre de los guiones se ve en el contenido, no solo en la nota.** Sobre el faro de Eddystone,
`gpt-4.1` inventó a *«un cirujano, John Smeaton»* (era ingeniero civil); `gpt-5.4` y Opus contaron
los dos la historia real de Henry Winstanley, que murió dentro de su propio faro en la gran tormenta.

⚠️ **Trampa al cambiar de modelo:** `registrar_openai()` hace `if not precio: return`, así que un
modelo que no esté en `PRECIOS_OPENAI` **no se cobra y `.costo_actual.json` miente en silencio**.
Los precios se añadieron desde la página oficial antes de tocar el modelo, y la prueba comprobó que
el costo se registrara ($0.0039, contra los $0.0040 estimados).

Los pasos 02, 04 y 05 se quedan en `gpt-4.1`: son extracción mecánica, no criterio.

⚠️ Todo esto es **n=1**: un tema, una comparación por modelo. Suficiente para decidir un cambio de
$0.0014, no para dar por hecho el salto de calidad. El próximo lote lo confirma o lo desmiente.

**Confirmado el 15 ago** con el lote `Historia09`-`Historia15`: ver
[la puerta calibrada](#-la-puerta-de-calidad-calibrada-con-datos-reales-15-ago-2026).

---

## ✅ La puerta de calidad, calibrada con datos reales (15 ago 2026)

La nota de P-04 decía «no lo ajustes a ojo, corre el próximo lote y mira la distribución». Se hizo.
Sobre los 7 temas de `Historia09`-`Historia15`:

| Tema | nota | dudosas | ¿pasa? |
|---|---:|---:|:--:|
| Historia14 La Odisea | **8** | **0** | ✅ |
| Historia13 Arqueología Aérea | 7 | 2 | ✅ |
| Historia11 Caminos Incas | 6 | 2 | ✅ |
| Historia12 Gran Muralla | 6 | 3 | ✅ |
| Historia15 Pompeya | 6 | 3 | ✅ |
| Historia10 Bomberos Romanos | 6 | 4 | ❌ |
| Historia09 Naufragio Romano | 5 | 4 | ❌ |

**El umbral nunca fue el problema: era el guionista.** Con `gpt-4.1` escribiendo, Opus comprimía
todas las notas entre 2 y 3 y no aprobaba nunca; con `gpt-5.4` el rango subió a 5-8 **sin tocar el
umbral**. Se diagnosticó como «el crítico es muy duro» y era «el texto era malo».

Dos hallazgos que no se ven sin la distribución:

**1. `nota_minima` no filtra nada.** Cinco de siete empatan en 6, y con `dudosas <= 3` salen los
mismos aprobados se mire la nota o no. Se conserva como suelo barato, pero **quien decide es
`dudosas_max`**. Afinar la nota es perder el tiempo.

**2. `dudosas_max` va a 3, no a 2.** A 2 se caían `Historia12` y `Historia15`, y sus «dudosas» son
**datos documentados**: la panadería de Modestus con sus 81 panes carbonizados, y las colonias
militares agrícolas de la dinastía Ming. El crítico las marca porque `SYSTEM_CRITICO` le ordena
literalmente *"ante la duda, marca la afirmación como dudosa"* — **el sesgo al rechazo es de
diseño y el umbral tiene que compensarlo.** Los que fallan de verdad traen 4: `Historia09` decía
*"lujo romano"* de una carga que era griega.

> ⚠️ **Hipótesis descartada.** Se predijo que `La Odisea`, `Gran Muralla`, `Pompeya` y
> `Caminos Incas` puntuarían peor por ser categorías y no incidentes concretos. Medido: los
> «concretos» dan mediana 6 con 4 dudosas y los «categoría» mediana 6 con 3 — **La Odisea sacó la
> mejor nota del lote**. No hay tal efecto en estos datos, y README ya no lo afirma.

---

## ✅ El flujo se vuelve automático: la puerta aborta (15 ago 2026)

Hasta aquí, un guion que no pasaba el control **se usaba igual con un aviso ruidoso**, y alguien
debía leerlo antes de programarlo. Al decidir que el flujo sea automático, ese diseño se vuelve
peligroso: **un aviso solo sirve si alguien lo lee**, y nadie iba a leerlo.

Se revisaron los 8 guiones publicados de `Historia01`-`Historia08` leyéndolos desde los `.srt`
—que son la transcripción de la voz, o sea el texto real— y dos afirmaban cosas falsas:

| | Qué decía | Qué pasó de verdad |
|---|---|---|
| Historia07 | un galeón explotó por su propia pólvora | La *Santísima Trinidad y Nuestra Señora del Buen Fin* (1751), el mayor galeón de Manila, fue **capturada por los ingleses en 1762** y vendida en Portsmouth. El «gabinete secreto» está inventado |
| Historia06 | Breton encerró a artistas, cortó la electricidad, solo él tenía fósforos | Nada de eso aparece en el registro documentado del surrealismo |

⚠️ **Y los `calidad_guion.json` de ese lote NO juzgan los guiones que se publicaron**: se generaron
el 15 ago midiendo Opus contra gpt-4.1, y su campo `guion` trae el texto de aquella prueba. Se ve
comparando con `social_posts/metadata.json`: el JSON de `Historia02` habla de Psamético III y el
video se llama *Batalla de Halys*. **La fuente fiable de qué se publicó es el `.srt`.**

**El arreglo: `abortar_si_ninguno_pasa: True`.** Lo que no pasa la puerta no llega a ser video.

- No corta el lote: `run_pipeline.sh` aborta **ese** tema, `run_all.sh` lo anota en
  `logs/failed.csv` —reusable tal cual como `temas.csv`— y sigue con el siguiente.
- Aborta en el **paso 01**, el primero: se tiran ~$0.09 de control de calidad, no los $0.18 de
  imágenes ni la voz.
- `intentos_max` sube de 2 a **3**, porque ahora agotar los intentos cuesta el tema entero y no un
  aviso: $0.043 contra perder un hueco del calendario.
- La decisión se extrajo a `cumple_la_puerta()` para poder testearla, y un test **congela**
  `abortar_si_ninguno_pasa: True`.

Simulado sobre `Historia09`-`Historia15`: **5 videos y 2 a `failed.csv`**, que son justo los dos con
afirmaciones falsas. Consecuencia operativa: **pedir 9-10 temas para obtener 7.**

---

## ✅ Los primeros tests: 98, y verificados por mutación (15 ago 2026)

**Por qué estos y no otros.** En el pipeline un error se nota: el tema aborta o el video sale mal y
se ve. En `10_metricas.py` y `11_reporte.py` **no se nota nada** — el informe se genera igual, se ve
bien y afirma lo contrario de lo que pasó. Es el peor fallo del repositorio y el único invisible.

| Archivo | Qué cubre |
|---|---|
| `test_reporte.py` | `comparar_lotes()`, `TIPO_METRICA`, el signo de la comparación, mediana vs promedio, y que los nombres de lote del paso 10 y del 11 no diverjan |
| `test_metricas.py` | la pegajosidad del lote, el índice a dos niveles, los decimales de Facebook, la fila de TikTok sin escapar, la curva de retención |
| `test_estado.py` | el sello del tema, los reintentos, y **que todo modelo nombrado en `pipeline/` esté en `PRECIOS_OPENAI`** |
| `test_pipeline.py` | `cumple_la_puerta()`, `verificar_reglas_mecanicas()`, `sanear_valor_env()`, `separar_hashtags()`, `recortar_a_limite()`, `_truncar_titulo()`, `repartir_planos()`, `dispersar_planos()` |

**Verificados por mutación**, que es lo que distingue un test de un adorno: se reintrodujo cada bug
—`grupos[-2] += grupos.pop()`, el voraz eligiendo el primer plano, `dispersar_planos: False`
ignorado, `sanear_valor_env()` sin recolapsar, los absolutos como graves, la pegajosidad del lote,
`vistas_por_dia` como tasa, el signo invertido, media en vez de mediana— y en cada caso fallan los
tests que le tocan **y solo esos**.

> ⚠️ **Corrección a lo que decía la nota de P-11:** el obstáculo NO obliga a mover las guardas de
> cada paso a `main()`. Los pasos sí trabajan al importarse, pero se resuelve **desde fuera**:
> `chdir` a un temporal (sin sello, `verificar_estado()` vuelve sin abortar y ningún `open()`
> relativo toca el tema en curso), claves de API **falsas** (los clientes se instancian pero no
> llaman a nadie) y `pipeline/` en `sys.path` (por el `from estado import …`). No se modificó ni
> una línea de `pipeline/`, y los tests corren **con un lote en marcha**.

---

## ✅ El lote se degradaba solo al cambiar `temas.csv` (15 ago 2026)

Encontrado sin buscarlo, al correr el paso 10 después de cargar los temas nuevos.

`lote` —la única columna con la que se comparan las tandas— se **recalculaba** en cada corrida a
partir de `temas.csv`. Y `temas.csv` cambia cada semana. Consecuencia: al cargar
`Historia09`-`Historia15`, los `Historia01`-`Historia08` dejaron de estar en el archivo y
**cayeron a `baseline` en silencio**:

| | Antes | Después |
|---|---:|---:|
| filas `v2-mas-cortes` | 23 | **4** |
| comparación del informe | n=6 vs 34 | **n=1 vs 44** |
| `se_quedaron_pct` en YouTube | −16 % | **+33 %** |

O sea: el informe pasó a afirmar **lo contrario** de lo real, sin avisar de nada.

**El arreglo es `lotes_ya_asignados()`, y la regla es asimétrica a propósito:**

- **Nunca degrada** un lote con nombre → la historia no se reescribe.
- **Sí promueve** desde `baseline` → un video que entró sin emparejar y luego reconoce su
  `PROYECTO` sube al lote que le toca.

`baseline` funciona aquí como el valor «vacío», igual que en el resto de la fusión, que tampoco
pisa nunca un valor lleno con uno vacío. Un video pertenece a la tanda que lo produjo, no a la que
esté cargada hoy.

⚠️ **Y hay que subir `lote_nuevo` al cargar un `temas.csv` con cambios de pipeline detrás**, o dos
tandas comparten nombre y dejan de distinguirse. Hoy: `v2-mas-cortes` (Historia01-08) y
`v3-guion-y-dispersion` (Historia09-15).

⚠️ De la misma familia: `11_reporte.py` tiene su propio `CONFIG["lote_nuevo"]` escrito a mano, con
un comentario que dice «si allí cambian, aquí también» y nada que lo compruebe. Hay un test que
falla si divergen.

---

## ✅ El archivo `T1/` era invisible para las métricas (15 ago 2026)

`indice_proyectos()` del paso 10 recorría `proyectos/*/social_posts` — **un solo nivel**. Pero
`proyectos/T1/` no es basura: son los **27 respaldos de la tanda anterior al pipeline** (Messi01,
Tupac01, Venecia01, Douglas_Bader…), y son justo los videos que forman el `baseline` con el que se
compara todo. Al estar un nivel más abajo, `proyectos/T1/Messi01/social_posts` era invisible.

Se aplicó el glob a dos niveles (no `rglob`: acotarlo evita que un respaldo dentro de otro entre
como proyecto). Medido:

| | Antes | Después |
|---|---:|---:|
| proyectos indexados | 28 | **50** |
| filas de `metricas.csv` sin `PROYECTO` | 78 | **35** |
| TikTok con `PROYECTO` | — | **15 de 15** |

Las 147 filas siguen siendo 147: no se creó ni se perdió ninguna medición, solo se les puso nombre.
Los rellenos a mano de `mapa_manual.csv` no se tocaron.

> ⚠️ Esto contradice lo que decían las notas antiguas («los videos anteriores al pipeline no tienen
> carpeta en `proyectos/`»). Sí la tienen; estaba un nivel más abajo de donde se buscaba.

---

## ✅ El paso 05 dormía el triple de lo necesario (15 ago 2026)

`DELAY = 7.0` se aplicaba igual a las dos fuentes. No son lo mismo:

- **Wikimedia Commons** es una API pública documentada. Su política pide **identificarse** (User-Agent
  con contacto) y no paralelizar — no pide lentitud. Y `search_commons()` / `get_image_url()` ya
  reintentaban con backoff de 10/20/30 s ante un 429, así que la red de seguridad existía.
- **DuckDuckGo** es scraping tolerado y es el que bloquea de verdad.

Quedó en `DELAY_WIKIMEDIA = 1.5` y `DELAY_DDG = 7.0`.

**Hallazgo por el camino:** la espera del final del bucle **no era «la de DuckDuckGo»** como decía
la nota. Es la pausa **entre imágenes**, y corría siempre — 7 s por imagen aunque la foto saliera
de Wikimedia a la primera. Ahora mira `uso_ddg` para elegir cuál aplicar. Ahí estaba la mayor parte
del tiempo perdido.

De paso, el `User-Agent` tenía un **paréntesis sin cerrar** y se hacía pasar por `Mozilla/5.0`.
Ahora se identifica con contacto, que es lo que Wikimedia pide de verdad.

Medido sobre los 7 temas (26.1 esperas de Wikimedia y 6 imágenes de media por tema): el paso pasa
de **3.7 a 1.0 min dormido → −2.7 min por tema, −19 min por lote de 7**. Probado contra la API real
con el User-Agent nuevo: 8 peticiones en 10.2 s, ningún 429.

---

## ✅ La curva de retención cierra P-12 (15 ago 2026)

`se_quedaron_pct` era la única métrica que empeoraba en v2 (−16 % en YouTube, −31 % en TikTok). La
nota planteaba: *«si la caída está en 0-2 s es el gancho; si está en 3-6 s es el ritmo del primer
corte»*. Se midió con la curva de retención (`elapsedVideoTimeRatio`), que **ningún export trae**.

⚠️ **Hay que comparar a segundos ABSOLUTOS iguales.** `elapsedVideoTimeRatio` es fracción del
video, y los lotes duran distinto (baseline 40 s, v2 26 s): el «10 %» son 4.0 s en uno y 2.6 s en
el otro. Comparar al mismo porcentaje compara instantes distintos.

| segundo | baseline | v2 | dif |
|---:|---:|---:|---:|
| 0.5 | 1.413 | 1.596 | **+12.9 %** |
| 2 | 1.294 | 1.473 | +13.9 % |
| 5 | 1.121 | 1.299 | +15.9 % |
| 10 | 0.829 | 0.930 | +12.1 % |
| 25 | 0.561 | 0.614 | +9.5 % |

**No es ninguna de las dos hipótesis.** v2 va por delante en todos los puntos desde el segundo 0.5,
con una ventaja plana. Ni el título ni el ritmo de los cortes cuestan retención.

**Por qué las dos métricas parecían contradecirse: miden denominadores distintos.**

| | Denominador | v2 vs baseline |
|---|---|---:|
| `se_quedaron_pct` | de los que el Short **empieza a reproducirse en el feed** | −16 % |
| `audienceWatchRatio` (la curva) | de los que **se quedan a verlo** | +9 a +16 % |

Lectura correcta: **para el scroll menos gente, pero la que para ve mucho más.** Encaja con todo lo
demás — `retencion_pct` +32 %, `vistas_24h` +513 %, y `duracion_media_s` solo −13 % con videos un
32 % más cortos.

Queda [P-20](TODO.md#p-20), que es una pregunta más estrecha: qué hace que menos gente pare el
scroll. Lo único que actúa antes de reproducir es **el primer frame**.

---

## ✅ Métricas de YouTube por API (15 ago 2026)

[13_youtube_api.py](herramientas/13_youtube_api.py). OAuth obligatorio: son datos privados del
canal y una API key no basta. Montaje completo en [README.md](README.md).

**Lo que da y lo que no.** `--metricas` descarga las 40 filas con datos y las funde en
`metricas.csv` **reusando `fusionar()` del paso 10** — no se reimplementa la fusión a propósito:
ya sabe no pisar valores llenos con vacíos, conservar las fotos de otros días y no degradar el
lote. ⚠️ La API **no expone** `se_quedaron_pct` («Se quedaron para mirar», específica de Shorts) ni
`alcance` (únicos por video), así que **reduce** el trabajo manual, no lo elimina. La fusión no las
pisa, así que se rellenan desde el export cuando hagan falta.

**Detalles que costaron tiempo:**

- ⚠️ **Publicar la app «En producción» en la consola no es opcional.** En estado *Prueba*, Google
  caduca el refresh token a los **7 días** — reautorizar cada semana, justo el trabajo que esto
  venía a quitar. La verificación de Google es otra cosa y **no hace falta**: exige dominio propio
  verificado en Search Console con la política de privacidad alojada ahí.
- ⚠️ **`comprobar_canal()` antes de fiarse de ningún número.** Con la cuenta equivocada la API
  responde **200 con datos vacíos**, y un informe de ceros parece un mal mes. Se compara contra el
  **ID** del canal, no contra el nombre ni el `@`: el canal se llama *Curiosidades Historicas*, su
  identificador de YouTube es `@curiosidadeshistoricas-03` y **no coincide con el `@chistoricas3`
  de las otras redes** — comparar contra cualquiera de los dos daba un falso aviso en cada corrida.
- ⚠️ **No llamar a `authorization_url()` antes de `run_local_server()`.** `run_local_server()` la
  llama otra vez internamente y genera un `state` NUEVO, así que la URL calculada antes queda
  invalidada al instante: el callback muere con `MismatchingStateError: CSRF Warning!` **mientras
  el navegador muestra que todo fue bien**. Costó tres intentos fallidos y parecía un problema de
  configuración de Google. La URL correcta es la que anuncia la propia librería.

---

## ✅ Métricas de Instagram y Facebook por API (15 ago 2026)

[14_meta_api.py](herramientas/14_meta_api.py). Un solo trámite de credenciales cierra la lectura de
métricas (P-09b) y deja montada la publicación (P-10): son los mismos permisos.

**El mapeo NO se dedujo de la documentación: se preguntó a la API con la cuenta real.** Tres cosas
que habrían salido mal escribiéndolo a ciegas:

| Lo que parecía | Lo que es |
|---|---|
| `plays` es la métrica de reproducciones de Instagram | **Deprecada.** La buena es `views` — `plays` devuelve un 400 que ni menciona la deprecación |
| Los tiempos vienen en segundos | **Milisegundos**, en las dos redes. El export en CSV los da en segundos con decimales — el mismo `9.378` que ya dio problemas |
| La curva de retención es exclusiva de YouTube | **Facebook también la expone**, en `post_video_retention_graph` (33 puntos). Sirve para [P-20](TODO.md#p-20) |

⚠️ **El bug que se comió media hora, y que habría sido invisible: `video_reels` devuelve el id del
VIDEO y el export en CSV trae el id del POST.** Son distintos (`1033620252602631` vs
`122111309283294832`) y ninguno de los dos lo dice. Usando el del video, cada reel entraba como
fila **nueva** en vez de fusionarse: 45 filas fantasma, cada video de Facebook contado dos veces y
las medianas del informe calculadas sobre datos duplicados. Se detectó porque la fusión anunció
**45 filas nuevas donde debían ser 0** — la misma señal que delató el bug del lote pegajoso. El
campo que las une es `post_id`, que hay que pedir explícitamente.

**Lo que se ganó:** Instagram **dejó de tener campos manuales**. `duracion_media_s` —el único que
había que teclear de esa red, mirando reel por reel en la app— lo da `ig_reels_avg_watch_time`.
Cobertura de 36/45 a 45/45 en una corrida.

**Lo que no se gana:** la API de YouTube sigue sin exponer `se_quedaron_pct` ni `alcance`, así que
para esas dos hay que bajar el zip. Y TikTok exige registrar una app y pasar una revisión de
semanas para la red que menos aporta.

Detalles de diseño que se repiten del paso 13:
- **No se reimplementa la fusión.** `fusionar()` del paso 10 ya sabe no pisar un valor lleno con
  uno vacío, conservar las fotos de otros días y no degradar el lote.
- **Se descartan las publicaciones sin ninguna métrica.** La API deja de devolver insights de las
  más antiguas (aquí, las de mayo), y una fila con todo vacío solo baja las n del informe.
- **La duración se presta entre redes.** Ni IG ni FB la exponen en sus insights, pero es el mismo
  video: se toma de las filas de YouTube que ya están en `metricas.csv`, y con eso la retención se
  puede calcular.
- ⚠️ **El token de página se enmascara en pantalla** y se escribe al `.env` con `--escribir-env`.
  Permite publicar en tu nombre, y esa salida acaba en logs y capturas.
- ⚠️ **`--diagnostico` desambigua la página por el Instagram vinculado**, no por el nombre ni el
  orden: la cuenta administra tres páginas (dos de otros proyectos) y elegir «la primera» habría
  publicado en la equivocada.

---

## ✅ Publicar en Instagram y Facebook (15 ago 2026)

`--publicar PROYECTO` en [14_meta_api.py](herramientas/14_meta_api.py).

⚠️ **`desuso/publisher.py` no servía de base, y no por las credenciales.** Mandaba el video como
`files={"video": …}` a `/media`. Esa forma **no existe** en la API de publicación de Instagram:
falla siempre, con credenciales o sin ellas. Las dos vías reales son:

| | Requiere | Sirve aquí |
|---|---|---|
| `video_url` | que el mp4 esté en una **URL pública** | No — el pipeline es local |
| Subida reanudable a `rupload.facebook.com` | nada, acepta bytes locales | **Sí** |

De ahí el `upload_type=resumable` de Instagram y las tres fases de Facebook
(`upload_phase=start` → subida → `upload_phase=finish`).

**Publicar es irreversible y va hacia fuera**, así que el diseño lo asume:

- **`--dry-run` hace todo menos la llamada final**, incluida la subida del video y la espera al
  procesado. Valida el camino entero sin que salga nada.
- **`publicar/publicado.csv` registra lo que salió, y se comprueba antes de subir.** El calendario
  dice cuándo *tocaba* publicar, no si se hizo, así que sin este registro correr el comando dos
  veces publica el mismo reel dos veces. De paso cierra el hueco que señalaba P-17.
- **`anotar_publicado()` se llama SOLO cuando la red confirma**, igual que en el recordatorio de
  Telegram: anotarlo antes haría que un fallo de red marcara como publicado algo que no salió, y
  ese reel no se reintentaría nunca.

⚠️ **El parseo de `descripcion.txt` corta por la línea de guiones, no por «el título va en
mayúsculas».** Los títulos reales llevan minúsculas dentro (`TAGS DE YOUTUBE (separados por coma)`,
`DESCRIPCIÓN LARGA (YouTube y Facebook) — 1447/1999 caracteres`), así que detectarlos por mayúsculas
hacía que una sección se tragara todas las siguientes: **el pie del reel de Instagram habría salido
con los tags de YouTube pegados al final**. Es un fallo que no se nota hasta que está publicado, y
por eso está congelado en tests.

Cada red lleva su sección: Instagram el pie corto (*DESCRIPCIÓN GENERAL*, ~530 caracteres) y
Facebook la larga (*DESCRIPCIÓN LARGA*, ~1450). Los hashtags van dentro de las dos, que es
justamente por lo que el paso 02 los repite.

---

## Anexo — Evidencia medida

Comandos ejecutados sobre los archivos reales el 2026-08-02.

**Bitrate y faststart** (`Mundial16`):
```
videos_no_music/video_Mundial16.mp4 → 3 270 052 bps · átomos: ftyp, moov, free, mdat
videos/video_Mundial16.mp4          → 2 418 168 bps · átomos: ftyp, free, mdat, moov
```

**Sonoridad** (`ffmpeg -af volumedetect`):
```
videos_no_music/video_Mundial16.mp4 → mean −20.2 dB · max −5.9 dB
videos/video_Mundial16.mp4          → mean −20.2 dB · max −5.5 dB   (la música no cambia nada)
```

**Duración de los 16 videos:** 30.6 s – 45.2 s · media ≈ 39 s · todos 1080×1920 @ 30 fps.

**Ritmo visual:** 8 imágenes ÷ 38.9 s = **4.86 s por plano**.

**Velocidad de habla:** `script.txt` = 90 palabras ÷ 37.8 s = **143 wpm**.

**Resolución de las imágenes IA:** los 8 `scene_N.png` = **720×1280** (se muestran a 1080×1920).

**`to_mask` en el entorno instalado** (moviepy 1.0.3, `ai_video_bot`):
```python
def to_mask(self, canal=0):
    newclip = self.fl_image(lambda pic: 1.0 * pic[:, :, canal] / 255)
```

**Frames inspeccionados:** `Mundial01` (t=0.3/1.5/3/8/20), `Mundial12` y `Mundial16` (mismos
tiempos), más recortes a resolución completa de la zona de subtítulos y de título.
