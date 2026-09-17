#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
12_recordatorio.py — El recordatorio semanal por Telegram.

No es un paso del pipeline. Lo llama `cron`, con **tres entradas y un solo
mensaje** (las de verdad instaladas, no un ejemplo):

    0 10 * * 0    herramientas/12_recordatorio.py
    0 16 * * 0    herramientas/12_recordatorio.py
    0 10 * * 1-6  herramientas/12_recordatorio.py --si-falta

⚠️ **La semana empieza el DOMINGO** (`dia_inicio_semana`, 6), que es cuando corre
el aviso principal; el `--si-falta` de lunes a sábado solo cubre el domingo con
el equipo apagado y no hace nada si ya se envió algo esa semana. Si mueves el
cron a otro día, mueve `dia_inicio_semana` con él o la recuperación cuenta mal
la semana.

**No es una alarma: mira el estado real del repositorio y solo habla si hay algo
que decir.** Un recordatorio fijo que dice lo mismo todos los lunes se ignora a
la tercera semana; uno que dice "quedan 2 temas caídos sin reintentar" no.

Todo lo que comprueba son archivos que ya existen —`logs/failed.csv`,
`publicar/calendario.csv`, `metricas.csv`, los `calidad_guion.json`— así que no
consulta ninguna API salvo la de Telegram para enviar.

    python herramientas/12_recordatorio.py              # envía (o imprime si no hay claves)
    python herramientas/12_recordatorio.py --dry-run    # solo imprime, nunca envía
    python herramientas/12_recordatorio.py --siempre    # envía aunque no haya nada urgente

Alta del bot, una vez: hablarle a `@BotFather` → `/newbot` → guardar el token.
El `chat_id` sale de escribirle al bot y abrir
`https://api.telegram.org/bot<TOKEN>/getUpdates`.

⚠️ El token es una credencial: va en el `.env` (que está en `.gitignore`), nunca
en el código. Y el `chat_id` es fijo a propósito — un bot que conteste a quien
le escriba es un bot con el que cualquiera puede leer tus métricas.

⚠️ Se ejecuta desde la RAÍZ del proyecto, no desde `herramientas/`.
"""

#%% ══════════════════════════════════════════════════════════════════════
#   IMPORTS Y CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════

import argparse
import csv
import importlib
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

CONFIG = {
    "temas": "temas.csv",
    "fallidos": "logs/failed.csv",
    "calendario": "publicar/calendario.csv",
    "publicado": "publicar/publicado.csv",
    "metricas": "metricas.csv",
    "proyectos": "proyectos",
    "videos": "videos",
    "informe": "reportes/ultimo.html",

    # Fecha del último envío conseguido. Lo usa `--si-falta` para no repetir el
    # aviso de una semana que ya se dio. Está en .gitignore: es estado local.
    "marca_envio": ".ultimo_recordatorio",

    # Qué día empieza la semana, para "¿ya avisé esta semana?". 6 = domingo en
    # la numeración de Python (lunes=0), que es cuando corre el aviso principal.
    # Si mueves el cron a otro día, mueve esto con él.
    "dia_inicio_semana": 6,

    # Días sin consolidar métricas antes de avisar. Una semana: el ciclo es semanal.
    "dias_metricas_viejas": 7,

    # Nota de calidad del guion por debajo de la cual conviene leerlo antes de
    # publicar. Es la escala 0-10 que devuelve el crítico del paso 01.
    # ⚠️ Tiene que ser la MISMA que `nota_minima` del paso 01 (6). Estuvo en 7
    # hasta el 16 sep, así que marcaba "por revisar" justo los guiones que la
    # puerta aprueba — y como la mitad del lote sale con 6, el aviso llegaba
    # cada domingo con media tanda dentro y se volvía ruido.
    "nota_minima": 6,

    # A qué redes subes el reel a mano, por Metricool. Es lo que se cruza con
    # `publicado.csv` para saber qué falta.
    "redes_a_mano": ["instagram", "facebook", "youtube", "tiktok"],

    # Cuántos videos subes por semana de verdad. El calendario reparte uno al
    # día, pero el ritmo real son 5-6, así que a mitad de semana siempre habrá
    # uno o dos "vencidos" que no son ningún problema.
    # ⚠️ Sin esto el domingo avisaría todas las semanas de un atraso normal, y un
    # aviso que salta siempre se aprende a ignorar.
    "ritmo_semanal": 6,

    # Días tras publicar en que ya vale la pena medir. En Instagram el reel se
    # congela hacia el día 5 (P-34: Historia07 tenía 192 vistas a los 9 días y
    # las mismas 192 a los 30), así que esperar más no añade nada.
    "dias_hasta_medir": 5,

    "timeout_s": 20,
}

# Cuánto se destaca cada aviso. El orden es el del mensaje.
NIVELES = {"bloquea": "🔴", "revisar": "🟠", "toca": "🔵", "info": "ℹ️"}


#%% ══════════════════════════════════════════════════════════════════════
#   ¿YA AVISÉ ESTA SEMANA?
# ═══════════════════════════════════════════════════════════════════════

def inicio_de_semana(hoy: date) -> date:
    """El último `dia_inicio_semana` (domingo por defecto), hoy incluido."""
    from datetime import timedelta
    retroceso = (hoy.weekday() - CONFIG["dia_inicio_semana"]) % 7
    return hoy - timedelta(days=retroceso)


def ya_avise_esta_semana(hoy: date) -> bool:
    marca = Path(CONFIG["marca_envio"])
    if not marca.exists():
        return False
    try:
        ultimo = datetime.strptime(marca.read_text(encoding="utf-8").strip(),
                                   "%Y-%m-%d").date()
    except (ValueError, OSError):
        return False
    return ultimo >= inicio_de_semana(hoy)


def anotar_envio(hoy: date) -> None:
    """Deja constancia del envío conseguido.

    Solo se llama cuando Telegram confirma: si se anotara al intentarlo, una
    caída de red el domingo marcaría la semana como avisada y la recuperación
    de los días siguientes no dispararía — justo el caso para el que existe.
    """
    try:
        Path(CONFIG["marca_envio"]).write_text(hoy.isoformat(), encoding="utf-8")
    except OSError:
        pass


#%% ══════════════════════════════════════════════════════════════════════
#   COMPROBACIONES SOBRE EL ESTADO DEL REPOSITORIO
# ═══════════════════════════════════════════════════════════════════════

def _filas_csv(ruta: str) -> list[dict]:
    archivo = Path(ruta)
    if not archivo.exists():
        return []
    with archivo.open(encoding="utf-8") as fh:
        return list(csv.DictReader(fh))


def temas_caidos() -> dict | None:
    """¿Quedaron temas sin video en el último lote?

    `logs/failed.csv` se escribe CON encabezado precisamente para poder reusarlo
    tal cual como `temas.csv` (ver la trampa 10 de CLAUDE.md), así que aquí se
    lee igual que cualquier otro csv del proyecto.
    """
    filas = [f for f in _filas_csv(CONFIG["fallidos"])
             if (f.get("PROYECTO") or "").strip()]
    if not filas:
        return None

    nombres = ", ".join(f["PROYECTO"] for f in filas[:5])
    if len(filas) > 5:
        nombres += f" y {len(filas) - 5} más"
    return {
        "nivel": "bloquea",
        "texto": f"<b>{len(filas)} temas sin video</b>: {nombres}",
        "accion": "cp logs/failed.csv temas.csv && bash run_all.sh",
    }


def guiones_sin_revisar() -> dict | None:
    """Guiones que no pasaron el control de calidad y siguen sin publicar.

    El paso 01 deja su veredicto en `proyectos/<PROYECTO>/calidad_guion.json`.
    Un guion no aprobado no es un fallo del pipeline —el crítico está haciendo
    su trabajo— pero conviene leerlo antes de que salga a cuatro redes.

    ⚠️ **"Y siguen sin publicar" no se comprobaba**, y eso convertía el aviso en
    ruido permanente: el domingo listaba 12 guiones de agosto con nota 3 y 4 que
    llevaban un mes publicados y sobre los que ya no se puede hacer nada. Un
    aviso que no se puede atender se aprende a ignorar, y entonces tampoco se
    lee el día que trae uno de verdad.
    Se descartan los que ya salieron, por dos señales: el registro de
    publicación y —para los anteriores a que el registro existiera— tener
    métricas, que solo las tiene un video que se publicó.
    ⚠️ Los veredictos viejos además se juzgaron con el crítico ANTERIOR al
    16 sep, que penalizaba por no llevar fechas (P-36). Sus notas no son
    comparables con las de hoy, otra razón para no arrastrarlos.
    """
    ya_salieron = {(f.get("proyecto") or "").strip()
                   for f in _filas_csv(CONFIG["publicado"])}
    ya_salieron |= {(f.get("PROYECTO") or "").strip()
                    for f in _filas_csv(CONFIG["metricas"])}
    ya_salieron.discard("")

    flojos = []
    for archivo in Path(CONFIG["proyectos"]).glob("*/calidad_guion.json"):
        if archivo.parent.name in ya_salieron:
            continue
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        nota = datos.get("nota")
        aprobado = datos.get("aprobado")
        if aprobado is False or (isinstance(nota, (int, float))
                                 and nota < CONFIG["nota_minima"]):
            flojos.append((archivo.parent.name, nota))

    if not flojos:
        return None

    flojos.sort(key=lambda x: (x[1] is None, x[1]))
    detalle = ", ".join(f"{p} ({n}/10)" if n is not None else p
                        for p, n in flojos[:5])
    if len(flojos) > 5:
        detalle += f" y {len(flojos) - 5} más"
    return {
        "nivel": "revisar",
        "texto": f"<b>{len(flojos)} guiones no pasaron el control</b>: {detalle}",
        "accion": "Léelos antes de programarlos — suele ser el tema, no el paso 01",
    }


def pendientes_de_subir(hoy: date) -> dict | None:
    """Videos cuya fecha pasó y que **no constan como subidos**.

    ⚠️ Cambió de sentido el 16 sep, y el aviso viejo daba un consejo FALSO.
    Cuando la agenda publicaba sola, una fecha vencida y sin salir significaba
    que `cron` no corría, y el aviso decía "mira logs/agenda.log". Desde que se
    sube todo a mano por Metricool eso ya no publica nada, así que el consejo
    mandaba a mirar un log que no tiene la respuesta.

    ⚠️ Y el registro dejó de crecer: `publicado.csv` lo escribía la agenda al
    confirmar la red. Sin `16_agenda.py --marcar`, aquí sale TODO como
    pendiente para siempre.

    ⚠️ Tolera el ritmo real (`ritmo_semanal`). El calendario reparte uno al día
    pero se suben 5-6 por semana, así que a mitad de semana sobra siempre algún
    vencido. Avisar de eso cada domingo es enseñar a ignorar el aviso.
    """
    filas = _filas_csv(CONFIG["calendario"])
    if not filas:
        return None

    columna = next((c for c in ("fecha", "Fecha", "fecha_publicacion")
                    if filas and c in filas[0]), None)
    if not columna:
        return None

    salidos = {(f.get("proyecto"), f.get("red"))
               for f in _filas_csv(CONFIG["publicado"])}
    redes = CONFIG["redes_a_mano"]
    vencidos = []
    for fila in filas:
        crudo = (fila.get(columna) or "").strip()[:10]
        try:
            cuando = datetime.strptime(crudo, "%Y-%m-%d").date()
        except ValueError:
            continue
        proyecto = fila.get("proyecto")
        if cuando < hoy and any((proyecto, red) not in salidos for red in redes):
            vencidos.append((cuando, proyecto))

    # El desfase que el propio ritmo explica: publicar 6 de cada 7 días deja
    # ~1 pendiente por semana transcurrida. Se tolera el doble antes de avisar.
    holgura = max(2, round(2 * (7 - CONFIG["ritmo_semanal"])))
    if len(vencidos) <= holgura:
        return None

    vencidos.sort()
    nombres = ", ".join(p for _, p in vencidos[:4])
    if len(vencidos) > 4:
        nombres += f" y {len(vencidos) - 4} más"
    return {
        "nivel": "toca",
        "texto": (f"<b>{len(vencidos)} sin subir o sin anotar</b> — "
                  f"el más viejo, {vencidos[0][1]} del {vencidos[0][0].isoformat()}: "
                  f"{nombres}"),
        "accion": ("Súbelos por Metricool y luego: "
                   "python herramientas/16_agenda.py --marcar " +
                   " ".join(p for _, p in vencidos[:4])),
    }


def toca_medir(hoy: date) -> dict | None:
    """Videos subidos hace ya bastante y sin medir desde entonces.

    ⚠️ Es **lo que hay que hacer DESPUÉS de subir**, que es justo el paso que se
    olvida: subir deja el trabajo a medias si nadie recoge el resultado. En
    cuatro meses solo hubo 4 fotos en `metricas.csv` y un hueco de 21 días, y un
    experimento sin medir a tiempo no se puede leer nunca (P-35).

    ⚠️ El umbral son `dias_hasta_medir` (5), no una semana, porque el reel de
    Instagram **se congela hacia el día 5**: medir antes da un número a medias y
    medir mucho después no añade nada.
    """
    publicados = []
    for f in _filas_csv(CONFIG["publicado"]):
        try:
            publicados.append(datetime.strptime(
                (f.get("fecha") or "").strip()[:10], "%Y-%m-%d").date())
        except ValueError:
            continue
    if not publicados:
        return None

    fotos = []
    for f in _filas_csv(CONFIG["metricas"]):
        try:
            fotos.append(datetime.strptime(
                (f.get("fecha_snapshot") or "").strip(), "%Y-%m-%d").date())
        except ValueError:
            continue
    ultima_foto = max(fotos) if fotos else None

    # Los que ya maduraron y se publicaron DESPUÉS de la última foto.
    maduros = [d for d in publicados
               if (hoy - d).days >= CONFIG["dias_hasta_medir"]
               and (ultima_foto is None or d > ultima_foto)]
    if not maduros:
        return None
    return {
        "nivel": "toca",
        "texto": (f"<b>{len(maduros)} publicación(es) ya maduras y sin medir</b> "
                  f"(la última foto es del "
                  f"{ultima_foto.isoformat() if ultima_foto else 'nunca'})"),
        "accion": ("Baja los exports —incluido el de YouTube, que la API NO trae "
                   "se_quedaron_pct— y corre 10_metricas.py + 11_reporte.py"),
    }


def token_threads_caduca(hoy: date) -> dict | None:
    """El token de Threads dura 60 días y **muere en silencio**.

    ⚠️ Es el único de los tres que caduca: el de la página de Facebook no
    caduca y el de YouTube se refresca solo. Si este muere, el hilo del sábado
    deja de salir sin que nada avise, porque el fallo se queda en el log.
    Renovarlo es un comando y solo funciona **mientras siga vivo**.
    """
    crudo = os.getenv("THREADS_TOKEN_CADUCA", "").strip()
    if not crudo:
        return None
    try:
        cuando = date.fromisoformat(crudo)
    except ValueError:
        return None
    dias = (cuando - hoy).days
    if dias > 14:
        return None
    return {
        "nivel": "bloquea" if dias < 0 else "revisar",
        "texto": (f"<b>El token de Threads {'caducó' if dias < 0 else 'caduca'} "
                  f"el {crudo}</b>" + (f" (en {dias} días)" if dias >= 0 else "")),
        "accion": ("Repite el alta entera: README, punto 7" if dias < 0 else
                   "python herramientas/15_threads_api.py --diagnostico --escribir-env"),
    }


def metricas_viejas(hoy: date) -> dict | None:
    """¿Cuánto hace que no se consolidan métricas?"""
    filas = _filas_csv(CONFIG["metricas"])
    fechas = []
    for fila in filas:
        try:
            fechas.append(datetime.strptime(
                (fila.get("fecha_snapshot") or "").strip(), "%Y-%m-%d").date())
        except ValueError:
            continue

    if not fechas:
        return {
            "nivel": "toca",
            "texto": "<b>No hay ninguna métrica consolidada todavía</b>",
            "accion": "python herramientas/10_metricas.py",
        }

    dias = (hoy - max(fechas)).days
    if dias < CONFIG["dias_metricas_viejas"]:
        return None
    return {
        "nivel": "toca",
        "texto": (f"<b>Últimas métricas de hace {dias} días</b> "
                  f"({max(fechas).isoformat()})"),
        "accion": "Descarga los exports y corre 10_metricas.py + 11_reporte.py",
    }


def temas_ya_usados() -> dict | None:
    """¿`temas.csv` sigue teniendo la lista del lote anterior, ya generada?"""
    filas = [f for f in _filas_csv(CONFIG["temas"])
             if (f.get("PROYECTO") or "").strip()]
    if not filas:
        return {
            "nivel": "toca",
            "texto": "<b>temas.csv está vacío</b>",
            "accion": "Elige los temas de la semana (ver INSTRUCCIONES_CHATGPT.md)",
        }

    ya_hechos = [f["PROYECTO"] for f in filas
                 if Path(CONFIG["videos"], f"video_{f['PROYECTO']}.mp4").exists()]
    if len(ya_hechos) < len(filas):
        return None
    return {
        "nivel": "toca",
        "texto": (f"<b>Los {len(filas)} temas de temas.csv ya tienen video</b> — "
                  "toca elegir los de esta semana"),
        "accion": "Pídeselos a ChatGPT con INSTRUCCIONES_CHATGPT.md y pégalos en temas.csv",
    }


#%% ══════════════════════════════════════════════════════════════════════
#   RESUMEN DE MÉTRICAS
# ═══════════════════════════════════════════════════════════════════════

def _reporte():
    """Importa `11_reporte.py` **ya sincronizado** con el paso 10, o None.

    ⚠️ El `sincronizar_lotes()` no es opcional y saltárselo costó un fallo real.
    `resumen_metricas()` importaba el módulo y calculaba directamente, así que
    usaba el `lote_nuevo` **por defecto del archivo** —congelado en
    `v3-guion-y-dispersion`— mientras el paso 10 ya iba por v5. El domingo salían
    números de una tanda bajo el título de otra, que es exactamente la mentira
    silenciosa contra la que se escribió `sincronizar_lotes()`.
    Por eso el import y la sincronización van juntos en un solo sitio: quien
    quiera el módulo lo pide aquí y no puede olvidarse.
    """
    sys.path.insert(0, "herramientas")
    try:
        reporte = importlib.import_module("11_reporte")
    except ImportError:
        return None
    if hasattr(reporte, "sincronizar_lotes"):
        try:
            reporte.sincronizar_lotes()
        except Exception:
            pass
    return reporte


def _lote_nuevo() -> str:
    """Cómo se llama la tanda en curso. No se escribe aquí: se pregunta.

    ⚠️ Estuvo clavado en "v2" en el texto del mensaje hasta el 16 sep, con el
    proyecto ya en v5: el domingo llevaba meses titulando mal la tabla.
    """
    reporte = _reporte()
    return reporte.CONFIG.get("lote_nuevo", "lote nuevo") if reporte else "lote nuevo"


def resumen_metricas() -> list[str]:
    """Las cifras de la semana, reusando el cálculo de 11_reporte.py.

    ⚠️ Se IMPORTA en vez de recalcular, y eso es deliberado: el informe filtra
    lo que no se puede comparar (acumulados entre lotes de edades muy
    distintas). Un resumen que rehiciera las cuentas por su cuenta acabaría
    mandando cada lunes un "+2493 % en vistas por día" que solo mide la
    antigüedad de los videos. El nombre del módulo empieza por dígito, así que
    no se puede `import` normal: hace falta `importlib`.
    """
    reporte = _reporte()
    if reporte is None:
        return []

    try:
        filas = reporte.leer_metricas(reporte.CONFIG["metricas"])
    except SystemExit:
        return []

    reporte.calcular_derivadas(filas, date.today())

    lineas = []
    for plataforma in sorted(reporte.COLUMNAS_POR_PLATAFORMA):
        validas = [
            c for c in (reporte.comparar_lotes(filas, plataforma, campo)
                        for campo in reporte.COLUMNAS_POR_PLATAFORMA[plataforma])
            if c and c["comparable"] and c["fiable"]
        ]
        if not validas:
            continue
        # La de mayor movimiento, que es la que dice algo en una línea.
        c = max(validas, key=lambda x: abs(x["cambio_pct"]))
        flecha = "📈" if c["mejora"] else "📉"
        etiqueta = reporte.ETIQUETAS.get(c["campo"], c["campo"])
        lineas.append(f"{flecha} <b>{plataforma}</b> · {etiqueta}: "
                      f"{c['cambio_pct']:+.0f}% (n={c['nuevo']['n']} vs {c['base']['n']})")
    return lineas


#%% ══════════════════════════════════════════════════════════════════════
#   MENSAJE Y ENVÍO
# ═══════════════════════════════════════════════════════════════════════

def construir_mensaje(avisos: list[dict], metricas: list[str], hoy: date) -> str:
    partes = [f"🏭 <b>Fábrica de videos</b> · {hoy.strftime('%d %b %Y')}", ""]

    if avisos:
        for aviso in avisos:
            partes.append(f"{NIVELES.get(aviso['nivel'], 'ℹ️')} {aviso['texto']}")
            if aviso.get("accion"):
                partes.append(f"    <code>{aviso['accion']}</code>")
        partes.append("")
    else:
        partes += ["✅ Nada pendiente: sin temas caídos, sin guiones por revisar "
                   "y las métricas al día.", ""]

    if metricas:
        # ⚠️ El nombre del lote sale del paso 10, no se escribe aquí: estuvo
        # clavado en "v2" hasta el 16 sep, cuando ya iba por v5.
        partes.append(f"<b>{_lote_nuevo()} frente a baseline</b> "
                      f"(solo lo comparable):")
        partes += metricas
        partes.append("")
        partes.append(f"Informe completo: <code>{CONFIG['informe']}</code>")

    return "\n".join(partes).strip()


def enviar(mensaje: str) -> bool:
    """Manda el mensaje por Telegram. La API es un POST; no hace falta librería."""
    token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.getenv("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        print("⚠️  Sin TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID en el .env: no se envía.")
        print("    Se degrada a imprimir por consola, igual que el paso 01 sin")
        print("    ANTHROPIC_API_KEY. Para activarlo, habla con @BotFather.")
        return False

    try:
        import requests
    except ImportError:
        print("❌ Falta `requests` (está en requirements.txt).")
        return False

    try:
        respuesta = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": mensaje,
                  "parse_mode": "HTML", "disable_web_page_preview": True},
            timeout=CONFIG["timeout_s"],
        )
    except Exception as error:                     # red caída, DNS, timeout…
        print(f"❌ No se pudo contactar con Telegram: {error}")
        return False

    if respuesta.status_code != 200:
        # ⚠️ El cuerpo del error de Telegram NO lleva el token, pero la URL sí:
        # se imprime solo la descripción para no filtrarlo a los logs de cron.
        detalle = ""
        try:
            detalle = respuesta.json().get("description", "")
        except ValueError:
            pass
        print(f"❌ Telegram respondió {respuesta.status_code}: {detalle}")
        return False

    print("✅ Recordatorio enviado.")
    return True


#%% ══════════════════════════════════════════════════════════════════════
#   MAIN
# ═══════════════════════════════════════════════════════════════════════

def main() -> None:
    parser = argparse.ArgumentParser(description="Recordatorio semanal por Telegram")
    parser.add_argument("--dry-run", action="store_true",
                        help="imprime el mensaje y no envía nada")
    parser.add_argument("--siempre", action="store_true",
                        help="envía aunque no haya ningún aviso")
    parser.add_argument("--si-falta", action="store_true",
                        help="no hace nada si ya se envió algo esta semana "
                             "(para la recuperación diaria: cubre el domingo "
                             "que tuviste el equipo apagado)")
    args = parser.parse_args()

    hoy = date.today()
    print("═" * 62)
    print(f"🔔 Recordatorio semanal · {hoy.isoformat()}")
    print("═" * 62)

    if args.si_falta and ya_avise_esta_semana(hoy):
        print(f"😴 Ya se avisó esta semana (desde {inicio_de_semana(hoy)}): "
              f"nada que hacer.")
        return

    # ⚠️ `toca_medir()` y `metricas_viejas()` dicen casi lo mismo por dos
    # caminos: "hay publicaciones maduras sin medir" y "hace mucho que no
    # consolidas". Cuando las dos saltan, la segunda sobra — el aviso específico
    # ya trae el comando. Dos líneas para una sola acción es como se erosiona la
    # costumbre de leer el mensaje.
    medir = toca_medir(hoy)
    avisos = [a for a in (
        temas_caidos(),
        guiones_sin_revisar(),
        pendientes_de_subir(hoy),
        token_threads_caduca(hoy),
        medir or metricas_viejas(hoy),
        temas_ya_usados(),
    ) if a]

    orden = list(NIVELES)
    avisos.sort(key=lambda a: orden.index(a["nivel"]))

    metricas = resumen_metricas()
    mensaje = construir_mensaje(avisos, metricas, hoy)

    print(mensaje.replace("<b>", "").replace("</b>", "")
                 .replace("<code>", "").replace("</code>", ""))
    print("─" * 62)

    if args.dry_run:
        print("🧪 --dry-run: no se envía.")
        return

    # Sin avisos y sin --siempre no se manda nada: un bot que escribe cada lunes
    # aunque no pase nada se acaba silenciando, y entonces tampoco avisa el día
    # que sí importa.
    if not avisos and not args.siempre:
        print("😴 Nada urgente que contar: no se envía (usa --siempre para forzarlo).")
        return

    if enviar(mensaje):
        anotar_envio(hoy)


if __name__ == "__main__":
    main()
