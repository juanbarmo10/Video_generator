
#%%


import os
import re
import json
from openai import OpenAI
from dotenv import load_dotenv
import shutil
from pathlib import Path

from estado import verificar_estado, registrar_openai, resumen_costo

load_dotenv()

# ========================================================================== #
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Aborta si script.txt es de otro tema (ver estado.py)
verificar_estado("paso 02")

PROYECTO = os.environ.get("PROYECTO")

if not PROYECTO:
    raise SystemExit(
        "❌ Falta PROYECTO (entorno o .env). Sin él el respaldo iría a 'proyectos//'."
    )

# ========================================================================== #

def read_script(path="script.txt") -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def research_real_history(script: str) -> str:
    """Busca la historia real detrás del script usando web search."""
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": (
                "Eres un historiador e investigador. "
                "Dado un resumen de una historia, extrae: "
                "1) El evento histórico real al que se refiere "
                "2) Personajes principales reales "
                "3) Fecha y lugar exactos "
                "4) 3 datos curiosos adicionales que no estén en el resumen "
                "5) Fuentes históricas confiables que lo respalden. "
                "Sé conciso y factual."
            )},
            {"role": "user", "content": f"Investiga la historia real detrás de este script:\n\n{script}"}
        ],
        #tools=[{"type": "web_search_preview"}],
        max_tokens=800
    )
    registrar_openai(response, "gpt-4.1", "investigación")
    return response.choices[0].message.content

SYSTEM_REDACTOR = (
    "Eres un experto en marketing de contenido histórico viral. "
    "Creas contenido que educa y engancha al mismo tiempo. "
    "Usas los datos reales de la investigación para dar credibilidad. "
    "Siempre escribes en español latino neutro."
)


def _contexto(script: str, research: str) -> str:
    return f"""
SCRIPT DEL VIDEO:
{script}

INVESTIGACIÓN HISTÓRICA REAL:
{research}
"""


def generar_descripcion_general(script: str, research: str) -> str:
    """UNA descripción que sirve para el mismo reel en todas las redes.

    El mismo video se sube a Reels de Facebook, Reels de Instagram, TikTok y
    Shorts de YouTube con el mismo texto, así que esto no puede mencionar
    ninguna plataforma en concreto ni asumir funciones que solo tenga una.
    """
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": SYSTEM_REDACTOR},
            {"role": "user", "content": f"""Escribe UNA descripción para acompañar este video
vertical. El MISMO texto se publica en Reels de Facebook, Reels de Instagram,
TikTok y Shorts de YouTube.

Reglas:
- Primera línea: gancho que pare el scroll. Es lo único que se ve antes del
  "ver más", así que se juega todo ahí. NO reveles el desenlace.
- Después: 2 o 3 líneas cortas de contexto, con saltos de línea entre ellas.
- Penúltima línea: una pregunta abierta que invite a comentar.
- Última línea: entre 8 y 12 hashtags, mezclando amplios y de nicho.
- PROHIBIDO nombrar una red concreta ("link en bio", "desliza", "guarda este
  post"): el mismo texto va a las cuatro y esas funciones no existen en todas.
- Sin emojis.
- Máximo 600 caracteres contando los hashtags. Es un pie de reel, no un ensayo.

Solo el texto, sin encabezados ni explicaciones.

{_contexto(script, research)}"""},
        ],
        max_tokens=600,
    )

    registrar_openai(response, "gpt-4.1", "descripción general")
    return response.choices[0].message.content.strip()


def generar_descripcion_detallada(script: str, research: str) -> dict:
    """Título de YouTube, descripción larga, tags y comentario para fijar.

    Devuelve json para que el paso 09 pueda leer el título sin parsear prosa.
    """
    response = client.chat.completions.create(
        model="gpt-4.1",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": (
                SYSTEM_REDACTOR + "\n\nDevuelve SOLO un objeto json con estas claves:\n"
                '- "titulo": título para YouTube, máximo 70 caracteres. La ENTIDAD '
                'PRINCIPAL (persona, equipo, lugar) va al inicio porque es la señal '
                'temática que lee el algoritmo. Genera curiosidad SIN revelar el '
                'desenlace. Sin clickbait falso.\n'
                '- "descripcion": entre 250 y 300 palabras, y NUNCA más de 1700 '
                'caracteres: debajo se le pegan los hashtags y el bloque entero tiene '
                'un tope de 1999. Tono emotivo y reflexivo, como una historia que vale '
                'la pena compartir. Incluye el contexto histórico adicional de la '
                'investigación que no cabe en el video. Separa en párrafos con una línea '
                'en blanco. El ÚLTIMO párrafo cierra con una pregunta que genere debate '
                '(si hay que recortar, es el que se conserva). Sirve tanto para la '
                'descripción de YouTube como para el post largo de Facebook.\n'
                '- "tags": lista de 12 strings, mezclando términos amplios y de nicho\n'
                '- "comentario_fijado": una pregunta abierta para fijar en comentarios'
            )},
            {"role": "user", "content": _contexto(script, research)},
        ],
        max_tokens=1500,
    )

    registrar_openai(response, "gpt-4.1", "descripción detallada")

    try:
        return json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        print("⚠️  La descripción detallada no vino en JSON válido")
        return {}


def generar_texto_carrusel(script: str, research: str) -> str:
    """Texto del carrusel de Instagram — NO es una descripción de publicación.

    ⚠️ El formato es un CONTRATO con el paso 06: párrafos separados por línea en
    blanco, el primero es la portada, el último antes de los hashtags es el CTA.
    Si cambias esto, se rompe el parseo del carrusel.
    """
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": SYSTEM_REDACTOR},
            {"role": "user", "content": f"""Crea el texto de un carrusel de Instagram
sobre esta historia. Cada párrafo se quema encima de una imagen distinta.

Reglas de contenido:
- Primera línea: gancho (termina con "..." para forzar "ver más")
- Sin emojis
- CTA al final antes de los hashtags: "Guarda este post para no olvidarlo"
- 20-25 hashtags al final mezclando grandes y nicho
- 6 slides contando la portada y el cta
- No más de 120 caracteres por slide

Reglas de formato ESTRICTAS:
- Cada slide es un párrafo separado por una línea en blanco
- NO escribas "Slide 1", "Slide 2", ni ningún encabezado, etiqueta o número
- NO uses corchetes, guiones ni ningún indicador de slide
- Solo texto plano, párrafo por párrafo
- El output debe verse exactamente así:

Gancho impactante que termina en...

Texto del slide 2 con dato histórico.

Texto del slide 3 con otro dato.

Guarda este post para no olvidarlo

#hashtag1 #hashtag2 #hashtag3

{_contexto(script, research)}"""},
        ],
        max_tokens=1200,
    )

    registrar_openai(response, "gpt-4.1", "texto carrusel")
    return response.choices[0].message.content


def generate_image_descriptions(instagram_content: str, script: str) -> list:

    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[

            {
                "role": "system",
                "content": (
                    "Eres experto en selección de imágenes para contenido viral histórico.\n\n"

                    "OBJETIVO:\n"
                    "Mantener coherencia visual entre slides.\n\n"

                    "REGLAS IMPORTANTES:\n"
                    "- Prioriza SIEMPRE el personaje principal.\n"
                    "- El protagonista debe aparecer en al menos 2 queries.\n"
                    "- Solo usa personas, lugares, equipos, organizaciones u objetos DIRECTAMENTE relacionados con la historia.\n"
                    "- NO uses conceptos abstractos.\n"
                    "- NO uses fechas.\n"
                    "- NO uses emociones.\n"
                    "- NO uses palabras genéricas.\n"
                    "- NO inventes entidades.\n"
                    "- Si faltan entidades, REPITE el protagonista con variaciones.\n\n"
                    
                    """ Las queries deben ser fácilmente buscables en Google Images,
                    Wikipedia Commons o DuckDuckGo Images.

                    Usa únicamente:
                    - nombres reales de personas
                    - lugares
                    - equipos
                    - estadios
                    - objetos famosos o genéricos MUY comunes

                    NO combines conceptos raros o escenas completas.

                    Las queries deben parecer títulos reales de fotografías

                    Si lo principal es un objeto (ej: Cerveza, Guitarra, etc) que ese sea el protagonista
                    
                    Evita acciones o frases largas
                    
                    La primera y la ultima descripción deben tener al protagonista"""

                    "FORMATO:\n"
                    "- Máximo 5 palabras por query\n"
                    "- En inglés\n"
                    "- Una query por línea\n"
                    "- Sin numeración\n"
                    "- Sin guiones\n"
                    "- Sin explicaciones\n\n"

                    "BUENAS queries:\n"
                    "Michael Jackson Thriller\n"
                    "Michael Jackson studio\n"
                    "Quincy Jones studio\n"
                    "Parc des Princes PSG\n\n"

                    "MALAS queries:\n"
                    "Sad atmosphere\n"
                    "1980s mystery\n"
                    "Broken dreams\n"
                    "Football transfer"
                )
            },

            {
                "role": "user",
                "content": (
                    f"SCRIPT:\n{script}\n\n"
                    f"CARRUSEL:\n{instagram_content}\n\n"

                    "Genera EXACTAMENTE 6 queries.\n"
                    "El personaje, lugar u objeto principal debe aparecer en al menos 2 queries."
                )
            }
        ],

        temperature=0.2,
        max_tokens=120
    )

    registrar_openai(response, "gpt-4.1", "queries imagen")

    raw = response.choices[0].message.content.strip()

    lines = [
        re.sub(r'^\d+[\.\)]\-?\s*', '', l.strip())
        for l in raw.split("\n")
        if l.strip()
    ]

    return lines[:6]

# EL archivo que se publica. El resto de lo que hay en social_posts/ son
# insumos internos de otros pasos, no textos para copiar y pegar.
ARCHIVO_DESCRIPCION = "descripcion.txt"
ARCHIVO_CARRUSEL = "carrusel.txt"          # insumo del paso 06

# Tope duro del bloque "descripción larga + hashtags", que es como se pega.
# El prompt pide menos para que el recorte casi nunca haga falta, pero el que
# garantiza el límite es Python: a un LLM no se le pide que cuente caracteres.
LIMITE_DESCRIPCION_LARGA = 1999

# Tope del título de YouTube. Pasado eso, la búsqueda lo corta con puntos
# suspensivos: lo que sobra no se ve feo, no se ve. Mismo reparto de
# responsabilidad que arriba — el prompt lo pide, `acortar_titulo()` lo cumple.
LIMITE_TITULO = 70


def separar_hashtags(texto: str) -> tuple[str, str]:
    """Parte la descripción general en (cuerpo, hashtags).

    El prompt pide los hashtags en la última línea, pero el modelo a veces los
    reparte en dos. Se recorren las líneas desde el final y se toman como
    hashtags todas las que solo contienen tokens que empiezan por '#'.

    Si no hay ninguna, devuelve (texto, "") — el archivo sale sin sección de
    hashtags en vez de romperse.
    """
    lineas = texto.strip().split("\n")
    corte = len(lineas)

    for i in range(len(lineas) - 1, -1, -1):
        tokens = lineas[i].split()
        if not tokens:                       # línea en blanco: sigue mirando
            continue
        if all(t.startswith("#") for t in tokens):
            corte = i
        else:
            break

    cuerpo = "\n".join(lineas[:corte]).strip()
    hashtags = " ".join(" ".join(lineas[corte:]).split())
    return cuerpo, hashtags


def _cortar_en_frase(texto: str, espacio: int) -> str:
    """El trozo más largo de `texto` que quepa en `espacio` y acabe en punto."""
    if espacio <= 0:
        return ""
    if len(texto) <= espacio:
        return texto
    corte = max(texto.rfind(s, 0, espacio + 1) for s in (". ", "! ", "? ", "… "))
    return texto[:corte + 1].strip() if corte > 0 else ""


def _truncar_titulo(titulo: str, limite: int) -> str:
    """Último recurso: corta el título sin partir una palabra por la mitad.

    Prefiere cortar en un límite de cláusula (`:` `—` `,`) porque estos títulos
    tienen forma "Entidad: gancho" y quedarse con la entidad sola es mejor que
    dejar el gancho a medias. Si no hay ninguno, corta en la última palabra.
    """
    if len(titulo) <= limite:
        return titulo

    for marca in (": ", " — ", " - ", ", "):
        corte = titulo.rfind(marca, 0, limite + 1)
        if corte > limite // 2:            # que no deje un muñón de dos palabras
            return titulo[:corte].strip()

    corte = titulo.rfind(" ", 0, limite + 1)
    recortado = titulo[:corte] if corte > 0 else titulo[:limite]

    # Quita las palabras vacías del final: cortar por longitud deja títulos que
    # acaban en "que Cambió la" o "ante los ojos del", y eso se lee como un
    # error, no como un título corto.
    COLGANTES = {"el", "la", "los", "las", "un", "una", "unos", "unas", "de",
                 "del", "al", "a", "en", "con", "por", "para", "y", "e", "o",
                 "u", "que", "su", "sus", "tras", "sobre", "entre", "desde"}
    palabras = recortado.split()
    while len(palabras) > 2 and palabras[-1].lower().strip(",;:") in COLGANTES:
        palabras.pop()

    return " ".join(palabras).rstrip(" ,;:—-").strip()


def acortar_titulo(titulo: str, limite: int = LIMITE_TITULO) -> str:
    """Deja el título de YouTube dentro del límite.

    YouTube corta el título en los resultados de búsqueda pasados ~70
    caracteres, así que lo que sobra no es que se vea feo: no se ve.

    Dos capas, como en el resto del proyecto: **el modelo lo intenta y Python
    lo garantiza.** A un LLM no se le pide que cuente caracteres —lo hace mal y
    cobra por hacerlo mal—, pero sí sabe reescribir sin perder el gancho, que
    es justo lo que un truncado no puede hacer.

    1. Una llamada barata (solo el título, ~40 tokens) pidiendo acortar.
    2. Si aun así se pasa, `_truncar_titulo()` corta en un límite de cláusula.

    Solo cuesta cuando hace falta: si el título ya cabe, no llama a nada.
    """
    titulo = " ".join(titulo.split())
    if len(titulo) <= limite:
        return titulo

    print(f"  ✂️  Título de {len(titulo)}/{limite} caracteres — pidiendo uno más corto")

    propuesta = ""
    for intento in range(1, 3):
        # El segundo intento le dice en qué falló el primero, igual que hace la
        # reescritura del paso 01. Hace falta cuando la propia entidad es larga
        # ("Santísima Trinidad y Nuestra Señora del Buen Fin" son 47 caracteres):
        # sin permiso explícito, el modelo no la toca y no hay forma de que quepa.
        extra = ""
        if intento > 1:
            extra = (f"\n\nTu propuesta anterior seguía midiendo {len(propuesta)} "
                     f"caracteres:\n{propuesta}\n"
                     "Sé más agresivo. Si el nombre propio es muy largo, usa su "
                     "forma corta o común.")
        try:
            response = client.chat.completions.create(
                model="gpt-4.1",
                messages=[
                    {"role": "system", "content": (
                        "Acortas títulos de YouTube. Devuelves SOLO el título nuevo, "
                        "sin comillas ni explicaciones."
                    )},
                    {"role": "user", "content": (
                        f"Este título mide {len(titulo)} caracteres y el máximo son "
                        f"{limite}:\n\n{titulo}\n\n"
                        f"Reescríbelo en {limite - 5} caracteres o menos. "
                        "Conserva la entidad principal al inicio (es la señal que lee "
                        "el algoritmo) y la curiosidad. No reveles el desenlace. "
                        "Quita adjetivos y subordinadas antes que datos." + extra
                    )},
                ],
                max_tokens=60,
            )
            registrar_openai(response, "gpt-4.1", "acortar título")
            propuesta = " ".join(response.choices[0].message.content.split()).strip('"')
        except Exception as error:
            print(f"  ⚠️  No se pudo acortar con el modelo ({error}); se trunca")
            break

        if len(propuesta) <= limite:
            print(f"  ✓ Título acortado a {len(propuesta)} caracteres "
                  f"(intento {intento})")
            return propuesta

    final = _truncar_titulo(propuesta or titulo, limite)
    print(f"  ✂️  Truncado a {len(final)} caracteres: '{final}'")
    return final


def recortar_a_limite(descripcion: str, hashtags: str, limite: int) -> str:
    """Recorta la descripción para que 'descripción + hashtags' quepa en `limite`.

    Dos reglas, en este orden:
    1. **El último párrafo se conserva siempre**: cierra con la pregunta que invita
       a comentar, y es lo que menos conviene perder.
    2. De los anteriores se guardan los que quepan enteros, y del primero que no
       quepa se salva la parte que termine en punto. Recortar por párrafos enteros
       tiraba 490 caracteres para ahorrar 53; por frases se pierde lo justo.
    """
    cola = f"\n\n{hashtags}" if hashtags else ""
    disponible = limite - len(cola)
    texto = descripcion.strip()

    if len(texto) <= disponible:
        return texto

    parrafos = [p.strip() for p in re.split(r"\n\s*\n", texto) if p.strip()]

    # Un solo bloque: no hay último párrafo que proteger, se corta por frases.
    if len(parrafos) < 2:
        return _cortar_en_frase(texto, disponible)

    ultimo = parrafos[-1]
    reservado = len(ultimo) + 2                      # el "\n\n" que lo separa
    elegidos, largo = [], 0

    for p in parrafos[:-1]:
        sep = 2 if elegidos else 0
        if largo + sep + len(p) + reservado <= disponible:
            elegidos.append(p)
            largo += sep + len(p)
            continue
        # No cabe entero: salvar las frases que quepan y parar.
        trozo = _cortar_en_frase(p, disponible - reservado - largo - sep)
        if trozo:
            elegidos.append(trozo)
        break

    if not elegidos:                                 # ni una frase cabe con el último
        return _cortar_en_frase(ultimo, disponible) or ultimo[:disponible].strip()

    return "\n\n".join(elegidos + [ultimo])


def escribir_descripcion(ruta: str, general: str, detallada: dict) -> None:
    """Escribe el único archivo publicable, con todo lo que hace falta para
    programar el video de una sentada.

    Todo en UN archivo a propósito: programar una semana en Metricool significa
    abrir el texto de cada video una vez, no dos.
    """
    tags = detallada.get("tags", [])
    titulo = detallada.get("titulo", "")
    cuerpo_general, hashtags = separar_hashtags(general)

    # El título ya viene acortado de `save_posts()`, que es quien lo hace una
    # sola vez para que `descripcion.txt` y `metadata.json` no se contradigan.
    # Esta guarda es por si alguien llama a esta función suelta.
    if len(titulo) > LIMITE_TITULO:
        print(f"⚠️  El título mide {len(titulo)}/{LIMITE_TITULO} caracteres "
              f"— YouTube lo cortará en la búsqueda")
    if not hashtags:
        print("⚠️  La descripción general vino sin hashtags — revísala a mano")

    # Los hashtags van repetidos bajo CADA descripción y sin encabezado propio,
    # para poder seleccionar descripción + hashtags de una pasada y pegarlos
    # juntos con la que se vaya a usar ese día.
    larga = recortar_a_limite(detallada.get("descripcion", ""), hashtags,
                              LIMITE_DESCRIPCION_LARGA)
    bloque_largo = f"{larga}\n\n{hashtags}" if hashtags else larga
    if len(bloque_largo) > LIMITE_DESCRIPCION_LARGA:
        print(f"⚠️  La descripción larga + hashtags mide {len(bloque_largo)} "
              f"caracteres (tope {LIMITE_DESCRIPCION_LARGA}) — acórtala a mano")

    def seccion(f, encabezado: str, cuerpo: str) -> None:
        f.write(f"{encabezado}\n")
        f.write("─" * 60 + "\n")
        f.write(f"{cuerpo}\n\n\n")

    with open(ruta, "w", encoding="utf-8") as f:
        seccion(f, f"TÍTULO ({len(titulo)}/{LIMITE_TITULO} caracteres)", titulo)
        # El pie del reel va arriba: es lo que más se copia al programar.
        seccion(f, "DESCRIPCIÓN GENERAL (pie del reel — las 4 redes)",
                f"{cuerpo_general}\n\n{hashtags}" if hashtags else cuerpo_general)
        seccion(f, f"DESCRIPCIÓN LARGA (YouTube y Facebook) "
                   f"— {len(bloque_largo)}/{LIMITE_DESCRIPCION_LARGA} caracteres",
                bloque_largo)
        seccion(f, "TAGS DE YOUTUBE (separados por coma)",
                ", ".join(tags) if isinstance(tags, list) else tags)
        f.write("COMENTARIO A FIJAR\n")
        f.write("─" * 60 + "\n")
        f.write(f"{detallada.get('comentario_fijado', '')}\n")


def guardar_descripciones(general: str, detallada: dict, carrusel: str,
                          research: str, output_dir="social_posts") -> None:
    """Escribe el archivo publicable único + los insumos internos."""
    os.makedirs(output_dir, exist_ok=True)

    # ⚠️ El título se acorta AQUÍ, una sola vez, antes de escribir nada. Salen
    # por dos caminos —`descripcion.txt`, que es lo que copias, y
    # `metadata.json`, de donde lo lee el paso 09— y si se acortara solo al
    # escribir el primero, el mismo video tendría dos títulos distintos según
    # dónde lo mires. El paso 10 además empareja las métricas por ese texto.
    detallada["titulo"] = acortar_titulo(detallada.get("titulo", ""), LIMITE_TITULO)

    escribir_descripcion(f"{output_dir}/{ARCHIVO_DESCRIPCION}", general, detallada)
    print(f"✅ Guardado: {output_dir}/{ARCHIVO_DESCRIPCION}")

    # ── Insumos internos (NO se publican tal cual) ────────────
    with open(f"{output_dir}/{ARCHIVO_CARRUSEL}", "w", encoding="utf-8") as f:
        f.write(carrusel)

    with open(f"{output_dir}/00_investigacion.txt", "w", encoding="utf-8") as f:
        f.write("=== INVESTIGACIÓN HISTÓRICA REAL ===\n\n")
        f.write(research)

    # El título también en json, para que el paso 09 no tenga que parsear prosa
    with open(f"{output_dir}/metadata.json", "w", encoding="utf-8") as f:
        json.dump(detallada, f, ensure_ascii=False, indent=2)

def save_image_list(descriptions: list, output_dir="social_posts"):
    """Guarda la lista de imágenes a descargar."""
    path = f"{output_dir}/images_to_download.txt"
    with open(path, "w", encoding="utf-8") as f:
        for i, desc in enumerate(descriptions):
            f.write(f"img_{i}.jpg → {desc}\n")
    print(f"✅ Guardado: {path}")

def generate_title(script: str) -> str:
    """Genera el texto que va quemado en pantalla los primeros segundos.

    ⚠️ NO es un resumen. Antes lo era, y como el resumen de una historia es su
    desenlace, el video abría con el spoiler escrito ("MEMO OCHOA PERDIÓ PSG POR
    VISA") antes de que el narrador dijera una palabra. Ahora abre la pregunta.
    """
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": (
                "Escribes ganchos para videos verticales. Máximo 7 palabras.\n"
                "PROHIBIDO revelar el desenlace: tu trabajo es CREAR la pregunta "
                "en la cabeza del espectador, no responderla.\n"
                "Debe dar contexto suficiente para intrigar, pero dejar el "
                "resultado en el aire.\n"
                "Ejemplo con la historia de un fichaje que se cayó por un trámite:\n"
                "  MAL:  'Ochoa perdió el PSG por una visa'  (cuenta el final)\n"
                "  BIEN: 'El PSG ya lo había fichado'        (abre la pregunta)\n"
                "Solo el texto, sin comillas, sin punto final, sin explicaciones."
            )},
            {"role": "user", "content": script}
        ],
        max_tokens=30
    )
    registrar_openai(response, "gpt-4.1", "gancho")
    return response.choices[0].message.content.strip()


def sanear_valor_env(value: str) -> str:
    """Deja un valor que se puede escribir en el .env sin romperlo.

    ⚠️ `run_pipeline.sh` hace `source .env`, o sea que esto lo lee BASH. El
    título lo escribe un LLM, así que hay que tratarlo como texto ajeno:

    - Los saltos de línea son el fallo que ya ocurrió: un título de dos líneas
      dejaba `TITULO_VIDEO="linea 1 / linea 2"` repartido en varias líneas del
      archivo. La corrida siguiente solo reemplaza la PRIMERA (el bucle corta en
      el primer `startswith`), y las demás quedan sueltas — prosa que bash
      intenta ejecutar como comando. Pasó de verdad con Historia07 (Galeón).
    - `"` cierra la comilla antes de tiempo; `$`, `` ` `` y `\` se interpretan
      DENTRO de comillas dobles, así que un título con `$(...)` se ejecutaría.

    Ninguno de esos caracteres tiene sentido en un título que va quemado en el
    frame 0 de un video, así que se quitan en vez de escaparse: es más simple y
    no hay forma de que se cuelen por una regla de escapado mal puesta.
    """
    plano = " ".join(str(value).split())          # \n, \r y \t → un solo espacio
    sin_peligro = plano.translate(str.maketrans("", "", '"`$\\'))
    # Se vuelve a colapsar DESPUÉS de quitar caracteres: borrar una barra final
    # dejaba un espacio colgando, y dos símbolos seguidos dejaban espacio doble.
    return " ".join(sin_peligro.split())


def save_to_env(key: str, value: str, env_path: str = ".env") -> None:
    """Actualiza o agrega una variable en el archivo .env."""
    path = Path(env_path)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []

    limpio = sanear_valor_env(value)
    if limpio != value:
        print(f"  ⚠️  {key} se saneó antes de escribirlo (rompía el .env)")

    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f'{key}="{limpio}"'
            updated = True
            break

    if not updated:
        lines.append(f'{key}="{limpio}"')

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  ✓ {key} guardado en {env_path}: '{limpio}'")


def clean_output_dir(output_dir="social_posts") -> None:
    """Borra los posts de la corrida anterior.

    Los pasos 04, 05 y 06 ya limpiaban su carpeta; este no. Si un tema generaba
    menos archivos que el anterior, quedaban mezclados los de dos temas.
    """
    if not os.path.isdir(output_dir):
        return

    borrados = 0
    for file_name in os.listdir(output_dir):
        if file_name.lower().endswith(".txt"):
            os.remove(os.path.join(output_dir, file_name))
            borrados += 1

    if borrados:
        print(f"🧹 {borrados} posts previos eliminados de '{output_dir}'")


def main():
    print("📖 Leyendo script...")
    script = read_script("script.txt")

    clean_output_dir()

    print("🔍 Investigando historia real...")
    research = research_real_history(script)
    print("\n📚 Investigación completada")

    print("\n✍️  Generando descripción general (las 4 redes)...")
    general = generar_descripcion_general(script, research)

    print("✍️  Generando descripción detallada (título, tags, comentario)...")
    detallada = generar_descripcion_detallada(script, research)

    print("✍️  Generando texto del carrusel...")
    carrusel = generar_texto_carrusel(script, research)

    guardar_descripciones(general, detallada, carrusel, research)

    # Gancho de pantalla del video → .env (lo consume el paso 07)
    titulo = generate_title(script)
    save_to_env("TITULO_VIDEO", titulo)

    print("\n🖼️  Generando lista de imágenes...")
    image_descriptions = generate_image_descriptions(carrusel, script)
    save_image_list(image_descriptions)
    for i, desc in enumerate(image_descriptions):
        print(f"   img_{i}.jpg → {desc}")

    shutil.copytree("social_posts", f"proyectos/{PROYECTO}/social_posts", dirs_exist_ok=True)
    print(f"\n✍️  Respaldo guardado en proyectos/{PROYECTO}/social_posts")
    print(resumen_costo())


if __name__ == "__main__":
    main()
# %%
