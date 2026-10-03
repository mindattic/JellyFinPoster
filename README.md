# JellyFinPoster

Keep your Jellyfin library tiles fresh: JellyFinPoster builds a poster collage from each library's newest additions and uploads it as that library's image, once a day, on its own.

![Python 3.10+](https://img.shields.io/badge/Python-3.10%2B-3776AB) ![Pillow](https://img.shields.io/badge/Pillow-imaging-4B8BBE) ![Jellyfin API](https://img.shields.io/badge/Jellyfin-API-00A4DC) ![Platform Windows](https://img.shields.io/badge/Platform-Windows%20Task%20Scheduler-0078D6) ![Status working](https://img.shields.io/badge/Status-working-2f7a4f)

```text
 One library tile, as JellyFinPoster draws it (up to 5 x 2 posters, 500 x 750 px each)

 ╭────────┬────────┬────────┬────────┬────────╮
 │ newest │ newest │ newest │ newest │ newest │
 │ poster │ poster │ poster │ poster │ poster │
 │████████████████████████████████████████████│  <- translucent black banner
 │███████████████    MOVIES    ███████████████│  <- white label, black outline
 │████████████████████████████████████████████│
 │ newest │ newest │ newest │ newest │ newest │
 │ poster │ poster │ poster │ poster │ poster │
 ╰────────┴────────┴────────┴────────┴────────╯  rounded corners, saved as JPEG
```

JellyFinPoster pulls the artwork straight from Jellyfin itself and uploads the finished collage as the Primary image for your **Movies**, **TV Shows**, **Books** and **Music** libraries, so the library folder art refreshes automatically instead of staying a static icon. The image goes to the Jellyfin server over its API, so once it is pushed every client (tablet, phone, browser, TV app) sees the new poster immediately.

## Why

- See what was just added the moment you open Jellyfin, right on the library tiles.
- Stop maintaining library artwork by hand; a daily scheduled task does it for you.
- Set it up with one double-click: `Start.bat` installs Python, asks for two values and schedules itself.
- Keep the tiles clean: duplicate artwork and blank posters are skipped, and a library with too few usable posters is left alone rather than given a broken collage.
- Use your own server's artwork only; nothing is fetched from outside Jellyfin.

## Features

- **Four libraries:** Movies (`Movie` items), TV (`Series`), Books (`Book`) and Music (`MusicAlbum`), labelled MOVIES, TV, BOOKS and MUSIC.
- **Automatic library lookup** by Jellyfin collection type (`movies`, `tvshows`, `books`, `music`), with display names as a fallback. No manual `ParentId` lookup.
- **Newest first:** asks Jellyfin for recently added items (sorted by date created), with three times the needed count as headroom, then shuffles them so the grid changes each run.
- **Clean grids:** posters are de-duplicated by an MD5 hash of the image bytes (not just by item ID), near-blank images are rejected, and a grid needs at least 3 usable posters. Rows shrink to fit a partial batch.
- **Readable label:** Noto Sans Bold (bundled in `fonts/`), auto-sized to fit long labels, on a translucent banner with a black outline.
- **Unattended:** a daily Windows Scheduled Task that runs without a console window and catches up if the PC was asleep or off.
- **Logging** to the console and to `jellyfin_poster.log`.

## Quick start

Double-click `Start.bat`. On each run it:

1. Installs Python 3.10 or newer if it is not already present (per-user, no admin rights needed).
2. Installs the project's dependencies (`requests`, `pillow`, `python-dotenv`).
3. If `.env` does not exist yet, asks for `JF_URL` and `JF_API_KEY` right in the console (with a hint on where to find each) and creates `.env` from your answers.
4. Registers a daily Windows Scheduled Task, `JellyfinPosterRefresh`, so the refresh keeps happening on its own.
5. Runs the refresh once immediately, so you see it working right away.

Then open Jellyfin: the library tiles show the new collages.

### Manual path

```bash
pip install -r requirements.txt
copy .env.example .env
python jellyfin_poster.py
```

Fill in `.env` before the last command. Output is logged to the console and to `jellyfin_poster.log`.

## Configuration

All settings live in `.env` (see `.env.example`).

| Variable | Required | Meaning |
|---|---|---|
| `JF_URL` | yes | Base URL of your Jellyfin server, for example `http://192.168.1.10:8096` |
| `JF_API_KEY` | yes | A Jellyfin API key (Dashboard, Advanced, API Keys) |
| `JF_MOVIES_LIBRARY_NAME` | no | Fallback display name, default `Movies` |
| `JF_TV_LIBRARY_NAME` | no | Fallback display name, default `TV Shows` |
| `JF_BOOKS_LIBRARY_NAME` | no | Fallback display name, default `Books` |
| `JF_MUSIC_LIBRARY_NAME` | no | Fallback display name, default `Music` |

Library IDs are looked up automatically by collection type. Only set the library name variables if your libraries use non-default names and the automatic lookup does not find them.

## The scheduled task

`JellyfinPosterRefresh` runs daily at midnight via `pythonw.exe` (no console window), and catches up automatically if the PC was asleep or off at the scheduled time. If a run fails it retries up to 3 times, 5 minutes apart.

To re-register it by hand (for example after moving the project folder), or to change its run time:

```powershell
.\scripts\register_scheduled_task.ps1 -Time "06:30"
```

The script also takes `-TaskName` and `-PythonExe`. To remove the task:

```powershell
Unregister-ScheduledTask -TaskName JellyfinPosterRefresh
```

Because the task runs on this machine, this PC needs to be powered on and able to reach `JF_URL` at run time. If Jellyfin runs on a different machine or a NAS, that machine just needs to be reachable over the network; it does not run the script itself.

## How it works

```text
 for each library (movies, tvshows, books, music):
   GET  {JF_URL}/Library/VirtualFolders            find the library by CollectionType (or name)
   GET  {JF_URL}/Items?ParentId=..&SortBy=DateCreated&SortOrder=Descending&Limit=30
   GET  {JF_URL}/Items/{id}/Images/Primary         for each item until 10 good posters
        skip duplicates (MD5) and near-blank images
   Pillow: fit to 500 x 750, paste into a 5-column grid, draw banner + label, round corners
   POST {JF_URL}/Items/{libraryId}/Images/Primary  JPEG, quality 85, base64 body
```

Every request carries the API key in the `X-Emby-Token` header.

## Project layout

| Path | What it is |
|---|---|
| `Start.bat` | Double-click launcher; runs `bootstrap.ps1` |
| `bootstrap.ps1` | Finds or installs Python, installs requirements, creates `.env`, registers the task, runs a refresh |
| `jellyfin_poster.py` | The refresh: fetch, compose, upload |
| `scripts/register_scheduled_task.ps1` | Registers the daily Windows Scheduled Task |
| `fonts/NotoSans.ttf` | Label font |
| `.env.example` | Configuration template |

## Limitations

- Windows only for the scheduled task; the Python script itself has fallback font paths for Linux, but scheduling there is up to you.
- A library with fewer than 3 usable posters is skipped and keeps its current image.
- `bootstrap.ps1` writes only the Movies and TV name fallbacks into a new `.env`; Books and Music use their built-in defaults unless you add them.

## Documentation

- [AGENTS.md](AGENTS.md): entry point for AI agents working in this repo; it points at the shared MindAttic agent standard.

## License

This repository has no LICENSE file; all rights are reserved. The bundled `fonts/NotoSans.ttf` is the Noto Sans typeface and keeps its own font license.

Part of [MindAttic](https://mindattic.com) — see more projects at [github.com/mindattic](https://github.com/mindattic). Related: [Audible-To-GoodReads](https://github.com/mindattic/Audible-To-GoodReads), another self-installing Python tool for your media library.
