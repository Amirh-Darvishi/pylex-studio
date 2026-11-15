"""Project domain model and filesystem context for PyLex Studio."""

from __future__ import annotations
import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Project:
    """Represent a project root and provide consistent path/process context."""

    root: Path
    name: str = field(init=False)

    def __post_init__(self):
        root = Path(self.root).expanduser().resolve()
        if not root.exists():
            raise FileNotFoundError(f"Project path does not exist: {root}")
        if not root.is_dir():
            raise NotADirectoryError(f"Project root is not a directory: {root}")
        object.__setattr__(self, "root", root)
        object.__setattr__(self, "name", root.name or str(root))

    @classmethod
    def open(cls, path):
        """Open a project from a directory path."""
        return cls(Path(path))

    @classmethod
    def from_file(cls, path):
        """Create a project context rooted at a file's parent directory."""
        return cls(Path(path).expanduser().resolve().parent)

    def resolve(self, path):
        """Resolve a path relative to the project root unless it is absolute."""
        candidate = Path(path).expanduser()
        return (
            candidate if candidate.is_absolute() else self.root / candidate
        ).resolve()

    def contains(self, path):
        """Return whether a path is located inside this project."""
        try:
            Path(path).expanduser().resolve().relative_to(self.root)
            return True
        except ValueError:
            return False

    def relative_path(self, path):
        """Return a project-relative path, or None for external files."""
        try:
            return Path(path).expanduser().resolve().relative_to(self.root)
        except ValueError:
            return None

    def working_directory_for(self, file_path=None):
        """Choose a stable working directory for a document in this project."""
        if file_path is None:
            return self.root
        candidate = Path(file_path).expanduser().resolve()
        return self.root if self.contains(candidate) else candidate.parent

    def execution_environment(self, base=None):
        """Build an environment that exposes the project to Python imports."""
        environment = dict(os.environ if base is None else base)
        existing = environment.get("PYTHONPATH", "")
        environment["PYTHONPATH"] = os.pathsep.join(
            [str(self.root)] + ([existing] if existing else [])
        )
        return environment
