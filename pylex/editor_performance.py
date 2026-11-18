"""Performance policies and file-aware lexer selection for the editor."""

from pathlib import Path

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
    return content.count("\\n") >= LARGE_DOCUMENT_LINE_THRESHOLD


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


def _iter_token_spans(source, lexer):
    """Yield source-relative token spans, using Pygments' offset-aware API."""
    tokenize_unprocessed = getattr(lexer, "get_tokens_unprocessed", None)
    if callable(tokenize_unprocessed):
        for start, token_type, value in tokenize_unprocessed(source):
            if value:
                yield token_type, start, start + len(value)
        return

    # Compatibility fallback for custom lexers that expose only get_tokens().
    offset = 0
    for token_type, value in lexer.get_tokens(source):
        end = offset + len(value)
        if value:
            yield token_type, offset, end
        offset = end


def build_token_spans(source, lexer, is_cancelled=None):
    """Tokenize source into exact offset spans without touching editor widgets.

    Pygments' unprocessed-token API supplies offsets directly, avoiding a second
    character-by-character offset accumulation pass. Cancellation discards
    partial output rather than returning incomplete highlighting information.
    """
    spans = []
    for token_type, start, end in _iter_token_spans(source, lexer):
        if is_cancelled is not None and is_cancelled():
            return None
        spans.append((token_type, start, end))
    if is_cancelled is not None and is_cancelled():
        return None
    return spans


def build_highlight_spans(source, lexer, tag_for_token, is_cancelled=None):
    """Build only visible editor tag spans, avoiding an intermediate token list."""
    spans = []
    for token_type, start, end in _iter_token_spans(source, lexer):
        if is_cancelled is not None and is_cancelled():
            return None
        tag = tag_for_token(token_type)
        if tag is not None:
            spans.append((tag, start, end))
    if is_cancelled is not None and is_cancelled():
        return None
    return spans
