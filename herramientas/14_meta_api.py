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
            largo = alargar_token(TOKEN)
            if largo:
                print("   🔄 Alargado a 60 días con META_APP_ID/META_APP_SECRET.")
                print("      Los tokens de página que salgan de este YA no caducan.")
                hallado["_token_largo"] = largo
                globals()["TOKEN"] = largo
            else:
                print("      ⚠️  Este token dura horas, y el de PÁGINA que salga de él\n"
                      "      heredará esa caducidad. Alárgalo antes, de una de las dos formas:\n"
                      "        · pon META_APP_ID y META_APP_SECRET en el .env y repite, o\n"
                      "        · en el Explorador, icono ⓘ junto al token → Abrir en\n"
                      "          herramienta de depuración → «Extender token de acceso».")

    # 2 · Permisos: los que hay contra los que hacen falta
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
    resp = _graph("me/accounts", tolerar_error=True, fields="id,name,access_token")
    if "_error" in resp:
        print(f"\n📘 Páginas de Facebook: no se pudieron leer")
        print(f"   {resp['_error']}")
        paginas = []
    else:
        paginas = resp.get("data", [])
        print(f"\n📘 Páginas de Facebook: {len(paginas)}")
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
    args = p.parse_args()

    if not any(vars(args).values()):
        p.print_help()
        return

    if args.diagnostico:
        hallado = diagnostico()
        if args.escribir_env:
            escribir_env(hallado)


if __name__ == "__main__":
    main()
