"""Tests for persisted UI preferences."""
import json
import tempfile
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from pylex.preferences import DEFAULTS, load_preferences, save_preferences


class PreferencesTests(unittest.TestCase):
    def test_defaults_are_returned_when_file_is_missing(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("pylex.preferences.Path.home", return_value=Path(folder)):
                self.assertEqual(load_preferences(), DEFAULTS)

    def test_preferences_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("pylex.preferences.Path.home", return_value=Path(folder)):
                values = dict(DEFAULTS)
                values.update(theme="light", font_family="Cascadia Code", font_size=16,
                              ui_font_family="Segoe UI", ui_font_size=10)
                save_preferences(values)
                loaded = load_preferences()
                self.assertEqual(loaded["theme"], "light")
                self.assertEqual(loaded["font_family"], "Cascadia Code")
                self.assertEqual(loaded["font_size"], 16)
                self.assertEqual(loaded["ui_font_family"], "Segoe UI")
                self.assertEqual(loaded["ui_font_size"], 10)

    def test_timeout_preference_round_trip_and_unlimited(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("pylex.preferences.Path.home", return_value=Path(folder)):
                values = dict(DEFAULTS)
                values["timeout_seconds"] = None
                save_preferences(values)
                self.assertIsNone(load_preferences()["timeout_seconds"])
                values["timeout_seconds"] = 30
                save_preferences(values)
                self.assertEqual(load_preferences()["timeout_seconds"], 30)

    def test_invalid_timeout_is_reset_to_default(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("pylex.preferences.Path.home", return_value=Path(folder)):
                path = Path(folder) / ".pylex_studio.json"
                path.write_text(json.dumps({"timeout_seconds": 999}), encoding="utf-8")
                self.assertEqual(load_preferences()["timeout_seconds"], 10)

    def test_interpreter_preferences_round_trip(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("pylex.preferences.Path.home", return_value=Path(folder)):
                values = dict(DEFAULTS)
                values["interpreter_path"] = sys.executable
                values["project_interpreters"] = {"/workspace": "/python"}
                values["recent_workspaces"] = ["/one", "/two"]
                save_preferences(values)
                loaded = load_preferences()
                self.assertEqual(loaded["interpreter_path"], sys.executable)
                self.assertEqual(loaded["project_interpreters"], values["project_interpreters"])
                self.assertEqual(loaded["recent_workspaces"], values["recent_workspaces"])

    def test_failed_atomic_replace_preserves_existing_preferences(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("pylex.preferences.Path.home", return_value=Path(folder)):
                path = Path(folder) / ".pylex_studio.json"
                original = json.dumps({"theme": "light"})
                path.write_text(original, encoding="utf-8")
                with patch("pylex.preferences.os.replace", side_effect=OSError("locked")):
                    with self.assertRaisesRegex(OSError, "locked"):
                        save_preferences({"theme": "dark"})
                self.assertEqual(path.read_text(encoding="utf-8"), original)
                self.assertEqual(list(Path(folder).glob(".pylex_studio.json.*.tmp")), [])

    def test_invalid_values_are_normalized(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch("pylex.preferences.Path.home", return_value=Path(folder)):
                path = Path(folder) / ".pylex_studio.json"
                path.write_text(json.dumps({
                    "theme": "neon", "font_family": "Missing Font", "font_size": 1000,
                }), encoding="utf-8")
                loaded = load_preferences()
                self.assertEqual(loaded["theme"], DEFAULTS["theme"])
                self.assertEqual(loaded["font_family"], DEFAULTS["font_family"])
                self.assertEqual(loaded["font_size"], 40)
                self.assertEqual(loaded["ui_font_size"], DEFAULTS["ui_font_size"])


if __name__ == "__main__":
    unittest.main()
