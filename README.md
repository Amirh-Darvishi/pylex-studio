# PyLex Studio

**Development version: 2.0.0 — Modern User Interface**

A lightweight Python desktop editor with independent lexical and syntax analysis.

## Language roadmap

PyLex Studio 2.0.0 focuses on a polished, Python-first desktop IDE. The file-type and editor presentation layers are being kept extensible so JavaScript, CSS, and HTML editing can be added in a later release without rebuilding the workspace UI.

## Features

- Python code editor with line numbers
- Pygments-powered syntax highlighting
- Lexical analysis using Python's `tokenize` module
- Syntax analysis using Python's `ast` module
- Run Python code asynchronously without freezing the editor
- Live streaming stdout and stderr with separate console colors
- Force-stop a running program and its child processes with the Stop control or Shift+F5
- Clear or save execution output; inspect exit code, execution status, and duration
- Dependency inspector classifying standard-library, local, installed, and missing imports; reports package versions and locations
- Discover and validate installed Python interpreters, including Windows Python launcher installations
- Select a global or per-workspace Python interpreter and automatically detect project virtual environments
- Create a project .venv without overwriting existing files
- Check pip availability and repair/bootstrap pip in the selected interpreter
- Run, debug, inspect dependencies, and generate pip commands with the exact selected interpreter
- Preflight dependency checks before execution, plus runtime missing-module diagnostics
- Open and save multiple files in independent editor tabs
- Per-tab unsaved-change indicators and save confirmation
- Project folder explorer with double-click file opening
- Close the active tab with Ctrl+W
- Open and save Python files
- Keyboard-navigable Python keyword and built-in completion with Ctrl+Space
- Automatic closing of brackets and quotes
- Smart indentation after Python suite headers and indentation-aware Backspace / Shift+Tab
- Toggle comments for a line or selected block with Ctrl+/
- Duplicate a line or selection with Ctrl+D; move lines with Alt+Up / Alt+Down
- Matching bracket highlighting and Go to Line with Ctrl+G
- Find and replace with Ctrl+H
- pdb-backed debugging with conditional and temporary breakpoints, Continue, Step Into, Step Over, Run Until, Return, Jump, expression evaluation, function arguments, variables, and stack inspection
- Integrated persistent terminal sessions with PowerShell, Command Prompt, Git Bash (when installed), and POSIX shells
- Black formatting for the active editor buffer and whole projects, with safe unsaved-buffer protection
- Ruff linting for the current buffer or entire workspace, with navigable file/line diagnostics
- Integrated pytest Test Explorer with test discovery, individual test execution, and full-suite runs
- Background quality-tool execution with output capture and explicit installation into the selected interpreter
- Multiple terminal tabs, live output streaming, command input with per-session Up/Down history, Ctrl+C interruption, process-tree termination, and per-session working directories
- Terminal sessions inherit the active workspace environment and selected Python virtual environment
- Adjustable editor font family and font size
- Persistent preferences for theme, UI/code fonts, font sizes, project explorer visibility, execution timeout, interpreter selection, configurable status-bar indicators, indentation, encoding and line endings, and local account display name
- Structured error panel with exact exception type and source location
- Click or double-click a diagnostic to jump to its line and column
- Current-line emphasis and inline error highlighting
- Separate Output, Lexical Analysis, Syntax Analysis, and Errors panels
- Analyze All and Clear Results actions
- Dark and light application themes, with a dark default
- VS Code-inspired Activity Bar and an Explorer with Open Editors and Workspace sections; recent workspaces are available from the File toolbar menu
- Dedicated cascading menu row above the restored logo/action toolbar, with File, Edit, Navigate, Run, Debug, Code, Tools, View and Help groups
- Consistent Run / Stop actions with matching dimensions and coordinated hover, pressed and disabled states across dark and light themes
- Expanded Account Center and Settings windows with local profile, workspace overview, keyboard shortcuts, privacy, security and product roadmap sections
- Extensibility roadmap for language packs, Language Server Protocol support, project templates, theme packs and a permission-aware extension marketplace
- Local Account center with a persistent display name; cloud sign-in and synchronization are not yet enabled
- Original PyLex Studio vector brand mark in the application header and About window
- Modern grouped toolbar and consistent application styling
- Context-aware, theme-matched right-click menus with editor line operations, Git staging/diff actions, test/diagnostic actions and clipboard controls

## Requirements

- Python 3.10+
- Tkinter (usually included with standard Python installations)
- ttkbootstrap 2.x (modern themed interface and bundled Bootstrap Icons)
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

## User interface preferences

Open View → Preferences to choose the dark or light theme, interface and code font families and sizes, project explorer visibility, and execution timeout (5, 10, 30, or 60 seconds, or Unlimited). The Settings window also documents shortcuts, planned language and extension support, and current privacy/security boundaries. Preferences are stored in `.pylex_studio.json` in the user's home directory and are reused on the next launch.

## Debugging

Start a session with **Tools → Start Debugging**. Toggle a normal breakpoint with the Breakpoint toolbar button or F9. The debugger also supports conditional and temporary breakpoints, clearing all breakpoints, enabling/disabling and ignoring breakpoint hits through the debugger API, Continue, Step Into, Step Over, Run Until the current line, Run Until Return, and Jump to Line (subject to Python pdb frame restrictions).

Inspect the current frame's local variables, function arguments, and stack; evaluate or pretty-print an expression in the paused frame from **Tools → Evaluate Expression**. Debug commands are sent to a dedicated child process using the selected workspace interpreter and project execution context. Stop Debugging terminates the debugger process tree. Debugged code runs with the current user's permissions and is not sandboxed.

## File and project management

Use File → Open Project Folder to browse a project. Double-click supported files in the explorer to open them in tabs. Each tab tracks its own unsaved changes; use Ctrl+W to close the active tab.

## Analysis and diagnostics

The lexical analyzer uses Python `tokenize` and reports token start/end positions. The syntax analyzer uses `ast.parse`. Diagnostics preserve concrete exception types (for example, `IndentationError`), are de-duplicated when the tokenizer and parser report the same issue, and can be selected in the Errors panel to navigate to the corresponding editor position. Editor columns are zero-based internally; the UI displays one-based columns.

## Running code

Code runs in a child process. The editor remains responsive while the process is active. Output streams into the console while the program runs. Use Force Stop or Shift+F5 to terminate the process tree (including child processes); executions use the configurable timeout selected in View → Preferences (5, 10, 30, or 60 seconds, or Unlimited). The Output status shows the remaining time while a limited execution is running. The console can be cleared or saved to a text file. A dedicated Dependencies panel classifies standard-library, local-project, installed, and missing imports, including installed versions and module locations. It reports the exact Python executable and virtual-environment status, and provides interpreter-specific pip commands. Static scans cannot identify every dynamic import, so runtime ModuleNotFoundError diagnostics remain authoritative. This is not a security sandbox: code runs with the current user's permissions. Do not run untrusted code.

## Tests and development checks

Run the automated test suite with either unittest or pytest:

```bash
python -m unittest discover -s tests -v
python -m pytest -v
```

Run the configured code-quality checks with:

```bash
python -m black --check pylex/quality.py tests/test_quality.py
python -m ruff check pylex/quality.py pylex/git.py pylex/git_panel.py tests/test_quality.py tests/test_git.py
```

The CI workflow validates Python 3.10, 3.11, and 3.13 on Ubuntu and Windows.

## Security

Code execution runs with the permissions of the current user. The runner is **not a security sandbox**. Do not execute untrusted code.

## Documentation

The Persian project guide is available at `docs/PROJECT_GUIDE.html`.


## Project model and execution context

PyLex Studio models an opened folder as a workspace root. The workspace explorer classifies common source, markup, data, configuration, document, image, audio, video, archive, database, and font formats with dedicated file icons. Text files can be edited in tabs; binary assets are delegated to the operating system's default application. Tabs expose a close control and prompt before discarding unsaved changes. Project paths are
normalized centrally, dependency inspection uses the project root, and code
execution uses the project's working directory. Saved, unchanged Python files
run from their real paths so sibling modules and local imports resolve naturally.
Unsaved editor buffers continue to run from temporary scripts while inheriting the
project working directory and import path. Runner and debugger services accept
explicit working-directory, environment, and interpreter parameters to support
future interpreter and virtual-environment management.

Code execution is not sandboxed and uses the current user's permissions.

## Python interpreter and virtual environments

Open **Tools → Python Interpreter** (also available from the toolbar or Dependencies panel) to inspect detected Python installations. Each candidate is probed by running that executable in isolated mode; PyLex displays its implementation, version, architecture, executable path, and whether it is a virtual environment.

You can select an interpreter globally or for the current workspace. Workspace-specific selections take precedence. When no explicit workspace selection exists, PyLex automatically checks the conventional .venv, venv, and env folders before falling back to the global interpreter. On Windows, discovery checks PATH and the Python launcher; on other platforms it checks the active interpreter and common PATH names.

Use **Create Project .venv** to create an isolated environment inside the workspace. PyLex refuses to overwrite a non-empty target folder and performs creation in the background so the editor remains responsive. The environment is selected for that workspace when creation succeeds.

Run, debug, static dependency inspection, and generated pip commands all use the same selected interpreter. Package operations are invoked as `<selected-python> -m pip`, never through an unrelated global pip executable. No shell activation is required for PyLex to run a program with the selected environment.

Virtual environments are machine-local and generally not portable because installed script entry points can contain absolute interpreter paths. Do not commit .venv to Git. Recreate it on another machine with `python -m venv .venv`, then install project dependencies with `python -m pip install -r requirements.txt`.

Interpreter probing and dependency inspection are not a security sandbox. Programs still run with the current user's operating-system permissions.
## Smart Editor

The editor continues indentation when pressing Enter, adds one indentation level after Python suite headers, and removes indentation in four-column steps with Backspace. Shift+Tab dedents the selected lines or current line. Use Ctrl+/ to toggle comments, Ctrl+D to duplicate a line or selection, Alt+Up / Alt+Down to move the current line, and Ctrl+G to navigate to a line. Matching Python delimiters are highlighted while the caret is adjacent to a bracket. These are editor conveniences, not a replacement for a language server or full semantic IntelliSense.

## Integrated terminal

Open Tools → Integrated Terminal or use the Terminal toolbar button. The terminal is separate from Output, Run, and Debug: each terminal tab owns a persistent shell process, so commands such as cd, environment-variable changes, and activated environments remain in that session.

On Windows, PowerShell and Command Prompt are supported; Git Bash is offered when detected. On Linux and macOS, available Bash, Zsh, or POSIX shell sessions are offered. Create multiple sessions, send commands through the input line, navigate that session's command history with Up/Down (including restoration of an unfinished input draft), interrupt the foreground command with Interrupt / Ctrl+C, clear a session's display, or close/kill a session. Output is collected asynchronously so shell activity does not block the Tk event loop.

New sessions start in the active workspace (or the active file's directory when no workspace is open). Their environment includes the selected project interpreter's Scripts/bin directory at the front of PATH and sets VIRTUAL_ENV when a virtual environment is selected. Shell sessions use redirected pipes rather than a full ConPTY/PTY terminal emulator: interactive command-line programs that require terminal device features, full-screen TUI rendering, or terminal resize events may not behave like a standalone console. Ordinary shell commands, Python REPLs, pip, and interactive line-oriented prompts are supported.


## Code quality and testing

Open **Tools → Formatter, Linter & Test Explorer** or select the **Quality** panel. All external tools run through the Python interpreter selected for the active workspace; PyLex never relies on an unrelated global `black`, `ruff`, or `pytest` executable.

- **Format Buffer** sends the current editor buffer to Black over stdin. The result is applied to that same editor tab, remains unsaved, and can be reviewed before saving.
- **Format Project** runs Black across the workspace. PyLex blocks this action while any editor tab has unsaved changes, avoiding conflicts between in-memory buffers and files changed on disk.
- **Lint Buffer / Lint Project** runs Ruff and displays structured diagnostics. Double-click a diagnostic to open the affected file and navigate to its line and column.
- **Test Explorer** discovers pytest test node IDs, displays the discovered tests, and runs either the complete workspace test suite or the selected test. Output and exit status are shown in the Tool Output tab.
- **Install Tools** explicitly installs or upgrades Black, Ruff, and pytest in the selected interpreter. These tools are also listed in `requirements.txt`.

Quality tasks run in background threads so the Tkinter interface remains responsive. Stop terminates the active quality-tool process. Ruff and Black settings are centralized in `pyproject.toml`; pytest discovers tests under `tests/` by default.

For command-line use:

```bash
python -m black .
python -m ruff check .
python -m pytest -v
```


## Git source control

Open **Tools → Git Source Control** or select the **Git** panel while a workspace is open. PyLex uses the Git executable installed on the system and operates on the workspace's repository; it does not require a Python Git package or a GitHub account for local version-control operations.

- Review the current branch, upstream, incoming/outgoing counts, and changed files.
- Inspect unstaged and staged diffs separately; stage or unstage selected files or the entire workspace.
- Commit staged changes with a message, create branches, and switch branches. Branch selection remains read-only outside the switch workflow.
- Fetch remote updates, pull with fast-forward-only behavior, and push the current branch using its configured upstream where available; otherwise PyLex discovers the default remote.
- Inspect recent commit history and stash the current working tree, including untracked files.
- Remote Git commands run in a background thread so the editor remains responsive.

Git commands are invoked with argument lists (never through a shell), scoped to the opened repository, and configured not to wait for interactive terminal prompts. Discard is an explicit, confirmation-gated action; untracked directory deletion is intentionally disabled. Pull uses `--ff-only` to avoid silently creating merge commits or conflict states. Review staged changes before committing and keep a backup of important work.
