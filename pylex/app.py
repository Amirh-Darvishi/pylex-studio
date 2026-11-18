"""Main graphical interface and composition root for PyLex Studio."""

from .app_support import (
    DebuggerController,
    DocumentController,
    ExecutionController,
    ExecutionService,
    ThemeManager,
    WorkspaceController,
    load_preferences,
    sys,
    tk,
    ttkb,
)
from .app_parts import (
    AnalysisMixin,
    DebuggerMixin,
    DocumentsMixin,
    ExecutionMixin,
    PanelsMixin,
    PreferencesMixin,
    ShellMixin,
    ToolbarMixin,
    WorkspaceMixin,
)


class PyLexApp(
    ToolbarMixin,
    ShellMixin,
    PanelsMixin,
    WorkspaceMixin,
    DocumentsMixin,
    AnalysisMixin,
    ExecutionMixin,
    DebuggerMixin,
    PreferencesMixin,
    tk.Tk,
):
    """Main application window and UI composition root."""

    @property
    def project(self):
        return (
            self.workspace_controller.project
            if hasattr(self, "workspace_controller")
            else self._project
        )

    @project.setter
    def project(self, value):
        if hasattr(self, "workspace_controller"):
            self.workspace_controller.project = value
        else:
            self._project = value

    @property
    def documents(self):
        return (
            self.document_controller.documents
            if hasattr(self, "document_controller")
            else self._documents
        )

    @documents.setter
    def documents(self, value):
        if hasattr(self, "document_controller"):
            self.document_controller.documents = value
        else:
            self._documents = value

    @property
    def editor(self):
        return (
            self.document_controller.active_editor
            if hasattr(self, "document_controller")
            else self._editor
        )

    @editor.setter
    def editor(self, value):
        if hasattr(self, "document_controller"):
            self.document_controller.active_editor = value
        else:
            self._editor = value

    @property
    def execution(self):
        return (
            self.execution_controller.handle
            if hasattr(self, "execution_controller")
            else self._execution
        )

    @execution.setter
    def execution(self, value):
        if hasattr(self, "execution_controller"):
            self.execution_controller.handle = value
        else:
            self._execution = value

    @property
    def debug_session(self):
        return (
            self.debugger_controller.session
            if hasattr(self, "debugger_controller")
            else self._debug_session
        )

    @debug_session.setter
    def debug_session(self, value):
        if hasattr(self, "debugger_controller"):
            self.debugger_controller.session = value
        else:
            self._debug_session = value

    def __init__(self):
        # Tk must become DPI-aware before its root window is created; otherwise
        # Windows bitmap-scales the UI and softens text and icon glyphs.
        if sys.platform == "win32":
            ttkb.enable_high_dpi_awareness()
        super().__init__()
        # Keep the IDE fully opaque: top-level alpha blending softens text,
        # icons and thin borders on Windows, especially on high-DPI displays.
        self._icon_cache = {}
        self._toolbar_icon_bindings = []
        self._tool_tab_icon_bindings = []
        self.title("PyLex Studio")
        self.geometry("1180x780")
        self.minsize(850, 560)
        self.current_path = None
        self.dirty = False
        self.project = None
        self.execution_service = ExecutionService()
        self.preferences = load_preferences()
        self.dark = self.preferences["theme"] == "dark"
        self.theme_manager = ThemeManager(self)
        self.theme_palette = self.theme_manager.apply(self.dark)
        self.diagnostics = []
        self.execution = None
        self._execution_poll = None
        self.debug_session = None
        self._debug_poll = None
        self._last_timeout_display = None
        self._execution_context = None
        self.breakpoints = {}
        self.conditional_breakpoints = {}
        self.documents = {}
        self.editor = None
        self.workspace_controller = WorkspaceController(self._project)
        self.document_controller = DocumentController(self._documents, self._editor)
        self.execution_controller = ExecutionController(self.execution_service)
        self.debugger_controller = DebuggerController(self.execution_service)
        self._menu()
        self._toolbar()
        self._workspace()
        self._restore_last_workspace()
        self._theme()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._title()

    def _close_toolbar_menu(self):
        """Close any active toolbar popup and cancel its scheduled timers."""
        close_menu = getattr(self, "_toolbar_menu_close", None)
        if callable(close_menu):
            close_menu()

    def _cancel_lifecycle_polls(self):
        """Cancel UI polling callbacks before destroying the Tk root."""
        self._cancel_execution_poll()
        self._cancel_debug_poll()

    def close(self):
        for editor, document in list(self.documents.items()):
            if not document["dirty"]:
                continue
            self.editor_tabs.select(document["frame"])
            self.editor = editor
            self._sync_active_document()
            if not self._confirm():
                return
        self._close_toolbar_menu()
        self._cancel_analysis()
        self._invalidate_file_loads()
        self._cancel_lifecycle_polls()
        if self.execution_controller.stop():
            handle = self.execution
            handle.wait(timeout=2)
            self.execution_controller.finish(handle)
        self.debugger_controller.finish()
        self.terminal_panel.close_all()
        self.quality_panel.close()
        self.git_panel.close()
        self.destroy()
