"""Opt-in watchdog traceback capture for diagnosing UI hangs.

Enable with PYLEX_HANG_TRACE=<seconds>. Tracebacks are written periodically
without calling Tk from the watchdog thread.
"""

import faulthandler
import os


def start_hang_trace():
    """Start opt-in periodic Python thread dumps; return the retained file handle."""
    raw_timeout = os.environ.get("PYLEX_HANG_TRACE", "").strip()
    if not raw_timeout:
        return None
    try:
        timeout = float(raw_timeout)
    except ValueError:
        return None
    if timeout <= 0:
        return None
    path = os.environ.get("PYLEX_HANG_TRACE_FILE", "pylex-hang-trace.log")
    stream = None
    try:
        stream = open(path, "w", encoding="utf-8")
        stream.write(
            "PyLex Studio hang diagnostic enabled. "
            f"Tracebacks repeat every {timeout:.1f} seconds.\n"
        )
        stream.flush()
        faulthandler.dump_traceback_later(timeout, repeat=True, file=stream)
        return stream
    except (OSError, RuntimeError):
        if stream is not None:
            stream.close()
        return None


def stop_hang_trace(stream):
    """Cancel watchdog and close its log safely."""
    if stream is None:
        return
    try:
        faulthandler.cancel_dump_traceback_later()
    except RuntimeError:
        pass
    try:
        stream.flush()
        stream.close()
    except OSError:
        pass
