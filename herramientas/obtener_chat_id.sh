source /home/juanb/miniforge3/etc/profile.d/conda.sh && conda activate ai_video_bot && python - <<'PY'
import os, json, urllib.request
from dotenv import load_dotenv
# Ruta explícita: el script llega por stdin, y load_dotenv() sin argumento
# busca el .env subiendo desde el archivo del llamador, que aquí no existe.
load_dotenv(".env")

token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
if not token:
    raise SystemExit("❌ Pon primero TELEGRAM_BOT_TOKEN en el .env")

with urllib.request.urlopen(
        f"https://api.telegram.org/bot{token}/getUpdates", timeout=20) as r:
    datos = json.load(r)

chats = {u["message"]["chat"]["id"]: u["message"]["chat"].get("first_name", "")
         for u in datos.get("result", []) if "message" in u}

if not chats:
    raise SystemExit("❌ Sin mensajes. Escríbele algo al bot y vuelve a correrlo.")

for cid, nombre in chats.items():
    print(f"✅ chat_id = {cid}   ({nombre})")
print("\nPégalo en el .env como TELEGRAM_CHAT_ID=<numero>")
PY
