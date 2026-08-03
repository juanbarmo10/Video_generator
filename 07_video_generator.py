
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
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance
from moviepy.editor import (
    AudioFileClip, ImageClip, VideoClip, ColorClip,
    CompositeVideoClip, concatenate_videoclips
)
from faster_whisper import WhisperModel
from dotenv import load_dotenv

from estado import verificar_estado

load_dotenv()

# Aborta si voice.mp3 / images_IA son de otro tema (ver estado.py)
verificar_estado("paso 07")
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

    # ── CTA final ─────────────────────────────────────────────
    # Posición vertical del CTA (0.0 = arriba, 1.0 = abajo).
    # Máximo 0.72: más abajo lo tapan el caption y los botones de Reels/TikTok.
    "cta_y_ratio": 0.70,
    # Va ENCIMA de la última frase, no después: un colchón al final hunde el
    # % de retención y corta el bucle.
    "cta_duration": 2.0,                # segundos que dura el CTA al final
    # Una pregunta genera comentarios, y los comentarios son señal de
    # distribución. "Sígueme" no lo es.
    "cta_texto": "¿Tú lo sabías?",

    # ── Configuración de Fondos de Subtítulos ─────────────────
    "subtitle_bg_mode": "none",         # Opciones: "full" (rectángulo ancho), "text" (sigue las letras), "none" (sin fondo)
    "subtitle_bg_color": (0, 0, 0),     # RGB del fondo de subtítulos
    "subtitle_bg_opacity": 100,         # 0=transparente, 255=opaco
    "subtitle_bg_padding": 0,          # Margen del fondo ajustado al texto
    
    # ── Configuración de Títulos ──────────────────────────────
    # y=200 es el borde de la zona segura: por encima queda tapado por la UI
    # de Reels/TikTok (~130px) y de Shorts (~110px).
    "title_position": ("center", 200),  # Posición (X, Y)
    "title_bg_mode": "text",            # Opciones: "full", "text", "none"
    "title_bg_color": (193, 89, 57),    # RGB del fondo del título
    # Antes 10: con el bug de to_mask() el rojo (193) mandaba y se veía al 76%.
    # Ya corregido, 10 sería invisible — 170 reproduce la banda que se veía.
    "title_bg_opacity": 170,            # 0=transparente, 255=opaco
    "title_bg_padding": 10,             # Margen del fondo ajustado al texto
    # El título quemado los 40s spoileaba la historia en el frame 0.
    # Ahora solo abre el video y se va con fade.
    "title_duration": 2.5,              # segundos que dura el título en pantalla
    "title_fadeout": 0.4,               # fade de salida del título

    # ── Animación de imágenes ─────────────────────────────────
    # Factor de zoom (1.0 = sin zoom, 1.05 = zoom suave, 1.15 = zoom pronunciado)
    "zoom_min": 1.05,
    "zoom_max": 1.15,
    # Duración del crossfade entre imágenes en segundos (0 = sin transición)
    "crossfade_duration": 0.5,

    # ── Ritmo visual (sub-planos) ─────────────────────────────
    # Cada imagen se parte en N encuadres distintos (Ken Burns sobre regiones
    # diferentes) para multiplicar los cortes SIN generar más imágenes.
    # Antes: 8 imágenes / 38s = 1 corte cada 4.9s — ritmo de diapositivas.
    #
    # El número de planos se calcula solo a partir de "duracion_plano_objetivo",
    # porque tanto la duración del audio como la cantidad de imágenes cambian
    # (las fotos reales suman a la secuencia). Con un valor fijo, un guion corto
    # + fotos reales daba cortes de 0.9s, que marean.
    "duracion_plano_objetivo": 1.8,     # segundos por corte (1.5-2.5 retiene)
    # Override manual: None = automático. Poner 1 restaura el comportamiento
    # anterior (un plano por imagen, sin sub-planos).
    "planos_por_imagen": None,
    # Escala mínima de los recortes. Ojo: 0.75 significa ampliar la imagen un
    # 33% extra. Con fuentes de 720x1280 no bajes de 0.85 o se ve pixelado.
    "recorte_escala_min": 0.85,

    # ── Barra de progreso ─────────────────────────────────────
    # Le dice al espectador "esto es corto, aguanta". Sube la tasa de completado.
    "barra_progreso": True,
    "barra_altura": 8,                  # px
    "barra_color": (255, 220, 0),       # mismo amarillo que el resaltado
    "barra_fondo_alpha": 40,            # opacidad del carril vacío (0-255)
    "barra_y": 0,                       # 0 = pegada arriba del todo

    # ── Subtítulos: ajuste automático ─────────────────────────
    # Palabras muy largas (CONSTANTINOPLA a 100px) se salían del clip por
    # ambos lados. Ahora la fuente se reduce hasta que el texto entra.
    "font_size_min": 44,

    # ── Exportación de subtítulos ─────────────────────────────
    # YouTube indexa el .srt → mejora la búsqueda. Los timestamps ya los
    # tenemos de Whisper, así que es gratis.
    "exportar_srt": True,
    "srt_palabras_por_linea": 6,

    # ── Fotos reales mezcladas con las ilustraciones ──────────
    # El paso 05 ya descarga fotos reales de Wikimedia/DuckDuckGo y hasta ahora
    # solo se usaban en el carrusel. Para historia y deporte una foto real vale
    # más que diez ilustraciones IA: da prueba, credibilidad y rompe la
    # monotonía de estilo (8 imágenes con la misma paleta cansan la vista).
    "usar_fotos_reales": True,
    "fotos_reales_dir": "source_images",
    "fotos_reales_max": 2,              # cuántas intercalar (0 = ninguna)
    # Dónde caen, como fracción de la secuencia (0.0 = inicio, 1.0 = final).
    # Se evita el arranque: ahí queremos el primer plano ilustrado del gancho.
    "fotos_reales_posiciones": (0.45, 0.80),
    # Tinte cálido para que la foto no choque con el estilo pergamino (0 = nada)
    "fotos_reales_tinte": 0.18,
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


CACHE_FOTOS = ".cache_fotos_reales"


def preparar_fotos_reales(cfg: dict) -> list[str]:
    """Convierte las fotos reales del paso 05 (1080x1080) a 9:16 verticales.

    El fondo se rellena con la propia foto ampliada y desenfocada, así no
    aparecen barras negras ni hay que recortar la cara del protagonista.
    Devuelve las rutas ya listas en el cache; [] si no hay fotos.
    """
    origen = cfg["fotos_reales_dir"]
    if not os.path.isdir(origen):
        return []

    fotos = sorted(
        f for f in os.listdir(origen)
        if f.lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
    )
    if not fotos:
        return []

    # El cache es del tema EN CURSO: hay que vaciarlo o se cuelan fotos del anterior
    if os.path.isdir(CACHE_FOTOS):
        shutil.rmtree(CACHE_FOTOS)
    os.makedirs(CACHE_FOTOS, exist_ok=True)

    target_w, target_h = cfg["video_width"], cfg["video_height"]
    tinte = cfg["fotos_reales_tinte"]
    listas = []

    for i, nombre in enumerate(fotos[: cfg["fotos_reales_max"]]):
        try:
            foto = Image.open(os.path.join(origen, nombre)).convert("RGB")
        except Exception as exc:
            print(f"⚠️  No se pudo abrir '{nombre}': {exc}")
            continue

        # Fondo: la misma foto ampliada a cubrir el frame y desenfocada
        ratio = max(target_w / foto.width, target_h / foto.height)
        fondo = foto.resize(
            (int(foto.width * ratio), int(foto.height * ratio)), Image.LANCZOS
        )
        izq = (fondo.width - target_w) // 2
        arr = (fondo.height - target_h) // 2
        fondo = fondo.crop((izq, arr, izq + target_w, arr + target_h))
        fondo = fondo.filter(ImageFilter.GaussianBlur(28))
        fondo = ImageEnhance.Brightness(fondo).enhance(0.55)

        # Primer plano: la foto completa escalada al ancho, centrada
        escala = target_w / foto.width
        frente = foto.resize(
            (target_w, int(foto.height * escala)), Image.LANCZOS
        )
        fondo.paste(frente, (0, (target_h - frente.height) // 2))

        # Tinte cálido para acercarla al look pergamino de las ilustraciones
        if tinte > 0:
            capa = Image.new("RGB", (target_w, target_h), (232, 196, 140))
            fondo = Image.blend(fondo, capa, tinte)

        destino = os.path.join(CACHE_FOTOS, f"real_{i}.png")
        fondo.save(destino, "PNG")
        listas.append(destino)

    if listas:
        print(f"📷  {len(listas)} fotos reales preparadas desde '{origen}'")
    return listas


def intercalar_fotos_reales(ilustraciones: list[str], fotos: list[str],
                            cfg: dict) -> list[str]:
    """Inserta las fotos reales en posiciones fijas de la secuencia."""
    if not fotos:
        return ilustraciones

    secuencia = list(ilustraciones)
    posiciones = cfg["fotos_reales_posiciones"]

    # De atrás hacia adelante para que los índices ya calculados no se corran
    for foto, frac in sorted(
        zip(fotos, posiciones), key=lambda par: par[1], reverse=True
    ):
        idx = max(1, min(len(secuencia), round(len(ilustraciones) * frac)))
        secuencia.insert(idx, foto)

    return secuencia


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


# Encuadres para los sub-planos: (centro_y, escala).
#   centro_y → 0.0 = arriba de la imagen, 1.0 = abajo
#   escala   → 1.0 = imagen completa, menor = más cerrado (más zoom)
# El centro X se deja fijo: las imágenes ya vienen en 9:16 y descentrarlas
# horizontalmente rompe la composición más de lo que aporta.
ENCUADRES = [
    (0.50, 1.00),   # completo, centrado
    (0.35, 0.88),   # cerrado sobre el tercio superior (suele estar la cara)
    (0.50, 0.88),   # cerrado al centro
    (0.65, 0.88),   # cerrado sobre el tercio inferior
    (0.42, 0.94),   # medio, ligeramente alto
]


def repartir_planos(n_images: int, total_duration: float, cfg: dict) -> list[int]:
    """Decide cuántos sub-planos recibe cada imagen para acercarse al ritmo objetivo.

    Se calcula sobre la duración real del audio y la cantidad real de imágenes
    (que varía: las fotos reales suman a la secuencia). Con un número fijo, un
    guion corto + fotos reales daba cortes de 0.9s.
    """
    override = cfg.get("planos_por_imagen")
    if override:
        return [max(1, int(override))] * n_images

    objetivo = cfg.get("duracion_plano_objetivo", 1.8)
    total_planos = max(n_images, round(total_duration / objetivo))

    base, resto = divmod(total_planos, n_images)
    # Las imágenes que reciben el plano extra se reparten a lo largo de la
    # secuencia, no todas al principio.
    reparto = [base] * n_images
    for j in range(resto):
        reparto[round(j * n_images / resto) % n_images] += 1

    return reparto


def crear_planos_de_imagen(img_path: str, idx: int, n_planos: int,
                           dur_plano: float, cfg: dict) -> list:
    """Parte UNA imagen en varios planos con encuadre y movimiento distintos.

    Multiplica los cortes sin generar más imágenes: 8 imágenes × 3 planos = 24
    cortes. El ojo lee cada cambio de encuadre como un corte de cámara nuevo.
    """
    target_w, target_h = cfg["video_width"], cfg["video_height"]
    crossfade = cfg["crossfade_duration"]
    escala_min = cfg["recorte_escala_min"]

    planos = []
    for k in range(n_planos):
        cy, escala = ENCUADRES[(idx * 2 + k) % len(ENCUADRES)]
        escala = max(escala, escala_min)

        clip = (
            ImageClip(img_path)
            .set_duration(dur_plano + crossfade)   # extra para solapar el crossfade
            .resize(height=int(target_h / escala))
        )

        # Si el ancho resultante es menor al objetivo, escalar por ancho
        if clip.size[0] < target_w:
            clip = clip.resize(width=target_w)

        # Recorte al encuadre elegido, acotado para no salirse de la imagen
        y_centro = clip.size[1] * cy
        y_centro = min(max(y_centro, target_h / 2), clip.size[1] - target_h / 2)

        clip = clip.crop(
            x_center=clip.size[0] / 2,
            y_center=y_centro,
            width=target_w,
            height=target_h,
        )

        # Zoom alternando dirección para que dos planos seguidos no se parezcan
        zoom = random.uniform(cfg["zoom_min"], cfg["zoom_max"])
        if (idx + k) % 2 == 0:
            clip = add_smooth_zoom(clip, zoom_factor=zoom)
        else:
            clip = add_smooth_zoom(clip, zoom_factor=1.0 / zoom + (zoom - 1))

        planos.append(clip)

    return planos


def create_video(image_paths: list[str], audio_path: str, cfg: dict):
    """
    Construye el video principal:
    - Parte cada imagen en varios planos (ver crear_planos_de_imagen)
    - Aplica zoom suave con easing
    - Agrega crossfade entre planos para transiciones fluidas
    - Sincroniza con el audio de narración
    """
    audio = AudioFileClip(audio_path)
    total_duration = audio.duration
    n_images = len(image_paths)
    target_w = cfg["video_width"]
    target_h = cfg["video_height"]
    crossfade = cfg["crossfade_duration"]

    planos_por_img = repartir_planos(n_images, total_duration, cfg)
    total_planos = sum(planos_por_img)
    dur_plano = total_duration / total_planos

    print(f"🎬  Creando video: {n_images} imágenes → {total_planos} cortes × "
          f"{dur_plano:.2f}s = {total_duration:.2f}s total")
    if dur_plano > 3.0:
        print(f"⚠️   {dur_plano:.1f}s por corte es lento para vertical "
              f"(el rango que retiene es 1.5-2.5s)")

    clips = []
    plano_global = 0
    for i, img_path in enumerate(image_paths):
        for k, clip in enumerate(
            crear_planos_de_imagen(img_path, i, planos_por_img[i], dur_plano, cfg)
        ):
            clips.append(clip.set_start(plano_global * dur_plano))
            plano_global += 1

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
# 🎭  OVERLAYS RGBA → CLIP CON TRANSPARENCIA
# ══════════════════════════════════════════════════════════════

def rgba_a_clip(make_frame, duration: float, fps: int) -> VideoClip:
    """Convierte una función que devuelve frames RGBA en un clip con transparencia.

    ⚠️ OJO CON to_mask(): en moviepy 1.0.3 la firma es `to_mask(self, canal=0)` y
    el canal 0 es el ROJO, no el alfa:

        newclip = self.fl_image(lambda pic: 1.0 * pic[:, :, canal] / 255)

    Con el default (canal=0) la transparencia la gobierna el rojo del texto, así que
    el contorno negro (0,0,0,255) queda con alfa 0 y NO SE DIBUJA NUNCA, y un fondo
    (193,89,57) con alfa 10 se ve al 76% de opacidad. Hay que pedir canal=3.
    """
    clip_rgba = VideoClip(make_frame, duration=duration)
    mask      = clip_rgba.to_mask(canal=3)                      # 3 = alfa
    clip_rgb  = clip_rgba.fl_image(lambda im: im[:, :, :3])
    return clip_rgb.set_mask(mask).set_fps(fps)


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

    # Antes de la primera palabra no hay nada que mostrar: si no, el primer par
    # queda congelado en pantalla durante el silencio inicial del audio.
    if t < words[0]["start"] - 0.15:
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


# Cache de fuentes por tamaño: ImageFont.truetype() en cada frame de un video
# de 1200 frames es caro y siempre devuelve lo mismo.
_FUENTES: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def cargar_fuente(ruta: str, size: int) -> ImageFont.FreeTypeFont:
    clave = (ruta, size)
    if clave not in _FUENTES:
        try:
            _FUENTES[clave] = ImageFont.truetype(ruta, size)
        except IOError:
            _FUENTES[clave] = ImageFont.load_default()
    return _FUENTES[clave]


def fuente_que_quepa(texto: str, draw: ImageDraw.Draw, cfg: dict,
                     ancho_max: float) -> ImageFont.FreeTypeFont:
    """Baja el tamaño de fuente hasta que el texto entre en el ancho disponible.

    Sin esto, una palabra larga ("CONSTANTINOPLA" a 100px) hace que x sea
    negativo y el texto se recorte por los dos lados.
    """
    ruta = cfg["font_path"]
    for size in range(cfg["font_size"], cfg["font_size_min"] - 1, -4):
        fuente = cargar_fuente(ruta, size)
        if draw.textlength(texto, font=fuente) <= ancho_max:
            return fuente
    return cargar_fuente(ruta, cfg["font_size_min"])

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

    # Si la palabra MÁS LARGA no entra ni sola, achicar la fuente para este frame.
    # Con la fuente fija, una palabra larga se recortaba por los dos lados.
    palabra_mas_larga = max(words_text, key=lambda w: draw.textlength(w, font=font))
    if draw.textlength(palabra_mas_larga, font=font) > max_width:
        font = fuente_que_quepa(palabra_mas_larga, draw, cfg, max_width)

    total_width = get_text_total_width(words_text, draw, font)

    bg_mode = cfg.get("subtitle_bg_mode", "none")
    bg_color = cfg.get("subtitle_bg_color", (0, 0, 0)) + (cfg.get("subtitle_bg_opacity", 0),)
    pad = cfg.get("subtitle_bg_padding", 15)

    # Tamaño efectivo: puede ser menor que cfg["font_size"] si se auto-ajustó
    alto_fuente = getattr(font, "size", cfg["font_size"])

    # Si no caben en una línea, partir en dos líneas (una palabra por línea)
    if total_width > max_width and len(words_text) == 2:
        lines = [[words_text[0], 0], [words_text[1], 1]]  # [texto, índice_original]
        line_h = alto_fuente + 10
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
        y_text = (height - alto_fuente) // 2
        x = (width - total_width) // 2

        # Dibujar fondo para 1 línea
        if bg_mode == "full":
            draw.rectangle([0, 0, width, height], fill=bg_color)
        elif bg_mode == "text":
            draw.rectangle([x - pad, y_text - pad, x + total_width + pad, y_text + alto_fuente + pad], fill=bg_color)

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

    subtitle_clip = rgba_a_clip(make_frame, duration, cfg.get("fps", 30))
    return subtitle_clip.set_position(("center", y_pos))


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

        return np.array(img)

    clip = rgba_a_clip(make_frame, duration, cfg.get("fps", 30))
    return clip.set_position(cfg.get("title_position", ("center", 0)))

def crear_barra_progreso(video_size: tuple, duration: float, cfg: dict) -> VideoClip:
    """Barra fina que se llena a lo largo del video.

    Le dice al espectador "esto es corto, aguanta" sin ocupar espacio útil.
    Es de las intervenciones con mejor relación esfuerzo/retención en vertical.
    """
    width = video_size[0]
    alto = cfg["barra_altura"]
    color = tuple(cfg["barra_color"]) + (255,)
    carril = (255, 255, 255, cfg["barra_fondo_alpha"])

    def make_frame(t):
        img = Image.new("RGBA", (width, alto), carril)
        avance = int(width * min(t / duration, 1.0))
        if avance > 0:
            ImageDraw.Draw(img).rectangle([0, 0, avance, alto], fill=color)
        return np.array(img)

    clip = rgba_a_clip(make_frame, duration, cfg.get("fps", 30))
    return clip.set_position(("center", cfg["barra_y"]))


def exportar_srt(words: list[dict], destino: str, palabras_por_linea: int = 6) -> None:
    """Escribe un .srt a partir de los timestamps por palabra de Whisper.

    YouTube indexa el contenido hablado del .srt → mejora la búsqueda.
    Los timestamps ya los tenemos, así que sale gratis.
    """
    def ts(segundos: float) -> str:
        h = int(segundos // 3600)
        m = int(segundos % 3600 // 60)
        s = segundos % 60
        return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")

    with open(destino, "w", encoding="utf-8") as f:
        for n, i in enumerate(range(0, len(words), palabras_por_linea), start=1):
            grupo = words[i:i + palabras_por_linea]
            f.write(f"{n}\n")
            f.write(f"{ts(grupo[0]['start'])} --> {ts(grupo[-1]['end'])}\n")
            f.write(" ".join(w["word"] for w in grupo) + "\n\n")

    print(f"📄  Subtítulos exportados: '{destino}'")


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
        return np.array(img)

    clip = rgba_a_clip(make_frame, duration, cfg.get("fps", 30))

    # A 0.82 el CTA caía debajo de la UI de Reels (~420px) y TikTok (~480px).
    # cta_y_ratio lo sube a la zona segura de las tres plataformas.
    return clip.set_position(("center", int(height * cfg["cta_y_ratio"])))


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

    # Intercalar fotos reales del paso 05 (credibilidad + contraste visual)
    if cfg.get("usar_fotos_reales") and cfg.get("fotos_reales_max", 0) > 0:
        images = intercalar_fotos_reales(images, preparar_fotos_reales(cfg), cfg)

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

    if not words:
        raise SystemExit(
            "❌ Whisper no transcribió ni una palabra — ¿voice.mp3 está vacío o corrupto?"
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

    tamano = (cfg["video_width"], cfg["video_height"])

    # El título ya no dura todo el video: aparece al inicio y se va con fade.
    # Antes se quedaba los 40s y, como suele resumir el desenlace, spoileaba
    # la historia desde el frame 0.
    title_duration = min(cfg["title_duration"], video.duration)
    title_clip = create_title_clip(
        cfg["video_title"], video_size=tamano, duration=title_duration, cfg=cfg
    ).crossfadeout(cfg["title_fadeout"])

    # El CTA va ENCIMA de la última frase, no después: 3 segundos de colchón al
    # final hundían el % de retención justo donde más se mide, y además cortaban
    # el bucle (el video que vuelve a empezar suma reproducción).
    cta_duration = min(cfg["cta_duration"], video.duration)
    cta_clip = create_cta_clip(
        cfg["cta_texto"], video_size=tamano, duration=cta_duration, cfg=cfg
    ).set_start(video.duration - cta_duration).crossfadein(0.3)

    capas = [video, subtitle_clip, title_clip, cta_clip]

    if cfg.get("barra_progreso"):
        capas.append(crear_barra_progreso(tamano, video.duration, cfg))

    final = CompositeVideoClip(capas, size=tamano).set_duration(video.duration)

    # 🧪 MODO PRUEBA — comenta esta línea para producción
    #final = final.subclip(0, 3)  # solo primeros 3 segundos

    # ── Paso 6: Exportar ──────────────────────────────────────
    export_video(final, cfg)

    # -- Copiar audio e imagenes_IA a proyectos ---

    dir_proyecto = f"proyectos/{cfg['video_name']}/"
    os.makedirs(dir_proyecto, exist_ok=True)

    shutil.copy(cfg['audio_file'], f"{dir_proyecto}{cfg['video_name']}.mp3")

    # Subtítulos para subir a YouTube / Meta (mejoran la indexación)
    if cfg.get("exportar_srt"):
        exportar_srt(
            words,
            f"{dir_proyecto}{cfg['video_name']}.srt",
            cfg.get("srt_palabras_por_linea", 6),
        )

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