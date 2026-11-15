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
        self._row_widgets = []
        self._active_row_index = -1

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
        if self._parent_menu is None:
            root = self.master.winfo_toplevel()
            if getattr(root, "_pylex_active_context_menu", None) is self:
                root._pylex_active_context_menu = None
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
        self.window.configure(background=border)
        shell = tk.Frame(self.window, background=border, padx=1, pady=1)
        shell.pack(fill="both", expand=True)
        body = tk.Frame(shell, background=surface, padx=4, pady=5)
        body.pack(fill="both", expand=True)

        self._row_widgets = []
        self._active_row_index = -1
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
                marker = ""

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

            row_index = len(self._row_widgets)
            self._row_widgets.append((row, text_label, enabled, item))
            hover_job = {"id": None}

            def set_row_hover(target, target_label, active, color, normal_fg=fg):
                if not active:
                    return
                target.configure(background=color)
                for child_widget in target.winfo_children():
                    child_widget.configure(background=color)
                    if child_widget is target_label:
                        child_widget.configure(
                            foreground=self._color("accent", "#8FB7D8")
                            if color != surface else normal_fg
                        )

            def hover(_event, target=row, target_label=text_label, active=enabled,
                      hover_data=hover_job, normal_fg=fg):
                if hover_data["id"] is not None:
                    try:
                        self.window.after_cancel(hover_data["id"])
                    except (tk.TclError, AttributeError):
                        pass
                    hover_data["id"] = None
                self._active_row_index = row_index
                set_row_hover(target, target_label, active, self._color("elevated", "#303B49"), normal_fg)

            def unhover(_event, target=row, target_label=text_label, active=enabled,
                        hover_data=hover_job, normal_fg=fg):
                if not active:
                    return
                def settle():
                    hover_data["id"] = None
                    try:
                        x, y = self.window.winfo_pointerxy()
                        inside = (target.winfo_rootx() <= x < target.winfo_rootx() + target.winfo_width()
                                  and target.winfo_rooty() <= y < target.winfo_rooty() + target.winfo_height())
                    except (tk.TclError, AttributeError):
                        inside = False
                    if not inside:
                        set_row_hover(target, target_label, active, surface, normal_fg)
                hover_data["id"] = self.window.after(45, settle)

            for widget in (row, *row.winfo_children()):
                widget.bind("<Enter>", hover, add="+")
                widget.bind("<Leave>", unhover, add="+")

            if not enabled:
                continue
            if kind == "cascade":
                child_menu = item["menu"]
                for widget in (row, *row.winfo_children()):
                    widget.bind("<Enter>", lambda event, r=row, child=child_menu: self._open_submenu(r, child), add="+")
                    widget.bind("<Button-1>", lambda event, r=row, child=child_menu: self._open_submenu(r, child), add="+")
            elif kind == "check":
                def toggle(entry=item):
                    entry["variable"].set(not bool(entry["variable"].get()))
                    callback = entry.get("command")
                    if callback:
                        callback()
                    self._dismiss()
                for widget in (row, *row.winfo_children()):
                    widget.bind("<Button-1>", lambda event, fn=toggle: fn(), add="+")
            elif kind == "radio":
                def choose(entry=item):
                    entry["variable"].set(entry["value"])
                    callback = entry.get("command")
                    if callback:
                        callback()
                    self._dismiss()
                for widget in (row, *row.winfo_children()):
                    widget.bind("<Button-1>", lambda event, fn=choose: fn(), add="+")
            else:
                callback = lambda entry=item: self._invoke(entry)
                for widget in (row, *row.winfo_children()):
                    widget.bind("<Button-1>", lambda event, fn=callback: fn(), add="+")
        self.window.update_idletasks()
        self.window.bind("<Escape>", lambda _event: self._root_menu()._dismiss(), add="+")
        self.window.bind("<Down>", lambda _event: self._move_selection(1), add="+")
        self.window.bind("<Up>", lambda _event: self._move_selection(-1), add="+")
        self.window.bind("<Return>", self._activate_selection, add="+")
        self.window.bind("<KP_Enter>", self._activate_selection, add="+")
        self.window.bind("<Right>", self._open_selected_submenu, add="+")
        self.window.bind("<Left>", self._close_to_parent, add="+")

    def _move_selection(self, direction):
        if not self._row_widgets:
            return "break"
        count = len(self._row_widgets)
        index = self._active_row_index
        for _ in range(count):
            index = (index + direction) % count
            row, label, enabled, item = self._row_widgets[index]
            if enabled:
                self._active_row_index = index
                for current, current_label, current_enabled, _entry in self._row_widgets:
                    color = self._color("elevated", "#303B49") if current is row else self._color("menu_bg", "#202936")
                    current.configure(background=color)
                    for child_widget in current.winfo_children():
                        child_widget.configure(background=color)
                        if child_widget is current_label:
                            child_widget.configure(
                                foreground=self._color("accent", "#8FB7D8") if current is row
                                else (self._color("menu_fg", "#D8DEE8") if current_enabled else self._color("muted", "#8290A2"))
                            )
                break
        return "break"

    def _activate_selection(self, _event=None):
        if 0 <= self._active_row_index < len(self._row_widgets):
            row, _label, enabled, item = self._row_widgets[self._active_row_index]
            if enabled:
                if item["kind"] == "cascade":
                    self._open_submenu(row, item["menu"])
                elif item["kind"] == "check":
                    item["variable"].set(not bool(item["variable"].get()))
                    callback = item.get("command")
                    if callback:
                        callback()
                    self._root_menu()._dismiss()
                elif item["kind"] == "radio":
                    item["variable"].set(item["value"])
                    callback = item.get("command")
                    if callback:
                        callback()
                    self._root_menu()._dismiss()
                else:
                    self._invoke(item)
        return "break"

    def _open_selected_submenu(self, _event=None):
        if 0 <= self._active_row_index < len(self._row_widgets):
            row, _label, enabled, item = self._row_widgets[self._active_row_index]
            if enabled and item["kind"] == "cascade":
                self._open_submenu(row, item["menu"])
        return "break"

    def _close_to_parent(self, _event=None):
        if self._parent_menu is not None:
            parent = self._parent_menu
            self._dismiss()
            if parent.window is not None:
                parent.window.focus_force()
        else:
            self._root_menu()._dismiss()
        return "break"

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
        try:
            self.window.focus_force()
        except tk.TclError:
            pass
        if self._parent_menu is None:
            root = self.master.winfo_toplevel()
            active = getattr(root, "_pylex_active_context_menu", None)
            if active is not None and active is not self:
                active._dismiss()
            root._pylex_active_context_menu = self
            if not getattr(root, "_pylex_context_menu_listener", False):
                root.bind_all(
                    "<Button-1>",
                    lambda event, owner=root: ContextMenu._dispatch_global_click(owner, event),
                    add="+",
                )
                root._pylex_context_menu_listener = True

    @staticmethod
    def _dispatch_global_click(root, event):
        active = getattr(root, "_pylex_active_context_menu", None)
        if active is not None:
            active._outside_click(event)

    def _outside_click(self, event):
        x, y = event.x_root, event.y_root
        menus = [self]
        parent = self._parent_menu
        while parent is not None:
            menus.append(parent)
            parent = parent._parent_menu
        child = self._submenu
        while child is not None:
            menus.append(child)
            child = child._submenu
        inside = False
        for menu in menus:
            try:
                window = menu.window
                if window is None or not window.winfo_exists():
                    continue
                left, top = window.winfo_rootx(), window.winfo_rooty()
                if left <= x < left + window.winfo_width() and top <= y < top + window.winfo_height():
                    inside = True
                    break
            except tk.TclError:
                continue
        if not inside:
            self._root_menu()._dismiss()

    def grab_release(self):
        # Keep the popup visible; unlike native tk.Menu, the window owns its grab.
        return None
