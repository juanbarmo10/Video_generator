# De dónde salen las métricas y cómo no perder la tarde

Guía para llenar `metricas.csv` de las cuatro plataformas.

⚠️ **Los menús y los nombres de columna cambian.** Las rutas de abajo son las que conozco;
si algo no está donde digo, busca la palabra clave (*Exportar*, *Descargar datos*, *Analytics*).
Lo que no cambia es la estrategia: **exporta en bloque, no vayas video por video.**

---

## La regla que ahorra todo el tiempo

Las cuatro plataformas dejan **descargar un CSV con todos los videos de una vez**. Nadie te obliga
a abrir video por video. Ir de a uno con 22 videos × 4 redes son 88 clics; los exports son 4.

Lo que **no** sale en el export masivo, y solo se ve entrando al video:

| Dato | Por qué no está |
|---|---|
| **Curva de retención** (el segundo exacto en que se van) | Es una serie temporal por video, no una fila de tabla |
| **Vistas a 24 h / 7 d** | El export trae vistas **acumuladas** a hoy, no por ventana |
| **Retención de TikTok e Instagram** | Esas dos no la exportan de ninguna forma (ver la tabla del final) |

La curva solo importa para diagnosticar, y para eso no necesitas los 22 videos: con mirar los 3
mejores y los 3 peores ya sabes qué falla. Y para el uso rutinario ni siquiera hace falta: el
export de YouTube trae **`Se quedaron para mirar (%)`**, que es el porcentaje que no deslizó en los
primeros segundos — la métrica del gancho, en la tabla.

Las vistas a 24 h se resuelven de otra forma: **exportando cada semana**. Comparando dos
descargas sale el delta. Por eso `metricas.csv` ahora tiene `fecha_snapshot`.

---

## Plataforma por plataforma

### YouTube Shorts — la que más te sirve

Es la única con datos de verdad sobre por qué te ven o no.

**Export masivo:** YouTube Studio → **Estadísticas** → arriba a la derecha **Modo avanzado** →
pestaña *Contenido* → elige el rango de fechas → **Exportar** (⬇ arriba a la derecha) → *CSV*.

Sale una fila por video con vistas, porcentaje promedio reproducido, duración media, me gusta,
comentarios y veces compartido. Esto es el 80 % de lo que necesitas, en un clic.

**Lo que solo se ve entrando al video:** Studio → Contenido → clic en el video → **Interacción** →
la **curva de retención**. Ahí está la única pregunta que importa ahora mismo: *¿cuánta gente se
va antes del segundo 3?* Caída en 0-2 s → el gancho. Caída en 5-10 s → el ritmo visual. Caída al
final → sobra el CTA.

**API (cuando ya no te alcance el CSV):** YouTube Analytics API, gratis, cuota de 10 000
unidades/día. Necesita **OAuth** — una API key no basta, son datos privados del canal.

```
pip install google-api-python-client google-auth-oauthlib
```
- Alcance: `https://www.googleapis.com/auth/yt-analytics.readonly`
- Tabla por video: `youtubeAnalytics.reports().query()` con
  `dimensions="video"`, `metrics="views,averageViewDuration,averageViewPercentage,comments,shares"`
- **La curva de retención**: `dimensions="elapsedVideoTimeRatio"` +
  `metrics="audienceWatchRatio,relativeRetentionPerformance"` — esto es lo que no puedes sacar de
  ningún CSV, y es lo más valioso de toda la API.

### TikTok

**Export masivo:** TikTok Studio en el navegador (`tiktok.com/tiktokstudio`) → **Analytics** →
pestaña *Contenido* → rango de fechas → **Descargar datos**.

⚠️ Desde el móvil **no** hay exportación: tiene que ser desde el navegador, y la cuenta debe estar
en modo **Creador o Empresa** (Configuración → Cuenta → Cambiar a cuenta de creador). Con cuenta
personal las analíticas están recortadas.

⚠️ **El export de TikTok es el más pobre de los cuatro**: solo vistas, me gusta, comentarios y
compartidos. Ni retención, ni alcance, ni tiempo visto, ni la duración del video.

Lo bueno de TikTok —*Tiempo medio de reproducción*, *Vieron el video completo* y el desglose de
tráfico (Para ti / búsqueda / perfil)— **solo se ve en pantalla, video por video**, y no sale en
ninguna descarga. Si el % de video completo es alto pero las vistas son bajas, el problema es la
distribución, no el contenido.

**API:** existe, pero para leer analíticas de tu propia cuenta necesitas registrar una app en
TikTok for Developers y pasar una revisión. **No lo montes ahora** — para tu volumen es semanas de
trámite para ahorrar 3 minutos por semana.

### Instagram y Facebook

Las dos salen del mismo sitio, porque las dos son Meta.

**Export masivo:** **Meta Business Suite** (`business.facebook.com`) → **Insights** →
*Contenido* → filtra por tipo *Reels* y por fecha → **Exportar datos**.

Da alcance, reproducciones, me gusta, comentarios, veces compartido y guardados, de Facebook e
Instagram, en el mismo sitio.

⚠️ Instagram exige cuenta **Business o Creador** vinculada a una página de Facebook. Si es
personal, no hay Insights ni API que valga.

**Presta atención a *guardados* y *compartidos*.** En Reels pesan más que los me gusta para que el
algoritmo te reparta. Están en el export y no están en `metricas.csv` original — por eso los añadí.

**API:** Instagram Graph API, `GET /{ig-media-id}/insights` con
`metric=plays,reach,saved,shares,total_interactions`. Necesita un token de larga duración.

💡 Ya tienes medio camino hecho: [publisher.py](publisher.py) espera `META_ACCESS_TOKEN`,
`FACEBOOK_PAGE_ID` e `INSTAGRAM_ACCOUNT_ID`, que **no están en el `.env`**. Son las mismas
credenciales para publicar y para leer métricas: si montas una, tienes la otra gratis.

### Metricool — el atajo que ya estás pagando

Como ya programas ahí y tienes las cuatro cuentas conectadas, **Metricool ya está recolectando
estas métricas**. Su sección de *Analíticas* las junta en un sitio y, según el plan, deja
exportar a CSV o PDF y programar informes periódicos por correo.

**Míralo antes que nada**: si tu plan incluye la exportación, es una descarga en vez de cuatro, y
te ahorras entrar a cada plataforma. Los planes de pago tienen además conector con Looker Studio,
que te daría el panel actualizándose solo.

Lo que Metricool **no** te va a dar es la curva de retención segundo a segundo de YouTube. Para
diagnosticar el gancho sigues necesitando YouTube Studio.

---

## La herramienta: `10_metricas.py`

**No tienes que tocar los archivos.** Descargas y sueltas en `metricas_export/`: los zip sin
descomprimir y los CSV con el nombre que traigan. Lo único que importa es que el nombre **empiece
por la plataforma**.

```bash
metricas_export/
    youtube_historico.zip      # trae 3 csv; usa "Datos de la tabla"
    tiktok_historico.zip       # trae Content.csv
    facebook_historico.csv     # export de Facebook
    facebook_historico2.csv    # export de Meta Business  ← los dos se fusionan
    instagram_historico.csv    # export de Meta Business

python 10_metricas.py --dry-run     # enseña qué haría
python 10_metricas.py
```

Descomprime, localiza el csv bueno de cada zip, **normaliza los 5 formatos a un csv por plataforma**
en `metricas_export/_normalizado/` (mismos nombres de columna para todos) y a partir de ahí empareja
y fusiona. Ese paso intermedio es el que quita la fricción: si algún día quieres mirar los datos a
mano, ya están uniformes.

### Cómo sabe qué fila es qué video

Las plataformas no conocen tu `PROYECTO`. El script compara el título o el caption contra los textos
de `proyectos/<P>/social_posts/` — `metadata.json`, `descripcion.txt` y también los legados
`04_facebook.txt` / `03_instagram.txt`, **sin los cuales los 16 Mundial no emparejarían ninguno**,
porque son anteriores a `metadata.json`.

Compara de dos formas y se queda con la mejor: por **solapamiento de palabras** (lo que salva los
títulos cortos escritos a mano — "Memo Ochoa al PSG" comparte *memo*, *ochoa* y *psg* con el caption
de Mundial16; por secuencia daba 0.33 y no emparejaba) y por **secuencia** (para captions largos).

⚠️ **Un proyecto solo puede ser un video.** Sin esa exclusividad, "Árbitro polémico", "Árbitro de
mundial" y "La mano de Dios" caían los tres en `Mundial01` y, como `metricas.csv` se indexa por
`(PROYECTO, plataforma, fecha)`, el último **pisaba a los otros dos en silencio**. Se asigna por
avaricia: el par con más parecido primero, y ni el video ni el proyecto se reutilizan.

### Lo que no empareja

Se acumula en `metricas_export/mapa_manual.csv` con la columna `PROYECTO` vacía:

```csv
plataforma,id,PROYECTO,candidato,score,texto
youtube,abc123,,Mundial09,0.41,Árbitro dormido
```

Rellenas el `PROYECTO` de los que te interesen **una vez** y el script lo respeta para siempre. Los
que dejes vacíos se ignoran en cada corrida — son los videos anteriores al pipeline (Michael Jackson,
Mother Love, Submarino nuclear…), y está bien que se queden fuera.

### Números y fechas

Entiende `1.284`, `1,284`, `62,5 %`, `0:00:44` y `9.378`. ⚠️ La distinción entre contador y decimal
es **por campo, no por heurística**: Facebook exporta los segundos medios vistos como `9.378`, y una
regla genérica de "3 dígitos detrás = separador de miles" lo leía como 9378 segundos y daba
retenciones del 17.000 %.

Fechas: `May 8, 2026` (YouTube), `08/14/2026 10:00` (Meta) y `9 de junio` (TikTok). ⚠️ **TikTok
exporta sin año**: se asume el actual, y si el mes cae en el futuro, el anterior. Si publicas algo
con más de un año, esa fecha saldrá mal.

---

## Qué métrica falta en cada plataforma

Medido sobre tus exports reales, no sobre la documentación:

| Métrica | YouTube | TikTok | Facebook | Instagram |
|---|:--:|:--:|:--:|:--:|
| Vistas | ✅ | ✅ | ✅ | ✅ |
| Alcance | ✅ | ❌ | ✅ | ✅ |
| Impresiones | ✅ | ❌ | ✅ | ❌ |
| **Retención %** | ✅ | ❌ | ⚠️ calculada | ❌ |
| **Duración media vista** | ✅ | ❌ | ✅ | ❌ |
| **Se quedaron a mirar %** | ✅ | ❌ | ❌ | ❌ |
| Me gusta / comentarios / compartidos | ✅ | ✅ | ✅ | ✅ |
| Guardados | ❌ | ❌ | ✅ | ✅ |
| Seguidores ganados | ✅ | ❌ | ✅ | ✅ |
| Duración del video | ✅ | ❌ | ✅ | ✅ |

**YouTube es la única plataforma con la que puedes diagnosticar.** Y trae un regalo que no esperaba:
**`Se quedaron para mirar (%)`** — el porcentaje que no deslizó en los primeros segundos. Es
exactamente la métrica del gancho, y es de export masivo. **Ya no hace falta abrir la curva de
retención a mano** para el diagnóstico rutinario; la curva solo sirve si quieres el segundo exacto.

**TikTok es el export más pobre que existe**: solo vistas, me gusta, comentarios y compartidos. Ni
retención, ni alcance, ni tiempo visto, ni siquiera la duración del video. Esos datos SÍ están en
TikTok Studio, pero solo en pantalla, video por video (Analytics → clic en el video → *Tiempo medio
de reproducción*, *Vieron el video completo*, *Fuentes de tráfico*). No hay export.

**Instagram no da nada de tiempo de visualización.** Ni segundos medios ni retención. Solo alcance,
interacciones y guardados. Para retención en IG hay que entrar reel por reel.

**Facebook sí trae segundos medios**, así que la retención se calcula dividiendo entre la duración
del video. El script ya lo hace y deja el resultado en `retencion_pct`, comparable con el de YouTube.
⚠️ No es idéntico conceptualmente: el de YouTube puede pasar del 100 % porque los Shorts se repiten
en bucle, el calculado de Facebook no.

---

## Los dos archivos de Facebook: usa los dos

No hay que elegir. **Son las mismas 45 publicaciones con el mismo `Identificador de la publicación`**,
así que el script los fusiona por ese id y se queda con lo mejor de cada uno.

| | `facebook_historico.csv` (de Facebook) | `facebook_historico2.csv` (Meta Business) |
|---|---|---|
| Columna de texto | `Título` = **el caption** | `Título` = **el título que generamos** + `Descripción` = caption |
| Alcance | `Espectadores` | `Alcance` |
| **Guardados** | ✅ | ❌ |
| **Impresiones** | ✅ | ❌ |
| **Seguimientos netos** | ✅ | ❌ |
| **Distribución** (`+0.2x`) | ✅ | ❌ |
| Ingresos / CPM | ❌ | ✅ (irrelevante, todo a 0) |

**Si tuvieras que quedarte con uno, el de Facebook** (`facebook_historico.csv`): tiene guardados,
impresiones y seguimientos netos, que el otro no. Pero el de Meta Business aporta algo que vale
mucho para esta herramienta: su columna `Título` es **el título exacto que generó el paso 02**, así
que empareja perfecto, mientras que el otro solo trae el caption.

Descarga los dos y suéltalos. El script hace el resto.

## El plan que yo seguiría

**Esta semana (una vez, ~20 min).** Export de YouTube en modo avanzado con el rango que cubre los
16 Mundial → `metricas_export/` → `python 10_metricas.py`. Ese es tu baseline. Con eso solo ya
puedes responder si los videos nuevos mejoran.

**Además, a mano (~10 min).** Abre la curva de retención de los **3 Mundial con más vistas y los 3
con menos**. Anota en la columna `notas` en qué segundo cae cada uno. Eso no sale de ningún CSV y
es lo que de verdad te dice si el problema es el gancho o el ritmo.

**Cada lunes (~5 min).** Los cuatro exports (o el de Metricool si tu plan lo trae) →
`python 10_metricas.py`. Los deltas salen solos de comparar snapshots.

**Cuándo montar las APIs.** Cuando llenar esto pase de 10 minutos por semana, o cuando pases de
~50 videos. Empieza por la de YouTube y **solo por la curva de retención**, que es lo único que no
puedes descargar de otra forma. Meta va después, aprovechando las credenciales de `publisher.py`.
TikTok, la última: es la que más trámite pide y la que menos aporta.

⚠️ **No compares contra el promedio de los 16 viejos.** Se renderizaron y publicaron en bloque, así
que compitieron entre ellos. Compara contra la **mediana**, y publica lo nuevo 1 por día a la misma
hora para que la comparación signifique algo.
