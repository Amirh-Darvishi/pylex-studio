# Changelog

All notable changes to PyLex Studio are documented here.

## [1.2.0] - In development

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
