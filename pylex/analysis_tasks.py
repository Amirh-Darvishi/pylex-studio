"""Background lexical and syntax analysis tasks for the PyLex UI."""

from .analyzer import (
    collect_diagnostics,
    format_tokens,
    lexical_analysis,
    syntax_analysis,
)


def analyze_source(source, mode="all", is_cancelled=None):
    """Analyze a source snapshot without accessing Tk widgets.

    mode may be lexical, syntax or all. Completed phases are reused when
    diagnostics are assembled so a full analysis does not tokenize or parse
    the same source repeatedly.
    """
    if mode not in {"lexical", "syntax", "all"}:
        raise ValueError(f"Unsupported analysis mode: {mode}")

    def cancelled():
        return is_cancelled is not None and is_cancelled()

    result = {"mode": mode}
    lexical_checked = False
    lexical_error = None
    syntax = None

    if mode in {"lexical", "all"}:
        try:
            tokens = lexical_analysis(source, is_cancelled)
            if tokens is None:
                return None
            result["lexical_report"] = format_tokens(tokens)
            result["lexical_count"] = len(tokens)
            result["lexical_error"] = None
        except Exception as exc:
            lexical_error = exc
            result["lexical_report"] = f"{type(exc).__name__}: {exc}"
            result["lexical_count"] = None
            result["lexical_error"] = type(exc).__name__
        lexical_checked = True

    if cancelled():
        return None

    if mode in {"syntax", "all"}:
        syntax = syntax_analysis(source)
        result["syntax"] = syntax
        result["syntax_report"] = f"{syntax.error_type or 'Success'}: {syntax.message}"
        if syntax.details:
            result["syntax_report"] += f"\\n{syntax.details}"
        if syntax.line is not None:
            result[
                "syntax_report"
            ] += f"\\nLine: {syntax.line} | Column: {syntax.column}"

    if cancelled():
        return None

    result["diagnostics"] = collect_diagnostics(
        source,
        is_cancelled,
        lexical_checked=lexical_checked,
        lexical_error=lexical_error,
        syntax_result=syntax,
    )
    return None if cancelled() else result
