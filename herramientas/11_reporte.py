#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
11_reporte.py — Convierte metricas.csv en un informe que se puede leer.

No es un paso del pipeline: se corre a mano cuando hay métricas nuevas, después
de `herramientas/10_metricas.py`.

    python herramientas/11_reporte.py

Lee `metricas.csv` (147 filas × 28 columnas que nadie va a mirar en un CSV) y
escribe un HTML autocontenido en `reportes/`. Sin dependencias: solo stdlib, y
el CSS va incrustado, así que el archivo se abre con doble clic, se manda por
Telegram o se guarda como registro de la semana.

Tres ideas de diseño, que son las que lo hacen útil:

1. **Una sección por plataforma, cada una con SUS columnas.** Ninguna red
   exporta lo mismo: TikTok no da `alcance`, YouTube y TikTok no dan
   `guardados`, `ctr_pct` solo existe en YouTube. Una tabla común sería un mar
   de celdas vacías, así que el mapeo es explícito (`COLUMNAS_POR_PLATAFORMA`),
   igual que `FUENTES` en el paso 10.

2. **Todo se compara por MEDIANA y con el tamaño de muestra al lado.** Con
   n=6 en el lote nuevo, un promedio lo decide un solo video viral. Y una
   mediana sin la n invita a concluir de más, que es peor que no tener informe.

3. **Métricas derivadas**, que dicen más que las crudas y salen de lo que ya
   hay: `vistas_por_dia` (quita el sesgo de antigüedad), `tasa_guardado`,
   `engagement` (comparable entre redes) y `retencion_relativa`.

⚠️ Se ejecuta desde la RAÍZ del proyecto, no desde `herramientas/`.
"""

#%% ══════════════════════════════════════════════════════════════════════
#   IMPORTS Y CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════════════

import csv
import importlib.util
import html
import statistics
import sys
from datetime import date, datetime
from pathlib import Path

CONFIG = {
    "metricas": "metricas.csv",
    "dir_reportes": "reportes",

    # ⚠️ **No se tocan a mano: los lee del paso 10 al arrancar** (ver
    # `sincronizar_lotes()`). Tenerlos duplicados fue un fallo silencioso real:
    # el paso 10 etiquetaba `v3-guion-y-dispersion` y aquí seguía puesto
    # `v2-mas-cortes`, así que el lote nuevo **desaparecía del veredicto** sin
    # salir en ningún sitio —ni como nuevo ni como baseline— y el informe
    # comparaba la tanda anterior con toda naturalidad. Quedan aquí solo como
    # valor de respaldo por si el paso 10 no se puede importar.
    "lote_nuevo": "v3-guion-y-dispersion",
    "lote_baseline": "baseline",

    # Debajo de esta n, la comparación se marca como no concluyente. No la
    # esconde: la enseña con el aviso, porque el dato sigue sirviendo de indicio.
    "n_minimo_fiable": 5,

    # Cuántos videos entran en los rankings de mejor y peor.
    "top_n": 5,

    # El valor que el paso 10 escribe cuando esa red NO exporta ese campo.
    # No es lo mismo que vacío (que sería "lo exporta pero falta el dato").
    "marca_no_aplica": "—",
}

# ── Qué columnas tienen sentido en cada red ─────────────────────────────
# Explícito a propósito: se sabe qué exporta cada plataforma (está medido en
# README.md), así que no hay que adivinarlo mirando cuántas celdas vienen llenas.
COLUMNAS_POR_PLATAFORMA = {
    "youtube": [
        "vistas", "vistas_24h", "vistas_7d", "vistas_por_dia",
        "ctr_pct", "se_quedaron_pct", "retencion_pct", "retencion_relativa",
        "tiempo_total_h", "engagement",
    ],
    "tiktok": [
        "vistas", "vistas_por_dia", "se_quedaron_pct",
        "retencion_pct", "retencion_relativa", "engagement",
    ],
    "facebook": [
        "vistas", "alcance", "vistas_por_dia", "distribucion",
        "retencion_pct", "retencion_relativa",
        "guardados", "tasa_guardado", "engagement",
    ],
    "instagram": [
        "vistas", "alcance", "vistas_por_dia",
        "retencion_pct", "retencion_relativa",
        "guardados", "tasa_guardado", "compartidos", "engagement",
    ],
    # ⚠️ Threads es TEXTO: no hay duración, así que no hay retención ni
    # `se_quedaron_pct` ni `tiempo_total_h`. Tampoco alcance ni guardados — su
    # API no los da. Lo que sí tiene, y es justo lo que se quiere comparar con
    # las otras redes, es `vistas` y `engagement`.
    "threads": [
        "vistas", "vistas_por_dia", "me_gusta", "comentarios",
        "compartidos", "engagement",
    ],
}

# ── Cómo se comporta cada métrica con el paso del tiempo ────────────────
# ⚠️ Esto es lo que decide qué se puede comparar entre lotes, y no es un detalle:
# los videos del lote nuevo tienen 4 días y los del baseline 66. Comparar
# cualquier acumulado entre grupos de edades tan distintas mide la antigüedad,
# no la calidad del video.
#
#   acumulativa → crece mientras el video siga publicado (vistas, alcance…).
#                 NO comparable entre lotes de edades distintas.
#   ventana     → medida en una ventana fija desde la publicación (24 h, 7 d).
#                 Comparable siempre: la edad ya está igualada por construcción.
#   tasa        → un cociente cuyo numerador y denominador crecen juntos
#                 (retención, CTR, engagement). Se estabiliza pronto → comparable.
#   interna     → normalizada DENTRO de su propio lote. Compararla entre lotes
#                 daría 0 % siempre, por construcción. Nunca entra en el veredicto.
TIPO_METRICA = {
    "vistas": "acumulativa", "alcance": "acumulativa", "impresiones": "acumulativa",
    "guardados": "acumulativa", "compartidos": "acumulativa", "me_gusta": "acumulativa",
    "comentarios": "acumulativa", "tiempo_total_h": "acumulativa",
    "distribucion": "acumulativa", "vistas_interesadas": "acumulativa",
    # `vistas_por_dia` PARECE una tasa y no lo es: supone que las vistas se
    # acumulan de forma lineal, y en video social llegan casi todas en las
    # primeras 48 h. Dividir entre 4 días en vez de entre 66 no quita el sesgo
    # de antigüedad: lo invierte. Sirve para ordenar videos de edad parecida,
    # nunca para comparar lotes. Por eso está aquí y no entre las tasas.
    "vistas_por_dia": "acumulativa",

    "vistas_24h": "ventana", "vistas_7d": "ventana",

    "retencion_pct": "tasa", "se_quedaron_pct": "tasa", "ctr_pct": "tasa",
    "engagement": "tasa", "tasa_guardado": "tasa", "duracion_media_s": "tasa",

    "retencion_relativa": "interna",
}

# Cuánto pueden diferir las edades medianas de dos lotes antes de que un
# acumulado deje de ser comparable. 1.5× es holgado: hoy la diferencia es 16×.
FACTOR_EDAD_MAX = 1.5

# ── La métrica de cabecera de cada red ──────────────────────────────────
# YouTube es la única que trae una ventana fija (24 h), que es la comparación
# limpia. En el resto se ordena por vistas crudas y se enseña la edad al lado,
# porque no hay ninguna métrica de ventana que pedirles.
METRICA_PRINCIPAL = {
    "youtube": "vistas_24h",
    "tiktok": "vistas",
    "facebook": "vistas",
    "instagram": "vistas",
    "threads": "vistas",
}

ETIQUETAS = {
    "vistas": "Vistas",
    "vistas_24h": "Vistas 24 h",
    "vistas_7d": "Vistas 7 d",
    "vistas_por_dia": "Vistas/día",
    "vistas_interesadas": "Vistas interesadas",
    "alcance": "Alcance",
    "impresiones": "Impresiones",
    "ctr_pct": "CTR %",
    "retencion_pct": "Retención %",
    "retencion_relativa": "Ret. relativa",
    "duracion_media_s": "Dur. media (s)",
    "se_quedaron_pct": "Se quedaron %",
    "tiempo_total_h": "Horas vistas",
    "me_gusta": "Me gusta",
    "comentarios": "Comentarios",
    "compartidos": "Compartidos",
    "guardados": "Guardados",
    "tasa_guardado": "Tasa guardado %",
    "engagement": "Engagement %",
    "seguidores_ganados": "Seguidores",
    "interacciones": "Interacciones",
    "distribucion": "Distribución",
    "edad_dias": "Días publicado",
}

# Cuántos decimales enseñar. Lo que no esté aquí se muestra como entero.
DECIMALES = {
    "vistas_por_dia": 1, "ctr_pct": 2, "retencion_pct": 1,
    "retencion_relativa": 2, "duracion_media_s": 1, "se_quedaron_pct": 1,
    "tiempo_total_h": 1, "tasa_guardado": 2, "engagement": 2,
}

# En estas, MENOS es mejor. Hoy ninguna, pero la comparación pregunta por ello
# y dejarlo explícito evita que alguien invierta un signo sin darse cuenta.
MENOS_ES_MEJOR: set[str] = set()

DERIVADAS = ["vistas_por_dia", "tasa_guardado", "engagement", "retencion_relativa"]


#%% ══════════════════════════════════════════════════════════════════════
#   LECTURA Y NORMALIZACIÓN
# ═══════════════════════════════════════════════════════════════════════

def num(valor) -> float | None:
    """Convierte una celda a número, o None si no hay dato.

    Distingue tres cosas que en un CSV se parecen: la celda vacía (la red lo
    exporta pero falta), la marca `—` (esa red NO exporta ese campo) y el cero
    de verdad, que SÍ es un dato y no se puede tratar como ausente.
    """
    if valor is None:
        return None
    texto = str(valor).strip()
    if texto == "" or texto == CONFIG["marca_no_aplica"]:
        return None
    try:
        return float(texto.replace(",", "."))
    except ValueError:
        return None


def leer_metricas(ruta: str) -> list[dict]:
    archivo = Path(ruta)
    if not archivo.exists():
        print(f"❌ No encuentro '{ruta}'.")
        print("   Se genera con: python herramientas/10_metricas.py")
        sys.exit(1)

    with archivo.open(encoding="utf-8") as fh:
        filas = list(csv.DictReader(fh))

    if not filas:
        print(f"❌ '{ruta}' está vacío.")
        sys.exit(1)

    return filas


def dias_desde(fecha_iso: str, hasta: date) -> int | None:
    """Días entre una fecha ISO y otra. Mínimo 1, para no dividir entre cero."""
    try:
        publicado = datetime.strptime(str(fecha_iso).strip(), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None
    return max((hasta - publicado).days, 1)


def nombre_video(fila: dict) -> str:
    """Cómo llamar a un video en el informe.

    ⚠️ 78 de las 147 filas NO tienen PROYECTO (es P-14: los respaldos del lote
    viejo están en `proyectos/T1/<TEMA>/`, un nivel por debajo de donde busca el
    paso 10). Esas filas son el baseline, así que no se pueden descartar: se
    las llama por su título, recortado.
    """
    proyecto = str(fila.get("PROYECTO", "")).strip()
    if proyecto:
        return proyecto
    titulo = str(fila.get("titulo", "")).strip()
    return (titulo[:48] + "…") if len(titulo) > 48 else (titulo or "(sin nombre)")


#%% ══════════════════════════════════════════════════════════════════════
#   MÉTRICAS DERIVADAS
# ═══════════════════════════════════════════════════════════════════════

def calcular_derivadas(filas: list[dict], hoy: date) -> None:
    """Añade a cada fila las columnas que no vienen de ninguna red.

    Se calculan aquí y no en el paso 10 a propósito: dependen de `hoy`
    (`vistas_por_dia`) y de la mediana del conjunto (`retencion_relativa`), así
    que congelarlas en el CSV las dejaría desactualizadas al día siguiente.
    """
    # ── edad_dias y vistas_por_dia ────────────────────────────────────
    # La edad no es decorativa: es lo que decide qué comparaciones valen
    # (ver TIPO_METRICA). Se calcula primero porque todo lo demás la usa.
    for fila in filas:
        dias = dias_desde(fila.get("fecha_publicacion", ""), hoy)
        fila["edad_dias"] = dias if dias else ""
        vistas = num(fila.get("vistas"))
        # `vistas is not None`, no `if vistas`: cero vistas es un dato real y
        # dejarlo en blanco lo sacaría de las medianas, subiéndolas.
        fila["vistas_por_dia"] = (
            round(vistas / dias, 2) if (vistas is not None and dias) else ""
        )

    # ── tasa_guardado ─────────────────────────────────────────────────
    # En reels pesa más que los me gusta para que te repartan. Solo Facebook e
    # Instagram exportan `guardados`.
    for fila in filas:
        guardados, alcance = num(fila.get("guardados")), num(fila.get("alcance"))
        fila["tasa_guardado"] = (
            round(guardados / alcance * 100, 3) if (guardados is not None and alcance) else ""
        )

    # ── engagement ────────────────────────────────────────────────────
    # El denominador cambia por red y por eso se elige aquí: TikTok no exporta
    # `alcance`, así que allí se usa `vistas`. Mezclar las dos bases en la misma
    # columna la haría incomparable, de modo que queda anotado en el informe.
    for fila in filas:
        partes = [num(fila.get(c)) for c in
                  ("me_gusta", "comentarios", "compartidos", "guardados")]
        presentes = [p for p in partes if p is not None]
        base = num(fila.get("alcance")) or num(fila.get("vistas"))
        # Si NO hay ninguna señal, la fila no tiene el dato: en blanco. Sin esta
        # guarda, `sum([])` daba 0 y la fila entraba en la mediana como un
        # engagement del 0 %, que es un dato inventado y además tira la mediana
        # hacia abajo. Un cero de verdad (hay señales y suman 0) sí cuenta.
        fila["engagement"] = (
            round(sum(presentes) / base * 100, 3) if (presentes and base) else ""
        )

    # ── retencion_relativa ────────────────────────────────────────────
    # Contra la mediana de SU plataforma y SU lote: dice si un video es bueno
    # para este canal, no contra un estándar de internet que no aplica.
    referencias: dict[tuple, float] = {}
    for plataforma in {f["plataforma"] for f in filas}:
        for lote in {f.get("lote", "") for f in filas}:
            valores = [
                num(f.get("retencion_pct")) for f in filas
                if f["plataforma"] == plataforma and f.get("lote", "") == lote
            ]
            valores = [v for v in valores if v is not None]
            if valores:
                referencias[(plataforma, lote)] = statistics.median(valores)

    for fila in filas:
        retencion = num(fila.get("retencion_pct"))
        base = referencias.get((fila["plataforma"], fila.get("lote", "")))
        fila["retencion_relativa"] = (
            round(retencion / base, 3) if (retencion is not None and base) else ""
        )


#%% ══════════════════════════════════════════════════════════════════════
#   ESTADÍSTICA
# ═══════════════════════════════════════════════════════════════════════

def resumen(filas: list[dict], campo: str) -> dict | None:
    """Mediana + n de un campo. None si nadie tiene ese dato."""
    valores = [num(f.get(campo)) for f in filas]
    valores = [v for v in valores if v is not None]
    if not valores:
        return None
    return {
        "mediana": statistics.median(valores),
        "n": len(valores),
        "min": min(valores),
        "max": max(valores),
    }


def comparar_lotes(filas: list[dict], plataforma: str, campo: str) -> dict | None:
    """Compara `v2-mas-cortes` contra `baseline` en una métrica y una red.

    Devuelve la comparación SIEMPRE que haya datos en los dos lotes, pero marca
    en `comparable` si el número significa algo. Dos motivos para que no:

    - `interna`: la métrica ya está normalizada dentro de su lote, así que la
      comparación daría 0 % por construcción.
    - `acumulativa` con edades muy distintas: es el caso real de hoy. Los
      videos nuevos llevan 4 días publicados y los del baseline 66, así que
      cualquier acumulado del baseline lleva 16 veces más tiempo sumando.
      Decir "+2493 % en vistas por día" con esos datos es medir el calendario.

    No se ocultan: se enseñan aparte y con el motivo escrito. Un número que se
    esconde acaba recalculándose a mano y peor.
    """
    tipo = TIPO_METRICA.get(campo, "acumulativa")
    de_la_red = [f for f in filas if f["plataforma"] == plataforma]
    filas_nuevo = [f for f in de_la_red if f.get("lote") == CONFIG["lote_nuevo"]]
    filas_base = [f for f in de_la_red if f.get("lote") == CONFIG["lote_baseline"]]

    nuevo = resumen(filas_nuevo, campo)
    base = resumen(filas_base, campo)
    if not nuevo or not base or not base["mediana"]:
        return None

    edad_nuevo = resumen(filas_nuevo, "edad_dias")
    edad_base = resumen(filas_base, "edad_dias")

    comparable, motivo = True, ""
    if tipo == "interna":
        comparable = False
        motivo = "normalizada dentro de su propio lote"
    elif tipo == "acumulativa" and edad_nuevo and edad_base:
        menor = min(edad_nuevo["mediana"], edad_base["mediana"]) or 1
        factor = max(edad_nuevo["mediana"], edad_base["mediana"]) / menor
        if factor > FACTOR_EDAD_MAX:
            comparable = False
            motivo = (f"acumulado y las edades no se parecen "
                      f"({edad_nuevo['mediana']:.0f} d vs {edad_base['mediana']:.0f} d)")

    cambio = (nuevo["mediana"] - base["mediana"]) / abs(base["mediana"]) * 100
    mejora = cambio < 0 if campo in MENOS_ES_MEJOR else cambio > 0
    return {
        "campo": campo,
        "tipo": tipo,
        "nuevo": nuevo,
        "base": base,
        "edad_nuevo": edad_nuevo,
        "edad_base": edad_base,
        "cambio_pct": cambio,
        "mejora": mejora,
        "comparable": comparable,
        "motivo": motivo,
        "fiable": min(nuevo["n"], base["n"]) >= CONFIG["n_minimo_fiable"],
    }


def formato(valor, campo: str) -> str:
    """Número listo para la tabla, con los decimales que le tocan."""
    v = num(valor)
    if v is None:
        return '<span class="nd">—</span>'
    decimales = DECIMALES.get(campo, 0)
    if decimales == 0:
        return f"{v:,.0f}".replace(",", ".")
    return f"{v:,.{decimales}f}".replace(",", "@").replace(".", ",").replace("@", ".")


#%% ══════════════════════════════════════════════════════════════════════
#   CONSTRUCCIÓN DEL HTML
# ═══════════════════════════════════════════════════════════════════════

CSS = """
:root {
  --fondo:#f7f7f5; --papel:#fff; --tinta:#1b1b1a; --suave:#6b6b66;
  --linea:#e3e3de; --bien:#0d7a4a; --mal:#b32d2d; --ojo:#8a6d1f; --acento:#2f4858;
}
@media (prefers-color-scheme: dark) {
  :root { --fondo:#16181a; --papel:#1e2124; --tinta:#e8e8e4; --suave:#9a9a94;
          --linea:#31353a; --bien:#4ac48a; --mal:#ff7b7b; --ojo:#e0b849; --acento:#8fb3c9; }
}
* { box-sizing:border-box; }
body { margin:0; padding:2rem 1rem 4rem; background:var(--fondo); color:var(--tinta);
       font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif; }
.wrap { max-width:1080px; margin:0 auto; }
h1 { font-size:1.7rem; margin:0 0 .2rem; letter-spacing:-.02em; }
h2 { font-size:1.15rem; margin:2.6rem 0 .8rem; padding-bottom:.4rem;
     border-bottom:2px solid var(--linea); }
h3 { font-size:.95rem; margin:1.6rem 0 .5rem; color:var(--suave);
     text-transform:uppercase; letter-spacing:.06em; }
.sub { color:var(--suave); margin:0 0 1.5rem; font-size:.9rem; }
.tarjetas { display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:.7rem; }
.t { background:var(--papel); border:1px solid var(--linea); border-radius:9px; padding:.85rem 1rem; }
.t .k { font-size:.72rem; color:var(--suave); text-transform:uppercase; letter-spacing:.05em; }
.t .v { font-size:1.5rem; font-weight:600; margin-top:.15rem; letter-spacing:-.02em; }
.t .n { font-size:.72rem; color:var(--suave); margin-top:.15rem; }
.bien { color:var(--bien); } .mal { color:var(--mal); } .ojo { color:var(--ojo); }
.suave { color:var(--suave); }
.t.apagada { opacity:.72; border-style:dashed; }
.t .motivo { font-style:italic; margin-top:.3rem; }
.scroll { overflow-x:auto; background:var(--papel); border:1px solid var(--linea); border-radius:9px; }
table { border-collapse:collapse; width:100%; font-size:.86rem; }
th,td { padding:.5rem .7rem; text-align:right; white-space:nowrap;
        border-bottom:1px solid var(--linea); }
th { background:var(--fondo); font-size:.72rem; text-transform:uppercase;
     letter-spacing:.04em; color:var(--suave); position:sticky; top:0; }
th:first-child,td:first-child { text-align:left; }
tbody tr:last-child td { border-bottom:none; }
tbody tr:hover { background:var(--fondo); }
.nd { color:var(--linea); }
.pill { display:inline-block; padding:.1rem .5rem; border-radius:99px; font-size:.7rem;
        font-weight:600; border:1px solid currentColor; }
.aviso { background:var(--papel); border-left:3px solid var(--ojo); border-radius:0 8px 8px 0;
         padding:.8rem 1rem; margin:1rem 0; font-size:.87rem; }
.pie { margin-top:3rem; padding-top:1rem; border-top:1px solid var(--linea);
       color:var(--suave); font-size:.8rem; }
code { background:var(--fondo); padding:.1rem .35rem; border-radius:4px; font-size:.85em; }
"""


def esc(texto) -> str:
    return html.escape(str(texto))


def bloque_veredicto(filas: list[dict]) -> str:
    """Pregunta 1: ¿el lote nuevo sigue ganando al baseline?"""
    partes = ['<h2>1 · ¿Sigue ganando el lote nuevo?</h2>',
              f'<p class="sub">Mediana de <code>{esc(CONFIG["lote_nuevo"])}</code> frente a '
              f'<code>{esc(CONFIG["lote_baseline"])}</code>. '
              'Mediana y no promedio: con muestras así, un solo video viral movería la media.</p>']

    def tarjeta(c: dict, apagada: bool = False, prefijo: str = "") -> str:
        clase = "suave" if apagada else ("bien" if c["mejora"] else "mal")
        signo = "+" if c["cambio_pct"] >= 0 else ""
        duda = "" if c["fiable"] else ' <span class="ojo" title="muestra pequeña">⚠</span>'
        pie = (f'<div class="n motivo">no comparable: {esc(c["motivo"])}</div>'
               if apagada else "")
        titulo = ETIQUETAS.get(c["campo"], c["campo"])
        if prefijo:
            titulo = f"{prefijo} · {titulo}"
        return (
            f'<div class="t{" apagada" if apagada else ""}">'
            f'<div class="k">{esc(titulo)}</div>'
            f'<div class="v {clase}">{signo}{c["cambio_pct"]:.0f}%{duda}</div>'
            f'<div class="n">{formato(c["nuevo"]["mediana"], c["campo"])} '
            f'vs {formato(c["base"]["mediana"], c["campo"])}<br>'
            f'n={c["nuevo"]["n"]} vs {c["base"]["n"]}</div>{pie}</div>'
        )

    hubo_alguna, descartadas = False, []
    for plataforma in sorted(COLUMNAS_POR_PLATAFORMA):
        comparaciones = [
            c for c in (comparar_lotes(filas, plataforma, campo)
                        for campo in COLUMNAS_POR_PLATAFORMA[plataforma])
            if c
        ]
        validas = [c for c in comparaciones if c["comparable"]]
        descartadas += [(plataforma, c) for c in comparaciones if not c["comparable"]]
        if not validas:
            continue
        hubo_alguna = True
        partes.append(f'<h3>{esc(plataforma)}</h3><div class="tarjetas">')
        partes += [tarjeta(c) for c in validas]
        partes.append('</div>')

    if not hubo_alguna:
        partes.append('<div class="aviso">Todavía no hay ninguna métrica comparable '
                      'entre los dos lotes.</div>')
    else:
        partes.append(
            f'<div class="aviso">⚠ <b>Las marcadas con ⚠ tienen menos de '
            f'{CONFIG["n_minimo_fiable"]} videos en algún lado.</b> Son indicio, no conclusión: '
            'una diferencia del 40 % con n=3 cabe de sobra dentro del ruido. '
            'La n va escrita debajo de cada cifra justamente para que no se lea sin ella.</div>'
        )

    if descartadas:
        partes.append(
            '<h3>Fuera del veredicto</h3>'
            '<div class="aviso">📅 <b>Estas cifras miden el calendario, no el video.</b> '
            'Los videos del lote nuevo llevan unos días publicados y los del baseline, meses. '
            'Todo lo que se <i>acumula</i> mientras el video sigue online —vistas, alcance, '
            'guardados— favorece al que lleva más tiempo, y <code>vistas_por_dia</code> comete '
            'el error inverso: reparte entre pocos días unas vistas que en video social llegan '
            'casi todas en las primeras 48 h, así que dispara al lote nuevo. '
            'Se enseñan para que no se recalculen a mano, pero <b>no sostienen ninguna '
            'conclusión.</b><br><br>'
            'Lo único que compara de verdad un acumulado es una <b>ventana fija</b> '
            '(<code>vistas_24h</code>, <code>vistas_7d</code>), que hoy solo da YouTube, o '
            '<b>dos fotos</b> del paso 10 para restar el crecimiento del mismo periodo.</div>'
            '<div class="tarjetas">'
        )
        for plataforma, c in descartadas:
            partes.append(tarjeta(c, apagada=True, prefijo=plataforma))
        partes.append('</div>')

    return "\n".join(partes)


def bloque_ranking(filas: list[dict]) -> str:
    """Pregunta 2: ¿cuál fue el mejor y cuál el peor, y por qué métrica?"""
    partes = ['<h2>2 · Mejores y peores</h2>',
              '<p class="sub">YouTube se ordena por sus vistas de 24 h, que comparan videos a la '
              'misma edad. Las demás redes no dan ninguna ventana fija, así que se ordenan por '
              'vistas crudas <b>con los días publicados a la vista</b>: un video de 4 días y uno '
              'de 66 no compiten en igualdad, y eso tiene que verse en la tabla.</p>']

    for plataforma in sorted(COLUMNAS_POR_PLATAFORMA):
        campo = METRICA_PRINCIPAL[plataforma]
        candidatos = [f for f in filas
                      if f["plataforma"] == plataforma and num(f.get(campo)) is not None]
        if not candidatos:
            continue
        candidatos.sort(key=lambda f: num(f.get(campo)), reverse=True)
        # Por índice y no comparando las filas: dos videos con exactamente los
        # mismos números darían dicts iguales y `x in lista` los confundiría.
        tope = min(CONFIG["top_n"], len(candidatos))
        arriba = list(range(tope))
        abajo = [i for i in range(len(candidatos) - tope, len(candidatos))
                 if i not in arriba]
        seleccion = ([("🔼", candidatos[i]) for i in arriba] +
                     [("🔽", candidatos[i]) for i in abajo])

        # ⚠️ Las de retención solo si esa red las tiene. Threads es TEXTO: no hay
        # duración, así que serían dos columnas de guiones en todas sus filas —
        # el mar de celdas vacías que `COLUMNAS_POR_PLATAFORMA` existe para evitar.
        extra = [c for c in ("retencion_pct", "retencion_relativa")
                 if c in COLUMNAS_POR_PLATAFORMA[plataforma]]
        partes.append(
            f'<h3>{esc(plataforma)} · por {esc(ETIQUETAS.get(campo, campo))}</h3>'
            '<div class="scroll"><table><thead><tr>'
            '<th>Video</th><th>Lote</th>'
            f'<th>{esc(ETIQUETAS.get(campo, campo))}</th><th>Días pub.</th>'
            + "".join(f'<th>{esc(ETIQUETAS.get(c, c))}</th>' for c in extra)
            + '<th>Publicado</th></tr></thead><tbody>'
        )
        for marca, f in seleccion:
            es_nuevo = f.get("lote") == CONFIG["lote_nuevo"]
            pill = ('<span class="pill bien">v2</span>' if es_nuevo
                    else '<span class="pill">base</span>')
            partes.append(
                f'<tr><td>{marca} {esc(nombre_video(f))}</td><td>{pill}</td>'
                f'<td>{formato(f.get(campo), campo)}</td>'
                f'<td>{formato(f.get("edad_dias"), "edad_dias")}</td>'
                + "".join(f'<td>{formato(f.get(c), c)}</td>' for c in extra)
                + f'<td>{esc(f.get("fecha_publicacion", ""))}</td></tr>'
            )
        partes.append('</tbody></table></div>')
    return "\n".join(partes)


def bloque_se_quedaron(filas: list[dict]) -> str:
    """Pregunta 3: la única métrica que iba en contra (P-12)."""
    partes = ['<h2>3 · <code>se_quedaron_pct</code>, la que iba en contra</h2>',
              '<p class="sub">Es el pendiente P-12: la única métrica que empeoró al pasar al '
              'lote nuevo. Mide cuántos no se van en los primeros segundos, así que es el '
              'termómetro del gancho — y de los primeros cortes.</p>']

    filas_utiles = []
    for plataforma in ("youtube", "tiktok"):     # las dos únicas que la exportan
        comparacion = comparar_lotes(filas, plataforma, "se_quedaron_pct")
        if comparacion:
            filas_utiles.append((plataforma, comparacion))

    if not filas_utiles:
        partes.append('<div class="aviso">Ninguna red tiene todavía el dato en los dos lotes.</div>')
        return "\n".join(partes)

    partes.append('<div class="tarjetas">')
    for plataforma, c in filas_utiles:
        clase = "bien" if c["mejora"] else "mal"
        signo = "+" if c["cambio_pct"] >= 0 else ""
        partes.append(
            f'<div class="t"><div class="k">{esc(plataforma)}</div>'
            f'<div class="v {clase}">{signo}{c["cambio_pct"]:.0f}%</div>'
            f'<div class="n">{formato(c["nuevo"]["mediana"], "se_quedaron_pct")} % '
            f'vs {formato(c["base"]["mediana"], "se_quedaron_pct")} %<br>'
            f'n={c["nuevo"]["n"]} vs {c["base"]["n"]}</div></div>'
        )
    partes.append('</div>')

    empeora = any(not c["mejora"] for _, c in filas_utiles)
    if empeora:
        partes.append(
            '<div class="aviso">📉 <b>Sigue por debajo.</b> Lo que no se puede saber desde aquí '
            'es <i>dónde</i> se van, y eso decide qué hay que tocar: si la caída está en los '
            'primeros 0–2 s es el gancho (el título en pantalla dura 2,5 s); si está en 3–6 s '
            'es el ritmo del primer corte, que ahora llega a 1,75 s. '
            'La curva de retención de YouTube Studio (<code>elapsedVideoTimeRatio</code>) es lo '
            'único que lo distingue, y es justamente lo que ningún export masivo trae.</div>'
        )
    else:
        partes.append('<div class="aviso">✅ Ya no empeora. Conviene confirmarlo con otra '
                      'foto antes de dar P-12 por cerrado.</div>')
    return "\n".join(partes)


def bloque_tendencia(filas: list[dict]) -> str:
    """Pregunta 4: evolución entre fotos. Necesita dos o más `fecha_snapshot`."""
    fechas = sorted({f.get("fecha_snapshot", "") for f in filas if f.get("fecha_snapshot")})
    partes = ['<h2>4 · Evolución entre fotos</h2>']

    if len(fechas) < 2:
        partes.append(
            f'<div class="aviso">Solo hay una foto (<code>{esc(fechas[0]) if fechas else "—"}</code>), '
            'así que todavía no hay tendencia que enseñar. Cada corrida del paso 10 con exports '
            'nuevos añade una <code>fecha_snapshot</code>; con la segunda, esta sección se llena '
            'sola. <b>Los deltas de 24 h y 7 d salen de restar dos fotos</b>, no de un solo '
            'export: un export trae vistas acumuladas desde la publicación.</div>'
        )
        return "\n".join(partes)

    anterior, ultima = fechas[-2], fechas[-1]
    partes.append(f'<p class="sub">De <code>{esc(anterior)}</code> a <code>{esc(ultima)}</code>.</p>'
                  '<div class="scroll"><table><thead><tr><th>Red</th><th>Métrica</th>'
                  '<th>Antes</th><th>Ahora</th><th>Cambio</th></tr></thead><tbody>')
    for plataforma in sorted(COLUMNAS_POR_PLATAFORMA):
        for campo in ("vistas", "retencion_pct", "engagement"):
            antes = resumen([f for f in filas if f["plataforma"] == plataforma
                             and f.get("fecha_snapshot") == anterior], campo)
            ahora = resumen([f for f in filas if f["plataforma"] == plataforma
                             and f.get("fecha_snapshot") == ultima], campo)
            if not antes or not ahora or not antes["mediana"]:
                continue
            delta = (ahora["mediana"] - antes["mediana"]) / abs(antes["mediana"]) * 100
            clase = "bien" if delta >= 0 else "mal"
            partes.append(
                f'<tr><td>{esc(plataforma)}</td>'
                f'<td>{esc(ETIQUETAS.get(campo, campo))}</td>'
                f'<td>{formato(antes["mediana"], campo)}</td>'
                f'<td>{formato(ahora["mediana"], campo)}</td>'
                f'<td class="{clase}">{delta:+.1f}%</td></tr>'
            )
    partes.append('</tbody></table></div>')
    return "\n".join(partes)


def bloque_detalle(filas: list[dict]) -> str:
    """El detalle por video, una tabla por red y cada una con SUS columnas."""
    partes = ['<h2>5 · Detalle por video</h2>',
              '<p class="sub">Cada red con las columnas que de verdad exporta. '
              'Un <span class="nd">—</span> significa que ese dato no existe para esa fila.</p>']

    for plataforma in sorted(COLUMNAS_POR_PLATAFORMA):
        de_la_red = [f for f in filas if f["plataforma"] == plataforma]
        if not de_la_red:
            continue
        campos = COLUMNAS_POR_PLATAFORMA[plataforma]
        principal = METRICA_PRINCIPAL[plataforma]
        de_la_red.sort(key=lambda f: (num(f.get(principal)) or -1), reverse=True)

        # `edad_dias` va fija en todas las tablas y no en COLUMNAS_POR_PLATAFORMA:
        # es contexto para leer el resto de la fila, no una métrica de la red.
        cabeceras = "".join(f'<th>{esc(ETIQUETAS.get(c, c))}</th>'
                            for c in ["edad_dias"] + campos)
        partes.append(
            f'<h3>{esc(plataforma)} · {len(de_la_red)} videos</h3>'
            f'<div class="scroll"><table><thead><tr><th>Video</th><th>Lote</th>'
            f'{cabeceras}</tr></thead><tbody>'
        )
        for f in de_la_red:
            es_nuevo = f.get("lote") == CONFIG["lote_nuevo"]
            pill = ('<span class="pill bien">v2</span>' if es_nuevo
                    else '<span class="pill">base</span>')
            celdas = "".join(f'<td>{formato(f.get(c), c)}</td>'
                             for c in ["edad_dias"] + campos)
            partes.append(f'<tr><td>{esc(nombre_video(f))}</td><td>{pill}</td>{celdas}</tr>')
        partes.append('</tbody></table></div>')
    return "\n".join(partes)


def construir_html(filas: list[dict], hoy: date) -> str:
    fechas = sorted({f.get("fecha_snapshot", "") for f in filas if f.get("fecha_snapshot")})
    ultima = fechas[-1] if fechas else "—"
    videos = len({(f["plataforma"], f["id_plataforma"]) for f in filas})
    con_proyecto = sum(1 for f in filas if str(f.get("PROYECTO", "")).strip())

    encabezado = (
        f'<h1>Informe de métricas</h1>'
        f'<p class="sub">Última foto <b>{esc(ultima)}</b> · {len(filas)} filas · '
        f'{videos} publicaciones · generado el {hoy.isoformat()}</p>'
    )

    nota_proyecto = ""
    if con_proyecto < len(filas):
        faltan = len(filas) - con_proyecto
        nota_proyecto = (
            f'<div class="aviso">ℹ️ {faltan} de {len(filas)} filas no tienen '
            '<code>PROYECTO</code> y salen aquí con su título. Son los videos anteriores al '
            'pipeline, cuyo respaldo está en <code>proyectos/T1/&lt;TEMA&gt;/</code>, un nivel '
            'por debajo de donde los busca el paso 10 (pendiente P-14). '
            '<b>No sobran: son el baseline con el que se compara todo.</b></div>'
        )

    cuerpo = "\n".join([
        encabezado,
        nota_proyecto,
        bloque_veredicto(filas),
        bloque_ranking(filas),
        bloque_se_quedaron(filas),
        bloque_tendencia(filas),
        bloque_detalle(filas),
        '<div class="pie">Generado por <code>herramientas/11_reporte.py</code> desde '
        '<code>metricas.csv</code>. Las derivadas (vistas/día, tasa de guardado, engagement y '
        'retención relativa) se calculan al vuelo y no están en el CSV: dependen de la fecha de '
        'hoy y de la mediana del conjunto, así que guardarlas las dejaría desactualizadas.<br>'
        '⚠️ El <b>engagement</b> usa <code>alcance</code> como denominador donde existe y '
        '<code>vistas</code> donde no (TikTok): compáralo dentro de cada red, no entre redes.'
        '</div>',
    ])

    return (f'<!doctype html><html lang="es"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Métricas {esc(ultima)}</title><style>{CSS}</style></head>'
            f'<body><div class="wrap">{cuerpo}</div></body></html>')


#%% ══════════════════════════════════════════════════════════════════════
#   MAIN
# ═══════════════════════════════════════════════════════════════════════

def sincronizar_lotes() -> None:
    """Toma `lote_nuevo` y `lote_baseline` del paso 10, que es quien etiqueta.

    Un nombre de lote es un contrato entre quien escribe `metricas.csv` y quien
    lo lee. Mantenerlo en dos sitios significaba que se podían desincronizar, y
    se desincronizaron: nada falla, el informe sale, se lee bien y compara la
    tanda equivocada. Ahora el paso 10 manda y aquí solo se copia.
    """
    ruta = Path(__file__).resolve().parent / "10_metricas.py"
    if not ruta.exists():
        return
    try:
        spec = importlib.util.spec_from_file_location("met10", ruta)
        met = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(met)
    except Exception as exc:                      # noqa: BLE001
        print(f"  ⚠️  No pude leer los lotes del paso 10 ({type(exc).__name__}); "
              f"uso los de respaldo")
        return
    for clave in ("lote_nuevo", "lote_baseline"):
        if met.CONFIG.get(clave) and met.CONFIG[clave] != CONFIG[clave]:
            print(f"  🔄 {clave}: '{CONFIG[clave]}' → '{met.CONFIG[clave]}' "
                  f"(según el paso 10)")
            CONFIG[clave] = met.CONFIG[clave]


def avisar_lotes_huerfanos(filas: list[dict]) -> None:
    """Un lote que no es ni el nuevo ni el baseline no sale en el veredicto.

    Puede ser legítimo —una tanda anterior que ya cumplió— pero también puede
    ser el lote nuevo mal nombrado. Se dice en voz alta con la n al lado, que es
    lo que distingue «26 filas de v2 que ya no comparo» de «se me perdió la
    tanda de esta semana».
    """
    conocidos = {CONFIG["lote_nuevo"], CONFIG["lote_baseline"], ""}
    otros = {}
    for f in filas:
        lote = (f.get("lote") or "").strip()
        if lote not in conocidos:
            otros[lote] = otros.get(lote, 0) + 1
    for lote, n in sorted(otros.items(), key=lambda kv: -kv[1]):
        print(f"  ⚠️  '{lote}' ({n} filas) no entra en la comparación: no es ni "
              f"'{CONFIG['lote_nuevo']}' ni '{CONFIG['lote_baseline']}'")


def main() -> None:
    print("═" * 62)
    print("📊 Informe de métricas")
    print("═" * 62)

    sincronizar_lotes()
    hoy = date.today()
    filas = leer_metricas(CONFIG["metricas"])
    print(f"  ✓ {len(filas)} filas leídas de {CONFIG['metricas']}")
    avisar_lotes_huerfanos(filas)

    calcular_derivadas(filas, hoy)
    print(f"  ✓ derivadas calculadas: {', '.join(DERIVADAS)}")

    destino = Path(CONFIG["dir_reportes"])
    destino.mkdir(exist_ok=True)
    fechas = sorted({f.get("fecha_snapshot", "") for f in filas if f.get("fecha_snapshot")})
    etiqueta = fechas[-1] if fechas else hoy.isoformat()

    html_final = construir_html(filas, hoy)
    fechado = destino / f"reporte_{etiqueta}.html"
    fechado.write_text(html_final, encoding="utf-8")

    # Copia con nombre fijo: es la que abre el navegador de siempre y la que
    # podrá adjuntar el recordatorio de Telegram sin adivinar la fecha.
    estable = destino / "ultimo.html"
    estable.write_text(html_final, encoding="utf-8")

    print("─" * 62)
    print(f"  {CONFIG['lote_nuevo']} vs {CONFIG['lote_baseline']} "
          f"— solo métricas comparables:")
    for plataforma in sorted(COLUMNAS_POR_PLATAFORMA):
        validas = [c for c in (comparar_lotes(filas, plataforma, campo)
                               for campo in COLUMNAS_POR_PLATAFORMA[plataforma])
                   if c and c["comparable"]]
        if not validas:
            print(f"  {plataforma:11} — nada comparable "
                  f"(las edades de los dos lotes no se parecen)")
            continue
        for c in validas:
            flecha = "📈" if c["mejora"] else "📉"
            duda = "  ⚠ n baja" if not c["fiable"] else ""
            print(f"  {plataforma:11} {flecha} {ETIQUETAS.get(c['campo'], c['campo']):<18} "
                  f"{c['cambio_pct']:+7.0f}%  (n={c['nuevo']['n']} vs {c['base']['n']}){duda}")
    print("─" * 62)
    print(f"✅ {fechado}")
    print(f"✅ {estable}")
    print(f"\n   Ábrelo con:  xdg-open {estable}")


if __name__ == "__main__":
    main()
