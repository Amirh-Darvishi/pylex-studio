"""Regression tests for file-aware highlighting and large-file policies."""

from pygments.lexers import JavascriptLexer, JsonLexer, PythonLexer

from pylex.editor_performance import (
    LARGE_FILE_THRESHOLD,
    is_large_document,
    lexer_for_path,
)


def test_lexer_is_selected_from_document_extension():
    assert isinstance(lexer_for_path("settings.json"), JsonLexer)
    assert isinstance(lexer_for_path("client.js"), JavascriptLexer)
    assert isinstance(lexer_for_path("main.py"), PythonLexer)


def test_untitled_and_unknown_documents_keep_python_fallback():
    assert isinstance(lexer_for_path(None), PythonLexer)
    assert isinstance(lexer_for_path("unknown.customext"), PythonLexer)


def test_large_document_threshold_uses_size_or_line_count():
    assert not is_large_document("small text\n")
    assert is_large_document("x" * LARGE_FILE_THRESHOLD)
    assert is_large_document("\n" * 15000)
