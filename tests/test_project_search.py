"""Regression tests for workspace search and replacement services."""

import tempfile
import threading
import unittest
from pathlib import Path

from pylex.project_search import (
    build_replacements, compile_search_pattern, iter_search_files,
    read_text_snapshot, search_text, write_replacements,
)


class ProjectSearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def test_literal_search_is_case_insensitive_by_default(self):
        (self.root / "main.py").write_text("Print('Hello')\n", encoding="utf-8")
        matches, _ = search_text(self.root, "print")
        self.assertEqual([(item.line, item.column) for item in matches], [(1, 1)])

    def test_regex_whole_word_and_case_options(self):
        pattern = compile_search_pattern(r"foo", regex=True, case_sensitive=True,
                                          whole_word=True)
        self.assertEqual([m.start() for m in pattern.finditer("foo foobar xfoo")], [0])

    def test_invalid_regex_has_actionable_error(self):
        with self.assertRaisesRegex(ValueError, "Invalid regular expression"):
            compile_search_pattern("[", regex=True)

    def test_file_glob_and_generated_directories_are_excluded(self):
        (self.root / "a.py").write_text("needle", encoding="utf-8")
        (self.root / "a.txt").write_text("needle", encoding="utf-8")
        ignored = self.root / ".venv"
        ignored.mkdir()
        (ignored / "hidden.py").write_text("needle", encoding="utf-8")
        self.assertEqual([p.name for p in iter_search_files(self.root,
                                                            include_glob="*.py")],
                         ["a.py"])

    def test_large_files_and_binary_files_are_skipped(self):
        (self.root / "large.py").write_bytes(b"x" * 40)
        (self.root / "binary.py").write_bytes(b"\x00\xff\x00")
        matches, _ = search_text(self.root, "x", max_file_bytes=20)
        self.assertEqual(matches, [])

    def test_unsaved_overlay_takes_precedence_over_disk(self):
        path = self.root / "open.py"
        path.write_text("old text", encoding="utf-8")
        matches, _ = search_text(self.root, "new", overlays={path: "new text"})
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].text, "new text")

    def test_cancelled_search_stops_before_scanning(self):
        event = threading.Event()
        event.set()
        (self.root / "main.py").write_text("needle", encoding="utf-8")
        matches, _ = search_text(self.root, "needle", cancel_event=event)
        self.assertEqual(matches, [])

    def test_replacement_preview_is_pure(self):
        updated, count = build_replacements("one one", compile_search_pattern("one"),
                                            "two")
        self.assertEqual((updated, count), ("two two", 2))

    def test_atomic_replacement_preserves_crlf_and_bom(self):
        path = self.root / "bom.py"
        path.write_bytes(b"\xef\xbb\xbfhello\r\nhello")
        snapshot = read_text_snapshot(path)
        written = write_replacements({path: "world\nworld"}, {path: snapshot})
        self.assertEqual(written, [path])
        self.assertEqual(path.read_bytes(), b"\xef\xbb\xbfworld\r\nworld")

    def test_changed_file_is_not_overwritten_after_preview(self):
        path = self.root / "race.py"
        path.write_text("before", encoding="utf-8")
        snapshot = read_text_snapshot(path)
        path.write_text("external change", encoding="utf-8")
        with self.assertRaisesRegex(RuntimeError, "changed after search"):
            write_replacements({path: "after"}, {path: snapshot})


if __name__ == "__main__":
    unittest.main()
