"""Tkinter presentation for the searchable application command registry."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from ..commands import CommandRegistry


class CommandPalette:
    """Render a themed, keyboard-friendly view of registered commands."""

    def __init__(
        self,
        master,
        registry: CommandRegistry,
        palette: dict[str, str] | None = None,
        font_family: str = "Segoe UI",
    ):
        self.master = master
        self.registry = registry
        self.palette = palette or {}
        self.font_family = font_family

    def show(self) -> tk.Toplevel:
        """Open the palette and return its dialog window."""
        dialog = tk.Toplevel(self.master)
        dialog.title("Command Palette")
        dialog.transient(self.master)
        dialog.geometry("560x420")
        dialog.minsize(420, 280)

        query = tk.StringVar()
        entry = ttk.Entry(
            dialog, textvariable=query, font=(self.font_family, 11)
        )
        entry.pack(fill="x", padx=12, pady=12)

        listing = tk.Listbox(
            dialog,
            activestyle="none",
            height=14,
            borderwidth=0,
            bg=self.palette.get("surface", "#202938"),
            fg=self.palette.get("editor_fg", "#f0f3f8"),
            selectbackground=self.palette.get("accent", "#4169b1"),
            selectforeground="#ffffff",
            highlightthickness=0,
            font=(self.font_family, 10),
        )
        listing.pack(fill="both", expand=True, padx=12, pady=(0, 12))

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
            dialog.destroy()
            self.registry.execute(command.command_id)
            return "break"

        def focus_results(_event=None):
            if matches:
                listing.focus_set()
                listing.selection_clear(0, "end")
                listing.selection_set(0)
                listing.activate(0)
            return "break"

        query.trace_add("write", refresh)
        listing.bind("<Double-1>", execute)
        listing.bind("<Return>", execute)
        entry.bind("<Down>", focus_results)
        entry.bind("<Return>", execute)
        dialog.bind("<Escape>", lambda _event: dialog.destroy())

        refresh()
        entry.focus_set()
        return dialog
