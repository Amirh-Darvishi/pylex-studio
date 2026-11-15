"""Load and save lightweight user-interface preferences."""
import json
from pathlib import Path


DEFAULTS = {
    "theme": "dark",
    "font_family": "Consolas",
    "font_size": 12,
    "show_project_explorer": True,
    "last_workspace": "",
    "timeout_seconds": 10,
}


def preferences_path():
    return Path.home() / ".pylex_studio.json"


def load_preferences():
    values = dict(DEFAULTS)
    try:
        stored = json.loads(preferences_path().read_text(encoding="utf-8"))
        if isinstance(stored, dict):
            values.update({key: stored[key] for key in DEFAULTS if key in stored})
    except (OSError, UnicodeError, json.JSONDecodeError):
        pass
    if values["theme"] not in {"dark", "light"}:
        values["theme"] = DEFAULTS["theme"]
    if values["font_family"] not in {"Consolas", "Cascadia Code", "Courier New", "Lucida Console"}:
        values["font_family"] = DEFAULTS["font_family"]
    try:
        values["font_size"] = max(7, min(40, int(values["font_size"])))
    except (TypeError, ValueError):
        values["font_size"] = DEFAULTS["font_size"]
    values["show_project_explorer"] = bool(values["show_project_explorer"])
    if not isinstance(values["last_workspace"], str):
        values["last_workspace"] = ""
    timeout = values["timeout_seconds"]
    if timeout is not None:
        try:
            timeout = int(timeout)
        except (TypeError, ValueError):
            timeout = DEFAULTS["timeout_seconds"]
        if timeout not in {5, 10, 30, 60}:
            timeout = DEFAULTS["timeout_seconds"]
    values["timeout_seconds"] = timeout
    return values


def save_preferences(values):
    data = {key: values.get(key, DEFAULTS[key]) for key in DEFAULTS}
    path = preferences_path()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path
