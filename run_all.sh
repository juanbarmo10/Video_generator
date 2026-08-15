#!/bin/bash

# ── Re-ejecutar con bash si se invocó con `sh` ──────────────────────────
# En Ubuntu /bin/sh es dash, que NO tiene `source`. Con `sh run_all.sh` el
# shebang se ignora, el source de conda falla en silencio, la función `conda`
# nunca se define y `conda activate` llama al binario real, que responde
# "CondaError: Run 'conda init' before 'conda activate'".
# Este bloque debe ser POSIX puro y estar ANTES de cualquier sintaxis de bash.
if [ -z "$BASH_VERSION" ]; then
    exec bash "$0" "$@"
fi

CONDA_SH="/home/juanb/miniforge3/etc/profile.d/conda.sh"
if [[ ! -f "$CONDA_SH" ]]; then
    echo "❌ No encuentro conda en '$CONDA_SH'." >&2
    echo "   Corrige la ruta en run_all.sh o instala miniforge." >&2
    exit 1
fi

source "$CONDA_SH"
if ! conda activate ai_video_bot; then
    echo "❌ No se pudo activar el entorno 'ai_video_bot'." >&2
    echo "   Compruébalo con: conda env list" >&2
    exit 1
fi

cd /home/juanb/video_generator

TEMAS_FILE="temas.csv"
LOG_DIR="logs"
FAILED_FILE="$LOG_DIR/failed.csv"

mkdir -p "$LOG_DIR"
> "$FAILED_FILE"

sed -i 's/\r//' "$TEMAS_FILE"
# Garantiza salto de línea final SIN acumular líneas en blanco en cada corrida:
# cada línea vacía se procesaba como un tema con PROYECTO y TEMA vacíos.
[[ -n "$(tail -c 1 "$TEMAS_FILE")" ]] && echo "" >> "$TEMAS_FILE"
TOTAL=$(tail -n +2 "$TEMAS_FILE" | grep -c '.')
CURRENT=0
SUCCESS=0
FAILED=0
EXITOSOS=()      # los PROYECTO que terminaron, para empaquetar solo estos

# ── Actualiza una variable en el .env sin borrar las demás ──────────────
update_env() {
    local key="$1"
    local value="$2"
    local env_file=".env"

    if grep -q "^${key}=" "$env_file"; then
        # La variable ya existe → reemplazarla
        sed -i "s|^${key}=.*|${key}=${value}|" "$env_file"
    else
        # No existe → agregarla al final
        echo "${key}=${value}" >> "$env_file"
    fi
}
# ────────────────────────────────────────────────────────────────────────

echo "🗂️  $TOTAL temas encontrados. Iniciando..."
echo "============================================"

# ⚠️  El CSV se lee por el descriptor 9, NO por stdin.
# Con stdin, cualquier proceso hijo que lea de ahí se COME bytes de la lista de
# temas. ffmpeg (pasos 03 y 08) sondea stdin buscando teclas interactivas, y así
# se perdieron las primeras letras de casi todos los PROYECTO de un lote entero:
# "Historia02" → "a02", "Historia04" → "04", "Historia07" → "oria07".
# El descriptor 9 es inalcanzable para los hijos; el </dev/null de abajo es el
# segundo cinturón.
while IFS=',' read -r PROYECTO TEMA EXTRA <&9 || [[ -n "$PROYECTO" ]]; do
    # Saltar líneas vacías o incompletas: correr el pipeline con estas variables
    # vacías es lo que creaba 'proyectos//social_posts' y 'video_None.mp4'
    if [[ -z "${PROYECTO// /}" || -z "${TEMA// /}" ]]; then
        continue
    fi

    # Encabezado repetido: `tail -n +2` salta solo la PRIMERA línea, así que un
    # segundo "PROYECTO,TEMA" pegado por error se procesaba como tema real y
    # generaba un video sobre "TEMA" en proyectos/PROYECTO/.
    if [[ "${PROYECTO^^}" == "PROYECTO" && "${TEMA^^}" == "TEMA" ]]; then
        echo "ℹ️  Encabezado repetido en la línea $((CURRENT + 2)) — se salta"
        continue
    fi

    # Una coma de más (p. ej. "Mundial11,Maradona,") metía todos los campos
    # sobrantes en $TEMA, que quedaba como "Maradona," y ensuciaba el guion.
    # Capturar $EXTRA aparte permite detectarlo en vez de tragárselo.
    if [[ -n "${EXTRA// /}" ]]; then
        echo "❌ Fila malformada (más de 2 campos): '$PROYECTO,$TEMA,$EXTRA'" >&2
        echo "   El formato es PROYECTO,TEMA — quita la coma sobrante." >&2
        echo "$PROYECTO,$TEMA" >> "$FAILED_FILE"
        FAILED=$((FAILED + 1))
        continue
    fi

    CURRENT=$((CURRENT + 1))
    TIMESTAMP=$(date '+%Y-%m-%d %H:%M:%S')
    LOG_FILE="$LOG_DIR/${PROYECTO}_${TEMA// /_}.log"

    echo ""
    echo "[$CURRENT/$TOTAL] 🚀 $PROYECTO | $TEMA"
    echo "    📄 Log: $LOG_FILE"

    # ── Actualizar .env antes de correr el pipeline ──────────────────
    update_env "PROYECTO" "$PROYECTO"
    update_env "TEMA" "$TEMA"
    echo "    📝 .env actualizado"
    # ────────────────────────────────────────────────────────────────

    export PROYECTO TEMA

    if bash run_pipeline.sh </dev/null >> "$LOG_FILE" 2>&1; then
        echo "    ✅ Completado"
        SUCCESS=$((SUCCESS + 1))
        EXITOSOS+=("$PROYECTO")
    else
        FAILED_STEP=$(grep -oP "(?<=Running: ).*" "$LOG_FILE" | tail -1)
        echo "    ❌ FALLÓ en: ${FAILED_STEP:-paso desconocido} — ver $LOG_FILE"
        echo "$PROYECTO,$TEMA" >> "$FAILED_FILE"
        FAILED=$((FAILED + 1))
    fi

done 9< <(tail -n +2 "$TEMAS_FILE")

echo ""
echo "============================================"
echo "📊 Resumen:"
echo "   ✅ Exitosos : $SUCCESS"
echo "   ❌ Fallidos : $FAILED"
echo "   📁 Logs     : $LOG_DIR/"
[[ $FAILED -gt 0 ]] && echo "   ⚠️  Fallos guardados en: $FAILED_FILE"
echo "============================================"

# ── Paquete de publicación ──────────────────────────────────────────────
# El paso 09 no es del pipeline por tema: se corre UNA vez al final y junta
# video + srt + descripcion.txt + carrusel en publicar/<TEMA>/.
# ⚠️ Se le pasan los PROYECTO de ESTE lote con --solo: sin eso empaqueta todo
# lo que haya en videos/, incluidos los lotes viejos.
if [[ ${#EXITOSOS[@]} -gt 0 ]]; then
    echo ""
    echo "📦 Armando el paquete de publicación..."
    if python 09_paquete_publicacion.py --solo "${EXITOSOS[@]}"; then
        echo ""
        echo "🏁 Listo para programar: publicar/ + publicar/calendario.csv"
    else
        echo "⚠️  El paquete falló, pero los videos están en videos/." >&2
        echo "   Puedes rehacerlo con: python 09_paquete_publicacion.py --solo ${EXITOSOS[*]}" >&2
    fi
else
    echo ""
    echo "⏭️  Ningún tema terminó: no hay nada que empaquetar."
fi