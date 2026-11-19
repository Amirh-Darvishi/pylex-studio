"""Unit tests for integrated terminal helpers."""

import os
import shlex
import sys
import time
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from pylex.terminal import (
    TerminalProcess,
    shell_command,
    terminal_environment,
    python_file_command,
)


class TerminalHelperTests(unittest.TestCase):
    def test_rejects_unknown_shell(self):
        with self.assertRaises(ValueError):
            shell_command("unknown-shell")

    def test_powershell_uses_non_profile_interactive_command(self):
        with (
            patch("pylex.terminal.os.name", "nt"),
            patch(
                "pylex.terminal.shutil.which",
                side_effect=lambda name: (
                    r"C:\PowerShell\pwsh.exe" if name == "pwsh" else None
                ),
            ),
        ):
            command = shell_command("powershell")
        self.assertEqual(command[0], r"C:\PowerShell\pwsh.exe")
        self.assertIn("-NoProfile", command)
        self.assertIn("-NoExit", command)
        self.assertNotIn("-Command", command)

    def test_cmd_uses_windows_command_processor(self):
        with (
            patch("pylex.terminal.os.name", "nt"),
            patch.dict(os.environ, {"COMSPEC": r"C:\Windows\System32\cmd.exe"}),
        ):
            self.assertEqual(shell_command("cmd")[-2:], ["/Q", "/K"])

    def test_selected_venv_is_preferred_in_path(self):
        base = {"PATH": "system-path", "PYTHONHOME": "invalid"}
        env = terminal_environment(base, r"C:\project\.venv\Scripts\python.exe")
        self.assertTrue(env["PATH"].startswith(r"C:\project\.venv\Scripts"))
        self.assertEqual(env["VIRTUAL_ENV"], r"C:\project\.venv")
        self.assertNotIn("PYTHONHOME", env)

    def test_python_file_command_quotes_paths_for_supported_shells(self):
        command = python_file_command(
            "powershell",
            r"C:\Program Files\Python\python.exe",
            r"C:\Project Files\main.py",
        )
        self.assertEqual(
            command,
            r"& 'C:\Program Files\Python\python.exe' 'C:\Project Files\main.py'",
        )
        bash_command = python_file_command(
            "bash",
            "/opt/python/bin/python",
            "/home/user/My Project/main.py",
        )
        self.assertIn("'/home/user/My Project/main.py'", bash_command)

    def test_active_editor_context_is_preserved_in_terminal_environment(self):
        base = {
            "PATH": "system-path",
            "PYLEX_ACTIVE_FILE": r"C:\workspace\src\main.py",
            "PYLEX_WORKSPACE_ROOT": r"C:\workspace",
        }
        env = terminal_environment(base)
        self.assertEqual(env["PYLEX_ACTIVE_FILE"], r"C:\workspace\src\main.py")
        self.assertEqual(env["PYLEX_WORKSPACE_ROOT"], r"C:\workspace")

    def test_base_environment_is_not_mutated(self):
        base = {"PATH": "original"}
        terminal_environment(base, r"C:\venv\Scripts\python.exe")
        self.assertEqual(base, {"PATH": "original"})

    def test_read_available_respects_chunk_limit(self):
        session = TerminalProcess.__new__(TerminalProcess)
        session.events = __import__("queue").Queue()
        session.events.put("first")
        session.events.put("second")
        session.events.put("third")

        self.assertEqual(session.read_available(max_chunks=2), ["first", "second"])
        self.assertEqual(session.read_available(max_chunks=1), ["third"])
        self.assertEqual(session.read_available(max_chunks=1), [])

    @unittest.skipIf(os.name == "nt", "POSIX process-group semantics")
    def test_shell_exit_cleans_up_child_holding_terminal_pipe(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "terminal-child-survived"
            child = (
                "import time; from pathlib import Path; "
                "time.sleep(2); Path(" + repr(str(marker)) + ").write_text('alive')"
            )
            session = TerminalProcess.start("sh", cwd=directory)
            try:
                command = shlex.join([sys.executable, "-c", child]) + " &"
                session.send(command)
                session.send("exit")
                self.assertTrue(session.done.wait(5))
                time.sleep(2.2)
                self.assertFalse(marker.exists())
            finally:
                if not session.done.is_set():
                    session.stop()
                    session.done.wait(3)


if __name__ == "__main__":
    unittest.main()
