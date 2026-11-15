"""Document and editor-tab state controller, independent from Tkinter."""

from pathlib import Path


class DocumentController:
    """Track document metadata and the active editor without owning its widgets."""

    def __init__(self, documents=None, active_editor=None):
        self.documents = documents if documents is not None else {}
        self.active_editor = active_editor

    def register(self, editor, metadata):
        if editor in self.documents:
            raise ValueError("The editor is already registered.")
        self.documents[editor] = metadata
        self.active_editor = editor
        return metadata

    def get(self, editor=None):
        return self.documents.get(editor if editor is not None else self.active_editor)

    def activate(self, editor):
        if editor not in self.documents:
            raise KeyError("The editor is not registered.")
        self.active_editor = editor
        return self.documents[editor]

    def find_path(self, path):
        target = Path(path).expanduser().resolve()
        for editor, document in self.documents.items():
            candidate = document.get("path")
            if (
                candidate is not None
                and Path(candidate).expanduser().resolve() == target
            ):
                return editor
        return None

    def mark_dirty(self, editor=None, dirty=True):
        document = self.get(editor)
        if document is None:
            return False
        document["dirty"] = bool(dirty)
        return True

    def remove(self, editor):
        document = self.documents.pop(editor, None)
        if self.active_editor is editor:
            self.active_editor = next(iter(self.documents), None)
        return document

    def clear(self):
        self.documents.clear()
        self.active_editor = None

    def __len__(self):
        return len(self.documents)
