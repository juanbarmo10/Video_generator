#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📄 REHACER LOS `.srt` QUE FALTEN, desde el mp3 de cada respaldo.

    python herramientas/18_rehacer_srt.py                 # los que falten, todos
    python herramientas/18_rehacer_srt.py --patron Mundial*
    python herramientas/18_rehacer_srt.py --rehacer-todos  # también los que ya están
    python herramientas/18_rehacer_srt.py --listar         # solo dice cuáles faltan

⚠️ **Esto es recuperación de verdad, no reconstrucción.** La fuente es el audio
que se publicó, así que el resultado es el mismo que habría salido entonces. Se
reusan las DOS funciones del paso 07 (`transcribe_words` y `exportar_srt`) en vez
de reimplementarlas, para que los .srt viejos y los nuevos salgan con el mismo
formato y el mismo troceado.

⚠️ **Es lento y no da resultados parciales gratis: ~11 min por video** con
whisper `medium` en CPU. Por eso escribe cada `.srt` en cuanto lo tiene, en vez
de acumular: si se interrumpe a la mitad, lo hecho se conserva y la corrida
siguiente sigue donde quedó (`--listar` dice cuánto falta). La primera vez que se
corrió esto vivía en un temporal, se lo llevó la limpieza del sistema a mitad de
camino y **P-08 se quedó en 10 de 16 sin que nada avisara**; está aquí para que
eso no vuelva a pasar.
"""

#%% ═══════════════════════════════════════════════════════════════
#   CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════

import argparse
import importlib.util
import os
import sys
import tempfile
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

CONFIG = {
    # Los respaldos cuelgan a dos niveles: `proyectos/Historia09/` los del
    # pipeline y `proyectos/T1/<TEMA>/` los de la tanda anterior (ver trampa 5
    # de CLAUDE.md). Se buscan los dos.
    "globs": ["proyectos/*", "proyectos/T1/*"],
}


#%% ═══════════════════════════════════════════════════════════════
#   CARGAR EL PASO 07 SIN QUE TRABAJE
# ═══════════════════════════════════════════════════════════════

def cargar_paso07():
    """Importa `07_video_generator.py` preparándole el entorno desde fuera.

    ⚠️ El paso 07 **trabaja al importarse**: aborta si faltan `PROYECTO` /
    `TITULO_VIDEO` y llama a `verificar_estado()`, que corta si `.estado_actual`
    es de otro tema — y lo es, porque el sello es del último que corrió el
    pipeline. Es el mismo apaño que `cargar_paso()` en los tests: un directorio
    temporal SIN sello (`verificar_estado()` vuelve sin abortar y ningún
    `open()` relativo toca el tema en curso) y variables de mentira.

    Todas las rutas de este script son **absolutas**, así que el `chdir` no
    afecta a nada más.
    """
    sys.path.insert(0, str(RAIZ / "pipeline"))
    os.environ.setdefault("PROYECTO", "_recuperacion")
    os.environ.setdefault("TITULO_VIDEO", "_recuperacion")
    os.chdir(tempfile.mkdtemp(prefix="rehacer_srt_"))

    ruta = RAIZ / "pipeline" / "07_video_generator.py"
    spec = importlib.util.spec_from_file_location("paso07", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


#%% ═══════════════════════════════════════════════════════════════
#   QUÉ FALTA
# ═══════════════════════════════════════════════════════════════

def pendientes(patron: str, forzar: bool) -> list[tuple[str, Path, Path]]:
    """Respaldos con mp3 y sin `.srt`, ordenados por nombre."""
    vistos, faltan = set(), []
    for glob in CONFIG["globs"]:
        for carpeta in sorted(RAIZ.glob(glob)):
            if not carpeta.is_dir() or carpeta.name in vistos:
                continue
            if not carpeta.match(f"*/{patron}"):
                continue
            vistos.add(carpeta.name)
            mp3 = carpeta / f"{carpeta.name}.mp3"
            srt = carpeta / f"{carpeta.name}.srt"
            if mp3.exists() and (forzar or not srt.exists()):
                faltan.append((carpeta.name, mp3, srt))
    return sorted(faltan)


#%% ═══════════════════════════════════════════════════════════════
#   CLI
# ═══════════════════════════════════════════════════════════════

def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--patron", default="*",
                   help="Filtra por nombre de PROYECTO (admite comodines)")
    p.add_argument("--rehacer-todos", action="store_true",
                   help="Rehace también los que ya tienen .srt")
    p.add_argument("--listar", action="store_true",
                   help="Solo dice cuáles faltan. No transcribe nada")
    args = p.parse_args()

    cola = pendientes(args.patron, args.rehacer_todos)
    if not cola:
        print(f"✅ Ningún .srt pendiente para '{args.patron}'")
        return

    print(f"🎙️  {len(cola)} .srt por rehacer:")
    for nombre, _, _ in cola:
        print(f"   · {nombre}")
    if args.listar:
        return

    paso07 = cargar_paso07()
    modelo = paso07.CONFIG["whisper_model"]
    por_linea = paso07.CONFIG["srt_palabras_por_linea"]
    idioma = paso07.CONFIG["whisper_language"]
    print(f"\n   whisper '{modelo}' · ~11 min por video en CPU\n")

    hechos = 0
    for i, (nombre, mp3, srt) in enumerate(cola, 1):
        print(f"[{i}/{len(cola)}] {nombre}", flush=True)
        palabras = paso07.transcribe_words(str(mp3), modelo, idioma)
        if not palabras:
            print("   ❌ sin transcripción, se salta")
            continue
        paso07.exportar_srt(palabras, str(srt), por_linea)
        hechos += 1

    print(f"\n✅ {hechos} de {len(cola)} rehechos")


if __name__ == "__main__":
    main()
