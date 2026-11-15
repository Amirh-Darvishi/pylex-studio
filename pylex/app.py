"""Main graphical interface for PyLex Studio."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
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
from .preferences import load_preferences, save_preferences


class PyLexApp(tk.Tk):
    """Main application window and coordinator for editor tools."""

    def __init__(self):
        super().__init__()
        self.title("PyLex Studio 1.3.0 — Python Editor")
        self.geometry("1180x780")
        self.minsize(850, 560)
        self.current_path = None
        self.dirty = False
        self.project = None
        self.execution_service = ExecutionService()
        self.preferences = load_preferences()
        self.dark = self.preferences["theme"] == "dark"
        self.diagnostics = []
        self.execution = None
        self._execution_poll = None
        self.debug_session = None
        self._debug_poll = None
        self._last_timeout_display = None
        self.breakpoints = {}
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
        file_menu = tk.Menu(menu, tearoff=False)
        for label, command in [
            ("New", self.new_file), ("Open...", self.open_file),
            ("Open Workspace...", self.open_project_folder),
            ("Close Workspace", self.close_workspace),
            ("Save", self.save_file), ("Save As...", self.save_as),
            ("Close Tab", self.close_tab),
        ]:
            file_menu.add_command(label=label, command=command)
        self.recent_workspace_menu = tk.Menu(file_menu, tearoff=False)
        file_menu.add_cascade(label="Open Recent Workspace", menu=self.recent_workspace_menu)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.close)
        self._refresh_recent_workspace_menu()
        menu.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menu, tearoff=False)
        edit_menu.add_command(label="Find / Replace...", command=self.find_replace)
        menu.add_cascade(label="Edit", menu=edit_menu)

        tools_menu = tk.Menu(menu, tearoff=False)
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
        tools_menu.add_command(label="Stop Debugging", command=self.stop_debugging)
        menu.add_cascade(label="Tools", menu=tools_menu)

        view_menu = tk.Menu(menu, tearoff=False)
        view_menu.add_command(label="Preferences...", command=self.open_preferences)
        view_menu.add_command(label="Toggle Project Explorer", command=self.toggle_project_explorer)
        menu.add_cascade(label="View", menu=view_menu)
        self.config(menu=menu)

        self.bind_all("<Control-n>", lambda event: self.new_file())
        self.bind_all("<Control-o>", lambda event: self.open_file())
        self.bind_all("<Control-s>", lambda event: self.save_file())
        self.bind_all("<Control-h>", lambda event: self.find_replace())
        self.bind_all("<Control-w>", lambda event: self.close_tab())
        self.bind_all("<Control-Shift-W>", lambda event: self.close_workspace())
        self.bind_all("<F5>", lambda event: self.run_code())
        self.bind_all("<Shift-F5>", lambda event: self.stop_execution())
        self.bind_all("<F6>", lambda event: self.analyze_all())

    def _toolbar(self):
        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")
        buttons = [
            ("New", self.new_file), ("Open", self.open_file),
            ("Open Workspace", self.open_project_folder),
            ("Close Workspace", self.close_workspace),
            ("Save", self.save_file), ("▶ Run", self.run_code), ("■ Force Stop", self.stop_execution),
            ("Debug", self.start_debugging), ("Continue", self.debug_continue),
            ("Step", self.debug_step), ("Next", self.debug_next),
            ("Breakpoint", self.toggle_breakpoint), ("Variables", self.debug_variables),
            ("Stack", self.debug_stack),
            ("Analyze All", self.analyze_all),
            ("Lexical", self.analyze_lexical), ("Syntax", self.analyze_syntax),
            ("Clear Results", self.clear_results),
            ("A+", lambda: self.zoom(1)), ("A-", lambda: self.zoom(-1)),
            ("Toggle Theme", self.toggle_theme),
        ]
        for label, action in buttons:
            ttk.Button(bar, text=label, command=action).pack(side="left", padx=2)

    def _workspace(self):
        workspace = ttk.Panedwindow(self, orient="horizontal")
        self.workspace = workspace
        workspace.pack(fill="both", expand=True, padx=6, pady=5)
        self.project_root = None
        self.explorer_frame = ttk.Frame(workspace)
        explorer_header = ttk.Frame(self.explorer_frame, padding=(6, 5))
        explorer_header.pack(fill="x")
        ttk.Label(explorer_header, text="WORKSPACE").pack(side="left")
        ttk.Button(explorer_header, text="Close", command=self.close_workspace).pack(side="right", padx=(4, 0))
        ttk.Button(explorer_header, text="Open Folder", command=self.open_project_folder).pack(side="right")
        ttk.Button(explorer_header, text="↻", width=3, command=self.refresh_workspace).pack(side="right", padx=(0, 4))
        self.workspace_path_label = ttk.Label(self.explorer_frame, text="No folder opened", padding=(7, 0, 7, 5))
        self.workspace_path_label.pack(fill="x")
        self.project_tree = ttk.Treeview(self.explorer_frame, show="tree", selectmode="browse")
        self.project_tree.pack(fill="both", expand=True)
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

        self.status = ttk.Label(self, text="Ready", padding=5)
        self.status.pack(fill="x")

    def _text_panel(self, title):
        frame = ttk.Frame(self.tabs)
        row = 0
        if title == "Output":
            actions = ttk.Frame(frame, padding=(4, 3))
            actions.grid(row=0, column=0, columnspan=2, sticky="ew")
            ttk.Button(actions, text="Clear Output", command=self.clear_output).pack(side="left", padx=2)
            ttk.Button(actions, text="Save Output...", command=self.save_output).pack(side="left", padx=2)
            ttk.Button(actions, text="Force Stop", command=self.stop_execution).pack(side="left", padx=2)
            row = 1
        text = tk.Text(frame, wrap="none", font=("Consolas", 10), height=8)
        text.tag_configure("stderr", foreground="#d9534f")
        text.tag_configure("stdout", foreground="#5b9b68")
        text.tag_configure("system", foreground="#4b83c3")
        ybar = ttk.Scrollbar(frame, command=text.yview)
        xbar = ttk.Scrollbar(frame, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        text.grid(row=row, column=0, sticky="nsew")
        ybar.grid(row=row, column=1, sticky="ns")
        xbar.grid(row=row + 1, column=0, sticky="ew")
        frame.rowconfigure(row, weight=1)
        frame.columnconfigure(0, weight=1)
        self.tabs.add(frame, text=title)
        return text

    def _dependencies_panel(self):
        frame = ttk.Frame(self.tabs, padding=4)
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(0, 4))
        ttk.Button(actions, text="Scan Current File", command=self.scan_dependencies).pack(side="left")
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
        self.tabs.add(frame, text="Dependencies")

    def _update_dependency_view(self, dependencies, scan_error=None):
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
        env = python_environment()
        mode = "venv" if env["virtual_environment"] else "base interpreter"
        message = f"Python {env['version']} ({mode}) — {env['executable']}"
        if scan_error:
            message += " | " + scan_error
        self.dependency_environment.configure(text=message)

    def scan_dependencies(self):
        document = self._active_document()
        root = self._project_for_document(document).root
        dependencies, error = inspect_dependencies(self.editor.get_content(), search_root=root)
        self._update_dependency_view(dependencies, error)
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
        env = python_environment()
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
        ybar = ttk.Scrollbar(frame, orient="vertical", command=self.error_tree.yview)
        self.error_tree.configure(yscrollcommand=ybar.set)
        self.error_tree.pack(side="left", fill="both", expand=True)
        ybar.pack(side="right", fill="y")
        self.error_tree.bind("<<TreeviewSelect>>", self._navigate_to_selected_error)
        self.error_tree.bind("<Double-1>", self._navigate_to_selected_error)
        self.tabs.add(frame, text="Errors")

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
            self.error_tree.insert(
                "", "end", iid=str(index),
                values=(
                    diagnostic.error_type, diagnostic.line,
                    diagnostic.column + 1, diagnostic.message,
                    diagnostic.source_line.strip(),
                ),
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
            if not self._confirm():
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
            "", "end", text=f"📂 {self.project_root.name}",
            values=(str(self.project_root), "directory"), open=True,
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
                        parent_id, "end", text=f"📁 {entry.name}",
                        values=(str(entry), "directory"), open=False,
                    )
                    add_children(node, entry)
                elif entry.is_file():
                    info = file_type_for(entry)
                    self.project_tree.insert(
                        parent_id, "end", text=f"{info.icon} {entry.name}",
                        values=(str(entry), info.kind),
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
        self.editor_tabs.add(frame, text=self._tab_label(self.documents[editor]))
        self.editor_tabs.select(frame)
        self.editor = editor
        editor.set_font_family(self.preferences["font_family"])
        editor.set_font_size(self.preferences["font_size"])
        editor.set_theme(self.dark)
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
        name = self.current_path.name if self.current_path else "Untitled"
        self.title(f"{'*' if self.dirty else ''}{name} — PyLex Studio 1.3.0")

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
        dependencies, scan_error = inspect_dependencies(source, search_root=project.root)
        self._update_dependency_view(dependencies, scan_error)
        self._show(self.output, "")
        env = python_environment()
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
                interpreter = python_environment()["executable"]
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
            if self.debug_session is not None and not self.debug_session.done:
                self.debug_session.clear_breakpoint(line)
            self.editor.set_breakpoints(points)
            self.status.configure(text=f"Breakpoint removed from line {line}.")
        else:
            points.add(line)
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
            )
        except OSError as exc:
            messagebox.showerror("Debugger Error", str(exc))
            return
        self._show(self.output, "Debugger started. Set breakpoints, then choose Continue.\n")
        for line in sorted(self.breakpoints.get(self.editor, set())):
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

    def open_preferences(self):
        dialog = tk.Toplevel(self)
        dialog.title("PyLex Studio Preferences")
        dialog.transient(self)
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=12)
        body.pack(fill="both", expand=True)

        ttk.Label(body, text="Theme").grid(row=0, column=0, sticky="w", pady=5)
        theme_var = tk.StringVar(value=self.preferences["theme"])
        theme_box = ttk.Combobox(
            body, textvariable=theme_var, values=("dark", "light"),
            state="readonly", width=20,
        )
        theme_box.grid(row=0, column=1, sticky="ew", pady=5)

        ttk.Label(body, text="Editor font").grid(row=1, column=0, sticky="w", pady=5)
        font_var = tk.StringVar(value=self.preferences["font_family"])
        font_box = ttk.Combobox(
            body, textvariable=font_var,
            values=("Consolas", "Cascadia Code", "Courier New", "Lucida Console"),
            state="readonly", width=20,
        )
        font_box.grid(row=1, column=1, sticky="ew", pady=5)

        ttk.Label(body, text="Font size").grid(row=2, column=0, sticky="w", pady=5)
        size_var = tk.IntVar(value=self.preferences["font_size"])
        size_box = tk.Spinbox(body, from_=7, to=40, textvariable=size_var, width=8)
        size_box.grid(row=2, column=1, sticky="w", pady=5)

        explorer_var = tk.BooleanVar(value=self.preferences["show_project_explorer"])
        ttk.Checkbutton(
            body, text="Show project explorer", variable=explorer_var,
        ).grid(row=3, column=0, columnspan=2, sticky="w", pady=5)

        ttk.Label(body, text="Execution timeout").grid(row=4, column=0, sticky="w", pady=5)
        timeout_values = ("5 seconds", "10 seconds", "30 seconds", "60 seconds", "Unlimited")
        current_timeout = self.preferences["timeout_seconds"]
        timeout_text = "Unlimited" if current_timeout is None else f"{current_timeout} seconds"
        timeout_var = tk.StringVar(value=timeout_text)
        timeout_box = ttk.Combobox(
            body, textvariable=timeout_var, values=timeout_values,
            state="readonly", width=20,
        )
        timeout_box.grid(row=4, column=1, sticky="ew", pady=5)

        def apply():
            self.preferences["theme"] = theme_var.get()
            self.preferences["font_family"] = font_var.get()
            try:
                self.preferences["font_size"] = max(7, min(40, int(size_var.get())))
            except (ValueError, tk.TclError):
                messagebox.showerror("Preferences", "Font size must be a number from 7 to 40.")
                return
            selected_timeout = timeout_var.get()
            timeout_map = {
                "5 seconds": 5, "10 seconds": 10,
                "30 seconds": 30, "60 seconds": 60,
                "Unlimited": None,
            }
            if selected_timeout not in timeout_map:
                messagebox.showerror("Preferences", "Choose a valid execution timeout.")
                return
            self.preferences["timeout_seconds"] = timeout_map[selected_timeout]
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

        buttons = ttk.Frame(body)
        buttons.grid(row=5, column=0, columnspan=2, sticky="e", pady=(10, 0))
        ttk.Button(buttons, text="Apply", command=apply).pack(side="right", padx=3)
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right", padx=3)

    def toggle_theme(self):
        self.dark = not self.dark
        self.preferences["theme"] = "dark" if self.dark else "light"
        self._theme()
        self._persist_preferences()

    def _theme(self):
        bg, fg = ("#1e1e1e", "#dddddd") if self.dark else ("#ffffff", "#202020")
        for editor in self.documents:
            editor.set_theme(self.dark)
        for panel in (self.output, self.lexical, self.syntax):
            panel.configure(bg=bg, fg=fg, insertbackground=fg)
        style = ttk.Style(self)
        if self.dark:
            style.configure("Treeview", background="#252526", foreground="#dddddd",
                            fieldbackground="#252526")
            style.configure("Treeview.Heading", background="#333333", foreground="#ffffff")
        else:
            style.configure("Treeview", background="#ffffff", foreground="#202020",
                            fieldbackground="#ffffff")
            style.configure("Treeview.Heading", background="#eeeeee", foreground="#202020")

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
        self.destroy()
