"""Build a poster collage from a Jellyfin library's most recently added
titles and push it as the Primary image for that library (Movies / TV Shows).

Runs once per invocation; schedule repeat runs with an OS-level scheduler
(see scripts/register_scheduled_task.ps1 for Windows Task Scheduler)."""
import base64
import logging
import os
import random
import sys
from io import BytesIO

import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageStat

load_dotenv()

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jellyfin_poster.log")
log_handlers = [logging.FileHandler(LOG_PATH, encoding="utf-8")]
if sys.stdout is not None:  # pythonw.exe has no console, so sys.stdout/stderr are None
    log_handlers.append(logging.StreamHandler())
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=log_handlers)
log = logging.getLogger("jellyfin-poster")

POSTER_W, POSTER_H = 500, 750
GRID_COLS, GRID_ROWS = 5, 2
MIN_POSTERS = 3

MEDIA = {
    "movies": {"item_type": "Movie", "label": "MOVIES", "collection_type": "movies"},
    "tvshows": {"item_type": "Series", "label": "TV SHOWS", "collection_type": "tvshows"},
}


def require_env(name):
    value = os.environ.get(name)
    if not value:
        log.error("Missing required environment variable: %s (see .env.example)", name)
        sys.exit(1)
    return value


JF_URL = require_env("JF_URL").rstrip("/")
JF_API_KEY = require_env("JF_API_KEY")

MOVIES_LIBRARY_NAME = os.environ.get("JF_MOVIES_LIBRARY_NAME", "Movies")
TV_LIBRARY_NAME = os.environ.get("JF_TV_LIBRARY_NAME", "TV Shows")


def get_font(size):
    for path in (
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "arial.ttf",
    ):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def get_library_item_id(collection_type, display_name):
    url = f"{JF_URL}/Library/VirtualFolders"
    try:
        resp = requests.get(url, headers={"X-Emby-Token": JF_API_KEY}, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error("Failed to query Jellyfin libraries: %s", e)
        return None

    for folder in resp.json():
        if folder.get("CollectionType") == collection_type or folder.get("Name") == display_name:
            return folder.get("ItemId")

    log.error("Could not find a %s library named %r on the Jellyfin server", collection_type, display_name)
    return None


def fetch_recent_item_ids(library_item_id, item_type, limit):
    url = f"{JF_URL}/Items"
    params = {
        "ParentId": library_item_id,
        "IncludeItemTypes": item_type,
        "Recursive": "true",
        "SortBy": "DateCreated",
        "SortOrder": "Descending",
        "Limit": limit,
    }
    try:
        resp = requests.get(url, headers={"X-Emby-Token": JF_API_KEY}, params=params, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error("Failed to fetch recent items for library %s: %s", library_item_id, e)
        return []

    seen = set()
    item_ids = []
    for item in resp.json().get("Items", []):
        item_id = item.get("Id")
        if item_id and item_id not in seen:
            seen.add(item_id)
            item_ids.append(item_id)
    return item_ids


def fetch_item_poster(item_id):
    url = f"{JF_URL}/Items/{item_id}/Images/Primary"
    resp = requests.get(url, headers={"X-Emby-Token": JF_API_KEY}, timeout=20)
    resp.raise_for_status()
    return resp.content


def is_valid_image(image):
    stat = ImageStat.Stat(image.convert("RGB"))
    return max(stat.stddev) > 5  # rejects near-solid (blank/black/white) images


def draw_title_label(image, text):
    draw = ImageDraw.Draw(image)
    font = get_font(300)
    w, h = image.size
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=12)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    text_top = (h - th) // 2
    x = (w - tw) // 2 - bbox[0]
    y = text_top - bbox[1]

    banner_pad = 40
    banner = Image.new("RGBA", image.size, (0, 0, 0, 0))
    ImageDraw.Draw(banner).rectangle([0, text_top - banner_pad, w, text_top + th + banner_pad], fill=(0, 0, 0, 120))
    image.paste(banner, (0, 0), banner)

    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255), stroke_width=12, stroke_fill=(0, 0, 0, 255))


def build_collage(media_key, library_item_id):
    info = MEDIA[media_key]
    max_needed = GRID_COLS * GRID_ROWS
    item_ids = fetch_recent_item_ids(library_item_id, info["item_type"], max_needed)
    if not item_ids:
        log.warning("No recently added items found for %s, skipping collage", media_key)
        return None

    random.shuffle(item_ids)

    posters = []
    for item_id in item_ids:
        try:
            content = fetch_item_poster(item_id)
            img = Image.open(BytesIO(content))
            img.load()
            if not is_valid_image(img):
                log.warning("Poster for item %s looks blank, skipping", item_id)
                continue
            fitted = ImageOps.fit(img.convert("RGBA"), (POSTER_W, POSTER_H), Image.Resampling.LANCZOS)
            posters.append(fitted)
        except Exception as e:
            log.warning("Skipping poster for item %s: %s", item_id, e)

    if len(posters) < MIN_POSTERS:
        log.warning("Only %d usable poster(s) for %s, skipping upload", len(posters), media_key)
        return None

    rows = -(-len(posters) // GRID_COLS)  # ceil division, so a partial batch doesn't leave dead rows
    canvas = Image.new("RGBA", (POSTER_W * GRID_COLS, POSTER_H * rows), (0, 0, 0, 0))
    for i, poster in enumerate(posters):
        canvas.paste(poster, ((i % GRID_COLS) * POSTER_W, (i // GRID_COLS) * POSTER_H))

    draw_title_label(canvas, info["label"])

    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0) + canvas.size, radius=60, fill=255)
    canvas.putalpha(mask)

    if not is_valid_image(canvas):
        log.error("Generated collage for %s looks blank, skipping upload", media_key)
        return None

    return canvas


def upload_library_image(item_id, image):
    if image is None or item_id is None:
        return

    buffer = BytesIO()
    image.convert("RGB").save(buffer, format="JPEG", quality=85)
    payload = base64.b64encode(buffer.getvalue())

    url = f"{JF_URL}/Items/{item_id}/Images/Primary"
    headers = {"X-Emby-Token": JF_API_KEY, "Content-Type": "image/jpeg"}

    try:
        resp = requests.post(url, headers=headers, data=payload, timeout=60)
        resp.raise_for_status()
        log.info("Updated primary image for library item %s", item_id)
    except requests.RequestException as e:
        log.error("Failed to upload image for %s: %s", item_id, e)


def run():
    log.info("Starting poster refresh")
    for media_key, info in MEDIA.items():
        library_name = MOVIES_LIBRARY_NAME if media_key == "movies" else TV_LIBRARY_NAME
        item_id = get_library_item_id(info["collection_type"], library_name)
        if item_id is None:
            continue
        collage = build_collage(media_key, item_id)
        upload_library_image(item_id, collage)
    log.info("Poster refresh complete")


if __name__ == "__main__":
    run()
