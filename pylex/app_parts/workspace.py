"""Workspace responsibilities for the PyLex application."""

# These modules intentionally consume the shared UI dependency namespace.
# ruff: noqa: F403, F405

from ..app_support import *  # noqa: F403
from ..editor_performance import LARGE_FILE_THRESHOLD
from ..file_loading import FileLoadCoordinator
from ..workspace_scan import iter_workspace_entries


class WorkspaceMixin:
    """Workspace UI behavior composed into :class:`PyLexApp`."""

    def mark_dirty(self, editor=None):
        editor = editor or self.editor
        document = self.documents.get(editor)
        if document is not None:
            document["dirty"] = True
            self.editor_tabs.tab(document["frame"], text=self._tab_label(document))
            self._refresh_open_editors()
            if self.editor is editor:
                self._sync_active_document()
                if self.diagnostics:
                    self._set_diagnostics([])
                    self.error_summary.configure(
                        text="Source changed. Run Analyze All to refresh diagnostics."
                    )
        self.document_controller.mark_dirty(editor, True)
        editor.clear_diagnostic()

    def _project_for_document(self, document=None):
        """Resolve a project context for a document or the current workspace."""
        path = document.get("path") if document else None
        return self.workspace_controller.project_for_file(path)

    def _confirm_all_dirty_documents(self):
        """Resolve every modified tab before changing the active workspace."""
        previous = self.editor
        previous_tab = self.editor_tabs.select()
        for editor, document in list(self.documents.items()):
            if not document["dirty"]:
                continue
            self.editor_tabs.select(document["frame"])
            self.editor = editor
            self._sync_active_document()
            answer = messagebox.askyesnocancel(
                "Unsaved Changes",
                f"Save changes to {document['path'].name if document['path'] else 'Untitled'} "
                "before changing the workspace?\\n\\n"
                "Choose No to keep this tab open with its unsaved changes.",
            )
            if answer is None or (answer and not self.save_file()):
                if previous in self.documents:
                    self.editor_tabs.select(self.documents[previous]["frame"])
                    self.editor = previous
                    self._sync_active_document()
                elif previous_tab:
                    self.editor_tabs.select(previous_tab)
                return False
        if previous in self.documents:
            self.editor_tabs.select(self.documents[previous]["frame"])
            self.editor = previous
            self._sync_active_document()
        elif previous_tab:
            self.editor_tabs.select(previous_tab)
        return True

    def _remember_workspace(self, path):
        """Persist active workspace and maintain a bounded recent list."""
        normalized = str(Path(path).expanduser().resolve())
        recent = self.preferences.get("recent_workspaces", [])
        recent = [
            item
            for item in recent
            if isinstance(item, str) and Path(item).expanduser() != Path(normalized)
        ]
        self.preferences["recent_workspaces"] = [normalized] + recent[:7]
        self.preferences["last_workspace"] = normalized
        self._persist_preferences()
        self._refresh_recent_workspace_menu()
        self._refresh_recent_workspace_list()

    def _refresh_recent_workspace_menu(self):
        menu = getattr(self, "recent_workspace_menu", None)
        if menu is None:
            return
        menu.delete(0, "end")
        recent = self.preferences.get("recent_workspaces", [])
        valid = [
            item for item in recent if isinstance(item, str) and Path(item).is_dir()
        ]
        if not valid:
            menu.add_command(label="No recent workspaces", state="disabled")
        else:
            for item in valid:
                menu.add_command(
                    label=Path(item).name + " — " + item,
                    command=lambda value=item: self._activate_workspace(value),
                )
        menu.add_separator()
        menu.add_command(
            label="Clear Recent Workspaces", command=self.clear_recent_workspaces
        )

    def _refresh_recent_workspace_list(self):
        """Compatibility no-op: recent workspaces are accessed from the File menu."""
        return

    def _select_recent_workspace(self, _event=None):
        return

    def _recent_workspace_toolbar_items(self):
        """Build the File toolbar's dynamic, hover-only recent-workspace submenu."""
        recent = [
            value
            for value in self.preferences.get("recent_workspaces", [])
            if isinstance(value, str) and Path(value).is_dir()
        ]
        items = []
        if not recent:
            items.append(("No recent workspaces", None))
        else:
            for value in recent:
                folder = Path(value)
                actions = [
                    (
                        "Open Workspace",
                        lambda target=value: self._activate_workspace(target),
                    ),
                    (
                        "Open in File Manager",
                        lambda target=folder: self._reveal_path(target),
                    ),
                    (
                        "Open Terminal Here",
                        lambda target=folder: self._open_terminal_at(target),
                    ),
                    None,
                    (
                        "Copy Workspace Path",
                        lambda target=value: self._copy_to_clipboard(target),
                    ),
                    (
                        "Remove from Recent",
                        lambda target=value: self._remove_recent_workspace(target),
                    ),
                ]
                items.append(("submenu", folder.name, actions))
        items.extend(
            [
                None,
                ("Open Workspace…", self.open_project_folder),
                ("Clear Recent Workspaces", self.clear_recent_workspaces),
            ]
        )
        return items

    def _show_recent_workspace_menu(self):
        """Show a styled, action-rich recent-workspace picker."""
        menu = self._new_context_menu()
        recent = [
            value
            for value in self.preferences.get("recent_workspaces", [])
            if isinstance(value, str) and Path(value).is_dir()
        ]
        menu.add_command(label="OPEN RECENT WORKSPACE", state="disabled")
        menu.add_separator()
        if not recent:
            menu.add_command(label="No recent workspaces", state="disabled")
        for value in recent:
            folder = Path(value)
            actions = self._new_context_menu()
            actions.add_command(
                label="Open Workspace",
                command=lambda target=value: self._activate_workspace(target),
            )
            actions.add_command(
                label="Open in File Manager",
                command=lambda target=folder: self._reveal_path(target),
            )
            actions.add_command(
                label="Open Terminal Here",
                command=lambda target=folder: self._open_terminal_at(target),
            )
            actions.add_separator()
            actions.add_command(
                label="Copy Workspace Path",
                command=lambda target=value: self._copy_to_clipboard(target),
            )
            actions.add_command(
                label="Remove from Recent",
                command=lambda target=value: self._remove_recent_workspace(target),
            )
            menu.add_cascade(label=folder.name, menu=actions)
        menu.add_separator()
        menu.add_command(label="Open Workspace…", command=self.open_project_folder)
        menu.add_command(
            label="Clear Recent Workspaces",
            command=self.clear_recent_workspaces,
            state="normal" if recent else "disabled",
        )
        x, y = self.winfo_pointerxy()
        menu.tk_popup(x, y)

    def _copy_to_clipboard(self, value):
        self.clipboard_clear()
        self.clipboard_append(str(value))
        self.status.configure(text="Copied to clipboard.")

    def clear_recent_workspaces(self):
        """Clear workspace history without changing the current workspace."""
        self.preferences["recent_workspaces"] = []
        self._persist_preferences()
        self._refresh_recent_workspace_menu()
        self._refresh_recent_workspace_list()
        self.status.configure(text="Recent workspace history cleared.")

    def _activate_workspace(self, folder):
        """Validate and activate a workspace after protecting unsaved documents."""
        try:
            candidate = Project.open(folder)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Workspace Error", str(exc))
            return False
        if self.project is not None and self.project.root == candidate.root:
            self.status.configure(text=f"Workspace already open: {candidate.root}")
            return True
        if not self._confirm_all_dirty_documents():
            self.status.configure(text="Workspace change cancelled.")
            return False
        self._invalidate_file_loads()
        self.workspace_controller.open(candidate)
        self.project_root = candidate.root
        self._remember_workspace(candidate.root)
        self._populate_project_tree()
        self._refresh_recent_workspace_list()
        self.workspace_path_label.configure(text=str(candidate.root))
        self.status.configure(text=f"Workspace opened: {candidate.root}")
        self.git_panel.refresh()
        return True

    def open_project_folder(self):
        """Choose and open a workspace without losing unsaved editor changes."""
        options = {"title": "Open Workspace Folder"}
        if self.project_root and self.project_root.is_dir():
            options["initialdir"] = str(self.project_root)
        folder = filedialog.askdirectory(**options)
        if folder:
            self._activate_workspace(folder)

    def close_workspace(self):
        """Close the active workspace while keeping editor tabs available."""
        if self.project is None:
            self.status.configure(text="No workspace is currently open.")
            return
        if not self._confirm_all_dirty_documents():
            self.status.configure(text="Close workspace cancelled.")
            return
        closed = self.project.root
        self._invalidate_file_loads()
        self.workspace_controller.close()
        self.project_root = None
        self.project_tree.delete(*self.project_tree.get_children())
        self.workspace_path_label.configure(
            text="No folder opened — use Open Folder to start a workspace"
        )
        self.preferences["last_workspace"] = ""
        self._persist_preferences()
        self.status.configure(
            text=f"Workspace closed: {closed}. Open editor tabs were kept."
        )
        self.git_panel.refresh()

    def _restore_last_workspace(self):
        """Restore the most recently used workspace when it still exists."""
        previous = self.preferences.get("last_workspace", "")
        if not previous:
            return
        self.project = self.workspace_controller.restore(previous)
        if self.project is None:
            self.preferences["last_workspace"] = ""
            self._persist_preferences()
            return
        self.project_root = self.project.root
        self._remember_workspace(self.project_root)
        self.workspace_path_label.configure(text=str(self.project_root))
        self._populate_project_tree()
        self._refresh_recent_workspace_list()
        self.git_panel.refresh()

    def refresh_workspace(self):
        """Refresh the workspace tree from disk."""
        if self.project is None:
            self.status.configure(text="Open a folder to create a workspace first.")
            return
        self._populate_project_tree()
        self.status.configure(text="Workspace refreshed.")

    @staticmethod
    def _file_display_name(path):
        info = file_type_for(path)
        return f"{info.icon} {Path(path).name}"

    def _open_external_file(self, path):
        """Open a recognized non-text file with the operating system default app."""
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(path))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(path)])
            else:
                subprocess.Popen(["xdg-open", str(path)])
            self.status.configure(text=f"Opened with system application: {path.name}")
        except (OSError, AttributeError) as exc:
            messagebox.showerror("Open File", f"Could not open {path.name}: {exc}")

    def _select_open_document(self, path):
        resolved = Path(path).resolve()
        editor = self.document_controller.find_path(resolved)
        if editor is not None:
            document = self.documents[editor]
            self.editor_tabs.select(document["frame"])
            self.editor = editor
            self._sync_active_document()
            return True
        return False

    def _open_path(self, path):
        """Open a workspace file, editing text or delegating binary files to the OS."""
        path = Path(path).expanduser().resolve()
        if path.is_dir():
            self._activate_workspace(path)
            return
        if not path.is_file():
            messagebox.showerror("Open File", f"File does not exist: {path}")
            return
        if self._select_open_document(path):
            return
        info = file_type_for(path)
        if not info.is_text:
            self._open_external_file(path)
            return
        try:
            file_size = path.stat().st_size
        except OSError as exc:
            messagebox.showerror("Open Error", f"Could not inspect {path.name}: {exc}")
            return
        if file_size >= LARGE_FILE_THRESHOLD:
            self._load_large_file_async(path, info, file_size)
            return
        try:
            content, encoding, newline = read_text_file_details(path)
        except (OSError, UnicodeError) as exc:
            messagebox.showerror("Open Error", f"Could not read {path.name}: {exc}")
            return
        self._create_document(
            path=path, content=content, encoding=encoding, newline=newline
        )
        self.clear_results()
        self.status.configure(text=f"Opened {path.name} ({info.description}).")

    def _file_load_coordinator(self):
        """Return the UI-thread-owned coordinator for outstanding file loads."""
        coordinator = getattr(self, "_load_coordinator", None)
        if coordinator is None:
            coordinator = FileLoadCoordinator()
            self._load_coordinator = coordinator
        return coordinator

    def _cancel_file_load(self, path):
        """Cancel one pending read and prevent its result from creating a tab."""
        resolved = str(Path(path).expanduser().resolve())
        cancel_events = getattr(self, "_file_load_cancel_events", {})
        cancel_event = cancel_events.pop(resolved, None)
        if cancel_event is not None:
            cancel_event.set()
        coordinator = getattr(self, "_load_coordinator", None)
        if coordinator is not None:
            coordinator.cancel(resolved)
        return cancel_event is not None

    def _invalidate_file_loads(self):
        """Invalidate pending reads and scans when their UI context is leaving."""
        cancel_events = getattr(self, "_file_load_cancel_events", {})
        for cancel_event in cancel_events.values():
            cancel_event.set()
        cancel_events.clear()
        coordinator = getattr(self, "_load_coordinator", None)
        if coordinator is not None:
            coordinator.invalidate()
        self._cancel_workspace_tree_scan()

    def _load_large_file_async(self, path, info, file_size):
        """Read large text files off-thread and ignore results from stale contexts."""
        resolved = str(path.resolve())
        coordinator = self._file_load_coordinator()
        ticket = coordinator.begin(resolved)
        if ticket is None:
            self.status.configure(text=f"Already loading {path.name}…")
            return

        cancel_event = threading.Event()
        cancel_events = getattr(self, "_file_load_cancel_events", {})
        cancel_events[resolved] = cancel_event
        self._file_load_cancel_events = cancel_events

        def clear_cancel_event():
            if cancel_events.get(resolved) is cancel_event:
                cancel_events.pop(resolved, None)

        result_queue = queue.Queue(maxsize=1)
        size_mb = file_size / (1024 * 1024)
        self.status.configure(
            text=f"Loading large file {path.name} ({size_mb:.1f} MB)…"
        )

        def read_file():
            try:
                result_queue.put(
                    (True, read_text_file_details(path, cancel_event=cancel_event))
                )
            except Exception as exc:
                result_queue.put((False, exc))

        threading.Thread(
            target=read_file, name="pylex-file-loader", daemon=True
        ).start()

        def poll_result():
            if not coordinator.is_current(ticket):
                cancel_event.set()
                coordinator.complete(ticket)
                clear_cancel_event()
                return
            try:
                if not self.winfo_exists():
                    cancel_event.set()
                    coordinator.complete(ticket)
                    clear_cancel_event()
                    return
            except tk.TclError:
                cancel_event.set()
                coordinator.complete(ticket)
                clear_cancel_event()
                return

            try:
                succeeded, result = result_queue.get_nowait()
            except queue.Empty:
                try:
                    self.after(40, poll_result)
                except tk.TclError:
                    cancel_event.set()
                    coordinator.complete(ticket)
                    clear_cancel_event()
                return

            coordinator.complete(ticket)
            clear_cancel_event()
            if not succeeded:
                messagebox.showerror(
                    "Open Error", f"Could not read {path.name}: {result}"
                )
                self.status.configure(text=f"Failed to load {path.name}.")
                return
            content, encoding, newline = result
            self._create_document(
                path=path, content=content, encoding=encoding, newline=newline
            )
            self.clear_results()
            self.status.configure(
                text=f"Opened {path.name} in large-file mode ({info.description})."
            )

        try:
            self.after(40, poll_result)
        except tk.TclError:
            cancel_event.set()
            coordinator.complete(ticket)
            clear_cancel_event()

    def _cancel_workspace_tree_scan(self):
        """Stop publishing entries from a scan of a previous workspace."""
        cancel = getattr(self, "_workspace_tree_cancel", None)
        if cancel is not None:
            cancel.set()
        self._workspace_tree_generation = (
            getattr(self, "_workspace_tree_generation", 0) + 1
        )

    def _populate_project_tree(self):
        """Scan workspace files off-thread and insert tree nodes in UI-sized batches."""
        self._cancel_workspace_tree_scan()
        self.project_tree.delete(*self.project_tree.get_children())
        if self.project_root is None:
            return

        root = Path(self.project_root)
        generation = self._workspace_tree_generation
        cancel = threading.Event()
        self._workspace_tree_cancel = cancel
        result_queue = queue.Queue(maxsize=4)
        finished = threading.Event()
        root_id = self.project_tree.insert(
            "",
            "end",
            text=root.name,
            image=self._icon("folder-fill", self.theme_palette.get("accent"), 18),
            values=(str(root), "directory"),
            tags=("directory",),
            open=True,
        )
        node_ids = {"": root_id}

        def scan():
            batch = []
            try:
                for entry in iter_workspace_entries(root):
                    if cancel.is_set():
                        return
                    batch.append(entry)
                    if len(batch) >= 100:
                        while not cancel.is_set():
                            try:
                                result_queue.put(batch, timeout=0.1)
                                batch = []
                                break
                            except queue.Full:
                                continue
                if batch and not cancel.is_set():
                    while not cancel.is_set():
                        try:
                            result_queue.put(batch, timeout=0.1)
                            break
                        except queue.Full:
                            continue
            finally:
                finished.set()

        threading.Thread(
            target=scan, name="pylex-workspace-scanner", daemon=True
        ).start()

        def insert_batch():
            if cancel.is_set() or generation != self._workspace_tree_generation:
                return
            try:
                if not self.winfo_exists():
                    cancel.set()
                    return
            except tk.TclError:
                cancel.set()
                return

            try:
                batch = result_queue.get_nowait()
            except queue.Empty:
                if finished.is_set():
                    return
                try:
                    self.after(25, insert_batch)
                except tk.TclError:
                    cancel.set()
                return

            for parent_rel, name, full_path, kind, is_directory in batch:
                parent_id = node_ids.get(parent_rel)
                if parent_id is None:
                    continue
                if is_directory:
                    node_id = self.project_tree.insert(
                        parent_id,
                        "end",
                        text=name,
                        image=self._icon(
                            "folder", self.theme_palette.get("accent"), 18
                        ),
                        values=(full_path, "directory"),
                        tags=("directory",),
                        open=False,
                    )
                    relative_path = Path(parent_rel) / name
                    node_ids[relative_path.as_posix()] = node_id
                else:
                    icon_color = self.theme_palette.get(
                        f"file_{kind}", self.theme_palette.get("editor_fg")
                    )
                    self.project_tree.insert(
                        parent_id,
                        "end",
                        text=name,
                        image=self._icon(self._file_icon_name(kind), icon_color, 18),
                        values=(full_path, kind),
                        tags=(kind,),
                    )

            try:
                self.after(1, insert_batch)
            except tk.TclError:
                cancel.set()

        try:
            self.after(25, insert_batch)
        except tk.TclError:
            cancel.set()

    def _show_recent_workspace_context_menu(self, event):
        index = self.recent_workspaces_list.nearest(event.y)
        self.recent_workspaces_list.selection_clear(0, "end")
        self.recent_workspaces_list.selection_set(index)
        menu = self._new_context_menu()
        paths = getattr(self, "_recent_workspace_paths", [])
        if index < len(paths):
            path = paths[index]
            menu.add_command(
                label="Open Workspace", command=lambda: self._activate_workspace(path)
            )
            menu.add_command(
                label="Copy Path", command=lambda: self._copy_to_clipboard(path)
            )
            menu.add_command(
                label="Remove from Recent",
                command=lambda: self._remove_recent_workspace(path),
            )
        menu.add_command(
            label="Clear Recent Workspaces", command=self.clear_recent_workspaces
        )
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _remove_recent_workspace(self, path):
        target = os.path.normcase(os.path.abspath(path))
        self.preferences["recent_workspaces"] = [
            p
            for p in self.preferences.get("recent_workspaces", [])
            if os.path.normcase(os.path.abspath(p)) != target
        ]
        self._persist_preferences()
        self._refresh_recent_workspace_menu()
        self._refresh_recent_workspace_list()

    def _show_open_editors_context_menu(self, event):
        index = self.open_editors_list.nearest(event.y)
        editors = list(self.documents)
        menu = self._new_context_menu()
        if index < len(editors):
            editor = editors[index]
            doc = self.documents[editor]
            menu.add_command(
                label="Activate", command=lambda: self.editor_tabs.select(doc["frame"])
            )
            menu.add_command(
                label="Close", command=lambda: self._close_document(editor)
            )
            if doc.get("path"):
                menu.add_command(
                    label="Copy Path",
                    command=lambda: self._copy_to_clipboard(doc["path"]),
                )
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _close_document(self, editor):
        if editor not in self.documents:
            return
        self.editor_tabs.select(self.documents[editor]["frame"])
        self.editor = editor
        self._sync_active_document()
        self.close_tab()

    def _show_tab_context_menu(self, event):
        try:
            index = self.editor_tabs.index("@{},{}".format(event.x, event.y))
        except (tk.TclError, ValueError):
            return "break"
        frame = self.editor_tabs.tabs()[index]
        editor = next(
            (
                item
                for item, doc in self.documents.items()
                if str(doc["frame"]) == frame
            ),
            None,
        )
        if editor is None:
            return "break"
        self.editor_tabs.select(frame)
        self.editor = editor
        menu = self._new_context_menu()
        menu.add_command(label="Close", command=self.close_tab)
        menu.add_command(
            label="Close Others", command=lambda: self._close_other_documents(editor)
        )
        menu.add_command(label="Close All", command=self._close_all_documents)
        path = self.documents[editor].get("path")
        if path:
            menu.add_separator()
            menu.add_command(
                label="Copy Path", command=lambda: self._copy_to_clipboard(path)
            )
            menu.add_command(
                label="Show in File Manager", command=lambda: self._reveal_path(path)
            )
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _close_other_documents(self, keep):
        for editor in list(self.documents):
            if editor is keep:
                continue
            self.editor_tabs.select(self.documents[editor]["frame"])
            self.editor = editor
            self._sync_active_document()
            if not self._confirm():
                return
            self.editor_tabs.forget(self.documents[editor]["frame"])
            self.document_controller.remove(editor)
        self._refresh_open_editors()
        self.editor_tabs.select(self.documents[keep]["frame"])
        self.editor = keep
        self._sync_active_document()

    def _close_all_documents(self):
        for editor in list(self.documents):
            self.editor_tabs.select(self.documents[editor]["frame"])
            self.editor = editor
            self._sync_active_document()
            if not self._confirm():
                return
            self.editor_tabs.forget(self.documents[editor]["frame"])
            self.document_controller.remove(editor)
        self._refresh_open_editors()
        self._create_document()

    def _reveal_path(self, path):
        target = path if Path(path).is_dir() else Path(path).parent
        try:
            if sys.platform.startswith("win"):
                os.startfile(str(target))
            elif sys.platform == "darwin":
                subprocess.Popen(["open", str(target)])
            else:
                subprocess.Popen(["xdg-open", str(target)])
        except OSError as exc:
            messagebox.showerror("Show in File Manager", str(exc), parent=self)

    def _copy_relative_workspace_path(self, path):
        try:
            relative = Path(path).resolve().relative_to(self.project_root.resolve())
        except (ValueError, AttributeError, OSError):
            relative = Path(path)
        self._copy_to_clipboard(str(relative))

    def _open_terminal_at(self, path):
        """Start a terminal session rooted at the selected workspace directory."""
        target = Path(path)
        target = target if target.is_dir() else target.parent
        if not target.is_dir():
            messagebox.showerror(
                "Open Terminal", f"Folder does not exist: {target}", parent=self
            )
            return
        self.tabs.select(self.terminal_panel)
        process = self.terminal_panel.create_session(cwd_override=str(target))
        if process is not None:
            self.status.configure(text=f"Terminal opened at {target}")

    def _show_project_tree_context_menu(self, event):
        row = self.project_tree.identify_row(event.y)
        if not row and self.project_root is not None:
            roots = self.project_tree.get_children("")
            row = roots[0] if roots else ""
        if row:
            self.project_tree.selection_set(row)
            self.project_tree.focus(row)
        values = self.project_tree.item(row, "values") if row else ()
        path = Path(values[0]) if values else self.project_root
        is_root = (
            path is not None
            and self.project_root is not None
            and path == self.project_root
        )
        menu = self._new_context_menu()

        if path is None:
            menu.add_command(label="Open Workspace…", command=self.open_project_folder)
            menu.add_command(
                label="Open Recent Workspaces", command=self._show_recent_workspace_menu
            )
        elif path.is_dir():
            menu.add_command(
                label=(
                    "Collapse Folder"
                    if row and self.project_tree.item(row, "open")
                    else "Expand Folder"
                ),
                command=lambda target=row: self._open_tree_directory(target),
            )
            menu.add_separator()
            menu.add_command(
                label="New File…",
                command=lambda target=path: self._create_tree_item(target, "file"),
            )
            menu.add_command(
                label="New Folder…",
                command=lambda target=path: self._create_tree_item(target, "folder"),
            )
            menu.add_command(
                label="Open Terminal Here",
                command=lambda target=path: self._open_terminal_at(target),
            )
            menu.add_separator()
            menu.add_command(label="Refresh Explorer", command=self.refresh_workspace)
            if is_root:
                menu.add_command(
                    label="Open Recent Workspaces",
                    command=self._show_recent_workspace_menu,
                )
                menu.add_command(label="Close Workspace", command=self.close_workspace)
        else:
            menu.add_command(
                label="Open", command=lambda target=path: self._open_path(target)
            )
            menu.add_command(
                label="Open with System App",
                command=lambda target=path: self._open_external_file(target),
            )
            menu.add_command(
                label="Open Containing Folder",
                command=lambda target=path: self._reveal_path(target),
            )
            menu.add_command(
                label="Open Terminal Here",
                command=lambda target=path: self._open_terminal_at(target),
            )

        if path is not None:
            menu.add_separator()
            menu.add_command(
                label="Copy Path",
                command=lambda target=path: self._copy_to_clipboard(target),
            )
            menu.add_command(
                label="Copy Relative Path",
                command=lambda target=path: self._copy_relative_workspace_path(target),
            )
            menu.add_command(
                label="Show in File Manager",
                command=lambda target=path: self._reveal_path(target),
            )
            if not is_root:
                menu.add_separator()
                menu.add_command(
                    label="Rename…",
                    command=lambda target=path: self._rename_tree_path(target),
                )
                menu.add_command(
                    label="Delete…",
                    command=lambda target=path: self._delete_tree_path(target),
                )
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _open_tree_directory(self, row):
        if row and self.project_tree.exists(row):
            self.project_tree.item(
                row, open=not bool(self.project_tree.item(row, "open"))
            )

    def _create_tree_item(self, directory, kind):
        name = simpledialog.askstring(
            "New " + kind.title(), kind.title() + " name:", parent=self
        )
        if not name or Path(name).name != name or name in {".", ".."}:
            return
        target = directory / name
        try:
            target.mkdir() if kind == "folder" else target.touch(exist_ok=False)
        except OSError as exc:
            messagebox.showerror("Create " + kind.title(), str(exc), parent=self)
            return
        self.refresh_workspace()
        if kind == "file":
            self._open_path(target)

    def _rename_tree_path(self, path):
        name = simpledialog.askstring(
            "Rename", "New name:", initialvalue=path.name, parent=self
        )
        if not name or Path(name).name != name or name in {".", ".."}:
            return
        destination = path.with_name(name)
        was_directory = path.is_dir()
        try:
            path.rename(destination)
        except OSError as exc:
            messagebox.showerror("Rename", str(exc), parent=self)
            return
        for _editor, document in self.documents.items():
            opened = document.get("path")
            if opened and (opened == path or was_directory and path in opened.parents):
                document["path"] = (
                    destination / opened.relative_to(path)
                    if opened != path
                    else destination
                )
                self.editor_tabs.tab(document["frame"], text=self._tab_label(document))
        self._sync_active_document()
        self.refresh_workspace()

    def _delete_tree_path(self, path):
        if any(
            document.get("path")
            and (
                document["path"] == path
                or path.is_dir()
                and path in document["path"].parents
            )
            for document in self.documents.values()
        ):
            messagebox.showwarning(
                "Delete",
                "Close files inside this item before deleting it.",
                parent=self,
            )
            return
        if not messagebox.askyesno(
            "Delete",
            "Delete {!r}? This cannot be undone.".format(path.name),
            parent=self,
        ):
            return
        try:
            shutil.rmtree(path) if path.is_dir() else path.unlink()
        except OSError as exc:
            messagebox.showerror("Delete", str(exc), parent=self)
            return
        self.refresh_workspace()

    def _on_project_tree_open(self, event=None):
        selection = self.project_tree.selection()
        if not selection:
            return
        values = self.project_tree.item(selection[0], "values")
        if not values:
            return
        path = Path(values[0])
        if path.is_dir():
            is_open = bool(self.project_tree.item(selection[0], "open"))
            self.project_tree.item(selection[0], open=not is_open)
            return "break"
        self._open_path(path)
