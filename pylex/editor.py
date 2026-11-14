"""Tkinter code editor with Pygments highlighting and diagnostic navigation."""
import builtins
import keyword
import tkinter as tk
from tkinter import font as tkfont

from pygments import lex
from pygments.lexers import PythonLexer
from pygments.token import (
    Comment, Error, Keyword, Name, Number, Operator, Punctuation, String,
)


class CodeEditor(tk.Frame):
    """Text editor with line numbers, current-line emphasis, and error markers."""

    def __init__(self, master, on_change=None):
        super().__init__(master)
        self.on_change = on_change
        self.font_size = 12
        self.editor_font = tkfont.Font(family="Consolas", size=self.font_size)
        self._highlight_job = None
        self._diagnostic_location = None
        self._completion_window = None
        self._completion_list = None
        self._breakpoints = set()

        self.gutter = tk.Text(
            self, width=5, padx=5, takefocus=0, state="disabled",
            font=self.editor_font, wrap="none", borderwidth=0,
            cursor="arrow", highlightthickness=0,
        )
        self.text = tk.Text(
            self, undo=True, wrap="none", font=self.editor_font,
            padx=8, pady=8, borderwidth=0, tabs=("4c"),
            highlightthickness=0,
        )
        self.sy = tk.Scrollbar(self, orient="vertical", command=self._scroll)
        self.sx = tk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=self._yscroll, xscrollcommand=self.sx.set)
        self.gutter.pack(side="left", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.sy.pack(side="right", fill="y")
        self.sx.pack(side="bottom", fill="x")

        self.text.bind("<<Modified>>", self._changed)
        self.text.bind("<KeyRelease>", self._cursor_changed)
        self.text.bind("<ButtonRelease-1>", self._cursor_changed)
        self.text.bind("<MouseWheel>", self._cursor_changed, add="+")
        self.text.bind("<Tab>", self._tab)
        self.text.bind("<KeyPress>", self._auto_pair, add="+")
        self.text.bind("<Control-space>", self.show_completions)
        self.text.bind("<Control-a>", self._select_all)
        self._configure_tags()
        self.text.edit_modified(False)
        self.refresh_lines()
        self.update_current_line()

    def _configure_tags(self):
        styles = {
            "py_keyword": "#c586c0", "py_builtin": "#4ec9b0",
            "py_string": "#ce9178", "py_comment": "#6a9955",
            "py_number": "#b5cea8", "py_function": "#dcdcaa",
            "py_class": "#4ec9b0", "py_error": "#f44747",
        }
        for name, color in styles.items():
            self.text.tag_configure(name, foreground=color)
        self.text.tag_configure("py_comment", font=self.editor_font)
        self.text.tag_configure("py_error", underline=True)
        self.text.tag_configure("current_line", background="#2a2d2e")
        self.text.tag_configure("error_line", background="#4b2528", underline=True)
        self.gutter.tag_configure("gutter_current", foreground="#ffffff")
        self.gutter.tag_configure("gutter_error", foreground="#ff7777")

    def set_theme(self, dark=True):
        if dark:
            bg, fg, gutter_bg, gutter_fg = "#1e1e1e", "#dddddd", "#252526", "#858585"
            current_bg, error_bg = "#2a2d2e", "#4b2528"
        else:
            bg, fg, gutter_bg, gutter_fg = "#ffffff", "#202020", "#eeeeee", "#666666"
            current_bg, error_bg = "#eef4ff", "#ffe8e8"
        self.text.configure(bg=bg, fg=fg, insertbackground=fg)
        self.gutter.configure(bg=gutter_bg, fg=gutter_fg)
        self.text.tag_configure("py_operator", foreground=fg)
        self.text.tag_configure("current_line", background=current_bg)
        self.text.tag_configure("error_line", background=error_bg)

    def _changed(self, event=None):
        if self.text.edit_modified():
            self.text.edit_modified(False)
            self.refresh_lines()
            self._schedule_highlight()
            self.update_current_line()
            if self.on_change:
                self.on_change()

    def _scroll(self, *args):
        self.text.yview(*args)
        self.gutter.yview(*args)

    def _yscroll(self, first, last):
        self.sy.set(first, last)
        self.gutter.yview_moveto(first)

    def _tab(self, event=None):
        self.text.insert("insert", "    ")
        return "break"

    def _select_all(self, event=None):
        self.text.tag_add("sel", "1.0", "end-1c")
        return "break"

    def _auto_pair(self, event):
        """Insert matching brackets and quotes, or skip an existing closer."""
        char = event.char
        pairs = {"(": ")", "[": "]", "{": "}", '"': '"', "'": "'"}
        if char in {")", "]", "}"} or char in {"'", '"'}:
            if self.text.get("insert") == char:
                self.text.mark_set("insert", "insert+1c")
                return "break"
            if char not in pairs:
                return None
        if char not in pairs:
            return None
        if char in {"'", '"'} and self.text.get("insert-1c", "insert") == "\\":
            return None

        try:
            selected = self.text.get("sel.first", "sel.last")
            start = self.text.index("sel.first")
            self.text.delete("sel.first", "sel.last")
        except tk.TclError:
            selected = ""
            start = self.text.index("insert")

        self.text.insert(start, char + selected + pairs[char])
        # Place the caret immediately after the opening character, before
        # the selected text (if any) and its closing delimiter.
        self.text.mark_set("insert", f"{start}+1c")
        return "break"

    def show_completions(self, event=None):
        """Show lightweight keyword and built-in completion suggestions."""
        prefix_start = self.text.index("insert wordstart")
        prefix = self.text.get(prefix_start, "insert")
        if not prefix:
            return "break"
        candidates = sorted(set(keyword.kwlist) | set(dir(builtins)))
        matches = [item for item in candidates if item.startswith(prefix) and item != prefix]
        if not matches:
            self._hide_completions()
            return "break"

        self._hide_completions()
        self._completion_start = prefix_start
        self._completion_end = self.text.index("insert")
        self._completion_window = tk.Toplevel(self)
        self._completion_window.wm_overrideredirect(True)
        self._completion_list = tk.Listbox(
            self._completion_window, height=min(8, len(matches)), exportselection=False,
        )
        self._completion_list.pack()
        for item in matches[:100]:
            self._completion_list.insert("end", item)
        bbox = self.text.bbox("insert")
        if bbox:
            x, y, _, height = bbox
            geometry = "+{}+{}".format(
                self.text.winfo_rootx() + x,
                self.text.winfo_rooty() + y + height,
            )
            self._completion_window.geometry(geometry)
        self._completion_list.selection_set(0)
        self._completion_list.bind("<Return>", self._apply_completion)
        self._completion_list.bind("<Double-Button-1>", self._apply_completion)
        self._completion_list.bind("<Escape>", self._cancel_completions)
        self._completion_list.bind("<Up>", self._completion_move)
        self._completion_list.bind("<Down>", self._completion_move)
        self._completion_list.focus_set()
        return "break"

    def _completion_move(self, event):
        """Keep keyboard navigation inside the completion list."""
        if self._completion_list is not None:
            size = self._completion_list.size()
            if size:
                current = self._completion_list.curselection()
                index = current[0] if current else 0
                index = max(0, min(size - 1, index + (1 if event.keysym == "Down" else -1)))
                self._completion_list.selection_clear(0, "end")
                self._completion_list.selection_set(index)
                self._completion_list.activate(index)
                self._completion_list.see(index)
        return "break"

    def _cancel_completions(self, event=None):
        self._hide_completions()
        self.text.focus_set()
        return "break"

    def _apply_completion(self, event=None):
        if self._completion_list is None:
            return "break"
        selection = self._completion_list.curselection()
        if selection:
            value = self._completion_list.get(selection[0])
            self.text.delete(self._completion_start, self._completion_end)
            self.text.insert(self._completion_start, value)
            self.text.mark_set("insert", f"{self._completion_start}+{len(value)}c")
        self._hide_completions()
        self.text.focus_set()
        return "break"

    def _hide_completions(self):
        if self._completion_window is not None:
            self._completion_window.destroy()
        self._completion_window = None
        self._completion_list = None

    def refresh_lines(self):
        count = max(1, int(self.text.index("end-1c").split(".")[0]))
        current = int(self.text.index("insert").split(".")[0])
        self.gutter.configure(state="normal")
        self.gutter.delete("1.0", "end")
        self.gutter.insert("1.0", "\n".join(("● " if i in self._breakpoints else "  ") + str(i) for i in range(1, count + 1)))
        self.gutter.tag_remove("gutter_current", "1.0", "end")
        self.gutter.tag_remove("gutter_error", "1.0", "end")
        self.gutter.tag_add("gutter_current", f"{current}.0", f"{current}.end")
        if self._diagnostic_location:
            line = self._diagnostic_location[0]
            if 1 <= line <= count:
                self.gutter.tag_add("gutter_error", f"{line}.0", f"{line}.end")
        self.gutter.configure(state="disabled")

    def set_breakpoints(self, lines):
        """Display breakpoint markers beside the corresponding line numbers."""
        self._breakpoints = {int(line) for line in lines if int(line) > 0}
        self.refresh_lines()

    def update_current_line(self, event=None):
        self.text.tag_remove("current_line", "1.0", "end")
        line = self.text.index("insert").split(".")[0]
        self.text.tag_add("current_line", f"{line}.0", f"{line}.0 lineend+1c")
        self.text.tag_raise("sel")
        self.text.tag_raise("error_line")
        self.refresh_gutter_marks()

    def refresh_gutter_marks(self):
        current = int(self.text.index("insert").split(".")[0])
        self.gutter.configure(state="normal")
        self.gutter.tag_remove("gutter_current", "1.0", "end")
        self.gutter.tag_remove("gutter_error", "1.0", "end")
        self.gutter.tag_add("gutter_current", f"{current}.0", f"{current}.end")
        if self._diagnostic_location:
            line = self._diagnostic_location[0]
            try:
                self.gutter.tag_add("gutter_error", f"{line}.0", f"{line}.end")
            except tk.TclError:
                pass
        self.gutter.configure(state="disabled")

    def _cursor_changed(self, event=None):
        self.update_current_line()

    def get_content(self):
        return self.text.get("1.0", "end-1c")

    def set_content(self, value):
        self.clear_diagnostic()
        self.text.delete("1.0", "end")
        self.text.insert("1.0", value)
        self.text.edit_modified(False)
        self.refresh_lines()
        self.highlight()
        self.update_current_line()

    @staticmethod
    def _tag_for_token(token_type):
        if token_type in Keyword:
            return "py_keyword"
        if token_type in Comment:
            return "py_comment"
        if token_type in String:
            return "py_string"
        if token_type in Number:
            return "py_number"
        if token_type in Error:
            return "py_error"
        if token_type in Name.Function:
            return "py_function"
        if token_type in Name.Class:
            return "py_class"
        if token_type in Name.Builtin:
            return "py_builtin"
        if token_type in Operator or token_type in Punctuation:
            return "py_operator"
        return None

    def _schedule_highlight(self, event=None):
        if self._highlight_job is not None:
            self.after_cancel(self._highlight_job)
        self._highlight_job = self.after(120, self.highlight)

    def highlight(self, event=None):
        """Apply Pygments token tags to the current editor content."""
        self._highlight_job = None
        source = self.get_content()
        tags = (
            "py_keyword", "py_builtin", "py_string", "py_comment",
            "py_number", "py_function", "py_class", "py_operator", "py_error",
        )
        for tag in tags:
            self.text.tag_remove(tag, "1.0", "end")
        offset = 0
        for token_type, value in lex(source, PythonLexer()):
            tag = self._tag_for_token(token_type)
            if tag and value:
                self.text.tag_add(tag, f"1.0+{offset}c", f"1.0+{offset + len(value)}c")
            offset += len(value)
        self.text.tag_raise("error_line")
        self.text.tag_raise("sel")

    def show_diagnostic(self, line, column=0, end_line=None, end_column=None):
        """Highlight an error span and move the insertion cursor to its location."""
        self.clear_diagnostic()
        self._diagnostic_location = (max(1, int(line)), max(0, int(column)))
        start = f"{self._diagnostic_location[0]}.{self._diagnostic_location[1]}"
        try:
            self.text.index(start)
        except tk.TclError:
            start = f"{self._diagnostic_location[0]}.0"
        line_number = self._diagnostic_location[0]
        self.text.tag_add("error_line", f"{line_number}.0", f"{line_number}.end+1c")
        if end_line == line_number and end_column is not None and end_column > self._diagnostic_location[1]:
            self.text.tag_add("py_error", start, f"{line_number}.{end_column}")
        self.text.mark_set("insert", start)
        self.text.see(start)
        self.text.focus_set()
        self.update_current_line()
        self.text.tag_raise("error_line")
        self.text.tag_raise("sel")

    def clear_diagnostic(self):
        self._diagnostic_location = None
        self.text.tag_remove("error_line", "1.0", "end")
        self.text.tag_remove("py_error", "1.0", "end")
        self.refresh_gutter_marks()

    def set_font_size(self, size):
        self.font_size = max(7, min(40, size))
        self.editor_font.configure(size=self.font_size)
