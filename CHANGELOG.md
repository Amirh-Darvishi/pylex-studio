# Changelog

All notable changes to PyLex Studio are documented here.

## [1.2.0] - In development

### Added
- Non-blocking Python code execution in a child process.
- Stop execution control and Shift+F5 shortcut.
- Execution status, duration, stdout, stderr, and exit-code reporting.
- Automatic process termination after the configured timeout.
- Runner tests for output capture, cancellation, timeout, backwards compatibility, and temporary-file cleanup.
- Basic keyword and built-in completion using Ctrl+Space.
- Automatic bracket and quote pairing.
- Find and replace dialog with Ctrl+H.
- Multiple open documents in independent editor tabs.
- Per-document dirty state, tab indicators, save prompts, and close-tab handling.
- Project folder explorer with recursive file browsing and double-click open.

### Improved
- Preserved the existing synchronous `run_source` API for compatibility.
- Kept the GUI responsive while user code is running.

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
