"""ToolbarMixin responsibilities for the PyLex application."""

# These modules intentionally consume the shared UI dependency namespace.
# ruff: noqa: F403, F405

from ..app_support import *  # noqa: F403


class ToolbarMixin:
    """Toolbar UI behavior composed into :class:`PyLexApp`."""

    def _menu(self):
        menu = tk.Menu(self)
        self._menus = [menu]
        file_menu = tk.Menu(menu, tearoff=False)
        self._menus.append(file_menu)
        for label, command, shortcut in [
            ("New", self.new_file, "Ctrl+N"),
            ("Open...", self.open_file, "Ctrl+O"),
            ("Open Workspace...", self.open_project_folder, ""),
            ("Close Workspace", self.close_workspace, "Ctrl+Shift+W"),
            ("Python Interpreter...", self.manage_interpreter, ""),
            ("Save", self.save_file, "Ctrl+S"),
            ("Save As...", self.save_as, "Ctrl+Shift+S"),
            ("Close Tab", self.close_tab, "Ctrl+W"),
        ]:
            file_menu.add_command(label=label, command=command, accelerator=shortcut)
        self.recent_workspace_menu = tk.Menu(
            file_menu,
            tearoff=False,
            background=self.theme_palette["menu_bg"],
            foreground=self.theme_palette["menu_fg"],
            activebackground=self.theme_palette["elevated"],
            activeforeground=self.theme_palette["accent"],
            disabledforeground=self.theme_palette["muted"],
            borderwidth=1,
            relief="solid",
            font=(self._resolved_ui_font(), self.preferences.get("ui_font_size", 9)),
        )
        self._menus.append(self.recent_workspace_menu)
        file_menu.add_cascade(
            label="Open Recent Workspace", menu=self.recent_workspace_menu
        )
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.close)
        self._refresh_recent_workspace_menu()
        menu.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menu, tearoff=False)
        self._menus.append(edit_menu)
        edit_menu.add_command(label="Find / Replace...", command=self.find_replace)
        edit_menu.add_command(
            label="Toggle Line Comment",
            command=lambda: self.editor._toggle_comment(),
            accelerator="Ctrl+/",
        )
        edit_menu.add_command(
            label="Duplicate Line / Selection",
            command=lambda: self.editor._duplicate_line(),
            accelerator="Ctrl+D",
        )
        edit_menu.add_command(
            label="Go to Line...",
            command=lambda: self.editor._go_to_line(),
            accelerator="Ctrl+G",
        )
        menu.add_cascade(label="Edit", menu=edit_menu)

        navigate_menu = tk.Menu(menu, tearoff=False)
        self._menus.append(navigate_menu)
        navigate_menu.add_command(
            label="Quick Open File...",
            command=self.open_quick_file,
            accelerator="Ctrl+P",
        )
        navigate_menu.add_command(
            label="Go to Line...",
            command=lambda: self.editor._go_to_line(),
            accelerator="Ctrl+G",
        )
        navigate_menu.add_command(
            label="Command Palette...",
            command=self.open_command_palette,
            accelerator="Ctrl+Shift+P",
        )
        menu.add_cascade(label="Navigate", menu=navigate_menu)

        tools_menu = tk.Menu(menu, tearoff=False)
        self._menus.append(tools_menu)
        tools_menu.add_command(
            label="Python Interpreter...", command=self.manage_interpreter
        )
        tools_menu.add_command(label="Integrated Terminal", command=self.open_terminal)
        tools_menu.add_command(
            label="Formatter, Linter & Test Explorer", command=self.open_quality_tools
        )
        tools_menu.add_command(label="Git Source Control", command=self.open_git_tools)
        tools_menu.add_separator()
        tools_menu.add_command(label="Analyze All", command=self.analyze_all)
        tools_menu.add_command(label="Lexical Analysis", command=self.analyze_lexical)
        tools_menu.add_command(label="Syntax Analysis", command=self.analyze_syntax)
        tools_menu.add_command(label="Clear Results", command=self.clear_results)
        tools_menu.add_separator()
        tools_menu.add_command(label="Run Code", command=self.run_code)
        tools_menu.add_command(
            label="Force Stop Execution", command=self.stop_execution
        )
        tools_menu.add_separator()
        tools_menu.add_command(label="Start Debugging", command=self.start_debugging)
        tools_menu.add_command(label="Continue", command=self.debug_continue)
        tools_menu.add_command(label="Step Into", command=self.debug_step)
        tools_menu.add_command(label="Step Over", command=self.debug_next)
        tools_menu.add_command(
            label="Toggle Breakpoint", command=self.toggle_breakpoint
        )
        tools_menu.add_command(label="Inspect Variables", command=self.debug_variables)
        tools_menu.add_command(label="Show Stack", command=self.debug_stack)
        tools_menu.add_command(
            label="Show Function Arguments", command=self.debug_arguments
        )
        tools_menu.add_command(label="Run Until Line", command=self.debug_until)
        tools_menu.add_command(label="Run Until Return", command=self.debug_return)
        tools_menu.add_command(label="Jump to Line", command=self.debug_jump)
        tools_menu.add_command(
            label="Evaluate Expression...", command=self.debug_evaluate
        )
        tools_menu.add_command(
            label="Conditional Breakpoint...", command=self.debug_conditional_breakpoint
        )
        tools_menu.add_command(
            label="Temporary Breakpoint", command=self.debug_temporary_breakpoint
        )
        tools_menu.add_command(
            label="Enable Breakpoint...",
            command=lambda: self.debug_manage_breakpoint("enable"),
        )
        tools_menu.add_command(
            label="Disable Breakpoint...",
            command=lambda: self.debug_manage_breakpoint("disable"),
        )
        tools_menu.add_command(
            label="Ignore Breakpoint Hits...",
            command=lambda: self.debug_manage_breakpoint("ignore"),
        )
        tools_menu.add_command(
            label="Clear All Breakpoints", command=self.debug_clear_breakpoints
        )
        tools_menu.add_command(label="Stop Debugging", command=self.stop_debugging)
        menu.add_cascade(label="Tools", menu=tools_menu)

        view_menu = tk.Menu(menu, tearoff=False)
        self._menus.append(view_menu)
        view_menu.add_command(label="Preferences...", command=self.open_preferences)
        view_menu.add_command(
            label="Toggle Project Explorer", command=self.toggle_project_explorer
        )
        menu.add_cascade(label="View", menu=view_menu)

        help_menu = tk.Menu(menu, tearoff=False)
        self._menus.append(help_menu)
        help_menu.add_command(label="Quick Start & Help...", command=self.show_help)
        help_menu.add_command(
            label="Command Palette...",
            command=self.open_command_palette,
            accelerator="Ctrl+Shift+P",
        )
        help_menu.add_separator()
        help_menu.add_command(label="About PyLex Studio...", command=self.show_about)
        menu.add_cascade(label="Help", menu=help_menu)
        self.config(menu=menu)

        self.bind_all("<Control-Shift-P>", lambda event: self.open_command_palette())
        self.bind_all("<Control-p>", lambda event: self.open_quick_file())
        self.bind_all("<Control-comma>", lambda event: self.open_preferences())
        self.bind_all("<Control-n>", lambda event: self.new_file())
        self.bind_all("<Control-o>", lambda event: self.open_file())
        self.bind_all("<Control-s>", lambda event: self.save_file())
        self.bind_all("<Control-h>", lambda event: self.find_replace())
        self.bind_all("<Control-w>", lambda event: self.close_tab())
        self.bind_all("<Control-Shift-W>", lambda event: self.close_workspace())
        self.bind_all("<F5>", lambda event: self.run_code())
        self.bind_all("<Shift-F5>", lambda event: self.stop_execution())
        self.bind_all("<F6>", lambda event: self.analyze_all())
        self.bind_all("<F9>", lambda event: self.toggle_breakpoint())
        self.bind_all("<F10>", lambda event: self.debug_next())
        self.bind_all("<F11>", lambda event: self.debug_step())
        self.bind_all("<Control-F5>", lambda event: self.start_debugging())
        self.bind_all("<Control-F10>", lambda event: self.debug_continue())

    def _icon(self, name, color=None, size=18):
        """Return a cached Bootstrap glyph using the active theme palette."""
        color = color or self.theme_palette.get("muted", "#91a0b7")
        key = (name, color, size)
        if key not in self._icon_cache:
            self._icon_cache[key] = ttkb.Icon(name, size=size, color=color)
        return self._icon_cache[key]

    @staticmethod
    def _file_icon_name(kind):
        """Map workspace file categories to one consistent icon family."""
        return {
            "python": "filetype-py",
            "web": "filetype-js",
            "markup": "filetype-html",
            "style": "filetype-css",
            "data": "filetype-json",
            "config": "gear",
            "shell": "terminal",
            "compiled": "file-earmark-code",
            "image": "file-earmark-image",
            "audio": "file-earmark-music",
            "video": "file-earmark-play",
            "pdf": "file-earmark-pdf",
            "document": "file-earmark-text",
            "archive": "file-earmark-zip",
            "database": "database",
            "font": "file-earmark-font",
            "text": "file-earmark-text",
            "binary": "file-earmark",
            "unknown": "file-earmark",
        }.get(kind, "file-earmark")

    def _toolbar(self):
        """Build a two-tier command surface: categorized menus above the brand/action row."""
        menu_row = ttk.Frame(self, style="PyLex.Toolbar.TFrame", padding=(10, 2))
        menu_row.pack(fill="x", side="top")

        brand = ttk.Frame(menu_row, style="PyLex.Toolbar.TFrame")
        brand.pack(side="left", padx=(0, 12))
        self._build_logo(brand, 28)
        ttk.Label(brand, text="PyLex Studio", style="PyLex.Brand.TLabel").pack(
            side="left", padx=(7, 0)
        )

        def add_menu(title, icon_name, color_key, commands):
            button = ttk.Button(
                menu_row,
                text=title,
                style="PyLex.Menu.TButton",
                image=self._icon(icon_name, self.theme_palette.get(color_key)),
                compound="left",
            )
            button.pack(side="left", padx=(0, 2), ipady=0)
            button.configure(takefocus=False)
            self._toolbar_icon_bindings.append((button, icon_name, color_key))

            state = {
                "windows": [],
                "open_id": None,
                "poll_id": None,
                "submenu_id": None,
                "closed": True,
                "outside_polls": 0,
            }

            def cancel_timer(key):
                timer_id = state.get(key)
                if timer_id is not None:
                    try:
                        self.after_cancel(timer_id)
                    except tk.TclError:
                        pass
                    state[key] = None

            def destroy_popups():
                cancel_timer("poll_id")
                cancel_timer("open_id")
                cancel_timer("submenu_id")
                for popup in reversed(state["windows"]):
                    try:
                        if popup.winfo_exists():
                            popup.destroy()
                    except tk.TclError:
                        pass
                state["windows"].clear()
                state["closed"] = True
                if getattr(self, "_toolbar_menu_close", None) is destroy_popups:
                    self._toolbar_menu_close = None

            def pointer_inside(widget, x, y, margin=5):
                try:
                    if not widget.winfo_exists():
                        return False
                    left, top = widget.winfo_rootx(), widget.winfo_rooty()
                    right = left + widget.winfo_width()
                    bottom = top + widget.winfo_height()
                    return (
                        left - margin <= x <= right + margin
                        and top - margin <= y <= bottom + margin
                    )
                except tk.TclError:
                    return False

            def poll_pointer():
                state["poll_id"] = None
                if state["closed"] or not state["windows"]:
                    return
                try:
                    x, y = self.winfo_pointerxy()
                except tk.TclError:
                    destroy_popups()
                    return
                # Treat the toolbar button, every open popup and the tiny
                # transition corridor between them as one continuous menu area.
                inside = pointer_inside(button, x, y) or any(
                    pointer_inside(popup, x, y) for popup in state["windows"]
                )
                if not inside and state["windows"]:
                    try:
                        first = state["windows"][0]
                        bx1, by1 = button.winfo_rootx(), button.winfo_rooty()
                        bx2, by2 = (
                            bx1 + button.winfo_width(),
                            by1 + button.winfo_height(),
                        )
                        px1, py1 = first.winfo_rootx(), first.winfo_rooty()
                        px2, py2 = px1 + first.winfo_width(), py1 + first.winfo_height()
                        inside = (
                            min(bx1, px1) - 7 <= x <= max(bx2, px2) + 7
                            and min(by1, py1) - 7 <= y <= max(by2, py2) + 7
                        )
                    except tk.TclError:
                        inside = False
                if inside:
                    state["outside_polls"] = 0
                else:
                    state["outside_polls"] += 1
                    # Ignore transient geometry/focus reports while the pointer
                    # is moving between the toolbar anchor and its popup.
                    if state["outside_polls"] >= 2:
                        destroy_popups()
                        return
                state["poll_id"] = self.after(70, poll_pointer)

            def schedule_poll():
                cancel_timer("poll_id")
                state["poll_id"] = self.after(70, poll_pointer)

            def close_descendant_popups(parent_popup):
                """Close only popups branching from this menu, preserving ancestors."""
                try:
                    parent_index = state["windows"].index(parent_popup)
                except ValueError:
                    return
                descendants = state["windows"][parent_index + 1 :]
                del state["windows"][parent_index + 1 :]
                for child_popup in reversed(descendants):
                    try:
                        if child_popup.winfo_exists():
                            child_popup.destroy()
                    except tk.TclError:
                        pass
                cancel_timer("submenu_id")

            def make_popup(anchor, items, parent_popup=None):
                popup = tk.Toplevel(self)
                popup.withdraw()
                popup.overrideredirect(True)
                popup.transient(self)
                popup.configure(
                    background=self.theme_palette["border"],
                    highlightthickness=1,
                    highlightbackground=self.theme_palette["border"],
                )
                body = tk.Frame(
                    popup,
                    background=self.theme_palette["menu_bg"],
                    padx=3,
                    pady=3,
                )
                body.pack(fill="both", expand=True)
                state["windows"].append(popup)
                hover_jobs = []

                def cancel_popup_hover_jobs(event=None, owner=popup, jobs=hover_jobs):
                    # Destroy events also fire for child widgets; only the popup
                    # that owns these callbacks should cancel this callback set.
                    if event is not None and event.widget is not owner:
                        return
                    for hover_data in jobs:
                        job_id = hover_data.get("job")
                        if job_id is not None:
                            try:
                                self.after_cancel(job_id)
                            except tk.TclError:
                                pass
                            hover_data["job"] = None

                popup.bind("<Destroy>", cancel_popup_hover_jobs, add="+")

                def show_submenu(item_button, submenu_items):
                    cancel_timer("submenu_id")
                    # A menu can have several nested levels. Destroy every
                    # descendant of this popup before opening its new child;
                    # merely popping references leaves orphaned Toplevels visible.
                    close_descendant_popups(popup)
                    submenu = make_popup(item_button, submenu_items, popup)
                    submenu.update_idletasks()
                    x = popup.winfo_rootx() + popup.winfo_width() - 2
                    y = item_button.winfo_rooty()
                    screen_w = self.winfo_screenwidth()
                    if x + submenu.winfo_reqwidth() > screen_w:
                        x = popup.winfo_rootx() - submenu.winfo_reqwidth() + 2
                    submenu.geometry(f"+{max(0, x)}+{max(0, y)}")
                    submenu.deiconify()
                    submenu.lift()
                    schedule_poll()

                for item in items:
                    if item is None:
                        tk.Frame(
                            body,
                            height=1,
                            background=self.theme_palette["border"],
                        ).pack(fill="x", padx=7, pady=4)
                        continue
                    if item[0] == "submenu":
                        label, submenu_items = item[1], item[2]
                        # Resolve dynamic submenu contents when the parent is
                        # opened so recent-workspace entries never go stale.
                        if callable(submenu_items):
                            submenu_items = submenu_items()
                        command = None
                        shortcut = ""
                        display = f"{label}    ›"
                    else:
                        label, command, *shortcuts = item
                        shortcut = shortcuts[0] if shortcuts else ""
                        display = label
                        submenu_items = None

                    row = tk.Frame(body, background=self.theme_palette["menu_bg"])
                    row.pack(fill="x")
                    item_action = (
                        (lambda callback=command: (destroy_popups(), callback()))
                        if command is not None
                        else None
                    )
                    item_button = tk.Button(
                        row,
                        text=display,
                        anchor="w",
                        command=item_action,
                        relief="flat",
                        borderwidth=0,
                        highlightthickness=0,
                        takefocus=False,
                        padx=11,
                        pady=6,
                        background=self.theme_palette["menu_bg"],
                        foreground=self.theme_palette["menu_fg"],
                        activebackground=self.theme_palette["elevated"],
                        activeforeground=self.theme_palette["accent"],
                        font=(
                            self._resolved_ui_font(),
                            self.preferences.get("ui_font_size", 9),
                        ),
                        cursor="hand2",
                    )
                    item_button.pack(side="left", fill="x", expand=True)
                    shortcut_label = None
                    if shortcut:
                        shortcut_label = tk.Label(
                            row,
                            text=shortcut,
                            background=self.theme_palette["menu_bg"],
                            foreground=self.theme_palette["muted"],
                            font=(
                                self._resolved_ui_font(),
                                max(7, self.preferences.get("ui_font_size", 9) - 1),
                            ),
                            padx=8,
                        )
                        shortcut_label.pack(side="right")

                    # Hover feedback belongs to every command row inside the popup,
                    # not merely to the File/Edit category button in the toolbar.
                    hover_state = {"job": None}
                    hover_jobs.append(hover_state)

                    def highlight_menu_row(
                        _event=None,
                        target=row,
                        button_widget=item_button,
                        shortcut_widget=shortcut_label,
                        hover_data=hover_state,
                    ):
                        if hover_data["job"] is not None:
                            try:
                                self.after_cancel(hover_data["job"])
                            except tk.TclError:
                                pass
                            hover_data["job"] = None
                        active_bg = self.theme_palette["elevated"]
                        target.configure(background=active_bg)
                        button_widget.configure(
                            background=active_bg,
                            foreground=self.theme_palette["accent"],
                        )
                        if shortcut_widget is not None:
                            shortcut_widget.configure(
                                background=active_bg,
                                foreground=self.theme_palette["menu_fg"],
                            )

                    def clear_menu_row_hover(
                        _event=None,
                        target=row,
                        button_widget=item_button,
                        shortcut_widget=shortcut_label,
                        hover_data=hover_state,
                        owner_popup=popup,
                    ):
                        def settle():
                            hover_data["job"] = None
                            try:
                                # A delayed Leave callback may outlive its popup.
                                # Check both widgets before querying geometry or styling.
                                if (
                                    not owner_popup.winfo_exists()
                                    or not target.winfo_exists()
                                ):
                                    return
                                px, py = self.winfo_pointerxy()
                                inside = (
                                    target.winfo_rootx()
                                    <= px
                                    < target.winfo_rootx() + target.winfo_width()
                                    and target.winfo_rooty()
                                    <= py
                                    < target.winfo_rooty() + target.winfo_height()
                                )
                                if inside:
                                    return
                                normal_bg = self.theme_palette["menu_bg"]
                                target.configure(background=normal_bg)
                                button_widget.configure(
                                    background=normal_bg,
                                    foreground=self.theme_palette["menu_fg"],
                                )
                                if (
                                    shortcut_widget is not None
                                    and shortcut_widget.winfo_exists()
                                ):
                                    shortcut_widget.configure(
                                        background=normal_bg,
                                        foreground=self.theme_palette["muted"],
                                    )
                            except tk.TclError:
                                # The popup or one of its row widgets was destroyed
                                # while this idle callback was waiting to run.
                                return

                        try:
                            hover_data["job"] = self.after(45, settle)
                        except tk.TclError:
                            hover_data["job"] = None

                    for hover_widget in (row, item_button, shortcut_label):
                        if hover_widget is not None:
                            hover_widget.bind("<Enter>", highlight_menu_row, add="+")
                            hover_widget.bind("<Leave>", clear_menu_row_hover, add="+")

                    if submenu_items is not None:
                        item_button.bind(
                            "<Enter>",
                            lambda event, b=item_button, entries=submenu_items: (
                                cancel_timer("submenu_id"),
                                state.update(
                                    submenu_id=self.after(
                                        110, lambda: show_submenu(b, entries)
                                    )
                                ),
                            ),
                            add="+",
                        )
                    else:

                        def enter_command_row(_event=None, owner_popup=popup):
                            cancel_timer("submenu_id")
                            # A sibling command replaces the currently displayed
                            # cascade: keep this menu and its ancestors, but close
                            # every submenu opened from it.
                            close_descendant_popups(owner_popup)

                        item_button.bind(
                            "<Enter>",
                            enter_command_row,
                            add="+",
                        )
                popup.update_idletasks()
                req_w = max(210, popup.winfo_reqwidth())
                req_h = popup.winfo_reqheight()
                popup.geometry(f"{req_w}x{req_h}")
                return popup

            def post_menu():
                cancel_timer("open_id")
                if not button.winfo_exists():
                    return
                active_close = getattr(self, "_toolbar_menu_close", None)
                if active_close and active_close is not destroy_popups:
                    active_close()
                destroy_popups()
                state["closed"] = False
                state["outside_polls"] = 0
                self._toolbar_menu_close = destroy_popups
                popup = make_popup(button, commands)
                popup.update_idletasks()
                x = button.winfo_rootx()
                y = button.winfo_rooty() + button.winfo_height()
                if x + popup.winfo_reqwidth() > self.winfo_screenwidth():
                    x = self.winfo_screenwidth() - popup.winfo_reqwidth() - 4
                if y + popup.winfo_reqheight() > self.winfo_screenheight():
                    y = button.winfo_rooty() - popup.winfo_reqheight()
                popup.geometry(f"+{max(0, x)}+{max(0, y)}")
                popup.deiconify()
                popup.lift()
                schedule_poll()

            def open_on_hover(_event=None):
                button.state(["active"])
                cancel_timer("open_id")
                if state["closed"]:
                    state["open_id"] = self.after(150, post_menu)

            def click_menu(_event=None):
                if state["closed"]:
                    post_menu()
                else:
                    destroy_popups()
                return "break"

            button.bind("<Enter>", open_on_hover, add="+")
            button.bind(
                "<Leave>",
                lambda _event: (cancel_timer("open_id"), button.state(["!active"])),
                add="+",
            )
            button.bind("<Button-1>", click_menu, add="+")
            button.bind("<Button-3>", click_menu, add="+")
            return button

        add_menu(
            "File",
            "folder2-open",
            "accent",
            [
                ("New File    Ctrl+N", self.new_file),
                ("Open File    Ctrl+O", self.open_file),
                ("Open Workspace...", self.open_project_folder),
                (
                    "submenu",
                    "Open Recent Workspace…",
                    self._recent_workspace_toolbar_items,
                ),
                ("Quick Open    Ctrl+P", self.open_quick_file),
                None,
                ("Save    Ctrl+S", self.save_file),
                ("Save As...", self.save_as),
                ("Close Tab    Ctrl+W", self.close_tab),
                ("Close Workspace", self.close_workspace),
            ],
        )
        add_menu(
            "Edit",
            "pencil-square",
            "muted",
            [
                ("Find / Replace    Ctrl+H", self.find_replace),
                (
                    "Toggle Line Comment    Ctrl+/",
                    lambda: self.editor._toggle_comment(),
                ),
                ("Duplicate Line    Ctrl+D", lambda: self.editor._duplicate_line()),
                ("Go to Line    Ctrl+G", lambda: self.editor._go_to_line()),
            ],
        )
        add_menu(
            "Navigate",
            "search",
            "accent",
            [
                ("Quick Open File    Ctrl+P", self.open_quick_file),
                ("Command Palette    Ctrl+Shift+P", self.open_command_palette),
                ("Go to Line    Ctrl+G", lambda: self.editor._go_to_line()),
            ],
        )
        add_menu(
            "Run",
            "play-fill",
            "success",
            [
                ("Run Current File    F5", self.run_code),
                ("Stop Execution    Shift+F5", self.stop_execution),
            ],
        )
        add_menu(
            "Debug",
            "bug-fill",
            "violet",
            [
                (
                    "submenu",
                    "Session",
                    [
                        ("Start Debugging    Ctrl+F5", self.start_debugging),
                        ("Continue    Ctrl+F10", self.debug_continue),
                        ("Stop Debugging", self.stop_debugging),
                    ],
                ),
                (
                    "submenu",
                    "Stepping",
                    [
                        ("Step Over    F10", self.debug_next),
                        ("Step Into    F11", self.debug_step),
                        ("Run Until Line...", self.debug_until),
                        ("Run Until Return", self.debug_return),
                        ("Jump to Line...", self.debug_jump),
                    ],
                ),
                (
                    "submenu",
                    "Breakpoints",
                    [
                        ("Toggle Breakpoint    F9", self.toggle_breakpoint),
                        ("Temporary Breakpoint", self.debug_temporary_breakpoint),
                        (
                            "Conditional Breakpoint...",
                            self.debug_conditional_breakpoint,
                        ),
                        (
                            "Enable Breakpoint...",
                            lambda: self.debug_manage_breakpoint("enable"),
                        ),
                        (
                            "Disable Breakpoint...",
                            lambda: self.debug_manage_breakpoint("disable"),
                        ),
                        (
                            "Ignore Breakpoint Hits...",
                            lambda: self.debug_manage_breakpoint("ignore"),
                        ),
                        ("Clear All Breakpoints", self.debug_clear_breakpoints),
                    ],
                ),
                (
                    "submenu",
                    "Inspect",
                    [
                        ("Inspect Variables", self.debug_variables),
                        ("Show Call Stack", self.debug_stack),
                        ("Function Arguments", self.debug_arguments),
                        ("Evaluate Expression...", self.debug_evaluate),
                    ],
                ),
            ],
        )
        add_menu(
            "Code",
            "braces",
            "accent",
            [
                ("Analyze All    F6", self.analyze_all),
                ("Lexical Analysis", self.analyze_lexical),
                ("Syntax Analysis", self.analyze_syntax),
                None,
                ("Formatter, Linter & Tests", self.open_quality_tools),
                ("Dependencies", self.scan_dependencies),
                ("Clear Results", self.clear_results),
            ],
        )
        add_menu(
            "Tools",
            "sliders",
            "muted",
            [
                ("Integrated Terminal", self.open_terminal),
                ("Git Source Control", self.open_git_tools),
                ("Python Interpreter...", self.manage_interpreter),
            ],
        )
        add_menu(
            "View",
            "columns-gap",
            "muted",
            [
                ("Toggle Project Explorer", self.toggle_project_explorer),
                ("Preferences...", self.open_preferences),
                ("Switch Theme", self.toggle_theme),
            ],
        )
        add_menu(
            "Help",
            "question-circle",
            "muted",
            [
                ("Quick Start & Help...", self.show_help),
                ("Command Palette...", self.open_command_palette),
                ("About PyLex Studio...", self.show_about),
            ],
        )

        # The custom categorized menu row replaces the duplicate native menu bar.
        self.config(menu="")

        action_row = ttk.Frame(self, style="PyLex.Toolbar.TFrame", padding=(10, 3))
        action_row.pack(fill="x", side="top")

        # Keep the command row focused: frequent workspace tools only.
        action_groups = (
            (
                ("Workspace", "folder2-open", self.open_project_folder, "accent"),
                ("Python", "filetype-py", self.manage_interpreter, "muted"),
                ("Save", "floppy", self.save_file, "muted"),
            ),
            (
                ("Terminal", "terminal", self.open_terminal, "muted"),
                ("Quality", "check2-square", self.open_quality_tools, "muted"),
                ("Git", "git", self.open_git_tools, "muted"),
            ),
            (
                ("Analyze", "braces", self.analyze_all, "muted"),
                ("Debug", "bug-fill", self.start_debugging, "muted"),
            ),
        )
        for group_index, group in enumerate(action_groups):
            if group_index:
                ttk.Separator(action_row, orient="vertical").pack(
                    side="left", fill="y", padx=7, pady=5
                )
            for label, icon_name, command, color_key in group:
                button = ttk.Button(
                    action_row,
                    text=label,
                    command=command,
                    style="PyLex.Toolbar.TButton",
                    image=self._icon(icon_name, self.theme_palette.get(color_key)),
                    compound="left",
                )
                button.pack(side="left", padx=1, ipady=2)
                button.configure(takefocus=False)
                button.bind(
                    "<Enter>",
                    lambda _event, target=button: target.state(["active"]),
                    add="+",
                )
                button.bind(
                    "<Leave>",
                    lambda _event, target=button: target.state(["!active"]),
                    add="+",
                )
                self._toolbar_icon_bindings.append((button, icon_name, color_key))

        spacer = ttk.Frame(action_row, style="PyLex.Toolbar.TFrame")
        spacer.pack(side="left", fill="x", expand=True)
        # Keep the command launcher and execution controls together in a
        # compact right-hand stack. The launcher is an outlined, transparent
        # surface rather than a filled toolbar button.
        self.theme_button = ttk.Button(
            action_row,
            text="Theme",
            command=self.toggle_theme,
            style="PyLex.Toolbar.TButton",
            image=self._icon(
                "sun" if self.dark else "moon-stars",
                self.theme_palette.get("warning"),
            ),
            compound="left",
        )
        self.theme_button.pack(side="right", padx=(4, 0))
        self.theme_button.configure(takefocus=False)
        self._toolbar_icon_bindings.append(
            (self.theme_button, "sun" if self.dark else "moon-stars", "warning")
        )

        self.execution_controls = ttk.Frame(action_row, style="PyLex.Toolbar.TFrame")
        self.execution_controls.pack(side="right", padx=(8, 0))

        self.command_palette_frame = tk.Frame(
            self.execution_controls,
            background=self.theme_palette["surface"],
            highlightthickness=1,
            highlightbackground=self.theme_palette["border"],
            highlightcolor=self.theme_palette["accent"],
            cursor="hand2",
            width=250,
            height=31,
        )
        self.command_palette_frame.pack(fill="x", pady=(0, 4))
        self.command_palette_frame.pack_propagate(False)
        self.command_palette_label = tk.Label(
            self.command_palette_frame,
            text="⌕   Command Palette",
            anchor="w",
            padx=10,
            background=self.theme_palette["surface"],
            foreground=self.theme_palette["muted"],
            font=(self._resolved_ui_font(), self.preferences.get("ui_font_size", 9)),
            cursor="hand2",
        )
        self.command_palette_label.pack(fill="both", expand=True)
        for widget in (self.command_palette_frame, self.command_palette_label):
            widget.bind("<Button-1>", lambda _event: self.open_command_palette())
            widget.bind(
                "<Enter>",
                lambda _event: self.command_palette_frame.configure(
                    highlightbackground=self.theme_palette["accent"]
                ),
            )
            widget.bind(
                "<Leave>",
                lambda _event: self.command_palette_frame.configure(
                    highlightbackground=self.theme_palette["border"]
                ),
            )

        self.execution_button_row = ttk.Frame(
            self.execution_controls, style="PyLex.Toolbar.TFrame"
        )
        self.execution_button_row.pack(fill="x")
        self.run_button = ttk.Button(
            self.execution_button_row,
            text="Run  F5",
            command=self.run_code,
            style="PyLex.Run.TButton",
            image=self._icon("play-fill", self.theme_palette.get("accent")),
            compound="left",
            width=11,
        )
        self.run_button.pack(side="left", padx=(0, 5), ipady=2)
        self.run_button.configure(takefocus=False)
        self.stop_button = ttk.Button(
            self.execution_button_row,
            text="Stop  Shift+F5",
            command=self.stop_execution,
            style="PyLex.Stop.TButton",
            image=self._icon("stop-fill", self.theme_palette.get("danger")),
            compound="left",
            width=13,
        )
        self.stop_button.pack(side="left", ipady=2)
        self.stop_button.configure(takefocus=False)
        self._toolbar_icon_bindings.extend(
            [
                (self.run_button, "play-fill", "accent"),
                (self.stop_button, "stop-fill", "danger"),
            ]
        )
