"""Main graphical interface for PyLex Studio."""

from . import __version__
from .commands import Command, CommandRegistry
from .controllers import (
    DebuggerController,
    DocumentController,
    ExecutionController,
    WorkspaceController,
)
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, font as tkfont
import ttkbootstrap as ttkb
import queue
import threading
from pathlib import Path
import os
import subprocess
import shutil
import sys
import re
import time

from .editor import CodeEditor
from .analyzer import (
    lexical_analysis,
    syntax_analysis,
    format_tokens,
    collect_diagnostics,
)
from .dependencies import inspect_dependencies, python_environment
from .core.project import Project
from .core.file_types import file_type_for, read_text_file
from .services.execution import ExecutionService
from .preferences import DEFAULTS, load_preferences, save_preferences
from .interpreters import (
    create_virtual_environment,
    discover_interpreters,
    ensure_pip,
    find_project_environment,
    probe_interpreter,
)
from .terminal import TerminalPanel, python_file_command
from .quality import QualityPanel
from .git_panel import GitPanel
from .ui.theme import ThemeManager
from .ui.context_menu import ContextMenu
from .ui.command_palette import CommandPalette


class PyLexApp(tk.Tk):
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
            self.workspace_controller._project = value
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
            file_menu.add_command(label=label, command=command, accelerator=shortcut)
        self.recent_workspace_menu = tk.Menu(
            file_menu,
            tearoff=False,
            background=self.theme_palette["menu_bg"],
            foreground=self.theme_palette["menu_fg"],
            activebackground=self.theme_palette["elevated"],
            activeforeground=self.theme_palette["accent"],
            disabledforeground=self.theme_palette["muted"],
            borderwidth=1,
            relief="solid",
            font=(self._resolved_ui_font(), self.preferences.get("ui_font_size", 9)),
        )
        self._menus.append(self.recent_workspace_menu)
        file_menu.add_cascade(
            label="Open Recent Workspace", menu=self.recent_workspace_menu
        )
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.close)
        self._refresh_recent_workspace_menu()
        menu.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menu, tearoff=False)
        self._menus.append(edit_menu)
        edit_menu.add_command(label="Find / Replace...", command=self.find_replace)
        edit_menu.add_command(
            label="Toggle Line Comment",
            command=lambda: self.editor._toggle_comment(),
            accelerator="Ctrl+/",
        )
        edit_menu.add_command(
            label="Duplicate Line / Selection",
            command=lambda: self.editor._duplicate_line(),
            accelerator="Ctrl+D",
        )
        edit_menu.add_command(
            label="Go to Line...",
            command=lambda: self.editor._go_to_line(),
            accelerator="Ctrl+G",
        )
        menu.add_cascade(label="Edit", menu=edit_menu)

        navigate_menu = tk.Menu(menu, tearoff=False)
        self._menus.append(navigate_menu)
        navigate_menu.add_command(
            label="Quick Open File...",
            command=self.open_quick_file,
            accelerator="Ctrl+P",
        )
        navigate_menu.add_command(
            label="Go to Line...",
            command=lambda: self.editor._go_to_line(),
            accelerator="Ctrl+G",
        )
        navigate_menu.add_command(
            label="Command Palette...",
            command=self.open_command_palette,
            accelerator="Ctrl+Shift+P",
        )
        menu.add_cascade(label="Navigate", menu=navigate_menu)

        tools_menu = tk.Menu(menu, tearoff=False)
        self._menus.append(tools_menu)
        tools_menu.add_command(
            label="Python Interpreter...", command=self.manage_interpreter
        )
        tools_menu.add_command(label="Integrated Terminal", command=self.open_terminal)
        tools_menu.add_command(
            label="Formatter, Linter & Test Explorer", command=self.open_quality_tools
        )
        tools_menu.add_command(label="Git Source Control", command=self.open_git_tools)
        tools_menu.add_separator()
        tools_menu.add_command(label="Analyze All", command=self.analyze_all)
        tools_menu.add_command(label="Lexical Analysis", command=self.analyze_lexical)
        tools_menu.add_command(label="Syntax Analysis", command=self.analyze_syntax)
        tools_menu.add_command(label="Clear Results", command=self.clear_results)
        tools_menu.add_separator()
        tools_menu.add_command(label="Run Code", command=self.run_code)
        tools_menu.add_command(
            label="Force Stop Execution", command=self.stop_execution
        )
        tools_menu.add_separator()
        tools_menu.add_command(label="Start Debugging", command=self.start_debugging)
        tools_menu.add_command(label="Continue", command=self.debug_continue)
        tools_menu.add_command(label="Step Into", command=self.debug_step)
        tools_menu.add_command(label="Step Over", command=self.debug_next)
        tools_menu.add_command(
            label="Toggle Breakpoint", command=self.toggle_breakpoint
        )
        tools_menu.add_command(label="Inspect Variables", command=self.debug_variables)
        tools_menu.add_command(label="Show Stack", command=self.debug_stack)
        tools_menu.add_command(
            label="Show Function Arguments", command=self.debug_arguments
        )
        tools_menu.add_command(label="Run Until Line", command=self.debug_until)
        tools_menu.add_command(label="Run Until Return", command=self.debug_return)
        tools_menu.add_command(label="Jump to Line", command=self.debug_jump)
        tools_menu.add_command(
            label="Evaluate Expression...", command=self.debug_evaluate
        )
        tools_menu.add_command(
            label="Conditional Breakpoint...", command=self.debug_conditional_breakpoint
        )
        tools_menu.add_command(
            label="Temporary Breakpoint", command=self.debug_temporary_breakpoint
        )
        tools_menu.add_command(
            label="Enable Breakpoint...",
            command=lambda: self.debug_manage_breakpoint("enable"),
        )
        tools_menu.add_command(
            label="Disable Breakpoint...",
            command=lambda: self.debug_manage_breakpoint("disable"),
        )
        tools_menu.add_command(
            label="Ignore Breakpoint Hits...",
            command=lambda: self.debug_manage_breakpoint("ignore"),
        )
        tools_menu.add_command(
            label="Clear All Breakpoints", command=self.debug_clear_breakpoints
        )
        tools_menu.add_command(label="Stop Debugging", command=self.stop_debugging)
        menu.add_cascade(label="Tools", menu=tools_menu)

        view_menu = tk.Menu(menu, tearoff=False)
        self._menus.append(view_menu)
        view_menu.add_command(label="Preferences...", command=self.open_preferences)
        view_menu.add_command(
            label="Toggle Project Explorer", command=self.toggle_project_explorer
        )
        menu.add_cascade(label="View", menu=view_menu)

        help_menu = tk.Menu(menu, tearoff=False)
        self._menus.append(help_menu)
        help_menu.add_command(label="Quick Start & Help...", command=self.show_help)
        help_menu.add_command(
            label="Command Palette...",
            command=self.open_command_palette,
            accelerator="Ctrl+Shift+P",
        )
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

    def _icon(self, name, color=None, size=18):
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
        """Build a two-tier command surface: categorized menus above the brand/action row."""
        menu_row = ttk.Frame(self, style="PyLex.Toolbar.TFrame", padding=(10, 2))
        menu_row.pack(fill="x", side="top")

        brand = ttk.Frame(menu_row, style="PyLex.Toolbar.TFrame")
        brand.pack(side="left", padx=(0, 12))
        self._build_logo(brand, 28)
        ttk.Label(brand, text="PyLex Studio", style="PyLex.Brand.TLabel").pack(
            side="left", padx=(7, 0)
        )

        def add_menu(title, icon_name, color_key, commands):
            button = ttk.Button(
                menu_row,
                text=title,
                style="PyLex.Menu.TButton",
                image=self._icon(icon_name, self.theme_palette.get(color_key)),
                compound="left",
            )
            button.pack(side="left", padx=(0, 2), ipady=0)
            button.configure(takefocus=False)
            self._toolbar_icon_bindings.append((button, icon_name, color_key))

            state = {
                "windows": [],
                "open_id": None,
                "poll_id": None,
                "submenu_id": None,
                "closed": True,
                "outside_polls": 0,
            }

            def cancel_timer(key):
                timer_id = state.get(key)
                if timer_id is not None:
                    try:
                        self.after_cancel(timer_id)
                    except tk.TclError:
                        pass
                    state[key] = None

            def destroy_popups():
                cancel_timer("poll_id")
                cancel_timer("open_id")
                cancel_timer("submenu_id")
                for popup in reversed(state["windows"]):
                    try:
                        if popup.winfo_exists():
                            popup.destroy()
                    except tk.TclError:
                        pass
                state["windows"].clear()
                state["closed"] = True
                if getattr(self, "_toolbar_menu_close", None) is destroy_popups:
                    self._toolbar_menu_close = None

            def pointer_inside(widget, x, y, margin=5):
                try:
                    if not widget.winfo_exists():
                        return False
                    left, top = widget.winfo_rootx(), widget.winfo_rooty()
                    right = left + widget.winfo_width()
                    bottom = top + widget.winfo_height()
                    return (
                        left - margin <= x <= right + margin
                        and top - margin <= y <= bottom + margin
                    )
                except tk.TclError:
                    return False

            def poll_pointer():
                state["poll_id"] = None
                if state["closed"] or not state["windows"]:
                    return
                try:
                    x, y = self.winfo_pointerxy()
                except tk.TclError:
                    destroy_popups()
                    return
                # Treat the toolbar button, every open popup and the tiny
                # transition corridor between them as one continuous menu area.
                inside = pointer_inside(button, x, y) or any(
                    pointer_inside(popup, x, y) for popup in state["windows"]
                )
                if not inside and state["windows"]:
                    try:
                        first = state["windows"][0]
                        bx1, by1 = button.winfo_rootx(), button.winfo_rooty()
                        bx2, by2 = (
                            bx1 + button.winfo_width(),
                            by1 + button.winfo_height(),
                        )
                        px1, py1 = first.winfo_rootx(), first.winfo_rooty()
                        px2, py2 = px1 + first.winfo_width(), py1 + first.winfo_height()
                        inside = (
                            min(bx1, px1) - 7 <= x <= max(bx2, px2) + 7
                            and min(by1, py1) - 7 <= y <= max(by2, py2) + 7
                        )
                    except tk.TclError:
                        inside = False
                if inside:
                    state["outside_polls"] = 0
                else:
                    state["outside_polls"] += 1
                    # Ignore transient geometry/focus reports while the pointer
                    # is moving between the toolbar anchor and its popup.
                    if state["outside_polls"] >= 2:
                        destroy_popups()
                        return
                state["poll_id"] = self.after(70, poll_pointer)

            def schedule_poll():
                cancel_timer("poll_id")
                state["poll_id"] = self.after(70, poll_pointer)

            def close_descendant_popups(parent_popup):
                """Close only popups branching from this menu, preserving ancestors."""
                try:
                    parent_index = state["windows"].index(parent_popup)
                except ValueError:
                    return
                descendants = state["windows"][parent_index + 1 :]
                del state["windows"][parent_index + 1 :]
                for child_popup in reversed(descendants):
                    try:
                        if child_popup.winfo_exists():
                            child_popup.destroy()
                    except tk.TclError:
                        pass
                cancel_timer("submenu_id")

            def make_popup(anchor, items, parent_popup=None):
                popup = tk.Toplevel(self)
                popup.withdraw()
                popup.overrideredirect(True)
                popup.transient(self)
                popup.configure(
                    background=self.theme_palette["border"],
                    highlightthickness=1,
                    highlightbackground=self.theme_palette["border"],
                )
                body = tk.Frame(
                    popup,
                    background=self.theme_palette["menu_bg"],
                    padx=3,
                    pady=3,
                )
                body.pack(fill="both", expand=True)
                state["windows"].append(popup)
                hover_jobs = []

                def cancel_popup_hover_jobs(event=None, owner=popup, jobs=hover_jobs):
                    # Destroy events also fire for child widgets; only the popup
                    # that owns these callbacks should cancel this callback set.
                    if event is not None and event.widget is not owner:
                        return
                    for hover_data in jobs:
                        job_id = hover_data.get("job")
                        if job_id is not None:
                            try:
                                self.after_cancel(job_id)
                            except tk.TclError:
                                pass
                            hover_data["job"] = None

                popup.bind("<Destroy>", cancel_popup_hover_jobs, add="+")

                def show_submenu(item_button, submenu_items):
                    cancel_timer("submenu_id")
                    # A menu can have several nested levels. Destroy every
                    # descendant of this popup before opening its new child;
                    # merely popping references leaves orphaned Toplevels visible.
                    close_descendant_popups(popup)
                    submenu = make_popup(item_button, submenu_items, popup)
                    submenu.update_idletasks()
                    x = popup.winfo_rootx() + popup.winfo_width() - 2
                    y = item_button.winfo_rooty()
                    screen_w = self.winfo_screenwidth()
                    if x + submenu.winfo_reqwidth() > screen_w:
                        x = popup.winfo_rootx() - submenu.winfo_reqwidth() + 2
                    submenu.geometry(f"+{max(0, x)}+{max(0, y)}")
                    submenu.deiconify()
                    submenu.lift()
                    schedule_poll()

                for item in items:
                    if item is None:
                        tk.Frame(
                            body,
                            height=1,
                            background=self.theme_palette["border"],
                        ).pack(fill="x", padx=7, pady=4)
                        continue
                    if item[0] == "submenu":
                        label, submenu_items = item[1], item[2]
                        # Resolve dynamic submenu contents when the parent is
                        # opened so recent-workspace entries never go stale.
                        if callable(submenu_items):
                            submenu_items = submenu_items()
                        command = None
                        shortcut = ""
                        display = f"{label}    ›"
                    else:
                        label, command, *shortcuts = item
                        shortcut = shortcuts[0] if shortcuts else ""
                        display = label
                        submenu_items = None

                    row = tk.Frame(body, background=self.theme_palette["menu_bg"])
                    row.pack(fill="x")
                    item_action = (
                        (lambda callback=command: (destroy_popups(), callback()))
                        if command is not None
                        else None
                    )
                    item_button = tk.Button(
                        row,
                        text=display,
                        anchor="w",
                        command=item_action,
                        relief="flat",
                        borderwidth=0,
                        highlightthickness=0,
                        takefocus=False,
                        padx=11,
                        pady=6,
                        background=self.theme_palette["menu_bg"],
                        foreground=self.theme_palette["menu_fg"],
                        activebackground=self.theme_palette["elevated"],
                        activeforeground=self.theme_palette["accent"],
                        font=(
                            self._resolved_ui_font(),
                            self.preferences.get("ui_font_size", 9),
                        ),
                        cursor="hand2",
                    )
                    item_button.pack(side="left", fill="x", expand=True)
                    shortcut_label = None
                    if shortcut:
                        shortcut_label = tk.Label(
                            row,
                            text=shortcut,
                            background=self.theme_palette["menu_bg"],
                            foreground=self.theme_palette["muted"],
                            font=(
                                self._resolved_ui_font(),
                                max(7, self.preferences.get("ui_font_size", 9) - 1),
                            ),
                            padx=8,
                        )
                        shortcut_label.pack(side="right")

                    # Hover feedback belongs to every command row inside the popup,
                    # not merely to the File/Edit category button in the toolbar.
                    hover_state = {"job": None}
                    hover_jobs.append(hover_state)

                    def highlight_menu_row(
                        _event=None,
                        target=row,
                        button_widget=item_button,
                        shortcut_widget=shortcut_label,
                        hover_data=hover_state,
                    ):
                        if hover_data["job"] is not None:
                            try:
                                self.after_cancel(hover_data["job"])
                            except tk.TclError:
                                pass
                            hover_data["job"] = None
                        active_bg = self.theme_palette["elevated"]
                        target.configure(background=active_bg)
                        button_widget.configure(
                            background=active_bg,
                            foreground=self.theme_palette["accent"],
                        )
                        if shortcut_widget is not None:
                            shortcut_widget.configure(
                                background=active_bg,
                                foreground=self.theme_palette["menu_fg"],
                            )

                    def clear_menu_row_hover(
                        _event=None,
                        target=row,
                        button_widget=item_button,
                        shortcut_widget=shortcut_label,
                        hover_data=hover_state,
                        owner_popup=popup,
                    ):
                        def settle():
                            hover_data["job"] = None
                            try:
                                # A delayed Leave callback may outlive its popup.
                                # Check both widgets before querying geometry or styling.
                                if (
                                    not owner_popup.winfo_exists()
                                    or not target.winfo_exists()
                                ):
                                    return
                                px, py = self.winfo_pointerxy()
                                inside = (
                                    target.winfo_rootx()
                                    <= px
                                    < target.winfo_rootx() + target.winfo_width()
                                    and target.winfo_rooty()
                                    <= py
                                    < target.winfo_rooty() + target.winfo_height()
                                )
                                if inside:
                                    return
                                normal_bg = self.theme_palette["menu_bg"]
                                target.configure(background=normal_bg)
                                button_widget.configure(
                                    background=normal_bg,
                                    foreground=self.theme_palette["menu_fg"],
                                )
                                if (
                                    shortcut_widget is not None
                                    and shortcut_widget.winfo_exists()
                                ):
                                    shortcut_widget.configure(
                                        background=normal_bg,
                                        foreground=self.theme_palette["muted"],
                                    )
                            except tk.TclError:
                                # The popup or one of its row widgets was destroyed
                                # while this idle callback was waiting to run.
                                return

                        try:
                            hover_data["job"] = self.after(45, settle)
                        except tk.TclError:
                            hover_data["job"] = None

                    for hover_widget in (row, item_button, shortcut_label):
                        if hover_widget is not None:
                            hover_widget.bind("<Enter>", highlight_menu_row, add="+")
                            hover_widget.bind("<Leave>", clear_menu_row_hover, add="+")

                    if submenu_items is not None:
                        item_button.bind(
                            "<Enter>",
                            lambda event, b=item_button, entries=submenu_items: (
                                cancel_timer("submenu_id"),
                                state.update(
                                    submenu_id=self.after(
                                        110, lambda: show_submenu(b, entries)
                                    )
                                ),
                            ),
                            add="+",
                        )
                    else:

                        def enter_command_row(_event=None, owner_popup=popup):
                            cancel_timer("submenu_id")
                            # A sibling command replaces the currently displayed
                            # cascade: keep this menu and its ancestors, but close
                            # every submenu opened from it.
                            close_descendant_popups(owner_popup)

                        item_button.bind(
                            "<Enter>",
                            enter_command_row,
                            add="+",
                        )
                popup.update_idletasks()
                req_w = max(210, popup.winfo_reqwidth())
                req_h = popup.winfo_reqheight()
                popup.geometry(f"{req_w}x{req_h}")
                return popup

            def post_menu():
                cancel_timer("open_id")
                if not button.winfo_exists():
                    return
                active_close = getattr(self, "_toolbar_menu_close", None)
                if active_close and active_close is not destroy_popups:
                    active_close()
                destroy_popups()
                state["closed"] = False
                state["outside_polls"] = 0
                self._toolbar_menu_close = destroy_popups
                popup = make_popup(button, commands)
                popup.update_idletasks()
                x = button.winfo_rootx()
                y = button.winfo_rooty() + button.winfo_height()
                if x + popup.winfo_reqwidth() > self.winfo_screenwidth():
                    x = self.winfo_screenwidth() - popup.winfo_reqwidth() - 4
                if y + popup.winfo_reqheight() > self.winfo_screenheight():
                    y = button.winfo_rooty() - popup.winfo_reqheight()
                popup.geometry(f"+{max(0, x)}+{max(0, y)}")
                popup.deiconify()
                popup.lift()
                schedule_poll()

            def open_on_hover(_event=None):
                button.state(["active"])
                cancel_timer("open_id")
                if state["closed"]:
                    state["open_id"] = self.after(150, post_menu)

            def click_menu(_event=None):
                if state["closed"]:
                    post_menu()
                else:
                    destroy_popups()
                return "break"

            button.bind("<Enter>", open_on_hover, add="+")
            button.bind(
                "<Leave>",
                lambda _event: (cancel_timer("open_id"), button.state(["!active"])),
                add="+",
            )
            button.bind("<Button-1>", click_menu, add="+")
            button.bind("<Button-3>", click_menu, add="+")
            return button

        add_menu(
            "File",
            "folder2-open",
            "accent",
            [
                ("New File    Ctrl+N", self.new_file),
                ("Open File    Ctrl+O", self.open_file),
                ("Open Workspace...", self.open_project_folder),
                (
                    "submenu",
                    "Open Recent Workspace…",
                    self._recent_workspace_toolbar_items,
                ),
                ("Quick Open    Ctrl+P", self.open_quick_file),
                None,
                ("Save    Ctrl+S", self.save_file),
                ("Save As...", self.save_as),
                ("Close Tab    Ctrl+W", self.close_tab),
                ("Close Workspace", self.close_workspace),
            ],
        )
        add_menu(
            "Edit",
            "pencil-square",
            "muted",
            [
                ("Find / Replace    Ctrl+H", self.find_replace),
                (
                    "Toggle Line Comment    Ctrl+/",
                    lambda: self.editor._toggle_comment(),
                ),
                ("Duplicate Line    Ctrl+D", lambda: self.editor._duplicate_line()),
                ("Go to Line    Ctrl+G", lambda: self.editor._go_to_line()),
            ],
        )
        add_menu(
            "Navigate",
            "search",
            "accent",
            [
                ("Quick Open File    Ctrl+P", self.open_quick_file),
                ("Command Palette    Ctrl+Shift+P", self.open_command_palette),
                ("Go to Line    Ctrl+G", lambda: self.editor._go_to_line()),
            ],
        )
        add_menu(
            "Run",
            "play-fill",
            "success",
            [
                ("Run Current File    F5", self.run_code),
                ("Stop Execution    Shift+F5", self.stop_execution),
            ],
        )
        add_menu(
            "Debug",
            "bug-fill",
            "violet",
            [
                (
                    "submenu",
                    "Session",
                    [
                        ("Start Debugging    Ctrl+F5", self.start_debugging),
                        ("Continue    Ctrl+F10", self.debug_continue),
                        ("Stop Debugging", self.stop_debugging),
                    ],
                ),
                (
                    "submenu",
                    "Stepping",
                    [
                        ("Step Over    F10", self.debug_next),
                        ("Step Into    F11", self.debug_step),
                        ("Run Until Line...", self.debug_until),
                        ("Run Until Return", self.debug_return),
                        ("Jump to Line...", self.debug_jump),
                    ],
                ),
                (
                    "submenu",
                    "Breakpoints",
                    [
                        ("Toggle Breakpoint    F9", self.toggle_breakpoint),
                        ("Temporary Breakpoint", self.debug_temporary_breakpoint),
                        (
                            "Conditional Breakpoint...",
                            self.debug_conditional_breakpoint,
                        ),
                        (
                            "Enable Breakpoint...",
                            lambda: self.debug_manage_breakpoint("enable"),
                        ),
                        (
                            "Disable Breakpoint...",
                            lambda: self.debug_manage_breakpoint("disable"),
                        ),
                        (
                            "Ignore Breakpoint Hits...",
                            lambda: self.debug_manage_breakpoint("ignore"),
                        ),
                        ("Clear All Breakpoints", self.debug_clear_breakpoints),
                    ],
                ),
                (
                    "submenu",
                    "Inspect",
                    [
                        ("Inspect Variables", self.debug_variables),
                        ("Show Call Stack", self.debug_stack),
                        ("Function Arguments", self.debug_arguments),
                        ("Evaluate Expression...", self.debug_evaluate),
                    ],
                ),
            ],
        )
        add_menu(
            "Code",
            "braces",
            "accent",
            [
                ("Analyze All    F6", self.analyze_all),
                ("Lexical Analysis", self.analyze_lexical),
                ("Syntax Analysis", self.analyze_syntax),
                None,
                ("Formatter, Linter & Tests", self.open_quality_tools),
                ("Dependencies", self.scan_dependencies),
                ("Clear Results", self.clear_results),
            ],
        )
        add_menu(
            "Tools",
            "sliders",
            "muted",
            [
                ("Integrated Terminal", self.open_terminal),
                ("Git Source Control", self.open_git_tools),
                ("Python Interpreter...", self.manage_interpreter),
            ],
        )
        add_menu(
            "View",
            "columns-gap",
            "muted",
            [
                ("Toggle Project Explorer", self.toggle_project_explorer),
                ("Preferences...", self.open_preferences),
                ("Switch Theme", self.toggle_theme),
            ],
        )
        add_menu(
            "Help",
            "question-circle",
            "muted",
            [
                ("Quick Start & Help...", self.show_help),
                ("Command Palette...", self.open_command_palette),
                ("About PyLex Studio...", self.show_about),
            ],
        )

        # The custom categorized menu row replaces the duplicate native menu bar.
        self.config(menu="")

        action_row = ttk.Frame(self, style="PyLex.Toolbar.TFrame", padding=(10, 3))
        action_row.pack(fill="x", side="top")

        # Keep the command row focused: frequent workspace tools only.
        action_groups = (
            (
                ("Workspace", "folder2-open", self.open_project_folder, "accent"),
                ("Python", "filetype-py", self.manage_interpreter, "muted"),
                ("Save", "floppy", self.save_file, "muted"),
            ),
            (
                ("Terminal", "terminal", self.open_terminal, "muted"),
                ("Quality", "check2-square", self.open_quality_tools, "muted"),
                ("Git", "git", self.open_git_tools, "muted"),
            ),
            (
                ("Analyze", "braces", self.analyze_all, "muted"),
                ("Debug", "bug-fill", self.start_debugging, "muted"),
            ),
        )
        for group_index, group in enumerate(action_groups):
            if group_index:
                ttk.Separator(action_row, orient="vertical").pack(
                    side="left", fill="y", padx=7, pady=5
                )
            for label, icon_name, command, color_key in group:
                button = ttk.Button(
                    action_row,
                    text=label,
                    command=command,
                    style="PyLex.Toolbar.TButton",
                    image=self._icon(icon_name, self.theme_palette.get(color_key)),
                    compound="left",
                )
                button.pack(side="left", padx=1, ipady=2)
                button.configure(takefocus=False)
                button.bind(
                    "<Enter>",
                    lambda _event, target=button: target.state(["active"]),
                    add="+",
                )
                button.bind(
                    "<Leave>",
                    lambda _event, target=button: target.state(["!active"]),
                    add="+",
                )
                self._toolbar_icon_bindings.append((button, icon_name, color_key))

        spacer = ttk.Frame(action_row, style="PyLex.Toolbar.TFrame")
        spacer.pack(side="left", fill="x", expand=True)
        # Keep the command launcher and execution controls together in a
        # compact right-hand stack. The launcher is an outlined, transparent
        # surface rather than a filled toolbar button.
        self.theme_button = ttk.Button(
            action_row,
            text="Theme",
            command=self.toggle_theme,
            style="PyLex.Toolbar.TButton",
            image=self._icon(
                "sun" if self.dark else "moon-stars",
                self.theme_palette.get("warning"),
            ),
            compound="left",
        )
        self.theme_button.pack(side="right", padx=(4, 0))
        self.theme_button.configure(takefocus=False)
        self._toolbar_icon_bindings.append(
            (self.theme_button, "sun" if self.dark else "moon-stars", "warning")
        )

        self.execution_controls = ttk.Frame(action_row, style="PyLex.Toolbar.TFrame")
        self.execution_controls.pack(side="right", padx=(8, 0))

        self.command_palette_frame = tk.Frame(
            self.execution_controls,
            background=self.theme_palette["surface"],
            highlightthickness=1,
            highlightbackground=self.theme_palette["border"],
            highlightcolor=self.theme_palette["accent"],
            cursor="hand2",
            width=250,
            height=31,
        )
        self.command_palette_frame.pack(fill="x", pady=(0, 4))
        self.command_palette_frame.pack_propagate(False)
        self.command_palette_label = tk.Label(
            self.command_palette_frame,
            text="⌕   Command Palette",
            anchor="w",
            padx=10,
            background=self.theme_palette["surface"],
            foreground=self.theme_palette["muted"],
            font=(self._resolved_ui_font(), self.preferences.get("ui_font_size", 9)),
            cursor="hand2",
        )
        self.command_palette_label.pack(fill="both", expand=True)
        for widget in (self.command_palette_frame, self.command_palette_label):
            widget.bind("<Button-1>", lambda _event: self.open_command_palette())
            widget.bind(
                "<Enter>",
                lambda _event: self.command_palette_frame.configure(
                    highlightbackground=self.theme_palette["accent"]
                ),
            )
            widget.bind(
                "<Leave>",
                lambda _event: self.command_palette_frame.configure(
                    highlightbackground=self.theme_palette["border"]
                ),
            )

        self.execution_button_row = ttk.Frame(
            self.execution_controls, style="PyLex.Toolbar.TFrame"
        )
        self.execution_button_row.pack(fill="x")
        self.run_button = ttk.Button(
            self.execution_button_row,
            text="Run  F5",
            command=self.run_code,
            style="PyLex.Run.TButton",
            image=self._icon("play-fill", self.theme_palette.get("accent")),
            compound="left",
            width=11,
        )
        self.run_button.pack(side="left", padx=(0, 5), ipady=2)
        self.run_button.configure(takefocus=False)
        self.stop_button = ttk.Button(
            self.execution_button_row,
            text="Stop  Shift+F5",
            command=self.stop_execution,
            style="PyLex.Stop.TButton",
            image=self._icon("stop-fill", self.theme_palette.get("danger")),
            compound="left",
            width=13,
        )
        self.stop_button.pack(side="left", ipady=2)
        self.stop_button.configure(takefocus=False)
        self._toolbar_icon_bindings.extend(
            [
                (self.run_button, "play-fill", "accent"),
                (self.stop_button, "stop-fill", "danger"),
            ]
        )

    def _build_logo(self, parent, size=40):
        """Draw the original PyLex emblem with native vector canvas primitives."""
        canvas = tk.Canvas(
            parent,
            width=size,
            height=size,
            bg=self.theme_palette["surface"],
            highlightthickness=0,
            bd=0,
        )
        canvas.pack(side="left")
        pad = size * 0.08
        canvas.create_polygon(
            size / 2,
            pad,
            size - pad,
            size / 2,
            size / 2,
            size - pad,
            pad,
            size / 2,
            fill="#101a35",
            outline="#2868ff",
            width=max(1, size / 32),
        )
        canvas.create_line(
            size * 0.28,
            size * 0.38,
            size * 0.16,
            size * 0.5,
            size * 0.28,
            size * 0.62,
            fill="#28c5ff",
            width=size * 0.105,
            capstyle="round",
            joinstyle="round",
        )
        canvas.create_line(
            size * 0.72,
            size * 0.38,
            size * 0.84,
            size * 0.5,
            size * 0.72,
            size * 0.62,
            fill="#a66bff",
            width=size * 0.105,
            capstyle="round",
            joinstyle="round",
        )
        canvas.create_arc(
            size * 0.32,
            size * 0.19,
            size * 0.68,
            size * 0.57,
            start=205,
            extent=270,
            style="arc",
            outline="#37aaff",
            width=size * 0.10,
        )
        canvas.create_arc(
            size * 0.32,
            size * 0.43,
            size * 0.68,
            size * 0.81,
            start=25,
            extent=270,
            style="arc",
            outline="#a66bff",
            width=size * 0.10,
        )
        return canvas

    def show_account(self):
        """Open the account center with local profile, workspace and feedback tools."""
        dialog = tk.Toplevel(self)
        dialog.title("PyLex Studio — Account Center")
        dialog.transient(self)
        dialog.geometry("940x720")
        dialog.minsize(800, 620)
        dialog.resizable(True, True)

        shell = ttk.Frame(dialog, padding=24)
        shell.pack(fill="both", expand=True)
        header = ttk.Frame(shell)
        header.pack(fill="x", pady=(0, 18))
        self._build_logo(header, 58)
        heading = ttk.Frame(header)
        heading.pack(side="left", padx=(14, 0), fill="x", expand=True)
        ttk.Label(
            heading, text="Account Center", style="PyLex.DialogTitle.TLabel"
        ).pack(anchor="w")
        ttk.Label(
            heading,
            text="Manage your local profile, workspace information and product feedback.",
            style="PyLex.Muted.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        notebook = ttk.Notebook(shell)
        notebook.pack(fill="both", expand=True)
        profile_page = ttk.Frame(notebook, padding=20)
        services_page = ttk.Frame(notebook, padding=20)
        workspace_page = ttk.Frame(notebook, padding=20)
        feedback_page = ttk.Frame(notebook, padding=20)
        notebook.add(profile_page, text="Profile")
        notebook.add(services_page, text="Connected Services")
        notebook.add(workspace_page, text="Workspace")
        notebook.add(feedback_page, text="Feedback")

        profile_name = tk.StringVar(
            value=self.preferences.get("account_display_name", "Developer")
        )
        ttk.Label(profile_page, text="Local profile", style="PyLex.Field.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            profile_page,
            text="Your display name is saved on this computer and is not uploaded to a server.",
            style="PyLex.Muted.TLabel",
            wraplength=700,
        ).pack(anchor="w", pady=(5, 18))
        ttk.Label(profile_page, text="Display name").pack(anchor="w")
        profile_entry = ttk.Entry(profile_page, textvariable=profile_name, width=48)
        profile_entry.pack(anchor="w", fill="x", pady=(5, 14))

        def save_profile():
            self.preferences["account_display_name"] = (
                profile_name.get().strip()[:48] or "Developer"
            )
            self._persist_preferences()
            self.status.configure(text="Local profile updated.")
            dialog.destroy()

        ttk.Button(
            profile_page,
            text="Save Profile",
            command=save_profile,
            style="PyLex.Primary.TButton",
        ).pack(anchor="w")
        ttk.Label(profile_page, text="Privacy", style="PyLex.Field.TLabel").pack(
            anchor="w", pady=(28, 6)
        )
        ttk.Label(
            profile_page,
            text="PyLex Studio currently keeps this profile in your local preferences file. "
            "No account registration, telemetry upload or cloud synchronization is performed by this screen.",
            style="PyLex.Muted.TLabel",
            wraplength=700,
            justify="left",
        ).pack(anchor="w")

        ttk.Label(
            services_page,
            text="Service availability",
            style="PyLex.DialogTitle.TLabel",
        ).pack(anchor="w", pady=(0, 12))
        service_items = (
            (
                "Local profile",
                "Available",
                "success",
                "Edit the display name stored in your local preferences.",
            ),
            (
                "Git source control",
                "Available",
                "success",
                "Use local Git repositories without linking an online account.",
            ),
            (
                "GitHub sign-in",
                "Planned",
                "muted",
                "A future opt-in integration for repository and pull-request workflows.",
            ),
            (
                "Cloud synchronization",
                "Planned",
                "warning",
                "A future opt-in service for synchronizing settings across devices.",
            ),
            (
                "Extensions marketplace",
                "Roadmap",
                "muted",
                "A future trusted extension catalog with permission and compatibility checks.",
            ),
        )
        for name, status, color_key, description in service_items:
            card = ttk.Frame(services_page, padding=12)
            card.pack(fill="x", pady=5)
            top = ttk.Frame(card)
            top.pack(fill="x")
            ttk.Label(top, text=name, style="PyLex.Field.TLabel").pack(side="left")
            ttk.Label(top, text=status, foreground=self.theme_palette[color_key]).pack(
                side="right"
            )
            ttk.Label(
                card,
                text=description,
                style="PyLex.Muted.TLabel",
                wraplength=700,
                justify="left",
            ).pack(anchor="w", pady=(5, 0))

        root = (
            str(self.project_root)
            if self.project_root
            else "No workspace is currently open."
        )
        document_count = len(self.documents)
        ttk.Label(
            workspace_page,
            text="Current workspace",
            style="PyLex.DialogTitle.TLabel",
        ).pack(anchor="w", pady=(0, 12))
        ttk.Label(workspace_page, text=root, wraplength=700).pack(
            anchor="w", pady=(0, 16)
        )
        metrics = ttk.Frame(workspace_page)
        metrics.pack(fill="x")
        for label, value in (
            ("Open documents", str(document_count)),
            ("Workspace", "Open" if self.project_root else "Not open"),
            ("Profile", "Local"),
        ):
            tile = ttk.Frame(metrics, padding=14)
            tile.pack(side="left", fill="both", expand=True, padx=(0, 8))
            ttk.Label(tile, text=value, style="PyLex.DialogTitle.TLabel").pack(
                anchor="w"
            )
            ttk.Label(tile, text=label, style="PyLex.Muted.TLabel").pack(
                anchor="w", pady=(4, 0)
            )

        ttk.Label(
            feedback_page,
            text="Share feedback",
            style="PyLex.DialogTitle.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            feedback_page,
            text="Report a bug, suggest an improvement or tell us what is working well.",
            style="PyLex.Muted.TLabel",
            wraplength=700,
        ).pack(anchor="w", pady=(5, 16))

        feedback_type = tk.StringVar(value="Suggestion")
        ttk.Label(feedback_page, text="Feedback type", style="PyLex.Field.TLabel").pack(
            anchor="w"
        )
        type_picker = ttk.Combobox(
            feedback_page,
            textvariable=feedback_type,
            state="readonly",
            values=("Suggestion", "Bug report", "Usability", "Performance", "Other"),
        )
        type_picker.pack(anchor="w", fill="x", pady=(5, 14))

        ttk.Label(feedback_page, text="Your message", style="PyLex.Field.TLabel").pack(
            anchor="w"
        )
        feedback_message = tk.Text(
            feedback_page,
            height=9,
            wrap="word",
            undo=True,
            font=("Segoe UI", 10),
            relief="solid",
            bd=1,
            padx=10,
            pady=8,
        )
        feedback_message.pack(fill="both", expand=True, pady=(5, 12))

        ttk.Label(
            feedback_page,
            text="Privacy: feedback is not sent automatically. You can copy it or save it as a local text file.",
            style="PyLex.Muted.TLabel",
            wraplength=700,
        ).pack(anchor="w", pady=(0, 12))

        def build_feedback():
            message = feedback_message.get("1.0", "end-1c").strip()
            if not message:
                messagebox.showinfo(
                    "Feedback",
                    "Please enter a message before continuing.",
                    parent=dialog,
                )
                return None
            return (
                "PyLex Studio Feedback\\n"
                "======================\\n"
                f"Type: {feedback_type.get()}\\n"
                f"Application version: {__version__}\\n"
                f"Platform: {sys.platform}\\n"
                f"Workspace: {root}\\n\\n"
                f"{message}\\n"
            )

        def copy_feedback():
            content = build_feedback()
            if content is None:
                return
            dialog.clipboard_clear()
            dialog.clipboard_append(content)
            self.status.configure(text="Feedback copied to clipboard.")
            messagebox.showinfo(
                "Feedback",
                "Feedback copied. You can paste it wherever you want to share it.",
                parent=dialog,
            )

        def save_feedback():
            content = build_feedback()
            if content is None:
                return
            destination = filedialog.asksaveasfilename(
                parent=dialog,
                title="Save Feedback",
                defaultextension=".txt",
                filetypes=(("Text files", "*.txt"), ("All files", "*.*")),
                initialfile="pylex-feedback.txt",
            )
            if not destination:
                return
            try:
                Path(destination).write_text(content, encoding="utf-8")
            except OSError as exc:
                messagebox.showerror("Save Feedback", str(exc), parent=dialog)
                return
            self.status.configure(text="Feedback saved locally.")
            messagebox.showinfo(
                "Feedback",
                "Your feedback was saved as a local text file.",
                parent=dialog,
            )

        feedback_actions = ttk.Frame(feedback_page)
        feedback_actions.pack(fill="x")
        ttk.Button(
            feedback_actions,
            text="Copy Feedback",
            command=copy_feedback,
        ).pack(side="left")
        ttk.Button(
            feedback_actions,
            text="Save Feedback…",
            command=save_feedback,
            style="PyLex.Primary.TButton",
        ).pack(side="left", padx=(8, 0))

        footer = ttk.Frame(shell)
        footer.pack(fill="x", pady=(14, 0))
        ttk.Label(
            footer,
            text="Online services remain disabled until explicitly implemented and configured.",
            style="PyLex.Muted.TLabel",
        ).pack(side="left", fill="x", expand=True)
        ttk.Button(footer, text="Close", command=dialog.destroy).pack(side="right")
        profile_entry.focus_set()

    def _show_activity_context_menu(self, view, event):
        menu = self._new_context_menu()
        if view == "explorer":
            menu.add_command(
                label="Open Explorer", command=lambda: self._activity_action("explorer")
            )
            menu.add_command(label="Open Workspace…", command=self.open_project_folder)
            menu.add_command(label="Refresh Workspace", command=self.refresh_workspace)
        elif view == "search":
            menu.add_command(label="Quick Open File…", command=self.open_quick_file)
            menu.add_command(
                label="Command Palette…", command=self.open_command_palette
            )
        elif view == "source":
            menu.add_command(label="Open Git Tools", command=self.open_git_tools)
            menu.add_command(
                label="Open Git Repository…", command=self.open_project_folder
            )
        elif view == "debug":
            menu.add_command(label="Start Debugging", command=self.start_debugging)
            menu.add_command(label="Continue", command=self.debug_continue)
            menu.add_command(label="Stop Debugging", command=self.stop_debugging)
        elif view == "extensions":
            menu.add_command(
                label="Open Quality Tools", command=self.open_quality_tools
            )
            menu.add_command(label="Scan Dependencies", command=self.scan_dependencies)
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _activity_action(self, view):
        """Route Activity Bar actions to existing workspace tools."""
        # Keep activity feedback transient: do not persist a selected state.
        for button, _icon_name, _color_key in self.activity_buttons.values():
            button.state(["!selected"])
        if view == "explorer":
            if not self.preferences["show_project_explorer"]:
                self.toggle_project_explorer()
            self.project_tree.focus_set()
            self.status.configure(
                text="Explorer ready — open a folder to browse its files."
            )
        elif view == "search":
            self.open_quick_file()
        elif view == "source":
            self.open_git_tools()
        elif view == "debug":
            self.start_debugging()
        elif view == "extensions":
            self.open_quality_tools()

    def create_project_folder(self):
        """Create a named folder at the workspace root."""
        if self.project_root is None:
            messagebox.showinfo("New Folder", "Open a workspace first.", parent=self)
            return
        name = simpledialog.askstring("New Folder", "Folder name:", parent=self)
        if not name or Path(name).name != name or name in {".", ".."}:
            return
        try:
            (self.project_root / name).mkdir()
        except OSError as exc:
            messagebox.showerror("New Folder", str(exc), parent=self)
            return
        self.refresh_workspace()

    def _select_open_editor(self, _event=None):
        selection = self.open_editors_list.curselection()
        if selection:
            editors = list(self.documents)
            if selection[0] < len(editors):
                self.editor_tabs.select(self.documents[editors[selection[0]]]["frame"])

    def _refresh_open_editors(self):
        if not hasattr(self, "open_editors_list"):
            return
        self.open_editors_list.delete(0, "end")
        for _editor, document in self.documents.items():
            path = document.get("path")
            marker = "● " if document.get("dirty") else "   "
            self.open_editors_list.insert(
                "end", marker + (path.name if path else "Untitled")
            )

    def _add_tool_tab(self, child, title, icon_name, color_key):
        """Add a lower-panel tab and retain its icon for live theme refreshes."""
        image = self._icon(icon_name, self.theme_palette.get(color_key))
        self.tabs.add(child, text=title, image=image, compound="left")
        self._tool_tab_icon_bindings.append((child, icon_name, color_key))

    def _workspace(self):
        # Pack the status bar before the expanding workspace so it always reserves bottom space.
        status_row = ttk.Frame(self, style="PyLex.Toolbar.TFrame", padding=(10, 3))
        status_row.pack(fill="x", side="bottom")
        self.status = ttk.Label(
            status_row,
            text="Ready",
            style="PyLex.Status.TLabel",
            anchor="w",
            padding=(6, 3),
        )
        self.status.pack(side="left", fill="x", expand=True)
        self.editor_status = ttk.Frame(status_row, style="PyLex.Toolbar.TFrame")
        self.editor_status.pack(side="right")
        self._editor_status_items = {}
        self._editor_status_separators = []
        for index, key in enumerate(
            ("position", "indent", "encoding", "eol", "language", "mode")
        ):
            if index:
                separator = ttk.Separator(self.editor_status, orient="vertical")
                separator.pack(side="left", fill="y", padx=2, pady=3)
                self._editor_status_separators.append(separator)
            label = ttk.Label(
                self.editor_status,
                text="",
                style="PyLex.Status.TLabel",
                padding=(7, 3),
                anchor="center",
            )
            label.pack(side="left")
            self._editor_status_items[key] = label
        ttk.Separator(self, orient="horizontal").pack(fill="x", side="bottom")
        self._apply_status_bar_visibility()
        self.status_row = status_row

        # Right-click must work across the complete status strip, not only
        # on the small indicators at its far-right edge.
        def bind_status_context(widget):
            widget.bind("<Button-3>", self._show_status_context_menu, add="+")
            for child in widget.winfo_children():
                bind_status_context(child)

        bind_status_context(status_row)
        self._update_editor_status()

        shell = ttk.Frame(self)
        shell.pack(fill="both", expand=True, padx=8, pady=(2, 8))
        self.workspace_shell = shell
        activity = ttk.Frame(shell, style="PyLex.Activity.TFrame", padding=(4, 9))
        activity.pack(side="left", fill="y")
        activity.configure(width=66)
        activity.pack_propagate(False)
        self.activity_buttons = {}
        for view, icon_name, label, color_key in (
            ("explorer", "folder2-open", "Explorer", "accent"),
            ("search", "search", "Search", "muted"),
            ("source", "git", "Source", "violet"),
            ("debug", "bug-fill", "Debug", "success"),
            ("extensions", "boxes", "Quality", "warning"),
        ):
            button = ttk.Button(
                activity,
                text=label,
                command=lambda name=view: self._activity_action(name),
                style="PyLex.Activity.TButton",
                image=self._icon(icon_name, self.theme_palette.get(color_key), size=21),
                compound="top",
            )
            button.pack(fill="x", pady=4, ipadx=1, ipady=7)
            button.bind(
                "<Button-3>",
                lambda event, name=view: self._show_activity_context_menu(name, event),
                add="+",
            )
            button.bind(
                "<Leave>",
                lambda _event, target=button: target.state(["!active", "!selected"]),
                add="+",
            )
            button.bind(
                "<FocusOut>",
                lambda _event, target=button: target.state(["!active", "!selected"]),
                add="+",
            )
            self.activity_buttons[view] = (button, icon_name, color_key)
        ttk.Separator(activity).pack(fill="x", pady=(10, 6))
        account_button = ttk.Button(
            activity,
            text="Account",
            command=self.show_account,
            style="PyLex.Activity.TButton",
            image=self._icon("person-circle", self.theme_palette.get("muted"), size=21),
            compound="top",
        )
        account_button.pack(side="bottom", fill="x", pady=4, ipady=7)
        account_button.configure(takefocus=False)
        settings_button = ttk.Button(
            activity,
            text="Manage",
            command=self.open_preferences,
            style="PyLex.Activity.TButton",
            image=self._icon("gear-fill", self.theme_palette.get("muted"), size=21),
            compound="top",
        )
        settings_button.pack(side="bottom", fill="x", pady=4, ipady=7)
        settings_button.configure(takefocus=False)
        self.activity_account_button = (account_button, "person-circle", "muted")
        self.activity_settings_button = (settings_button, "gear-fill", "muted")
        workspace = ttk.Panedwindow(shell, orient="horizontal")
        self.workspace = workspace
        workspace.pack(side="left", fill="both", expand=True)
        self.project_root = None
        self.explorer_frame = ttk.Frame(workspace)
        explorer_header = ttk.Frame(self.explorer_frame, padding=(6, 5))
        explorer_header.pack(fill="x")
        ttk.Label(explorer_header, text="EXPLORER", style="PyLex.Section.TLabel").pack(
            side="left"
        )
        explorer_actions = ttk.Frame(self.explorer_frame, padding=(7, 3))
        explorer_actions.pack(fill="x")
        for icon_name, label, command, color_key in (
            ("file-earmark-plus", "New file", self.new_file, "accent"),
            ("folder-plus", "New folder", self.create_project_folder, "success"),
            ("arrow-clockwise", "Refresh", self.refresh_workspace, "muted"),
            ("folder2-open", "Open folder", self.open_project_folder, "accent"),
        ):
            action = ttk.Button(
                explorer_actions,
                text=label,
                command=command,
                style="PyLex.IconAction.TButton",
                image=self._icon(icon_name, self.theme_palette.get(color_key)),
            )
            action.pack(side="left", padx=(0, 3))
            self._toolbar_icon_bindings.append((action, icon_name, color_key))
        ttk.Separator(self.explorer_frame).pack(fill="x", pady=(4, 6))
        ttk.Label(
            self.explorer_frame,
            text="OPEN EDITORS",
            style="PyLex.Group.TLabel",
            padding=(9, 4),
        ).pack(fill="x")
        self.open_editors_list = tk.Listbox(
            self.explorer_frame,
            height=4,
            activestyle="none",
            borderwidth=0,
            highlightthickness=0,
            bg=self.theme_palette["surface"],
            fg=self.theme_palette["editor_fg"],
            selectbackground=self.theme_palette["accent"],
        )
        self.open_editors_list.pack(fill="x", padx=6, pady=(0, 8))
        self.open_editors_list.bind("<Double-1>", self._select_open_editor)
        self.open_editors_list.bind(
            "<Button-3>", self._show_open_editors_context_menu, add="+"
        )
        ttk.Label(
            self.explorer_frame,
            text="WORKSPACE",
            style="PyLex.Group.TLabel",
            padding=(9, 4),
        ).pack(fill="x")
        self.workspace_path_label = ttk.Label(
            self.explorer_frame,
            text="No folder opened",
            style="PyLex.Muted.TLabel",
            padding=(9, 4),
        )
        self.workspace_path_label.pack(fill="x")
        self.project_tree = ttk.Treeview(
            self.explorer_frame, show="tree", selectmode="browse"
        )
        self.project_tree.pack(fill="both", expand=True, padx=4, pady=(0, 5))
        self.project_tree.tag_configure(
            "directory", foreground=self.theme_palette["accent"]
        )
        self.project_tree.tag_configure(
            "python", foreground=self.theme_palette["file_python"]
        )
        self.project_tree.tag_configure(
            "web", foreground=self.theme_palette["file_web"]
        )
        self.project_tree.tag_configure(
            "markup", foreground=self.theme_palette["file_markup"]
        )
        self.project_tree.tag_configure(
            "style", foreground=self.theme_palette["file_style"]
        )
        self.project_tree.tag_configure(
            "data", foreground=self.theme_palette["file_data"]
        )
        self.project_tree.tag_configure(
            "config", foreground=self.theme_palette["muted"]
        )
        self.project_tree.tag_configure(
            "text", foreground=self.theme_palette["editor_fg"]
        )
        self.project_tree.bind("<Double-1>", self._on_project_tree_open)
        self.project_tree.bind(
            "<Button-3>", self._show_project_tree_context_menu, add="+"
        )
        self.project_tree.bind(
            "<Shift-F10>", self._show_project_tree_context_menu, add="+"
        )
        if self.preferences["show_project_explorer"]:
            workspace.add(self.explorer_frame, weight=1)

        panes = ttk.Panedwindow(workspace, orient="vertical")
        self.editor_panes = panes
        workspace.add(panes, weight=5)
        self.editor_tabs = ttk.Notebook(panes)
        panes.add(self.editor_tabs, weight=4)
        self.editor_tabs.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self.editor_tabs.bind("<Button-1>", self._on_tab_close_click, add="+")
        self.editor_tabs.bind("<Button-3>", self._show_tab_context_menu, add="+")
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
            lower,
            self._terminal_context,
            default_shell=self.preferences.get("terminal_shell", ""),
            on_shell_change=self._save_terminal_shell,
            on_run_file=self.run_active_file_in_terminal,
        )
        self._add_tool_tab(self.terminal_panel, "Terminal", "terminal", "accent")
        self.quality_panel = QualityPanel(
            lower,
            self._quality_context,
            self._quality_document,
            self._apply_formatted_source,
            self._navigate_quality_diagnostic,
            status_callback=lambda message: self.status.configure(text=message),
            project_format_guard=self._can_format_project,
        )
        self._add_tool_tab(self.quality_panel, "Quality", "check2-square", "success")
        self.git_panel = GitPanel(
            lower,
            lambda: self.project.root if self.project else None,
            status_callback=lambda message: self.status.configure(text=message),
        )
        self._add_tool_tab(self.git_panel, "Git", "git", "violet")

    def _update_editor_status(self, editor=None):
        """Refresh compact, editor-specific indicators in the bottom status strip."""
        if not hasattr(self, "_editor_status_items"):
            return
        editor = editor or self.editor
        if editor is None or editor not in self.documents:
            values = {
                "position": "Ln 1, Col 1",
                "indent": "Spaces: 4",
                "encoding": "UTF-8",
                "eol": "LF",
                "language": "Plain Text",
                "mode": "INS",
            }
        else:
            line, column = editor.text.index("insert").split(".")
            document = self.documents.get(editor, {})
            path = document.get("path")
            language = file_type_for(path).description if path else "Python"
            content = editor.get_content()
            eol = "CRLF" if "\r\n" in content else "LF"
            leading = next((line for line in content.splitlines() if line.strip()), "")
            indent = "Tabs" if leading.startswith("\t") else "Spaces: 4"
            values = {
                "position": f"Ln {line}, Col {int(column) + 1}",
                "indent": indent,
                "encoding": "UTF-8",
                "eol": eol,
                "language": language,
                "mode": "INS",
            }
        values["indent"] = self.preferences.get("status_bar_indent", values["indent"])
        values["encoding"] = self.preferences.get("status_bar_encoding", "UTF-8")
        eol_mode = self.preferences.get("status_bar_eol", "Auto")
        if eol_mode != "Auto":
            values["eol"] = eol_mode
        for key, value in values.items():
            self._editor_status_items[key].configure(text=value)

    def _apply_status_bar_visibility(self):
        visible = set(
            self.preferences.get("status_bar_items", DEFAULTS["status_bar_items"])
        )
        for label in self._editor_status_items.values():
            label.pack_forget()
        for separator in self._editor_status_separators:
            separator.pack_forget()
        visible_keys = [key for key in self._editor_status_items if key in visible]
        for index, key in enumerate(visible_keys):
            if index:
                self._editor_status_separators[index - 1].pack(
                    side="left", fill="y", padx=2, pady=3
                )
            self._editor_status_items[key].pack(side="left")

    def _configured_indent_string(self):
        value = self.preferences.get("status_bar_indent", "Spaces: 4")
        if value == "Tabs":
            return "\t"
        try:
            width = int(value.split(":", 1)[1].strip())
        except (IndexError, ValueError):
            width = 4
        return " " * max(1, min(8, width))

    def _configure_status_bar(self):
        """Open the inline status-bar context menu; no separate settings window."""
        try:
            x, y = self.winfo_pointerxy()
        except tk.TclError:
            x, y = (
                self.winfo_rootx() + 20,
                self.winfo_rooty() + self.winfo_height() - 24,
            )
        event = type("PointerEvent", (), {"x_root": x, "y_root": y})()
        self._show_status_context_menu(event)

    def _configure_status_item(self, _item):
        self._configure_status_bar()

    def _set_status_item_visible(self, key, visible):
        current = set(
            self.preferences.get("status_bar_items", DEFAULTS["status_bar_items"])
        )
        if visible:
            current.add(key)
        else:
            if len(current) <= 1:
                self.status.configure(
                    text="At least one status item must remain visible."
                )
                return
            current.discard(key)
        order = ("position", "indent", "encoding", "eol", "language", "mode")
        self.preferences["status_bar_items"] = [
            item for item in order if item in current
        ]
        self._persist_preferences()
        self._apply_status_bar_visibility()

    def _set_status_preference(self, key, value):
        self.preferences[key] = value
        if key == "status_bar_indent":
            indent_string = self._configured_indent_string()
            for editor in self.documents:
                editor.indent_string = indent_string
        self._persist_preferences()
        self._update_editor_status()

    def _new_context_menu(self):
        return ContextMenu(
            self,
            palette=self.theme_palette,
            font_family=self._resolved_ui_font(),
            font_size=self.preferences.get("ui_font_size", 9),
        )

    def _show_status_context_menu(self, event):
        menu = self._new_context_menu()
        visible = set(
            self.preferences.get("status_bar_items", DEFAULTS["status_bar_items"])
        )
        menu.add_command(label="Status Bar  ·  Visible Items", state="disabled")
        menu.add_separator()
        labels = (
            ("position", "Cursor Position"),
            ("indent", "Indentation"),
            ("encoding", "Encoding"),
            ("eol", "Line Ending"),
            ("language", "Language Mode"),
            ("mode", "Insert / Overwrite Mode"),
        )
        menu._status_vars = []
        for key, label in labels:
            variable = tk.BooleanVar(self, value=key in visible)
            menu._status_vars.append(variable)
            menu.add_checkbutton(
                label=label,
                variable=variable,
                command=lambda item=key, var=variable: self._set_status_item_visible(
                    item, var.get()
                ),
            )
        menu.add_separator()
        for title, key, values in (
            (
                "Indentation",
                "status_bar_indent",
                ("Spaces: 2", "Spaces: 4", "Spaces: 8", "Tabs"),
            ),
            ("Encoding", "status_bar_encoding", ("UTF-8", "UTF-8 with BOM", "ASCII")),
            ("Line Ending", "status_bar_eol", ("Auto", "LF", "CRLF")),
        ):
            submenu = self._new_context_menu()
            variable = tk.StringVar(self, value=self.preferences.get(key, values[0]))
            menu._status_vars.append(variable)
            for value in values:
                submenu.add_radiobutton(
                    label=value,
                    variable=variable,
                    value=value,
                    command=lambda setting=key, choice=value: self._set_status_preference(
                        setting, choice
                    ),
                )
            menu.add_cascade(label=title, menu=submenu)
        menu.add_separator()
        menu.add_command(label="Reset to Defaults", command=self._reset_status_bar)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _reset_status_bar(self):
        for key in (
            "status_bar_items",
            "status_bar_indent",
            "status_bar_encoding",
            "status_bar_eol",
        ):
            self.preferences[key] = (
                list(DEFAULTS[key]) if key == "status_bar_items" else DEFAULTS[key]
            )
        self._persist_preferences()
        self._apply_status_bar_visibility()
        self._update_editor_status()

    def _show_tree_data_context_menu(self, tree, event):
        row = tree.identify_row(event.y)
        column = tree.identify_column(event.x)
        if row:
            tree.selection_set(row)
            tree.focus(row)
        menu = self._new_context_menu()
        if row:
            values = tree.item(row, "values")
            menu.add_command(
                label="Copy Row",
                command=lambda: self._copy_to_clipboard("  |  ".join(map(str, values))),
            )
            if column and column != "#0":
                index = int(column[1:]) - 1
                if index < len(values):
                    menu.add_command(
                        label="Copy Cell",
                        command=lambda: self._copy_to_clipboard(values[index]),
                    )
            menu.add_command(
                label="Select All",
                command=lambda: tree.selection_set(tree.get_children("")),
            )
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _text_context_menu(self, widget, event):
        menu = self._new_context_menu()
        try:
            selected = bool(widget.tag_ranges("sel"))
        except (tk.TclError, AttributeError):
            selected = False
        menu.add_command(
            label="Copy",
            command=lambda: widget.event_generate("<<Copy>>"),
            state="normal" if selected else "disabled",
        )
        menu.add_command(
            label="Select All", command=lambda: widget.tag_add("sel", "1.0", "end-1c")
        )
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _text_panel(self, title):
        frame = ttk.Frame(self.tabs)
        row = 0
        if title == "Output":
            actions = ttk.Frame(frame, padding=(4, 3))
            actions.grid(row=0, column=0, columnspan=2, sticky="ew")
            ttk.Button(actions, text="Clear Output", command=self.clear_output).pack(
                side="left", padx=2
            )
            ttk.Button(actions, text="Save Output...", command=self.save_output).pack(
                side="left", padx=2
            )
            ttk.Button(
                actions, text="Force Stop Run", command=self.stop_execution
            ).pack(side="left", padx=2)
            ttk.Button(actions, text="Stop Debugger", command=self.stop_debugging).pack(
                side="left", padx=2
            )
            row = 1
        text = tk.Text(frame, wrap="none", font=("Consolas", 10), height=8)
        text.tag_configure("stderr", foreground="#d9534f")
        text.tag_configure("stdout", foreground="#5b9b68")
        text.tag_configure("system", foreground="#4b83c3")
        text.bind(
            "<Button-3>",
            lambda event, widget=text: self._text_context_menu(widget, event),
            add="+",
        )
        # Text widgets retain native wheel/keyboard scrolling without visible bars.
        text.bind(
            "<Shift-MouseWheel>",
            lambda event: (
                text.xview_scroll(-int(event.delta / 120) * 3, "units"),
                "break",
            ),
            add="+",
        )
        text.grid(row=row, column=0, columnspan=2, sticky="nsew")
        frame.rowconfigure(row, weight=1)
        frame.columnconfigure(0, weight=1)
        if title == "Output":
            input_row = ttk.Frame(frame, padding=(4, 4))
            input_row.grid(row=row + 1, column=0, columnspan=2, sticky="ew")
            ttk.Label(input_row, text="Program Input").pack(side="left", padx=(2, 7))
            self.output_input = ttk.Entry(input_row)
            self.output_input.pack(side="left", fill="x", expand=True)
            self.output_input.bind("<Return>", self._send_output_input)
            ttk.Button(input_row, text="Send", command=self._send_output_input).pack(
                side="left", padx=(6, 2)
            )
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
        cwd = (
            project.working_directory_for(path)
            if project
            else (Path(path).expanduser().resolve().parent if path else Path.cwd())
        )
        env = project.execution_environment() if project else dict(os.environ)
        if path:
            env["PYLEX_ACTIVE_FILE"] = str(Path(path).expanduser().resolve())
        else:
            env.pop("PYLEX_ACTIVE_FILE", None)
        if project:
            env["PYLEX_WORKSPACE_ROOT"] = str(project.root)
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
        return (
            self.editor,
            document.get("path") if document else None,
            self.editor.get_content(),
        )

    def _apply_formatted_source(self, editor, source):
        """Apply Black output only to the editor that initiated the request."""
        if editor not in self.documents:
            self.status.configure(
                text="Formatted output discarded: the originating tab was closed."
            )
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
        self.status.configure(
            text="Current editor buffer formatted with Black. Save to keep the changes."
        )

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
            if (
                document.get("path") is not None
                and Path(document["path"]).resolve() == path
            ):
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
            diagnostic.get("line", 1),
            max(0, diagnostic.get("column", 1) - 1),
            diagnostic.get("end_line"),
            diagnostic.get("end_column"),
        )
        self.status.configure(
            text=f"{diagnostic.get('code', 'Ruff')} — {path.name}:{diagnostic.get('line', 1)}"
        )

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
        """Open a shell in the active document's workspace context."""
        self.tabs.select(self.terminal_panel)
        cwd, _env, _interpreter = self._terminal_context()
        desired_cwd = Path(cwd).expanduser().resolve()
        document = self._active_document()
        active_path = document.get("path") if document else self.current_path
        desired_file = Path(active_path).expanduser().resolve() if active_path else None
        frame = self.terminal_panel._current_frame()
        session = self.terminal_panel.sessions.get(frame)
        if (
            session is None
            or not session.running
            or session.cwd != desired_cwd
            or getattr(session, "active_file", None) != desired_file
        ):
            return self.terminal_panel.create_session(cwd_override=desired_cwd)
        view = self.terminal_panel.views.get(frame)
        if view:
            view["entry"].focus_set()
        return session

    def _dependencies_panel(self):
        frame = ttk.Frame(self.tabs, padding=4)
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(0, 4))
        ttk.Button(
            actions, text="Scan Current File", command=self.scan_dependencies
        ).pack(side="left")
        ttk.Button(
            actions, text="Python Interpreter...", command=self.manage_interpreter
        ).pack(side="left", padx=4)
        ttk.Button(
            actions,
            text="Copy Python Install Command",
            command=self.copy_install_command,
        ).pack(side="left", padx=4)
        self.dependency_environment = ttk.Label(
            frame, text="Python environment: not scanned"
        )
        self.dependency_environment.pack(fill="x", pady=(2, 5))
        columns = ("module", "status", "distribution", "version")
        self.dependency_tree = ttk.Treeview(
            frame, columns=columns, show="headings", height=7
        )
        for key, label in (
            ("module", "Import"),
            ("status", "Status"),
            ("distribution", "Package / Source"),
            ("version", "Version"),
        ):
            self.dependency_tree.heading(key, text=label)
        self.dependency_tree.column("module", width=150)
        self.dependency_tree.column("status", width=100, anchor="center")
        self.dependency_tree.column("distribution", width=220)
        self.dependency_tree.column("version", width=170)
        self.dependency_tree.pack(fill="both", expand=True)
        self.dependency_tree.bind(
            "<Button-3>",
            lambda event, tree=self.dependency_tree: self._show_tree_data_context_menu(
                tree, event
            ),
            add="+",
        )
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
        return probe_interpreter(
            self.preferences.get("interpreter_path") or sys.executable
        )

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
        ttk.Label(body, text="Workspace: " + str(project.root)).grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        ttk.Label(body, text="Interpreter").grid(row=1, column=0, sticky="w", pady=6)
        status = ttk.Label(body, text=current.executable)
        status.grid(row=2, column=0, columnspan=3, sticky="w", pady=6)
        if warning:
            status.configure(
                text="Saved interpreter is unavailable: "
                + warning
                + " — choose a replacement."
            )
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
        status.configure(
            text="Scanning installed Python interpreters in the background..."
        )
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
            status.configure(
                text="Found " + str(len(value)) + " verified Python interpreter(s)."
            )

        dialog.after(120, poll_discovery)

        def browse():
            path = filedialog.askopenfilename(
                parent=dialog,
                title="Select Python",
                filetypes=[
                    ("Python executable", "*.exe" if os.name == "nt" else "python*"),
                    ("All files", "*.*"),
                ],
            )
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
            self.status.configure(
                text="Workspace interpreter set to automatic detection."
            )
            dialog.destroy()

        def repair_pip():
            try:
                base = selected()
            except ValueError as exc:
                messagebox.showerror("Repair pip", str(exc), parent=dialog)
                return
            repair_button.configure(state="disabled")
            status.configure(
                text="Checking and repairing pip in the selected interpreter..."
            )
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
                messagebox.showerror(
                    "Create .venv",
                    "The .venv folder already exists and is not empty.",
                    parent=dialog,
                )
                return
            create_button.configure(state="disabled")
            status.configure(text="Creating project virtual environment...")
            result = queue.Queue()

            def worker():
                try:
                    result.put(
                        ("ok", create_virtual_environment(base.executable, target))
                    )
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
        ttk.Button(
            buttons, text="Use for Workspace", command=lambda: apply("project")
        ).pack(side="left", padx=3)
        ttk.Button(buttons, text="Use Globally", command=lambda: apply("global")).pack(
            side="left", padx=3
        )
        ttk.Button(buttons, text="Auto Detect", command=reset).pack(side="left", padx=3)
        repair_button = ttk.Button(buttons, text="Repair pip", command=repair_pip)
        repair_button.pack(side="left", padx=3)
        create_button = ttk.Button(
            buttons, text="Create Project .venv", command=create_env
        )
        create_button.pack(side="left", padx=3)
        ttk.Button(buttons, text="Close", command=dialog.destroy).pack(
            side="right", padx=3
        )

    def _update_dependency_view(
        self, dependencies, scan_error=None, python_executable=None
    ):
        for item in self.dependency_tree.get_children():
            self.dependency_tree.delete(item)
        for dependency in dependencies:
            version = dependency.version or (
                "—" if dependency.status != "missing" else "Not installed"
            )
            self.dependency_tree.insert(
                "",
                "end",
                values=(
                    dependency.import_name,
                    dependency.status,
                    dependency.distribution,
                    version,
                ),
                tags=(dependency.status,),
            )
        env = python_environment(
            python_executable
            or self._interpreter_for_project(
                self._project_for_document(self._active_document())
            ).executable
        )
        mode = "venv" if env["virtual_environment"] else "base interpreter"
        message = f"Python {env['version']} ({mode}, pip {'available' if env['pip_available'] else 'missing'}) — {env['executable']}"
        if scan_error:
            message += " | " + scan_error
        self.dependency_environment.configure(text=message)

    def scan_dependencies(self):
        document = self._active_document()
        root = self._project_for_document(document).root
        try:
            interpreter = self._interpreter_for_project(
                self._project_for_document(document)
            )
        except (OSError, ValueError, TimeoutError) as exc:
            self.status.configure(text=f"Python interpreter error: {exc}")
            return
        dependencies, error = inspect_dependencies(
            self.editor.get_content(),
            search_root=root,
            python_executable=interpreter.executable,
        )
        self._update_dependency_view(dependencies, error, interpreter.executable)
        self.tabs.select(self.dependency_tree.master)
        missing = sum(item.status == "missing" for item in dependencies)
        self.status.configure(
            text=(
                f"Dependency scan complete — {len(dependencies)} imports, {missing} missing."
                if not error
                else "Dependency scan needs valid Python syntax."
            )
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
            interpreter = self._interpreter_for_project(
                self._project_for_document(self._active_document())
            )
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
        self.error_tree = ttk.Treeview(
            frame, columns=columns, show="headings", height=7
        )
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
        self.error_tree.bind(
            "<Button-3>",
            lambda event, tree=self.error_tree: self._show_tree_data_context_menu(
                tree, event
            ),
            add="+",
        )
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
                "warning"
                if "warning" in diagnostic.error_type.lower()
                else "info" if "info" in diagnostic.error_type.lower() else "error"
            )
            self.error_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    diagnostic.error_type,
                    diagnostic.line,
                    diagnostic.column + 1,
                    diagnostic.message,
                    diagnostic.source_line.strip(),
                ),
                tags=(severity,),
            )
        count = len(self.diagnostics)
        self.error_summary.configure(
            text=(
                f"{count} diagnostic(s) found. Select or double-click an item to jump to its location."
                if count
                else "No diagnostics. The current source passed lexical and syntax checks."
            )
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
            diagnostic.line,
            diagnostic.column,
            diagnostic.end_line,
            diagnostic.end_column,
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
            self._refresh_open_editors()
            if self.editor is editor:
                self._sync_active_document()
                if self.diagnostics:
                    self._set_diagnostics([])
                    self.error_summary.configure(
                        text="Source changed. Run Analyze All to refresh diagnostics."
                    )
        self.document_controller.mark_dirty(editor, True)
        editor.clear_diagnostic()

    def _project_for_document(self, document=None):
        """Resolve a project context for a document or the current workspace."""
        path = document.get("path") if document else None
        return self.workspace_controller.project_for_file(path)

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
                "Choose No to keep this tab open with its unsaved changes.",
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
        recent = [
            item
            for item in recent
            if isinstance(item, str) and Path(item).expanduser() != Path(normalized)
        ]
        self.preferences["recent_workspaces"] = [normalized] + recent[:7]
        self.preferences["last_workspace"] = normalized
        self._persist_preferences()
        self._refresh_recent_workspace_menu()
        self._refresh_recent_workspace_list()

    def _refresh_recent_workspace_menu(self):
        menu = getattr(self, "recent_workspace_menu", None)
        if menu is None:
            return
        menu.delete(0, "end")
        recent = self.preferences.get("recent_workspaces", [])
        valid = [
            item for item in recent if isinstance(item, str) and Path(item).is_dir()
        ]
        if not valid:
            menu.add_command(label="No recent workspaces", state="disabled")
        else:
            for item in valid:
                menu.add_command(
                    label=Path(item).name + " — " + item,
                    command=lambda value=item: self._activate_workspace(value),
                )
        menu.add_separator()
        menu.add_command(
            label="Clear Recent Workspaces", command=self.clear_recent_workspaces
        )

    def _refresh_recent_workspace_list(self):
        """Compatibility no-op: recent workspaces are accessed from the File menu."""
        return

    def _select_recent_workspace(self, _event=None):
        return

    def _recent_workspace_toolbar_items(self):
        """Build the File toolbar's dynamic, hover-only recent-workspace submenu."""
        recent = [
            value
            for value in self.preferences.get("recent_workspaces", [])
            if isinstance(value, str) and Path(value).is_dir()
        ]
        items = []
        if not recent:
            items.append(("No recent workspaces", None))
        else:
            for value in recent:
                folder = Path(value)
                actions = [
                    (
                        "Open Workspace",
                        lambda target=value: self._activate_workspace(target),
                    ),
                    (
                        "Open in File Manager",
                        lambda target=folder: self._reveal_path(target),
                    ),
                    (
                        "Open Terminal Here",
                        lambda target=folder: self._open_terminal_at(target),
                    ),
                    None,
                    (
                        "Copy Workspace Path",
                        lambda target=value: self._copy_to_clipboard(target),
                    ),
                    (
                        "Remove from Recent",
                        lambda target=value: self._remove_recent_workspace(target),
                    ),
                ]
                items.append(("submenu", folder.name, actions))
        items.extend(
            [
                None,
                ("Open Workspace…", self.open_project_folder),
                ("Clear Recent Workspaces", self.clear_recent_workspaces),
            ]
        )
        return items

    def _show_recent_workspace_menu(self):
        """Show a styled, action-rich recent-workspace picker."""
        menu = self._new_context_menu()
        recent = [
            value
            for value in self.preferences.get("recent_workspaces", [])
            if isinstance(value, str) and Path(value).is_dir()
        ]
        menu.add_command(label="OPEN RECENT WORKSPACE", state="disabled")
        menu.add_separator()
        if not recent:
            menu.add_command(label="No recent workspaces", state="disabled")
        for value in recent:
            folder = Path(value)
            actions = self._new_context_menu()
            actions.add_command(
                label="Open Workspace",
                command=lambda target=value: self._activate_workspace(target),
            )
            actions.add_command(
                label="Open in File Manager",
                command=lambda target=folder: self._reveal_path(target),
            )
            actions.add_command(
                label="Open Terminal Here",
                command=lambda target=folder: self._open_terminal_at(target),
            )
            actions.add_separator()
            actions.add_command(
                label="Copy Workspace Path",
                command=lambda target=value: self._copy_to_clipboard(target),
            )
            actions.add_command(
                label="Remove from Recent",
                command=lambda target=value: self._remove_recent_workspace(target),
            )
            menu.add_cascade(label=folder.name, menu=actions)
        menu.add_separator()
        menu.add_command(label="Open Workspace…", command=self.open_project_folder)
        menu.add_command(
            label="Clear Recent Workspaces",
            command=self.clear_recent_workspaces,
            state="normal" if recent else "disabled",
        )
        x, y = self.winfo_pointerxy()
        menu.tk_popup(x, y)

    def _copy_to_clipboard(self, value):
        self.clipboard_clear()
        self.clipboard_append(str(value))
        self.status.configure(text="Copied to clipboard.")

    def clear_recent_workspaces(self):
        """Clear workspace history without changing the current workspace."""
        self.preferences["recent_workspaces"] = []
        self._persist_preferences()
        self._refresh_recent_workspace_menu()
        self._refresh_recent_workspace_list()
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
        self.workspace_controller.open(candidate)
        self.project_root = candidate.root
        self._remember_workspace(candidate.root)
        self._populate_project_tree()
        self._refresh_recent_workspace_list()
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
        self.workspace_controller.close()
        self.project_root = None
        self.project_tree.delete(*self.project_tree.get_children())
        self.workspace_path_label.configure(
            text="No folder opened — use Open Folder to start a workspace"
        )
        self.preferences["last_workspace"] = ""
        self._persist_preferences()
        self.status.configure(
            text=f"Workspace closed: {closed}. Open editor tabs were kept."
        )
        self.git_panel.refresh()

    def _restore_last_workspace(self):
        """Restore the most recently used workspace when it still exists."""
        previous = self.preferences.get("last_workspace", "")
        if not previous:
            return
        self.project = self.workspace_controller.restore(previous)
        if self.project is None:
            self.preferences["last_workspace"] = ""
            self._persist_preferences()
            return
        self.project_root = self.project.root
        self._remember_workspace(self.project_root)
        self.workspace_path_label.configure(text=str(self.project_root))
        self._populate_project_tree()
        self._refresh_recent_workspace_list()
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
        editor = self.document_controller.find_path(resolved)
        if editor is not None:
            document = self.documents[editor]
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
            "",
            "end",
            text=self.project_root.name,
            image=self._icon("folder-fill", self.theme_palette.get("accent"), 18),
            values=(str(self.project_root), "directory"),
            tags=("directory",),
            open=True,
        )
        ignored = {
            ".git",
            ".venv",
            "venv",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".tox",
            "node_modules",
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
                        parent_id,
                        "end",
                        text=entry.name,
                        image=self._icon(
                            "folder", self.theme_palette.get("accent"), 18
                        ),
                        values=(str(entry), "directory"),
                        tags=("directory",),
                        open=False,
                    )
                    add_children(node, entry)
                elif entry.is_file():
                    info = file_type_for(entry)
                    icon_color = self.theme_palette.get(
                        f"file_{info.kind}", self.theme_palette.get("editor_fg")
                    )
                    self.project_tree.insert(
                        parent_id,
                        "end",
                        text=entry.name,
                        image=self._icon(
                            self._file_icon_name(info.kind), icon_color, 18
                        ),
                        values=(str(entry), info.kind),
                        tags=(info.kind,),
                    )

        add_children(root_id, self.project_root)

    def _show_recent_workspace_context_menu(self, event):
        index = self.recent_workspaces_list.nearest(event.y)
        self.recent_workspaces_list.selection_clear(0, "end")
        self.recent_workspaces_list.selection_set(index)
        menu = self._new_context_menu()
        paths = getattr(self, "_recent_workspace_paths", [])
        if index < len(paths):
            path = paths[index]
            menu.add_command(
                label="Open Workspace", command=lambda: self._activate_workspace(path)
            )
            menu.add_command(
                label="Copy Path", command=lambda: self._copy_to_clipboard(path)
            )
            menu.add_command(
                label="Remove from Recent",
                command=lambda: self._remove_recent_workspace(path),
            )
        menu.add_command(
            label="Clear Recent Workspaces", command=self.clear_recent_workspaces
        )
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _remove_recent_workspace(self, path):
        target = os.path.normcase(os.path.abspath(path))
        self.preferences["recent_workspaces"] = [
            p
            for p in self.preferences.get("recent_workspaces", [])
            if os.path.normcase(os.path.abspath(p)) != target
        ]
        self._persist_preferences()
        self._refresh_recent_workspace_menu()
        self._refresh_recent_workspace_list()

    def _show_open_editors_context_menu(self, event):
        index = self.open_editors_list.nearest(event.y)
        editors = list(self.documents)
        menu = self._new_context_menu()
        if index < len(editors):
            editor = editors[index]
            doc = self.documents[editor]
            menu.add_command(
                label="Activate", command=lambda: self.editor_tabs.select(doc["frame"])
            )
            menu.add_command(
                label="Close", command=lambda: self._close_document(editor)
            )
            if doc.get("path"):
                menu.add_command(
                    label="Copy Path",
                    command=lambda: self._copy_to_clipboard(doc["path"]),
                )
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _close_document(self, editor):
        if editor not in self.documents:
            return
        self.editor_tabs.select(self.documents[editor]["frame"])
        self.editor = editor
        self._sync_active_document()
        self.close_tab()

    def _show_tab_context_menu(self, event):
        try:
            index = self.editor_tabs.index("@{},{}".format(event.x, event.y))
        except (tk.TclError, ValueError):
            return "break"
        frame = self.editor_tabs.tabs()[index]
        editor = next(
            (
                item
                for item, doc in self.documents.items()
                if str(doc["frame"]) == frame
            ),
            None,
        )
        if editor is None:
            return "break"
        self.editor_tabs.select(frame)
        self.editor = editor
        menu = self._new_context_menu()
        menu.add_command(label="Close", command=self.close_tab)
        menu.add_command(
            label="Close Others", command=lambda: self._close_other_documents(editor)
        )
        menu.add_command(label="Close All", command=self._close_all_documents)
        path = self.documents[editor].get("path")
        if path:
            menu.add_separator()
            menu.add_command(
                label="Copy Path", command=lambda: self._copy_to_clipboard(path)
            )
            menu.add_command(
                label="Show in File Manager", command=lambda: self._reveal_path(path)
            )
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _close_other_documents(self, keep):
        for editor in list(self.documents):
            if editor is keep:
                continue
            self.editor_tabs.select(self.documents[editor]["frame"])
            self.editor = editor
            self._sync_active_document()
            if not self._confirm():
                return
            self.editor_tabs.forget(self.documents[editor]["frame"])
            self.document_controller.remove(editor)
        self._refresh_open_editors()
        self.editor_tabs.select(self.documents[keep]["frame"])
        self.editor = keep
        self._sync_active_document()

    def _close_all_documents(self):
        for editor in list(self.documents):
            self.editor_tabs.select(self.documents[editor]["frame"])
            self.editor = editor
            self._sync_active_document()
            if not self._confirm():
                return
            self.editor_tabs.forget(self.documents[editor]["frame"])
            self.document_controller.remove(editor)
        self._refresh_open_editors()
        self._create_document()

    def _reveal_path(self, path):
        target = path if Path(path).is_dir() else Path(path).parent
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(target))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except OSError as exc:
            messagebox.showerror("Show in File Manager", str(exc), parent=self)

    def _copy_relative_workspace_path(self, path):
        try:
            relative = Path(path).resolve().relative_to(self.project_root.resolve())
        except (ValueError, AttributeError, OSError):
            relative = Path(path)
        self._copy_to_clipboard(str(relative))

    def _open_terminal_at(self, path):
        """Start a terminal session rooted at the selected workspace directory."""
        target = Path(path)
        target = target if target.is_dir() else target.parent
        if not target.is_dir():
            messagebox.showerror(
                "Open Terminal", f"Folder does not exist: {target}", parent=self
            )
            return
        self.tabs.select(self.terminal_panel)
        process = self.terminal_panel.create_session(cwd_override=str(target))
        if process is not None:
            self.status.configure(text=f"Terminal opened at {target}")

    def _show_project_tree_context_menu(self, event):
        row = self.project_tree.identify_row(event.y)
        if not row and self.project_root is not None:
            roots = self.project_tree.get_children("")
            row = roots[0] if roots else ""
        if row:
            self.project_tree.selection_set(row)
            self.project_tree.focus(row)
        values = self.project_tree.item(row, "values") if row else ()
        path = Path(values[0]) if values else self.project_root
        is_root = (
            path is not None
            and self.project_root is not None
            and path == self.project_root
        )
        menu = self._new_context_menu()

        if path is None:
            menu.add_command(label="Open Workspace…", command=self.open_project_folder)
            menu.add_command(
                label="Open Recent Workspaces", command=self._show_recent_workspace_menu
            )
        elif path.is_dir():
            menu.add_command(
                label=(
                    "Collapse Folder"
                    if row and self.project_tree.item(row, "open")
                    else "Expand Folder"
                ),
                command=lambda target=row: self._open_tree_directory(target),
            )
            menu.add_separator()
            menu.add_command(
                label="New File…",
                command=lambda target=path: self._create_tree_item(target, "file"),
            )
            menu.add_command(
                label="New Folder…",
                command=lambda target=path: self._create_tree_item(target, "folder"),
            )
            menu.add_command(
                label="Open Terminal Here",
                command=lambda target=path: self._open_terminal_at(target),
            )
            menu.add_separator()
            menu.add_command(label="Refresh Explorer", command=self.refresh_workspace)
            if is_root:
                menu.add_command(
                    label="Open Recent Workspaces",
                    command=self._show_recent_workspace_menu,
                )
                menu.add_command(label="Close Workspace", command=self.close_workspace)
        else:
            menu.add_command(
                label="Open", command=lambda target=path: self._open_path(target)
            )
            menu.add_command(
                label="Open with System App",
                command=lambda target=path: self._open_external_file(target),
            )
            menu.add_command(
                label="Open Containing Folder",
                command=lambda target=path: self._reveal_path(target),
            )
            menu.add_command(
                label="Open Terminal Here",
                command=lambda target=path: self._open_terminal_at(target),
            )

        if path is not None:
            menu.add_separator()
            menu.add_command(
                label="Copy Path",
                command=lambda target=path: self._copy_to_clipboard(target),
            )
            menu.add_command(
                label="Copy Relative Path",
                command=lambda target=path: self._copy_relative_workspace_path(target),
            )
            menu.add_command(
                label="Show in File Manager",
                command=lambda target=path: self._reveal_path(target),
            )
            if not is_root:
                menu.add_separator()
                menu.add_command(
                    label="Rename…",
                    command=lambda target=path: self._rename_tree_path(target),
                )
                menu.add_command(
                    label="Delete…",
                    command=lambda target=path: self._delete_tree_path(target),
                )
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _open_tree_directory(self, row):
        if row and self.project_tree.exists(row):
            self.project_tree.item(
                row, open=not bool(self.project_tree.item(row, "open"))
            )

    def _create_tree_item(self, directory, kind):
        name = simpledialog.askstring(
            "New " + kind.title(), kind.title() + " name:", parent=self
        )
        if not name or Path(name).name != name or name in {".", ".."}:
            return
        target = directory / name
        try:
            target.mkdir() if kind == "folder" else target.touch(exist_ok=False)
        except OSError as exc:
            messagebox.showerror("Create " + kind.title(), str(exc), parent=self)
            return
        self.refresh_workspace()
        if kind == "file":
            self._open_path(target)

    def _rename_tree_path(self, path):
        name = simpledialog.askstring(
            "Rename", "New name:", initialvalue=path.name, parent=self
        )
        if not name or Path(name).name != name or name in {".", ".."}:
            return
        destination = path.with_name(name)
        was_directory = path.is_dir()
        try:
            path.rename(destination)
        except OSError as exc:
            messagebox.showerror("Rename", str(exc), parent=self)
            return
        for _editor, document in self.documents.items():
            opened = document.get("path")
            if opened and (opened == path or was_directory and path in opened.parents):
                document["path"] = (
                    destination / opened.relative_to(path)
                    if opened != path
                    else destination
                )
                self.editor_tabs.tab(document["frame"], text=self._tab_label(document))
        self._sync_active_document()
        self.refresh_workspace()

    def _delete_tree_path(self, path):
        if any(
            document.get("path")
            and (
                document["path"] == path
                or path.is_dir()
                and path in document["path"].parents
            )
            for document in self.documents.values()
        ):
            messagebox.showwarning(
                "Delete",
                "Close files inside this item before deleting it.",
                parent=self,
            )
            return
        if not messagebox.askyesno(
            "Delete",
            "Delete {!r}? This cannot be undone.".format(path.name),
            parent=self,
        ):
            return
        try:
            shutil.rmtree(path) if path.is_dir() else path.unlink()
        except OSError as exc:
            messagebox.showerror("Delete", str(exc), parent=self)
            return
        self.refresh_workspace()

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
            requested,
            "Segoe UI",
            "Inter",
            "Noto Sans",
            "Ubuntu",
            "DejaVu Sans",
            "Arial",
            "Tahoma",
            "TkDefaultFont",
        )
        return next(
            (family for family in candidates if family in available), "TkDefaultFont"
        )

    def _resolved_code_font(self, available_fonts=None):
        """Choose the best installed coding font with reliable cross-platform fallbacks."""
        available = set(available_fonts or tkfont.families(self))
        requested = self.preferences.get("font_family", DEFAULTS["font_family"])
        candidates = (
            requested,
            "JetBrains Mono",
            "Cascadia Code",
            "Fira Code",
            "Consolas",
            "Cascadia Mono",
            "DejaVu Sans Mono",
            "Liberation Mono",
            "Courier New",
            "Lucida Console",
            "TkFixedFont",
        )
        return next(
            (family for family in candidates if family in available), "TkFixedFont"
        )

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
        self.document_controller.remove(self.editor)
        self._refresh_open_editors()
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
        editor = CodeEditor(
            frame,
            on_change=lambda: self.mark_dirty(editor),
            on_cursor_change=lambda: self._update_editor_status(editor),
        )
        editor.pack(fill="both", expand=True)
        editor.indent_string = self._configured_indent_string()
        editor.text.bind("<<PyLexAnalyze>>", lambda _event: self.analyze_all(), add="+")
        editor.set_content(content)
        self.document_controller.register(
            editor,
            {
                "frame": frame,
                "path": Path(path) if path else None,
                "dirty": False,
            },
        )
        self._refresh_open_editors()
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
            frame,
            text=self._tab_label(document),
            image=self._icon(tab_icon, tab_color),
            compound="left",
        )
        self.editor_tabs.select(frame)
        self.editor = editor
        editor.set_font_family(self._resolved_code_font())
        editor.set_font_size(self.preferences["font_size"])
        editor.set_theme(self.dark, self.theme_palette)
        self._sync_active_document()
        self._update_editor_status(editor)
        self.editor.set_breakpoints(self.breakpoints.get(editor, set()))
        return editor

    def _active_document(self):
        return self.document_controller.get(self.editor)

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
                self._update_editor_status(editor)
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
            f"Save changes to {document['path'].name if document['path'] else 'Untitled'} before continuing?",
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
            source = self.editor.get_content().replace("\r\n", "\n").replace("\r", "\n")
            eol = self.preferences.get("status_bar_eol", "Auto")
            if eol == "CRLF":
                source = source.replace("\n", "\r\n")
            encoding = self.preferences.get("status_bar_encoding", "UTF-8")
            codec = {
                "UTF-8": "utf-8",
                "UTF-8 with BOM": "utf-8-sig",
                "ASCII": "ascii",
            }.get(encoding, "utf-8")
            document["path"].write_text(source, encoding=codec, newline="")
            document["dirty"] = False
            self.editor_tabs.tab(document["frame"], text=self._tab_label(document))
            self._sync_active_document()
            self.status.configure(text="File saved.")
            return True
        except (OSError, UnicodeError) as exc:
            messagebox.showerror("Save Error", str(exc))
            return False

    def save_as(self):
        document = self._active_document()
        if document is None:
            return False
        path = filedialog.asksaveasfilename(
            defaultextension=".py",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")],
        )
        if not path:
            return False
        path = Path(path)
        for editor, other in self.documents.items():
            if (
                editor is not self.editor
                and other["path"]
                and other["path"].resolve() == path.resolve()
            ):
                messagebox.showerror(
                    "Save Error", "That file is already open in another tab."
                )
                return False
        document["path"] = path
        return self.save_file()

    def analyze_lexical(self):
        source = self.editor.get_content()
        try:
            tokens = lexical_analysis(source)
            report = format_tokens(tokens)
            self.status.configure(
                text=f"Lexical analysis complete — {len(tokens)} tokens."
            )
        except Exception as exc:
            report = f"{type(exc).__name__}: {exc}"
            self.status.configure(
                text=f"Lexical analysis failed — {type(exc).__name__}."
            )
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
            text=(
                "Syntax analysis successful."
                if result.success
                else f"{result.error_type or 'Syntax error'} detected."
            )
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
            self.status.configure(
                text="Stop debugging before starting normal execution."
            )
            return
        if self.execution is not None and not self.execution.done:
            self.status.configure(
                text="A program is already running. Force Stop it before starting another."
            )
            return
        source = self.editor.get_content()
        document = self._active_document()
        project = self._project_for_document(document)
        try:
            interpreter = self._interpreter_for_project(project)
        except (OSError, ValueError, TimeoutError) as exc:
            messagebox.showerror("Python Interpreter", str(exc))
            return
        dependencies, scan_error = inspect_dependencies(
            source, search_root=project.root, python_executable=interpreter.executable
        )
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
                lines.append(
                    "pip is unavailable in this interpreter. Use Tools → Python Interpreter → Repair pip first."
                )
            lines.append(
                "Static scanning cannot detect every dynamic import; runtime errors are also reported.\n"
            )
            self._append_output("\n".join(lines) + "\n", "system")
        elif not scan_error:
            self._append_output(
                "Dependency check: no missing imports detected.\n", "system"
            )
        self._append_output("Starting program...\n", "system")
        try:
            timeout = self.preferences["timeout_seconds"]
            self.execution_controller.start_document(
                source,
                document.get("path") if document else None,
                project,
                timeout=timeout,
                dirty=bool(document and document.get("dirty")),
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
        if self.execution_controller.stop():
            self.status.configure(text="Force-stopping process and child processes...")
            return
        if self.debugger_controller.stop():
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
                status_text = (
                    "Running — no time limit. Use Force Stop / Shift+F5 to terminate."
                )
            else:
                remaining = max(
                    0, int(timeout - (time.monotonic() - handle.started_at) + 0.999)
                )
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
        self.execution_controller.finish(handle)
        self._execution_poll = None

    def run_active_file_in_terminal(self):
        """Run the active, saved editor document in the integrated shell."""
        document = self._active_document()
        if document is None:
            messagebox.showinfo("Run Active File", "Open a Python file first.")
            return
        if document["path"] is None or document["dirty"]:
            if not self.save_file():
                return
            document = self._active_document()
        path = document.get("path") if document else None
        if path is None or not Path(path).is_file():
            messagebox.showwarning(
                "Run Active File", "Save the active file before running it in Terminal."
            )
            return
        _cwd, _env, interpreter = self._terminal_context()
        if not interpreter:
            messagebox.showerror(
                "Run Active File",
                "No Python interpreter is available for this workspace.",
            )
            return
        session = self.open_terminal()
        if session is None or not session.running:
            messagebox.showerror(
                "Run Active File", "Could not create a terminal for this file."
            )
            return
        frame = self.terminal_panel._current_frame()
        view = self.terminal_panel.views.get(frame, {})
        shell = view.get("shell", self.terminal_panel.shell_var.get())
        try:
            command = python_file_command(shell, interpreter, path)
        except ValueError as exc:
            messagebox.showerror("Run Active File", str(exc))
            return
        if not self.terminal_panel.run_command(command):
            messagebox.showerror(
                "Run Active File", "The terminal session is not ready."
            )

    def _send_output_input(self, _event=None):
        """Forward one line from Output to the active run or debug process."""
        if not hasattr(self, "output_input"):
            return "break"
        value = self.output_input.get()
        accepted = False
        if self.execution is not None and not self.execution.done:
            accepted = self.execution.send_input(value)
        elif self.debug_session is not None and not self.debug_session.done:
            accepted = self.debug_session.send_input(value)
        if not accepted:
            self.status.configure(text="No running program is waiting for input.")
            return "break"
        self._append_output(value + "\n", "system")
        self.output_input.delete(0, "end")
        self.output_input.focus_set()
        self.status.configure(text="Input sent to the running program.")
        return "break"

    def _append_output(self, content, channel="stdout"):
        self.output.configure(state="normal")
        self.output.insert(
            "end",
            content,
            channel if channel in {"stdout", "stderr", "system"} else "stdout",
        )
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
            title="Save Execution Output",
            defaultextension=".txt",
            filetypes=[
                ("Text files", "*.txt"),
                ("Log files", "*.log"),
                ("All files", "*.*"),
            ],
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
            stderr,
            re.MULTILINE,
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

                package = PIP_NAMES.get(
                    module.split(".", 1)[0], module.split(".", 1)[0]
                )
                interpreter = self._interpreter_for_project(
                    self._project_for_document(self._active_document())
                ).executable
                message = (
                    f"Missing library '{module}'. Install it into the active interpreter with: "
                    f'"{interpreter}" -m pip install "{package}"'
                )
        from .analyzer import Diagnostic

        diagnostic = Diagnostic(
            error_type,
            message,
            line,
            0,
            line,
            0,
            source_line,
        )
        self._set_diagnostics([diagnostic])
        self.tabs.select(self.error_tree.master)
        self.status.configure(
            text=f"Runtime error: {error_type} — line {line}. See Errors and Output."
        )

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
            self.status.configure(
                text="Stop normal execution before starting the debugger."
            )
            return
        if self.debug_session is not None and not self.debug_session.done:
            self.status.configure(text="A debugging session is already active.")
            return
        try:
            document = self._active_document()
            project = self._project_for_document(document)
            self.debugger_controller.start_document(
                self.editor.get_content(),
                document.get("path") if document else None,
                project,
                dirty=bool(document and document.get("dirty")),
                python_executable=self._interpreter_for_project(project).executable,
            )
        except (OSError, ValueError, TimeoutError) as exc:
            messagebox.showerror("Debugger Error", str(exc))
            return
        self._show(
            self.output, "Debugger started. Set breakpoints, then choose Continue.\n"
        )
        conditions = self.conditional_breakpoints.get(self.editor, {})
        for line in sorted(self.breakpoints.get(self.editor, set())):
            condition = conditions.get(line)
            if condition:
                self.debug_session.set_conditional_breakpoint(line, condition)
            else:
                self.debug_session.set_breakpoint(line)
        self.status.configure(
            text="Debugger ready — set breakpoints or press Continue."
        )
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
            "Debugger — Jump to Line",
            "Target line:",
            parent=self,
            minvalue=1,
        )
        if line is not None:
            try:
                session.jump(line)
                self.status.configure(
                    text=f"Requested jump to line {line} (pdb frame restrictions apply)."
                )
            except ValueError as exc:
                messagebox.showerror("Debugger", str(exc))

    def debug_evaluate(self):
        session = self._active_debug_session()
        if session is None:
            return
        expression = simpledialog.askstring(
            "Debugger — Evaluate",
            "Python expression in the selected frame:",
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
            self.status.configure(
                text=f"Temporary breakpoint requested at line {line}."
            )
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
            self.status.configure(
                text=f"Conditional breakpoint requested at line {line}."
            )
        except ValueError as exc:
            messagebox.showerror("Debugger", str(exc))

    def debug_manage_breakpoint(self, action):
        session = self._active_debug_session()
        if session is None:
            return
        number = simpledialog.askinteger(
            "Debugger — Breakpoint",
            "Breakpoint number (shown by pdb's breakpoint list):",
            parent=self,
            minvalue=1,
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
                    "Ignore Breakpoint Hits",
                    "Number of hits to ignore:",
                    parent=self,
                    minvalue=1,
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
        self.debugger_controller.stop()
        self.status.configure(text="Stopping debugger...")

    def _poll_debugger(self):
        session = self.debug_session
        if session is None:
            return
        output = session.read_available()
        if output:
            self._append_output(output)
        if session.done:
            completion = session.completion_status
            session.close()
            final_output = session.read_available()
            if final_output:
                self._append_output(final_output)
            self.debugger_controller.finish(close=False, session=session)
            self._debug_poll = None
            if completion == "error":
                self._append_output(
                    "\nDEBUG RESULT: Unhandled exception detected.\n", "stderr"
                )
                self.status.configure(
                    text="Debugging finished with an unhandled exception."
                )
            elif completion == "finished":
                self._append_output(
                    "\nDEBUG RESULT: Program completed successfully.\n", "system"
                )
                self.status.configure(text="Debugging finished successfully.")
            else:
                self.status.configure(text="Debugging session stopped.")
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

        ttk.Button(body, text="Find Next", command=find_next).grid(
            row=3, column=1, sticky="ew", padx=2
        )
        ttk.Button(body, text="Replace", command=replace_one).grid(
            row=3, column=2, sticky="ew", padx=2
        )
        ttk.Button(body, text="Replace All", command=replace_all).grid(
            row=3, column=3, sticky="ew", padx=2
        )
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
        dialog.geometry("960x700")
        dialog.minsize(820, 600)
        dialog.resizable(True, True)

        shell = ttk.Frame(dialog, padding=16)
        shell.pack(fill="both", expand=True)
        ttk.Label(shell, text="Settings", style="PyLex.DialogTitle.TLabel").pack(
            anchor="w", pady=(0, 2)
        )
        ttk.Label(
            shell,
            text="Personalize the editor and workspace experience.",
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
        productivity_page = ttk.Frame(notebook, padding=16)
        extensions_page = ttk.Frame(notebook, padding=16)
        security_page = ttk.Frame(notebook, padding=16)
        pages = (
            (appearance, "Appearance"),
            (editor_page, "Editor"),
            (workspace_page, "Workspace"),
            (execution_page, "Execution"),
            (productivity_page, "Productivity"),
            (languages_page, "Languages"),
            (extensions_page, "Extensions"),
            (security_page, "Privacy & Security"),
            (help_page, "Help"),
        )
        for page, label in pages:
            notebook.add(page, text=label)
        if initial_tab == "help":
            notebook.select(help_page)

        ttk.Label(
            languages_page,
            text="Language roadmap",
            style="PyLex.DialogTitle.TLabel",
        ).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            languages_page,
            text="The workspace already recognizes common web file types. Full syntax highlighting, "
            "language-aware editing and analysis will be enabled incrementally in a later release.",
            style="PyLex.Muted.TLabel",
            wraplength=560,
        ).pack(anchor="w", pady=(0, 14))
        for name, status, color_key, description in (
            (
                "Python",
                "Available now",
                "success",
                "Editing, highlighting, analysis, execution and debugging",
            ),
            (
                "JavaScript",
                "Planned",
                "warning",
                "Dedicated lexer, completion and diagnostics",
            ),
            (
                "HTML",
                "Planned",
                "warning",
                "Markup highlighting and document-aware editing",
            ),
            (
                "CSS",
                "Planned",
                "warning",
                "Stylesheet highlighting and language-aware tooling",
            ),
        ):
            row = ttk.Frame(languages_page, padding=(10, 8))
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=name, style="PyLex.Field.TLabel", width=16).pack(
                side="left"
            )
            ttk.Label(
                row, text=status, foreground=self.theme_palette[color_key], width=14
            ).pack(side="left")
            ttk.Label(row, text=description, style="PyLex.Muted.TLabel").pack(
                side="left", padx=(8, 0)
            )

        ttk.Label(
            productivity_page,
            text="Keyboard-first workflow",
            style="PyLex.DialogTitle.TLabel",
        ).pack(anchor="w", pady=(0, 8))
        shortcut_rows = (
            ("Command Palette", "Ctrl+Shift+P", "Search available commands"),
            ("Quick Open", "Ctrl+P", "Find a workspace file by name"),
            ("Run Current File", "F5", "Execute the active Python file"),
            ("Stop Execution", "Shift+F5", "Stop the active run"),
            ("Start Debugging", "Ctrl+F5", "Start a debugger session"),
            ("Toggle Breakpoint", "F9", "Set or remove a breakpoint"),
            ("Step Over / Into", "F10 / F11", "Move through the current debug session"),
            ("Analyze All", "F6", "Run lexical and syntax analysis"),
            ("Settings", "Ctrl+,", "Open application preferences"),
        )
        for command, shortcut, description in shortcut_rows:
            row = ttk.Frame(productivity_page, padding=(10, 8))
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=command, style="PyLex.Field.TLabel", width=24).pack(
                side="left"
            )
            ttk.Label(
                row, text=shortcut, foreground=self.theme_palette["accent"], width=20
            ).pack(side="left")
            ttk.Label(row, text=description, style="PyLex.Muted.TLabel").pack(
                side="left", padx=(8, 0)
            )

        ttk.Label(
            extensions_page,
            text="Extensibility roadmap",
            style="PyLex.DialogTitle.TLabel",
        ).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            extensions_page,
            text="These are planned product capabilities, not active integrations. "
            "They will be introduced only with compatibility checks, clear permissions and tests.",
            style="PyLex.Muted.TLabel",
            wraplength=720,
        ).pack(anchor="w", pady=(0, 12))
        for name, state, detail in (
            ("Language packs", "Planned", "JavaScript, HTML and CSS language services"),
            (
                "Extension marketplace",
                "Planned",
                "Signed or trusted extensions with permission review",
            ),
            (
                "Language servers",
                "Planned",
                "LSP-based completion, navigation and diagnostics",
            ),
            (
                "Themes and icon packs",
                "Planned",
                "Validated third-party visual themes and icon sets",
            ),
            (
                "Project templates",
                "Planned",
                "Reusable starter projects and configurable scaffolding",
            ),
            (
                "Plugin API",
                "Planned",
                "Documented extension points with versioned compatibility",
            ),
        ):
            row = ttk.Frame(extensions_page, padding=(10, 8))
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=name, style="PyLex.Field.TLabel", width=24).pack(
                side="left"
            )
            ttk.Label(
                row, text=state, foreground=self.theme_palette["warning"], width=13
            ).pack(side="left")
            ttk.Label(row, text=detail, style="PyLex.Muted.TLabel").pack(
                side="left", padx=(8, 0)
            )

        ttk.Label(
            security_page,
            text="Security and privacy",
            style="PyLex.DialogTitle.TLabel",
        ).pack(anchor="w", pady=(0, 8))
        for heading, detail in (
            (
                "Local-first preferences",
                "Account display name and application preferences are stored locally.",
            ),
            (
                "Code execution",
                "Programs run with your operating-system permissions. PyLex Studio is not a security sandbox.",
            ),
            (
                "External integrations",
                "Cloud sync, telemetry and GitHub sign-in are not enabled by the current account screen.",
            ),
            (
                "Future extension permissions",
                "Planned extensions must declare capabilities and request user consent before accessing protected workflows.",
            ),
        ):
            card = ttk.Frame(security_page, padding=10)
            card.pack(fill="x", pady=4)
            ttk.Label(card, text=heading, style="PyLex.Field.TLabel").pack(anchor="w")
            ttk.Label(
                card, text=detail, style="PyLex.Muted.TLabel", wraplength=720
            ).pack(anchor="w", pady=(4, 0))

        theme_var = tk.StringVar(value=self.preferences["theme"])
        ttk.Label(appearance, text="Color theme", style="PyLex.Field.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )
        theme_box = ttk.Combobox(
            appearance,
            textvariable=theme_var,
            values=("dark", "light"),
            state="readonly",
            width=24,
        )
        theme_box.grid(row=1, column=0, sticky="w")
        ttk.Label(
            appearance,
            text="Dark uses deep navy surfaces with blue and violet accents. "
            "Light uses soft white surfaces and professional blue accents.",
            style="PyLex.Muted.TLabel",
            wraplength=560,
        ).grid(row=2, column=0, sticky="w", pady=(8, 18))

        available_fonts = sorted(tkfont.families(dialog), key=str.casefold)
        ui_font_var = tk.StringVar(value=self._resolved_ui_font(available_fonts))
        ui_size_var = tk.IntVar(value=self.preferences.get("ui_font_size", 9))
        ttk.Label(appearance, text="Interface font").grid(
            row=3, column=0, sticky="w", pady=(0, 5)
        )
        ui_fonts = [
            name
            for name in (
                "Segoe UI",
                "Inter",
                "Noto Sans",
                "Ubuntu",
                "DejaVu Sans",
                "Arial",
                "Tahoma",
            )
            if name in available_fonts
        ]
        if not ui_fonts:
            ui_fonts = ["TkDefaultFont"]
        ui_box = ttk.Combobox(
            appearance,
            textvariable=ui_font_var,
            values=ui_fonts,
            state="readonly",
            width=24,
        )
        ui_box.grid(row=4, column=0, sticky="w")
        ttk.Label(appearance, text="Interface size").grid(
            row=3, column=1, sticky="w", padx=(24, 0), pady=(0, 5)
        )
        ttk.Spinbox(appearance, from_=8, to=14, textvariable=ui_size_var, width=6).grid(
            row=4, column=1, sticky="w", padx=(24, 0)
        )

        code_fonts = [
            name
            for name in (
                "JetBrains Mono",
                "Cascadia Code",
                "Fira Code",
                "Consolas",
                "Cascadia Mono",
                "DejaVu Sans Mono",
                "Liberation Mono",
                "Courier New",
                "Lucida Console",
                "TkFixedFont",
            )
            if name in available_fonts
        ]
        if not code_fonts:
            code_fonts = ["TkFixedFont"]
        code_font_var = tk.StringVar(value=self._resolved_code_font(available_fonts))
        code_size_var = tk.IntVar(value=self.preferences["font_size"])
        ttk.Label(editor_page, text="Code font family").grid(
            row=0, column=0, sticky="w", pady=(0, 5)
        )
        code_box = ttk.Combobox(
            editor_page,
            textvariable=code_font_var,
            values=code_fonts,
            state="readonly",
            width=28,
        )
        code_box.grid(row=1, column=0, sticky="w")
        ttk.Label(editor_page, text="Code font size").grid(
            row=0, column=1, sticky="w", padx=(24, 0), pady=(0, 5)
        )
        ttk.Spinbox(
            editor_page, from_=8, to=32, textvariable=code_size_var, width=6
        ).grid(row=1, column=1, sticky="w", padx=(24, 0))
        ttk.Label(
            editor_page,
            text="JetBrains Mono is preferred for code when installed. "
            "Cascadia Code and Consolas are reliable fallbacks.",
            style="PyLex.Muted.TLabel",
            wraplength=560,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))

        explorer_var = tk.BooleanVar(value=self.preferences["show_project_explorer"])
        ttk.Checkbutton(
            workspace_page,
            text="Show project explorer on startup",
            variable=explorer_var,
        ).pack(anchor="w", pady=(0, 10))
        ttk.Label(
            workspace_page,
            text="Drag the separators between Explorer, Editor and the lower tool panel "
            "to resize each area. Use the mouse wheel over a panel to scroll.",
            style="PyLex.Muted.TLabel",
            wraplength=560,
        ).pack(anchor="w")

        timeout_var = tk.StringVar()
        current_timeout = self.preferences["timeout_seconds"]
        timeout_var.set(
            "Unlimited" if current_timeout is None else f"{current_timeout} seconds"
        )
        ttk.Label(execution_page, text="Execution timeout").grid(
            row=0, column=0, sticky="w", pady=(0, 5)
        )
        ttk.Combobox(
            execution_page,
            textvariable=timeout_var,
            values=("5 seconds", "10 seconds", "30 seconds", "60 seconds", "Unlimited"),
            state="readonly",
            width=22,
        ).grid(row=1, column=0, sticky="w")
        ttk.Label(
            execution_page,
            text="Unlimited execution is useful for long-running scripts. You can always stop a run manually.",
            style="PyLex.Muted.TLabel",
            wraplength=560,
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
            help_page,
            wrap="word",
            height=18,
            borderwidth=0,
            padx=8,
            pady=8,
            font=(ui_font_var.get(), 10),
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
                if DEFAULTS["ui_font_family"] in ui_fonts
                else ui_fonts[0]
            )
            ui_size_var.set(DEFAULTS["ui_font_size"])
            default_font = next(
                (
                    name
                    for name in (
                        "JetBrains Mono",
                        "Cascadia Code",
                        "Fira Code",
                        "Consolas",
                        "Cascadia Mono",
                        "DejaVu Sans Mono",
                        "Liberation Mono",
                        "Courier New",
                        "Lucida Console",
                        "TkFixedFont",
                    )
                    if name in code_fonts
                ),
                code_fonts[0],
            )
            code_font_var.set(default_font)
            code_size_var.set(DEFAULTS["font_size"])
            explorer_var.set(DEFAULTS["show_project_explorer"])
            timeout_var.set(
                "Unlimited"
                if DEFAULTS["timeout_seconds"] is None
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
                "5 seconds": 5,
                "10 seconds": 10,
                "30 seconds": 30,
                "60 seconds": 60,
                "Unlimited": None,
            }
            if selected_timeout not in timeout_map:
                messagebox.showerror(
                    "Settings", "Choose a valid execution timeout.", parent=dialog
                )
                return
            self.preferences.update(
                {
                    "theme": theme_var.get(),
                    "font_family": code_font_var.get(),
                    "font_size": code_size,
                    "ui_font_family": ui_font_var.get(),
                    "ui_font_size": ui_size,
                    "timeout_seconds": timeout_map[selected_timeout],
                }
            )
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

        ttk.Button(
            buttons, text="Apply", command=apply, style="PyLex.Primary.TButton"
        ).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="Reset to Defaults", command=reset_defaults).pack(
            side="left"
        )

    def show_about(self):
        """Show product identity and version outside the main title area."""
        dialog = tk.Toplevel(self)
        dialog.title("About PyLex Studio")
        dialog.transient(self)
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=26)
        body.pack(fill="both", expand=True)
        self._build_logo(body, 72)
        ttk.Label(body, text="PyLex Studio", style="PyLex.AboutTitle.TLabel").pack(
            anchor="w", pady=(12, 0)
        )
        ttk.Label(
            body,
            text=f"Version {__version__}",
            style="PyLex.Muted.TLabel",
        ).pack(anchor="w", pady=(2, 14))
        ttk.Label(
            body,
            text="A focused Python development environment with code editing, "
            "analysis, execution, debugging, Git and quality tools.",
            wraplength=390,
            justify="left",
        ).pack(anchor="w")
        ttk.Button(body, text="Close", command=dialog.destroy).pack(
            anchor="e", pady=(20, 0)
        )

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
            ".git",
            ".venv",
            "venv",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".tox",
            "node_modules",
            "dist",
            "build",
        }
        candidates = []
        for directory, subdirectories, filenames in os.walk(root):
            subdirectories[:] = sorted(
                name
                for name in subdirectories
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
        entry = ttk.Entry(
            dialog, textvariable=query, font=(self._resolved_ui_font(), 11)
        )
        entry.pack(fill="x", padx=12, pady=12)
        listing = tk.Listbox(
            dialog,
            activestyle="none",
            height=16,
            borderwidth=0,
            bg=self.theme_palette["surface"],
            fg=self.theme_palette["editor_fg"],
            selectbackground=self.theme_palette["accent"],
            selectforeground="#ffffff",
            highlightthickness=0,
        )
        listing.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        hint = ttk.Label(
            dialog,
            text="Type to filter  ·  Enter to open  ·  Esc to close",
            style="PyLex.Muted.TLabel",
            padding=(12, 0, 12, 10),
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
        """Open the searchable palette backed by the shared command registry."""
        registry = CommandRegistry(
            [
                Command("file.new", "New File", "Ctrl+N", self.new_file),
                Command("file.open", "Open File", "Ctrl+O", self.open_file),
                Command("file.save", "Save File", "Ctrl+S", self.save_file),
                Command(
                    "workspace.open",
                    "Open Workspace",
                    "",
                    self.open_project_folder,
                ),
                Command(
                    "file.quick-open",
                    "Quick Open File",
                    "Ctrl+P",
                    self.open_quick_file,
                ),
                Command("run.active", "Run Current File", "F5", self.run_code),
                Command("run.stop", "Stop Execution", "Shift+F5", self.stop_execution),
                Command("analysis.all", "Analyze All", "F6", self.analyze_all),
                Command(
                    "debug.start",
                    "Start Debugging",
                    "Ctrl+F5",
                    self.start_debugging,
                ),
                Command("terminal.open", "Open Terminal", "", self.open_terminal),
                Command(
                    "quality.open",
                    "Open Quality Tools",
                    "",
                    self.open_quality_tools,
                ),
                Command("git.open", "Open Git", "", self.open_git_tools),
                Command("view.theme", "Toggle Theme", "", self.toggle_theme),
                Command(
                    "settings.open",
                    "Settings",
                    "Ctrl+,",
                    self.open_preferences,
                ),
                Command("help.open", "Quick Start & Help", "", self.show_help),
                Command(
                    "about.open",
                    "About PyLex Studio",
                    "",
                    self.show_about,
                ),
            ]
        )
        CommandPalette(
            self,
            registry,
            palette=self.theme_palette,
            font_family=self._resolved_ui_font(),
            anchor=self.command_palette_frame,
        ).show()

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
        # Keep native Tk controls and dialogs aligned with the selected interface font.
        ui_family = self._resolved_ui_font()
        ui_size = self.preferences.get("ui_font_size", 9)
        for font_name in (
            "TkDefaultFont",
            "TkMenuFont",
            "TkHeadingFont",
            "TkCaptionFont",
            "TkSmallCaptionFont",
            "TkIconFont",
            "TkTooltipFont",
        ):
            try:
                tkfont.nametofont(font_name).configure(family=ui_family, size=ui_size)
            except tk.TclError:
                pass
        self._icon_cache.clear()
        self.configure(bg=palette["window_bg"])
        for editor in self.documents:
            editor.set_theme(self.dark, palette)
        for panel in (self.output, self.lexical, self.syntax):
            panel.configure(
                bg=palette["editor_bg"],
                fg=palette["editor_fg"],
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
                "python",
                "web",
                "markup",
                "style",
                "data",
                "config",
                "shell",
                "compiled",
                "image",
                "audio",
                "video",
                "pdf",
                "document",
                "archive",
                "database",
                "font",
                "text",
                "binary",
                "unknown",
            ):
                self.project_tree.tag_configure(
                    kind, foreground=palette.get(f"file_{kind}", palette["editor_fg"])
                )
        if hasattr(self, "run_button"):
            self.run_button.configure(image=self._icon("play-fill", palette["accent"]))
            self.stop_button.configure(image=self._icon("stop-fill", palette["danger"]))
        if hasattr(self, "command_palette_frame"):
            self.command_palette_frame.configure(
                background=palette["surface"],
                highlightbackground=palette["border"],
                highlightcolor=palette["accent"],
            )
            self.command_palette_label.configure(
                background=palette["surface"],
                foreground=palette["muted"],
                font=(ui_family, ui_size),
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
            self.help_button.configure(
                image=self._icon("question-circle", palette.get("muted"))
            )
        if hasattr(self, "settings_button"):
            self.settings_button.configure(
                image=self._icon("gear-fill", palette.get("muted"))
            )
        for button, icon_name, color_key in getattr(self, "_toolbar_icon_bindings", []):
            button.configure(image=self._icon(icon_name, palette.get(color_key)))
        for _view, (button, icon_name, color_key) in getattr(
            self, "activity_buttons", {}
        ).items():
            button.configure(image=self._icon(icon_name, palette.get(color_key)))
        for button, icon_name, color_key in (
            getattr(self, "activity_account_button", (None, None, None)),
            getattr(self, "activity_settings_button", (None, None, None)),
        ):
            if button is not None:
                button.configure(image=self._icon(icon_name, palette.get(color_key)))
        if hasattr(self, "open_editors_list"):
            self.open_editors_list.configure(
                bg=palette["surface"],
                fg=palette["editor_fg"],
                selectbackground=palette["accent"],
            )
        for child, icon_name, color_key in getattr(self, "_tool_tab_icon_bindings", []):
            try:
                self.tabs.tab(
                    child,
                    image=self._icon(icon_name, palette.get(color_key)),
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
                    document["frame"],
                    image=self._icon(icon_name, icon_color),
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
        if self.execution_controller.stop():
            handle = self.execution
            handle.wait(timeout=2)
            self.execution_controller.finish(handle)
        self.debugger_controller.finish()
        self.terminal_panel.close_all()
        self.quality_panel.close()
        self.git_panel.close()
        self.destroy()
