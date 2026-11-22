"""Regression tests for the full-project audit fixes."""

import gc
import os
import sys
import threading
import time
import tkinter as tk
from types import SimpleNamespace

import pytest

from pylex.ui.context_menu import ContextMenu


def _menu():
    root = SimpleNamespace(theme_palette={})
    master = SimpleNamespace(winfo_toplevel=lambda: root)
    menu = ContextMenu(master, palette={})
    for label in ("a", "b", "c", "d"):
        menu.add_command(label=label)
    return menu


def test_context_menu_delete_single_index_keeps_other_items():
    menu = _menu()
    menu.delete(0)
    assert [item["label"] for item in menu.items] == ["b", "c", "d"]


def test_context_menu_delete_ranges_and_all():
    menu = _menu()
    menu.delete(1, "end")
    assert [item["label"] for item in menu.items] == ["a"]
    menu.delete(0, "end")
    assert menu.items == []
    menu = _menu()
    menu.delete("all")
    assert menu.items == []


def _close(root, editor):
    """Stop highlight workers before Tk objects are released on this thread."""
    editor._cancel_highlight_work()
    for thread in threading.enumerate():
        if thread.name == "pylex-syntax-highlighter":
            thread.join(timeout=5)
    root.destroy()
    gc.collect()


def _editor():
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("Tk GUI test requires a display (headless runner)")
    from pylex.editor import CodeEditor

    try:
        root = tk.Tk()
    except tk.TclError as error:
        pytest.skip(f"Tk display is unavailable: {error}")
    root.withdraw()
    return root, CodeEditor(root)


@pytest.mark.gui
def test_edit_inside_line_does_not_rebuild_gutter():
    root, editor = _editor()
    try:
        editor.set_content("a = 1\nb = 2\nc = 3\n")
        editor.update_idletasks()
        calls = []
        original = editor.refresh_lines
        editor.refresh_lines = lambda *a, **k: (calls.append(1), original())[1]
        editor.text.insert("1.5", "0")
        editor._refresh_lines_after_edit()
        assert calls == []
        editor.text.insert("end-1c", "\nd = 4")
        editor._refresh_lines_after_edit()
        assert calls == [1]
        assert editor.gutter.get("1.0", "end-1c").splitlines()[-1].strip() == "5"
    finally:
        _close(root, editor)


@pytest.mark.gui
def test_large_paste_applies_highlight_without_offset_indexes():
    root, editor = _editor()
    try:
        editor.set_content("")
        editor.text.insert("1.0", "def f():\n    return 'x'\n" * 300)
        editor.highlight()
        deadline = time.time() + 10
        while time.time() < deadline:
            root.update()
            time.sleep(0.01)
            if (
                editor.text.tag_ranges("py_keyword")
                and editor._highlight_apply_job is None
                and editor._highlight_poll_job is None
            ):
                break
        assert editor.text.tag_ranges("py_keyword")
    finally:
        _close(root, editor)
