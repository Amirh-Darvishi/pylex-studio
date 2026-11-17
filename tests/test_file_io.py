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


def test_atomic_write_respects_read_only_destination(tmp_path):
    target = tmp_path / "readonly.txt"
    target.write_text("original", encoding="utf-8")
    target.chmod(0o444)

    try:
        with pytest.raises(PermissionError, match="read-only"):
            atomic_write_text(target, "replacement")
        assert target.read_text(encoding="utf-8") == "original"
    finally:
        target.chmod(0o644)


def test_atomic_write_follows_file_symlinks_when_supported(tmp_path):
    target = tmp_path / "target.txt"
    target.write_text("original", encoding="utf-8")
    link = tmp_path / "alias.txt"
    try:
        link.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Symlink creation is not available.")

    atomic_write_text(link, "updated")

    assert link.is_symlink()
    assert target.read_text(encoding="utf-8") == "updated"


def test_atomic_write_creates_new_file(tmp_path):
    target = Path(tmp_path) / "new.txt"

    atomic_write_text(target, "created", encoding="utf-8")

    assert target.read_text(encoding="utf-8") == "created"
