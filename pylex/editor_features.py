"""Pure text helpers for Smart Editor behaviour."""

from io import StringIO
import tokenize

from pygments import lex
from pygments.lexers import PythonLexer
from pygments.token import Punctuation


def indentation_for_newline(source_line, indent_width=4):
    """Return indentation for a newline after a Python source line."""
    leading = source_line[: len(source_line) - len(source_line.lstrip(" \t"))]
    try:
        tokens = [
            item
            for item in tokenize.generate_tokens(StringIO(source_line).readline)
            if item.type
            not in {
                tokenize.ENCODING,
                tokenize.NL,
                tokenize.NEWLINE,
                tokenize.INDENT,
                tokenize.DEDENT,
                tokenize.COMMENT,
                tokenize.ENDMARKER,
            }
        ]
    except (tokenize.TokenError, IndentationError):
        tokens = []
    if tokens and tokens[-1].type == tokenize.OP and tokens[-1].string == ":":
        return leading + (" " * indent_width)
    return leading


def smart_backspace_prefix(prefix, indent_width=4):
    """Return the indentation prefix after one smart backspace, or None."""
    if not prefix or prefix.strip(" \t"):
        return None
    width = max(1, int(indent_width))
    current = len(prefix.expandtabs(width))
    target = ((current - 1) // width) * width
    return " " * target


def toggle_comment_block(source):
    """Toggle Python-style comments for a block, preserving indentation."""
    lines = source.splitlines(keepends=True)
    nonblank = [line for line in lines if line.strip()]
    if not nonblank:
        return source
    uncomment = all(line.lstrip().startswith("#") for line in nonblank)
    result = []
    for line in lines:
        ending = (
            "\r\n" if line.endswith("\r\n") else "\n" if line.endswith("\n") else ""
        )
        body = line[: -len(ending)] if ending else line
        if not body.strip():
            result.append(line)
            continue
        indent = body[: len(body) - len(body.lstrip(" \t"))]
        content = body[len(indent) :]
        if uncomment and content.startswith("#"):
            content = content[1:]
            if content.startswith(" "):
                content = content[1:]
        elif not uncomment:
            content = "# " + content
        result.append(indent + content + ending)
    return "".join(result)


def find_matching_bracket(source, cursor_offset):
    """Return matching delimiter offsets around the cursor, ignoring strings/comments."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    reverse = {value: key for key, value in pairs.items()}
    delimiters = []
    offset = 0
    for token_type, value in lex(source, PythonLexer()):
        if token_type in Punctuation:
            for index, char in enumerate(value):
                if char in pairs or char in reverse:
                    delimiters.append((offset + index, char))
        offset += len(value)
    if not delimiters:
        return None
    selected = next(
        (item for item in delimiters if item[0] == cursor_offset),
        next((item for item in delimiters if item[0] == cursor_offset - 1), None),
    )
    if selected is None:
        return None
    position, char = selected
    if char in pairs:
        stack = []
        for candidate, value in delimiters:
            if candidate < position:
                continue
            if value in pairs:
                stack.append((candidate, value))
            elif value in reverse:
                if not stack or pairs[stack[-1][1]] != value:
                    return None
                stack.pop()
                if not stack:
                    return (position, candidate)
    else:
        stack = []
        for candidate, value in reversed(delimiters):
            if candidate > position:
                continue
            if value in reverse:
                stack.append((candidate, value))
            elif value in pairs:
                if not stack or reverse[stack[-1][1]] != value:
                    return None
                stack.pop()
                if not stack:
                    return (candidate, position)
    return None
