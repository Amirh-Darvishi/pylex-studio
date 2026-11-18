"""Tests for workspace file type recognition."""

import mimetypes
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

    def test_cached_mime_lookup_preserves_single_and_compound_extensions(self):
        for filename in ("main.py", "archive.tar.gz"):
            with self.subTest(filename=filename):
                self.assertEqual(
                    file_type_for(filename).mime_type,
                    mimetypes.guess_type(filename)[0],
                )

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
            "module.pyc": "binary",
            "native.dll": "binary",
        }
        for filename, kind in expected.items():
            with self.subTest(filename=filename):
                self.assertEqual(file_type_for(filename).kind, kind)

    def test_unknown_text_detection_reads_large_file_sample_safely(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "custom.extension"
            path.write_bytes(b"plain text\\n" + b"x" * (2 * 1024 * 1024))
            info = file_type_for(path)
            self.assertTrue(info.is_text)
            self.assertEqual(info.kind, "text")

    def test_binary_files_keep_binary_description(self):
        info = file_type_for("payload.bin")
        self.assertEqual(info.kind, "binary")
        self.assertEqual(info.description, "Binary file")

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

    def test_unknown_cp1252_file_is_detected_as_text(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "legacy.custom"
            path.write_bytes("café – résumé".encode("cp1252"))
            info = file_type_for(path)
            self.assertTrue(info.is_text)
            self.assertEqual(info.kind, "text")
            from pylex.core.file_types import read_text_file_details

            content, encoding, _newline = read_text_file_details(path)
            self.assertEqual(content, "café – résumé")
            self.assertEqual(encoding, "cp1252")

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

    def test_read_text_preserves_utf8_bom_and_newline_metadata(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "bom.txt"
            path.write_bytes(b"\xef\xbb\xbffirst\r\nsecond\r\n")
            from pylex.core.file_types import read_text_file_details

            content, encoding, newline = read_text_file_details(path)
            self.assertEqual(content, "first\r\nsecond\r\n")
            self.assertEqual(encoding, "utf-8-sig")
            self.assertEqual(newline, "\r\n")

    def test_read_text_can_be_cancelled_before_reading(self):
        import threading

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "large.txt"
            path.write_text("content", encoding="utf-8")
            cancel_event = threading.Event()
            cancel_event.set()
            from pylex.core.file_types import read_text_file_details

            with self.assertRaises(InterruptedError):
                read_text_file_details(path, cancel_event=cancel_event)

    def test_read_text_falls_back_to_windows_1252(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "legacy.txt"
            path.write_bytes("caf\xe9".encode("cp1252"))
            from pylex.core.file_types import read_text_file_details

            content, encoding, newline = read_text_file_details(path)
            self.assertEqual(content, "caf\xe9")
            self.assertEqual(encoding, "cp1252")
            self.assertEqual(newline, "\n")


if __name__ == "__main__":
    unittest.main()
