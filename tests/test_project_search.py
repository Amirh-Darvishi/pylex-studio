"""Regression tests for workspace search and replacement services."""

import hashlib
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from pylex.project_search import (
    build_replacements,
    compile_search_pattern,
    iter_search_files,
    read_text_snapshot,
    search_text,
    write_replacements,
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

    def test_search_tracks_line_positions_without_repeated_prefix_scans(self):
        path = self.root / "many_hits.py"
        path.write_text("hit hit\n\nhit\nhit hit", encoding="utf-8")

        matches, snapshots = search_text(self.root, "hit")

        self.assertEqual(
            [(item.line, item.column, item.text) for item in matches],
            [
                (1, 1, "hit hit"),
                (1, 5, "hit hit"),
                (3, 1, "hit"),
                (4, 1, "hit hit"),
                (4, 5, "hit hit"),
            ],
        )
        self.assertEqual(set(snapshots), {path.resolve()})

    def test_multiline_regex_keeps_the_full_matching_context(self):
        path = self.root / "multiline.py"
        path.write_text("begin\nmiddle\nend\n", encoding="utf-8")

        matches, _snapshots = search_text(self.root, r"begin\nmiddle", regex=True)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].line, 1)
        self.assertEqual(matches[0].text, "begin\nmiddle")

    def test_search_does_not_retain_snapshots_for_unmatched_files(self):
        (self.root / "match.py").write_text("needle", encoding="utf-8")
        (self.root / "no_match.py").write_text("nothing here", encoding="utf-8")

        matches, snapshots = search_text(self.root, "needle")

        self.assertEqual(len(matches), 1)
        self.assertEqual(set(snapshots), {(self.root / "match.py").resolve()})

    def test_search_computes_digests_only_for_files_with_matches(self):
        matched = self.root / "matched.py"
        unmatched = self.root / "unmatched.py"
        matched.write_text("needle here", encoding="utf-8")
        unmatched.write_text("nothing here", encoding="utf-8")

        with patch(
            "pylex.project_search.hashlib.sha256", wraps=hashlib.sha256
        ) as digest:
            matches, snapshots = search_text(self.root, "needle")

        self.assertEqual(len(matches), 1)
        self.assertEqual(set(snapshots), {matched.resolve()})
        self.assertEqual(digest.call_count, 1)
        self.assertEqual(len(snapshots[matched.resolve()].digest), 64)

    def test_regex_whole_word_and_case_options(self):
        pattern = compile_search_pattern(
            r"foo", regex=True, case_sensitive=True, whole_word=True
        )
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
        self.assertEqual(
            [p.name for p in iter_search_files(self.root, include_glob="*.py")],
            ["a.py"],
        )

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
        updated, count = build_replacements(
            "one one", compile_search_pattern("one"), "two"
        )
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
