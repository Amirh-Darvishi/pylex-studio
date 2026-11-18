"""Repeatable, non-gating performance benchmarks for PyLex Studio hot paths.

Run from the repository root:
    python scripts/benchmark_performance.py --lines 5000 --files 500 --repeats 3

These timings are diagnostic only: they are not CI pass/fail thresholds and should
be compared on the same machine, Python version, and workload.
"""

from __future__ import annotations

import argparse
import statistics
import tempfile
import time
import tracemalloc
from pathlib import Path

from pygments.lexers import PythonLexer

from pylex.analyzer import collect_diagnostics, syntax_analysis
from pylex.editor_features import find_matching_bracket
from pylex.editor_performance import build_token_spans
from pylex.workspace_scan import iter_workspace_entries


def measure(label, operation, repeats):
    """Measure a callable and return median milliseconds plus peak MiB."""
    samples = []
    for _ in range(repeats):
        started = time.perf_counter()
        operation()
        samples.append((time.perf_counter() - started) * 1000

    tracemalloc.start()
    operation()
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    return label, statistics.median(samples), peak / (1024 * 1024)


def make_source(lines):
    """Create deterministic valid Python source with repeated nested structures."""
    return "\n".join(
        f"def function_{i}(value):\n"
        f"    result = (value + {i}) * 2\n"
        f"    if result > 10:\n"
        f"        return result\n"
        f"    return value"
        for i in range(max(1, lines // 5))
    ) + "\n"


def make_workspace(root, file_count):
    """Create a bounded synthetic workspace for directory-scan benchmarks."""
    for index in range(file_count):
        folder = root / f"package_{index // 50:03d}"
        folder.mkdir(exist_ok=True)
        (folder / f"module_{index:05d}.py").write_text(
            "value = 1\n", encoding="utf-8"
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lines", type=int, default=5000)
    parser.add_argument("--files", type=int, default=500)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()

    source = make_source(args.lines)
    lexer = PythonLexer()
    cursor = max(0, len(source) - 1)
    tasks = [
        ("Pygments token spans", lambda: build_token_spans(source, lexer)),
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
        make_workspace(root, args.files)
        name, elapsed, peak = measure(
            "Workspace scan",
            lambda: list(iter_workspace_entries(root)),
            args.repeats,
        )
        print(f"{name:<28} {elapsed:>14.2f} {peak:>12.2f}")


if __name__ == "__main__":
    main()
