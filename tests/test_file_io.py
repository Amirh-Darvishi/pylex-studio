"""Tests for safe atomic document persistence."""

from pathlib import Path
from unittest.mock import patch

import pytest

from pylex.core.file_io import atomic_write_text


def test_atomic_write_replaces_file_with_requested_encoding(tmp_path):
    target = tmp_path / "notes.txt"
    target.write_text("old", encoding="utf-8")

    atomic_write_text(target, "café", encoding="utf-8", newline="")

    assert target.read_text(encoding="utf-8") == "café"
    assert list(tmp_path.glob(".notes.txt.*.tmp")) == []


def test_failed_replace_preserves_original_file_and_cleans_temp(tmp_path):
    target = tmp_path / "notes.txt"
    target.write_text("original", encoding="utf-8")

    with patch("pylex.core.file_io.os.replace", side_effect=OSError("locked")):
        with pytest.raises(OSError, match="locked"):
            atomic_write_text(target, "replacement")

    assert target.read_text(encoding="utf-8") == "original"
    assert list(tmp_path.glob(".notes.txt.*.tmp")) == []


def test_atomic_write_creates_new_file(tmp_path):
    target = Path(tmp_path) / "new.txt"

    atomic_write_text(target, "created", encoding="utf-8")

    assert target.read_text(encoding="utf-8") == "created"
