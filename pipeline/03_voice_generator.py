
#%%
from dotenv import load_dotenv
import os
import subprocess
import requests

from estado import verificar_estado, registrar_elevenlabs, resumen_costo

load_dotenv()

# Aborta si script.txt es de otro tema (ver estado.py)
verificar_estado("paso 03")

# ========================================================================== #
elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY")

path_script= "script.txt"
output = "voice.mp3"

# Aceleración de la narración. ElevenLabs entrega ~143 palabras/minuto, y la
# narración que retiene en vertical va a 170-190. atempo NO altera el tono
# (no suena a ardilla) y hasta 1.15 es imperceptible.
# 1.0 = desactivado. El paso 07 transcribe el audio YA acelerado, así que los
# subtítulos siguen sincronizados solos.
VELOCIDAD = 1.10

# ========================================================================== #

if not elevenlabs_api_key:
    raise SystemExit("❌ Falta ELEVENLABS_API_KEY en el .env")

with open(path_script, "r", encoding="utf-8") as f:
    script = f.read().strip()

if not script:
    raise SystemExit(f"❌ '{path_script}' está vacío — el paso 01 no generó guion")

voice_id = "l1zE9xgNpUTaQCZzpNJa"
#voice_id = "QhRZzy7zvGun8cV3aJaM"
url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"

headers = {
    "xi-api-key": elevenlabs_api_key,
    "Content-Type": "application/json",
    "accept": "audio/mpeg"
}

data = {
    "text": script,
    "model_id": "eleven_multilingual_v2",
    "voice_settings": {
        "stability": 0.5,
        "similarity_boost": 0.75,
        "style": 0.7,
        "use_speaker_boost": True
    }
}

response = requests.post(url, json=data, headers=headers, timeout=180)

# ⚠️ Este paso DEBE abortar con código != 0 si falla.
# Antes solo imprimía el error y salía con 0: `set -e` de run_pipeline.sh no lo
# detectaba y los pasos 04/07 seguían usando el voice.mp3 del tema ANTERIOR,
# produciendo un video con la narración equivocada marcado como ✅ Completado.
if response.status_code != 200:
    raise SystemExit(
        f"❌ ElevenLabs falló ({response.status_code}): {response.text[:300]}"
    )

# Un 200 con cuerpo diminuto significa audio corrupto o truncado: también aborta,
# porque un mp3 vacío deja el voice.mp3 viejo intacto o rompe el paso 07.
MIN_BYTES = 10_000  # ~90 palabras narradas pesan ~500 KB
if len(response.content) < MIN_BYTES:
    raise SystemExit(
        f"❌ ElevenLabs devolvió {len(response.content)} bytes — audio inválido"
    )

with open(output, "wb") as f:
    f.write(response.content)

print(f"✅ Voz generada: '{output}' ({len(response.content) // 1024} KB)")
registrar_elevenlabs(len(script))


def duracion(path: str) -> float:
    salida = subprocess.check_output([
        "ffprobe", "-v", "error", "-show_entries", "format=duration",
        "-of", "default=nw=1:nk=1", path,
    ], text=True)
    return float(salida.strip())


if VELOCIDAD != 1.0:
    antes = duracion(output)
    temporal = "voice_tempo.mp3"

    resultado = subprocess.run([
        # -nostdin: sin esto ffmpeg sondea stdin buscando teclas interactivas y se
        # COME bytes del pipe con el que run_all.sh lee temas.csv. Así se perdieron
        # las primeras letras de los PROYECTO ("Historia02" → "a02").
        "ffmpeg", "-nostdin", "-y", "-loglevel", "error",
        "-i", output,
        "-filter:a", f"atempo={VELOCIDAD}",
        "-b:a", "192k",
        temporal,
    ])

    if resultado.returncode != 0:
        os.path.exists(temporal) and os.remove(temporal)
        raise SystemExit(f"❌ ffmpeg falló acelerando la voz (código {resultado.returncode})")

    os.replace(temporal, output)
    despues = duracion(output)
    palabras = len(script.split())
    print(f"⏩ Narración acelerada ×{VELOCIDAD}: {antes:.1f}s → {despues:.1f}s "
          f"({palabras / despues * 60:.0f} palabras/minuto)")



# """
# 🎙️ GENERADOR DE VOZ — Google Cloud Text-to-Speech
# Lee script.txt → genera voice.mp3
# API key desde .env — sin necesidad de service account
# """

# import os
# import json
# import base64
# import requests
# from dotenv import load_dotenv

# load_dotenv()

# # ══════════════════════════════════════════════════════════════
# # ⚙️  CONFIGURACIÓN
# # ══════════════════════════════════════════════════════════════

# CONFIG = {
#     "input_file":  "script.txt",
#     "output_file": "voice.mp3",

#     # Voces recomendadas en español — masculinas, narración:
#     #
#     # Neural2 (mejor calidad, 1M chars/mes gratis):
#     #   "es-US-Neural2-B"  → grave, neutro latinoamericano   ← prueba este primero
#     #   "es-US-Neural2-C"  → femenina
#     #   "es-ES-Neural2-B"  → masculina, acento España
#     #
#     # Wavenet (muy buena calidad, 1M chars/mes gratis):
#     #   "es-US-Wavenet-B"  → masculina, latinoamericano
#     #   "es-US-Wavenet-C"  → femenina, latinoamericano
#     #
#     # Standard (calidad básica, 4M chars/mes gratis):
#     #   "es-US-Standard-B" → masculina, latinoamericano
#     #
#     "voice_name":     "es-US-Neural2-B",
#     "language_code":  "es-US",

#     # Velocidad: 0.25 (muy lento) → 1.0 (normal) → 4.0 (muy rápido)
#     "speaking_rate": 0.95,

#     # Tono: -20.0 (muy grave) → 0.0 (normal) → 20.0 (muy agudo)
#     "pitch": -2.0,

#     # Volumen: -96.0 → 0.0 (normal) → 16.0
#     "volume_gain_db": 0.0,
# }

# # ══════════════════════════════════════════════════════════════
# # 🎙️  GENERACIÓN
# # ══════════════════════════════════════════════════════════════

# def generate_voice(cfg: dict = CONFIG):
#     api_key = os.getenv("GOOGLE_TTS_API_KEY")
#     if not api_key:
#         raise ValueError("Falta GOOGLE_TTS_API_KEY en el .env")

#     with open(cfg["input_file"], "r", encoding="utf-8") as f:
#         text = f.read().strip()

#     if not text:
#         raise ValueError(f"El archivo '{cfg['input_file']}' está vacío.")

#     print(f"📄 Script: {len(text)} caracteres")
#     print(f"🎙️  Voz: {cfg['voice_name']} | Velocidad: {cfg['speaking_rate']} | Tono: {cfg['pitch']}")

#     url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}"

#     payload = {
#         "input": {"text": text},
#         "voice": {
#             "languageCode": cfg["language_code"],
#             "name":         cfg["voice_name"],
#         },
#         "audioConfig": {
#             "audioEncoding":  "MP3",
#             "speakingRate":   cfg["speaking_rate"],
#             "pitch":          cfg["pitch"],
#             "volumeGainDb":   cfg["volume_gain_db"],
#         }
#     }

#     response = requests.post(url, json=payload)

#     if response.status_code != 200:
#         raise Exception(f"❌ Error Google TTS: {response.status_code} — {response.text}")

#     audio_base64 = response.json()["audioContent"]
#     audio_bytes  = base64.b64decode(audio_base64)

#     with open(cfg["output_file"], "wb") as f:
#         f.write(audio_bytes)

#     size_kb = os.path.getsize(cfg["output_file"]) / 1024
#     print(f"✅ Audio guardado: '{cfg['output_file']}' ({size_kb:.1f} KB)")


# # ══════════════════════════════════════════════════════════════
# # 🧪  MODO PRUEBA — compara todas las voces masculinas
# # ══════════════════════════════════════════════════════════════

# def test_all_voices(cfg: dict = CONFIG):
#     """Genera un sample con cada voz para que elijas la que más te guste."""

#     api_key = os.getenv("GOOGLE_TTS_API_KEY")

#     with open(cfg["input_file"], "r", encoding="utf-8") as f:
#         sample = f.read().strip()[:300]  # primeras 300 letras para ahorrar cuota

#     voices = [
#         ("es-US-Neural2-B",  "es-US"),  # masculina Neural2 latinoam.
#         ("es-US-Neural2-C",  "es-US"),  # femenina  Neural2 latinoam.
#         ("es-US-Wavenet-B",  "es-US"),  # masculina Wavenet latinoam.
#         ("es-US-Wavenet-C",  "es-US"),  # femenina  Wavenet latinoam.
#         ("es-ES-Neural2-B",  "es-ES"),  # masculina Neural2 España
#         ("es-US-Standard-B", "es-US"),  # masculina Standard latinoam.
#     ]

#     os.makedirs("voice_samples", exist_ok=True)
#     url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}"

#     print(f"🧪 Probando {len(voices)} voces...\n")

#     for voice_name, lang in voices:
#         payload = {
#             "input": {"text": sample},
#             "voice": {"languageCode": lang, "name": voice_name},
#             "audioConfig": {
#                 "audioEncoding": "MP3",
#                 "speakingRate":  cfg["speaking_rate"],
#                 "pitch":         cfg["pitch"],
#             }
#         }

#         r = requests.post(url, json=payload)
#         output = f"voice_samples/sample_{voice_name}.mp3"

#         if r.status_code == 200:
#             audio_bytes = base64.b64decode(r.json()["audioContent"])
#             with open(output, "wb") as f:
#                 f.write(audio_bytes)
#             print(f"   ✅ {voice_name} → {output}")
#         else:
#             print(f"   ❌ {voice_name} → Error {r.status_code}")

#     print(f"\n📁 Escucha los samples en 'voice_samples/' y elige tu favorita.")
#     print(f"   Luego actualiza CONFIG['voice_name'] con tu elección.")


# # ══════════════════════════════════════════════════════════════
# # ▶️  EJECUCIÓN
# # ══════════════════════════════════════════════════════════════

# if __name__ == "__main__":
#     import argparse

#     parser = argparse.ArgumentParser()
#     parser.add_argument(
#         "--test-voices",
#         action="store_true",
#         help="Genera samples de todas las voces disponibles para comparar"
#     )
#     args = parser.parse_args()

#     if args.test_voices:
#         test_all_voices()
#     else:
#         generate_voice()