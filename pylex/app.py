"""Main graphical interface for PyLex Studio."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
import re

from .editor import CodeEditor
from .analyzer import (
    lexical_analysis, syntax_analysis, format_tokens, collect_diagnostics,
)
from .runner import start_source
from .dependencies import find_missing_imports
from .debugger import DebugSession
from .preferences import load_preferences, save_preferences


class PyLexApp(tk.Tk):
    """Main application window and coordinator for editor tools."""

    def __init__(self):
        super().__init__()
        self.title("PyLex Studio 1.2.0 — Python Editor")
        self.geometry("1180x780")
        self.minsize(850, 560)
        self.current_path = None
        self.dirty = False
        self.preferences = load_preferences()
        self.dark = self.preferences["theme"] == "dark"
        self.diagnostics = []
        self.execution = None
        self._execution_poll = None
        self.debug_session = None
        self._debug_poll = None
        self.breakpoints = {}
        self.documents = {}
        self.editor = None
        self._menu()
        self._toolbar()
        self._workspace()
        self._theme()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._title()

    def _menu(self):
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        for label, command in [
            ("New", self.new_file), ("Open...", self.open_file),
            ("Open Project Folder...", self.open_project_folder),
            ("Save", self.save_file), ("Save As...", self.save_as),
            ("Close Tab", self.close_tab),
        ]:
            file_menu.add_command(label=label, command=command)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.close)
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
        self.bind_all("<F5>", lambda event: self.run_code())
        self.bind_all("<Shift-F5>", lambda event: self.stop_execution())
        self.bind_all("<F6>", lambda event: self.analyze_all())

    def _toolbar(self):
        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")
        buttons = [
            ("New", self.new_file), ("Open", self.open_file),
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
        self.project_tree = ttk.Treeview(workspace, show="tree", selectmode="browse")
        self.project_tree.bind("<Double-1>", self._on_project_tree_open)
        if self.preferences["show_project_explorer"]:
            workspace.add(self.project_tree, weight=1)

        panes = ttk.Panedwindow(workspace, orient="vertical")
        self.editor_panes = panes
        workspace.add(panes, weight=5)
        self.editor_tabs = ttk.Notebook(panes)
        panes.add(self.editor_tabs, weight=4)
        self.editor_tabs.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self._create_document()

        lower = ttk.Frame(panes)
        panes.add(lower, weight=2)
        self.tabs = ttk.Notebook(lower)
        self.tabs.pack(fill="both", expand=True)

        self.output = self._text_panel("Output")
        self.lexical = self._text_panel("Lexical Analysis")
        self.syntax = self._text_panel("Syntax Analysis")
        self._errors_panel()

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
            label = document["path"].name if document["path"] else "Untitled"
            self.editor_tabs.tab(document["frame"], text="*" + label)
            if self.editor is editor:
                self._sync_active_document()
                if self.diagnostics:
                    self._set_diagnostics([])
                    self.error_summary.configure(text="Source changed. Run Analyze All to refresh diagnostics.")
        editor.clear_diagnostic()

    def open_project_folder(self):
        """Choose a project root and display its files in the explorer."""
        folder = filedialog.askdirectory(title="Open Project Folder")
        if not folder:
            return
        self.project_root = Path(folder)
        self._populate_project_tree()
        self.status.configure(text=f"Project opened: {self.project_root}")

    def _populate_project_tree(self):
        self.project_tree.delete(*self.project_tree.get_children())
        if self.project_root is None:
            return
        root_id = self.project_tree.insert(
            "", "end", text=self.project_root.name,
            values=(str(self.project_root),), open=True,
        )
        ignored = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", "node_modules"}

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
                        values=(str(entry),), open=False,
                    )
                    add_children(node, entry)
                elif entry.is_file():
                    self.project_tree.insert(
                        parent_id, "end", text=entry.name,
                        values=(str(entry),),
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
        if path.suffix.lower() not in {".py", ".pyw", ".txt", ".md", ".json", ".toml", ".yaml", ".yml"}:
            self.status.configure(text=f"Selected {path.name}.")
            return
        for editor, document in self.documents.items():
            if document["path"] and document["path"].resolve() == path.resolve():
                self.editor_tabs.select(document["frame"])
                self.editor = editor
                self._sync_active_document()
                return
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            messagebox.showerror("Open Error", str(exc))
            return
        self._create_document(path=path, content=content)
        self.status.configure(text=f"Opened {path.name}.")

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
        label = Path(path).name if path else "Untitled"
        self.editor_tabs.add(frame, text=label)
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
        self.title(f"{'*' if self.dirty else ''}{name} — PyLex Studio 1.2.0")

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
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )
        if not path:
            return
        path = Path(path)
        for editor, document in self.documents.items():
            if document["path"] and document["path"].resolve() == path.resolve():
                self.editor_tabs.select(document["frame"])
                self.editor = editor
                self._sync_active_document()
                return
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            messagebox.showerror("Open Error", str(exc))
            return
        self._create_document(path=path, content=content)
        self.clear_results()
        self.status.configure(text=f"Opened {path.name}.")

    def save_file(self):
        document = self._active_document()
        if document is None:
            return False
        if document["path"] is None:
            return self.save_as()
        try:
            document["path"].write_text(self.editor.get_content(), encoding="utf-8")
            document["dirty"] = False
            self.editor_tabs.tab(document["frame"], text=document["path"].name)
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
        missing = find_missing_imports(source)
        self._show(self.output, "")
        if missing:
            lines = [
                "DEPENDENCY CHECK — possible missing third-party libraries",
                "The following imports were not found in this Python environment:",
            ]
            lines.extend(f"  • {module}  →  python -m pip install {package}"
                         for module, package in missing)
            lines.append("Execution will continue; the real traceback will be shown if import fails.\n")
            self._append_output("\n".join(lines) + "\n", "system")
        self._append_output("Starting program...\n", "system")
        try:
            self.execution = start_source(source, timeout=10)
        except OSError as exc:
            self._append_output(f"Could not start Python process: {exc}\n", "stderr")
            self.status.configure(text="Could not start Python process.")
            return
        self.status.configure(text="Running — live output enabled. Shift+F5 / Force Stop terminates the process tree.")
        self._poll_execution()

    def stop_execution(self):
        if self.execution is None or self.execution.done:
            self.status.configure(text="No program is currently running.")
            return
        self.execution.force_stop()
        self.status.configure(text="Force-stopping process and child processes...")

    def _poll_execution(self):
        handle = self.execution
        if handle is None:
            return
        for channel, content in handle.read_available():
            self._append_output(content, channel)
        if not handle.done:
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
        missing = re.search(r"No module named ['\"]([^'\"]+)['\"]", stderr)
        if not missing:
            return
        module = missing.group(1)
        line_matches = re.findall(r'File "[^"]+", line (\d+)', stderr)
        line = int(line_matches[-1]) if line_matches else 1
        source_lines = self.editor.get_content().splitlines()
        source_line = source_lines[line - 1] if 1 <= line <= len(source_lines) else ""
        from .analyzer import Diagnostic
        diagnostic = Diagnostic(
            "ModuleNotFoundError",
            f"Missing library '{module}'. Install it with: python -m pip install {module}",
            line, 0, line, 0, source_line,
        )
        self._set_diagnostics([diagnostic])
        self.tabs.select(self.error_tree.master)
        self.status.configure(text=f"Missing dependency: {module}. See Errors and Output.")

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
            self.debug_session = DebugSession.start(self.editor.get_content())
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
            self.workspace.forget(self.project_tree)
        else:
            self.workspace.insert(0, self.project_tree, weight=1)
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

        def apply():
            self.preferences["theme"] = theme_var.get()
            self.preferences["font_family"] = font_var.get()
            try:
                self.preferences["font_size"] = max(7, min(40, int(size_var.get())))
            except (ValueError, tk.TclError):
                messagebox.showerror("Preferences", "Font size must be a number from 7 to 40.")
                return
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
        buttons.grid(row=4, column=0, columnspan=2, sticky="e", pady=(10, 0))
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
