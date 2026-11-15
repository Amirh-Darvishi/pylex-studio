"""Consistent, theme-aware popup and context menus for PyLex Studio."""
from __future__ import annotations

import tkinter as tk


class ContextMenu:
    """Lightweight custom popup menu with hover rows and cascading submenus."""

    def __init__(self, master, *, palette=None, font_family="Segoe UI", font_size=9):
        self.master = master
        root = master.winfo_toplevel()
        self.palette = palette or getattr(root, "theme_palette", {})
        self.font_family = font_family
        self.font_size = font_size
        self.items = []
        self.window = None
        self._submenu = None
        self._parent_menu = None
        self._closed = False

    def add_command(self, *, label, command=None, state="normal", accelerator="", **_kwargs):
        self.items.append({
            "kind": "command", "label": label, "command": command,
            "state": state, "accelerator": accelerator,
        })

    def add_separator(self):
        self.items.append({"kind": "separator"})

    def add_cascade(self, *, label, menu, state="normal", **_kwargs):
        self.items.append({"kind": "cascade", "label": label, "menu": menu, "state": state})

    def add_checkbutton(self, *, label, variable, command=None, state="normal", **_kwargs):
        self.items.append({
            "kind": "check", "label": label, "variable": variable,
            "command": command, "state": state,
        })

    def add_radiobutton(self, *, label, variable, value, command=None, state="normal", **_kwargs):
        self.items.append({
            "kind": "radio", "label": label, "variable": variable,
            "value": value, "command": command, "state": state,
        })

    def delete(self, first, last=None):
        if first in ("all", 0) and (last in (None, "end", 0) or first == "all"):
            self.items.clear()
        elif isinstance(first, int):
            end = first if last is None or last == "end" else int(last)
            del self.items[first:end + 1]

    def _color(self, name, fallback):
        return self.palette.get(name, fallback)

    def _dismiss(self, _event=None):
        if self._closed:
            return
        self._closed = True
        if self._parent_menu is not None:
            self._parent_menu._dismiss()
        if self._submenu is not None:
            self._submenu._dismiss()
            self._submenu = None
        if self.window is not None:
            try:
                if self.window.winfo_exists():
                    self.window.destroy()
            except tk.TclError:
                pass
        self.window = None

    def _root_menu(self):
        menu = self
        while menu._parent_menu is not None:
            menu = menu._parent_menu
        return menu

    def _invoke(self, item):
        self._root_menu()._dismiss()
        callback = item.get("command")
        if callback is not None:
            callback()

    def _open_submenu(self, row, child):
        if child is None or child is self:
            return
        if self._submenu is not None and self._submenu is not child:
            self._submenu._dismiss()
        self._submenu = child
        child._parent_menu = self
        if child.window is None or not child.window.winfo_exists():
            child._render()
        child.window.update_idletasks()
        x = self.window.winfo_rootx() + self.window.winfo_width() - 2
        y = row.winfo_rooty()
        screen_w = self.master.winfo_screenwidth()
        if x + child.window.winfo_reqwidth() > screen_w:
            x = self.window.winfo_rootx() - child.window.winfo_reqwidth() + 2
        child.window.geometry(f"+{max(0, x)}+{max(0, y)}")
        child.window.deiconify()
        child.window.lift()

    def _render(self):
        root = self.master.winfo_toplevel()
        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.transient(root)
        border = self._color("border", "#394657")
        surface = self._color("menu_bg", "#202936")
        self.window.configure(background=border, padx=1, pady=1)
        body = tk.Frame(self.window, background=surface, padx=4, pady=5)
        body.pack(fill="both", expand=True)

        for item in self.items:
            kind = item["kind"]
            if kind == "separator":
                tk.Frame(body, height=1, background=border).pack(fill="x", padx=8, pady=4)
                continue

            row_bg = surface
            row = tk.Frame(body, background=row_bg, padx=3, pady=1)
            row.pack(fill="x")
            enabled = item.get("state", "normal") != "disabled"
            fg = self._color("menu_fg", "#D8DEE8") if enabled else self._color("muted", "#8290A2")
            label = item.get("label", "")
            marker = ""
            if kind == "check":
                marker = "✓ " if bool(item["variable"].get()) else "   "
            elif kind == "radio":
                marker = "● " if item["variable"].get() == item["value"] else "○ "
            elif kind == "cascade":
                marker = "›"

            text_label = tk.Label(
                row, text=(marker + label), anchor="w",
                background=surface, foreground=fg,
                font=(self.font_family, self.font_size),
                padx=10, pady=5, cursor="hand2" if enabled else "arrow",
            )
            text_label.pack(side="left", fill="x", expand=True)
            trailing = item.get("accelerator", "")
            if kind == "cascade":
                trailing = "›"
            elif kind in ("check", "radio"):
                trailing = ""
            if trailing:
                tk.Label(
                    row, text=trailing, background=surface,
                    foreground=self._color("muted", "#8290A2"),
                    font=(self.font_family, max(7, self.font_size - 1)),
                    padx=10,
                ).pack(side="right")

            hover_job = {"id": None}

            def set_row_hover(target, target_label, active, color):
                if not active:
                    return
                target.configure(background=color)
                for child_widget in target.winfo_children():
                    child_widget.configure(background=color)
                    if child_widget is target_label:
                        child_widget.configure(
                            foreground=self._color("accent", "#8FB7D8")
                            if color != surface else fg
                        )

            def hover(_event, target=row, target_label=text_label, active=enabled):
                if hover_job["id"] is not None:
                    try:
                        self.window.after_cancel(hover_job["id"])
                    except tk.TclError:
                        pass
                    hover_job["id"] = None
                set_row_hover(target, target_label, active, self._color("elevated", "#303B49"))

            def unhover(_event, target=row, target_label=text_label, active=enabled):
                if not active:
                    return
                def settle():
                    hover_job["id"] = None
                    try:
                        x, y = self.window.winfo_pointerxy()
                        inside = (target.winfo_rootx() <= x < target.winfo_rootx() + target.winfo_width()
                                  and target.winfo_rooty() <= y < target.winfo_rooty() + target.winfo_height())
                    except tk.TclError:
                        inside = False
                    if not inside:
                        set_row_hover(target, target_label, active, surface)
                hover_job["id"] = self.window.after(45, settle)

            for widget in (row, text_label, *row.winfo_children()):
                widget.bind("<Enter>", hover, add="+")
                widget.bind("<Leave>", unhover, add="+")

            if not enabled:
                continue
            if kind == "cascade":
                child_menu = item["menu"]
                for widget in (row, text_label):
                    widget.bind(
                        "<Enter>",
                        lambda event, r=row, child=child_menu: self._open_submenu(r, child),
                        add="+",
                    )
            elif kind == "check":
                def toggle(entry=item):
                    entry["variable"].set(not bool(entry["variable"].get()))
                    callback = entry.get("command")
                    if callback:
                        callback()
                    self._dismiss()
                for widget in (row, text_label):
                    widget.bind("<Button-1>", lambda event, fn=toggle: fn(), add="+")
            elif kind == "radio":
                def choose(entry=item):
                    entry["variable"].set(entry["value"])
                    callback = entry.get("command")
                    if callback:
                        callback()
                    self._dismiss()
                for widget in (row, text_label):
                    widget.bind("<Button-1>", lambda event, fn=choose: fn(), add="+")
            else:
                callback = lambda entry=item: self._invoke(entry)
                for widget in (row, text_label):
                    widget.bind("<Button-1>", lambda event, fn=callback: fn(), add="+")
        self.window.update_idletasks()

    def tk_popup(self, x, y, *_args):
        self._closed = False
        if self.window is not None:
            self._dismiss()
            self._closed = False
        self._render()
        width = max(220, self.window.winfo_reqwidth())
        height = self.window.winfo_reqheight()
        screen_w = self.master.winfo_screenwidth()
        screen_h = self.master.winfo_screenheight()
        if x + width > screen_w:
            x = screen_w - width - 6
        if y + height > screen_h:
            y = screen_h - height - 6
        self.window.geometry(f"+{max(0, x)}+{max(0, y)}")
        self.window.deiconify()
        self.window.lift()
        self.window.bind("<Escape>", lambda _event: self._dismiss(), add="+")
        self.window.bind("<Button-1>", self._outside_click, add="+")
        try:
            self.window.grab_set()
        except tk.TclError:
            pass

    def _outside_click(self, event):
        x, y = event.x_root, event.y_root
        try:
            left, top = self.window.winfo_rootx(), self.window.winfo_rooty()
            inside = left <= x < left + self.window.winfo_width() and top <= y < top + self.window.winfo_height()
            if self._submenu is not None and self._submenu.window is not None:
                child = self._submenu.window
                cx, cy = child.winfo_rootx(), child.winfo_rooty()
                inside = inside or (cx <= x < cx + child.winfo_width() and cy <= y < cy + child.winfo_height())
        except tk.TclError:
            inside = False
        if not inside:
            self._dismiss()

    def grab_release(self):
        # Keep the popup visible; unlike native tk.Menu, the window owns its grab.
        return None
