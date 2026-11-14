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
    """A lexical token with its type, value, and source position."""
    token_type: str
    value: str
    line: int
    column: int


@dataclass
class AnalysisResult:
    """Result of syntax analysis, including optional error location."""
    success: bool
    message: str
    details: str = ""
    line: Optional[int] = None
    column: Optional[int] = None


def lexical_analysis(source: str):
    """Tokenize Python source independently of the syntax highlighter.

    Args:
        source: Python source code.

    Returns:
        TokenInfo objects containing token type, value, line, and column.

    Raises:
        tokenize.TokenError or IndentationError: If tokenization fails.
    """
    result = []
    for item in tokenize.generate_tokens(io.StringIO(source).readline):
        if item.type in (tokenize.ENCODING, tokenize.ENDMARKER):
            continue
        name = tokenize.tok_name.get(item.type, str(item.type))
        if item.type == tokenize.NAME:
            if keyword.iskeyword(item.string):
                name = "KEYWORD"
            elif item.string in vars(builtins):
                name = "BUILTIN" if not item.string.startswith("__") else "NAME"
            else:
                name = "NAME"
        result.append(TokenInfo(name, item.string, item.start[0], item.start[1]))
    return result


def syntax_analysis(source: str):
    """Validate Python syntax with ast.parse and return structured diagnostics."""
    try:
        tree = ast.parse(source)
        count = sum(1 for _ in ast.walk(tree))
        return AnalysisResult(True, "Syntax analysis completed successfully.",
                              f"AST node count: {count}")
    except SyntaxError as exc:
        return AnalysisResult(False, exc.msg or "Invalid syntax.", "SyntaxError",
                              exc.lineno, exc.offset)
    except (ValueError, TypeError) as exc:
        return AnalysisResult(False, str(exc), type(exc).__name__)


def format_tokens(tokens):
    """Format lexical tokens as an English-language report."""
    lines = [f"{'TYPE':<18} {'LINE':>5} {'COLUMN':>7}  VALUE", "-" * 65]
    for token in tokens:
        value = token.value.replace("\n", r"\n").replace("\t", r"\t")
        lines.append(f"{token.token_type:<18} {token.line:>5} {token.column:>7}  {value}")
    return "\n".join(lines) if tokens else "No tokens found."
