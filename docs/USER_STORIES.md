---
codex: 1
project: JellyFinPoster
code: JFP
layer: stories
status: living
updated: 2026-10-12
---
<!-- GENERATED from MindAttic.Tickets/data/Tickets.db by `tickets db render`. Do not edit: this file is rewritten from the database; change stories and tickets with the tickets CLI. -->

# JellyFinPoster — User Stories
> ✅ done (shipped & tested) · 🟡 partial · ⬜ planned. Every ✅ cites the test.

## Priority backlog
_Nothing recorded yet._

## Tickets
> Permanent log of every change and fix — this repo's ticket system. Rows are append-only: never
> delete or reword one; only move its Status (open → closed / wont-do) and fill in Ref. Status is
> a word, not a glyph, so tickets don't count toward the story index. Keep this section last.

| ID | Date | Type | Status | Summary | Ref |
|---|---|---|---|---|---|
| JFP-T1 | 2026-10-12 | docs | closed | Start the permanent ticket log in USER_STORIES.md | — |
| JFP-T2 | 2026-10-16 | chore | closed | install.ps1 adds this repo's 9 .prose/commands stubs for the shared global commands, so any LLM client finds them | mindattic-agent-standard/install.ps1 run 2026-10-16 |
| JFP-T3 | 2026-10-16 | chore | closed | Bug hunt: run an exhaustive /bughunt over the whole repo and fix every real bug found (each fix under its own fix ticket), then hunt again; close this only when a full pass finds nothing | 9a5f84c |
| JFP-T4 | 2026-10-16 | chore | open | Run the full unit test suite and fix every failure (each under its own fix ticket) until it passes; put the passing run in --ref. No test project: close this wont-do saying so | user request 2026-10-16: approved repo sweep |
| JFP-T5 | 2026-10-16 | chore | open | Clean up code and docs: remove dead code, stale comments and outdated or duplicated docs, and simplify where behaviour doesn't change (/simplify); tests stay green | user request 2026-10-16: approved repo sweep |
| JFP-T6 | 2026-10-16 | docs | open | Bring README.md up to date with the code as it is now (what it is, setup, usage, commands, current state), following codex-standard/README-STYLE.md; README.htm regenerated if the repo has one | user request 2026-10-16: approved repo sweep |
| JFP-T7 | 2026-10-16 | docs | closed | Update USER_STORIES.md | — |
| JFP-T8 | 2026-10-18 | chore | open | Retire scripts/register_scheduled_task.ps1 and its README steps (job now in MindAttic.Scheduler M.SCHD-T7) | scheduled-task consolidation 2026-10-18 |
| JFP-T9 | 2026-10-19 | chore | wont-do | Convert tracked source files to LF line endings via .gitattributes, per HOUSE-LAW-13 (low priority) | — |
| JFP-T10 | 2026-10-20 | docs | open | Publish JellyFinPoster docs to GitHub Pages via the shared Agency DocFX pipeline: run adopt-docs-site.ps1 (README.md as home page, docs/*.md as articles, API reference only where the code builds in CI), enable Pages with build_type=workflow, set the repo homepage URL, retire tools/build-readme.ps1 and README.htm, confirm the docs Actions run is green and https://mindattic.github.io/JellyFinPoster/ returns 200. Depends on MAT-T8. | — |
| JFP-T11 | 2026-10-20 | fix | closed | bootstrap.ps1 writes .env with a UTF-8 BOM (Windows PowerShell Set-Content -Encoding utf8), so python-dotenv reads the first key as '\ufeffJF_URL' and every run exits 'Missing required environment variable: JF_URL' | 2df67d7 |
| JFP-T12 | 2026-10-20 | fix | closed | Collage rounded corners never show: the mask only sets alpha, and upload's convert('RGB') drops alpha, so the JPEG keeps square poster corners; flatten onto black before saving | f4d0312 |
| JFP-T13 | 2026-10-20 | fix | closed | A non-JSON 200 response (e.g. a reverse proxy login page at JF_URL) makes resp.json() raise outside the try in get_library_item_id/fetch_recent_item_ids, killing the whole run with a traceback that never reaches jellyfin_poster.log under pythonw | 9a5f84c |
| JFP-T14 | 2026-10-20 | feature | open | Library lookup returns the first VirtualFolder whose CollectionType OR Name matches, so with two libraries of one type (e.g. Movies + 4K Movies) only whichever the server lists first gets a collage, and JF_*_LIBRARY_NAME can't pick between them (a type match always wins regardless of name, and a same-named library of another type listed earlier wins over the real one). Decide: prefer type+name match, then type, then name? Or refresh every library of each type? | — |
| JFP-T15 | 2026-10-20 | docs | open | Stale user-facing text: register_scheduled_task.ps1 registers the task with description 'from trending TMDB titles' (artwork now comes from Jellyfin itself), and bootstrap.ps1 prints 'Setting up hourly scheduled task' and 'Refreshing Movies and TV Shows' though the task is daily and all four libraries refresh | — |
| JFP-T16 | 2026-10-21 | docs | closed | Update USER_STORIES.md | — |
| JFP-T17 | 2026-10-22 | docs | closed | Update USER_STORIES.md | — |
| JFP-T18 | 2026-10-24 | docs | closed | Update USER_STORIES.md | — |
