"""Atomic text-file persistence helpers."""

import os
import secrets
import stat
from pathlib import Path


def file_disk_signature(path):
    """Return file size and nanosecond modification time, or None if unavailable."""
    if path is None:
        return None
    try:
        info = Path(path).stat()
    except OSError:
        return None
    return (info.st_size, info.st_mtime_ns)


def _create_temporary_file(destination):
    """Create a unique sibling file using the process' normal creation mode."""
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    for _attempt in range(100):
        candidate = destination.with_name(
            f".{destination.name}.{secrets.token_hex(8)}.tmp"
        )
        try:
            descriptor = os.open(candidate, flags, 0o666)
            return candidate, descriptor
        except FileExistsError:
            continue
    raise FileExistsError(f"Could not allocate a temporary file for {destination}.")


def atomic_write_text(path, content, encoding="utf-8", newline=""):
    """Write text beside its destination and replace it only after a full write.

    The destination remains untouched if encoding, writing, flushing, or the
    final replace fails. A temporary file is always cleaned up when possible.
    New files receive the normal process creation permissions; existing files
    retain their permission bits.
    """
    destination = Path(path)
    if destination.is_symlink():
        destination = destination.resolve()
    temporary_path = None
    try:
        temporary_path, descriptor = _create_temporary_file(destination)
        with os.fdopen(descriptor, "w", encoding=encoding, newline=newline) as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())

        if destination.exists():
            existing_mode = destination.stat().st_mode
            writable_bits = stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH
            if not existing_mode & writable_bits:
                raise PermissionError(f"{destination} is read-only.")
            os.chmod(temporary_path, stat.S_IMODE(existing_mode))
        os.replace(temporary_path, destination)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass


def rename_without_overwrite(source, destination):
    """Rename a path without replacing an existing destination."""
    source = Path(source)
    destination = Path(destination)
    source_text = os.path.abspath(os.fspath(source))
    destination_text = os.path.abspath(os.fspath(destination))
    if source_text == destination_text:
        return source

    # Windows treats case-only path variants as the same existing destination.
    # Use a temporary sibling so users can still change filename casing.
    if os.path.normcase(source_text) == os.path.normcase(destination_text):
        temporary = source.with_name(f".{source.name}.{secrets.token_hex(8)}.rename")
        source.rename(temporary)
        try:
            temporary.rename(destination)
        except OSError:
            try:
                temporary.rename(source)
            except OSError:
                pass
            raise
        return destination

    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"Destination already exists: {destination}")
    source.rename(destination)
    return destination
