"""Run Python source in an isolated process group with streaming output and cancellation."""
from dataclasses import dataclass
import os
from pathlib import Path
import queue
import signal
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


def _terminate_process_tree(process):
    """Terminate the process and descendants, not only the Python parent."""
    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                check=False, timeout=5,
            )
        else:
            os.killpg(process.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError):
        try:
            process.kill()
        except OSError:
            pass


class ExecutionHandle:
    """Thread-safe handle exposing live stdout/stderr and force-stop support."""

    def __init__(self, process, script_path, timeout, cleanup_script=True):
        self.process = process
        self.script_path = Path(script_path)
        self.timeout = timeout
        self.cleanup_script = cleanup_script
        self.started_at = time.monotonic()
        self._done = threading.Event()
        self._lock = threading.Lock()
        self._stop_requested = False
        self._input_lock = threading.Lock()
        self._result = None
        self._events = queue.Queue()
        self._stdout_parts = []
        self._stderr_parts = []
        self._readers = [
            threading.Thread(target=self._read_stream, args=(process.stdout, "stdout"),
                             daemon=True),
            threading.Thread(target=self._read_stream, args=(process.stderr, "stderr"),
                             daemon=True),
        ]
        for reader in self._readers:
            reader.start()
        self._thread = threading.Thread(target=self._collect, daemon=True)
        self._thread.start()

    @property
    def done(self):
        return self._done.is_set()

    @property
    def result(self):
        with self._lock:
            return self._result

    def _read_stream(self, stream, channel):
        parts = self._stdout_parts if channel == "stdout" else self._stderr_parts
        try:
            for line in iter(stream.readline, ""):
                parts.append(line)
                self._events.put((channel, line))
        except (OSError, ValueError):
            pass
        finally:
            try:
                stream.close()
            except OSError:
                pass

    def read_available(self):
        """Return queued live output as (channel, text) pairs without blocking."""
        chunks = []
        while True:
            try:
                chunks.append(self._events.get_nowait())
            except queue.Empty:
                return chunks

    def send_input(self, value):
        """Send one line of interactive input to the running program."""
        if self.done or self.process.stdin is None:
            return False
        value = str(value)
        if "\x00" in value:
            raise ValueError("Program input cannot contain a NUL character.")
        with self._input_lock:
            if self.done or self.process.poll() is not None:
                return False
            try:
                self.process.stdin.write(value + "\n")
                self.process.stdin.flush()
                return True
            except (BrokenPipeError, OSError, ValueError):
                return False

    def close_input(self):
        """Send EOF to a program that no longer needs interactive input."""
        with self._input_lock:
            try:
                if self.process.stdin is not None and not self.process.stdin.closed:
                    self.process.stdin.close()
            except OSError:
                pass

    def stop(self):
        """Force-stop the process tree so descendants cannot keep pipes alive."""
        with self._lock:
            if self._done.is_set():
                return False
            self._stop_requested = True
        _terminate_process_tree(self.process)
        return True

    force_stop = stop

    def wait(self, timeout=None):
        """Wait for completion and return the result, or None on wait timeout."""
        if not self._done.wait(timeout):
            return None
        return self.result

    def _collect(self):
        status = "finished"
        try:
            try:
                self.process.wait(timeout=self.timeout)
            except subprocess.TimeoutExpired:
                status = "timed_out"
                _terminate_process_tree(self.process)
                self.process.wait()
            for reader in self._readers:
                reader.join(timeout=3)
            with self._lock:
                if self._stop_requested:
                    status = "stopped"
            stdout = "".join(self._stdout_parts)
            stderr = "".join(self._stderr_parts)
            if status == "timed_out":
                stderr += ("\n" if stderr else "") + (
                    f"Execution timed out after {self.timeout:g} seconds."
                )
            elif status == "stopped":
                stderr += ("\n" if stderr else "") + "Execution force-stopped by user."
            exit_code = self.process.returncode
        except Exception as exc:
            status = "failed"
            stdout = "".join(self._stdout_parts)
            stderr = "".join(self._stderr_parts)
            stderr += ("\n" if stderr else "") + f"{type(exc).__name__}: {exc}"
            exit_code = self.process.poll()
            if exit_code is None:
                _terminate_process_tree(self.process)
                self.process.wait()
                exit_code = self.process.returncode
        finally:
            if self.cleanup_script:
                try:
                    self.script_path.unlink(missing_ok=True)
                except OSError:
                    pass
            result = ExecutionResult(
                stdout=stdout or "", stderr=stderr or "",
                exit_code=exit_code if exit_code is not None else -1,
                status=status,
                duration=max(0.0, time.monotonic() - self.started_at),
            )
            with self._lock:
                self._result = result
            self._done.set()


def _process_options():
    """Return platform-specific options for a cancellable child process."""
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    return {"start_new_session": True}


def start_source(source, timeout=10, cwd=None, env=None, python_executable=None):
    """Start unsaved source in an explicit project context. Code is not sandboxed."""
    script_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", encoding="utf-8", delete=False) as script:
            script.write(source)
            script_path = Path(script.name)
        process = subprocess.Popen(
            [str(python_executable or sys.executable), "-u", str(script_path)],
            cwd=str(cwd) if cwd is not None else None, env=env,
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, encoding="utf-8", errors="replace", bufsize=1,
            **_process_options(),
        )
        return ExecutionHandle(process, script_path, timeout)
    except Exception:
        if script_path is not None:
            script_path.unlink(missing_ok=True)
        raise


def start_file(path, timeout=10, cwd=None, env=None, python_executable=None):
    """Run a saved Python file by its real path without copying it to a temp file."""
    script_path = Path(path).expanduser().resolve()
    if not script_path.is_file():
        raise FileNotFoundError(f"Python file does not exist: {script_path}")
    process = subprocess.Popen(
        [str(python_executable or sys.executable), "-u", str(script_path)],
        cwd=str(cwd) if cwd is not None else None, env=env,
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", errors="replace", bufsize=1,
        **_process_options(),
    )
    return ExecutionHandle(process, script_path, timeout, cleanup_script=False)


def run_source(source, timeout=10):
    """Backward-compatible blocking API returning stdout, stderr, and exit code."""
    result = start_source(source, timeout=timeout).wait()
    exit_code = -1 if result.status == "timed_out" else result.exit_code
    return result.stdout, result.stderr, exit_code
