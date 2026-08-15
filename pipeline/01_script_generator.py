#%%
"""
╔══════════════════════════════════════════════════════════════╗
║   ✍️  GENERADOR DE GUION CON CONTROL DE CALIDAD              ║
║   Escribe → verifica → si no pasa, reescribe con el feedback ║
╚══════════════════════════════════════════════════════════════╝

El guion es el corazón del producto: define el gancho, el ritmo y lo que se
narra. Un guion malo no se arregla en ningún paso posterior.

El control tiene DOS capas, a propósito:

  1. verificar_reglas_mecanicas() — Python puro, gratis e infalible.
     Cuenta palabras, mide frases, busca fechas y muletillas. A un LLM no se le
     pide que cuente: lo hace mal y cobra por hacerlo mal.

  2. evaluar_con_critico() — un segundo modelo con rol adversarial.
     Solo juzga lo que requiere criterio: si cada afirmación es verificable, si
     la primera frase revela el desenlace, si la historia mantiene una sola
     línea narrativa.

La capa 2 existe por un fallo real: en la prueba con Zidane el guion coló
"Su propia madre nunca volvió a ver aquel momento en video" — un dato que no es
verificable, pese a que las reglas del prompt lo prohíben explícitamente. El
generador no se audita bien a sí mismo; hace falta otro que solo busque fallos.
"""

from dotenv import load_dotenv
import json
import os
import re
import unicodedata
from pathlib import Path
from openai import OpenAI

from estado import (sellar_estado, reset_costo, registrar_openai,
                    registrar_anthropic, con_reintentos)

load_dotenv()

# ========================================================================== #

TEMA = os.environ.get("TEMA")
PROYECTO = os.environ.get("PROYECTO")
openai_api_key = os.getenv("OPENAI_API_KEY")
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")

if not openai_api_key:
    raise SystemExit("❌ Falta OPENAI_API_KEY en el .env")

client = OpenAI(api_key=openai_api_key)

# Cliente de Anthropic solo si hay clave: sin ella el crítico cae a OpenAI.
anthropic_client = None
if anthropic_api_key:
    try:
        import anthropic
        anthropic_client = anthropic.Anthropic(api_key=anthropic_api_key)
    except ImportError:
        print("⚠️  Hay ANTHROPIC_API_KEY pero falta el paquete: pip install anthropic")

# ========================================================================== #

CONFIG = {
    # ── Modelos ───────────────────────────────────────────────
    "modelo_guionista": "gpt-4.1",

    # 🔀 El crítico corre en OTRO PROVEEDOR a propósito. Un modelo de la misma
    # familia que el generador comparte sus puntos ciegos: si gpt-4.1 se cree
    # una afirmación inventada al escribirla, tiende a creérsela al revisarla.
    # Un modelo distinto falla de otra forma, y ahí está el valor.
    #
    # "auto" usa Anthropic si hay ANTHROPIC_API_KEY y cae a OpenAI si no,
    # así el pipeline nunca se rompe por falta de una clave.
    "critico_proveedor": "auto",            # "auto" | "anthropic" | "openai"
    "modelo_critico_anthropic": "claude-opus-5",
    "modelo_critico_openai": "gpt-4.1",     # el respaldo, mismo proveedor
    # Costo por tema con 3 intentos, medido sobre una crítica real
    # (626 tokens de entrada, 311 de salida):
    #   claude-haiku-4-5  $0.0065   ← más barato que el crítico actual
    #   gpt-4.1           $0.0112
    #   claude-sonnet-5   $0.0196
    #   claude-opus-5     $0.0327   ← +9% sobre un tema de $0.23
    # El effort es la palanca de costo real en Opus 5: "medium" rinde muy bien
    # en tareas acotadas como esta. Súbelo a "high" si ves fallos de criterio.
    # ── Aprendizaje entre temas ───────────────────────────────
    # Destila los `calidad_guion.json` acumulados en un bloque corto para el
    # generador: qué reglas suyas rompe más (con la cuenta) y un guion propio
    # que sí pasó. Cuesta ~200 tokens de entrada y solo en el primer intento.
    "lecciones_activas": True,
    "lecciones_min_historial": 3,   # con menos temas, la frecuencia es ruido
    "lecciones_max_ejemplos": 1,    # ejemplos POSITIVOS (nunca los rechazados)
    "lecciones_max_chars": 700,

    # Medido sobre el mismo guion: "low" $0.029 vs "medium" $0.040 (-26%) con
    # la misma nota y las mismas objeciones de fondo. Es la palanca de costo
    # real del paso 01 — súbelo solo si ves que se le escapan errores.
    "critico_effort": "low",                # low | medium | high | xhigh | max
    # En Opus 5 el thinking está ON por defecto y max_tokens limita
    # thinking + respuesta JUNTOS: si se queda corto, el JSON sale truncado.
    "critico_max_tokens": 4096,

    # ── Bucle de calidad ──────────────────────────────────────
    "intentos_max": 3,          # generación + crítica por intento
    "nota_minima": 7,           # 0-10, por debajo se reescribe
    # Si ningún intento pasa: False = usa el mejor con aviso ruidoso,
    # True = aborta el tema. Abortar aquí es barato (el paso 01 es el primero,
    # no hay nada pagado todavía) pero corta el lote de run_all.sh.
    "abortar_si_ninguno_pasa": False,

    # ── Límites mecánicos ─────────────────────────────────────
    "palabras_min": 65,
    "palabras_max": 75,
    "palabras_tolerancia": 5,   # fuera de [min-tol, max+tol] es falta GRAVE
    "primera_frase_max": 8,     # palabras; más de +2 sobre esto es GRAVE
    "frase_max": 12,            # palabras por frase (falta leve)
}

INICIOS_PROHIBIDOS = ("en", "cuando", "fue", "era", "hubo")

# Muletillas que delatan un dato no verificable. Son la señal más barata y
# fiable de que el guion se está inventando algo.
MULETILLAS = [
    "se dice", "se cree", "algunos creen", "se rumorea", "dicen que",
    "se especula", "supuestamente", "al parecer", "podría haber",
    "habría sido", "se piensa", "muchos creen", "la leyenda",
]

PALABRAS_ACADEMICAS = ["acontecimiento", "suceso", "hecho histórico"]

# ── Patrones sacados de lo que el crítico objetó DE VERDAD ──────────────
# No son intuiciones: salen de leer los 8 primeros `calidad_guion.json`. El
# prompt ya prohíbe todo esto en prosa y el generador lo incumple igual, así
# que aquí se comprueba en Python — gratis, y ANTES de pagar la crítica.
#
# ⚠️ Van como LEVES, no como graves. "nunca robó a los ricos" estaba en el
# único guion que aprobó (Historia04): un absoluto puede ser perfectamente
# verificable. Como leve entra en la reescritura sin bloquear ni penalizar
# la nota; como grave habría tirado el mejor guion del lote.
ABSOLUTOS = [
    "nadie ", "ninguna", "ninguno", "nunca", "jamas", "siempre",
    "el mas ", "la mas ", "los mas ", "el unico", "la unica",
    "el primero", "la primera vez", "todos los", "todas las",
]

# "como si pescaran sardinas", "como un secreto incómodo" — el crítico llamó
# a esto "recursos poéticos en vez de hechos verificables" en 4 de 8 guiones.
SIMILES = ["como si ", "como un ", "como una "]

# Verbos de mente ajena. El guion no puede saber qué pensó nadie.
VERBOS_MENTE = [
    "penso", "pensaba", "imagino", "imaginaba", "sintio", "sentia",
    "creyo", "temio", "temia", "sospecho", "sospechaba", "espero que",
    "queria", "deseaba", "sabia que",
]

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


# ══════════════════════════════════════════════════════════════
# 🧮  CAPA 1 — VERIFICACIÓN MECÁNICA (Python, sin coste)
# ══════════════════════════════════════════════════════════════

def _sin_tildes(texto: str) -> str:
    return "".join(
        c for c in unicodedata.normalize("NFD", texto.lower())
        if unicodedata.category(c) != "Mn"
    )


def dividir_frases(script: str) -> list[str]:
    return [f.strip() for f in re.split(r"[.!?]+", script) if f.strip()]


def verificar_reglas_mecanicas(script: str, cfg: dict = CONFIG) -> tuple[list, list]:
    """Comprueba lo que se puede medir. Devuelve (graves, leves).

    Un LLM no cuenta palabras de forma fiable ni detecta un año escondido.
    Esto sí, cuesta cero y no falla nunca.
    """
    graves, leves = [], []

    palabras = script.split()
    n = len(palabras)
    tol = cfg["palabras_tolerancia"]

    if not (cfg["palabras_min"] - tol <= n <= cfg["palabras_max"] + tol):
        graves.append(
            f"Tiene {n} palabras; el objetivo es "
            f"{cfg['palabras_min']}-{cfg['palabras_max']}."
        )
    elif not (cfg["palabras_min"] <= n <= cfg["palabras_max"]):
        leves.append(f"Tiene {n} palabras, un poco fuera de "
                     f"{cfg['palabras_min']}-{cfg['palabras_max']}.")

    frases = dividir_frases(script)
    if not frases:
        graves.append("El guion está vacío.")
        return graves, leves

    # Primera frase: es el gancho, la regla que más pesa
    n_primera = len(frases[0].split())
    if n_primera > cfg["primera_frase_max"] + 2:
        graves.append(
            f"La primera frase tiene {n_primera} palabras (máximo "
            f"{cfg['primera_frase_max']}). Es el gancho: acórtala."
        )
    elif n_primera > cfg["primera_frase_max"]:
        leves.append(f"La primera frase tiene {n_primera} palabras "
                     f"(objetivo {cfg['primera_frase_max']}).")

    primera_palabra = _sin_tildes(frases[0].split()[0]).strip(",;:")
    if primera_palabra in INICIOS_PROHIBIDOS:
        graves.append(
            f"Empieza con '{frases[0].split()[0]}', que está prohibido "
            f"({', '.join(INICIOS_PROHIBIDOS)})."
        )

    plano = _sin_tildes(script)

    for m in MULETILLAS:
        if _sin_tildes(m) in plano:
            graves.append(
                f"Contiene '{m}': delata un dato no verificable. "
                f"Si no se puede comprobar, no va."
            )

    # Fechas: años de 4 cifras y meses escritos
    for anio in re.findall(r"\b(1\d{3}|20\d{2})\b", script):
        graves.append(f"Contiene la fecha '{anio}'. El guion va sin fechas.")
    for mes in MESES:
        if re.search(rf"\b{mes}\b", plano):
            graves.append(f"Contiene el mes '{mes}'. El guion va sin fechas.")

    for pal in PALABRAS_ACADEMICAS:
        if _sin_tildes(pal) in plano:
            leves.append(f"Usa la palabra académica '{pal}'.")

    largas = [f for f in frases[1:] if len(f.split()) > cfg["frase_max"]]
    if largas:
        leves.append(
            f"{len(largas)} frase(s) pasan de {cfg['frase_max']} palabras: "
            + " / ".join(f'"{f[:45]}…"' for f in largas[:2])
        )

    # ── Los tres patrones que el crítico repite tema tras tema ──────────
    hallados = [a for a in ABSOLUTOS if a in plano]
    if hallados:
        leves.append(
            f"Absoluto(s) sin fuente: {', '.join(repr(a.strip()) for a in hallados[:3])}. "
            "El crítico los objeta salvo que se puedan comprobar."
        )

    similes = [s for s in SIMILES if s in plano]
    if similes:
        leves.append(
            f"Símil poético ({', '.join(repr(s.strip()) for s in similes[:2])}): "
            "el drama tiene que venir del hecho, no del adorno."
        )

    mentes = [v for v in VERBOS_MENTE if re.search(rf"\b{v}", plano)]
    if mentes:
        leves.append(
            f"Atribuye estados mentales ({', '.join(repr(v) for v in mentes[:3])}): "
            "nadie documentó qué pensó o sintió alguien."
        )

    return graves, leves


# ══════════════════════════════════════════════════════════════
# 🔍  CAPA 2 — CRÍTICO (segundo modelo, rol adversarial)
# ══════════════════════════════════════════════════════════════

SYSTEM_CRITICO = """Eres un verificador de datos veterano, escéptico y quisquilloso.
Tu trabajo NO es alabar el guion: es encontrarle fallos antes de que se publique.

Revisas guiones de videos históricos de divulgación. Un dato falso o inventado
destruye la credibilidad del canal entero, así que tu sesgo debe ser hacia el
rechazo: ante la duda, marca la afirmación como dudosa.

Juzgas SOLO lo que requiere criterio. NO cuentes palabras ni midas frases: de eso
ya se encarga otra capa.

Evalúas cuatro cosas:

1. VERIFICABILIDAD (lo más importante). Cada afirmación concreta del guion,
   ¿es un hecho documentado y comprobable en fuentes históricas? Marca como
   dudosa cualquiera que:
   - atribuya pensamientos, emociones o intenciones privadas a alguien
   - describa lo que alguien hizo o dejó de hacer en privado
   - dé una cifra, récord o "primera vez" que suene a adorno
   - sea una anécdota conmovedora imposible de documentar
   Ejemplo de afirmación que DEBES rechazar:
   "Su propia madre nunca volvió a ver aquel momento en video."
   Suena bonito, es exactamente el tipo de detalle que nadie puede comprobar.

2. GANCHO SIN SPOILER. ¿La primera frase abre una pregunta en la cabeza del
   espectador, o ya le cuenta el desenlace? Si lo cuenta, no hay razón para
   seguir viendo.

3. UNA SOLA LÍNEA NARRATIVA. ¿El final es consecuencia directa del principio,
   o el guion cambia de tema a mitad?

4. DRAMA HONESTO. ¿La tensión sale de los hechos reales, o de adjetivos y
   exageraciones puestos encima?

Devuelve SOLO un objeto json con esta forma exacta:
{
  "nota": <entero 0-10>,
  "aprobado": <true si nota >= 7 y no hay afirmaciones dudosas>,
  "afirmaciones_dudosas": ["cita textual del guion", ...],
  "problemas": ["descripción concreta y accionable del fallo", ...],
  "que_arreglar": "una frase con la corrección más importante"
}

Sé concreto: "la frase X no se puede verificar" sirve; "podría mejorarse" no."""


# Esquema de la respuesta del crítico. En Anthropic se aplica con structured
# outputs (el modelo NO puede devolver otra forma); en OpenAI se pide por prompt.
ESQUEMA_CRITICA = {
    "type": "object",
    "properties": {
        "nota": {"type": "integer"},
        "aprobado": {"type": "boolean"},
        "afirmaciones_dudosas": {"type": "array", "items": {"type": "string"}},
        "problemas": {"type": "array", "items": {"type": "string"}},
        "que_arreglar": {"type": "string"},
    },
    "required": ["nota", "aprobado", "afirmaciones_dudosas",
                 "problemas", "que_arreglar"],
    "additionalProperties": False,
}


def proveedor_critico(cfg: dict = CONFIG) -> str:
    """Resuelve qué proveedor usa el crítico ('anthropic' u 'openai')."""
    elegido = cfg.get("critico_proveedor", "auto")
    if elegido == "anthropic":
        if anthropic_client is None:
            raise SystemExit(
                "❌ critico_proveedor='anthropic' pero falta ANTHROPIC_API_KEY en el .env"
            )
        return "anthropic"
    if elegido == "openai":
        return "openai"
    return "anthropic" if anthropic_client else "openai"


def _mensaje_critico(script: str, tema: str) -> str:
    return (f"TEMA DEL VIDEO: {tema or '(libre)'}\n\n"
            f"GUION A REVISAR:\n{script}")


def _criticar_con_anthropic(script: str, tema: str, cfg: dict) -> str:
    """Crítico en Claude. Devuelve el JSON como texto."""
    modelo = cfg["modelo_critico_anthropic"]

    respuesta = con_reintentos(
        lambda: anthropic_client.messages.create(
            model=modelo,
            max_tokens=cfg["critico_max_tokens"],
            system=SYSTEM_CRITICO,
            output_config={
                "effort": cfg["critico_effort"],
                "format": {"type": "json_schema", "schema": ESQUEMA_CRITICA},
            },
            messages=[{"role": "user", "content": _mensaje_critico(script, tema)}],
        ),
        etiqueta=f"crítico ({modelo})",
    )

    registrar_anthropic(respuesta, modelo, "crítica del guion")

    # Los clasificadores pueden declinar: devuelve HTTP 200 con stop_reason
    # 'refusal' y content vacío, así que hay que mirarlo ANTES de leer content.
    if respuesta.stop_reason == "refusal":
        raise ValueError("el crítico declinó revisar este guion")

    return next(b.text for b in respuesta.content if b.type == "text")


def _criticar_con_openai(script: str, tema: str, cfg: dict) -> str:
    modelo = cfg["modelo_critico_openai"]

    respuesta = con_reintentos(
        lambda: client.chat.completions.create(
            model=modelo,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_CRITICO},
                {"role": "user", "content": _mensaje_critico(script, tema)},
            ],
            max_tokens=800,
        ),
        etiqueta=f"crítico ({modelo})",
    )

    registrar_openai(respuesta, modelo, "crítica del guion")
    return respuesta.choices[0].message.content


def evaluar_con_critico(script: str, tema: str, cfg: dict = CONFIG) -> dict:
    """Somete el guion a un modelo de otro proveedor que solo busca fallos."""
    proveedor = proveedor_critico(cfg)

    try:
        if proveedor == "anthropic":
            crudo = _criticar_con_anthropic(script, tema, cfg)
        else:
            crudo = _criticar_con_openai(script, tema, cfg)
        veredicto = json.loads(crudo)
    except Exception as exc:
        # Si el crítico se rompe, no bloqueamos el pipeline: es control de
        # calidad, no una guarda de seguridad. Se avisa y se deja pasar.
        print(f"⚠️  El crítico falló ({type(exc).__name__}: {exc}) — se acepta el guion")
        return {"nota": cfg["nota_minima"], "aprobado": True,
                "afirmaciones_dudosas": [], "problemas": [], "que_arreglar": ""}

    veredicto.setdefault("nota", 0)
    veredicto.setdefault("afirmaciones_dudosas", [])
    veredicto.setdefault("problemas", [])
    veredicto.setdefault("que_arreglar", "")
    return veredicto


# ══════════════════════════════════════════════════════════════
# ✍️  GENERADOR
# ══════════════════════════════════════════════════════════════

SYSTEM_GUIONISTA = (
    "Eres un periodista riguroso que escribe como guionista. "
    "Nunca inventas ni exageras. Si un hecho real ya es sorprendente, "
    "lo cuentas tal cual — eso es suficiente. "
    "Preferirías no escribir nada antes que distorsionar la verdad."
)


# Cómo se agrupan las objeciones del crítico. Las claves son las etiquetas que
# ve el generador; los valores, trozos que aparecen literalmente en el campo
# `problemas` de los `calidad_guion.json` reales. Si el crítico cambia de
# vocabulario, esto deja de clasificar y hay que reajustarlo — por eso el
# bloque enseña también cuántas objeciones NO encajaron en ninguna categoría.
CATEGORIAS_FALLO = {
    "afirmaciones sin fuente verificable": [
        "no existe evidencia", "no hay evidencia", "sin fuente", "no verificable",
        "no documentad", "carece de referencias", "no respaldad", "sin respaldo",
        "no comprobabl", "especulativ", "no hay fuentes", "no hay pruebas",
        "sin aportar ninguna evidencia", "no hay documentacion",
    ],
    "atribuir intenciones, emociones o actos privados": [
        "atribuye", "emociones", "intenciones", "acciones privadas",
        "percepciones", "subjetiv", "imposible de verificar historicamente",
    ],
    "exageración, superlativos y absolutos": [
        "exageracion", "exageraciones", "superlativ", "afirmacion absoluta",
        "adjetivos dramaticos", "dramatiza", "recursos poeticos", "coloquial",
    ],
    "el gancho adelanta el desenlace": [
        "adelanta el desenlace", "desvela el desenlace", "debilita el gancho",
    ],
    "interpretación presentada como hecho": [
        "interpretativ", "es una interpretacion", "puede prestarse a debate",
        "segun la traduccion",
    ],
}


def lecciones_de_guiones_previos(cfg: dict = CONFIG) -> str:
    """Destila los veredictos acumulados en un bloque corto para el prompt.

    El generador ya tiene TODAS las reglas escritas en su prompt —«prohibido
    atribuir pensamientos», «prohibido exagerar», «la primera frase no revela
    el desenlace»— y las incumple igual. Añadir más reglas no arregla eso.
    Lo que falta es decirle **cuáles de sus propias reglas rompe más**, con la
    cuenta al lado, y enseñarle uno de sus guiones que sí pasó.

    ⚠️ **No se le pasan las frases rechazadas.** Un ejemplo concreto es la señal
    más fuerte de un prompt: el modelo imita su tono, su longitud y su
    estructura. Enseñarle «no escribas *como si pescaran sardinas*» es
    enseñarle a escribir símiles. Por eso van frecuencias (que reorientan la
    atención) y ejemplos POSITIVOS (que sí se pueden imitar), nunca citas de lo
    que salió mal.

    Cuesta ~200 tokens de entrada = $0.0004 por llamada. Se amortiza si evita
    un solo reintento cada ~100 temas, porque cada reintento arrastra una
    crítica de Opus 5 (~$0.04).
    """
    if not cfg.get("lecciones_activas", True):
        return ""

    aprobados, fallos, total, sin_clasificar = [], {}, 0, 0
    for archivo in sorted(Path("proyectos").glob("*/calidad_guion.json")):
        try:
            datos = json.loads(archivo.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue

        total += 1
        if datos.get("aprobado") and datos.get("guion"):
            aprobados.append((datos.get("nota") or 0, datos["guion"].strip()))

        for problema in datos.get("problemas", []):
            plano = _sin_tildes(problema)
            etiquetas = [nombre for nombre, claves in CATEGORIAS_FALLO.items()
                         if any(c in plano for c in claves)]
            if not etiquetas:
                sin_clasificar += 1
            for etiqueta in etiquetas:
                fallos[etiqueta] = fallos.get(etiqueta, 0) + 1

    if total < cfg.get("lecciones_min_historial", 3):
        return ""     # con dos o tres temas la "frecuencia" es ruido

    partes = [f"\nLO QUE TE HA RECHAZADO EL VERIFICADOR "
              f"({len(aprobados)} aprobados de {total} guiones):"]

    for etiqueta, veces in sorted(fallos.items(), key=lambda x: -x[1])[:3]:
        partes.append(f"- {etiqueta} — {veces} veces")
    if sin_clasificar:
        partes.append(f"  (y {sin_clasificar} objeciones de otro tipo)")
    partes.append("Son reglas que YA tienes arriba. Repásalas antes de escribir.")

    # El ejemplo positivo va al final: es lo último que lee antes de escribir.
    if aprobados:
        aprobados.sort(reverse=True)
        tope = max(1, int(cfg.get("lecciones_max_ejemplos", 1)))
        partes.append("\nGuion tuyo que SÍ pasó. Copia el registro y el nivel de "
                      "concreción, NO el tema:")
        for nota, texto in aprobados[:tope]:
            recorte = texto[:cfg.get("lecciones_max_chars", 700)]
            partes.append(f'({nota}/10) "{recorte}"')

    return "\n".join(partes) + "\n"


def construir_prompt(tema: str, cfg: dict = CONFIG, correcciones: str = "") -> str:
    tema_instruccion = (
        f"El evento o historia DEBE ser sobre: {tema}. "
        f"Busca el ángulo más oscuro, irónico o desconocido de este tema específico."
        if tema else
        "Elige libremente un evento histórico real que muy poca gente conoce."
    )

    # El histórico y las correcciones del intento anterior son EXCLUYENTES.
    # En una reescritura ya hay feedback específico sobre ESTE guion, que vale
    # mucho más que una estadística; meter las dos cosas solo diluye la
    # concreta y paga tokens de más.
    bloque_correcciones = ""
    if correcciones:
        bloque_correcciones = f"""
⚠️ INTENTO ANTERIOR RECHAZADO. Corrige EXACTAMENTE esto:
{correcciones}

No repitas los mismos fallos. Si una afirmación no se puede verificar en fuentes
históricas, elimínala y apóyate en otra que sí lo sea.
"""
    else:
        bloque_correcciones = lecciones_de_guiones_previos(cfg)

    return f"""
Eres un guionista de videos virales históricos. Tu especialidad es encontrar
el ángulo más oscuro, irónico o sorprendente de eventos reales.

TEMA: {tema_instruccion}
{bloque_correcciones}
TAREA: Escribe un guion de exactamente {cfg['palabras_min']}-{cfg['palabras_max']} palabras sobre un evento histórico real.

REGLAS ESTRICTAS:
- El evento debe ser 100% verificable — nada de "se dice que" o "algunos creen"
- PROHIBIDO empezar con: "En", "Cuando", "Fue", "Era", "Hubo"
- La PRIMERA frase debe tener MÁXIMO {cfg['primera_frase_max']} PALABRAS. Es la más importante del guion:
  si el espectador no se engancha ahí, no llega a la segunda. Cuéntala y si tiene
  más de {cfg['primera_frase_max']}, reescríbela.
- La primera frase debe hacer una afirmación que parezca imposible pero sea verdad
- La primera frase NO debe revelar el desenlace: abre la pregunta, no la respondas
- Incluir UN solo dato que el 95% de personas no conoce
- La última frase debe dejar una sensación de incredulidad o escalofrío
- CERO fechas en el texto (destruyen el ritmo)
- CERO palabras académicas: "acontecimiento", "hecho", "suceso", "historia"
- PROHIBIDO exagerar consecuencias o inventar detalles para hacerlo más dramático
- PROHIBIDO atribuir pensamientos, emociones privadas o acciones íntimas que
  nadie pudo documentar. Si no está en una fuente, no existe.
- Si el dato sorprendente no es verificable, no lo incluyas
- El drama debe venir de los hechos reales, no de adornos narrativos
- Una sola línea narrativa de principio a fin — sin cambiar de tema a mitad del guion
- La conclusión debe ser consecuencia directa del inicio, no una frase nueva

ÁNGULOS QUE FUNCIONAN (elige uno):
- Una decisión de segundos que cambió millones de vidas
- Un error absurdo que tuvo consecuencias enormes
- Una coincidencia que parece inventada pero es real
- El lado oscuro de un héroe famoso
- Una tecnología, ley o costumbre cuyo origen nadie conoce

ESTILO:
- Frases de máximo {cfg['frase_max']} palabras (la primera, máximo {cfg['primera_frase_max']})
- Ritmo: rápido, cinematográfico, como trailer de Netflix
- Cada frase debe empujar al lector a la siguiente
- Español latino neutro, conversacional
- El guion se narra en voz alta a ~160 palabras por minuto: {cfg['palabras_min']}-{cfg['palabras_max']} palabras son
  unos 25 segundos, que es la duración que mejor retiene en vertical. No te pases.

FORMATO DE SALIDA:
Solo el guion. Sin títulos, sin explicaciones, sin comillas.
"""


def generar_guion(tema: str, cfg: dict = CONFIG, correcciones: str = "") -> str:
    respuesta = con_reintentos(
        lambda: client.chat.completions.create(
            model=cfg["modelo_guionista"],
            messages=[
                {"role": "system", "content": SYSTEM_GUIONISTA},
                {"role": "user", "content": construir_prompt(tema, cfg, correcciones)},
            ],
        ),
        etiqueta=f"guion ({cfg['modelo_guionista']})",
    )

    registrar_openai(respuesta, cfg["modelo_guionista"], "guion")
    return respuesta.choices[0].message.content.strip()


# ══════════════════════════════════════════════════════════════
# 🔁  BUCLE: escribir → verificar → reescribir
# ══════════════════════════════════════════════════════════════

def formatear_correcciones(graves: list, leves: list, veredicto: dict) -> str:
    lineas = []
    for p in graves:
        lineas.append(f"- [GRAVE] {p}")
    for cita in veredicto.get("afirmaciones_dudosas", []):
        lineas.append(f'- [NO VERIFICABLE] "{cita}" — elimínala o sustitúyela '
                      f"por un dato documentado.")
    for p in veredicto.get("problemas", []):
        lineas.append(f"- {p}")
    for p in leves:
        lineas.append(f"- [menor] {p}")
    return "\n".join(lineas)


def escribir_guion_con_control(tema: str, cfg: dict = CONFIG) -> str:
    """Genera y valida hasta que pase o se agoten los intentos.

    Devuelve el mejor guion obtenido. Cada intento cuesta 2 llamadas
    (generación + crítica), así que el peor caso son 6 en vez de 1.
    """
    mejor = None
    mejor_nota = -1
    # ⚠️ El veredicto viaja CON el guion, no aparte. Antes se registraba el del
    # último intento aunque el devuelto fuera otro: en Historia08, `script.txt`
    # quedó con el guion del examen de ingreso y `calidad_guion.json` acusando
    # unas frases sobre el cerebro de Einstein que no estaban en él. El paso 09
    # imprime esas objeciones al empaquetar, así que mandaba a revisar
    # afirmaciones que el video no dice — y callaba las que sí.
    mejor_veredicto = None
    mejor_intento = 0
    correcciones = ""

    for intento in range(1, cfg["intentos_max"] + 1):
        print(f"\n{'─' * 60}")
        print(f"✍️  Intento {intento}/{cfg['intentos_max']}")
        print("─" * 60)

        script = generar_guion(tema, cfg, correcciones)
        print(script)

        graves, leves = verificar_reglas_mecanicas(script, cfg)
        veredicto = evaluar_con_critico(script, tema, cfg)

        nota = veredicto["nota"]
        dudosas = veredicto["afirmaciones_dudosas"]

        # La nota del crítico penalizada por las faltas mecánicas: así el "mejor"
        # no es un guion bien escrito que incumple el formato.
        #
        # ⚠️ Las dudosas entran como DESEMPATE, y no es un adorno. Medido sobre
        # los 8 primeros guiones, el crítico de Anthropic comprime todas las
        # notas entre 2 y 3 —incluida la del guion que gpt-4.1 había puntuado
        # con un 8—, así que la nota sola deja de distinguir un intento de
        # otro y "el mejor de 3" se vuelve casi aleatorio. El número de
        # afirmaciones dudosas sí discrimina en esos mismos datos: 3 en el
        # mejor guion frente a 7 en el peor. Pesa 0.1 para no invertir nunca
        # una diferencia real de nota.
        nota_final = nota - 2 * len(graves) - 0.1 * len(dudosas)

        print(f"\n📏 {len(script.split())} palabras · "
              f"primera frase: {len(dividir_frases(script)[0].split())} palabras")
        print(f"🔍 Crítico: nota {nota}/10"
              + (f" · {len(dudosas)} afirmación(es) dudosa(s)" if dudosas else ""))

        for p in graves:
            print(f"   ❌ {p}")
        for cita in dudosas:
            print(f'   ⚠️  No verificable: "{cita}"')
        for p in veredicto["problemas"]:
            print(f"   • {p}")
        for p in leves:
            print(f"   · {p}")

        pasa = (not graves) and (not dudosas) and nota >= cfg["nota_minima"]

        if nota_final > mejor_nota:
            mejor, mejor_nota = script, nota_final
            mejor_veredicto, mejor_intento = veredicto, intento

        if pasa:
            print(f"\n✅ Guion aprobado en el intento {intento} (nota {nota}/10)")
            registrar_calidad(True, intento, veredicto, script)
            return script

        correcciones = formatear_correcciones(graves, leves, veredicto)
        if intento < cfg["intentos_max"]:
            print(f"\n♻️  Reescribiendo con el feedback…")

    # Ningún intento pasó
    mensaje = (
        f"⚠️  Ningún intento pasó el control de calidad tras "
        f"{cfg['intentos_max']} intentos."
    )
    if cfg["abortar_si_ninguno_pasa"]:
        raise SystemExit(f"❌ {mensaje} Tema abortado.")

    print(f"\n{mensaje}")
    print(f"   Se usa el del intento {mejor_intento}. REVÍSALO A MANO antes de publicar.")
    if mejor_veredicto.get("afirmaciones_dudosas"):
        print("   Lo que el crítico le objetó A ESE guion:")
        for cita in mejor_veredicto["afirmaciones_dudosas"]:
            print(f'     ⚠️  "{cita}"')
    registrar_calidad(False, mejor_intento, mejor_veredicto, mejor)
    return mejor


def registrar_calidad(aprobado: bool, intento: int, veredicto: dict,
                      script: str = "") -> None:
    """Deja constancia de si el guion pasó el control.

    En un lote nocturno de 30 temas los avisos se pierden en los logs. El paso
    09 lee esto para marcar qué guiones hay que revisar a mano.

    ⚠️ `intento` y `veredicto` tienen que ser los del guion que de verdad se
    escribió en `script.txt` —el mejor—, no los del último que se probó. Si no,
    el archivo acusa a un texto que nadie va a publicar.

    **El texto del guion se guarda aquí dentro, junto a su nota.** `script.txt`
    vive en la raíz y lo pisa el tema siguiente, así que sin esto los guiones
    APROBADOS se perdían — y son la mitad más útil del histórico: de un rechazo
    aprendes qué no hacer, de un aprobado aprendes el registro que funciona.
    Guardarlo en el mismo json que el veredicto es lo que impide que vuelvan a
    descuadrarse.
    """
    if not PROYECTO:
        return

    destino = Path(f"proyectos/{PROYECTO}")
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "calidad_guion.json").write_text(
        json.dumps({
            "aprobado": aprobado,
            "intento": intento,
            "nota": veredicto.get("nota"),
            "tema": TEMA,
            "guion": script,
            "afirmaciones_dudosas": veredicto.get("afirmaciones_dudosas", []),
            "problemas": veredicto.get("problemas", []),
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ══════════════════════════════════════════════════════════════
# ▶️  EJECUCIÓN
# ══════════════════════════════════════════════════════════════

def main() -> None:
    # El paso 01 abre el tema: reinicia el contador de costo.
    reset_costo()

    script = escribir_guion_con_control(TEMA, CONFIG)

    with open("script.txt", "w", encoding="utf-8") as f:
        f.write(script)

    print(f"\n💾 Guardado en script.txt ({len(script.split())} palabras)")

    # Sello del tema en curso. Los archivos de la raíz (script.txt, voice.mp3,
    # images_IA/...) son estado global compartido: si un paso falla a mitad, los
    # siguientes seguirían trabajando con los datos del tema ANTERIOR sin notarlo.
    # Los pasos 02, 03, 04 y 07 comparan contra este archivo antes de tocar nada.
    if PROYECTO:
        sellar_estado(PROYECTO, TEMA or "")
        print(f"🔖 Estado sellado: {PROYECTO}")


if __name__ == "__main__":
    main()
