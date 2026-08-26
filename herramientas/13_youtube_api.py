#%%
"""
13_youtube_api.py — métricas de YouTube por API, sin descargar CSV a mano.

No es un paso del pipeline: se corre aparte, como el 10 y el 11.

Existe por dos motivos, y el segundo es el que no tiene alternativa:

1. Quita un tercio del trabajo semanal de métricas (P-09b). El export de YouTube
   son 4 zips que hay que descargar en tandas porque la gráfica solo marca unos
   pocos videos a la vez.
2. **La curva de retención NO la exporta ningún CSV** (P-12). Es el único sitio
   donde se puede ver si la caída de `se_quedaron_pct` está en los primeros 2
   segundos (el gancho) o en el segundo 3-6 (el ritmo del primer corte).

⚠️ Requiere OAuth, no una API key: son datos privados del canal. El montaje en
Google Cloud Console está en README.md. Dos archivos, los dos secretos y los dos
en .gitignore:

    credenciales/client_secret_*.json   lo descargas de la consola
    credenciales/token_youtube.json     lo escribe este script al autorizar

Uso:
    python herramientas/13_youtube_api.py --autorizar   # una vez, abre el navegador
    python herramientas/13_youtube_api.py --canal       # comprueba a qué canal accede
    python herramientas/13_youtube_api.py --retencion Q1x2y3z   # la curva de un video
    python herramientas/13_youtube_api.py --retencion-lote      # la de todos los del lote nuevo
"""

import argparse
import csv
import json
import re
import sys
from datetime import date, timedelta
from pathlib import Path

CONFIG = {
    "dir_credenciales": "credenciales",
    "token": "credenciales/token_youtube.json",

    # ⚠️ Los dos permisos hacen falta y son distintos:
    #   yt-analytics.readonly  → las métricas (YouTube Analytics API)
    #   youtube.readonly       → qué video es cada ID (YouTube Data API v3)
    "scopes": [
        "https://www.googleapis.com/auth/yt-analytics.readonly",
        "https://www.googleapis.com/auth/youtube.readonly",
    ],

    # Desde cuándo pedir datos. El canal no tiene nada anterior a esto.
    "desde": "2026-05-01",

    # ⚠️ El ID del canal, no su nombre ni su @identificador. Es lo único que no
    # cambia: el nombre visible es "Curiosidades Historicas" y el identificador
    # de YouTube es @curiosidadeshistoricas-03, que NO coincide con el
    # @chistoricas3 de las otras redes (y de la marca de agua del carrusel).
    # Comparar contra cualquiera de los dos daba un falso aviso en cada corrida.
    "canal_esperado": "UCuXiD-UbvlLUxTCmij33Urg",

    "salida_retencion": "metricas_export/retencion_youtube.csv",

    # La curva viene en pasos de 1 % del video (0.00 … 1.00).
    # Los tramos que interesan para P-12, en fracción de la duración:
    "tramo_gancho": (0.00, 0.10),    # los primeros ~2.5 s de un video de 25 s
    "tramo_primer_corte": (0.10, 0.25),
}


# ══════════════════════════════════════════════════════════════
# 🔑  AUTORIZACIÓN
# ══════════════════════════════════════════════════════════════

def _archivo_secreto() -> Path:
    """El client_secret que descargaste de la consola.

    Google lo entrega con un nombre larguísimo
    (`client_secret_1234-abc.apps.googleusercontent.com.json`), así que se busca
    por patrón en vez de pedir que lo renombres.
    """
    carpeta = Path(CONFIG["dir_credenciales"])
    candidatos = sorted(carpeta.glob("client_secret*.json")) if carpeta.exists() else []
    if not candidatos:
        raise SystemExit(
            f"❌ No encuentro ningún 'client_secret*.json' en {carpeta}/.\n"
            f"   Descárgalo de Google Cloud Console (Credenciales → ID de cliente\n"
            f"   de OAuth → Aplicación de escritorio) y muévelo ahí. Los pasos\n"
            f"   completos están en README.md."
        )
    if len(candidatos) > 1:
        print(f"⚠️  Hay {len(candidatos)} client_secret en {carpeta}/. "
              f"Uso {candidatos[0].name}")
    return candidatos[0]


def autorizar(forzar: bool = False, abrir_navegador: bool = True):
    """Devuelve credenciales válidas, reusando el token si lo hay.

    ⚠️ El refresh token solo es permanente si la app está **publicada En
    producción** en la consola. En estado "Prueba", Google lo caduca a los 7
    días y habría que reautorizar cada semana — justo la tarea manual que este
    script viene a quitar.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        raise SystemExit(
            "❌ Faltan las librerías de Google. Instálalas con:\n"
            "   pip install google-api-python-client google-auth-oauthlib"
        )

    ruta_token = Path(CONFIG["token"])
    cred = None

    if ruta_token.exists() and not forzar:
        cred = Credentials.from_authorized_user_file(str(ruta_token),
                                                     CONFIG["scopes"])

    if cred and cred.valid:
        return cred

    if cred and cred.expired and cred.refresh_token:
        try:
            cred.refresh(Request())
            ruta_token.write_text(cred.to_json(), encoding="utf-8")
            print("🔄 Token renovado sin abrir el navegador")
            return cred
        except Exception as exc:
            print(f"⚠️  No se pudo renovar el token ({type(exc).__name__}). "
                  f"Vuelvo a pedir autorización.")
            print("   Si esto pasa cada semana, la app está en estado 'Prueba' "
                  "en la consola: publícala En producción.")

    flujo = InstalledAppFlow.from_client_secrets_file(
        str(_archivo_secreto()), CONFIG["scopes"])
    if abrir_navegador:
        print("🌐 Abriendo el navegador para autorizar…")
    else:
        # ⚠️ Con el navegador abriéndose solo, un error de Google se queda EN el
        # navegador y aquí no llega nada: el script sigue esperando el callback
        # para siempre y parece colgado. Imprimir la URL permite ver qué se está
        # pidiendo (scopes, client_id) y leer el código de error de la respuesta.
        print("🔗 Abre esta URL a mano:\n")
    print("   Si sale 'Google no ha verificado esta aplicación':")
    print("   Configuración avanzada → Ir a … (no seguro). Es tu propia app.\n")
    cred = flujo.run_local_server(port=0, prompt="consent",
                                  open_browser=abrir_navegador)

    ruta_token.parent.mkdir(parents=True, exist_ok=True)
    ruta_token.write_text(cred.to_json(), encoding="utf-8")
    # 0600: da acceso de lectura a las analíticas del canal hasta que se revoque.
    ruta_token.chmod(0o600)
    print(f"✅ Token guardado en {ruta_token} (permisos 600)")
    return cred


def servicios(cred):
    """(analytics, data) — los dos clientes que hacen falta."""
    from googleapiclient.discovery import build
    return (build("youtubeAnalytics", "v2", credentials=cred),
            build("youtube", "v3", credentials=cred))


# ══════════════════════════════════════════════════════════════
# 📺  COMPROBACIÓN
# ══════════════════════════════════════════════════════════════

def comprobar_canal(cred) -> str:
    """Imprime a qué canal se está accediendo y devuelve su ID.

    ⚠️ Vale la pena mirarlo antes de fiarse de ningún número: si autorizaste con
    una cuenta que no es la dueña de @chistoricas3, la API responde 200 con
    datos vacíos en vez de dar un error. Un informe de ceros parece un mal mes.
    """
    _, data = servicios(cred)
    r = data.channels().list(part="snippet,statistics", mine=True).execute()
    items = r.get("items", [])
    if not items:
        raise SystemExit(
            "❌ La cuenta autorizada no tiene ningún canal.\n"
            "   Autorizaste con la cuenta equivocada. Borra "
            f"{CONFIG['token']} y vuelve a correr --autorizar,\n"
            "   eligiendo la cuenta dueña de @chistoricas3."
        )
    canal = items[0]
    snippet = canal["snippet"]
    stats = canal.get("statistics", {})
    print(f"📺 Canal: {snippet['title']}  ({snippet.get('customUrl', '')})")
    print(f"   id {canal['id']}")
    print(f"   {stats.get('videoCount', '?')} videos · "
          f"{stats.get('subscriberCount', '?')} suscriptores · "
          f"{stats.get('viewCount', '?')} visualizaciones")

    esperado = CONFIG.get("canal_esperado")
    if esperado and canal["id"] != esperado:
        print(f"\n⚠️  ESTE NO ES EL CANAL DE SIEMPRE.")
        print(f"   esperado: {esperado}")
        print(f"   obtenido: {canal['id']}")
        print(f"   Las métricas que guardes serían de otro canal. Borra "
              f"{CONFIG['token']} y autoriza con la cuenta correcta.")
    return canal["id"]


# ══════════════════════════════════════════════════════════════
# 📉  CURVA DE RETENCIÓN — lo que ningún export trae (P-12)
# ══════════════════════════════════════════════════════════════

def curva_de_retencion(cred, video_id: str, desde: str = None,
                       hasta: str = None) -> list[dict]:
    """[{ratio, audiencia, relativa}, …] a lo largo del video.

    `elapsedVideoTimeRatio` va de 0.00 a 1.00 en pasos del 1 %.
    `audienceWatchRatio` es qué fracción de espectadores seguía ahí.
    `relativeRetentionPerformance` compara con videos de duración parecida en
    todo YouTube (0.5 = la mediana); solo llega si el video tiene datos
    suficientes, así que puede venir vacío y no es un error.
    """
    analytics, _ = servicios(cred)
    r = analytics.reports().query(
        ids="channel==MINE",
        startDate=desde or CONFIG["desde"],
        endDate=hasta or date.today().isoformat(),
        metrics="audienceWatchRatio,relativeRetentionPerformance",
        dimensions="elapsedVideoTimeRatio",
        filters=f"video=={video_id}",
    ).execute()

    columnas = [c["name"] for c in r.get("columnHeaders", [])]
    filas = []
    for fila in r.get("rows", []):
        d = dict(zip(columnas, fila))
        filas.append({
            "video_id": video_id,
            "ratio": d.get("elapsedVideoTimeRatio"),
            "audiencia": d.get("audienceWatchRatio"),
            "relativa": d.get("relativeRetentionPerformance"),
        })
    return filas


def resumir_curva(curva: list[dict]) -> dict:
    """Reduce la curva a los dos números que decide P-12.

    La pregunta es concreta: ¿la gente se va en el **gancho** (0-10 % del video,
    los primeros ~2.5 s) o en el **primer corte** (10-25 %)? La respuesta manda
    a sitios opuestos — el texto del guion o el ritmo del montaje.
    """
    def media(desde, hasta):
        vals = [c["audiencia"] for c in curva
                if c["audiencia"] is not None
                and desde <= (c["ratio"] or 0) < hasta]
        return sum(vals) / len(vals) if vals else None

    g0, g1 = CONFIG["tramo_gancho"]
    c0, c1 = CONFIG["tramo_primer_corte"]
    inicio = curva[0]["audiencia"] if curva else None
    return {
        "puntos": len(curva),
        "arranque": inicio,
        "gancho": media(g0, g1),
        "primer_corte": media(c0, c1),
        "caida_gancho": (inicio - media(g0, g1))
                        if inicio is not None and media(g0, g1) is not None else None,
    }


def guardar_retencion(filas: list[dict]) -> None:
    ruta = Path(CONFIG["salida_retencion"])
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with ruta.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=["video_id", "ratio", "audiencia", "relativa"])
        w.writeheader()
        w.writerows(filas)
    print(f"✅ Guardado: {ruta}  ({len(filas)} puntos)")


def ids_publicados() -> dict[str, str]:
    """{id_youtube: PROYECTO} de lo que ya está en metricas.csv."""
    ruta = Path("metricas.csv")
    if not ruta.exists():
        return {}
    ids = {}
    with ruta.open(encoding="utf-8") as fh:
        for f in csv.DictReader(fh):
            if f.get("plataforma") == "youtube" and f.get("id_plataforma"):
                ids[f["id_plataforma"]] = f.get("PROYECTO", "")
    return ids


# ══════════════════════════════════════════════════════════════
# 📊  MÉTRICAS POR VIDEO — lo que sustituye a descargar los 4 zips
# ══════════════════════════════════════════════════════════════

# Métricas del API → columnas de metricas.csv.
# ⚠️ Dos columnas del export NO existen en la API y hay que seguir sacándolas
# del CSV si se quieren: `se_quedaron_pct` ("Se quedaron para mirar", que es
# específica de Shorts) y `alcance` (espectadores únicos por video). Por eso
# esto REDUCE el trabajo manual, no lo elimina del todo. Ojo: `se_quedaron_pct`
# es justo la métrica de P-12, así que si se sigue investigando, el export hace
# falta.
METRICAS_API = [
    "views", "estimatedMinutesWatched", "averageViewDuration",
    "averageViewPercentage", "likes", "comments", "shares",
    "subscribersGained",
]


def _iso8601_a_segundos(iso: str) -> int | None:
    """'PT1M14S' → 74. Es como la Data API devuelve la duración."""
    m = re.fullmatch(r"P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:([\d.]+)S)?", iso or "")
    if not m:
        return None
    d, h, mi, s = (float(x) if x else 0 for x in m.groups())
    return int(d * 86400 + h * 3600 + mi * 60 + s)


def catalogo_de_videos(cred) -> dict[str, dict]:
    """{video_id: {titulo, fecha_publicacion, duracion_s}} de todo el canal.

    Sale de la Data API, no de Analytics: la duración y la fecha de publicación
    son propiedades del video, no métricas.
    """
    _, data = servicios(cred)
    canal = data.channels().list(part="contentDetails", mine=True).execute()
    subidas = canal["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    ids, pagina = [], None
    while True:
        r = data.playlistItems().list(part="contentDetails", playlistId=subidas,
                                      maxResults=50, pageToken=pagina).execute()
        ids += [i["contentDetails"]["videoId"] for i in r.get("items", [])]
        pagina = r.get("nextPageToken")
        if not pagina:
            break

    catalogo = {}
    # videos().list acepta 50 ids por llamada; en tandas para no pasarse.
    for i in range(0, len(ids), 50):
        r = data.videos().list(part="snippet,contentDetails",
                               id=",".join(ids[i:i + 50])).execute()
        for v in r.get("items", []):
            catalogo[v["id"]] = {
                "titulo": v["snippet"]["title"],
                "fecha_publicacion": v["snippet"]["publishedAt"][:10],
                "duracion_s": _iso8601_a_segundos(
                    v["contentDetails"].get("duration", "")),
            }
    return catalogo


def metricas_por_video(cred, desde: str = None, hasta: str = None) -> dict[str, dict]:
    """{video_id: {metrica: valor}} acumulado en el periodo."""
    analytics, _ = servicios(cred)
    r = analytics.reports().query(
        ids="channel==MINE",
        startDate=desde or CONFIG["desde"],
        endDate=hasta or date.today().isoformat(),
        metrics=",".join(METRICAS_API),
        dimensions="video",
        sort="-views",
        maxResults=200,
    ).execute()

    columnas = [c["name"] for c in r.get("columnHeaders", [])]
    salida = {}
    for fila in r.get("rows", []):
        d = dict(zip(columnas, fila))
        salida[d.pop("video")] = d
    return salida


def a_filas_de_metricas(catalogo: dict, metricas: dict, hoy: str) -> list[dict]:
    """Pasa lo del API al esquema de metricas.csv.

    Solo se incluyen los videos que tienen métricas: uno recién subido sin
    ninguna vista no aporta una fila, aporta ruido.
    """
    filas = []
    for vid, m in metricas.items():
        info = catalogo.get(vid, {})
        fila = {
            "plataforma": "youtube",
            "id_plataforma": vid,
            "fecha_snapshot": hoy,
            "titulo": " ".join((info.get("titulo") or "").split())[:90],
            "fecha_publicacion": info.get("fecha_publicacion", ""),
            "duracion_s": str(info["duracion_s"]) if info.get("duracion_s") else "",
            "vistas": _n(m.get("views")),
            "me_gusta": _n(m.get("likes")),
            "comentarios": _n(m.get("comments")),
            "compartidos": _n(m.get("shares")),
            "seguidores_ganados": _n(m.get("subscribersGained")),
            "duracion_media_s": _n(m.get("averageViewDuration")),
            "retencion_pct": _n(m.get("averageViewPercentage"), 1),
            "tiempo_total_h": _n(_div(m.get("estimatedMinutesWatched"), 60), 1),
        }
        filas.append(fila)
    return filas


def _n(v, decimales: int = 0) -> str:
    if v is None:
        return ""
    return f"{float(v):.{decimales}f}" if decimales else f"{float(v):.0f}"


def _div(v, d):
    return None if v is None else float(v) / d


def guardar_en_metricas(cred, dry_run: bool = False) -> None:
    """Descarga y funde en metricas.csv **reusando el paso 10**.

    ⚠️ No se reimplementa la fusión ni el emparejado a propósito. `fusionar()`
    del paso 10 ya sabe lo que costó aprender: no pisar un valor lleno con uno
    vacío, conservar las fotos de otros días, y que el `lote` se decide una vez
    y no se degrada. Reescribir eso aquí sería tener dos versiones de las mismas
    reglas y que una se quedara atrás.
    """
    met = _paso10()
    cfg10 = met.CONFIG
    hoy = date.today().isoformat()

    print("📥 Leyendo el catálogo del canal…")
    catalogo = catalogo_de_videos(cred)
    print(f"   {len(catalogo)} videos")

    print("📊 Pidiendo métricas…")
    metricas = metricas_por_video(cred)
    print(f"   {len(metricas)} con datos en el periodo")

    filas = a_filas_de_metricas(catalogo, metricas, hoy)

    # Emparejar con los PROYECTO, con la misma lógica que el paso 10.
    indice = met.indice_proyectos(cfg10)
    temas = met.temas_por_proyecto(cfg10)
    # `asignar_uno_a_uno()` trabaja con los campos internos del paso 10.
    for f in filas:
        f["_texto"] = f["titulo"]
        f["_id"] = f["id_plataforma"]
    asignado, _ = met.asignar_uno_a_uno(filas, indice, cfg10["umbral_match"], {})
    for i, f in enumerate(filas):
        proyecto = asignado.get(i, "")
        f["PROYECTO"] = proyecto
        f["lote"] = met.lote_de(proyecto, cfg10)
        f["tema"] = temas.get(proyecto, "")
        for interno in ("_texto", "_id"):
            f.pop(interno, None)
        met.calcular_retencion(f)

    con_nombre = sum(1 for f in filas if f["PROYECTO"])
    print(f"   {con_nombre} con PROYECTO reconocido · "
          f"{len(filas) - con_nombre} sin él (anteriores al pipeline)")

    ruta = Path(cfg10["salida"])
    previas = met.leer_csv(ruta) if ruta.exists() else []
    fundidas, nuevas_n, actualizadas = met.fusionar(previas, filas)
    print(f"\n📊 {nuevas_n} filas nuevas · {actualizadas} actualizadas · "
          f"{len(fundidas)} en total")

    if dry_run:
        print("🧪 --dry-run: no se escribió nada")
        return
    met.escribir(cfg10["salida"], fundidas)
    print(f"✅ Guardado: {cfg10['salida']}")
    print("\nℹ️  `se_quedaron_pct` y `alcance` NO los da la API: si los quieres,\n"
          "   sigue descargando el export de YouTube. La fusión no los pisa.")


def _paso10():
    """Importa 10_metricas.py (el nombre empieza por dígito: no vale `import`)."""
    import importlib.util
    ruta = Path(__file__).with_name("10_metricas.py")
    spec = importlib.util.spec_from_file_location("met10", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


#%% ══════════════════════════════════════════════════════════════
#   CLI
# ═══════════════════════════════════════════════════════════════

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--autorizar", action="store_true",
                   help="Hace el flujo OAuth y guarda el token")
    p.add_argument("--reautorizar", action="store_true",
                   help="Ignora el token guardado y vuelve a autorizar")
    p.add_argument("--sin-navegador", action="store_true",
                   help="Imprime la URL en vez de abrir el navegador (para diagnosticar)")
    p.add_argument("--canal", action="store_true",
                   help="Comprueba a qué canal se accede")
    p.add_argument("--retencion", metavar="VIDEO_ID",
                   help="Curva de retención de un video")
    p.add_argument("--retencion-lote", action="store_true",
                   help="Curva de todos los videos que ya están en metricas.csv")
    p.add_argument("--metricas", action="store_true",
                   help="Descarga las métricas por video y las funde en metricas.csv")
    p.add_argument("--dry-run", action="store_true",
                   help="Con --metricas: enseña qué haría sin escribir")
    args = p.parse_args()

    if not any(vars(args).values()):
        p.print_help()
        return

    cred = autorizar(forzar=args.reautorizar,
                     abrir_navegador=not args.sin_navegador)

    if args.autorizar or args.reautorizar:
        print()
        comprobar_canal(cred)
        return

    if args.canal:
        comprobar_canal(cred)
        return

    if args.metricas:
        comprobar_canal(cred)
        print()
        guardar_en_metricas(cred, dry_run=args.dry_run)
        return

    if args.retencion:
        curva = curva_de_retencion(cred, args.retencion)
        if not curva:
            print(f"⚠️  Sin datos de retención para {args.retencion}. "
                  f"Puede ser demasiado nuevo o tener muy pocas vistas.")
            return
        r = resumir_curva(curva)
        print(f"\n📉 {args.retencion} — {r['puntos']} puntos")
        print(f"   arranque      : {r['arranque']}")
        print(f"   gancho (0-10%): {r['gancho']}")
        print(f"   corte (10-25%): {r['primer_corte']}")
        guardar_retencion(curva)
        return

    if args.retencion_lote:
        ids = ids_publicados()
        if not ids:
            raise SystemExit("❌ No hay ids de YouTube en metricas.csv. "
                             "Corre antes herramientas/10_metricas.py")
        print(f"📉 Curva de retención de {len(ids)} video(s)…\n")
        todas = []
        for vid, proyecto in ids.items():
            curva = curva_de_retencion(cred, vid)
            if not curva:
                print(f"   ⚠️  {proyecto or vid}: sin datos")
                continue
            r = resumir_curva(curva)
            todas.extend(curva)
            print(f"   {proyecto or vid:<14} gancho {r['gancho']}  "
                  f"corte {r['primer_corte']}")
        if todas:
            guardar_retencion(todas)


if __name__ == "__main__":
    main()
