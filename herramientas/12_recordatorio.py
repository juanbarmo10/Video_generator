#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
12_recordatorio.py — El recordatorio semanal por Telegram.

No es un paso del pipeline. Lo llama `cron` una vez por semana:

    # crontab -e   →   lunes a las 9:00
    0 9 * * 1  cd /home/juanb/video_generator && \\
               /home/juanb/miniforge3/envs/ai_video_bot/bin/python \\
               herramientas/12_recordatorio.py

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
    "nota_minima": 7,

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
    """
    flojos = []
    for archivo in Path(CONFIG["proyectos"]).glob("*/calidad_guion.json"):
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


def calendario_vencido(hoy: date) -> dict | None:
    """Videos cuya fecha pasó y que **siguen sin publicarse**.

    ⚠️ Desde que la agenda publica sola, una fecha pasada ya no es un aviso: lo
    normal es que esté publicada. Lo que importa es el cruce con
    `publicar/publicado.csv` — si algo lleva días vencido Y sin salir, es que
    `cron` no está corriendo o está fallando, y eso no se entera nadie porque el
    error se queda en `logs/agenda.log`.
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
    vencidos = []
    for fila in filas:
        crudo = (fila.get(columna) or "").strip()[:10]
        try:
            cuando = datetime.strptime(crudo, "%Y-%m-%d").date()
        except ValueError:
            continue
        proyecto = fila.get("proyecto")
        falta = any((proyecto, red) not in salidos
                    for red in ("instagram", "facebook"))
        if cuando < hoy and falta:
            vencidos.append(fila)

    if not vencidos:
        return None
    return {
        "nivel": "revisar",
        "texto": (f"<b>{len(vencidos)} video(s) vencidos y sin publicar</b> — "
                  f"el más viejo, {vencidos[0].get('proyecto')} del "
                  f"{vencidos[0].get(columna, '')[:10]}"),
        "accion": "Mira logs/agenda.log: la agenda no está saliendo",
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

def resumen_metricas() -> list[str]:
    """Las cifras de la semana, reusando el cálculo de 11_reporte.py.

    ⚠️ Se IMPORTA en vez de recalcular, y eso es deliberado: el informe filtra
    lo que no se puede comparar (acumulados entre lotes de edades muy
    distintas). Un resumen que rehiciera las cuentas por su cuenta acabaría
    mandando cada lunes un "+2493 % en vistas por día" que solo mide la
    antigüedad de los videos. El nombre del módulo empieza por dígito, así que
    no se puede `import` normal: hace falta `importlib`.
    """
    sys.path.insert(0, "herramientas")
    try:
        reporte = importlib.import_module("11_reporte")
    except ImportError:
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
        partes.append("<b>v2 frente a baseline</b> (solo lo comparable):")
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

    avisos = [a for a in (
        temas_caidos(),
        guiones_sin_revisar(),
        calendario_vencido(hoy),
        token_threads_caduca(hoy),
        metricas_viejas(hoy),
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
