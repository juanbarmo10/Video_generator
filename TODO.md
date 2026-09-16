# TODO — lo que queda por hacer

> **Este documento solo lleva trabajo pendiente.** Lo ya resuelto está en
> **[HISTORIAL.md](HISTORIAL.md)** con lo que se midió en cada caso. Léelo antes de tocar el
> pipeline: casi todo valor que parece arbitrario en el código sale de un fallo documentado allí.
>
> Operar el pipeline (generar, empaquetar, programar, medir) es **[README.md](README.md)**.
> Arquitectura y trampas del código, **[CLAUDE.md](CLAUDE.md)**.

## Dónde vamos

**Estado a 15 sep 2026.** El lote `v4` salió entero y la automatización aguantó:
se recuperó sola de tres fallos de subida de Instagram y de una caída de DNS.

**Pero el reel ya no lo publica nadie solo**, y por dos motivos distintos que no
hay que mezclar. Facebook (28 ago) salió porque **la app está restringida**;
Instagram (15 sep) sale **por decisión del dueño**.

**Facebook salió de la automatización por la app, no por el contenido.** No por un fallo del código
—publicaba bien— sino porque esta app de Meta solo enseña lo que publica en la
página a quien tenga un rol en ella, y solo tiene un administrador: diez
publicaciones con **alcance 2**, contra **1.039** del mismo vídeo por Metricool
([P-31](#p-31) en Resueltos). Se sube a mano, como YouTube y TikTok.

**Lo único que se publica solo es el hilo de Threads (sábados).** El álbum de
Facebook se quitó porque lo publicaba la misma app restringida, y el carrusel de
Instagram el 15 sep — ese **como experimento**, no como limpieza ([P-35](#p-35)).

⚠️ **El alcance de Instagram baja, pero un 38 %, no un 80 %** — [P-34](#p-34),
rehecho el 15 sep porque la primera versión comparaba contra la mejor semana de
la cuenta. Y no es lo que pasó en Facebook: aquello era un interruptor, esto es
reparto que se apaga poco a poco.

**Herramienta nueva: [19_figuras.py](herramientas/19_figuras.py)**, que dibuja
`metricas.csv`. El informe da medianas; las figuras dan la forma, que con n=6-9
es justo lo que una mediana esconde.

**Lote `v4-hashtags-limpios` (29 ago):** 10 temas pedidos, **9
completados y aprobados**, 1 abortado. Coste **$2.32** más el control de calidad
del abortado (~$0.09); mediana **$0.254** por tema. Se publica del 30 ago al 7 sep.

Verificado sobre los 9: **0 títulos** fuera de los 70 caracteres y **0
descripciones con hashtags duplicados** — la primera corrida real del arreglo del
paso 02, que es lo que sacó a `Historia07` con 24.

⚠️ **`Historia20` (maratón olímpico de 1904) abortó tras 3 intentos**, y el motivo
merece leerse antes de volver a proponerlo: es una historia famosísima pero se
cuenta entera con cifras precisas —dosis de estricnina, 32 grados, 3 h 28 min— y
el crítico las marca una por una. En el tercer intento además cazó algo real: el
guion decía que Hicks «llegó primero» cuando Lorz cruzó antes y fue descalificado.
**Un tema cuyo gancho son los datos exactos es mal candidato**, aunque la anécdota
sea buenísima.

**Facebook, al 28 ago:** `Historia13` publicado por Metricool (1.039 de alcance,
el que cerró el diagnóstico) y `Historia07`, `Historia14` y `Historia15` ya
programados por ahí.

⚠️ **Quedan 5 por subir a mano, sin prisa**: `Historia08`, `Historia09`,
`Historia10`, `Historia11` y `Historia12`. Se publican a lo largo del mes.
No los toca ningún automatismo — Facebook está fuera de `redes_reel`— así que
esta lista **es el único sitio donde consta que faltan**.

| | `v2-mas-cortes` (Historia01-08) | `v3-guion-y-dispersion` (Historia09-15) |
|---|---|---|
| Resultado | +513 % vistas 24 h, CTR +785 %, retención +32 % vs baseline | 7 de 7, **65 min**, 9.3 min/tema, **$0.285** de mediana |
| Qué lleva | más cortes, −14 LUFS, gancho sin spoiler | guionista `gpt-5.4`, crítico Opus 5, planos dispersados, títulos acortados |

Verificado sobre los 7: **0 transiciones repetidas** de 15-18 y **0 títulos** fuera del límite de
70 caracteres.

⚠️ **La decisión de operación es que nadie revise guiones a mano.** Por eso la puerta del paso 01
**aborta el tema** en vez de avisar, y lo que queda por hacer se mide por si **reduce intervención
humana**, no por si mejora un número.

**Tu semana son ahora tres cosas** (~45 min): elegir los temas, correr los cuatro comandos de
métricas y **subir los reels por Metricool a las cuatro redes**. Generar y empaquetar va solo, y
también el hilo de los sábados — que desde el 15 sep es **lo único** que se publica solo.

| | # | Pendiente | Gana |
|---|---|---|---|
| 🟡 | [P-35](#p-35) | Sin carrusel: ¿sube el alcance del reel? Mirar en octubre | la red que quedaba |
| 🟡 | [P-34](#p-34) | El alcance de Instagram baja un 38 %: queda la interacción | la red que quedaba |
| 🟡 | [P-33](#p-33) | El informe compara 2 lotes y ya hay 4: falta `v3` vs `v2` | la pregunta real |
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

## 🟡 Producto y datos

<a id="p-34"></a>
**P-34 · El alcance de Instagram baja, pero menos de lo que parecía.**

⚠️ **Rehecho el 15 sep. La versión anterior de esta nota decía «cayó a un
quinto» y estaba mal por dos motivos**, los dos de método:

1. Partía las cohortes por quincenas naturales, así que `Historia16` y
   `Historia17` (30 y 31 ago) caían en el grupo de agosto siendo `v4`.
2. Comparaba contra **la semana del 8-14 ago, que fue la mejor de la historia de
   la cuenta** (mediana 492). Es la misma trampa que [P-32](#p-32) advierte, y
   se cayó en ella en la dirección contraria.

Contra la línea de base de verdad, por fecha de publicación y con la última foto
de cada reel:

| era | n | vistas | alcance | vistas/alcance | % interacción | bajo 40 vistas |
|---|--:|--:|--:|--:|--:|--:|
| may-jul (a mano) | 38 | 144 | 118 | 1,26 | 1,87 % | 3/38 |
| 8-14 ago (a mano) | 7 | 492 | 371 | 1,33 | 1,27 % | 0/7 |
| 16-26 ago (API, v3) | 9 | 204 | 160 | 1,28 | 1,56 % | 0/9 |
| 30 ago-7 sep (API, v4) | 9 | **90** | **66** | 1,23 | **0,70 %** | **4/9** |

O sea **−38 % contra la base real**, no −80 %.

⚠️ **La edad NO confunde esta comparación, y merece saberse porque contradice la
intuición.** Los reels de Instagram **se congelan hacia el día 5**: `Historia07`
tenía 192 vistas a los 9 días y **las mismas 192 a los 30**; `Historia10`, 347 y
347. Así que aquí sí se pueden comparar cohortes de distinta edad — y es la
única red donde se puede.

**Lo nuevo no es la mediana, es el suelo.** 4 de 9 reels por debajo de 40 vistas,
cuando en los 38 de may-jul eso pasó 3 veces. La mitad rinde normal (123, 142,
156, 195) y la otra mitad no se muestra a nadie (11, 24, 26, 35).

**Es reparto, no rechazo.** `vistas/alcance` se mantiene en ~1,25 en las cuatro
eras: de los que lo ven en el feed, la misma proporción lo reproduce. Lo que cayó
es **a cuánta gente se lo enseñan** (118 → 66).

**Y el contenido queda descartado por TikTok**, que es el control natural: son
los mismos vídeos, y allí los me gusta **subieron** (14 → 21, 4,2 % de
interacción, alcance plano 604 → 434 a igualdad de edad). TikTok no depende de
seguidores; si los guiones `v4` fueran peores se vería allí primero. La duración
también queda descartada: los vídeos cortos van **mejor** en todas partes
(en YouTube, <32 s da 1.364 vistas contra 304 de los de 32-40 s).

**La hipótesis que queda** es que la interacción lleva meses bajando
(1,87 % → 1,56 % → 0,86 %) y ya está por debajo del nivel en que Instagram
reparte. La mediana de `v4` tiene **0 me gusta, 0 guardados, 0 compartidos y 0
comentarios**: sin una sola señal positiva el alcance se apaga solo, y menos
alcance da menos señal. Qué lo alimenta, en [P-35](#p-35).

⚠️ **Lo que NO se puede concluir todavía**: nada sobre las otras tres redes. La
impresión de que «bajan todas» es un artefacto de edad — `vistas` es acumulativa
y los vídeos de septiembre tenían 6-11 días contra 24-127 los demás. A igualdad
de edad, TikTok y Facebook están planos y YouTube es ruidoso pero con la
retención intacta (69,5 % → 88 % → 70 %).


<a id="p-35"></a>
**P-35 · Quitado el carrusel de Instagram: experimento en marcha (15 sep).**

`dias_extra` se queda **solo con Threads**. No es limpieza, es la prueba de la
hipótesis de [P-34](#p-34): publicar algo que nadie mira le enseña a Instagram
que la cuenta no merece reparto.

Lo que sostiene la hipótesis es **una coincidencia de fechas, y nada más**:

- 6 carruseles publicados desde el 16 ago (16, 18, 25 ago · 1, 10, 15 sep).
- Su alcance medido es **1-7** ([P-32](#p-32)).
- En esa misma ventana el alcance del reel pasó de 118 a 66.

⚠️ **No está demostrada.** Tres explicaciones alternativas siguen vivas y
ninguna se descarta con estos datos: saturación de una audiencia pequeña a la que
se publica a diario, un lazo de realimentación que empezó antes del primer
carrusel, y estacionalidad de septiembre.

**Cómo se mide** — y esto es lo que hay que leer antes de sacar conclusiones en
octubre:

- ⚠️ **NO se puede mirar en el informe: los carruseles no están en
  `metricas.csv`.** Comprobados los 6 ids el 15 sep, cero filas. Se publican y no
  los mide nadie.
- Se mira el **alcance del reel** de las semanas sin carrusel contra 66, que es
  la mediana de `v4`.
- ⚠️ **El experimento está limpio por casualidad**: como el reel también pasó a
  subirse a mano el 15 sep, el `v5` no lleva ni carrusel ni publicación por API.
  Si el alcance sube, **no se sabrá cuál de las dos cosas fue**. Para separarlas
  haría falta volver a poner una de las dos sola, y eso es una decisión, no un
  descuido.
- Hace falta **n≥5 reels** antes de decir nada. Con `v5` en marcha, eso es la
  primera semana de octubre.

Si en octubre el alcance sigue en ~66, la hipótesis del carrusel muere y hay que
mirar la saturación de la audiencia.


<a id="p-32"></a>
**P-32 · Los carruseles nunca alcanzaron a nadie. ¿Se quitan?**

Medido contra el histórico entero, no contra las últimas semanas:

| grupo | n | mediana | mín | máx |
|---|---:|---:|---:|---:|
| reel instagram manual | 45 | 127 | 14 | 2.984 |
| reel instagram por API | 8 | **146** | 80 | 272 |
| carrusel instagram manual | 5 | **2** | 2 | 2 |
| carrusel instagram por API | 3 | **5** | 1 | 7 |

⚠️ **Esto se midió el 25 ago y septiembre lo contradijo en parte: ver
[P-34](#p-34).** Entonces los reels por API iban *mejor* que la línea de base
(146 contra 127) y la conclusión fue que no había nada que arreglar en Instagram.
Con los siete de septiembre la mediana cae a **35**. La lectura de agosto era
correcta con lo que había; lo que cambió son los datos, no el razonamiento. **La
parte de los carruseles sigue en pie** — esa no depende de la de los reels.

⚠️ **Los carruseles llevan muertos desde siempre**: los cinco manuales de mayo
dieron **2 de alcance cada uno**. No es una regresión del API — de hecho los de
API van algo mejor. El álbum de Facebook de `Historia04` sacó **0 reacciones y 1
clic**.

✅ **Decidido el 15 sep: se quitan.** Pero no por lo que dice esta nota —que solo
dice que no alcanzan a nadie, y algo que no alcanza a nadie tampoco estorba— sino
porque puede estar arrastrando al reel. El seguimiento está en [P-35](#p-35).

**La decisión es de producto, no de código:** la agenda gasta dos de los tres
días de extras (martes carrusel de IG, jueves álbum de FB) en un formato que
nunca ha alcanzado a nadie en esta cuenta. O se le busca una razón para seguir, o
se quitan esas dos entradas de `dias_extra` en
[16_agenda.py](herramientas/16_agenda.py) y se deja el hilo de Threads, que al
menos tiene un techo de 22.024 ([P-25](#p-25)). El paso 06 seguiría existiendo
para el archivo.
⚠️ El álbum de Facebook, además, **ya no tiene sentido**: lo publica la misma app
restringida de [P-31](#p-31), así que su público son 2 personas pase lo que pase.


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
| <a id="p-31"></a>**P-31** | Facebook dio **alcance 2** en las 10 publicaciones por API, del 15 al 27 ago | **No era el código: era la app.** `/{app-id}/roles` tiene **un solo administrador**, y una app en Desarrollo/Standard Access solo enseña lo que publica en una página a quien tenga rol en ella. Metricool sacó **1.039** el 28 en la misma página. ⚠️ Se persiguieron el `title` y el endpoint (`/videos` vs `/video_reels`) antes de dar con esto: los dos eran **marcadores** de que Metricool publicaba por otra vía, no la causa. **Decisión: Facebook a mano por Metricool** ([README §4.1.b](README.md)) |
| <a id="p-30"></a>**P-30** | `publicado.csv` guardaba el `video_id` de Facebook y `metricas.csv` el `post_id` | Se cerró de paso al pasar a `/videos`, que devuelve los dos. Ya no aplica: Facebook no pasa por la agenda |
| <a id="p-27"></a>**P-27** | Un video de una tanda cerrada entraba como `baseline` | `lotes_historicos` en el `CONFIG` del paso 10, y `lote_de()` lo consulta **antes** que `temas.csv`. La pertenencia a una tanda es historia; `temas.csv` solo sabe cuál es la tanda en curso |
| <a id="p-28"></a>**P-28** | El informe comparaba `v2` mientras el paso 10 etiquetaba `v3` | `sincronizar_lotes()` los lee del paso 10 al arrancar, y `avisar_lotes_huerfanos()` canta cualquier lote que se quede fuera del veredicto, con la n al lado |
| <a id="p-11"></a>**P-11** | Tests solo de los pasos 01, 02 y 07 | +27 sobre los pasos **04, 05 y 06** ([tests/test_pasos_medios.py](tests/test_pasos_medios.py)), **166** en total |
| <a id="p-12"></a>**P-12** | `se_quedaron_pct` bajó en v2 | La curva de retención descartó gancho y cortes. Queda [P-20](#p-20), que es una pregunta distinta |
| <a id="p-14"></a>**P-14** | `proyectos/T1/` anidado dejaba 78 de 147 filas sin `PROYECTO` | Glob a dos niveles en `indice_proyectos()`: 43 filas recuperadas |
| <a id="p-15"></a>**P-15** | Los planos salían en pares de la misma imagen | `dispersar_planos()`: de 8 de 13 transiciones repetidas a **0 de 15-18** |
| <a id="p-19"></a>**P-19** | `DELAY = 7.0` uniforme en el paso 05 | Separado por fuente (1.5 s Wikimedia / 7 s DDG): **−2.7 min por tema** |
