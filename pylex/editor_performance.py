"""Performance policies and file-aware lexer selection for the editor."""

from pathlib import Path

from pygments.lexers import PythonLexer, get_lexer_for_filename
from pygments.util import ClassNotFound

LARGE_FILE_THRESHOLD = 512 * 1024
LARGE_DOCUMENT_LINE_THRESHOLD = 15000


def is_large_document(content):
    """Return whether content should use the editor's lightweight mode."""
    if len(content) >= LARGE_FILE_THRESHOLD:
        return True
    return content.count("\n") >= LARGE_DOCUMENT_LINE_THRESHOLD


def lexer_for_path(path):
    """Return a Pygments lexer appropriate for a file path."""
    if not path:
        return PythonLexer()
    try:
        return get_lexer_for_filename(
            Path(path).name,
            stripnl=False,
            ensurenl=False,
        )
    except ClassNotFound:
        return PythonLexer()
