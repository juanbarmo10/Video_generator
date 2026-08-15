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


def _graph(ruta: str, **params) -> dict:
    """GET contra la Graph API con el token puesto y los errores legibles.

    ⚠️ Meta devuelve los errores con HTTP 400 y el detalle en el cuerpo, así que
    `raise_for_status()` a secas pierde justo lo que dice qué falta.
    """
    params["access_token"] = TOKEN
    r = requests.get(f"{CONFIG['graph']}/{CONFIG['api']}/{ruta.lstrip('/')}",
                     params=params, timeout=CONFIG["timeout"])
    datos = r.json()
    if "error" in datos:
        e = datos["error"]
        raise SystemExit(
            f"❌ Meta respondió con un error en /{ruta}:\n"
            f"   {e.get('message')}\n"
            f"   tipo {e.get('type')} · código {e.get('code')}"
            + (f" · subcódigo {e['error_subcode']}" if e.get("error_subcode") else "")
        )
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
    info = _graph("debug_token", input_token=TOKEN).get("data", {})
    tipo = info.get("type", "?")
    expira = info.get("expires_at", 0)
    print(f"🔑 Token de tipo {tipo}, app {info.get('app_id', '?')}")
    if expira == 0:
        print("   ✅ No caduca")
    else:
        from datetime import datetime, timezone
        cuando = datetime.fromtimestamp(expira, timezone.utc)
        dias = (cuando - datetime.now(timezone.utc)).days
        marca = "✅" if dias > 30 else ("⚠️ " if dias > 0 else "❌")
        print(f"   {marca} Caduca el {cuando:%Y-%m-%d} (en {dias} días)")
        if dias < 30:
            print("      Cámbialo por un token de PÁGINA, que no caduca: sale en\n"
                  "      la sección de páginas de abajo.")

    # 2 · Permisos: los que hay contra los que hacen falta
    concedidos = {p["permission"] for p in _graph("me/permissions").get("data", [])
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
    paginas = _graph("me/accounts", fields="id,name,access_token").get("data", [])
    print(f"\n📘 Páginas de Facebook: {len(paginas)}")
    for pg in paginas:
        print(f"   · {pg['name']}  →  FACEBOOK_PAGE_ID={pg['id']}")
    if len(paginas) == 1:
        hallado["FACEBOOK_PAGE_ID"] = paginas[0]["id"]
        hallado["_token_pagina"] = paginas[0].get("access_token", "")
    elif not paginas:
        print("   ❌ Ninguna. El token no tiene `pages_show_list`, o la cuenta no\n"
              "      administra ninguna página.")

    # 4 · Cuenta de Instagram vinculada a cada página
    print(f"\n📸 Cuentas de Instagram:")
    encontradas = []
    for pg in paginas:
        d = _graph(f"{pg['id']}", fields="instagram_business_account{id,username}")
        ig = d.get("instagram_business_account")
        if ig:
            encontradas.append(ig)
            print(f"   · @{ig.get('username', '?')} en «{pg['name']}»  →  "
                  f"INSTAGRAM_ACCOUNT_ID={ig['id']}")
    if not encontradas:
        print("   ❌ Ninguna vinculada.\n"
              "      La cuenta de Instagram tiene que ser **Empresa o Creador** y estar\n"
              "      vinculada a la página de Facebook. Con cuenta personal no hay API.")
    elif len(encontradas) == 1:
        hallado["INSTAGRAM_ACCOUNT_ID"] = encontradas[0]["id"]

    # 5 · Qué escribir en el .env
    if hallado:
        print(f"\n📝 Añade esto al .env:")
        for k in ("FACEBOOK_PAGE_ID", "INSTAGRAM_ACCOUNT_ID"):
            if k in hallado:
                print(f"   {k}={hallado[k]}")
        if hallado.get("_token_pagina") and expira:
            print(f"\n   Y cambia META_ACCESS_TOKEN por el token de PÁGINA, que no\n"
                  f"   caduca (los tokens de usuario sí, a los 60 días):")
            print(f"   META_ACCESS_TOKEN={hallado['_token_pagina']}")

    listo = not faltan and "FACEBOOK_PAGE_ID" in hallado and "INSTAGRAM_ACCOUNT_ID" in hallado
    print(f"\n{'✅ Todo listo.' if listo else '⚠️  Falta algo de lo de arriba.'}")
    return hallado


#%% ══════════════════════════════════════════════════════════════
#   CLI
# ═══════════════════════════════════════════════════════════════

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--diagnostico", action="store_true",
                   help="Comprueba el token y descubre los IDs. Empieza por aquí")
    args = p.parse_args()

    if not any(vars(args).values()):
        p.print_help()
        return

    if args.diagnostico:
        diagnostico()


if __name__ == "__main__":
    main()
