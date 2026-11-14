"""رابط گرافیکی اصلی PyLex Studio."""
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path
from .editor import CodeEditor
from .analyzer import lexical_analysis, syntax_analysis, format_tokens
from .runner import run_source

class PyLexApp(tk.Tk):
    """پنجره اصلی و هماهنگ‌کننده ابزارهای برنامه."""

    def __init__(self):
        """منوها، نوار ابزار، ویرایشگر و پنل تحلیل را می‌سازد."""
        super().__init__()
        self.title("PyLex Studio — Python IDE")
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
        """این متد عملیات  menu را انجام می‌دهد."""
        menu = tk.Menu(self)
        fm = tk.Menu(menu, tearoff=False)
        for label, cmd in [("فایل جدید", self.new_file), ("باز کردن", self.open_file),
                           ("ذخیره", self.save_file), ("ذخیره با نام", self.save_as)]:
            fm.add_command(label=label, command=cmd)
        fm.add_separator()
        fm.add_command(label="خروج", command=self.close)
        menu.add_cascade(label="فایل", menu=fm)
        am = tk.Menu(menu, tearoff=False)
        am.add_command(label="تحلیل لغوی", command=self.analyze_lexical)
        am.add_command(label="تحلیل نحوی", command=self.analyze_syntax)
        am.add_command(label="اجرای کد", command=self.run_code)
        menu.add_cascade(label="تحلیل و اجرا", menu=am)
        self.config(menu=menu)
        self.bind_all("<Control-n>", lambda e: self.new_file())
        self.bind_all("<Control-o>", lambda e: self.open_file())
        self.bind_all("<Control-s>", lambda e: self.save_file())
        self.bind_all("<F5>", lambda e: self.run_code())

    def _toolbar(self):
        """این متد عملیات  toolbar را انجام می‌دهد."""
        bar = ttk.Frame(self, padding=6)
        bar.pack(fill="x")
        buttons = [("جدید", self.new_file), ("باز کردن", self.open_file),
                   ("ذخیره", self.save_file), ("▶ اجرا", self.run_code),
                   ("تحلیل لغوی", self.analyze_lexical), ("تحلیل نحوی", self.analyze_syntax),
                   ("A+", lambda: self.zoom(1)), ("A-", lambda: self.zoom(-1)),
                   ("تم روشن/تاریک", self.toggle_theme)]
        for label, action in buttons:
            ttk.Button(bar, text=label, command=action).pack(side="left", padx=2)

    def _workspace(self):
        """این متد عملیات  workspace را انجام می‌دهد."""
        panes = ttk.Panedwindow(self, orient="vertical")
        panes.pack(fill="both", expand=True, padx=6, pady=5)
        self.editor = CodeEditor(panes, self.mark_dirty)
        panes.add(self.editor, weight=4)
        lower = ttk.Frame(panes)
        panes.add(lower, weight=2)
        self.tabs = ttk.Notebook(lower)
        self.tabs.pack(fill="both", expand=True)
        self.output = self._panel("خروجی")
        self.lexical = self._panel("تحلیل لغوی")
        self.syntax = self._panel("تحلیل نحوی")
        self.status = ttk.Label(self, text="آماده", padding=5)
        self.status.pack(fill="x")

    def _panel(self, title):
        """این متد عملیات  panel را انجام می‌دهد."""
        frame = ttk.Frame(self.tabs)
        text = tk.Text(frame, wrap="none", font=("Consolas", 10))
        sb = ttk.Scrollbar(frame, command=text.yview)
        text.configure(yscrollcommand=sb.set)
        text.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tabs.add(frame, text=title)
        return text

    def _show(self, panel, content):
        """این متد عملیات  show را انجام می‌دهد."""
        panel.configure(state="normal")
        panel.delete("1.0", "end")
        panel.insert("1.0", content)
        panel.configure(state="disabled")
        self.tabs.select(panel.master)

    def mark_dirty(self):
        """این متد عملیات mark dirty را انجام می‌دهد."""
        self.dirty = True
        self._title()

    def _title(self):
        """این متد عملیات  title را انجام می‌دهد."""
        name = self.current_path.name if self.current_path else "بدون‌نام"
        self.title(f"{'*' if self.dirty else ''}{name} — PyLex Studio")

    def _confirm(self):
        """این متد عملیات  confirm را انجام می‌دهد."""
        if not self.dirty:
            return True
        answer = messagebox.askyesnocancel("ذخیره", "تغییرات ذخیره نشده‌اند. ذخیره شوند؟")
        if answer is None:
            return False
        return self.save_file() if answer else True

    def new_file(self):
        """سند جدید می‌سازد."""
        if self._confirm():
            self.editor.set_content("")
            self.current_path = None
            self.dirty = False
            self._title()

    def open_file(self):
        """فایل متنی یا پایتون را باز می‌کند."""
        if not self._confirm():
            return
        path = filedialog.askopenfilename(filetypes=[("Python", "*.py"), ("همه فایل‌ها", "*.*")])
        if path:
            try:
                self.editor.set_content(Path(path).read_text(encoding="utf-8"))
                self.current_path = Path(path)
                self.dirty = False
                self._title()
            except (OSError, UnicodeError) as exc:
                messagebox.showerror("خطا", str(exc))

    def save_file(self):
        """فایل جاری را با UTF-8 ذخیره می‌کند."""
        if self.current_path is None:
            return self.save_as()
        try:
            self.current_path.write_text(self.editor.get_content(), encoding="utf-8")
            self.dirty = False
            self._title()
            self.status.configure(text="فایل ذخیره شد.")
            return True
        except OSError as exc:
            messagebox.showerror("خطا در ذخیره", str(exc))
            return False

    def save_as(self):
        """مسیر جدیدی برای ذخیره سند انتخاب می‌کند."""
        path = filedialog.asksaveasfilename(defaultextension=".py",
            filetypes=[("Python", "*.py"), ("همه فایل‌ها", "*.*")])
        if not path:
            return False
        self.current_path = Path(path)
        return self.save_file()

    def analyze_lexical(self):
        """تحلیل لغوی مستقل را اجرا می‌کند."""
        try:
            tokens = lexical_analysis(self.editor.get_content())
            self._show(self.lexical, format_tokens(tokens))
            self.status.configure(text=f"تعداد توکن‌ها: {len(tokens)}")
        except Exception as exc:
            self._show(self.lexical, f"خطا در تحلیل لغوی:\n{exc}")

    def analyze_syntax(self):
        """تحلیل نحوی مستقل را اجرا و خطا را گزارش می‌کند."""
        result = syntax_analysis(self.editor.get_content())
        text = result.message + "\n" + result.details
        if result.line:
            text += f"\nخط: {result.line} | ستون: {result.column}"
        self._show(self.syntax, text)
        self.status.configure(text="تحلیل نحوی موفق" if result.success else "خطای نحوی")

    def run_code(self):
        """کد را اجرا و خروجی و خطا را نمایش می‌دهد."""
        out, err, code = run_source(self.editor.get_content())
        text = out + (("\nخطا:\n" + err) if err else "")
        text += f"\n\nکد خروج: {code}"
        self._show(self.output, text)
        self.status.configure(text=f"پایان اجرا؛ کد خروج {code}")

    def zoom(self, delta):
        """اندازه قلم را کم یا زیاد می‌کند."""
        self.editor.set_font_size(self.editor.font_size + delta)
        self.status.configure(text=f"اندازه قلم: {self.editor.font_size}")

    def toggle_theme(self):
        """تم روشن و تاریک را جابه‌جا می‌کند."""
        self.dark = not self.dark
        self._theme()

    def _theme(self):
        """رنگ پس‌زمینه و متن ویرایشگر و پنل‌ها را تنظیم می‌کند."""
        bg, fg = ("#1e1e1e", "#dddddd") if self.dark else ("#ffffff", "#202020")
        self.editor.text.configure(bg=bg, fg=fg, insertbackground=fg)
        self.editor.gutter.configure(bg="#252526" if self.dark else "#eeeeee", fg="#888888")
        for panel in (self.output, self.lexical, self.syntax):
            panel.configure(bg=bg, fg=fg, insertbackground=fg)

    def close(self):
        """با بررسی تغییرات ذخیره‌نشده برنامه را می‌بندد."""
        if self._confirm():
            self.destroy()
