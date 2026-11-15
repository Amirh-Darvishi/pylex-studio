"""Tests for interpreter discovery and virtual-environment management."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

from pylex.interpreters import (
    create_virtual_environment, discover_interpreters, ensure_pip, find_project_environment,
    probe_interpreter, run_pip, virtual_environment_python,
)


class InterpreterTests(unittest.TestCase):
    def test_probe_current_interpreter(self):
        info = probe_interpreter(sys.executable)
        self.assertEqual(Path(os.path.abspath(info.executable)), Path(os.path.abspath(sys.executable)))
        self.assertTrue(info.version)
        self.assertIn(info.architecture, {"32-bit", "64-bit"})

    def test_probe_rejects_non_python_executable(self):
        with tempfile.TemporaryDirectory() as folder:
            fake = Path(folder) / ("not-python.exe" if os.name == "nt" else "not-python")
            fake.write_text("not a python executable", encoding="utf-8")
            if os.name != "nt":
                fake.chmod(0o755)
            with self.assertRaises((OSError, ValueError)):
                probe_interpreter(fake)

    def test_discovery_includes_current_interpreter_once(self):
        found = discover_interpreters()
        matches = [item for item in found
                   if os.path.abspath(item.executable) == os.path.abspath(sys.executable)]
        self.assertEqual(len(matches), 1)

    def test_create_environment_and_find_project_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            env_path = root / ".venv"
            info = create_virtual_environment(sys.executable, env_path, timeout=60)
            self.assertTrue(info.is_venv)
            self.assertEqual(Path(os.path.abspath(info.executable)),
                             Path(os.path.abspath(virtual_environment_python(env_path))))
            found = find_project_environment(root)
            self.assertIsNotNone(found)
            self.assertTrue(found.is_venv)
            from pylex.dependencies import inspect_dependencies
            dependencies, error = inspect_dependencies("import pygments", python_executable=info.executable)
            self.assertIsNone(error)
            self.assertEqual(dependencies[0].status, "missing")

    def test_create_environment_refuses_nonempty_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / ".venv"
            target.mkdir()
            (target / "keep.txt").write_text("keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                create_virtual_environment(sys.executable, target)
            self.assertEqual((target / "keep.txt").read_text(encoding="utf-8"), "keep")

    @unittest.skipIf(os.name == "nt", "Symlink creation may require elevated Windows permissions.")
    def test_create_environment_refuses_symlink_target(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            external = root / "external"
            external.mkdir()
            target = root / ".venv"
            target.symlink_to(external, target_is_directory=True)
            with self.assertRaises(ValueError):
                create_virtual_environment(sys.executable, target)
            self.assertEqual(list(external.iterdir()), [])

    def test_find_project_environment_ignores_invalid_environment(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            invalid = root / ".venv"
            python_path = virtual_environment_python(invalid)
            python_path.parent.mkdir(parents=True)
            python_path.write_text("broken", encoding="utf-8")
            self.assertIsNone(find_project_environment(root))

    def test_run_pip_uses_selected_interpreter(self):
        result = run_pip(sys.executable, ["--version"])
        self.assertEqual(result.returncode, 0)
        self.assertIn("pip", result.stdout.lower())

    def test_ensure_pip_is_idempotent_when_already_available(self):
        result = ensure_pip(sys.executable)
        self.assertEqual(result.returncode, 0)

    def test_run_pip_rejects_arbitrary_commands(self):
        with self.assertRaises(ValueError):
            run_pip(sys.executable, ["--help"])


if __name__ == "__main__":
    unittest.main()
