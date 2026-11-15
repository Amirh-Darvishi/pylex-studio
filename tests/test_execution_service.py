"""Tests for project-aware process orchestration."""
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from pylex.core.project import Project
from pylex.services.execution import ExecutionService


class ExecutionServiceTests(unittest.TestCase):
    def test_saved_file_runs_from_real_path_and_imports_sibling(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "helper.py").write_text("VALUE = 'from-helper'\n", encoding="utf-8")
            script = root / "main.py"
            script.write_text("from helper import VALUE\nprint(VALUE)\n", encoding="utf-8")
            handle = ExecutionService().start_document(
                script.read_text(encoding="utf-8"), script, Project.open(root), timeout=5,
            )
            self.assertEqual(handle.script_path, script.resolve())
            result = handle.wait(5)
            self.assertEqual(result.status, "finished")
            self.assertEqual(result.stdout.strip(), "from-helper")
            self.assertTrue(script.exists())

    def test_unsaved_source_uses_project_import_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "helper.py").write_text("VALUE = 42\n", encoding="utf-8")
            handle = ExecutionService().start_document(
                "from helper import VALUE\nprint(VALUE)\n", None, Project.open(root), timeout=5,
            )
            result = handle.wait(5)
            self.assertEqual(result.status, "finished")
            self.assertEqual(result.stdout.strip(), "42")

    def test_selected_interpreter_is_forwarded_for_unsaved_source(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Project.open(folder)
            with patch("pylex.services.execution.start_source") as starter:
                ExecutionService().start_document(
                    "print('ok')", None, project, dirty=True,
                    python_executable=sys.executable,
                )
            self.assertEqual(starter.call_args.kwargs["python_executable"], sys.executable)

    def test_selected_interpreter_is_forwarded_for_debugger(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Project.open(folder)
            with patch("pylex.services.execution.DebugSession.start") as starter:
                ExecutionService().start_debugger_document(
                    "print('ok')", None, project, dirty=True,
                    python_executable=sys.executable,
                )
            self.assertEqual(starter.call_args.kwargs["python_executable"], sys.executable)

    def test_dirty_saved_buffer_runs_buffer_not_disk_content(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            script = root / "main.py"
            script.write_text("print('disk')\n", encoding="utf-8")
            handle = ExecutionService().start_document(
                "print('buffer')\n", script, Project.open(root), timeout=5, dirty=True,
            )
            self.assertNotEqual(handle.script_path, script.resolve())
            self.assertEqual(handle.wait(5).stdout.strip(), "buffer")


if __name__ == "__main__":
    unittest.main()
