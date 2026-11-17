"""Tests for the filesystem-only workspace scanner."""

from pathlib import Path

from pylex.workspace_scan import iter_workspace_entries


def test_scanner_orders_directories_before_files_and_preserves_parent_paths(tmp_path):
    (tmp_path / "z-folder").mkdir()
    (tmp_path / "z-folder" / "nested").mkdir()
    (tmp_path / "z-folder" / "nested" / "config.json").write_text(
        "{}", encoding="utf-8"
    )
    (tmp_path / "a.py").write_text("pass", encoding="utf-8")
    (tmp_path / "b.txt").write_text("hello", encoding="utf-8")

    entries = list(iter_workspace_entries(tmp_path))

    assert [item[1] for item in entries[:3]] == ["z-folder", "a.py", "b.txt"]
    nested = next(item for item in entries if item[1] == "nested")
    assert nested[0] == "z-folder"
    config = next(item for item in entries if item[1] == "config.json")
    assert config[0] == "z-folder/nested"
    assert config[3] == "data"


def test_scanner_ignores_generated_directories_and_symlinks(tmp_path):
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("ignored", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "module.pyc").write_bytes(b"binary")
    (tmp_path / "visible.py").write_text("pass", encoding="utf-8")
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    outside.mkdir(exist_ok=True)
    (outside / "secret.txt").write_text("outside", encoding="utf-8")
    try:
        (tmp_path / "linked").symlink_to(outside, target_is_directory=True)
    except (OSError, NotImplementedError):
        pass

    paths = [item[2] for item in iter_workspace_entries(tmp_path)]
    assert any(path.endswith("visible.py") for path in paths)
    assert not any(".git" in path or "__pycache__" in path for path in paths)
    assert not any(path.endswith("secret.txt") for path in paths)


def test_scanner_skips_unreadable_or_removed_directories(tmp_path):
    (tmp_path / "vanishing").mkdir()
    (tmp_path / "main.py").write_text("pass", encoding="utf-8")
    entries = list(iter_workspace_entries(tmp_path))
    assert any(item[1] == "main.py" for item in entries)
