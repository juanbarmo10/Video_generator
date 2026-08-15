# Fábrica de videos históricos — `@chistoricas3`

Genera, de punta a punta y sin intervención, videos verticales de curiosidades históricas para
Reels, TikTok y Shorts. Le das una lista de temas y te devuelve los videos listos para programar,
cada uno con su texto, sus subtítulos y su carrusel.

**Coste real: ~$0.29 y ~9 minutos por video.** Un lote de 7 son unos $2 y poco más de una hora.

```
temas.csv  →  bash run_all.sh  →  publicar/<PROYECTO>/  →  Metricool
              (8 pasos + paquete)                          ↓
        reportes/ultimo.html  ←  metricas.csv  ←  python herramientas/10_metricas.py
        (11_reporte.py)
```

De cada tema salen:

| Qué | Cómo |
|---|---|
| Guion de 65-75 palabras | GPT-5.4, con Claude Opus 5 auditándolo; si no pasa lo manda a reescribir, y tras 3 intentos **aborta el tema** |
| Narración | ElevenLabs, acelerada ×1.10 hasta ~165 palabras/minuto |
| 6 ilustraciones | fal.ai (Flux dev), estilo grabado sobre pergamino |
| Video 9:16 | Subtítulos animados palabra por palabra, fotos reales intercaladas, música a −14 LUFS |
| `descripcion.txt` | Título de YouTube, pie del reel, hashtags, descripción larga, tags y comentario a fijar |
| Carrusel de Instagram | Imágenes reales + texto quemado |

---

## Antes de empezar (una sola vez)

1. **Entorno**: conda `ai_video_bot` con Python 3.11. Los `.sh` lo activan solos.
   ```bash
   conda create -n ai_video_bot python=3.11 && conda activate ai_video_bot
   pip install -r requirements.txt
   sudo apt install ffmpeg
   ```
2. **Claves** en `.env` (copia `.env.example`): `OPENAI_API_KEY`, `ELEVENLABS_API_KEY`, `FAL_KEY`.
   `ANTHROPIC_API_KEY` es opcional pero **muy recomendable**: sin ella el crítico del guion cae en
   `gpt-4.1`, que comparte familia con el guionista y sus puntos ciegos.
   ⚠️ **Sin ella la puerta de calidad cambia de comportamiento**: el crítico de gpt-4.1 puntúa
   3-4 puntos más alto sobre el mismo texto, así que aprueba casi todo. Los umbrales están
   calibrados para Opus.
3. **Saldo en fal.ai.** Es lo único que se agota y lo que aborta el lote a mitad.
4. **Opcional: el recordatorio semanal.** Las dos claves van en el **`.env`**, junto a las demás:
   ```bash
   TELEGRAM_BOT_TOKEN=8123456789:AAF...   # te lo da @BotFather con /newbot
   TELEGRAM_CHAT_ID=123456789             # ver abajo
   ```
   El token sale de hablar con **`@BotFather`** en Telegram y mandarle `/newbot`. Para el
   `chat_id`: pega primero el token, **escríbele algo al bot** (sin un mensaje previo la consulta
   sale vacía) y corre
   ```bash
   bash herramientas/obtener_chat_id.sh
   ```
   que lo lee de la API y te lo imprime.

   **Ya está programado en `cron`** (`crontab -l` para verlo, `crontab -e` para cambiarlo):

   | Cuándo | Qué |
   |---|---|
   | Domingo 10:00 | El aviso principal, al abrir la semana |
   | Domingo 16:00 | Segundo toque, por si el de la mañana se quedó sin leer |
   | Lunes a sábado 10:00 | Recuperación con `--si-falta`: **no hace nada** si ya se envió algo esa semana. Solo dispara si el domingo tuviste el equipo apagado |

   Mira el repositorio y te escribe **solo si hay algo que hacer**: temas caídos sin reintentar,
   guiones que no pasaron el control, videos con fecha de publicación ya pasada o métricas de hace
   más de una semana. Si no hay nada, calla — así que esas tres entradas **no son tres mensajes**:
   en una semana limpia no llega ninguno. Pruébalo sin enviar nada con
   `python herramientas/12_recordatorio.py --dry-run`, y mira qué hizo en `logs/recordatorio.log`.

5. **Opcional: métricas de YouTube por API.** Quita un tercio del trabajo semanal de métricas y es
   **la única forma de obtener la curva de retención**, que ningún export trae.

   Necesita OAuth, no una API key: son datos privados del canal.

   ```bash
   pip install google-api-python-client google-auth-oauthlib
   ```

   En [console.cloud.google.com](https://console.cloud.google.com), **con la cuenta dueña del
   canal** (si es una *Cuenta de marca*, la cuenta personal que la administra — con otra cuenta
   todo funciona y la API devuelve datos vacíos sin explicar por qué):

   | | Dónde | Qué |
   |---|---|---|
   | 1 | Selector de proyecto | *Proyecto nuevo* → `chistoricas-metricas` |
   | 2 | APIs y servicios → Biblioteca | Habilitar **YouTube Analytics API** y **YouTube Data API v3** |
   | 3 | Pantalla de consentimiento de OAuth | Tipo **Externo** · nombre y correos · **añádete como usuario de prueba** |
   | 4 | Misma pantalla | **Publicar aplicación → En producción** (ver el aviso de abajo) |
   | 5 | Credenciales | *Crear credenciales → ID de cliente de OAuth* → **Aplicación de escritorio** → Descargar JSON |

   ⚠️ **El paso 4 no es opcional aunque lo parezca.** Con la app en estado *Prueba*, Google
   **caduca el refresh token a los 7 días** y habría que reautorizar cada semana, que es justo la
   tarea manual que esto viene a quitar. Al estar publicada sin verificar, la primera autorización
   muestra *«Google no ha verificado esta aplicación»*: **Configuración avanzada → Ir a … (no
   seguro)**. La verificación solo hace falta para apps con usuarios ajenos; esta la usas tú.

   Guarda el JSON y autoriza:

   ```bash
   mv ~/Descargas/client_secret_*.json credenciales/
   python herramientas/13_youtube_api.py --autorizar
   ```

   Se abre el navegador una vez; después imprime a qué canal accede — **míralo**, es lo que
   distingue "el mes fue malo" de "autoricé con la cuenta equivocada". Debe salir
   *Curiosidades Historicas* (`@curiosidadeshistoricas-03`).
   ⚠️ **El identificador de YouTube no es `@chistoricas3`**, que es el de las otras redes. No es un
   error: son handles distintos por red.

   Después ya no hace falta volver a tocarlo:

   ```bash
   python herramientas/13_youtube_api.py --metricas        # las métricas → metricas.csv
   python herramientas/13_youtube_api.py --retencion-lote  # la curva de retención
   ```

6. **Opcional: Instagram y Facebook por API.** Un solo trámite sirve para **leer métricas** y para
   **publicar** — son los mismos permisos.

   **Requisito previo:** la cuenta de Instagram tiene que ser **Empresa o Creador** y estar
   **vinculada a una página de Facebook**. Con cuenta personal no hay API que valga.

   | | Dónde | Qué |
   |---|---|---|
   | 1 | [developers.facebook.com](https://developers.facebook.com) → Mis apps | *Crear app* → caso de uso **Otro** → tipo **Empresa** → `chistoricas-publica` |
   | 2 | Panel de la app → Agregar producto | **Instagram** (Graph API) y **Facebook Login para empresas** |
   | 3 | [Explorador de la API Graph](https://developers.facebook.com/tools/explorer/) | Elige tu app, marca los 7 permisos de abajo, *Generar token de acceso* |

   Los siete permisos:

   ```
   instagram_basic              instagram_manage_insights
   instagram_content_publish    pages_show_list
   pages_read_engagement        pages_manage_posts
   read_insights
   ```

   ⚠️ **No hace falta App Review.** Con la app en modo *Desarrollo*, tú como administradora tienes
   todos esos permisos sobre tus propios activos. La revisión solo es para que otros usen tu app.

   Pega el token en el `.env` como `META_ACCESS_TOKEN` y corre:

   ```bash
   python herramientas/14_meta_api.py --diagnostico
   ```

   **Descubre solo los dos IDs que faltan** (`FACEBOOK_PAGE_ID` e `INSTAGRAM_ACCOUNT_ID`), que no
   están a la vista en ninguna pantalla obvia de Meta, comprueba permiso por permiso y te dice qué
   escribir en el `.env`.

   ⚠️ **Cambia el token de usuario por el de PÁGINA** cuando el diagnóstico te lo ofrezca: el de
   usuario caduca a los 60 días, el de página no caduca.

⚠️ El `.env` lleva claves en texto plano y **es estado mutable del pipeline** (los scripts escriben
ahí `PROYECTO`, `TEMA` y `TITULO_VIDEO`). No se commitea nunca. Lo mismo vale para
`credenciales/`: el `client_secret*.json` y el `token_youtube.json` son secretos y están en
`.gitignore` — el token de YouTube da acceso de lectura a las analíticas del canal hasta que lo
revoques en [myaccount.google.com/permissions](https://myaccount.google.com/permissions), y el de
Meta permite **publicar en tu nombre**.

---

# La semana

Cinco bloques. En total, algo más de una hora de máquina y unos 30 minutos tuyos.

## 1 · Elegir los temas (~15 min)

Pega en ChatGPT las instrucciones de **[INSTRUCCIONES_CHATGPT.md](INSTRUCCIONES_CHATGPT.md)** (con
búsqueda web activada) y pídele la tanda:

> Dame 10 temas para la próxima tanda, universo: Mundiales de fútbol

Revisa la columna **Riesgo** de la tabla que te devuelve y pega el CSV en `temas.csv`:

```csv
PROYECTO,TEMA
Historia01,El cabezazo de Zidane en la final
Historia02,La mano de Dios
```

⚠️ **Exactamente 2 columnas, sin coma al final.** `PROYECTO` sin espacios ni acentos: da nombre a
archivos y carpetas.

💡 **Un incidente concreto va mejor que una categoría**, pero no es determinante: medido sobre el
lote de agosto, los temas tipo categoría (`La Odisea`, `Pompeya`, `Gran Muralla`) puntuaron igual o
mejor que los concretos — `La Odisea` sacó la mejor nota de los 7. Lo que sí importa es que el
tema tenga **algo documentado que contar**; si no lo tiene, el modelo se lo inventa y el control de
calidad tumba el tema.

## 2 · Generar (~1 h de máquina, 0 tuyas)

```bash
bash run_all.sh
```

Procesa cada fila de `temas.csv` de punta a punta. Puedes irte: cada tema tarda ~9 min y va
imprimiendo el progreso (65 min los 7 del lote de agosto).

- Los logs quedan en `logs/{PROYECTO}_{TEMA}.log`.
- Lo que falle se acumula en **`logs/failed.csv`**, que tiene el mismo formato que `temas.csv`:
  se puede usar tal cual como entrada para reintentar.
  ```bash
  cp logs/failed.csv temas.csv && bash run_all.sh
  ```

> ⚠️ **Pide 9-10 temas para obtener 7 videos.** El paso 01 **aborta el tema** si el guion no pasa
> el control de calidad tras 3 intentos — es lo que evita publicar datos falsos sin que nadie los
> lea. Sobre el lote de agosto se habrían caído **2 de 7**, así que cuenta con perder ~2 de cada 10
> y pídele a ChatGPT unos cuantos de más. Los caídos quedan en `logs/failed.csv`: reintentarlos
> vuelve a tirar los dados (el guion se genera de nuevo), así que a veces pasan a la segunda.
> Cada aborto cuesta solo ~$0.09, no los ~$0.29 del tema completo.

**Si quieres probar un cambio, no lances el lote** — cuesta dinero real. Usa un tema suelto:

```bash
PROYECTO=Test01 TEMA="El cabezazo de Zidane" bash run_pipeline.sh
```

## 3 · Revisar el paquete (~10 min)

**Esto ya lo hace `run_all.sh` solo** al terminar el lote: empaqueta los temas que salieron bien
—y solo esos— y te deja todo junto, una carpeta por tema:

```
publicar/
    calendario.csv          ← fechas ya repartidas, 1 video al día
    Historia01/
        Historia01.mp4      ← hardlink: no ocupa espacio extra
        Historia01.srt
        descripcion.txt     ← título, pie del reel, hashtags, descripción larga, tags
        carrusel/           ← slides de Instagram
```

Si quieres rehacerlo con otras fechas o cadencia, se corre a mano:

```bash
python herramientas/09_paquete_publicacion.py --solo Historia01 Historia02 --desde 2026-08-20 --hora 19:00
python herramientas/09_paquete_publicacion.py --solo Historia01 --cada 2       # uno cada dos días
python herramientas/09_paquete_publicacion.py --solo Historia01 --semanas      # agrupa en semana_01/, semana_02/
```

⚠️ **Sin `--solo` empaqueta todo lo que haya en `videos/`**, incluidos los lotes viejos. Por eso
`run_all.sh` le pasa siempre los `PROYECTO` de la tanda.

**Ya no hay que leer los guiones antes de programar.** Los que no pasan el control de calidad no
llegan hasta aquí: el paso 01 aborta el tema y lo deja en `logs/failed.csv`, así que todo lo que
haya en `publicar/` está aprobado. La columna `revisar_a_mano` de `calendario.csv` debería salir
siempre en `no`; si ves un `SÍ`, es un paquete de antes de agosto de 2026.

Lo que sí conviene mirar es **cuántos temas se cayeron** (lo dice el resumen del lote) para
reponerlos en la tanda siguiente.

## 4 · Programar en Metricool (~15 min)

Uno por día, a la misma hora. Subir el lote de golpe hace que compitan entre ellos.

Por cada tema, abres `publicar/<PROYECTO>/` (la carpeta se llama como el `PROYECTO` del CSV,
`Historia04`, no como el tema) y:

1. Subes el `.mp4` como Reel a Facebook e Instagram, Short a YouTube, y video a TikTok.
2. Abres `descripcion.txt` y copias:
   - **Reels, TikTok y Shorts** → la sección *DESCRIPCIÓN GENERAL* **con los hashtags de debajo**
     (van pegados a propósito: seleccionas los dos de una pasada).
   - **YouTube y Facebook** → *TÍTULO*, y la *DESCRIPCIÓN LARGA* con sus hashtags.
   - **YouTube** → los *TAGS*.
3. El `.srt` se sube aparte en YouTube: mejora la indexación y sale gratis.
4. Dejas el *COMENTARIO A FIJAR* programado o lo pones a mano al publicar.

`publicar/calendario.csv` trae la fecha, hora y título de cada uno para ir tachando.

## 5 · Recoger las métricas de la semana anterior (~15 min)

Esto es lo del lote **pasado**, no el que acabas de subir: los números necesitan días para cuajar.

### 5.1 Descargar

**YouTube ya no hace falta descargarlo** si montaste la API (punto 5 de *Antes de empezar*):

```bash
python herramientas/13_youtube_api.py --metricas
```

⚠️ Con dos salvedades: la API **no da** `se_quedaron_pct` («Se quedaron para mirar», que es la
métrica de [P-20](TODO.md#p-20)) ni `alcance` (únicos por video). Si las quieres, sigue bajando el
zip — la fusión no las pisa, así que se pueden completar después.

El resto se sueltan **tal cual se descargan** en `metricas_export/` — zips sin descomprimir, con el
nombre empezando por la plataforma:

| Red | Dónde | Deja el archivo como |
|---|---|---|
| **YouTube** *(opcional, ver arriba)* | Studio → Estadísticas → **Modo avanzado** → Contenido → Exportar | `youtube_tanda1.zip` |
| **TikTok** | `tiktok.com/tiktokstudio` → Analytics → Contenido → Descargar | `tiktok.zip` |
| **Facebook** | Meta Business Suite → Insights → Contenido → Exportar | `facebook1.csv` |
| **Facebook** | *(también el export desde Facebook)* | `facebook2.csv` |
| **Instagram** | Meta Business Suite → Insights → Contenido → Exportar | `instagram.csv` |

⚠️ **Los dos de Facebook hacen falta.** Son las mismas publicaciones con el mismo id, y el script
las fusiona: el de Meta Business trae el **título** que usamos para emparejar y el alcance; el de
Facebook trae **guardados, impresiones, seguimientos netos y `Distribución`** (`+0.2x` frente a tus
otras publicaciones, lo único que dice si Facebook te está repartiendo o te tiene frenado).

⚠️ **TikTok solo exporta desde el navegador**, no desde el móvil, y la cuenta tiene que estar en
modo Creador o Empresa. **Instagram exige cuenta Business o Creador** vinculada a una página de
Facebook; con cuenta personal no hay Insights que valgan.

💡 **En YouTube, selecciona todos los videos en la gráfica antes de exportar.** Solo se exporta la
serie diaria de lo que esté dibujado, y de ahí salen las vistas a 24 h y 7 d. Si son muchos, hazlo
en varias tandas (`youtube_tanda1.zip`, `youtube_tanda2.zip`…): el script las une.

### 5.2 Consolidar

```bash
python herramientas/10_metricas.py
```

Descomprime, normaliza los cinco formatos, empareja cada video con su `PROYECTO` y lo escribe en
`metricas.csv`. Al terminar **archiva los exports** en `_procesados/<fecha>/` para que la semana que
viene la carpeta esté limpia.

### 5.3 Teclear lo que ninguna plataforma exporta (~5 min)

El script te deja `metricas_export/manual.csv` **ya identificado** — plataforma, id, fecha y título
puestos. Solo rellenas números, y solo las celdas vacías (las que llevan `—` es que esa red sí lo
exporta):

| Red | Qué teclear | De dónde |
|---|---|---|
| **Instagram** | segundos medios vistos | App → el reel → Ver estadísticas → *Tiempo de reproducción medio* |
| **TikTok** | alcance, segundos medios, % que vio completo | TikTok Studio → Analytics → clic en el video |

No teclees la retención: la calcula sola dividiendo por la duración. Los porcentajes, **como
porcentaje** (`21`, no `0.21`) — si te equivocas, avisa y lo convierte.

Vuelve a correr para recogerlo:

```bash
python herramientas/10_metricas.py
```

Sin descargas nuevas reprocesa la última tanda archivada con su fecha original, así que es
idempotente: correrlo de más no ensucia nada.

💡 **Si te da pereza, sáltate TikTok.** Es donde más hay que teclear y donde menos se decide.

---

### 5.4 Leer el informe (~5 min)

```bash
python herramientas/11_reporte.py
xdg-open reportes/ultimo.html
```

Convierte las 147 filas × 28 columnas de `metricas.csv` en una página que se lee de un vistazo.
No hace falta Excel ni internet: el HTML es autocontenido.

Trae el veredicto `v2-mas-cortes` vs `baseline`, el ranking de mejores y peores, el seguimiento de
`se_quedaron_pct` y una tabla por red **con solo las columnas que esa red exporta**. Y calcula
cuatro cosas que no están en el CSV: `vistas_por_dia`, `tasa_guardado`, `engagement` y
`retencion_relativa` (retención del video ÷ mediana de su lote — si es bueno *para tu canal*).

---

## Leer los resultados

La única columna que importa para comparar es **`lote`**: `baseline` es todo lo anterior al
pipeline, `v2-mas-cortes` son `Historia01`-`Historia08` y `v3-guion-y-dispersion` los
`Historia09`-`Historia15`. El informe de 5.4 ya hace la comparación; esto es para saber **cómo
leerla**.

⚠️ **Al cargar un `temas.csv` nuevo con cambios de pipeline detrás, sube `lote_nuevo` en el
`CONFIG` de [10_metricas.py](herramientas/10_metricas.py)**, o dos tandas distintas comparten
nombre y dejan de distinguirse. Las tandas anteriores no se tocan: el lote es pegajoso a propósito
(ver [HISTORIAL.md](HISTORIAL.md#-el-lote-se-degradaba-solo-al-cambiar-temascsv-15-ago-2026)).

Compara siempre contra la **mediana**, no contra el mejor ni el peor, y mira la **n** que va al
lado: con 6 videos, una diferencia del 40 % cabe dentro del ruido.

⚠️ **No compares vistas entre lotes de edades distintas — y hoy lo son.** Los videos nuevos llevan
4 días publicados y los del baseline 66. Todo lo que se *acumula* mientras el video sigue online
(vistas, alcance, guardados) favorece al viejo por el simple paso del tiempo. Y `vistas_por_dia`
comete el error contrario: reparte entre 4 días unas vistas que en video social llegan casi todas
en las primeras 48 h, y dispara al nuevo. **El informe aparta solas esas cifras** a un bloque
"fuera del veredicto" en vez de dejarte concluir con ellas.

Lo que sí compara de verdad:

- **`vistas_24h` y `vistas_7d`** (solo YouTube) — ventana fija desde la publicación, así que las
  edades ya están igualadas. Es la comparación limpia, y por eso YouTube es la red que más dice.
- **`se_quedaron_pct`** (YouTube y TikTok) — cuántos no deslizaron en los primeros segundos. Es el
  gancho, y es la única que va en contra ([P-12](TODO.md#p-12)).
- **`retencion_pct`** — cuánto del video se ve de media. Un cociente, así que la edad no lo mueve.
  En YouTube puede pasar de 100 %: son los bucles de Shorts, no un error.
- **`ctr_pct`** (YouTube) — si es bajo, el problema es el título, no el video.
- **`guardados` y `compartidos`** — pesan más que los me gusta para que te repartan.

Para comparar acumulados hacen falta **dos fotos** y restar el crecimiento del mismo periodo. Hoy
solo hay una (`2026-08-15`); con la segunda, el informe llena solo su sección de tendencia.

---

## Qué trae cada red

Medido sobre los exports reales, no sobre la documentación de las plataformas:

| Métrica | YouTube | TikTok | Facebook | Instagram |
|---|:--:|:--:|:--:|:--:|
| Vistas · me gusta · comentarios · compartidos | ✅ | ✅ | ✅ | ✅ |
| Alcance | ✅ | ✍️ | ✅ | ✅ |
| Impresiones | ✅ | ❌ | ✅ | ❌ |
| **Retención %** | ✅ | ✍️ | ⚙️ | ✍️ |
| **Duración media vista** | ✅ | ✍️ | ✅ | ✍️ |
| **Se quedaron a mirar %** | ✅ | ✍️ | ❌ | ❌ |
| Guardados | ❌ | ❌ | ✅ | ✅ |
| Seguidores ganados | ✅ | ❌ | ✅ | ✅ |

✅ viene en el export · ✍️ se teclea en `manual.csv` · ⚙️ la calcula el script · ❌ no existe

**YouTube es la única red con la que puedes diagnosticar de verdad**, y trae dos cosas que las
demás no:

- **`se_quedaron_pct`** — el porcentaje que no deslizó en los primeros segundos. Es la métrica del
  gancho, y viene en el export masivo: no hace falta abrir la curva de retención a mano.
- **`ctr_pct`** — clics sobre impresiones. Separa dos problemas que se confunden: si el CTR es
  bajo, no entran (el título); si entran y se van, es el gancho.

También trae **`tiempo_total_h`** (horas totales vistas), que es *la* señal de ranking: YouTube
reparte por tiempo retenido, no por clics.

**El export de TikTok es el más pobre de los cuatro**: solo vistas, me gusta, comentarios y
compartidos. Ni siquiera la duración del video — el script se la presta de otra red, porque es el
mismo mp4 en las cuatro.

---

## Si algo falla

| Síntoma | Qué pasa |
|---|---|
| `User is locked. Reason: Exhausted balance` | Se acabó el saldo de fal.ai. Recarga y reintenta: `cp logs/failed.csv temas.csv && bash run_all.sh` |
| `CondaError: Run 'conda init'` | Ya no debería pasar; los `.sh` se re-ejecutan con bash solos |
| `❌ Los archivos de la raíz son de 'X', no de 'Y'` | El sello anti-mezcla. Corre el paso 01 de ese tema o borra `.estado_actual` |
| `❌ Falta PROYECTO` / `Falta TITULO_VIDEO` | Estás corriendo un paso suelto sin exportar las variables |
| Solo se generaron N/6 imágenes | Saldo de fal, o el prompt cayó en el filtro de moderación |
| El lote deja carpetas con nombres raros | Ya arreglado (ffmpeg se comía bytes de `temas.csv`); si reaparece, ponle `-nostdin` a la llamada nueva de ffmpeg |
| `command not found` al correr un paso suelto | Alguna línea del `.env` no es `CLAVE=VALOR`. `run_pipeline.sh` hace `source .env` y bash intenta ejecutarla. Bórrala |
| El informe da porcentajes absurdos (+2000 %) | Estás mirando una métrica acumulada entre lotes de edades distintas. El informe las aparta solo; si la ves, es del bloque "fuera del veredicto" |

Los logs por tema están en `logs/`. El coste del tema en curso, en `.costo_actual.json`.

---

## Documentación

| Archivo | Para qué |
|---|---|
| **[CLAUDE.md](CLAUDE.md)** | Cómo está hecho: arquitectura, qué hace cada paso, mapa del repositorio y trampas. **Léelo antes de tocar código** |
| **[TODO.md](TODO.md)** | Qué queda por hacer, y solo eso. Priorizado |
| **[HISTORIAL.md](HISTORIAL.md)** | Por qué está así: la auditoría de 18 bugs, las 5 fases y todo lo medido. Consúltalo antes de "arreglar" un valor que parezca raro |
| **[INSTRUCCIONES_CHATGPT.md](INSTRUCCIONES_CHATGPT.md)** | El prompt para que ChatGPT proponga temas que el pipeline aguante |
