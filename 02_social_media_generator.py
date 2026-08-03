
#%%


import os
import re
from openai import OpenAI
from dotenv import load_dotenv
import shutil
from pathlib import Path

load_dotenv()

# ========================================================================== #
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

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
    """Genera un título corto y preciso basado en el script."""
    response = client.chat.completions.create(
        model="gpt-4.1-mini",
        messages=[
            {"role": "system", "content": (
                "Genera un título corto (máximo 6 palabras) para un video basado en este script. "
                "Solo el título, sin comillas, sin puntuación al final, sin explicaciones."
            )},
            {"role": "user", "content": script}
        ],
        max_tokens=30
    )
    return response.choices[0].message.content.strip()

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

def main():
    print("📖 Leyendo script...")
    script = read_script("script.txt")

    print("🔍 Investigando historia real...")
    research = research_real_history(script)
    print("\n📚 Investigación completada")

    print("\n✍️  Generando publicaciones...")
    posts = generate_posts(script, research)

    save_posts(posts, research)
    print(f"\n🎉 Publicaciones guardadas en /social_posts")

    # Título del video → .env
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

if __name__ == "__main__":
    main()
# %%
