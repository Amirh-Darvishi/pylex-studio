"""Atomic text-file persistence helpers."""

import os
import stat
import tempfile
from pathlib import Path


def atomic_write_text(path, content, encoding="utf-8", newline=""):
    """Write text beside its destination and replace it only after a full write.

    The destination remains untouched if encoding, writing, flushing, or the
    final replace fails. A temporary file is always cleaned up when possible.
    """
    destination = Path(path)
    if destination.is_symlink():
        destination = destination.resolve()
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            newline=newline,
            dir=str(destination.parent),
            prefix=f".{destination.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = Path(stream.name)
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
