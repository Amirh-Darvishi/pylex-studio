"""Tkinter code editor with Pygments-based Python syntax highlighting."""
import tkinter as tk
from tkinter import font as tkfont

from pygments import lex
from pygments.lexers import PythonLexer
from pygments.token import Comment, Error, Keyword, Name, Number, Operator, Punctuation, String


class CodeEditor(tk.Frame):
    """A text editor with line numbers, configurable font size, and syntax highlighting."""

    def __init__(self, master, on_change=None):
        super().__init__(master)
        self.on_change = on_change
        self.font_size = 12
        self.editor_font = tkfont.Font(family="Consolas", size=self.font_size)
        self._highlight_job = None
        self.gutter = tk.Text(self, width=5, padx=5, takefocus=0, state="disabled",
                              font=self.editor_font, wrap="none", borderwidth=0)
        self.text = tk.Text(self, undo=True, wrap="none", font=self.editor_font,
                            padx=8, pady=8, borderwidth=0, tabs=("4c",))
        self.sy = tk.Scrollbar(self, orient="vertical", command=self._scroll)
        self.sx = tk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=self._yscroll, xscrollcommand=self.sx.set)
        self.gutter.pack(side="left", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.sy.pack(side="right", fill="y")
        self.sx.pack(side="bottom", fill="x")
        self.text.bind("<<Modified>>", self._changed)
        self.text.bind("<KeyRelease>", self._schedule_highlight)
        self.text.bind("<Tab>", self._tab)
        self.text.bind("<Control-a>", self._select_all)
        self._configure_tags()
        self.text.edit_modified(False)
        self.refresh_lines()

    def _configure_tags(self):
        """Define semantic tags for Pygments token categories."""
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

    def set_theme(self, dark=True):
        """Apply editor and gutter colors for the selected theme."""
        if dark:
            bg, fg, gutter_bg, gutter_fg = "#1e1e1e", "#dddddd", "#252526", "#858585"
        else:
            bg, fg, gutter_bg, gutter_fg = "#ffffff", "#202020", "#eeeeee", "#666666"
        self.text.configure(bg=bg, fg=fg, insertbackground=fg)
        self.gutter.configure(bg=gutter_bg, fg=gutter_fg)
        self.text.tag_configure("py_operator", foreground=fg)

    def _changed(self, event=None):
        if self.text.edit_modified():
            self.text.edit_modified(False)
            self.refresh_lines()
            self._schedule_highlight()
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

    def refresh_lines(self):
        count = int(self.text.index("end-1c").split(".")[0])
        self.gutter.configure(state="normal")
        self.gutter.delete("1.0", "end")
        self.gutter.insert("1.0", "\n".join(map(str, range(1, count + 1))))
        self.gutter.configure(state="disabled")

    def get_content(self):
        return self.text.get("1.0", "end-1c")

    def set_content(self, value):
        self.text.delete("1.0", "end")
        self.text.insert("1.0", value)
        self.text.edit_modified(False)
        self.refresh_lines()
        self.highlight()

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
        """Lex the current buffer with Pygments and apply token tags."""
        self._highlight_job = None
        source = self.get_content()
        tags = ("py_keyword", "py_builtin", "py_string", "py_comment",
                "py_number", "py_function", "py_class", "py_operator", "py_error")
        for tag in tags:
            self.text.tag_remove(tag, "1.0", "end")
        offset = 0
        for token_type, value in lex(source, PythonLexer()):
            tag = self._tag_for_token(token_type)
            if tag and value:
                self.text.tag_add(tag, f"1.0+{offset}c", f"1.0+{offset + len(value)}c")
            offset += len(value)

    def set_font_size(self, size):
        self.font_size = max(7, min(40, size))
        self.editor_font.configure(size=self.font_size)
