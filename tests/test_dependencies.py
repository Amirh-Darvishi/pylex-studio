"""Tests for third-party dependency preflight reporting."""
import unittest
from pylex.dependencies import find_missing_imports


class DependencyTests(unittest.TestCase):
    def test_reports_missing_third_party_module(self):
        missing = find_missing_imports("import pylex_studio_test_missing_package_xyz")
        self.assertIn(
            ("pylex_studio_test_missing_package_xyz",
             "pylex_studio_test_missing_package_xyz"),
            missing,
        )

    def test_ignores_standard_library(self):
        self.assertEqual(find_missing_imports("import os\nimport json\nfrom pathlib import Path"), [])

    def test_maps_common_distribution_names(self):
        missing = find_missing_imports("import cv2\nimport yaml")
        self.assertIn(("cv2", "opencv-python"), missing)
        self.assertIn(("yaml", "PyYAML"), missing)

    def test_invalid_source_does_not_crash_preflight(self):
        self.assertEqual(find_missing_imports("import ("), [])


if __name__ == "__main__":
    unittest.main()
