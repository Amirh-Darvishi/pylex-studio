"""Regression coverage for stale UI lifecycle callbacks."""

import tkinter as tk

from pylex.app import PyLexApp
from pylex.app_parts.debugger import DebuggerMixin
from pylex.app_parts.execution import ExecutionMixin
from pylex.app_parts.panels import _dialog_exists, _schedule_dialog_poll
from pylex.editor import CodeEditor


class _FakeRoot:
    def __init__(self, execution, debugger):
        self.execution = execution
        self.debug_session = debugger
        self._execution_poll = "execution-job"
        self._debug_poll = "debug-job"
        self.cancelled = []

    def after_cancel(self, job):
        self.cancelled.append(job)

    def _cancel_execution_poll(self):
        ExecutionMixin._cancel_execution_poll(self)

    def _cancel_debug_poll(self):
        DebuggerMixin._cancel_debug_poll(self)


def test_execution_poll_ignores_stale_handle():
    current = object()
    stale = object()
    app = _FakeRoot(current, None)

    assert ExecutionMixin._poll_execution(app, stale) is None
    assert app.cancelled == []


def test_debugger_poll_ignores_stale_session():
    current = object()
    stale = object()
    app = _FakeRoot(None, current)

    assert DebuggerMixin._poll_debugger(app, stale) is None
    assert app.cancelled == []


def test_shutdown_cancels_registered_ui_poll_jobs():
    app = _FakeRoot(None, None)

    PyLexApp._cancel_lifecycle_polls(app)

    assert app.cancelled == ["execution-job", "debug-job"]
    assert app._execution_poll is None
    assert app._debug_poll is None


def test_shutdown_tolerates_already_cancelled_tk_jobs():
    app = _FakeRoot(None, None)

    def cancel(job):
        raise tk.TclError("invalid command name")

    app.after_cancel = cancel
    PyLexApp._cancel_lifecycle_polls(app)

    assert app._execution_poll is None
    assert app._debug_poll is None


def test_cancel_poll_helpers_cancel_pending_jobs():
    app = _FakeRoot(None, None)
    ExecutionMixin._cancel_execution_poll(app)
    DebuggerMixin._cancel_debug_poll(app)

    assert app.cancelled == ["execution-job", "debug-job"]
    assert app._execution_poll is None
    assert app._debug_poll is None


class _DiagnosticRoot:
    def __init__(self, active_editor, documents):
        self.editor = active_editor
        self.documents = documents
        self.diagnostics = None
        self.status = _FakeStatus()
        self.tabs = _FakeTabs()
        self.error_tree = _FakeTree()

    def _set_diagnostics(self, diagnostics):
        self.diagnostics = diagnostics


class _FakeStatus:
    def configure(self, **kwargs):
        self.text = kwargs.get("text")


class _FakeTabs:
    def select(self, _widget=None):
        self.selected = _widget


class _FakeTree:
    master = object()


def test_runtime_error_uses_run_snapshot_for_diagnostic_source_line():
    editor = object()
    app = _DiagnosticRoot(editor, {editor: {}})
    stderr = 'Traceback (most recent call last):\n  File "program.py", line 2, in <module>\nValueError: invalid value\n'

    ExecutionMixin._report_runtime_error(
        app, stderr, source="first line\nraise ValueError()", editor=editor
    )

    assert app.diagnostics[0].line == 2
    assert app.diagnostics[0].source_line == "raise ValueError()"


def test_runtime_error_from_inactive_editor_does_not_replace_active_diagnostics():
    active, previous = object(), object()
    app = _DiagnosticRoot(active, {active: {}, previous: {}})
    app.diagnostics = ["active diagnostics"]
    stderr = 'Traceback (most recent call last):\n  File "program.py", line 1, in <module>\nValueError: invalid value\n'

    ExecutionMixin._report_runtime_error(
        app, stderr, source="raise ValueError()", editor=previous
    )

    assert app.diagnostics == ["active diagnostics"]
    assert app.status.text.startswith("Runtime error: ValueError")


def test_runtime_error_prefers_frame_for_executed_source_path():
    editor = object()
    app = _DiagnosticRoot(editor, {editor: {}})
    stderr = (
        'Traceback (most recent call last):\n'
        '  File "/library/module.py", line 50, in helper\n'
        '  File "/tmp/pylex-run.py", line 2, in <module>\n'
        'ValueError: invalid value\n'
    )

    ExecutionMixin._report_runtime_error(
        app,
        stderr,
        source="first line\nraise ValueError()",
        editor=editor,
        source_path="/tmp/pylex-run.py",
    )

    assert app.diagnostics[0].line == 2
    assert app.diagnostics[0].source_line == "raise ValueError()"


class _FakeDialog:
    def __init__(self, exists=True, error=False):
        self.exists = exists
        self.error = error
        self.after_error = False
        self.scheduled = []

    def winfo_exists(self):
        if self.error:
            raise tk.TclError("bad window")
        return self.exists

    def after(self, delay, callback):
        if self.error or self.after_error:
            raise tk.TclError("bad window")
        self.scheduled.append((delay, callback))
        return "poll-id"


def test_dialog_poll_helper_skips_destroyed_dialog():
    dialog = _FakeDialog(exists=False)

    assert not _dialog_exists(dialog)
    assert _schedule_dialog_poll(dialog, 100, lambda: None) is None
    assert dialog.scheduled == []


def test_dialog_poll_helper_handles_tcl_destroy_race():
    dialog = _FakeDialog(error=True)

    assert not _dialog_exists(dialog)
    assert _schedule_dialog_poll(dialog, 100, lambda: None) is None
    assert dialog.scheduled == []


def test_dialog_poll_helper_handles_after_scheduling_race():
    dialog = _FakeDialog()
    dialog.after_error = True

    assert _dialog_exists(dialog)
    assert _schedule_dialog_poll(dialog, 100, lambda: None) is None
    assert dialog.scheduled == []


def test_dialog_poll_helper_schedules_when_dialog_is_alive():
    dialog = _FakeDialog()

    def callback():
        return None

    assert _dialog_exists(dialog)
    assert _schedule_dialog_poll(dialog, 100, callback) == "poll-id"
    assert dialog.scheduled == [(100, callback)]


class _FakeCompletion:
    def __init__(self):
        self.destroyed = False

    def winfo_exists(self):
        return True

    def destroy(self):
        self.destroyed = True


class _FakeEditorLifecycle:
    def __init__(self):
        self._highlight_job = "highlight"
        self._line_refresh_job = "lines"
        self._bracket_job = "bracket"
        self._content_job = "content"
        self._completion_window = _FakeCompletion()
        self._completion_list = object()
        self.cancelled = []

    def _cancel_highlight_work(self):
        pass

    def _cancel_bracket_work(self):
        pass

    def after_cancel(self, job):
        self.cancelled.append(job)


def test_editor_destroy_cancels_chunked_content_and_closes_completion():
    editor = _FakeEditorLifecycle()
    completion = editor._completion_window
    event = type("DestroyEvent", (), {"widget": editor})()

    CodeEditor._on_destroy(editor, event)

    assert editor.cancelled == ["highlight", "lines", "bracket", "content"]
    assert completion.destroyed
    assert editor._content_job is None
    assert editor._completion_window is None
    assert editor._completion_list is None


def test_shutdown_closes_active_toolbar_popup():
    app = _FakeRoot(None, None)
    closed = []
    app._toolbar_menu_close = lambda: closed.append(True)

    PyLexApp._close_toolbar_menu(app)

    assert closed == [True]

