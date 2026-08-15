#%%
"""
╔══════════════════════════════════════════════════════════════╗
║   📊 CONSOLIDADOR DE MÉTRICAS                                ║
║   Lee los exports TAL CUAL vienen y los une en metricas.csv   ║
╚══════════════════════════════════════════════════════════════╝

NO es un paso del pipeline. Se corre cuando quieras actualizar los números.

Tú solo descargas y sueltas los archivos en `metricas_export/`, **sin tocarlos**:
zips sin descomprimir, CSV con el nombre que traigan. El script se encarga.

    metricas_export/
        youtube_historico.zip      → trae 3 csv; usa "Datos de la tabla"
        tiktok_historico.zip       → trae Content.csv
        facebook_historico.csv     → export de Facebook
        facebook_historico2.csv    → export de Meta Business (se fusionan por id)
        instagram_historico.csv    → export de Meta Business

Uso:
    python 10_metricas.py                # normaliza, empareja y escribe
    python 10_metricas.py --dry-run      # enseña qué haría, sin escribir
    python 10_metricas.py --umbral 0.45  # afloja el emparejado por texto

Qué hace, en orden:
  1. Descomprime los zip y localiza el csv bueno de cada uno.
  2. Normaliza los 5 formatos a un csv por plataforma en
     `metricas_export/_normalizado/` — mismos nombres de columna para todos.
     Ese paso es el que quita la fricción: a partir de ahí todo es uniforme.
  3. Empareja cada fila con su PROYECTO por parecido de texto.
  4. Fusiona en `metricas.csv` sin pisar el histórico.

Lo que no empareje se acumula en `metricas_export/mapa_manual.csv` con la
columna PROYECTO vacía: la rellenas UNA vez y el script la respeta para siempre.
"""

import argparse
import csv
import os
import re
import shutil
import unicodedata
import zipfile
from datetime import date, datetime
from difflib import SequenceMatcher
from pathlib import Path

# ══════════════════════════════════════════════════════════════
# ⚙️  CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════

CONFIG = {
    "dir_export":     "metricas_export",
    "dir_normalizado": "metricas_export/_normalizado",
    "mapa_manual":    "metricas_export/mapa_manual.csv",
    "dir_proyectos":  "proyectos",
    "temas":          "temas.csv",
    "salida":         "metricas.csv",

    # Similitud mínima texto-exportación para dar por bueno un emparejado.
    # 0.55 va bien con captions largos; lo dudoso se manda al mapa manual.
    "umbral_match":   0.55,

    # Marca del lote. Los PROYECTO de temas.csv son los del pipeline nuevo
    # (más cortes, planos con movimiento, audio a −14 LUFS, gancho sin spoiler);
    # todo lo demás es lo de antes y sirve de referencia.
    "lote_nuevo":     "v2-mas-cortes",
    "lote_baseline":  "baseline",
}

# Columnas de metricas.csv. `fecha_snapshot` es la clave del asunto: un export
# trae vistas ACUMULADAS, no "vistas a 24 h". Guardando una foto por fecha, los
# deltas salen de restar dos filas.
COLUMNAS = [
    "PROYECTO", "lote", "tema", "plataforma", "fecha_snapshot", "fecha_publicacion",
    "duracion_s", "vistas", "alcance", "impresiones",
    "retencion_pct", "duracion_media_s", "se_quedaron_pct",
    "me_gusta", "comentarios", "compartidos", "guardados", "seguidores_ganados",
    "notas",
]


# ══════════════════════════════════════════════════════════════
# 🗺️  QUÉ COLUMNA ES QUÉ, EN CADA EXPORT
# ══════════════════════════════════════════════════════════════
# Mapeo explícito, no por adivinanza: estos son los nombres REALES que traen los
# archivos de esta cuenta (en español). Si cambias el idioma de la cuenta o
# Meta/Google renombran algo, se toca aquí y en ningún otro sitio.

FUENTES = {
    "youtube": {
        "patron_zip":  "tabla",              # el zip trae 3 csv; este es el bueno
        "texto":       ["Título del video"],
        "id":          "Contenido",
        # ⚠️ La primera fila del export es el TOTAL del canal, no un video.
        "descartar_si": lambda f: f.get("Contenido", "").strip() == "Total",
        "columnas": {
            "fecha_publicacion":  "Tiempo de publicación del video",
            "duracion_s":         "Duración",
            "vistas":             "Vistas",
            "alcance":            "Alcance único",
            "impresiones":        "Impresiones",
            "retencion_pct":      "Porcentaje promedio reproducido (%)",
            "duracion_media_s":   "Duración promedio de vistas",
            "se_quedaron_pct":    "Se quedaron para mirar (%)",
            "me_gusta":           "Me gusta",
            "comentarios":        "Comentarios agregados",
            "compartidos":        "Elementos compartidos",
            "seguidores_ganados": "Suscriptores obtenidos",
        },
    },
    "tiktok": {
        "patron_zip":  "content",
        "texto":       ["Video title"],      # en TikTok el "título" es el caption
        "id":          "Video link",
        "columnas": {
            "fecha_publicacion": "Post time",
            "vistas":            "Total views",
            "me_gusta":          "Total likes",
            "comentarios":       "Total comments",
            "compartidos":       "Total shares",
        },
    },
    "instagram": {
        "texto":       ["Descripción"],
        "id":          "Identificador de la publicación",
        # Fuera secuencias (carruseles) y todo lo que no sea reel.
        "descartar_si": lambda f: "Reel" not in f.get("Tipo de publicación", ""),
        "columnas": {
            "fecha_publicacion":  "Hora de publicación",
            "duracion_s":         "Duración (segundos)",
            "vistas":             "Visualizaciones",
            "alcance":            "Alcance",
            "me_gusta":           "Me gusta",
            "comentarios":        "Comentarios",
            "compartidos":        "Veces que se compartió",
            "guardados":          "Veces que se guardó",
            "seguidores_ganados": "Seguimientos",
        },
    },
    # Facebook son DOS archivos del mismo periodo que se fusionan por id:
    #   · el de Meta Business trae el TÍTULO que generamos (emparejar) y el alcance
    #   · el de Facebook trae guardados, impresiones y seguimientos netos
    # Ver METRICAS.md para el porqué.
    "facebook": {
        "texto":       ["Título", "Descripción"],
        "id":          "Identificador de la publicación",
        "descartar_si": lambda f: f.get("Tipo de publicación", "") not in ("Reel", "Videos"),
        "columnas": {
            "fecha_publicacion":  "Hora de publicación",
            "duracion_s":         "Duración (segundos)",
            "vistas":             "Visualizaciones",
            "alcance":            "Alcance",
            "impresiones":        "Impresiones",
            "duracion_media_s":   "Segundos en promedio reproducidos",
            "me_gusta":           "Reacciones",
            "comentarios":        "Comentarios",
            "compartidos":        "Veces que se compartió",
            "guardados":          "Veces que se guardó",
            "seguidores_ganados": "Seguimientos netos",
        },
        "alternativas": {                    # si falta la principal, usar esta
            "alcance": "Espectadores",
        },
    },
}


# ══════════════════════════════════════════════════════════════
# 📦  INGESTA: zips y csv tal cual vienen
# ══════════════════════════════════════════════════════════════

def nombre_zip(info: zipfile.ZipInfo) -> str:
    """Los zip de YouTube guardan el nombre en cp437 si no marcan UTF-8, así que
    'Datos del gráfico.csv' llega como 'Datos del gr├бfico.csv'. Se rehace."""
    if info.flag_bits & 0x800:
        return info.filename
    try:
        return info.filename.encode("cp437").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return info.filename


def extraer_zips(cfg: dict) -> None:
    """Descomprime cada zip en _normalizado/_crudo/<plataforma>/."""
    destino_base = Path(cfg["dir_normalizado"]) / "_crudo"
    for z in sorted(Path(cfg["dir_export"]).glob("*.zip")):
        plataforma = detectar_plataforma(z)
        if not plataforma:
            continue
        destino = destino_base / plataforma
        destino.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(z) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                nombre = nombre_zip(info)
                with zf.open(info) as origen, open(destino / Path(nombre).name, "wb") as salida:
                    shutil.copyfileobj(origen, salida)
        print(f"   📦 {z.name} → {destino}/")


def detectar_plataforma(ruta: Path) -> str | None:
    nombre = normalizar(ruta.stem)
    for p in FUENTES:
        if nombre.startswith(p) or p in nombre.split():
            return p
    return None


def archivos_de(plataforma: str, cfg: dict) -> list[Path]:
    """Los csv de esa plataforma: los sueltos y los que salieron de su zip."""
    sueltos = [p for p in Path(cfg["dir_export"]).glob("*.csv")
               if detectar_plataforma(p) == plataforma]

    del_zip = []
    carpeta = Path(cfg["dir_normalizado"]) / "_crudo" / plataforma
    patron = FUENTES[plataforma].get("patron_zip")
    if carpeta.is_dir():
        for p in sorted(carpeta.glob("*.csv")):
            if not patron or patron in normalizar(p.stem):
                del_zip.append(p)

    return sorted(sueltos) + del_zip


def leer_csv(ruta: Path) -> list[dict]:
    with open(ruta, encoding="utf-8-sig", newline="") as f:
        return [dict(fila) for fila in csv.DictReader(f)]


# ══════════════════════════════════════════════════════════════
# 🔢  LIMPIEZA DE VALORES
# ══════════════════════════════════════════════════════════════

MESES = {"enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6,
         "julio": 7, "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10,
         "noviembre": 11, "diciembre": 12,
         "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "jul": 7,
         "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12}


def normalizar(texto: str) -> str:
    """Minúsculas, sin acentos y sin puntuación."""
    texto = unicodedata.normalize("NFKD", str(texto))
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9 ]", " ", texto.lower()).strip()


# Campos que SON decimales. El resto son contadores enteros (vistas, me gusta…).
# ⚠️ Esta distinción no es un lujo: Facebook exporta los segundos medios vistos
# como "9.378" y una regla genérica de "3 dígitos detrás = separador de miles"
# lo leía como 9378 segundos, dando retenciones del 17.000 %.
CAMPOS_DECIMALES = {"retencion_pct", "duracion_media_s", "se_quedaron_pct"}


def limpiar_numero(valor: str, decimal: bool = False) -> str:
    """Normaliza un número de cualquiera de los exports. '' si no se puede.

    Contadores  ('1.284', '1,284')      → '1284'   (los separadores son de miles)
    Decimales   ('9.378', '62,5 %')     → '9.378', '62.5'
    Duraciones  ('0:00:44')             → '44'     (segundos)
    """
    if valor is None:
        return ""
    v = str(valor).strip().replace("%", "").strip()
    if not v or v in ("--", "N/A", "-"):
        return ""

    if ":" in v:                                   # duración h:mm:ss o mm:ss
        try:
            segundos = 0
            for parte in v.split(":"):
                segundos = segundos * 60 + int(parte)
            return str(segundos)
        except ValueError:
            return ""

    v = re.sub(r"[^\d,.\-]", "", v)
    if not v:
        return ""

    # Con los dos separadores, el ÚLTIMO es el decimal: 1.234,56 y 1,234.56 son
    # el mismo número escrito en dos idiomas.
    if "," in v and "." in v:
        return (v.replace(".", "").replace(",", ".") if v.rfind(",") > v.rfind(".")
                else v.replace(",", ""))

    if not decimal:                                # contador: todo separador es de miles
        return v.replace(",", "").replace(".", "")

    # Decimal con un solo separador: ese separador ES la coma decimal. Estos
    # campos son porcentajes y segundos, nunca cifras de miles.
    return v.replace(",", ".") if v.count(",") == 1 else v


def limpiar_fecha(valor: str) -> str:
    """Deja la fecha en ISO. Entiende los tres formatos que llegan:
       'May 8, 2026' (YouTube) · '08/14/2026 10:00' (Meta) · '9 de junio' (TikTok).

    ⚠️ TikTok exporta el día y el mes SIN año. Se asume el año en curso, y si el
    mes queda en el futuro se toma el anterior. Es una suposición: si publicas
    algo con más de un año de antigüedad, esa fecha saldrá mal.
    """
    if not valor:
        return ""
    v = str(valor).strip()

    for formato in ("%m/%d/%Y %H:%M", "%m/%d/%Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(v, formato).date().isoformat()
        except ValueError:
            pass

    m = re.match(r"(\d{1,2})\s+de\s+(\w+)(?:\s+de\s+(\d{4}))?", normalizar(v))
    if m:
        dia, mes_txt, anio = m.groups()
        mes = MESES.get(mes_txt)
        if mes:
            hoy = date.today()
            anio = int(anio) if anio else (hoy.year if mes <= hoy.month else hoy.year - 1)
            try:
                return date(anio, mes, int(dia)).isoformat()
            except ValueError:
                return ""
    return v


# ══════════════════════════════════════════════════════════════
# 🔄  NORMALIZACIÓN
# ══════════════════════════════════════════════════════════════

def normalizar_filas(plataforma: str, crudas: list[dict]) -> list[dict]:
    """Pasa un export al formato canónico. Ignora lo que no sea video."""
    spec = FUENTES[plataforma]
    descartar = spec.get("descartar_si")
    salida = []

    for cruda in crudas:
        if descartar and descartar(cruda):
            continue

        texto = next((cruda[c].strip() for c in spec["texto"]
                      if cruda.get(c) and cruda[c].strip()), "")
        if not texto:
            continue

        fila = {
            "plataforma": plataforma,
            "_id": (cruda.get(spec["id"]) or "").strip(),
            "_texto": texto,
        }
        for campo, columna in spec["columnas"].items():
            valor = cruda.get(columna)
            if (valor is None or not str(valor).strip()) and campo in spec.get("alternativas", {}):
                valor = cruda.get(spec["alternativas"][campo])
            if valor is None:
                continue
            fila[campo] = (limpiar_fecha(valor) if campo == "fecha_publicacion"
                           else limpiar_numero(valor, campo in CAMPOS_DECIMALES))

        # Facebook e Instagram no dan el % de retención, pero sí los segundos
        # medios vistos y la duración: dividiendo sale, y es comparable con YouTube.
        if not fila.get("retencion_pct"):
            media, total = fila.get("duracion_media_s"), fila.get("duracion_s")
            try:
                if media and total and float(total) > 0:
                    fila["retencion_pct"] = f"{float(media) / float(total) * 100:.1f}"
            except ValueError:
                pass

        salida.append(fila)

    return salida


def fusionar_por_id(bloques: list[list[dict]]) -> list[dict]:
    """Une varios exports de la misma plataforma por id (caso Facebook).

    El primero que traiga un valor manda; los siguientes solo rellenan huecos.
    Así el archivo de Meta Business aporta título y alcance, y el de Facebook
    aporta guardados, impresiones y seguimientos netos, sin pisarse.
    """
    unido: dict[str, dict] = {}
    for bloque in bloques:
        for fila in bloque:
            clave = fila.get("_id") or fila.get("_texto", "")[:80]
            if clave not in unido:
                unido[clave] = dict(fila)
                continue
            for campo, valor in fila.items():
                if valor not in ("", None) and not unido[clave].get(campo):
                    unido[clave][campo] = valor
    return list(unido.values())


def escribir_normalizado(cfg: dict, plataforma: str, filas: list[dict]) -> Path:
    ruta = Path(cfg["dir_normalizado"]) / f"{plataforma}.csv"
    ruta.parent.mkdir(parents=True, exist_ok=True)
    columnas = ["_id", "_texto"] + [c for c in COLUMNAS if c not in ("PROYECTO", "lote", "tema", "notas")]
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(f, fieldnames=columnas, extrasaction="ignore")
        escritor.writeheader()
        for fila in filas:
            escritor.writerow({c: fila.get(c, "") for c in columnas})
    return ruta


# ══════════════════════════════════════════════════════════════
# 🔗  EMPAREJADO CON LOS PROYECTOS
# ══════════════════════════════════════════════════════════════

# Textos de cada proyecto que sirven para reconocerlo en un export. Los tres
# primeros son del pipeline actual; los dos últimos, de los respaldos viejos
# (los 16 Mundial no tienen metadata.json y sin esto no se emparejaría ninguno).
FUENTES_TEXTO = ["metadata.json", "descripcion.txt", "descripcion_general.txt",
                 "04_facebook.txt", "03_instagram.txt"]


def textos_de_proyecto(posts: Path) -> list[str]:
    textos = []
    for nombre in FUENTES_TEXTO:
        ruta = posts / nombre
        if not ruta.exists():
            continue
        contenido = ruta.read_text(encoding="utf-8", errors="ignore")

        if nombre == "metadata.json":
            m = re.search(r'"titulo"\s*:\s*"(.*?)"', contenido)
            if m:
                textos.append(m.group(1))
            continue

        if nombre == "descripcion.txt":
            m = re.search(r"DESCRIPCIÓN GENERAL.*?─+\n(.*?)\n\n", contenido, re.S)
            textos.append(m.group(1) if m else contenido[:400])
            continue

        # Los legados abren con "=== FACEBOOK ===" y una línea en blanco.
        cuerpo = re.sub(r"^\s*===.*?===\s*", "", contenido, flags=re.S)
        textos.append(cuerpo[:400])

    return [t for t in textos if t.strip()]


def indice_proyectos(cfg: dict) -> dict:
    indice = {}
    for posts in sorted(Path(cfg["dir_proyectos"]).glob("*/social_posts")):
        textos = textos_de_proyecto(posts)
        if textos:
            indice[posts.parent.name] = textos
    return indice


def tokens(texto: str, minimo: int = 4) -> set[str]:
    """Palabras significativas. Las de 3 letras o menos ('al', 'de', 'la') no
    distinguen nada y ensucian el solapamiento."""
    return {t for t in normalizar(texto).split() if len(t) >= minimo}


def puntuar(a: str, b: str) -> tuple[float, int]:
    """(parecido 0-1, nº de palabras en común). Dos vías, gana la mejor.

    1. **Solapamiento de palabras.** Es la que salva los títulos cortos escritos
       a mano: "Memo Ochoa al PSG" contra el caption largo de Mundial16 comparte
       'memo', 'ochoa' y 'psg'. Comparando secuencias eso daba 0.33 y no
       emparejaba; por palabras da 1.0. Se exigen 2 coincidencias como mínimo
       para que una palabra suelta y común no dispare un falso positivo.
    2. **Secuencia**, para cuando los dos textos son largos y parecidos (el
       caption que publicamos contra el que guardamos).

    El nº de palabras comunes se devuelve aparte porque es el desempate: varios
    títulos cortos pueden dar 1.00 contra el mismo proyecto, y gana el que
    comparta más palabras.
    """
    ta, tb = tokens(a), tokens(b)
    cobertura, comunes = 0.0, set()
    if ta and tb:
        comunes = ta & tb
        corto = ta if len(ta) <= len(tb) else tb
        if len(comunes) >= 2:
            cobertura = len(comunes) / len(corto)

    na, nb = " ".join(normalizar(a).split())[:300], " ".join(normalizar(b).split())[:300]
    secuencia = SequenceMatcher(None, na, nb).ratio() if na and nb else 0.0

    return max(cobertura, secuencia), len(comunes)


def emparejar(texto: str, indice: dict, umbral: float) -> tuple[str | None, float]:
    """Mejor proyecto para un texto suelto (sin exclusividad). Para diagnóstico."""
    mejor, mejor_score = None, 0.0
    for proyecto, textos in indice.items():
        score = max(puntuar(texto, t)[0] for t in textos)
        if score > mejor_score:
            mejor, mejor_score = proyecto, score
    return (mejor if mejor_score >= umbral else None), mejor_score


def asignar_uno_a_uno(filas: list[dict], indice: dict, umbral: float,
                      fijados: dict) -> tuple[dict, dict]:
    """Asigna como mucho UN video por proyecto, y un proyecto por video.

    ⚠️ Sin esta exclusividad, "Árbitro polémico", "Árbitro de mundial" y "La mano
    de Dios" caían los tres en Mundial01 y, como metricas.csv se indexa por
    (PROYECTO, plataforma, fecha), el último pisaba a los otros dos EN SILENCIO.

    Se resuelve por avaricia: se ordenan todos los pares candidatos por parecido
    (y a igualdad, por nº de palabras compartidas) y se van tomando los que no
    tengan ni el video ni el proyecto ya cogidos.

    Devuelve ({índice_de_fila: PROYECTO}, {índice_de_fila: (candidato, score)}).
    """
    asignado: dict[int, str] = {}
    tomados: set[str] = set()
    mejor_intento: dict[int, tuple[str | None, float]] = {}

    # Los fijados a mano mandan sobre cualquier cálculo.
    for i, fila in enumerate(filas):
        proyecto = fijados.get(fila["_id"])
        if proyecto:
            asignado[i] = proyecto
            tomados.add(proyecto)

    candidatos = []
    for i, fila in enumerate(filas):
        if i in asignado:
            continue
        for proyecto, textos in indice.items():
            score, comunes = max((puntuar(fila["_texto"], t) for t in textos),
                                 key=lambda x: (x[0], x[1]))
            if score > mejor_intento.get(i, (None, 0.0))[1]:
                mejor_intento[i] = (proyecto, score)
            if score >= umbral:
                candidatos.append((score, comunes, i, proyecto))

    for score, _comunes, i, proyecto in sorted(candidatos, reverse=True,
                                               key=lambda c: (c[0], c[1])):
        if i in asignado or proyecto in tomados:
            continue
        asignado[i] = proyecto
        tomados.add(proyecto)

    sin_asignar = {i: mejor_intento.get(i, (None, 0.0))
                   for i in range(len(filas)) if i not in asignado}
    return asignado, sin_asignar


def cargar_mapa_manual(cfg: dict) -> dict:
    """{(plataforma, id): PROYECTO} de las correcciones puestas a mano."""
    ruta = Path(cfg["mapa_manual"])
    if not ruta.exists():
        return {}
    mapa = {}
    for fila in leer_csv(ruta):
        proyecto = (fila.get("PROYECTO") or "").strip()
        if proyecto:
            mapa[(fila.get("plataforma", ""), fila.get("id", ""))] = proyecto
    return mapa


def guardar_mapa_manual(cfg: dict, pendientes: list[dict]) -> None:
    """Acumula lo no emparejado conservando lo que ya estuviera relleno."""
    ruta = Path(cfg["mapa_manual"])
    previas = {(f.get("plataforma", ""), f.get("id", "")): f for f in
               (leer_csv(ruta) if ruta.exists() else [])}
    for p in pendientes:
        clave = (p["plataforma"], p["id"])
        if clave in previas:
            previas[clave]["texto"] = p["texto"]      # refresca el texto, no el PROYECTO
        else:
            previas[clave] = p

    with open(ruta, "w", newline="", encoding="utf-8") as f:
        escritor = csv.DictWriter(
            f, fieldnames=["plataforma", "id", "PROYECTO", "candidato", "score", "texto"])
        escritor.writeheader()
        for fila in sorted(previas.values(), key=lambda x: (x.get("plataforma", ""), x.get("id", ""))):
            escritor.writerow({c: fila.get(c, "") for c in
                               ["plataforma", "id", "PROYECTO", "candidato", "score", "texto"]})


# ══════════════════════════════════════════════════════════════
# 🏷️  LOTES
# ══════════════════════════════════════════════════════════════

def temas_por_proyecto(cfg: dict) -> dict:
    """{PROYECTO: TEMA}. De temas.csv el lote actual; de los logs los anteriores,
    que se llaman '{PROYECTO}_{TEMA}.log' y son lo único que guarda el tema viejo."""
    temas = {}
    for log in Path("logs").glob("*_*.log"):
        proyecto, _, tema = log.stem.partition("_")
        if proyecto and tema:
            temas[proyecto] = tema.replace("_", " ")

    ruta = Path(cfg["temas"])
    if ruta.exists():
        for fila in ruta.read_text(encoding="utf-8").splitlines()[1:]:
            campos = [c.strip() for c in fila.split(",")]
            if len(campos) >= 2 and campos[0] and campos[0].upper() != "PROYECTO":
                temas[campos[0]] = campos[1]
    return temas


def proyectos_del_lote_nuevo(cfg: dict) -> set[str]:
    """Los PROYECTO de temas.csv: el primer lote con el pipeline cambiado."""
    ruta = Path(cfg["temas"])
    if not ruta.exists():
        return set()
    nuevos = set()
    for fila in ruta.read_text(encoding="utf-8").splitlines()[1:]:
        campos = [c.strip() for c in fila.split(",")]
        if campos and campos[0] and campos[0].upper() != "PROYECTO":
            nuevos.add(campos[0])
    return nuevos


# ══════════════════════════════════════════════════════════════
# 💾  ESCRITURA
# ══════════════════════════════════════════════════════════════

def fusionar(previas: list[dict], nuevas: list[dict]) -> tuple[list[dict], int, int]:
    """Une por (PROYECTO, plataforma, fecha_snapshot): reescribe la foto de hoy y
    conserva las de otros días, así el histórico no se pisa."""
    clave = lambda f: (f.get("PROYECTO", ""), f.get("plataforma", ""),
                       f.get("fecha_snapshot", ""))
    indice = {clave(f): f for f in previas}
    nuevas_filas = actualizadas = 0

    for fila in nuevas:
        k = clave(fila)
        if k in indice:
            indice[k].update({c: v for c, v in fila.items() if v not in ("", None)})
            actualizadas += 1
        else:
            indice[k] = fila
            nuevas_filas += 1

    return sorted(indice.values(), key=clave), nuevas_filas, actualizadas


def escribir(ruta: str, filas: list[dict]) -> None:
    columnas = list(COLUMNAS)
    for fila in filas:
        for c in fila:
            if c not in columnas and not c.startswith("_"):
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

    print("📦 Descomprimiendo…")
    extraer_zips(cfg)

    indice = indice_proyectos(cfg)
    if not indice:
        raise SystemExit("❌ No encontré proyectos con textos en proyectos/*/social_posts/")
    nuevos = proyectos_del_lote_nuevo(cfg)
    temas = temas_por_proyecto(cfg)
    print(f"\n🔎 {len(indice)} proyectos indexados · {len(nuevos)} marcados como "
          f"'{cfg['lote_nuevo']}' (de {cfg['temas']})")

    manual = cargar_mapa_manual(cfg)
    if manual:
        print(f"🖐️  {len(manual)} emparejado(s) fijados a mano en {cfg['mapa_manual']}")

    hoy = date.today().isoformat()
    todas, pendientes = [], []
    print("\n🔄 Normalizando:")

    for plataforma in FUENTES:
        archivos = archivos_de(plataforma, cfg)
        if not archivos:
            print(f"   ⏭️  {plataforma}: sin archivos")
            continue

        bloques = [normalizar_filas(plataforma, leer_csv(r)) for r in archivos]
        filas = fusionar_por_id(bloques) if len(bloques) > 1 else bloques[0]

        ruta = escribir_normalizado(cfg, plataforma, filas) if not args.dry_run else None
        origen = ", ".join(r.name for r in archivos)
        print(f"   ✅ {plataforma:<10} {len(filas):>3} videos  ({origen})"
              + (f" → {ruta}" if ruta else ""))

        fijados = {i: p for (plat, i), p in manual.items() if plat == plataforma}
        asignado, sin_asignar = asignar_uno_a_uno(
            filas, indice, cfg["umbral_match"], fijados)

        for i, proyecto in asignado.items():
            limpia = {c: v for c, v in filas[i].items() if not c.startswith("_")}
            limpia.update({
                "PROYECTO": proyecto,
                "lote": cfg["lote_nuevo"] if proyecto in nuevos else cfg["lote_baseline"],
                "tema": temas.get(proyecto, ""),
                "fecha_snapshot": hoy,
            })
            todas.append(limpia)

        for i, (candidato, score) in sin_asignar.items():
            pendientes.append({
                "plataforma": plataforma, "id": filas[i]["_id"], "PROYECTO": "",
                "candidato": candidato or "", "score": f"{score:.2f}",
                "texto": " ".join(filas[i]["_texto"].split())[:110],
            })

        print(f"      └─ {len(asignado)} emparejados con un PROYECTO")

    if pendientes:
        print(f"\n⚠️  {len(pendientes)} video(s) sin emparejar. Son de antes del pipeline "
              f"o el texto cambió al publicar.")
        for p_ in pendientes[:8]:
            print(f"   · [{p_['score']}] {p_['plataforma']:<10} {p_['texto'][:60]}")
        if len(pendientes) > 8:
            print(f"   … y {len(pendientes) - 8} más")
        print(f"   → Se apuntan en {cfg['mapa_manual']}: rellena la columna PROYECTO\n"
              f"     de los que te interesen y vuelve a correr. Lo demás se ignora.")

    if not todas:
        raise SystemExit("\n❌ Nada emparejado — nada que escribir.")

    previas = leer_csv(Path(cfg["salida"])) if os.path.exists(cfg["salida"]) else []
    fusionadas, nuevas_filas, actualizadas = fusionar(previas, todas)

    print(f"\n📊 {nuevas_filas} filas nuevas · {actualizadas} actualizadas · "
          f"{len(fusionadas)} en total")

    if args.dry_run:
        print("\n🧪 --dry-run: no se escribió nada")
        return

    escribir(cfg["salida"], fusionadas)
    guardar_mapa_manual(cfg, pendientes)
    print(f"✅ Guardado: {cfg['salida']}")
    print("\n💡 Vuelve a exportar cada semana: los deltas de 24 h y 7 d salen de\n"
          "   comparar dos fechas de snapshot, no de una sola descarga.")


if __name__ == "__main__":
    main()
# %%
