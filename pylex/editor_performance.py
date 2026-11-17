"""Performance policies and file-aware lexer selection for the editor."""

from pathlib import Path

from pygments import lex
from pygments.lexers import PythonLexer, get_lexer_for_filename
from pygments.util import ClassNotFound

LARGE_FILE_THRESHOLD = 512 * 1024
LARGE_DOCUMENT_LINE_THRESHOLD = 15000


def is_large_document(content, path=None):
    """Return whether content should use the editor's lightweight mode."""
    if path:
        try:
            if Path(path).stat().st_size >= LARGE_FILE_THRESHOLD:
                return True
        except OSError:
            pass
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


def build_token_spans(source, lexer, is_cancelled=None):
    """Tokenize source into offset spans without touching editor widgets.

    The optional predicate lets background callers abandon obsolete work
    between tokens. A cancelled operation returns None rather than partial tags.
    """
    spans = []
    offset = 0
    for token_type, value in lex(source, lexer):
        if is_cancelled is not None and is_cancelled():
            return None
        end = offset + len(value)
        if value:
            spans.append((token_type, offset, end))
        offset = end
    if is_cancelled is not None and is_cancelled():
        return None
    return spans
