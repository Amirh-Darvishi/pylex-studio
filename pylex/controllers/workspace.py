"""Workspace lifecycle controller, independent from Tkinter widgets."""

from pathlib import Path

from ..core.project import Project


class WorkspaceController:
    """Own the active project and validate workspace lifecycle transitions."""

    def __init__(self, project=None):
        self._project = project

    @property
    def project(self):
        return self._project

    def open(self, path):
        """Validate a workspace path and make its Project the active project."""
        project = path if isinstance(path, Project) else Project.open(path)
        self._project = project
        return project

    def restore(self, path):
        """Restore a previous workspace, returning None when it is no longer valid."""
        if not path:
            self._project = None
            return None
        try:
            return self.open(path)
        except (OSError, ValueError):
            self._project = None
            return None

    def close(self):
        """Close the active workspace and return the project that was closed."""
        previous = self._project
        self._project = None
        return previous

    def project_for_file(self, path=None):
        """Resolve the project context for a document without changing active state."""
        if self._project is not None and (path is None or self._project.contains(path)):
            return self._project
        if path is not None:
            return Project.from_file(path)
        return self._project or Project.open(Path.cwd())
