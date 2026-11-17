"""Preferences responsibilities for the PyLex application."""

# These modules intentionally consume the shared UI dependency namespace.
# ruff: noqa: F403, F405

from ..app_support import *  # noqa: F403


class PreferencesMixin:
    """Preferences UI behavior composed into :class:`PyLexApp`."""

    def find_replace(self):
        """Open a compact find-and-replace dialog for the active editor."""
        dialog = tk.Toplevel(self)
        dialog.title("Find and Replace")
        dialog.transient(self)
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=10)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="Find").grid(row=0, column=0, sticky="w", pady=3)
        find_entry = ttk.Entry(body, width=34)
        find_entry.grid(row=0, column=1, columnspan=3, sticky="ew", pady=3)
        ttk.Label(body, text="Replace").grid(row=1, column=0, sticky="w", pady=3)
        replace_entry = ttk.Entry(body, width=34)
        replace_entry.grid(row=1, column=1, columnspan=3, sticky="ew", pady=3)
        status = ttk.Label(body, text="")
        status.grid(row=2, column=0, columnspan=4, sticky="w", pady=4)

        def find_next():
            needle = find_entry.get()
            if not needle:
                status.configure(text="Enter text to find.")
                return
            text_widget = self.editor.text
            start = text_widget.index("insert")
            match = text_widget.search(needle, start, stopindex="end")
            if not match:
                match = text_widget.search(needle, "1.0", stopindex=start)
            if match:
                end = "{}+{}c".format(match, len(needle))
                text_widget.tag_remove("sel", "1.0", "end")
                text_widget.tag_add("sel", match, end)
                text_widget.mark_set("insert", end)
                text_widget.see(match)
                text_widget.focus_set()
                status.configure(text="Match found.")
            else:
                status.configure(text="No matches found.")

        def replace_one():
            needle = find_entry.get()
            if not needle:
                return
            text_widget = self.editor.text
            try:
                selected = text_widget.get("sel.first", "sel.last")
            except tk.TclError:
                selected = ""
            if selected == needle:
                text_widget.delete("sel.first", "sel.last")
                text_widget.insert("insert", replace_entry.get())
                status.configure(text="One occurrence replaced.")
            find_next()

        def replace_all():
            needle = find_entry.get()
            if not needle:
                return
            text_widget = self.editor.text
            count = 0
            position = "1.0"
            while True:
                match = text_widget.search(needle, position, stopindex="end")
                if not match:
                    break
                end = "{}+{}c".format(match, len(needle))
                text_widget.delete(match, end)
                text_widget.insert(match, replace_entry.get())
                position = "{}+{}c".format(match, len(replace_entry.get()))
                count += 1
            status.configure(text="{} occurrence(s) replaced.".format(count))

        ttk.Button(body, text="Find Next", command=find_next).grid(
            row=3, column=1, sticky="ew", padx=2
        )
        ttk.Button(body, text="Replace", command=replace_one).grid(
            row=3, column=2, sticky="ew", padx=2
        )
        ttk.Button(body, text="Replace All", command=replace_all).grid(
            row=3, column=3, sticky="ew", padx=2
        )
        find_entry.focus_set()
        dialog.bind("<Return>", lambda _event: find_next())

    def zoom(self, delta):
        self.preferences["font_size"] = max(7, min(40, self.editor.font_size + delta))
        for editor in self.documents:
            editor.set_font_size(self.preferences["font_size"])
        self._persist_preferences()
        self.status.configure(text=f"Editor font size: {self.preferences['font_size']}")

    def _persist_preferences(self):
        try:
            save_preferences(self.preferences)
        except OSError as exc:
            self.status.configure(text=f"Could not save preferences: {exc}")

    def toggle_project_explorer(self):
        visible = bool(self.preferences["show_project_explorer"])
        if visible:
            self.workspace.forget(self.explorer_frame)
        else:
            self.workspace.insert(0, self.explorer_frame, weight=1)
        self.preferences["show_project_explorer"] = not visible
        self._persist_preferences()

    def open_preferences(self, initial_tab=None):
        """Open a structured, resizable preferences window."""
        dialog = tk.Toplevel(self)
        dialog.title("PyLex Studio — Settings")
        dialog.transient(self)
        dialog.geometry("960x700")
        dialog.minsize(820, 600)
        dialog.resizable(True, True)

        shell = ttk.Frame(dialog, padding=16)
        shell.pack(fill="both", expand=True)
        ttk.Label(shell, text="Settings", style="PyLex.DialogTitle.TLabel").pack(
            anchor="w", pady=(0, 2)
        )
        ttk.Label(
            shell,
            text="Personalize the editor and workspace experience.",
            style="PyLex.Muted.TLabel",
        ).pack(anchor="w", pady=(0, 12))

        notebook = ttk.Notebook(shell)
        notebook.pack(fill="both", expand=True)

        appearance = ttk.Frame(notebook, padding=16)
        editor_page = ttk.Frame(notebook, padding=16)
        workspace_page = ttk.Frame(notebook, padding=16)
        execution_page = ttk.Frame(notebook, padding=16)
        help_page = ttk.Frame(notebook, padding=16)
        languages_page = ttk.Frame(notebook, padding=16)
        productivity_page = ttk.Frame(notebook, padding=16)
        extensions_page = ttk.Frame(notebook, padding=16)
        security_page = ttk.Frame(notebook, padding=16)
        pages = (
            (appearance, "Appearance"),
            (editor_page, "Editor"),
            (workspace_page, "Workspace"),
            (execution_page, "Execution"),
            (productivity_page, "Productivity"),
            (languages_page, "Languages"),
            (extensions_page, "Extensions"),
            (security_page, "Privacy & Security"),
            (help_page, "Help"),
        )
        for page, label in pages:
            notebook.add(page, text=label)
        if initial_tab == "help":
            notebook.select(help_page)

        ttk.Label(
            languages_page,
            text="Language roadmap",
            style="PyLex.DialogTitle.TLabel",
        ).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            languages_page,
            text="The workspace already recognizes common web file types. Full syntax highlighting, "
            "language-aware editing and analysis will be enabled incrementally in a later release.",
            style="PyLex.Muted.TLabel",
            wraplength=560,
        ).pack(anchor="w", pady=(0, 14))
        for name, status, color_key, description in (
            (
                "Python",
                "Available now",
                "success",
                "Editing, highlighting, analysis, execution and debugging",
            ),
            (
                "JavaScript",
                "Planned",
                "warning",
                "Dedicated lexer, completion and diagnostics",
            ),
            (
                "HTML",
                "Planned",
                "warning",
                "Markup highlighting and document-aware editing",
            ),
            (
                "CSS",
                "Planned",
                "warning",
                "Stylesheet highlighting and language-aware tooling",
            ),
        ):
            row = ttk.Frame(languages_page, padding=(10, 8))
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=name, style="PyLex.Field.TLabel", width=16).pack(
                side="left"
            )
            ttk.Label(
                row, text=status, foreground=self.theme_palette[color_key], width=14
            ).pack(side="left")
            ttk.Label(row, text=description, style="PyLex.Muted.TLabel").pack(
                side="left", padx=(8, 0)
            )

        ttk.Label(
            productivity_page,
            text="Keyboard-first workflow",
            style="PyLex.DialogTitle.TLabel",
        ).pack(anchor="w", pady=(0, 8))
        shortcut_rows = (
            ("Command Palette", "Ctrl+Shift+P", "Search available commands"),
            ("Quick Open", "Ctrl+P", "Find a workspace file by name"),
            ("Run Current File", "F5", "Execute the active Python file"),
            ("Stop Execution", "Shift+F5", "Stop the active run"),
            ("Start Debugging", "Ctrl+F5", "Start a debugger session"),
            ("Toggle Breakpoint", "F9", "Set or remove a breakpoint"),
            ("Step Over / Into", "F10 / F11", "Move through the current debug session"),
            ("Analyze All", "F6", "Run lexical and syntax analysis"),
            ("Settings", "Ctrl+,", "Open application preferences"),
        )
        for command, shortcut, description in shortcut_rows:
            row = ttk.Frame(productivity_page, padding=(10, 8))
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=command, style="PyLex.Field.TLabel", width=24).pack(
                side="left"
            )
            ttk.Label(
                row, text=shortcut, foreground=self.theme_palette["accent"], width=20
            ).pack(side="left")
            ttk.Label(row, text=description, style="PyLex.Muted.TLabel").pack(
                side="left", padx=(8, 0)
            )

        ttk.Label(
            extensions_page,
            text="Extensibility roadmap",
            style="PyLex.DialogTitle.TLabel",
        ).pack(anchor="w", pady=(0, 8))
        ttk.Label(
            extensions_page,
            text="These are planned product capabilities, not active integrations. "
            "They will be introduced only with compatibility checks, clear permissions and tests.",
            style="PyLex.Muted.TLabel",
            wraplength=720,
        ).pack(anchor="w", pady=(0, 12))
        for name, state, detail in (
            ("Language packs", "Planned", "JavaScript, HTML and CSS language services"),
            (
                "Extension marketplace",
                "Planned",
                "Signed or trusted extensions with permission review",
            ),
            (
                "Language servers",
                "Planned",
                "LSP-based completion, navigation and diagnostics",
            ),
            (
                "Themes and icon packs",
                "Planned",
                "Validated third-party visual themes and icon sets",
            ),
            (
                "Project templates",
                "Planned",
                "Reusable starter projects and configurable scaffolding",
            ),
            (
                "Plugin API",
                "Planned",
                "Documented extension points with versioned compatibility",
            ),
        ):
            row = ttk.Frame(extensions_page, padding=(10, 8))
            row.pack(fill="x", pady=3)
            ttk.Label(row, text=name, style="PyLex.Field.TLabel", width=24).pack(
                side="left"
            )
            ttk.Label(
                row, text=state, foreground=self.theme_palette["warning"], width=13
            ).pack(side="left")
            ttk.Label(row, text=detail, style="PyLex.Muted.TLabel").pack(
                side="left", padx=(8, 0)
            )

        ttk.Label(
            security_page,
            text="Security and privacy",
            style="PyLex.DialogTitle.TLabel",
        ).pack(anchor="w", pady=(0, 8))
        for heading, detail in (
            (
                "Local-first preferences",
                "Account display name and application preferences are stored locally.",
            ),
            (
                "Code execution",
                "Programs run with your operating-system permissions. PyLex Studio is not a security sandbox.",
            ),
            (
                "External integrations",
                "Cloud sync, telemetry and GitHub sign-in are not enabled by the current account screen.",
            ),
            (
                "Future extension permissions",
                "Planned extensions must declare capabilities and request user consent before accessing protected workflows.",
            ),
        ):
            card = ttk.Frame(security_page, padding=10)
            card.pack(fill="x", pady=4)
            ttk.Label(card, text=heading, style="PyLex.Field.TLabel").pack(anchor="w")
            ttk.Label(
                card, text=detail, style="PyLex.Muted.TLabel", wraplength=720
            ).pack(anchor="w", pady=(4, 0))

        theme_var = tk.StringVar(value=self.preferences["theme"])
        ttk.Label(appearance, text="Color theme", style="PyLex.Field.TLabel").grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )
        theme_box = ttk.Combobox(
            appearance,
            textvariable=theme_var,
            values=("dark", "light"),
            state="readonly",
            width=24,
        )
        theme_box.grid(row=1, column=0, sticky="w")
        ttk.Label(
            appearance,
            text="Dark uses deep navy surfaces with blue and violet accents. "
            "Light uses soft white surfaces and professional blue accents.",
            style="PyLex.Muted.TLabel",
            wraplength=560,
        ).grid(row=2, column=0, sticky="w", pady=(8, 18))

        available_fonts = sorted(tkfont.families(dialog), key=str.casefold)
        ui_font_var = tk.StringVar(value=self._resolved_ui_font(available_fonts))
        ui_size_var = tk.IntVar(value=self.preferences.get("ui_font_size", 9))
        ttk.Label(appearance, text="Interface font").grid(
            row=3, column=0, sticky="w", pady=(0, 5)
        )
        ui_fonts = [
            name
            for name in (
                "Segoe UI",
                "Inter",
                "Noto Sans",
                "Ubuntu",
                "DejaVu Sans",
                "Arial",
                "Tahoma",
            )
            if name in available_fonts
        ]
        if not ui_fonts:
            ui_fonts = ["TkDefaultFont"]
        ui_box = ttk.Combobox(
            appearance,
            textvariable=ui_font_var,
            values=ui_fonts,
            state="readonly",
            width=24,
        )
        ui_box.grid(row=4, column=0, sticky="w")
        ttk.Label(appearance, text="Interface size").grid(
            row=3, column=1, sticky="w", padx=(24, 0), pady=(0, 5)
        )
        ttk.Spinbox(appearance, from_=8, to=14, textvariable=ui_size_var, width=6).grid(
            row=4, column=1, sticky="w", padx=(24, 0)
        )

        code_fonts = [
            name
            for name in (
                "JetBrains Mono",
                "Cascadia Code",
                "Fira Code",
                "Consolas",
                "Cascadia Mono",
                "DejaVu Sans Mono",
                "Liberation Mono",
                "Courier New",
                "Lucida Console",
                "TkFixedFont",
            )
            if name in available_fonts
        ]
        if not code_fonts:
            code_fonts = ["TkFixedFont"]
        code_font_var = tk.StringVar(value=self._resolved_code_font(available_fonts))
        code_size_var = tk.IntVar(value=self.preferences["font_size"])
        ttk.Label(editor_page, text="Code font family").grid(
            row=0, column=0, sticky="w", pady=(0, 5)
        )
        code_box = ttk.Combobox(
            editor_page,
            textvariable=code_font_var,
            values=code_fonts,
            state="readonly",
            width=28,
        )
        code_box.grid(row=1, column=0, sticky="w")
        ttk.Label(editor_page, text="Code font size").grid(
            row=0, column=1, sticky="w", padx=(24, 0), pady=(0, 5)
        )
        ttk.Spinbox(
            editor_page, from_=8, to=32, textvariable=code_size_var, width=6
        ).grid(row=1, column=1, sticky="w", padx=(24, 0))
        ttk.Label(
            editor_page,
            text="JetBrains Mono is preferred for code when installed. "
            "Cascadia Code and Consolas are reliable fallbacks.",
            style="PyLex.Muted.TLabel",
            wraplength=560,
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(10, 0))

        explorer_var = tk.BooleanVar(value=self.preferences["show_project_explorer"])
        ttk.Checkbutton(
            workspace_page,
            text="Show project explorer on startup",
            variable=explorer_var,
        ).pack(anchor="w", pady=(0, 10))
        ttk.Label(
            workspace_page,
            text="Drag the separators between Explorer, Editor and the lower tool panel "
            "to resize each area. Use the mouse wheel over a panel to scroll.",
            style="PyLex.Muted.TLabel",
            wraplength=560,
        ).pack(anchor="w")

        timeout_var = tk.StringVar()
        current_timeout = self.preferences["timeout_seconds"]
        timeout_var.set(
            "Unlimited" if current_timeout is None else f"{current_timeout} seconds"
        )
        ttk.Label(execution_page, text="Execution timeout").grid(
            row=0, column=0, sticky="w", pady=(0, 5)
        )
        ttk.Combobox(
            execution_page,
            textvariable=timeout_var,
            values=("5 seconds", "10 seconds", "30 seconds", "60 seconds", "Unlimited"),
            state="readonly",
            width=22,
        ).grid(row=1, column=0, sticky="w")
        ttk.Label(
            execution_page,
            text="Unlimited execution is useful for long-running scripts. You can always stop a run manually.",
            style="PyLex.Muted.TLabel",
            wraplength=560,
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))

        help_text = (
            "QUICK START\n\n"
            "1. Open a folder with File → Open Workspace.\n"
            "2. Select a file in Explorer or use File → Open.\n"
            "3. Edit your code and press Ctrl+S to save.\n"
            "4. Press F5 to run the current Python file.\n"
            "5. Press F6 to run lexical and syntax analysis.\n"
            "6. Use the bottom tabs for Output, Terminal, Quality and Git.\n\n"
            "USEFUL SHORTCUTS\n"
            "Ctrl+N  New file     Ctrl+O  Open file\n"
            "Ctrl+S  Save         Ctrl+W  Close tab\n"
            "F5      Run           Shift+F5  Stop\n"
            "Ctrl+F5 Debug         F6  Analyze all\n"
            "F9      Toggle breakpoint   F10  Step over\n"
            "F11     Step into     Ctrl+Shift+P  Command palette\n"
            "Ctrl+,  Settings     Ctrl+P  Quick open file\n"
            "Ctrl+G  Go to line\n\n"
            "TIPS\n"
            "• Drag pane separators to resize the workspace.\n"
            "• Use the mouse wheel over the editor and panels to scroll.\n"
            "• Hover toolbar actions to see their purpose.\n"
            "• The About window shows the installed application version."
        )
        help_view = tk.Text(
            help_page,
            wrap="word",
            height=18,
            borderwidth=0,
            padx=8,
            pady=8,
            font=(ui_font_var.get(), 10),
        )
        help_view.configure(
            bg=self.theme_palette["editor_bg"],
            fg=self.theme_palette["editor_fg"],
            insertbackground=self.theme_palette["editor_fg"],
            selectbackground=self.theme_palette["selection_bg"],
            selectforeground=self.theme_palette["editor_fg"],
        )
        help_view.pack(fill="both", expand=True)
        help_view.insert("1.0", help_text)
        help_view.configure(state="disabled")

        buttons = ttk.Frame(shell)
        buttons.pack(fill="x", pady=(12, 0))

        def reset_defaults():
            theme_var.set(DEFAULTS["theme"])
            ui_font_var.set(
                DEFAULTS["ui_font_family"]
                if DEFAULTS["ui_font_family"] in ui_fonts
                else ui_fonts[0]
            )
            ui_size_var.set(DEFAULTS["ui_font_size"])
            default_font = next(
                (
                    name
                    for name in (
                        "JetBrains Mono",
                        "Cascadia Code",
                        "Fira Code",
                        "Consolas",
                        "Cascadia Mono",
                        "DejaVu Sans Mono",
                        "Liberation Mono",
                        "Courier New",
                        "Lucida Console",
                        "TkFixedFont",
                    )
                    if name in code_fonts
                ),
                code_fonts[0],
            )
            code_font_var.set(default_font)
            code_size_var.set(DEFAULTS["font_size"])
            explorer_var.set(DEFAULTS["show_project_explorer"])
            timeout_var.set(
                "Unlimited"
                if DEFAULTS["timeout_seconds"] is None
                else f"{DEFAULTS['timeout_seconds']} seconds"
            )

        def apply():
            try:
                code_size = max(8, min(32, int(code_size_var.get())))
                ui_size = max(8, min(14, int(ui_size_var.get())))
            except (ValueError, tk.TclError):
                messagebox.showerror(
                    "Settings", "Font sizes must be valid numbers.", parent=dialog
                )
                return
            selected_timeout = timeout_var.get()
            timeout_map = {
                "5 seconds": 5,
                "10 seconds": 10,
                "30 seconds": 30,
                "60 seconds": 60,
                "Unlimited": None,
            }
            if selected_timeout not in timeout_map:
                messagebox.showerror(
                    "Settings", "Choose a valid execution timeout.", parent=dialog
                )
                return
            self.preferences.update(
                {
                    "theme": theme_var.get(),
                    "font_family": code_font_var.get(),
                    "font_size": code_size,
                    "ui_font_family": ui_font_var.get(),
                    "ui_font_size": ui_size,
                    "timeout_seconds": timeout_map[selected_timeout],
                }
            )
            desired_explorer = bool(explorer_var.get())
            if desired_explorer != self.preferences["show_project_explorer"]:
                self.toggle_project_explorer()
            self.dark = self.preferences["theme"] == "dark"
            for editor in self.documents:
                editor.set_font_family(self.preferences["font_family"])
                editor.set_font_size(self.preferences["font_size"])
            self._theme()
            self._persist_preferences()
            dialog.destroy()

        ttk.Button(
            buttons, text="Apply", command=apply, style="PyLex.Primary.TButton"
        ).pack(side="right", padx=(6, 0))
        ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="right")
        ttk.Button(buttons, text="Reset to Defaults", command=reset_defaults).pack(
            side="left"
        )

    def show_about(self):
        """Show product identity and version outside the main title area."""
        dialog = tk.Toplevel(self)
        dialog.title("About PyLex Studio")
        dialog.transient(self)
        dialog.resizable(False, False)
        body = ttk.Frame(dialog, padding=26)
        body.pack(fill="both", expand=True)
        self._build_logo(body, 72)
        ttk.Label(body, text="PyLex Studio", style="PyLex.AboutTitle.TLabel").pack(
            anchor="w", pady=(12, 0)
        )
        ttk.Label(
            body,
            text=f"Version {__version__}",
            style="PyLex.Muted.TLabel",
        ).pack(anchor="w", pady=(2, 14))
        ttk.Label(
            body,
            text="A focused Python development environment with code editing, "
            "analysis, execution, debugging, Git and quality tools.",
            wraplength=390,
            justify="left",
        ).pack(anchor="w")
        ttk.Button(body, text="Close", command=dialog.destroy).pack(
            anchor="e", pady=(20, 0)
        )

    def show_help(self):
        """Open the built-in getting-started guide directly in Settings."""
        self.open_preferences(initial_tab="help")

    def open_quick_file(self):
        """Search workspace paths quickly, inspired by modern editor quick-open."""
        root = self.project_root
        if root is None or not root.is_dir():
            self.open_file()
            return

        ignored = {
            ".git",
            ".venv",
            "venv",
            "__pycache__",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            ".tox",
            "node_modules",
            "dist",
            "build",
        }
        candidates = []
        for directory, subdirectories, filenames in os.walk(root):
            subdirectories[:] = sorted(
                name
                for name in subdirectories
                if name not in ignored and not (Path(directory) / name).is_symlink()
            )
            for filename in filenames:
                path = Path(directory) / filename
                try:
                    relative = path.relative_to(root).as_posix()
                except ValueError:
                    continue
                candidates.append((relative, path))
                if len(candidates) >= 6000:
                    break
            if len(candidates) >= 6000:
                break
        candidates.sort(key=lambda item: item[0].casefold())

        dialog = tk.Toplevel(self)
        dialog.title("Quick Open")
        dialog.transient(self)
        dialog.geometry("660x460")
        dialog.minsize(440, 300)
        query = tk.StringVar()
        entry = ttk.Entry(
            dialog, textvariable=query, font=(self._resolved_ui_font(), 11)
        )
        entry.pack(fill="x", padx=12, pady=12)
        listing = tk.Listbox(
            dialog,
            activestyle="none",
            height=16,
            borderwidth=0,
            bg=self.theme_palette["surface"],
            fg=self.theme_palette["editor_fg"],
            selectbackground=self.theme_palette["accent"],
            selectforeground="#ffffff",
            highlightthickness=0,
        )
        listing.pack(fill="both", expand=True, padx=12, pady=(0, 8))
        hint = ttk.Label(
            dialog,
            text="Type to filter  ·  Enter to open  ·  Esc to close",
            style="PyLex.Muted.TLabel",
            padding=(12, 0, 12, 10),
        )
        hint.pack(anchor="w")
        matches = []

        def refresh(*_args):
            listing.delete(0, "end")
            matches.clear()
            term = query.get().strip().casefold()
            ranked = []
            for relative, path in candidates:
                folded = relative.casefold()
                basename = path.name.casefold()
                if not term:
                    rank = (0, len(relative), folded)
                elif term in basename:
                    rank = (0, basename.find(term), len(relative), folded)
                elif term in folded:
                    rank = (1, folded.find(term), len(relative), folded)
                else:
                    continue
                ranked.append((rank, relative, path))
            for _rank, relative, path in sorted(ranked)[:200]:
                matches.append(path)
                listing.insert("end", relative)
            if matches:
                listing.selection_set(0)
                listing.activate(0)

        def execute(_event=None):
            selection = listing.curselection()
            index = selection[0] if selection else (0 if matches else None)
            if index is None or index >= len(matches):
                return "break"
            path = matches[index]
            dialog.destroy()
            self._open_path(path)
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
        dialog.bind("<Return>", execute)
        dialog.bind("<Escape>", lambda _event: dialog.destroy())
        refresh()
        entry.focus_set()

    def open_command_palette(self):
        """Open the searchable palette backed by the shared command registry."""
        registry = CommandRegistry(
            [
                Command("file.new", "New File", "Ctrl+N", self.new_file),
                Command("file.open", "Open File", "Ctrl+O", self.open_file),
                Command("file.save", "Save File", "Ctrl+S", self.save_file),
                Command(
                    "workspace.open",
                    "Open Workspace",
                    "",
                    self.open_project_folder,
                ),
                Command(
                    "file.quick-open",
                    "Quick Open File",
                    "Ctrl+P",
                    self.open_quick_file,
                ),
                Command("run.active", "Run Current File", "F5", self.run_code),
                Command("run.stop", "Stop Execution", "Shift+F5", self.stop_execution),
                Command("analysis.all", "Analyze All", "F6", self.analyze_all),
                Command(
                    "debug.start",
                    "Start Debugging",
                    "Ctrl+F5",
                    self.start_debugging,
                ),
                Command("terminal.open", "Open Terminal", "", self.open_terminal),
                Command(
                    "quality.open",
                    "Open Quality Tools",
                    "",
                    self.open_quality_tools,
                ),
                Command("git.open", "Open Git", "", self.open_git_tools),
                Command("view.theme", "Toggle Theme", "", self.toggle_theme),
                Command(
                    "settings.open",
                    "Settings",
                    "Ctrl+,",
                    self.open_preferences,
                ),
                Command("help.open", "Quick Start & Help", "", self.show_help),
                Command(
                    "about.open",
                    "About PyLex Studio",
                    "",
                    self.show_about,
                ),
            ]
        )
        CommandPalette(
            self,
            registry,
            palette=self.theme_palette,
            font_family=self._resolved_ui_font(),
            anchor=self.command_palette_frame,
        ).show()

    def toggle_theme(self):
        self.dark = not self.dark
        self.preferences["theme"] = "dark" if self.dark else "light"
        self._theme()
        self._persist_preferences()

    def _theme(self):
        palette = self.theme_manager.apply(
            self.dark,
            ui_font_family=self._resolved_ui_font(),
            ui_font_size=self.preferences.get("ui_font_size", 9),
        )
        self.theme_palette = palette
        # Keep native Tk controls and dialogs aligned with the selected interface font.
        ui_family = self._resolved_ui_font()
        ui_size = self.preferences.get("ui_font_size", 9)
        for font_name in (
            "TkDefaultFont",
            "TkMenuFont",
            "TkHeadingFont",
            "TkCaptionFont",
            "TkSmallCaptionFont",
            "TkIconFont",
            "TkTooltipFont",
        ):
            try:
                tkfont.nametofont(font_name).configure(family=ui_family, size=ui_size)
            except tk.TclError:
                pass
        self._icon_cache.clear()
        self.configure(bg=palette["window_bg"])
        for editor in self.documents:
            editor.set_theme(self.dark, palette)
        for panel in (self.output, self.lexical, self.syntax):
            panel.configure(
                bg=palette["editor_bg"],
                fg=palette["editor_fg"],
                insertbackground=palette["editor_fg"],
                selectbackground=palette["selection_bg"],
                selectforeground=palette["editor_fg"],
            )
            panel.tag_configure("stderr", foreground=palette["danger"])
            panel.tag_configure("stdout", foreground=palette["success"])
            panel.tag_configure("system", foreground=palette["accent"])
        self.terminal_panel.set_theme(self.dark, palette)
        if hasattr(self, "error_tree"):
            self.error_tree.tag_configure("error", foreground=palette["danger"])
            self.error_tree.tag_configure("warning", foreground=palette["warning"])
            self.error_tree.tag_configure("info", foreground=palette["accent"])
        if hasattr(self, "project_tree"):
            self.project_tree.tag_configure("directory", foreground=palette["accent"])
            for kind in (
                "python",
                "web",
                "markup",
                "style",
                "data",
                "config",
                "shell",
                "compiled",
                "image",
                "audio",
                "video",
                "pdf",
                "document",
                "archive",
                "database",
                "font",
                "text",
                "binary",
                "unknown",
            ):
                self.project_tree.tag_configure(
                    kind, foreground=palette.get(f"file_{kind}", palette["editor_fg"])
                )
        if hasattr(self, "run_button"):
            self.run_button.configure(image=self._icon("play-fill", palette["accent"]))
            self.stop_button.configure(image=self._icon("stop-fill", palette["danger"]))
        if hasattr(self, "command_palette_frame"):
            self.command_palette_frame.configure(
                background=palette["surface"],
                highlightbackground=palette["border"],
                highlightcolor=palette["accent"],
            )
            self.command_palette_label.configure(
                background=palette["surface"],
                foreground=palette["muted"],
                font=(ui_family, ui_size),
            )
        if hasattr(self, "theme_button"):
            self.theme_button.configure(
                text="Light theme" if self.dark else "Dark theme",
                image=self._icon(
                    "sun" if self.dark else "moon-stars",
                    palette.get("warning"),
                ),
            )
        if hasattr(self, "help_button"):
            self.help_button.configure(
                image=self._icon("question-circle", palette.get("muted"))
            )
        if hasattr(self, "settings_button"):
            self.settings_button.configure(
                image=self._icon("gear-fill", palette.get("muted"))
            )
        for button, icon_name, color_key in getattr(self, "_toolbar_icon_bindings", []):
            button.configure(image=self._icon(icon_name, palette.get(color_key)))
        for _view, (button, icon_name, color_key) in getattr(
            self, "activity_buttons", {}
        ).items():
            button.configure(image=self._icon(icon_name, palette.get(color_key)))
        for button, icon_name, color_key in (
            getattr(self, "activity_account_button", (None, None, None)),
            getattr(self, "activity_settings_button", (None, None, None)),
        ):
            if button is not None:
                button.configure(image=self._icon(icon_name, palette.get(color_key)))
        if hasattr(self, "open_editors_list"):
            self.open_editors_list.configure(
                bg=palette["surface"],
                fg=palette["editor_fg"],
                selectbackground=palette["accent"],
            )
        for child, icon_name, color_key in getattr(self, "_tool_tab_icon_bindings", []):
            try:
                self.tabs.tab(
                    child,
                    image=self._icon(icon_name, palette.get(color_key)),
                    compound="left",
                )
            except tk.TclError:
                pass
        for document in getattr(self, "documents", {}).values():
            path = document["path"]
            if path:
                file_info = file_type_for(path)
                icon_name = self._file_icon_name(file_info.kind)
                icon_color = palette.get(
                    f"file_{file_info.kind}", palette.get("editor_fg")
                )
            else:
                icon_name = "file-earmark-plus"
                icon_color = palette.get("accent")
            try:
                self.editor_tabs.tab(
                    document["frame"],
                    image=self._icon(icon_name, icon_color),
                    compound="left",
                )
            except tk.TclError:
                pass
        if hasattr(self, "project_tree") and self.project_root is not None:
            self._populate_project_tree()
        for menu in getattr(self, "_menus", []):
            try:
                menu.configure(
                    background=palette["menu_bg"],
                    foreground=palette["menu_fg"],
                    activebackground=palette["accent"],
                    activeforeground="#ffffff",
                    borderwidth=0,
                )
            except tk.TclError:
                pass
