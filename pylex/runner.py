"""Run Python source in a child process with timeout and cancellation support."""
from dataclasses import dataclass
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time


@dataclass(frozen=True)
class ExecutionResult:
    """Immutable result returned when a child process finishes."""

    stdout: str
    stderr: str
    exit_code: int
    status: str
    duration: float


class ExecutionHandle:
    """Thread-safe handle for observing and stopping a running Python process."""

    def __init__(self, process, script_path, timeout):
        self.process = process
        self.script_path = Path(script_path)
        self.timeout = timeout
        self.started_at = time.monotonic()
        self._done = threading.Event()
        self._lock = threading.Lock()
        self._stop_requested = False
        self._result = None
        self._thread = threading.Thread(target=self._collect, daemon=True)
        self._thread.start()

    @property
    def done(self):
        return self._done.is_set()

    @property
    def result(self):
        with self._lock:
            return self._result

    def stop(self):
        """Stop the child process if it is still running."""
        with self._lock:
            if self._done.is_set():
                return False
            self._stop_requested = True
        if self.process.poll() is None:
            try:
                self.process.kill()
            except OSError:
                pass
        return True

    def wait(self, timeout=None):
        """Wait for completion and return the result, or None on wait timeout."""
        if not self._done.wait(timeout):
            return None
        return self.result

    def _collect(self):
        stdout = stderr = ""
        status = "finished"
        exit_code = -1
        try:
            try:
                stdout, stderr = self.process.communicate(timeout=self.timeout)
                exit_code = self.process.returncode
            except subprocess.TimeoutExpired:
                status = "timed_out"
                self.process.kill()
                stdout, stderr = self.process.communicate()
                exit_code = self.process.returncode
                message = f"Execution timed out after {self.timeout:g} seconds."
                stderr = (stderr + "\n" if stderr else "") + message
            with self._lock:
                if self._stop_requested:
                    status = "stopped"
                    message = "Execution stopped by user."
                    stderr = (stderr + "\n" if stderr else "") + message
        except Exception as exc:
            status = "failed"
            stderr = (stderr + "\n" if stderr else "") + f"{type(exc).__name__}: {exc}"
        finally:
            try:
                self.script_path.unlink(missing_ok=True)
            except OSError:
                pass
            result = ExecutionResult(
                stdout=stdout or "",
                stderr=stderr or "",
                exit_code=exit_code,
                status=status,
                duration=max(0.0, time.monotonic() - self.started_at),
            )
            with self._lock:
                self._result = result
            self._done.set()


def start_source(source, timeout=10):
    """Start source asynchronously and immediately return an ExecutionHandle.

    Code runs with the current user's permissions. This is not a security sandbox.
    """
    script_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", encoding="utf-8", delete=False
        ) as script:
            script.write(source)
            script_path = Path(script.name)
        process = subprocess.Popen(
            [sys.executable, str(script_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return ExecutionHandle(process, script_path, timeout)
    except Exception:
        if script_path is not None:
            script_path.unlink(missing_ok=True)
        raise


def run_source(source, timeout=10):
    """Backward-compatible blocking API returning stdout, stderr, and exit code."""
    result = start_source(source, timeout=timeout).wait()
    return result.stdout, result.stderr, result.exit_code
