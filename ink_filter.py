
#%%

"""
🎨 FILTRO INK DRAWING — Convierte fotos reales al estilo parchment/ink
Reemplaza la generación con IA para consistencia 100% garantizada.
"""

import os
import numpy as np
from PIL import Image, ImageFilter, ImageEnhance, ImageOps, ImageChops

# ══════════════════════════════════════════════════════════════
# ⚙️  CONFIG — ajusta estos valores a tu gusto
# ══════════════════════════════════════════════════════════════
CONFIG = {
    "source_dir":       "source_images",
    "output_dir":       "images_IA",
    "width":            720,
    "height":           1280,

    # Intensidad de líneas de tinta (0.5=suave, 1.5=agresivo)
    "ink_strength":     1.5,

    # Qué tan visible es la foto original debajo del efecto
    # 0.0 = solo líneas | 1.0 = foto original completa
    "photo_blend":      0.60,

    # Intensidad del tono sepia (0.0=sin sepia, 1.0=sepia total)
    "sepia_strength":   0.55,

    # Añadir textura de papel encima
    "paper_texture":    True,
    "paper_opacity":    0.15,  # 0.0=sin textura, 0.5=muy visible

    # Viñeta oscura en bordes
    "vignette":         True,
    "vignette_strength": 0.6,
}


# ══════════════════════════════════════════════════════════════
# 🎨 FUNCIONES DE FILTRO
# ══════════════════════════════════════════════════════════════

def resize_crop(img: Image.Image, w: int, h: int) -> Image.Image:
    """Redimensiona y recorta al centro manteniendo proporción."""
    ratio_img = img.width / img.height
    ratio_tgt = w / h
    if ratio_img > ratio_tgt:
        new_h = h
        new_w = int(h * ratio_img)
    else:
        new_w = w
        new_h = int(w / ratio_img)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - w) // 2
    top  = (new_h - h) // 2
    return img.crop((left, top, left + w, top + h))


def apply_ink_lines(img: Image.Image, strength: float = 1.0) -> Image.Image:
    """Extrae bordes de la foto y los convierte en líneas de tinta."""
    gray = img.convert("L")

    # Boost de contraste antes de detectar bordes
    gray = ImageEnhance.Contrast(gray).enhance(1.4)

    # Detectar bordes con find_edges
    edges = gray.filter(ImageFilter.FIND_EDGES)

    # Suavizar un poco para que las líneas no sean tan pixeladas
    edges = edges.filter(ImageFilter.GaussianBlur(radius=0.8))

    # Invertir: fondo blanco, líneas negras (estilo ink drawing)
    edges = ImageOps.invert(edges)

    # Aumentar contraste de las líneas según strength
    edges = ImageEnhance.Contrast(edges).enhance(1.0 + strength)

    return edges.convert("RGB")


def apply_sepia(img: Image.Image, strength: float = 0.85) -> Image.Image:
    """Aplica tono sepia con paleta histórica."""
    gray = img.convert("L").convert("RGB")

    # Paleta sepia: marrón cálido con toques de rojo oscuro y dorado apagado
    sepia = Image.new("RGB", img.size)
    pixels = np.array(gray, dtype=np.float32)

    r = np.clip(pixels[:,:,0] * 1.08 + 15, 0, 255)
    g = np.clip(pixels[:,:,1] * 0.88,      0, 255)
    b = np.clip(pixels[:,:,2] * 0.72 - 10, 0, 255)

    sepia_arr = np.stack([r, g, b], axis=2).astype(np.uint8)
    sepia = Image.fromarray(sepia_arr)

    # Mezclar con la imagen original según strength
    return Image.blend(img, sepia, alpha=strength)


def apply_paper_texture(img: Image.Image, opacity: float = 0.25) -> Image.Image:
    """Genera y aplica textura de papel viejo proceduralmente."""
    w, h = img.size
    rng = np.random.default_rng(42)  # seed fijo = misma textura siempre

    # Ruido base de papel
    noise = rng.integers(200, 255, (h, w), dtype=np.uint8)
    noise_img = Image.fromarray(noise, mode="L")
    noise_img = noise_img.filter(ImageFilter.GaussianBlur(radius=1.2))

    # Convertir a RGB con tono amarillento de papel viejo
    noise_rgb = noise_img.convert("RGB")
    noise_arr = np.array(noise_rgb, dtype=np.float32)
    noise_arr[:,:,0] = np.clip(noise_arr[:,:,0] * 1.05, 0, 255)  # más rojo
    noise_arr[:,:,2] = np.clip(noise_arr[:,:,2] * 0.82, 0, 255)  # menos azul
    paper = Image.fromarray(noise_arr.astype(np.uint8))

    return Image.blend(img, paper, alpha=opacity)


def apply_vignette(img: Image.Image, strength: float = 0.6) -> Image.Image:
    """Viñeta oscura difuminada en los bordes."""
    from PIL import ImageFilter as IF
    w, h = img.size

    mask = Image.new("L", (w, h), 255)
    draw_mask = mask.copy()

    # Elipse blanca centrada (zona sin viñeta)
    from PIL import ImageDraw
    draw = ImageDraw.Draw(draw_mask)
    margin_x = int(w * 0.3)
    margin_y = int(h * 0.25)
    draw.ellipse([margin_x, margin_y, w - margin_x, h - margin_y], fill=0)
    draw_mask = draw_mask.filter(IF.GaussianBlur(radius=min(w, h) // 5))
    draw_mask = draw_mask.point(lambda x: int(x * strength))

    dark = Image.new("RGB", (w, h), (0, 0, 0))
    return Image.composite(dark, img, draw_mask)


# ══════════════════════════════════════════════════════════════
# 🚀 PIPELINE PRINCIPAL
# ══════════════════════════════════════════════════════════════

def apply_ink_filter(image_path: str, cfg: dict = CONFIG) -> Image.Image:
    """
    Pipeline completo:
    foto real → resize → ink lines + photo blend → sepia → paper → vignette
    """
    img = Image.open(image_path).convert("RGB")
    img = resize_crop(img, cfg["width"], cfg["height"])

    # 1. Extraer líneas de tinta
    ink = apply_ink_lines(img, strength=cfg["ink_strength"])

    # 2. Mezclar foto original con las líneas (photo_blend controla cuánto se ve la foto)
    blended = Image.blend(ink, img, alpha=cfg["photo_blend"])

    # 3. Tono sepia
    result = apply_sepia(blended, strength=cfg["sepia_strength"])

    # 4. Textura de papel
    if cfg.get("paper_texture"):
        result = apply_paper_texture(result, opacity=cfg["paper_opacity"])

    # 5. Viñeta
    if cfg.get("vignette"):
        result = apply_vignette(result, strength=cfg["vignette_strength"])

    return result


def process_all_images(cfg: dict = CONFIG):
    """Procesa todas las imágenes en source_dir y guarda en output_dir."""
    source_dir = cfg["source_dir"]
    output_dir = cfg["output_dir"]

    if not os.path.exists(source_dir):
        print(f"❌ No existe la carpeta '{source_dir}'")
        print(f"   Crea la carpeta y pon tus fotos ahí nombradas: scene_0.jpg, scene_1.jpg...")
        return []

    files = sorted([
        f for f in os.listdir(source_dir)
        if f.lower().endswith((".jpg", ".jpeg", ".png"))
    ])

    if not files:
        print(f"❌ No hay imágenes en '{source_dir}'")
        return []

    os.makedirs(output_dir, exist_ok=True)
    print(f"🎨 Procesando {len(files)} imágenes con filtro ink/parchment...\n")

    output_paths = []
    for i, filename in enumerate(files):
        src_path = os.path.join(source_dir, filename)
        # Renombrar al formato scene_N.png que espera video_generator
        out_name = f"scene_{i}.png"
        out_path = os.path.join(output_dir, out_name)

        print(f"  [{i+1}/{len(files)}] {filename} → {out_name}")
        result = apply_ink_filter(src_path, cfg)
        result.save(out_path, "PNG")
        print(f"  ✅ Guardado: {out_path}")

        output_paths.append(out_path)

    print(f"\n🎉 {len(output_paths)} imágenes procesadas en '{output_dir}'")
    return output_paths


# ══════════════════════════════════════════════════════════════
# ▶️ EJECUCIÓN
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    process_all_images(CONFIG)
