"""Load and validate persistent PyLex Studio preferences."""
import json
import os
import tempfile
from pathlib import Path


DEFAULTS = {
    "theme": "dark",
    "font_family": "JetBrains Mono",
    "font_size": 12,
    "ui_font_family": "Segoe UI",
    "ui_font_size": 9,
    "show_project_explorer": True,
    "last_workspace": "",
    "recent_workspaces": [],
    "timeout_seconds": 10,
    "interpreter_path": "",
    "project_interpreters": {},
    "terminal_shell": "",
    "account_display_name": "Developer",
}


def preferences_path():
    return Path.home() / ".pylex_studio.json"


def _normalise(values):
    result = dict(DEFAULTS)
    if isinstance(values, dict):
        result.update({key: values[key] for key in DEFAULTS if key in values})
    if result["theme"] not in {"dark", "light"}:
        result["theme"] = DEFAULTS["theme"]
    if result["font_family"] not in {
        "JetBrains Mono", "Cascadia Code", "Fira Code",
        "Consolas", "Cascadia Mono", "Courier New", "Lucida Console",
        "DejaVu Sans Mono", "Liberation Mono", "TkFixedFont",
    }:
        result["font_family"] = DEFAULTS["font_family"]
    if result["ui_font_family"] not in {
        "Segoe UI", "Inter", "Arial", "Tahoma", "Noto Sans", "Ubuntu",
        "DejaVu Sans", "TkDefaultFont",
    }:
        result["ui_font_family"] = DEFAULTS["ui_font_family"]
    try:
        result["ui_font_size"] = max(8, min(14, int(result["ui_font_size"])))
    except (TypeError, ValueError):
        result["ui_font_size"] = DEFAULTS["ui_font_size"]
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
    if not isinstance(result["account_display_name"], str):
        result["account_display_name"] = "Developer"
    result["account_display_name"] = result["account_display_name"].strip()[:48] or "Developer"
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
    """Persist preferences atomically so an interrupted write cannot corrupt them."""
    data = _normalise(values)
    path = preferences_path()
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=path.name + ".",
            suffix=".tmp",
            delete=False,
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(data, temporary, indent=2)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, path)
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
    return path
