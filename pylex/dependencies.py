"""Project dependency inspection using the same Python interpreter as PyLex Studio."""
import ast
from dataclasses import dataclass
import importlib.metadata
import importlib.util
from pathlib import Path
import sys

PIP_NAMES = {
    "PIL": "Pillow", "cv2": "opencv-python", "yaml": "PyYAML",
    "sklearn": "scikit-learn", "bs4": "beautifulsoup4",
    "dotenv": "python-dotenv", "Crypto": "pycryptodome",
    "OpenSSL": "pyOpenSSL",
}

@dataclass(frozen=True)
class Dependency:
    import_name: str
    distribution: str
    status: str
    version: str = ""
    location: str = ""

def python_environment():
    """Describe the interpreter used by the editor and its child scripts."""
    return {
        "executable": sys.executable,
        "version": sys.version.split()[0],
        "prefix": sys.prefix,
        "base_prefix": sys.base_prefix,
        "virtual_environment": sys.prefix != sys.base_prefix,
        "platform": sys.platform,
    }

def _local_module(name, root):
    if (root / (name + ".py")).is_file() or (root / name / "__init__.py").is_file():
        return True
    return (root / name).is_dir()  # PEP 420 namespace package

def _distribution_for(name, package_map):
    mapped = package_map.get(name) or ()
    return sorted(mapped)[0] if mapped else PIP_NAMES.get(name, name)

def inspect_dependencies(source, search_root=None):
    """Inspect imports; dynamic imports remain detectable only at runtime."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [], f"Cannot scan imports until syntax is corrected: {exc.msg} (line {exc.lineno})"

    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".", 1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".", 1)[0])

    root = Path(search_root or Path.cwd()).resolve()
    stdlib = set(getattr(sys, "stdlib_module_names", ())) | set(sys.builtin_module_names)
    package_map = importlib.metadata.packages_distributions()
    results = []

    for name in sorted(names):
        if not name:
            continue
        if name in stdlib:
            results.append(Dependency(name, "Python standard library", "standard"))
            continue
        if _local_module(name, root):
            results.append(Dependency(name, "Local project module", "local"))
            continue

        distribution = _distribution_for(name, package_map)
        try:
            spec = importlib.util.find_spec(name)
        except (ImportError, ModuleNotFoundError, ValueError, AttributeError):
            spec = None
        if spec is None:
            results.append(Dependency(name, distribution, "missing"))
            continue
        try:
            version = importlib.metadata.version(distribution)
        except importlib.metadata.PackageNotFoundError:
            version = "available (metadata unavailable)"
        results.append(Dependency(name, distribution, "installed", version, spec.origin or ""))

    return results, None

def find_missing_imports(source, search_root=None):
    """Backward-compatible missing-import API."""
    dependencies, _error = inspect_dependencies(source, search_root)
    return [(item.import_name, item.distribution)
            for item in dependencies if item.status == "missing"]
