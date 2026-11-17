"""Composable UI responsibility mixins for :class:`pylex.app.PyLexApp`."""

from .analysis import AnalysisMixin
from .debugger import DebuggerMixin
from .documents import DocumentsMixin
from .execution import ExecutionMixin
from .preferences import PreferencesMixin
from .shell import ShellMixin
from .workspace import WorkspaceMixin

__all__ = [
    "AnalysisMixin",
    "DebuggerMixin",
    "DocumentsMixin",
    "ExecutionMixin",
    "PreferencesMixin",
    "ShellMixin",
    "WorkspaceMixin",
]
