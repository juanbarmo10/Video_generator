#%%

# import edge_tts
# import asyncio
# from dotenv import load_dotenv
# import nest_asyncio

# path_script = "script.txt"
# output = "voice.mp3"

# with open(path_script, "r", encoding="utf-8") as f:
#     script = f.read()

# async def generate():
#     communicate = edge_tts.Communicate(
#         script,
#         voice="es-MX-JorgeNeural",
#         rate="+25%",    # Velocidad: -50% (lento) a +50% (rápido)
#         volume="+20%",   # Volumen: -50% a +50%
#         pitch="+0Hz"    # Tono: -50Hz (más grave) a +50Hz (más agudo)
#     )
#     await communicate.save(output)
#     print(f"✅ Audio guardado: {output}")

# # Compatible con Jupyter y scripts normales
# try:
#     loop = asyncio.get_event_loop()
#     if loop.is_running():
#         nest_asyncio.apply()
#         loop.run_until_complete(generate())
#     else:
#         loop.run_until_complete(generate())
# except RuntimeError:
#     asyncio.run(generate())

#%%
"""
╔══════════════════════════════════════════════════════════════╗
║         🎙️  GENERADOR DE VOZ — OpenAI TTS                    ║
║         Lee script.txt → genera voice.mp3                    ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# ══════════════════════════════════════════════════════════════
# ⚙️  CONFIGURACIÓN
# ══════════════════════════════════════════════════════════════

CONFIG = {
    "input_file":  "script.txt",   # archivo con el texto a narrar
    "output_file": "voice.mp3",    # archivo de salida

    # Modelo:
    #   "tts-1"    → más rápido, menor calidad
    #   "tts-1-hd" → más lento, mayor calidad (recomendado)
    "model": "tts-1-hd",

    # Voz:
    #   "onyx"  → grave, narrativa, autoritaria  ← mejor para historia
    #   "echo"  → media, clara, profesional
    #   "fable" → expresiva, cálida
    #   "alloy" → neutra, equilibrada
    #   "nova"  → femenina, clara
    #   "shimmer" → femenina, suave
    "voice": "onyx",

    # Velocidad: 0.25 (muy lento) → 1.0 (normal) → 4.0 (muy rápido)
    # 0.92-0.96 da un tono más dramático y pausado, ideal para narración
    "speed": 0.94,

    # Formato de salida: mp3, opus, aac, flac, wav, pcm
    "format": "mp3",
}

# ══════════════════════════════════════════════════════════════
# 🎙️  GENERACIÓN
# ══════════════════════════════════════════════════════════════

def generate_voice(cfg: dict = CONFIG):
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    # Leer script
    with open(cfg["input_file"], "r", encoding="utf-8") as f:
        text = f.read().strip()

    if not text:
        raise ValueError(f"El archivo '{cfg['input_file']}' está vacío.")

    chars = len(text)
    cost  = (chars / 1000) * 0.030  # tts-1-hd: $0.030 por 1K caracteres
    print(f"📄 Script cargado: {chars} caracteres | Costo estimado: ${cost:.4f}")
    print(f"🎙️  Generando voz con modelo '{cfg['model']}' — voz '{cfg['voice']}'...")

    response = client.audio.speech.create(
        model=cfg["model"],
        voice=cfg["voice"],
        input=text,
        speed=cfg["speed"],
        response_format=cfg["format"],
    )

    response.stream_to_file(cfg["output_file"])

    size_kb = os.path.getsize(cfg["output_file"]) / 1024
    print(f"✅ Audio guardado: '{cfg['output_file']}' ({size_kb:.1f} KB)")


# ══════════════════════════════════════════════════════════════
# 🧪  MODO PRUEBA — compara las voces disponibles
# ══════════════════════════════════════════════════════════════

def test_all_voices(sample_text: str = None, cfg: dict = CONFIG):
    """
    Genera un archivo de audio por cada voz disponible
    usando las primeras 300 letras del script (para ahorrar costo).
    Útil para elegir la voz que más te guste.
    """
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

    if sample_text is None:
        with open(cfg["input_file"], "r", encoding="utf-8") as f:
            sample_text = f.read().strip()[:300]  # solo primeras 300 letras

    voices = ["onyx", "echo", "fable", "alloy", "nova", "shimmer"]

    print(f"🧪 Probando {len(voices)} voces con '{cfg['model']}'...")
    print(f"   Texto de muestra ({len(sample_text)} chars): {sample_text[:80]}...\n")

    os.makedirs("voice_samples", exist_ok=True)

    for voice in voices:
        output = f"voice_samples/sample_{voice}.mp3"
        print(f"   🎙️  Generando: {voice}...", end=" ")

        response = client.audio.speech.create(
            model=cfg["model"],
            voice=voice,
            input=sample_text,
            speed=cfg["speed"],
            response_format=cfg["format"],
        )
        response.stream_to_file(output)
        print(f"✅ {output}")

    print(f"\n📁 Muestras guardadas en 'voice_samples/'")
    print(f"   Escúchalas y elige la que más te guste.")
    print(f"   Luego actualiza CONFIG['voice'] con tu elección.")


# ══════════════════════════════════════════════════════════════
# ▶️  EJECUCIÓN
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generador de voz con OpenAI TTS")
    parser.add_argument(
        "--test-voices",
        action="store_true",
        help="Genera una muestra de audio con cada voz disponible para comparar"
    )
    args = parser.parse_args()

    if args.test_voices:
        # Modo prueba: genera samples de todas las voces
        # Uso: python voice_generator.py --test-voices
        test_all_voices()
    else:
        # Modo normal: genera el voice.mp3 del script completo
        # Uso: python voice_generator.py
        generate_voice()