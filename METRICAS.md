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
| **% que llega a los 3 s** | Se lee de esa curva |
| **Vistas a 24 h / 7 d** | El export trae vistas **acumuladas** a hoy, no por ventana |

Las dos primeras solo importan para diagnosticar, y para eso no necesitas los 22 videos: con
mirar los 3 mejores y los 3 peores ya sabes qué falla.

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

TikTok da algo que las demás no: **"Espectadores que vieron el video completo"** y el desglose de
dónde vino el tráfico (Para ti / búsqueda / perfil). Si el % de video completo es alto pero las
vistas son bajas, el problema es la distribución, no el contenido.

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

Une los CSV que descargues en `metricas.csv`, emparejando cada fila con su `PROYECTO`.

```bash
# 1. deja los exports aquí, con el nombre empezando por la plataforma
metricas_export/youtube_agosto.csv
metricas_export/tiktok_agosto.csv
metricas_export/instagram_agosto.csv
metricas_export/facebook_agosto.csv

# 2.
python 10_metricas.py --dry-run     # enseña qué haría, sin escribir
python 10_metricas.py
```

**Cómo sabe qué fila es qué video.** Las plataformas no conocen tu `PROYECTO`. El script compara el
título (o el pie del reel, en TikTok/IG/FB donde no hay título) contra el `titulo` de
`proyectos/<P>/social_posts/metadata.json` y contra la descripción general. Lo que no llega al
umbral de parecido **se reporta, no se adivina**:

```
⚠️  1 fila(s) sin emparejar — revísalas:
   · [0.42] Video de otro canal que no es mío
   Si son videos tuyos, baja el umbral: --umbral 0.45
```

**Los nombres de columna cambian con el idioma y con cada rediseño.** El mapeo va por alias
(diccionario `ALIAS` al inicio del script, con variantes en español e inglés) y al terminar
imprime las columnas que no supo reconocer:

```
ℹ️  columnas no reconocidas: Contenido
```

Si ves ahí una columna que te interesa, añade su nombre al alias correspondiente y vuelve a correr.
No hay que tocar nada más.

**Números:** entiende `1.284`, `1,284`, `62,5 %`, `0:16` y `1:02:03`. La regla para el separador
ambiguo es que **exactamente 3 dígitos detrás = separador de miles** (`1.284` son 1284 vistas),
cualquier otra cantidad = decimal (`62,5` es 62.5 %).

**Se puede correr las veces que quieras.** Fusiona por `(PROYECTO, plataforma, fecha_snapshot)`:
reescribe la foto de hoy y conserva las de otros días, así el histórico no se pisa. Nunca sobrescribe
un valor que ya tenía con uno vacío.

---

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
