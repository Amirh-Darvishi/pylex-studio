"""Tests for workspace file type recognition."""
import tempfile
import unittest
from pathlib import Path
from pylex.core.file_types import file_type_for, read_text_file


class FileTypeTests(unittest.TestCase):
    def test_python_source_has_python_identity(self):
        info = file_type_for("main.py")
        self.assertEqual(info.kind, "python")
        self.assertTrue(info.is_text)
        self.assertEqual(info.icon, "🐍")

    def test_common_workspace_formats_are_classified(self):
        expected = {
            "index.html": "markup",
            "app.ts": "web",
            "theme.css": "style",
            "settings.json": "data",
            "notes.md": "markup",
            "photo.png": "image",
            "movie.mp4": "video",
            "manual.pdf": "pdf",
            "bundle.zip": "archive",
            "store.sqlite": "database",
        }
        for filename, kind in expected.items():
            with self.subTest(filename=filename):
                self.assertEqual(file_type_for(filename).kind, kind)

    def test_special_project_files_are_recognized(self):
        self.assertEqual(file_type_for("Dockerfile").kind, "config")
        self.assertEqual(file_type_for(".gitignore").kind, "config")
        self.assertEqual(file_type_for("README.md").kind, "markup")

    def test_unknown_utf8_file_is_detected_as_text(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "custom.extension"
            path.write_text("hello workspace", encoding="utf-8")
            info = file_type_for(path)
            self.assertTrue(info.is_text)
            self.assertEqual(info.kind, "text")

    def test_binary_file_is_not_opened_as_editor_text(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "payload.unknown"
            path.write_bytes(b"\x00\x01\x02")
            self.assertFalse(file_type_for(path).is_text)

    def test_read_text_supports_utf8_and_rejects_binary(self):
        with tempfile.TemporaryDirectory() as folder:
            text_path = Path(folder) / "hello.txt"
            text_path.write_text("hello", encoding="utf-8")
            self.assertEqual(read_text_file(text_path), "hello")
            binary_path = Path(folder) / "image.png"
            binary_path.write_bytes(b"\x89PNG\x00")
            with self.assertRaises(UnicodeError):
                read_text_file(binary_path)


if __name__ == "__main__":
    unittest.main()
