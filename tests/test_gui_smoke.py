"""Display-aware smoke test for the real Tk application shell."""

import os
import sys
import tkinter as tk

import pytest

from pylex.app import PyLexApp
from pylex.preferences import DEFAULTS


@pytest.mark.gui
def test_application_window_starts_with_core_workspace_widgets(monkeypatch):
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        pytest.skip("Tk GUI smoke test requires a display (headless runner)")

    monkeypatch.setattr("pylex.app.load_preferences", lambda: dict(DEFAULTS))
    try:
        app = PyLexApp()
    except tk.TclError as error:
        if "display" in str(error).lower() or "screen" in str(error).lower():
            pytest.skip(f"Tk display is unavailable: {error}")
        raise

    try:
        app.update_idletasks()
        assert app.title() == "PyLex Studio"
        assert app.winfo_exists()
        assert app.workspace_shell.winfo_exists()
        assert app.status.winfo_exists()
        assert app.output.winfo_exists()
    finally:
        app.destroy()
