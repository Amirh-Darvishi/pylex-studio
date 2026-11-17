"""Tkinter workspace search window with cancellable search and reviewed replacement."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .project_search import (
    build_replacements, compile_search_pattern, search_text, write_replacements,
)


class ProjectSearchWindow(tk.Toplevel):
    """Search all supported workspace files without blocking the Tk event loop."""

    def __init__(self, app):
        super().__init__(app)
        self.app = app
        self.root_path = app.project.root
        self.title("PyLex Studio — Search in Workspace")
        self.geometry("980x680")
        self.minsize(760, 500)
        self.transient(app)
        self._events = queue.Queue()
        self._worker = None
        self._cancel = None
        self._generation = 0
        self._matches = []
        self._snapshots = {}
        self._preview = {}
        self._build()
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.after(80, self._poll)

    def _build(self):
        shell = ttk.Frame(self, padding=12)
        shell.pack(fill="both", expand=True)
        ttk.Label(shell, text=f"Workspace: {self.root_path}").pack(anchor="w")
        query_row = ttk.Frame(shell)
        query_row.pack(fill="x", pady=(10, 4))
        ttk.Label(query_row, text="Find").pack(side="left")
        self.query = tk.StringVar()
        ttk.Entry(query_row, textvariable=self.query).pack(
            side="left", fill="x", expand=True, padx=(8, 12)
        )
        ttk.Label(query_row, text="Replace").pack(side="left")
        self.replacement = tk.StringVar()
        ttk.Entry(query_row, textvariable=self.replacement, width=28).pack(
            side="left", padx=(8, 0)
        )
        options = ttk.Frame(shell)
        options.pack(fill="x", pady=5)
        self.regex = tk.BooleanVar()
        self.case = tk.BooleanVar()
        self.word = tk.BooleanVar()
        ttk.Checkbutton(options, text="Regular expression", variable=self.regex).pack(side="left")
        ttk.Checkbutton(options, text="Match case", variable=self.case).pack(side="left", padx=10)
        ttk.Checkbutton(options, text="Whole word", variable=self.word).pack(side="left")
        ttk.Label(options, text="File pattern").pack(side="left", padx=(20, 5))
        self.glob = tk.StringVar(value="*")
        ttk.Entry(options, textvariable=self.glob, width=16).pack(side="left")
        self.search_button = ttk.Button(options, text="Search", command=self.start_search)
        self.search_button.pack(side="right")
        self.cancel_button = ttk.Button(options, text="Cancel", command=self.cancel,
                                        state="disabled")
        self.cancel_button.pack(side="right", padx=5)
        self.results = ttk.Treeview(shell, columns=("location", "replacement"), show="tree headings")
        self.results.heading("#0", text="File and matching line")
        self.results.heading("location", text="Line / Column")
        self.results.heading("replacement", text="Replacement preview")
        self.results.column("#0", width=690)
        self.results.column("location", width=110, anchor="center")
        self.results.column("replacement", width=260)
        self.results.pack(fill="both", expand=True, pady=(8, 4))
        self.results.bind("<Double-1>", self._open_match)
        footer = ttk.Frame(shell)
        footer.pack(fill="x")
        self.status = ttk.Label(footer, text="Ready")
        self.status.pack(side="left", fill="x", expand=True)
        self.preview_button = ttk.Button(footer, text="Preview Replace All",
                                         command=self.preview_replacements)
        self.preview_button.pack(side="right", padx=4)
        self.apply_button = ttk.Button(footer, text="Apply Reviewed Changes",
                                       command=self.apply_replacements, state="disabled")
        self.apply_button.pack(side="right", padx=4)

    def _overlays(self):
        overlays = {}
        for editor, document in list(self.app.documents.items()):
            path = document.get("path")
            if path and document.get("dirty"):
                overlays[path] = editor.text.get("1.0", "end-1c")
        return overlays

    def start_search(self):
        query = self.query.get()
        if not query.strip():
            messagebox.showinfo("Workspace Search", "Enter text to search for.", parent=self)
            return
        self.cancel()
        self._generation += 1
        generation = self._generation
        self._cancel = threading.Event()
        overlays = self._overlays()
        options = dict(regex=self.regex.get(), case_sensitive=self.case.get(),
                       whole_word=self.word.get(), include_glob=self.glob.get() or "*",
                       overlays=overlays, cancel_event=self._cancel)
        self.search_button.configure(state="disabled")
        self.cancel_button.configure(state="normal")
        self.status.configure(text="Searching workspace…")
        self._matches = []
        self._snapshots = {}
        self._preview = {}
        self.apply_button.configure(state="disabled")
        self.results.delete(*self.results.get_children())

        def worker():
            try:
                matches, snapshots = search_text(self.root_path, query, **options)
                self._events.put((generation, "done", matches, snapshots))
            except Exception as exc:
                self._events.put((generation, "error", str(exc)))

        self._worker = threading.Thread(target=worker, name="PyLexProjectSearch", daemon=True)
        self._worker.start()

    def cancel(self):
        if self._cancel is not None:
            self._cancel.set()
        self.cancel_button.configure(state="disabled")

    def _poll(self):
        try:
            while True:
                event = self._events.get_nowait()
                generation, kind, *payload = event
                if generation != self._generation:
                    continue
                if kind == "error":
                    self.status.configure(text=f"Search failed: {payload[0]}")
                else:
                    self._matches, self._snapshots = payload
                    for index, match in enumerate(self._matches):
                        relative = match.path.relative_to(self.root_path)
                        self.results.insert("", "end", iid=str(index),
                                             text=f"{relative}: {match.text.strip()}",
                                             values=(f"{match.line}:{match.column}",))
                    self.status.configure(text=f"{len(self._matches)} matches in "
                                                f"{len({m.path for m in self._matches})} files")
                self.search_button.configure(state="normal")
                self.cancel_button.configure(state="disabled")
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(80, self._poll)

    def _open_match(self, _event=None):
        selected = self.results.selection()
        if not selected:
            return
        match = self._matches[int(selected[0])]
        self.app._open_path(match.path)
        editor = self.app.editor
        editor.text.mark_set("insert", f"{match.line}.{match.column - 1}")
        editor.text.see("insert")
        editor.text.focus_set()

    def preview_replacements(self):
        if not self._matches:
            messagebox.showinfo("Replace", "Run a search and review its results first.",
                                parent=self)
            return
        try:
            pattern = compile_search_pattern(self.query.get(), regex=self.regex.get(),
                                             case_sensitive=self.case.get(),
                                             whole_word=self.word.get())
        except ValueError as exc:
            messagebox.showerror("Invalid Search", str(exc), parent=self)
            return
        overlays = self._overlays()
        grouped = {}
        for match in self._matches:
            grouped.setdefault(match.path, None)
        preview = {}
        for path in grouped:
            if path in overlays:
                original = overlays[path]
            else:
                snapshot = self._snapshots.get(path)
                if snapshot is None:
                    continue
                original = snapshot.content
            updated, count = build_replacements(original, pattern, self.replacement.get())
            if count:
                preview[path] = (updated, count)
                new_lines = updated.splitlines()
                for index, match in enumerate(self._matches):
                    if match.path == path:
                        replacement_line = new_lines[match.line - 1] if match.line <= len(new_lines) else ""
                        self.results.item(str(index), values=(
                            f"{match.line}:{match.column}", replacement_line
                        ))
        self._preview = preview
        total = sum(count for _, count in preview.values())
        self.status.configure(text=f"Preview ready: {total} replacements across "
                                   f"{len(preview)} files. No files changed yet.")
        self.apply_button.configure(state="normal" if total else "disabled")

    def apply_replacements(self):
        if not self._preview:
            return
        total = sum(count for _, count in self._preview.values())
        if not messagebox.askyesno(
            "Confirm Workspace Replacement",
            f"Apply {total} reviewed replacements in {len(self._preview)} files?\n"
            "Open unsaved documents will remain unsaved.",
            parent=self,
        ):
            return
        overlays = self._overlays()
        dirty_paths = {path.resolve() for path in overlays}
        disk_changes = {path: content for path, (content, _count) in self._preview.items()
                        if path.resolve() not in dirty_paths}
        try:
            if disk_changes:
                write_replacements(disk_changes, self._snapshots)
            for editor, document in list(self.app.documents.items()):
                path = document.get("path")
                if path is None or path.resolve() not in dirty_paths:
                    continue
                replacement = self._preview.get(path)
                if replacement is None:
                    continue
                editor.text.delete("1.0", "end")
                editor.text.insert("1.0", replacement[0])
                self.app.mark_dirty(editor)
            for editor, document in list(self.app.documents.items()):
                path = document.get("path")
                if path and path.resolve() in disk_changes:
                    snapshot = self._snapshots[path.resolve()]
                    editor.set_content(disk_changes[path.resolve()])
                    document["dirty"] = False
                    document["encoding"] = snapshot.encoding
                    document["newline"] = snapshot.newline
                    self.app.editor_tabs.tab(document["frame"],
                                             text=self.app._tab_label(document))
            self.status.configure(text=f"Applied {total} replacements in "
                                       f"{len(self._preview)} files.")
            self.apply_button.configure(state="disabled")
            self._preview = {}
            self.start_search()
        except (OSError, RuntimeError, ValueError) as exc:
            messagebox.showerror("Replacement Failed", str(exc), parent=self)

    def close(self):
        self.cancel()
        self.destroy()
