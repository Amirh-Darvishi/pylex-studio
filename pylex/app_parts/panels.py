"""PanelsMixin responsibilities for the PyLex application."""

# These modules intentionally consume the shared UI dependency namespace.
# ruff: noqa: F403, F405

from ..app_support import *  # noqa: F403


class PanelsMixin:
    """Panels UI behavior composed into :class:`PyLexApp`."""

    def _update_editor_status(self, editor=None):
        """Refresh compact, editor-specific indicators in the bottom status strip."""
        if not hasattr(self, "_editor_status_items"):
            return
        editor = editor or self.editor
        if editor is None or editor not in self.documents:
            values = {
                "position": "Ln 1, Col 1",
                "indent": "Spaces: 4",
                "encoding": "UTF-8",
                "eol": "LF",
                "language": "Plain Text",
                "mode": "INS",
            }
        else:
            line, column = editor.text.index("insert").split(".")
            document = self.documents.get(editor, {})
            path = document.get("path")
            language = file_type_for(path).description if path else "Python"
            encoding = document.get("encoding") or self.preferences.get(
                "status_bar_encoding", "UTF-8"
            )
            encoding_labels = {
                "utf-8": "UTF-8",
                "utf-8-sig": "UTF-8 BOM",
                "ascii": "ASCII",
                "cp1252": "Windows-1252",
            }
            encoding = encoding_labels.get(encoding.lower(), encoding)
            newline = document.get("newline", "\n")
            eol = {"\r\n": "CRLF", "\r": "CR", "\n": "LF"}.get(newline, "LF")
            values = {
                "position": f"Ln {line}, Col {int(column) + 1}",
                "indent": self.preferences.get("status_bar_indent", "Spaces: 4"),
                "encoding": encoding,
                "eol": eol,
                "language": language,
                "mode": "INS",
            }
        values["indent"] = self.preferences.get("status_bar_indent", values["indent"])
        if (
            editor is None
            or editor not in self.documents
            or not self.documents[editor].get("encoding")
        ):
            values["encoding"] = self.preferences.get("status_bar_encoding", "UTF-8")
        eol_mode = self.preferences.get("status_bar_eol", "Auto")
        if eol_mode != "Auto":
            values["eol"] = eol_mode
        for key, value in values.items():
            self._editor_status_items[key].configure(text=value)

    def _apply_status_bar_visibility(self):
        visible = set(
            self.preferences.get("status_bar_items", DEFAULTS["status_bar_items"])
        )
        for label in self._editor_status_items.values():
            label.pack_forget()
        for separator in self._editor_status_separators:
            separator.pack_forget()
        visible_keys = [key for key in self._editor_status_items if key in visible]
        for index, key in enumerate(visible_keys):
            if index:
                self._editor_status_separators[index - 1].pack(
                    side="left", fill="y", padx=2, pady=3
                )
            self._editor_status_items[key].pack(side="left")

    def _configured_indent_string(self):
        value = self.preferences.get("status_bar_indent", "Spaces: 4")
        if value == "Tabs":
            return "\t"
        try:
            width = int(value.split(":", 1)[1].strip())
        except (IndexError, ValueError):
            width = 4
        return " " * max(1, min(8, width))

    def _configure_status_bar(self):
        """Open the inline status-bar context menu; no separate settings window."""
        try:
            x, y = self.winfo_pointerxy()
        except tk.TclError:
            x, y = (
                self.winfo_rootx() + 20,
                self.winfo_rooty() + self.winfo_height() - 24,
            )
        event = type("PointerEvent", (), {"x_root": x, "y_root": y})()
        self._show_status_context_menu(event)

    def _configure_status_item(self, _item):
        self._configure_status_bar()

    def _set_status_item_visible(self, key, visible):
        current = set(
            self.preferences.get("status_bar_items", DEFAULTS["status_bar_items"])
        )
        if visible:
            current.add(key)
        else:
            if len(current) <= 1:
                self.status.configure(
                    text="At least one status item must remain visible."
                )
                return
            current.discard(key)
        order = ("position", "indent", "encoding", "eol", "language", "mode")
        self.preferences["status_bar_items"] = [
            item for item in order if item in current
        ]
        self._persist_preferences()
        self._apply_status_bar_visibility()

    def _set_status_preference(self, key, value):
        self.preferences[key] = value
        if key == "status_bar_indent":
            indent_string = self._configured_indent_string()
            for editor in self.documents:
                editor.indent_string = indent_string
        self._persist_preferences()
        self._update_editor_status()

    def _new_context_menu(self):
        return ContextMenu(
            self,
            palette=self.theme_palette,
            font_family=self._resolved_ui_font(),
            font_size=self.preferences.get("ui_font_size", 9),
        )

    def _show_status_context_menu(self, event):
        menu = self._new_context_menu()
        visible = set(
            self.preferences.get("status_bar_items", DEFAULTS["status_bar_items"])
        )
        menu.add_command(label="Status Bar  ·  Visible Items", state="disabled")
        menu.add_separator()
        labels = (
            ("position", "Cursor Position"),
            ("indent", "Indentation"),
            ("encoding", "Encoding"),
            ("eol", "Line Ending"),
            ("language", "Language Mode"),
            ("mode", "Insert / Overwrite Mode"),
        )
        menu._status_vars = []
        for key, label in labels:
            variable = tk.BooleanVar(self, value=key in visible)
            menu._status_vars.append(variable)
            menu.add_checkbutton(
                label=label,
                variable=variable,
                command=lambda item=key, var=variable: self._set_status_item_visible(
                    item, var.get()
                ),
            )
        menu.add_separator()
        for title, key, values in (
            (
                "Indentation",
                "status_bar_indent",
                ("Spaces: 2", "Spaces: 4", "Spaces: 8", "Tabs"),
            ),
            ("Encoding", "status_bar_encoding", ("UTF-8", "UTF-8 with BOM", "ASCII")),
            ("Line Ending", "status_bar_eol", ("Auto", "LF", "CRLF")),
        ):
            submenu = self._new_context_menu()
            variable = tk.StringVar(self, value=self.preferences.get(key, values[0]))
            menu._status_vars.append(variable)
            for value in values:
                submenu.add_radiobutton(
                    label=value,
                    variable=variable,
                    value=value,
                    command=lambda setting=key, choice=value: self._set_status_preference(
                        setting, choice
                    ),
                )
            menu.add_cascade(label=title, menu=submenu)
        menu.add_separator()
        menu.add_command(label="Reset to Defaults", command=self._reset_status_bar)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _reset_status_bar(self):
        for key in (
            "status_bar_items",
            "status_bar_indent",
            "status_bar_encoding",
            "status_bar_eol",
        ):
            self.preferences[key] = (
                list(DEFAULTS[key]) if key == "status_bar_items" else DEFAULTS[key]
            )
        self._persist_preferences()
        self._apply_status_bar_visibility()
        self._update_editor_status()

    def _show_tree_data_context_menu(self, tree, event):
        row = tree.identify_row(event.y)
        column = tree.identify_column(event.x)
        if row:
            tree.selection_set(row)
            tree.focus(row)
        menu = self._new_context_menu()
        if row:
            values = tree.item(row, "values")
            menu.add_command(
                label="Copy Row",
                command=lambda: self._copy_to_clipboard("  |  ".join(map(str, values))),
            )
            if column and column != "#0":
                index = int(column[1:]) - 1
                if index < len(values):
                    menu.add_command(
                        label="Copy Cell",
                        command=lambda: self._copy_to_clipboard(values[index]),
                    )
            menu.add_command(
                label="Select All",
                command=lambda: tree.selection_set(tree.get_children("")),
            )
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _text_context_menu(self, widget, event):
        menu = self._new_context_menu()
        try:
            selected = bool(widget.tag_ranges("sel"))
        except (tk.TclError, AttributeError):
            selected = False
        menu.add_command(
            label="Copy",
            command=lambda: widget.event_generate("<<Copy>>"),
            state="normal" if selected else "disabled",
        )
        menu.add_command(
            label="Select All", command=lambda: widget.tag_add("sel", "1.0", "end-1c")
        )
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _text_panel(self, title):
        frame = ttk.Frame(self.tabs)
        row = 0
        if title == "Output":
            actions = ttk.Frame(frame, padding=(4, 3))
            actions.grid(row=0, column=0, columnspan=2, sticky="ew")
            ttk.Button(actions, text="Clear Output", command=self.clear_output).pack(
                side="left", padx=2
            )
            ttk.Button(actions, text="Save Output...", command=self.save_output).pack(
                side="left", padx=2
            )
            ttk.Button(
                actions, text="Force Stop Run", command=self.stop_execution
            ).pack(side="left", padx=2)
            ttk.Button(actions, text="Stop Debugger", command=self.stop_debugging).pack(
                side="left", padx=2
            )
            row = 1
        text = tk.Text(frame, wrap="none", font=("Consolas", 10), height=8)
        text.tag_configure("stderr", foreground="#d9534f")
        text.tag_configure("stdout", foreground="#5b9b68")
        text.tag_configure("system", foreground="#4b83c3")
        text.bind(
            "<Button-3>",
            lambda event, widget=text: self._text_context_menu(widget, event),
            add="+",
        )
        # Text widgets retain native wheel/keyboard scrolling without visible bars.
        text.bind(
            "<Shift-MouseWheel>",
            lambda event: (
                text.xview_scroll(-int(event.delta / 120) * 3, "units"),
                "break",
            ),
            add="+",
        )
        text.grid(row=row, column=0, columnspan=2, sticky="nsew")
        frame.rowconfigure(row, weight=1)
        frame.columnconfigure(0, weight=1)
        if title == "Output":
            input_row = ttk.Frame(frame, padding=(4, 4))
            input_row.grid(row=row + 1, column=0, columnspan=2, sticky="ew")
            ttk.Label(input_row, text="Program Input").pack(side="left", padx=(2, 7))
            self.output_input = ttk.Entry(input_row)
            self.output_input.pack(side="left", fill="x", expand=True)
            self.output_input.bind("<Return>", self._send_output_input)
            ttk.Button(input_row, text="Send", command=self._send_output_input).pack(
                side="left", padx=(6, 2)
            )
        panel_icons = {
            "Output": ("terminal", "accent"),
            "Lexical Analysis": ("braces", "violet"),
            "Syntax Analysis": ("check-circle", "success"),
        }
        icon_name, color_key = panel_icons.get(title, ("file-earmark-text", "muted"))
        self._add_tool_tab(frame, title, icon_name, color_key)
        return text

    def _terminal_context(self):
        """Return the current workspace, environment, and selected interpreter."""
        document = self._active_document()
        path = document.get("path") if document else self.current_path
        try:
            project = self._project_for_document(document)
        except (OSError, ValueError):
            project = self.project
        cwd = (
            project.working_directory_for(path)
            if project
            else (Path(path).expanduser().resolve().parent if path else Path.cwd())
        )
        env = project.execution_environment() if project else dict(os.environ)
        if path:
            env["PYLEX_ACTIVE_FILE"] = str(Path(path).expanduser().resolve())
        else:
            env.pop("PYLEX_ACTIVE_FILE", None)
        if project:
            env["PYLEX_WORKSPACE_ROOT"] = str(project.root)
        try:
            interpreter = self._interpreter_for_project(project).executable
        except (OSError, ValueError, TimeoutError):
            interpreter = sys.executable
        return cwd, env, interpreter

    def _quality_context(self):
        """Return the active workspace root, interpreter, and import environment."""
        document = self._active_document()
        project = self._project_for_document(document)
        info = self._interpreter_for_project(project)
        env = project.execution_environment()
        executable_dir = Path(info.executable).parent
        if executable_dir.name.lower() in {"scripts", "bin"}:
            env["VIRTUAL_ENV"] = str(executable_dir.parent)
            env["PATH"] = str(executable_dir) + os.pathsep + env.get("PATH", "")
        return project.root, info.executable, env

    def _quality_document(self):
        """Snapshot the active editor so async formatting cannot target another tab."""
        document = self._active_document()
        return (
            self.editor,
            document.get("path") if document else None,
            self.editor.get_content(),
        )

    def _apply_formatted_source(self, editor, source):
        """Apply Black output only to the editor that initiated the request."""
        if editor not in self.documents:
            self.status.configure(
                text="Formatted output discarded: the originating tab was closed."
            )
            return
        widget = editor.text
        try:
            cursor = int(widget.count("1.0", "insert", "chars")[0])
        except (TypeError, IndexError):
            cursor = 0
        widget.edit_separator()
        widget.delete("1.0", "end")
        widget.insert("1.0", source)
        widget.mark_set("insert", f"1.0+{min(cursor, len(source))}c")
        widget.edit_separator()
        widget.edit_modified(False)
        self.mark_dirty(editor)
        editor.highlight()
        self.status.configure(
            text="Current editor buffer formatted with Black. Save to keep the changes."
        )

    def _navigate_quality_diagnostic(self, diagnostic):
        """Open the reported file and navigate to the Ruff diagnostic location."""
        raw_path = diagnostic.get("path", "")
        if not raw_path or raw_path == "<stdin>":
            self.status.configure(text="Ruff diagnostic has no navigable file path.")
            return
        path = Path(raw_path)
        if not path.is_absolute():
            path = self._project_for_document(self._active_document()).root / path
        path = path.resolve()
        target = None
        for editor, document in self.documents.items():
            if (
                document.get("path") is not None
                and Path(document["path"]).resolve() == path
            ):
                target = editor
                self.editor_tabs.select(document["frame"])
                break
        if target is None:
            if not path.is_file():
                self.status.configure(text=f"Diagnostic file no longer exists: {path}")
                return
            self._open_path(path)
            target = self.editor
        target.show_diagnostic(
            diagnostic.get("line", 1),
            max(0, diagnostic.get("column", 1) - 1),
            diagnostic.get("end_line"),
            diagnostic.get("end_column"),
        )
        self.status.configure(
            text=f"{diagnostic.get('code', 'Ruff')} — {path.name}:{diagnostic.get('line', 1)}"
        )

    def _can_format_project(self):
        """Protect unsaved editor buffers from whole-project formatting."""
        if any(document["dirty"] for document in self.documents.values()):
            messagebox.showwarning(
                "Format Project",
                "Save or close all modified editor tabs before formatting the whole project. "
                "This prevents unsaved buffers from conflicting with files changed on disk.",
                parent=self,
            )
            return False
        return True

    def open_quality_tools(self):
        """Show the integrated formatter, linter, and test explorer."""
        self.tabs.select(self.quality_panel)

    def open_git_tools(self):
        """Show Git status, staging, commits, branches, and remote controls."""
        self.tabs.select(self.git_panel)
        self.git_panel.refresh()

    def _save_terminal_shell(self, shell):
        self.preferences["terminal_shell"] = shell
        self._persist_preferences()

    def open_terminal(self):
        """Open a shell in the active document's workspace context."""
        self.tabs.select(self.terminal_panel)
        cwd, _env, _interpreter = self._terminal_context()
        desired_cwd = Path(cwd).expanduser().resolve()
        document = self._active_document()
        active_path = document.get("path") if document else self.current_path
        desired_file = Path(active_path).expanduser().resolve() if active_path else None
        frame = self.terminal_panel._current_frame()
        session = self.terminal_panel.sessions.get(frame)
        if (
            session is None
            or not session.running
            or session.cwd != desired_cwd
            or getattr(session, "active_file", None) != desired_file
        ):
            return self.terminal_panel.create_session(cwd_override=desired_cwd)
        view = self.terminal_panel.views.get(frame)
        if view:
            view["entry"].focus_set()
        return session

    def _dependencies_panel(self):
        frame = ttk.Frame(self.tabs, padding=4)
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=(0, 4))
        ttk.Button(
            actions, text="Scan Current File", command=self.scan_dependencies
        ).pack(side="left")
        ttk.Button(
            actions, text="Python Interpreter...", command=self.manage_interpreter
        ).pack(side="left", padx=4)
        ttk.Button(
            actions,
            text="Copy Python Install Command",
            command=self.copy_install_command,
        ).pack(side="left", padx=4)
        self.dependency_environment = ttk.Label(
            frame, text="Python environment: not scanned"
        )
        self.dependency_environment.pack(fill="x", pady=(2, 5))
        columns = ("module", "status", "distribution", "version")
        self.dependency_tree = ttk.Treeview(
            frame, columns=columns, show="headings", height=7
        )
        for key, label in (
            ("module", "Import"),
            ("status", "Status"),
            ("distribution", "Package / Source"),
            ("version", "Version"),
        ):
            self.dependency_tree.heading(key, text=label)
        self.dependency_tree.column("module", width=150)
        self.dependency_tree.column("status", width=100, anchor="center")
        self.dependency_tree.column("distribution", width=220)
        self.dependency_tree.column("version", width=170)
        self.dependency_tree.pack(fill="both", expand=True)
        self.dependency_tree.bind(
            "<Button-3>",
            lambda event, tree=self.dependency_tree: self._show_tree_data_context_menu(
                tree, event
            ),
            add="+",
        )
        self.dependency_tree.tag_configure("missing", foreground="#d9534f")
        self.dependency_tree.tag_configure("installed", foreground="#5b9b68")
        self._add_tool_tab(frame, "Dependencies", "boxes", "warning")

    def _interpreter_for_project(self, project=None):
        """Resolve project override, local .venv, global setting, or current Python."""
        root = project.root if project is not None else None
        mapping = self.preferences.get("project_interpreters", {})
        selected = mapping.get(str(root)) if root is not None else None
        if selected:
            return probe_interpreter(selected)
        if root is not None:
            detected = find_project_environment(root)
            if detected is not None:
                return detected
        return probe_interpreter(
            self.preferences.get("interpreter_path") or sys.executable
        )

    def manage_interpreter(self):
        """Select a verified Python interpreter for this workspace or globally."""
        project = self._project_for_document(self._active_document())
        warning = None
        try:
            current = self._interpreter_for_project(project)
        except (OSError, ValueError, TimeoutError) as exc:
            warning = str(exc)
            current = probe_interpreter(sys.executable)
        dialog = tk.Toplevel(self)
        dialog.title("Python Interpreter")
        dialog.transient(self)
        dialog.resizable(True, False)
        body = ttk.Frame(dialog, padding=12)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Workspace: " + str(project.root)).grid(
            row=0, column=0, columnspan=3, sticky="w"
        )
        ttk.Label(body, text="Interpreter").grid(row=1, column=0, sticky="w", pady=6)
        status = ttk.Label(body, text=current.executable)
        status.grid(row=2, column=0, columnspan=3, sticky="w", pady=6)
        if warning:
            status.configure(
                text="Saved interpreter is unavailable: "
                + warning
                + " — choose a replacement."
            )
        entries = {}
        choice = tk.StringVar(value=current.label)
        combo = ttk.Combobox(body, textvariable=choice, state="readonly", width=82)
        combo.grid(row=1, column=1, sticky="ew", padx=5)
        body.columnconfigure(1, weight=1)

        def add(info, select=False):
            entries[info.label] = info
            values = list(combo.cget("values"))
            if info.label not in values:
                values.append(info.label)
                combo.configure(values=values)
            if select:
                choice.set(info.label)

        add(current, select=True)
        status.configure(
            text="Scanning installed Python interpreters in the background..."
        )
        discovery_queue = queue.Queue()

        def discovery_worker():
            try:
                discovery_queue.put(("ok", discover_interpreters()))
            except Exception as exc:
                discovery_queue.put(("error", exc))

        threading.Thread(target=discovery_worker, daemon=True).start()

        def poll_discovery():
            if not dialog.winfo_exists():
                return
            try:
                kind, value = discovery_queue.get_nowait()
            except queue.Empty:
                dialog.after(120, poll_discovery)
                return
            if kind == "error":
                status.configure(text="Interpreter discovery warning: " + str(value))
                return
            for info in value:
                add(info)
            add(current, select=True)
            status.configure(
                text="Found " + str(len(value)) + " verified Python interpreter(s)."
            )

        dialog.after(120, poll_discovery)

        def browse():
            path = filedialog.askopenfilename(
                parent=dialog,
                title="Select Python",
                filetypes=[
                    ("Python executable", "*.exe" if os.name == "nt" else "python*"),
                    ("All files", "*.*"),
                ],
            )
            if path:
                try:
                    add(probe_interpreter(path), select=True)
                except (OSError, ValueError, TimeoutError) as exc:
                    messagebox.showerror("Invalid Python", str(exc), parent=dialog)

        ttk.Button(body, text="Browse...", command=browse).grid(row=1, column=2)

        def selected():
            info = entries.get(choice.get())
            if info is None:
                raise ValueError("Choose a verified Python interpreter.")
            return info

        def apply(scope):
            try:
                info = selected()
            except ValueError as exc:
                messagebox.showerror("Python Interpreter", str(exc), parent=dialog)
                return
            if scope == "project":
                mapping = dict(self.preferences.get("project_interpreters", {}))
                mapping[str(project.root)] = info.executable
                self.preferences["project_interpreters"] = mapping
            else:
                self.preferences["interpreter_path"] = info.executable
            self._persist_preferences()
            self.status.configure(text="Python " + info.version + " selected.")
            dialog.destroy()

        def reset():
            mapping = dict(self.preferences.get("project_interpreters", {}))
            mapping.pop(str(project.root), None)
            self.preferences["project_interpreters"] = mapping
            self._persist_preferences()
            self.status.configure(
                text="Workspace interpreter set to automatic detection."
            )
            dialog.destroy()

        def repair_pip():
            try:
                base = selected()
            except ValueError as exc:
                messagebox.showerror("Repair pip", str(exc), parent=dialog)
                return
            repair_button.configure(state="disabled")
            status.configure(
                text="Checking and repairing pip in the selected interpreter..."
            )
            result = queue.Queue()

            def worker():
                try:
                    ensure_pip(base.executable)
                    result.put(("ok", probe_interpreter(base.executable)))
                except Exception as exc:
                    result.put(("error", exc))

            threading.Thread(target=worker, daemon=True).start()

            def poll_repair():
                try:
                    kind, value = result.get_nowait()
                except queue.Empty:
                    if dialog.winfo_exists():
                        dialog.after(100, poll_repair)
                    return
                if not dialog.winfo_exists():
                    return
                repair_button.configure(state="normal")
                if kind == "error":
                    status.configure(text="pip repair failed.")
                    messagebox.showerror("Repair pip", str(value), parent=dialog)
                    return
                add(value, select=True)
                status.configure(text="pip is available: " + value.executable)

            dialog.after(100, poll_repair)

        def create_env():
            try:
                base = selected()
            except ValueError as exc:
                messagebox.showerror("Create .venv", str(exc), parent=dialog)
                return
            target = project.root / ".venv"
            if target.exists() and (not target.is_dir() or any(target.iterdir())):
                messagebox.showerror(
                    "Create .venv",
                    "The .venv folder already exists and is not empty.",
                    parent=dialog,
                )
                return
            create_button.configure(state="disabled")
            status.configure(text="Creating project virtual environment...")
            result = queue.Queue()

            def worker():
                try:
                    result.put(
                        ("ok", create_virtual_environment(base.executable, target))
                    )
                except Exception as exc:
                    result.put(("error", exc))

            threading.Thread(target=worker, daemon=True).start()

            def poll():
                try:
                    kind, value = result.get_nowait()
                except queue.Empty:
                    if dialog.winfo_exists():
                        dialog.after(100, poll)
                    return
                if not dialog.winfo_exists():
                    return
                create_button.configure(state="normal")
                if kind == "error":
                    status.configure(text="Environment creation failed.")
                    messagebox.showerror("Create .venv", str(value), parent=dialog)
                    return
                add(value, select=True)
                mapping = dict(self.preferences.get("project_interpreters", {}))
                mapping[str(project.root)] = value.executable
                self.preferences["project_interpreters"] = mapping
                self._persist_preferences()
                status.configure(text="Created and selected " + value.executable)
                self.status.configure(text="Project virtual environment created.")

            dialog.after(100, poll)

        buttons = ttk.Frame(body)
        buttons.grid(row=3, column=0, columnspan=3, sticky="ew", pady=10)
        ttk.Button(
            buttons, text="Use for Workspace", command=lambda: apply("project")
        ).pack(side="left", padx=3)
        ttk.Button(buttons, text="Use Globally", command=lambda: apply("global")).pack(
            side="left", padx=3
        )
        ttk.Button(buttons, text="Auto Detect", command=reset).pack(side="left", padx=3)
        repair_button = ttk.Button(buttons, text="Repair pip", command=repair_pip)
        repair_button.pack(side="left", padx=3)
        create_button = ttk.Button(
            buttons, text="Create Project .venv", command=create_env
        )
        create_button.pack(side="left", padx=3)
        ttk.Button(buttons, text="Close", command=dialog.destroy).pack(
            side="right", padx=3
        )

    def _update_dependency_view(
        self, dependencies, scan_error=None, python_executable=None
    ):
        for item in self.dependency_tree.get_children():
            self.dependency_tree.delete(item)
        for dependency in dependencies:
            version = dependency.version or (
                "—" if dependency.status != "missing" else "Not installed"
            )
            self.dependency_tree.insert(
                "",
                "end",
                values=(
                    dependency.import_name,
                    dependency.status,
                    dependency.distribution,
                    version,
                ),
                tags=(dependency.status,),
            )
        env = python_environment(
            python_executable
            or self._interpreter_for_project(
                self._project_for_document(self._active_document())
            ).executable
        )
        mode = "venv" if env["virtual_environment"] else "base interpreter"
        message = f"Python {env['version']} ({mode}, pip {'available' if env['pip_available'] else 'missing'}) — {env['executable']}"
        if scan_error:
            message += " | " + scan_error
        self.dependency_environment.configure(text=message)

    def scan_dependencies(self):
        document = self._active_document()
        root = self._project_for_document(document).root
        try:
            interpreter = self._interpreter_for_project(
                self._project_for_document(document)
            )
        except (OSError, ValueError, TimeoutError) as exc:
            self.status.configure(text=f"Python interpreter error: {exc}")
            return
        dependencies, error = inspect_dependencies(
            self.editor.get_content(),
            search_root=root,
            python_executable=interpreter.executable,
        )
        self._update_dependency_view(dependencies, error, interpreter.executable)
        self.tabs.select(self.dependency_tree.master)
        missing = sum(item.status == "missing" for item in dependencies)
        self.status.configure(
            text=(
                f"Dependency scan complete — {len(dependencies)} imports, {missing} missing."
                if not error
                else "Dependency scan needs valid Python syntax."
            )
        )

    def copy_install_command(self):
        selected = self.dependency_tree.selection()
        if not selected:
            self.status.configure(text="Select a missing dependency first.")
            return
        values = self.dependency_tree.item(selected[0], "values")
        if values[1] != "missing":
            self.status.configure(text="The selected dependency is not missing.")
            return
        try:
            interpreter = self._interpreter_for_project(
                self._project_for_document(self._active_document())
            )
        except (OSError, ValueError, TimeoutError) as exc:
            self.status.configure(text=f"Python interpreter error: {exc}")
            return
        env = python_environment(interpreter.executable)
        command = f'"{env["executable"]}" -m pip install "{values[2]}"'
        self.clipboard_clear()
        self.clipboard_append(command)
        self.status.configure(text="Interpreter-specific install command copied.")

    def _errors_panel(self):
        frame = ttk.Frame(self.tabs, padding=4)
        self.error_summary = ttk.Label(frame, text="No diagnostics.")
        self.error_summary.pack(fill="x", pady=(0, 4))
        columns = ("type", "line", "column", "message", "source")
        self.error_tree = ttk.Treeview(
            frame, columns=columns, show="headings", height=7
        )
        self.error_tree.heading("type", text="Type")
        self.error_tree.heading("line", text="Line")
        self.error_tree.heading("column", text="Column")
        self.error_tree.heading("message", text="Message")
        self.error_tree.heading("source", text="Source Line")
        self.error_tree.column("type", width=125, stretch=False)
        self.error_tree.column("line", width=48, anchor="center", stretch=False)
        self.error_tree.column("column", width=58, anchor="center", stretch=False)
        self.error_tree.column("message", width=330)
        self.error_tree.column("source", width=360)
        self.error_tree.pack(fill="both", expand=True)
        self.error_tree.bind(
            "<Button-3>",
            lambda event, tree=self.error_tree: self._show_tree_data_context_menu(
                tree, event
            ),
            add="+",
        )
        self.error_tree.tag_configure("error", foreground="#ef6b73")
        self.error_tree.tag_configure("warning", foreground="#e6b45a")
        self.error_tree.tag_configure("info", foreground="#4f8cff")
        self.error_tree.bind("<<TreeviewSelect>>", self._navigate_to_selected_error)
        self.error_tree.bind("<Double-1>", self._navigate_to_selected_error)
        self._add_tool_tab(frame, "Problems", "exclamation-triangle", "danger")

    def _show(self, panel, content):
        panel.configure(state="normal")
        panel.delete("1.0", "end")
        panel.insert("1.0", content)
        panel.configure(state="disabled")
        self.tabs.select(panel.master)

    def _set_diagnostics(self, diagnostics):
        self.diagnostics = list(diagnostics)
        self.editor.clear_diagnostic()
        for item in self.error_tree.get_children():
            self.error_tree.delete(item)
        for index, diagnostic in enumerate(self.diagnostics):
            severity = (
                "warning"
                if "warning" in diagnostic.error_type.lower()
                else "info" if "info" in diagnostic.error_type.lower() else "error"
            )
            self.error_tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    diagnostic.error_type,
                    diagnostic.line,
                    diagnostic.column + 1,
                    diagnostic.message,
                    diagnostic.source_line.strip(),
                ),
                tags=(severity,),
            )
        count = len(self.diagnostics)
        self.error_summary.configure(
            text=(
                f"{count} diagnostic(s) found. Select or double-click an item to jump to its location."
                if count
                else "No diagnostics. The current source passed lexical and syntax checks."
            )
        )

    def _navigate_to_selected_error(self, event=None):
        selection = self.error_tree.selection()
        if not selection:
            return
        try:
            diagnostic = self.diagnostics[int(selection[0])]
        except (ValueError, IndexError):
            return
        self.editor.show_diagnostic(
            diagnostic.line,
            diagnostic.column,
            diagnostic.end_line,
            diagnostic.end_column,
        )
        self.status.configure(
            text=f"{diagnostic.error_type} — line {diagnostic.line}, column {diagnostic.column + 1}"
        )

    def _refresh_diagnostics(self):
        diagnostics = collect_diagnostics(self.editor.get_content())
        self._set_diagnostics(diagnostics)
        return diagnostics
