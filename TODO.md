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

⚠️ Los 8 guiones publicados ya están **leídos uno por uno** (15 ago, desde los `.srt`): dos afirman
cosas falsas y no deben publicarse tal cual. Ver [P-02](#p-02).

| | # | Pendiente |
|---|---|---|
| 🔴 | [P-02](#p-02) | `Historia07` y `Historia06` afirman cosas falsas — el primero estaba programado |
| 🟠 | [P-04](#p-04) | El crítico de Anthropic nunca se ha ejecutado |
| 🟠 | [P-12](#p-12) | `se_quedaron_pct` bajó — la única métrica que empeoró en v2 |
| 🟡 | [P-19](#p-19) | `DELAY = 7.0` uniforme en el paso 05 — ~2-3 min/video dormidos |
| ⚪ | [P-06](#p-06) | Paralelizar los temas — evaluado: no compensa todavía |
| 🔵 | [P-17](#p-17) | Afinar el recordatorio con unas semanas de uso (ya funciona y está en cron) |
| ✅ | [P-14](#p-14) | ~~`proyectos/T1/` anidado~~ — hecho: 43 filas de métricas recuperadas |
| ⚪ | [P-07](#p-07) | Basura de corridas viejas (~750 MB recuperables) |
| ⚪ | [P-08](#p-08) | Los 16 Mundial no tienen `descripcion.txt` ni `.srt` |
| ⚪ | [P-09](#p-09) | ¿Se sigue usando el carrusel de Instagram? |
| ⚪ | [P-09b](#p-09b) | Automatizar la recogida de métricas por API |
| ⚪ | [P-10](#p-10) | `publisher.py` sigue incompleto |
| ⚪ | [P-18](#p-18) | La cabecera del paso 06 miente sobre su entrada |
| 🟡 | [P-11](#p-11) | Tests: hecho `herramientas/` + `estado.py` (52), falta `pipeline/` |

---

## 🔴 Bloquean el lote actual

<a id="p-02"></a>
**P-02 · Dos de los 8 guiones publicados afirman cosas falsas. Uno estaba programado.**

⚠️ **Los `proyectos/Historia0*/calidad_guion.json` NO juzgan los guiones que se publicaron.**
Están todos escritos el 15 ago a las 11:46 — los generó la medición de Opus contra gpt-4.1, no el
pipeline, y el campo `guion` de cada uno trae el texto que se le dio al crítico en esa prueba, que
no es el del video. Se ve de un vistazo comparando con `social_posts/metadata.json` (del 7 ago):
el JSON de `Historia02` habla de Psamético III en Egipto y el video se llama *Batalla de Halys*;
el de `Historia03` cuenta el ahorcamiento de las sirvientas y el video va de los Lestrigones.
**El texto real de cada video está en su `.srt`** (`proyectos/$PROYECTO/*.srt`), que es la
transcripción de la voz. Es la única fuente fiable de qué se publicó.

Revisados los 8 `.srt` uno por uno (15 ago):

| | Riesgo | Qué le pasa al guion publicado |
|---|:--:|---|
| Historia07 Galeón | 🔴 | **El barco existe y la historia es falsa.** La *Santísima Trinidad y Nuestra Señora del Buen Fin* (1751) fue el mayor galeón de Manila; en 1762 la **capturaron los ingleses** y la vendieron en Portsmouth. No explotó ni se hundió. El «gabinete secreto que nadie explica» está inventado |
| Historia06 Surrealismo | 🔴 | *Prohibió relojes, cortó la electricidad, solo él tenía fósforos, Breton impedía salir.* Nada de eso aparece en el registro documentado |
| Historia01 Power bank | 🟠 | Mezcla dos sucesos: el incendio a bordo y un retiro de «más de 2 millones de baterías» — el retiro de Samsung fue de teléfonos Note 7 |
| Historia03 Lestrigones | 🟠 | Se contradice: *«gigantes caníbales»* y tres frases después *«sin dioses ni monstruos, solo humanos hambrientos»* |
| Historia02 Halys | 🟡 | *«dos ejércitos **lidian** bajo el mismo sol»* — se comió a los **lidios**. No es falso, se lee como el verbo *lidiar*, pero el espectador nunca sabe quiénes eran |
| Historia04, Historia05, Historia08 | ✅ | Limpios. Robin Hood, el tesoro de San Lorenzo y el examen de ingreso al ETH están bien contados (único matiz: Einstein conoció a Grossmann ya en el ETH, no en el año de Aarau) |

**Acción: `Historia07` fuera de `publicar/calendario.csv` — estaba programado para el 16 ago — y
`Historia06` no se publica tal cual.**

Lo que esto dice del pipeline: **el crítico viejo (gpt-4.1) dejó pasar los dos rojos.** El de Opus
sí los habría visto — su crítica a `Historia09` nombra a Valerios Stais, el Museo Nacional de
Atenas, el año 1902 y corrige «lujo romano» → objetos griegos. La puerta no aprueba nunca
([P-04](#p-04)), pero **el diagnóstico ya vale**: léelo como lista de verificación antes de
programar, que es justo para lo que sirve hoy.

Y el problema de fondo sigue entrando por `temas.csv`: `2016`, `Eclipse`, `Odisea` y
`Surrealismo` son categorías, no incidentes. Cuando el tema no trae una historia concreta, el
modelo se la inventa. Es lo que advierte
[INSTRUCCIONES_CHATGPT.md](INSTRUCCIONES_CHATGPT.md): *"UNA SOLA LÍNEA NARRATIVA. Un incidente
concreto con principio y final, no la biografía de alguien."*

---

## 🟠 Calidad del producto

<a id="p-04"></a>
**P-04 · Calibrar el umbral de aprobación para el crítico de Anthropic.**
✅ La clave ya está puesta (15 ago) y el crítico corre en `claude-opus-5`. Encontró en la primera
prueba un error que gpt-4.1 no habría visto: llamaba **cirujano** a John Smeaton, que era ingeniero
civil. También se añadió el aprendizaje entre temas (ver
[HISTORIAL.md](HISTORIAL.md#-el-generador-aprende-de-los-veredictos-15-ago-2026)).

**Lo que queda es que el umbral no vale para este crítico.** Medido sobre los 8 guiones:

| Tema | gpt-4.1 | Opus 5 | dudosas |
|---|---:|---:|---:|
| Historia02 | 3 | 2 | 7 |
| Historia05 | 4 | 2 | 5 |
| Historia08 | 6 | 2 | 6 |
| Historia04 (el único aprobado) | 8 | **3** | 3 |

Opus comprime todo entre 2 y 3 y encuentra dudosas en **todos**. Aprobar exige `nota >= 7` **y**
cero dudosas, así que **no aprueba nunca**: cada tema quema los 3 intentos, ~$0.10 de control de
calidad frente a los ~$0.019 de antes.

⚠️ **No lo ajustes a ojo.** No hay ni un dato de qué puntúa Opus a un guion que él considere bueno
—los 4 medidos son malos para su criterio—, así que bajar `nota_minima` a 4 o 5 es adivinar.
**Corre el próximo lote, mira la distribución de notas y dudosas, y fija el umbral con eso.** Si
sale que ni el mejor pasa de 3, la conclusión no es bajar el listón: es que el formato de 70
palabras no puede ser "sin afirmaciones dudosas" y el crítico vale como **lista de verificación**
(P-02), no como puerta.

Mientras tanto: `intentos_max: 2` ahorraría un tercio del costo, porque el tercer intento paga una
crítica de $0.029 para una puerta que no se abre.

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

⚠️ **Ojo con lo que se mide ahora.** El lote que venga ya llevará los planos dispersados (P-15,
hecho el 15 ago), que cambia el ritmo percibido a propósito. Si `se_quedaron_pct` sube, no habrá
forma de saber si fue eso o el gancho. Si quieres separarlo, genera un par de temas con
`dispersar_planos: False` en el `CONFIG` del paso 07 y compáralos — es un interruptor, no hay que
tocar código.

---

## 🟡 Tiempo y costo

Medido sobre `Historia01` (13m 41s de punta a punta) y `.costo_actual.json` ($0.24827).

**Los pasos 05 y 07 son el 91% del tiempo.** El 05 (4m 56s) está casi todo **dormido**:
`DELAY = 7.0` uniforme, aplicado en cuatro puntos, más un ciclo extra por cada foto que el filtro
de visión rechaza. El 07 (7m 34s) sí trabaja, pero el techo es el hardware: **i5-7200U, 2 núcleos
de 2016**, corriendo whisper `medium` y 766 frames compuestos en Python con PIL.

✅ **El 07 ya bajó a ~5m 50s** con el arreglo de P-05 (15 ago): la composición pasó de 3.23 a
5.12 fps. Eso cambia el reparto — ahora el 05 y el 07 pesan parecido, y el 05 es el que sigue
dormido.

**El 74% del costo es fal.ai**: 6 imágenes × $0.0306 (832×1472 = 1.225 MP × $0.025/MP).
OpenAI son $0.052 (21%), de los cuales $0.023 es el control de calidad del guion — bien gastados.
ElevenLabs, $0.012 (5%).

| Palanca | Gana | Riesgo |
|---|---|---|
| **[P-19](#p-19) · `DELAY` por fuente en el paso 05** | ~2-3 min/video | bajo — es el siguiente que haría |
| whisper `medium` → `small` | 1-2 min/video | hay que revisar el `.srt`, que sí se publica |
| `gpt-4.1-mini` en las llamadas mecánicas (queries, contexto, gancho, validación visual) | $0.0066/video | bajo — son tareas de extracción, no de criterio |
| 6 → 5 imágenes | $0.031/video (12%) | 5 imágenes para 14 cortes empieza a repetirse |

<a id="p-19"></a>
**P-19 · `DELAY = 7.0` uniforme en el paso 05.**
Se aplica igual a Wikimedia Commons (líneas 308, 320, 328) que a DuckDuckGo (354). **Wikimedia es
una API pública documentada y el que bloquea es DDG**, así que ~1.5 s en el primero y 7 s en el
segundo es razonable y educado.

No es un ahorro teórico: el filtro de visión rechaza mucho y cada rechazo cuesta otra espera de
7 s. Medido en el log de `Historia08`, **28 rechazos o fallos** en un solo tema.

Es la palanca de tiempo con mejor relación esfuerzo/riesgo que queda, y **la alternativa barata a
[P-06](#p-06)**: gana un tercio de lo mismo tocando una constante en vez de reescribir el lote.

<a id="p-06"></a>
**P-06 · Paralelizar los temas — evaluado el 15 ago: NO compensa todavía.**
La nota anterior decía "el lote pasaría de ~1h50m a ~50 min". Medido, no sale esa cuenta:

| Qué se midió | Resultado | Qué implica |
|---|---|---|
| CPU que usa el paso 07 | **203 % de 400 %** | dos renders a la vez ya saturan la máquina; no hay 2× que ganar |
| RAM pico del render | **1.35 GB** (+ ~1.5 GB de whisper `medium`) | dos temas ≈ 5-6 GB con 5 GB libres → riesgo de swap |
| Recursos de la raíz en colisión | **5** (`script.txt`, `voice.mp3`, `images_IA/`, `source_images/`, `social_posts/`) | resolubles con un directorio de trabajo por tema |

Y el bloqueo de verdad **no es el que decía la nota**: es que **`.env` es el transporte entre
pasos**. El paso 02 escribe ahí `TITULO_VIDEO` y el 07 lo lee. Con dos temas a la vez, el 02 del
tema B pisa el título antes de que el 07 del tema A lo lea, y ese texto va **quemado en el frame 0**.
⚠️ Un directorio de trabajo por tema **no lo arregla**: `load_dotenv()` busca el `.env` desde la
carpeta del script, no desde el directorio de trabajo, así que los dos temas leerían el mismo.

**Requisito previo, y es barato:** que el título viaje por `social_posts/metadata.json` —donde el
paso 02 **ya lo escribe**— en vez de por el `.env`. Eso quita el único dato mutable compartido que
no se arregla aislando carpetas, y de paso elimina un round-trip por un archivo que lee `bash`
(el mismo que ya dio el susto de la prosa ejecutable).

**Veredicto:** el techo real de la paralelización en esta máquina es ~25-35 %, no el 55 % que
suponía la nota, y exige reescribir `run_all.sh` — la pieza con más historial de bugs sutiles
(stdin, encabezado, nombres mutilados). [P-19](#p-19) da un tercio de esa ganancia tocando una
constante. **Hacer P-19 primero; volver a P-06 solo si el lote crece bastante o cambia la máquina.**

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
**P-14 · ✅ HECHO (15 ago) · `proyectos/T1/` anidado dejaba 78 de 147 filas sin `PROYECTO`.**
Se aplicó la salida 2 (glob a dos niveles en `indice_proyectos()`, sin mover nada de sitio). El
índice pasó de **28 a 50 proyectos** —los 22 de `T1/` eran invisibles— y `metricas.csv` de **78 a
35 filas sin `PROYECTO`**: 43 recuperadas, con TikTok al 15/15. Las 147 filas siguen siendo 147,
así que no se creó ni se perdió ninguna medición, solo se les puso nombre. Los rellenos a mano de
`mapa_manual.csv` no se tocaron. Queda el texto de abajo como registro de por qué pasaba.


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

**P-11 · Tests: hechos `herramientas/` y `estado.py`, faltan los 8 pasos.**

✅ **Hecho el 15 ago:** `tests/` con **52 tests** de `unittest` (stdlib, sin red, ~0.05 s) sobre
[10_metricas.py](herramientas/10_metricas.py), [11_reporte.py](herramientas/11_reporte.py) y
[estado.py](pipeline/estado.py) — `comparar_lotes()`, `TIPO_METRICA`, el signo de la comparación,
mediana vs promedio, la pegajosidad del lote, el índice a dos niveles, los decimales de Facebook,
la fila de TikTok sin escapar, el sello del tema, los reintentos y **que todo modelo nombrado en
`pipeline/` esté en `PRECIOS_OPENAI`** (hoy detecta `gpt-4.1` y `gpt-5.4`).

Se eligieron **por tipo de fallo, no por cobertura**: en el pipeline un error se nota —el tema
aborta o el video sale mal—, pero aquí no se nota nada, el informe se genera igual y afirma lo
contrario de lo que pasó. Verificados por mutación: desactivando cada mecanismo (pegajosidad del
lote, glob a dos niveles, `vistas_por_dia` como tasa, signo invertido, media en vez de mediana),
los tests correspondientes fallan.

**Queda `pipeline/`:** `separar_hashtags()`, `repartir_planos()`, `dispersar_planos()`,
`verificar_reglas_mecanicas()`, `sanear_valor_env()` y el parseo de `carrusel.txt` del paso 06.

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
