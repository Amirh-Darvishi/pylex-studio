"""Application-level execution and debugger orchestration."""

from pathlib import Path
from ..debugger import DebugSession
from ..runner import start_file, start_source


class ExecutionService:
    """Coordinate processes using a project's paths and selected interpreter."""

    def start_document(
        self,
        source,
        path,
        project,
        timeout=10,
        dirty=False,
        python_executable=None,
    ):
        """Run a document with the interpreter selected for its project."""
        file_path = Path(path).expanduser().resolve() if path else None
        cwd = project.working_directory_for(file_path)
        env = project.execution_environment()
        if file_path is not None and file_path.is_file() and not dirty:
            return start_file(
                file_path,
                timeout=timeout,
                cwd=cwd,
                env=env,
                python_executable=python_executable,
            )
        return start_source(
            source,
            timeout=timeout,
            cwd=cwd,
            env=env,
            python_executable=python_executable,
        )

    def start_debugger_document(
        self,
        source,
        path,
        project,
        dirty=False,
        python_executable=None,
    ):
        """Start pdb with the same interpreter and project context as Run."""
        file_path = Path(path).expanduser().resolve() if path else None
        cwd = project.working_directory_for(file_path)
        env = project.execution_environment()
        if file_path is not None and file_path.is_file() and not dirty:
            return DebugSession.start_file(
                file_path,
                cwd=cwd,
                env=env,
                python_executable=python_executable,
            )
        return DebugSession.start(
            source,
            cwd=cwd,
            env=env,
            python_executable=python_executable,
        )
