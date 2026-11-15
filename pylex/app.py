"""Main graphical interface for PyLex Studio."""
from . import __version__
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, font as tkfont
import ttkbootstrap as ttkb
import queue
import threading
from pathlib import Path
import os
import subprocess
import sys
import re
import time

from .editor import CodeEditor
from .analyzer import (
    lexical_analysis, syntax_analysis, format_tokens, collect_diagnostics,
)
from .dependencies import inspect_dependencies, python_environment
from .core.project import Project
from .core.file_types import file_type_for, read_text_file
from .services.execution import ExecutionService
from .debugger import DebugSession
from .preferences import DEFAULTS, load_preferences, save_preferences
from .interpreters import create_virtual_environment, discover_interpreters, ensure_pip, find_project_environment, probe_interpreter
from .terminal import TerminalPanel
from .quality import QualityPanel
from .git_panel import GitPanel
from .ui.theme import ThemeManager


class PyLexApp(tk.Tk):
    """Main application window and coordinator for editor tools."""

    def __init__(self):
        super().__init__()
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
        self.breakpoints = {}
        self.conditional_breakpoints = {}
        self.documents = {}
        self.editor = None
        self._menu()
        self._toolbar()
        self._workspace()
        self._restore_last_workspace()
        self._theme()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._title()

    def _menu(self):
        menu = tk.Menu(self)
        self._menus = [menu]
        file_menu = tk.Menu(menu, tearoff=False)
        self._menus.append(file_menu)
        for label, command, shortcut in [
            ("New", self.new_file, "Ctrl+N"),
            ("Open...", self.open_file, "Ctrl+O"),
            ("Open Workspace...", self.open_project_folder, ""),
            ("Close Workspace", self.close_workspace, "Ctrl+Shift+W"),
            ("Python Interpreter...", self.manage_interpreter, ""),
            ("Save", self.save_file, "Ctrl+S"),
            ("Save As...", self.save_as, "Ctrl+Shift+S"),
            ("Close Tab", self.close_tab, "Ctrl+W"),
        ]:
            file_menu.add_command(
                label=label, command=command, accelerator=shortcut
            )
        self.recent_workspace_menu = tk.Menu(file_menu, tearoff=False)
        self._menus.append(self.recent_workspace_menu)
        file_menu.add_cascade(label="Open Recent Workspace", menu=self.recent_workspace_menu)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.close)
        self._refresh_recent_workspace_menu()
        menu.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menu, tearoff=False)
        self._menus.append(edit_menu)
        edit_menu.add_command(label="Find / Replace...", command=self.find_replace)
        edit_menu.add_command(label="Toggle Line Comment", command=lambda: self.editor._toggle_comment(), accelerator="Ctrl+/")
        edit_menu.add_command(label="Duplicate Line / Selection", command=lambda: self.editor._duplicate_line(), accelerator="Ctrl+D")
        edit_menu.add_command(label="Go to Line...", command=lambda: self.editor._go_to_line(), accelerator="Ctrl+G")
        menu.add_cascade(label="Edit", menu=edit_menu)

        navigate_menu = tk.Menu(menu, tearoff=False)
        self._menus.append(navigate_menu)
        navigate_menu.add_command(
            label="Quick Open File...", command=self.open_quick_file,
            accelerator="Ctrl+P",
        )
        navigate_menu.add_command(
            label="Go to Line...", command=lambda: self.editor._go_to_line(),
            accelerator="Ctrl+G",
        )
        navigate_menu.add_command(
            label="Command Palette...", command=self.open_command_palette,
            accelerator="Ctrl+Shift+P",
        )
        menu.add_cascade(label="Navigate", menu=navigate_menu)

        tools_menu = tk.Menu(menu, tearoff=False)
        self._menus.append(tools_menu)
        tools_menu.add_command(label="Python Interpreter...", command=self.manage_interpreter)
        tools_menu.add_command(label="Integrated Terminal", command=self.open_terminal)
        tools_menu.add_command(label="Formatter, Linter & Test Explorer", command=self.open_quality_tools)
        tools_menu.add_command(label="Git Source Control", command=self.open_git_tools)
        tools_menu.add_separator()
        tools_menu.add_command(label="Analyze All", command=self.analyze_all)
        tools_menu.add_command(label="Lexical Analysis", command=self.analyze_lexical)
        tools_menu.add_command(label="Syntax Analysis", command=self.analyze_syntax)
        tools_menu.add_command(label="Clear Results", command=self.clear_results)
        tools_menu.add_separator()
        tools_menu.add_command(label="Run Code", command=self.run_code)
        tools_menu.add_command(label="Force Stop Execution", command=self.stop_execution)
        tools_menu.add_separator()
        tools_menu.add_command(label="Start Debugging", command=self.start_debugging)
        tools_menu.add_command(label="Continue", command=self.debug_continue)
        tools_menu.add_command(label="Step Into", command=self.debug_step)
        tools_menu.add_command(label="Step Over", command=self.debug_next)
        tools_menu.add_command(label="Toggle Breakpoint", command=self.toggle_breakpoint)
        tools_menu.add_command(label="Inspect Variables", command=self.debug_variables)
        tools_menu.add_command(label="Show Stack", command=self.debug_stack)
        tools_menu.add_command(label="Show Function Arguments", command=self.debug_arguments)
        tools_menu.add_command(label="Run Until Line", command=self.debug_until)
        tools_menu.add_command(label="Run Until Return", command=self.debug_return)
        tools_menu.add_command(label="Jump to Line", command=self.debug_jump)
        tools_menu.add_command(label="Evaluate Expression...", command=self.debug_evaluate)
        tools_menu.add_command(label="Conditional Breakpoint...", command=self.debug_conditional_breakpoint)
        tools_menu.add_command(label="Temporary Breakpoint", command=self.debug_temporary_breakpoint)
        tools_menu.add_command(label="Enable Breakpoint...", command=lambda: self.debug_manage_breakpoint("enable"))
        tools_menu.add_command(label="Disable Breakpoint...", command=lambda: self.debug_manage_breakpoint("disable"))
        tools_menu.add_command(label="Ignore Breakpoint Hits...", command=lambda: self.debug_manage_breakpoint("ignore"))
        tools_menu.add_command(label="Clear All Breakpoints", command=self.debug_clear_breakpoints)
        tools_menu.add_command(label="Stop Debugging", command=self.stop_debugging)
        menu.add_cascade(label="Tools", menu=tools_menu)

        view_menu = tk.Menu(menu, tearoff=False)
        self._menus.append(view_menu)
        view_menu.add_command(label="Preferences...", command=self.open_preferences)
        view_menu.add_command(label="Toggle Project Explorer", command=self.toggle_project_explorer)
        menu.add_cascade(label="View", menu=view_menu)

        help_menu = tk.Menu(menu, tearoff=False)
        self._menus.append(help_menu)
        help_menu.add_command(label="Quick Start & Help...", command=self.show_help)
        help_menu.add_command(label="Command Palette...", command=self.open_command_palette, accelerator="Ctrl+Shift+P")
        help_menu.add_separator()
        help_menu.add_command(label="About PyLex Studio...", command=self.show_about)
        menu.add_cascade(label="Help", menu=help_menu)
        self.config(menu=menu)

        self.bind_all("<Control-Shift-P>", lambda event: self.open_command_palette())
        self.bind_all("<Control-p>", lambda event: self.open_quick_file())
        self.bind_all("<Control-comma>", lambda event: self.open_preferences())
        self.bind_all("<Control-n>", lambda event: self.new_file())
        self.bind_all("<Control-o>", lambda event: self.open_file())
        self.bind_all("<Control-s>", lambda event: self.save_file())
        self.bind_all("<Control-h>", lambda event: self.find_replace())
        self.bind_all("<Control-w>", lambda event: self.close_tab())
        self.bind_all("<Control-Shift-W>", lambda event: self.close_workspace())
        self.bind_all("<F5>", lambda event: self.run_code())
        self.bind_all("<Shift-F5>", lambda event: self.stop_execution())
        self.bind_all("<F6>", lambda event: self.analyze_all())
        self.bind_all("<F9>", lambda event: self.toggle_breakpoint())
        self.bind_all("<F10>", lambda event: self.debug_next())
        self.bind_all("<F11>", lambda event: self.debug_step())
        self.bind_all("<Control-F5>", lambda event: self.start_debugging())
        self.bind_all("<Control-F10>", lambda event: self.debug_continue())

    def _icon(self, name, color=None, size=16):
        """Return a cached Bootstrap glyph using the active theme palette."""
        color = color or self.theme_palette.get("muted", "#91a0b7")
        key = (name, color, size)
        if key not in self._icon_cache:
            self._icon_cache[key] = ttkb.Icon(name, size=size, color=color)
        return self._icon_cache[key]

    @staticmethod
    def _file_icon_name(kind):
        """Map workspace file categories to one consistent icon family."""
        return {
            "python": "filetype-py",
            "web": "filetype-js",
            "markup": "filetype-html",
            "style": "filetype-css",
            "data": "filetype-json",
            "config": "gear",
            "shell": "terminal",
            "compiled": "file-earmark-code",
            "image": "file-earmark-image",
            "audio": "file-earmark-music",
            "video": "file-earmark-play",
            "pdf": "file-earmark-pdf",
            "document": "file-earmark-text",
            "archive": "file-earmark-zip",
            "database": "database",
            "font": "file-earmark-font",
            "text": "file-earmark-text",
            "binary": "file-earmark",
            "unknown": "file-earmark",
        }.get(kind, "file-earmark")

    def _toolbar(self):
        """Build a compact, shortcut-aware toolbar with non-duplicated actions."""
        bar = ttk.Frame(self, style="PyLex.Toolbar.TFrame", padding=(14, 8))
        bar.pack(fill="x")

        brand = ttk.Label(bar, text="PyLex Studio", style="PyLex.Brand.TLabel")
        brand.pack(side="left", padx=(0, 20))

        def add_group(title, actions):
            group = ttk.Frame(bar, style="PyLex.Toolbar.TFrame")
            group.pack(side="left", padx=(0, 14))
            ttk.Label(
                group, text=title.upper(), style="PyLex.Group.TLabel"
            ).pack(anchor="w", padx=(2, 3), pady=(0, 3))
            buttons = ttk.Frame(group, style="PyLex.Toolbar.TFrame")
            buttons.pack(anchor="w")
            for label, action, style_name, icon_name, color_key in actions:
                button = ttk.Button(
                    buttons, text=label, command=action,
                    style=style_name,
                    image=self._icon(icon_name, self.theme_palette.get(color_key)),
                    compound="left",
                )
                button.pack(side="left", padx=(0, 4))
                self._toolbar_icon_bindings.append((button, icon_name, color_key))
            return group

        add_group("File", [
            ("New  Ctrl+N", self.new_file, "PyLex.Toolbar.TButton", "file-earmark-plus", "accent"),
            ("Open  Ctrl+O", self.open_file, "PyLex.Toolbar.TButton", "folder2-open", "accent"),
            ("Save  Ctrl+S", self.save_file, "PyLex.Toolbar.TButton", "floppy", "success"),
        ])
        add_group("Run & Debug", [
            ("Run  F5", self.run_code, "PyLex.Primary.TButton", "play-fill", "accent"),
            ("Stop  Shift+F5", self.stop_execution, "PyLex.Danger.TButton", "stop-fill", "danger"),
            ("Debug  Ctrl+F5", self.start_debugging, "PyLex.Toolbar.TButton", "bug-fill", "violet"),
        ])
        add_group("Code", [
            ("Analyze  F6", self.analyze_all, "PyLex.Toolbar.TButton", "activity", "accent"),
        ])

        spacer = ttk.Frame(bar, style="PyLex.Toolbar.TFrame")
        spacer.pack(side="left", fill="x", expand=True)
        self.help_button = ttk.Button(
            bar, text="Help", command=self.show_help,
            style="PyLex.Toolbar.TButton",
            image=self._icon("question-circle", self.theme_palette.get("muted")),
            compound="left",
        )
        self.help_button.pack(side="right", padx=(4, 0))
        self.settings_button = ttk.Button(
            bar, text="Settings  Ctrl+,", command=self.open_preferences,
            style="PyLex.Toolbar.TButton",
            image=self._icon("gear-fill", self.theme_palette.get("muted")),
            compound="left",
        )
        self.settings_button.pack(side="right", padx=(4, 0))
        self.theme_button = ttk.Button(
            bar, text="Light theme" if self.dark else "Dark theme",
            command=self.toggle_theme, style="PyLex.Toolbar.TButton",
            image=self._icon("sun" if self.dark else "moon-stars", self.theme_palette.get("warning")),
            compound="left",
        )
        self.theme_button.pack(side="right", padx=(4, 0))

    def _add_tool_tab(self, child, title, icon_name, color_key):
        """Add a lower-panel tab and retain its icon for live theme refreshes."""
        image = self._icon(icon_name, self.theme_palette.get(color_key))
        self.tabs.add(child, text=title, image=image, compound="left")
        self._tool_tab_icon_bindings.append((child, icon_name, color_key))

    def _workspace(self):
        workspace = ttk.Panedwindow(self, orient="horizontal")
        self.workspace = workspace
        workspace.pack(fill="both", expand=True, padx=10, pady=(2, 8))
        self.project_root = None
        self.explorer_frame = ttk.Frame(workspace)
        explorer_header = ttk.Frame(self.explorer_frame, padding=(6, 5))
        explorer_header.pack(fill="x")
        ttk.Label(
            explorer_header, text="EXPLORER", style="PyLex.Section.TLabel"
        ).pack(side="left")
        ttk.Button(explorer_header, text="Close", command=self.close_workspace).pack(side="right", padx=(4, 0))
        ttk.Button(explorer_header, text="Open Folder", command=self.open_project_folder).pack(side="right")
        ttk.Button(explorer_header, text="Refresh", width=8, command=self.refresh_workspace).pack(side="right", padx=(0, 4))
        self.workspace_path_label = ttk.Label(self.explorer_frame, text="No folder opened", padding=(7, 0, 7, 5))
        self.workspace_path_label.pack(fill="x")
        self.project_tree = ttk.Treeview(self.explorer_frame, show="tree", selectmode="browse")
        self.project_tree.pack(fill="both", expand=True)
        self.project_tree.tag_configure("directory", foreground=self.theme_palette["accent"])
        self.project_tree.tag_configure("python", foreground=self.theme_palette["file_python"])
        self.project_tree.tag_configure("web", foreground=self.theme_palette["file_web"])
        self.project_tree.tag_configure("markup", foreground=self.theme_palette["file_markup"])
        self.project_tree.tag_configure("style", foreground=self.theme_palette["file_style"])
        self.project_tree.tag_configure("data", foreground=self.theme_palette["file_data"])
        self.project_tree.tag_configure("config", foreground=self.theme_palette["muted"])
        self.project_tree.tag_configure("text", foreground=self.theme_palette["editor_fg"])
        self.project_tree.bind("<Double-1>", self._on_project_tree_open)
        if self.preferences["show_project_explorer"]:
            workspace.add(self.explorer_frame, weight=1)

        panes = ttk.Panedwindow(workspace, orient="vertical")
        self.editor_panes = panes
        workspace.add(panes, weight=5)
        self.editor_tabs = ttk.Notebook(panes)
        panes.add(self.editor_tabs, weight=4)
        self.editor_tabs.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self.editor_tabs.bind("<Button-1>", self._on_tab_close_click, add="+")
        self._create_document()

        lower = ttk.Frame(panes)
        panes.add(lower, weight=2)
        self.tabs = ttk.Notebook(lower)
        self.tabs.pack(fill="both", expand=True)

        self.output = self._text_panel("Output")
        self.lexical = self._text_panel("Lexical Analysis")
        self.syntax = self._text_panel("Syntax Analysis")
        self._errors_panel()
        self._dependencies_panel()
        self.terminal_panel = TerminalPanel(
            lower, self._terminal_context,
            default_shell=self.preferences.get("terminal_shell", ""),
            on_shell_change=self._save_terminal_shell,
        )
        self._add_tool_tab(self.terminal_panel, "Terminal", "terminal", "accent")
        self.quality_panel = QualityPanel(
            lower, self._quality_context, self._quality_document,
            self._apply_formatted_source, self._navigate_quality_diagnostic,
            status_callback=lambda message: self.status.configure(text=message),
            project_format_guard=self._can_format_project,
        )
        self._add_tool_tab(self.quality_panel, "Quality", "check2-square", "success")
        self.git_panel = GitPanel(
            lower, lambda: self.project.root if self.project else None,
            status_callback=lambda message: self.status.configure(text=message),
        )
        self._add_tool_tab(self.git_panel, "Git", "git", "violet")

        self.status = ttk.Label(
            self, text="Ready", style="PyLex.Status.TLabel"
        )
        self.status.pack(fill="x")

    def _text_panel(self, title):
        frame = ttk.Frame(self.tabs)
        row = 0
        if title == "Output":
            actions = ttk.Frame(frame, padding=(4, 3))
            actions.grid(row=0, column=0, columnspan=2, sticky="ew")
            ttk.Button(actions, text="Clear Output", command=self.clear_output).pack(side="left", padx=2)
            ttk.Button(actions, text="Save Output...", command=self.save_output).pack(side="left", padx=2)
            ttk.Button(actions, text="Force Stop Run", command=self.stop_execution).pack(side="left", padx=2)
            ttk.Button(actions, text="Stop Debugger", command=self.stop_debugging).pack(side="left", padx=2)
            row = 1
        text = tk.Text(frame, wrap="none", font=("Consolas", 10), height=8)
        text.tag_configure("stderr", foreground="#d9534f")
        text.tag_configure("stdout", foreground="#5b9b68")
        text.tag_configure("system", foreground="#4b83c3")
        # Text widgets retain native wheel/keyboard scrolling without visible bars.
        text.bind(
            "<Shift-MouseWheel>",
            lambda event: (text.xview_scroll(-int(event.delta / 120) * 3, "units"), "break"),
            add="+",
        )
        text.grid(row=row, column=0, columnspan=2, sticky="nsew")
        frame.rowconfigure(row, weight=1)
        frame.columnconfigure(0, weight=1)
        panel_icons = {
            "Output": ("terminal", "accent"),
            "Lexical Analysis": ("braces", "violet"),
            "Syntax Analysis": ("check-circle", "success"),
        }
        icon_name, color_key = panel_icons.get(title, ("file-earmark-text", "muted"))
        self._add_tool_tab(frame, title, icon_name, color_key)
        return text

    def _terminal_context(self):
        """Return the current workspace, environment, and selected interpreter."""
        document = self._active_document()
        path = document.get("path") if document else self.current_path
        try:
            project = self._project_for_document(document)
        except (OSError, ValueError):
            project = self.project
        cwd = project.working_directory_for(path) if project else (
            Path(path).expanduser().resolve().parent if path else Path.cwd()
        )
        env = project.execution_environment() if project else dict(os.environ)
        try:
            interpreter = self._interpreter_for_project(project).executable
        except (OSError, ValueError, TimeoutError):
            interpreter = sys.executable
        return cwd, env, interpreter

    def _quality_context(self):
        """Return the active workspace root, interpreter, and import environment."""
        document = self._active_document()
        project = self._project_for_document(document)
        info = self._interpreter_for_project(project)
        env = project.execution_environment()
        executable_dir = Path(info.executable).parent
        if executable_dir.name.lower() in {"scripts", "bin"}:
            env["VIRTUAL_ENV"] = str(executable_dir.parent)
            env["PATH"] = str(executable_dir) + os.pathsep + env.get("PATH", "")
        return project.root, info.executable, env

    def _quality_document(self):
        """Snapshot the active editor so async formatting cannot target another tab."""
        document = self._active_document()
        return self.editor, document.get("path") if document else None, self.editor.get_content()

    def _apply_formatted_source(self, editor, source):
        """Apply Black output only to the editor that initiated the request."""
        if editor not in self.documents:
            self.status.configure(text="Formatted output discarded: the originating tab was closed.")
            return
        widget = editor.text
        try:
            cursor = int(widget.count("1.0", "insert", "chars")[0])
        except (TypeError, IndexError):
            cursor = 0
        widget.edit_separator()
        widget.delete("1.0", "end")
        widget.insert("1.0", source)
        widget.mark_set("insert", f"1.0+{min(cursor, len(source))}c")
        widget.edit_separator()
        widget.edit_modified(False)
        self.mark_dirty(editor)
        editor.highlight()
        self.status.configure(text="Current editor buffer formatted with Black. Save to keep the changes.")

    def _navigate_quality_diagnostic(self, diagnostic):
        """Open the reported file and navigate to the Ruff diagnostic location."""
        raw_path = diagnostic.get("path", "")
        if not raw_path or raw_path == "<stdin>":
            self.status.configure(text="Ruff diagnostic has no navigable file path.")
            return
        path = Path(raw_path)
        if not path.is_absolute():
            path = self._project_for_document(self._active_document()).root / path
        path = path.resolve()
        target = None
        for editor, document in self.documents.items():
            if document.get("path") is not None and Path(document["path"]).resolve() == path:
                target = editor
                self.editor_tabs.select(document["frame"])
                break
        if target is None:
            if not path.is_file():
                self.status.configure(text=f"Diagnostic file no longer exists: {path}")
                return
            self._open_path(path)
            target = self.editor
        target.show_diagnostic(
            diagnostic.get("line", 1), max(0, diagnostic.get("column", 1) - 1),
            diagnostic.get("end_line"), diagnostic.get("end_column"),
        )
        self.status.configure(text=f"{diagnostic.get('code', 'Ruff')} — {path.name}:{diagnostic.get('line', 1)}")

    def _can_format_project(self):
        """Protect unsaved editor buffers from whole-project formatting."""
        if any(document["dirty"] for document in self.documents.values()):
            messagebox.showwarning(
                "Format Project",
                "Save or close all modified editor tabs before formatting the whole project. "
                "This prevents unsaved buffers from conflicting with files changed on disk.",
                parent=self,
            )
            return False
        return True

    def open_quality_tools(self):
        """Show the integrated formatter, linter, and test explorer."""
        self.tabs.select(self.quality_panel)

    def open_git_tools(self):
        """Show Git status, staging, commits, branches, and remote controls."""
        self.tabs.select(self.git_panel)
        self.git_panel.refresh()

    def _save_terminal_shell(self, shell):
        self.preferences["terminal_shell"] = shell
        self._persist_preferences()

    def open_terminal(self):
        """Open the Terminal panel and create a shell session when needed."""
        self.tabs.select(self.terminal_panel)
        if self.terminal_panel.session_count == 0:
            self.terminal_panel.create_session()
        else:
            frame = self.terminal_panel._current_frame()
            if frame in self.terminal_panel.views:
                self.terminal_panel.views[frame]["entry"].focus_set()

    def _dependencies_panel(self):
        frame = ttk.Frame(self.tabs, padding=4)
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(0, 4))
        ttk.Button(actions, text="Scan Current File", command=self.scan_dependencies).pack(side="left")
        ttk.Button(actions, text="Python Interpreter...", command=self.manage_interpreter).pack(side="left", padx=4)
        ttk.Button(actions, text="Copy Python Install Command", command=self.copy_install_command).pack(side="left", padx=4)
        self.dependency_environment = ttk.Label(frame, text="Python environment: not scanned")
        self.dependency_environment.pack(fill="x", pady=(2, 5))
        columns = ("module", "status", "distribution", "version")
        self.dependency_tree = ttk.Treeview(frame, columns=columns, show="headings", height=7)
        for key, label in (("module", "Import"), ("status", "Status"),
                           ("distribution", "Package / Source"), ("version", "Version")):
            self.dependency_tree.heading(key, text=label)
        self.dependency_tree.column("module", width=150)
        self.dependency_tree.column("status", width=100, anchor="center")
        self.dependency_tree.column("distribution", width=220)
        self.dependency_tree.column("version", width=170)
        self.dependency_tree.pack(fill="both", expand=True)
        self.dependency_tree.tag_configure("missing", foreground="#d9534f")
        self.dependency_tree.tag_configure("installed", foreground="#5b9b68")
        self._add_tool_tab(frame, "Dependencies", "boxes", "warning")

    def _interpreter_for_project(self, project=None):
        """Resolve project override, local .venv, global setting, or current Python."""
        root = project.root if project is not None else None
        mapping = self.preferences.get("project_interpreters", {})
        selected = mapping.get(str(root)) if root is not None else None
        if selected:
            return probe_interpreter(selected)
        if root is not None:
            detected = find_project_environment(root)
            if detected is not None:
                return detected
        return probe_interpreter(self.preferences.get("interpreter_path") or sys.executable)

    def manage_interpreter(self):
        """Select a verified Python interpreter for this workspace or globally."""
        project = self._project_for_document(self._active_document())
        warning = None
        try:
            current = self._interpreter_for_project(project)
        except (OSError, ValueError, TimeoutError) as exc:
            warning = str(exc)
            current = probe_interpreter(sys.executable)
        dialog = tk.Toplevel(self)
        dialog.title("Python Interpreter")
        dialog.transient(self)
        dialog.resizable(True, False)
        body = ttk.Frame(dialog, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Workspace: " + str(project.root)).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Label(body, text="Interpreter").grid(row=1, column=0, sticky="w", pady=6)
        status = ttk.Label(body, text=current.executable)
        status.grid(row=2, column=0, columnspan=3, sticky="w", pady=6)
        if warning:
            status.configure(text="Saved interpreter is unavailable: " + warning + " — choose a replacement.")
        entries = {}
        choice = tk.StringVar(value=current.label)
        combo = ttk.Combobox(body, textvariable=choice, state="readonly", width=82)
        combo.grid(row=1, column=1, sticky="ew", padx=5)
        body.columnconfigure(1, weight=1)
        def add(info, select=False):
            entries[info.label] = info
            values = list(combo.cget("values"))
            if info.label not in values:
                values.append(info.label)
                combo.configure(values=values)
            if select:
                choice.set(info.label)
        add(current, select=True)
        status.configure(text="Scanning installed Python interpreters in the background...")
        discovery_queue = queue.Queue()
        def discovery_worker():
            try:
                discovery_queue.put(("ok", discover_interpreters()))
            except Exception as exc:
                discovery_queue.put(("error", exc))
        threading.Thread(target=discovery_worker, daemon=True).start()
        def poll_discovery():
            if not dialog.winfo_exists():
                return
            try:
                kind, value = discovery_queue.get_nowait()
            except queue.Empty:
                dialog.after(120, poll_discovery)
                return
            if kind == "error":
                status.configure(text="Interpreter discovery warning: " + str(value))
                return
            for info in value:
                add(info)
            add(current, select=True)
            status.configure(text="Found " + str(len(value)) + " verified Python interpreter(s).")
        dialog.after(120, poll_discovery)
        def browse():
            path = filedialog.askopenfilename(parent=dialog, title="Select Python", filetypes=[("Python executable", "*.exe" if os.name == "nt" else "python*"), ("All files", "*.*")])
            if path:
                try:
                    add(probe_interpreter(path), select=True)
                except (OSError, ValueError, TimeoutError) as exc:
                    messagebox.showerror("Invalid Python", str(exc), parent=dialog)
        ttk.Button(body, text="Browse...", command=browse).grid(row=1, column=2)
        def selected():
            info = entries.get(choice.get())
            if info is None:
                raise ValueError("Choose a verified Python interpreter.")
            return info
        def apply(scope):
            try:
                info = selected()
            except ValueError as exc:
                messagebox.showerror("Python Interpreter", str(exc), parent=dialog)
                return
            if scope == "project":
                mapping = dict(self.preferences.get("project_interpreters", {}))
                mapping[str(project.root)] = info.executable
                self.preferences["project_interpreters"] = mapping
            else:
                self.preferences["interpreter_path"] = info.executable
            self._persist_preferences()
            self.status.configure(text="Python " + info.version + " selected.")
            dialog.destroy()
        def reset():
            mapping = dict(self.preferences.get("project_interpreters", {}))
            mapping.pop(str(project.root), None)
            self.preferences["project_interpreters"] = mapping
            self._persist_preferences()
            self.status.configure(text="Workspace interpreter set to automatic detection.")
            dialog.destroy()
        def repair_pip():
            try:
                base = selected()
            except ValueError as exc:
                messagebox.showerror("Repair pip", str(exc), parent=dialog)
                return
            repair_button.configure(state="disabled")
            status.configure(text="Checking and repairing pip in the selected interpreter...")
            result = queue.Queue()
            def worker():
                try:
                    ensure_pip(base.executable)
                    result.put(("ok", probe_interpreter(base.executable)))
                except Exception as exc:
                    result.put(("error", exc))
            threading.Thread(target=worker, daemon=True).start()
            def poll_repair():
                try:
                    kind, value = result.get_nowait()
                except queue.Empty:
                    if dialog.winfo_exists():
                        dialog.after(100, poll_repair)
                    return
                if not dialog.winfo_exists():
                    return
                repair_button.configure(state="normal")
                if kind == "error":
                    status.configure(text="pip repair failed.")
                    messagebox.showerror("Repair pip", str(value), parent=dialog)
                    return
                add(value, select=True)
                status.configure(text="pip is available: " + value.executable)
            dialog.after(100, poll_repair)
        def create_env():
            try:
                base = selected()
            except ValueError as exc:
                messagebox.showerror("Create .venv", str(exc), parent=dialog)
                return
            target = project.root / ".venv"
            if target.exists() and (not target.is_dir() or any(target.iterdir())):
                messagebox.showerror("Create .venv", "The .venv folder already exists and is not empty.", parent=dialog)
                return
            create_button.configure(state="disabled")
            status.configure(text="Creating project virtual environment...")
            result = queue.Queue()
            def worker():
                try:
                    result.put(("ok", create_virtual_environment(base.executable, target)))
                except Exception as exc:
                    result.put(("error", exc))
            threading.Thread(target=worker, daemon=True).start()
            def poll():
                try:
                    kind, value = result.get_nowait()
                except queue.Empty:
                    if dialog.winfo_exists():
                        dialog.after(100, poll)
                    return
                if not dialog.winfo_exists():
                    return
                create_button.configure(state="normal")
                if kind == "error":
                    status.configure(text="Environment creation failed.")
                    messagebox.showerror("Create .venv", str(value), parent=dialog)
                    return
                add(value, select=True)
                mapping = dict(self.preferences.get("project_interpreters", {}))
                mapping[str(project.root)] = value.executable
                self.preferences["project_interpreters"] = mapping
                self._persist_preferences()
                status.configure(text="Created and selected " + value.executable)
                self.status.configure(text="Project virtual environment created.")
            dialog.after(100, poll)
        buttons = ttk.Frame(body)
        buttons.grid(row=3, column=0, columnspan=3, sticky="ew", pady=10)
        ttk.Button(buttons, text="Use for Workspace", command=lambda: apply("project")).pack(side="left", padx=3)
        ttk.Button(buttons, text="Use Globally", command=lambda: apply("global")).pack(side="left", padx=3)
        ttk.Button(buttons, text="Auto Detect", command=reset).pack(side="left", padx=3)
        repair_button = ttk.Button(buttons, text="Repair pip", command=repair_pip)
        repair_button.pack(side="left", padx=3)
        create_button = ttk.Button(buttons, text="Create Project .venv", command=create_env)
        create_button.pack(side="left", padx=3)
        ttk.Button(buttons, text="Close", command=dialog.destroy).pack(side="right", padx=3)
    def _update_dependency_view(self, dependencies, scan_error=None, python_executable=None):
        for item in self.dependency_tree.get_children():
            self.dependency_tree.delete(item)
        for dependency in dependencies:
            version = dependency.version or ("—" if dependency.status != "missing" else "Not installed")
            self.dependency_tree.insert(
                "", "end",
                values=(dependency.import_name, dependency.status,
                        dependency.distribution, version),
                tags=(dependency.status,),
            )
        env = python_environment(python_executable or self._interpreter_for_project(self._project_for_document(self._active_document())).executable)
        mode = "venv" if env["virtual_environment"] else "base interpreter"
        message = f"Python {env['version']} ({mode}, pip {'available' if env['pip_available'] else 'missing'}) — {env['executable']}"
        if scan_error:
            message += " | " + scan_error
        self.dependency_environment.configure(text=message)

    def scan_dependencies(self):
        document = self._active_document()
        root = self._project_for_document(document).root
        try:
            interpreter = self._interpreter_for_project(self._project_for_document(document))
        except (OSError, ValueError, TimeoutError) as exc:
            self.status.configure(text=f"Python interpreter error: {exc}")
            return
        dependencies, error = inspect_dependencies(self.editor.get_content(), search_root=root, python_executable=interpreter.executable)
        self._update_dependency_view(dependencies, error, interpreter.executable)
        self.tabs.select(self.dependency_tree.master)
        missing = sum(item.status == "missing" for item in dependencies)
        self.status.configure(
            text=f"Dependency scan complete — {len(dependencies)} imports, {missing} missing."
            if not error else "Dependency scan needs valid Python syntax."
        )

    def copy_install_command(self):
        selected = self.dependency_tree.selection()
        if not selected:
            self.status.configure(text="Select a missing dependency first.")
            return
        values = self.dependency_tree.item(selected[0], "values")
        if values[1] != "missing":
            self.status.configure(text="The selected dependency is not missing.")
            return
        try:
            interpreter = self._interpreter_for_project(self._project_for_document(self._active_document()))
        except (OSError, ValueError, TimeoutError) as exc:
            self.status.configure(text=f"Python interpreter error: {exc}")
            return
        env = python_environment(interpreter.executable)
        command = f'"{env["executable"]}" -m pip install "{values[2]}"'
        self.clipboard_clear()
        self.clipboard_append(command)
        self.status.configure(text="Interpreter-specific install command copied.")

    def _errors_panel(self):
        frame = ttk.Frame(self.tabs, padding=4)
        self.error_summary = ttk.Label(frame, text="No diagnostics.")
        self.error_summary.pack(fill="x", pady=(0, 4))
        columns = ("type", "line", "column", "message", "source")
        self.error_tree = ttk.Treeview(frame, columns=columns, show="headings", height=7)
        self.error_tree.heading("type", text="Type")
        self.error_tree.heading("line", text="Line")
        self.error_tree.heading("column", text="Column")
        self.error_tree.heading("message", text="Message")
        self.error_tree.heading("source", text="Source Line")
        self.error_tree.column("type", width=125, stretch=False)
        self.error_tree.column("line", width=48, anchor="center", stretch=False)
        self.error_tree.column("column", width=58, anchor="center", stretch=False)
        self.error_tree.column("message", width=330)
        self.error_tree.column("source", width=360)
        self.error_tree.pack(fill="both", expand=True)
        self.error_tree.tag_configure("error", foreground="#ef6b73")
        self.error_tree.tag_configure("warning", foreground="#e6b45a")
        self.error_tree.tag_configure("info", foreground="#4f8cff")
        self.error_tree.bind("<<TreeviewSelect>>", self._navigate_to_selected_error)
        self.error_tree.bind("<Double-1>", self._navigate_to_selected_error)
        self._add_tool_tab(frame, "Problems", "exclamation-triangle", "danger")

    def _show(self, panel, content):
        panel.configure(state="normal")
        panel.delete("1.0", "end")
        panel.insert("1.0", content)
        panel.configure(state="disabled")
        self.tabs.select(panel.master)

    def _set_diagnostics(self, diagnostics):
        self.diagnostics = list(diagnostics)
        self.editor.clear_diagnostic()
        for item in self.error_tree.get_children():
            self.error_tree.delete(item)
        for index, diagnostic in enumerate(self.diagnostics):
            severity = (
                "warning" if "warning" in diagnostic.error_type.lower()
                else "info" if "info" in diagnostic.error_type.lower()
                else "error"
            )
            self.error_tree.insert(
                "", "end", iid=str(index),
                values=(
                    diagnostic.error_type, diagnostic.line,
                    diagnostic.column + 1, diagnostic.message,
                    diagnostic.source_line.strip(),
                ),
                tags=(severity,),
            )
        count = len(self.diagnostics)
        self.error_summary.configure(
            text=f"{count} diagnostic(s) found. Select or double-click an item to jump to its location."
            if count else "No diagnostics. The current source passed lexical and syntax checks."
        )

    def _navigate_to_selected_error(self, event=None):
        selection = self.error_tree.selection()
        if not selection:
            return
        try:
            diagnostic = self.diagnostics[int(selection[0])]
        except (ValueError, IndexError):
            return
        self.editor.show_diagnostic(
            diagnostic.line, diagnostic.column,
            diagnostic.end_line, diagnostic.end_column,
        )
        self.status.configure(
            text=f"{diagnostic.error_type} — line {diagnostic.line}, column {diagnostic.column + 1}"
        )

    def _refresh_diagnostics(self):
        diagnostics = collect_diagnostics(self.editor.get_content())
        self._set_diagnostics(diagnostics)
        return diagnostics

    def mark_dirty(self, editor=None):
        editor = editor or self.editor
        document = self.documents.get(editor)
        if document is not None:
            document["dirty"] = True
            self.editor_tabs.tab(document["frame"], text=self._tab_label(document))
            if self.editor is editor:
                self._sync_active_document()
                if self.diagnostics:
                    self._set_diagnostics([])
                    self.error_summary.configure(text="Source changed. Run Analyze All to refresh diagnostics.")
        editor.clear_diagnostic()

    def _project_for_document(self, document=None):
        """Resolve a project context for a document or the current workspace."""
        path = document.get("path") if document else None
        if self.project is not None and (path is None or self.project.contains(path)):
            return self.project
        if path is not None:
            return Project.from_file(path)
        return self.project or Project.open(Path.cwd())

    def _confirm_all_dirty_documents(self):
        """Resolve every modified tab before changing the active workspace."""
        previous = self.editor
        previous_tab = self.editor_tabs.select()
        for editor, document in list(self.documents.items()):
            if not document["dirty"]:
                continue
            self.editor_tabs.select(document["frame"])
            self.editor = editor
            self._sync_active_document()
            answer = messagebox.askyesnocancel(
                "Unsaved Changes",
                f"Save changes to {document['path'].name if document['path'] else 'Untitled'} "
                "before changing the workspace?\\n\\n"
                "Choose No to keep this tab open with its unsaved changes."
            )
            if answer is None or (answer and not self.save_file()):
                if previous in self.documents:
                    self.editor_tabs.select(self.documents[previous]["frame"])
                    self.editor = previous
                    self._sync_active_document()
                elif previous_tab:
                    self.editor_tabs.select(previous_tab)
                return False
        if previous in self.documents:
            self.editor_tabs.select(self.documents[previous]["frame"])
            self.editor = previous
            self._sync_active_document()
        elif previous_tab:
            self.editor_tabs.select(previous_tab)
        return True

    def _remember_workspace(self, path):
        """Persist active workspace and maintain a bounded recent list."""
        normalized = str(Path(path).expanduser().resolve())
        recent = self.preferences.get("recent_workspaces", [])
        recent = [item for item in recent if isinstance(item, str)
                  and Path(item).expanduser() != Path(normalized)]
        self.preferences["recent_workspaces"] = [normalized] + recent[:7]
        self.preferences["last_workspace"] = normalized
        self._persist_preferences()
        self._refresh_recent_workspace_menu()

    def _refresh_recent_workspace_menu(self):
        menu = getattr(self, "recent_workspace_menu", None)
        if menu is None:
            return
        menu.delete(0, "end")
        recent = self.preferences.get("recent_workspaces", [])
        valid = [item for item in recent if isinstance(item, str) and Path(item).is_dir()]
        if not valid:
            menu.add_command(label="No recent workspaces", state="disabled")
        else:
            for item in valid:
                menu.add_command(
                    label=Path(item).name + " — " + item,
                    command=lambda value=item: self._activate_workspace(value),
                )
        menu.add_separator()
        menu.add_command(label="Clear Recent Workspaces", command=self.clear_recent_workspaces)

    def clear_recent_workspaces(self):
        """Clear workspace history without changing the current workspace."""
        self.preferences["recent_workspaces"] = []
        self._persist_preferences()
        self._refresh_recent_workspace_menu()
        self.status.configure(text="Recent workspace history cleared.")

    def _activate_workspace(self, folder):
        """Validate and activate a workspace after protecting unsaved documents."""
        try:
            candidate = Project.open(folder)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Workspace Error", str(exc))
            return False
        if self.project is not None and self.project.root == candidate.root:
            self.status.configure(text=f"Workspace already open: {candidate.root}")
            return True
        if not self._confirm_all_dirty_documents():
            self.status.configure(text="Workspace change cancelled.")
            return False
        self.project = candidate
        self.project_root = candidate.root
        self._remember_workspace(candidate.root)
        self._populate_project_tree()
        self.workspace_path_label.configure(text=str(candidate.root))
        self.status.configure(text=f"Workspace opened: {candidate.root}")
        self.git_panel.refresh()
        return True

    def open_project_folder(self):
        """Choose and open a workspace without losing unsaved editor changes."""
        options = {"title": "Open Workspace Folder"}
        if self.project_root and self.project_root.is_dir():
            options["initialdir"] = str(self.project_root)
        folder = filedialog.askdirectory(**options)
        if folder:
            self._activate_workspace(folder)

    def close_workspace(self):
        """Close the active workspace while keeping editor tabs available."""
        if self.project is None:
            self.status.configure(text="No workspace is currently open.")
            return
        if not self._confirm_all_dirty_documents():
            self.status.configure(text="Close workspace cancelled.")
            return
        closed = self.project.root
        self.project = None
        self.project_root = None
        self.project_tree.delete(*self.project_tree.get_children())
        self.workspace_path_label.configure(text="No folder opened — use Open Folder to start a workspace")
        self.preferences["last_workspace"] = ""
        self._persist_preferences()
        self.status.configure(text=f"Workspace closed: {closed}. Open editor tabs were kept.")
        self.git_panel.refresh()

    def _restore_last_workspace(self):
        """Restore the most recently used workspace when it still exists."""
        previous = self.preferences.get("last_workspace", "")
        if not previous:
            return
        try:
            self.project = Project.open(previous)
        except (OSError, ValueError):
            self.preferences["last_workspace"] = ""
            self._persist_preferences()
            return
        self.project_root = self.project.root
        self._remember_workspace(self.project_root)
        self.workspace_path_label.configure(text=str(self.project_root))
        self._populate_project_tree()
        self.git_panel.refresh()

    def refresh_workspace(self):
        """Refresh the workspace tree from disk."""
        if self.project is None:
            self.status.configure(text="Open a folder to create a workspace first.")
            return
        self._populate_project_tree()
        self.status.configure(text="Workspace refreshed.")

    @staticmethod
    def _file_display_name(path):
        info = file_type_for(path)
        return f"{info.icon} {Path(path).name}"

    def _open_external_file(self, path):
        """Open a recognized non-text file with the operating system default app."""
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
            self.status.configure(text=f"Opened with system application: {path.name}")
        except (OSError, AttributeError) as exc:
            messagebox.showerror("Open File", f"Could not open {path.name}: {exc}")

    def _select_open_document(self, path):
        resolved = Path(path).resolve()
        for editor, document in self.documents.items():
            if document["path"] and document["path"].resolve() == resolved:
                self.editor_tabs.select(document["frame"])
                self.editor = editor
                self._sync_active_document()
                return True
        return False

    def _open_path(self, path):
        """Open a workspace file, editing text or delegating binary files to the OS."""
        path = Path(path).expanduser().resolve()
        if path.is_dir():
            self._activate_workspace(path)
            return
        if not path.is_file():
            messagebox.showerror("Open File", f"File does not exist: {path}")
            return
        if self._select_open_document(path):
            return
        info = file_type_for(path)
        if not info.is_text:
            self._open_external_file(path)
            return
        try:
            content = read_text_file(path)
        except (OSError, UnicodeError) as exc:
            messagebox.showerror("Open Error", f"Could not read {path.name}: {exc}")
            return
        self._create_document(path=path, content=content)
        self.clear_results()
        self.status.configure(text=f"Opened {path.name} ({info.description}).")

    def _populate_project_tree(self):
        self.project_tree.delete(*self.project_tree.get_children())
        if self.project_root is None:
            return
        root_id = self.project_tree.insert(
            "", "end", text=self.project_root.name,
            image=self._icon("folder-fill", self.theme_palette.get("accent"), 16),
            values=(str(self.project_root), "directory"), tags=("directory",), open=True,
        )
        ignored = {
            ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
            ".mypy_cache", ".ruff_cache", ".tox", "node_modules",
        }

        def add_children(parent_id, directory):
            try:
                entries = sorted(
                    directory.iterdir(),
                    key=lambda item: (not item.is_dir(), item.name.lower()),
                )
            except OSError:
                return
            for entry in entries:
                if entry.name in ignored or entry.is_symlink():
                    continue
                if entry.is_dir():
                    node = self.project_tree.insert(
                        parent_id, "end", text=entry.name,
                        image=self._icon("folder", self.theme_palette.get("accent"), 16),
                        values=(str(entry), "directory"), tags=("directory",), open=False,
                    )
                    add_children(node, entry)
                elif entry.is_file():
                    info = file_type_for(entry)
                    icon_color = self.theme_palette.get(
                        f"file_{info.kind}", self.theme_palette.get("editor_fg")
                    )
                    self.project_tree.insert(
                        parent_id, "end", text=entry.name,
                        image=self._icon(self._file_icon_name(info.kind), icon_color, 16),
                        values=(str(entry), info.kind), tags=(info.kind,),
                    )

        add_children(root_id, self.project_root)

    def _on_project_tree_open(self, event=None):
        selection = self.project_tree.selection()
        if not selection:
            return
        values = self.project_tree.item(selection[0], "values")
        if not values:
            return
        path = Path(values[0])
        if path.is_dir():
            is_open = bool(self.project_tree.item(selection[0], "open"))
            self.project_tree.item(selection[0], open=not is_open)
            return "break"
        self._open_path(path)

    def _resolved_ui_font(self, available_fonts=None):
        """Choose a polished installed interface font on each supported platform."""
        available = set(available_fonts or tkfont.families(self))
        requested = self.preferences.get("ui_font_family", DEFAULTS["ui_font_family"])
        candidates = (
            requested, "Segoe UI", "Inter", "Noto Sans", "Ubuntu",
            "DejaVu Sans", "Arial", "Tahoma", "TkDefaultFont",
        )
        return next((family for family in candidates if family in available), "TkDefaultFont")

    def _resolved_code_font(self, available_fonts=None):
        """Choose the best installed coding font with reliable cross-platform fallbacks."""
        available = set(available_fonts or tkfont.families(self))
        requested = self.preferences.get("font_family", DEFAULTS["font_family"])
        candidates = (
            requested, "JetBrains Mono", "Cascadia Code", "Fira Code",
            "Consolas", "Cascadia Mono", "DejaVu Sans Mono",
            "Liberation Mono", "Courier New", "Lucida Console", "TkFixedFont",
        )
        return next((family for family in candidates if family in available), "TkFixedFont")

    def _tab_label(self, document):
        name = document["path"].name if document["path"] else "Untitled"
        return f"{'*' if document['dirty'] else ''}{name}  ×"

    def _on_tab_close_click(self, event):
        """Close a tab only when its visible close glyph is clicked."""
        try:
            index = self.editor_tabs.index(f"@{event.x},{event.y}")
            x, _y, width, _height = self.editor_tabs.bbox(index)
        except (tk.TclError, ValueError):
            return
        if event.x < x + width - 25:
            return
        frame = self.editor_tabs.tabs()[index]
        self.editor_tabs.select(frame)
        for editor, document in self.documents.items():
            if str(document["frame"]) == frame:
                self.editor = editor
                self._sync_active_document()
                self.close_tab()
                return "break"

    def close_tab(self):
        """Close the active document after resolving its unsaved changes."""
        document = self._active_document()
        if document is None or not self._confirm():
            return
        frame = document["frame"]
        self.editor_tabs.forget(frame)
        del self.documents[self.editor]
        if not self.documents:
            self._create_document()
        else:
            selected = self.editor_tabs.select()
            for editor, item in self.documents.items():
                if str(item["frame"]) == selected:
                    self.editor = editor
                    break
            self._sync_active_document()
        self._set_diagnostics([])
        self.status.configure(text="Tab closed.")

    def _create_document(self, path=None, content=""):
        """Create a new editor tab and register its independent document state."""
        frame = ttk.Frame(self.editor_tabs)
        editor = CodeEditor(frame, on_change=lambda: self.mark_dirty(editor))
        editor.pack(fill="both", expand=True)
        editor.set_content(content)
        self.documents[editor] = {
            "frame": frame, "path": Path(path) if path else None, "dirty": False,
        }
        document = self.documents[editor]
        if document["path"]:
            file_info = file_type_for(document["path"])
            tab_icon = self._file_icon_name(file_info.kind)
            tab_color = self.theme_palette.get(
                f"file_{file_info.kind}", self.theme_palette.get("editor_fg")
            )
        else:
            tab_icon = "file-earmark-plus"
            tab_color = self.theme_palette.get("accent")
        self.editor_tabs.add(
            frame, text=self._tab_label(document),
            image=self._icon(tab_icon, tab_color), compound="left",
        )
        self.editor_tabs.select(frame)
        self.editor = editor
        editor.set_font_family(self._resolved_code_font())
        editor.set_font_size(self.preferences["font_size"])
        editor.set_theme(self.dark, self.theme_palette)
        self._sync_active_document()
        self.editor.set_breakpoints(self.breakpoints.get(editor, set()))
        return editor

    def _active_document(self):
        return self.documents.get(self.editor)

    def _sync_active_document(self):
        document = self._active_document()
        if document is None:
            self.current_path = None
            self.dirty = False
            return
        self.current_path = document["path"]
        self.dirty = document["dirty"]
        self._title()

    def _on_tab_changed(self, event=None):
        selected = self.editor_tabs.select()
        if not selected:
            return
        for editor, document in self.documents.items():
            if str(document["frame"]) == selected:
                self.editor = editor
                self._sync_active_document()
                self.editor.set_breakpoints(self.breakpoints.get(self.editor, set()))
                self._set_diagnostics([])
                break

    def _title(self):
        # Keep the application identity stable; document names and dirty state
        # are represented by editor tabs and their modified markers.
        self.title("PyLex Studio")

    def _confirm(self):
        document = self._active_document()
        if document is None or not document["dirty"]:
            return True
        answer = messagebox.askyesnocancel(
            "Unsaved Changes",
            f"Save changes to {document['path'].name if document['path'] else 'Untitled'} before continuing?"
        )
        if answer is None:
            return False
        return self.save_file() if answer else True

    def new_file(self):
        self._create_document()

    def open_file(self):
        path = filedialog.askopenfilename(
            title="Open File",
            filetypes=[("All files", "*.*"), ("Python files", "*.py")],
        )
        if path:
            self._open_path(path)

    def save_file(self):
        document = self._active_document()
        if document is None:
            return False
        if document["path"] is None:
            return self.save_as()
        try:
            document["path"].write_text(self.editor.get_content(), encoding="utf-8")
            document["dirty"] = False
            self.editor_tabs.tab(document["frame"], text=self._tab_label(document))
            self._sync_active_document()
            self.status.configure(text="File saved.")
            return True
        except OSError as exc:
            messagebox.showerror("Save Error", str(exc))
            return False

    def save_as(self):
        document = self._active_document()
        if document is None:
            return False
        path = filedialog.asksaveasfilename(
            defaultextension=".py",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )
        if not path:
            return False
        path = Path(path)
        for editor, other in self.documents.items():
            if editor is not self.editor and other["path"] and other["path"].resolve() == path.resolve():
                messagebox.showerror("Save Error", "That file is already open in another tab.")
                return False
        document["path"] = path
        return self.save_file()


    def analyze_lexical(self):
        source = self.editor.get_content()
        try:
            tokens = lexical_analysis(source)
            report = format_tokens(tokens)
            self.status.configure(text=f"Lexical analysis complete — {len(tokens)} tokens.")
        except Exception as exc:
            report = f"{type(exc).__name__}: {exc}"
            self.status.configure(text=f"Lexical analysis failed — {type(exc).__name__}.")
        self._show(self.lexical, report)
        self._refresh_diagnostics()

    def analyze_syntax(self):
        result = syntax_analysis(self.editor.get_content())
        report = f"{result.error_type or 'Success'}: {result.message}"
        if result.details:
            report += f"\n{result.details}"
        if result.line is not None:
            report += f"\nLine: {result.line} | Column: {result.column}"
        self._show(self.syntax, report)
        self._refresh_diagnostics()
        self.status.configure(
            text="Syntax analysis successful." if result.success
            else f"{result.error_type or 'Syntax error'} detected."
        )

    def analyze_all(self):
        source = self.editor.get_content()
        try:
            tokens = lexical_analysis(source)
            lexical_report = format_tokens(tokens)
            lexical_status = f"{len(tokens)} tokens"
        except Exception as exc:
            lexical_report = f"{type(exc).__name__}: {exc}"
            lexical_status = f"failed ({type(exc).__name__})"
        syntax = syntax_analysis(source)
        syntax_report = f"{syntax.error_type or 'Success'}: {syntax.message}"
        if syntax.details:
            syntax_report += f"\n{syntax.details}"
        if syntax.line is not None:
            syntax_report += f"\nLine: {syntax.line} | Column: {syntax.column}"
        diagnostics = self._refresh_diagnostics()
        self._show(self.lexical, lexical_report)
        self._show(self.syntax, syntax_report)
        self.tabs.select(self.error_tree.master)
        self.status.configure(
            text=f"Analysis complete — {lexical_status}; "
                 f"{'syntax valid' if syntax.success else syntax.error_type}; "
                 f"{len(diagnostics)} diagnostic(s)."
        )

    def clear_results(self):
        for panel in (self.output, self.lexical, self.syntax):
            panel.configure(state="normal")
            panel.delete("1.0", "end")
            panel.configure(state="disabled")
        for item in self.error_tree.get_children():
            self.error_tree.delete(item)
        self.diagnostics = []
        self.error_summary.configure(text="Results cleared.")
        self.editor.clear_diagnostic()
        self.status.configure(text="Analysis results cleared.")

    def run_code(self):
        if self.debug_session is not None and not self.debug_session.done:
            self.status.configure(text="Stop debugging before starting normal execution.")
            return
        if self.execution is not None and not self.execution.done:
            self.status.configure(text="A program is already running. Force Stop it before starting another.")
            return
        source = self.editor.get_content()
        document = self._active_document()
        project = self._project_for_document(document)
        try:
            interpreter = self._interpreter_for_project(project)
        except (OSError, ValueError, TimeoutError) as exc:
            messagebox.showerror("Python Interpreter", str(exc))
            return
        dependencies, scan_error = inspect_dependencies(source, search_root=project.root, python_executable=interpreter.executable)
        self._update_dependency_view(dependencies, scan_error, interpreter.executable)
        self._show(self.output, "")
        env = python_environment(interpreter.executable)
        self._append_output(
            f"Python: {env['version']} | {env['executable']}\n"
            f"Environment: {'virtual environment' if env['virtual_environment'] else 'base interpreter'}\n",
            "system",
        )
        missing = [item for item in dependencies if item.status == "missing"]
        if scan_error:
            self._append_output(scan_error + "\n", "stderr")
        if missing:
            lines = [
                "DEPENDENCY CHECK — missing imports detected",
                "Install into this exact interpreter using the commands below:",
            ]
            lines.extend(
                f"  • {item.import_name} → {item.distribution}: "
                f"{env['executable']} -m pip install {item.distribution}"
                for item in missing
            )
            if not env["pip_available"]:
                lines.append("pip is unavailable in this interpreter. Use Tools → Python Interpreter → Repair pip first.")
            lines.append(
                "Static scanning cannot detect every dynamic import; runtime errors are also reported.\n"
            )
            self._append_output("\n".join(lines) + "\n", "system")
        elif not scan_error:
            self._append_output("Dependency check: no missing imports detected.\n", "system")
        self._append_output("Starting program...\n", "system")
        try:
            timeout = self.preferences["timeout_seconds"]
            self.execution = self.execution_service.start_document(
                source, document.get("path") if document else None, project,
                timeout=timeout, dirty=bool(document and document.get("dirty")),
                python_executable=interpreter.executable,
            )
        except OSError as exc:
            self._append_output(f"Could not start Python process: {exc}\n", "stderr")
            self.status.configure(text="Could not start Python process.")
            return
        timeout_label = "unlimited" if timeout is None else f"{timeout} seconds"
        self._append_output(f"Execution timeout: {timeout_label}.\n", "system")
        self._last_timeout_display = None
        self.status.configure(
            text=f"Running — timeout: {timeout_label}. Shift+F5 / Force Stop terminates the process tree."
        )
        self._poll_execution()

    def stop_execution(self):
        if self.execution is not None and not self.execution.done:
            self.execution.force_stop()
            self.status.configure(text="Force-stopping process and child processes...")
            return
        if self.debug_session is not None and not self.debug_session.done:
            self.debug_session.stop()
            self.status.configure(text="Force-stopping debugger and child processes...")
            return
        self.status.configure(text="No program is currently running.")

    def _poll_execution(self):
        handle = self.execution
        if handle is None:
            return
        for channel, content in handle.read_available():
            self._append_output(content, channel)
        if not handle.done:
            timeout = handle.timeout
            if timeout is None:
                display = "unlimited"
                status_text = "Running — no time limit. Use Force Stop / Shift+F5 to terminate."
            else:
                remaining = max(0, int(timeout - (time.monotonic() - handle.started_at) + 0.999))
                display = str(remaining)
                status_text = (
                    f"Running — {remaining}s remaining before timeout. "
                    "Use Force Stop / Shift+F5 to terminate."
                )
            if display != self._last_timeout_display:
                self.status.configure(text=status_text)
                self._last_timeout_display = display
            self._execution_poll = self.after(60, self._poll_execution)
            return
        result = handle.result
        # Drain any final chunks queued as the reader threads close.
        for channel, content in handle.read_available():
            self._append_output(content, channel)
        self._append_output(
            f"\n{'=' * 64}\nExecution: {result.status.upper()}\n"
            f"Exit code: {result.exit_code}\nDuration: {result.duration:.2f}s\n",
            "system",
        )
        if result.stderr:
            self._report_runtime_error(result.stderr)
        self.status.configure(
            text=f"Execution {result.status} — exit code {result.exit_code}."
        )
        self.execution = None
        self._execution_poll = None

    def _append_output(self, content, channel="stdout"):
        self.output.configure(state="normal")
        self.output.insert("end", content, channel if channel in {"stdout", "stderr", "system"} else "stdout")
        self.output.see("end")
        self.output.configure(state="disabled")

    def clear_output(self):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")
        self.status.configure(text="Output cleared.")

    def save_output(self):
        content = self.output.get("1.0", "end-1c")
        if not content:
            self.status.configure(text="There is no output to save.")
            return
        path = filedialog.asksaveasfilename(
            title="Save Execution Output", defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("Log files", "*.log"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            Path(path).write_text(content, encoding="utf-8")
            self.status.configure(text=f"Output saved to {path}.")
        except OSError as exc:
            messagebox.showerror("Save Output Error", str(exc))

    def _report_runtime_error(self, stderr):
        exception_matches = re.findall(
            r"^([A-Za-z_][\w.]*(?:Error|Exception)): (.*)$",
            stderr, re.MULTILINE,
        )
        if not exception_matches:
            return
        error_type, message = exception_matches[-1]
        line_matches = re.findall(r'File "[^"]+", line (\d+)', stderr)
        line = int(line_matches[-1]) if line_matches else 1
        source_lines = self.editor.get_content().splitlines()
        source_line = source_lines[line - 1] if 1 <= line <= len(source_lines) else ""
        if error_type == "ModuleNotFoundError":
            missing = re.search(r"No module named ['\"]([^'\"]+)['\"]", message)
            if missing:
                module = missing.group(1)
                from .dependencies import PIP_NAMES
                package = PIP_NAMES.get(module.split(".", 1)[0], module.split(".", 1)[0])
                interpreter = self._interpreter_for_project(self._project_for_document(self._active_document())).executable
                message = (
                    f"Missing library '{module}'. Install it into the active interpreter with: "
                    f'"{interpreter}" -m pip install "{package}"'
                )
        from .analyzer import Diagnostic
        diagnostic = Diagnostic(
            error_type, message, line, 0, line, 0, source_line,
        )
        self._set_diagnostics([diagnostic])
        self.tabs.select(self.error_tree.master)
        self.status.configure(text=f"Runtime error: {error_type} — line {line}. See Errors and Output.")

    def toggle_breakpoint(self):
        line = int(self.editor.text.index("insert").split(".")[0])
        points = self.breakpoints.setdefault(self.editor, set())
        if line in points:
            points.remove(line)
            self.conditional_breakpoints.setdefault(self.editor, {}).pop(line, None)
            if self.debug_session is not None and not self.debug_session.done:
                self.debug_session.clear_breakpoint(line)
            self.editor.set_breakpoints(points)
            self.status.configure(text=f"Breakpoint removed from line {line}.")
        else:
            points.add(line)
            self.conditional_breakpoints.setdefault(self.editor, {}).pop(line, None)
            if self.debug_session is not None and not self.debug_session.done:
                self.debug_session.set_breakpoint(line)
            self.editor.set_breakpoints(points)
            self.status.configure(text=f"Breakpoint set on line {line}.")
        return line

    def start_debugging(self):
        if self.debug_session is not None and self.debug_session.done:
            self.debug_session.close()
            self.debug_session = None
        if self.execution is not None and not self.execution.done:
            self.status.configure(text="Stop normal execution before starting the debugger.")
            return
        if self.debug_session is not None and not self.debug_session.done:
            self.status.configure(text="A debugging session is already active.")
            return
        try:
            document = self._active_document()
            project = self._project_for_document(document)
            self.debug_session = self.execution_service.start_debugger_document(
                self.editor.get_content(), document.get("path") if document else None,
                project, dirty=bool(document and document.get("dirty")),
                python_executable=self._interpreter_for_project(project).executable,
            )
        except (OSError, ValueError, TimeoutError) as exc:
            messagebox.showerror("Debugger Error", str(exc))
            return
        self._show(self.output, "Debugger started. Set breakpoints, then choose Continue.\n")
        conditions = self.conditional_breakpoints.get(self.editor, {})
        for line in sorted(self.breakpoints.get(self.editor, set())):
            condition = conditions.get(line)
            if condition:
                self.debug_session.set_conditional_breakpoint(line, condition)
            else:
                self.debug_session.set_breakpoint(line)
        self.status.configure(text="Debugger ready — set breakpoints or press Continue.")
        self._poll_debugger()

    def debug_continue(self):
        if self.debug_session is None or self.debug_session.done:
            self.status.configure(text="No active debugging session.")
            return
        self.debug_session.continue_execution()
        self.status.configure(text="Debugger running...")

    def debug_step(self):
        if self.debug_session is None or self.debug_session.done:
            self.status.configure(text="No active debugging session.")
            return
        self.debug_session.step()
        self.status.configure(text="Stepping into next statement...")

    def debug_next(self):
        if self.debug_session is None or self.debug_session.done:
            self.status.configure(text="No active debugging session.")
            return
        self.debug_session.next()
        self.status.configure(text="Stepping over current statement...")

    def debug_variables(self):
        if self.debug_session is None or self.debug_session.done:
            self.status.configure(text="No active debugging session.")
            return
        self.debug_session.inspect_variables()
        self.status.configure(text="Requested current-frame variables.")

    def debug_stack(self):
        if self.debug_session is None or self.debug_session.done:
            self.status.configure(text="No active debugging session.")
            return
        self.debug_session.command("where")
        self.status.configure(text="Requested current stack trace.")

    def _active_debug_session(self):
        session = self.debug_session
        if session is None or session.done:
            self.status.configure(text="No active debugging session.")
            return None
        return session

    def debug_arguments(self):
        session = self._active_debug_session()
        if session is not None:
            session.show_arguments()
            self.status.configure(text="Requested current function arguments.")

    def debug_until(self):
        session = self._active_debug_session()
        if session is None:
            return
        line = int(self.editor.text.index("insert").split(".")[0])
        session.until(line)
        self.status.configure(text=f"Running until line {line}.")

    def debug_return(self):
        session = self._active_debug_session()
        if session is not None:
            session.return_from_frame()
            self.status.configure(text="Running until the current function returns.")

    def debug_jump(self):
        session = self._active_debug_session()
        if session is None:
            return
        line = simpledialog.askinteger(
            "Debugger — Jump to Line", "Target line:",
            parent=self, minvalue=1,
        )
        if line is not None:
            try:
                session.jump(line)
                self.status.configure(text=f"Requested jump to line {line} (pdb frame restrictions apply).")
            except ValueError as exc:
                messagebox.showerror("Debugger", str(exc))

    def debug_evaluate(self):
        session = self._active_debug_session()
        if session is None:
            return
        expression = simpledialog.askstring(
            "Debugger — Evaluate", "Python expression in the selected frame:",
            parent=self,
        )
        if expression is None:
            return
        try:
            session.pretty_print(expression)
            self.status.configure(text="Expression evaluation requested; see Output.")
        except ValueError as exc:
            messagebox.showerror("Debugger", str(exc))

    def debug_temporary_breakpoint(self):
        session = self._active_debug_session()
        if session is None:
            return
        line = int(self.editor.text.index("insert").split(".")[0])
        try:
            session.set_temporary_breakpoint(line)
            self.status.configure(text=f"Temporary breakpoint requested at line {line}.")
        except ValueError as exc:
            messagebox.showerror("Debugger", str(exc))

    def debug_conditional_breakpoint(self):
        session = self._active_debug_session()
        if session is None:
            return
        line = int(self.editor.text.index("insert").split(".")[0])
        condition = simpledialog.askstring(
            "Conditional Breakpoint",
            f"Stop at line {line} only when this expression is true:",
            parent=self,
        )
        if condition is None:
            return
        try:
            session.set_conditional_breakpoint(line, condition)
            self.breakpoints.setdefault(self.editor, set()).add(line)
            self.conditional_breakpoints.setdefault(self.editor, {})[line] = condition
            self.editor.set_breakpoints(self.breakpoints[self.editor])
            self.status.configure(text=f"Conditional breakpoint requested at line {line}.")
        except ValueError as exc:
            messagebox.showerror("Debugger", str(exc))

    def debug_manage_breakpoint(self, action):
        session = self._active_debug_session()
        if session is None:
            return
        number = simpledialog.askinteger(
            "Debugger — Breakpoint",
            "Breakpoint number (shown by pdb's breakpoint list):",
            parent=self, minvalue=1,
        )
        if number is None:
            return
        try:
            if action == "enable":
                session.enable_breakpoint(number)
                message = f"Enabled breakpoint {number}."
            elif action == "disable":
                session.disable_breakpoint(number)
                message = f"Disabled breakpoint {number}."
            else:
                count = simpledialog.askinteger(
                    "Ignore Breakpoint Hits", "Number of hits to ignore:",
                    parent=self, minvalue=1,
                )
                if count is None:
                    return
                session.ignore_breakpoint(number, count)
                message = f"Breakpoint {number} will ignore the next {count} hit(s)."
            self.status.configure(text=message)
        except ValueError as exc:
            messagebox.showerror("Debugger", str(exc))

    def debug_clear_breakpoints(self):
        points = self.breakpoints.setdefault(self.editor, set())
        points.clear()
        self.conditional_breakpoints.setdefault(self.editor, {}).clear()
        self.editor.set_breakpoints(points)
        session = self._active_debug_session()
        if session is not None:
            session.clear_all_breakpoints()
        self.status.configure(text="All breakpoints cleared.")

    def stop_debugging(self):
        if self.debug_session is None:
            self.status.configure(text="No active debugging session.")
            return
        self.debug_session.stop()
        self.status.configure(text="Stopping debugger...")

    def _poll_debugger(self):
        session = self.debug_session
        if session is None:
            return
        output = session.read_available()
        if output:
            self._append_output(output)
            if "The program finished" in output or "The program exited" in output:
                self.status.configure(text="Program finished — choose Stop Debugging to close the debugger.")
        if session.done:
            session.close()
            self.debug_session = None
            self._debug_poll = None
            self.status.configure(text="Debugging session finished.")
            return
        self._debug_poll = self.after(80, self._poll_debugger)

    def find_replace(self):
        """Open a compact find-and-replace dialog for the active editor."""
        dialog = tk.Toplevel(self)
        dialog.title("Find and Replace")
        dialog.transient(self)
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=10)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Find").grid(row=0, column=0, sticky="w", pady=3)
        find_entry = ttk.Entry(body, width=34)
        find_entry.grid(row=0, column=1, columnspan=3, sticky="ew", pady=3)
        ttk.Label(body, text="Replace").grid(row=1, column=0, sticky="w", pady=3)
        replace_entry = ttk.Entry(body, width=34)
        replace_entry.grid(row=1, column=1, columnspan=3, sticky="ew", pady=3)
        status = ttk.Label(body, text="")
        status.grid(row=2, column=0, columnspan=4, sticky="w", pady=4)

        def find_next():
            needle = find_entry.get()
            if not needle:
                status.configure(text="Enter text to find.")
                return
            text_widget = self.editor.text
            start = text_widget.index("insert")
            match = text_widget.search(needle, start, stopindex="end")
            if not match:
                match = text_widget.search(needle, "1.0", stopindex=start)
            if match:
                end = "{}+{}c".format(match, len(needle))
                text_widget.tag_remove("sel", "1.0", "end")
                text_widget.tag_add("sel", match, end)
                text_widget.mark_set("insert", end)
                text_widget.see(match)
                text_widget.focus_set()
                status.configure(text="Match found.")
            else:
                status.configure(text="No matches found.")

        def replace_one():
            needle = find_entry.get()
            if not needle:
                return
            text_widget = self.editor.text
            try:
                selected = text_widget.get("sel.first", "sel.last")
            except tk.TclError:
                selected = ""
            if selected == needle:
                text_widget.delete("sel.first", "sel.last")
                text_widget.insert("insert", replace_entry.get())
                status.configure(text="One occurrence replaced.")
            find_next()

        def replace_all():
            needle = find_entry.get()
            if not needle:
                return
            text_widget = self.editor.text
            count = 0
            position = "1.0"
            while True:
                match = text_widget.search(needle, position, stopindex="end")
                if not match:
                    break
                end = "{}+{}c".format(match, len(needle))
                text_widget.delete(match, end)
                text_widget.insert(match, replace_entry.get())
                position = "{}+{}c".format(match, len(replace_entry.get()))
                count += 1
            status.configure(text="{} occurrence(s) replaced.".format(count))

        ttk.Button(body, text="Find Next", command=find_next).grid(row=3, column=1, sticky="ew", padx=2)
        ttk.Button(body, text="Replace", command=replace_one).grid(row=3, column=2, sticky="ew", padx=2)
        ttk.Button(body, text="Replace All", command=replace_all).grid(row=3, column=3, sticky="ew", padx=2)
        find_entry.focus_set()
        dialog.bind("<Return>", lambda _event: find_next())

    def zoom(self, delta):
        self.preferences["font_size"] = max(7, min(40, self.editor.font_size + delta))
        for editor in self.documents:
            editor.set_font_size(self.preferences["font_size"])
        self._persist_preferences()
        self.status.configure(text=f"Editor font size: {self.preferences['font_size']}")

    def _persist_preferences(self):
        try:
            save_preferences(self.preferences)
        except OSError as exc:
            self.status.configure(text=f"Could not save preferences: {exc}")

    def toggle_project_explorer(self):
        visible = bool(self.preferences["show_project_explorer"])
        if visible:
            self.workspace.forget(self.explorer_frame)
        else:
            self.workspace.insert(0, self.explorer_frame, weight=1)
        self.preferences["show_project_explorer"] = not visible
        self._persist_preferences()

    def open_preferences(self, initial_tab=None):
        """Open a structured, resizable preferences window."""
        dialog = tk.Toplevel(self)
        dialog.title("PyLex Studio — Settings")
        dialog.transient(self)
        dialog.geometry("760x560")
        dialog.minsize(640, 460)
        dialog.resizable(True, True)

        shell = ttk.Frame(dialog, padding=16)
        shell.pack(fill="both", expand=True)
        ttk.Label(shell, text="Settings", style="PyLex.DialogTitle.TLabel").pack(
            anchor="w", pady=(0, 2)
        )
        ttk.Label(
            shell, text="Personalize the editor and workspace experience.",
            style="PyLex.Muted.TLabel",
        ).pack(anchor="w", pady=(0, 12))

        notebook = ttk.Notebook(shell)
        notebook.pack(fill="both", expand=True)

        appearance = ttk.Frame(notebook, padding=16)
        editor_page = ttk.Frame(notebook, padding=16)
        workspace_page = ttk.Frame(notebook, padding=16)
        execution_page = ttk.Frame(notebook, padding=16)
        help_page = ttk.Frame(notebook, padding=16)
        languages_page = ttk.Frame(notebook, padding=16)
        pages = (
            (appearance, "Appearance"), (editor_page, "Editor"),
            (workspace_page, "Workspace"), (execution_page, "Execution"),
            (languages_page, "Languages"), (help_page, "Help"),
        )
        for page, label in pages:
            notebook.add(page, text=label)
        if initial_tab == "help":
            notebook.select(help_page)

        ttk.Label(
            languages_page, text="Language roadmap",
            style="PyLex.DialogTitle.TLabel",
        ).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            languages_page,
            text="The workspace already recognizes common web file types. Full syntax highlighting, "
                 "language-aware editing and analysis will be enabled incrementally in a later release.",
            style="PyLex.Muted.TLabel", wraplength=560,
        ).pack(anchor="w", pady=(0, 14))
        for name, status, color_key, description in (
            ("Python", "Available now", "success", "Editing, highlighting, analysis, execution and debugging"),
            ("JavaScript", "Planned", "warning", "Dedicated lexer, completion and diagnostics"),
            ("HTML", "Planned", "warning", "Markup highlighting and document-aware editing"),
            ("CSS", "Planned", "warning", "Stylesheet highlighting and language-aware tooling"),
        ):
            row = ttk.Frame(languages_page, padding=(10, 8))
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=name, style="PyLex.Field.TLabel", width=16).pack(side="left")
            ttk.Label(row, text=status, foreground=self.theme_palette[color_key], width=14).pack(side="left")
            ttk.Label(row, text=description, style="PyLex.Muted.TLabel").pack(side="left", padx=(8, 0))

        theme_var = tk.StringVar(value=self.preferences["theme"])
        ttk.Label(appearance, text="Color theme", style="PyLex.Field.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )
        theme_box = ttk.Combobox(
            appearance, textvariable=theme_var, values=("dark", "light"),
            state="readonly", width=24,
        )
        theme_box.grid(row=1, column=0, sticky="w")
        ttk.Label(
            appearance,
            text="Dark uses deep navy surfaces with blue and violet accents. "
                 "Light uses soft white surfaces and professional blue accents.",
            style="PyLex.Muted.TLabel", wraplength=560,
        ).grid(row=2, column=0, sticky="w", pady=(8, 18))

        available_fonts = sorted(tkfont.families(dialog), key=str.casefold)
        ui_font_var = tk.StringVar(value=self._resolved_ui_font(available_fonts))
        ui_size_var = tk.IntVar(value=self.preferences.get("ui_font_size", 9))
        ttk.Label(appearance, text="Interface font").grid(row=3, column=0, sticky="w", pady=(0, 5))
        ui_fonts = [
            name for name in (
                "Segoe UI", "Inter", "Noto Sans", "Ubuntu",
                "DejaVu Sans", "Arial", "Tahoma",
            ) if name in available_fonts
        ]
        if not ui_fonts:
            ui_fonts = ["TkDefaultFont"]
        ui_box = ttk.Combobox(
            appearance, textvariable=ui_font_var, values=ui_fonts,
            state="readonly", width=24,
        )
        ui_box.grid(row=4, column=0, sticky="w")
        ttk.Label(appearance, text="Interface size").grid(row=3, column=1, sticky="w", padx=(24, 0), pady=(0, 5))
        ttk.Spinbox(appearance, from_=8, to=14, textvariable=ui_size_var, width=6).grid(
            row=4, column=1, sticky="w", padx=(24, 0)
        )

        code_fonts = [
            name for name in (
                "JetBrains Mono", "Cascadia Code", "Fira Code",
                "Consolas", "Cascadia Mono", "DejaVu Sans Mono",
                "Liberation Mono", "Courier New", "TkFixedFont",
            ) if name in available_fonts
        ]
        if not code_fonts:
            code_fonts = ["TkFixedFont"]
        code_font_var = tk.StringVar(
            value=self._resolved_code_font(available_fonts)
        )
        code_size_var = tk.IntVar(value=self.preferences["font_size"])
        ttk.Label(editor_page, text="Code font family").grid(row=0, column=0, sticky="w", pady=(0, 5))
        code_box = ttk.Combobox(
            editor_page, textvariable=code_font_var, values=code_fonts,
            state="readonly", width=28,
        )
        code_box.grid(row=1, column=0, sticky="w")
        ttk.Label(editor_page, text="Code font size").grid(row=0, column=1, sticky="w", padx=(24, 0), pady=(0, 5))
        ttk.Spinbox(editor_page, from_=8, to=32, textvariable=code_size_var, width=6).grid(
            row=1, column=1, sticky="w", padx=(24, 0)
        )
        ttk.Label(
            editor_page,
            text="JetBrains Mono is preferred for code when installed. "
                 "Cascadia Code and Consolas are reliable fallbacks.",
            style="PyLex.Muted.TLabel", wraplength=560,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))

        explorer_var = tk.BooleanVar(value=self.preferences["show_project_explorer"])
        ttk.Checkbutton(
            workspace_page, text="Show project explorer on startup",
            variable=explorer_var,
        ).pack(anchor="w", pady=(0, 10))
        ttk.Label(
            workspace_page,
            text="Drag the separators between Explorer, Editor and the lower tool panel "
                 "to resize each area. Use the mouse wheel over a panel to scroll.",
            style="PyLex.Muted.TLabel", wraplength=560,
        ).pack(anchor="w")

        timeout_var = tk.StringVar()
        current_timeout = self.preferences["timeout_seconds"]
        timeout_var.set("Unlimited" if current_timeout is None else f"{current_timeout} seconds")
        ttk.Label(execution_page, text="Execution timeout").grid(row=0, column=0, sticky="w", pady=(0, 5))
        ttk.Combobox(
            execution_page, textvariable=timeout_var,
            values=("5 seconds", "10 seconds", "30 seconds", "60 seconds", "Unlimited"),
            state="readonly", width=22,
        ).grid(row=1, column=0, sticky="w")
        ttk.Label(
            execution_page,
            text="Unlimited execution is useful for long-running scripts. You can always stop a run manually.",
            style="PyLex.Muted.TLabel", wraplength=560,
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))

        help_text = (
            "QUICK START\n\n"
            "1. Open a folder with File → Open Workspace.\n"
            "2. Select a file in Explorer or use File → Open.\n"
            "3. Edit your code and press Ctrl+S to save.\n"
            "4. Press F5 to run the current Python file.\n"
            "5. Press F6 to run lexical and syntax analysis.\n"
            "6. Use the bottom tabs for Output, Terminal, Quality and Git.\n\n"
            "USEFUL SHORTCUTS\n"
            "Ctrl+N  New file     Ctrl+O  Open file\n"
            "Ctrl+S  Save         Ctrl+W  Close tab\n"
            "F5      Run           Shift+F5  Stop\n"
            "Ctrl+F5 Debug         F6  Analyze all\n"
            "F9      Toggle breakpoint   F10  Step over\n"
            "F11     Step into     Ctrl+Shift+P  Command palette\n"
            "Ctrl+,  Settings     Ctrl+P  Quick open file\n"
            "Ctrl+G  Go to line\n\n"
            "TIPS\n"
            "• Drag pane separators to resize the workspace.\n"
            "• Use the mouse wheel over the editor and panels to scroll.\n"
            "• Hover toolbar actions to see their purpose.\n"
            "• The About window shows the installed application version."
        )
        help_view = tk.Text(
            help_page, wrap="word", height=18, borderwidth=0,
            padx=8, pady=8, font=(ui_font_var.get(), 10),
        )
        help_view.configure(
            bg=self.theme_palette["editor_bg"],
            fg=self.theme_palette["editor_fg"],
            insertbackground=self.theme_palette["editor_fg"],
            selectbackground=self.theme_palette["selection_bg"],
            selectforeground=self.theme_palette["editor_fg"],
        )
        help_view.pack(fill="both", expand=True)
        help_view.insert("1.0", help_text)
        help_view.configure(state="disabled")

        buttons = ttk.Frame(shell)
        buttons.pack(fill="x", pady=(12, 0))

        def reset_defaults():
            theme_var.set(DEFAULTS["theme"])
            ui_font_var.set(
                DEFAULTS["ui_font_family"]
                if DEFAULTS["ui_font_family"] in ui_fonts else ui_fonts[0]
            )
            ui_size_var.set(DEFAULTS["ui_font_size"])
            default_font = next(
                (name for name in (
                    "JetBrains Mono", "Cascadia Code", "Fira Code",
                    "Consolas", "Cascadia Mono", "DejaVu Sans Mono",
                    "Liberation Mono", "Courier New", "Lucida Console", "TkFixedFont",
                ) if name in code_fonts),
                code_fonts[0],
            )
            code_font_var.set(default_font)
            code_size_var.set(DEFAULTS["font_size"])
            explorer_var.set(DEFAULTS["show_project_explorer"])
            timeout_var.set(
                "Unlimited" if DEFAULTS["timeout_seconds"] is None
                else f"{DEFAULTS['timeout_seconds']} seconds"
            )

        def apply():
            try:
                code_size = max(8, min(32, int(code_size_var.get())))
                ui_size = max(8, min(14, int(ui_size_var.get())))
            except (ValueError, tk.TclError):
                messagebox.showerror(
                    "Settings", "Font sizes must be valid numbers.", parent=dialog
                )
                return
            selected_timeout = timeout_var.get()
            timeout_map = {
                "5 seconds": 5, "10 seconds": 10,
                "30 seconds": 30, "60 seconds": 60, "Unlimited": None,
            }
            if selected_timeout not in timeout_map:
                messagebox.showerror("Settings", "Choose a valid execution timeout.", parent=dialog)
                return
            self.preferences.update({
                "theme": theme_var.get(),
                "font_family": code_font_var.get(),
                "font_size": code_size,
                "ui_font_family": ui_font_var.get(),
                "ui_font_size": ui_size,
                "timeout_seconds": timeout_map[selected_timeout],
            })
            desired_explorer = bool(explorer_var.get())
            if desired_explorer != self.preferences["show_project_explorer"]:
                self.toggle_project_explorer()
            self.dark = self.preferences["theme"] == "dark"
            for editor in self.documents:
                editor.set_font_family(self.preferences["font_family"])
                editor.set_font_size(self.preferences["font_size"])
            self._theme()
            self._persist_preferences()
            dialog.destroy()

        ttk.Button(buttons, text="Apply", command=apply, style="PyLex.Primary.TButton").pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="Reset to Defaults", command=reset_defaults).pack(side="left")

    def show_about(self):
        """Show product identity and version outside the main title area."""
        dialog = tk.Toplevel(self)
        dialog.title("About PyLex Studio")
        dialog.transient(self)
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=26)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="PyLex Studio", style="PyLex.AboutTitle.TLabel").pack(anchor="w")
        ttk.Label(
            body, text=f"Version {__version__}",
            style="PyLex.Muted.TLabel",
        ).pack(anchor="w", pady=(2, 14))
        ttk.Label(
            body,
            text="A focused Python development environment with code editing, "
                 "analysis, execution, debugging, Git and quality tools.",
            wraplength=390, justify="left",
        ).pack(anchor="w")
        ttk.Button(body, text="Close", command=dialog.destroy).pack(anchor="e", pady=(20, 0))

    def show_help(self):
        """Open the built-in getting-started guide directly in Settings."""
        self.open_preferences(initial_tab="help")

    def open_quick_file(self):
        """Search workspace paths quickly, inspired by modern editor quick-open."""
        root = self.project_root
        if root is None or not root.is_dir():
            self.open_file()
            return

        ignored = {
            ".git", ".venv", "venv", "__pycache__", ".pytest_cache",
            ".mypy_cache", ".ruff_cache", ".tox", "node_modules", "dist", "build",
        }
        candidates = []
        for directory, subdirectories, filenames in os.walk(root):
            subdirectories[:] = sorted(
                name for name in subdirectories
                if name not in ignored and not (Path(directory) / name).is_symlink()
            )
            for filename in filenames:
                path = Path(directory) / filename
                try:
                    relative = path.relative_to(root).as_posix()
                except ValueError:
                    continue
                candidates.append((relative, path))
                if len(candidates) >= 6000:
                    break
            if len(candidates) >= 6000:
                break
        candidates.sort(key=lambda item: item[0].casefold())

        dialog = tk.Toplevel(self)
        dialog.title("Quick Open")
        dialog.transient(self)
        dialog.geometry("660x460")
        dialog.minsize(440, 300)
        query = tk.StringVar()
        entry = ttk.Entry(dialog, textvariable=query, font=(
            self._resolved_ui_font(), 11
        ))
        entry.pack(fill="x", padx=12, pady=12)
        listing = tk.Listbox(
            dialog, activestyle="none", height=16, borderwidth=0,
            bg=self.theme_palette["surface"], fg=self.theme_palette["editor_fg"],
            selectbackground=self.theme_palette["accent"],
            selectforeground="#ffffff", highlightthickness=0,
        )
        listing.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        hint = ttk.Label(
            dialog, text="Type to filter  ·  Enter to open  ·  Esc to close",
            style="PyLex.Muted.TLabel", padding=(12, 0, 12, 10),
        )
        hint.pack(anchor="w")
        matches = []

        def refresh(*_args):
            listing.delete(0, "end")
            matches.clear()
            term = query.get().strip().casefold()
            ranked = []
            for relative, path in candidates:
                folded = relative.casefold()
                basename = path.name.casefold()
                if not term:
                    rank = (0, len(relative), folded)
                elif term in basename:
                    rank = (0, basename.find(term), len(relative), folded)
                elif term in folded:
                    rank = (1, folded.find(term), len(relative), folded)
                else:
                    continue
                ranked.append((rank, relative, path))
            for _rank, relative, path in sorted(ranked)[:200]:
                matches.append(path)
                listing.insert("end", relative)
            if matches:
                listing.selection_set(0)
                listing.activate(0)

        def execute(_event=None):
            selection = listing.curselection()
            index = selection[0] if selection else (0 if matches else None)
            if index is None or index >= len(matches):
                return "break"
            path = matches[index]
            dialog.destroy()
            self._open_path(path)
            return "break"

        def focus_results(_event=None):
            if matches:
                listing.focus_set()
                listing.selection_clear(0, "end")
                listing.selection_set(0)
                listing.activate(0)
            return "break"

        query.trace_add("write", refresh)
        listing.bind("<Double-1>", execute)
        listing.bind("<Return>", execute)
        entry.bind("<Down>", focus_results)
        dialog.bind("<Return>", execute)
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        refresh()
        entry.focus_set()

    def open_command_palette(self):
        """Show searchable commands and their keyboard shortcuts."""
        commands = [
            ("New File", "Ctrl+N", self.new_file),
            ("Open File", "Ctrl+O", self.open_file),
            ("Save File", "Ctrl+S", self.save_file),
            ("Open Workspace", "", self.open_project_folder),
            ("Quick Open File", "Ctrl+P", self.open_quick_file),
            ("Run Current File", "F5", self.run_code),
            ("Stop Execution", "Shift+F5", self.stop_execution),
            ("Analyze All", "F6", self.analyze_all),
            ("Start Debugging", "Ctrl+F5", self.start_debugging),
            ("Open Terminal", "", self.open_terminal),
            ("Open Quality Tools", "", self.open_quality_tools),
            ("Open Git", "", self.open_git_tools),
            ("Toggle Theme", "", self.toggle_theme),
            ("Settings", "Ctrl+,", self.open_preferences),
            ("Quick Start & Help", "", self.show_help),
            ("About PyLex Studio", "", self.show_about),
        ]
        dialog = tk.Toplevel(self)
        dialog.title("Command Palette")
        dialog.transient(self)
        dialog.geometry("560x420")
        dialog.minsize(420, 280)
        query = tk.StringVar()
        entry = ttk.Entry(dialog, textvariable=query, font=("Segoe UI", 11))
        entry.pack(fill="x", padx=12, pady=12)
        listing = tk.Listbox(dialog, activestyle="none", height=14, borderwidth=0)
        listing.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        matches = []

        def refresh(*_args):
            listing.delete(0, "end")
            matches.clear()
            term = query.get().casefold().strip()
            for label, shortcut, action in commands:
                if term in label.casefold():
                    matches.append((label, action))
                    listing.insert("end", f"{label}    {shortcut}".rstrip())
            if matches:
                listing.selection_set(0)

        def execute(_event=None):
            selection = listing.curselection()
            if not selection:
                return "break"
            action = matches[selection[0]][1]
            dialog.destroy()
            action()
            return "break"

        query.trace_add("write", refresh)
        listing.bind("<Double-1>", execute)
        listing.bind("<Return>", execute)
        entry.bind("<Down>", lambda _event: (listing.focus_set(), listing.selection_set(0), "break"))
        entry.bind("<Return>", execute)
        refresh()
        entry.focus_set()

    def toggle_theme(self):
        self.dark = not self.dark
        self.preferences["theme"] = "dark" if self.dark else "light"
        self._theme()
        self._persist_preferences()

    def _theme(self):
        palette = self.theme_manager.apply(
            self.dark,
            ui_font_family=self._resolved_ui_font(),
            ui_font_size=self.preferences.get("ui_font_size", 9),
        )
        self.theme_palette = palette
        self._icon_cache.clear()
        self.configure(bg=palette["window_bg"])
        for editor in self.documents:
            editor.set_theme(self.dark, palette)
        for panel in (self.output, self.lexical, self.syntax):
            panel.configure(
                bg=palette["editor_bg"], fg=palette["editor_fg"],
                insertbackground=palette["editor_fg"],
                selectbackground=palette["selection_bg"],
                selectforeground=palette["editor_fg"],
            )
            panel.tag_configure("stderr", foreground=palette["danger"])
            panel.tag_configure("stdout", foreground=palette["success"])
            panel.tag_configure("system", foreground=palette["accent"])
        self.terminal_panel.set_theme(self.dark, palette)
        if hasattr(self, "error_tree"):
            self.error_tree.tag_configure("error", foreground=palette["danger"])
            self.error_tree.tag_configure("warning", foreground=palette["warning"])
            self.error_tree.tag_configure("info", foreground=palette["accent"])
        if hasattr(self, "project_tree"):
            self.project_tree.tag_configure("directory", foreground=palette["accent"])
            for kind in (
                "python", "web", "markup", "style", "data", "config",
                "shell", "compiled", "image", "audio", "video", "pdf",
                "document", "archive", "database", "font", "text",
                "binary", "unknown",
            ):
                self.project_tree.tag_configure(
                    kind, foreground=palette.get(f"file_{kind}", palette["editor_fg"])
                )
        if hasattr(self, "theme_button"):
            self.theme_button.configure(
                text="Light theme" if self.dark else "Dark theme",
                image=self._icon(
                    "sun" if self.dark else "moon-stars",
                    palette.get("warning"),
                ),
            )
        if hasattr(self, "help_button"):
            self.help_button.configure(image=self._icon("question-circle", palette.get("muted")))
        if hasattr(self, "settings_button"):
            self.settings_button.configure(image=self._icon("gear-fill", palette.get("muted")))
        for button, icon_name, color_key in getattr(self, "_toolbar_icon_bindings", []):
            button.configure(image=self._icon(icon_name, palette.get(color_key)))
        for child, icon_name, color_key in getattr(self, "_tool_tab_icon_bindings", []):
            try:
                self.tabs.tab(
                    child, image=self._icon(icon_name, palette.get(color_key)),
                    compound="left",
                )
            except tk.TclError:
                pass
        for document in getattr(self, "documents", {}).values():
            path = document["path"]
            if path:
                file_info = file_type_for(path)
                icon_name = self._file_icon_name(file_info.kind)
                icon_color = palette.get(
                    f"file_{file_info.kind}", palette.get("editor_fg")
                )
            else:
                icon_name = "file-earmark-plus"
                icon_color = palette.get("accent")
            try:
                self.editor_tabs.tab(
                    document["frame"], image=self._icon(icon_name, icon_color),
                    compound="left",
                )
            except tk.TclError:
                pass
        if hasattr(self, "project_tree") and self.project_root is not None:
            self._populate_project_tree()
        for menu in getattr(self, "_menus", []):
            try:
                menu.configure(
                    background=palette["menu_bg"],
                    foreground=palette["menu_fg"],
                    activebackground=palette["accent"],
                    activeforeground="#ffffff",
                    borderwidth=0,
                )
            except tk.TclError:
                pass

    def close(self):
        for editor, document in list(self.documents.items()):
            if not document["dirty"]:
                continue
            self.editor_tabs.select(document["frame"])
            self.editor = editor
            self._sync_active_document()
            if not self._confirm():
                return
        if self.execution is not None and not self.execution.done:
            self.execution.force_stop()
            self.execution.wait(timeout=2)
        if self.debug_session is not None:
            self.debug_session.close()
        self.terminal_panel.close_all()
        self.quality_panel.close()
        self.git_panel.close()
        self.destroy()
