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
    # ⚠️ **Facebook NO está aquí, y es una decisión, no un olvido ni un apaño
    # temporal: se publica a mano por Metricool.**
    # Todo lo que publica esta app en la página llega a **2 personas**, mientras
    # que el mismo vídeo subido por Metricool el 28 alcanzó **1.039**. La página
    # está sana; lo que está limitado es nuestra app: tiene **un solo rol**
    # (`/roles` devuelve un administrador) y una app de Meta en modo Desarrollo
    # o con Standard Access **solo enseña a quien tenga rol en ella** lo que
    # publica en una página. Eso explica el «exactamente 2» diez veces seguidas,
    # que ninguna penalización de ranking produciría.
    # Instagram no está afectado y sigue automático.
    # ⚠️ **Añadir "facebook" aquí sin arreglar antes la app publica a 2
    # personas.** Haría falta pasarla a **Live** con **Advanced Access** para
    # `pages_manage_posts` (verificación de negocio, días de trámite) y
    # comprobarlo con UNA publicación antes de volver a confiar — que es
    # exactamente lo que no se hizo el 15 ago y costó diez vídeos. Ver P-31.
    "redes_reel": ["instagram"],

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


def pendientes(hoy: str) -> list[dict]:
    """Filas cuya fecha ya llegó y a las que aún les falta alguna red.

    ⚠️ **Esto es lo que hace que un día sin encender el PC no pierda un video.**
    Mirar solo la fila de hoy parecía natural y era un agujero: si `cron` no
    corre el día 18, `Historia10` no se publica **nunca** — nadie vuelve a mirar
    esa fila, y el fallo no deja rastro porque no llega a ejecutarse nada.

    Una fila sigue pendiente mientras le falte **una sola** red: si Instagram
    salió y Facebook falló, vuelve mañana y `publicar()` se salta la que ya está.
    """
    vivas = []
    for f in calendario():
        if f.get("fecha", "") > hoy:
            continue
        if any(not ya_salio(f["proyecto"], red) for red in CONFIG["redes_reel"]):
            vivas.append(f)
    # ⚠️ **Por fecha, no por orden del archivo.** Decía «el más antiguo» y
    # devolvía «el primero del CSV»: coincidían solo mientras nadie reordenara
    # el calendario. Al reprogramar las resubidas de Facebook (25 ago) una fila
    # quedó al final con fecha anterior, y el atraso se habría recuperado en el
    # orden equivocado sin que nada avisara.
    return sorted(vivas, key=lambda f: f.get("fecha", ""))


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
    """Publica UN reel: el más antiguo al que aún le falte alguna red.

    ⚠️ **Uno por corrida, aunque haya varios atrasados.** Si el PC estuvo tres
    días apagado, la tentación es soltar los tres de golpe; pero la cadencia de
    uno al día es justamente lo que evita que compitan entre ellos, así que el
    calendario se recupera a un video por día en vez de vaciarse en una tarde.
    """
    cola = pendientes(hoy)
    if not cola:
        hay_calendario = bool(calendario())
        print(f"🗓️  {hoy}: nada pendiente."
              + ("" if hay_calendario else " El calendario está vacío."))
        return False

    fila = cola[0]
    atraso = (datetime.strptime(hoy, "%Y-%m-%d").date()
              - datetime.strptime(fila["fecha"], "%Y-%m-%d").date()).days
    if atraso:
        print(f"⏰ {fila['proyecto']} se quedó atrás: le tocaba el "
              f"{fila['fecha']} ({atraso} día(s)). Se publica ahora.")
        if len(cola) > 1:
            print(f"   Quedan {len(cola) - 1} atrasado(s); saldrán uno por día.")

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


DIAS = "lunes martes miércoles jueves viernes sábado domingo".split()


def inicio_de_semana(hoy: str) -> str:
    """El lunes de la semana de `hoy`."""
    d = datetime.strptime(hoy, "%Y-%m-%d").date()
    return (d - timedelta(days=d.weekday())).isoformat()


def extra_que_toca(hoy: str) -> str | None:
    """La red cuyo extra falta esta semana y cuyo día ya pasó.

    ⚠️ **No es «¿hoy es martes?», y ahí está la recuperación.** Con la pregunta
    simple, un martes con el PC apagado se lleva por delante el carrusel de esa
    semana entera. Aquí se mira si el extra de cada red **ya salió esta semana**;
    si no y su día ya pasó, sale hoy. Es la misma idea que el `--si-falta` del
    recordatorio de Telegram.

    Devuelve una sola red por corrida: dos publicaciones el mismo día en la misma
    página compiten entre ellas, que es justo lo que reparte `dias_extra`.
    """
    dia = datetime.strptime(hoy, "%Y-%m-%d").date().weekday()
    desde = inicio_de_semana(hoy)
    ya_esta_semana = {f["red"] for f in publicado() if f.get("fecha", "") >= desde}
    for dia_red, red in sorted(CONFIG["dias_extra"].items()):
        if dia_red <= dia and red not in ya_esta_semana:
            return red
    return None


def publicar_extra(hoy: str, dry_run: bool) -> bool:
    red = extra_que_toca(hoy)
    if not red:
        dia = datetime.strptime(hoy, "%Y-%m-%d").date().weekday()
        print(f"🗓️  {DIAS[dia]}: no toca extra "
              f"(o el de esta semana ya salió).")
        return False

    dia_suyo = next(d for d, r in CONFIG["dias_extra"].items() if r == red)
    if dia_suyo != datetime.strptime(hoy, "%Y-%m-%d").date().weekday():
        print(f"⏰ El extra de {red} era el {DIAS[dia_suyo]} y no salió. "
              f"Se recupera hoy.")

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
    futuros = [f for f in cal if f.get("fecha", "") > hoy]
    atrasados = pendientes(hoy)
    print(f"📹 Reels: {len(atrasados)} pendiente(s), {len(futuros)} programado(s)")
    for f in atrasados:
        dias = (datetime.strptime(hoy, "%Y-%m-%d").date()
                - datetime.strptime(f["fecha"], "%Y-%m-%d").date()).days
        print(f"   ⏰ {f['fecha']}  {f['proyecto']:<12} atrasado {dias} día(s)")
    for f in futuros[:4]:
        marca = "⚠️ " if (f.get("revisar_a_mano") or "").upper().startswith("SÍ") else "  "
        print(f"   {marca} {f['fecha']} {f['hora']}  {f['proyecto']}")
    if len(futuros) > 4:
        print(f"      … y {len(futuros) - 4} más")
    if cal and not futuros and not atrasados:
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
        _sin_reventar(publicar_reel, hoy, args.dry_run)
    elif args.extras:
        _sin_reventar(publicar_extra, hoy, args.dry_run)
    else:
        p.print_help()


def _sin_reventar(fn, hoy: str, dry_run: bool) -> None:
    """Deja que un fallo de red muera con una línea, no con un traceback.

    ⚠️ Esto corre bajo `cron` y su salida acaba en `logs/agenda.log`. El 27 ago
    una caída de DNS a mitad de `subir_foto_staging()` soltó 20 líneas de
    traceback ahí dentro; el fallo era transitorio y la recuperación ya estaba
    resuelta —lo que no salió hoy vuelve a estar pendiente mañana— pero el log
    quedó ilegible justo el día que había que leerlo.

    Se traga solo lo que es de red. Un `SystemExit` (falta el token, no existe
    el vídeo) sigue saliendo entero: eso no se arregla esperando a mañana.
    """
    import requests
    try:
        fn(hoy, dry_run=dry_run)
    except requests.exceptions.RequestException as exc:
        print(f"🌐 Falló la red ({type(exc).__name__}). No se publicó nada; "
              f"mañana vuelve a intentarlo solo.")


if __name__ == "__main__":
    main()
