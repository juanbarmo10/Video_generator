#%%

import os
import re
import requests
import random
import time
from dotenv import load_dotenv
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import fal_client

from estado import (verificar_estado, registrar_openai,
                    registrar_imagen_fal, resumen_costo)

load_dotenv()

# Aborta si script.txt es de otro tema (ver estado.py)
verificar_estado("paso 04")

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

# ⚠️ Este es el BASE_PROMPT ACTIVO (Python se queda con la última definición;
# el de arriba es código muerto).
#
# Cambios respecto a la versión anterior:
# - "full-bleed edge-to-edge": el borde de pergamino desperdiciaba ~8% de pantalla
#   y hacía que el video se leyera como un póster metido dentro del teléfono.
# - "clean well-formed hands": Flux dev NO acepta negative_prompt (es un modelo
#   destilado sin CFG), así que las protecciones de anatomía tienen que ir aquí.
# - "no text, no letters, no numbers": Flux no sabe escribir. Sin esto salían
#   documentos con garabatos ilegibles como primer frame del video.
BASE_PROMPT = """
vintage editorial illustration, colored ink drawing,
aged parchment paper texture, warm beige tones,

bold flat colors on figures and objects,
hand-drawn outlines, minimal shading, no depth,
flat perspective, stylized figures, clean well-formed hands,

historic illustration style,

full-bleed edge-to-edge composition, no paper border, no frame, no margins,
9:16 vertical composition optimized for mobile,
no text, no letters, no numbers, no signage, no watermark
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

    registrar_openai(response, "gpt-4.1", "contexto")

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

🚫 REGLAS VISUALES (el modelo de imágenes NO sabe escribir):
- PROHIBIDO centrar una escena en documentos, contratos, cartas, periódicos,
  pantallas, carteles, letreros, pizarras, libros abiertos o cualquier superficie
  con texto legible. Sale texto inventado ilegible y arruina la toma.
- Si la historia gira sobre un documento, muestra la REACCIÓN humana, no el papel:
  ❌ "close-up of a contract being signed with a fountain pen"
  ✅ "a man in a suit stares at an empty desk, shoulders slumped, window behind him"

👤 REGLAS DE COMPOSICIÓN (retención en vertical):
- Al menos 4 de las escenas deben mostrar ROSTROS HUMANOS con emoción clara.
- La ESCENA 1 debe ser un PRIMER PLANO de un rostro con emoción legible: es el
  primer fotograma del video y decide si el espectador se queda.
- Al menos 2 escenas más deben ser primer plano (close-up), no plano general.
- Evita figuras de espaldas o muy lejanas: no transmiten emoción.

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

    registrar_openai(response, "gpt-4.1", "escenas")

    # extract_context() sí se protegía del JSON mal formado; esto no. Un bloque
    # ```json al inicio abortaba el tema entero con el guion, la voz y las 6
    # llamadas del paso 02 ya pagadas.
    raw = response.choices[0].message.content.strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw).strip()

    try:
        scenes_json = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"❌ Las escenas no vinieron en JSON válido: {exc}\n{raw[:400]}")

    scenes = [s["scene"] for s in scenes_json if s.get("scene")]

    if not scenes:
        raise SystemExit(f"❌ El JSON de escenas vino vacío o sin clave 'scene':\n{raw[:400]}")

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

# ── Resolución de las imágenes ────────────────────────────────────────────
# Antes 720x1280: el paso 07 las escalaba a 1080x1920 (+50%) y encima les
# aplicaba zoom, con un pico real de ampliación de ~1.7x. Se veían blandas.
# fal cobra Flux dev por megapíxel, así que esto es un trade-off de costo:
#   720x1280  = 0.92 MP · 1.0x costo · upscale 1.50x (malo)
#   832x1472  = 1.22 MP · 1.3x costo · upscale 1.30x (equilibrio)  ← elegido
#   1088x1920 = 2.09 MP · 2.3x costo · upscale 1.00x (ideal)
# Si subes a 1088x1920, baja también "zoom_max" del paso 07 a 1.08 y
# "recorte_escala_min" a 0.75 para aprovechar la resolución extra.
IMAGE_WIDTH  = 832
IMAGE_HEIGHT = 1472

# Seed base. Cada escena usa SEED_BASE + i*977 para que sea reproducible pero
# distinta entre escenas (ver generate_images_from_script).
SEED_BASE = 12345

# Mínimo de imágenes para que el video tenga sentido. Con menos, aborta el tema
# en vez de entregar un video degradado en silencio.
MIN_IMAGENES = 6


def generate_image(prompt, seed, idx, output_dir="images_IA"):
    """Genera imagen con Flux dev via fal.ai"""

    try:
        result = fal_client.run(
            "fal-ai/flux/dev",
            arguments={
                "prompt": prompt,
                # OJO: `negative_prompt` NO va aquí. Flux dev es un modelo
                # destilado sin guidance clásico y el endpoint no lo expone en su
                # schema: el que había antes se ignoraba silenciosamente. Las
                # restricciones de anatomía viven ahora en BASE_PROMPT.
                "image_size": {
                    "width": IMAGE_WIDTH,
                    "height": IMAGE_HEIGHT   # 9:16
                },
                "num_inference_steps": 28,
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

        registrar_imagen_fal(IMAGE_WIDTH, IMAGE_HEIGHT)
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
    with ThreadPoolExecutor(max_workers=3) as executor:
        for i, scene in enumerate(scenes):
            prompt = build_prompt(scene, context=context)
            # Seed distinta por escena, pero determinista: con la seed fija que
            # había antes, las 8 imágenes salían con composiciones parecidas
            # entre sí — justo lo contrario de la variedad que retiene.
            tasks.append((i, executor.submit(
                generate_image, prompt, SEED_BASE + i * 977, i, output
            )))

    image_paths = [None] * len(scenes)
    for i, future in tasks:
        result = future.result()
        if result:
            image_paths[i] = result

    generadas = [p for p in image_paths if p]

    # Antes esto devolvía lo que hubiera. Si 5 de 8 fallaban, el paso 04 salía
    # con éxito y el paso 07 armaba un video con 3 imágenes de 13s cada una.
    if len(generadas) < MIN_IMAGENES:
        raise SystemExit(
            f"❌ Solo se generaron {len(generadas)}/{len(scenes)} imágenes "
            f"(mínimo {MIN_IMAGENES}) — el video quedaría inservible"
        )

    if len(generadas) < len(scenes):
        print(f"⚠️  {len(scenes) - len(generadas)} imágenes fallaron — "
              f"el ritmo del video se resiente")

    return generadas

# ▶️ EJECUCIÓN
if __name__ == "__main__":
    with open(path_script, "r", encoding="utf-8") as f:
        script = f.read()

    images = generate_images_from_script(script, n_scenes=8)

    print(resumen_costo())
    print("\n📁 Imágenes generadas:")
    for img in images:
        print(img)
# %%
