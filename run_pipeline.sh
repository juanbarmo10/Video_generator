#!/bin/bash

# Re-ejecutar con bash si se invocó con `sh`: en Ubuntu /bin/sh es dash, que no
# tiene `source` ni `[[ ]]`. Debe ser POSIX puro y estar antes de todo lo demás.
if [ -z "$BASH_VERSION" ]; then
    exec bash "$0" "$@"
fi

CONDA_SH="/home/juanb/miniforge3/etc/profile.d/conda.sh"
if [[ ! -f "$CONDA_SH" ]]; then
    echo "❌ No encuentro conda en '$CONDA_SH'." >&2
    exit 1
fi
source "$CONDA_SH"

set -e  # Detener si cualquier comando falla

# PROYECTO y TEMA vienen del entorno (seteados por run_all.sh)
# o desde .env si se corre standalone
if [[ -z "$PROYECTO" || -z "$TEMA" ]]; then
    source .env
    export PROYECTO TEMA
fi

# Sin estas dos variables los respaldos caen en 'proyectos//' y el video queda
# como 'video_None.mp4' — mejor abortar que ensuciar el árbol de proyectos.
if [[ -z "$PROYECTO" || -z "$TEMA" ]]; then
    echo "❌ PROYECTO y TEMA son obligatorios (por entorno o .env)" >&2
    exit 1
fi

cd /home/juanb/video_generator
conda activate ai_video_bot

run_step() {
    echo "Running: $1"
    python "$1" "${@:2}"
}

echo "🚀 Iniciando: $PROYECTO | $TEMA"

run_step 01_script_generator.py
run_step 02_social_media_generator.py
run_step 03_voice_generator.py
run_step 04_image_generator.py
run_step 05_download_images.py social_posts/images_to_download.txt
run_step 06_carrusel_generator.py --profile perfil/historia_profile.png
run_step 07_video_generator.py
run_step 08_music_mixer.py

echo "✅ Pipeline completado: $PROYECTO | $TEMA"