# TODO — lo que queda por hacer

> **Este documento solo lleva trabajo pendiente.** Lo ya resuelto está en
> **[HISTORIAL.md](HISTORIAL.md)** con lo que se midió en cada caso. Léelo antes de tocar el
> pipeline: casi todo valor que parece arbitrario en el código sale de un fallo documentado allí.
>
> Operar el pipeline (generar, empaquetar, programar, medir) es **[README.md](README.md)**.
> Arquitectura y trampas del código, **[CLAUDE.md](CLAUDE.md)**.

## Dónde vamos

**Estado a 25 ago 2026.** El pipeline lleva **diez días publicando solo**: 8 reels,
6 extras y tres fallos de Instagram de los que la agenda se recuperó ella sola al
día siguiente. La automatización funciona.

⚠️ **Pero Facebook no distribuye nada desde el 15 ago** ([P-31](#p-31)) y **el
calendario se agota mañana con `Historia15`**: hace falta generar el lote
siguiente.

| | `v2-mas-cortes` (Historia01-08) | `v3-guion-y-dispersion` (Historia09-15) |
|---|---|---|
| Resultado | +513 % vistas 24 h, CTR +785 %, retención +32 % vs baseline | 7 de 7, **65 min**, 9.3 min/tema, **$0.285** de mediana |
| Qué lleva | más cortes, −14 LUFS, gancho sin spoiler | guionista `gpt-5.4`, crítico Opus 5, planos dispersados, títulos acortados |

Verificado sobre los 7: **0 transiciones repetidas** de 15-18 y **0 títulos** fuera del límite de
70 caracteres.

⚠️ **La decisión de operación es que nadie revise guiones a mano.** Por eso la puerta del paso 01
**aborta el tema** en vez de avisar, y lo que queda por hacer se mide por si **reduce intervención
humana**, no por si mejora un número.

**Tu semana son ahora dos cosas** (~20 min): elegir los temas y correr los cuatro comandos de
métricas. Generar, empaquetar y publicar en Instagram, Facebook y Threads va solo; de subir a mano
solo quedan YouTube y TikTok, las dos cuyo trámite de publicación por API no compensa.

| | # | Pendiente | Gana |
|---|---|---|---|
| 🔴 | [P-31](#p-31) | Facebook no distribuye desde que publicamos por API | todo el alcance de una red |
| 🟡 | [P-33](#p-33) | El informe compara 2 lotes y ya hay 3: falta `v3` vs `v2` | la pregunta real |
| 🟡 | [P-32](#p-32) | Los carruseles nunca alcanzaron a nadie: ¿se quitan? | 2 días de semana |
| 🟡 | [P-20](#p-20) | Por qué menos gente para el scroll (el frame 0) | la única métrica en contra |
| 🟡 | [P-26](#p-26) | TikTok: 3 columnas que ninguna API pública da | ~5 min/semana |
| 🔵 | [P-22](#p-22) | Vigilar la primera semana de publicación automática | confianza |
| 🔵 | [P-23](#p-23) | ¿Un equipo siempre encendido? Decidir con datos | la hora exacta |
| 🔵 | [P-25](#p-25) | ¿Rinde Threads de verdad? Volver a mirar con n suficiente | dónde poner el esfuerzo |
| 🔵 | [P-17](#p-17) | Afinar el recordatorio con unas semanas de uso | ruido |
| ⚪ | [P-29](#p-29) | 880 MB de intermedios y de una prueba | espacio en disco |

✅ **P-27 y P-28 cerrados el 25 ago**, justo antes de recoger las métricas de la
semana — que es cuando habrían mordido. El aviso nuevo del informe saltó a la
primera y avisó de que las **26 filas de `v2-mas-cortes` se caían del veredicto**
en silencio.

---

## 🔴 Lo que miente en silencio

<a id="p-31"></a>
**P-31 · Facebook dejó de distribuir los reels el día que empezamos a publicar por API.**

Medido el 18 ago. No es «rinden poco»: es **alcance 1-2 personas**.

| fecha | vistas | alcance | seguidores | origen |
|---|---:|---:|---:|---|
| 09 ago | 322 | 275 | 116 | manual |
| 11 ago | 1154 | 1001 | 119 | manual |
| 13 ago | 988 | 843 | 123 | manual |
| 14 ago | 289 | 239 | 127 | manual |
| 16 ago | 9 | **2** | 128 | API |
| 17 ago | 7 | **2** | 128 | API |
| 18 ago | 2 | **1** | 128 | API |

Los seguidores crecían solos y se congelaron el 15 ago, el día del cambio.

**Descartado con datos, no por intuición:**

| Hipótesis | Cómo se descartó |
|---|---|
| La app o el token | Instagram usa **los mismos** y su alcance es normal (105-261) |
| El vídeo | Mismos 1080×1920, 4 renditions, 11 miniaturas, `copyright_check` sin match |
| Visibilidad | `EVERYONE`, `is_hidden: false`, permalink **200 sin sesión**, en `/feed` |
| El tipo de objeto | Los manuales también son reels (`/reel/<id>/`, `added_video`) |

**Lo único que difiere:** los de Metricool llevan `title` y los nuestros no.
⚠️ **Y eso no prueba la causa**: «sin título» y «publicado por nuestra app» son
la misma columna en estos datos — no hay ni un manual sin título ni un
automático con él.

### Lo que se probó el 18 ago, y por qué cambia la hipótesis

Se intentó ponerle `title` al reel de `Historia09` (35 h, alcance estancado en 2,
el más fresco de los muertos y sin la anomalía de hashtags de `Historia07`).

⚠️ **Facebook respondió `{"success": true}` y NO guardó el título.** Releído
después: sigue en `None`. O sea que **`title` no se puede poner en un objeto de
`video_reels`** — ni al crearlo ni después. Es exactamente el fallo silencioso
para el que se escribió `_verificar_titulo()`, y salió a la primera.

**Eso hunde la hipótesis del título como causa** y deja una mucho mejor, porque
si el campo no es escribible aquí, los manuales **no se hicieron por aquí**:

| | `post_views` (vistas que vienen del post del muro) |
|---|---|
| manual | 136 · 275 · 56 · 314 |
| API | 0 · 1 · 1 · 1 |

Los manuales sacaban **un tercio de sus vistas del muro**; los nuestros, ninguna.
Sumado a que llevan `title` —campo que sí admite `/videos` y no `/video_reels`—
la lectura es que **Metricool los subía por `/videos`**, creando un post de vídeo
de verdad que Facebook además enseña como reel, mientras que `/video_reels` crea
un reel puro que nunca llega al muro ni, por tanto, a los seguidores.

**El título era un marcador del camino de subida, no la causa.**

### La semana completa (25 ago): ya no hay duda

Se dejó correr ocho publicaciones. Comparado contra **todo** el histórico, no
contra los cuatro anteriores:

| grupo | n | mediana | mín | máx |
|---|---:|---:|---:|---:|
| facebook manual | 45 | **544** | 4 | 5.079 |
| facebook por API | 8 | **2** | 2 | 2 |

⚠️ **Los ocho dieron exactamente 2. No 1, no 3: dos, ocho veces.** Eso no es una
penalización de ranking —eso daría dispersión— sino **un interruptor apagado**.
Junto con `post_views` (0-1 nuestros contra 57-2.599 los manuales), el mecanismo
es que `/video_reels` crea un reel que **nunca aterriza en el muro**, así que no
llega a los 128 seguidores, que son la semilla de toda la distribución.

**✅ Hecho el 25 ago:** `CONFIG["endpoint_facebook"] = "videos"`.
`publicar_facebook_videos()` sube por `/videos` en una sola llamada multipart,
manda `title` (que `/video_reels` no admitía) y devuelve el **`post_id`**, con lo
que de paso cierra [P-30](#p-30) para los nuevos. Se vuelve atrás cambiando el
`CONFIG` a `"video_reels"`.

**La prueba se hace sola:** `Historia15` sale **el 26 a las 12:00** por el camino
nuevo, a la hora canónica. No hace falta publicar nada a mano.

### Los ocho muertos: borrados y en cola para resubir (25 ago)

Decisión de operación: no se dan por perdidos. Los 8 reels se **borraron de
Facebook** (verificando cada borrado releyendo el objeto, no fiándose del
`success`) y sus proyectos vuelven al calendario para que la agenda los resuba
por `/videos`, uno al día:

| | |
|---|---|
| Evidencia previa | [`evidencia/p31_reels_video_reels.json`](evidencia/p31_reels_video_reels.json) — alcance, `post_views`, duración y descripción de los 8, **antes** de borrarlos |
| `publicado.csv` | fuera las 8 filas de `facebook` (las de `instagram` se quedan: esas sí funcionaron) |
| Calendario | `Historia07`→27 ago … `Historia14`→3 sep, **después** de `Historia15` |

⚠️ **El orden no es casual: la resubida empieza el 27, un día después del
veredicto de `Historia15`.** Si el 26 no revive, hay tiempo de parar antes de
gastar ocho publicaciones más por el camino equivocado — basta con borrar esas
filas del calendario.

⚠️ **Facebook nunca verá esos 8 videos en `metricas.csv`**, porque los borramos
antes de la primera consolidación. Su único registro es el JSON de evidencia, y
está bien así: meterlos habría hundido las medianas del lote con ocho `alcance 2`
de un camino de publicación que ya no usamos.

⚠️ **Riesgo asumido:** resubir el mismo vídeo que ya estuvo publicado puede leerse
como contenido repetido. Se borró antes de resubir precisamente para que no haya
dos copias vivas, pero si Meta lo marca, se vería en la resubida de `Historia07`
el 27 y habría que parar.

<a id="p-32"></a>
**P-32 · Instagram NO tiene el problema — y los carruseles nunca funcionaron.**

Esto sale de medir contra el histórico entero en vez de contra las últimas
semanas, y **corrige dos impresiones equivocadas** (una del usuario y otra mía):

| grupo | n | mediana | mín | máx |
|---|---:|---:|---:|---:|
| reel instagram manual | 45 | 127 | 14 | 2.984 |
| reel instagram por API | 8 | **146** | 80 | 272 |
| carrusel instagram manual | 5 | **2** | 2 | 2 |
| carrusel instagram por API | 3 | **5** | 1 | 7 |

⚠️ **Los reels de Instagram por API van MEJOR que la línea de base**, no peor. La
sensación de «también cayó» viene de compararlos con los tres manuales grandes
que cayeron justo antes del cambio (2.984, 1.159, 1.064); la mediana real de 45
manuales es 127. **No hay nada que arreglar en Instagram, y el esfuerzo que se
ponga ahí es esfuerzo tirado.**

⚠️ **Los carruseles llevan muertos desde siempre**: los cinco manuales de mayo
dieron **2 de alcance cada uno**. No es una regresión del API — de hecho los de
API van algo mejor (mediana 5). El álbum de Facebook de `Historia04` sacó **0
reacciones y 1 clic**.

**La decisión que toca, y es de producto, no de código:** la agenda gasta dos de
los tres días de extras (martes carrusel de IG, jueves álbum de FB) en un formato
que **nunca ha alcanzado a nadie en esta cuenta**. O se le busca una razón para
seguir, o se quitan esas dos entradas de `dias_extra` en
[16_agenda.py](herramientas/16_agenda.py) y se deja el hilo de Threads, que al
menos tiene un techo de 22.024 ([P-25](#p-25)). El paso 06 seguiría existiendo
para el archivo.


---|
| [10_metricas.py](herramientas/10_metricas.py) | `v3-guion-y-dispersion` ← con lo que se **etiqueta** |
| [11_reporte.py](herramientas/11_reporte.py) | `v2-mas-cortes` ← con lo que se **compara** |

Hoy no se nota porque `Historia09`-`Historia15` aún no tienen ni una fila (empiezan
a publicarse mañana). En cuanto la tengan, sus métricas entrarán a `metricas.csv`
como `v3` y el informe **no las mirará**: no son `lote_nuevo` para él, tampoco son
`baseline`, así que **desaparecen del veredicto sin aparecer en ningún sitio**. El
informe seguirá comparando `v2` contra `baseline` y diciéndolo con toda claridad,
que es lo que lo hace difícil de pillar.

**Dos arreglos posibles, y el segundo es el bueno:**
1. Acordarse de subir `lote_nuevo` a mano en los dos archivos. Es lo que ya falló.
2. Que `11_reporte.py` **lea el `lote_nuevo` del paso 10** en vez de tener el suyo,
   y que avise si encuentra en `metricas.csv` algún `lote` que no sea ni el nuevo
   ni el baseline. Un lote huérfano es siempre un error; que lo diga él.

---

## 🟡 Producto y datos

<a id="p-20"></a>
**P-20 · Menos gente para el scroll, y no se sabe por qué.**
Sale de cerrar [P-12](HISTORIAL.md#-la-curva-de-retención-cierra-p-12-15-ago-2026): la curva de
retención **descartó** las dos hipótesis que había (el gancho y el ritmo del primer corte). v2 va
por delante en **todos** los puntos desde el segundo 0.5, entre +9 % y +16 %.

Lo que baja es `se_quedaron_pct` (−16 %), y mide otra cosa: de los que el Short **empieza a
reproducirse en el feed**, cuántos no deslizan. O sea que la pérdida ocurre **antes de que la curva
empiece**. Lo único que actúa ahí es lo que se ve sin reproducir: **el primer frame**, que es
`images_IA/scene_0.png` con el título quemado encima.

**Cómo aislarlo, y es barato:** un par de temas con `title_duration` distinto —o sin título en el
frame 0— y comparar. Es `CONFIG` del paso 07, no hay que tocar código.
⚠️ n=6 en v2 y los lotes difieren en muchas cosas a la vez (duración, gancho, cortes, música).
Esto **acota** el problema, no lo demuestra.
⚠️ `se_quedaron_pct` **no la da la API** (ver [P-26](#p-26)): para seguir midiendo esto hay que
descargar el export de YouTube.

<a id="p-26"></a>
**P-26 · TikTok: tres columnas que ninguna API pública da.**

[P-09b](#p-09b) está cerrado —las cinco redes bajan métricas por API— pero TikTok **no dejó de
teclearse del todo**, y conviene que quede claro por qué.

La Display API trae vistas, me gusta, comentarios, compartidos y la **duración**. Lo que no trae, y
sigue saliendo de `metricas_export/manual.csv`:

| Columna | Dónde está |
|---|---|
| `alcance` | Solo en pantalla, video por video |
| `duracion_media_s` | Solo en pantalla |
| `se_quedaron_pct` | Solo en pantalla |

⚠️ **No es un permiso que falte: no existen en la Display API.** Están en la *Research API*, que
pide acreditación académica y no la vamos a tener. Así que esto no se «arregla»: o se teclean, o se
vive sin ellas — y sin `duracion_media_s` no hay `retencion_pct` de TikTok.

**Lo que sí ganó la API**, medido el 16 ago:

| | export | API |
|---|---:|---:|
| Videos | 15 | **41** |
| `duracion_s` | prestada de otra red | **nativa, 41/41** |

Los 26 videos de más son los anteriores al pipeline, que el export no traía. Y la duración nativa
importa: antes solo la tenían los que emparejaban un `PROYECTO` con otra red.

**Decidir con uso:** si al cabo de unas semanas `retencion_pct` de TikTok no se usa para nada en el
informe, lo honesto es sacar esas tres de `CAMPOS_MANUALES` y dejar de pedirlas.

---

## 🔵 Operación y seguimiento

<a id="p-22"></a>
**P-22 · Vigilar la primera semana de publicación automática.**

Desde el 15 ago `cron` publica solo: el reel a las 12:00 y el extra semanal a las 18:00.

✅ **Primera corrida real: 16 ago, 12:00.** `Historia08` salió en Instagram (`1812283566…`) y
Facebook (`1601375514…`), las dos anotadas en `publicado.csv`, sin intervención. También quedó
confirmado que `cron` va bien: el recordatorio de las 10:00 de ese mismo domingo se envió solo.

Lo que hay que mirar durante una semana **no es si funciona —eso ya salió— sino lo que ninguna
prueba puede anticipar**:

- **`logs/agenda.log`**, que es donde va todo. Un fallo de red a las 12:00 no avisa a nadie: la
  agenda lo escribe ahí y sigue. Merece que el recordatorio del paso 12 lo mire (una línea).
- **Que la cadencia se vea bien en la página.** Reel diario + extra semanal son 8 publicaciones por
  semana en Instagram y otras 8 en Facebook. Si es demasiado, la palanca es `dias_extra` en el
  `CONFIG` de [16_agenda.py](herramientas/16_agenda.py), no tocar el `cron`.
- **Si el álbum de Facebook rinde.** Es lo único que no tiene precedente: el carrusel se ha
  publicado a mano en Instagram, pero como álbum de Facebook no lo hemos visto nunca. Si no aporta,
  se quita esa entrada de `dias_extra` y ya.

⚠️ **El calendario se agota el 2026-08-23.** A partir de ahí `--reel` no encuentra fila y lo dice
en el log, pero **no avisa**: hay que generar el paquete del lote siguiente. El recordatorio de los
domingos ya mira `publicar/calendario.csv`, así que esto es más un recordatorio de que existe.

<a id="p-25"></a>
**P-25 · ¿Rinde Threads de verdad? Volver a mirar con n suficiente.**

Ya está en `metricas.csv` ([P-24](#p-24) cerrado), y la primera lectura **no confirma ni desmiente**
lo que se veía a ojo. Medianas de vistas, 15 ago:

| Red | Mediana | Máximo | n |
|---|---:|---:|---:|
| facebook | 674 | 6.068 | 45 |
| tiktok | 664 | 3.320 | 15 |
| **threads** | **616** | **22.024** | **6** |
| youtube | 448 | 3.209 | 40 |
| instagram | 165 | 4.241 | 45 |

⚠️ **La mediana de Threads es del montón; lo que se sale es el techo** — 22.024 vistas, 3,6× el
mejor post de Facebook. Con n=6 eso puede ser un hilo que se viralizó y nada más, así que la
sensación de «Threads da mucho alcance» **puede venir entera de ese caso**. No es motivo para
apostar por la red ni para descartarla: es motivo para esperar.

Con un hilo por semana, hacen falta ~2 meses para tener n≈14 y poder decir algo. Lo que hay que
mirar entonces:

- ¿El techo se repite, o fue una vez? Si se repite, Threads es la red de mayor varianza y merece
  más de un hilo por semana.
- ¿Los hilos automáticos rinden como los que escribías a mano? Los 6 de la tabla son **todos
  manuales**; el primero automático es del 15 ago.
- Si rinde, la palanca es `dias_extra` en [16_agenda.py](herramientas/16_agenda.py) — subirlo a dos
  días no cuesta nada, porque el hilo se genera del guion que ya existe (~$0.002).

<a id="p-23"></a>
**P-23 · ¿Merece la pena un equipo siempre encendido?**

Con el PC apagado no se pierde nada —la agenda recupera lo atrasado, uno por día— pero **la hora sí
se pierde**, y la hora es una de las condiciones que mantiene comparables los lotes. Un video que
sale a las 20:00 en vez de a las 12:00 ensucia la medición de un modo que ninguna columna registra.

Programar en la plataforma **no lo resuelve**: medido el 15 ago, `scheduled_publish_time` funciona
en Facebook, Instagram responde *«User must be on whitelist»* y Threads no lo tiene. Cubre una red
de tres.

Así que la opción real es un equipo encendido: un VPS de ~5 €/mes o una Raspberry Pi. **Solo
necesita la parte de publicar**, no la de generar: el repo, el `.env` y `publicar/` (~140 MB por
semana, un `rsync` después de cada lote). La generación se queda donde está, que es donde están la
GPU y los 1.6 GB.

**Decidir después de unas semanas**, cuando se sepa cuántos días se pierde la hora de verdad. Si
son uno o dos al mes, no compensa.

<a id="p-17"></a>
**P-17 · Afinar el recordatorio con unas semanas de uso.**
El bot ya funciona (`@CHvideo_bot`) y está en `cron`: domingo 10:00 y 16:00, más `--si-falta` de
lunes a sábado por si ese domingo tuviste el equipo apagado. Montaje en
[HISTORIAL.md](HISTORIAL.md#-el-recordatorio-semanal-por-telegram-15-ago-2026).

Dos ajustes que **solo se deciden con uso**, no ahora:

- **¿Avisa de demasiados guiones?** Con la puerta abortando ([P-04](HISTORIAL.md)), los guiones
  malos ya no llegan a publicarse, así que ese aviso debería quedarse casi siempre vacío. Hay que
  ver si sigue teniendo sentido.
- **¿Adjuntar `reportes/ultimo.html`?** Se dejó fuera: pesa 51 KB y Telegram lo manda como archivo.
  Si nunca lo abres desde el móvil, mejor las 3-4 cifras en el mensaje (ya lo hace).

---

<a id="p-33"></a>
**P-33 · El informe solo sabe comparar DOS lotes, y ya hay tres.**

Al consolidar el 25 ago saltó el aviso nuevo: **`v2-mas-cortes` (54 filas) se
queda fuera del veredicto**. No es un fallo —es una tanda cerrada y el aviso hace
justo lo que debe— pero deja ver el límite: `comparar_lotes()` contrasta
`lote_nuevo` contra `lote_baseline` y no hay sitio para un tercero.

⚠️ **Y el tercero es el que interesa.** `v3` contra `baseline` mide «pipeline
nuevo contra los videos de antes de todo esto»; lo que de verdad se quiere saber
es **`v3` contra `v2`**: si el guionista `gpt-5.4`, el crítico de Opus y los
planos dispersados mejoraron algo sobre la tanda anterior. Hoy esa comparación
no se puede leer en ninguna parte.

De momento se ve a mano; el arreglo es que `comparar_lotes()` acepte qué dos
lotes contrastar y que el informe saque las dos tablas.

---

## ⚪ Deuda y limpieza

<a id="p-29"></a>
**P-29 · 880 MB de intermedios y de una prueba. Decidir, no borrar a ciegas.**

Medido el 16 ago, con el proyecto en **2,1 GB**:

| Qué | Pesa | ¿Se puede borrar? |
|---|---:|---|
| `videos_no_music/` | **858 MB** | Sí, pero **no es gratis**: son la entrada del paso 08 |
| `videos/video_Test01.mp4` + `proyectos/Test01/` + `publicar/Test01/` | **22 MB** | Sí, es una prueba |
| `logs/` | 42 MB | Sí; casi todo son barras de progreso de moviepy |

⚠️ **`videos_no_music/` no es basura: es lo que permite cambiar la música sin
rehacer el video.** El paso 08 es un mux de 3 segundos sobre ese archivo; sin él,
rehacer la mezcla obliga a repetir el paso 07 entero (whisper + moviepy, ~10 min
por video). La pregunta honesta es si alguna vez se va a querer recambiar la
música de un video ya publicado. Si la respuesta es no —y probablemente lo es—,
se borran los de los lotes ya medidos y se quedan solo los de la tanda en curso.

Ya hecho en esta revisión: **−38 MB** de `muestras_p15/` (las dos muestras de
[P-15](#p-15), que está cerrado y documentado) y de los `__pycache__`.

<a id="p-30"></a>
**P-30 · `publicado.csv` guarda el `video_id` de Facebook; `metricas.csv`, el `post_id`.**

`publicar_facebook()` devuelve el `video_id` de `me/video_reels` y eso es lo que
acaba en `publicar/publicado.csv`. Pero la parte de métricas del mismo archivo ya
hace lo correcto —`v.get("post_id") or v["id"]`, con su aviso al lado— porque el
export de Facebook trae el del **post**. Son dos ids distintos del mismo reel.

**No rompe nada hoy**: quien se apoya en `publicado.csv` (`ya_salio()` de la
agenda, `calendario_vencido()` del recordatorio) empareja por `proyecto` + `red`,
no por id, así que la protección contra publicar dos veces sigue intacta. Lo que
se pierde es poder **cruzar las dos tablas**: dado un reel en `metricas.csv`, no
hay forma de llegar a su fila de `publicado.csv`, ni al revés.

Arreglo: leer el `post_id` en la fase `finish` (o pedirlo después con
`fields=post_id`) y guardar ese. Un `id_video` extra al lado no sobra.

---

## Resueltos

Los anclajes se conservan porque el código y las otras notas enlazan aquí. El detalle de cada uno,
con lo que se midió, está en [HISTORIAL.md](HISTORIAL.md).

| # | Qué era | Cómo se cerró |
|---|---|---|
| <a id="p-02"></a>**P-02** | Guiones con datos falsos llegaban a publicarse | De raíz: la puerta del paso 01 **aborta el tema** en vez de avisar a un humano que no iba a leerlo |
| <a id="p-03"></a>**P-03** | 4 de 8 títulos de YouTube pasaban de 70 caracteres | `acortar_titulo()` reescribe con el modelo y `_truncar_titulo()` garantiza el límite en Python. 0 de 7 fuera en el lote siguiente |
| <a id="p-04"></a>**P-04** | La puerta de calidad no aprobaba nunca | Calibrada con los 7 temas reales: `nota >= 6` y `dudosas <= 3`. El problema no era el umbral, era el guionista |
| <a id="p-05"></a>**P-05** | El paso 07 componía un mask fantasma | `bg_color=(0,0,0)` en el composite interno: **×1.59** de velocidad, píxel a píxel idéntico |
| <a id="p-10"></a>**P-10** | Publicar en Meta era manual | `--publicar PROYECTO` por subida reanudable. `Historia07` estrenado el 15 ago en las dos redes |
| <a id="p-10b"></a>**P-10b** | Había que acordarse de correr el comando | [16_agenda.py](herramientas/16_agenda.py) lo dispara desde `cron`: reel diario a las 12:00, extra semanal a las 18:00 |
| <a id="p-09"></a>**P-09** | ¿Se sigue usando el carrusel? | Resuelto por el uso: la agenda lo publica sola los martes en IG y los jueves como álbum en FB. El paso 06 se queda |
| <a id="p-21"></a>**P-21** | Threads se publicaba a mano | [15_threads_api.py](herramientas/15_threads_api.py): hilo de 3 mensajes con 2 fotos reales, los sábados. Estrenado con `Historia01` |
| <a id="p-24"></a>**P-24** | Threads no estaba en `metricas.csv` | `--metricas`: **una fila por hilo**, no tres. Vistas de la raíz, interacciones sumadas y los comentarios sin contar nuestras propias respuestas. ¿Rinde? [P-25](#p-25) |
| <a id="p-06"></a>**P-06** | ¿Paralelizar los temas? | **Medido y descartado, no pendiente.** El techo real en esta máquina es 25-35 %, no el 55 % que suponía la nota vieja, y exige reescribir `run_all.sh`. **No lo vuelvas a proponer sin cambiar de máquina** — los números están abajo |
| <a id="p-18"></a>**P-18** | La cabecera del paso 06 mentía sobre su entrada | Docstring corregido (`carrusel.txt`, `source_images/`), la `parse_instagram_file()` muerta borrada y la viva renombrada a `parse_carrusel()`. Congelado en tests |
| <a id="p-07"></a>**P-07** | Basura de corridas viejas | **36 MB borrados.** ⚠️ Los slides obsoletos no estaban donde decía la nota, y su receta habría borrado el CTA bueno de dos respaldos: [HISTORIAL](HISTORIAL.md#limpieza-y-recuperación-de-los-lotes-viejos-15-ago-2026) |
| <a id="p-08"></a>**P-08** | Los 16 Mundial sin `descripcion.txt` ni `.srt` | Recuperados: el texto estaba en el formato viejo (`03_instagram.txt` + `04_facebook.txt`) y los `.srt` se rehacen desde el mp3 con el mismo whisper del paso 07. ⚠️ Se dio por cerrado el 15 ago **estando a medias** (10 de 16): el script vivía en un temporal y se lo llevó la limpieza del sistema sin que nada avisara. Ahora es [herramientas/18_rehacer_srt.py](herramientas/18_rehacer_srt.py), con `--listar` para no volver a creerse un «ya está» |
| <a id="p-09b"></a>**P-09b** | Métricas a mano en las 5 redes | Las cinco por API: YouTube, Meta, Threads y TikTok. ⚠️ De TikTok quedan 3 columnas que **ninguna API pública expone**: [P-26](#p-26) |
| <a id="p-27"></a>**P-27** | Un video de una tanda cerrada entraba como `baseline` | `lotes_historicos` en el `CONFIG` del paso 10, y `lote_de()` lo consulta **antes** que `temas.csv`. La pertenencia a una tanda es historia; `temas.csv` solo sabe cuál es la tanda en curso |
| <a id="p-28"></a>**P-28** | El informe comparaba `v2` mientras el paso 10 etiquetaba `v3` | `sincronizar_lotes()` los lee del paso 10 al arrancar, y `avisar_lotes_huerfanos()` canta cualquier lote que se quede fuera del veredicto, con la n al lado |
| <a id="p-11"></a>**P-11** | Tests solo de los pasos 01, 02 y 07 | +27 sobre los pasos **04, 05 y 06** ([tests/test_pasos_medios.py](tests/test_pasos_medios.py)), **166** en total |
| <a id="p-12"></a>**P-12** | `se_quedaron_pct` bajó en v2 | La curva de retención descartó gancho y cortes. Queda [P-20](#p-20), que es una pregunta distinta |
| <a id="p-14"></a>**P-14** | `proyectos/T1/` anidado dejaba 78 de 147 filas sin `PROYECTO` | Glob a dos niveles en `indice_proyectos()`: 43 filas recuperadas |
| <a id="p-15"></a>**P-15** | Los planos salían en pares de la misma imagen | `dispersar_planos()`: de 8 de 13 transiciones repetidas a **0 de 15-18** |
| <a id="p-19"></a>**P-19** | `DELAY = 7.0` uniforme en el paso 05 | Separado por fuente (1.5 s Wikimedia / 7 s DDG): **−2.7 min por tema** |
