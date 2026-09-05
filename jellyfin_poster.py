"""Build a poster collage from trending TMDB titles and push it as the
Primary image for a Jellyfin library (Movies / TV Shows).

Runs once per invocation; schedule repeat runs with an OS-level scheduler
(see scripts/register_scheduled_task.ps1 for Windows Task Scheduler)."""
import base64
import datetime
import logging
import os
import sys
from io import BytesIO

import requests
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

load_dotenv()

LOG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "jellyfin_poster.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler(LOG_PATH, encoding="utf-8")],
)
log = logging.getLogger("jellyfin-poster")

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMG_BASE_URL = "https://image.tmdb.org/t/p/w500"

POSTER_W, POSTER_H = 500, 750
GRID_COLS, GRID_ROWS = 5, 2

MEDIA = {
    "movies": {
        "tmdb_endpoint": "movie",
        "date_field": "primary_release_date",
        "label": "MOVIES",
        "collection_type": "movies",
    },
    "tvshows": {
        "tmdb_endpoint": "tv",
        "date_field": "first_air_date",
        "label": "TV SHOWS",
        "collection_type": "tvshows",
    },
}


def require_env(name):
    value = os.environ.get(name)
    if not value:
        log.error("Missing required environment variable: %s (see .env.example)", name)
        sys.exit(1)
    return value


TMDB_TOKEN = require_env("TMDB_TOKEN")
JF_URL = require_env("JF_URL").rstrip("/")
JF_API_KEY = require_env("JF_API_KEY")

MOVIES_LIBRARY_NAME = os.environ.get("JF_MOVIES_LIBRARY_NAME", "Movies")
TV_LIBRARY_NAME = os.environ.get("JF_TV_LIBRARY_NAME", "TV Shows")

DISCOVER_WINDOW_DAYS = int(os.environ.get("TMDB_WINDOW_DAYS", "30"))
MIN_VOTE_COUNT = int(os.environ.get("TMDB_MIN_VOTE_COUNT", "30"))


def get_font(size):
    for path in (
        "C:\\Windows\\Fonts\\arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "arial.ttf",
    ):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def fetch_poster_paths(media_key):
    info = MEDIA[media_key]
    today = datetime.date.today()
    start = today - datetime.timedelta(days=DISCOVER_WINDOW_DAYS)
    url = (
        f"{TMDB_BASE_URL}/discover/{info['tmdb_endpoint']}"
        f"?sort_by=vote_average.desc&vote_count.gte={MIN_VOTE_COUNT}"
        f"&{info['date_field']}.gte={start.isoformat()}&{info['date_field']}.lte={today.isoformat()}"
        f"&page=1"
    )
    headers = {"Authorization": f"Bearer {TMDB_TOKEN}", "accept": "application/json"}
    try:
        resp = requests.get(url, headers=headers, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as e:
        log.error("TMDB discover request failed for %s: %s", media_key, e)
        return []

    results = resp.json().get("results", [])
    return [item["poster_path"] for item in results[: GRID_COLS * GRID_ROWS] if item.get("poster_path")]


def draw_neon_label(image, text):
    draw = ImageDraw.Draw(image)
    font = get_font(300)
    w, h = image.size
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x, y = (w - tw) // 2, (h - th) // 2

    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow)
    for offset in range(20, 0, -4):
        glow_draw.text((x, y), text, font=font, fill=(0, 255, 255, 160), stroke_width=offset)
    image.paste(glow.filter(ImageFilter.GaussianBlur(12)), (0, 0), glow)
    draw.text((x, y), text, font=font, fill=(255, 255, 255, 255), stroke_width=3)


def build_collage(media_key):
    paths = fetch_poster_paths(media_key)
    if not paths:
        log.warning("No TMDB results for %s, skipping collage", media_key)
        return None

    posters = []
    for path in paths:
        try:
            resp = requests.get(TMDB_IMG_BASE_URL + path, timeout=20)
            resp.raise_for_status()
            img = Image.open(BytesIO(resp.content)).convert("RGBA")
            posters.append(ImageOps.fit(img, (POSTER_W, POSTER_H), Image.Resampling.LANCZOS))
        except Exception as e:
            log.warning("Skipping poster %s: %s", path, e)

    if not posters:
        return None

    canvas = Image.new("RGBA", (POSTER_W * GRID_COLS, POSTER_H * GRID_ROWS), (0, 0, 0, 0))
    for i, poster in enumerate(posters):
        canvas.paste(poster, ((i % GRID_COLS) * POSTER_W, (i // GRID_COLS) * POSTER_H))

    draw_neon_label(canvas, MEDIA[media_key]["label"])

    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0) + canvas.size, radius=60, fill=255)
    canvas.putalpha(mask)
    return canvas


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
        collage = build_collage(media_key)
        upload_library_image(item_id, collage)
    log.info("Poster refresh complete")


if __name__ == "__main__":
    run()
