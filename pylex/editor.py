"""Tkinter code editor with Pygments highlighting and diagnostic navigation."""

import builtins
import keyword
import tkinter as tk
from tkinter import font as tkfont

from pygments import lex
from pygments.lexers import PythonLexer
from pygments.token import (
    Comment,
    Error,
    Keyword,
    Name,
    Number,
    Operator,
    Punctuation,
    String,
)

from .ui.context_menu import ContextMenu

from .editor_features import (
    find_matching_bracket,
    indentation_for_newline,
    smart_backspace_prefix,
    toggle_comment_block,
)


class CodeEditor(tk.Frame):
    """Text editor with line numbers, current-line emphasis, and error markers."""

    def __init__(self, master, on_change=None, on_cursor_change=None):
        super().__init__(master)
        self.on_change = on_change
        self.on_cursor_change = on_cursor_change
        self.font_size = 12
        self.indent_string = "    "
        self.editor_font = tkfont.Font(family="Consolas", size=self.font_size)
        self._highlight_job = None
        self._diagnostic_location = None
        self._completion_window = None
        self._completion_list = None
        self._breakpoints = set()

        self.gutter = tk.Text(
            self,
            width=5,
            padx=5,
            takefocus=0,
            state="disabled",
            font=self.editor_font,
            wrap="none",
            borderwidth=0,
            cursor="arrow",
            highlightthickness=0,
            pady=8,
        )
        self.text = tk.Text(
            self,
            undo=True,
            wrap="none",
            font=self.editor_font,
            padx=8,
            pady=8,
            borderwidth=0,
            tabs=("4c"),
            highlightthickness=0,
        )
        # The gutter and source must share identical vertical text metrics.
        for widget in (self.gutter, self.text):
            widget.configure(spacing1=0, spacing2=0, spacing3=0)
        self.sy = tk.Scrollbar(self, orient="vertical", command=self._scroll)
        self.sx = tk.Scrollbar(self, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=self._yscroll, xscrollcommand=self.sx.set)
        self.gutter.pack(side="left", fill="y")
        self.text.pack(side="left", fill="both", expand=True)
        # Keep native scrolling, but hide the visual bars for a cleaner editor.
        self.text.bind("<Shift-MouseWheel>", self._horizontal_wheel, add="+")
        self.text.bind("<Button-4>", lambda _event: self._wheel_units(-3), add="+")
        self.text.bind("<Button-5>", lambda _event: self._wheel_units(3), add="+")
        self.gutter.bind("<MouseWheel>", self._wheel_from_event, add="+")
        self.gutter.bind("<Button-4>", lambda _event: self._wheel_units(-3), add="+")
        self.gutter.bind("<Button-5>", lambda _event: self._wheel_units(3), add="+")

        self.text.bind("<<Modified>>", self._changed)
        self.text.bind("<KeyRelease>", self._cursor_changed)
        self.text.bind("<ButtonRelease-1>", self._cursor_changed)
        self.text.bind("<MouseWheel>", self._cursor_changed, add="+")
        self.text.bind("<Tab>", self._tab)
        self.text.bind("<Shift-Tab>", self._dedent)
        self.text.bind("<Return>", self._smart_newline)
        self.text.bind("<BackSpace>", self._smart_backspace)
        self.text.bind("<Control-slash>", self._toggle_comment)
        self.text.bind("<Control-d>", self._duplicate_line)
        self.text.bind("<Alt-Up>", lambda event: self._move_line(-1))
        self.text.bind("<Alt-Down>", lambda event: self._move_line(1))
        self.text.bind("<Control-g>", self._go_to_line)
        self.text.bind("<KeyPress>", self._auto_pair, add="+")
        self.text.bind("<Control-space>", self.show_completions)
        self.text.bind("<Control-a>", self._select_all)
        self.text.bind("<Button-3>", self._show_context_menu, add="+")
        self.text.bind("<Shift-F10>", self._show_context_menu, add="+")
        self._configure_tags()
        self.text.edit_modified(False)
        self.refresh_lines()
        self.update_current_line()

    def _configure_tags(self):
        styles = {
            "py_keyword": "#c586c0",
            "py_builtin": "#4ec9b0",
            "py_string": "#ce9178",
            "py_comment": "#6a9955",
            "py_number": "#b5cea8",
            "py_function": "#dcdcaa",
            "py_class": "#4ec9b0",
            "py_error": "#f44747",
        }
        for name, color in styles.items():
            self.text.tag_configure(name, foreground=color)
        self.text.tag_configure("py_comment", font=self.editor_font)
        self.text.tag_configure("py_error", underline=True)
        self.text.tag_configure("current_line", background="#2a2d2e")
        self.text.tag_configure("error_line", background="#4b2528", underline=True)
        self.text.tag_configure(
            "matching_bracket", background="#565b63", underline=True
        )
        self.gutter.tag_configure("gutter_current", foreground="#ffffff")
        self.gutter.tag_configure("gutter_error", foreground="#ff7777")

    def set_theme(self, dark=True, palette=None):
        """Apply the shared application palette to the editor and syntax tokens."""
        palette = palette or {}
        if dark:
            bg = palette.get("editor_bg", "#111827")
            fg = palette.get("editor_fg", "#e6edf7")
            gutter_bg = palette.get("panel_bg", "#161f2d")
            gutter_fg = palette.get("muted", "#91a0b7")
            current_bg = "#182438"
            error_bg = "#48252e"
            bracket_bg = "#344b70"
            syntax = {
                "py_keyword": "#c792ea",
                "py_builtin": "#82aaff",
                "py_string": "#c3e88d",
                "py_comment": "#7f8c9f",
                "py_number": "#f78c6c",
                "py_function": "#82aaff",
                "py_class": "#ffcb6b",
                "py_error": "#ff6b78",
            }
        else:
            bg = palette.get("editor_bg", "#ffffff")
            fg = palette.get("editor_fg", "#202938")
            gutter_bg = palette.get("panel_bg", "#edf2f9")
            gutter_fg = palette.get("muted", "#68778d")
            current_bg = "#f1f5fc"
            error_bg = "#ffe8e8"
            bracket_bg = "#d7e5ff"
            syntax = {
                "py_keyword": "#8e44ad",
                "py_builtin": "#087f8c",
                "py_string": "#21834a",
                "py_comment": "#788392",
                "py_number": "#b45309",
                "py_function": "#245fbe",
                "py_class": "#946200",
                "py_error": "#c62828",
            }
        self.text.configure(
            bg=bg,
            fg=fg,
            insertbackground=fg,
            selectbackground=palette.get("selection_bg", bracket_bg),
            selectforeground=fg,
        )
        self.gutter.configure(bg=gutter_bg, fg=gutter_fg)
        for tag, color in syntax.items():
            self.text.tag_configure(tag, foreground=color)
        self.text.tag_configure("py_comment", font=self.editor_font)
        self.text.tag_configure("py_error", underline=True)
        self.text.tag_configure("py_operator", foreground=fg)
        self.text.tag_configure("current_line", background=current_bg)
        self.text.tag_configure("error_line", background=error_bg)
        self.text.tag_configure("matching_bracket", background=bracket_bg)
        self.gutter.tag_configure(
            "gutter_current", foreground=palette.get("accent", fg)
        )
        self.gutter.tag_configure(
            "gutter_error", foreground=palette.get("danger", "#c62828")
        )

    def _changed(self, event=None):
        if self.text.edit_modified():
            self.text.edit_modified(False)
            self.refresh_lines()
            self._schedule_highlight()
            self.update_current_line()
            if self.on_cursor_change:
                self.on_cursor_change()
            if self.on_change:
                self.on_change()

    def _wheel_from_event(self, event):
        units = -int(event.delta / 120) * 3 if event.delta else 0
        return self._wheel_units(units)

    def _wheel_units(self, units):
        self.text.yview_scroll(units, "units")
        self.gutter.yview_scroll(units, "units")
        return "break"

    def _horizontal_wheel(self, event):
        units = -int(event.delta / 120) if event.delta else 0
        self.text.xview_scroll(units * 3, "units")
        return "break"

    def _scroll(self, *args):
        self.text.yview(*args)
        self.gutter.yview(*args)

    def _yscroll(self, first, last):
        self.sy.set(first, last)
        self.gutter.yview_moveto(first)

    def _tab(self, event=None):
        self.text.insert("insert", self.indent_string)
        return "break"

    def _smart_newline(self, event=None):
        """Continue indentation and add one level after a Python suite header."""
        prefix = self.text.get("insert linestart", "insert")
        indentation = indentation_for_newline(prefix)
        if prefix.rstrip().endswith(":") and indentation.endswith("    "):
            indentation = indentation[:-4] + self.indent_string
        self.text.insert("insert", "\n" + indentation)
        # Keep the insertion point visible and move the gutter in lockstep.
        self.text.see("insert")
        self.text.update_idletasks()
        first, last = self.text.yview()
        self.gutter.yview_moveto(first)
        self._cursor_changed()
        return "break"

    def _smart_backspace(self, event=None):
        """Delete indentation to the previous four-column stop."""
        prefix = self.text.get("insert linestart", "insert")
        replacement = smart_backspace_prefix(prefix)
        if replacement is None:
            return None
        self.text.delete("insert linestart", "insert")
        self.text.insert("insert", replacement)
        return "break"

    def _dedent(self, event=None):
        """Dedent selected lines, or the current line, by one level."""
        try:
            first = int(self.text.index("sel.first").split(".")[0])
            last_index = self.text.index("sel.last")
            last = int(last_index.split(".")[0])
            if last > first and last_index.endswith(".0"):
                last -= 1
        except tk.TclError:
            first = last = int(self.text.index("insert").split(".")[0])
        for line in range(first, last + 1):
            start = f"{line}.0"
            prefix = self.text.get(start, f"{line}.0+4c")
            if prefix.startswith("    "):
                self.text.delete(start, f"{line}.0+4c")
            elif prefix.startswith("\t"):
                self.text.delete(start, f"{line}.0+1c")
        return "break"

    def _toggle_comment(self, event=None):
        """Toggle comments for the selected block or current line."""
        try:
            first = int(self.text.index("sel.first").split(".")[0])
            last_index = self.text.index("sel.last")
            last = int(last_index.split(".")[0])
            if last > first and last_index.endswith(".0"):
                last -= 1
        except tk.TclError:
            first = last = int(self.text.index("insert").split(".")[0])
        start, end = f"{first}.0", f"{last}.end"
        replacement = toggle_comment_block(self.text.get(start, end))
        self.text.delete(start, end)
        self.text.insert(start, replacement)
        self.text.tag_remove("sel", "1.0", "end")
        self.text.tag_add("sel", start, f"{start}+{len(replacement)}c")
        return "break"

    def _duplicate_line(self, event=None):
        """Duplicate selected text or the current line."""
        try:
            start, end = self.text.index("sel.first"), self.text.index("sel.last")
            value = self.text.get(start, end)
            self.text.insert(end, value)
            self.text.tag_remove("sel", "1.0", "end")
            self.text.tag_add("sel", end, f"{end}+{len(value)}c")
        except tk.TclError:
            line = self.text.index("insert").split(".")[0]
            start, end = f"{line}.0", f"{line}.0 lineend+1c"
            self.text.insert(end, self.text.get(start, end))
        return "break"

    def _move_line(self, direction):
        """Move the current line one position while preserving its cursor column."""
        line = int(self.text.index("insert").split(".")[0])
        column = int(self.text.index("insert").split(".")[1])
        count = int(self.text.index("end-1c").split(".")[0])
        target = line + direction
        if target < 1 or target > count:
            return "break"
        if direction < 0:
            start, end = f"{target}.0", f"{line}.0"
            previous = self.text.get(start, end)
            current = self.text.get(end, f"{line}.0 lineend+1c")
            self.text.delete(start, f"{line}.0 lineend+1c")
            self.text.insert(start, current + previous)
        else:
            start, end = f"{line}.0", f"{target}.0"
            current = self.text.get(start, end)
            following = self.text.get(end, f"{target}.0 lineend+1c")
            self.text.delete(start, f"{target}.0 lineend+1c")
            self.text.insert(start, following + current)
        self.text.mark_set("insert", f"{target}.0+{column}c")
        self.text.see("insert")
        return "break"

    def _go_to_line(self, event=None):
        """Prompt for a line number and navigate to it."""
        from tkinter import simpledialog

        line = simpledialog.askinteger(
            "Go to Line",
            "Line number:",
            parent=self.winfo_toplevel(),
            initialvalue=int(self.text.index("insert").split(".")[0]),
            minvalue=1,
        )
        if line is not None:
            self.text.mark_set("insert", f"{line}.0")
            self.text.see("insert")
            self.text.focus_set()
            self.update_current_line()
        return "break"

    def _update_matching_bracket(self):
        self.text.tag_remove("matching_bracket", "1.0", "end")
        source = self.get_content()
        cursor_count = self.text.count("1.0", "insert", "chars")
        offset = cursor_count[0] if cursor_count else 0
        match = find_matching_bracket(source, offset)
        if match:
            for position in match:
                self.text.tag_add(
                    "matching_bracket", f"1.0+{position}c", f"1.0+{position + 1}c"
                )
            self.text.tag_raise("matching_bracket")
            self.text.tag_raise("sel")

    def _safe_edit_history(self, action):
        try:
            self.text.edit_undo() if action == "undo" else self.text.edit_redo()
        except tk.TclError:
            pass

    def _copy_current_line(self):
        line = self.text.index("insert").split(".")[0]
        value = self.text.get(f"{line}.0", f"{line}.end")
        self.clipboard_clear()
        self.clipboard_append(value)

    def _select_current_line(self):
        line = self.text.index("insert").split(".")[0]
        self.text.tag_remove("sel", "1.0", "end")
        self.text.tag_add("sel", f"{line}.0", f"{line}.end")
        self.text.mark_set("insert", f"{line}.end")
        self.text.see("insert")

    def _delete_current_line(self):
        line = int(self.text.index("insert").split(".")[0])
        self.text.delete(f"{line}.0", f"{line + 1}.0")
        self.text.mark_set("insert", f"{max(1, line)}.0")
        self.refresh_lines()
        self._cursor_changed()

    def _show_context_menu(self, event=None):
        """Show context-aware editing, navigation and code actions at the pointer."""
        if event is not None:
            try:
                clicked = self.text.index(f"@{event.x},{event.y}")
                if not (
                    self.text.tag_ranges("sel")
                    and self.text.compare(clicked, ">=", "sel.first")
                    and self.text.compare(clicked, "<=", "sel.last")
                ):
                    self.text.tag_remove("sel", "1.0", "end")
                    self.text.mark_set("insert", clicked)
            except tk.TclError:
                pass
        root = self.winfo_toplevel()
        palette = getattr(root, "theme_palette", {})
        preferences = getattr(root, "preferences", {})
        font_family = (
            root._resolved_ui_font()
            if hasattr(root, "_resolved_ui_font")
            else "Segoe UI"
        )
        menu = ContextMenu(
            self,
            palette=palette,
            font_family=font_family,
            font_size=preferences.get("ui_font_size", 9),
        )
        try:
            has_selection = bool(self.text.tag_ranges("sel"))
        except tk.TclError:
            has_selection = False
        menu.add_command(label="Undo", command=lambda: self._safe_edit_history("undo"))
        menu.add_command(label="Redo", command=lambda: self._safe_edit_history("redo"))
        menu.add_separator()
        menu.add_command(
            label="Cut",
            command=lambda: self.text.event_generate("<<Cut>>"),
            state="normal" if has_selection else "disabled",
        )
        menu.add_command(
            label="Copy Selection",
            command=lambda: self.text.event_generate("<<Copy>>"),
            state="normal" if has_selection else "disabled",
        )
        menu.add_command(label="Copy Line", command=self._copy_current_line)
        menu.add_command(
            label="Paste", command=lambda: self.text.event_generate("<<Paste>>")
        )
        menu.add_command(label="Select All", command=self._select_all)
        menu.add_separator()
        menu.add_command(
            label="Duplicate Line / Selection", command=self._duplicate_line
        )
        menu.add_command(label="Delete Line", command=self._delete_current_line)
        menu.add_command(
            label="Move Line Up    Alt+Up", command=lambda: self._move_line(-1)
        )
        menu.add_command(
            label="Move Line Down    Alt+Down", command=lambda: self._move_line(1)
        )
        menu.add_command(label="Select Current Line", command=self._select_current_line)
        menu.add_command(
            label="Toggle Line Comment    Ctrl+/", command=self._toggle_comment
        )
        menu.add_separator()
        menu.add_command(label="Go to Line…    Ctrl+G", command=self._go_to_line)
        menu.add_command(
            label="Show Completions    Ctrl+Space", command=self.show_completions
        )
        menu.add_command(
            label="Format / Analyze",
            command=lambda: self.text.event_generate("<<PyLexAnalyze>>"),
        )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
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
        matches = [
            item for item in candidates if item.startswith(prefix) and item != prefix
        ]
        if not matches:
            self._hide_completions()
            return "break"

        self._hide_completions()
        self._completion_start = prefix_start
        self._completion_end = self.text.index("insert")
        self._completion_window = tk.Toplevel(self)
        self._completion_window.wm_overrideredirect(True)
        self._completion_list = tk.Listbox(
            self._completion_window,
            height=min(8, len(matches)),
            exportselection=False,
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
                index = max(
                    0, min(size - 1, index + (1 if event.keysym == "Down" else -1))
                )
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
        """Rebuild line numbers without resetting the editor's current scroll offset."""
        first, _last = self.text.yview()
        count = max(1, int(self.text.index("end-1c").split(".")[0]))
        current = int(self.text.index("insert").split(".")[0])
        self.gutter.configure(state="normal")
        self.gutter.delete("1.0", "end")
        self.gutter.insert(
            "1.0",
            "\n".join(
                ("● " if i in self._breakpoints else "  ") + str(i)
                for i in range(1, count + 1)
            ),
        )
        self.gutter.tag_remove("gutter_current", "1.0", "end")
        self.gutter.tag_remove("gutter_error", "1.0", "end")
        self.gutter.tag_add("gutter_current", f"{current}.0", f"{current}.end")
        if self._diagnostic_location:
            line = self._diagnostic_location[0]
            if 1 <= line <= count:
                self.gutter.tag_add("gutter_error", f"{line}.0", f"{line}.end")
        self.gutter.configure(state="disabled")
        self.gutter.yview_moveto(first)

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
        self._update_matching_bracket()
        if self.on_cursor_change:
            self.on_cursor_change()

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
            "py_keyword",
            "py_builtin",
            "py_string",
            "py_comment",
            "py_number",
            "py_function",
            "py_class",
            "py_operator",
            "py_error",
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
        self._update_matching_bracket()

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
        if (
            end_line == line_number
            and end_column is not None
            and end_column > self._diagnostic_location[1]
        ):
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
        self.font_size = max(7, min(40, int(size)))
        self.editor_font.configure(size=self.font_size)

    def set_font_family(self, family):
        family = str(family).strip()
        if not family:
            return
        try:
            installed = set(tkfont.families(self))
        except tk.TclError:
            installed = set()
        if installed and family not in installed:
            family = next(
                (
                    candidate
                    for candidate in ("Cascadia Code", "Consolas", "Courier New")
                    if candidate in installed
                ),
                "TkFixedFont",
            )
        self.editor_font.configure(family=family)
