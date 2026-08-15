# TODO.md — Auditoría técnica + plan de crecimiento

> Generado el 2026-08-02 tras revisar los 8 pasos del pipeline, los 16 videos de `videos/`,
> los respaldos de `proyectos/` y medir los archivos con `ffprobe`/`ffmpeg`.
> Todo lo marcado **CONFIRMADO** está verificado con evidencia (ver [Anexo](#anexo--evidencia-medida)).

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

**Dónde:** [07_video_generator.py:439](07_video_generator.py#L439),
[07_video_generator.py:551](07_video_generator.py#L551),
[07_video_generator.py:592](07_video_generator.py#L592).

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

**Dónde:** [03_voice_generator.py:42-51](03_voice_generator.py#L42-L51).

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

**Dónde:** [08_music_mixer.py:77-83](08_music_mixer.py#L77-L83).

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

**Dónde:** [04_image_generator.py:318-321](04_image_generator.py#L318-L321).

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

**Dónde:** [07_video_generator.py:653-658](07_video_generator.py#L653-L658) — `duration=video.duration`.

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

**Dónde:** [07_video_generator.py:601](07_video_generator.py#L601) — `int(height * 0.82)`.

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

**Dónde:** [04_image_generator.py:162](04_image_generator.py#L162).

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

**Dónde:** [04_image_generator.py:380-386](04_image_generator.py#L380-L386).

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

**Dónde:** [04_image_generator.py:372](04_image_generator.py#L372).

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

**Dónde:** [04_image_generator.py:317](04_image_generator.py#L317).

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

**Dónde:** [07_video_generator.py:390-407](07_video_generator.py#L390-L407).

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

**Dónde:** [07_video_generator.py:289-333](07_video_generator.py#L289-L333).

`get_active_word_window()` siempre devuelve un par, incluso en `t=0` cuando el narrador todavía no
empezó. El primer par se ve congelado durante el silencio inicial.

**Fix:** al inicio de la función,

```python
if t < words[0]["start"] - 0.15:
    return [], -1
```

---

### ⚪ BUG-16 (P3) — `resize_for_social()` asume la carpeta de salida

**Dónde:** [05_download_images.py:158](05_download_images.py#L158) — `dest = out_dir / "source_images" / src.name`,
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
| Contador de costo por tema en el log | Hoy no sabes cuánto te cuesta cada video (trampa 10) |
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
- [x] Sello `.estado_actual` — nuevo módulo [estado.py](estado.py). El paso 01 sella el
      `PROYECTO`; los pasos 02, 03, 04 y 07 abortan si los archivos de la raíz son de otro tema
- [x] Contador de costo por tema en `.costo_actual.json` (OpenAI por tokens, fal por
      megapíxel, ElevenLabs por carácter). Los pasos 02 y 04 lo imprimen al terminar
- [x] `con_reintentos()` con backoff exponencial (aplicado al paso 01)
- [ ] **Pendiente tuyo:** calendario de publicación 1/día + registro de métricas a 24 h y 7 días

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

## De dónde salen las métricas

Todo el código está hecho. **Lo único que falta para saber si sirvió son los números**, y esos no
los genera el pipeline: hay que sacarlos de cada plataforma.

### YouTube Shorts — la fuente que más importa

**A mano (empieza por aquí):** YouTube Studio → Contenido → Shorts → clic en un video → pestaña
**Interacción**. Los tres números que importan:

| Métrica | Dónde | Qué te dice |
|---|---|---|
| **Espectadores que se quedaron** | gráfico de retención, primeros segundos | Si cae >60 % antes del segundo 3, el problema es el gancho |
| **Duración media de la reproducción** | pestaña Interacción | Divídela entre la duración total = % de retención |
| **Vistas en las primeras 24 h** | pestaña Alcance | Si el gancho retiene pero esto no sube, el problema es la metadata |

La **curva de retención** es la herramienta de diagnóstico real: te dice el **segundo exacto** donde
se van. Caída en 0-2 s → gancho. Caída en 5-10 s → ritmo visual. Caída al final → el CTA sobra.

**Automatizado (YouTube Data API v3 + Analytics API):** gratis, cuota de 10 000 unidades/día, de
sobra. Requiere OAuth (no basta una API key, porque son datos privados del canal).

```
pip install google-api-python-client google-auth-oauthlib
```

- Alcance de OAuth: `https://www.googleapis.com/auth/yt-analytics.readonly`
- Endpoint: `youtubeAnalytics.reports().query()` con
  `metrics="views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage"`
  y `dimensions="video"`
- Para la curva de retención: `dimensions="elapsedVideoTimeRatio"` con
  `metrics="audienceWatchRatio,relativeRetentionPerformance"` — **esta es la buena**

### Instagram y Facebook

**A mano:** app → Perfil → gráfico de estadísticas → Contenido. Para Reels miras *Reproducciones*,
*Retención* y *Interacciones*.

**Automatizado:** Instagram Graph API, `GET /{ig-media-id}/insights` con
`metric=plays,reach,saved,shares,total_interactions`. Requiere cuenta **Business o Creator**
vinculada a una página de Facebook, más un token de acceso de larga duración.

⚠️ Aquí ya tienes medio camino hecho y roto: [publisher.py](publisher.py) espera
`META_ACCESS_TOKEN`, `FACEBOOK_PAGE_ID`, `INSTAGRAM_ACCOUNT_ID` y `THREADS_USER_ID`, que **no están
en el `.env`**. Los mismos credenciales sirven para publicar y para leer métricas: si vas a montar
uno, monta los dos.

### Lo mínimo viable, y es una hoja de cálculo

No montes nada automatizado todavía. Con 16 videos publicados, la API es sobreingeniería: tardas
más en resolver el OAuth que en copiar los números a mano.

Crea `metricas.csv` en el repo con una fila por video:

```
PROYECTO,fecha_publicacion,plataforma,vistas_24h,vistas_7d,retencion_pct,pct_llega_3s,comentarios
```

Rellénalo **una vez** con los 16 videos viejos → ese es tu baseline. Después una fila por video
nuevo. Con 5 videos nuevos ya vas a ver si la retención a 3 s se movió, que es la única pregunta
que importa ahora mismo.

**Cuándo automatizar:** cuando llenar la hoja te lleve más de 10 minutos por semana, o cuando pases
de ~50 videos. Antes de eso no compensa.

### La trampa de medir mal

Los 16 videos actuales se renderizaron el mismo día (16:27 → 21:27 del 14 de junio). Si también se
publicaron en bloque, su rendimiento está contaminado por la canibalización entre ellos: no son un
baseline limpio.

Para que la comparación signifique algo, los videos nuevos van **1 por día, a la misma hora**, y se
comparan contra la mediana de los viejos, no contra el mejor ni el peor.

---

## Pendientes (8 ago 2026)

Estado tras el primer lote real con el pipeline auditado (`Historia01`–`Historia08`).
Ordenado por lo que bloquea publicar, no por dificultad.

### 🔴 Bloquean el lote actual

**P-01 · Saldo de fal.ai agotado — 2 temas sin video.**
`Historia07` (Galeón) y `Historia08` (Einstein) abortaron en el paso 04:
```
❌ Error generando imagen 1: User is locked. Reason: Exhausted balance.
❌ Solo se generaron 0/6 imágenes (mínimo 5) — el video quedaría inservible
```
El corte fue limpio: no se gastó de más y no quedó un video a medias. `logs/failed.csv` ya
tiene las dos filas con los nombres corregidos, así que sirve tal cual como `temas.csv` para
reintentar. **Recargar antes de correr cualquier lote nuevo.**

**P-02 · 5 de 6 guiones NO pasaron el control de calidad.**
Y eso es ya el mejor de 3 intentos, con reescritura guiada por los fallos concretos.

| Tema | Nota | Qué le objetó el crítico |
|---|---:|---|
| Historia02 Eclipse | **3/10** | narra *"dos ejércitos **lidian** bajo el mismo sol"* — se comió que eran **lidios**, y sale así en la voz |
| Historia05 San Lorenzo | 4/10 | *"el festival de parrilladas más popular de Roma"* |
| Historia06 Surrealismo | 4/10 | *"juró que podía hipnotizar a una ciudad entera"* |
| Historia01, Historia03 | 5/10 | afirmaciones sin fuente verificable |
| Historia04 Robin Hood | ✅ | el único aprobado |

**El problema no está en el paso 01: entró por `temas.csv`.** `2016`, `Eclipse`, `Odisea` y
`Surrealismo` son categorías, no historias. El único que pasó es el único que era un personaje
con un relato concreto. Es exactamente lo que advierte
[INSTRUCCIONES_CHATGPT.md](INSTRUCCIONES_CHATGPT.md): *"UNA SOLA LÍNEA NARRATIVA. Un incidente
concreto con principio y final, no la biografía de alguien."*
El crítico está funcionando — está avisando de un problema aguas arriba. **Acción: elegir los
temas del próximo lote con esas instrucciones, y no publicar los 5 sin leerlos.**

### 🟠 Calidad del producto

**P-03 · Títulos de YouTube por encima de 70 caracteres.**
4 de 8 (`Historia01` 77, `Historia03` 71, `Historia05` 74, `Historia07` 74). El paso 02 avisa
pero no corrige, así que salen igual y YouTube los recorta en la búsqueda. Opciones: reintentar
la llamada pidiendo acortar, o cortar en el último límite de palabra que quepa. Reintentar es
mejor — truncar deja títulos que terminan a media idea.

**P-04 · El crítico de Anthropic nunca se ha ejecutado.**
No hay `ANTHROPIC_API_KEY` en el `.env`, así que `critico_proveedor: "auto"` siempre cayó a
`gpt-4.1` — es decir, **el generador y el crítico son el mismo modelo y comparten puntos ciegos**.
Ese es justo el fallo que la separación de proveedor debía evitar. Al poner la clave, vigilar en
la primera corrida que el JSON no salga truncado: en Opus 5 el thinking está on por defecto y
`critico_max_tokens` limita thinking + respuesta juntos.

### 🟡 Tiempo y costo

Medido sobre `Historia01` (13m 41s de punta a punta) y `.costo_actual.json` ($0.24827).

**Los pasos 05 y 07 son el 91% del tiempo.** El 05 (4m 56s) está casi todo **dormido**:
`DELAY = 7.0` uniforme, aplicado en cuatro puntos, más un ciclo extra por cada foto que el filtro
de visión rechaza. El 07 (7m 34s) sí trabaja, pero el techo es el hardware: **i5-7200U, 2 núcleos
de 2016**, corriendo whisper `medium` y 766 frames compuestos en Python con PIL.

**El 74% del costo es fal.ai**: 6 imágenes × $0.0306 (832×1472 = 1.225 MP × $0.025/MP).
OpenAI son $0.052 (21%), de los cuales $0.023 es el control de calidad del guion — bien gastados.
ElevenLabs, $0.012 (5%).

| Palanca | Gana | Riesgo |
|---|---|---|
| `DELAY` distinto por fuente en el paso 05 (1.5s Wikimedia / 7s DuckDuckGo) | ~3 min/video, **~25 min por lote** | bajo — Wikimedia tiene API pública; el que bloquea es DDG |
| whisper `medium` → `small` | 1-2 min/video | hay que revisar el `.srt`, que sí se publica |
| `gpt-4.1-mini` en las llamadas mecánicas (queries, contexto, gancho, validación visual) | $0.0066/video | bajo — son tareas de extracción, no de criterio |
| 6 → 5 imágenes | $0.031/video (12%) | 5 imágenes para 14 cortes empieza a repetirse |

**P-05 · Hallazgo SIN CONFIRMAR sobre el composite del paso 07.**
Los dos `CompositeVideoClip` (líneas ~555 y ~1028) se construyen sin `bg_color`, lo que hace que
moviepy monte **un composite paralelo entero solo para la máscara alfa** — que el mp4 final no usa.
Medí hasta 2× de mejora, y solo aparece si se corrigen **los dos a la vez**. Pero **no me fío del
número**: las mediciones corrieron peleando por los mismos 4 hilos que el render del lote, y dos
benchmarks se contradijeron. **Re-medir con la máquina quieta antes de tocar nada.**

**P-06 · Paralelizar los temas — la palanca grande, y está bloqueada por diseño.**
El paso 05 es red (dormido) y el 07 es CPU: se solaparían perfecto. Pero `run_all.sh` es serial
porque `script.txt`, `voice.mp3` e `images_IA/` son **estado global en la raíz**; dos temas a la
vez se pisan. Habilitarlo exige un directorio de trabajo por tema. Es el cambio más grande del
proyecto y el que más tiempo ahorra: el lote pasaría de ~1h50m a ~50 min.

### ⚪ Limpieza y deuda

**P-07 · Basura de corridas viejas en `proyectos/`.** Siguen ahí `proyectos/social_posts/`,
`proyectos/carousel_slides/`, `proyectos/source_images/` (de cuando `PROYECTO` iba vacío) y
`proyectos/T1/`. Ya no se pueden volver a crear — hay guardas en los pasos y en `run_pipeline.sh` —
pero nadie las ha borrado. Los 16 respaldos `Mundial*` conservan además slides obsoletos.

**P-08 · Los 16 Mundial no tienen `descripcion.txt` ni `.srt`.** Son anteriores a la
reestructuración del paso 02, así que el paso 09 los marca incompletos, y con razón. No vale la
pena regenerarlos: si se republican, se reescribe el texto a mano.

**P-09 · `metricas.csv` está vacío.** Tiene las 16 filas de baseline con `notas` puesto, pero
ni una sola vista, retención ni `pct_llega_3s`. **Sin esa línea base no se puede saber si algo de
todo esto funcionó.**
Ya no hay que copiar a mano: **[METRICAS.md](METRICAS.md)** dice de dónde se exporta en bloque en
cada red y **[10_metricas.py](10_metricas.py)** une los CSV en `metricas.csv` emparejando cada fila
con su `PROYECTO`. Son ~20 min la primera vez y ~5 por semana. Lo único que sigue siendo manual es
la **curva de retención de YouTube** (el `pct_llega_3s`), que no está en ningún export — y con
mirarla en los 3 mejores y los 3 peores basta para diagnosticar.

**P-10 · Preguntas abiertas que cambian el alcance.**
- ¿Se sigue usando el carrusel de Instagram? Si no, el paso 06 y `carrusel.txt` salen del pipeline
  (ahorra $0.004 y 8s por tema, y quita el contrato frágil de formato con el paso 02).
- ¿El plan de Metricool incluye API de publicación o importación masiva por CSV? Si sí, se puede
  automatizar la programación desde `publicar/calendario.csv`.

**P-11 · `publisher.py` sigue incompleto.** Le faltan `META_ACCESS_TOKEN`, `FACEBOOK_PAGE_ID`,
`INSTAGRAM_ACCOUNT_ID` y `THREADS_USER_ID`, y apunta a `post_images/`, que no existe. La
publicación es manual.

**P-12 · No hay tests.** Todo se valida a mano corriendo un tema. Lo más rentable serían pruebas
puras, sin red: `separar_hashtags()`, `repartir_planos()`, `verificar_reglas_mecanicas()` y el
parseo de `carrusel.txt` del paso 06.

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
