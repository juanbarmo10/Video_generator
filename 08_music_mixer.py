
#%%
"""
Toma el video final generado y le mezcla música de fondo royalty-free.
Uso: python music_mixer.py
"""

import os
import random
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeAudioClip
from dotenv import load_dotenv

load_dotenv()

PROYECTO = os.environ.get("PROYECTO")

if not PROYECTO:
    raise SystemExit(
        "❌ Falta PROYECTO (entorno o .env). Sin él se buscaría 'video_None.mp4'."
    )

CONFIG = {
    "video_input":    f"videos_no_music/video_{PROYECTO}.mp4",
    "video_output":   f"videos/video_{PROYECTO}.mp4",
    "music_dir":      "music/",        # carpeta con tus .mp3 royalty-free
    "music_volume":   0.1,            # volumen música (0.0 a 1.0) — voz es 1.0
    "fade_in":        2.0,             # segundos de fade in al inicio
    "fade_out":       3.0,             # segundos de fade out al final
}

def pick_music(music_dir: str) -> str:
    """Elige una canción aleatoria de la carpeta."""
    tracks = [
        f for f in os.listdir(music_dir)
        if f.lower().endswith((".mp3", ".wav", ".ogg"))
    ]
    if not tracks:
        raise FileNotFoundError(f"No hay música en '{music_dir}'")
    chosen = random.choice(tracks)
    print(f"🎵 Música elegida: {chosen}")
    return os.path.join(music_dir, chosen)

def mix_music(cfg: dict):
    print("🎬 Cargando video...")
    video = VideoFileClip(cfg["video_input"])
    duration = video.duration

    print("🎵 Cargando música...")
    music_path = pick_music(cfg["music_dir"])
    music = AudioFileClip(music_path)

    # Si la música es más corta que el video, la repetimos
    if music.duration < duration:
        loops = int(duration / music.duration) + 1
        from moviepy.audio.fx.audio_loop import audio_loop
        music = audio_loop(music, nloops=loops)

    # Recortar al largo exacto del video
    music = music.subclip(0, duration)

    # Ajustar volumen y aplicar fades
    music = (
        music
        .volumex(cfg["music_volume"])
        .audio_fadein(cfg["fade_in"])
        .audio_fadeout(cfg["fade_out"])
    )

    # Mezclar voz original + música
    voz_original = video.audio
    audio_final = CompositeAudioClip([voz_original, music])

    # Componer y exportar
    video_final = video.set_audio(audio_final)

    print(f"💾 Exportando a {cfg['video_output']}...")
    video_final.write_videofile(
        cfg["video_output"],
        codec="libx264",
        audio_codec="aac",
        preset="fast",
        logger=None
    )
    print("✅ ¡Listo!")

if __name__ == "__main__":
    mix_music(CONFIG)