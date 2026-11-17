"""Shared imports for the modular PyLex application UI."""
# ruff: noqa: F401

from . import __version__
from .commands import Command, CommandRegistry
from .controllers import (
    DebuggerController,
    DocumentController,
    ExecutionController,
    WorkspaceController,
)
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog, font as tkfont
import ttkbootstrap as ttkb
import queue
import threading
from pathlib import Path
import os
import subprocess
import shutil
import sys
import re
import time

from .editor import CodeEditor
from .analyzer import (
    lexical_analysis,
    syntax_analysis,
    format_tokens,
    collect_diagnostics,
)
from .dependencies import inspect_dependencies, python_environment
from .core.project import Project
from .core.file_types import file_type_for, read_text_file
from .services.execution import ExecutionService
from .preferences import DEFAULTS, load_preferences, save_preferences
from .interpreters import (
    create_virtual_environment,
    discover_interpreters,
    ensure_pip,
    find_project_environment,
    probe_interpreter,
)
from .terminal import TerminalPanel, python_file_command
from .quality import QualityPanel
from .git_panel import GitPanel
from .ui.theme import ThemeManager
from .ui.context_menu import ContextMenu
from .ui.command_palette import CommandPalette


# This module intentionally re-exports dependencies used by app mixins.
__all__ = [name for name in globals() if not name.startswith("_")] + ["__version__"]
