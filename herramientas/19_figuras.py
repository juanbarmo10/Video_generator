#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📈  FIGURAS — convierte `metricas.csv` en gráficos que se puedan mirar.

    python herramientas/19_figuras.py              # las cuatro, a figuras/
    python herramientas/19_figuras.py --oscuro     # paleta para fondo oscuro
    python herramientas/19_figuras.py --solo historia
    python herramientas/19_figuras.py --listar

Complementa a [11_reporte.py](11_reporte.py), no lo sustituye: el informe da
**medianas y veredictos**, esto da **la forma de los datos**, que con n=6-9 es
justo lo que una mediana esconde. Un 674 de mediana puede ser seis videos
parecidos o cinco de 200 y uno de 6.000, y esas dos situaciones piden decisiones
opuestas.

⚠️ **Reusa el paso 11 entero** (`TIPO_METRICA`, `ETIQUETAS`,
`COLUMNAS_POR_PLATAFORMA`, `leer_metricas()`, `calcular_derivadas()`,
`sincronizar_lotes()`). No se reimplementa ni una regla: si una métrica deja de
ser comparable allí, aquí deja de dibujarse sola. Duplicar esa tabla era la
forma más fácil de que las figuras dijeran una cosa y el informe otra.

Cuatro decisiones de diseño que no son estéticas:

1. **Una rejilla por red, no cinco líneas en un eje.** Las redes se diferencian
   en órdenes de magnitud (Facebook llegó a 5.079 y Threads a 22.024); en un eje
   compartido, cuatro se aplastan contra el cero y la figura solo muestra la más
   grande. Además así cada panel lleva una sola serie y no hay que distinguir
   cinco colores a la vez.
2. **Puntos, no cajas.** Con 6-9 videos por lote, un diagrama de caja dibuja
   cuartiles que no existen: sugiere una precisión que la muestra no da. Se
   pintan **todos los puntos** y encima la mediana.
3. **La n va escrita en la figura, siempre.** Es la misma regla del informe.
   Una mediana sin su n invita a concluir de más.
4. **Solo se comparan lotes con métricas comparables.** `TIPO_METRICA` manda: un
   acumulado entre lotes de edades distintas mide la antigüedad, no el video.
"""

#%% ═══════════════════════════════════════════════════════════════
#   CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════

import argparse
import importlib.util
import statistics as st
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")          # sin pantalla: esto puede correr bajo cron
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

RAIZ = Path(__file__).resolve().parent.parent

CONFIG = {
    "salida": "figuras",
    "dpi": 150,
    "ancho_panel": 3.6,
    "alto_panel": 2.9,

    # Orden fijo de las redes. ⚠️ Fijo a propósito: el color sigue a la red, no
    # a su posición en el ranking de esta semana. Si el orden cambiara con los
    # datos, dos figuras de dos semanas no se podrían comparar de un vistazo.
    "redes": ["youtube", "instagram", "facebook", "tiktok", "threads"],

    # Cuántos videos como mucho en la figura del mismo tema en varias redes.
    "top_temas": 12,
}

# Paleta categórica validada (slots 1-5, en su orden fijo). Las dos columnas son
# la misma paleta escalonada para cada fondo, no un volteo automático.
PALETA = {
    "claro":  ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"],
    "oscuro": ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181"],
}
TINTA = {
    "claro":  {"fondo": "#fcfcfb", "principal": "#0b0b0b",
               "secundaria": "#52514e", "tenue": "#c9c8c2"},
    "oscuro": {"fondo": "#1a1a19", "principal": "#ffffff",
               "secundaria": "#c3c2b7", "tenue": "#4a4a46"},
}


#%% ═══════════════════════════════════════════════════════════════
#   REUSAR EL PASO 11
# ═══════════════════════════════════════════════════════════════

def cargar_reporte():
    """Importa `11_reporte.py` por ruta (su nombre empieza por dígito).

    Mismo truco que el paso 12 y que los tests. Se importa el módulo entero
    porque lo que se quiere no es una función suelta: son sus **tablas de
    decisión** (qué métrica es comparable, cómo se llama cada una, cuáles
    exporta cada red).
    """
    ruta = RAIZ / "herramientas" / "11_reporte.py"
    spec = importlib.util.spec_from_file_location("rep11", ruta)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


rep = cargar_reporte()


def etiqueta(campo: str) -> str:
    return rep.ETIQUETAS.get(campo, campo.replace("_", " "))


#%% ═══════════════════════════════════════════════════════════════
#   PREPARAR LOS DATOS
# ═══════════════════════════════════════════════════════════════

def ultima_foto(filas: list[dict]) -> list[dict]:
    """Una fila por video: la foto más reciente de cada uno.

    ⚠️ **Sin esto cada video entra tantas veces como snapshots tenga**, y los
    que llevan más semanas medidos pesarían más en cada mediana solo por llevar
    más tiempo. `metricas.csv` guarda una fila por
    `(plataforma, id_plataforma, fecha_snapshot)` justo para poder mirar la
    historia; para comparar videos entre sí hace falta aplanarla.
    """
    mejor: dict[tuple[str, str], dict] = {}
    for f in filas:
        clave = (f.get("plataforma", ""), f.get("id_plataforma", ""))
        if not clave[1]:
            continue
        previo = mejor.get(clave)
        if previo is None or f.get("fecha_snapshot", "") > previo.get("fecha_snapshot", ""):
            mejor[clave] = f
    return list(mejor.values())


def valores(filas: list[dict], campo: str) -> list[float]:
    vs = [rep.num(f.get(campo)) for f in filas]
    return [v for v in vs if v is not None]


def _fecha(f: dict):
    try:
        return datetime.strptime(f.get("fecha_publicacion", ""), "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _miles(v, _pos=None) -> str:
    """1500 → «1,5k». Los ejes con cuatro cifras se leen mal.

    ⚠️ Los valores pequeños NO se redondean a entero. La primera versión hacía
    `:.0f` siempre y el eje de «Tasa guardado %» salía con las etiquetas
    `0, 0, 1, 1`: dos pares repetidos, porque 0,5 y 1,5 se redondeaban a sus
    vecinos. Un eje con etiquetas duplicadas no es feo, es ilegible.
    """
    if abs(v) >= 1000:
        return f"{v / 1000:.1f}k".replace(".0k", "k")
    if v == 0 or abs(v) >= 10:
        return f"{v:.0f}"
    return f"{v:g}"


#%% ═══════════════════════════════════════════════════════════════
#   ESTILO
# ═══════════════════════════════════════════════════════════════

def estilo(modo: str) -> dict:
    t = TINTA[modo]
    plt.rcParams.update({
        "figure.facecolor": t["fondo"],
        "axes.facecolor": t["fondo"],
        "savefig.facecolor": t["fondo"],
        "text.color": t["principal"],
        "axes.labelcolor": t["secundaria"],
        "xtick.color": t["secundaria"],
        "ytick.color": t["secundaria"],
        "axes.edgecolor": t["tenue"],
        "grid.color": t["tenue"],
        "font.size": 8,
        "axes.titlesize": 9,
        "figure.titlesize": 12,
    })
    return t


def _limpiar(ax, t: dict) -> None:
    """Rejilla y ejes recesivos: el dato manda, el andamiaje no."""
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_linewidth(0.8)
    ax.grid(True, axis="y", linewidth=0.5, alpha=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(length=3, width=0.8)


def _pie(fig, texto: str, t: dict) -> None:
    fig.text(0.5, 0.005, texto, ha="center", va="bottom",
             fontsize=7, color=t["secundaria"], wrap=True)


#%% ═══════════════════════════════════════════════════════════════
#   FIGURA 1 · La historia en el tiempo
# ═══════════════════════════════════════════════════════════════

def fig_historia(filas: list[dict], modo: str, destino: Path) -> Path | None:
    """Alcance (o vistas) por fecha de publicación, un panel por red.

    Es la figura que enseña lo que ninguna tabla enseñó durante diez días: el
    desplome de Facebook del 15 ago se ve como un acantilado, no como una fila
    más baja. El eje Y es **logarítmico** porque los valores van de 1 a 22.000:
    en lineal, todo lo que no sea el máximo se pega al cero.
    """
    t, colores = estilo(modo), PALETA[modo]
    redes = [r for r in CONFIG["redes"]
             if any(f.get("plataforma") == r for f in filas)]
    if not redes:
        return None

    fig, ejes = plt.subplots(
        1, len(redes), sharey=True,
        figsize=(CONFIG["ancho_panel"] * len(redes), CONFIG["alto_panel"] + 0.6))
    ejes = [ejes] if len(redes) == 1 else list(ejes)

    # ⚠️ **`vistas` en las cinco, no «alcance donde lo haya».** La primera
    # versión usaba alcance en Instagram y Facebook y vistas en el resto, con
    # `sharey=True`: dos magnitudes distintas sobre un mismo eje compartido, que
    # es exactamente la comparación que el eje invita a hacer y que no vale.
    # `vistas` la exportan las cinco, así que el eje común es legítimo.
    campo = "vistas"
    for i, (ax, red) in enumerate(zip(ejes, redes)):
        color = colores[i % len(colores)]
        puntos = []
        for f in filas:
            if f.get("plataforma") != red:
                continue
            d, v = _fecha(f), rep.num(f.get(campo))
            if d and v is not None and v > 0:
                puntos.append((d, v))
        puntos.sort()
        _limpiar(ax, t)
        ax.set_title(f"{red}  ·  n={len(puntos)}", color=t["principal"], pad=8)
        if not puntos:
            ax.text(0.5, 0.5, "sin datos", ha="center", va="center",
                    transform=ax.transAxes, color=t["secundaria"], fontsize=8)
            ax.set_xticks([]); ax.set_yticks([])
            continue
        xs, ys = zip(*puntos)
        # ⚠️ **Sin línea que una los puntos.** Cada punto es un video distinto,
        # no la misma serie medida en el tiempo: una línea entre dos videos
        # dibuja una continuidad que no existe y el zigzag tapa el nivel, que
        # es lo único que aquí importa. La referencia es la mediana.
        ax.scatter(xs, ys, s=26, color=color, zorder=3,
                   edgecolor=t["fondo"], linewidth=1.2, alpha=0.9)
        m = st.median(ys)
        ax.axhline(m, color=t["principal"], linewidth=1.2, alpha=0.75, zorder=2)
        ax.text(0.98, m, f"mediana {rep.formato(m, campo)}", transform=
                ax.get_yaxis_transform(), ha="right", va="bottom", fontsize=7,
                color=t["principal"])
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(FuncFormatter(_miles))
        if i == 0:
            ax.set_ylabel(etiqueta(campo), color=t["secundaria"])
        ax.set_xlabel("")
        for etq in ax.get_xticklabels():
            etq.set_rotation(45)
            etq.set_horizontalalignment("right")

    fig.suptitle("Cada video, el día que se publicó", color=t["principal"])
    _pie(fig, "Eje Y logarítmico y compartido: los valores van de 1 a más de "
              "20.000. Un punto por video, su medición más reciente. La línea "
              "es la mediana de la red.", t)
    fig.tight_layout(rect=(0, 0.04, 1, 0.97))
    salida = destino / f"01_historia{'_oscuro' if modo == 'oscuro' else ''}.png"
    fig.savefig(salida, dpi=CONFIG["dpi"])
    plt.close(fig)
    return salida


#%% ═══════════════════════════════════════════════════════════════
#   FIGURA 2 · Distribución por lote
# ═══════════════════════════════════════════════════════════════

def _lote_corto(lote: str) -> str:
    """`v4-hashtags-limpios` → `v4`. Solo para el eje.

    ⚠️ Los nombres de lote son descriptivos a propósito —dicen qué cambió— pero
    miden 20+ caracteres y en un panel de 3 columnas se solapan hasta ser
    ilegibles: `v2-mas-cortes` y `v3-guion-y-dispersion` se imprimían uno encima
    del otro. Se acorta en el eje; el nombre entero va al pie, que es donde se
    lee sin prisa.
    """
    cabeza = lote.split("-", 1)[0]
    return cabeza if cabeza.startswith("v") and cabeza[1:].isdigit() else lote


def fig_lotes(filas: list[dict], modo: str, destino: Path) -> Path | None:
    """Todos los puntos de cada lote, con su mediana encima.

    ⚠️ **Solo métricas que `TIPO_METRICA` declara comparables** (`ventana` y
    `tasa`). Un acumulado entre lotes de edades distintas mide cuánto lleva
    publicado el video, no si es mejor — es el fallo del «+5591 %» que el paso
    11 tiene congelado en un test.
    """
    t, colores = estilo(modo), PALETA[modo]
    comparables = [c for c, tipo in rep.TIPO_METRICA.items()
                   if tipo in ("ventana", "tasa")]
    lotes = sorted({f.get("lote", "") for f in filas if f.get("lote")})
    if not lotes:
        return None

    paneles = []
    for red in CONFIG["redes"]:
        de_red = [f for f in filas if f.get("plataforma") == red]
        cols = rep.COLUMNAS_POR_PLATAFORMA.get(red, [])
        for campo in comparables:
            if campo not in cols and campo not in rep.DERIVADAS:
                continue
            datos = {l: valores([f for f in de_red if f.get("lote") == l], campo)
                     for l in lotes}
            datos = {l: v for l, v in datos.items() if v}
            if len(datos) >= 2:                  # con un solo lote no hay qué comparar
                paneles.append((red, campo, datos))
    if not paneles:
        return None
    paneles = paneles[:12]

    filas_g = (len(paneles) + 2) // 3
    fig, ejes = plt.subplots(filas_g, 3,
                             figsize=(CONFIG["ancho_panel"] * 3,
                                      CONFIG["alto_panel"] * filas_g + 0.8))
    ejes = [ejes] if filas_g * 3 == 1 else list(ejes.flat)

    for ax, (red, campo, datos) in zip(ejes, paneles):
        _limpiar(ax, t)
        for j, (lote, vs) in enumerate(datos.items()):
            color = colores[j % len(colores)]
            # Dispersión horizontal determinista: sin ella los puntos iguales se
            # tapan y n=8 parece n=3. Sin azar, para que la figura no cambie
            # entre dos corridas con los mismos datos.
            for k, v in enumerate(sorted(vs)):
                dx = ((k % 5) - 2) * 0.045
                ax.scatter(j + dx, v, s=30, color=color, alpha=0.75,
                           edgecolor=t["fondo"], linewidth=0.8, zorder=3)
            m = st.median(vs)
            ax.hlines(m, j - 0.28, j + 0.28, color=t["principal"],
                      linewidth=2, zorder=4)
            # Pegada al borde derecho del panel y no sobre la línea: centrada
            # caía encima de los propios puntos.
            ax.text(j + 0.34, m, rep.formato(m, campo), va="center", ha="left",
                    fontsize=7, color=t["principal"], zorder=5)
        ax.set_xticks(range(len(datos)))
        ax.set_xticklabels([f"{_lote_corto(l)}\nn={len(v)}"
                            for l, v in datos.items()], fontsize=7)
        ax.set_title(f"{red} · {etiqueta(campo)}", color=t["principal"], pad=8)
        ax.yaxis.set_major_formatter(FuncFormatter(_miles))
    for ax in ejes[len(paneles):]:
        ax.set_visible(False)

    fig.suptitle("Cada video como un punto, y la mediana encima",
                 color=t["principal"])
    nombres = " · ".join(f"{_lote_corto(l)} = {l}" for l in lotes
                         if _lote_corto(l) != l)
    _pie(fig, (f"{nombres}\n" if nombres else "") +
              "Solo métricas comparables entre lotes (ventana y tasa). "
              "Los acumulados se omiten a propósito: entre lotes de edades "
              "distintas miden la antigüedad, no el video.", t)
    fig.tight_layout(rect=(0, 0.03, 1, 0.97))
    salida = destino / f"02_lotes{'_oscuro' if modo == 'oscuro' else ''}.png"
    fig.savefig(salida, dpi=CONFIG["dpi"])
    plt.close(fig)
    return salida


#%% ═══════════════════════════════════════════════════════════════
#   FIGURA 3 · El mismo video en cada red
# ═══════════════════════════════════════════════════════════════

def fig_redes(filas: list[dict], modo: str, destino: Path) -> Path | None:
    """El mismo `PROYECTO` comparado consigo mismo en las redes donde salió.

    Es la única comparación entre redes que no confunde red con contenido: el
    video es literalmente el mismo archivo, así que lo que queda es la red.

    ⚠️ **Puntos en filas, sin líneas que unan proyectos.** La primera versión
    ponía los proyectos en el eje X y unía cada red con una línea: eso dibuja
    una tendencia a lo largo de un eje **categórico y ordenado arbitrariamente**
    (por vistas totales), o sea una pendiente que no significa nada. Además los
    nombres de proyecto son largos y en horizontal se leen sin rotar.
    """
    t, colores = estilo(modo), PALETA[modo]
    por_proy: dict[str, dict[str, float]] = defaultdict(dict)
    for f in filas:
        proy, red = f.get("PROYECTO", ""), f.get("plataforma", "")
        v = rep.num(f.get("vistas"))
        if proy and red and v is not None and v > 0:
            por_proy[proy][red] = max(por_proy[proy].get(red, 0), v)

    completos = {p: r for p, r in por_proy.items() if len(r) >= 3}
    if not completos:
        return None
    orden = sorted(completos, key=lambda p: st.median(completos[p].values()))
    orden = orden[-CONFIG["top_temas"]:]
    redes = [r for r in CONFIG["redes"] if any(r in completos[p] for p in orden)]

    fig, ax = plt.subplots(figsize=(9.5, 0.46 * len(orden) + 2.4))
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_linewidth(0.8)
    ax.grid(True, axis="x", linewidth=0.5, alpha=0.5)
    ax.set_axisbelow(True)
    ax.tick_params(length=3, width=0.8)

    for i, proy in enumerate(orden):
        # Un hilo tenue de mínimo a máximo: ese sí une valores del MISMO video,
        # que es una relación real, y da el rango de un vistazo.
        vs = list(completos[proy].values())
        ax.plot([min(vs), max(vs)], [i, i], color=t["tenue"], linewidth=1.5,
                zorder=1, solid_capstyle="round")
    for k, red in enumerate(redes):
        color = colores[k % len(colores)]
        ys = [i for i, p in enumerate(orden) if red in completos[p]]
        xs = [completos[orden[i]][red] for i in ys]
        ax.scatter(xs, ys, s=52, color=color, label=red, zorder=3,
                   edgecolor=t["fondo"], linewidth=1.4)

    ax.set_xscale("log")
    ax.xaxis.set_major_formatter(FuncFormatter(_miles))
    ax.set_yticks(range(len(orden)))
    ax.set_yticklabels(orden, fontsize=8)
    ax.set_xlabel("vistas", color=t["secundaria"])
    ax.set_ylim(-0.7, len(orden) - 0.3)
    ax.legend(frameon=False, ncols=len(redes), fontsize=8,
              loc="lower center", bbox_to_anchor=(0.5, 1.01))
    ax.set_title(f"El mismo video en cada red  ·  {len(orden)} temas",
                 color=t["principal"], pad=32)
    _pie(fig, "Solo temas publicados en 3 redes o más. Mismo archivo de video en "
              "todas, así que la diferencia es la red. Eje X logarítmico; la "
              "barra gris une el mínimo y el máximo de cada tema.", t)
    fig.tight_layout(rect=(0, 0.05, 1, 1))
    salida = destino / f"03_redes{'_oscuro' if modo == 'oscuro' else ''}.png"
    fig.savefig(salida, dpi=CONFIG["dpi"])
    plt.close(fig)
    return salida


#%% ═══════════════════════════════════════════════════════════════
#   FIGURA 4 · Qué se puede analizar
# ═══════════════════════════════════════════════════════════════

def fig_cobertura(filas: list[dict], modo: str, destino: Path) -> Path | None:
    """Qué porcentaje de filas tiene dato en cada columna, por red.

    No es una figura bonita: es la que evita perder una tarde intentando
    comparar algo que media red no exporta. `alcance` no existe en TikTok,
    `guardados` no existe en YouTube ni TikTok, y `duracion_media_s` se teclea a
    mano — si nadie la tecleó, no hay retención que calcular.
    """
    t = estilo(modo)
    redes = [r for r in CONFIG["redes"]
             if any(f.get("plataforma") == r for f in filas)]
    columnas = [c for c in rep.TIPO_METRICA if c not in rep.DERIVADAS]
    columnas = [c for c in columnas
                if any(rep.num(f.get(c)) is not None for f in filas)]
    if not redes or not columnas:
        return None

    malla = []
    for red in redes:
        de_red = [f for f in filas if f.get("plataforma") == red]
        malla.append([
            (100.0 * sum(1 for f in de_red if rep.num(f.get(c)) is not None)
             / len(de_red)) if de_red else 0.0
            for c in columnas])

    fig, ax = plt.subplots(figsize=(0.62 * len(columnas) + 3.2,
                                    0.52 * len(redes) + 2.4))
    # Rampa secuencial de un solo tono (claro → oscuro). Nunca arcoíris: esto
    # es magnitud, y un arcoíris inventa categorías donde hay una escala.
    im = ax.imshow(malla, cmap="Blues", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(columnas)))
    ax.set_xticklabels([etiqueta(c) for c in columnas], rotation=45,
                       ha="right", fontsize=7)
    ax.set_yticks(range(len(redes)))
    ax.set_yticklabels([f"{r}  (n={sum(1 for f in filas if f.get('plataforma')==r)})"
                        for r in redes], fontsize=8)
    for i in range(len(redes)):
        for j in range(len(columnas)):
            v = malla[i][j]
            if v <= 0:
                continue
            # El número va siempre: el color solo no basta para leer un valor.
            ax.text(j, i, f"{v:.0f}", ha="center", va="center", fontsize=6.5,
                    color="#ffffff" if v > 55 else "#0b0b0b")
    for lado in ("top", "right", "left", "bottom"):
        ax.spines[lado].set_visible(False)
    ax.tick_params(length=0)
    fig.colorbar(im, ax=ax, shrink=0.7, label="% de filas con dato")
    ax.set_title("Qué se puede analizar de cada red", color=t["principal"], pad=10)
    _pie(fig, "Una celda vacía no es un cero: es que esa red no exporta ese "
              "dato. Lo que está al 100 % y al 0 % es estructural, no un hueco.", t)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    salida = destino / f"04_cobertura{'_oscuro' if modo == 'oscuro' else ''}.png"
    fig.savefig(salida, dpi=CONFIG["dpi"])
    plt.close(fig)
    return salida


#%% ═══════════════════════════════════════════════════════════════
#   CLI
# ═══════════════════════════════════════════════════════════════

FIGURAS = {
    "historia":  ("Cada video el día que se publicó, una red por panel", fig_historia),
    "lotes":     ("Distribución por lote, con todos los puntos", fig_lotes),
    "redes":     ("El mismo video comparado entre redes", fig_redes),
    "cobertura": ("Qué columna trae dato en cada red", fig_cobertura),
}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--solo", metavar="NOMBRE",
                   help=f"Genera una sola: {', '.join(FIGURAS)}")
    p.add_argument("--oscuro", action="store_true",
                   help="Paleta escalonada para fondo oscuro")
    p.add_argument("--listar", action="store_true", help="Qué figura es cada una")
    p.add_argument("--salida", default=CONFIG["salida"])
    args = p.parse_args()

    if args.listar:
        for nombre, (que, _) in FIGURAS.items():
            print(f"  {nombre:<11} {que}")
        return

    rep.sincronizar_lotes()
    filas = rep.leer_metricas(str(RAIZ / rep.CONFIG["metricas"]))
    rep.calcular_derivadas(filas, date.today())
    print(f"📊 {len(filas)} filas leídas")

    planas = ultima_foto(filas)
    print(f"   {len(planas)} videos (la medición más reciente de cada uno)")
    rep.avisar_lotes_huerfanos(planas)

    destino = RAIZ / args.salida
    destino.mkdir(exist_ok=True)
    modo = "oscuro" if args.oscuro else "claro"

    pedidas = {args.solo: FIGURAS[args.solo]} if args.solo else FIGURAS
    if args.solo and args.solo not in FIGURAS:
        raise SystemExit(f"❌ No existe '{args.solo}'. Hay: {', '.join(FIGURAS)}")

    hechas = 0
    for nombre, (_, fn) in pedidas.items():
        ruta = fn(planas, modo, destino)
        if ruta:
            print(f"   ✅ {ruta.relative_to(RAIZ)}")
            hechas += 1
        else:
            print(f"   ⏭️  {nombre}: sin datos suficientes todavía")
    print(f"\n📈 {hechas} figura(s) en {args.salida}/")


if __name__ == "__main__":
    main()
