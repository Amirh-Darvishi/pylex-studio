"""Architecture checks for the modular PyLex application composition."""

import tkinter as tk

from pylex.app import PyLexApp
from pylex.app_parts import (
    AnalysisMixin,
    DebuggerMixin,
    DocumentsMixin,
    ExecutionMixin,
    PreferencesMixin,
    ShellMixin,
    WorkspaceMixin,
)


def test_application_remains_a_tk_root_and_composes_responsibility_mixins():
    assert issubclass(PyLexApp, tk.Tk)
    for mixin in (
        ShellMixin,
        WorkspaceMixin,
        DocumentsMixin,
        AnalysisMixin,
        ExecutionMixin,
        DebuggerMixin,
        PreferencesMixin,
    ):
        assert mixin in PyLexApp.__mro__


def test_major_responsibilities_are_owned_by_their_modules():
    assert "_menu" in ShellMixin.__dict__
    assert "_workspace" in ShellMixin.__dict__
    assert "_populate_project_tree" in WorkspaceMixin.__dict__
    assert "_create_document" in DocumentsMixin.__dict__
    assert "analyze_all" in AnalysisMixin.__dict__
    assert "run_code" in ExecutionMixin.__dict__
    assert "start_debugging" in DebuggerMixin.__dict__
    assert "open_preferences" in PreferencesMixin.__dict__


def test_composition_root_keeps_initialization_and_shutdown_ownership():
    assert "__init__" in PyLexApp.__dict__
    assert "close" in PyLexApp.__dict__
    for method in ("_menu", "_populate_project_tree", "run_code", "start_debugging"):
        assert method not in PyLexApp.__dict__
