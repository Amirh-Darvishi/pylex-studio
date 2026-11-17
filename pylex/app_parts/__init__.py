"""Composable UI responsibility mixins for :class:`pylex.app.PyLexApp`."""

from .analysis import AnalysisMixin
from .debugger import DebuggerMixin
from .documents import DocumentsMixin
from .execution import ExecutionMixin
from .preferences import PreferencesMixin
from .panels import PanelsMixin
from .shell import ShellMixin
from .workspace import WorkspaceMixin
from .toolbar import ToolbarMixin

__all__ = [
    "AnalysisMixin",
    "DebuggerMixin",
    "DocumentsMixin",
    "ExecutionMixin",
    "PreferencesMixin",
    "PanelsMixin",
    "ShellMixin",
    "WorkspaceMixin",
    "ToolbarMixin",
]
