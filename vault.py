"""JellyFinPoster's settings and Jellyfin key from MindAttic Vault.

Settings live in %APPDATA%\\MindAttic\\JellyFinPoster\\settings.json and the key in the shared
"jellyfin" named key list (%APPDATA%\\MindAttic\\LLM\\providers.json); both are edited in
MindAttic.Vault.Desktop. The .env / environment values the script used before are imported once,
and remain a fallback on a machine without Vault. Standard library only.
"""
import json
import os
import sys
from datetime import datetime, timezone

APP_ID = "JellyFinPoster"
PROVIDER = "jellyfin"
SCHEMA_VERSION = 1
PREFIX = f"MindAttic:Settings:{APP_ID}"

# (property, label, group, help, kind, default, env var)
FIELDS = [
    ("jfUrl", "Jellyfin server URL", "Server", "Base URL of your Jellyfin server, e.g. http://192.168.1.10:8096.", "Url", "", "JF_URL"),
    ("moviesLibraryName", "Movies library", "Libraries", "Library name used when the movies collection type isn't found.", "Text", "Movies", "JF_MOVIES_LIBRARY_NAME"),
    ("tvLibraryName", "TV library", "Libraries", "Library name used when the TV collection type isn't found.", "Text", "TV Shows", "JF_TV_LIBRARY_NAME"),
    ("booksLibraryName", "Books library", "Libraries", "Library name used when the books collection type isn't found.", "Text", "Books", "JF_BOOKS_LIBRARY_NAME"),
    ("musicLibraryName", "Music library", "Libraries", "Library name used when the music collection type isn't found.", "Text", "Music", "JF_MUSIC_LIBRARY_NAME"),
]
ENV_KEY = "JF_API_KEY"


def roaming_root():
    override = os.environ.get("MINDATTIC_VAULT_ROAMING_ROOT", "").strip()
    if override:
        return override
    base = os.environ.get("APPDATA") or os.path.join(os.path.expanduser("~"), ".config")
    return os.path.join(base, "MindAttic")


def local_root():
    override = os.environ.get("MINDATTIC_VAULT_LOCAL_ROOT", "").strip()
    if override:
        return override
    base = os.environ.get("LOCALAPPDATA") or os.path.join(os.path.expanduser("~"), ".local", "share")
    return os.path.join(base, "MindAttic")


def app_dir():
    return os.path.join(roaming_root(), APP_ID)


def settings_path():
    return os.path.join(app_dir(), "settings.json")


def _read_json(path):
    try:
        with open(path, encoding="utf-8-sig") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def _write_json_atomic(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def defaults():
    return {prop: default for prop, _, _, _, _, default, _ in FIELDS}


def load_settings():
    """The saved settings over the defaults (a missing or corrupt file means defaults)."""
    saved = _read_json(settings_path())
    merged = defaults()
    if isinstance(saved, dict):
        merged.update({k: v for k, v in saved.items() if k in merged})
    return merged


def manifest():
    fields = []
    for order, (prop, label, group, help_text, kind, default, _) in enumerate(FIELDS, start=1):
        fields.append({
            "name": f"{PREFIX}:{prop}", "property": prop, "label": label, "group": group, "help": help_text,
            "order": order, "kind": kind, "readOnly": False, "nullable": True, "default": default,
        })
    return {
        "schemaVersion": SCHEMA_VERSION, "appId": APP_ID, "displayName": "Jellyfin Poster", "icon": "image",
        "description": "Builds poster collages for Jellyfin libraries.", "scope": "Roaming",
        "settingsFile": "settings.json", "configurationPrefix": PREFIX, "fields": fields,
        "credentials": [{"providerId": PROVIDER, "displayName": "Jellyfin", "required": True,
                         "purpose": "Reads library items and uploads the poster images."}],
    }


def write_manifest():
    path = os.path.join(app_dir(), "settings.manifest.json")
    data = manifest()
    if _read_json(path) != data:
        _write_json_atomic(path, data)
    return path


def _providers_path():
    return os.path.join(roaming_root(), "LLM", "providers.json")


def named_keys(provider=PROVIDER):
    """[(name, key, disabled)] in failover order, named exactly as MindAttic.Vault names them."""
    entry = (_read_json(_providers_path()) or {}).get(provider)
    if not isinstance(entry, dict):
        return []
    raw = []
    pool = entry.get("apiKeys")
    if isinstance(pool, list):
        for item in pool:
            if isinstance(item, dict) and isinstance(item.get("key"), str) and item["key"].strip():
                raw.append((item.get("label"), item["key"].strip(), item.get("disabled") is True))
    if not raw and isinstance(entry.get("apiKey"), str) and entry["apiKey"].strip():
        raw.append((None, entry["apiKey"].strip(), False))
    used, named, pending = set(), [None] * len(raw), []
    for i, (label, key, disabled) in enumerate(raw):
        label = (label or "").strip()
        if not label or ":" in label:
            pending.append(i)
            continue
        unique, n = label, 2
        while unique.lower() in used:
            unique, n = f"{label} ({n})", n + 1
        used.add(unique.lower())
        named[i] = (unique, key, disabled)
    n = 1
    for i in pending:
        while f"key{n}" in used:
            n += 1
        used.add(f"key{n}")
        named[i] = (f"key{n}", raw[i][1], raw[i][2])
        n += 1
    return named


def assignment(provider=PROVIDER):
    data = _read_json(os.path.join(roaming_root(), "Vault", "key-assignments.json")) or {}
    for app, by_provider in data.items():
        if app.lower() == APP_ID.lower() and isinstance(by_provider, dict):
            names = by_provider.get(provider)
            return [n for n in names if isinstance(n, str)] if isinstance(names, list) else []
    return []


def _unhealthy(provider):
    health = (_read_json(os.path.join(local_root(), "Vault", "key-health.json")) or {}).get(provider) or {}
    now = datetime.now(timezone.utc)
    bad = set()
    for name, h in health.items():
        if not isinstance(h, dict):
            continue
        until = h.get("coolDownUntilUtc")
        cooling = False
        if isinstance(until, str):
            try:
                cooling = datetime.fromisoformat(until.replace("Z", "+00:00")) > now
            except ValueError:
                pass
        if h.get("failed") is True or cooling:
            bad.add(name.lower())
    return bad


def get_key(provider=PROVIDER):
    """This app's active key: its assigned names in order (else the shared order), skipping disabled and unhealthy keys."""
    keys = named_keys(provider)
    order = assignment(provider)
    if order:
        by_name = {name.lower(): (name, key, disabled) for name, key, disabled in keys}
        keys = [by_name[n.lower()] for n in order if n.lower() in by_name]
    bad = _unhealthy(provider)
    for name, key, disabled in keys:
        if not disabled and name.lower() not in bad:
            return key
    return None


def _add_named_key(provider, name, value):
    path = _providers_path()
    data = _read_json(path) or {}
    entry = data.get(provider) if isinstance(data.get(provider), dict) else {"type": "bearer"}
    pool = [(n, k, d) for n, k, d in named_keys(provider)]
    if any(k == value for _, k, _ in pool):
        return next(n for n, k, _ in pool if k == value)
    taken = {n.lower() for n, _, _ in pool}
    unique, i = name, 2
    while unique.lower() in taken:
        unique, i = f"{name} {i}", i + 1
    pool.append((unique, value, False))
    entry["apiKey"] = next((k for _, k, d in pool if not d), "")
    entry["apiKeys"] = [dict({"key": k, "label": n}, **({"disabled": True} if d else {})) for n, k, d in pool]
    data[provider] = entry
    _write_json_atomic(path, dict(sorted(data.items(), key=lambda kv: kv[0].lower())))
    return unique


def _assign_first(provider, name):
    path = os.path.join(roaming_root(), "Vault", "key-assignments.json")
    data = _read_json(path) or {}
    app_key = next((a for a in data if a.lower() == APP_ID.lower()), APP_ID)
    by_provider = data.get(app_key) if isinstance(data.get(app_key), dict) else {}
    current = [n for n in by_provider.get(provider, []) if isinstance(n, str)]
    by_provider[provider] = [name] + [n for n in current if n.lower() != name.lower()]
    data[app_key] = by_provider
    _write_json_atomic(path, data)


def import_env_once(env=None):
    """First run under Vault: carry today's .env / environment values into Vault. Never overwrites."""
    env = os.environ if env is None else env
    if not os.path.exists(settings_path()):
        settings = defaults()
        for prop, _, _, _, _, _, var in FIELDS:
            value = (env.get(var) or "").strip()
            if value:
                settings[prop] = value
        _write_json_atomic(settings_path(), settings)
    key = (env.get(ENV_KEY) or "").strip()
    if key and not any(k == key for _, k, _ in named_keys(PROVIDER)):
        name = _add_named_key(PROVIDER, f"{APP_ID} (imported)", key)
        _assign_first(PROVIDER, name)
    write_manifest()


def resolve(env=None):
    """(url, api_key, {media: library_name}) for the script: Vault first, then the environment."""
    env = os.environ if env is None else env
    s = load_settings()
    url = (s.get("jfUrl") or env.get("JF_URL") or "").strip().rstrip("/")
    key = get_key(PROVIDER) or (env.get(ENV_KEY) or "").strip() or None
    names = {
        "movies": s.get("moviesLibraryName") or env.get("JF_MOVIES_LIBRARY_NAME") or "Movies",
        "tvshows": s.get("tvLibraryName") or env.get("JF_TV_LIBRARY_NAME") or "TV Shows",
        "books": s.get("booksLibraryName") or env.get("JF_BOOKS_LIBRARY_NAME") or "Books",
        "music": s.get("musicLibraryName") or env.get("JF_MUSIC_LIBRARY_NAME") or "Music",
    }
    return url, key, names


if __name__ == "__main__" and "--write-settings-manifest" in sys.argv:
    import_env_once()
    print(write_manifest())
