"""
Sello del tema en curso — guarda contra mezclar dos temas en un mismo video.

Los archivos de la raíz (`script.txt`, `voice.mp3`, `images_IA/`, `source_images/`)
son estado global compartido: solo existe el tema EN CURSO. Si un paso falla a
mitad del pipeline, los siguientes seguirían trabajando con los datos del tema
anterior sin notarlo, y producirían un video convincente pero equivocado.

El paso 01 escribe `.estado_actual` con el PROYECTO y el TEMA; los pasos 02, 03,
04 y 07 llaman a `verificar_estado()` antes de trabajar.

Es el único módulo compartido del pipeline: el resto de los pasos siguen siendo
procesos independientes que se comunican solo por archivos.
"""

import json
import os
import time
from pathlib import Path

ARCHIVO_ESTADO = ".estado_actual"
ARCHIVO_COSTO = ".costo_actual.json"

# Precios por 1M de tokens (USD), a mayo 2026. Ajusta si cambian.
# ⚠️ Un modelo que NO esté aquí no se cobra: `registrar_openai()` hace
# `if not precio: return` y el contador miente en silencio. Si cambias de
# modelo en cualquier paso, añádelo aquí ANTES.
# Precios de developers.openai.com/api/docs/pricing (consultados 15 ago 2026).
PRECIOS_OPENAI = {
    "gpt-4.1":      {"in": 2.00, "out": 8.00},
    "gpt-4.1-mini": {"in": 0.40, "out": 1.60},
    "gpt-5.4":      {"in": 2.50, "out": 15.00},
    "gpt-5.4-mini": {"in": 0.75, "out": 4.50},
    "gpt-5.2":      {"in": 1.75, "out": 14.00},
    # ⚠️ gpt-5.5 razona antes de responder y esos tokens se facturan como
    # SALIDA: medido en este guion, 2560 tokens de razonamiento para 137 de
    # texto → $0.085 por guion, 33× gpt-4.1 y más caro que escribirlo con Opus.
    "gpt-5.5":      {"in": 5.00, "out": 30.00},
}

# Anthropic (agosto 2026). Los tokens de "thinking" se facturan como salida.
PRECIOS_ANTHROPIC = {
    "claude-opus-5":   {"in": 5.00, "out": 25.00},
    "claude-sonnet-5": {"in": 3.00, "out": 15.00},
    "claude-haiku-4-5": {"in": 1.00, "out": 5.00},
}
# fal.ai Flux dev cobra por megapíxel generado
PRECIO_FAL_POR_MP = 0.025
# ElevenLabs, aproximado por carácter en el plan Creator
PRECIO_ELEVENLABS_POR_CHAR = 0.00003


def sellar_estado(proyecto: str, tema: str = "") -> None:
    """Escribe el sello del tema en curso (lo llama el paso 01)."""
    Path(ARCHIVO_ESTADO).write_text(f"{proyecto}\n{tema}\n", encoding="utf-8")


def leer_estado() -> tuple[str, str] | None:
    """Devuelve (proyecto, tema) del sello, o None si no existe."""
    ruta = Path(ARCHIVO_ESTADO)
    if not ruta.exists():
        return None

    lineas = ruta.read_text(encoding="utf-8").splitlines()
    if not lineas:
        return None

    return lineas[0].strip(), (lineas[1].strip() if len(lineas) > 1 else "")


def verificar_estado(paso: str) -> None:
    """Aborta si los archivos de la raíz son de otro PROYECTO.

    No hace nada si no hay sello (p. ej. al correr un paso suelto a mano sobre
    artefactos ya existentes, que es un flujo legítimo documentado en CLAUDE.md).
    """
    proyecto = os.environ.get("PROYECTO")
    if not proyecto:
        return

    estado = leer_estado()
    if estado is None:
        return

    dueno, tema = estado
    if dueno and dueno != proyecto:
        raise SystemExit(
            f"❌ [{paso}] Los archivos de la raíz son de '{dueno}'"
            f"{f' ({tema})' if tema else ''}, no de '{proyecto}'.\n"
            f"   Corre el paso 01 para este tema, o borra {ARCHIVO_ESTADO} "
            f"si sabes lo que haces."
        )


# ══════════════════════════════════════════════════════════════
# 🔁  REINTENTOS
# ══════════════════════════════════════════════════════════════

def con_reintentos(fn, intentos: int = 3, espera_base: float = 2.0,
                   etiqueta: str = "llamada"):
    """Ejecuta fn() reintentando con backoff exponencial.

    Un 429 o un corte de red a mitad del pipeline abortaba el tema entero
    habiendo pagado ya los pasos anteriores. Reintentar sale más barato.
    """
    for intento in range(1, intentos + 1):
        try:
            return fn()
        except Exception as exc:
            if intento == intentos:
                raise
            espera = espera_base * (2 ** (intento - 1))
            print(f"⚠️  {etiqueta} falló (intento {intento}/{intentos}): "
                  f"{type(exc).__name__} — reintentando en {espera:.0f}s")
            time.sleep(espera)


# ══════════════════════════════════════════════════════════════
# 💰  CONTADOR DE COSTO POR TEMA
# ══════════════════════════════════════════════════════════════

def _leer_costo() -> dict:
    ruta = Path(ARCHIVO_COSTO)
    if not ruta.exists():
        return {"total_usd": 0.0, "detalle": []}
    try:
        return json.loads(ruta.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"total_usd": 0.0, "detalle": []}


def _guardar_costo(datos: dict) -> None:
    Path(ARCHIVO_COSTO).write_text(
        json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def reset_costo() -> None:
    """Arranca el contador del tema (lo llama el paso 01)."""
    _guardar_costo({"total_usd": 0.0, "detalle": []})


def registrar_costo(concepto: str, usd: float) -> None:
    """Suma un gasto al acumulado del tema en curso."""
    datos = _leer_costo()
    datos["total_usd"] = round(datos["total_usd"] + usd, 5)
    datos["detalle"].append({"concepto": concepto, "usd": round(usd, 5)})
    _guardar_costo(datos)


def registrar_openai(response, modelo: str, concepto: str = "") -> None:
    """Registra el costo de una respuesta de la API de OpenAI."""
    precio = PRECIOS_OPENAI.get(modelo)
    uso = getattr(response, "usage", None)
    if not precio or uso is None:
        return

    usd = (uso.prompt_tokens / 1e6 * precio["in"]
           + uso.completion_tokens / 1e6 * precio["out"])
    registrar_costo(f"{modelo} {concepto}".strip(), usd)


def registrar_anthropic(response, modelo: str, concepto: str = "") -> None:
    """Registra el costo de una respuesta de la API de Anthropic.

    Los tokens de thinking van dentro de output_tokens, así que ya quedan
    contabilizados sin hacer nada especial.
    """
    precio = PRECIOS_ANTHROPIC.get(modelo)
    uso = getattr(response, "usage", None)
    if not precio or uso is None:
        return

    usd = (uso.input_tokens / 1e6 * precio["in"]
           + uso.output_tokens / 1e6 * precio["out"])
    registrar_costo(f"{modelo} {concepto}".strip(), usd)


def registrar_imagen_fal(ancho: int, alto: int, n: int = 1) -> None:
    registrar_costo(f"fal flux dev {ancho}x{alto} x{n}",
                    ancho * alto / 1e6 * PRECIO_FAL_POR_MP * n)


def registrar_elevenlabs(n_chars: int) -> None:
    registrar_costo(f"elevenlabs {n_chars} chars",
                    n_chars * PRECIO_ELEVENLABS_POR_CHAR)


def resumen_costo() -> str:
    datos = _leer_costo()
    return f"💰 Costo del tema: ${datos['total_usd']:.4f} USD"
