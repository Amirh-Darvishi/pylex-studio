# PyLex Studio Performance Benchmarks

This document describes the repeatable, non-gating benchmark harness introduced for the 2.7.0 performance work.

## Run locally

From the repository root:

```powershell
.\.venv\Scripts\python.exe scripts/benchmark_performance.py --lines 5000 --files 500 --repeats 3
.\.venv\Scripts\python.exe scripts/benchmark_performance.py --lines 20000 --files 2000 --repeats 3
```

The script also works with a regular Python executable:

```bash
python scripts/benchmark_performance.py --lines 5000 --files 500 --repeats 3
```

- `--lines`: number of source lines in the deterministic Python workload.
- `--files`: number of synthetic workspace files.
- `--repeats`: number of timed samples; the reported duration is the median.

Use the same machine, Python version, workload, and broadly similar system load when comparing results. The harness deliberately has no CI timing thresholds because hosted-runner timing is variable.

## Measurements

| Benchmark | What it measures |
|---|---|
| Pygments token spans | Tokenization and source-relative token span creation |
| Editor highlight spans | Tokenization plus filtering to the tags actually applied by the editor |
| AST syntax analysis | Parsing and AST node counting |
| Combined diagnostics | Token validation and parser diagnostics |
| Bracket matching | Finding the matching delimiter at a cursor offset |
| Large-file read | Reading a generated source file from disk |
| Workspace scan | Enumerating a synthetic workspace using the Explorer scanner |
| Workspace search | Searching supported text files and creating match/snapshot results |

Each benchmark reports median elapsed time in milliseconds and peak Python allocation measured with `tracemalloc`. Peak MiB is not the application's total resident memory. Large-file read measures disk reading only; it does not measure inserting text into Tkinter widgets. UI responsiveness must also be checked in the running application.

## Initial Windows baseline

The initial 2.7.0 baseline was collected locally on Windows with Python 3.13 and three repeats.

| Operation | 5,000 lines / 500 files (ms) | 20,000 lines / 2,000 files (ms) |
|---|---:|---:|
| Pygments token spans | 593.22 | 2,442.58 |
| AST syntax analysis | 84.44 | 360.45 |
| Combined diagnostics | 195.55 | 800.00 |
| Bracket matching | 614.17 | 2,836.87 |
| Large-file read | 0.20 | 1.26 |
| Workspace scan | 28.61 | 122.88 |

## Bracket-matching optimization measurement

After switching the normal path to Python's tokenizer and delimiter-stack matching, the same local workloads measured:

| Workload | Before (ms) | After (ms) | Change |
|---|---:|---:|---:|
| 5,000 lines | 614.17 | 73.33 | 88.1% faster |
| 20,000 lines | 2,836.87 | 284.94 | 90.0% faster |

The bracket matcher retains its Pygments fallback for incomplete source and older Python tokenizers that treat f-strings as opaque string tokens. These measurements validate this optimization only. Re-run the complete benchmark after the latest tokenization, diagnostics, and workspace-search changes before drawing conclusions about overall 2.7.0 performance.

## CI

CI runs a small smoke workload to ensure the benchmark remains executable. It does not enforce timing thresholds. Full-size comparisons are intended to be run locally on a stable machine and reviewed alongside functional tests.
