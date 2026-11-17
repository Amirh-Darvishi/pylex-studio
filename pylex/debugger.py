"""Interactive pdb-backed debugging for Python source files."""

from pathlib import Path
import codecs
import os
import queue
import subprocess
import sys
import tempfile
import threading

from .process_control import (
    attach_process_job,
    terminate_process_tree,
)


class DebugSession:
    """Control a pdb child process and collect its interactive output."""

    def __init__(self, process, script_path, cleanup_script=True):
        self.process = process
        self.script_path = Path(script_path)
        self.cleanup_script = cleanup_script
        self.completion_status = None
        self._stdin_lock = threading.Lock()
        self._completion_sent = False
        self._output = queue.Queue()
        self._reader = threading.Thread(target=self._read_output, daemon=True)
        self._reader.start()

    @classmethod
    def start(cls, source, cwd=None, env=None, python_executable=None):
        """Start pdb for unsaved source in the supplied project context."""
        script_path = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".py", encoding="utf-8", delete=False
            ) as script:
                script.write(source)
                script_path = Path(script.name)
            options = (
                {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
                if os.name == "nt"
                else {"start_new_session": True}
            )
            process = subprocess.Popen(
                [
                    str(python_executable or sys.executable),
                    "-u",
                    "-m",
                    "pdb",
                    str(script_path),
                ],
                cwd=str(cwd) if cwd is not None else None,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=False,
                bufsize=0,
                **options,
            )
            attach_process_job(process)
            return cls(process, script_path)
        except Exception:
            if script_path is not None:
                script_path.unlink(missing_ok=True)
            raise

    @classmethod
    def start_file(cls, path, cwd=None, env=None, python_executable=None):
        """Start pdb against a real source file, preserving its actual path."""
        script_path = Path(path).expanduser().resolve()
        if not script_path.is_file():
            raise FileNotFoundError(f"Python file does not exist: {script_path}")
        options = (
            {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
            if os.name == "nt"
            else {"start_new_session": True}
        )
        process = subprocess.Popen(
            [
                str(python_executable or sys.executable),
                "-u",
                "-m",
                "pdb",
                str(script_path),
            ],
            cwd=str(cwd) if cwd is not None else None,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=False,
            bufsize=0,
            **options,
        )
        attach_process_job(process)
        return cls(process, script_path, cleanup_script=False)

    @property
    def done(self):
        return self.process.poll() is not None

    def _read_output(self):
        """Collect raw pdb output and close the session when the debuggee finishes."""
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        line_buffer = ""
        pending_completion = None
        try:
            while True:
                data = os.read(self.process.stdout.fileno(), 4096)
                if not data:
                    break
                chunk = decoder.decode(data)
                if not chunk:
                    continue
                self._output.put(chunk)
                line_buffer = (line_buffer + chunk)[-1024:]
                while "\n" in line_buffer and not self._completion_sent:
                    line, line_buffer = line_buffer.split("\n", 1)
                    line = line.strip()
                    if (
                        line == "The program finished and will be restarted"
                        or line == "The program exited"
                    ):
                        pending_completion = "finished"
                    elif "Uncaught exception. Entering post mortem debugging" in line:
                        pending_completion = "error"
                    elif "Post mortem debugger finished." in line:
                        # Python 3.10/3.11 restart pdb after leaving post-mortem.
                        # A second quit is required at the fresh initial prompt.
                        pending_completion = "error_restart_prompt"
                    elif pending_completion == "finished" and line.startswith("> "):
                        # A successful run returns to the original script frame.
                        self.completion_status = "finished"
                        self._completion_sent = True
                        self.command("q")
                # Post-mortem pdb prints its prompt without a trailing newline.
                # Wait for that prompt after the exception marker, then quit pdb.
                # This also works when the frame path is abbreviated on Windows.
                if (
                    pending_completion == "error"
                    and not self._completion_sent
                    and "(Pdb) " in line_buffer
                ):
                    # First quit leaves post-mortem. Older pdb versions then
                    # restart the script and present a second, initial prompt.
                    self.completion_status = "error"
                    pending_completion = "error_restart"
                    self.command("q")
                elif (
                    pending_completion == "error_restart_prompt"
                    and not self._completion_sent
                    and "(Pdb) " in line_buffer
                ):
                    # The post-mortem-finished line and the new prompt may
                    # arrive in one OS read; handle that chunk boundary too.
                    self._completion_sent = True
                    self.command("q")
            tail = decoder.decode(b"", final=True)
            if tail:
                self._output.put(tail)
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
        value = str(value)
        if any(char in value for char in ("\n", "\r", "\x00")):
            return False
        try:
            with self._stdin_lock:
                if self.done:
                    return False
                self.process.stdin.write((value + "\n").encode("utf-8"))
                self.process.stdin.flush()
            return True
        except (BrokenPipeError, OSError, ValueError):
            return False

    def send_input(self, value):
        """Send one input line to a debugged program waiting in input()."""
        value = str(value)
        if "\x00" in value or "\n" in value or "\r" in value or self.done:
            return False
        try:
            with self._stdin_lock:
                if self.done:
                    return False
                self.process.stdin.write((value + "\n").encode("utf-8"))
                self.process.stdin.flush()
            return True
        except (BrokenPipeError, OSError, ValueError):
            return False

    @staticmethod
    def _positive_number(value, label="number"):
        try:
            number = int(value)
        except (TypeError, ValueError):
            raise ValueError(f"{label} must be a positive integer.") from None
        if number < 1:
            raise ValueError(f"{label} must be a positive integer.")
        return number

    @staticmethod
    def _single_line(value, label="value"):
        value = str(value).strip()
        if not value or any(char in value for char in ("\n", "\r", "\x00")):
            raise ValueError(f"{label} must be a non-empty single line.")
        return value

    def set_breakpoint(self, line):
        """Set a source-line breakpoint after validating its line number."""
        return self.command(f"b {self._positive_number(line, 'Line number')}")

    def set_conditional_breakpoint(self, line, condition):
        """Set a breakpoint that is active only when its expression is true."""
        line = self._positive_number(line, "Line number")
        condition = self._single_line(condition, "Breakpoint condition")
        return self.command(f"b {line}, {condition}")

    def set_temporary_breakpoint(self, line):
        """Set a one-shot breakpoint."""
        return self.command(f"tbreak {self._positive_number(line, 'Line number')}")

    def clear_breakpoint(self, line):
        return self.command(f"cl {self._positive_number(line, 'Line number')}")

    def clear_all_breakpoints(self):
        """Remove all breakpoints, confirming pdb's interactive prompt."""
        if not self.command("cl"):
            return False
        return self.command("y")

    def enable_breakpoint(self, number):
        return self.command(
            f"enable {self._positive_number(number, 'Breakpoint number')}"
        )

    def disable_breakpoint(self, number):
        return self.command(
            f"disable {self._positive_number(number, 'Breakpoint number')}"
        )

    def ignore_breakpoint(self, number, count):
        number = self._positive_number(number, "Breakpoint number")
        count = self._positive_number(count, "Ignore count")
        return self.command(f"ignore {number} {count}")

    def continue_execution(self):
        return self.command("c")

    def step(self):
        return self.command("s")

    def next(self):
        return self.command("n")

    def until(self, line=None):
        """Run until the current frame reaches a later line, or a target line."""
        return self.command(
            "until"
            if line is None
            else f"until {self._positive_number(line, 'Line number')}"
        )

    def return_from_frame(self):
        """Continue until the current function returns."""
        return self.command("return")

    def jump(self, line):
        """Move the current frame's next execution line (pdb restrictions apply)."""
        return self.command(f"jump {self._positive_number(line, 'Line number')}")

    def inspect_variables(self):
        return self.command("p locals()")

    def show_arguments(self):
        return self.command("args")

    def pretty_print(self, expression):
        expression = self._single_line(expression, "Expression")
        return self.command(f"pp {expression}")

    def evaluate(self, expression):
        """Evaluate a Python expression in the current paused frame."""
        expression = self._single_line(expression, "Expression")
        return self.command(f"p {expression}")

    def stop(self):
        """Force-stop the debugger and every process spawned beneath it."""
        if self.done:
            return terminate_process_tree(self.process)
        terminate_process_tree(self.process)
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
        # A completed debuggee can still have descendants without inherited pipes.
        terminate_process_tree(self.process)
        self._reader.join(timeout=2)
        with self._stdin_lock:
            if self.process.stdin is not None:
                try:
                    self.process.stdin.close()
                except (OSError, ValueError):
                    pass
        if self.process.stdout is not None:
            try:
                self.process.stdout.close()
            except (OSError, ValueError):
                pass
        if self.cleanup_script:
            try:
                self.script_path.unlink(missing_ok=True)
            except OSError:
                pass
