"""Filesystem-only workspace scanner used by the responsive project tree."""

import os
from pathlib import Path

from .core.file_types import file_type_for


IGNORED_DIRECTORY_NAMES = frozenset(
    {
        ".git",
        ".venv",
        "venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".tox",
        "node_modules",
    }
)


def iter_workspace_entries(root):
    """Yield workspace entries depth-first without following directory symlinks.

    Each result is (parent_relative_path, name, absolute_path, kind, is_directory).
    Directory entries are yielded before their siblings' files so consumers can
    create parents before their descendants. Filesystem access stays outside Tk.
    """
    root = Path(root).expanduser().resolve()
    stack = [(root, Path("."))]
    while stack:
        directory, relative_parent = stack.pop()
        try:
            with os.scandir(directory) as iterator:
                entries = list(iterator)
        except OSError:
            continue

        directories = []
        files = []
        for entry in entries:
            if entry.name in IGNORED_DIRECTORY_NAMES or entry.is_symlink():
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    directories.append(entry)
                elif entry.is_file(follow_symlinks=False):
                    files.append(entry)
            except OSError:
                continue

        directories.sort(key=lambda item: item.name.lower())
        files.sort(key=lambda item: item.name.lower())

        for entry in directories:
            relative = relative_parent / entry.name
            yield (
                relative_parent.as_posix() if relative_parent != Path(".") else "",
                entry.name,
                str(Path(entry.path)),
                "directory",
                True,
            )
        for entry in files:
            path = Path(entry.path)
            yield (
                relative_parent.as_posix() if relative_parent != Path(".") else "",
                entry.name,
                str(path),
                file_type_for(path).kind,
                False,
            )

        for entry in reversed(directories):
            stack.append((Path(entry.path), relative_parent / entry.name))
