import os
import re
import requests
import time
import argparse
from dotenv import load_dotenv

load_dotenv()

META_TOKEN    = os.getenv("META_ACCESS_TOKEN")
FB_PAGE_ID    = os.getenv("FACEBOOK_PAGE_ID")
IG_ACCOUNT_ID = os.getenv("INSTAGRAM_ACCOUNT_ID")
THREADS_USER_ID = os.getenv("THREADS_USER_ID")

API_VERSION      = "v21.0"
SOCIAL_POSTS_DIR = "social_posts"
CAROUSEL_DIR     = "carousel_slides"
IMAGES_DIR       = "post_images"


# ─── Leer archivos ───────────────────────────────────────

def read_post(filename: str) -> str:
    path = os.path.join(SOCIAL_POSTS_DIR, filename)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    lines = [l for l in content.split("\n") if not l.startswith("===")]
    return "\n".join(lines).strip()

def clean_text(text: str) -> str:
    text = re.sub(r'\[(?:IMAGEN|SLIDE \d+)[^\]]*\]', '', text)
    text = re.sub(r'(?im)^(Texto:|Imagen:).*$', '', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()

def extract_hashtags(ig_file: str) -> str:
    """Extrae solo el bloque de hashtags de 03_instagram.txt"""
    content = read_post(ig_file)
    match = re.search(r'(#\w+[\s#\w]*)', content, re.DOTALL)
    return match.group(1).strip() if match else ""

def get_images(folder: str, prefix: str = None) -> list:
    extensions = (".jpg", ".jpeg", ".png")
    files = sorted([
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.lower().endswith(extensions)
        and (prefix is None or f.startswith(prefix))
    ])
    return files


# ─── Facebook ────────────────────────────────────────────

def publish_facebook_post(text: str, image_paths: list = None):
    base = f"https://graph.facebook.com/{API_VERSION}/{FB_PAGE_ID}"
    clean = clean_text(text)

    if not image_paths:
        res = requests.post(f"{base}/feed", data={
            "message": clean, "access_token": META_TOKEN
        })
    elif len(image_paths) == 1:
        with open(image_paths[0], "rb") as f:
            res = requests.post(f"{base}/photos", data={
                "caption": clean, "access_token": META_TOKEN
            }, files={"source": f})
    else:
        media_ids = []
        for img_path in image_paths:
            with open(img_path, "rb") as f:
                r = requests.post(f"{base}/photos", data={
                    "published": "false", "access_token": META_TOKEN
                }, files={"source": f})
            media_ids.append(r.json()["id"])
        res = requests.post(f"{base}/feed", json={
            "message": clean,
            "attached_media": [{"media_fbid": mid} for mid in media_ids],
            "access_token": META_TOKEN
        })

    data = res.json()
    print(f"✅ Facebook post: {data['id']}" if "id" in data else f"❌ Facebook: {data}")
    return data

def publish_facebook_video(video_path: str, text: str):
    base = f"https://graph.facebook.com/{API_VERSION}/{FB_PAGE_ID}/videos"
    clean = clean_text(text)
    with open(video_path, "rb") as f:
        res = requests.post(base, data={
            "description": clean, "access_token": META_TOKEN
        }, files={"source": f})
    data = res.json()
    print(f"✅ Facebook video: {data['id']}" if "id" in data else f"❌ Facebook video: {data}")
    return data


# ─── Instagram ───────────────────────────────────────────

def publish_instagram_carousel(image_paths: list, caption: str):
    base = f"https://graph.facebook.com/{API_VERSION}/{IG_ACCOUNT_ID}"
    pub_url = f"{base}/media_publish"

    if len(image_paths) == 1:
        with open(image_paths[0], "rb") as f:
            r = requests.post(f"{base}/media", data={
                "caption": caption, "access_token": META_TOKEN
            }, files={"image": f})
        media_id = r.json().get("id")
    else:
        item_ids = []
        for img_path in image_paths:
            with open(img_path, "rb") as f:
                r = requests.post(f"{base}/media", data={
                    "is_carousel_item": "true", "access_token": META_TOKEN
                }, files={"image": f})
            item_ids.append(r.json().get("id"))

        r2 = requests.post(f"{base}/media", data={
            "media_type": "CAROUSEL",
            "children": ",".join(item_ids),
            "caption": caption,
            "access_token": META_TOKEN
        })
        media_id = r2.json().get("id")

    if not media_id:
        print(f"❌ Instagram error creando media")
        return

    res = requests.post(pub_url, data={
        "creation_id": media_id, "access_token": META_TOKEN
    })
    data = res.json()
    print(f"✅ Instagram carrusel: {data['id']}" if "id" in data else f"❌ Instagram: {data}")
    return data

def publish_instagram_video(video_path: str, caption: str):
    base = f"https://graph.facebook.com/{API_VERSION}/{IG_ACCOUNT_ID}"
    with open(video_path, "rb") as f:
        r = requests.post(f"{base}/media", data={
            "media_type": "REELS",
            "caption": caption,
            "access_token": META_TOKEN
        }, files={"video": f})
    media_id = r.json().get("id")
    if not media_id:
        print(f"❌ Instagram video error: {r.json()}")
        return

    # Esperar a que procese
    print("⏳ Esperando procesamiento de video...")
    for _ in range(20):
        time.sleep(10)
        status = requests.get(f"{base}/media/{media_id}", params={
            "fields": "status_code", "access_token": META_TOKEN
        }).json()
        if status.get("status_code") == "FINISHED":
            break

    res = requests.post(f"{base}/media_publish", data={
        "creation_id": media_id, "access_token": META_TOKEN
    })
    data = res.json()
    print(f"✅ Instagram reel: {data['id']}" if "id" in data else f"❌ Instagram reel: {data}")
    return data


# ─── Threads ─────────────────────────────────────────────

def publish_threads(text: str, image_path: str = None):
    clean = clean_text(text)
    create_url = f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads"

    params = {"text": clean, "access_token": META_TOKEN}
    if image_path:
        with open(image_path, "rb") as f:
            res = requests.post(create_url, data={
                **params, "media_type": "IMAGE"
            }, files={"image": f})
    else:
        params["media_type"] = "TEXT"
        res = requests.post(create_url, data=params)

    container_id = res.json().get("id")
    if not container_id:
        print(f"❌ Threads error: {res.json()}")
        return

    print("⏳ Esperando Threads (30s)...")
    time.sleep(30)

    pub = requests.post(
        f"https://graph.threads.net/v1.0/{THREADS_USER_ID}/threads_publish",
        data={"creation_id": container_id, "access_token": META_TOKEN}
    )
    data = pub.json()
    print(f"✅ Threads: {data['id']}" if "id" in data else f"❌ Threads: {data}")
    return data


# ─── Main ────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["post", "video"], default="post",
                        help="post = carrusel de imágenes | video = reel/video corto")
    parser.add_argument("--video", default="final_video.mp4",
                        help="Ruta al video (solo en modo video)")
    parser.add_argument("--platforms", nargs="+",
                        choices=["instagram", "facebook", "threads"],
                        default=["instagram", "facebook", "threads"],
                        help="Plataformas donde publicar")
    args = parser.parse_args()

    print(f"📱 Modo: {args.mode} | Plataformas: {', '.join(args.platforms)}\n")

    # Textos
    fb_text      = read_post("04_facebook.txt")
    threads_text = read_post("02_threads.txt")
    investigacion = read_post("00_investigacion.txt")
    hashtags      = extract_hashtags("03_instagram.txt")
    ig_caption    = f"{clean_text(investigacion)}\n\n{hashtags}"

    if args.mode == "post":
        carousel_images = get_images(CAROUSEL_DIR)
        all_images      = get_images(IMAGES_DIR)

        if "instagram" in args.platforms:
            print("── Instagram carrusel ──")
            publish_instagram_carousel(carousel_images, ig_caption)

        if "facebook" in args.platforms:
            print("\n── Facebook post ──")
            publish_facebook_post(fb_text, all_images[:2])

        if "threads" in args.platforms:
            print("\n── Threads ──")
            th_img = all_images[0] if all_images else None
            publish_threads(threads_text, th_img)

    elif args.mode == "video":
        if not os.path.exists(args.video):
            print(f"❌ Video no encontrado: {args.video}")
            return

        if "instagram" in args.platforms:
            print("── Instagram reel ──")
            publish_instagram_video(args.video, ig_caption)

        if "facebook" in args.platforms:
            print("\n── Facebook video ──")
            publish_facebook_video(args.video, fb_text)

        if "threads" in args.platforms:
            print("\n── Threads (video no soportado, publicando texto) ──")
            publish_threads(threads_text)

if __name__ == "__main__":
    main()