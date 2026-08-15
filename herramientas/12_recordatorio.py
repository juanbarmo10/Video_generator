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
    "metricas": "metricas.csv",
    "proyectos": "proyectos",
    "videos": "videos",
    "informe": "reportes/ultimo.html",

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
    """Videos empaquetados cuya fecha de publicación ya pasó."""
    filas = _filas_csv(CONFIG["calendario"])
    if not filas:
        return None

    columna = next((c for c in ("fecha", "Fecha", "fecha_publicacion")
                    if filas and c in filas[0]), None)
    if not columna:
        return None

    vencidos = []
    for fila in filas:
        crudo = (fila.get(columna) or "").strip()[:10]
        try:
            cuando = datetime.strptime(crudo, "%Y-%m-%d").date()
        except ValueError:
            continue
        if cuando < hoy:
            vencidos.append(fila)

    if not vencidos:
        return None
    return {
        "nivel": "revisar",
        "texto": (f"<b>{len(vencidos)} videos con fecha ya pasada</b> en "
                  f"publicar/calendario.csv"),
        "accion": "Comprueba en Metricool que se subieron de verdad",
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
    args = parser.parse_args()

    hoy = date.today()
    print("═" * 62)
    print(f"🔔 Recordatorio semanal · {hoy.isoformat()}")
    print("═" * 62)

    avisos = [a for a in (
        temas_caidos(),
        guiones_sin_revisar(),
        calendario_vencido(hoy),
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

    enviar(mensaje)


if __name__ == "__main__":
    main()
