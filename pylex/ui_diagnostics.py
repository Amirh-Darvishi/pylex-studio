"""Opt-in low-overhead callback tracing for diagnosing UI hangs.

Enable with PYLEX_HANG_TRACE=<watchdog seconds>. Only callbacks slower than
PYLEX_HANG_TRACE_MIN_MS (default 100 ms) are written. No Tk calls are made
from the diagnostic worker.
"""

import faulthandler
import os
import sys
import threading
import time

_TARGETS = {
    "_set_status_item_visible",
    "_set_status_preference",
    "_apply_status_bar_visibility",
    "_reset_status_bar",
    "_update_editor_status",
    "_changed",
    "_schedule_line_refresh",
    "refresh_lines",
    "_schedule_highlight",
    "highlight",
    "_poll_highlight_result",
    "_apply_highlight_batch",
    "_cursor_changed",
    "paste",
    "_paste",
    "_show_status_context_menu",
    "_show_context_menu",
    "_render",
    "_dismiss",
    "_invoke",
}


def start_hang_trace(root):
    """Enable diagnostics only when requested; return resources for shutdown."""
    raw_timeout = os.environ.get("PYLEX_HANG_TRACE", "").strip()
    if not raw_timeout:
        return None
    try:
        timeout = float(raw_timeout)
        min_duration_ms = float(
            os.environ.get("PYLEX_HANG_TRACE_MIN_MS", "100").strip()
        )
    except ValueError:
        return None
    if timeout <= 0 or min_duration_ms < 0:
        return None

    path = os.environ.get("PYLEX_HANG_TRACE_FILE", "pylex-hang-trace.log")
    stream = None
    lock = threading.Lock()
    last_heartbeat = [time.monotonic()]
    last_callback = ["(none)"]
    callback_starts = {}
    stop_event = threading.Event()
    heartbeat_job = [None]

    try:
        stream = open(path, "w", encoding="utf-8", buffering=1)
        stream.write(
            f"PyLex diagnostic started; timeout={timeout:.1f}s; "
            f"slow_callback_threshold={min_duration_ms:.1f}ms; pid={os.getpid()}\n"
        )

        def log(message):
            with lock:
                stream.write(f"{time.monotonic():.6f} {message}\n")
                stream.flush()

        def profile(frame, event, arg):
            if event not in ("call", "return"):
                return
            code = frame.f_code
            name = code.co_name
            module = frame.f_globals.get("__name__", "")
            if name not in _TARGETS or not module.startswith("pylex"):
                return
            frame_key = id(frame)
            if event == "call":
                callback_starts[frame_key] = time.monotonic()
                last_callback[0] = f"{module}.{name} ({code.co_filename}:{frame.f_lineno})"
                return
            started = callback_starts.pop(frame_key, None)
            if started is None:
                return
            duration_ms = (time.monotonic() - started) * 1000
            if duration_ms >= min_duration_ms:
                log(
                    f"SLOW_CALLBACK {module}.{name} duration_ms={duration_ms:.1f} "
                    f"line={frame.f_lineno}"
                )

        sys.setprofile(profile)

        def heartbeat():
            last_heartbeat[0] = time.monotonic()
            try:
                heartbeat_job[0] = root.after(250, heartbeat)
            except Exception:
                heartbeat_job[0] = None

        heartbeat_job[0] = root.after(250, heartbeat)

        def watchdog():
            while not stop_event.wait(timeout):
                elapsed = time.monotonic() - last_heartbeat[0]
                log(
                    f"WATCHDOG heartbeat_age={elapsed:.2f}s "
                    f"last_callback={last_callback[0]}"
                )
                if elapsed > timeout:
                    log("WARNING: Tk heartbeat stalled or delayed.")

        worker = threading.Thread(
            target=watchdog, name="pylex-hang-watchdog", daemon=True
        )
        worker.start()
        faulthandler.dump_traceback_later(timeout, repeat=True, file=stream)
        return {
            "stream": stream,
            "lock": lock,
            "stop": stop_event,
            "worker": worker,
            "heartbeat_job": heartbeat_job,
        }
    except (OSError, RuntimeError):
        if stream is not None:
            try:
                stream.close()
            except OSError:
                pass
        sys.setprofile(None)
        return None


def stop_hang_trace(resource, root=None):
    """Stop diagnostic callbacks and close the trace file safely."""
    if resource is None:
        return
    stream = resource["stream"]
    try:
        faulthandler.cancel_dump_traceback_later()
    except RuntimeError:
        pass
    resource["stop"].set()
    sys.setprofile(None)
    worker = resource.get("worker")
    if worker is not None:
        worker.join(timeout=1.0)
    if root is not None:
        job = resource.get("heartbeat_job", [None])[0]
        if job is not None:
            try:
                root.after_cancel(job)
            except Exception:
                pass
    try:
        stream.flush()
        stream.close()
    except OSError:
        pass
