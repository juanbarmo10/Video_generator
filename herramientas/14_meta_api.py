#%%
"""
14_meta_api.py — Instagram y Facebook por API: métricas hoy, publicación después.

No es un paso del pipeline: se corre aparte, como el 10, el 11 y el 13.

Cierra dos pendientes con un solo trámite de credenciales:
  · P-09b — las métricas de IG y FB, que hoy se descargan a mano en tres CSV.
  · P-10  — publicar, que hoy es el único paso 100 % manual de la semana.

⚠️ **`desuso/publisher.py` NO sirve como base.** No es que le falten credenciales:
sube el video con `files={"video": f}` a `/media`, y la API de publicación de
Instagram no funciona así. Para un archivo local hay que usar la **subida
reanudable** contra `rupload.facebook.com` (ver `_subir_video_ig()`). La forma
que usa el archivo viejo falla siempre, con credenciales o sin ellas.

Uso:
    python herramientas/14_meta_api.py --diagnostico   # empieza por aquí
    python herramientas/14_meta_api.py --metricas
    python herramientas/14_meta_api.py --metricas --dry-run
"""

import argparse
import os
import re
from datetime import date
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

CONFIG = {
    # ⚠️ Si Meta deprecia esta versión, los errores llegan como 400 con un
    # mensaje que no menciona la versión. Se sube aquí y en ningún otro sitio.
    "api": "v21.0",
    "graph": "https://graph.facebook.com",
    "rupload": "https://rupload.facebook.com/ig-api-upload",

    "permisos_necesarios": [
        "instagram_basic",
        "instagram_manage_insights",
        "instagram_content_publish",
        "pages_show_list",
        "pages_read_engagement",
        "pages_manage_posts",
        "read_insights",
    ],
    # Los que solo hacen falta para publicar (P-10), no para leer métricas.
    "permisos_solo_publicar": ["instagram_content_publish", "pages_manage_posts"],

    "timeout": 30,
}

TOKEN = os.getenv("META_ACCESS_TOKEN", "").strip()
APP_ID = os.getenv("META_APP_ID", "").strip()
APP_SECRET = os.getenv("META_APP_SECRET", "").strip()


def alargar_token(token_corto: str) -> str | None:
    """Cambia un token de usuario de ~2 h por uno de 60 días.

    ⚠️ **Es el paso que hace permanente al token de página**, y el que más se
    salta la gente. El de página hereda la caducidad del de usuario del que sale:
    derivado de uno corto dura horas, derivado de uno largo **no caduca**. Sin
    esto, las métricas dejan de bajar a media tarde del mismo día.

    Necesita `META_APP_ID` y `META_APP_SECRET` (panel de la app →
    Configuración → Básica). Si no están, se puede hacer a mano desde el
    Explorador: el icono ⓘ junto al token → *Abrir en herramienta de depuración*
    → **Extender token de acceso**, abajo del todo.
    """
    if not (APP_ID and APP_SECRET):
        return None
    r = requests.get(
        f"{CONFIG['graph']}/{CONFIG['api']}/oauth/access_token",
        params={"grant_type": "fb_exchange_token", "client_id": APP_ID,
                "client_secret": APP_SECRET, "fb_exchange_token": token_corto},
        timeout=CONFIG["timeout"])
    datos = r.json()
    if "error" in datos:
        print(f"   ⚠️  No se pudo alargar el token: {datos['error'].get('message')}")
        return None
    return datos.get("access_token")


def _graph(ruta: str, tolerar_error: bool = False, **params) -> dict:
    """GET contra la Graph API con el token puesto y los errores legibles.

    ⚠️ Meta devuelve los errores con HTTP 400 y el detalle en el cuerpo, así que
    `raise_for_status()` a secas pierde justo lo que dice qué falta.

    `tolerar_error=True` devuelve `{"_error": "..."}` en vez de abortar. Lo usa
    el diagnóstico: **su trabajo es funcionar cuando faltan permisos**, que es
    justo cuando más falta hace. Abortando en la primera llamada que falla se
    perdía todo lo que sí se podía averiguar con los permisos que ya había.
    """
    params["access_token"] = TOKEN
    r = requests.get(f"{CONFIG['graph']}/{CONFIG['api']}/{ruta.lstrip('/')}",
                     params=params, timeout=CONFIG["timeout"])
    datos = r.json()
    if "error" in datos:
        e = datos["error"]
        detalle = (f"{e.get('message')} (tipo {e.get('type')}, código {e.get('code')}"
                   + (f", subcódigo {e['error_subcode']}" if e.get("error_subcode") else "")
                   + ")")
        if tolerar_error:
            return {"_error": detalle}
        raise SystemExit(f"❌ Meta respondió con un error en /{ruta}:\n   {detalle}")
    return datos


def _exigir_token() -> None:
    if not TOKEN:
        raise SystemExit(
            "❌ Falta META_ACCESS_TOKEN en el .env.\n"
            "   Se genera en el Explorador de la API Graph:\n"
            "   https://developers.facebook.com/tools/explorer/\n"
            "   Los pasos completos están en README.md."
        )


# ══════════════════════════════════════════════════════════════
# 🩺  DIAGNÓSTICO — convierte un token suelto en todo lo demás
# ══════════════════════════════════════════════════════════════

def diagnostico() -> dict:
    """Comprueba el token y descubre los IDs. Devuelve lo que encuentre.

    ⚠️ Existe porque los IDs de página y de cuenta de Instagram **no están a la
    vista en ninguna pantalla obvia** de Meta, y pedirlos a mano es la parte del
    montaje donde más se falla. Aquí salen de una llamada.
    """
    _exigir_token()
    hallado = {}

    # 1 · Qué es este token y cuándo caduca
    resp_token = _graph("debug_token", tolerar_error=True, input_token=TOKEN)
    if "_error" in resp_token:
        print(f"🔑 Token: no se pudo inspeccionar\n   {resp_token['_error']}")
        info = {}
    else:
        info = resp_token.get("data", {})
    tipo = info.get("type", "?")
    expira = info.get("expires_at", 0)
    print(f"🔑 Token de tipo {tipo}, app {info.get('app_id', '?')}")
    if expira == 0:
        print("   ✅ No caduca")
    else:
        from datetime import datetime, timezone
        cuando = datetime.fromtimestamp(expira, timezone.utc)
        horas = (cuando - datetime.now(timezone.utc)).total_seconds() / 3600
        marca = "✅" if horas > 24 * 30 else ("⚠️ " if horas > 0 else "❌")
        print(f"   {marca} Caduca el {cuando:%Y-%m-%d %H:%M} "
              f"({horas / 24:.0f} días)" if horas > 48 else
              f"   {marca} Caduca el {cuando:%Y-%m-%d %H:%M} (en {horas:.1f} horas)")

        # ⚠️ El de página HEREDA la caducidad del de usuario del que sale. Con un
        # token corto, el de página también dura horas: hay que alargar ANTES.
        if horas < 24 * 7:
            # ⚠️ Un token de PÁGINA no se puede intercambiar: `fb_exchange_token`
            # responde «An unexpected error has occurred. Please retry your request
            # later», que suena a fallo transitorio y no lo es — reintentarlo no
            # funciona nunca. La permanencia se hereda, no se pide: hay que alargar
            # el token de USUARIO y derivar la página DESPUÉS.
            largo = None if tipo == "PAGE" else alargar_token(TOKEN)
            if largo:
                print("   🔄 Alargado a 60 días con META_APP_ID/META_APP_SECRET.")
                print("      Los tokens de página que salgan de este YA no caducan.")
                hallado["_token_largo"] = largo
                globals()["TOKEN"] = largo
            elif tipo == "PAGE":
                print("      ⚠️  Este token es de PÁGINA y los de página NO se pueden alargar.\n"
                      "      La permanencia se HEREDA del token de usuario del que salen, así\n"
                      "      que hay que rehacer el camino entero, en este orden:\n"
                      "        1. Explorador de la API Graph → arriba a la derecha, en\n"
                      "           «Usuario o página», elige **Usuario actual** (no la página).\n"
                      "        2. Genera el token y ponlo en META_ACCESS_TOKEN del .env.\n"
                      "        3. Repite este diagnóstico con --escribir-env: alarga el de\n"
                      "           usuario a 60 días y de él saca el de página, que ya NO caduca.")
            else:
                print("      ⚠️  Este token dura horas, y el de PÁGINA que salga de él\n"
                      "      heredará esa caducidad. Alárgalo antes, de una de las dos formas:\n"
                      "        · pon META_APP_ID y META_APP_SECRET en el .env y repite, o\n"
                      "        · en el Explorador, icono ⓘ junto al token → Abrir en\n"
                      "          herramienta de depuración → «Extender token de acceso».")

    # 2 · Permisos: los que hay contra los que hacen falta
    #
    # ⚠️ Salen de `debug_token`, NO de `me/permissions`. Esa segunda llamada solo
    # responde a tokens de USUARIO: con uno de página devuelve una lista vacía sin
    # dar error, y entonces el diagnóstico anunciaba «0/7 permisos» y mandaba a
    # regenerar el token cuando estaban los siete concedidos. `debug_token` trae
    # los `scopes` de los dos tipos, y ya se ha llamado arriba.
    concedidos = set(info.get("scopes", []))
    if not concedidos:
        perms = _graph("me/permissions", tolerar_error=True)
        concedidos = {p["permission"] for p in perms.get("data", [])
                      if p.get("status") == "granted"}

    # ⚠️ Meta partió la API de Instagram en dos caminos que NO son intercambiables:
    #   · "con Facebook Login"  → instagram_basic…      · graph.facebook.com
    #   · "con Instagram Login" → instagram_business_…  · graph.instagram.com
    # Este archivo habla el primero, que es el único que además publica en la
    # página de Facebook. Si la app se creó por el segundo camino, las llamadas
    # fallan con "permiso no válido" sin decir que el problema es el camino.
    if any(p.startswith("instagram_business_") for p in concedidos):
        raise SystemExit(
            "❌ La app se creó por el camino **Instagram API con Instagram Login**\n"
            f"   (los permisos salen como `instagram_business_*`).\n\n"
            "   Este pipeline necesita el otro: **Instagram API con Facebook Login**,\n"
            "   porque el mismo reel va también a la página de Facebook, y ese camino\n"
            "   es el único que toca las dos redes con un solo token.\n\n"
            "   Créala de nuevo eligiendo el caso de uso que menciona la PÁGINA DE\n"
            "   FACEBOOK y su cuenta de Instagram vinculada, no el de solo Instagram."
        )
    faltan = [p for p in CONFIG["permisos_necesarios"] if p not in concedidos]
    print(f"\n🔐 Permisos: {len(concedidos & set(CONFIG['permisos_necesarios']))}"
          f"/{len(CONFIG['permisos_necesarios'])}")
    for p in CONFIG["permisos_necesarios"]:
        solo_pub = p in CONFIG["permisos_solo_publicar"]
        etiqueta = " (solo para publicar)" if solo_pub else ""
        print(f"   {'✅' if p in concedidos else '❌'} {p}{etiqueta}")
    if faltan:
        print(f"\n   Vuelve al Explorador de la API Graph, marca los que faltan y\n"
              f"   genera el token otra vez.")

    # 3 · Páginas de Facebook y su token (el que NO caduca)
    #
    # ⚠️ `me/accounts` **necesita un token de USUARIO**: con uno de página, `me`
    # ya ES la página, y Meta responde «nonexisting field (accounts)» — que no
    # dice en ningún momento que el problema sea el tipo de token. Con un token
    # de página no hay nada que enumerar: la página es una sola y es esta, así
    # que se pregunta por ella directamente y el diagnóstico sigue sirviendo.
    if tipo == "PAGE":
        resp = _graph("me", tolerar_error=True, fields="id,name")
        paginas = [] if "_error" in resp else [resp]
        print("\n📘 Página del token (es de PÁGINA: no hay lista que enumerar)")
    else:
        resp = _graph("me/accounts", tolerar_error=True, fields="id,name,access_token")
        paginas = [] if "_error" in resp else resp.get("data", [])
        print(f"\n📘 Páginas de Facebook: "
              + ("no se pudieron leer" if "_error" in resp else str(len(paginas))))
    if "_error" in resp:
        print(f"   {resp['_error']}")
    for pg in paginas:
        print(f"   · {pg['name']}  →  FACEBOOK_PAGE_ID={pg['id']}")
    if not paginas and "_error" not in resp:
        print("   ❌ Ninguna. La cuenta no administra ninguna página, o el token no\n"
              "      tiene `pages_show_list`.")

    # 4 · Cuenta de Instagram vinculada a cada página
    #
    # ⚠️ Y de paso, esto es lo que DESAMBIGUA la página cuando hay varias. Una
    # cuenta personal suele administrar páginas de otros proyectos (aquí tres),
    # y elegir «la primera» sería jugársela: el pipeline publicaría en la página
    # equivocada. La página del canal es la única con el Instagram vinculado, así
    # que ese es el criterio, no el nombre ni el orden.
    print(f"\n📸 Cuentas de Instagram:")
    encontradas = []
    for pg in paginas:
        d = _graph(f"{pg['id']}", tolerar_error=True,
                   fields="instagram_business_account{id,username}")
        if "_error" in d:
            print(f"   · «{pg['name']}»: {d['_error'][:90]}")
            continue
        ig = d.get("instagram_business_account")
        if ig:
            encontradas.append((ig, pg))
            print(f"   · @{ig.get('username', '?')} en «{pg['name']}»  →  "
                  f"INSTAGRAM_ACCOUNT_ID={ig['id']}")
    if not encontradas and paginas:
        print("   ❌ Ninguna vinculada.\n"
              "      La cuenta de Instagram tiene que ser **Empresa o Creador** y estar\n"
              "      vinculada a la página de Facebook. Con cuenta personal no hay API.")
    elif len(encontradas) == 1:
        ig, pg = encontradas[0]
        hallado["INSTAGRAM_ACCOUNT_ID"] = ig["id"]
        hallado["FACEBOOK_PAGE_ID"] = pg["id"]
        hallado["_token_pagina"] = pg.get("access_token", "")
        hallado["_nombre_pagina"] = pg["name"]
        if len(paginas) > 1:
            print(f"\n   → De las {len(paginas)} páginas, la del canal es «{pg['name']}»:\n"
                  f"     es la única con Instagram vinculado.")
    elif len(encontradas) > 1:
        print(f"\n   ⚠️  Hay {len(encontradas)} páginas con Instagram vinculado. Elige a mano\n"
              f"      cuál es la del canal y pon sus dos IDs en el .env.")
    elif len(paginas) == 1:
        hallado["FACEBOOK_PAGE_ID"] = paginas[0]["id"]
        hallado["_token_pagina"] = paginas[0].get("access_token", "")

    # 5 · Qué escribir en el .env
    if hallado:
        print(f"\n📝 Añade esto al .env:")
        for k in ("FACEBOOK_PAGE_ID", "INSTAGRAM_ACCOUNT_ID"):
            if k in hallado:
                print(f"   {k}={hallado[k]}")
        if hallado.get("_token_pagina"):
            corto = expira and not hallado.get("_token_largo")
            tk = hallado["_token_pagina"]
            print(f"\n   Y cambia META_ACCESS_TOKEN por el token de PÁGINA de "
                  f"«{hallado.get('_nombre_pagina', '?')}»:")
            # ⚠️ Enmascarado a propósito. Es una credencial que permite PUBLICAR
            # en tu nombre, y esta salida acaba en logs, en capturas y en el
            # historial del terminal. Para ponerlo en el .env está --escribir-env,
            # que además evita copiar 200 caracteres a mano.
            print(f"   META_ACCESS_TOKEN={tk[:8]}…{tk[-6:]}  ({len(tk)} caracteres)")
            print(f"   → escríbelo con:  python herramientas/14_meta_api.py "
                  f"--diagnostico --escribir-env")
            if corto:
                print(f"\n   ⚠️  PERO ESTE TOKEN DE PÁGINA TAMBIÉN CADUCA, porque sale de un\n"
                      f"   token de usuario corto. Alarga primero el de usuario (arriba),\n"
                      f"   vuelve a correr el diagnóstico, y usa el token de página de ESA\n"
                      f"   corrida — ese ya no caduca.")

    listo = not faltan and "FACEBOOK_PAGE_ID" in hallado and "INSTAGRAM_ACCOUNT_ID" in hallado
    if listo:
        print("\n✅ Todo listo: ya se pueden leer métricas y publicar.")
    elif not faltan:
        print("\n⚠️  Los permisos están, pero falta descubrir algún ID (mira arriba).")
    else:
        solo_lectura = [p for p in faltan if p not in CONFIG["permisos_solo_publicar"]]
        if solo_lectura:
            print(f"\n⚠️  Faltan {len(faltan)} permiso(s). Con los que hay todavía no se\n"
                  f"   pueden leer las métricas.")
        else:
            print("\n✅ Suficiente para LEER MÉTRICAS. Lo que falta es solo para publicar,\n"
                  "   así que se puede seguir con P-09b y dejar P-10 para después.")
    return hallado


# ══════════════════════════════════════════════════════════════
# 📊  MÉTRICAS — P-09b
# ══════════════════════════════════════════════════════════════
#
# ⚠️ Este mapeo NO se dedujo de la documentación: se preguntó a la API con la
# cuenta real (15 ago 2026), porque los nombres cambian entre versiones y la
# documentación va por detrás. Lo que se descubrió preguntando:
#   · `plays` está DEPRECADO en Instagram; el bueno es `views`.
#   · Los tiempos vienen en MILISEGUNDOS en las dos redes. El export en CSV los
#     da en segundos con decimales — de ahí el `9.378` que ya dio problemas.
#   · Facebook expone `post_video_retention_graph`, una curva de retención de 33
#     puntos que ningún export trae. Sirve para P-20.
IG_METRICAS = ("views,reach,likes,comments,shares,saved,total_interactions,"
               "ig_reels_avg_watch_time,ig_reels_video_view_total_time")

IG_A_COLUMNA = {
    "views": "vistas",
    "reach": "alcance",
    "likes": "me_gusta",
    "comments": "comentarios",
    "shares": "compartidos",
    "saved": "guardados",
    "total_interactions": "interacciones",
}
FB_A_COLUMNA = {
    "fb_reels_total_plays": "vistas",
    "post_impressions_unique": "alcance",
    "post_video_followers": "seguidores_ganados",
}
# Los que hay que dividir: {métrica: (columna, divisor)}. ms → s, ms → h.
IG_TIEMPOS = {"ig_reels_avg_watch_time": ("duracion_media_s", 1000),
              "ig_reels_video_view_total_time": ("tiempo_total_h", 1000 * 3600)}
FB_TIEMPOS = {"post_video_avg_time_watched": ("duracion_media_s", 1000),
              "post_video_view_time": ("tiempo_total_h", 1000 * 3600)}


def _insights(ruta: str, metric: str = "") -> dict:
    """{nombre: valor} de un endpoint de insights. {} si falla."""
    params = {"metric": metric} if metric else {}
    d = _graph(ruta, tolerar_error=True, **params)
    if "_error" in d:
        return {}
    return {x["name"]: (x["values"][0].get("value") if x.get("values") else None)
            for x in d.get("data", [])}


def _num(v, divisor: int = 1, dec: int = 0) -> str:
    if v is None:
        return ""
    try:
        n = float(v) / divisor
    except (TypeError, ValueError):
        return ""
    return f"{n:.{dec}f}"


def metricas_instagram(hoy: str, limite: int = 100) -> list[dict]:
    ig = os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip()
    if not ig:
        print("   ⚠️  Falta INSTAGRAM_ACCOUNT_ID en el .env")
        return []
    filas, despues = [], None
    while len(filas) < limite:
        params = {"fields": "id,caption,media_type,media_product_type,timestamp",
                  "limit": 25}
        if despues:
            params["after"] = despues
        r = _graph(f"{ig}/media", tolerar_error=True, **params)
        if "_error" in r:
            print(f"   ❌ {r['_error'][:110]}")
            break
        for m in r.get("data", []):
            ins = _insights(f"{m['id']}/insights", IG_METRICAS)
            fila = {
                "plataforma": "instagram", "id_plataforma": m["id"],
                "fecha_snapshot": hoy,
                "fecha_publicacion": (m.get("timestamp") or "")[:10],
                "titulo": " ".join((m.get("caption") or "").split())[:90],
            }
            for k, col in IG_A_COLUMNA.items():
                fila[col] = _num(ins.get(k))
            for k, (col, div) in IG_TIEMPOS.items():
                fila[col] = _num(ins.get(k), div, 1 if div == 1000 else 2)
            filas.append(fila)
        despues = r.get("paging", {}).get("cursors", {}).get("after")
        if not despues or not r.get("data"):
            break
    return filas


def metricas_facebook(hoy: str, limite: int = 100) -> list[dict]:
    pg = os.getenv("FACEBOOK_PAGE_ID", "").strip()
    if not pg:
        print("   ⚠️  Falta FACEBOOK_PAGE_ID en el .env")
        return []
    filas, despues = [], None
    while len(filas) < limite:
        # ⚠️ `post_id` no es opcional. `video_reels` devuelve el id del VIDEO
        # (1033620252602631) y el export en CSV trae el id del POST
        # (122111309283294832). Son distintos y ninguno de los dos lo dice.
        # Usando el del video, cada reel entraba como fila NUEVA en vez de
        # fusionarse con la del export: 45 filas fantasma, cada video contado
        # dos veces y las medianas del informe calculadas sobre datos repetidos.
        # Se descubrió porque la fusión anunció 45 nuevas donde debían ser 0.
        params = {"fields": "id,post_id,description,created_time", "limit": 25}
        if despues:
            params["after"] = despues
        r = _graph(f"{pg}/video_reels", tolerar_error=True, **params)
        if "_error" in r:
            print(f"   ❌ {r['_error'][:110]}")
            break
        for v in r.get("data", []):
            ins = _insights(f"{v['id']}/video_insights")
            reacciones = ins.get("post_video_likes_by_reaction_type") or {}
            fila = {
                "plataforma": "facebook",
                "id_plataforma": v.get("post_id") or v["id"],
                "fecha_snapshot": hoy,
                "fecha_publicacion": (v.get("created_time") or "")[:10],
                "titulo": " ".join((v.get("description") or "").split())[:90],
            }
            for k, col in FB_A_COLUMNA.items():
                fila[col] = _num(ins.get(k))
            for k, (col, div) in FB_TIEMPOS.items():
                fila[col] = _num(ins.get(k), div, 1 if div == 1000 else 2)
            if isinstance(reacciones, dict) and reacciones:
                fila["me_gusta"] = str(sum(reacciones.values()))
            filas.append(fila)
        despues = r.get("paging", {}).get("cursors", {}).get("after")
        if not despues or not r.get("data"):
            break
    return filas


def guardar_en_metricas(dry_run: bool = False) -> None:
    """Descarga IG + FB y funde en metricas.csv **reusando el paso 10**.

    Igual que en el 13: no se reimplementa la fusión. `fusionar()` ya sabe no
    pisar un valor lleno con uno vacío, conservar las fotos de otros días y no
    degradar el lote.
    """
    _exigir_token()
    met = _paso10()
    cfg10 = met.CONFIG
    hoy = date.today().isoformat()

    print("📸 Instagram…")
    filas = metricas_instagram(hoy)
    print(f"   {len(filas)} publicaciones")
    print("📘 Facebook…")
    fb = metricas_facebook(hoy)
    print(f"   {len(fb)} publicaciones")
    filas += fb
    if not filas:
        raise SystemExit("❌ Nada que guardar.")

    indice = met.indice_proyectos(cfg10)
    nuevos = met.proyectos_del_lote_nuevo(cfg10)
    temas = met.temas_por_proyecto(cfg10)
    for f in filas:
        f["_texto"], f["_id"] = f["titulo"], f["id_plataforma"]

    for plataforma in ("instagram", "facebook"):
        suyas = [f for f in filas if f["plataforma"] == plataforma]
        asignado, _ = met.asignar_uno_a_uno(suyas, indice, cfg10["umbral_match"], {})
        for i, f in enumerate(suyas):
            proyecto = asignado.get(i, "")
            f["PROYECTO"] = proyecto
            f["lote"] = (cfg10["lote_nuevo"] if proyecto in nuevos
                         else cfg10["lote_baseline"])
            f["tema"] = temas.get(proyecto, "")

    for f in filas:
        for interno in ("_texto", "_id"):
            f.pop(interno, None)
        met.calcular_retencion(f)

    # ⚠️ Fuera las publicaciones sin ninguna métrica. La API deja de devolver
    # insights de las más antiguas (aquí, las de mayo), y una fila con todo
    # vacío no aporta nada: solo ensucia metricas.csv y baja las n del informe.
    METRICAS = ("vistas", "alcance", "me_gusta", "duracion_media_s")
    vacias = [f for f in filas if not any(f.get(c, "").strip() for c in METRICAS)]
    if vacias:
        filas = [f for f in filas if f not in vacias]
        print(f"   ⏭️  {len(vacias)} publicación(es) sin métricas, descartadas "
              f"(la API no las devuelve para las más antiguas)")

    con_nombre = sum(1 for f in filas if f["PROYECTO"])
    print(f"\n   {con_nombre} con PROYECTO reconocido · {len(filas) - con_nombre} sin él")

    ruta = Path(cfg10["salida"])
    previas = met.leer_csv(ruta) if ruta.exists() else []

    # La duración se presta entre plataformas: es el MISMO video en las cuatro
    # redes, y ni IG ni FB la exponen en sus insights. Sin ella no hay retención.
    # Las de YouTube ya están en metricas.csv, así que se toman de ahí.
    duraciones = {f["PROYECTO"]: f["duracion_s"] for f in previas
                  if f.get("PROYECTO") and f.get("duracion_s")}
    prestadas = 0
    for f in filas:
        if not f.get("duracion_s") and duraciones.get(f.get("PROYECTO")):
            f["duracion_s"] = duraciones[f["PROYECTO"]]
            f["notas"] = (f.get("notas") or "") + "duración tomada de otra red; "
            met.calcular_retencion(f)
            prestadas += 1
    if prestadas:
        print(f"   🔁 {prestadas} fila(s) tomaron la duración de otra red "
              f"→ retención calculable")

    fundidas, nuevas_n, actualizadas = met.fusionar(previas, filas)
    print(f"📊 {nuevas_n} filas nuevas · {actualizadas} actualizadas · "
          f"{len(fundidas)} en total")
    if dry_run:
        print("🧪 --dry-run: no se escribió nada")
        return
    met.escribir(cfg10["salida"], fundidas)
    print(f"✅ Guardado: {cfg10['salida']}")


def _paso10():
    """Importa 10_metricas.py (empieza por dígito: no vale `import`)."""
    import importlib.util
    ruta = Path(__file__).with_name("10_metricas.py")
    spec = importlib.util.spec_from_file_location("met10", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


# ══════════════════════════════════════════════════════════════
# 📤  PUBLICAR — P-10
# ══════════════════════════════════════════════════════════════
#
# ⚠️ **Publicar es irreversible y es hacia fuera.** Un error aquí no deja un
# archivo mal en el disco: deja un reel publicado en una cuenta real. Por eso:
#   · `--dry-run` hace TODO menos la llamada final, incluida la subida del
#     video, así que valida el camino entero sin publicar nada.
#   · Se registra en `publicar/publicado.csv` y se comprueba antes de subir,
#     porque el calendario dice cuándo TOCABA publicar, no si se hizo. Sin eso,
#     correr el comando dos veces publica el mismo reel dos veces.

REGISTRO_PUBLICADO = "publicar/publicado.csv"
SECCIONES = {
    "instagram": "DESCRIPCIÓN GENERAL",
    "facebook": "DESCRIPCIÓN LARGA",
}


def secciones_de(ruta: Path) -> dict[str, str]:
    """{título: contenido} de `descripcion.txt`.

    ⚠️ El corte se hace por la **línea de guiones** que el paso 02 escribe bajo
    cada título, no por «el título va en mayúsculas»: los títulos reales llevan
    minúsculas dentro (`TAGS DE YOUTUBE (separados por coma)`,
    `DESCRIPCIÓN LARGA (YouTube y Facebook) — 1447/1999 caracteres`). Detectarlos
    por mayúsculas hacía que una sección se tragara todas las siguientes, y el
    pie del reel de Instagram habría salido con los tags de YouTube pegados.
    """
    lineas = ruta.read_text(encoding="utf-8").splitlines()
    rayas = [i for i, l in enumerate(lineas) if l.strip() and set(l.strip()) == {"─"}]
    secciones = {}
    for n, raya in enumerate(rayas):
        if raya == 0:
            continue
        titulo = lineas[raya - 1].strip()
        # El contenido llega hasta el título de la sección siguiente, que es la
        # línea justo encima de su raya.
        fin = (rayas[n + 1] - 1) if n + 1 < len(rayas) else len(lineas)
        secciones[titulo] = "\n".join(lineas[raya + 1:fin]).strip()
    return secciones


def leer_seccion(ruta: Path, encabezado: str) -> str:
    """El contenido de la sección cuyo título empieza por `encabezado`."""
    for titulo, cuerpo in secciones_de(ruta).items():
        if titulo.upper().startswith(encabezado.upper()):
            return cuerpo
    return ""


def ya_publicado(proyecto: str, red: str) -> dict | None:
    ruta = Path(REGISTRO_PUBLICADO)
    if not ruta.exists():
        return None
    import csv as _csv
    with ruta.open(encoding="utf-8") as fh:
        for f in _csv.DictReader(fh):
            if f.get("proyecto") == proyecto and f.get("red") == red:
                return f
    return None


def anotar_publicado(proyecto: str, red: str, id_pub: str) -> None:
    """⚠️ Se llama SOLO cuando la red confirma, igual que en el recordatorio de
    Telegram. Anotarlo antes haría que un fallo de red marcara como publicado
    algo que no salió, y ese reel no se volvería a intentar nunca."""
    import csv as _csv
    ruta = Path(REGISTRO_PUBLICADO)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    nuevo = not ruta.exists()
    with ruta.open("a", encoding="utf-8", newline="") as fh:
        w = _csv.writer(fh)
        if nuevo:
            w.writerow(["fecha", "proyecto", "red", "id_publicacion"])
        w.writerow([date.today().isoformat(), proyecto, red, id_pub])


def _subir_bytes(url: str, video: Path) -> bool:
    """Sube el archivo a rupload con el protocolo reanudable de Meta."""
    datos = video.read_bytes()
    r = requests.post(url, data=datos, timeout=600, headers={
        "Authorization": f"OAuth {TOKEN}",
        "offset": "0",
        "file_size": str(len(datos)),
    })
    try:
        respuesta = r.json()
    except ValueError:
        respuesta = {"_raw": r.text[:200]}
    if r.status_code >= 400 or "error" in respuesta:
        print(f"   ❌ Falló la subida: {respuesta}")
        return False
    return True


def publicar_instagram(video: Path, caption: str, dry_run: bool) -> str | None:
    """Reel de Instagram desde un archivo LOCAL.

    ⚠️ La vía documentada estándar (`video_url`) exige que el mp4 esté en una
    URL pública, cosa que este pipeline no tiene. La alternativa es la subida
    reanudable a `rupload.facebook.com`, que sí acepta bytes locales: por eso el
    `upload_type=resumable`. `desuso/publisher.py` mandaba el archivo como
    `files={"video": …}` a `/media`, que no es ninguna de las dos y falla siempre.
    """
    ig = os.getenv("INSTAGRAM_ACCOUNT_ID", "").strip()
    if not ig:
        print("   ❌ Falta INSTAGRAM_ACCOUNT_ID"); return None

    r = requests.post(f"{CONFIG['graph']}/{CONFIG['api']}/{ig}/media",
                      data={"media_type": "REELS", "upload_type": "resumable",
                            "caption": caption, "access_token": TOKEN},
                      timeout=CONFIG["timeout"]).json()
    if "error" in r:
        print(f"   ❌ No se creó el contenedor: {r['error'].get('message')}")
        return None
    contenedor = r.get("id")
    print(f"   contenedor {contenedor}")

    if not _subir_bytes(f"{CONFIG['rupload']}/{CONFIG['api']}/{contenedor}", video):
        return None
    print(f"   ✅ video subido ({video.stat().st_size / 1e6:.1f} MB)")

    import time
    for intento in range(30):
        time.sleep(5)
        est = _graph(f"{contenedor}", tolerar_error=True, fields="status_code,status")
        codigo = est.get("status_code")
        if codigo == "FINISHED":
            break
        if codigo == "ERROR":
            print(f"   ❌ Meta rechazó el video: {est.get('status')}")
            return None
    else:
        print("   ❌ El video sigue procesándose tras 150 s. No se publica.")
        return None

    if dry_run:
        print("   🧪 --dry-run: subido y procesado, NO publicado")
        return "dry-run"

    pub = requests.post(f"{CONFIG['graph']}/{CONFIG['api']}/{ig}/media_publish",
                        data={"creation_id": contenedor, "access_token": TOKEN},
                        timeout=CONFIG["timeout"]).json()
    if "error" in pub:
        print(f"   ❌ {pub['error'].get('message')}")
        return None
    return pub.get("id")


def publicar_facebook(video: Path, descripcion: str, dry_run: bool) -> str | None:
    """Reel de la página de Facebook, en tres fases (start → subida → finish)."""
    pg = os.getenv("FACEBOOK_PAGE_ID", "").strip()
    if not pg:
        print("   ❌ Falta FACEBOOK_PAGE_ID"); return None

    base = f"{CONFIG['graph']}/{CONFIG['api']}/{pg}/video_reels"
    r = requests.post(base, data={"upload_phase": "start", "access_token": TOKEN},
                      timeout=CONFIG["timeout"]).json()
    if "error" in r:
        print(f"   ❌ No se inició la subida: {r['error'].get('message')}")
        return None
    video_id, url = r.get("video_id"), r.get("upload_url")
    print(f"   video_id {video_id}")

    if not _subir_bytes(url, video):
        return None
    print(f"   ✅ video subido ({video.stat().st_size / 1e6:.1f} MB)")

    if dry_run:
        print("   🧪 --dry-run: subido, NO publicado (queda sin finalizar)")
        return "dry-run"

    fin = requests.post(base, data={
        "video_id": video_id, "upload_phase": "finish",
        "video_state": "PUBLISHED", "description": descripcion,
        "access_token": TOKEN}, timeout=CONFIG["timeout"]).json()
    if "error" in fin:
        print(f"   ❌ {fin['error'].get('message')}")
        return None
    return video_id


def publicar(proyecto: str, redes: list[str], dry_run: bool) -> None:
    _exigir_token()
    carpeta = Path("publicar") / proyecto
    video = carpeta / f"{proyecto}.mp4"
    desc = carpeta / "descripcion.txt"
    if not video.exists():
        raise SystemExit(f"❌ No existe {video}")
    if not desc.exists():
        raise SystemExit(f"❌ No existe {desc}")

    print(f"📤 {proyecto}  ({video.stat().st_size / 1e6:.1f} MB)"
          + ("   🧪 DRY-RUN" if dry_run else ""))

    for red in redes:
        texto = leer_seccion(desc, SECCIONES[red])
        if not texto:
            print(f"\n⚠️  {red}: no encontré la sección "
                  f"«{SECCIONES[red]}» en descripcion.txt. Se salta.")
            continue

        previo = ya_publicado(proyecto, red)
        if previo and not dry_run:
            print(f"\n⏭️  {red}: ya se publicó el {previo['fecha']} "
                  f"(id {previo['id_publicacion']}). Se salta.")
            continue

        print(f"\n── {red} ──  {len(texto)} caracteres")
        print("   " + texto.split("\n")[0][:88])

        fn = publicar_instagram if red == "instagram" else publicar_facebook
        id_pub = fn(video, texto, dry_run)
        if id_pub and not dry_run:
            anotar_publicado(proyecto, red, id_pub)
            print(f"   ✅ publicado · id {id_pub}")
        elif not id_pub:
            print(f"   ❌ {red} no se publicó")


def escribir_env(hallado: dict, ruta: str = ".env") -> None:
    """Mete en el .env lo que descubrió el diagnóstico, sin duplicar líneas.

    ⚠️ `run_pipeline.sh` hace `source .env`: ese archivo lo lee **bash**. Aquí
    los valores son ids y tokens (solo alfanuméricos y guiones), pero se
    comprueba igual antes de escribir — un valor con espacios o comillas
    rompería el `source` y abortaría el lote entero. Es el mismo susto que dio
    `TITULO_VIDEO` en su día.
    """
    nuevos = {k: v for k, v in hallado.items() if not k.startswith("_")}
    if hallado.get("_token_pagina"):
        nuevos["META_ACCESS_TOKEN"] = hallado["_token_pagina"]
    if not nuevos:
        print("\n⚠️  Nada que escribir.")
        return

    import re as _re
    for k, v in nuevos.items():
        if not _re.fullmatch(r"[A-Za-z0-9_\-]+", str(v)):
            raise SystemExit(f"❌ El valor de {k} tiene caracteres que romperían "
                             f"el `source .env` de run_pipeline.sh. No se escribe nada.")

    p = Path(ruta)
    lineas = p.read_text(encoding="utf-8").splitlines() if p.exists() else []
    for clave, valor in nuevos.items():
        for i, linea in enumerate(lineas):
            if linea.startswith(f"{clave}="):
                lineas[i] = f"{clave}={valor}"
                break
        else:
            lineas.append(f"{clave}={valor}")
    p.write_text("\n".join(lineas) + "\n", encoding="utf-8")
    print(f"\n✅ Escrito en {ruta}: {', '.join(nuevos)}")
    print("   (el .env está en .gitignore, no se commitea)")


#%% ══════════════════════════════════════════════════════════════
#   CLI
# ═══════════════════════════════════════════════════════════════

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--diagnostico", action="store_true",
                   help="Comprueba el token y descubre los IDs. Empieza por aquí")
    p.add_argument("--escribir-env", action="store_true",
                   help="Con --diagnostico: escribe los IDs y el token de página en el .env")
    p.add_argument("--metricas", action="store_true",
                   help="Descarga las métricas de IG y FB y las funde en metricas.csv")
    p.add_argument("--dry-run", action="store_true",
                   help="Con --metricas no escribe; con --publicar sube el video pero NO publica")
    p.add_argument("--publicar", metavar="PROYECTO",
                   help="Publica el reel de publicar/PROYECTO/ en Instagram y Facebook")
    p.add_argument("--solo", nargs="*", choices=["instagram", "facebook"],
                   help="Con --publicar: limitar a una red")
    args = p.parse_args()

    if not any(vars(args).values()):
        p.print_help()
        return

    if args.diagnostico:
        hallado = diagnostico()
        if args.escribir_env:
            escribir_env(hallado)
        return

    if args.metricas:
        guardar_en_metricas(dry_run=args.dry_run)
        return

    if args.publicar:
        publicar(args.publicar, args.solo or ["instagram", "facebook"],
                 dry_run=args.dry_run)


if __name__ == "__main__":
    main()
