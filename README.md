# JellyfinPoster

Builds a poster collage from currently trending/top-rated TMDB titles and
uploads it as the Primary image for your Jellyfin **Movies** and **TV Shows**
libraries, so the library folder art refreshes automatically instead of
staying a static icon.

The image is uploaded straight to the Jellyfin server over its API, so once
it's pushed, every client (tablet, phone, browser, TV app) sees the new
poster immediately.

## Setup

Double-click **`Start.bat`**. On each run it:

1. Installs Python if it isn't already present (per-user, no admin rights needed).
2. Installs the project's dependencies.
3. If `.env` doesn't exist yet, creates it from `.env.example` and stops —
   fill in `TMDB_TOKEN`, `JF_URL` and `JF_API_KEY`, then run `Start.bat` again.
4. Registers an hourly Windows Scheduled Task (`JellyfinPosterRefresh`) so
   the refresh keeps happening on its own from then on.
5. Runs the refresh once immediately, so you see it working right away.

Library IDs are looked up automatically by collection type (movies/tvshows),
so no manual `ParentId` lookup is needed. Only set
`JF_MOVIES_LIBRARY_NAME`/`JF_TV_LIBRARY_NAME` in `.env` if your libraries use
non-default names and the automatic lookup doesn't find them.

### Manual path (no `Start.bat`)

```
pip install -r requirements.txt
copy .env.example .env   # then fill it in
python jellyfin_poster.py
```

Output is logged to the console and to `jellyfin_poster.log`.

## The scheduled task

`JellyfinPosterRefresh` runs every hour via `pythonw.exe` (no console window),
starting at midnight, and catches up automatically if the PC was asleep or
off at a scheduled run.

To re-register it by hand (e.g. after moving the project folder), or to
change its start time:

```
.\scripts\register_scheduled_task.ps1 -StartTime "06:30"
```

To remove it: `Unregister-ScheduledTask -TaskName JellyfinPosterRefresh`.

Since the task runs on this machine, this PC needs to be powered on and able
to reach `JF_URL` at run time for the refresh to succeed — if Jellyfin runs
on a different machine or NAS, that just needs to be reachable over the
network, not run the script itself.
