# Changelog

All notable changes to PyLex Studio are documented here.

## [1.1.1] - In development\n\n### Added\n- Structured diagnostics with exact exception types, source lines, and editor coordinates.\n- Errors panel with clickable diagnostics that navigate to the corresponding line and column.\n- Current-line emphasis, diagnostic line highlighting, and synchronized line-number gutter.\n- Analyze All and Clear Results commands, plus separate Output, Lexical, Syntax, and Errors panels.\n- Token end positions and expanded test coverage for diagnostic de-duplication, source spans, and coordinate conversion.\n- 16 automated tests pass in the development environment.\n\n### Improved\n- De-duplicated matching tokenizer/parser reports while preferring the parser diagnostic.\n- Improved analysis status messages and invalidated stale diagnostics after source edits.\n\n## [1.1.0] - 2026-11-14

### Added
- Pygments-based Python syntax highlighting.
- Highlight categories for keywords, built-ins, strings, comments, numbers, functions, classes, operators, and lexer errors.
- English-language application menus, toolbar, dialogs, status messages, and analysis reports.
- Explicit Pygments dependency declaration.

### Improved
- Kept lexical analysis based on Python `tokenize`, independent from syntax highlighting.
- Kept syntax validation based on Python `ast`.
- Expanded analyzer tests for built-ins, multiline strings, token positions, and malformed strings.
