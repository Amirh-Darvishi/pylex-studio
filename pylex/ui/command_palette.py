"""Tkinter presentation for the searchable application command registry."""

from __future__ import annotations

import tkinter as tk

from ..commands import CommandRegistry


class CommandPalette:
    """Render a compact, themed command popup anchored to its toolbar surface."""

    def __init__(
        self,
        master,
        registry: CommandRegistry,
        palette: dict[str, str] | None = None,
        font_family: str = "Segoe UI",
        anchor: tk.Widget | None = None,
    ):
        self.master = master
        self.registry = registry
        self.palette = palette or {}
        self.font_family = font_family
        self.anchor = anchor

    def show(self) -> tk.Toplevel:
        """Open a context-menu-like popup aligned to the launcher frame."""
        root = self.master.winfo_toplevel()
        previous = getattr(root, "_pylex_command_palette_window", None)
        if previous is not None:
            try:
                if previous.winfo_exists():
                    previous.destroy()
            except tk.TclError:
                pass
            root._pylex_command_palette_window = None
        dialog = tk.Toplevel(root)
        dialog.withdraw()
        dialog.overrideredirect(True)
        dialog.transient(root)

        border = self.palette.get("border", "#394655")
        surface = self.palette.get("menu_bg", "#252D38")
        foreground = self.palette.get("menu_fg", "#D8DEE8")
        muted = self.palette.get("muted", "#9AA7B7")
        accent = self.palette.get("accent", "#8FB7D8")
        elevated = self.palette.get("elevated", "#303B49")

        dialog.configure(
            background=border,
            highlightthickness=1,
            highlightbackground=border,
        )
        shell = tk.Frame(dialog, background=border, padx=1, pady=1)
        shell.pack(fill="both", expand=True)
        body = tk.Frame(shell, background=surface, padx=10, pady=9)
        body.pack(fill="both", expand=True)

        heading = tk.Label(
            body,
            text="COMMAND PALETTE",
            anchor="w",
            background=surface,
            foreground=muted,
            font=(self.font_family, 8, "bold"),
            padx=2,
            pady=2,
        )
        heading.pack(fill="x", pady=(0, 7))

        query = tk.StringVar()
        entry = tk.Entry(
            body,
            textvariable=query,
            relief="flat",
            borderwidth=0,
            highlightthickness=1,
            highlightbackground=border,
            highlightcolor=accent,
            background=elevated,
            foreground=foreground,
            insertbackground=accent,
            selectbackground=accent,
            selectforeground="#ffffff",
            font=(self.font_family, 10),
        )
        entry.pack(fill="x", ipady=7, pady=(0, 8))

        results_frame = tk.Frame(body, background=surface)
        results_frame.pack(fill="both", expand=True)
        listing = tk.Listbox(
            results_frame,
            activestyle="none",
            height=12,
            borderwidth=0,
            highlightthickness=0,
            bg=surface,
            fg=foreground,
            selectbackground=accent,
            selectforeground="#ffffff",
            font=(self.font_family, 9),
            exportselection=False,
        )
        scrollbar = tk.Scrollbar(
            results_frame,
            orient="vertical",
            command=listing.yview,
            relief="flat",
            borderwidth=0,
        )
        listing.configure(yscrollcommand=scrollbar.set)
        listing.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        matches = []

        def refresh(*_args):
            listing.delete(0, "end")
            matches.clear()
            matches.extend(self.registry.search(query.get()))
            for command in matches:
                label = f"{command.label}    {command.shortcut}".rstrip()
                listing.insert("end", label)
            if matches:
                listing.selection_set(0)
                listing.activate(0)

        def execute(_event=None):
            selection = listing.curselection()
            if not selection:
                return "break"
            command = matches[selection[0]]
            dismiss()
            self.registry.execute(command.command_id)
            return "break"

        def select_result(index, *, focus=False):
            if not matches:
                return "break"
            index = max(0, min(len(matches) - 1, index))
            listing.selection_clear(0, "end")
            listing.selection_set(index)
            listing.activate(index)
            listing.see(index)
            if focus:
                listing.focus_set()
            return "break"

        def focus_results(_event=None):
            return select_result(0, focus=True)

        def move_selection(direction):
            selection = listing.curselection()
            current = (
                selection[0]
                if selection
                else (0 if direction > 0 else len(matches) - 1)
            )
            return select_result(current + direction)

        def wheel_scroll(event):
            if getattr(event, "delta", 0):
                listing.yview_scroll(-1 if event.delta > 0 else 1, "units")
            return "break"

        def wheel_up(_event):
            listing.yview_scroll(-1, "units")
            return "break"

        def wheel_down(_event):
            listing.yview_scroll(1, "units")
            return "break"

        def dismiss(_event=None):
            if getattr(root, "_pylex_command_palette_window", None) is dialog:
                root._pylex_command_palette_window = None
            try:
                if dialog.winfo_exists():
                    dialog.destroy()
            except tk.TclError:
                pass

        def outside_click(event):
            active = getattr(root, "_pylex_command_palette_window", None)
            if active is None:
                return
            try:
                # The launcher's instance binding runs before the application-wide
                # binding. Ignore that same click after it has opened/reopened the
                # popup, otherwise the newly created window would close instantly.
                if self.anchor is not None and self.anchor.winfo_exists():
                    anchor_left = self.anchor.winfo_rootx()
                    anchor_top = self.anchor.winfo_rooty()
                    anchor_right = anchor_left + self.anchor.winfo_width()
                    anchor_bottom = anchor_top + self.anchor.winfo_height()
                    if (
                        anchor_left <= event.x_root < anchor_right
                        and anchor_top <= event.y_root < anchor_bottom
                    ):
                        return
                if not active.winfo_exists():
                    root._pylex_command_palette_window = None
                    return
                left, top = active.winfo_rootx(), active.winfo_rooty()
                inside = (
                    left <= event.x_root < left + active.winfo_width()
                    and top <= event.y_root < top + active.winfo_height()
                )
                if not inside:
                    active.destroy()
                    root._pylex_command_palette_window = None
            except tk.TclError:
                root._pylex_command_palette_window = None

        query.trace_add("write", refresh)
        listing.bind("<Motion>", lambda event: select_result(listing.nearest(event.y)))
        listing.bind("<Leave>", lambda _event: "break")
        listing.bind(
            "<Button-1>", lambda event: select_result(listing.nearest(event.y))
        )
        listing.bind("<Double-1>", execute)
        listing.bind("<Return>", execute)
        entry.bind("<Down>", focus_results)
        entry.bind("<Up>", lambda _event: select_result(len(matches) - 1))
        entry.bind("<Return>", execute)
        listing.bind("<Up>", lambda _event: move_selection(-1))
        listing.bind("<Down>", lambda _event: move_selection(1))
        listing.bind("<MouseWheel>", wheel_scroll)
        listing.bind("<Button-4>", wheel_up)
        listing.bind("<Button-5>", wheel_down)
        entry.bind("<MouseWheel>", wheel_scroll)
        entry.bind("<Button-4>", wheel_up)
        entry.bind("<Button-5>", wheel_down)
        dialog.bind("<Escape>", dismiss)
        if not getattr(root, "_pylex_command_palette_listener", False):
            root.bind_all("<Button-1>", outside_click, add="+")
            root._pylex_command_palette_listener = True
        root._pylex_command_palette_window = dialog

        refresh()
        dialog.update_idletasks()

        width = 320
        x = root.winfo_rootx() + 24
        y = root.winfo_rooty() + 64
        if self.anchor is not None and self.anchor.winfo_exists():
            width = max(250, self.anchor.winfo_width())
            x = self.anchor.winfo_rootx()
            y = self.anchor.winfo_rooty() + self.anchor.winfo_height()

        height = 360
        screen_width = root.winfo_screenwidth()
        screen_height = root.winfo_screenheight()
        if x + width > screen_width:
            x = screen_width - width - 6
        if y + height > screen_height:
            y = (
                self.anchor.winfo_rooty() - height - 4
                if self.anchor is not None
                else screen_height - height - 6
            )
        dialog.geometry(f"{width}x{height}+{max(0, x)}+{max(0, y)}")
        dialog.deiconify()
        dialog.lift()
        entry.focus_set()
        return dialog
