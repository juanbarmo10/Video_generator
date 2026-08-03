
#%%
"""
Toma el video final generado y le mezcla música de fondo royalty-free.
Uso: python 08_music_mixer.py

⚠️ Este paso NO recomprime el video (-c:v copy). Antes usaba moviepy, que volvía a
codificar todo el video solo para cambiarle el audio y perdía por el camino el -crf,
el -pix_fmt, el -profile:v y el +faststart que el paso 07 sí configuraba:
    videos_no_music/  → 3 270 kbps · ftyp, moov, free, mdat
    videos/           → 2 418 kbps · ftyp, free, mdat, moov   (−26% y sin faststart)
Ahora el video pasa intacto y solo se re-codifica la pista de audio.
"""

import os
import json
import random
import subprocess
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

    # Volumen de la música. Antes 0.1: medido, la música era literalmente
    # inaudible (mean_volume idéntico con y sin ella). Con ducking activo se
    # puede subir sin tapar la voz.
    "music_volume":   0.22,            # 0.0 a 1.0 — voz es 1.0
    "fade_in":        2.0,             # segundos de fade in al inicio
    "fade_out":       3.0,             # segundos de fade out al final

    # ── Ducking (sidechain) ───────────────────────────────────
    # La música baja sola mientras habla el narrador y vuelve en los silencios.
    "ducking":            True,
    "ducking_threshold":  0.03,        # nivel de voz que dispara la bajada
    "ducking_ratio":      12,          # cuánto baja (más alto = más agresivo)
    "ducking_release":    350,         # ms que tarda en recuperar volumen

    # ── Sonoridad ─────────────────────────────────────────────
    # Redes sociales normalizan a ≈ −14 LUFS. El pipeline entregaba −20 dB,
    # que se percibe apagado al lado del siguiente video del feed.
    "lufs":           -14.0,           # objetivo de loudness integrado
    "true_peak":      -1.5,            # techo de pico real (dBTP)
    "loudness_range":  11.0,

    # ── Audio de salida ───────────────────────────────────────
    "audio_bitrate":  "192k",
    "audio_rate":     "48000",
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


def duracion(path: str) -> float:
    """Duración en segundos vía ffprobe."""
    salida = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", path,
    ], text=True)
    return float(salida.strip())


def tiene_audio(path: str) -> bool:
    """True si el archivo trae al menos una pista de audio."""
    salida = subprocess.check_output([
        "ffprobe", "-v", "error",
        "-select_streams", "a",
        "-show_entries", "stream=index",
        "-of", "json", path,
    ], text=True)
    return bool(json.loads(salida).get("streams"))


def construir_filtro(cfg: dict, dur: float) -> str:
    """Cadena de filtros: fades → ducking → mezcla → normalización."""
    fade_out_start = max(0.0, dur - cfg["fade_out"])

    # [1:a] = música (en loop infinito, recortada por -shortest)
    partes = [
        f"[1:a]volume={cfg['music_volume']},"
        f"afade=t=in:st=0:d={cfg['fade_in']},"
        f"afade=t=out:st={fade_out_start}:d={cfg['fade_out']}[bg]"
    ]

    if cfg["ducking"]:
        # sidechaincompress[main][sidechain]: comprime la música usando la voz
        # como disparador, para que baje sola cuando el narrador habla.
        partes.append(
            f"[bg][0:a]sidechaincompress="
            f"threshold={cfg['ducking_threshold']}:"
            f"ratio={cfg['ducking_ratio']}:"
            f"attack=5:release={cfg['ducking_release']}[music]"
        )
    else:
        partes.append("[bg]anull[music]")

    partes.append(
        "[0:a][music]amix=inputs=2:duration=first:dropout_transition=0[mix]"
    )
    partes.append(
        f"[mix]loudnorm=I={cfg['lufs']}:TP={cfg['true_peak']}:"
        f"LRA={cfg['loudness_range']}[out]"
    )

    return ";".join(partes)


def mix_music(cfg: dict) -> None:
    entrada = cfg["video_input"]

    if not os.path.exists(entrada):
        raise SystemExit(f"❌ No existe '{entrada}' — ¿corrió el paso 07?")
    if not tiene_audio(entrada):
        raise SystemExit(f"❌ '{entrada}' no tiene pista de audio")

    dur = duracion(entrada)
    print(f"🎬 Video: {entrada} ({dur:.2f}s)")

    musica = pick_music(cfg["music_dir"])
    filtro = construir_filtro(cfg, dur)

    os.makedirs(os.path.dirname(cfg["video_output"]), exist_ok=True)

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error", "-stats",
        "-i", entrada,
        "-stream_loop", "-1", "-i", musica,   # loopea la música hasta cubrir el video
        "-filter_complex", filtro,
        "-map", "0:v", "-map", "[out]",
        "-c:v", "copy",                       # ← el video pasa intacto, sin recomprimir
        "-c:a", "aac",
        "-b:a", cfg["audio_bitrate"],
        "-ar", cfg["audio_rate"],
        "-movflags", "+faststart",            # índice al inicio: streaming inmediato
        "-shortest",
        cfg["video_output"],
    ]

    print(f"💾 Mezclando → {cfg['video_output']} (sin recomprimir video)...")
    resultado = subprocess.run(cmd)

    if resultado.returncode != 0:
        raise SystemExit(f"❌ ffmpeg falló con código {resultado.returncode}")

    tam = os.path.getsize(cfg["video_output"]) / 1024 / 1024
    print(f"✅ ¡Listo! {cfg['video_output']} ({tam:.1f} MB) · "
          f"loudness {cfg['lufs']} LUFS · faststart activo")


if __name__ == "__main__":
    mix_music(CONFIG)
