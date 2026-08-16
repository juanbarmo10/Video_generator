#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🎵  TIKTOK — métricas de los videos por API, para no teclearlas a mano.

    python herramientas/17_tiktok_api.py --autorizar        # imprime el enlace
    python herramientas/17_tiktok_api.py --codigo XXXXX     # canjea el código
    python herramientas/17_tiktok_api.py --diagnostico
    python herramientas/17_tiktok_api.py --metricas

Cierra el último hueco de P-09b: era la única de las cinco redes cuyos números
había que escribir a mano en `metricas_export/manual.csv`.

⚠️ **No hay flujo automático como en YouTube, y no es un descuido.** TikTok exige
que el `redirect_uri` sea **https y esté registrado en la app**, así que el
`run_local_server()` de Google (que levanta un `http://localhost`) no vale aquí.
El código llega a la barra del navegador y se pega con `--codigo`. Es una vez.

⚠️ **Los scopes `user.info.basic` y `video.list` hay que pedirlos en la app.**
Hasta que TikTok los conceda, la autorización funciona pero las llamadas
devuelven `scope_not_authorized`. El alta completa está en README.md, punto 8.
"""

#%% ═══════════════════════════════════════════════════════════════
#   CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════

import argparse
import importlib.util
import json
import os
import secrets
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv

load_dotenv(".env")

CONFIG = {
    # Verificados contra la documentación de TikTok el 15 ago 2026.
    "autorizar":  "https://www.tiktok.com/v2/auth/authorize/",
    "token":      "https://open.tiktokapis.com/v2/oauth/token/",
    "usuario":    "https://open.tiktokapis.com/v2/user/info/",
    "videos":     "https://open.tiktokapis.com/v2/video/list/",

    # `video.list` es el que da las métricas; `user.info.basic` identifica la
    # cuenta y da el `username`, que hace falta para la clave de fusión.
    "scopes": ["user.info.basic", "video.list"],

    # El Video Object completo. Las cuatro métricas de engagement están aquí:
    # el export en CSV no trae ni la duración, y sin ella no hay retención.
    "campos_video": ("id,create_time,share_url,video_description,title,duration,"
                     "like_count,comment_count,share_count,view_count"),
    "campos_usuario": "open_id,display_name,username,follower_count,video_count",

    "token_local": "credenciales/token_tiktok.json",
    "por_pagina": 20,
    "max_videos": 200,
    "timeout": 30,
}

RAIZ = Path(__file__).resolve().parent.parent
CLIENT_KEY = os.getenv("TIKTOK_CLIENT_KEY", "").strip()
CLIENT_SECRET = os.getenv("TIKTOK_CLIENT_SECRET", "").strip()
REDIRECT_URI = os.getenv("TIKTOK_REDIRECT_URI", "").strip()


def _exigir_app() -> None:
    if not (CLIENT_KEY and CLIENT_SECRET and REDIRECT_URI):
        raise SystemExit(
            "❌ Faltan TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET o "
            "TIKTOK_REDIRECT_URI en el .env.\n"
            "   Los tres salen del panel de la app en developers.tiktok.com.\n"
            "   El alta completa está en README.md, punto 8.")


#%% ═══════════════════════════════════════════════════════════════
#   🔑  TOKENS — 24 h el de acceso, 365 días el de refresco
# ═══════════════════════════════════════════════════════════════
#
# ⚠️ Al contrario que el de la página de Facebook, **este caduca siempre**: el
# de acceso a las 24 h. Por eso se guarda el `refresh_token` (365 días) y se
# renueva solo antes de cada uso. Y ⚠️ **el refresco puede devolver un
# `refresh_token` distinto** — hay que guardar el nuevo, o a los 365 días se
# pierde el acceso sin que nada avise.

def _ruta_token() -> Path:
    ruta = RAIZ / CONFIG["token_local"]
    ruta.parent.mkdir(parents=True, exist_ok=True)
    return ruta


def _guardar(datos: dict) -> None:
    ruta = _ruta_token()
    datos["_caduca"] = (datetime.now(timezone.utc)
                        + timedelta(seconds=datos.get("expires_in", 0))).isoformat()
    datos["_refresh_caduca"] = (datetime.now(timezone.utc)
                                + timedelta(seconds=datos.get("refresh_expires_in", 0))).isoformat()
    ruta.write_text(json.dumps(datos, indent=2), encoding="utf-8")
    os.chmod(ruta, 0o600)          # da acceso a las analíticas de la cuenta


def _leer() -> dict | None:
    ruta = _ruta_token()
    if not ruta.exists():
        return None
    return json.loads(ruta.read_text(encoding="utf-8"))


def _canjear(datos: dict) -> dict:
    r = requests.post(CONFIG["token"], data=datos,
                      headers={"Content-Type": "application/x-www-form-urlencoded"},
                      timeout=CONFIG["timeout"])
    respuesta = r.json()
    if respuesta.get("error"):
        raise SystemExit(f"❌ TikTok: {respuesta.get('error')} — "
                         f"{respuesta.get('error_description', '')}")
    return respuesta


def enlace_de_autorizacion() -> str:
    _exigir_app()
    return CONFIG["autorizar"] + "?" + urlencode({
        "client_key": CLIENT_KEY,
        "response_type": "code",
        "scope": ",".join(CONFIG["scopes"]),
        "redirect_uri": REDIRECT_URI,
        "state": secrets.token_urlsafe(16),
    })


def canjear_codigo(codigo: str) -> None:
    _exigir_app()
    # ⚠️ El código llega URL-encoded en la barra del navegador (`%2A` al final).
    # TikTok lo rechaza si no se decodifica: el error dice sólo «invalid_grant».
    from urllib.parse import unquote
    datos = _canjear({
        "client_key": CLIENT_KEY, "client_secret": CLIENT_SECRET,
        "code": unquote(codigo.strip()), "grant_type": "authorization_code",
        "redirect_uri": REDIRECT_URI,
    })
    _guardar(datos)
    print(f"✅ Token guardado en {CONFIG['token_local']} (permisos 600)")
    print(f"   Acceso: {datos.get('expires_in', 0) / 3600:.0f} h · "
          f"Refresco: {datos.get('refresh_expires_in', 0) / 86400:.0f} días")
    print("   Se renueva solo; no hay que repetir esto.")


def token_vivo() -> str:
    """El token de acceso, renovándolo si hace falta."""
    guardado = _leer()
    if not guardado:
        raise SystemExit(
            "❌ No hay token de TikTok. Empieza por:\n"
            "   python herramientas/17_tiktok_api.py --autorizar")

    caduca = datetime.fromisoformat(guardado["_caduca"])
    if caduca - datetime.now(timezone.utc) > timedelta(minutes=5):
        return guardado["access_token"]

    _exigir_app()
    print("   🔄 Renovando el token de acceso…")
    datos = _canjear({
        "client_key": CLIENT_KEY, "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token", "refresh_token": guardado["refresh_token"],
    })
    _guardar(datos)
    return datos["access_token"]


def _cabecera() -> dict:
    return {"Authorization": f"Bearer {token_vivo()}"}


#%% ═══════════════════════════════════════════════════════════════
#   🩺  DIAGNÓSTICO
# ═══════════════════════════════════════════════════════════════

def info_usuario() -> dict:
    r = requests.get(CONFIG["usuario"], headers=_cabecera(),
                     params={"fields": CONFIG["campos_usuario"]},
                     timeout=CONFIG["timeout"]).json()
    if r.get("error", {}).get("code") not in (None, "ok"):
        e = r["error"]
        raise SystemExit(f"❌ {e.get('code')}: {e.get('message')}\n"
                         + ("   Los scopes aún no están concedidos. Panel de la "
                            "app → Manage apps → añade `video.list`.\n"
                            if "scope" in str(e.get("code")) else ""))
    return r.get("data", {}).get("user", {})


def diagnostico() -> None:
    guardado = _leer()
    if not guardado:
        raise SystemExit("❌ No hay token. Corre --autorizar.")
    usuario = info_usuario()
    print(f"🎵 Cuenta: @{usuario.get('username', '?')} "
          f"({usuario.get('display_name', '')})")
    print(f"   {usuario.get('follower_count', '?')} seguidores · "
          f"{usuario.get('video_count', '?')} videos")
    for etiqueta, clave in (("Acceso", "_caduca"), ("Refresco", "_refresh_caduca")):
        cuando = datetime.fromisoformat(guardado[clave])
        dias = (cuando - datetime.now(timezone.utc)).total_seconds() / 86400
        marca = "✅" if dias > 1 else "⚠️ "
        print(f"   {marca} {etiqueta}: caduca el {cuando:%Y-%m-%d %H:%M} "
              f"({dias:.1f} días)")
    print("\n✅ El token responde.")


#%% ═══════════════════════════════════════════════════════════════
#   📊  MÉTRICAS
# ═══════════════════════════════════════════════════════════════

def videos() -> list[dict]:
    """Todos los videos de la cuenta, paginando."""
    todos, cursor = [], None
    while len(todos) < CONFIG["max_videos"]:
        cuerpo = {"max_count": CONFIG["por_pagina"]}
        if cursor:
            cuerpo["cursor"] = cursor
        r = requests.post(CONFIG["videos"], headers=_cabecera(),
                          params={"fields": CONFIG["campos_video"]},
                          json=cuerpo, timeout=CONFIG["timeout"]).json()
        if r.get("error", {}).get("code") not in (None, "ok"):
            e = r["error"]
            print(f"   ❌ {e.get('code')}: {e.get('message')}")
            break
        datos = r.get("data", {})
        todos += datos.get("videos", [])
        cursor = datos.get("cursor")
        if not datos.get("has_more") or not cursor:
            break
    return todos


def _num(v) -> str:
    return "" if v is None else str(v)


def filas_de(videos_api: list[dict], usuario: str, hoy: str) -> list[dict]:
    """Convierte la respuesta de la API en filas de `metricas.csv`.

    ⚠️ **`id_plataforma` es la URL completa, no el `id` numérico**, y esto es lo
    único delicado de todo el archivo. Las 15 filas que ya hay vienen del export
    en CSV, que identifica cada video por su enlace
    (`https://www.tiktok.com/@usuario/video/7641…`). La API devuelve el `id`
    pelado (`7641…`): usarlo tal cual **no fusionaría nada**, crearía 15 filas
    nuevas y cada video quedaría contado dos veces — exactamente el fallo de las
    45 filas fantasma de Facebook, que se descubrió porque la fusión anunció
    filas nuevas donde debían ser 0. Se reconstruye la URL con el mismo formato.

    No se usa `share_url` de la API porque a veces devuelve un enlace corto
    (`tiktok.com/t/…`), que tampoco casaría.
    """
    filas = []
    for v in videos_api:
        publicado = ""
        if v.get("create_time"):
            publicado = datetime.fromtimestamp(v["create_time"],
                                               timezone.utc).date().isoformat()
        texto = (v.get("title") or v.get("video_description") or "").strip()
        filas.append({
            "plataforma": "tiktok",
            "id_plataforma": f"https://www.tiktok.com/@{usuario}/video/{v['id']}",
            "fecha_snapshot": hoy,
            "fecha_publicacion": publicado,
            "titulo": " ".join(texto.split())[:90],
            "duracion_s": _num(v.get("duration")),
            "vistas": _num(v.get("view_count")),
            "me_gusta": _num(v.get("like_count")),
            "comentarios": _num(v.get("comment_count")),
            "compartidos": _num(v.get("share_count")),
        })
    return filas


def _paso10():
    ruta = RAIZ / "herramientas" / "10_metricas.py"
    spec = importlib.util.spec_from_file_location("met10", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def guardar_en_metricas(dry_run: bool = False) -> None:
    """Funde en `metricas.csv` **reusando el paso 10**, igual que 13, 14 y 15."""
    met = _paso10()
    cfg10 = met.CONFIG
    hoy = date.today().isoformat()

    usuario = info_usuario().get("username", "")
    if not usuario:
        raise SystemExit("❌ La API no devolvió el `username`; sin él la clave de "
                         "fusión no casaría con las filas del export.")
    print("🎵 TikTok…")
    filas = filas_de(videos(), usuario, hoy)
    print(f"   {len(filas)} video(s)")
    if not filas:
        raise SystemExit("❌ Nada que guardar.")

    indice = met.indice_proyectos(cfg10)
    nuevos = met.proyectos_del_lote_nuevo(cfg10)
    temas = met.temas_por_proyecto(cfg10)
    for f in filas:
        f["_texto"], f["_id"] = f["titulo"], f["id_plataforma"]

    asignado, _ = met.asignar_uno_a_uno(filas, indice, cfg10["umbral_match"], {})
    for i, f in enumerate(filas):
        proyecto = asignado.get(i, "")
        f["PROYECTO"] = proyecto
        f["lote"] = (cfg10["lote_nuevo"] if proyecto in nuevos
                     else cfg10["lote_baseline"])
        f["tema"] = temas.get(proyecto, "")
        for interno in ("_texto", "_id"):
            f.pop(interno, None)
        met.calcular_retencion(f)

    con_nombre = sum(1 for f in filas if f["PROYECTO"])
    print(f"   {con_nombre} con PROYECTO reconocido · {len(filas) - con_nombre} sin él")

    ruta = Path(cfg10["salida"])
    previas = met.leer_csv(ruta) if ruta.exists() else []
    fundidas, nuevas_n, actualizadas = met.fusionar(previas, filas)
    print(f"📊 {nuevas_n} filas nuevas · {actualizadas} actualizadas · "
          f"{len(fundidas)} en total")
    if nuevas_n and actualizadas == 0:
        print("   ⚠️  Ninguna fila se fundió con las que ya había. Si esperabas\n"
              "      actualizar, mira que `id_plataforma` tenga el MISMO formato\n"
              "      que las del export (la URL completa, no el id numérico).")
    if dry_run:
        print("🧪 --dry-run: no se escribió nada")
        return
    met.escribir(cfg10["salida"], fundidas)
    print(f"✅ Guardado: {cfg10['salida']}")


#%% ═══════════════════════════════════════════════════════════════
#   CLI
# ═══════════════════════════════════════════════════════════════

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--autorizar", action="store_true",
                   help="Imprime el enlace de autorización. Empieza por aquí")
    p.add_argument("--codigo", metavar="CODE",
                   help="Canjea el `code` que quedó en la barra del navegador")
    p.add_argument("--diagnostico", action="store_true",
                   help="Comprueba el token y la cuenta")
    p.add_argument("--metricas", action="store_true",
                   help="Descarga las métricas y las funde en metricas.csv")
    p.add_argument("--dry-run", action="store_true",
                   help="Con --metricas: no escribe nada")
    args = p.parse_args()

    if args.autorizar:
        print("1. Abre este enlace y autoriza con la cuenta del canal:\n")
        print(f"   {enlace_de_autorizacion()}\n")
        print("2. Acabarás en tu redirect_uri con `?code=…` en la barra.")
        print("   Copia SOLO el valor de `code` y pégalo aquí:\n")
        print("   python herramientas/17_tiktok_api.py --codigo <code>")
    elif args.codigo:
        canjear_codigo(args.codigo)
    elif args.diagnostico:
        diagnostico()
    elif args.metricas:
        guardar_en_metricas(dry_run=args.dry_run)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
