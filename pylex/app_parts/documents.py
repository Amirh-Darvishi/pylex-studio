"""Documents responsibilities for the PyLex application."""

from ..app_support import *  # noqa: F403


class DocumentsMixin:
    """Documents UI behavior composed into :class:`PyLexApp`."""

    def _resolved_ui_font(self, available_fonts=None):
        """Choose a polished installed interface font on each supported platform."""
        available = set(available_fonts or tkfont.families(self))
        requested = self.preferences.get("ui_font_family", DEFAULTS["ui_font_family"])
        candidates = (
            requested,
            "Segoe UI",
            "Inter",
            "Noto Sans",
            "Ubuntu",
            "DejaVu Sans",
            "Arial",
            "Tahoma",
            "TkDefaultFont",
        )
        return next(
            (family for family in candidates if family in available), "TkDefaultFont"
        )

    def _resolved_code_font(self, available_fonts=None):
        """Choose the best installed coding font with reliable cross-platform fallbacks."""
        available = set(available_fonts or tkfont.families(self))
        requested = self.preferences.get("font_family", DEFAULTS["font_family"])
        candidates = (
            requested,
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
        return next(
            (family for family in candidates if family in available), "TkFixedFont"
        )

    def _tab_label(self, document):
        name = document["path"].name if document["path"] else "Untitled"
        return f"{'*' if document['dirty'] else ''}{name}  ×"

    def _on_tab_close_click(self, event):
        """Close a tab only when its visible close glyph is clicked."""
        try:
            index = self.editor_tabs.index(f"@{event.x},{event.y}")
            x, _y, width, _height = self.editor_tabs.bbox(index)
        except (tk.TclError, ValueError):
            return
        if event.x < x + width - 25:
            return
        frame = self.editor_tabs.tabs()[index]
        self.editor_tabs.select(frame)
        for editor, document in self.documents.items():
            if str(document["frame"]) == frame:
                self.editor = editor
                self._sync_active_document()
                self.close_tab()
                return "break"

    def close_tab(self):
        """Close the active document after resolving its unsaved changes."""
        document = self._active_document()
        if document is None or not self._confirm():
            return
        frame = document["frame"]
        self.editor_tabs.forget(frame)
        self.document_controller.remove(self.editor)
        self._refresh_open_editors()
        if not self.documents:
            self._create_document()
        else:
            selected = self.editor_tabs.select()
            for editor, item in self.documents.items():
                if str(item["frame"]) == selected:
                    self.editor = editor
                    break
            self._sync_active_document()
        self._set_diagnostics([])
        self.status.configure(text="Tab closed.")

    def _create_document(self, path=None, content=""):
        """Create a new editor tab and register its independent document state."""
        frame = ttk.Frame(self.editor_tabs)
        editor = CodeEditor(
            frame,
            on_change=lambda: self.mark_dirty(editor),
            on_cursor_change=lambda: self._update_editor_status(editor),
        )
        editor.pack(fill="both", expand=True)
        editor.indent_string = self._configured_indent_string()
        editor.text.bind("<<PyLexAnalyze>>", lambda _event: self.analyze_all(), add="+")
        editor.set_content(content)
        self.document_controller.register(
            editor,
            {
                "frame": frame,
                "path": Path(path) if path else None,
                "dirty": False,
            },
        )
        self._refresh_open_editors()
        document = self.documents[editor]
        if document["path"]:
            file_info = file_type_for(document["path"])
            tab_icon = self._file_icon_name(file_info.kind)
            tab_color = self.theme_palette.get(
                f"file_{file_info.kind}", self.theme_palette.get("editor_fg")
            )
        else:
            tab_icon = "file-earmark-plus"
            tab_color = self.theme_palette.get("accent")
        self.editor_tabs.add(
            frame,
            text=self._tab_label(document),
            image=self._icon(tab_icon, tab_color),
            compound="left",
        )
        self.editor_tabs.select(frame)
        self.editor = editor
        editor.set_font_family(self._resolved_code_font())
        editor.set_font_size(self.preferences["font_size"])
        editor.set_theme(self.dark, self.theme_palette)
        self._sync_active_document()
        self._update_editor_status(editor)
        self.editor.set_breakpoints(self.breakpoints.get(editor, set()))
        return editor

    def _active_document(self):
        return self.document_controller.get(self.editor)

    def _sync_active_document(self):
        document = self._active_document()
        if document is None:
            self.current_path = None
            self.dirty = False
            return
        self.current_path = document["path"]
        self.dirty = document["dirty"]
        self._title()

    def _on_tab_changed(self, event=None):
        selected = self.editor_tabs.select()
        if not selected:
            return
        for editor, document in self.documents.items():
            if str(document["frame"]) == selected:
                self.editor = editor
                self._sync_active_document()
                self.editor.set_breakpoints(self.breakpoints.get(self.editor, set()))
                self._set_diagnostics([])
                self._update_editor_status(editor)
                break

    def _title(self):
        # Keep the application identity stable; document names and dirty state
        # are represented by editor tabs and their modified markers.
        self.title("PyLex Studio")

    def _confirm(self):
        document = self._active_document()
        if document is None or not document["dirty"]:
            return True
        answer = messagebox.askyesnocancel(
            "Unsaved Changes",
            f"Save changes to {document['path'].name if document['path'] else 'Untitled'} before continuing?",
        )
        if answer is None:
            return False
        return self.save_file() if answer else True

    def new_file(self):
        self._create_document()

    def open_file(self):
        path = filedialog.askopenfilename(
            title="Open File",
            filetypes=[("All files", "*.*"), ("Python files", "*.py")],
        )
        if path:
            self._open_path(path)

    def save_file(self):
        document = self._active_document()
        if document is None:
            return False
        if document["path"] is None:
            return self.save_as()
        try:
            source = self.editor.get_content().replace("\r\n", "\n").replace("\r", "\n")
            eol = self.preferences.get("status_bar_eol", "Auto")
            if eol == "CRLF":
                source = source.replace("\n", "\r\n")
            encoding = self.preferences.get("status_bar_encoding", "UTF-8")
            codec = {
                "UTF-8": "utf-8",
                "UTF-8 with BOM": "utf-8-sig",
                "ASCII": "ascii",
            }.get(encoding, "utf-8")
            document["path"].write_text(source, encoding=codec, newline="")
            document["dirty"] = False
            self.editor_tabs.tab(document["frame"], text=self._tab_label(document))
            self._sync_active_document()
            self.status.configure(text="File saved.")
            return True
        except (OSError, UnicodeError) as exc:
            messagebox.showerror("Save Error", str(exc))
            return False

    def save_as(self):
        document = self._active_document()
        if document is None:
            return False
        path = filedialog.asksaveasfilename(
            defaultextension=".py",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")],
        )
        if not path:
            return False
        path = Path(path)
        for editor, other in self.documents.items():
            if (
                editor is not self.editor
                and other["path"]
                and other["path"].resolve() == path.resolve()
            ):
                messagebox.showerror(
                    "Save Error", "That file is already open in another tab."
                )
                return False
        document["path"] = path
        return self.save_file()

