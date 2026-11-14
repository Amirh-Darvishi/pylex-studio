"""Main graphical interface for PyLex Studio."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path

from .editor import CodeEditor
from .analyzer import lexical_analysis, syntax_analysis, format_tokens
from .runner import run_source


class PyLexApp(tk.Tk):
    """Main application window and coordinator for editor tools."""

    def __init__(self):
        super().__init__()
        self.title("PyLex Studio — Python Editor")
        self.geometry("1120x740")
        self.current_path = None
        self.dirty = False
        self.dark = True
        self._menu()
        self._toolbar()
        self._workspace()
        self._theme()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self._title()

    def _menu(self):
        menu = tk.Menu(self)
        file_menu = tk.Menu(menu, tearoff=False)
        for label, command in [("New", self.new_file), ("Open...", self.open_file),
                               ("Save", self.save_file), ("Save As...", self.save_as)]:
            file_menu.add_command(label=label, command=command)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.close)
        menu.add_cascade(label="File", menu=file_menu)

        tools_menu = tk.Menu(menu, tearoff=False)
        tools_menu.add_command(label="Lexical Analysis", command=self.analyze_lexical)
        tools_menu.add_command(label="Syntax Analysis", command=self.analyze_syntax)
        tools_menu.add_command(label="Run Code", command=self.run_code)
        menu.add_cascade(label="Tools", menu=tools_menu)
        self.config(menu=menu)

        self.bind_all("<Control-n>", lambda event: self.new_file())
        self.bind_all("<Control-o>", lambda event: self.open_file())
        self.bind_all("<Control-s>", lambda event: self.save_file())
        self.bind_all("<F5>", lambda event: self.run_code())

    def _toolbar(self):
        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")
        buttons = [
            ("New", self.new_file), ("Open", self.open_file),
            ("Save", self.save_file), ("▶ Run", self.run_code),
            ("Lexical Analysis", self.analyze_lexical),
            ("Syntax Analysis", self.analyze_syntax),
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
        self.output = self._panel("Output")
        self.lexical = self._panel("Lexical Analysis")
        self.syntax = self._panel("Syntax Analysis")
        self.status = ttk.Label(self, text="Ready", padding=5)
        self.status.pack(fill="x")

    def _panel(self, title):
        frame = ttk.Frame(self.tabs)
        text = tk.Text(frame, wrap="none", font=("Consolas", 10))
        scrollbar = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=scrollbar.set)
        text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.tabs.add(frame, text=title)
        return text

    def _show(self, panel, content):
        panel.configure(state="normal")
        panel.delete("1.0", "end")
        panel.insert("1.0", content)
        panel.configure(state="disabled")
        self.tabs.select(panel.master)

    def mark_dirty(self):
        self.dirty = True
        self._title()

    def _title(self):
        name = self.current_path.name if self.current_path else "Untitled"
        self.title(f"{'*' if self.dirty else ''}{name} — PyLex Studio")

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
        try:
            tokens = lexical_analysis(self.editor.get_content())
            self._show(self.lexical, format_tokens(tokens))
            self.status.configure(text=f"Lexical analysis complete — {len(tokens)} tokens.")
        except Exception as exc:
            self._show(self.lexical, f"Lexical analysis error: {exc}")
            self.status.configure(text="Lexical analysis failed.")

    def analyze_syntax(self):
        result = syntax_analysis(self.editor.get_content())
        report = f"{result.message}\n{result.details}"
        if result.line is not None:
            report += f"\nLine: {result.line} | Column: {result.column}"
        self._show(self.syntax, report)
        self.status.configure(
            text="Syntax analysis successful." if result.success else "Syntax error detected."
        )

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

    def close(self):
        if self._confirm():
            self.destroy()
