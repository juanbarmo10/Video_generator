
#%%

"""
╔══════════════════════════════════════════════════════════════╗
║         🎬 GENERADOR DE VIDEO VIRAL PARA REDES SOCIALES      ║
║         Imágenes + Audio de narración + Subtítulos animados  ║
╚══════════════════════════════════════════════════════════════╝

Requisitos:
    pip install moviepy faster-whisper Pillow numpy

Uso básico:
    python video_generator.py

Archivos necesarios:
    - images/       → Carpeta con imágenes .png (ordenadas alfabéticamente)
    - voice.mp3     → Audio de narración
    - fonts/        → Fuente .ttf para los subtítulos
"""

import os
import shutil
import math
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    AudioFileClip, ImageClip, VideoClip, ColorClip,
    CompositeVideoClip, concatenate_videoclips
)
from faster_whisper import WhisperModel
from dotenv import load_dotenv

load_dotenv()
# ══════════════════════════════════════════════════════════════
# ⚙️  CONFIGURACIÓN CENTRAL — Ajusta todo aquí
# ══════════════════════════════════════════════════════════════
TITULO_VIDEO = os.environ.get("TITULO_VIDEO")
PROYECTO = os.environ.get("PROYECTO")

if not PROYECTO:
    raise SystemExit(
        "❌ Falta PROYECTO (entorno o .env). Sin él el video se llamaría 'video_None.mp4'."
    )

if not TITULO_VIDEO:
    raise SystemExit(
        "❌ Falta TITULO_VIDEO (lo escribe el paso 02 en .env). Sin él falla el render del título."
    )


CONFIG = {
    "video_title": TITULO_VIDEO,  # cambia por video
    "video_name" : PROYECTO,

    # ── Archivos ──────────────────────────────────────────────
    "images_dir":   "images_IA",           # Carpeta de imágenes
    "audio_file":   "voice.mp3",        # Audio de narración
    # "output_file":  "final_video.mp4",  # Nombre del archivo de salida

    # ── Dimensiones del video ─────────────────────────────────
    # Formatos comunes:
    #   TikTok / Reels / Shorts → (1080, 1920)  [9:16 vertical]
    #   YouTube estándar        → (1920, 1080)  [16:9 horizontal]
    #   Instagram cuadrado      → (1080, 1080)  [1:1]
    #   Twitter/X               → (1280, 720)   [16:9 HD]
    "video_width":  1080,
    "video_height": 1920,

    # ── Calidad y rendimiento ─────────────────────────────────
    # fps: 24 = cinematográfico, 30 = estándar redes, 60 = suave/gaming
    "fps": 30,
    # preset: ultrafast < superfast < veryfast < faster < fast < medium < slow < veryslow
    # → Más lento = mejor compresión/calidad, más tiempo de exportación
    "preset": "fast",
    # crf: Calidad de compresión (0=sin pérdida, 23=default, 28=bajo, 51=mínimo)
    # → Para redes: entre 18 y 23 es ideal
    "crf": "20",
    # Códec de video: libx264 (compatible), libx265 (mejor compresión, menos compatible)
    "video_codec": "libx264",
    # Códec de audio: aac (universal), mp3, libopus (mejor calidad/tamaño)
    "audio_codec": "aac",

    # ── Modelo de transcripción Whisper ───────────────────────
    # Opciones: "tiny" (rápido), "base", "small", "medium", "large" (preciso)
    "whisper_model": "medium",
    # Idioma del audio (None = detección automática, "es" = español, "en" = inglés)
    "whisper_language": "es",

    # ── Subtítulos ────────────────────────────────────────────
    # Fuente para los subtítulos (ruta a archivo .ttf)
    "font_path": "fonts/Bungee_Spice/BungeeSpice-Regular.ttf", #fonts/Cossette_Texte/CossetteTexte-Regular.ttf",
    # Tamaño de la fuente (en píxeles)
    "font_size": 100,
    # Número de palabras visibles simultáneamente
    "words_on_screen": 2,
    # Posición vertical de los subtítulos (0.0 = arriba, 1.0 = abajo)
    # 0.75 = 75% desde arriba → zona inferior pero sin pegarse al borde
    "subtitle_y_ratio": 0.55,
    # Altura del área de subtítulos en píxeles
    "subtitle_area_height": 220,
    # Color de la palabra activa (siendo pronunciada)
    "highlight_color": (255, 220, 0),   # Amarillo dorado
    # Color de palabras inactivas (contexto)
    "inactive_color": (255, 255, 255),  # Blanco

    # ── Configuración de Fondos de Subtítulos ─────────────────
    "subtitle_bg_mode": "none",         # Opciones: "full" (rectángulo ancho), "text" (sigue las letras), "none" (sin fondo)
    "subtitle_bg_color": (0, 0, 0),     # RGB del fondo de subtítulos
    "subtitle_bg_opacity": 100,         # 0=transparente, 255=opaco
    "subtitle_bg_padding": 0,          # Margen del fondo ajustado al texto
    
    # ── Configuración de Títulos ──────────────────────────────
    "title_position": ("center", 20),   # Posición (X, Y)
    "title_bg_mode": "text",            # Opciones: "full", "text", "none"
    "title_bg_color": (193, 89, 57),    # RGB del fondo del título
    "title_bg_opacity": 10,            # 0=transparente, 255=opaco
    "title_bg_padding": 10,             # Margen del fondo ajustado al texto

    # ── Animación de imágenes ─────────────────────────────────
    # Factor de zoom (1.0 = sin zoom, 1.05 = zoom suave, 1.15 = zoom pronunciado)
    "zoom_min": 1.05,
    "zoom_max": 1.15,
    # Duración del crossfade entre imágenes en segundos (0 = sin transición)
    "crossfade_duration": 0.5,
}


# ══════════════════════════════════════════════════════════════
# 🖼️  CARGA DE IMÁGENES
# ══════════════════════════════════════════════════════════════

def load_images(images_dir: str) -> list[str]:
    """
    Carga las rutas de todas las imágenes PNG de la carpeta,
    ordenadas alfabéticamente para mantener secuencia.
    """
    files = sorted([
        f for f in os.listdir(images_dir)
        if f.lower().endswith(".png")
    ])
    if not files:
        raise FileNotFoundError(f"No se encontraron imágenes .png en '{images_dir}'")
    
    paths = [os.path.join(images_dir, f) for f in files]
    print(f"🖼️  {len(paths)} imágenes cargadas desde '{images_dir}'")
    return paths


# ══════════════════════════════════════════════════════════════
# 🎙️  TRANSCRIPCIÓN DE AUDIO (Whisper)
# ══════════════════════════════════════════════════════════════

def transcribe_words(audio_path: str, model_size: str = "base", language: str = None) -> list[dict]:
    """
    Transcribe el audio y extrae timestamps por PALABRA (no por segmento).
    Esto permite resaltar cada palabra exactamente cuando se pronuncia.
    
    Retorna lista de: {"word": str, "start": float, "end": float}
    """
    print(f"🎙️  Transcribiendo audio con modelo '{model_size}'...")
    
    model = WhisperModel(model_size)
    segments, info = model.transcribe(
        audio_path,
        word_timestamps=True,
        language=language,
        # Mejora la precisión de los timestamps
        condition_on_previous_text=False,
        vad_filter=True,                    # Filtra silencios automáticamente
    )

    words = []
    for segment in segments:
        if segment.words:
            for word in segment.words:
                # Limpiamos la palabra de espacios y caracteres extraños
                clean_word = word.word.strip()
                if clean_word:
                    words.append({
                        "word":  clean_word,
                        "start": word.start,
                        "end":   word.end
                    })

    print(f"✅  {len(words)} palabras transcritas")
    return words


# ══════════════════════════════════════════════════════════════
# 🎬  CREACIÓN DEL VIDEO (imágenes + audio)
# ══════════════════════════════════════════════════════════════

def ease_in_out_sine(t: float) -> float:
    """
    Curva de easing suave (sinusoidal).
    Transforma t ∈ [0,1] → [0,1] con aceleración y desaceleración.
    Mucho más natural que el zoom lineal original.
    """
    return -(math.cos(math.pi * t) - 1) / 2


def add_smooth_zoom(clip, zoom_factor: float = 1.05):
    """
    Aplica un zoom suave con easing sinusoidal al clip.
    El zoom arranca lento, acelera en el medio y vuelve a desacelerar.
    Evita el efecto "mecánico" del zoom lineal.
    """
    def zoom_func(t):
        progress = ease_in_out_sine(t / clip.duration)
        return 1 + (zoom_factor - 1) * progress

    return clip.resize(zoom_func)


def create_video(image_paths: list[str], audio_path: str, cfg: dict):
    """
    Construye el video principal:
    - Escala cada imagen al tamaño de video configurado
    - Aplica zoom suave con easing
    - Agrega crossfade entre imágenes para transiciones fluidas
    - Sincroniza con el audio de narración
    """
    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    n_images = len(image_paths)
    target_w = cfg["video_width"]
    target_h = cfg["video_height"]
    crossfade = cfg["crossfade_duration"]

    # Tiempo por imagen, descontando los crossfades solapados
    duration_per_image = total_duration / n_images

    print(f"🎬  Creando video: {n_images} imágenes × {duration_per_image:.2f}s = {total_duration:.2f}s total")

    clips = []
    for i, img_path in enumerate(image_paths):
        # Carga la imagen y la escala para cubrir el frame (sin barras negras)
        clip = (
            ImageClip(img_path)
            .set_duration(duration_per_image + crossfade)  # Un poco extra para el crossfade
            .resize(height=target_h)                        # Escala por altura primero
        )

        # Si el ancho resultante es menor al objetivo, escalar por ancho
        if clip.size[0] < target_w:
            clip = clip.resize(width=target_w)

        # Recortar al centro para que quede exactamente en las dimensiones objetivo
        clip = clip.crop(
            x_center=clip.size[0] / 2,
            y_center=clip.size[1] / 2,
            width=target_w,
            height=target_h
        )

        # Zoom con variación aleatoria entre escenas (dentro del rango configurado)
        zoom = random.uniform(cfg["zoom_min"], cfg["zoom_max"])
        # Dirección del zoom alterna (a veces zoom-in, a veces zoom-out)
        if i % 2 == 0:
            clip = add_smooth_zoom(clip, zoom_factor=zoom)
        else:
            # Zoom-out: empieza grande y reduce
            clip = add_smooth_zoom(clip, zoom_factor=1.0 / zoom + (zoom - 1))

        clip = clip.set_start(i * duration_per_image)
        clips.append(clip)

    # Aplicar crossfade entre clips consecutivos
    if crossfade > 0 and len(clips) > 1:
        faded_clips = [clips[0]]
        for i in range(1, len(clips)):
            faded_clips.append(clips[i].crossfadein(crossfade))
        video = CompositeVideoClip(faded_clips, size=(target_w, target_h))
        video = video.set_duration(total_duration)
    else:
        video = concatenate_videoclips(clips, method="compose")
        video = video.set_duration(total_duration)

    video = video.set_audio(audio)
    return video


# ══════════════════════════════════════════════════════════════
# 📝  SUBTÍTULOS DINÁMICOS (por palabra)
# ══════════════════════════════════════════════════════════════

def get_active_word_window(words: list[dict], t: float, window_size: int = 2) -> tuple[list[dict], int]:
    """
    Agrupa las palabras en pares fijos. Muestra el par actual y resalta
    la palabra que se está pronunciando. Cambia al siguiente par solo
    cuando la 2da palabra del par termina de pronunciarse.
    Si una palabra es muy larga para el par, va sola.
    """
    if not words:
        return [], -1

    # Construir pares fijos de palabras
    pairs = []
    i = 0
    while i < len(words):
        pairs.append((i, min(i + 1, len(words) - 1)))
        i += 2

    # Encontrar qué par corresponde al tiempo t
    active_pair_idx = None
    for pi, (start_wi, end_wi) in enumerate(pairs):
        pair_end_time = words[end_wi]["end"]
        next_pair_start = words[pairs[pi + 1][0]]["start"] if pi + 1 < len(pairs) else float("inf")

        if t <= pair_end_time or (pi + 1 < len(pairs) and t < next_pair_start):
            active_pair_idx = pi
            break

    if active_pair_idx is None:
        active_pair_idx = len(pairs) - 1

    start_wi, end_wi = pairs[active_pair_idx]
    window = words[start_wi:end_wi + 1]

    # Encontrar cuál palabra dentro del par está activa
    local_active = -1
    for li, w in enumerate(window):
        if w["start"] <= t <= w["end"]:
            local_active = li
            break
    # Si estamos entre palabras del mismo par, mantener la última pronunciada
    if local_active == -1 and len(window) > 1:
        if t > window[0]["end"] and t < window[1]["start"]:
            local_active = 0

    return window, local_active

def get_text_total_width(words_text: list[str], draw: ImageDraw.Draw, font: ImageFont.FreeTypeFont) -> float:
    """Calcula el ancho total de un grupo de palabras (para centrar el bloque)."""
    total = 0
    for i, word in enumerate(words_text):
        text = word + (" " if i < len(words_text) - 1 else "")
        total += draw.textlength(text, font=font)
    return total

def create_subtitle_frame(
    words: list[dict],
    t: float,
    width: int,
    height: int,
    cfg: dict,
    font: ImageFont.FreeTypeFont
) -> np.ndarray:
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    window, local_active = get_active_word_window(words, t, cfg["words_on_screen"])

    if not window:
        return np.array(img)#np.array(img.convert("RGB"))

    draw = ImageDraw.Draw(img)
    words_text = [w["word"] for w in window]

    max_width = width - 60  # margen lateral
    total_width = get_text_total_width(words_text, draw, font)

    bg_mode = cfg.get("subtitle_bg_mode", "none")
    bg_color = cfg.get("subtitle_bg_color", (0, 0, 0)) + (cfg.get("subtitle_bg_opacity", 0),)
    pad = cfg.get("subtitle_bg_padding", 15)

    # Si no caben en una línea, partir en dos líneas (una palabra por línea)
    if total_width > max_width and len(words_text) == 2:
        lines = [[words_text[0], 0], [words_text[1], 1]]  # [texto, índice_original]
        line_h = cfg["font_size"] + 10
        y_start = (height - line_h * 2) // 2

        # Dibujar fondo para 2 líneas
        if bg_mode == "full":
            draw.rectangle([0, 0, width, height], fill=bg_color)
        elif bg_mode == "text":
            max_w = max(draw.textlength(w, font=font) for w, _ in lines)
            total_h = len(lines) * line_h
            x0 = (width - max_w) // 2 - pad
            draw.rectangle([x0, y_start - pad, x0 + max_w + pad*2, y_start + total_h - 10 + pad], fill=bg_color)

        for li, (word, orig_idx) in enumerate(lines):
            is_active = (orig_idx == local_active)
            color = cfg["highlight_color"] if is_active else cfg["inactive_color"]
            text_w = draw.textlength(word, font=font)
            x = (width - text_w) // 2
            y = y_start + li * line_h
            draw.text((x, y), word, font=font, fill=color,
                      stroke_width=6, stroke_fill=(0, 0, 0, 255))
    else:
        # Una sola línea centrada
        y_text = (height - cfg["font_size"]) // 2
        x = (width - total_width) // 2

        # Dibujar fondo para 1 línea
        if bg_mode == "full":
            draw.rectangle([0, 0, width, height], fill=bg_color)
        elif bg_mode == "text":
            draw.rectangle([x - pad, y_text - pad, x + total_width + pad, y_text + cfg["font_size"] + pad], fill=bg_color)

        for i, word in enumerate(words_text):
            is_active = (i == local_active)
            color = cfg["highlight_color"] if is_active else cfg["inactive_color"]
            draw.text((x, y_text), word, font=font, fill=color,
                      stroke_width=6, stroke_fill=(0, 0, 0, 255))
            sep = " " if i < len(words_text) - 1 else ""
            x += draw.textlength(word + sep, font=font)

    return np.array(img) #np.array(img.convert("RGB"))

def create_dynamic_subtitles(words: list[dict], video_size: tuple, duration: float, cfg: dict) -> VideoClip:
    """
    Crea el clip de subtítulos como un VideoClip dinámico.
    Cada frame se genera en tiempo real según las palabras activas.
    """
    width = video_size[0]
    #height = cfg["subtitle_area_height"]
    #height = cfg["font_size"] + 80
    height = (cfg["font_size"] + 10) * 2 + 40  # espacio para 2 líneas

    # Cargar fuente una sola vez (fuera del loop de frames, por eficiencia)
    try:
        font = ImageFont.truetype(cfg["font_path"], cfg["font_size"])
    except IOError:
        print(f"⚠️  No se encontró la fuente '{cfg['font_path']}'. Usando fuente por defecto.")
        font = ImageFont.load_default()

    # y_position: qué porcentaje del video (de arriba hacia abajo)
    # Usamos set_position con lambda para posición dinámica
    y_pos = int(video_size[1] * cfg["subtitle_y_ratio"] - height // 2)

    def make_frame(t):
        return create_subtitle_frame(words, t, width, height, cfg, font)
    # Creamos el clip manteniendo los 4 canales (RGBA)
    clip_rgba = VideoClip(make_frame, duration=duration)

    # Separamos el canal Alpha para usarlo como máscara
    # Esto convierte el clip de (H, W, 4) a (H, W, 3) y le asigna su transparencia aparte
    mask = clip_rgba.to_mask()

    # 2. Convertimos el clip a RGB (quita el 4to canal para que sea shape (..., 3))
    # Usamos un lambda para forzar la conversión de cada frame a RGB
    clip_rgb = clip_rgba.fl_image(lambda image: image[:,:,:3])

    # 3. Le asignamos la máscara al clip de 3 canales
    subtitle_clip = clip_rgb.set_mask(mask)

    subtitle_clip = subtitle_clip.set_position(("center", y_pos))
    # Agregar el alpha manualmente:
    subtitle_clip = subtitle_clip.set_fps(cfg.get("fps", 15))

    return subtitle_clip


# ══════════════════════════════════════════════════════════════
# 💾  EXPORTACIÓN DEL VIDEO
# ══════════════════════════════════════════════════════════════

def export_video(final_clip, cfg: dict):
    """
    Exporta el video final con los parámetros de calidad configurados.
    Incluye parámetros FFmpeg optimizados para redes sociales.
    """
    output = cfg["output_file"]
    print(f"\n🚀  Exportando video → '{output}'")
    print(f"    Resolución: {cfg['video_width']}×{cfg['video_height']} | FPS: {cfg['fps']} | Preset: {cfg['preset']}")

    final_clip.write_videofile(
        output,
        verbose=False,
        fps=cfg["fps"],
        codec=cfg["video_codec"],
        audio_codec=cfg["audio_codec"],
        preset=cfg["preset"],
        ffmpeg_params=[
            "-pix_fmt", "yuv420p",      # Compatibilidad máxima (iOS, Android, web)
            "-crf", cfg["crf"],          # Calidad de compresión (ver CONFIG)
            "-movflags", "+faststart",   # Permite reproducción mientras descarga (streaming)
            "-profile:v", "high",        # Perfil H.264 de alta calidad
        ],
        threads=os.cpu_count(),                       # Usar múltiples núcleos de CPU
        logger="bar",                    # Muestra barra de progreso
    )

    print(f"\n✅  Video exportado exitosamente: '{output}'")

def create_title_clip(title: str, video_size: tuple, duration: float, cfg: dict) -> VideoClip:
    width, height = video_size
    font_size = 52
    try:
        font = ImageFont.truetype(cfg["font_path"], font_size)
    except IOError:
        font = ImageFont.load_default()

    # Dividir en dos líneas si no cabe en una
    def wrap_title(text, draw, font, max_width):
        words = text.split()
        lines = []
        current = []
        for word in words:
            test = " ".join(current + [word])
            if draw.textlength(test, font=font) <= max_width:
                current.append(word)
            else:
                if current:
                    lines.append(" ".join(current))
                current = [word]
        if current:
            lines.append(" ".join(current))
        return lines

    clip_h = (font_size + 20) * 2 + 30  # altura para hasta 2 líneas + padding

    def make_frame(t):
        img = Image.new("RGBA", (width, clip_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        lines = wrap_title(title, draw, font, width - 40)

        # Fondo configurable
        bg_mode = cfg.get("title_bg_mode", "full")
        bg_color = cfg["title_bg_color"] + (cfg["title_bg_opacity"],)
        total_text_h = len(lines) * (font_size + 10)
        y = (clip_h - total_text_h) // 2
        
        if bg_mode == "full":
            draw.rectangle([0, 0, width, clip_h], fill=bg_color)
        elif bg_mode == "text":
            pad = cfg.get("title_bg_padding", 20)
            max_text_w = max([draw.textlength(line, font=font) for line in lines])
            x0 = (width - max_text_w) // 2 - pad
            draw.rectangle([x0, y - pad, x0 + max_text_w + pad*2, y + total_text_h - 10 + pad], fill=bg_color)

        # Dibujar líneas centradas
        total_text_h = len(lines) * (font_size + 10)
        y = (clip_h - total_text_h) // 2
        for line in lines:
            text_w = draw.textlength(line, font=font)
            x = (width - text_w) // 2
            draw.text((x, y), line, font=font, fill=(255, 255, 255, 255),
                      stroke_width=4, stroke_fill=(0, 0, 0, 255))
            y += font_size + 10

        return np.array(img)#np.array(img.convert("RGB"))

    # Creamos el clip manteniendo los 4 canales (RGBA)
    clip_rgba = VideoClip(make_frame, duration=duration)

    # Separamos el canal Alpha para usarlo como máscara
    # Esto convierte el clip de (H, W, 4) a (H, W, 3) y le asigna su transparencia aparte
    mask = clip_rgba.to_mask()

    # 2. Convertimos el clip a RGB (quita el 4to canal para que sea shape (..., 3))
    # Usamos un lambda para forzar la conversión de cada frame a RGB
    clip_rgb = clip_rgba.fl_image(lambda image: image[:,:,:3])

    # 3. Le asignamos la máscara al clip de 3 canales
    clip = clip_rgb.set_mask(mask)

    clip = clip.set_fps(cfg.get("fps", 30))
    clip = clip.set_position(cfg.get("title_position", ("center", 0)))
    return clip

def create_cta_clip(text: str, video_size: tuple, duration: float, cfg: dict) -> VideoClip:
    """Overlay de CTA que aparece en los últimos segundos del video."""
    width, height = video_size
    font_size = 65
    try:
        font = ImageFont.truetype(cfg["font_path"], font_size)
    except IOError:
        font = ImageFont.load_default()

    clip_h = font_size + 40

    def make_frame(t):
        img = Image.new("RGBA", (width, clip_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)
        text_w = draw.textlength(text, font=font)
        x = (width - text_w) // 2
        y = 5
        draw.text((x, y), text, font=font, fill=(255, 220, 0, 255),
                stroke_width=6, stroke_fill=(0, 0, 0, 255))
        return np.array(img)#np.array(img.convert("RGB"))


    # Creamos el clip manteniendo los 4 canales (RGBA)
    clip_rgba = VideoClip(make_frame, duration=duration)

    # Separamos el canal Alpha para usarlo como máscara
    # Esto convierte el clip de (H, W, 4) a (H, W, 3) y le asigna su transparencia aparte
    # 1. Extraemos la máscara del clip que tiene transparencia
    mask = clip_rgba.to_mask()

    # 2. Convertimos el clip a RGB (quita el 4to canal para que sea shape (..., 3))
    # Usamos un lambda para forzar la conversión de cada frame a RGB
    clip_rgb = clip_rgba.fl_image(lambda image: image[:,:,:3])

    # 3. Le asignamos la máscara al clip de 3 canales
    clip = clip_rgb.set_mask(mask)

    clip = clip.set_position(("center", int(height * 0.82)))
    clip = clip.set_fps(cfg.get("fps", 30))
    return clip


# ══════════════════════════════════════════════════════════════
# 🎯  PIPELINE PRINCIPAL
# ══════════════════════════════════════════════════════════════

def main():
    print("═" * 60)
    print("  GENERADOR DE VIDEOS — INICIO")
    print("═" * 60)

    cfg = CONFIG

    name = cfg["video_name"]

    print(f"📦 Creando respaldo del proyecto: {name}...")

    cfg["output_file"] = f"videos_no_music/video_{name}.mp4"

    # ── Paso 1: Cargar imágenes ───────────────────────────────
    images = load_images(cfg["images_dir"])

    # ── Paso 2: Crear video base (imágenes + audio) ───────────
    video = create_video(images, cfg["audio_file"], cfg)
    video = video.set_ismask(False)
    print(f"✅  Video base creado | Duración: {video.duration:.2f}s | Tamaño: {video.size}")

    # ── Paso 3: Transcribir audio por palabras ────────────────
    words = transcribe_words(
        cfg["audio_file"],
        model_size=cfg["whisper_model"],
        language=cfg["whisper_language"]
    )

    # ── Paso 4: Crear subtítulos dinámicos ───────────────────
    print("📝  Generando subtítulos dinámicos...")
    subtitle_clip = create_dynamic_subtitles(
        words,
        video_size=(cfg["video_width"], cfg["video_height"]),
        duration=video.duration,
        cfg=cfg
    )

    # ── Paso 5: Componer video final ──────────────────────────
    print("🎞️  Componiendo video final...")

    cta_duration = 3  # segundos que dura el CTA
    cta_start = video.duration - cta_duration

    title_clip = create_title_clip(
        cfg["video_title"],
        video_size=(cfg["video_width"], cfg["video_height"]),
        duration=video.duration,
        cfg=cfg
    )

    cta_clip = create_cta_clip(
        "Sígueme para más historias",
        video_size=(cfg["video_width"], cfg["video_height"]),
        duration=cta_duration,
        cfg=cfg
    ).set_start(cta_start)

    final = CompositeVideoClip(
        [video, subtitle_clip, title_clip, cta_clip],
        size=(cfg["video_width"], cfg["video_height"])
    ).set_duration(video.duration)

    # 🧪 MODO PRUEBA — comenta esta línea para producción
    #final = final.subclip(0, 3)  # solo primeros 3 segundos

    # ── Paso 6: Exportar ──────────────────────────────────────
    export_video(final, cfg)

    # -- Copiar audio e imagenes_IA a proyectos ---

    dir_proyecto = f"proyectos/{cfg['video_name']}/"
    os.makedirs(dir_proyecto, exist_ok=True)

    shutil.copy(cfg['audio_file'], f"{dir_proyecto}{cfg['video_name']}.mp3")

    dir_images_IA = f'{dir_proyecto}images_IA/'
    os.makedirs(dir_images_IA, exist_ok=True)

    for file_name in os.listdir(cfg['images_dir']):
        source_file = os.path.join(cfg['images_dir'], file_name)
        dest_file = os.path.join(dir_images_IA, file_name)

        if os.path.isfile(source_file):
            shutil.copy(source_file, dest_file)

    print("\n🏆  ¡Listo para publicar!")
    print("═" * 60)

if __name__ == "__main__":
    main()