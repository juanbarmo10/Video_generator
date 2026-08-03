
#%%

"""
download_images.py
Parses an image list file and downloads the best matching free image
from Wikimedia Commons for each entry.

Usage:
    python download_images.py images_to_download.txt
    python download_images.py images_to_download.txt --out my_folder
"""

import re
import sys
import time
import argparse
from pathlib import Path
import requests
from ddgs import DDGS
from PIL import Image
import io

# ── Config ────────────────────────────────────────────────────────────────────
COMMONS_API = "https://commons.wikimedia.org/w/api.php"
OPENVERSE_API = "https://api.openverse.org/v1/images/"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; ImageBot/1.0"}
DOWNLOAD_HEADERS = {**HEADERS, "Referer": "https://commons.wikimedia.org/"}
DELAY = 7.0          # seconds between requests (be polite)
THUMB_WIDTH = 1200   # px – request a reasonably large thumbnail
# ─────────────────────────────────────────────────────────────────────────────



def parse_image_list(filepath: str) -> list[tuple[str, str]]:
    """Return [(filename, description), …] from the txt file."""
    pattern = re.compile(r"^(img_\d+\.jpg)\s*→\s*(.+)$")
    entries = []
    with open(filepath, encoding="utf-8") as f:
        for line in f:
            m = pattern.match(line.strip())
            if m:
                entries.append((m.group(1), m.group(2).strip()))
    return entries


def build_query(description: str) -> str:
    """El LLM ya genera queries optimizadas — solo limpiar caracteres raros."""
    query = re.sub(r"[\"',()\[\]]", " ", description)
    return re.sub(r"\s+", " ", query).strip()

def search_commons(query: str) -> list[dict]:
    """Search Wikimedia Commons and return up to 5 candidate file names."""
    params = {
        "action": "query",
        "list": "search",
        "srsearch": query,
        "srnamespace": 6,
        "srlimit": 5,
        "format": "json",
    }
    for attempt in range(4):
        r = requests.get(COMMONS_API, params=params, headers=HEADERS, timeout=15)
        if r.status_code == 429:
            wait = 10 * (attempt + 1)
            print(f"    Rate limited, esperando {wait}s…")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return r.json().get("query", {}).get("search", [])
    return []


def get_image_url(page_title: str) -> str | None:
    params = {
        "action": "query",
        "titles": page_title,
        "prop": "imageinfo",
        "iiprop": "url|mime",
        "format": "json",
    }
    for attempt in range(4):
        r = requests.get(COMMONS_API, params=params, headers=HEADERS, timeout=15)
        if r.status_code == 429:
            wait = 10 * (attempt + 1)
            print(f"    Rate limited, esperando {wait}s…")
            time.sleep(wait)
            continue
        r.raise_for_status()
        pages = r.json().get("query", {}).get("pages", {})
        for page in pages.values():
            info = page.get("imageinfo", [{}])[0]
            mime = info.get("mime", "")
            if mime.startswith("image/") and "svg" not in mime:
                url = info.get("url", "")
                # Eliminar UTM params que causan 403
                return url.split("?")[0]
        return None
    return None

def search_openverse(query: str) -> str | None:
    """Busca en OpenVerse (Creative Commons) y retorna URL de la primera imagen."""
    params = {"q": query, "page_size": 3}
    try:
        r = requests.get(OPENVERSE_API, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        results = r.json().get("results", [])
        for item in results:
            url = item.get("url") or item.get("thumbnail")
            if url:
                return url
    except Exception as exc:
        print(f"    OpenVerse error: {exc}")
    return None

BLOCKED_DOMAINS = {"clipart", "clipartbest", "shutterstock", "gettyimages",
                   "dreamstime", "alamy", "istockphoto", "coedcherry",
                   "onlyfans", "xxx", "porn", "adult", "sexy"}

def search_duckduckgo(query: str) -> list[str]:
    try:
        ddgs = DDGS()
        results = list(ddgs.images(query, max_results=10, safesearch="on"))
        urls = []
        for r in results:
            url = r.get("image", "")
            width = int(r.get("width", 0) or 0)
            height = int(r.get("height", 0) or 0)
            if not url.startswith("http"):
                continue
            if any(b in url.lower() for b in BLOCKED_DOMAINS):
                continue
            if width < 400 or height < 300:
                continue
            if not is_relevant(query, r):
                continue
            urls.append(url)
        return urls
    except Exception as exc:
        print(f"    DuckDuckGo error: {exc}")
    return []

def resize_for_social(src: Path, out_dir: Path) -> None:
    img = Image.open(src).convert("RGB")
    target_w, target_h = 1080, 1080
    
    # Escalar manteniendo proporción hasta cubrir el cuadrado
    ratio = max(target_w / img.width, target_h / img.height)
    new_w = int(img.width * ratio)
    new_h = int(img.height * ratio)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    
    # Crop centrado
    left = (new_w - target_w) // 2
    top  = (new_h - target_h) // 2
    img  = img.crop((left, top, left + target_w, top + target_h))
    
    dest = out_dir / "source_images" / src.name
    dest.parent.mkdir(parents=True, exist_ok=True)
    img.save(dest, "JPEG", quality=90)

def is_relevant(query: str, result: dict) -> bool:
    """Verifica que el resultado tenga relación con el query."""
    keywords = set(query.lower().split())
    # Ignorar palabras genéricas
    keywords -= {"the", "a", "an", "of", "in", "at", "for", "and", "de", "la", "el"}
    
    haystack = (
        result.get("title", "") + " " +
        result.get("url", "") + " " +          # URL de la página fuente
        result.get("image", "")
    ).lower()
    
    matches = sum(1 for kw in keywords if kw in haystack)
    return matches >= max(1, len(keywords) // 2)  # al menos la mitad de keywords

def download(url: str, dest: Path) -> bool:
    try:
        with requests.get(url, headers=DOWNLOAD_HEADERS, stream=True, timeout=30) as r:
            r.raise_for_status()
            if "image" not in r.headers.get("Content-Type", ""):
                print(f"    ✗ URL no es imagen")
                return False
            data = r.content
            img = Image.open(io.BytesIO(data))
            img.load()                          # decodifica completamente
            img.convert("RGB").save(dest, "JPEG", quality=85)
        return True
    except Exception as exc:
        print(f"    ✗ Download failed: {exc}")
        return False

def process(entries: list[tuple[str, str]], out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    # Borrar TODAS las imágenes previas, no solo .jpg: un archivo suelto con otra
    # extensión sobrevive a la limpieza y termina como slide del carrusel siguiente.
    for f in out_dir.iterdir():
        if f.is_file() and f.suffix.lower() in (".jpg", ".jpeg", ".png", ".webp"):
            f.unlink()
    used_titles = set()

    for filename, description in entries:
        dest = out_dir / filename
        print(f"\n[{filename}] {description[:80]}…")

        query = build_query(description)
        print(f"  \u2192 query: '{query}'")

        candidates = search_commons(query)
        if not candidates:
            print("  ✗ No results on Wikimedia Commons")

        downloaded = False
        for candidate in candidates:
            title = candidate["title"]
            if title in used_titles:   # ← agrega esto
                continue
            time.sleep(DELAY)
            url = get_image_url(title)
            if not url:
                continue
            print(f"  ↓ {title[:70]}")
            if download(url, dest):
                used_titles.add(title)
                size_kb = dest.stat().st_size // 1024
                print(f"  ✓ Saved → {dest}  ({size_kb} KB)")
                resize_for_social(dest, out_dir.parent)
                downloaded = True
                break
            time.sleep(DELAY)
        

        if not downloaded:
            print("  → Intentando DuckDuckGo (⚠ puede tener derechos)…")
            # Intenta primero con query completa, luego con las 2 primeras palabras
            queries_to_try = [query, " ".join(query.split()[:2])]
            for q in queries_to_try:
                for url in search_duckduckgo(q):
                    print(f"    ⚠ Imagen con posibles derechos: {url[:60]}")
                    if download(url, dest):
                        print(f"  ✓ Guardado desde DuckDuckGo → {dest}")
                        resize_for_social(dest, out_dir.parent)
                        downloaded = True
                        break
                if downloaded:
                    break
            if not downloaded:
                print("  ✗ No encontrado en ninguna fuente")

        time.sleep(DELAY)



def main():
    parser = argparse.ArgumentParser(description="Download free images from Wikimedia Commons")
    parser.add_argument("file", help="Path to the images_to_download.txt file")
    parser.add_argument("--out", default="source_images", help="Output folder (default: source_images)")
    args = parser.parse_args()

    entries = parse_image_list(args.file)
    if not entries:
        sys.exit("No image entries found in the file.")

    print(f"Found {len(entries)} images to download → '{args.out}/'")
    process(entries, Path(args.out))
    print("\nDone.")


if __name__ == "__main__":
    main()