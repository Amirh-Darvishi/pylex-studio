"""ویرایشگر کد با شماره خطوط، قلم و رنگ‌بندی پایه."""
import tkinter as tk
from tkinter import font as tkfont
import keyword
import re

class CodeEditor(tk.Frame):
    """کامپوننت ویرایش متن پایتون."""

    def __init__(self, master, on_change=None):
        """اجزای ویرایشگر و رویدادهای صفحه‌کلید را می‌سازد."""
        super().__init__(master)
        self.on_change = on_change
        self.font_size = 12
        self.editor_font = tkfont.Font(family="Consolas", size=12)
        self.gutter = tk.Text(self, width=5, padx=5, takefocus=0, state="disabled", font=self.editor_font)
        self.text = tk.Text(self, undo=True, wrap="none", font=self.editor_font, padx=8, pady=8)
        self.sy = tk.Scrollbar(self, orient="vertical", command=self._scroll)
        self.sx = tk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=self._yscroll, xscrollcommand=self.sx.set)
        self.gutter.pack(side="left", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        self.sy.pack(side="right", fill="y")
        self.sx.pack(side="bottom", fill="x")
        self.text.bind("<<Modified>>", self._changed)
        self.text.bind("<KeyRelease>", self.highlight)
        self.text.bind("<Tab>", self._tab)
        self.text.bind("<Control-a>", self._select_all)
        self._tags()
        self.text.edit_modified(False)
        self.refresh_lines()

    def _tags(self):
        """رنگ‌های پایه توکن‌ها را تعریف می‌کند."""
        self.text.tag_configure("keyword", foreground="#c586c0")
        self.text.tag_configure("string", foreground="#ce9178")
        self.text.tag_configure("comment", foreground="#6a9955")
        self.text.tag_configure("number", foreground="#b5cea8")

    def _changed(self, event=None):
        """این متد عملیات  changed را انجام می‌دهد."""
        if self.text.edit_modified():
            self.text.edit_modified(False)
            self.refresh_lines()
            if self.on_change:
                self.on_change()

    def _scroll(self, *args):
        """این متد عملیات  scroll را انجام می‌دهد."""
        self.text.yview(*args)
        self.gutter.yview(*args)

    def _yscroll(self, first, last):
        """این متد عملیات  yscroll را انجام می‌دهد."""
        self.sy.set(first, last)
        self.gutter.yview_moveto(first)

    def _tab(self, event=None):
        """این متد عملیات  tab را انجام می‌دهد."""
        self.text.insert("insert", "    ")
        return "break"

    def _select_all(self, event=None):
        """این متد عملیات  select all را انجام می‌دهد."""
        self.text.tag_add("sel", "1.0", "end-1c")
        return "break"

    def refresh_lines(self):
        """شماره خطوط را تازه‌سازی می‌کند."""
        count = int(self.text.index("end-1c").split(".")[0])
        self.gutter.configure(state="normal")
        self.gutter.delete("1.0", "end")
        self.gutter.insert("1.0", "\\n".join(map(str, range(1, count + 1))))
        self.gutter.configure(state="disabled")

    def get_content(self):
        """متن کامل ویرایشگر را می‌دهد."""
        return self.text.get("1.0", "end-1c")

    def set_content(self, value):
        """متن ویرایشگر را جایگزین می‌کند."""
        self.text.delete("1.0", "end")
        self.text.insert("1.0", value)
        self.text.edit_modified(False)
        self.refresh_lines()
        self.highlight()

    def highlight(self, event=None):
        """کلمات کلیدی، رشته‌ها، اعداد و کامنت‌ها را رنگی می‌کند."""
        source = self.get_content()
        for tag in ("keyword", "string", "comment", "number"):
            self.text.tag_remove(tag, "1.0", "end")
        patterns = {
            "comment": r"#[^\\n]*",
            "string": r'"[^"\\n]*"|\\x27[^\\x27\\n]*\\x27',
            "number": r"\\b\\d+(?:\\.\\d+)?\\b",
        }
        for tag, pattern in patterns.items():
            for m in re.finditer(pattern, source):
                self.text.tag_add(tag, f"1.0+{m.start()}c", f"1.0+{m.end()}c")
        for word in keyword.kwlist:
            for m in re.finditer(r"\\b" + re.escape(word) + r"\\b", source):
                self.text.tag_add("keyword", f"1.0+{m.start()}c", f"1.0+{m.end()}c")

    def set_font_size(self, size):
        """اندازه قلم را در محدوده قابل‌قبول تنظیم می‌کند."""
        self.font_size = max(7, min(40, size))
        self.editor_font.configure(size=self.font_size)
