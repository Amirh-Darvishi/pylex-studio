"""Main graphical interface for PyLex Studio."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from .editor import CodeEditor
from .analyzer import (
    lexical_analysis, syntax_analysis, format_tokens, collect_diagnostics,
)
from .runner import run_source


class PyLexApp(tk.Tk):
    """Main application window and coordinator for editor tools."""

    def __init__(self):
        super().__init__()
        self.title("PyLex Studio 1.1.1 — Python Editor")
        self.geometry("1180x780")
        self.minsize(850, 560)
        self.current_path = None
        self.dirty = False
        self.dark = True
        self.diagnostics = []
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
            ("Save", self.save_file), ("Save As...", self.save_as),
        ]:
            file_menu.add_command(label=label, command=command)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.close)
        menu.add_cascade(label="File", menu=file_menu)

        tools_menu = tk.Menu(menu, tearoff=False)
        tools_menu.add_command(label="Analyze All", command=self.analyze_all)
        tools_menu.add_command(label="Lexical Analysis", command=self.analyze_lexical)
        tools_menu.add_command(label="Syntax Analysis", command=self.analyze_syntax)
        tools_menu.add_command(label="Clear Results", command=self.clear_results)
        tools_menu.add_separator()
        tools_menu.add_command(label="Run Code", command=self.run_code)
        menu.add_cascade(label="Tools", menu=tools_menu)
        self.config(menu=menu)

        self.bind_all("<Control-n>", lambda event: self.new_file())
        self.bind_all("<Control-o>", lambda event: self.open_file())
        self.bind_all("<Control-s>", lambda event: self.save_file())
        self.bind_all("<F5>", lambda event: self.run_code())
        self.bind_all("<F6>", lambda event: self.analyze_all())

    def _toolbar(self):
        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")
        buttons = [
            ("New", self.new_file), ("Open", self.open_file),
            ("Save", self.save_file), ("▶ Run", self.run_code),
            ("Analyze All", self.analyze_all),
            ("Lexical", self.analyze_lexical), ("Syntax", self.analyze_syntax),
            ("Clear Results", self.clear_results),
            ("A+", lambda: self.zoom(1)), ("A-", lambda: self.zoom(-1)),
            ("Toggle Theme", self.toggle_theme),
        ]
        for label, action in buttons:
            ttk.Button(bar, text=label, command=action).pack(side="left", padx=2)

    def _workspace(self):
        panes = ttk.Panedwindow(self, orient="vertical")
        panes.pack(fill="both", expand=True, padx=6, pady=5)
        self.editor = CodeEditor(panes, self.mark_dirty)
        panes.add(self.editor, weight=4)

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
        text = tk.Text(frame, wrap="none", font=("Consolas", 10), height=8)
        ybar = ttk.Scrollbar(frame, command=text.yview)
        xbar = ttk.Scrollbar(frame, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        text.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        frame.rowconfigure(0, weight=1)
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

    def mark_dirty(self):
        self.dirty = True
        self._title()
        if self.diagnostics:
            self._set_diagnostics([])
            self.error_summary.configure(text="Source changed. Run Analyze All to refresh diagnostics.")
        self.editor.clear_diagnostic()

    def _title(self):
        name = self.current_path.name if self.current_path else "Untitled"
        self.title(f"{'*' if self.dirty else ''}{name} — PyLex Studio 1.1.1")

    def _confirm(self):
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel(
            "Unsaved Changes", "Save changes before continuing?"
        )
        if answer is None:
            return False
        return self.save_file() if answer else True

    def new_file(self):
        if self._confirm():
            self.editor.set_content("")
            self.current_path = None
            self.dirty = False
            self.clear_results()
            self._title()

    def open_file(self):
        if not self._confirm():
            return
        path = filedialog.askopenfilename(
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )
        if path:
            try:
                self.editor.set_content(Path(path).read_text(encoding="utf-8"))
                self.current_path = Path(path)
                self.dirty = False
                self.clear_results()
                self._title()
                self.status.configure(text="File opened.")
            except (OSError, UnicodeError) as exc:
                messagebox.showerror("Open Error", str(exc))

    def save_file(self):
        if self.current_path is None:
            return self.save_as()
        try:
            self.current_path.write_text(self.editor.get_content(), encoding="utf-8")
            self.dirty = False
            self._title()
            self.status.configure(text="File saved.")
            return True
        except OSError as exc:
            messagebox.showerror("Save Error", str(exc))
            return False

    def save_as(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".py",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )
        if not path:
            return False
        self.current_path = Path(path)
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
        stdout, stderr, exit_code = run_source(self.editor.get_content())
        report = stdout
        if stderr:
            report += ("\n" if report else "") + "Errors:\n" + stderr
        report += f"\n\nExit code: {exit_code}"
        self._show(self.output, report)
        self.status.configure(text=f"Execution finished — exit code {exit_code}.")

    def zoom(self, delta):
        self.editor.set_font_size(self.editor.font_size + delta)
        self.status.configure(text=f"Editor font size: {self.editor.font_size}")

    def toggle_theme(self):
        self.dark = not self.dark
        self._theme()

    def _theme(self):
        bg, fg = ("#1e1e1e", "#dddddd") if self.dark else ("#ffffff", "#202020")
        self.editor.set_theme(self.dark)
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
        if self._confirm():
            self.destroy()
