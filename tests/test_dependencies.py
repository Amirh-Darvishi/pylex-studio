"""Tests for project dependency inspection."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pylex.dependencies import (
    inspect_dependencies, find_missing_imports, python_environment,
)


class DependencyInspectionTests(unittest.TestCase):
    def test_standard_library_is_classified(self):
        items, error = inspect_dependencies("import json\nfrom pathlib import Path")
        self.assertIsNone(error)
        self.assertEqual({item.status for item in items}, {"standard"})

    def test_local_project_module_is_classified(self):
        with tempfile.TemporaryDirectory() as folder:
            Path(folder, "my_helper.py").write_text("VALUE = 1", encoding="utf-8")
            items, error = inspect_dependencies("import my_helper", search_root=folder)
        self.assertIsNone(error)
        self.assertEqual(items[0].status, "local")

    def test_missing_package_uses_known_distribution_name(self):
        with patch("pylex.dependencies.importlib.util.find_spec", return_value=None), \
             patch("pylex.dependencies.importlib.metadata.packages_distributions", return_value={}):
            items, error = inspect_dependencies("import cv2")
        self.assertIsNone(error)
        self.assertEqual(items[0].status, "missing")
        self.assertEqual(items[0].distribution, "opencv-python")
        self.assertEqual(find_missing_imports("import cv2"), [("cv2", "opencv-python")])

    def test_installed_module_reports_version_and_location(self):
        spec = type("Spec", (), {"origin": "/site-packages/example.py"})()
        with patch("pylex.dependencies.importlib.util.find_spec", return_value=spec), \
             patch("pylex.dependencies.importlib.metadata.packages_distributions", return_value={"example": ["example-dist"]}), \
             patch("pylex.dependencies.importlib.metadata.version", return_value="2.4.1"):
            items, error = inspect_dependencies("import example")
        self.assertIsNone(error)
        self.assertEqual(items[0].status, "installed")
        self.assertEqual(items[0].version, "2.4.1")
        self.assertEqual(items[0].location, "/site-packages/example.py")

    def test_syntax_error_returns_scan_diagnostic(self):
        items, error = inspect_dependencies("import (")
        self.assertEqual(items, [])
        self.assertIn("line 1", error)

    def test_environment_reports_active_interpreter(self):
        env = python_environment()
        self.assertEqual(env["executable"], __import__("sys").executable)
        self.assertIn("version", env)

    def test_reports_missing_third_party_module(self):
        missing = find_missing_imports("import pylex_studio_test_missing_package_xyz")
        self.assertIn(
            ("pylex_studio_test_missing_package_xyz", "pylex_studio_test_missing_package_xyz"),
            missing,
        )

    def test_ignores_standard_library(self):
        self.assertEqual(
            find_missing_imports("import os\nimport json\nfrom pathlib import Path"), []
        )

    def test_maps_common_distribution_names(self):
        missing = find_missing_imports("import cv2\nimport yaml")
        self.assertIn(("cv2", "opencv-python"), missing)
        self.assertIn(("yaml", "PyYAML"), missing)

    def test_invalid_source_does_not_crash_preflight(self):
        self.assertEqual(find_missing_imports("import ("), [])


if __name__ == "__main__":
    unittest.main()
