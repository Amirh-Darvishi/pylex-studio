"""Tests for project roots and filesystem context."""
import os
import tempfile
import unittest
from pathlib import Path
from pylex.core.project import Project


class ProjectTests(unittest.TestCase):
    def test_project_normalizes_root_and_resolves_relative_paths(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Project.open(folder)
            self.assertEqual(project.root, Path(folder).resolve())
            self.assertEqual(project.resolve("src/main.py"), project.root / "src" / "main.py")

    def test_contains_and_relative_path(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            project = Project.open(root)
            nested = root / "src" / "main.py"
            self.assertTrue(project.contains(nested))
            self.assertEqual(project.relative_path(nested), Path("src/main.py"))
            self.assertFalse(project.contains(root.parent / "outside.py"))

    def test_working_directory_for_project_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            project = Project.open(root)
            # Windows may expose the same directory through an 8.3 alias
            # (for example, USERNA~1) or its long name. Compare resolved paths.
            self.assertEqual(project.working_directory_for(root / "src/main.py"), root.resolve())
            self.assertEqual(project.working_directory_for(), root.resolve())

    def test_external_file_uses_its_parent(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / "project"
            outside = Path(folder) / "outside"
            root.mkdir()
            outside.mkdir()
            self.assertEqual(
                Project.open(root).working_directory_for(outside / "a.py"),
                outside.resolve(),
            )

    def test_execution_environment_prepends_project_path(self):
        with tempfile.TemporaryDirectory() as folder:
            project = Project.open(folder)
            env = project.execution_environment({"PYTHONPATH": "existing"})
            self.assertEqual(env["PYTHONPATH"], os.pathsep.join([str(project.root), "existing"]))

    def test_invalid_project_paths_raise(self):
        with tempfile.TemporaryDirectory() as folder:
            file_path = Path(folder) / "a.py"
            file_path.write_text("pass", encoding="utf-8")
            with self.assertRaises(NotADirectoryError):
                Project.open(file_path)
            with self.assertRaises(FileNotFoundError):
                Project.open(Path(folder) / "missing")


if __name__ == "__main__":
    unittest.main()
