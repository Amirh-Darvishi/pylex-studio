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


def _find_matching_bracket_with_pygments(source, cursor_offset, is_cancelled=None):
    """Compatibility fallback for incomplete code and legacy f-string tokenization."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    reverse = {value: key for key, value in pairs.items()}
    delimiters = []
    offset = 0
    for token_type, value in lex(source, PythonLexer()):
        if is_cancelled is not None and is_cancelled():
            return None
        if token_type in Punctuation:
            for index, char in enumerate(value):
                if char in pairs or char in reverse:
                    delimiters.append((offset + index, char))
        offset += len(value)
    return _match_delimiter_sequence(delimiters, cursor_offset, is_cancelled)


def _match_delimiter_sequence(delimiters, cursor_offset, is_cancelled=None):
    """Match one selected delimiter from an ordered sequence of offsets."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    reverse = {value: key for key, value in pairs.items()}
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
            if is_cancelled is not None and is_cancelled():
                return None
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
            if is_cancelled is not None and is_cancelled():
                return None
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


def find_matching_bracket(source, cursor_offset, is_cancelled=None):
    """Return matching delimiter offsets, using Python's tokenizer when possible.

    The standard-library tokenizer is substantially lighter than Pygments for
    this task. Pygments remains the compatibility fallback for incomplete
    source and f-strings on Python versions whose tokenizer treats them as one
    opaque STRING token.
    """
    pairs = {"(": ")", "[": "]", "{": "}"}
    reverse = {value: key for key, value in pairs.items()}
    line_offsets = [0]
    line_offsets.extend(
        index + 1 for index, char in enumerate(source) if char == "\\n"
    )
    delimiters = []
    try:
        for item in tokenize.generate_tokens(StringIO(source).readline):
            if is_cancelled is not None and is_cancelled():
                return None
            if item.type == tokenize.STRING:
                quote_index = next(
                    (
                        index
                        for index, char in enumerate(item.string)
                        if char in {"'", '"'}
                    ),
                    len(item.string),
                )
                prefix = item.string[:quote_index].lower()
                if "f" in prefix:
                    return _find_matching_bracket_with_pygments(
                        source, cursor_offset, is_cancelled
                    )
            if item.type != tokenize.OP or item.string not in pairs | reverse:
                continue
            row, column = item.start
            position = line_offsets[row - 1] + column
            delimiters.append((position, item.string))
    except (tokenize.TokenError, IndentationError):
        return _find_matching_bracket_with_pygments(
            source, cursor_offset, is_cancelled
        )

    return _match_delimiter_sequence(delimiters, cursor_offset, is_cancelled)
