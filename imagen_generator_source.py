#%%

import os
import json
import requests
import random
import time
from dotenv import load_dotenv
from openai import OpenAI
from concurrent.futures import ThreadPoolExecutor

load_dotenv()

# 🔑 APIs
LEONARDO_API_KEY = os.getenv("LEONARDO_API_KEY")
OPENAI_API_KEY   = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)

BASE_PROMPT = """
ancient parchment illustration,
sepia ink drawing on aged paper,
hand-drawn line art with subtle shading,
historical manuscript style,
9:16 vertical,
no text
"""

# 🎥 Estilos de cámara
CAMERA_STYLES = [
    "centered composition",
    "symmetrical composition",
    "medium shot",
    "portrait composition"
]

HEADERS = {
    "authorization": f"Bearer {LEONARDO_API_KEY}",
    "content-type": "application/json"
}


# ──────────────────────────────────────────────────────────
# 🎨 2. Construir prompt por escena
# ──────────────────────────────────────────────────────────

def build_prompt():

    camera = random.choice([
        "centered composition",
        "symmetrical composition",
        "medium shot",
        "close-up portrait"
    ])

    prompt = f"""
    {BASE_PROMPT},

    {camera},

    preserve recognizable facial features,
    preserve original clothing,
    preserve original hairstyle,
    preserve original background objects,
    preserve room details,
    preserve environment composition,

    transform the reference image into
    historical parchment artwork,

    detailed background,
    foreground middle ground and background,

    same person,
    same identity,
    same proportions
    """

    return prompt[:850]


# ──────────────────────────────────────────────────────────
# 📤 3. Subir imagen fuente a Leonardo (para img2img)
# ──────────────────────────────────────────────────────────

def upload_source_image(image_path: str) -> str | None:
    """Sube una imagen local a Leonardo y retorna su init_image_id."""
    ext = os.path.splitext(image_path)[1].lower().replace(".", "")
    if ext == "jpg":
        ext = "jpeg"

    # Paso 1 — solicitar URL de upload
    res = requests.post(
        "https://cloud.leonardo.ai/api/rest/v1/init-image",
        headers=HEADERS,
        json={"extension": ext}
    )

    if res.status_code != 200:
        print(f"❌ Error obteniendo URL de upload: {res.text}")
        return None

    data       = res.json()["uploadInitImage"]
    upload_url = data["url"]
    image_id   = data["id"]
    fields_raw = data["fields"]
    fields     = json.loads(fields_raw) if isinstance(fields_raw, str) else fields_raw

    # Paso 2 — subir el archivo a S3
    with open(image_path, "rb") as f:
        file_content = f.read()

    upload_res = requests.post(
        upload_url,
        data=fields,
        files={"file": (os.path.basename(image_path), file_content, f"image/{ext}")}
    )

    if upload_res.status_code not in (200, 204):
        print(f"❌ Error subiendo imagen: {upload_res.text}")
        return None

    print(f"📤 Imagen subida: {os.path.basename(image_path)} → ID: {image_id}")
    return image_id


# ──────────────────────────────────────────────────────────
# 🖼️ 4. Generar imagen con Leonardo
#        Si se pasa init_image_id → img2img (foto real → estilo)
#        Si no → generación normal
# ──────────────────────────────────────────────────────────

def generate_image(prompt: str, seed: int, idx, output_dir: str = "images_IA",
                   init_image_id: str = None) -> str | None:

    url = "https://cloud.leonardo.ai/api/rest/v1/generations"

    if init_image_id:
        payload = {
            "prompt": prompt,
            "modelId": "b2614463-296c-462a-9586-aafdb8f00e36",
            "width": 720,
            "height": 1280,
            "num_images": 1,
            "seed": seed,
            "controlnets": [
                {
                    "initImageId": init_image_id,
                    "initImageType": "UPLOADED", # Importante: indica que es una subida directa
                    "preprocessorId": 233,       # 233 es 'Content Reference' (mantiene la forma de tu foto)
                    "strengthType": "Ultra"     # Valores: "Low", "Mid", "High" "Ultra" "Max"
                }
            ]
        }
    else:
        # Generación normal sin foto fuente
        payload = {
            "prompt": prompt,
            "modelId": "b2614463-296c-462a-9586-aafdb8f00e36",
            "width": 720,
            "height": 1280,
            "num_images": 1,
            "seed": seed,
            "guidance_scale": 7,
            "num_inference_steps": 30,
        }

    response = requests.post(url, json=payload, headers=HEADERS)

    if response.status_code != 200:
        print(f"❌ Error POST escena {idx}: {response.text}")
        return None

    data = response.json()
    generation_id = data.get("sdGenerationJob", {}).get("generationId")

    if not generation_id:
        print(f"❌ No generation_id escena {idx}: {data}")
        return None

    mode = "img2img" if init_image_id else "txt2img"
    print(f"🎬 Escena {idx+1} [{mode}] | ID: {generation_id}")

    # ⏱️ Polling hasta completar
    get_url = f"https://cloud.leonardo.ai/api/rest/v1/generations/{generation_id}"
    for _ in range(30):
        res = requests.get(get_url, headers=HEADERS)

        if res.status_code != 200:
            print(f"❌ Error GET escena {idx}: {res.text}")
            return None

        result = res.json()
        status = result["generations_by_pk"]["status"]

        if status == "COMPLETE":
            image_url = result["generations_by_pk"]["generated_images"][0]["url"]
            img_data  = requests.get(image_url).content

            os.makedirs(output_dir, exist_ok=True)
            file_path = f"{output_dir}/scene_{idx}.png"

            with open(file_path, "wb") as f:
                f.write(img_data)

            print(f"✅ Escena {idx+1} guardada: {file_path}")
            return file_path

        elif status == "FAILED":
            print(f"❌ Generación falló escena {idx}")
            return None

        time.sleep(2)

    print(f"⏱️ Timeout escena {idx}")
    return None


# ──────────────────────────────────────────────────────────
# 🚀 5. Pipeline completo
# ──────────────────────────────────────────────────────────

def generate_images_from_images(source_dir: str = "source_images") -> list:
    """
    Si existe source_images/ con imágenes → usa img2img (foto real → estilo)
    
    Nombra tus fotos fuente como: scene_0.jpg, scene_1.jpg, scene_2.jpg...
    Una por escena, en el mismo orden que quieres que aparezcan en el video.
    """

    # Cargar fotos fuente si existen
    source_files = []
    if os.path.exists(source_dir):
        source_files = sorted([
            os.path.join(source_dir, f)
            for f in os.listdir(source_dir)
            if f.lower().endswith((".jpg", ".jpeg", ".png"))
        ])

    if source_files:
        print(f"📸 {len(source_files)} fotos fuente encontradas en '{source_dir}' → modo img2img")
    else:
        print(f"⚠️  Sin fotos fuente → modo txt2img (generación desde cero)")

    source_ids = [None] * len(source_files)
    if source_files:
        print("\n📤 Subiendo fotos fuente a Leonardo...")
        for i, src_path in enumerate(source_files):
            source_ids[i] = upload_source_image(src_path)

    seed   = 12345
    # Generar imágenes en paralelo
    print("\n🎨 Generando imágenes...")
    tasks = []
    with ThreadPoolExecutor(max_workers=3) as executor:
        for i, _ in enumerate(source_files):
            prompt = build_prompt()
            init_id = source_ids[i] if i < len(source_ids) else None
            tasks.append((i, executor.submit(
                generate_image, prompt, seed, i, "images_IA_guidance", init_id
            )))

    image_paths = [None] * len(source_files)
    for i, future in tasks:
        result = future.result()
        if result:
            image_paths[i] = result

    return [p for p in image_paths if p]


# ──────────────────────────────────────────────────────────
# ▶️ EJECUCIÓN
# ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    with open("script.txt", "r", encoding="utf-8") as f:
        script = f.read()

    # Coloca tus fotos en source_images/scene_0.jpg, scene_1.jpg...
    # Si no hay fotos, genera desde cero
    images = generate_images_from_images()

    print("\n📁 Imágenes generadas:")
    for img in images:
        print(f"  {img}")