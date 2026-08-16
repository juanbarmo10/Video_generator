#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🧵  THREADS — hilos cortos a partir de un tema ya publicado.

    python herramientas/15_threads_api.py --diagnostico
    python herramientas/15_threads_api.py --hilo Historia01 --dry-run
    python herramientas/15_threads_api.py --hilo Historia01

Publica un hilo de 3 mensajes encadenados con 1-2 fotos reales del tema. La razón
de existir es de uso, no de código: publicando a mano, Threads daba bastante más
alcance que el resto y arrastraba a Instagram.

⚠️ **Threads es una API aparte de verdad, no un añadido de la de Meta.** Otro
host (`graph.threads.net`), otro flujo de autorización y **otro token** — el de
la página de Facebook no sirve aquí. Por eso vive en su propio archivo.

⚠️ **Las imágenes solo entran por URL pública**, igual que en el carrusel de
Instagram. El andamio es el mismo y se reusa de `14_meta_api.py`: subir la foto a
la página de Facebook con `published=false` y usar la URL de su CDN. Es la única
dependencia entre los dos archivos, y va en una sola función.
"""

#%% ═══════════════════════════════════════════════════════════════
#   CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════

import argparse
import importlib.util
import json
import os
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(".env")

CONFIG = {
    # ⚠️ Ni el host ni la versión son los de Meta. `graph.facebook.com` responde
    # a estas rutas con «Unsupported get request», que no dice nada del host.
    "graph": "https://graph.threads.net",
    "api": "v1.0",

    "permisos_necesarios": [
        "threads_basic",
        "threads_content_publish",
        "threads_manage_insights",
    ],

    # Threads corta a 500 caracteres por mensaje. Se pide menos para que el
    # modelo no tenga que apretar y salga un texto atropellado.
    "max_chars": 480,
    "mensajes": 3,
    "imagenes": 2,

    "modelo": "gpt-4.1",
    "timeout": 30,
    # Cuántos días antes de caducar se renueva el token. Con margen de sobra:
    # `th_refresh_token` solo funciona mientras el token siga vivo.
    "avisar_dias_antes": 10,
    # Cada mensaje del hilo hay que publicarlo antes de contestarle, y Threads
    # tarda un momento en darlo por bueno.
    "espera_publicacion": 3,
}

RAIZ = Path(__file__).resolve().parent.parent
REGISTRO_PUBLICADO = "publicar/publicado.csv"

TOKEN = os.getenv("THREADS_ACCESS_TOKEN", "").strip()
USER_ID = os.getenv("THREADS_USER_ID", "").strip()


def _exigir_token() -> None:
    if not (TOKEN and USER_ID):
        raise SystemExit(
            "❌ Faltan THREADS_ACCESS_TOKEN o THREADS_USER_ID en el .env.\n"
            "   Threads NO reusa el token de la página de Facebook: es otra API\n"
            "   con su propia autorización. El montaje está en README.md."
        )


def _post(ruta: str, **datos) -> dict:
    datos["access_token"] = TOKEN
    r = requests.post(f"{CONFIG['graph']}/{CONFIG['api']}/{ruta.lstrip('/')}",
                      data=datos, timeout=CONFIG["timeout"])
    return r.json()


def _get(ruta: str, **params) -> dict:
    params["access_token"] = TOKEN
    r = requests.get(f"{CONFIG['graph']}/{CONFIG['api']}/{ruta.lstrip('/')}",
                     params=params, timeout=CONFIG["timeout"])
    return r.json()


#%% ═══════════════════════════════════════════════════════════════
#   🩺  DIAGNÓSTICO
# ═══════════════════════════════════════════════════════════════

def alargar_token(token: str) -> tuple[str, str] | None:
    """Cambia el token corto del Explorador por uno de 60 días.

    ⚠️ **Es la misma trampa que en Meta, con otro nombre.** El token que da el
    Explorador dura ~1 hora; aquí no hay token de página del que heredar
    permanencia, así que 60 días es el máximo y **hay que renovarlo antes de que
    caduque** con `th_refresh_token` (`refrescar_token()`). Si caduca del todo,
    toca repetir el alta entera.

    Devuelve `(token, fecha_de_caducidad)`.
    """
    secreto = os.getenv("META_APP_SECRET", "").strip()
    if not secreto:
        return None
    return _canjear({"grant_type": "th_exchange_token",
                     "client_secret": secreto, "access_token": token})


def refrescar_token(token: str) -> tuple[str, str] | None:
    """Estira 60 días más un token largo. Necesita que tenga >24 h de vida."""
    return _canjear({"grant_type": "th_refresh_token", "access_token": token})


def _canjear(params: dict) -> tuple[str, str] | None:
    ruta = "refresh_access_token" if "refresh" in params["grant_type"] else "access_token"
    r = requests.get(f"{CONFIG['graph']}/{ruta}", params=params,
                     timeout=CONFIG["timeout"]).json()
    if "error" in r:
        print(f"   ⚠️  No se pudo alargar: {r['error'].get('message', '')[:120]}")
        return None
    caduca = (date.today() + timedelta(seconds=r.get("expires_in", 0))).isoformat()
    return r["access_token"], caduca


def _es_token_de_facebook(token: str) -> bool:
    """¿Este token es de la API de Meta en vez de la de Threads?

    ⚠️ Es el error fácil de cometer y el peor de diagnosticar: el Explorador de
    la API Graph sirve para las dos, y si no cambias el host de `facebook.com` a
    `threads.net` te da un token de Facebook perfectamente válido… que
    `graph.threads.net` rechaza con **«Invalid OAuth access token - Cannot parse
    access token»**, un mensaje que no menciona ni el host ni el tipo de token.
    Pasó el 15 ago.
    """
    app = os.getenv("META_APP_ID", "").strip()
    secreto = os.getenv("META_APP_SECRET", "").strip()
    if not (app and secreto):
        return False
    try:
        d = requests.get("https://graph.facebook.com/v21.0/debug_token",
                         params={"input_token": token,
                                 "access_token": f"{app}|{secreto}"},
                         timeout=CONFIG["timeout"]).json()
    except requests.RequestException:
        return False
    return bool(d.get("data", {}).get("is_valid"))


def diagnostico(escribir: bool = False) -> None:
    _exigir_token()
    yo = _get("me", fields="id,username,threads_profile_picture_url")
    if "error" in yo:
        mensaje = yo["error"].get("message", "")
        if "parse" in mensaje.lower() and _es_token_de_facebook(TOKEN):
            raise SystemExit(
                "❌ THREADS_ACCESS_TOKEN tiene un token de **Facebook**, no de Threads.\n"
                "   Es válido —responde en graph.facebook.com— pero graph.threads.net\n"
                "   no sabe leerlo, y su error no lo dice.\n\n"
                "   En el Explorador de la API Graph, arriba a la izquierda hay un\n"
                "   desplegable de host con `facebook.com` / `instagram.com` /\n"
                "   `threads.net`. **Ponlo en `threads.net`** y genera el token otra\n"
                "   vez: cambian los permisos a `threads_*` y el token empieza por `TH`,\n"
                "   no por `EAA`.")
        raise SystemExit(f"❌ {mensaje}")
    print(f"🧵 Cuenta: @{yo.get('username', '?')}  (id {yo.get('id')})")

    # ⚠️ El id de la cuenta de Threads **no es** el de Instagram ni el de la app,
    # y se teclea a mano: es fácil poner otro sin enterarse. La API no protesta
    # —el token manda— así que se compara aquí. Pasó el 15 ago: el `.env` traía
    # el id de la app y las lecturas fallaban con «Object does not exist».
    real = yo.get("id", "")
    if real and real != USER_ID:
        print(f"   ⚠️  THREADS_USER_ID dice {USER_ID}, pero el token es de {real}.")
        if escribir:
            _meta().escribir_env({"THREADS_USER_ID": real})
            globals()["USER_ID"] = real
        else:
            print("      Corrígelo, o repite con --escribir-env.")

    # ⚠️ El token del Explorador dura ~1 hora. Aquí no hay token de página del
    # que heredar permanencia como en Facebook: 60 días es el techo, y hay que
    # renovarlo antes de que caduque o se repite el alta entera.
    caduca = os.getenv("THREADS_TOKEN_CADUCA", "").strip()
    dias = (date.fromisoformat(caduca) - date.today()).days if caduca else -1
    if dias > CONFIG["avisar_dias_antes"]:
        print(f"   🔑 Token largo, caduca el {caduca} (en {dias} días)")
    elif escribir:
        nuevo = (refrescar_token(TOKEN) if dias >= 0 else alargar_token(TOKEN))
        if nuevo:
            token, hasta = nuevo
            _meta().escribir_env({"THREADS_ACCESS_TOKEN": token,
                                  "THREADS_TOKEN_CADUCA": hasta})
            globals()["TOKEN"] = token
            print(f"   🔄 Token alargado hasta el {hasta} (60 días)")
    else:
        print(f"   ⚠️  {'Caduca en %d días' % dias if dias >= 0 else 'Token corto (~1 h)'}. "
              f"Repite con --escribir-env para alargarlo a 60.")

    hilos = _get(f"{USER_ID}/threads", fields="id,text,timestamp", limit=3)
    if "error" in hilos:
        print(f"   ⚠️  No se pudieron leer los hilos: {hilos['error'].get('message')}")
    else:
        print(f"   Últimos {len(hilos.get('data', []))} hilos:")
        for h in hilos.get("data", []):
            print(f"      · {h.get('timestamp', '')[:10]}  {(h.get('text') or '')[:60]}")
    print("\n✅ El token responde.")


#%% ═══════════════════════════════════════════════════════════════
#   ✍️   ESCRIBIR EL HILO
# ═══════════════════════════════════════════════════════════════

SYSTEM = """Escribes hilos para Threads de una cuenta de curiosidades históricas.
Rigor periodístico: solo afirmaciones verificables, sin adornos ni especulación.
Tono directo y conversacional, en español neutro. Nada de emojis decorativos."""

PROMPT = """A partir de este material, escribe un hilo de {n} mensajes.

GUION DEL VIDEO
{guion}

INVESTIGACIÓN DE APOYO
{investigacion}

REGLAS
- Mensaje 1: el gancho. Abre la pregunta SIN responderla. Máximo 2 frases.
- Mensajes intermedios: el dato concreto, lo que lo hace sorprendente.
- Último mensaje: cierra la respuesta y termina con una pregunta al lector.
- Cada mensaje, máximo {max_chars} caracteres. Ninguno los cuenta por ti: sé breve.
- NO uses hashtags. NO menciones otras redes ni digas "mira el video".
- No repitas literalmente frases del guion: es el mismo hecho contado en texto.

Devuelve SOLO un JSON: {{"mensajes": ["...", "...", "..."]}}"""


def material_de(proyecto: str) -> tuple[str, str]:
    """El guion aprobado y la investigación de un tema ya producido.

    ⚠️ El guion se lee de `calidad_guion.json`, no de `script.txt`: ese vive en la
    raíz y lo pisa el tema siguiente. Es la misma razón por la que el paso 01 lo
    guarda ahí.
    """
    base = RAIZ / "proyectos" / proyecto
    guion = ""
    calidad = base / "calidad_guion.json"
    if calidad.exists():
        guion = json.loads(calidad.read_text(encoding="utf-8")).get("guion", "")
    investigacion = ""
    inv = base / "social_posts" / "00_investigacion.txt"
    if inv.exists():
        investigacion = inv.read_text(encoding="utf-8")[:3000]
    return guion, investigacion


def escribir_hilo(proyecto: str) -> list[str]:
    """Redacta los mensajes con GPT. Devuelve [] si no hay material.

    ⚠️ **No llama a `registrar_openai()` a propósito.** Ese contador escribe
    `.costo_actual.json`, que es el estado del tema EN CURSO del pipeline: esta
    herramienta corre una vez por semana y podría hacerlo con un lote en marcha,
    sumándole a otro tema un gasto que no es suyo. El coste real aquí es de
    ~$0.002 por hilo.
    """
    guion, investigacion = material_de(proyecto)
    if not guion:
        print(f"   ❌ {proyecto} no tiene guion en proyectos/{proyecto}/calidad_guion.json")
        return []

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    r = client.chat.completions.create(
        model=CONFIG["modelo"],
        messages=[{"role": "system", "content": SYSTEM},
                  {"role": "user", "content": PROMPT.format(
                      n=CONFIG["mensajes"], guion=guion,
                      investigacion=investigacion or "(sin material extra)",
                      max_chars=CONFIG["max_chars"])}],
        response_format={"type": "json_object"},
        temperature=0.7,
    )
    try:
        mensajes = json.loads(r.choices[0].message.content).get("mensajes", [])
    except (json.JSONDecodeError, AttributeError):
        print("   ❌ El modelo no devolvió JSON usable")
        return []

    # ⚠️ El recorte lo garantiza Python, no el prompt: a un LLM no se le pide que
    # cuente caracteres. Es la misma regla que en los pasos 01 y 02.
    return [recortar(m) for m in mensajes if m and m.strip()]


def recortar(texto: str, limite: int = None) -> str:
    """Recorta al límite de Threads sin partir una palabra por la mitad."""
    limite = limite or CONFIG["max_chars"]
    texto = texto.strip()
    if len(texto) <= limite:
        return texto
    corte = texto[:limite].rsplit(" ", 1)[0]
    return corte.rstrip(" ,;:") + "…"


def fotos_de(proyecto: str, cuantas: int = None) -> list[Path]:
    """Las fotos REALES del tema (Wikimedia/DuckDuckGo), no las ilustradas.

    Son las que dan credibilidad al hilo: en texto plano una ilustración de IA
    no aporta nada, una foto del objeto o del lugar sí.
    """
    cuantas = cuantas or CONFIG["imagenes"]
    base = RAIZ / "proyectos" / proyecto / "source_images"
    if not base.is_dir():
        return []
    fotos = sorted(p for p in base.iterdir()
                   if p.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"))
    return fotos[:cuantas]


#%% ═══════════════════════════════════════════════════════════════
#   📤  PUBLICAR
# ═══════════════════════════════════════════════════════════════

def _meta():
    """`14_meta_api.py`, solo para el andamio de fotos (empieza por dígito)."""
    ruta = RAIZ / "herramientas" / "14_meta_api.py"
    spec = importlib.util.spec_from_file_location(ruta.stem, ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _publicar_mensaje(texto: str, image_url: str = "",
                      responde_a: str = "") -> str | None:
    """Un mensaje del hilo: contenedor y publicación, como en Instagram."""
    datos = {"text": texto,
             "media_type": "IMAGE" if image_url else "TEXT"}
    if image_url:
        datos["image_url"] = image_url
    if responde_a:
        datos["reply_to_id"] = responde_a

    r = _post(f"{USER_ID}/threads", **datos)
    if "error" in r:
        print(f"   ❌ No se creó el contenedor: {r['error'].get('message')}")
        return None

    time.sleep(CONFIG["espera_publicacion"])
    pub = _post(f"{USER_ID}/threads_publish", creation_id=r["id"])
    if "error" in pub:
        print(f"   ❌ No se publicó: {pub['error'].get('message')}")
        return None
    return pub.get("id")


def publicar_hilo(mensajes: list[str], fotos: list[Path],
                  dry_run: bool) -> str | None:
    """Publica los mensajes encadenados. Devuelve el id del primero.

    ⚠️ **Los mensajes van en serie, no en paralelo**: cada uno responde al
    anterior y necesita su id ya publicado. Si uno falla a mitad, los anteriores
    quedan publicados — se avisa en vez de fingir que no pasó nada, porque un
    hilo cortado es visible y hay que rematarlo a mano.
    """
    _exigir_token()
    meta = _meta()

    staging, urls = [], []
    try:
        for foto in fotos:
            subida = meta.subir_foto_staging(foto)
            if subida:
                staging.append(subida[0])
                urls.append(subida[1])
        if fotos and not urls:
            print("   ⚠️  Ninguna foto se pudo preparar; el hilo sale sin imágenes")

        for i, texto in enumerate(mensajes):
            url = urls[i] if i < len(urls) else ""
            print(f"   {i + 1}. {'🖼️ ' if url else '  '} {texto[:70]}"
                  f"{'…' if len(texto) > 70 else ''}  ({len(texto)} car.)")

        if dry_run:
            print(f"   🧪 --dry-run: {len(mensajes)} mensajes y {len(urls)} "
                  f"imagen(es) preparados, NO publicado")
            return "dry-run"

        raiz_id, anterior = None, ""
        for i, texto in enumerate(mensajes):
            url = urls[i] if i < len(urls) else ""
            pub = _publicar_mensaje(texto, url, anterior)
            if not pub:
                if raiz_id:
                    print(f"   ⚠️  El hilo quedó a medias: {i} de {len(mensajes)} "
                          f"mensajes publicados. Remátalo a mano.")
                return raiz_id
            raiz_id = raiz_id or pub
            anterior = pub
        return raiz_id
    finally:
        for pid in staging:
            meta.borrar_foto(pid)


def publicar_hilo_de(proyecto: str, dry_run: bool = False) -> str | None:
    """De un `PROYECTO` a un hilo publicado. Es lo que llama `16_agenda.py`."""
    _exigir_token()
    meta = _meta()
    previo = meta.ya_publicado(proyecto, "threads")
    if previo and not dry_run:
        print(f"⏭️  {proyecto} ya salió en Threads el {previo['fecha']} "
              f"(id {previo['id_publicacion']}). Se salta.")
        return None

    print(f"🧵 {proyecto}" + ("   🧪 DRY-RUN" if dry_run else ""))
    mensajes = escribir_hilo(proyecto)
    if not mensajes:
        return None
    fotos = fotos_de(proyecto)
    print(f"   {len(mensajes)} mensajes · {len(fotos)} foto(s) real(es)\n")

    id_pub = publicar_hilo(mensajes, fotos, dry_run)
    if id_pub and not dry_run:
        meta.anotar_publicado(proyecto, "threads", id_pub)
        print(f"   ✅ publicado · id {id_pub}")
    return id_pub


#%% ═══════════════════════════════════════════════════════════════
#   CLI
# ═══════════════════════════════════════════════════════════════

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--diagnostico", action="store_true",
                   help="Comprueba el token de Threads. Empieza por aquí")
    p.add_argument("--escribir-env", action="store_true",
                   help="Con --diagnostico: corrige THREADS_USER_ID en el .env")
    p.add_argument("--hilo", metavar="PROYECTO",
                   help="Escribe y publica el hilo de ese tema")
    p.add_argument("--solo-texto", action="store_true",
                   help="Con --hilo: escribe el hilo y lo imprime, sin tocar la API")
    p.add_argument("--dry-run", action="store_true",
                   help="Prepara todo pero no publica")
    args = p.parse_args()

    if args.diagnostico:
        diagnostico(escribir=args.escribir_env)
    elif args.hilo and args.solo_texto:
        # ⚠️ No pasa por `_exigir_token()`: es el único modo que sirve para
        # afinar el prompt antes de tener la cuenta de Threads montada.
        for i, m in enumerate(escribir_hilo(args.hilo), 1):
            print(f"\n{i}. ({len(m)} car.)\n{m}")
    elif args.hilo:
        publicar_hilo_de(args.hilo, dry_run=args.dry_run)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
