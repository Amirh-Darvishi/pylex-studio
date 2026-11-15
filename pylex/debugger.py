"""Interactive pdb-backed debugging for Python source files."""
from pathlib import Path
import os
import queue
import signal
import subprocess
import sys
import tempfile
import threading


class DebugSession:
    """Control a pdb child process and collect its interactive output."""

    def __init__(self, process, script_path):
        self.process = process
        self.script_path = Path(script_path)
        self._output = queue.Queue()
        self._reader = threading.Thread(target=self._read_output, daemon=True)
        self._reader.start()

    @classmethod
    def start(cls, source):
        script_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", encoding="utf-8", delete=False
            ) as script:
                script.write(source)
                script_path = Path(script.name)
            options = {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)} if os.name == "nt" else {"start_new_session": True}
            process = subprocess.Popen(
                [sys.executable, "-m", "pdb", str(script_path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1,
                **options,
            )
            return cls(process, script_path)
        except Exception:
            if script_path is not None:
                script_path.unlink(missing_ok=True)
            raise

    @property
    def done(self):
        return self.process.poll() is not None

    def _read_output(self):
        try:
            while True:
                chunk = self.process.stdout.read(1)
                if not chunk:
                    break
                self._output.put(chunk)
        finally:
            self._output.put(None)

    def read_available(self):
        """Return currently available debugger output without blocking."""
        chunks = []
        while True:
            try:
                item = self._output.get_nowait()
            except queue.Empty:
                break
            if item is None:
                continue
            chunks.append(item)
        return "".join(chunks)

    def wait(self, timeout=None):
        """Wait for the debugged process to exit."""
        return self.process.wait(timeout=timeout)

    def command(self, value):
        if self.done or self.process.stdin is None:
            return False
        try:
            self.process.stdin.write(value.rstrip("\n") + "\n")
            self.process.stdin.flush()
            return True
        except (BrokenPipeError, OSError, ValueError):
            return False

    def set_breakpoint(self, line):
        return self.command(f"b {int(line)}")

    def clear_breakpoint(self, line):
        return self.command(f"cl {int(line)}")

    def continue_execution(self):
        return self.command("c")

    def step(self):
        return self.command("s")

    def next(self):
        return self.command("n")

    def inspect_variables(self):
        return self.command("p locals()")

    def evaluate(self, expression):
        """Evaluate a Python expression in the current paused frame."""
        expression = str(expression).strip()
        if not expression or "\n" in expression:
            return False
        return self.command(f"p {expression}")

    def stop(self):
        """Force-stop the debugger and every process spawned beneath it."""
        if self.done:
            return False
        try:
            if os.name == "nt":
                subprocess.run(
                    ["taskkill", "/PID", str(self.process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    check=False, timeout=5,
                )
            else:
                os.killpg(self.process.pid, signal.SIGKILL)
        except (OSError, subprocess.SubprocessError):
            try:
                self.process.kill()
            except OSError:
                pass
        return True

    def close(self):
        if not self.done:
            self.stop()
        try:
            self.process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        self._reader.join(timeout=1)
        for stream in (self.process.stdin, self.process.stdout):
            if stream is not None:
                try:
                    stream.close()
                except OSError:
                    pass
        try:
            self.script_path.unlink(missing_ok=True)
        except OSError:
            pass
