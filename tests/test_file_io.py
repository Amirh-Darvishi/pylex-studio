"""Tests for safe atomic document persistence."""

import os
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from pylex.core.file_io import atomic_write_text, file_disk_signature, rename_without_overwrite


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


def test_atomic_write_creates_new_file_with_normal_umask(tmp_path):
    target = Path(tmp_path) / "new.txt"
    previous_umask = os.umask(0o022)
    try:
        atomic_write_text(target, "created", encoding="utf-8")
    finally:
        os.umask(previous_umask)

    assert target.read_text(encoding="utf-8") == "created"
    if os.name == "posix":
        assert stat.S_IMODE(target.stat().st_mode) == 0o644


def test_rename_without_overwrite_preserves_existing_destination(tmp_path):
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    source.write_text("source", encoding="utf-8")
    destination.write_text("destination", encoding="utf-8")

    with pytest.raises(FileExistsError, match="Destination already exists"):
        rename_without_overwrite(source, destination)

    assert source.read_text(encoding="utf-8") == "source"
    assert destination.read_text(encoding="utf-8") == "destination"


def test_rename_without_overwrite_moves_file_and_same_path_is_noop(tmp_path):
    source = tmp_path / "source.txt"
    destination = tmp_path / "renamed.txt"
    source.write_text("content", encoding="utf-8")

    assert rename_without_overwrite(source, source) == source
    assert rename_without_overwrite(source, destination) == destination
    assert not source.exists()
    assert [item.name for item in tmp_path.iterdir()] == ["renamed.txt"]
    assert destination.read_text(encoding="utf-8") == "content"


def test_rename_without_overwrite_supports_case_only_rename_on_windows(tmp_path):
    if os.name != "nt":
        pytest.skip("Case-insensitive rename semantics are Windows-specific.")
    source = tmp_path / "Example.py"
    destination = tmp_path / "example.py"
    source.write_text("content", encoding="utf-8")

    assert rename_without_overwrite(source, destination) == destination
    assert destination.read_text(encoding="utf-8") == "content"
    assert [item.name for item in tmp_path.iterdir()] == ["example.py"]


def test_file_disk_signature_detects_content_replacement(tmp_path):
    target = tmp_path / "tracked.txt"
    target.write_text("one", encoding="utf-8")
    original = file_disk_signature(target)

    target.write_text("a longer replacement", encoding="utf-8")

    assert file_disk_signature(target) != original


def test_file_disk_signature_returns_none_for_missing_path(tmp_path):
    assert file_disk_signature(tmp_path / "missing.txt") is None
    assert file_disk_signature(None) is None
