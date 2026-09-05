"""Build a poster collage from trending TMDB titles and push it as the
Primary image for a Jellyfin library (Movies / TV Shows).

Runs once per invocation; schedule repeat runs with an OS-level scheduler
(see scripts/register_scheduled_task.ps1 for Windows Task Scheduler)."""
import base64
import datetime
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

TMDB_BASE_URL = "https://api.themoviedb.org/3"
TMDB_IMG_BASE_URL = "https://image.tmdb.org/t/p/w500"

POSTER_W, POSTER_H = 500, 750
GRID_COLS, GRID_ROWS = 5, 2
MIN_POSTERS = 3

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


def _tmdb_get(path, params, error_context):
    headers = {"Authorization": f"Bearer {TMDB_TOKEN}", "accept": "application/json"}
    try:
        resp = requests.get(f"{TMDB_BASE_URL}{path}", headers=headers, params=params, timeout=20)
        resp.raise_for_status()
        return resp.json().get("results", [])
    except requests.RequestException as e:
        log.error("TMDB request failed for %s: %s", error_context, e)
        return []


def _discover_windows():
    today = datetime.date.today()
    last_year = today.year - 1
    return [
        ("last 30 days", today - datetime.timedelta(days=30), today),
        ("last 90 days", today - datetime.timedelta(days=90), today),
        ("this year", today.replace(month=1, day=1), today),
        ("last year", datetime.date(last_year, 1, 1), datetime.date(last_year, 12, 31)),
        ("last 5 years", today - datetime.timedelta(days=365 * 5), today),
        ("last 10 years", today - datetime.timedelta(days=365 * 10), today),
        ("all time", None, None),
    ]


def _discover_poster_paths(media_key, start, end):
    info = MEDIA[media_key]
    params = {"sort_by": "vote_average.desc", "vote_count.gte": MIN_VOTE_COUNT, "page": 1}
    if start is not None:
        params[f"{info['date_field']}.gte"] = start.isoformat()
        params[f"{info['date_field']}.lte"] = end.isoformat()
    results = _tmdb_get(f"/discover/{info['tmdb_endpoint']}", params, f"discover:{media_key}")
    return [item["poster_path"] for item in results if item.get("poster_path")]


def fetch_poster_paths(media_key):
    max_needed = GRID_COLS * GRID_ROWS
    seen = set()
    paths = []
    for window_name, start, end in _discover_windows():
        if len(paths) >= max_needed:
            break
        new_paths = [p for p in _discover_poster_paths(media_key, start, end) if p not in seen]
        if new_paths:
            log.info("Found %d new result(s) for %s in window '%s'", len(new_paths), media_key, window_name)
        seen.update(new_paths)
        paths.extend(new_paths)
    selected = paths[:max_needed]
    random.shuffle(selected)
    return selected


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
            img = Image.open(BytesIO(resp.content))
            img.load()
            if not is_valid_image(img):
                log.warning("Downloaded poster %s looks blank, skipping", path)
                continue
            fitted = ImageOps.fit(img.convert("RGBA"), (POSTER_W, POSTER_H), Image.Resampling.LANCZOS)
            posters.append(fitted)
        except Exception as e:
            log.warning("Skipping poster %s: %s", path, e)

    if len(posters) < MIN_POSTERS:
        log.warning("Only %d usable poster(s) for %s, skipping upload", len(posters), media_key)
        return None

    rows = -(-len(posters) // GRID_COLS)  # ceil division, so a partial batch doesn't leave dead rows
    canvas = Image.new("RGBA", (POSTER_W * GRID_COLS, POSTER_H * rows), (0, 0, 0, 0))
    for i, poster in enumerate(posters):
        canvas.paste(poster, ((i % GRID_COLS) * POSTER_W, (i // GRID_COLS) * POSTER_H))

    draw_title_label(canvas, MEDIA[media_key]["label"])

    mask = Image.new("L", canvas.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0) + canvas.size, radius=60, fill=255)
    canvas.putalpha(mask)

    if not is_valid_image(canvas):
        log.error("Generated collage for %s looks blank, skipping upload", media_key)
        return None

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
