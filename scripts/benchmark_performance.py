"""Repeatable, non-gating performance benchmarks for PyLex Studio hot paths.

Run from the repository root:
    python scripts/benchmark_performance.py --lines 5000 --files 500 --repeats 3

Compare results on the same machine, Python version, and workload. Timing results
are diagnostic only and deliberately do not create CI pass/fail thresholds.
"""

from __future__ import annotations

import argparse
import statistics
import sys
import tempfile
import time
import tracemalloc
from pathlib import Path

from pygments.lexers import PythonLexer
from pygments.token import Comment, Error, Keyword, Name, Number, Operator, Punctuation, String


def measure(label, operation, repeats):
    """Measure a callable and return median milliseconds plus peak MiB."""
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        operation()
        samples.append((time.perf_counter() - started) * 1000)

    tracemalloc.start()
    try:
        operation()
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return label, statistics.median(samples), peak / (1024 * 1024)


def make_source(lines):
    """Create deterministic valid Python source with repeatable code patterns."""
    blocks = [
        (
            f"def function_{index}(value):\n"
            f"    result = (value + {index}) * 2\n"
            "    if result > 10:\n"
            "        return result\n"
            "    return value"
        )
        for index in range(lines // 5)
    ]
    remainder = lines % 5
    if remainder:
        blocks.append("\n".join(f"value_{i} = {i}" for i in range(remainder)))
    return "\n".join(blocks) + ("\n" if blocks else "")


def make_workspace(root, file_count):
    """Create a bounded synthetic workspace for directory-scan benchmarks."""
    for index in range(file_count):
        folder = root / f"package_{index // 50:03d}"
        folder.mkdir(exist_ok=True)
        (folder / f"module_{index:05d}.py").write_text("value = 1\n", encoding="utf-8")


def positive_int(value):
    """Parse a positive CLI integer."""
    parsed = int(value)
    if parsed < 1:
        raise argparse.ArgumentTypeError("value must be greater than zero")
    return parsed


def non_negative_int(value):
    """Parse a non-negative CLI integer."""
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be zero or greater")
    return parsed


def main():
    # Support direct execution without requiring an editable installation.
    root_path = str(Path(__file__).resolve().parents[1])
    if root_path not in sys.path:
        sys.path.insert(0, root_path)

    from pylex.analyzer import collect_diagnostics, syntax_analysis
    from pylex.editor_features import find_matching_bracket
    from pylex.editor_performance import build_highlight_spans, build_token_spans
    from pylex.project_search import search_text
    from pylex.workspace_scan import iter_workspace_entries

    def editor_tag(token_type):
        if token_type in Keyword:
            return "py_keyword"
        if token_type in Comment:
            return "py_comment"
        if token_type in String:
            return "py_string"
        if token_type in Number:
            return "py_number"
        if token_type in Error:
            return "py_error"
        if token_type in Name.Function:
            return "py_function"
        if token_type in Name.Class:
            return "py_class"
        if token_type in Name.Builtin:
            return "py_builtin"
        if token_type in Operator or token_type in Punctuation:
            return "py_operator"
        return None

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lines", type=positive_int, default=5000)
    parser.add_argument("--files", type=non_negative_int, default=500)
    parser.add_argument("--repeats", type=positive_int, default=3)
    args = parser.parse_args()

    source = make_source(args.lines)
    lexer = PythonLexer()
    cursor = source.index("(")
    tasks = [
        ("Pygments token spans", lambda: build_token_spans(source, lexer)),
        (
            "Editor highlight spans",
            lambda: build_highlight_spans(source, lexer, editor_tag),
        ),
        ("AST syntax analysis", lambda: syntax_analysis(source)),
        ("Combined diagnostics", lambda: collect_diagnostics(source)),
        ("Bracket matching", lambda: find_matching_bracket(source, cursor)),
    ]

    print(f"Source: {len(source):,} chars / {source.count(chr(10)):,} lines")
    print(f"Workspace target: {args.files:,} files; repeats: {args.repeats}")
    print()
    print(f"{'Benchmark':<28} {'Median (ms)':>14} {'Peak MiB':>12}")
    print("-" * 56)
    for label, operation in tasks:
        name, elapsed, peak = measure(label, operation, args.repeats)
        print(f"{name:<28} {elapsed:>14.2f} {peak:>12.2f}")

    with tempfile.TemporaryDirectory(prefix="pylex-perf-") as directory:
        root = Path(directory)
        source_file = root / "benchmark_source.py"
        source_file.write_text(source, encoding="utf-8")
        name, elapsed, peak = measure(
            "Large-file read",
            lambda: source_file.read_text(encoding="utf-8"),
            args.repeats,
        )
        print(f"{name:<28} {elapsed:>14.2f} {peak:>12.2f}")

        workspace = root / "workspace"
        workspace.mkdir()
        make_workspace(workspace, args.files)
        name, elapsed, peak = measure(
            "Workspace scan",
            lambda: list(iter_workspace_entries(workspace)),
            args.repeats,
        )
        print(f"{name:<28} {elapsed:>14.2f} {peak:>12.2f}")
        name, elapsed, peak = measure(
            "Workspace search",
            lambda: search_text(workspace, "value"),
            args.repeats,
        )
        print(f"{name:<28} {elapsed:>14.2f} {peak:>12.2f}")


if __name__ == "__main__":
    main()
