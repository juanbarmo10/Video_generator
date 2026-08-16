# TODO — lo que queda por hacer

> **Este documento solo lleva trabajo pendiente.** Lo ya resuelto está en
> **[HISTORIAL.md](HISTORIAL.md)** con lo que se midió en cada caso. Léelo antes de tocar el
> pipeline: casi todo valor que parece arbitrario en el código sale de un fallo documentado allí.
>
> Operar el pipeline (generar, empaquetar, programar, medir) es **[README.md](README.md)**.
> Arquitectura y trampas del código, **[CLAUDE.md](CLAUDE.md)**.

## Dónde vamos

**Estado a 15 ago 2026.** Dos lotes completos y el pipeline **sin intervención humana de punta a
punta**.

| | `v2-mas-cortes` (Historia01-08) | `v3-guion-y-dispersion` (Historia09-15) |
|---|---|---|
| Resultado | +513 % vistas 24 h, CTR +785 %, retención +32 % vs baseline | 7 de 7, **65 min**, 9.3 min/tema, **$0.285** de mediana |
| Qué lleva | más cortes, −14 LUFS, gancho sin spoiler | guionista `gpt-5.4`, crítico Opus 5, planos dispersados, títulos acortados |

Verificado sobre los 7: **0 transiciones repetidas** de 15-18 y **0 títulos** fuera del límite de
70 caracteres.

⚠️ **La decisión de operación es que nadie revise guiones a mano.** Por eso la puerta del paso 01
**aborta el tema** en vez de avisar, y lo que queda por hacer se mide por si **reduce intervención
humana**, no por si mejora un número. Hoy tu tiempo semanal está en tres sitios de ~15 min:
elegir temas, programar en Metricool y recoger métricas de las redes que aún no tienen API.

| | # | Pendiente | Gana |
|---|---|---|---|
| 🟠 | [P-10](#p-10) | Publicar automáticamente en Meta | ~15 min/semana |
| 🟠 | [P-21](#p-21) | Publicar en Threads — texto, sin render | alcance medido a mano |
| 🟡 | [P-20](#p-20) | Por qué menos gente para el scroll (el frame 0) | la única métrica en contra |
| 🟡 | [P-09b](#p-09b) | Métricas por API: hechas 3 de 4 redes, falta TikTok | ~5 min/semana |
| 🟡 | [P-11](#p-11) | Tests de los pasos 03-06 | red de seguridad |
| 🔵 | [P-17](#p-17) | Afinar el recordatorio con unas semanas de uso | ruido |
| ⚪ | [P-06](#p-06) | Paralelizar los temas — evaluado: no compensa | ~25-35 % de tiempo |
| ⚪ | [P-18](#p-18) | La cabecera del paso 06 miente sobre su entrada | claridad |
| ⚪ | [P-09](#p-09) | ¿Se sigue usando el carrusel de Instagram? | $0.004 y 8 s/tema |
| ⚪ | [P-07](#p-07) | Basura de corridas viejas | 35 MB reales |
| ⚪ | [P-08](#p-08) | Los 16 Mundial no tienen `descripcion.txt` ni `.srt` | — |

---

## 🟠 Lo que más trabajo manual quita

<a id="p-10"></a>
**P-10 · Publicar automáticamente — Instagram y Facebook escritos, sin estrenar.**

✅ **Código listo** en [14_meta_api.py](herramientas/14_meta_api.py) (`--publicar PROYECTO`), con
los permisos ya concedidos. **Falta la primera publicación real**, que es la única prueba que vale.

⚠️ **`desuso/publisher.py` no servía de base.** No era que le faltaran credenciales: mandaba el
video como `files={"video": …}` a `/media`, y esa forma no existe en la API. Para un archivo local
hay que usar la **subida reanudable** a `rupload.facebook.com` — tres fases en vez de una. Ver
[HISTORIAL.md](HISTORIAL.md#-publicar-en-instagram-y-facebook-15-ago-2026).

Dos salvaguardas, porque publicar no se deshace:
- `--dry-run` hace **todo menos la llamada final**, incluida la subida del video.
- `publicar/publicado.csv` registra lo que salió y se comprueba antes de subir. Sin eso, correr el
  comando dos veces publica el mismo reel dos veces — el calendario dice cuándo *tocaba*
  publicar, no si se hizo. **Y de paso cierra el hueco que señalaba [P-17](#p-17)**: por fin hay un
  registro de qué se publicó.

**Queda por decidir cómo se dispara.** Hoy es un comando por tema; lo natural es que
`publicar/calendario.csv` mande y un `cron` publique el del día, pero eso conviene hacerlo
**después** de ver unas cuantas publicaciones manuales salir bien.

Las otras dos redes, por coste de trámite:

1. **YouTube** — ya tienes OAuth, pero subir exige `youtube.upload`, que es **restringido**: ahí sí
   hace falta pasar la verificación de Google con dominio propio.
2. **TikTok, la última.** Registrar app y pasar revisión: semanas de trámite para la red que menos
   aporta.

<a id="p-21"></a>
**P-21 · Publicar en Threads.**
**La señal viene del uso real, no de una suposición:** publicando a mano, Threads daba
bastante más alcance que el resto, y sirve de empuje para Instagram. No está en `metricas.csv`
porque nunca hubo export — eso también habría que resolverlo.

**Es lo más barato que queda por añadir:** un post de Threads es **texto**, así que no hay que
generar nada nuevo ni renderizar nada. El paso 02 ya escribe el gancho, el pie del reel y los
hashtags.

⚠️ **Threads es una API aparte de verdad**, no un añadido de la de Meta: otro host
(`graph.threads.net`), otro flujo de autorización y **otro token**. Marcar el caso de uso al crear
la app solo evita tener que rehacer la configuración después. Los permisos son `threads_basic`,
`threads_content_publish` y `threads_manage_insights`.

`desuso/publisher.py` tiene un `publish_threads()` de cuando se intentó, y **es el único de ese
archivo que puede servir de base**: Threads sí acepta texto directo, así que no arrastra el
problema de la subida de video que invalida el resto.

Hacerlo **después** de [P-10](#p-10): el mismo trámite ya habrá dejado la app creada.

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
⚠️ `se_quedaron_pct` **no la da la API** (ver P-09b): para seguir midiendo esto hay que descargar
el export de YouTube.

<a id="p-09b"></a>
**P-09b · Métricas por API — hechas 3 de 4 redes. Solo falta TikTok.**

✅ **YouTube** ([13_youtube_api.py](herramientas/13_youtube_api.py)) e ✅ **Instagram + Facebook**
([14_meta_api.py](herramientas/14_meta_api.py)), los dos el 15 ago. Las dos herramientas funden en
`metricas.csv` **reusando `fusionar()` del paso 10**, así que heredan sus reglas en vez de
duplicarlas. Detalle y hallazgos en
[HISTORIAL.md](HISTORIAL.md#-métricas-de-instagram-y-facebook-por-api-15-ago-2026).

De paso, **Instagram dejó de tener campos manuales**: `duracion_media_s` lo da
`ig_reels_avg_watch_time`, que era el único que había que teclear de esa red.

⚠️ **Dos columnas de YouTube siguen necesitando el export**: `se_quedaron_pct` («Se quedaron para
mirar», la de [P-20](#p-20)) y `alcance`. La API no las expone. La fusión no las pisa, así que se
completan bajando el zip cuando hagan falta.

**Queda TikTok**, y es la peor relación esfuerzo/beneficio: hay que registrar una app y pasar una
revisión de semanas para la red que menos aporta. Hoy son ~5 min de tecleo por lote.

💡 Antes de meterse en eso, mira si tu plan de **Metricool** exporta analíticas a CSV: ya tiene las
cuatro cuentas conectadas.

<a id="p-11"></a>
**P-11 · Tests: falta ampliar a los pasos 03-06.**
Hay **98 tests** (`python -m unittest discover tests`) sobre `10_metricas.py`, `11_reporte.py`,
`13_youtube_api.py`, `estado.py` y las funciones puras de los pasos **01, 02 y 07**. Detalle y
método en [HISTORIAL.md](HISTORIAL.md#-los-primeros-tests-98-y-verificados-por-mutación-15-ago-2026).

**Queda:** el parseo de `carrusel.txt` del paso 06 y las funciones de los pasos 03, 04 y 05.
No hace falta tocar `pipeline/`: `cargar_paso()` en
[tests/test_pipeline.py](tests/test_pipeline.py) prepara el entorno desde fuera y con eso basta.

---

## 🔵 Operación y seguimiento

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

## ⚪ Deuda y limpieza

<a id="p-06"></a>
**P-06 · Paralelizar los temas — evaluado el 15 ago: NO compensa todavía.**

| Qué se midió | Resultado | Qué implica |
|---|---|---|
| CPU del paso 07 | **203 % de 400 %** | dos renders saturan la máquina; no hay 2× que ganar |
| RAM pico | **1.35 GB** (+ ~1.5 GB de whisper) | dos temas ≈ 5-6 GB con 5 GB libres → swap |
| Recursos de la raíz en colisión | **5** | resolubles con un directorio por tema |

El bloqueo real es que **`.env` es el transporte entre pasos**: el 02 escribe `TITULO_VIDEO` y el
07 lo lee, así que con dos temas a la vez el B pisa el título del A — y ese texto va quemado en el
frame 0. ⚠️ Un directorio por tema **no lo arregla**: `load_dotenv()` busca el `.env` desde la
carpeta del script, no desde el directorio de trabajo.

**Requisito previo, barato:** que el título viaje por `social_posts/metadata.json`, donde el paso
02 **ya lo escribe**.

**Veredicto:** el techo real en esta máquina es ~25-35 %, no el 55 % que suponía la nota vieja, y
exige reescribir `run_all.sh` — la pieza con más historial de bugs sutiles. Volver solo si el lote
crece mucho o cambia la máquina.

<a id="p-18"></a>
**P-18 · La cabecera del paso 06 miente sobre su propia entrada.**
El docstring de [06_carrusel_generator.py](pipeline/06_carrusel_generator.py) dice que lee
`social_posts/03_instagram.txt`, que **dejó de existir**; su `CONFIG` apunta bien a `carrusel.txt`.
Manda el `CONFIG`. Son dos líneas de comentario, y de paso conviene renombrar
`parse_instagram_file()` — que además está duplicada y gana la segunda.

<a id="p-09"></a>
**P-09 · ¿Se sigue usando el carrusel de Instagram?** Si no, el paso 06 y `carrusel.txt` salen del
pipeline: ahorra $0.004 y 8 s por tema, y quita el contrato frágil de formato con el paso 02.

<a id="p-07"></a>
**P-07 · Basura de corridas viejas — menos de lo que parecía.**
La nota decía «~750 MB recuperables», pero **700 de esos son `videos_no_music/`**, que conviene
conservar: es lo único que permite rehacer la mezcla de música sin re-renderizar (~6 min de CPU por
video). La basura real son **35 MB**, y hay **279 GB libres**, así que no corre ninguna prisa.

Lo seguro, que no toca ningún entregable ni respaldo:

```bash
rm -rf proyectos/social_posts proyectos/carousel_slides proyectos/source_images
rm -rf proyectos/T1/social_posts proyectos/T1/carousel_slides \
       proyectos/T1/source_images proyectos/T1/images_IA
rm -rf images_IA_guidance __pycache__
rm -f  logs/_.log test_voz.mp3 fonts/*.zip "videos_no_music/T1/video_.mp4"
```

Nada de eso está en git. Los 16 respaldos `Mundial*` conservan además slides obsoletos
(`slide_06_cta.jpg` **y** `slide_07_cta.jpg`), de cuando el paso 06 no limpiaba su salida.

<a id="p-08"></a>
**P-08 · Los 16 Mundial no tienen `descripcion.txt` ni `.srt`.** Son anteriores a la
reestructuración del paso 02, así que el paso 09 los marca incompletos, y con razón. No vale la
pena regenerarlos: si se republican, se reescribe el texto a mano.

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
| <a id="p-12"></a>**P-12** | `se_quedaron_pct` bajó en v2 | La curva de retención descartó gancho y cortes. Queda [P-20](#p-20), que es una pregunta distinta |
| <a id="p-14"></a>**P-14** | `proyectos/T1/` anidado dejaba 78 de 147 filas sin `PROYECTO` | Glob a dos niveles en `indice_proyectos()`: 43 filas recuperadas |
| <a id="p-15"></a>**P-15** | Los planos salían en pares de la misma imagen | `dispersar_planos()`: de 8 de 13 transiciones repetidas a **0 de 15-18** |
| <a id="p-19"></a>**P-19** | `DELAY = 7.0` uniforme en el paso 05 | Separado por fuente (1.5 s Wikimedia / 7 s DDG): **−2.7 min por tema** |
