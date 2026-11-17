"""ShellMixin responsibilities for the PyLex application."""

# These modules intentionally consume the shared UI dependency namespace.
# ruff: noqa: F403, F405

from ..app_support import *  # noqa: F403


class ShellMixin:
    """Shell UI behavior composed into :class:`PyLexApp`."""

    def _build_logo(self, parent, size=40):
        """Draw the original PyLex emblem with native vector canvas primitives."""
        canvas = tk.Canvas(
            parent,
            width=size,
            height=size,
            bg=self.theme_palette["surface"],
            highlightthickness=0,
            bd=0,
        )
        canvas.pack(side="left")
        pad = size * 0.08
        canvas.create_polygon(
            size / 2,
            pad,
            size - pad,
            size / 2,
            size / 2,
            size - pad,
            pad,
            size / 2,
            fill="#101a35",
            outline="#2868ff",
            width=max(1, size / 32),
        )
        canvas.create_line(
            size * 0.28,
            size * 0.38,
            size * 0.16,
            size * 0.5,
            size * 0.28,
            size * 0.62,
            fill="#28c5ff",
            width=size * 0.105,
            capstyle="round",
            joinstyle="round",
        )
        canvas.create_line(
            size * 0.72,
            size * 0.38,
            size * 0.84,
            size * 0.5,
            size * 0.72,
            size * 0.62,
            fill="#a66bff",
            width=size * 0.105,
            capstyle="round",
            joinstyle="round",
        )
        canvas.create_arc(
            size * 0.32,
            size * 0.19,
            size * 0.68,
            size * 0.57,
            start=205,
            extent=270,
            style="arc",
            outline="#37aaff",
            width=size * 0.10,
        )
        canvas.create_arc(
            size * 0.32,
            size * 0.43,
            size * 0.68,
            size * 0.81,
            start=25,
            extent=270,
            style="arc",
            outline="#a66bff",
            width=size * 0.10,
        )
        return canvas

    def show_account(self):
        """Open the account center with local profile, workspace and feedback tools."""
        dialog = tk.Toplevel(self)
        dialog.title("PyLex Studio — Account Center")
        dialog.transient(self)
        dialog.geometry("940x720")
        dialog.minsize(800, 620)
        dialog.resizable(True, True)

        shell = ttk.Frame(dialog, padding=24)
        shell.pack(fill="both", expand=True)
        header = ttk.Frame(shell)
        header.pack(fill="x", pady=(0, 18))
        self._build_logo(header, 58)
        heading = ttk.Frame(header)
        heading.pack(side="left", padx=(14, 0), fill="x", expand=True)
        ttk.Label(
            heading, text="Account Center", style="PyLex.DialogTitle.TLabel"
        ).pack(anchor="w")
        ttk.Label(
            heading,
            text="Manage your local profile, workspace information and product feedback.",
            style="PyLex.Muted.TLabel",
        ).pack(anchor="w", pady=(4, 0))

        notebook = ttk.Notebook(shell)
        notebook.pack(fill="both", expand=True)
        profile_page = ttk.Frame(notebook, padding=20)
        services_page = ttk.Frame(notebook, padding=20)
        workspace_page = ttk.Frame(notebook, padding=20)
        feedback_page = ttk.Frame(notebook, padding=20)
        notebook.add(profile_page, text="Profile")
        notebook.add(services_page, text="Connected Services")
        notebook.add(workspace_page, text="Workspace")
        notebook.add(feedback_page, text="Feedback")

        profile_name = tk.StringVar(
            value=self.preferences.get("account_display_name", "Developer")
        )
        ttk.Label(profile_page, text="Local profile", style="PyLex.Field.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            profile_page,
            text="Your display name is saved on this computer and is not uploaded to a server.",
            style="PyLex.Muted.TLabel",
            wraplength=700,
        ).pack(anchor="w", pady=(5, 18))
        ttk.Label(profile_page, text="Display name").pack(anchor="w")
        profile_entry = ttk.Entry(profile_page, textvariable=profile_name, width=48)
        profile_entry.pack(anchor="w", fill="x", pady=(5, 14))

        def save_profile():
            self.preferences["account_display_name"] = (
                profile_name.get().strip()[:48] or "Developer"
            )
            self._persist_preferences()
            self.status.configure(text="Local profile updated.")
            dialog.destroy()

        ttk.Button(
            profile_page,
            text="Save Profile",
            command=save_profile,
            style="PyLex.Primary.TButton",
        ).pack(anchor="w")
        ttk.Label(profile_page, text="Privacy", style="PyLex.Field.TLabel").pack(
            anchor="w", pady=(28, 6)
        )
        ttk.Label(
            profile_page,
            text="PyLex Studio currently keeps this profile in your local preferences file. "
            "No account registration, telemetry upload or cloud synchronization is performed by this screen.",
            style="PyLex.Muted.TLabel",
            wraplength=700,
            justify="left",
        ).pack(anchor="w")

        ttk.Label(
            services_page,
            text="Service availability",
            style="PyLex.DialogTitle.TLabel",
        ).pack(anchor="w", pady=(0, 12))
        service_items = (
            (
                "Local profile",
                "Available",
                "success",
                "Edit the display name stored in your local preferences.",
            ),
            (
                "Git source control",
                "Available",
                "success",
                "Use local Git repositories without linking an online account.",
            ),
            (
                "GitHub sign-in",
                "Planned",
                "muted",
                "A future opt-in integration for repository and pull-request workflows.",
            ),
            (
                "Cloud synchronization",
                "Planned",
                "warning",
                "A future opt-in service for synchronizing settings across devices.",
            ),
            (
                "Extensions marketplace",
                "Roadmap",
                "muted",
                "A future trusted extension catalog with permission and compatibility checks.",
            ),
        )
        for name, status, color_key, description in service_items:
            card = ttk.Frame(services_page, padding=12)
            card.pack(fill="x", pady=5)
            top = ttk.Frame(card)
            top.pack(fill="x")
            ttk.Label(top, text=name, style="PyLex.Field.TLabel").pack(side="left")
            ttk.Label(top, text=status, foreground=self.theme_palette[color_key]).pack(
                side="right"
            )
            ttk.Label(
                card,
                text=description,
                style="PyLex.Muted.TLabel",
                wraplength=700,
                justify="left",
            ).pack(anchor="w", pady=(5, 0))

        root = (
            str(self.project_root)
            if self.project_root
            else "No workspace is currently open."
        )
        document_count = len(self.documents)
        ttk.Label(
            workspace_page,
            text="Current workspace",
            style="PyLex.DialogTitle.TLabel",
        ).pack(anchor="w", pady=(0, 12))
        ttk.Label(workspace_page, text=root, wraplength=700).pack(
            anchor="w", pady=(0, 16)
        )
        metrics = ttk.Frame(workspace_page)
        metrics.pack(fill="x")
        for label, value in (
            ("Open documents", str(document_count)),
            ("Workspace", "Open" if self.project_root else "Not open"),
            ("Profile", "Local"),
        ):
            tile = ttk.Frame(metrics, padding=14)
            tile.pack(side="left", fill="both", expand=True, padx=(0, 8))
            ttk.Label(tile, text=value, style="PyLex.DialogTitle.TLabel").pack(
                anchor="w"
            )
            ttk.Label(tile, text=label, style="PyLex.Muted.TLabel").pack(
                anchor="w", pady=(4, 0)
            )

        ttk.Label(
            feedback_page,
            text="Share feedback",
            style="PyLex.DialogTitle.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            feedback_page,
            text="Report a bug, suggest an improvement or tell us what is working well.",
            style="PyLex.Muted.TLabel",
            wraplength=700,
        ).pack(anchor="w", pady=(5, 16))

        feedback_type = tk.StringVar(value="Suggestion")
        ttk.Label(feedback_page, text="Feedback type", style="PyLex.Field.TLabel").pack(
            anchor="w"
        )
        type_picker = ttk.Combobox(
            feedback_page,
            textvariable=feedback_type,
            state="readonly",
            values=("Suggestion", "Bug report", "Usability", "Performance", "Other"),
        )
        type_picker.pack(anchor="w", fill="x", pady=(5, 14))

        ttk.Label(feedback_page, text="Your message", style="PyLex.Field.TLabel").pack(
            anchor="w"
        )
        feedback_message = tk.Text(
            feedback_page,
            height=9,
            wrap="word",
            undo=True,
            font=("Segoe UI", 10),
            relief="solid",
            bd=1,
            padx=10,
            pady=8,
        )
        feedback_message.pack(fill="both", expand=True, pady=(5, 12))

        ttk.Label(
            feedback_page,
            text="Privacy: feedback is not sent automatically. You can copy it or save it as a local text file.",
            style="PyLex.Muted.TLabel",
            wraplength=700,
        ).pack(anchor="w", pady=(0, 12))

        def build_feedback():
            message = feedback_message.get("1.0", "end-1c").strip()
            if not message:
                messagebox.showinfo(
                    "Feedback",
                    "Please enter a message before continuing.",
                    parent=dialog,
                )
                return None
            return (
                "PyLex Studio Feedback\\n"
                "======================\\n"
                f"Type: {feedback_type.get()}\\n"
                f"Application version: {__version__}\\n"
                f"Platform: {sys.platform}\\n"
                f"Workspace: {root}\\n\\n"
                f"{message}\\n"
            )

        def copy_feedback():
            content = build_feedback()
            if content is None:
                return
            dialog.clipboard_clear()
            dialog.clipboard_append(content)
            self.status.configure(text="Feedback copied to clipboard.")
            messagebox.showinfo(
                "Feedback",
                "Feedback copied. You can paste it wherever you want to share it.",
                parent=dialog,
            )

        def save_feedback():
            content = build_feedback()
            if content is None:
                return
            destination = filedialog.asksaveasfilename(
                parent=dialog,
                title="Save Feedback",
                defaultextension=".txt",
                filetypes=(("Text files", "*.txt"), ("All files", "*.*")),
                initialfile="pylex-feedback.txt",
            )
            if not destination:
                return
            try:
                Path(destination).write_text(content, encoding="utf-8")
            except OSError as exc:
                messagebox.showerror("Save Feedback", str(exc), parent=dialog)
                return
            self.status.configure(text="Feedback saved locally.")
            messagebox.showinfo(
                "Feedback",
                "Your feedback was saved as a local text file.",
                parent=dialog,
            )

        feedback_actions = ttk.Frame(feedback_page)
        feedback_actions.pack(fill="x")
        ttk.Button(
            feedback_actions,
            text="Copy Feedback",
            command=copy_feedback,
        ).pack(side="left")
        ttk.Button(
            feedback_actions,
            text="Save Feedback…",
            command=save_feedback,
            style="PyLex.Primary.TButton",
        ).pack(side="left", padx=(8, 0))

        footer = ttk.Frame(shell)
        footer.pack(fill="x", pady=(14, 0))
        ttk.Label(
            footer,
            text="Online services remain disabled until explicitly implemented and configured.",
            style="PyLex.Muted.TLabel",
        ).pack(side="left", fill="x", expand=True)
        ttk.Button(footer, text="Close", command=dialog.destroy).pack(side="right")
        profile_entry.focus_set()

    def _show_activity_context_menu(self, view, event):
        menu = self._new_context_menu()
        if view == "explorer":
            menu.add_command(
                label="Open Explorer", command=lambda: self._activity_action("explorer")
            )
            menu.add_command(label="Open Workspace…", command=self.open_project_folder)
            menu.add_command(label="Refresh Workspace", command=self.refresh_workspace)
        elif view == "search":
            menu.add_command(label="Quick Open File…", command=self.open_quick_file)
            menu.add_command(
                label="Command Palette…", command=self.open_command_palette
            )
        elif view == "source":
            menu.add_command(label="Open Git Tools", command=self.open_git_tools)
            menu.add_command(
                label="Open Git Repository…", command=self.open_project_folder
            )
        elif view == "debug":
            menu.add_command(label="Start Debugging", command=self.start_debugging)
            menu.add_command(label="Continue", command=self.debug_continue)
            menu.add_command(label="Stop Debugging", command=self.stop_debugging)
        elif view == "extensions":
            menu.add_command(
                label="Open Quality Tools", command=self.open_quality_tools
            )
            menu.add_command(label="Scan Dependencies", command=self.scan_dependencies)
        menu.tk_popup(event.x_root, event.y_root)
        return "break"

    def _activity_action(self, view):
        """Route Activity Bar actions to existing workspace tools."""
        # Keep activity feedback transient: do not persist a selected state.
        for button, _icon_name, _color_key in self.activity_buttons.values():
            button.state(["!selected"])
        if view == "explorer":
            if not self.preferences["show_project_explorer"]:
                self.toggle_project_explorer()
            self.project_tree.focus_set()
            self.status.configure(
                text="Explorer ready — open a folder to browse its files."
            )
        elif view == "search":
            self.open_quick_file()
        elif view == "source":
            self.open_git_tools()
        elif view == "debug":
            self.start_debugging()
        elif view == "extensions":
            self.open_quality_tools()

    def create_project_folder(self):
        """Create a named folder at the workspace root."""
        if self.project_root is None:
            messagebox.showinfo("New Folder", "Open a workspace first.", parent=self)
            return
        name = simpledialog.askstring("New Folder", "Folder name:", parent=self)
        if not name or Path(name).name != name or name in {".", ".."}:
            return
        try:
            (self.project_root / name).mkdir()
        except OSError as exc:
            messagebox.showerror("New Folder", str(exc), parent=self)
            return
        self.refresh_workspace()

    def _select_open_editor(self, _event=None):
        selection = self.open_editors_list.curselection()
        if selection:
            editors = list(self.documents)
            if selection[0] < len(editors):
                self.editor_tabs.select(self.documents[editors[selection[0]]]["frame"])

    def _refresh_open_editors(self):
        if not hasattr(self, "open_editors_list"):
            return
        self.open_editors_list.delete(0, "end")
        for _editor, document in self.documents.items():
            path = document.get("path")
            marker = "● " if document.get("dirty") else "   "
            self.open_editors_list.insert(
                "end", marker + (path.name if path else "Untitled")
            )

    def _add_tool_tab(self, child, title, icon_name, color_key):
        """Add a lower-panel tab and retain its icon for live theme refreshes."""
        image = self._icon(icon_name, self.theme_palette.get(color_key))
        self.tabs.add(child, text=title, image=image, compound="left")
        self._tool_tab_icon_bindings.append((child, icon_name, color_key))

    def _workspace(self):
        # Pack the status bar before the expanding workspace so it always reserves bottom space.
        status_row = ttk.Frame(self, style="PyLex.Toolbar.TFrame", padding=(10, 3))
        status_row.pack(fill="x", side="bottom")
        self.status = ttk.Label(
            status_row,
            text="Ready",
            style="PyLex.Status.TLabel",
            anchor="w",
            padding=(6, 3),
        )
        self.status.pack(side="left", fill="x", expand=True)
        self.editor_status = ttk.Frame(status_row, style="PyLex.Toolbar.TFrame")
        self.editor_status.pack(side="right")
        self._editor_status_items = {}
        self._editor_status_separators = []
        for index, key in enumerate(
            ("position", "indent", "encoding", "eol", "language", "mode")
        ):
            if index:
                separator = ttk.Separator(self.editor_status, orient="vertical")
                separator.pack(side="left", fill="y", padx=2, pady=3)
                self._editor_status_separators.append(separator)
            label = ttk.Label(
                self.editor_status,
                text="",
                style="PyLex.Status.TLabel",
                padding=(7, 3),
                anchor="center",
            )
            label.pack(side="left")
            self._editor_status_items[key] = label
        ttk.Separator(self, orient="horizontal").pack(fill="x", side="bottom")
        self._apply_status_bar_visibility()
        self.status_row = status_row

        # Right-click must work across the complete status strip, not only
        # on the small indicators at its far-right edge.
        def bind_status_context(widget):
            widget.bind("<Button-3>", self._show_status_context_menu, add="+")
            for child in widget.winfo_children():
                bind_status_context(child)

        bind_status_context(status_row)
        self._update_editor_status()

        shell = ttk.Frame(self)
        shell.pack(fill="both", expand=True, padx=8, pady=(2, 8))
        self.workspace_shell = shell
        activity = ttk.Frame(shell, style="PyLex.Activity.TFrame", padding=(4, 9))
        activity.pack(side="left", fill="y")
        activity.configure(width=66)
        activity.pack_propagate(False)
        self.activity_buttons = {}
        for view, icon_name, label, color_key in (
            ("explorer", "folder2-open", "Explorer", "accent"),
            ("search", "search", "Search", "muted"),
            ("source", "git", "Source", "violet"),
            ("debug", "bug-fill", "Debug", "success"),
            ("extensions", "boxes", "Quality", "warning"),
        ):
            button = ttk.Button(
                activity,
                text=label,
                command=lambda name=view: self._activity_action(name),
                style="PyLex.Activity.TButton",
                image=self._icon(icon_name, self.theme_palette.get(color_key), size=21),
                compound="top",
            )
            button.pack(fill="x", pady=4, ipadx=1, ipady=7)
            button.bind(
                "<Button-3>",
                lambda event, name=view: self._show_activity_context_menu(name, event),
                add="+",
            )
            button.bind(
                "<Leave>",
                lambda _event, target=button: target.state(["!active", "!selected"]),
                add="+",
            )
            button.bind(
                "<FocusOut>",
                lambda _event, target=button: target.state(["!active", "!selected"]),
                add="+",
            )
            self.activity_buttons[view] = (button, icon_name, color_key)
        ttk.Separator(activity).pack(fill="x", pady=(10, 6))
        account_button = ttk.Button(
            activity,
            text="Account",
            command=self.show_account,
            style="PyLex.Activity.TButton",
            image=self._icon("person-circle", self.theme_palette.get("muted"), size=21),
            compound="top",
        )
        account_button.pack(side="bottom", fill="x", pady=4, ipady=7)
        account_button.configure(takefocus=False)
        settings_button = ttk.Button(
            activity,
            text="Manage",
            command=self.open_preferences,
            style="PyLex.Activity.TButton",
            image=self._icon("gear-fill", self.theme_palette.get("muted"), size=21),
            compound="top",
        )
        settings_button.pack(side="bottom", fill="x", pady=4, ipady=7)
        settings_button.configure(takefocus=False)
        self.activity_account_button = (account_button, "person-circle", "muted")
        self.activity_settings_button = (settings_button, "gear-fill", "muted")
        workspace = ttk.Panedwindow(shell, orient="horizontal")
        self.workspace = workspace
        workspace.pack(side="left", fill="both", expand=True)
        self.project_root = None
        self.explorer_frame = ttk.Frame(workspace)
        explorer_header = ttk.Frame(self.explorer_frame, padding=(6, 5))
        explorer_header.pack(fill="x")
        ttk.Label(explorer_header, text="EXPLORER", style="PyLex.Section.TLabel").pack(
            side="left"
        )
        explorer_actions = ttk.Frame(self.explorer_frame, padding=(7, 3))
        explorer_actions.pack(fill="x")
        for icon_name, label, command, color_key in (
            ("file-earmark-plus", "New file", self.new_file, "accent"),
            ("folder-plus", "New folder", self.create_project_folder, "success"),
            ("arrow-clockwise", "Refresh", self.refresh_workspace, "muted"),
            ("folder2-open", "Open folder", self.open_project_folder, "accent"),
        ):
            action = ttk.Button(
                explorer_actions,
                text=label,
                command=command,
                style="PyLex.IconAction.TButton",
                image=self._icon(icon_name, self.theme_palette.get(color_key)),
            )
            action.pack(side="left", padx=(0, 3))
            self._toolbar_icon_bindings.append((action, icon_name, color_key))
        ttk.Separator(self.explorer_frame).pack(fill="x", pady=(4, 6))
        ttk.Label(
            self.explorer_frame,
            text="OPEN EDITORS",
            style="PyLex.Group.TLabel",
            padding=(9, 4),
        ).pack(fill="x")
        self.open_editors_list = tk.Listbox(
            self.explorer_frame,
            height=4,
            activestyle="none",
            borderwidth=0,
            highlightthickness=0,
            bg=self.theme_palette["surface"],
            fg=self.theme_palette["editor_fg"],
            selectbackground=self.theme_palette["accent"],
        )
        self.open_editors_list.pack(fill="x", padx=6, pady=(0, 8))
        self.open_editors_list.bind("<Double-1>", self._select_open_editor)
        self.open_editors_list.bind(
            "<Button-3>", self._show_open_editors_context_menu, add="+"
        )
        ttk.Label(
            self.explorer_frame,
            text="WORKSPACE",
            style="PyLex.Group.TLabel",
            padding=(9, 4),
        ).pack(fill="x")
        self.workspace_path_label = ttk.Label(
            self.explorer_frame,
            text="No folder opened",
            style="PyLex.Muted.TLabel",
            padding=(9, 4),
        )
        self.workspace_path_label.pack(fill="x")
        self.project_tree = ttk.Treeview(
            self.explorer_frame, show="tree", selectmode="browse"
        )
        self.project_tree.pack(fill="both", expand=True, padx=4, pady=(0, 5))
        self.project_tree.tag_configure(
            "directory", foreground=self.theme_palette["accent"]
        )
        self.project_tree.tag_configure(
            "python", foreground=self.theme_palette["file_python"]
        )
        self.project_tree.tag_configure(
            "web", foreground=self.theme_palette["file_web"]
        )
        self.project_tree.tag_configure(
            "markup", foreground=self.theme_palette["file_markup"]
        )
        self.project_tree.tag_configure(
            "style", foreground=self.theme_palette["file_style"]
        )
        self.project_tree.tag_configure(
            "data", foreground=self.theme_palette["file_data"]
        )
        self.project_tree.tag_configure(
            "config", foreground=self.theme_palette["muted"]
        )
        self.project_tree.tag_configure(
            "text", foreground=self.theme_palette["editor_fg"]
        )
        self.project_tree.bind("<Double-1>", self._on_project_tree_open)
        self.project_tree.bind(
            "<Button-3>", self._show_project_tree_context_menu, add="+"
        )
        self.project_tree.bind(
            "<Shift-F10>", self._show_project_tree_context_menu, add="+"
        )
        if self.preferences["show_project_explorer"]:
            workspace.add(self.explorer_frame, weight=1)

        panes = ttk.Panedwindow(workspace, orient="vertical")
        self.editor_panes = panes
        workspace.add(panes, weight=5)
        self.editor_tabs = ttk.Notebook(panes)
        panes.add(self.editor_tabs, weight=4)
        self.editor_tabs.bind("<<NotebookTabChanged>>", self._on_tab_changed)
        self.editor_tabs.bind("<Button-1>", self._on_tab_close_click, add="+")
        self.editor_tabs.bind("<Button-3>", self._show_tab_context_menu, add="+")
        self._create_document()

        lower = ttk.Frame(panes)
        panes.add(lower, weight=2)
        self.tabs = ttk.Notebook(lower)
        self.tabs.pack(fill="both", expand=True)

        self.output = self._text_panel("Output")
        self.lexical = self._text_panel("Lexical Analysis")
        self.syntax = self._text_panel("Syntax Analysis")
        self._errors_panel()
        self._dependencies_panel()
        self.terminal_panel = TerminalPanel(
            lower,
            self._terminal_context,
            default_shell=self.preferences.get("terminal_shell", ""),
            on_shell_change=self._save_terminal_shell,
            on_run_file=self.run_active_file_in_terminal,
        )
        self._add_tool_tab(self.terminal_panel, "Terminal", "terminal", "accent")
        self.quality_panel = QualityPanel(
            lower,
            self._quality_context,
            self._quality_document,
            self._apply_formatted_source,
            self._navigate_quality_diagnostic,
            status_callback=lambda message: self.status.configure(text=message),
            project_format_guard=self._can_format_project,
        )
        self._add_tool_tab(self.quality_panel, "Quality", "check2-square", "success")
        self.git_panel = GitPanel(
            lower,
            lambda: self.project.root if self.project else None,
            status_callback=lambda message: self.status.configure(text=message),
        )
        self._add_tool_tab(self.git_panel, "Git", "git", "violet")
