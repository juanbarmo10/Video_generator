#!/bin/bash

source /home/juanb/miniforge3/etc/profile.d/conda.sh
conda activate ai_video_bot

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

while IFS=',' read -r PROYECTO TEMA || [[ -n "$PROYECTO" ]]; do
    # Saltar líneas vacías o incompletas: correr el pipeline con estas variables
    # vacías es lo que creaba 'proyectos//social_posts' y 'video_None.mp4'
    if [[ -z "${PROYECTO// /}" || -z "${TEMA// /}" ]]; then
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

    if bash run_pipeline.sh >> "$LOG_FILE" 2>&1; then
        echo "    ✅ Completado"
        SUCCESS=$((SUCCESS + 1))
    else
        FAILED_STEP=$(grep -oP "(?<=Running: ).*" "$LOG_FILE" | tail -1)
        echo "    ❌ FALLÓ en: ${FAILED_STEP:-paso desconocido} — ver $LOG_FILE"
        echo "$PROYECTO,$TEMA" >> "$FAILED_FILE"
        FAILED=$((FAILED + 1))
    fi

done < <(tail -n +2 "$TEMAS_FILE")

echo ""
echo "============================================"
echo "📊 Resumen:"
echo "   ✅ Exitosos : $SUCCESS"
echo "   ❌ Fallidos : $FAILED"
echo "   📁 Logs     : $LOG_DIR/"
[[ $FAILED -gt 0 ]] && echo "   ⚠️  Fallos guardados en: $FAILED_FILE"
echo "============================================"