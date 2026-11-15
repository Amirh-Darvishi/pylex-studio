"""Tkinter Git source-control panel for PyLex Studio."""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog

from .git import GitError, GitService
from .ui.context_menu import ContextMenu


class GitPanel(ttk.Frame):
    """Workspace Git UI with asynchronous remote operations."""

    def __init__(self, master, workspace_provider, status_callback=None):
        super().__init__(master, padding=5)
        self.workspace_provider = workspace_provider
        self.status_callback = status_callback or (lambda message: None)
        self.service = None
        self._events = queue.Queue()
        self._busy = False
        self._poll_id = None
        self._build()
        self.refresh()

    def _build(self):
        top = ttk.Frame(self)
        top.pack(fill="x", pady=(0, 5))
        ttk.Label(
            top, text="Git Source Control", font=("TkDefaultFont", 10, "bold")
        ).pack(side="left")
        ttk.Button(top, text="Refresh", command=self.refresh).pack(side="right")
        self.branch_label = ttk.Label(self, text="No Git repository")
        self.branch_label.pack(fill="x", pady=(0, 4))

        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(0, 4))
        for label, command in [
            ("Stage", self.stage_selected),
            ("Stage All", self.stage_all),
            ("Unstage", self.unstage_selected),
            ("Unstage All", self.unstage_all),
            ("Discard", self.discard_selected),
            ("Diff", self.show_diff),
            ("Staged Diff", self.show_staged_diff),
            ("History", self.show_history),
        ]:
            ttk.Button(actions, text=label, command=command).pack(
                side="left", padx=(0, 3)
            )

        columns = ("status", "path")
        self.tree = ttk.Treeview(
            self, columns=columns, show="headings", height=8, selectmode="extended"
        )
        self.tree.heading("status", text="Status")
        self.tree.heading("path", text="Changed File")
        self.tree.column("status", width=75, anchor="center", stretch=False)
        self.tree.column("path", width=450)
        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Button-3>", self._show_tree_context_menu, add="+")

        commit = ttk.LabelFrame(self, text="Commit", padding=5)
        commit.pack(fill="x", pady=(5, 4))
        self.message = tk.StringVar()
        entry = ttk.Entry(commit, textvariable=self.message)
        entry.pack(side="left", fill="x", expand=True, padx=(0, 5))
        entry.bind("<Return>", lambda _event: self.commit())
        entry.bind("<Button-3>", lambda event: self._show_entry_context_menu(entry, event), add="+")
        ttk.Button(commit, text="Commit Staged", command=self.commit).pack(side="right")

        branch = ttk.LabelFrame(self, text="Branches", padding=5)
        branch.pack(fill="x", pady=(0, 4))
        self.branch_var = tk.StringVar()
        self.branch_box = ttk.Combobox(
            branch, textvariable=self.branch_var, state="readonly", width=28
        )
        self.branch_box.pack(side="left", padx=(0, 4))
        ttk.Button(branch, text="Switch", command=self.switch_branch).pack(side="left")
        ttk.Button(branch, text="New Branch", command=self.create_branch).pack(
            side="left", padx=4
        )

        sync = ttk.Frame(self)
        sync.pack(fill="x")
        for label, command in [
            ("Fetch", self.fetch),
            ("Pull (FF only)", self.pull),
            ("Push", self.push),
            ("Stash", self.stash),
        ]:
            ttk.Button(sync, text=label, command=command).pack(side="left", padx=(0, 4))
        self.progress = ttk.Label(sync, text="Ready")
        self.progress.pack(side="right")

    def _ensure_service(self):
        root = self.workspace_provider()
        if root is None:
            raise GitError("Open a workspace folder before using Git.")
        self.service = GitService(root)
        return self.service

    def _selected_paths(self):
        return [self.tree.item(item, "values")[1] for item in self.tree.selection()]

    def _set_busy(self, busy, label="Ready"):
        self._busy = busy
        self.progress.configure(text=label)
        state = "disabled" if busy else "normal"
        for child in self.winfo_children():
            self._set_widget_state(child, state)

    @staticmethod
    def _set_widget_state(widget, state):
        try:
            if isinstance(widget, ttk.Combobox):
                widget.configure(
                    state="disabled" if state == "disabled" else "readonly"
                )
            elif isinstance(widget, (ttk.Button, ttk.Entry)):
                widget.configure(state=state)
        except tk.TclError:
            pass
        for child in widget.winfo_children():
            GitPanel._set_widget_state(child, state)

    def _task(self, label, operation, on_success=None):
        if self._busy:
            return
        try:
            service = self._ensure_service()
        except GitError as exc:
            self.branch_label.configure(text=str(exc))
            return
        self._set_busy(True, label + "…")

        def worker():
            try:
                result = operation(service)
                self._events.put(("ok", result, on_success))
            except Exception as exc:  # surfaced in the UI thread
                self._events.put(("error", str(exc), None))

        threading.Thread(target=worker, daemon=True).start()
        self._poll_events()

    def _poll_events(self):
        try:
            kind, payload, callback = self._events.get_nowait()
        except queue.Empty:
            self._poll_id = self.after(80, self._poll_events)
            return
        self._poll_id = None
        self._set_busy(False)
        if kind == "error":
            self.progress.configure(text="Failed")
            self.branch_label.configure(text=payload)
            self.status_callback("Git: " + payload)
            return
        self.progress.configure(text="Done")
        if callback:
            callback(payload)
        self.status_callback("Git operation completed.")

    def refresh(self):
        def done(status):
            self.branch_label.configure(
                text=f"Branch: {status.branch}   "
                f"{'↑ ' + str(status.ahead) if status.ahead else ''}"
                f"{'↓ ' + str(status.behind) if status.behind else ''}"
                f"   {status.upstream or 'No upstream'}"
            )
            self.tree.delete(*self.tree.get_children())
            for change in status.changes:
                self.tree.insert("", "end", values=(change.status, change.path))
            try:
                branches = self.service.branches()
                self.branch_box.configure(values=[item["name"] for item in branches])
                current = next(
                    (item["name"] for item in branches if item["current"]),
                    status.branch,
                )
                self.branch_var.set(current)
            except GitError:
                pass
            self.progress.configure(
                text="Clean" if status.clean else f"{len(status.changes)} change(s)"
            )

        self._task("Refreshing", lambda service: service.status(), done)

    def _each_selected(self, label, operation):
        paths = self._selected_paths()
        if not paths:
            messagebox.showinfo(
                "Git", "Select one or more changed files first.", parent=self
            )
            return

        def run(service):
            for path in paths:
                operation(service, path)
            return service.status()

        self._task(label, run, lambda _result: self.refresh())

    def stage_selected(self):
        self._each_selected("Staging", lambda service, path: service.stage(path))

    def stage_all(self):
        self._task(
            "Staging all",
            lambda service: service.stage_all(),
            lambda _result: self.refresh(),
        )

    def unstage_selected(self):
        self._each_selected("Unstaging", lambda service, path: service.unstage(path))

    def unstage_all(self):
        self._task(
            "Unstaging all",
            lambda service: service.unstage_all(),
            lambda _result: self.refresh(),
        )

    def discard_selected(self):
        paths = self._selected_paths()
        if not paths:
            messagebox.showinfo(
                "Git", "Select one or more changed files first.", parent=self
            )
            return
        if not messagebox.askyesno(
            "Discard Changes",
            "Permanently discard the selected unstaged changes? This cannot be undone.",
            parent=self,
        ):
            return
        self._each_selected("Discarding", lambda service, path: service.discard(path))

    def show_diff(self):
        self._show_diff(staged=False)

    def show_staged_diff(self):
        self._show_diff(staged=True)

    def _show_diff(self, staged):
        selected = self._selected_paths()
        path = selected[0] if selected else None

        def done(diff):
            window = tk.Toplevel(self)
            window.title("Git Diff" + (f" — {path}" if path else ""))
            window.geometry("900x600")
            text = tk.Text(window, wrap="none", font=("Consolas", 10))
            text.pack(fill="both", expand=True)
            text.insert("1.0", diff or "No diff available for the selected file.")
            text.configure(state="disabled")

        self._task(
            "Loading diff", lambda service: service.diff(path, staged=staged), done
        )

    def commit(self):
        message = self.message.get().strip()
        if not message:
            messagebox.showwarning("Commit", "Enter a commit message.", parent=self)
            return
        self._task(
            "Committing",
            lambda service: service.commit(message),
            lambda _result: (self.message.set(""), self.refresh()),
        )

    def _run_remote(self, label, method):
        self._task(
            label, lambda service: method(service), lambda _result: self.refresh()
        )

    def fetch(self):
        self._run_remote("Fetching", lambda service: service.fetch())

    def pull(self):
        if not messagebox.askyesno(
            "Pull",
            "Pull with fast-forward only? Local changes may block this operation.",
            parent=self,
        ):
            return
        self._run_remote("Pulling", lambda service: service.pull())

    def push(self):
        self._run_remote("Pushing", lambda service: service.push())

    def stash(self):
        self._run_remote("Stashing", lambda service: service.stash())

    def create_branch(self):
        name = simpledialog.askstring("New Branch", "Branch name:", parent=self)
        if name:
            self._task(
                "Creating branch",
                lambda service: service.create_branch(name),
                lambda _result: self.refresh(),
            )

    def switch_branch(self):
        name = self.branch_var.get()
        if not name:
            return
        if not messagebox.askyesno(
            "Switch Branch",
            f"Switch to '{name}'? Git may refuse if local changes conflict.",
            parent=self,
        ):
            return
        self._task(
            "Switching branch",
            lambda service: service.switch_branch(name),
            lambda _result: self.refresh(),
        )

    def show_history(self):
        self._task(
            "Loading history", lambda service: service.log(150), self._display_history
        )

    def _display_history(self, commits):
        window = tk.Toplevel(self)
        window.title("Git History")
        window.geometry("900x420")
        tree = ttk.Treeview(
            window, columns=("hash", "date", "author", "subject"), show="headings"
        )
        for key, label, width in [
            ("hash", "Commit", 100),
            ("date", "Date", 95),
            ("author", "Author", 150),
            ("subject", "Message", 500),
        ]:
            tree.heading(key, text=label)
            tree.column(key, width=width)
        tree.pack(fill="both", expand=True)
        for commit in commits:
            tree.insert(
                "",
                "end",
                values=(commit.short_hash, commit.date, commit.author, commit.subject),
            )

    def _context_menu(self):
        palette = getattr(self.winfo_toplevel(), "theme_palette", {})
        return tk.Menu(
            self, tearoff=False,
            background=palette.get("menu_bg", "#252D38"),
            foreground=palette.get("menu_fg", "#D8DEE8"),
            activebackground=palette.get("elevated", "#303B49"),
            activeforeground=palette.get("accent", "#8FB7D8"),
            disabledforeground=palette.get("muted", "#9AA7B7"),
            borderwidth=1, relief="solid",
        )

    def _show_tree_context_menu(self, event):
        row = self.tree.identify_row(event.y)
        if row:
            if row not in self.tree.selection():
                self.tree.selection_set(row)
            self.tree.focus(row)
        menu = self._context_menu()
        if row:
            values = self.tree.item(row, "values")
            path = values[-1] if values else ""
            menu.add_command(label="Stage Selected", command=self.stage_selected)
            menu.add_command(label="Unstage Selected", command=self.unstage_selected)
            menu.add_command(label="Discard Selected Changes…", command=self.discard_selected)
            menu.add_separator()
            menu.add_command(label="Show Diff", command=self.show_diff)
            menu.add_command(label="Show Staged Diff", command=self.show_staged_diff)
            menu.add_command(label="Copy File Path", command=lambda: self._copy_context_text(path))
        menu.add_separator()
        menu.add_command(label="Stage All", command=self.stage_all)
        menu.add_command(label="Unstage All", command=self.unstage_all)
        menu.add_command(label="Refresh Changes", command=self.refresh)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _copy_context_text(self, value):
        self.clipboard_clear()
        self.clipboard_append(str(value))

    def _show_entry_context_menu(self, widget, event):
        menu = self._context_menu()
        selected = bool(widget.selection_present())
        menu.add_command(label="Cut", command=lambda: widget.event_generate("<<Cut>>"),
                         state="normal" if selected else "disabled")
        menu.add_command(label="Copy", command=lambda: widget.event_generate("<<Copy>>"),
                         state="normal" if selected else "disabled")
        menu.add_command(label="Paste", command=lambda: widget.event_generate("<<Paste>>"))
        menu.add_command(label="Select All", command=lambda: widget.select_range(0, "end"))
        menu.add_command(label="Clear Message", command=lambda: widget.delete(0, "end"))
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def close(self):
        if self._poll_id is not None:
            try:
                self.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None