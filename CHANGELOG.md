# Changelog

## [Unreleased]

### Performance and responsiveness
- Add repeatable benchmarks for editor tokenization and tag spans, AST analysis, combined diagnostics, bracket matching, large-file reads, workspace scanning, and workspace search; document the methodology and initial baseline in `docs/PERFORMANCE.md`.
- Use Pygments token offsets directly and retain only syntax spans needed by the editor, reducing repeated work and intermediate allocations.
- Reuse completed lexical and syntax results when assembling diagnostics in the full-analysis workflow; standalone diagnostics validate tokenization without retaining a second token collection.
- Make workspace-search line/column mapping linear in file length, retain replacement snapshots only for files with matches, and render large result sets in bounded UI batches.
- Optimize bracket matching with Python tokenization and delimiter-stack traversal while preserving the fallback for incomplete and legacy syntax.
- Preserve cancellable background work, debounced updates, chunked large-file loading, and bounded UI updates.

### Validation
- Performance comparisons and the full Windows/Ubuntu × Python 3.10/3.11/3.13 CI matrix are pending final verification for this development branch.

## [2.6.0] - 2026-11-17

### Process lifecycle and stability
- Align the package `__version__` with the 2.6.0 release and add a version regression test.
- Harden Runner, integrated Terminal, and Debugger shutdown so child processes cannot outlive their owning session.
- Use isolated POSIX process groups to clean up descendants even after the process-group leader exits.
- Attach Windows child processes to a kill-on-close Job Object when permitted; retain the process-tree fallback for environments where Job Object assignment is rejected.
- Fix the Quality panel race where a subprocess could start while the application was closing; cancel active or not-yet-published work and stop the recurring UI poll during close.
- Add regression tests for Runner and Debugger descendants, Terminal child cleanup on POSIX, Quality panel close-during-startup, and package version consistency.

### Validation
- Pass all six Windows/Ubuntu × Python 3.10/3.11/3.13 CI jobs.
- Pass pytest, compileall, Black, and Ruff in every matrix job.
- Linux: 184 passed, 1 GUI smoke test skipped because the runner is headless.
- Windows: 183 passed, 2 platform/display-related tests skipped.
- Merge implementation through PR #26: https://github.com/Amirh-Darvishi/pylex-studio/pull/26
- Merged into `main` at commit `3d5a97aebd7a76fac03666f1a07def4f3ef62fd3`.
- CI run: https://github.com/Amirh-Darvishi/pylex-studio/actions/runs/44183746021
- Published as the stable 2.6.0 release: https://github.com/Amirh-Darvishi/pylex-studio/releases/tag/2.6.0

## [2.5.0] - 2026-11-17

### Workspace search and replacement
- Add a UI-independent workspace search service with literal and regular-expression matching, case sensitivity, whole-word matching, and filename glob filtering.
- Scan supported text files with size limits and skip generated, VCS, virtual-environment, and hidden directories by default.
- Run workspace search on a cancellable background worker and display grouped file/line results with direct editor navigation.
- Include unsaved open-document buffers in search results without writing them to disk.
- Preview replacements before applying them; preserve encoding and newline conventions and use atomic writes for disk files.
- Reject replacement when a target file has changed since its search snapshot.
- Add regression tests for matching modes, exclusions, overlays, cancellation, encoding/newline preservation, and stale-file protection.

### User experience and compatibility
- Add the `Ctrl+Shift+F` shortcut and Tools menu entry for Workspace Search.
- Handle equivalent Windows paths when resolving replacement targets.

### Validation and release
- Pass all six Windows/Ubuntu × Python 3.10/3.11/3.13 CI jobs on the merged `main` commit.
- Pass pytest, compileall, Black, and Ruff checks in every CI matrix job.
- Publish the stable 2.5.0 release: https://github.com/Amirh-Darvishi/pylex-studio/releases/tag/2.5.0
- Merge implementation through PR #25: https://github.com/Amirh-Darvishi/pylex-studio/pull/25


## [2.4.1] - 2026-11-17

### Analysis and UI responsiveness
- Run lexical analysis, syntax analysis, and diagnostic collection on a background worker so large source files do not block the Tk event loop.
- Deliver results through a thread-safe queue and apply them only on the UI thread.
- Invalidate pending analysis immediately when the active document changes, the user switches tabs, results are cleared, or the application closes.
- Discard results if the originating document is closed, no longer active, or no longer matches the captured source snapshot.
- Move matching-bracket scans to a cancellable background worker and keep the existing debounce before starting a scan.
- Add focused tests for analysis modes, syntax diagnostics, cancellation, and bracket-scan cancellation.

### Existing editor responsiveness
- Keep Pygments tokenization on a cancellable worker with bounded UI-thread tag batches.
- Keep debounced gutter updates and metadata-backed status-bar encoding/newline indicators.

### Validation
- Feature-branch CI passed all six Windows/Ubuntu × Python 3.10/3.11/3.13 jobs: 169 passed, 1 skipped, and 12 subtests passed; compileall, Black, and Ruff passed.
- The display-dependent GUI smoke test was skipped on the headless runner.
- Published as the stable 2.4.1 release: https://github.com/Amirh-Darvishi/pylex-studio/releases/tag/2.4.1

## [2.4.0] - 2026-11-17

### Stability and reliability
- Guard asynchronous large-file loading against stale workspace and window lifecycles, with cancellable chunked reads.
- Move workspace filesystem scanning off the Tk event loop and populate the project tree incrementally.
- Save documents atomically and preserve their detected text encoding and newline convention.
- Limit file-type detection to a bounded sample instead of reading entire unknown files.
- Add regression coverage for stale load completions and workspace scanning.

### Editor responsiveness
- Build Pygments token spans in a cancellable background task without accessing Tkinter widgets from the worker.
- Deliver tokenization results through a queue and apply syntax tags in bounded UI-thread batches.
- Discard stale highlighting results when document content changes, a new document is selected, or the editor is destroyed.
- Debounce line-number gutter refreshes and matching-bracket calculations to reduce redundant event-loop work.
- Read status-bar encoding and newline indicators from document metadata, avoiding repeated full-buffer reads.

### Validation and CI
- Run pytest and compileall on Windows and Ubuntu with Python 3.10, 3.11, and 3.13.
- Run Black formatting and Ruff lint checks on every matrix combination, rather than a single OS/version subset.
- Full matrix passed; the display-dependent GUI smoke test is skipped in headless environments.


## [2.3.1] - 2026-11-17

### Performance
- Read large text files on a background worker so disk I/O does not block the Tk event loop.
- Insert large documents in bounded chunks and enter a lightweight large-file mode that avoids full-document syntax highlighting, bracket scans, and expensive line-number gutter generation.
- Select Pygments lexers by file extension so JSON, JavaScript, and other supported text formats are no longer tokenized as Python.
- Added focused regression tests for lexer selection and large-document thresholds.

## [2.3.0] - 2026-11-17

### Architecture
- Decomposed the large `PyLexApp` implementation into focused UI responsibility mixins for toolbar/menus, shell/layout, panels, workspace, documents, analysis, execution, debugging, and preferences.
- Kept `PyLexApp` as the Tkinter composition root and preserved existing callbacks, widgets, themes, shortcuts, and lifecycle behavior during extraction.
- Centralized shared application imports in `pylex/app_support.py` to keep the extracted modules consistent.

### Dependencies and tests
- Split runtime dependencies (`requirements.txt`) from contributor/test tooling (`requirements-dev.txt`).
- Added application composition tests and a display-aware Tk startup smoke test.
- Updated CI to install the development dependency set while retaining the Windows/Ubuntu Python 3.10, 3.11, and 3.13 matrix and Ruff/Black checks.

### Documentation
- Updated installation, development, and architecture guidance for the modular application layout.


## [2.2.0] - 2026-11-15

### Architecture
- Introduced UI-independent Workspace, Document, Execution, and Debugger controllers.
- Routed workspace activation/restoration, document registration and lookup, execution startup/stop/completion, and debugger startup/stop/cleanup through their respective controllers.
- Kept Tkinter widgets, prompts, rendering, and polling schedules in the application layer; controllers own lifecycle state and delegate process creation to the existing execution service.
- Preserved the existing PyLexApp state attributes through compatibility properties while migrating ownership behind controller boundaries.

### Tests
- Added isolated controller tests for workspace restoration, external-file project context, document activation and dirty state, execution lifecycle, stale-handle protection, and debugger cleanup.
- Retained the Windows/Ubuntu Python 3.10, 3.11, and 3.13 CI matrix and Ruff/Black quality checks.

### Documentation
- Updated the Persian project guide with the 2.2.0 controller boundaries, lifecycle ownership, compatibility strategy, and testing approach.

## [2.1.0] - 2026-11-15

### Architecture
- Added a UI-independent command registry with stable command IDs, shortcut-aware search, duplicate registration protection, and explicit command execution.
- Extracted the searchable Command Palette into a dedicated Tkinter UI component; the main application now supplies registered actions and theme context.
- Added a transparent, outlined Command Palette launcher stacked above the Run and Stop controls; its anchored popup matches the launcher's width and retains the existing keyboard shortcut.
- Added focused tests for command registration, search, lookup, ordering, and execution without requiring a Tk display.
- Added a real child-process integration test verifying that a saved file in a nested directory inherits the Workspace working directory and Python import path.

### Quality and validation
- Expanded Ruff linting from a hand-picked file list to the complete `pylex` and `tests` trees.
- Added Black formatting checks for the new architecture modules and existing formatting-enforced modules.
- Removed duplicate unittest/pytest execution from CI; pytest discovers and runs the existing unittest-compatible suite once on every matrix target.
- Retained the six-platform/version validation matrix: Windows and Ubuntu with Python 3.10, 3.11, and 3.13.

### Documentation
- Updated the README to identify 2.1.0 as the latest stable release and link to its release notes.


## [2.0.2] - 2026-11-15

### Fixed
- Restored interactive standard input in the Output panel, including prompts that do not end with a newline.
- Routed terminal execution through the active editor file, workspace working directory, and selected Python interpreter.
- Fixed debugger completion and cleanup for successful runs and uncaught exceptions across supported Python versions.

### Improved
- Added regression coverage for input streaming, terminal execution context, debugger lifecycle, and cross-platform path handling.
- Kept terminal shell sessions separate from the Output and debugger process workflows.

### Execution, terminal, and debugger reliability
- Added interactive standard-input support to Output for saved and unsaved Python programs.
- Streamed output character-by-character so prompts without a newline are visible before the user responds.
- Bound terminal sessions to the active editor file and workspace context, refreshing the terminal context when the active document changes.
- Added a **Run Active File** terminal action with shell-safe quoting and automatic save-before-run behavior.
- Made pdb sessions close automatically after successful completion and after reporting an uncaught exception.
- Added regression tests for interactive input, prompt streaming, debugger completion, exception reporting, and terminal context propagation.

## [2.0.1] - 2026-11-15

### Documentation and release metadata
- Updated the README to identify 2.0.0 as the latest stable release and link to the complete Persian project guide.
- Reworked the Persian HTML project guide for the 2.0.x interface, including themes, Activity Bar, Explorer, cascading menus, Command Palette, Quick Open, Status Bar, Account Center, Settings, and current product boundaries.
- Aligned the package version metadata with the 2.0.1 patch-release target.

## [2.0.0] - 2026-11-15

### Added
- Began the modern interface refresh with a unified dark/light theme foundation.
- Added a compact, grouped toolbar for common file, run, tool, and analysis workflows.
- Added ttkbootstrap 2 as the themed widget layer and a consistent, recolorable Bootstrap icon system for toolbar, workspace files, and tool panels.
- Expanded Settings with a reset-to-defaults action and a language roadmap for Python, JavaScript, HTML, and CSS.
- Added workspace Quick Open (`Ctrl+P`) with ranked file-name and path filtering.
- Applied the selected interface font consistently to notebook tabs and other themed controls while retaining the existing Tkinter editor and application services.
- Added a VS Code-inspired Activity Bar, an Explorer with Open Editors and Workspace sections, and quick actions for creating files/folders.
- Added a dedicated categorized menu row above the brand/action toolbar, with cascading File, Edit, Navigate, Run, Debug, Code, Tools, View and Help menus.
- Restored a compact brand/action row beside the logo with workspace, interpreter, save, terminal, quality, Git, analysis, Debug, Run and Stop shortcuts.
- Unified Run and Stop button dimensions, typography, spacing, hover, pressed and disabled states across both themes.
- Expanded Account Center and Settings into larger resizable workspaces with Profile, Connected Services, Workspace, Productivity, Extensions and Privacy & Security sections.
- Applied the selected interface font to native Tk controls and expanded the future language, language-server, plugin, theme and project-template roadmap.
- Added a bottom-left Account center with a locally stored display name and clearly marked future cloud/GitHub account integrations.
- Added an original PyLex Studio vector logo at `assets/pylex-logo.svg` and reused its visual mark in the app header and About window.
- Moved Recent Workspaces out of Explorer into the File toolbar menu, with open, copy-path, remove and clear actions.
- Added configurable, persistent status-bar indicators with an inline right-click menu for visibility, indentation, encoding and line-ending settings; no separate configuration dialog is required.
- Replaced native-looking context menus with a shared, theme-aware popup system featuring clear spacing, high-contrast hover states, disabled-item styling, cascading submenus, and consistent behavior across the editor, Explorer, tabs, Activity Bar, Status Bar, terminal, Git, diagnostics and tests.
- Expanded Workspace right-click actions with folder-aware create/open/rename/delete operations, relative-path copying, file-manager reveal, terminal launch at the selected directory, workspace refresh and close actions.
- Added an action-rich Recent Workspaces submenu with open, reveal, terminal, copy-path and remove actions.
- Added immediate row-level hover highlighting to every command inside categorized Toolbar dropdowns, including shortcut labels and submenu entries.

### Design goals
- Keep file-type presentation extensible for future JavaScript, CSS, and HTML editing support.
- Keep the dark theme as the default and provide a coordinated light theme.
- Preserve existing editor, execution, debugger, terminal, Git, and quality workflows during the visual refresh.


All notable changes to PyLex Studio are documented here.

## [1.10.0] - Unreleased

### Improved
- Centralized the application version so the window title stays consistent with package metadata.
- Made preference persistence atomic to protect existing settings from interrupted writes.
- Expanded continuous integration to cover Python 3.10, 3.11, and 3.13 on Windows and Ubuntu.
- Updated project documentation and corrected the released 1.9.0 changelog status.
- Corrected the binary-file classification metadata.

### Tests
- Added regression coverage ensuring a failed preference-file replacement preserves the previous settings and cleans up its temporary file.

## [1.9.0] - 2026-11-15

### Added
- Added a Git source-control panel for repository status, staged and unstaged changes, file diffs, and commit history.
- Added file-level and bulk staging/unstaging, separate staged and unstaged diff review, safe discard, and commits of staged changes.
- Added local branch listing, branch creation, and branch switching.
- Added asynchronous fetch, fast-forward-only pull, upstream-aware push/pull, remote discovery, and stash operations.
- Added a shell-free Git service with workspace path restrictions and automated tests.

### Security
- Git commands use argument arrays, disable interactive prompts, and restrict path operations to the active repository.
- Untracked directory deletion is disabled; pull is fast-forward-only.


## [1.8.0] - 2026-11-15

### Added
- Added Black formatting for the active editor buffer and whole projects, with protection against formatting while editor tabs contain unsaved changes.
- Added Ruff linting for editor buffers and workspaces, structured diagnostics, and navigation to the reported source location.
- Added a pytest Test Explorer with discovery, selected-test execution, full-suite execution, and captured tool output.
- Added background execution and selected-interpreter installation for Black, Ruff, and pytest.
- Added centralized Black, Ruff, and pytest configuration in pyproject.toml.

### Improved
- Routed quality tools through the active workspace interpreter and project environment.


## [1.7.0] - 2026-11-15

### Added
- Added an integrated terminal panel with independent persistent shell sessions.
- Added PowerShell and Command Prompt support on Windows, optional Git Bash discovery, and available Bash/Zsh/POSIX shells on Unix-like systems.
- Added asynchronous output streaming, command input with per-session Up/Down history, Ctrl+C interruption, process-tree termination, session clearing, and multiple terminal tabs.
- New terminal sessions inherit the active workspace working directory and selected Python interpreter environment.
- Added terminal helper tests for shell commands, virtual-environment PATH setup, and environment isolation.

### Improved
- Kept terminal processes isolated from the existing Run, Output, and pdb Debugger workflows.
- Added explicit documentation for redirected-pipe terminal limitations.


## [1.6.0] - 2026-11-15

### Added
- Expanded pdb controls with conditional and temporary breakpoints, Run Until, Run Until Return, Jump to Line, function argument inspection, and pretty-printed expression evaluation.
- Added commands to enable, disable, ignore, and clear breakpoints in an active session.
- Added input validation for debugger line numbers and single-line expressions to prevent accidental multi-command input.
- Exposed advanced debugger actions through the Tools menu and toolbar.
- Added tests for advanced command coverage and invalid argument handling.

### Improved
- Centralized debugger command validation and retained project-aware interpreter execution.

## [1.5.0] - 2026-11-15

### Added
- Smart Python indentation after suite headers and indentation-aware Backspace and Shift+Tab dedenting.
- Line and block comment toggling, line/selection duplication, and current-line movement shortcuts.
- Matching bracket highlighting that ignores delimiters inside strings and comments.
- Go to Line navigation and keyboard shortcuts for common editing actions.
- Pure editor text helpers with dedicated unit tests.

### Improved
- Exposed Smart Editor actions through the Edit menu and toolbar.

## [1.4.0] - 2026-11-15

### Added
- Verified Python interpreter discovery from the active runtime, common PATH entries, and Windows Python launcher registrations.
- Interpreter metadata inspection: implementation, version, architecture, executable, prefix, pip availability, and PEP 405 virtual-environment detection.
- Global and per-workspace interpreter selection with persistent preferences.
- Automatic detection of project .venv, venv, and env environments.
- Background creation of project .venv with protection against overwriting non-empty directories.
- Added pip availability reporting and an asynchronous ensurepip repair action.
- Run, Debug, dependency inspection, and pip commands routed through the selected interpreter.
- Added interpreter discovery, validation, venv creation, package-manager, preference, and execution-routing tests.

### Improved
- Dependency inspection queries the selected interpreter rather than assuming the interpreter running the editor.
- Preserved virtual-environment executable paths even when the platform uses symlinks.
- Added recent-workspace persistence to the preference schema.

## [1.3.0] - 2026-11-15

### Added
- Introduced a filesystem-backed Project model with normalized roots, containment checks, relative paths, and project-aware working directories.
- Added a dedicated Workspace explorer with folder opening, visible root path, refresh, and nested directory navigation.
- Added file-type recognition and distinct icons for common programming languages, markup, data/configuration, documents, media, archives, databases, and fonts; text files open in editor tabs and binary files launch through the system default application.
- Added per-tab close controls with save/discard/cancel protection for unsaved edits and duplicate-open detection.
- Added an execution service boundary so the UI no longer constructs runner/debugger processes directly.
- Added project-aware process context (working directory, environment, and interpreter injection points) for execution and debugging.
- Added real-file execution and debugging for saved, unchanged documents, preserving their actual source paths and enabling sibling/local module imports.
- Preserved temporary-script execution for unsaved buffers and the existing synchronous runner API.

### Improved
- Dependency inspection now resolves local modules from the project root.
- Kept the existing Tkinter interface and editor behavior while establishing modular core and service packages.

## [1.2.0] - 2026-11-15

### Added
- Configurable execution timeout: 5, 10, 30, 60 seconds, or Unlimited.
- Persist timeout preference and show a live remaining-time status during execution.
- Interactive pdb-based debugging in a child process.
- Per-editor breakpoints, Continue, Step Into, Step Over, variable inspection, and stack inspection.
- Debugger lifecycle and output-capture tests.
- Preferences dialog for theme, editor font family, font size, and project explorer visibility.
- Persistent user preferences stored outside the project directory.

- Non-blocking Python code execution in a child process.
- Stop execution control and Shift+F5 shortcut.
- Execution status, duration, stdout, stderr, and exit-code reporting.
- Automatic process termination after the configured timeout.
- Runner tests for output capture, cancellation, timeout, backwards compatibility, and temporary-file cleanup.
- Basic keyword and built-in completion using Ctrl+Space.
- Automatic bracket and quote pairing, including correct caret placement around selected text.
- Keyboard-navigable keyword and built-in completion suggestions.
- Find and replace dialog with Ctrl+H.
- Multiple open documents in independent editor tabs.
- Per-document dirty state, tab indicators, save prompts, and close-tab handling.
- Project folder explorer with recursive file browsing and double-click open.

### Improved
- Add a dedicated dependency inspector showing standard-library, local, installed, and missing imports with package versions and module locations.
- Report the exact active Python executable and virtual-environment state; generate pip install commands targeting that interpreter.
- Expand dependency inspection tests for local modules, missing packages, installed versions, and syntax errors.
- Stream stdout and stderr live into a color-coded output console.
- Add controls to clear and save execution logs.
- Preflight third-party imports and suggest exact pip installation commands for common package-name differences.
- Force-stop the entire execution/debugger process tree so child processes cannot leave the editor stuck.
- Preserve the synchronous `run_source` API for compatibility.

### Security
- Execution is not sandboxed and uses the current user's permissions.

## [1.1.0] - 2026-11-14

### Added
- Pygments-based Python syntax highlighting.
- Highlight categories for keywords, built-ins, strings, comments, numbers, functions, classes, operators, and lexer errors.
- English-language application menus, toolbar, dialogs, status messages, and analysis reports.
- Explicit Pygments dependency declaration.

### Improved
- Kept lexical analysis based on Python `tokenize`, independent from syntax highlighting.
- Kept syntax validation based on Python `ast`.
- Expanded analyzer tests for built-ins, multiline strings, token positions, and malformed strings.
