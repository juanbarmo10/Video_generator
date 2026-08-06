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
from openai import OpenAI

from estado import sellar_estado, reset_costo, registrar_openai, con_reintentos

load_dotenv()

# ========================================================================== #

TEMA = os.environ.get("TEMA")
PROYECTO = os.environ.get("PROYECTO")
openai_api_key = os.getenv("OPENAI_API_KEY")

if not openai_api_key:
    raise SystemExit("❌ Falta OPENAI_API_KEY en el .env")

client = OpenAI(api_key=openai_api_key)

# ========================================================================== #

CONFIG = {
    # ── Modelos ───────────────────────────────────────────────
    "modelo_guionista": "gpt-4.1",
    # El crítico necesita criterio para juzgar verificabilidad histórica: no lo
    # bajes a un modelo pequeño para ahorrar, es justo donde hace falta cabeza.
    # Si algún día quieres un crítico de OTRO proveedor (juicio menos
    # correlacionado con el del generador), este es el único punto a tocar.
    "modelo_critico": "gpt-4.1",

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


def evaluar_con_critico(script: str, tema: str, cfg: dict = CONFIG) -> dict:
    """Somete el guion a un segundo modelo que solo busca fallos."""
    respuesta = con_reintentos(
        lambda: client.chat.completions.create(
            model=cfg["modelo_critico"],
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_CRITICO},
                {"role": "user", "content": (
                    f"TEMA DEL VIDEO: {tema or '(libre)'}\n\n"
                    f"GUION A REVISAR:\n{script}"
                )},
            ],
            max_tokens=800,
        ),
        etiqueta=f"crítico ({cfg['modelo_critico']})",
    )

    registrar_openai(respuesta, cfg["modelo_critico"], "crítica del guion")

    try:
        veredicto = json.loads(respuesta.choices[0].message.content)
    except json.JSONDecodeError:
        # Si el crítico se rompe, no bloqueamos el pipeline: es control de
        # calidad, no una guarda de seguridad. Se avisa y se deja pasar.
        print("⚠️  El crítico no devolvió json válido — se acepta el guion")
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


def construir_prompt(tema: str, cfg: dict = CONFIG, correcciones: str = "") -> str:
    tema_instruccion = (
        f"El evento o historia DEBE ser sobre: {tema}. "
        f"Busca el ángulo más oscuro, irónico o desconocido de este tema específico."
        if tema else
        "Elige libremente un evento histórico real que muy poca gente conoce."
    )

    bloque_correcciones = ""
    if correcciones:
        bloque_correcciones = f"""
⚠️ INTENTO ANTERIOR RECHAZADO. Corrige EXACTAMENTE esto:
{correcciones}

No repitas los mismos fallos. Si una afirmación no se puede verificar en fuentes
históricas, elimínala y apóyate en otra que sí lo sea.
"""

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
        nota_final = nota - 2 * len(graves)

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

        if pasa:
            print(f"\n✅ Guion aprobado en el intento {intento} (nota {nota}/10)")
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
    print("   Se usa el mejor de los intentos. REVÍSALO A MANO antes de publicar.")
    return mejor


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
