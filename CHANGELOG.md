# Changelog

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
