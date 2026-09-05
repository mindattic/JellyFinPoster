# JellyfinPoster

Builds a poster collage from currently trending/top-rated TMDB titles and
uploads it as the Primary image for your Jellyfin **Movies** and **TV Shows**
libraries, so the library folder art refreshes automatically instead of
staying a static icon.

## Setup

1. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill in:
   - `TMDB_TOKEN` — a TMDB v4 read access token
   - `JF_URL` — your Jellyfin server's base URL (e.g. `http://192.168.1.10:8096`)
   - `JF_API_KEY` — a Jellyfin API key (Dashboard > API Keys)

   Library IDs are looked up automatically by collection type (movies/tvshows),
   so no manual `ParentId` lookup is needed. Only set
   `JF_MOVIES_LIBRARY_NAME`/`JF_TV_LIBRARY_NAME` if your libraries use
   non-default names and the automatic lookup doesn't find them.

3. Run it once to test:
   ```
   python jellyfin_poster.py
   ```
   Output is logged to the console and to `jellyfin_poster.log`.

## Running automatically

The image is uploaded straight to the Jellyfin server over its API, so once
it's pushed, every client (tablet, phone, browser, TV app) sees the new
poster immediately — the script just needs to run somewhere with network
access to `JF_URL`.

On Windows, register an hourly Scheduled Task from a PowerShell prompt:

```
.\scripts\register_scheduled_task.ps1
```

This creates a task named `JellyfinPosterRefresh` that runs every hour
under your user account (starting at midnight by default), and catches up
automatically if the PC was asleep or off at a scheduled run. Pass
`-StartTime "06:30"` to change the first run's anchor time, or
`-PythonExe "C:\path\to\python.exe"` if `python` isn't on PATH for
scheduled tasks.

To remove it later: `Unregister-ScheduledTask -TaskName JellyfinPosterRefresh`.
