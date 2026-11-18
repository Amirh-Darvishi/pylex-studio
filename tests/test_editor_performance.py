"""Regression tests for file-aware highlighting and large-file policies."""

from pygments.lexers import JavascriptLexer, JsonLexer, PythonLexer
from pygments.token import Keyword

from pylex.editor_performance import (
    LARGE_FILE_THRESHOLD,
    build_token_spans,
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


def test_large_file_mode_uses_actual_file_size(tmp_path):
    path = tmp_path / "large.json"
    path.write_bytes(b"x" * LARGE_FILE_THRESHOLD)
    assert is_large_document("small decoded content", path)


def test_token_spans_preserve_source_offsets():
    source = "if ready:\n    print('ok')\n"
    spans = build_token_spans(source, PythonLexer())

    assert spans is not None
    assert spans[0][1:] == (0, 2)
    assert spans[0][0] in Keyword
    assert spans[-1][2] == len(source)


def test_token_span_generation_can_be_cancelled():
    source = "print('a lot of source')\n" * 100

    assert build_token_spans(source, PythonLexer(), lambda: True) is None


def test_token_spans_use_exact_source_offsets_for_unicode_and_newlines():
    source = "\n# café\nvalue = 42\n"
    lexer = PythonLexer(stripnl=False, ensurenl=False)

    spans = build_token_spans(source, lexer)

    assert spans is not None
    assert all(source[start:end] for _token, start, end in spans)
    assert spans[-1][2] == len(source)
    assert any("café" in source[start:end] for _token, start, end in spans)


def test_editor_token_tag_mapping_preserves_pygments_categories():
    from pylex.editor import CodeEditor
    from pygments.token import (
        Comment,
        Error,
        Name,
        Number,
        Operator,
        Punctuation,
        String,
    )

    assert CodeEditor._tag_for_token(Keyword) == "py_keyword"
    assert CodeEditor._tag_for_token(Comment.Single) == "py_comment"
    assert CodeEditor._tag_for_token(String.Double) == "py_string"
    assert CodeEditor._tag_for_token(Number.Integer) == "py_number"
    assert CodeEditor._tag_for_token(Error) == "py_error"
    assert CodeEditor._tag_for_token(Name.Function) == "py_function"
    assert CodeEditor._tag_for_token(Name.Class) == "py_class"
    assert CodeEditor._tag_for_token(Name.Builtin) == "py_builtin"
    assert CodeEditor._tag_for_token(Operator) == "py_operator"
    assert CodeEditor._tag_for_token(Punctuation) == "py_operator"
    assert CodeEditor._tag_for_token(Name) is None


def test_highlight_spans_keep_only_tokens_with_editor_tags():
    from pylex.editor_performance import build_highlight_spans

    source = "if ready:\n    value = 'ok'\n"
    spans = build_highlight_spans(
        source,
        PythonLexer(stripnl=False, ensurenl=False),
        lambda token: "keyword" if token in Keyword else None,
    )

    assert spans == [("keyword", 0, 2)]


def test_highlight_span_generation_can_be_cancelled():
    from pylex.editor_performance import build_highlight_spans

    source = "if ready:\n    print('ok')\n"
    assert (
        build_highlight_spans(source, PythonLexer(), lambda _token: "tag", lambda: True)
        is None
    )
