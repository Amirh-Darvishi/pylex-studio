"""Dependency inspection against the selected project's Python interpreter."""
import ast
from dataclasses import dataclass
import importlib.metadata
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

from .interpreters import probe_interpreter

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


def python_environment(python_executable=None):
    """Describe the exact interpreter used by the editor or project."""
    info = probe_interpreter(python_executable or sys.executable)
    return {
        "executable": info.executable,
        "version": info.version,
        "prefix": info.prefix,
        "base_prefix": info.base_prefix,
        "virtual_environment": info.is_venv,
        "platform": info.platform,
        "implementation": info.implementation,
        "architecture": info.architecture,
        "pip_available": info.pip_available,
    }


def _local_module(name, root):
    if (root / (name + ".py")).is_file() or (root / name / "__init__.py").is_file():
        return True
    return (root / name).is_dir()


def _distribution_for(name, package_map):
    mapped = package_map.get(name) or ()
    return sorted(mapped)[0] if mapped else PIP_NAMES.get(name, name)


def _inspect_with_interpreter(names, executable):
    """Inspect modules in one subprocess so results match the selected interpreter."""
    script = r'''
import importlib.metadata, importlib.util, json, sys
names = json.loads(sys.stdin.read())
stdlib = set(getattr(sys, "stdlib_module_names", ())) | set(sys.builtin_module_names)
package_map = importlib.metadata.packages_distributions()
result = []
for name in names:
    if name in stdlib:
        result.append({"name": name, "distribution": "Python standard library",
                       "status": "standard", "version": "", "location": ""})
        continue
    try:
        spec = importlib.util.find_spec(name)
    except (ImportError, ModuleNotFoundError, ValueError, AttributeError):
        spec = None
    if spec is None:
        result.append({"name": name, "distribution": "", "status": "missing",
                       "version": "", "location": ""})
        continue
    mapped = package_map.get(name) or []
    distribution = sorted(mapped)[0] if mapped else name
    try:
        version = importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        version = "available (metadata unavailable)"
    result.append({"name": name, "distribution": distribution, "status": "installed",
                   "version": version, "location": spec.origin or ""})
print(json.dumps(result))
'''
    info = probe_interpreter(executable)
    completed = subprocess.run(
        [info.executable, "-I", "-c", script],
        input=json.dumps(names), capture_output=True, text=True,
        encoding="utf-8", errors="replace", timeout=15, check=False,
    )
    if completed.returncode:
        detail = completed.stderr.strip() or "Interpreter dependency scan failed."
        raise RuntimeError(detail)
    return json.loads(completed.stdout.strip().splitlines()[-1])


def inspect_dependencies(source, search_root=None, python_executable=None):
    """Inspect imports in source and classify them in the selected interpreter."""
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
    local_names = {name for name in names if _local_module(name, root)}
    external_names = sorted(names - local_names)
    results = [Dependency(name, "Local project module", "local")
               for name in sorted(local_names)]
    try:
        if python_executable:
            inspected = _inspect_with_interpreter(external_names, python_executable)
            for item in inspected:
                distribution = item["distribution"] or PIP_NAMES.get(item["name"], item["name"])
                if distribution == item["name"]:
                    distribution = PIP_NAMES.get(item["name"], distribution)
                results.append(Dependency(
                    item["name"], distribution, item["status"],
                    item["version"], item["location"],
                ))
        else:
            stdlib = set(getattr(sys, "stdlib_module_names", ())) | set(sys.builtin_module_names)
            package_map = importlib.metadata.packages_distributions()
            for name in external_names:
                if name in stdlib:
                    results.append(Dependency(name, "Python standard library", "standard"))
                    continue
                try:
                    spec = importlib.util.find_spec(name)
                except (ImportError, ModuleNotFoundError, ValueError, AttributeError):
                    spec = None
                if spec is None:
                    results.append(Dependency(name, PIP_NAMES.get(name, name), "missing"))
                    continue
                distribution = _distribution_for(name, package_map)
                try:
                    version = importlib.metadata.version(distribution)
                except importlib.metadata.PackageNotFoundError:
                    version = "available (metadata unavailable)"
                results.append(Dependency(name, distribution, "installed", version, spec.origin or ""))
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
        return results, f"Could not inspect selected interpreter: {exc}"
    return sorted(results, key=lambda item: item.import_name.lower()), None


def find_missing_imports(source, search_root=None, python_executable=None):
    """Backward-compatible missing-import API."""
    dependencies, _error = inspect_dependencies(
        source, search_root, python_executable=python_executable,
    )
    return [(item.import_name, item.distribution)
            for item in dependencies if item.status == "missing"]
