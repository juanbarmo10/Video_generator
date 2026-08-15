# Fábrica de videos históricos — `@chistoricas3`

Genera, de punta a punta y sin intervención, videos verticales de curiosidades históricas para
Reels, TikTok y Shorts. Le das una lista de temas y te devuelve los videos listos para programar,
cada uno con su texto, sus subtítulos y su carrusel.

**Coste real: ~$0.25 y ~14 minutos por video.** Un lote de 8 son unos $2 y menos de dos horas.

```
temas.csv  →  [ 8 pasos automáticos ]  →  publicar/<TEMA>/  →  Metricool
                                                            ↘  metricas.csv
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

## 3 · Empaquetar y revisar (~10 min)

```bash
python 09_paquete_publicacion.py --desde 2026-08-20 --hora 19:00
```

Deja todo junto, una carpeta por tema:

```
publicar/
    calendario.csv          ← fechas ya repartidas, 1 video al día
    Historia01/
        Historia01.mp4      ← hardlink: no ocupa espacio extra
        Historia01.srt
        descripcion.txt     ← título, pie del reel, hashtags, descripción larga, tags
        carrusel/           ← slides de Instagram
```

Opciones útiles: `--cada 2` (uno cada dos días), `--semanas` (agrupa en `semana_01/`, `semana_02/`),
`--solo Historia01 Historia02`.

⚠️ **Sin `--solo` empaqueta todo lo que haya en `videos/`**, incluidos los lotes viejos.

**Lo que tienes que mirar antes de programar** — el script te lo dice al terminar:

```
⚠️  5 guion(es) NO pasaron el control de calidad.
     · Historia02 (nota 3/10)
         "Un eclipse hizo desaparecer a un faraón para siempre."
```

Eso es el crítico avisando de afirmaciones que no pudo verificar. **Léelos.** Un dato inventado que
se publica es peor que un video menos.

## 4 · Programar en Metricool (~15 min)

Uno por día, a la misma hora. Subir el lote de golpe hace que compitan entre ellos.

Por cada tema, abres `publicar/<TEMA>/` y:

1. Subes el `.mp4` como Reel a Facebook e Instagram, Short a YouTube, y video a TikTok.
2. Abres `descripcion.txt` y copias:
   - **Reels, TikTok y Shorts** → la sección *DESCRIPCIÓN GENERAL* **con los hashtags de debajo**
     (van pegados a propósito: seleccionas los dos de una pasada).
   - **YouTube y Facebook** → *TÍTULO*, y la *DESCRIPCIÓN LARGA* con sus hashtags.
   - **YouTube** → los *TAGS*.
3. El `.srt` se sube aparte en YouTube: mejora la indexación y sale gratis.
4. Dejas el *COMENTARIO A FIJAR* programado o lo pones a mano al publicar.

`publicar/calendario.csv` trae la fecha, hora y título de cada uno para ir tachando.

## 5 · Recoger las métricas de la semana anterior (~10 min)

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

⚠️ **Los dos de Facebook hacen falta**: el de Meta Business trae el título que emparejamos, el de
Facebook trae guardados, impresiones y distribución. Se fusionan solos.

💡 **En YouTube, selecciona todos los videos en la gráfica antes de exportar.** Solo se exporta la
serie diaria de lo que esté dibujado, y de ahí salen las vistas a 24 h y 7 d. Si son muchos, hazlo
en varias tandas (`youtube_tanda1.zip`, `youtube_tanda2.zip`…): el script las une.

### 5.2 Consolidar

```bash
python 10_metricas.py
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
python 10_metricas.py
```

Sin descargas nuevas reprocesa la última tanda archivada con su fecha original, así que es
idempotente: correrlo de más no ensucia nada.

💡 **Si te da pereza, sáltate TikTok.** Es donde más hay que teclear y donde menos se decide.

---

## Leer los resultados

La única columna que importa para comparar es **`lote`**: `baseline` es todo lo anterior al cambio
de pipeline, `v2-mas-cortes` los nuevos.

```bash
python -c "
import csv, statistics as st, collections
f=list(csv.DictReader(open('metricas.csv')))
for plat in ['youtube','instagram','facebook','tiktok']:
    for lote in ['baseline','v2-mas-cortes']:
        g=[r for r in f if r['plataforma']==plat and r['lote']==lote]
        v=[float(r['vistas']) for r in g if r['vistas']]
        if v: print(f'{plat:<11}{lote:<15}n={len(g):<4}vistas mediana={st.median(v):g}')
"
```

Compara siempre contra la **mediana**, no contra el mejor ni el peor. Y las métricas que de verdad
dicen algo no son las vistas:

- **`se_quedaron_pct`** (YouTube) — cuántos no deslizaron en los primeros segundos. Es el gancho.
- **`retencion_pct`** — cuánto del video se ve de media.
- **`vistas_24h`** — quita el sesgo de que un video lleve más días publicado.
- **`ctr_pct`** (YouTube) — si es bajo, el problema es el título, no el video.
- **`guardados` y `compartidos`** — pesan más que los me gusta para que te repartan.

---

## Si algo falla

| Síntoma | Qué pasa |
|---|---|
| `User is locked. Reason: Exhausted balance` | Se acabó el saldo de fal.ai. Recarga y reintenta con `logs/failed.csv` |
| `CondaError: Run 'conda init'` | Ya no debería pasar; los `.sh` se re-ejecutan con bash solos |
| `❌ Los archivos de la raíz son de 'X', no de 'Y'` | El sello anti-mezcla. Corre el paso 01 de ese tema o borra `.estado_actual` |
| `❌ Falta PROYECTO` / `Falta TITULO_VIDEO` | Estás corriendo un paso suelto sin exportar las variables |
| Solo se generaron N/6 imágenes | Saldo de fal, o el prompt cayó en el filtro de moderación |
| El lote deja carpetas con nombres raros | Ya arreglado (ffmpeg se comía bytes de `temas.csv`); si reaparece, ponle `-nostdin` a la llamada nueva de ffmpeg |

Los logs por tema están en `logs/`. El coste del tema en curso, en `.costo_actual.json`.

---

## Documentación

| Archivo | Para qué |
|---|---|
| **[CLAUDE.md](CLAUDE.md)** | Arquitectura, qué hace cada paso y las trampas conocidas. **Léelo antes de tocar código** |
| **[TODO.md](TODO.md)** | Auditoría de bugs, diagnóstico de contenido y lo que queda pendiente |
| **[METRICAS.md](METRICAS.md)** | De dónde sale cada métrica, qué falta en cada red y cómo funciona el consolidador |
| **[INSTRUCCIONES_CHATGPT.md](INSTRUCCIONES_CHATGPT.md)** | El prompt para que ChatGPT proponga temas que el pipeline aguante |
