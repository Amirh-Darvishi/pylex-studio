# PyLex Studio

**Current development target: 1.2.0** (in development)

A lightweight Python desktop editor with independent lexical and syntax analysis.

## Features

- Python code editor with line numbers
- Pygments-powered syntax highlighting
- Lexical analysis using Python's `tokenize` module
- Syntax analysis using Python's `ast` module
- Run Python code asynchronously without freezing the editor
- Live streaming stdout and stderr with separate console colors
- Force-stop a running program and its child processes with the Stop control or Shift+F5
- Clear or save execution output; inspect exit code, execution status, and duration
- Preflight checks for unavailable third-party imports with suggested pip install commands
- Open and save multiple files in independent editor tabs
- Per-tab unsaved-change indicators and save confirmation
- Project folder explorer with double-click file opening
- Close the active tab with Ctrl+W
- Open and save Python files
- Keyboard-navigable Python keyword and built-in completion with Ctrl+Space
- Automatic closing of brackets and quotes
- Find and replace with Ctrl+H
- pdb-backed debugging with breakpoints, Continue, Step Into, Step Over, variables, and stack inspection
- Adjustable editor font family and font size
- Persistent preferences for theme, font, font size, and project explorer visibility
- Structured error panel with exact exception type and source location
- Click or double-click a diagnostic to jump to its line and column
- Current-line emphasis and inline error highlighting
- Separate Output, Lexical Analysis, Syntax Analysis, and Errors panels
- Analyze All and Clear Results actions
- Dark and light editor themes

## Requirements

- Python 3.10+
- Tkinter (usually included with standard Python installations)
- Pygments

## Installation

```bash
git clone https://github.com/Amirh-Darvishi/pylex-studio.git
cd pylex-studio
python -m venv .venv
```

Activate the environment:

```powershell
# Windows PowerShell
.venv\Scripts\Activate.ps1
```

```bash
# Linux / macOS
source .venv/bin/activate
```

Install dependencies and run:

```bash
python -m pip install -r requirements.txt
python main.py
```

## User interface preferences (1.2.0 development)

Open View → Preferences to choose the dark or light theme, editor font family, font size, and project explorer visibility. Preferences are stored in `.pylex_studio.json` in the user's home directory and are reused on the next launch.

## Debugging (1.2.0 development)

Use Debug or Tools → Start Debugging to launch the current source under Python's built-in `pdb` debugger. Toggle Breakpoint at the current line, then use Continue, Step Into, Step Over, Variables, and Stack. Debugged code runs with the current user's permissions and is not sandboxed.

## File and project management (1.2.0 development)

Use File → Open Project Folder to browse a project. Double-click supported files in the explorer to open them in tabs. Each tab tracks its own unsaved changes; use Ctrl+W to close the active tab.

## Analysis and diagnostics

The lexical analyzer uses Python `tokenize` and reports token start/end positions. The syntax analyzer uses `ast.parse`. Diagnostics preserve concrete exception types (for example, `IndentationError`), are de-duplicated when the tokenizer and parser report the same issue, and can be selected in the Errors panel to navigate to the corresponding editor position. Editor columns are zero-based internally; the UI displays one-based columns.

## Running code (1.2.0 development)

Code runs in a child process. The editor remains responsive while the process is active. Output streams into the console while the program runs. Use Force Stop or Shift+F5 to terminate the process tree (including child processes); executions also have a 10-second timeout. The console can be cleared or saved to a text file. A preflight import check reports likely missing third-party packages and suggests installation commands; Python tracebacks remain authoritative. This is not a security sandbox: code runs with the current user's permissions. Do not run untrusted code.

## Tests

```bash
python -m unittest discover -s tests -v
```

## Security

Code execution runs with the permissions of the current user. The runner is **not a security sandbox**. Do not execute untrusted code.

## Documentation

The Persian project guide is available at `docs/PROJECT_GUIDE.html`.
