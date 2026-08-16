#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
🗓️  AGENDA — decide QUÉ se publica hoy y se lo pide a quien sabe hacerlo.

Es lo único que llama `cron`. Los clientes de API (`14_meta_api.py`,
`15_threads_api.py`) saben publicar pero no saben cuándo: aquí vive el calendario,
la rotación semanal y el reparto entre redes.

    python herramientas/16_agenda.py --reel              # el video del día
    python herramientas/16_agenda.py --extras            # carrusel / álbum / hilo
    python herramientas/16_agenda.py --estado            # qué hay hecho y qué falta
    python herramientas/16_agenda.py --extras --dry-run  # ensayo

Dos ritmos distintos, a propósito:

- **El reel va todos los días a las 12:00**, según `publicar/calendario.csv`.
  ⚠️ La hora no es una preferencia: todo lo que hay en `metricas.csv` se publicó
  a mediodía, y la hora mueve el alcance por sí sola. Cambiarla mezclaría dos
  condiciones en la misma columna y los lotes dejarían de ser comparables.

- **Los extras van uno por red y por semana, cada uno de un tema distinto**, para
  dar variedad a las páginas sin competir con el reel del día (por eso a otra
  hora). Un tema recibe **como mucho un extra en toda su vida**, en una sola red:
  es lo que garantiza que las tres redes nunca cuenten lo mismo la misma semana.
"""

#%% ═══════════════════════════════════════════════════════════════
#   CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════

import argparse
import csv
import importlib.util
from datetime import date, datetime, timedelta
from pathlib import Path

CONFIG = {
    "calendario": "publicar/calendario.csv",
    "registro":   "publicar/publicado.csv",
    "dir_publicar": "publicar",

    # Qué extra sale cada día de la semana (lunes = 0). Repartidos para que la
    # página no tenga tres publicaciones el mismo día y luego cuatro días muda.
    "dias_extra": {
        1: "instagram_carrusel",   # martes
        3: "facebook_album",       # jueves
        5: "threads",              # sábado
    },

    # Las redes del reel diario.
    "redes_reel": ["instagram", "facebook"],

    # ⚠️ Los temas que NO pasaron el control de calidad del paso 01 se publican
    # igual, por decisión de operación: la tanda de agosto se generó ANTES de que
    # la puerta abortara, ya está empaquetada y se publica tal cual para ver cómo
    # le va. De los lotes siguientes no puede llegar ninguno — un guion que no
    # pasa aborta el tema y nunca alcanza `publicar/`. Ponlo en True si algún día
    # vuelve a haber material sin auditar en la carpeta.
    "saltar_no_aprobados": False,

    # Temas que nunca entran en la rotación de extras.
    "excluir": ["Test01"],
}

RAIZ = Path(__file__).resolve().parent.parent


#%% ═══════════════════════════════════════════════════════════════
#   LEER EL ESTADO — calendario y registro
# ═══════════════════════════════════════════════════════════════

def _filas(ruta: Path) -> list[dict]:
    if not ruta.exists():
        return []
    with ruta.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def calendario() -> list[dict]:
    return _filas(RAIZ / CONFIG["calendario"])


def publicado() -> list[dict]:
    return _filas(RAIZ / CONFIG["registro"])


def ya_salio(proyecto: str, red: str) -> dict | None:
    for f in publicado():
        if f.get("proyecto") == proyecto and f.get("red") == red:
            return f
    return None


def toca_hoy(hoy: str) -> dict | None:
    """La fila del calendario cuya fecha es hoy."""
    for f in calendario():
        if f.get("fecha") == hoy:
            return f
    return None


#%% ═══════════════════════════════════════════════════════════════
#   ROTACIÓN — qué tema le toca al extra de esta semana
# ═══════════════════════════════════════════════════════════════

def temas_con_material() -> list[str]:
    """Temas empaquetados que tienen carrusel, en orden de nombre."""
    base = RAIZ / CONFIG["dir_publicar"]
    return sorted(
        d.name for d in base.iterdir()
        if d.is_dir() and d.name not in CONFIG["excluir"]
        and (d / "carrusel").is_dir() and any((d / "carrusel").glob("*.jpg"))
    )


def temas_pendientes_de_reel(hoy: str) -> set[str]:
    """Los que el calendario aún no ha emitido: su fecha es posterior a hoy.

    ⚠️ Un tema no puede recibir un extra **antes** que su propio reel: el
    carrusel remata la publicación del día, no la adelanta. Los temas que no
    están en el calendario (los lotes viejos, publicados a mano) sí entran.
    """
    return {f["proyecto"] for f in calendario() if f.get("fecha", "") > hoy}


def temas_ya_usados() -> set[str]:
    """Los que ya recibieron un extra, **de cualquier red**.

    ⚠️ Es la regla que da la variedad, y por eso mira todas las redes juntas y
    no una por una: un tema gasta un solo extra en toda su vida. Si cada red
    llevara su propia cuenta, las tres acabarían contando el mismo tema en
    semanas distintas, que es justo lo contrario de lo que se busca.
    """
    extras = set(CONFIG["dias_extra"].values())
    return {f["proyecto"] for f in publicado() if f.get("red") in extras}


def siguiente_tema(hoy: str) -> str | None:
    """El tema más antiguo que aún no ha gastado su extra."""
    usados = temas_ya_usados()
    futuros = temas_pendientes_de_reel(hoy)
    for tema in temas_con_material():
        if tema not in usados and tema not in futuros:
            return tema
    return None


#%% ═══════════════════════════════════════════════════════════════
#   PUBLICAR — se lo pedimos a los clientes de API
# ═══════════════════════════════════════════════════════════════

def _cargar(nombre: str):
    """Importa un `herramientas/NN_*.py` por ruta.

    El nombre empieza por dígito y `import` no lo admite; es el mismo truco que
    usa el paso 12 con `11_reporte.py`.
    """
    ruta = RAIZ / "herramientas" / nombre
    if not ruta.exists():
        return None
    spec = importlib.util.spec_from_file_location(ruta.stem, ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def publicar_reel(hoy: str, dry_run: bool) -> bool:
    fila = toca_hoy(hoy)
    if not fila:
        print(f"🗓️  {hoy}: el calendario no tiene nada para hoy.")
        return False

    proyecto = fila["proyecto"]
    aviso = (fila.get("revisar_a_mano") or "").strip()
    if CONFIG["saltar_no_aprobados"] and aviso.upper().startswith("SÍ"):
        print(f"⏭️  {proyecto}: el guion no pasó el control y "
              f"`saltar_no_aprobados` está activo. No se publica.")
        return False
    if aviso.upper().startswith("SÍ"):
        print(f"⚠️  {proyecto}: el guion no pasó el control del paso 01 "
              f"(nota {fila.get('nota_guion', '?')}). Se publica igual.")

    meta = _cargar("14_meta_api.py")
    meta.publicar(proyecto, CONFIG["redes_reel"], dry_run=dry_run)
    return True


def publicar_extra(hoy: str, dry_run: bool) -> bool:
    dia = datetime.strptime(hoy, "%Y-%m-%d").date().weekday()
    red = CONFIG["dias_extra"].get(dia)
    if not red:
        dias = "lunes martes miércoles jueves viernes sábado domingo".split()
        print(f"🗓️  {dias[dia]}: no toca extra. "
              f"Salen {', '.join(sorted(set(CONFIG['dias_extra'].values())))}.")
        return False

    tema = siguiente_tema(hoy)
    if not tema:
        print(f"✅ No queda ningún tema sin extra. Nada que publicar en {red}.\n"
              f"   Los extras se reponen solos con cada lote nuevo.")
        return False

    print(f"🗓️  {hoy} · toca {red} · le corresponde a {tema}\n")

    if red == "threads":
        hilos = _cargar("15_threads_api.py")
        if hilos is None:
            print("⏭️  15_threads_api.py todavía no existe. Se salta.")
            return False
        return bool(hilos.publicar_hilo_de(tema, dry_run=dry_run))

    meta = _cargar("14_meta_api.py")
    return bool(meta.publicar_extra(tema, red, dry_run=dry_run))


#%% ═══════════════════════════════════════════════════════════════
#   ESTADO — qué hay hecho y qué falta
# ═══════════════════════════════════════════════════════════════

def estado(hoy: str) -> None:
    print(f"🗓️  Agenda al {hoy}\n")

    cal = calendario()
    pendientes = [f for f in cal if f.get("fecha", "") >= hoy]
    print(f"📹 Reels programados: {len(pendientes)} de {len(cal)} por salir")
    for f in pendientes[:5]:
        marca = "⚠️ " if (f.get("revisar_a_mano") or "").upper().startswith("SÍ") else "  "
        print(f"   {marca} {f['fecha']} {f['hora']}  {f['proyecto']}")
    if len(pendientes) > 5:
        print(f"      … y {len(pendientes) - 5} más")
    if cal and not pendientes:
        print("   ⚠️  El calendario se agotó: genera el paquete del lote siguiente")

    hechos = publicado()
    reels = {f["proyecto"] for f in hechos if f["red"] in CONFIG["redes_reel"]}
    print(f"\n✅ Publicado: {len(reels)} reel(s), "
          f"{len(temas_ya_usados())} extra(s)")

    print(f"\n🔁 Rotación de extras")
    usados, futuros = temas_ya_usados(), temas_pendientes_de_reel(hoy)
    libres = [t for t in temas_con_material() if t not in usados and t not in futuros]
    for red_dia, red_nombre in sorted(CONFIG["dias_extra"].items()):
        dias = "lunes martes miércoles jueves viernes sábado domingo".split()
        print(f"   {dias[red_dia]:<10} {red_nombre}")
    print(f"\n   Siguiente en la cola: {libres[0] if libres else '— (agotada)'}")
    print(f"   Quedan {len(libres)} tema(s) sin extra"
          + (f", y {len(futuros)} esperando su reel" if futuros else ""))
    for f in sorted(hechos, key=lambda x: x["fecha"])[-4:]:
        print(f"      · {f['fecha']}  {f['proyecto']:<12} {f['red']}")


#%% ═══════════════════════════════════════════════════════════════
#   CLI
# ═══════════════════════════════════════════════════════════════

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--reel", action="store_true",
                   help="Publica el reel que toca hoy según el calendario")
    p.add_argument("--extras", action="store_true",
                   help="Publica el extra semanal que toca hoy (carrusel/álbum/hilo)")
    p.add_argument("--estado", action="store_true",
                   help="Qué hay publicado y qué falta. No publica nada")
    p.add_argument("--dry-run", action="store_true",
                   help="Ensaya sin publicar (sube las imágenes y las retira)")
    p.add_argument("--fecha", metavar="AAAA-MM-DD",
                   help="Fingir otra fecha. Para probar la rotación")
    args = p.parse_args()

    hoy = args.fecha or date.today().isoformat()

    if args.estado:
        estado(hoy)
    elif args.reel:
        publicar_reel(hoy, dry_run=args.dry_run)
    elif args.extras:
        publicar_extra(hoy, dry_run=args.dry_run)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
