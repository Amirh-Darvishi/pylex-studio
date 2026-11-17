"""Independent lexical and syntax analysis for Python source code."""

import ast
import builtins
import io
import keyword
import tokenize
from dataclasses import dataclass
from typing import Optional


@dataclass
class TokenInfo:
    """A lexical token with its type, value, and source span (zero-based columns)."""

    token_type: str
    value: str
    line: int
    column: int
    end_line: Optional[int] = None
    end_column: Optional[int] = None


@dataclass
class AnalysisResult:
    """Result of syntax analysis, including a precise diagnostic location."""

    success: bool
    message: str
    details: str = ""
    line: Optional[int] = None
    column: Optional[int] = None
    error_type: Optional[str] = None
    end_line: Optional[int] = None
    end_column: Optional[int] = None
    source_line: str = ""


@dataclass(frozen=True)
class Diagnostic:
    """A normalized issue that can be displayed and navigated to in the editor."""

    error_type: str
    message: str
    line: int
    column: int
    end_line: Optional[int] = None
    end_column: Optional[int] = None
    source_line: str = ""

    @property
    def identity(self):
        return (self.error_type, self.message, self.line, self.column)


def _line_text(source: str, line: Optional[int]) -> str:
    if not line or line < 1:
        return ""
    lines = source.splitlines()
    return lines[line - 1] if line <= len(lines) else ""


def _syntax_error_diagnostic(exc: SyntaxError, source: str) -> Diagnostic:
    """Convert Python's SyntaxError family into a zero-based editor location."""
    line = exc.lineno or 1
    # SyntaxError.offset is one-based; Tk Text columns are zero-based.
    column = max(0, (exc.offset or 1) - 1)
    end_line = getattr(exc, "end_lineno", None)
    end_offset = getattr(exc, "end_offset", None)
    end_column = max(0, end_offset - 1) if end_offset else None
    return Diagnostic(
        type(exc).__name__,
        exc.msg or str(exc),
        line,
        column,
        end_line,
        end_column,
        _line_text(source, line),
    )


def _token_error_diagnostic(exc: tokenize.TokenError, source: str) -> Diagnostic:
    message = str(exc.args[0]) if exc.args else "Tokenization failed."
    location = exc.args[1] if len(exc.args) > 1 else (1, 0)
    line, column = location
    return Diagnostic(
        "TokenError",
        message,
        max(1, line),
        max(0, column),
        line,
        column,
        _line_text(source, line),
    )


def lexical_analysis(source: str, is_cancelled=None):
    """Tokenize source with Python tokenize, retaining start and end positions.

    Tokenization errors are intentionally raised so callers can distinguish a
    partial token stream from a complete lexical analysis.
    """
    result = []
    generated = []
    for item in tokenize.generate_tokens(io.StringIO(source).readline):
        if is_cancelled is not None and is_cancelled():
            return None
        generated.append(item)
    # Some Python versions emit an ERRORTOKEN for an unterminated quote
    # instead of raising TokenError. Ask the parser for its canonical error.
    if any(item.type == tokenize.ERRORTOKEN for item in generated):
        ast.parse(source)
    for item in generated:
        if item.type in (tokenize.ENCODING, tokenize.ENDMARKER):
            continue
        name = tokenize.tok_name.get(item.type, str(item.type))
        if item.type == tokenize.NAME:
            if keyword.iskeyword(item.string):
                name = "KEYWORD"
            elif item.string in vars(builtins) and not item.string.startswith("__"):
                name = "BUILTIN"
            else:
                name = "NAME"
        result.append(
            TokenInfo(
                name,
                item.string,
                item.start[0],
                item.start[1],
                item.end[0],
                item.end[1],
            )
        )
    return result


def syntax_analysis(source: str) -> AnalysisResult:
    """Validate Python syntax with ast.parse and return structured diagnostics."""
    try:
        tree = ast.parse(source)
        count = sum(1 for _ in ast.walk(tree))
        return AnalysisResult(
            True, "Syntax analysis completed successfully.", f"AST node count: {count}"
        )
    except SyntaxError as exc:
        diagnostic = _syntax_error_diagnostic(exc, source)
        return AnalysisResult(
            False,
            diagnostic.message,
            "",
            diagnostic.line,
            diagnostic.column + 1,
            diagnostic.error_type,
            diagnostic.end_line,
            diagnostic.end_column,
            diagnostic.source_line,
        )
    except (ValueError, TypeError) as exc:
        return AnalysisResult(
            False, str(exc), type(exc).__name__, error_type=type(exc).__name__
        )


def collect_diagnostics(source: str, is_cancelled=None):
    """Collect lexical and parser diagnostics, removing duplicate reports."""
    found = []
    try:
        lexical_result = lexical_analysis(source, is_cancelled)
        if lexical_result is None and is_cancelled is not None and is_cancelled():
            return None
    except tokenize.TokenError as exc:
        found.append(_token_error_diagnostic(exc, source))
    except SyntaxError as exc:
        found.append(_syntax_error_diagnostic(exc, source))
    except (ValueError, TypeError) as exc:
        found.append(
            Diagnostic(
                type(exc).__name__, str(exc), 1, 0, source_line=_line_text(source, 1)
            )
        )

    if is_cancelled is not None and is_cancelled():
        return None
    syntax = syntax_analysis(source)
    if not syntax.success and syntax.error_type:
        candidate = Diagnostic(
            syntax.error_type,
            syntax.message,
            syntax.line or 1,
            max(0, (syntax.column or 1) - 1),
            syntax.end_line,
            syntax.end_column,
            syntax.source_line,
        )
        found.append(candidate)

    if is_cancelled is not None and is_cancelled():
        return None

    # A tokenizer EOF report and the parser's SyntaxError often describe the
    # same unclosed delimiter/string, but with different messages and columns.
    # Prefer the parser's more actionable explanation for that source line.
    parser_diagnostics = [
        item
        for item in found
        if item.error_type in {"SyntaxError", "IndentationError", "TabError"}
    ]
    parser_lines = {item.line for item in parser_diagnostics}
    filtered = [
        item
        for item in found
        if not (
            item.error_type == "TokenError"
            and (
                item.line in parser_lines
                or (
                    parser_diagnostics and "EOF in multi-line statement" in item.message
                )
            )
        )
    ]

    unique = {}
    for item in filtered:
        # When both stages report the same message on the same line, retain the
        # parser diagnostic added last, which has the parser's source position.
        unique[(item.message, item.line)] = item
    return sorted(
        unique.values(), key=lambda item: (item.line, item.column, item.error_type)
    )


def format_tokens(tokens):
    """Format lexical tokens as an English-language report with token spans."""
    lines = [
        f"{'TYPE':<18} {'LINE':>5} {'COLUMN':>7} {'END':>10}  VALUE",
        "-" * 78,
    ]
    for token in tokens:
        value = token.value.replace("\n", r"\n").replace("\t", r"\t")
        end = (
            f"{token.end_line}:{token.end_column}"
            if token.end_line is not None and token.end_column is not None
            else "-"
        )
        lines.append(
            f"{token.token_type:<18} {token.line:>5} {token.column:>7} "
            f"{end:>10}  {value}"
        )
    return "\n".join(lines) if tokens else "No tokens found."
