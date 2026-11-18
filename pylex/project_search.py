"""Workspace-wide text search and safe replacement services."""

from __future__ import annotations

import fnmatch
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


DEFAULT_EXCLUDES = (
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "node_modules",
    "build",
    "dist",
)
DEFAULT_EXTENSIONS = {
    ".py",
    ".pyi",
    ".txt",
    ".md",
    ".rst",
    ".toml",
    ".ini",
    ".cfg",
    ".json",
    ".yaml",
    ".yml",
    ".xml",
    ".html",
    ".htm",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".sql",
    ".sh",
    ".bat",
    ".ps1",
    ".gitignore",
}
MAX_FILE_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class SearchMatch:
    path: Path
    line: int
    column: int
    text: str
    start: int
    end: int


@dataclass(frozen=True)
class FileSnapshot:
    path: Path
    content: str
    encoding: str
    newline: str
    mtime_ns: int
    size: int
    digest: str


def compile_search_pattern(
    query: str, *, regex=False, case_sensitive=False, whole_word=False
):
    """Compile literal or regular-expression search with explicit options."""
    if not query:
        raise ValueError("Search text cannot be empty.")
    expression = query if regex else re.escape(query)
    if whole_word:
        expression = rf"(?<!\w)(?:{expression})(?!\w)"
    flags = 0 if case_sensitive else re.IGNORECASE
    try:
        return re.compile(expression, flags)
    except re.error as exc:
        raise ValueError(f"Invalid regular expression: {exc}") from exc


def iter_search_files(
    root,
    *,
    include_glob="*",
    excluded_dirs=DEFAULT_EXCLUDES,
    max_file_bytes=MAX_FILE_BYTES,
    cancel_event=None,
):
    """Yield supported, bounded-size regular files beneath a workspace."""
    root = Path(root).expanduser().resolve()
    excluded = set(excluded_dirs)
    for directory, dirs, filenames in __import__("os").walk(root):
        if cancel_event is not None and cancel_event.is_set():
            break
        dirs[:] = sorted(
            name
            for name in dirs
            if name not in excluded and (not name.startswith(".") or name == ".github")
        )
        for filename in sorted(filenames):
            if cancel_event is not None and cancel_event.is_set():
                return
            path = Path(directory) / filename
            if not fnmatch.fnmatch(path.name, include_glob):
                continue
            if path.is_symlink():
                continue
            try:
                if path.stat().st_size > max_file_bytes:
                    continue
            except OSError:
                continue
            if path.suffix.lower() not in DEFAULT_EXTENSIONS and path.name not in {
                ".gitignore",
                ".editorconfig",
                "Makefile",
            }:
                continue
            yield path


def _read_text_data(path, *, max_file_bytes=MAX_FILE_BYTES):
    """Read and decode a bounded text file without computing its digest."""
    path = Path(path)
    before = path.stat()
    if before.st_size > max_file_bytes:
        raise ValueError("File exceeds the configured search size limit.")
    raw = path.read_bytes()
    if b"\x00" in raw:
        raise ValueError("File contains binary data.")
    encoding = "utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8"
    try:
        content = raw.decode(encoding)
    except UnicodeDecodeError:
        try:
            encoding = "cp1252"
            content = raw.decode(encoding)
        except UnicodeDecodeError as exc:
            raise ValueError("File is binary or uses an unsupported encoding.") from exc
    newline = "\r\n" if "\r\n" in content else ("\r" if "\r" in content else "\n")
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    after = path.stat()
    return (
        path.resolve(),
        normalized,
        encoding,
        newline,
        after.st_mtime_ns,
        after.st_size,
        raw,
    )


def read_text_snapshot(path, *, max_file_bytes=MAX_FILE_BYTES):
    """Read a text file and retain the digest needed for safe replacement."""
    resolved, content, encoding, newline, mtime_ns, size, raw = _read_text_data(
        path, max_file_bytes=max_file_bytes
    )
    return FileSnapshot(
        resolved,
        content,
        encoding,
        newline,
        mtime_ns,
        size,
        hashlib.sha256(raw).hexdigest(),
    )


def search_text(
    root,
    query,
    *,
    regex=False,
    case_sensitive=False,
    whole_word=False,
    include_glob="*",
    excluded_dirs=DEFAULT_EXCLUDES,
    max_file_bytes=MAX_FILE_BYTES,
    cancel_event=None,
    overlays=None,
):
    """Search workspace files, optionally overlaying unsaved open-document text."""
    pattern = compile_search_pattern(
        query, regex=regex, case_sensitive=case_sensitive, whole_word=whole_word
    )
    root = Path(root).expanduser().resolve()
    overlays = {Path(path).resolve(): text for path, text in (overlays or {}).items()}
    candidates = set(
        iter_search_files(
            root,
            include_glob=include_glob,
            excluded_dirs=excluded_dirs,
            max_file_bytes=max_file_bytes,
            cancel_event=cancel_event,
        )
    )
    candidates.update(
        path for path in overlays if path.is_file() and path.is_relative_to(root)
    )
    results = []
    snapshots = {}
    for path in sorted(candidates):
        if cancel_event is not None and cancel_event.is_set():
            break
        try:
            (
                resolved,
                disk_content,
                encoding,
                newline,
                mtime_ns,
                size,
                raw,
            ) = _read_text_data(path, max_file_bytes=max_file_bytes)
            content = overlays.get(path, disk_content)
        except (OSError, ValueError):
            continue
        line_number = 1
        line_start = 0
        line_end = content.find("\n")
        matched = False
        for match in pattern.finditer(content):
            # Advance line boundaries monotonically. Repeated str.count/rfind
            # scans made searches with many hits quadratic in file length.
            while line_end >= 0 and match.start() > line_end:
                line_number += 1
                line_start = line_end + 1
                line_end = content.find("\n", line_start)
            if not matched:
                # Hash only files that need a replacement snapshot. Keep the
                # bytes from this read so a matching file is never read twice.
                snapshots[path] = FileSnapshot(
                    resolved,
                    disk_content,
                    encoding,
                    newline,
                    mtime_ns,
                    size,
                    hashlib.sha256(raw).hexdigest(),
                )
                matched = True
            visible_end = line_end if line_end >= 0 else len(content)
            if match.end() > visible_end:
                following_line_end = content.find("\n", match.end())
                visible_end = (
                    following_line_end if following_line_end >= 0 else len(content)
                )
            results.append(
                SearchMatch(
                    path,
                    line_number,
                    match.start() - line_start + 1,
                    content[line_start:visible_end],
                    match.start(),
                    match.end(),
                )
            )
    return results, snapshots


def build_replacements(content, pattern, replacement):
    """Return updated normalized text and the number of replacements."""
    try:
        return pattern.subn(replacement, content)
    except re.error as exc:
        raise ValueError(f"Invalid replacement expression: {exc}") from exc


def write_replacements(changes, snapshots):
    """Apply reviewed replacements atomically, rejecting files changed since search."""
    from .core.file_io import atomic_write_text

    prepared = []
    for path, new_content in changes.items():
        target = Path(path)
        snapshot = snapshots.get(target.resolve())
        if snapshot is None:
            # Windows may expose the same file through its long and 8.3 paths.
            # Path equality does not recognize those aliases, but samefile does.
            for candidate in snapshots.values():
                try:
                    if Path(candidate.path).samefile(target):
                        snapshot = candidate
                        break
                except OSError:
                    continue
        if snapshot is None:
            raise ValueError(f"No original snapshot exists for {path}.")
        current = target.stat()
        current_digest = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        if (
            current.st_mtime_ns != snapshot.mtime_ns
            or current.st_size != snapshot.size
            or current_digest != snapshot.digest
        ):
            raise RuntimeError(f"{path} changed after search; run the search again.")
        prepared.append(
            (Path(path), new_content.replace("\n", snapshot.newline), snapshot)
        )
    written = []
    for path, content, snapshot in prepared:
        atomic_write_text(path, content, encoding=snapshot.encoding, newline="")
        written.append(path)
    return written
