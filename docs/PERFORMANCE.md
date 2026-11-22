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
| Workspace search | Searching supported text files and creating match/snapshot results (all files match) |
| Workspace search (10% hits) | Searching a workspace where approximately one in ten files contains the query |

Each benchmark reports median elapsed time in milliseconds and peak Python allocation measured with `tracemalloc`. Peak MiB is not the application's total resident memory. Large-file read measures disk reading only; it does not measure inserting text into Tkinter widgets. UI responsiveness must also be checked in the running application.

The workspace-search benchmarks include both an all-match workload and a sparse workload with approximately 10% matching files. This makes the cost of scanning non-matching files visible. The harness uses one warm-up by default to reduce first-run effects, then reports the median of timed samples. Peak allocation is measured in a separate run and should be treated as an approximate per-operation Python allocation peak, not process-wide memory use.

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

## Final 2.7.0 measurements

The following representative runs were collected locally on Windows with Python 3.13.14 and Pygments 2.21.0. Workloads were 5,000 source lines / 500 workspace files and 20,000 lines / 2,000 files. They are reference observations, not CI thresholds; machine load and runtime versions affect timings.

| Benchmark | 5,000 lines / 500 files | 20,000 lines / 2,000 files |
|---|---:|---:|
| Pygments token spans | 690.18 ms / 5.57 MiB | 2,458.97 ms / 22.54 MiB |
| Editor highlight spans | 849.75 ms / 2.15 MiB | 3,336.46 ms / 9.00 MiB |
| Lexical analysis | 94.64 ms / 6.83 MiB | 385.17 ms / 27.60 MiB |
| AST syntax analysis | 83.22 ms / 17.10 MiB | 362.73 ms / 68.45 MiB |
| Standalone diagnostics | 128.25 ms / 17.10 MiB | 524.03 ms / 68.45 MiB |
| Full analysis workflow | 232.18 ms / 18.64 MiB | 916.84 ms / 74.63 MiB |
| Bracket matching | 68.77 ms / 0.91 MiB | 264.55 ms / 3.94 MiB |
| Large-file read | 0.22 ms / 0.35 MiB | 1.15 ms / 1.40 MiB |
| Workspace scan | 21.12 ms / 0.13 MiB | 87.34 ms / 0.43 MiB |
| Workspace search (all match) | 207.65 ms / 1.17 MiB | 834.93 ms / 4.66 MiB |
| Workspace search (10% hits) | 196.87 ms / 0.81 MiB | 812.24 ms / 3.20 MiB |

Each cell shows median elapsed time and peak Python allocation. The sparse-search workload showed roughly 31% lower peak allocation than the all-match workload, but timing was similar; do not describe it as a confirmed speed improvement. These full measurements are from the benchmark harness used for 2.7.0 and should be compared only against runs using the same harness and setup.

## Release validation

The 2.7.0 release validation recorded 198 passing tests, 3 skipped tests, and 14 passing subtests locally. Black reported 75 files unchanged and Ruff passed. The six CI combinations (Windows and Ubuntu, Python 3.10/3.11/3.13) all passed pytest, compileall, the benchmark smoke test, Black, and Ruff. Skips were platform/environment limitations such as symlink availability and POSIX process-group semantics.

## Editor highlight application (post-2.7.0)

Applying syntax tags with character-offset indexes (`1.0+Nc`) is linear per call inside Tk, so highlighting a large pasted block was quadratic and froze the UI. Offsets are now converted to `line.column` indexes with `spans_to_text_indexes()` (binary search over line starts) on the highlight worker thread, so the UI thread only calls `tag_add` with direct indexes. Manual measurement under Xvfb, pasting `print('hello')` lines into an empty editor until highlighting finished:

| Pasted lines | Before | After |
|---|---|---|
| 2,000 | ~2.7 s | ~0.4 s |
| 8,000 | ~40.5 s | ~1.3 s |

These are single-machine, single-run figures meant to show the scaling change, not benchmark-harness results.
