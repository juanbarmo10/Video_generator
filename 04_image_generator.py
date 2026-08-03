#%%

import os
import requests
import random
import time
from dotenv import load_dotenv
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import fal_client

load_dotenv()

# ========================================================================== #

LEONARDO_API_KEY = os.getenv("LEONARDO_API_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

path_script= "script.txt"
output = "images_IA"

# ========================================================================== #

client = OpenAI(api_key=OPENAI_API_KEY)

BASE_PROMPT = """
ancient parchment illustration, flat 2D drawing, ink drawing,
aged paper texture, sepia tones,

hand-drawn lines, minimal shading, no depth,
flat perspective, stylized figures,

historic illustration style,

9:16 vertical composition optimized for mobile,
no text, no watermark
"""

BASE_PROMPT = """
vintage editorial illustration, colored ink drawing,
aged parchment paper background, warm beige paper texture,

bold flat colors on figures and objects,
hand-drawn outlines, minimal shading, no depth,
flat perspective, stylized figures,

historic illustration style,

9:16 vertical composition optimized for mobile,
no text, no watermark
"""

# 🎥 estilos de cámara (para variedad)
CAMERA_STYLES = [
    "wide shot",
    "close-up",
    "overhead view",
    "dramatic angle",
    "medium shot",
    "cinematic perspective"
]

CONTEXT_KEYS = ("personaje", "epoca", "estilo_visual")

def extract_context(script: str) -> dict | None:
    """Extrae personaje, época y apariencia del script para anclar todas las escenas.

    Devuelve None si el modelo no responde con un json usable, para que el pipeline
    siga generando escenas sin anclaje en vez de abortar el tema completo.
    """
    response = client.chat.completions.create(
        model="gpt-4.1",
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": "Responde SOLO con un objeto json válido, sin markdown."},
            {"role": "user", "content": f"""Del siguiente texto extrae:
                - "personaje": nombre completo del personaje, lugar u objeto principal
                - "epoca": Dependiendo del texto, busca en que año y transcurre el evento, y representa las escenas con base en esto.
                - "estilo_visual": descripción MUY específica del personaje obtenida de su apariencia real
                Texto: {script}"""}
        ]
    )

    try:
        context = json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        print("⚠️  El contexto no vino en JSON válido — se generan escenas sin anclaje")
        return None

    faltantes = [k for k in CONTEXT_KEYS if not context.get(k)]
    if faltantes:
        print(f"⚠️  Contexto incompleto (falta: {', '.join(faltantes)}) — se ignora")
        return None

    print(f"🎯 Contexto: {context['personaje']} | {context['epoca']}")
    return context

def generate_visual_scenes(script, n_scenes=6, context=None):

    contexto_str = ""
    if context:
        contexto_str = f"""
        Época: {context['epoca']}
        Apariencia principal: {context['estilo_visual']}
        """

    prompt = f"""
Genera EXACTAMENTE {n_scenes} escenas visuales para IA de imágenes.

Devuelve SOLO un JSON válido con esta estructura:

[
  {{
    "scene": "descripción visual compacta y cinematográfica"
  }}
]

Reglas:
- Cada escena debe ser UNA SOLA descripción visual
- Máximo 60 palabras
- Prioriza claridad visual
- Describir: sujeto, acción, ambiente, iluminación
- No metáforas abstractas
- NO markdown, NO numeración
- Al menos dos tercios deben mostrar el sujeto/lugar principal
- Optimiza para modelo de imágenes
- Escribe en inglés

🚨 REGLAS DE MODERACIÓN (CRÍTICO):
- NUNCA uses: bodies, corpses, dead, death, dying, violence, violent, blood,
  gore, victims, murder, terror, terrified, cowering, panic, destruction,
  crash, erupting, catastrophe, disaster, fatal, lifeless
- Describe el RESULTADO visual sin mencionar muerte o violencia:
  ❌ "Eight lifeless bodies lie on the street"
  ✅ "Eight figures rest covered with cloth in a solemn candlelit hall, 
      priests kneeling nearby, boots and soaked garments nearby"
- Usa lenguaje artístico y neutral: solemn, still, aftermath, flooded, 
  submerged, overflowing, turbulent waters, rushing liquid
- Si hay una escena de caos: descríbela como movimiento y agua, no como violencia

Contexto:
{contexto_str}

Texto:
{script}
"""
    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {
                "role": "system",
                "content": "Eres experto en prompts para generación de imágenes IA."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
    )

    scenes_json = json.loads(response.choices[0].message.content)

    scenes = [s["scene"] for s in scenes_json]

    print("\n🧩 Escenas generadas:")
    for i, s in enumerate(scenes):
        print(f"{i+1}. {s}")

    return scenes

BANNED_WORDS = [
    "dead", "death", "dying", "bodies", "corpse", "victim", "murder",
    "violent", "violence", "terror", "terrified", "fatal", "lifeless",
    "gore", "blood", "crash", "destroy", "catastrophe", "panic", "cowering"
]

REPLACEMENTS = {
    "dead": "still",
    "bodies": "figures",
    "corpse": "figure",
    "victims": "people",
    "terrified": "solemn",
    "violent": "turbulent",
    "violence": "turbulence",
    "fatal": "historic",
    "lifeless": "motionless",
    "crash": "collapse",
    "destroy": "submerge",
    "terror": "solemnity",
    "panic": "urgency",
    "cowering": "sheltering",
    "catastrophe": "event",
    "disaster": "incident",
}

def sanitize_prompt(prompt: str) -> str:
    """Reemplaza palabras que disparan moderación de Leonardo."""
    import re
    result = prompt
    for word, replacement in REPLACEMENTS.items():
        result = re.sub(rf'\b{word}\b', replacement, result, flags=re.IGNORECASE)
    return result

# Largo máximo del prompt. La parte fija (estilo + cámara + época) ocupa ~400
# caracteres, así que el resto es el presupuesto real para la escena.
PROMPT_MAX_CHARS = 900

def build_prompt(scene_text, context=None):

    camera = random.choice(CAMERA_STYLES)

    prompt_parts = [
        BASE_PROMPT,
        camera,
    ]

    # contexto visual corto
    if context:
        prompt_parts.append(
            f"{context['epoca']} historical setting"
        )

    # El estilo base y el contexto van siempre completos: si hay que recortar,
    # se recorta la escena, nunca el encabezado que define el look del video.
    fijo = ", ".join(prompt_parts)
    presupuesto = PROMPT_MAX_CHARS - len(fijo) - 2  # 2 = ", "

    if presupuesto > 0:
        prompt = f"{fijo}, {scene_text[:presupuesto]}"
    else:
        prompt = fijo[:PROMPT_MAX_CHARS]

    prompt = sanitize_prompt(prompt)

    return prompt

# 🖼️ 3. Generar imagen con Leonardo
def generate_image(prompt, seed, idx, output_dir="images_IA"):
    url = "https://cloud.leonardo.ai/api/rest/v1/generations"

    headers = {
        "authorization": f"Bearer {LEONARDO_API_KEY}",
        "content-type": "application/json"
    }

    payload = {
        "prompt": prompt,
        "modelId": "b2614463-296c-462a-9586-aafdb8f00e36",
        "width": 720,
        "height": 1280,
        "num_images": 1,
        "seed": seed,
        "guidance_scale": 7,
        "num_inference_steps": 30
    }

    response = requests.post(url, json=payload, headers=headers)

    if response.status_code != 200:
        print("❌ Error POST:", response.text)
        return None

    data = response.json()

    generation_id = data.get("sdGenerationJob", {}).get("generationId")

    if not generation_id:
        print("❌ No generation_id:", data)
        return None

    #print(f"🎬 Escena {idx+1} | ID: {generation_id}")

    get_url = f"https://cloud.leonardo.ai/api/rest/v1/generations/{generation_id}"

    # ⏱️ polling
    for _ in range(30):
        res = requests.get(get_url, headers=headers)

        if res.status_code != 200:
            print("❌ Error GET:", res.text)
            return None

        result = res.json()
        status = result["generations_by_pk"]["status"]

        if status == "COMPLETE":
            image_url = result["generations_by_pk"]["generated_images"][0]["url"]
            img_data = requests.get(image_url).content

            os.makedirs(output_dir, exist_ok=True)
            file_path = f"{output_dir}/scene_{idx}.png"

            with open(file_path, "wb") as f:
                f.write(img_data)

            print(f"✅ Imagen guardada: {file_path}")
            return file_path

        elif status == "FAILED":
            print(f"❌ Generación falló. Respuesta completa: {json.dumps(result, indent=2)}")
            return None

        time.sleep(2)

    print("⏱️ Timeout esperando imagen")
    return None

def generate_image(prompt, seed, idx, output_dir="images_IA"):
    """Genera imagen con Flux Schnell via fal.ai"""
    
    try:
        result = fal_client.run(
            "fal-ai/flux/dev", #schnell
            arguments={
                "prompt": prompt,
                "negative_prompt": "deformed hands, extra fingers, missing fingers, bad anatomy, distorted limbs, mutated hands, fused fingers, poorly drawn hands, extra limbs",
                "image_size": {
                    "width": 720,
                    "height": 1280   # 9:16 exacto, igual que antes
                },
                "num_inference_steps": 28,  # Schnell es muy rápido
                "num_images": 1,
                "seed": seed,
                "enable_safety_checker": False  # para evitar falsos positivos
            }
        )

        image_url = result["images"][0]["url"]
        img_data = requests.get(image_url).content

        os.makedirs(output_dir, exist_ok=True)
        file_path = f"{output_dir}/scene_{idx}.png"

        with open(file_path, "wb") as f:
            f.write(img_data)

        print(f"✅ Imagen guardada: {file_path}")
        return file_path

    except Exception as e:
        print(f"❌ Error generando imagen {idx}: {e}")
        return None

def clean_output_dir(output_dir: str) -> None:
    """Borra las imágenes de la corrida anterior.

    Sin esto, si un tema genera menos escenas que el anterior, los scene_N.png
    viejos sobreviven y se cuelan en el video del tema nuevo.
    """
    if not os.path.isdir(output_dir):
        return

    borradas = 0
    for file_name in os.listdir(output_dir):
        if file_name.lower().endswith(".png"):
            os.remove(os.path.join(output_dir, file_name))
            borradas += 1

    if borradas:
        print(f"🧹 {borradas} imágenes previas eliminadas de '{output_dir}'")

def generate_images_from_script(script, n_scenes=6):
    clean_output_dir(output)

    print("🔍 Extrayendo contexto...")
    context = extract_context(script)

    scenes = generate_visual_scenes(script, n_scenes, context=context)

    tasks = []
    seed = 12345
    with ThreadPoolExecutor(max_workers=3) as executor:
        for i, scene in enumerate(scenes):
            prompt = build_prompt(scene, context=context)
            tasks.append((i, executor.submit(
                generate_image, prompt, seed, i, output
            )))

    image_paths = [None] * len(scenes)
    for i, future in tasks:
        result = future.result()
        if result:
            image_paths[i] = result

    return [p for p in image_paths if p]

# ▶️ EJECUCIÓN
if __name__ == "__main__":
    with open(path_script, "r", encoding="utf-8") as f:
        script = f.read()

    images = generate_images_from_script(script, n_scenes=8)

    print("\n📁 Imágenes generadas:")
    for img in images:
        print(img)
# %%
