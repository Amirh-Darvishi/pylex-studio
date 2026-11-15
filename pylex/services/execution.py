"""Application-level execution and debugger orchestration."""
from pathlib import Path
from ..debugger import DebugSession
from ..runner import start_file, start_source


class ExecutionService:
    """Coordinate process creation using a project's execution context."""

    def start_document(self, source, path, project, timeout=10, dirty=False):
        """Run a document, preserving its real path when its buffer is saved."""
        file_path = Path(path).expanduser().resolve() if path else None
        cwd = project.working_directory_for(file_path)
        env = project.execution_environment()
        if file_path is not None and file_path.is_file() and not dirty:
            return start_file(file_path, timeout=timeout, cwd=cwd, env=env)
        return start_source(source, timeout=timeout, cwd=cwd, env=env)

    def start_debugger_document(self, source, path, project, dirty=False):
        """Start pdb with the same path and working-directory rules as execution."""
        file_path = Path(path).expanduser().resolve() if path else None
        cwd = project.working_directory_for(file_path)
        env = project.execution_environment()
        if file_path is not None and file_path.is_file() and not dirty:
            return DebugSession.start_file(file_path, cwd=cwd, env=env)
        return DebugSession.start(source, cwd=cwd, env=env)
