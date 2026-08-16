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
    python herramientas/09_paquete_publicacion.py                       # desde mañana, 1/día
    python herramientas/09_paquete_publicacion.py --desde 2026-09-01 --hora 19:00
    python herramientas/09_paquete_publicacion.py --cada 2              # 1 cada 2 días
    python herramientas/09_paquete_publicacion.py --solo Mundial06 Mundial07

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
    #
    # ⚠️ **Las 12:00 no son una preferencia: son la hora de los videos anteriores.**
    # Todo lo que hay en `metricas.csv` se publicó a mediodía, y la hora de
    # publicación mueve el alcance por sí sola. Cambiarla mezclaría en la misma
    # columna dos condiciones distintas y los lotes dejarían de ser comparables —
    # el mismo problema que resolvió `lote` en el paso 10, pero sin una columna
    # que lo delate. Si algún día se prueba otra hora, que sea un lote entero y
    # con su propio nombre de `lote`.
    "hora_defecto":  "12:00",
    "cada_n_dias":   1,

    # EL archivo publicable que queda al lado del video: título, pie del reel,
    # hashtags, descripción larga, tags y comentario a fijar, todo junto.
    "textos": ["descripcion.txt"],

    # Respaldos anteriores a la fusión traían estos dos en vez de descripcion.txt.
    # Se aceptan como alternativa para no marcar como incompletos los lotes viejos.
    "textos_legado": [
        "descripcion_general.txt",     # pie del reel, las 4 redes
        "descripcion_detallada.txt",   # título YouTube + descripción larga + tags
    ],

    # Agrupar por semanas de publicación: publicar/semana_01/<TEMA>/
    # Útil cuando subes el contenido de una semana de una sentada.
    "agrupar_por_semana": False,
    "videos_por_semana": 7,
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
    """Título de YouTube. Sale del json que escribe el paso 02, no de la prosa."""
    ruta = Path(cfg["dir_proyectos"]) / tema / "social_posts" / "metadata.json"
    if not ruta.exists():
        return ""
    try:
        return json.loads(ruta.read_text(encoding="utf-8")).get("titulo", "")
    except json.JSONDecodeError:
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


def carpeta_destino(cfg: dict, tema: str, indice: int) -> Path:
    """publicar/<tema>/  o  publicar/semana_NN/<tema>/ si se agrupa."""
    base = Path(cfg["dir_salida"])
    if cfg.get("agrupar_por_semana"):
        semana = indice // max(1, cfg["videos_por_semana"]) + 1
        base = base / f"semana_{semana:02d}"
    return base / tema


def armar_paquete(cfg: dict, tema: str, indice: int = 0) -> dict:
    """Deja en la carpeta del tema el video y sus 2 textos, uno al lado del otro."""
    origen = Path(cfg["dir_proyectos"]) / tema
    destino = carpeta_destino(cfg, tema, indice)
    destino.mkdir(parents=True, exist_ok=True)

    resumen = {"tema": tema, "faltantes": [], "carpeta": str(destino)}

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

    # 3. El texto publicable, al lado del video. Si el respaldo es anterior a la
    #    fusión en descripcion.txt, se copian los dos archivos viejos.
    posts = origen / "social_posts"

    # Rehacer el paquete no debe dejar residuos del formato anterior: sin esto,
    # los descripcion_general/detallada de una corrida previa seguirían ahí y no
    # se sabría cuál es el bueno.
    for viejo in cfg["textos"] + cfg["textos_legado"]:
        (destino / viejo).unlink(missing_ok=True)

    presentes = [a for a in cfg["textos"] if (posts / a).exists()]
    if not presentes:
        presentes = [a for a in cfg["textos_legado"] if (posts / a).exists()]

    for archivo in presentes:
        shutil.copy2(posts / archivo, destino / archivo)

    if not presentes:
        resumen["faltantes"].append("descripcion")

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
            "video": f"{carpeta_destino(cfg, tema, i)}/{tema}.mp4",
            "carpeta": f"{carpeta_destino(cfg, tema, i)}/",
            "semana": i // max(1, cfg["videos_por_semana"]) + 1,
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
    p.add_argument("--semanas", type=int, metavar="N", nargs="?", const=7,
                   help="Agrupar en carpetas de N videos: publicar/semana_01/... "
                        "(sin valor = 7, una semana)")
    args = p.parse_args()

    cfg = CONFIG
    if args.semanas:
        cfg["agrupar_por_semana"] = True
        cfg["videos_por_semana"] = args.semanas

    desde = (datetime.strptime(args.desde, "%Y-%m-%d") if args.desde
             else datetime.now() + timedelta(days=1))

    temas = descubrir_temas(cfg, args.solo)
    if not temas:
        raise SystemExit("❌ No hay temas publicables (falta el video o el respaldo)")

    print(f"📦 Armando el paquete de {len(temas)} tema(s)...\n")

    revisar, incompletos = [], []
    for i, tema in enumerate(temas):
        r = armar_paquete(cfg, tema, i)
        calidad = leer_calidad(cfg, tema)

        marca = "✅"
        if calidad and not calidad.get("aprobado"):
            marca = "⚠️ "
            revisar.append(tema)
        if r["faltantes"]:
            marca = "❌"
            incompletos.append((tema, r["faltantes"]))

        print(f"  {marca} {r['carpeta']:34} {r.get('slides', 0)} slides"
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
