"""Atomic text-file persistence helpers."""

import os
import tempfile
from pathlib import Path


def atomic_write_text(path, content, encoding="utf-8", newline=""):
    """Write text beside its destination and replace it only after a full write.

    The destination remains untouched if encoding, writing, flushing, or the
    final replace fails. A temporary file is always cleaned up when possible.
    """
    destination = Path(path)
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
            try:
                os.chmod(temporary_path, destination.stat().st_mode)
            except OSError:
                pass
        os.replace(temporary_path, destination)
        temporary_path = None
    finally:
        if temporary_path is not None:
            try:
                temporary_path.unlink(missing_ok=True)
            except OSError:
                pass
