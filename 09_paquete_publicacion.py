#%%
"""
╔══════════════════════════════════════════════════════════════╗
║   📦 PAQUETE DE PUBLICACIÓN                                  ║
║   Junta todo lo publicable y reparte los temas en el mes     ║
╚══════════════════════════════════════════════════════════════╝

NO es un paso del pipeline por tema: se corre UNA VEZ después de `run_all.sh`.

El problema que resuelve: lo que produce el pipeline queda repartido en cinco
sitios (videos/, proyectos/X/social_posts/, carousel_slides/, el .srt), así que
subir un lote a un programador como Metricool significa ir a buscar cada pieza
tema por tema. Esto deja una carpeta por tema con todo junto, más un
calendario.csv con las fechas ya asignadas.

Uso:
    python 09_paquete_publicacion.py                       # desde mañana, 1/día
    python 09_paquete_publicacion.py --desde 2026-09-01 --hora 19:00
    python 09_paquete_publicacion.py --cada 2              # 1 cada 2 días
    python 09_paquete_publicacion.py --solo Mundial06 Mundial07

El video se enlaza con hardlink (mismo disco, cero espacio extra); si no se
puede, se copia.
"""

import argparse
import csv
import json
import os
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# ══════════════════════════════════════════════════════════════
# ⚙️  CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════

CONFIG = {
    "dir_videos":    "videos",
    "dir_proyectos": "proyectos",
    "dir_salida":    "publicar",
    "calendario":    "publicar/calendario.csv",

    # Cadencia por defecto. 1 video al día es lo que sostiene la señal de canal;
    # subir el lote entero de golpe hace que compitan entre ellos.
    "hora_defecto":  "19:00",
    "cada_n_dias":   1,

    # Qué archivo de social_posts alimenta cada plataforma
    "textos": {
        "youtube":   "05_youtube.txt",
        "instagram": "03_instagram.txt",
        "facebook":  "04_facebook.txt",
        "twitter":   "01_twitter_hilo.txt",
        "threads":   "02_threads.txt",
    },
}


# ══════════════════════════════════════════════════════════════
# 🔎  DESCUBRIMIENTO
# ══════════════════════════════════════════════════════════════

def descubrir_temas(cfg: dict, solo: list[str] | None = None) -> list[str]:
    """Temas con video final Y respaldo — los únicos publicables."""
    videos = Path(cfg["dir_videos"])
    proyectos = Path(cfg["dir_proyectos"])

    encontrados = []
    for mp4 in sorted(videos.glob("video_*.mp4")):
        nombre = mp4.stem.replace("video_", "", 1)
        if solo and nombre not in solo:
            continue
        if not (proyectos / nombre).is_dir():
            print(f"⚠️  {nombre}: hay video pero no respaldo en proyectos/ — se salta")
            continue
        encontrados.append(nombre)

    return encontrados


def leer_calidad(cfg: dict, tema: str) -> dict | None:
    """Veredicto del control de calidad del guion (lo escribe el paso 01)."""
    ruta = Path(cfg["dir_proyectos"]) / tema / "calidad_guion.json"
    if not ruta.exists():
        return None
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def titulo_youtube(cfg: dict, tema: str) -> str:
    """Extrae el título del 05_youtube.txt para que se vea en el calendario."""
    ruta = Path(cfg["dir_proyectos"]) / tema / "social_posts" / "05_youtube.txt"
    if not ruta.exists():
        return ""

    lineas = ruta.read_text(encoding="utf-8").splitlines()
    for i, linea in enumerate(lineas):
        if linea.startswith("TÍTULO"):
            # El título va en la línea siguiente
            for siguiente in lineas[i + 1:]:
                if siguiente.strip():
                    return siguiente.strip()
    return ""


# ══════════════════════════════════════════════════════════════
# 📦  ARMADO DEL PAQUETE
# ══════════════════════════════════════════════════════════════

def enlazar_o_copiar(origen: Path, destino: Path) -> None:
    """Hardlink si se puede (cero espacio), copia si no."""
    if destino.exists():
        destino.unlink()
    try:
        os.link(origen, destino)
    except OSError:
        shutil.copy2(origen, destino)


def armar_paquete(cfg: dict, tema: str) -> dict:
    """Deja en publicar/<tema>/ todo lo que hace falta para publicar."""
    origen = Path(cfg["dir_proyectos"]) / tema
    destino = Path(cfg["dir_salida"]) / tema
    destino.mkdir(parents=True, exist_ok=True)

    resumen = {"tema": tema, "faltantes": []}

    # 1. Video final
    video = Path(cfg["dir_videos"]) / f"video_{tema}.mp4"
    if video.exists():
        enlazar_o_copiar(video, destino / f"{tema}.mp4")
    else:
        resumen["faltantes"].append("video")

    # 2. Subtítulos (para subir a YouTube y Meta)
    srt = origen / f"{tema}.srt"
    if srt.exists():
        shutil.copy2(srt, destino / f"{tema}.srt")
    else:
        resumen["faltantes"].append("srt")

    # 3. Un .txt por plataforma, con el nombre de la plataforma
    posts = origen / "social_posts"
    for plataforma, archivo in cfg["textos"].items():
        fuente = posts / archivo
        if fuente.exists():
            shutil.copy2(fuente, destino / f"{plataforma}.txt")
        else:
            resumen["faltantes"].append(f"texto {plataforma}")

    # 4. Carrusel de Instagram
    slides = origen / "carousel_slides"
    if slides.is_dir():
        dir_carrusel = destino / "carrusel"
        dir_carrusel.mkdir(exist_ok=True)
        n = 0
        for slide in sorted(slides.glob("slide_*.jpg")):
            shutil.copy2(slide, dir_carrusel / slide.name)
            n += 1
        resumen["slides"] = n
    else:
        resumen["faltantes"].append("carrusel")
        resumen["slides"] = 0

    return resumen


# ══════════════════════════════════════════════════════════════
# 🗓️  CALENDARIO
# ══════════════════════════════════════════════════════════════

def generar_calendario(cfg: dict, temas: list[str], desde: datetime,
                       hora: str, cada: int) -> list[dict]:
    filas = []
    for i, tema in enumerate(temas):
        fecha = desde + timedelta(days=i * cada)
        calidad = leer_calidad(cfg, tema)

        if calidad is None:
            revisar = "sin dato"
        elif calidad.get("aprobado"):
            revisar = "no"
        else:
            revisar = "SÍ — el guion no pasó el control"

        filas.append({
            "fecha": fecha.strftime("%Y-%m-%d"),
            "hora": hora,
            "proyecto": tema,
            "titulo_youtube": titulo_youtube(cfg, tema),
            "video": f"{cfg['dir_salida']}/{tema}/{tema}.mp4",
            "carpeta": f"{cfg['dir_salida']}/{tema}/",
            "nota_guion": (calidad or {}).get("nota", ""),
            "revisar_a_mano": revisar,
        })
    return filas


def escribir_calendario(cfg: dict, filas: list[dict]) -> None:
    ruta = Path(cfg["calendario"])
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with open(ruta, "w", encoding="utf-8", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
        escritor.writeheader()
        escritor.writerows(filas)
    print(f"\n🗓️  Calendario: {ruta}")


# ══════════════════════════════════════════════════════════════
# ▶️  EJECUCIÓN
# ══════════════════════════════════════════════════════════════

def main() -> None:
    p = argparse.ArgumentParser(description="Arma el paquete de publicación del lote")
    p.add_argument("--desde", help="Primera fecha (YYYY-MM-DD). Por defecto: mañana")
    p.add_argument("--hora", default=CONFIG["hora_defecto"], help="Hora de publicación")
    p.add_argument("--cada", type=int, default=CONFIG["cada_n_dias"],
                   help="Días entre publicaciones (1 = diario)")
    p.add_argument("--solo", nargs="*", help="Limitar a estos PROYECTO")
    args = p.parse_args()

    cfg = CONFIG
    desde = (datetime.strptime(args.desde, "%Y-%m-%d") if args.desde
             else datetime.now() + timedelta(days=1))

    temas = descubrir_temas(cfg, args.solo)
    if not temas:
        raise SystemExit("❌ No hay temas publicables (falta el video o el respaldo)")

    print(f"📦 Armando el paquete de {len(temas)} tema(s)...\n")

    revisar, incompletos = [], []
    for tema in temas:
        r = armar_paquete(cfg, tema)
        calidad = leer_calidad(cfg, tema)

        marca = "✅"
        if calidad and not calidad.get("aprobado"):
            marca = "⚠️ "
            revisar.append(tema)
        if r["faltantes"]:
            marca = "❌"
            incompletos.append((tema, r["faltantes"]))

        print(f"  {marca} {tema:14} {r.get('slides', 0)} slides"
              + (f"  · falta: {', '.join(r['faltantes'])}" if r["faltantes"] else ""))

    filas = generar_calendario(cfg, temas, desde, args.hora, args.cada)
    escribir_calendario(cfg, filas)

    print(f"    {filas[0]['fecha']} → {filas[-1]['fecha']} "
          f"a las {args.hora}, 1 cada {args.cada} día(s)")

    # ── Lo que hay que mirar antes de programar ───────────────
    if revisar:
        print(f"\n⚠️  {len(revisar)} guion(es) NO pasaron el control de calidad.")
        print("   Léelos antes de publicar — pueden tener datos no verificables:")
        for tema in revisar:
            c = leer_calidad(cfg, tema) or {}
            print(f"     · {tema} (nota {c.get('nota')}/10)")
            for cita in c.get("afirmaciones_dudosas", [])[:2]:
                print(f'         "{cita[:70]}"')

    if incompletos:
        print(f"\n❌ {len(incompletos)} tema(s) incompletos — NO los programes:")
        for tema, faltan in incompletos:
            print(f"     · {tema}: falta {', '.join(faltan)}")

    if not revisar and not incompletos:
        print("\n🏆 Todo el lote pasó el control y está completo.")

    print(f"\n📂 Todo en '{cfg['dir_salida']}/' — una carpeta por tema.")


if __name__ == "__main__":
    main()
