# PyLex Studio Performance Benchmarks

This document describes the repeatable, non-gating benchmark harness used during the 2.7.0 performance work.

## Run locally

From the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_performance.py --lines 5000 --files 500 --warmups 1 --repeats 5
.\.venv\Scripts\python.exe scripts/benchmark_performance.py --lines 20000 --files 2000 --warmups 1 --repeats 5
```

The script also works with a regular Python executable:

```bash
python scripts/benchmark_performance.py --lines 5000 --files 500 --warmups 1 --repeats 5
```

- `--lines`: number of source lines in the deterministic Python workload.
- `--files`: number of synthetic workspace files.
- `--warmups`: untimed warm-up runs before collecting samples (default: 1).
- `--repeats`: number of timed samples; the reported duration is the median (default: 5).

The output records the Python and Pygments versions. Use the same machine, Python version, workload, warm-up/repeat counts, and broadly similar system load when comparing results. The harness deliberately has no CI timing thresholds because hosted-runner timing is variable.

## Measurements

| Benchmark | What it measures |
|---|---|
| Pygments token spans | Tokenization and source-relative token span creation |
| Editor highlight spans | Tokenization plus filtering to the tags actually applied by the editor |
| Lexical analysis | Python tokenizer traversal and retained lexical token records |
| AST syntax analysis | Parsing and AST node counting |
| Standalone diagnostics | Lexical validation plus parser diagnostics without reusing prior analysis phases |
| Full analysis workflow | The production `analyze_source(mode="all")` pipeline, including lexical output, syntax output, and reused diagnostics |
| Bracket matching | Finding the matching delimiter at a cursor offset |
| Large-file read | Reading a generated source file from disk |
| Workspace scan | Enumerating a synthetic workspace using the Explorer scanner |
| Workspace search | Searching supported text files and creating match/snapshot results |

Each benchmark reports median elapsed time in milliseconds and peak Python allocation measured with `tracemalloc`. Peak MiB is not the application's total resident memory. Large-file read measures disk reading only; it does not measure inserting text into Tkinter widgets. UI responsiveness must also be checked in the running application.

The harness uses one warm-up by default to reduce first-run effects, then reports the median of timed samples. Peak allocation is measured in a separate run and should be treated as an approximate per-operation Python allocation peak, not process-wide memory use.

## Initial Windows baseline

The initial 2.7.0 baseline was collected locally on Windows with Python 3.13 and three timed repeats, before warm-up support and the expanded benchmark set were added.

| Operation | 5,000 lines / 500 files (ms) | 20,000 lines / 2,000 files (ms) |
|---|---:|---:|
| Pygments token spans | 593.22 | 2,442.58 |
| AST syntax analysis | 84.44 | 360.45 |
| Combined diagnostics | 195.55 | 800.00 |
| Bracket matching | 614.17 | 2,836.87 |
| Large-file read | 0.20 | 1.26 |
| Workspace scan | 28.61 | 122.88 |

**Important:** the initial figures are historical reference measurements from the earlier harness. Because the harness now includes warm-ups and additional production-pipeline measurements, compare new runs against other runs made with the same harness version. Do not interpret differences between the old and revised harness as confirmed regressions or improvements.

## Bracket-matching optimization measurement

After switching the normal path to Python's tokenizer and delimiter-stack matching, the same local workloads measured:

| Workload | Before (ms) | After (ms) | Change |
|---|---:|---:|---:|
| 5,000 lines | 614.17 | 73.33 | 88.1% faster |
| 20,000 lines | 2,836.87 | 284.94 | 90.0% faster |

The bracket matcher retains its Pygments fallback for incomplete source and older Python tokenizers that treat f-strings as opaque string tokens. These measurements validate this optimization only. Re-run the complete benchmark after the latest tokenization, diagnostics, and workspace-search changes before drawing conclusions about overall 2.7.0 performance.

## CI

CI runs a small smoke workload to ensure the benchmark remains executable. It does not enforce timing thresholds. Full-size comparisons are intended to be run locally on a stable machine and reviewed alongside functional tests.
