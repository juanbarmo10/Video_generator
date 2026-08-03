
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

def generate_posts(script: str, research: str) -> dict:
    """Genera publicaciones optimizadas para cada red social."""
    
    context = f"""
SCRIPT ORIGINAL (100 palabras):
{script}

INVESTIGACIÓN HISTÓRICA REAL:
{research}
"""

    platforms = {
        "twitter_thread": {
            "instruction": """Crea un HILO de Twitter/X de 5 tweets sobre esta historia.

Reglas:
- Tweet 1: GANCHO brutal que pare el scroll (pregunta o dato impactante)
- Tweets 2-4: desarrollo de la historia, un dato por tweet
- Tweet 5: reflexión final + pregunta para generar respuestas
- Máximo 280 caracteres por tweet
- Sin hashtags excepto en el último tweet (máximo 2)
- Formato: numerados 1/5, 2/5, etc.
"""
        },
        "threads": {
            "instruction": """Crea un post de Threads sobre esta historia.

Reglas:
- Primer párrafo: gancho fuerte (máximo 2 líneas)
- Desarrollo: 3-4 párrafos cortos con saltos de línea generosos
- Tono: como si se lo contaras a un amigo inteligente
- Final: pregunta abierta que genere debate
- Sin hashtags
"""
        },
        "instagram": {
            "instruction": """Crea texto para añadir a imagenes para un carrusel en instagram de esta historia.

Reglas de contenido:
- Primera línea: gancho (termina con "..." para forzar "ver más")
- }sin emojis
- CTA al final antes de los hashtags: "Guarda este post para no olvidarlo"
- 20-25 hashtags al final mezclando grandes y nicho
- 6 slides contando la portada y el cta
- No más de 120 caracteres
 
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
"""
        },
        "facebook": {
            "instruction": """Crea una publicación de Facebook sobre esta historia.

Reglas:
- Tono: emotivo y reflexivo, como una historia que vale la pena compartir
- Más largo que otras redes (300-400 palabras)
- Incluir contexto histórico adicional de la investigación
- Pregunta al final que genere debate en comentarios
- Sin hashtags (Facebook no los necesita)
"""
        }
    }

    results = {}

    for platform, config in platforms.items():
        print(f"✍️  Generando post para {platform}...")
        
        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": (
                    "Eres un experto en marketing de contenido histórico viral. "
                    "Creas contenido que educa y engancha al mismo tiempo. "
                    "Usas los datos reales de la investigación para dar credibilidad. "
                    "Siempre escribes en español latino neutro."
                )},
                {"role": "user", "content": f"{config['instruction']}\n\n{context}"}
            ],
            max_tokens=1500
        )
        
        registrar_openai(response, "gpt-4.1", f"post {platform}")
        results[platform] = response.choices[0].message.content

    return results


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

def save_posts(posts: dict, research: str, output_dir="social_posts"):
    """Guarda cada publicación en archivos separados."""
    os.makedirs(output_dir, exist_ok=True)

    # Guardar investigación
    with open(f"{output_dir}/00_investigacion.txt", "w", encoding="utf-8") as f:
        f.write("=== INVESTIGACIÓN HISTÓRICA REAL ===\n\n")
        f.write(research)

    names = {
        "twitter_thread": "01_twitter_hilo.txt",
        "threads": "02_threads.txt",
        "instagram": "03_instagram.txt",
        "facebook": "04_facebook.txt"
    }

    for platform, content in posts.items():
        filename = names.get(platform, f"{platform}.txt")
        with open(f"{output_dir}/{filename}", "w", encoding="utf-8") as f:
            f.write(f"=== {platform.upper()} ===\n\n")
            f.write(content)
        print(f"✅ Guardado: {output_dir}/{filename}")

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


def generate_youtube_metadata(script: str, research: str) -> dict:
    """Genera título, descripción, tags y comentario fijado para YouTube Shorts.

    El pipeline generaba posts para Twitter, Threads, Instagram y Facebook, y
    NADA para YouTube — que es justo donde falta alcance. Para un canal nuevo el
    título es la principal señal de clasificación temática y la única palanca de
    búsqueda: subir un Short sin metadata es subirlo a ciegas.
    """
    response = client.chat.completions.create(
        model="gpt-4.1",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": (
                "Eres experto en SEO de YouTube Shorts en español latino. "
                "Devuelve SOLO un objeto json con estas claves:\n"
                '- "titulo": máximo 70 caracteres. La ENTIDAD PRINCIPAL (persona, '
                'equipo, lugar) va al inicio porque es la señal temática que lee '
                'el algoritmo. Genera curiosidad SIN revelar el desenlace. '
                'Sin clickbait falso.\n'
                '- "descripcion": 2 frases de contexto + 3 hashtags de nicho + #Shorts\n'
                '- "tags": lista de 12 strings, mezclando términos amplios y de nicho\n'
                '- "comentario_fijado": una pregunta abierta para fijar en '
                'comentarios y arrancar la conversación'
            )},
            {"role": "user", "content": f"SCRIPT:\n{script}\n\nINVESTIGACIÓN:\n{research}"}
        ],
        max_tokens=700
    )
    registrar_openai(response, "gpt-4.1", "metadata youtube")

    try:
        return json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        print("⚠️  Metadata de YouTube no vino en JSON válido — se omite")
        return {}


def save_youtube_metadata(meta: dict, output_dir="social_posts") -> None:
    """Guarda la metadata en un .txt listo para copiar y pegar al subir."""
    if not meta:
        return

    path = f"{output_dir}/05_youtube.txt"
    tags = meta.get("tags", [])

    with open(path, "w", encoding="utf-8") as f:
        f.write("=== YOUTUBE SHORTS ===\n\n")
        f.write(f"TÍTULO ({len(meta.get('titulo', ''))}/70 caracteres):\n")
        f.write(f"{meta.get('titulo', '')}\n\n")
        f.write("DESCRIPCIÓN:\n")
        f.write(f"{meta.get('descripcion', '')}\n\n")
        f.write("TAGS (separados por coma):\n")
        f.write(f"{', '.join(tags) if isinstance(tags, list) else tags}\n\n")
        f.write("COMENTARIO A FIJAR:\n")
        f.write(f"{meta.get('comentario_fijado', '')}\n")

    print(f"✅ Guardado: {path}")

def save_to_env(key: str, value: str, env_path: str = ".env") -> None:
    """Actualiza o agrega una variable en el archivo .env."""
    path = Path(env_path)
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    
    updated = False
    for i, line in enumerate(lines):
        if line.startswith(f"{key}="):
            lines[i] = f'{key}="{value}"'
            updated = True
            break
    
    if not updated:
        lines.append(f'{key}="{value}"')
    
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  ✓ {key} guardado en {env_path}: '{value}'")

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

    print("\n✍️  Generando publicaciones...")
    posts = generate_posts(script, research)

    save_posts(posts, research)
    print(f"\n🎉 Publicaciones guardadas en /social_posts")

    print("\n📺 Generando metadata de YouTube Shorts...")
    save_youtube_metadata(generate_youtube_metadata(script, research))

    # Gancho de pantalla del video → .env (lo consume el paso 07)
    titulo = generate_title(script)
    save_to_env("TITULO_VIDEO", titulo)

    print("\n🖼️  Generando lista de imágenes...")
    image_descriptions = generate_image_descriptions(posts["instagram"], script)
    save_image_list(image_descriptions)
    print(f"\n📋 Imágenes a descargar:")
    for i, desc in enumerate(image_descriptions):
        print(f"   img_{i}.jpg → {desc}")


    shutil.copytree("social_posts", f"proyectos/{PROYECTO}/social_posts", dirs_exist_ok=True)
    print(f"\n✍️  Respaldo guardado en proyectos/{PROYECTO}/social_posts")
    print(resumen_costo())

if __name__ == "__main__":
    main()
# %%
