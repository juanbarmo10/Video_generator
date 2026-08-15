#%%
"""
╔══════════════════════════════════════════════════════════════╗
║   📊 CONSOLIDADOR DE MÉTRICAS                                ║
║   Une los CSV que exportas de cada plataforma en metricas.csv ║
╚══════════════════════════════════════════════════════════════╝

NO es un paso del pipeline. Se corre cuando quieras actualizar los números.

El problema que resuelve: las cuatro plataformas exportan su propio CSV, con
sus propios nombres de columna y sin ninguna referencia a tu `PROYECTO`. Copiar
eso a mano son 15 minutos por semana que crecen con cada video.

Uso:
    1. Exporta de cada plataforma (ver METRICAS.md) y deja los CSV en
       `metricas_export/`, con el nombre empezando por la plataforma:
           metricas_export/youtube_agosto.csv
           metricas_export/tiktok_agosto.csv
           metricas_export/instagram_agosto.csv
           metricas_export/facebook_agosto.csv
    2. python 10_metricas.py

    python 10_metricas.py --dry-run     # enseña qué haría, sin escribir
    python 10_metricas.py --umbral 0.5  # afloja el emparejado por título

Cómo empareja: las plataformas no conocen tu `PROYECTO`, así que se compara el
título/descripción de cada fila exportada contra el `titulo` de
`proyectos/<P>/social_posts/metadata.json` y contra el pie del reel. Lo que no
llegue al umbral se reporta para que lo mires, NO se adivina.

⚠️ Los nombres de columna cambian con el idioma de la cuenta y con cada rediseño
de las plataformas. Por eso el mapeo es por ALIAS (abajo) y el script imprime
qué columnas no supo reconocer: si ves una que te interesa, añádela a ALIAS y
vuelve a correr. No hace falta tocar nada más.
"""

import argparse
import csv
import glob
import json
import os
import re
import unicodedata
from datetime import date
from difflib import SequenceMatcher
from pathlib import Path

# ══════════════════════════════════════════════════════════════
# ⚙️  CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════

CONFIG = {
    "dir_export":    "metricas_export",
    "dir_proyectos": "proyectos",
    "salida":        "metricas.csv",

    # Similitud mínima título-exportación para dar por bueno un emparejado.
    # 0.60 es conservador: prefiere reportar dudas a inventarse filas.
    "umbral_match":  0.60,

    "plataformas":   ["youtube", "tiktok", "instagram", "facebook"],
}

# Columnas de metricas.csv. `fecha_snapshot` es la clave del asunto: un export
# normal trae vistas ACUMULADAS, no "vistas a 24h". Guardando una foto por fecha,
# los deltas (24h, 7d) salen de comparar dos filas en vez de pedírselos a nadie.
COLUMNAS = [
    "PROYECTO", "tema", "plataforma", "fecha_snapshot", "fecha_publicacion",
    "vistas", "alcance", "retencion_pct", "duracion_media_s",
    "me_gusta", "comentarios", "compartidos", "guardados",
    # No sale de ningún export: se lee de la curva de retención de YouTube Studio.
    # Es la métrica que dice si el gancho funciona, así que va a mano.
    "pct_llega_3s",
    "notas",
]

# Alias de columnas: {campo_nuestro: [posibles nombres en el export]}
# En minúsculas y sin acentos — la comparación normaliza ambos lados.
ALIAS = {
    # ⚠️ El ORDEN importa: gana el alias más específico, no la primera columna del
    # archivo. Sin esto, el export de YouTube emparejaba "Contenido" —que es el ID
    # del video, no el título— y no encajaba ni una fila.
    "titulo_export": [
        "titulo del video", "video title", "titulo", "title",
        "texto de la publicacion", "post text", "descripcion", "description",
        "caption", "publicacion", "post",
    ],
    "fecha_publicacion": [
        "fecha de publicacion del video", "video publish time", "fecha de publicacion",
        "publish time", "post time", "fecha de creacion", "hora de publicacion",
        "time posted", "fecha", "date",
    ],
    "vistas": [
        "vistas", "views", "video views", "reproducciones", "plays",
        "reproducciones de video", "visualizaciones", "impresiones de video",
    ],
    "alcance": ["alcance", "reach", "cuentas alcanzadas", "accounts reached"],
    "retencion_pct": [
        "porcentaje promedio reproducido", "porcentaje promedio reproducido (%)",
        "average percentage viewed", "average percentage viewed (%)",
        "porcentaje visto", "retencion", "retention",
    ],
    "duracion_media_s": [
        "duracion media de la reproduccion", "average view duration",
        "tiempo medio de reproduccion", "average time watched",
        "average watch time", "tiempo promedio de visualizacion",
    ],
    "me_gusta": ["me gusta", "likes", "reacciones", "reactions"],
    "comentarios": ["comentarios", "comments", "comentarios anadidos", "comments added"],
    "compartidos": ["veces compartido", "compartidos", "shares", "veces que se compartio"],
    "guardados": ["guardados", "saves", "saved", "elementos guardados"],
}


# ══════════════════════════════════════════════════════════════
# 🔤  NORMALIZACIÓN Y EMPAREJADO
# ══════════════════════════════════════════════════════════════

def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos y sin puntuación: para comparar nombres de columna."""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", " ", texto.lower()).strip()


def normalizar_titulo(texto: str) -> str:
    """Como normalizar(), pero además colapsa espacios y recorta.

    Los títulos se editan al subirlos (emojis, hashtags al final, cortes por
    longitud), así que se compara la versión desnuda de ambos lados.
    """
    return " ".join(normalizar(texto).split())[:120]


def similitud(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, normalizar_titulo(a), normalizar_titulo(b)).ratio()


def indice_proyectos(cfg: dict) -> dict:
    """{PROYECTO: {"tema":…, "textos":[título, pie del reel]}} para emparejar."""
    indice = {}
    for meta in sorted(Path(cfg["dir_proyectos"]).glob("*/social_posts/metadata.json")):
        proyecto = meta.parts[1]
        textos = []
        try:
            datos = json.loads(meta.read_text(encoding="utf-8"))
            if datos.get("titulo"):
                textos.append(datos["titulo"])
        except json.JSONDecodeError:
            pass

        # El pie del reel: en TikTok/IG/FB no hay título, solo el texto del post.
        desc = meta.parent / "descripcion.txt"
        if desc.exists():
            cuerpo = desc.read_text(encoding="utf-8")
            m = re.search(r"DESCRIPCIÓN GENERAL.*?─+\n(.*?)\n\n", cuerpo, re.S)
            if m:
                textos.append(m.group(1))

        if textos:
            indice[proyecto] = {"textos": textos}
    return indice


def emparejar(texto: str, indice: dict, umbral: float) -> tuple[str | None, float]:
    """Devuelve (PROYECTO, score) del mejor candidato, o (None, score) si no llega."""
    mejor, mejor_score = None, 0.0
    for proyecto, datos in indice.items():
        score = max(similitud(texto, t) for t in datos["textos"])
        if score > mejor_score:
            mejor, mejor_score = proyecto, score
    return (mejor, mejor_score) if mejor_score >= umbral else (None, mejor_score)


# ══════════════════════════════════════════════════════════════
# 📥  LECTURA DE LOS EXPORTS
# ══════════════════════════════════════════════════════════════

def detectar_plataforma(ruta: Path, cfg: dict) -> str | None:
    nombre = normalizar(ruta.stem)
    for p in cfg["plataformas"]:
        if nombre.startswith(p) or p in nombre.split():
            return p
    return None


def mapear_columnas(cabecera: list[str]) -> tuple[dict, list[str]]:
    """{campo_nuestro: nombre_real} + lista de columnas que no se reconocieron.

    Para cada campo se recorren sus alias EN ORDEN DE PREFERENCIA y se coge la
    primera columna que case, en vez de la primera columna del archivo que case
    con cualquier alias. Un alias exacto siempre gana a uno por prefijo.
    """
    mapa, usadas = {}, set()
    normalizadas = {col: normalizar(col) for col in cabecera}

    for campo, alias in ALIAS.items():
        for patron in alias:                       # ← el orden del alias manda
            exacta = [c for c, n in normalizadas.items()
                      if c not in usadas and n == patron]
            prefijo = [c for c, n in normalizadas.items()
                       if c not in usadas and n.startswith(patron)]
            elegida = next(iter(exacta + prefijo), None)
            if elegida:
                mapa[campo] = elegida
                usadas.add(elegida)
                break

    return mapa, [c for c in cabecera if c not in usadas]


def limpiar_numero(valor: str) -> str:
    """'1.234' / '1,234' / '12,5 %' / '0:07' → número plano. '' si no se puede."""
    if valor is None:
        return ""
    v = str(valor).strip().replace("%", "").strip()
    if not v:
        return ""

    if ":" in v:                                   # duración mm:ss o h:mm:ss
        partes = v.split(":")
        try:
            segundos = 0
            for p in partes:
                segundos = segundos * 60 + int(p)
            return str(segundos)
        except ValueError:
            return ""

    v = re.sub(r"[^\d,.\-]", "", v)
    if not v:
        return ""

    # Con los dos separadores, el ÚLTIMO en aparecer es el decimal: 1.234,56 y
    # 1,234.56 son el mismo número escrito en dos idiomas.
    if "," in v and "." in v:
        if v.rfind(",") > v.rfind("."):
            return v.replace(".", "").replace(",", ".")
        return v.replace(",", "")

    # Con uno solo hay que decidir si es miles o decimal. La regla: exactamente
    # 3 dígitos detrás = separador de miles ("1.284" son 1284 vistas, no 1,284),
    # cualquier otra cantidad = decimal ("62,5" es 62.5 %).
    for sep in (",", "."):
        if v.count(sep) > 1:                       # 1.234.567 → solo puede ser miles
            return v.replace(sep, "")
        if v.count(sep) == 1:
            entero, resto = v.split(sep)
            return entero + resto if len(resto) == 3 else v.replace(sep, ".")

    return v


def leer_export(ruta: Path, plataforma: str, indice: dict, cfg: dict) -> tuple[list, list, list]:
    """Devuelve (filas emparejadas, filas sin emparejar, columnas ignoradas)."""
    with open(ruta, newline="", encoding="utf-8-sig") as f:
        muestra = f.read(4096)
        f.seek(0)
        try:
            dialecto = csv.Sniffer().sniff(muestra, delimiters=",;\t")
        except csv.Error:
            dialecto = csv.excel
        lector = csv.DictReader(f, dialect=dialecto)
        cabecera = lector.fieldnames or []
        mapa, ignoradas = mapear_columnas(cabecera)

        if "titulo_export" not in mapa:
            return [], [{"_error": f"no encontré la columna de título/descripción "
                                   f"(columnas: {', '.join(cabecera[:6])}…)"}], ignoradas

        hoy = date.today().isoformat()
        emparejadas, sueltas = [], []

        for cruda in lector:
            texto = (cruda.get(mapa["titulo_export"]) or "").strip()
            if not texto:
                continue

            proyecto, score = emparejar(texto, indice, cfg["umbral_match"])
            fila = {
                "PROYECTO": proyecto or "",
                "tema": "",
                "plataforma": plataforma,
                "fecha_snapshot": hoy,
                "notas": "",
            }
            for campo in ("fecha_publicacion", "vistas", "alcance", "retencion_pct",
                          "duracion_media_s", "me_gusta", "comentarios",
                          "compartidos", "guardados"):
                if campo in mapa:
                    valor = cruda.get(mapa[campo], "")
                    fila[campo] = valor.strip() if campo == "fecha_publicacion" \
                        else limpiar_numero(valor)

            if proyecto:
                emparejadas.append(fila)
            else:
                sueltas.append({"texto": texto[:70], "score": score})

    return emparejadas, sueltas, ignoradas


# ══════════════════════════════════════════════════════════════
# 💾  ESCRITURA
# ══════════════════════════════════════════════════════════════

def cargar_existentes(ruta: str) -> list[dict]:
    if not os.path.exists(ruta):
        return []
    with open(ruta, newline="", encoding="utf-8") as f:
        return [dict(fila) for fila in csv.DictReader(f)]


def fusionar(previas: list[dict], nuevas: list[dict]) -> tuple[list[dict], int, int]:
    """Une por (PROYECTO, plataforma, fecha_snapshot). Reemplaza la foto del día,
    conserva las de otros días: así el histórico no se pisa y los deltas salen."""
    clave = lambda f: (f.get("PROYECTO", ""), f.get("plataforma", ""),
                       f.get("fecha_snapshot", ""))
    indice = {clave(f): f for f in previas}
    actualizadas = nuevas_filas = 0

    for fila in nuevas:
        k = clave(fila)
        if k in indice:
            # No pisar con vacío lo que ya estaba relleno
            indice[k].update({c: v for c, v in fila.items() if v not in ("", None)})
            actualizadas += 1
        else:
            indice[k] = fila
            nuevas_filas += 1

    orden = lambda f: (f.get("PROYECTO", ""), f.get("plataforma", ""),
                       f.get("fecha_snapshot", ""))
    return sorted(indice.values(), key=orden), nuevas_filas, actualizadas


def escribir(ruta: str, filas: list[dict]) -> None:
    columnas = list(COLUMNAS)
    for fila in filas:                      # conserva columnas viejas del csv previo
        for c in fila:
            if c not in columnas:
                columnas.append(c)

    with open(ruta, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
        escritor.writeheader()
        for fila in filas:
            escritor.writerow({c: fila.get(c, "") for c in columnas})


# ══════════════════════════════════════════════════════════════
# ▶️  EJECUCIÓN
# ══════════════════════════════════════════════════════════════

def main() -> None:
    p = argparse.ArgumentParser(description="Une los exports de las plataformas en metricas.csv")
    p.add_argument("--dry-run", action="store_true", help="Enseña qué haría, sin escribir")
    p.add_argument("--umbral", type=float, help="Similitud mínima para emparejar (0-1)")
    args = p.parse_args()

    cfg = dict(CONFIG)
    if args.umbral:
        cfg["umbral_match"] = args.umbral

    os.makedirs(cfg["dir_export"], exist_ok=True)
    archivos = sorted(Path(x) for x in glob.glob(f"{cfg['dir_export']}/*.csv"))

    if not archivos:
        raise SystemExit(
            f"❌ No hay CSV en '{cfg['dir_export']}/'.\n"
            f"   Exporta de cada plataforma y deja los archivos ahí, con el nombre\n"
            f"   empezando por la plataforma: youtube_*.csv, tiktok_*.csv,\n"
            f"   instagram_*.csv, facebook_*.csv  (ver METRICAS.md)"
        )

    indice = indice_proyectos(cfg)
    if not indice:
        raise SystemExit("❌ No encontré proyectos con metadata.json en proyectos/")
    print(f"🔎 {len(indice)} proyectos indexados para emparejar\n")

    todas, sin_emparejar = [], []

    for ruta in archivos:
        plataforma = detectar_plataforma(ruta, cfg)
        if not plataforma:
            print(f"⏭️  {ruta.name}: no sé de qué plataforma es — renómbralo empezando "
                  f"por {', '.join(cfg['plataformas'])}")
            continue

        filas, sueltas, ignoradas = leer_export(ruta, plataforma, indice, cfg)
        todas.extend(filas)
        sin_emparejar.extend((ruta.name, s) for s in sueltas)

        print(f"📄 {ruta.name}  [{plataforma}]")
        print(f"   ✅ {len(filas)} emparejadas · ⚠️  {len(sueltas)} sin emparejar")
        if ignoradas:
            print(f"   ℹ️  columnas no reconocidas: {', '.join(ignoradas[:6])}"
                  + ("…" if len(ignoradas) > 6 else ""))

    if sin_emparejar:
        print(f"\n⚠️  {len(sin_emparejar)} fila(s) sin emparejar — revísalas:")
        for archivo, s in sin_emparejar[:12]:
            if "_error" in s:
                print(f"   · {archivo}: {s['_error']}")
            else:
                print(f"   · [{s['score']:.2f}] {s['texto']}")
        print("   Si son videos tuyos, baja el umbral: --umbral 0.45")

    if not todas:
        raise SystemExit("\n❌ Nada que escribir.")

    previas = cargar_existentes(cfg["salida"])
    fusionadas, nuevas, actualizadas = fusionar(previas, todas)

    print(f"\n📊 {nuevas} filas nuevas · {actualizadas} actualizadas · "
          f"{len(fusionadas)} en total")

    if args.dry_run:
        print("\n🧪 --dry-run: no se escribió nada")
        return

    escribir(cfg["salida"], fusionadas)
    print(f"✅ Guardado: {cfg['salida']}")
    print("\n💡 Vuelve a exportar cada semana: los deltas de 24h/7d salen de comparar\n"
          "   dos fechas de snapshot, no de una sola descarga.")


if __name__ == "__main__":
    main()
# %%
