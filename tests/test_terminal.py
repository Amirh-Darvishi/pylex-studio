"""Unit tests for integrated terminal helpers."""
import os
import unittest
from unittest.mock import patch
from pylex.terminal import shell_command, terminal_environment

class TerminalHelperTests(unittest.TestCase):
    def test_rejects_unknown_shell(self):
        with self.assertRaises(ValueError):
            shell_command("unknown-shell")

    def test_powershell_uses_non_profile_interactive_command(self):
        with patch("pylex.terminal.os.name", "nt"), patch(
            "pylex.terminal.shutil.which",
            side_effect=lambda name: r"C:\PowerShell\pwsh.exe" if name == "pwsh" else None
        ):
            command = shell_command("powershell")
        self.assertEqual(command[0], r"C:\PowerShell\pwsh.exe")
        self.assertIn("-NoProfile", command)
        self.assertIn("-NoExit", command)
        self.assertNotIn("-Command", command)

    def test_cmd_uses_windows_command_processor(self):
        with patch("pylex.terminal.os.name", "nt"), patch.dict(
            os.environ, {"COMSPEC": r"C:\Windows\System32\cmd.exe"}
        ):
            self.assertEqual(shell_command("cmd")[-2:], ["/Q", "/K"])

    def test_selected_venv_is_preferred_in_path(self):
        base = {"PATH": "system-path", "PYTHONHOME": "invalid"}
        env = terminal_environment(base, r"C:\project\.venv\Scripts\python.exe")
        self.assertTrue(env["PATH"].startswith(r"C:\project\.venv\Scripts"))
        self.assertEqual(env["VIRTUAL_ENV"], r"C:\project\.venv")
        self.assertNotIn("PYTHONHOME", env)

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

if __name__ == "__main__":
    unittest.main()
