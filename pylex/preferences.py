"""Load and validate persistent PyLex Studio preferences."""
import json
import os
from pathlib import Path


DEFAULTS = {
    "theme": "dark",
    "font_family": "Consolas",
    "font_size": 12,
    "show_project_explorer": True,
    "last_workspace": "",
    "recent_workspaces": [],
    "timeout_seconds": 10,
    "interpreter_path": "",
    "project_interpreters": {},
    "terminal_shell": "",
}


def preferences_path():
    return Path.home() / ".pylex_studio.json"


def _normalise(values):
    result = dict(DEFAULTS)
    if isinstance(values, dict):
        result.update({key: values[key] for key in DEFAULTS if key in values})
    if result["theme"] not in {"dark", "light"}:
        result["theme"] = DEFAULTS["theme"]
    if result["font_family"] not in {"Consolas", "Cascadia Code", "Courier New", "Lucida Console"}:
        result["font_family"] = DEFAULTS["font_family"]
    try:
        result["font_size"] = max(7, min(40, int(result["font_size"])))
    except (TypeError, ValueError):
        result["font_size"] = DEFAULTS["font_size"]
    result["show_project_explorer"] = bool(result["show_project_explorer"])
    if not isinstance(result["last_workspace"], str):
        result["last_workspace"] = ""
    timeout = result["timeout_seconds"]
    if timeout is not None:
        try:
            timeout = int(timeout)
        except (TypeError, ValueError):
            timeout = DEFAULTS["timeout_seconds"]
        if timeout not in {5, 10, 30, 60}:
            timeout = DEFAULTS["timeout_seconds"]
    result["timeout_seconds"] = timeout
    recent = result["recent_workspaces"]
    if not isinstance(recent, list):
        recent = []
    cleaned = []
    seen = set()
    for item in recent:
        if not isinstance(item, str) or not item.strip():
            continue
        # Preserve the user's path spelling for a faithful preferences
        # round-trip; normalize only the comparison key for deduplication.
        normalized = os.path.expanduser(item.strip())
        key = os.path.normcase(os.path.abspath(normalized))
        if key not in seen:
            seen.add(key)
            cleaned.append(normalized)
        if len(cleaned) == 8:
            break
    result["recent_workspaces"] = cleaned
    if not isinstance(result["interpreter_path"], str):
        result["interpreter_path"] = ""
    if not isinstance(result["terminal_shell"], str):
        result["terminal_shell"] = ""
    mappings = result["project_interpreters"]
    if not isinstance(mappings, dict):
        mappings = {}
    result["project_interpreters"] = {
        str(root): str(executable)
        for root, executable in mappings.items()
        if isinstance(root, str) and root.strip()
        and isinstance(executable, str) and executable.strip()
    }
    return result


def load_preferences():
    try:
        stored = json.loads(preferences_path().read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        stored = {}
    return _normalise(stored)


def save_preferences(values):
    data = _normalise(values)
    path = preferences_path()
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path
