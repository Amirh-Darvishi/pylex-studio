"""Static preflight checks for imported third-party Python dependencies."""
import ast
import importlib.util
import sys
from pathlib import Path

# Common import-name to PyPI distribution-name differences.
PIP_NAMES = {
    "PIL": "Pillow",
    "cv2": "opencv-python",
    "yaml": "PyYAML",
    "sklearn": "scikit-learn",
    "bs4": "beautifulsoup4",
    "dotenv": "python-dotenv",
}


def find_missing_imports(source, search_root=None):
    """Return unique (import_name, pip_name) pairs that appear unavailable.

    This is a best-effort preflight only: dynamic imports and custom import hooks
    cannot be discovered statically. The actual interpreter traceback remains
    authoritative.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".", 1)[0])

    root = Path(search_root or Path.cwd())
    missing = []
    for name in sorted(roots):
        if not name or name in sys.stdlib_module_names or name in sys.builtin_module_names:
            continue
        if (root / (name + ".py")).is_file() or (root / name / "__init__.py").is_file():
            continue
        try:
            spec = importlib.util.find_spec(name)
        except (ImportError, ModuleNotFoundError, ValueError):
            spec = None
        if spec is None:
            missing.append((name, PIP_NAMES.get(name, name)))
    return missing
