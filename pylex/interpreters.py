"""Python interpreter discovery and virtual-environment management."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from typing import Iterable


_PROBE = r"""
import importlib.util, json, platform, struct, sys
try:
    import pip
    pip_available = True
except Exception:
    pip_available = False
print(json.dumps({
    "executable": sys.executable,
    "version": platform.python_version(),
    "implementation": platform.python_implementation(),
    "prefix": sys.prefix,
    "base_prefix": sys.base_prefix,
    "is_venv": sys.prefix != sys.base_prefix,
    "architecture": f"{struct.calcsize('P') * 8}-bit",
    "platform": sys.platform,
    "pip_available": pip_available,
}))
"""


@dataclass(frozen=True)
class InterpreterInfo:
    """Metadata for one verified Python interpreter."""
    executable: str
    version: str
    implementation: str
    prefix: str
    base_prefix: str
    is_venv: bool
    architecture: str
    platform: str
    pip_available: bool

    @property
    def label(self) -> str:
        kind = "venv" if self.is_venv else "base"
        return f"{self.implementation} {self.version} ({self.architecture}, {kind}) — {self.executable}"


def _normalise_executable(value: os.PathLike | str) -> str:
    raw = os.fspath(value).strip().strip('"')
    if not raw:
        raise ValueError("Python interpreter path is empty.")
    candidate = Path(raw).expanduser()
    resolved = candidate.resolve() if candidate.exists() else None
    executable = str(resolved) if resolved is not None else shutil.which(raw)
    if not executable:
        raise FileNotFoundError(f"Python interpreter was not found: {raw}")
    path = Path(executable)
    if not path.is_file():
        raise FileNotFoundError(f"Python interpreter is not a file: {path}")
    return str(path.resolve())


def probe_interpreter(executable: os.PathLike | str, timeout: float = 6.0) -> InterpreterInfo:
    """Run a short isolated probe and reject non-Python or broken executables."""
    resolved = _normalise_executable(executable)
    try:
        completed = subprocess.run(
            [resolved, "-I", "-c", _PROBE],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"Python interpreter probe timed out: {resolved}") from exc
    except OSError as exc:
        raise OSError(f"Could not start Python interpreter {resolved}: {exc}") from exc
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        raise ValueError(f"Interpreter probe failed ({completed.returncode}): {detail}")
    try:
        data = json.loads(completed.stdout.strip().splitlines()[-1])
        info = InterpreterInfo(**data)
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        raise ValueError(f"Interpreter returned invalid metadata: {resolved}") from exc
    # Use the executable reported by Python, not a launcher alias or symlink.
    return InterpreterInfo(
        executable=str(Path(info.executable).resolve()),
        version=info.version, implementation=info.implementation,
        prefix=info.prefix, base_prefix=info.base_prefix,
        is_venv=info.is_venv, architecture=info.architecture,
        platform=info.platform, pip_available=info.pip_available,
    )


def _launcher_candidates() -> Iterable[str]:
    """Yield interpreter paths reported by the Windows Python launcher."""
    if os.name != "nt":
        return ()
    launcher = shutil.which("py")
    if not launcher:
        return ()
    try:
        result = subprocess.run(
            [launcher, "-0p"], capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=4, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return ()
    paths = []
    for line in result.stdout.splitlines():
        match = re.search(r"([A-Za-z]:\\.*?python(?:w)?\.exe)\s*$", line, re.I)
        if match:
            paths.append(match.group(1).strip())
    return paths


def discover_interpreters(extra_paths: Iterable[str] = (), timeout: float = 6.0) -> list[InterpreterInfo]:
    """Discover and verify common PATH, active, and Windows launcher interpreters."""
    candidates = [sys.executable]
    for name in ("python", "python3", "python3.13", "python3.12", "python3.11", "python3.10"):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    candidates.extend(_launcher_candidates())
    candidates.extend(extra_paths or ())
    results: list[InterpreterInfo] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            info = probe_interpreter(candidate, timeout=timeout)
        except (OSError, ValueError, TimeoutError):
            continue
        key = os.path.normcase(os.path.realpath(info.executable))
        if key not in seen:
            seen.add(key)
            results.append(info)
    return sorted(results, key=lambda item: (
        item.is_venv, tuple(int(part) if part.isdigit() else 0
                            for part in item.version.split(".")[:3]),
        item.executable.lower(),
    ), reverse=True)


def virtual_environment_python(environment_path: os.PathLike | str) -> Path:
    """Return the platform-specific Python executable inside a venv."""
    root = Path(environment_path).expanduser()
    return root / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def create_virtual_environment(
    base_interpreter: os.PathLike | str,
    environment_path: os.PathLike | str,
    *,
    with_pip: bool = True,
    upgrade_deps: bool = False,
    timeout: float = 180.0,
) -> InterpreterInfo:
    """Create a new venv without deleting or overwriting existing user data."""
    base = probe_interpreter(base_interpreter)
    target = Path(environment_path).expanduser().resolve()
    if target.exists():
        if not target.is_dir():
            raise NotADirectoryError(f"Environment target is not a directory: {target}")
        if any(target.iterdir()):
            raise FileExistsError(
                f"Environment directory is not empty; choose another location: {target}"
            )
    else:
        target.parent.mkdir(parents=True, exist_ok=True)
    command = [base.executable, "-m", "venv"]
    if not with_pip:
        command.append("--without-pip")
    if upgrade_deps:
        command.append("--upgrade-deps")
    command.append(str(target))
    try:
        result = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8",
            errors="replace", timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise TimeoutError(f"Virtual environment creation timed out: {target}") from exc
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "Unknown venv error."
        raise RuntimeError(f"Could not create virtual environment: {detail}")
    executable = virtual_environment_python(target)
    try:
        info = probe_interpreter(executable)
    except Exception:
        # Preserve a useful failure message but never report a broken environment as ready.
        raise RuntimeError(
            f"Virtual environment was created but its interpreter could not be verified: {executable}"
        )
    if not info.is_venv:
        raise RuntimeError(f"Created interpreter is not recognized as a virtual environment: {executable}")
    return info


def find_project_environment(project_root: os.PathLike | str) -> InterpreterInfo | None:
    """Find a valid conventional project environment without guessing arbitrary folders."""
    root = Path(project_root).expanduser().resolve()
    for name in (".venv", "venv", "env"):
        candidate = virtual_environment_python(root / name)
        if candidate.is_file():
            try:
                info = probe_interpreter(candidate)
            except (OSError, ValueError, TimeoutError):
                continue
            if info.is_venv:
                return info
    return None


def run_pip(
    interpreter: os.PathLike | str,
    arguments: Iterable[str],
    *,
    cwd: os.PathLike | str | None = None,
    timeout: float = 300.0,
) -> subprocess.CompletedProcess:
    """Run pip through the selected interpreter, never through a global pip command."""
    info = probe_interpreter(interpreter)
    args = [str(item) for item in arguments]
    if not args:
        raise ValueError("A pip subcommand is required.")
    if args[0] not in {"install", "list", "show", "check", "freeze", "uninstall"}:
        raise ValueError(f"Unsupported pip operation: {args[0]}")
    return subprocess.run(
        [info.executable, "-m", "pip", *args],
        cwd=str(Path(cwd).resolve()) if cwd is not None else None,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=timeout, check=False,
    )
