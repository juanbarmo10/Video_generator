# TODO — lo que queda por hacer

> **Este documento solo lleva trabajo pendiente.** Lo ya resuelto —la auditoría de 18 bugs, las
> 5 fases de implementación, la prueba end-to-end, el control de calidad del guion y todas las
> mediciones— está en **[HISTORIAL.md](HISTORIAL.md)**. Léelo antes de tocar el pipeline: casi
> todo valor que parece arbitrario en el código sale de un fallo documentado allí.
>
> Operar el pipeline (generar, empaquetar, programar, medir) es **[README.md](README.md)**.
> Arquitectura y trampas del código, **[CLAUDE.md](CLAUDE.md)**.

**Estado a 15 ago 2026.** Primer lote real con el pipeline auditado (`Historia01`–`Historia08`):
**los 8 terminados** — `Historia07` y `Historia08` se recuperaron tras recargar fal.ai. El informe
de métricas confirma el salto de `v2-mas-cortes` sobre `baseline` con las cifras que resisten un
filtro de comparabilidad (YouTube +513 % a 24 h, CTR +785 %, retención +32 %) y una sola métrica en
contra, `se_quedaron_pct`. **Nada del pipeline está roto.** Lo que queda es elección de temas,
costo, tiempo y orden del repositorio.

⚠️ Lo urgente ya no es generar: es **leer los 7 guiones que no pasaron el control antes de
programarlos**.

| | # | Pendiente |
|---|---|---|
| 🔴 | [P-02](#p-02) | 7 de 8 guiones no pasaron el control de calidad (el problema entró por `temas.csv`) |
| 🟠 | [P-03](#p-03) | Títulos de YouTube por encima de 70 caracteres |
| 🟠 | [P-04](#p-04) | El crítico de Anthropic nunca se ha ejecutado |
| 🟠 | [P-12](#p-12) | `se_quedaron_pct` bajó — la única métrica que empeoró en v2 |
| 🟠 | [P-15](#p-15) | Los planos de una misma imagen salen consecutivos: se perciben la mitad de los cortes |
| 🟡 | [P-05](#p-05) | Composite del paso 07 sin `bg_color` — hallazgo sin confirmar |
| 🟡 | [P-06](#p-06) | Paralelizar los temas (bloqueado por el estado global de la raíz) |
| 🔵 | [P-17](#p-17) | Afinar el recordatorio con unas semanas de uso (ya funciona y está en cron) |
| ⚪ | [P-14](#p-14) | `proyectos/T1/` anidado: 78 de 147 filas de métricas sin `PROYECTO` |
| ⚪ | [P-07](#p-07) | Basura de corridas viejas (~750 MB recuperables) |
| ⚪ | [P-08](#p-08) | Los 16 Mundial no tienen `descripcion.txt` ni `.srt` |
| ⚪ | [P-09](#p-09) | ¿Se sigue usando el carrusel de Instagram? |
| ⚪ | [P-09b](#p-09b) | Automatizar la recogida de métricas por API |
| ⚪ | [P-10](#p-10) | `publisher.py` sigue incompleto |
| ⚪ | [P-18](#p-18) | La cabecera del paso 06 miente sobre su entrada |
| ⚪ | [P-11](#p-11) | No hay tests |

---

## 🔴 Bloquean el lote actual

<a id="p-02"></a>
**P-02 · 7 de 8 guiones NO pasaron el control de calidad.**
Y eso es ya el mejor de 3 intentos, con reescritura guiada por los fallos concretos.

| Tema | Nota | Qué le objetó el crítico |
|---|---:|---|
| Historia02 Eclipse | **3/10** | narra *"dos ejércitos **lidian** bajo el mismo sol"* — se comió que eran **lidios**, y sale así en la voz |
| Historia05 San Lorenzo | 4/10 | *"el festival de parrilladas más popular de Roma"* |
| Historia06 Surrealismo | 4/10 | *"juró que podía hipnotizar a una ciudad entera"* |
| Historia07 Galeón | 4/10 | *"tres clavos cambiaron la ruta del oro"*, *"millones en plata y porcelanas"* |
| Historia01, Historia03 | 5/10 | afirmaciones sin fuente verificable |
| Historia08 Einstein | 6/10 | ⚠️ su `calidad_guion.json` es de **antes** del arreglo del veredicto (abajo): acusa a un guion sobre el cerebro de Einstein que no se usó. El que se publica es el del examen de ingreso — léelo directamente |
| Historia04 Robin Hood | ✅ | el único aprobado |

**El problema no está en el paso 01: entró por `temas.csv`.** `2016`, `Eclipse`, `Odisea` y
`Surrealismo` son categorías, no historias. El único que pasó es el único que era un personaje
con un relato concreto. Es exactamente lo que advierte
[INSTRUCCIONES_CHATGPT.md](INSTRUCCIONES_CHATGPT.md): *"UNA SOLA LÍNEA NARRATIVA. Un incidente
concreto con principio y final, no la biografía de alguien."*
El crítico está funcionando — está avisando de un problema aguas arriba. **Acción: elegir los
temas del próximo lote con esas instrucciones, y no publicar los 5 sin leerlos.**

---

## 🟠 Calidad del producto

<a id="p-03"></a>
**P-03 · Títulos de YouTube por encima de 70 caracteres.**
4 de 8 (`Historia01` 77, `Historia03` 71, `Historia05` 74, `Historia07` 74). El paso 02 avisa
pero no corrige, así que salen igual y YouTube los recorta en la búsqueda. Opciones: reintentar
la llamada pidiendo acortar, o cortar en el último límite de palabra que quepa. Reintentar es
mejor — truncar deja títulos que terminan a media idea.

<a id="p-04"></a>
**P-04 · El crítico de Anthropic nunca se ha ejecutado.**
No hay `ANTHROPIC_API_KEY` en el `.env`, así que `critico_proveedor: "auto"` siempre cayó a
`gpt-4.1` — es decir, **el generador y el crítico son el mismo modelo y comparten puntos ciegos**.
Ese es justo el fallo que la separación de proveedor debía evitar. Al poner la clave, vigilar en
la primera corrida que el JSON no salga truncado: en Opus 5 el thinking está on por defecto y
`critico_max_tokens` limita thinking + respuesta juntos.

<a id="p-12"></a>
**P-12 · `se_quedaron_pct` bajó: la única métrica que empeoró en v2.**
YouTube 48.5 % → **40.7 %**, TikTok 13 % → **9 %**, mientras todo lo demás subía (ver la
[primera lectura](HISTORIAL.md#primera-lectura-15-ago-2026) en el historial). No se explica por
tiempo de exposición, porque las ventanas de 24 h ya lo neutralizan. Con n=6 puede ser ruido,
pero apunta a que **los primeros 2 segundos empeoraron** aunque quien se queda vea mucho más.

✅ **Confirmado el 15 ago con el informe** (`herramientas/11_reporte.py`): −16 % en YouTube (n=6 vs
34) y −31 % en TikTok (n=3 vs 8, muestra pequeña). Es la **única** métrica que baja de las que
sobreviven al filtro de comparabilidad — el resto de las que caían resultaron ser acumulados
contaminados por la antigüedad. Que aparezca en las dos redes que la exportan, y en la misma
dirección, le quita bastante de casualidad.

Sospechosos, en orden: el título en pantalla dura 2.5 s y arranca en `y=200`; el primer corte
llega a 1.75 s (antes 4.9 s), que puede leerse como brusco; el gancho generado abre pregunta
pero ya no dice el desenlace, que es lo que retenía a quien buscaba respuesta rápida.

**Acción:** en el próximo lote, contrastar con la **curva de retención** de dos o tres v2 en
YouTube Studio (dimensión `elapsedVideoTimeRatio`; es lo único que ningún export masivo trae).
Si la caída está en 0–2 s es el gancho; si está en 3–6 s es el ritmo del primer corte.

<a id="p-15"></a>
**P-15 · Los planos de una misma imagen salen consecutivos: dispersarlos.**
Hoy `create_video()` recorre las imágenes en orden y, por cada una, encadena todos sus sub-planos
seguidos. Con 8 imágenes × ~2 planos la secuencia real es:

```
A1 A2  B1 B2  C1 C2  D1 D2 …          ← lo que se ve ahora
```

Los dos primeros cortes son **la misma ilustración con otro encuadre**. El ojo lo lee como "zoom
sobre lo mismo", no como corte nuevo, así que la mitad de los cortes que cuenta
`repartir_planos()` no se perciben como tales. Intercalándolos:

```
A1 B1  A2 B2  C1 D1  C2 D2 …          ← misma duración, el doble de cortes percibidos
```

Es gratis: no cambia el número de imágenes ni el costo de fal, solo el orden de los clips en el
bucle de [07_video_generator.py](pipeline/07_video_generator.py) (`plano_global`, ~línea 545).

⚠️ **No barajar al azar, y esto es lo importante.** Las 6 imágenes las genera el paso 04 **en orden
narrativo**, a partir de las escenas del guion: la imagen 1 ilustra la primera frase y la 6 el
desenlace. Un shuffle global pondría el desenlace en el segundo 3 y rompería la sincronía entre lo
que se oye y lo que se ve — que es peor que el problema que resuelve. Lo que hay que hacer es
**intercalar dentro de una ventana corta** (pares o tríos de imágenes vecinas), conservando el
avance general.

Ojo también con `intercalar_fotos_reales()`: las fotos reales se colocan en posiciones concretas
(`fotos_reales_solo_extremos`) y el reordenado tiene que respetarlas o se pierde el contraste
buscado entre ilustración y foto de archivo.

**Cómo saber si funcionó:** es una hipótesis sobre ritmo percibido, así que se mide con
`se_quedaron_pct` y con la curva de retención de los 3-6 s — la misma medición de [P-12](#p-12),
con la que conviene coordinarlo para no cambiar dos cosas a la vez y no poder atribuir el efecto.

---

## 🟡 Tiempo y costo

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

<a id="p-05"></a>
**P-05 · Hallazgo SIN CONFIRMAR sobre el composite del paso 07.**
Los dos `CompositeVideoClip` (líneas ~555 y ~1028) se construyen sin `bg_color`, lo que hace que
moviepy monte **un composite paralelo entero solo para la máscara alfa** — que el mp4 final no usa.
Medí hasta 2× de mejora, y solo aparece si se corrigen **los dos a la vez**. Pero **no me fío del
número**: las mediciones corrieron peleando por los mismos 4 hilos que el render del lote, y dos
benchmarks se contradijeron. **Re-medir con la máquina quieta antes de tocar nada.**

<a id="p-06"></a>
**P-06 · Paralelizar los temas — la palanca grande, y está bloqueada por diseño.**
El paso 05 es red (dormido) y el 07 es CPU: se solaparían perfecto. Pero `run_all.sh` es serial
porque `script.txt`, `voice.mp3` e `images_IA/` son **estado global en la raíz**; dos temas a la
vez se pisan. Habilitarlo exige un directorio de trabajo por tema. Es el cambio más grande del
proyecto y el que más tiempo ahorra: el lote pasaría de ~1h50m a ~50 min.

> Ojo: el estado global de la raíz es lo **único** que queda por ordenar ahí. El código ya se
> movió a `pipeline/`, `herramientas/` y `desuso/`
> ([reorganización](HISTORIAL.md#-reorganización-del-código-15-ago-2026)), y esa parte se hizo
> precisamente porque era barata; esta no lo es. Un directorio de trabajo por tema resolvería la
> paralelización *y* vaciaría la raíz de estado mutable: si algún día se hace, hágase una sola vez
> y por ese motivo, no por estética.

---

## 🔵 Operación y seguimiento

El informe ya existe ([11_reporte.py](herramientas/11_reporte.py), hecho el 15 ago — está en
[HISTORIAL.md](HISTORIAL.md#-informe-de-métricas-y-la-trampa-de-la-antigüedad-15-ago-2026)). Falta
que **avise solo** de que toca trabajar.

<a id="p-17"></a>
**P-17 · Afinar el recordatorio con unas semanas de uso.**

El bot **ya funciona** (`@CHvideo_bot`, primer mensaje enviado el 15 ago) y está en `cron`: domingo
10:00 y 16:00, más `--si-falta` de lunes a sábado por si ese domingo tuviste el equipo apagado. El
montaje está en
[HISTORIAL.md](HISTORIAL.md#-el-recordatorio-semanal-por-telegram-15-ago-2026).

Lo que queda son dos ajustes que **solo se pueden decidir con unas semanas de uso**, no ahora:

- **¿`nota_minima` (7) hace demasiado ruido?** Hoy marca 7 guiones en un solo mensaje, que es
  mucho para leerlo en el móvil. Lo más probable es que convenga avisar solo de los que están
  **pendientes de publicar**, no de todo el histórico — pero eso exige saber qué se publicó, y
  hoy el repositorio no lo registra (`publicar/calendario.csv` dice cuándo *tocaba*, no si se
  hizo). Es el mismo dato que le falta a la comprobación de "lote sin programar".
- **¿Adjuntar `reportes/ultimo.html` con `sendDocument`?** Se dejó fuera a propósito: pesa 51 KB y
  Telegram lo manda como archivo, no en línea, así que hay que abrirlo aparte. Si resulta que
  nunca lo abres desde el móvil, mejor meter las 3-4 cifras en el propio mensaje (ya lo hace) y
  no complicarlo.

---

## ⚪ Estructura del repositorio

<a id="p-14"></a>
**P-14 · `proyectos/T1/` anidado deja 78 de 147 filas de métricas sin `PROYECTO`.**
`proyectos/T1/` no es basura: son los **27 respaldos de la tanda anterior al pipeline** (Messi01,
Tupac01, Venecia01, Douglas_Bader…), 22 de ellos con su `social_posts/`. Son justo los videos que
forman el `baseline` con el que se compara todo.

El problema es la profundidad. `indice_proyectos()` del paso 10 recorre `proyectos/*/social_posts`
— **un solo nivel**, así que `proyectos/T1/Messi01/social_posts` es invisible. Consecuencia
medida: 79 filas en `metricas_export/mapa_manual.csv` sin emparejar, de las que **al menos 14
nombran literalmente una carpeta que está dentro de `T1/`**, y 78 de las 147 filas de
`metricas.csv` se quedan sin `PROYECTO`.

Dos salidas, las dos baratas:

1. **Aplanar el archivo** — mover `proyectos/T1/<TEMA>/` a `proyectos/<TEMA>/`. Cero código, pero
   pierde la separación visual entre tandas y hay que comprobar colisiones de nombre.
2. **Glob recursivo** en el paso 10 (`rglob("*/social_posts")` acotado a 2 niveles) y tomar el
   nombre de `posts.parent.name`. Una línea, y `T1/` sigue siendo un archivo aparte.

Recomendada la **2**. Ojo: `mapa_manual.csv` ya tiene rellenos a mano que el script respeta para
siempre — el emparejado nuevo no los pisa, así que se puede probar sin miedo.

> ⚠️ Esto contradice lo que decían las notas antiguas ("los videos anteriores al pipeline no
> tienen carpeta en `proyectos/`"). Sí la tienen; está un nivel más abajo de donde se busca.

<a id="p-07"></a>
**P-07 · Basura de corridas viejas — ~750 MB recuperables.**
Nada de esto se puede volver a crear (hay guardas en los pasos y en `run_pipeline.sh`), pero
tampoco lo ha borrado nadie:

| Qué | Tamaño | Qué es |
|---|---|---|
| `videos_no_music/` (menos `T1/`) | ~700 MB | intermedio del paso 07; el entregable con música ya está en `videos/` |
| `logs/_.log` | 4.6 MB | corrida con `PROYECTO` vacío |
| `images_IA_guidance/` | 4.8 MB | 7 png de mayo; solo lo escribía `imagen_generator_source.py`, que ya no se usa |
| `proyectos/social_posts/`, `proyectos/carousel_slides/`, `proyectos/source_images/` | pocos KB | corridas con `PROYECTO` vacío |
| `proyectos/T1/{social_posts,carousel_slides,source_images,images_IA}/` | pocos MB | lo mismo, dentro del archivo |
| `videos_no_music/T1/video_.mp4` | 13 MB | video de un tema sin nombre |
| `test_voz.mp3`, `fonts/*.zip`, `__pycache__/` | 3.5 MB | pruebas y zips ya extraídos |

Los 16 respaldos `Mundial*` conservan además slides obsoletos (`slide_06_cta.jpg` **y**
`slide_07_cta.jpg` en la misma carpeta), de cuando el paso 06 no limpiaba su salida.

⚠️ **Antes de borrar `videos_no_music/`**: es lo único que permite rehacer la mezcla de música sin
volver a renderizar (~7 min de CPU por video). Si se quiere conservar la opción, borrar solo los
temas ya publicados.

Lo seguro, que no toca ningún entregable ni ningún respaldo real:

```bash
rm -rf proyectos/social_posts proyectos/carousel_slides proyectos/source_images
rm -rf proyectos/T1/social_posts proyectos/T1/carousel_slides \
       proyectos/T1/source_images proyectos/T1/images_IA
rm -rf images_IA_guidance __pycache__
rm -f  logs/_.log test_voz.mp3 fonts/*.zip "videos_no_music/T1/video_.mp4"
```

Nada de eso está en git, así que no hay nada que commitear después.

<a id="p-08"></a>
**P-08 · Los 16 Mundial no tienen `descripcion.txt` ni `.srt`.** Son anteriores a la
reestructuración del paso 02, así que el paso 09 los marca incompletos, y con razón. No vale la
pena regenerarlos: si se republican, se reescribe el texto a mano.

---

## ⚪ Deuda

<a id="p-09"></a>
**P-09 · ¿Se sigue usando el carrusel de Instagram?** Si no, el paso 06 y `carrusel.txt` salen del
pipeline: ahorra $0.004 y 8 s por tema, y quita el contrato frágil de formato con el paso 02.

<a id="p-09b"></a>
**P-09b · Automatizar la recogida de métricas por API.** Hoy son ~15 min por semana de descargas
y tecleo, que es asumible. Cuando pase de ahí o superes ~50 videos, en este orden:

1. **YouTube Analytics API** — gratis, 10 000 unidades/día, pero **OAuth obligatorio** (son datos
   privados del canal; una API key no basta). `pip install google-api-python-client
   google-auth-oauthlib`, alcance `yt-analytics.readonly`. Lo único que no se puede descargar de
   ninguna otra forma es la **curva de retención**: `dimensions="elapsedVideoTimeRatio"` con
   `metrics="audienceWatchRatio,relativeRetentionPerformance"`. Empieza por ahí — es justo lo que
   pide [P-12](#p-12).
2. **Meta** — Instagram Graph API, `GET /{ig-media-id}/insights` con
   `metric=plays,reach,saved,shares,total_interactions`. Aprovecha que `desuso/publisher.py` ya espera
   esas credenciales (ver P-10): las mismas sirven para publicar y para leer.
3. **TikTok, la última.** Hay que registrar una app y pasar una revisión: semanas de trámite para
   la red que menos aporta y donde más hay que teclear.

💡 Antes de nada, mira si tu plan de **Metricool** incluye exportar analíticas a CSV: ya tiene las
cuatro cuentas conectadas y sería una descarga en vez de cinco. No te dará la curva de retención.

<a id="p-10"></a>
**P-10 · `desuso/publisher.py` sigue incompleto.** Le faltan `META_ACCESS_TOKEN`,
`FACEBOOK_PAGE_ID`, `INSTAGRAM_ACCOUNT_ID` y `THREADS_USER_ID`, y apunta a `post_images/`, que no
existe. Además lee `03_instagram.txt` y `04_facebook.txt`, que el paso 02 dejó de generar en
agosto. La publicación es manual. Está en `desuso/` justamente por eso: si algún día se retoma,
vuelve a `herramientas/`.

<a id="p-11"></a>
<a id="p-18"></a>
**P-18 · La cabecera del paso 06 miente sobre su propia entrada.**
El docstring de [06_carrusel_generator.py](pipeline/06_carrusel_generator.py) dice que lee
`social_posts/03_instagram.txt`, un archivo que **dejó de existir** cuando el paso 02 se
reestructuró; su `CONFIG` apunta bien a `carrusel.txt`. Manda el `CONFIG`, pero quien abra el
archivo por primera vez va a buscar un contrato que ya no existe. Son dos líneas de comentario, y
de paso conviene renombrar `parse_instagram_file()` — que además está duplicada, y gana la segunda.

**P-11 · No hay tests.** Todo se valida a mano corriendo un tema. Lo más rentable serían pruebas
puras, sin red: `separar_hashtags()`, `repartir_planos()`, `verificar_reglas_mecanicas()`,
`sanear_valor_env()` y el parseo de `carrusel.txt` del paso 06. También `comparar_lotes()` y
`TIPO_METRICA` de [11_reporte.py](herramientas/11_reporte.py): ahí un signo invertido no rompe
nada, solo hace que el informe afirme lo contrario de lo que pasó, que es peor.

Lo que hay que saber antes de intentarlo: **el obstáculo no son los prefijos numéricos**
(`importlib.import_module("02_…")` funciona), sino que **los pasos trabajan al importarse**. Basta
cargar el módulo para que se ejecute:

| Paso | Qué pasa con solo importarlo |
|---|---|
| 01 | `SystemExit` si no hay `OPENAI_API_KEY`; instancia el cliente |
| 02, 07 | `SystemExit` si no hay `PROYECTO`, y llaman a `verificar_estado()` |
| 06 | `SystemExit` si no hay `PROYECTO` |
| 03 | lee `script.txt` a nivel de módulo |

O sea que un test tendría que preparar el entorno antes de importar. Lo barato es mover esas
guardas dentro de `main()` en el paso que se quiera probar — un cambio por script, sin tocar la
lógica.
