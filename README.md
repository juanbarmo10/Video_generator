# Fábrica de videos históricos — `@chistoricas3`

Genera, de punta a punta y sin intervención, videos verticales de curiosidades históricas para
Reels, TikTok y Shorts. Le das una lista de temas y te devuelve los videos listos para programar,
cada uno con su texto, sus subtítulos y su carrusel.

**Coste real: ~$0.25 y ~14 minutos por video.** Un lote de 8 son unos $2 y menos de dos horas.

```
temas.csv  →  bash run_all.sh  →  publicar/<PROYECTO>/  →  Metricool
              (8 pasos + paquete)                          ↓
        reportes/ultimo.html  ←  metricas.csv  ←  python herramientas/10_metricas.py
        (11_reporte.py)
```

De cada tema salen:

| Qué | Cómo |
|---|---|
| Guion de 65-75 palabras | GPT-4.1, con un segundo modelo que lo audita y lo manda a reescribir si no pasa |
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
   `gpt-4.1`, o sea el mismo modelo que lo escribió, y comparte sus puntos ciegos.
3. **Saldo en fal.ai.** Es lo único que se agota y lo que aborta el lote a mitad.
4. **Opcional: el recordatorio semanal.** Habla con `@BotFather` en Telegram (`/newbot`), guarda el
   token, escríbele al bot y saca tu `chat_id` de
   `https://api.telegram.org/bot<TOKEN>/getUpdates`. Ponlos en el `.env` como
   `TELEGRAM_BOT_TOKEN` y `TELEGRAM_CHAT_ID`, y prográmalo:
   ```bash
   # crontab -e   →   lunes a las 9:00
   0 9 * * 1  cd /home/juanb/video_generator && \
              /home/juanb/miniforge3/envs/ai_video_bot/bin/python \
              herramientas/12_recordatorio.py
   ```
   Cada lunes mira el repositorio y te escribe **solo si hay algo que hacer**: temas caídos sin
   reintentar, guiones que no pasaron el control, videos con fecha de publicación ya pasada o
   métricas de hace más de una semana. Si no hay nada, calla. Pruébalo sin enviar nada con
   `python herramientas/12_recordatorio.py --dry-run`.

⚠️ El `.env` lleva claves en texto plano y **es estado mutable del pipeline** (los scripts escriben
ahí `PROYECTO`, `TEMA` y `TITULO_VIDEO`). No se commitea nunca.

---

# La semana

Cinco bloques. En total, poco más de dos horas de máquina y unos 30 minutos tuyos.

## 1 · Elegir los temas (~15 min)

Pega en ChatGPT las instrucciones de **[INSTRUCCIONES_CHATGPT.md](INSTRUCCIONES_CHATGPT.md)** (con
búsqueda web activada) y pídele la tanda:

> Dame 8 temas para la próxima tanda, universo: Mundiales de fútbol

Revisa la columna **Riesgo** de la tabla que te devuelve y pega el CSV en `temas.csv`:

```csv
PROYECTO,TEMA
Historia01,El cabezazo de Zidane en la final
Historia02,La mano de Dios
```

⚠️ **Exactamente 2 columnas, sin coma al final.** `PROYECTO` sin espacios ni acentos: da nombre a
archivos y carpetas.

⚠️ **El tema tiene que ser una historia, no una categoría.** `Eclipse`, `Odisea` o `Surrealismo`
son categorías, y de los 8 del primer lote real solo pasó el control de calidad el único que era un
relato concreto. Si el tema es vago, el guion sale flojo y no hay pipeline que lo salve.

## 2 · Generar (~2 h de máquina, 0 tuyas)

```bash
bash run_all.sh
```

Procesa cada fila de `temas.csv` de punta a punta. Puedes irte: cada tema tarda ~14 min y va
imprimiendo el progreso.

- Los logs quedan en `logs/{PROYECTO}_{TEMA}.log`.
- Lo que falle se acumula en **`logs/failed.csv`**, que tiene el mismo formato que `temas.csv`:
  se puede usar tal cual como entrada para reintentar.
  ```bash
  cp logs/failed.csv temas.csv && bash run_all.sh
  ```

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

**Lo que tienes que mirar antes de programar** — el script te lo dice al terminar del lote:

```
⚠️  5 guion(es) NO pasaron el control de calidad.
     · Historia02 (nota 3/10)
         "Un eclipse hizo desaparecer a un faraón para siempre."
```

Eso es el crítico avisando de afirmaciones que no pudo verificar. **Léelos al programar**: un dato
inventado que se publica es peor que un video menos. La nota de cada guion está también en
`publicar/calendario.csv`, columna `revisar_a_mano`.

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

Suelta los archivos **tal cual se descargan** en `metricas_export/` — zips sin descomprimir, con el
nombre empezando por la plataforma:

| Red | Dónde | Deja el archivo como |
|---|---|---|
| **YouTube** | Studio → Estadísticas → **Modo avanzado** → Contenido → Exportar | `youtube_tanda1.zip` |
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

La única columna que importa para comparar es **`lote`**: `baseline` es todo lo anterior al cambio
de pipeline, `v2-mas-cortes` los nuevos. El informe de 5.4 ya hace la comparación; esto es para
saber **cómo leerla**.

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
