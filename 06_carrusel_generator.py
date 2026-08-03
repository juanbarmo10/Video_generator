#%%

"""
╔══════════════════════════════════════════════════════════════╗
║         📱 GENERADOR DE CARRUSEL INSTAGRAM                   ║
║         Lee 03_instagram.txt + imágenes → slides listos      ║
╚══════════════════════════════════════════════════════════════╝

Carpetas necesarias:
    - social_posts/03_instagram.txt  → texto del post
    - post_images/                   → imágenes img_01.jpg, img_02.jpg...
    - fonts/                         → misma fuente que video_generator

Salida:
    - carousel_slides/               → slides numerados listos para publicar
"""

import os
import re
import textwrap
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import shutil
from dotenv import load_dotenv
load_dotenv()

# ══════════════════════════════════════════════════════════════
# ⚙️  CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════

PROYECTO = os.environ.get("PROYECTO")

if not PROYECTO:
    raise SystemExit(
        "❌ Falta PROYECTO (entorno o .env). Sin él el respaldo iría a 'proyectos//'."
    )

CONFIG = {
    # Archivos
    "instagram_post":   "social_posts/03_instagram.txt",
    "images_dir":       "source_images",
    "output_dir":       "carousel_slides",

    # Filtro sobre las imágenes
    # Opciones: None, "warm", "cool", "noir", "vintage"
    "image_filter": "warm",

    # Filtro de bordes
    # Opciones: None, "vignette", "vignette_soft", "frame_dark", 
    #           "frame_light", "glow", "letterbox", "polaroid"
    "border_filter": "frame_dark",
    "border_intensity": 1,  # 0.0 = sutil, 1.0 = intenso

    # Dimensiones — Instagram cuadrado o vertical
    "width":  1080,
    "height": 1350,  # 4:5 — el mejor formato para carrusel Instagram

    # Fuente — misma que video_generator
    "font_path":        "fonts/Bungee_Spice/BungeeSpice-Regular.ttf",
    "font_size_title":  92,   # portada
    "font_size_body":   63,   # slides de contenido
    "font_size_cta":    80,   # CTA final

    # Colores
    "text_color":       (255, 255, 255),
    "highlight_color":  (255, 220, 0),   # amarillo — igual que subtítulos
    "stroke_color":     (0, 0, 0),
    "stroke_width":     6,

    # Overlay oscuro sobre imagen (0=sin overlay, 180=oscuro)
    "overlay_opacity":  160,

    # Gradiente en la parte inferior para legibilidad
    "gradient_height_ratio": 0.55,  # qué % de la imagen cubre el gradiente
}


# ══════════════════════════════════════════════════════════════
# 📄 PARSEO DEL ARCHIVO 03_instagram.txt
# ══════════════════════════════════════════════════════════════

def parse_instagram_file(path: str) -> dict:
    """
    Extrae del archivo:
    - hook: primera línea (portada)
    - slides: párrafos intermedios
    - cta: última línea con CTA
    - hashtags: bloque de hashtags
    """
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Quitar encabezado === INSTAGRAM ===
    content = re.sub(r'===.*?===\n*', '', content).strip()

    # Separar hashtags (bloque que empieza con #)
    hashtag_match = re.search(r'\n(#\w+.*?)$', content, re.DOTALL)
    hashtags = ""
    if hashtag_match:
        hashtags = hashtag_match.group(1).strip()
        content = content[:hashtag_match.start()].strip()

    # Dividir en párrafos no vacíos
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]
    paragraphs = [p for p in paragraphs if p]

    # Limpiar indicadores de imagen tipo [IMAGEN: ...] o [SLIDE N: ...]
    clean = []
    for p in paragraphs:
        # Quitar líneas de Imagen: ...
        p_clean = re.sub(r'(?m)^Imagen:.*$', '', p)
        # Si hay Texto: "..." extraer solo lo que está entre comillas
        # Extraer texto entre comillas si existe "Texto: '...'"
        texto_match = re.search(r'Texto:\s*[\u201c"\'«](.+?)[\u201d"\'»]', p_clean)
        if texto_match:
            p_clean = texto_match.group(1).strip()
        else:
            # Sin comillas — quitar el prefijo "Texto:" y lo que sigue en esa línea si es label
            p_clean = re.sub(r'(?im)^Texto:\s*', '', p_clean)
            p_clean = re.sub(r'\[(?:IMAGEN|SLIDE)[^\]]*\]', '', p_clean).strip()
        if p_clean:
            clean.append(p_clean)

    hook = clean[0] if clean else ""
    cta  = clean[-1] if len(clean) > 1 else ""
    body = clean[1:-1] if len(clean) > 2 else []

    print(f"📄 Archivo parseado:")
    print(f"   Hook: {hook[:60]}...")
    print(f"   Slides de contenido: {len(body)}")
    print(f"   CTA: {cta[:60]}...")

    return {
        "hook": hook,
        "body": body,
        "cta": cta,
        "hashtags": hashtags
    }

def parse_instagram_file(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()

    # Quitar encabezado === INSTAGRAM ===
    content = re.sub(r'===.*?===\n*', '', content).strip()

    # Separar hashtags (bloque que empieza con #)
    hashtag_match = re.search(r'\n(#\w+.*?)$', content, re.DOTALL)
    hashtags = ""
    if hashtag_match:
        hashtags = hashtag_match.group(1).strip()
        content = content[:hashtag_match.start()].strip()

    # Dividir en párrafos no vacíos
    paragraphs = [p.strip() for p in content.split("\n\n") if p.strip()]

    hook = paragraphs[0] if paragraphs else ""
    cta  = paragraphs[-1] if len(paragraphs) > 1 else ""
    body = paragraphs[1:-1] if len(paragraphs) > 2 else []

    print(f"📄 Archivo parseado:")
    print(f"   Hook: {hook[:60]}...")
    print(f"   Slides de contenido: {len(body)}")
    print(f"   CTA: {cta[:60]}...")

    return {
        "hook": hook,
        "body": body,
        "cta": cta,
        "hashtags": hashtags
    }
# ══════════════════════════════════════════════════════════════
# 🖼️  CARGA DE IMÁGENES
# ══════════════════════════════════════════════════════════════

def load_images(images_dir: str) -> list:
    """Carga imágenes en orden numérico (img_01, img_02...)"""
    extensions = (".jpg", ".jpeg", ".png", ".webp")
    files = sorted([
        f for f in os.listdir(images_dir)
        if f.lower().endswith(extensions)
    ])
    paths = [os.path.join(images_dir, f) for f in files]
    print(f"🖼️  {len(paths)} imágenes encontradas en '{images_dir}'")
    return paths


# ══════════════════════════════════════════════════════════════
# 🎨 UTILIDADES DE DIBUJO — misma lógica que video_generator
# ══════════════════════════════════════════════════════════════

def load_font(font_path: str, size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(font_path, size)
    except IOError:
        print(f"⚠️  Fuente '{font_path}' no encontrada. Usando fuente por defecto.")
        return ImageFont.load_default()


def add_gradient_overlay(img: Image.Image, cfg: dict) -> Image.Image:
    """Añade gradiente oscuro en la parte inferior para que el texto sea legible."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    h = img.height
    grad_start = int(h * (1 - cfg["gradient_height_ratio"]))

    for y in range(grad_start, h):
        progress = (y - grad_start) / (h - grad_start)
        alpha = int(progress * cfg["overlay_opacity"])
        draw.line([(0, y), (img.width, y)], fill=(0, 0, 0, alpha))

    img = img.convert("RGBA")
    img = Image.alpha_composite(img, overlay)
    return img.convert("RGB")

def apply_filter(img: Image.Image, filter_name: str) -> Image.Image:
    """Aplica un filtro de color a la imagen."""
    if not filter_name:
        return img

    img = img.convert("RGB")
    r, g, b = img.split()

    if filter_name == "warm":
        # Sube rojos y bajar azules levemente
        r = r.point(lambda i: min(255, i + 20))
        b = b.point(lambda i: max(0, i - 15))

    elif filter_name == "cool":
        # Sube azules, baja rojos
        b = b.point(lambda i: min(255, i + 20))
        r = r.point(lambda i: max(0, i - 15))

    elif filter_name == "noir":
        # Blanco y negro con alto contraste
        img = img.convert("L").convert("RGB")
        img = img.point(lambda i: min(255, int(i * 1.2)))
        return img

    elif filter_name == "vintage":
        # Tono sepia suave
        r = r.point(lambda i: min(255, int(i * 1.1) + 15))
        g = g.point(lambda i: int(i * 0.95))
        b = b.point(lambda i: max(0, int(i * 0.85)))

    return Image.merge("RGB", (r, g, b))

def apply_border_filter(img: Image.Image, filter_name: str, intensity: float = 0.85) -> Image.Image:
    if not filter_name:
        return img

    img = img.convert("RGB")
    w, h = img.size

    if filter_name in ("vignette", "vignette_soft"):
        # Máscara: blanco en bordes (oscuro), negro en centro (transparente)
        mask = Image.new("L", (w, h), 255)
        draw = ImageDraw.Draw(mask)
        radius_x = int(w * (0.55 if filter_name == "vignette_soft" else 0.45))
        radius_y = int(h * (0.55 if filter_name == "vignette_soft" else 0.45))
        cx, cy = w // 2, h // 2
        draw.ellipse([cx - radius_x, cy - radius_y, cx + radius_x, cy + radius_y], fill=0)
        blur_radius = min(w, h) // (4 if filter_name == "vignette_soft" else 6)
        mask = mask.filter(ImageFilter.GaussianBlur(radius=blur_radius))
        mask = mask.point(lambda x: int(x * intensity))
        dark = Image.new("RGB", (w, h), (0, 0, 0))
        img = Image.composite(dark, img, mask)

    elif filter_name == "glow":
        # Igual pero overlay dorado en lugar de negro
        mask = Image.new("L", (w, h), 255)
        draw = ImageDraw.Draw(mask)
        cx, cy = w // 2, h // 2
        draw.ellipse([cx - w//2, cy - h//2, cx + w//2, cy + h//2], fill=0)
        mask = mask.filter(ImageFilter.GaussianBlur(radius=min(w, h) // 5))
        mask = mask.point(lambda x: int(x * intensity))
        glow = Image.new("RGB", (w, h), (180, 120, 20))
        img = Image.composite(glow, img, mask)

    elif filter_name == "frame_dark":
        border = int(18 * intensity)
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        for i in range(border):
            alpha = int(255 * (1 - i / border))
            draw.rectangle([i, i, w - i, h - i], outline=(0, 0, 0, alpha), width=1)
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    elif filter_name == "frame_light":
        border = int(16 * intensity)
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        for i in range(border):
            alpha = int(220 * (1 - i / border))
            draw.rectangle([i, i, w - i, h - i], outline=(255, 255, 255, alpha), width=1)
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    elif filter_name == "letterbox":
        bar_h = int(h * 0.08 * intensity)
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        draw.rectangle([0, 0, w, bar_h], fill=(0, 0, 0, 245))
        draw.rectangle([0, h - bar_h, w, h], fill=(0, 0, 0, 245))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    elif filter_name == "polaroid":
        b = int(22 * intensity)
        b_bottom = int(90 * intensity)
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        draw.rectangle([0, 0, b, h], fill=(255, 255, 255, 230))
        draw.rectangle([w - b, 0, w, h], fill=(255, 255, 255, 230))
        draw.rectangle([0, 0, w, b], fill=(255, 255, 255, 230))
        draw.rectangle([0, h - b_bottom, w, h], fill=(255, 255, 255, 230))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")

    return img

def draw_text_wrapped(draw, text: str, font, cfg: dict, y_start: int,
                      color=None, max_chars_per_line: int = 22):
    """Dibuja texto centrado con wrap automático y stroke."""
    if color is None:
        color = cfg["text_color"]

    width = cfg["width"]
    lines = textwrap.wrap(text, width=max_chars_per_line)

    line_height = font.size + 18
    total_h = len(lines) * line_height
    y = y_start - total_h // 2

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_w = bbox[2] - bbox[0]
        x = (width - text_w) // 2
        draw.text(
            (x, y), line, font=font, fill=color,
            stroke_width=cfg["stroke_width"],
            stroke_fill=cfg["stroke_color"]
        )
        y += line_height

    return y  # retorna y final por si necesitas apilar más texto

def draw_watermark(draw, cfg: dict, font_path: str):
    """Dibuja @chistoricas3 en la esquina superior izquierda de todas las imágenes."""
    font = load_font(font_path, 32)
    text = "@chistoricas3"
    draw.text(
        (30, 30),  # 👈 antes era (30, cfg["height"] - 55)
        text,
        font=font, fill=(255, 255, 255, 180),
        stroke_width=2, stroke_fill=(0, 0, 0)
    )

def prepare_base_image(image_path: str, cfg: dict) -> Image.Image:
    """Carga, recorta al tamaño del slide y aplica gradiente."""
    img = Image.open(image_path).convert("RGB")
    target_w, target_h = cfg["width"], cfg["height"]

    # Resize manteniendo proporción (crop centrado)
    img_ratio = img.width / img.height
    target_ratio = target_w / target_h

    if img_ratio > target_ratio:
        new_h = target_h
        new_w = int(new_h * img_ratio)
    else:
        new_w = target_w
        new_h = int(new_w / img_ratio)

    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - target_w) // 2
    top  = (new_h - target_h) // 2
    img = img.crop((left, top, left + target_w, top + target_h))

    img = apply_filter(img, cfg.get("image_filter"))
    img = apply_border_filter(img, cfg.get("border_filter"), cfg.get("border_intensity", 0.85))
    img = add_gradient_overlay(img, cfg)
    return img


# ══════════════════════════════════════════════════════════════
# 🃏 GENERACIÓN DE SLIDES
# ══════════════════════════════════════════════════════════════

def create_cover_slide(image_path: str, hook_text: str, cfg: dict) -> Image.Image:
    """
    Slide 1 — Portada:
    Imagen con texto grande de gancho en el centro-inferior.
    """
    img = prepare_base_image(image_path, cfg)
    draw = ImageDraw.Draw(img)
    font = load_font(cfg["font_path"], cfg["font_size_title"])

    y_center = int(cfg["height"] * 0.72)
    draw_text_wrapped(draw, hook_text, font, cfg, y_center,
                      color=cfg["highlight_color"], max_chars_per_line=18)
    draw_watermark(draw, cfg, cfg["font_path"])
    return img


def create_body_slide(image_path: str, body_text: str, slide_num: int,
                      total: int, cfg: dict) -> Image.Image:
    """
    Slides de contenido:
    Imagen con texto del cuerpo en la parte inferior.
    Número de slide pequeño arriba.
    """
    img = prepare_base_image(image_path, cfg)
    draw = ImageDraw.Draw(img)
    font_body  = load_font(cfg["font_path"], cfg["font_size_body"])
    font_small = load_font(cfg["font_path"], 36)

    # Número de slide arriba derecha
    num_text = f"{slide_num}/{total}"
    bbox = draw.textbbox((0, 0), num_text, font=font_small)
    num_w = bbox[2] - bbox[0]
    draw.text(
        (cfg["width"] - num_w - 40, 40), num_text,
        font=font_small, fill=(255, 255, 255, 200),
        stroke_width=3, stroke_fill=(0, 0, 0)
    )

    # Texto principal centrado en zona inferior
    y_center = int(cfg["height"] * 0.78)
    draw_text_wrapped(draw, body_text, font_body, cfg, y_center,
                      max_chars_per_line=24)
    draw_watermark(draw, cfg, cfg["font_path"])
    return img


def create_cta_slide(image_path: str, cta_text: str, cfg: dict) -> Image.Image:
    """
    Slide final — CTA:
    Fondo oscuro + texto en amarillo centrado.
    """
    img = prepare_base_image(image_path, cfg)

    # Overlay más oscuro para el CTA
    dark = Image.new("RGBA", (cfg["width"], cfg["height"]), (0, 0, 0, 180))
    img = img.convert("RGBA")
    img = Image.alpha_composite(img, dark).convert("RGB")

    draw = ImageDraw.Draw(img)
    font = load_font(cfg["font_path"], cfg["font_size_cta"])

    y_center = int(cfg["height"] * 0.50)
    draw_text_wrapped(draw, cta_text, font, cfg, y_center,
                      color=cfg["highlight_color"], max_chars_per_line=20)

    # Flecha o emoji de seguir debajo
    font_small = load_font(cfg["font_path"], 42)
    sub_text = "Desliza para ver más >"
    bbox = draw.textbbox((0, 0), sub_text, font=font_small)
    sub_w = bbox[2] - bbox[0]
    draw.text(
        ((cfg["width"] - sub_w) // 2, int(cfg["height"] * 0.75)),
        sub_text, font=font_small, fill=(255, 255, 255),
        stroke_width=3, stroke_fill=(0, 0, 0)
    )
    draw_watermark(draw, cfg, cfg["font_path"])
    return img


# ══════════════════════════════════════════════════════════════
# 🚀 PIPELINE PRINCIPAL
# ══════════════════════════════════════════════════════════════

def generate_carousel(cfg: dict = CONFIG, profile_image: str = None, cover_image: str = None):
    print("📱 Generando carrusel de Instagram...\n")

    # 1. Leer archivo instagram
    post = parse_instagram_file(cfg["instagram_post"])

    # 2. Cargar imágenes
    images = load_images(cfg["images_dir"])

    if len(images) < 1:
        raise FileNotFoundError(f"No hay imágenes en '{cfg['images_dir']}'")

    # 3. Calcular cuántos slides de contenido generar
    #    La portada usa img_01, el CTA usa la última imagen disponible
    #    Los slides intermedios usan las imágenes del medio
    body_texts  = post["body"]
    body_images = images[:] if len(images) > 2 else images[1:]

    # Si hay más textos que imágenes, recortar textos
    pairs = list(zip(body_texts, body_images))
    total_slides = 1 + len(pairs) + 1  # portada + contenido + CTA

    print(f"\n📊 Estructura del carrusel:")
    print(f"   Slide 1:        Portada")
    for i, (text, img) in enumerate(pairs):
        print(f"   Slide {i+2}:        Contenido → {os.path.basename(img)}")
    print(f"   Slide {total_slides}: CTA")
    print(f"   Total: {total_slides} slides\n")

    # 4. Crear carpeta de salida (limpia: si el carrusel anterior tenía más
    #    slides, los sobrantes se publicarían mezclados con los nuevos)
    os.makedirs(cfg["output_dir"], exist_ok=True)
    borrados = 0
    for file_name in os.listdir(cfg["output_dir"]):
        if file_name.lower().endswith((".jpg", ".jpeg", ".png")):
            os.remove(os.path.join(cfg["output_dir"], file_name))
            borrados += 1
    if borrados:
        print(f"🧹 {borrados} slides previos eliminados de '{cfg['output_dir']}'\n")

    slides_generated = []

    # Slide 1 — Portada
    print("🎨 Generando slide 1 (portada)...")
    #cover = create_cover_slide(images[0], post["hook"], cfg)
    # Slide 1 — Portada (usa --cover o img_01 por defecto)
    cover_path = cover_image if cover_image else images[0]
    cover = create_cover_slide(cover_path, post["hook"], cfg)
    path = os.path.join(cfg["output_dir"], "slide_01_portada.jpg")
    cover.save(path, "JPEG", quality=95)
    slides_generated.append(path)
    print(f"   ✅ {path}")

    # Slides de contenido
    for i, (text, img_path) in enumerate(pairs):
        slide_num = i + 2
        print(f"🎨 Generando slide {slide_num} (contenido)...")
        slide = create_body_slide(img_path, text, slide_num, total_slides, cfg)
        path = os.path.join(cfg["output_dir"], f"slide_{slide_num:02d}_contenido.jpg")
        slide.save(path, "JPEG", quality=95)
        slides_generated.append(path)
        print(f"   ✅ {path}")

    # Slide CTA — última imagen
    print(f"🎨 Generando slide {total_slides} (CTA)...")
    #cta_img = images[-1] if len(images) > 1 else images[0]
    #cta = create_cta_slide(cta_img, post["cta"], cfg)
    # Slide CTA — usa imagen de perfil obligatoria
    if not profile_image or not os.path.exists(profile_image):
        raise FileNotFoundError(f"Imagen de perfil no encontrada: {profile_image}")
    cta = create_cta_slide(profile_image, post["cta"], cfg)
    path = os.path.join(cfg["output_dir"], f"slide_{total_slides:02d}_cta.jpg")
    cta.save(path, "JPEG", quality=95)
    slides_generated.append(path)
    print(f"   ✅ {path}")

    print(f"\n🎉 Carrusel listo en '{cfg['output_dir']}' — {len(slides_generated)} slides")
    print(f"\n📋 Caption para Instagram (pegar en la app):")
    print("─" * 50)
    # El caption es el texto limpio sin instrucciones de imagen
    clean_body = "\n\n".join(post["body"])
    print(f"{post['hook']}\n\n{clean_body}\n\n{post['cta']}\n\n{post['hashtags']}")
    print("─" * 50)

    return slides_generated


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile", required=True,
                        help="Ruta a la imagen de perfil (slide CTA final)")
    parser.add_argument("--cover", default=None,
                        help="Imagen para portada (por defecto: img_01 del folder)")
    args = parser.parse_args()

    generate_carousel(CONFIG, profile_image=args.profile, cover_image=args.cover)

    shutil.copytree("carousel_slides", f"proyectos/{PROYECTO}/carousel_slides", dirs_exist_ok=True)
    shutil.copytree("source_images", f"proyectos/{PROYECTO}/source_images", dirs_exist_ok=True)

