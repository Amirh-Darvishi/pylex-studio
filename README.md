# PyLex Studio

A lightweight Python desktop editor with independent lexical and syntax analysis.

## Features

- Python code editor with line numbers
- Pygments-powered syntax highlighting
- Lexical analysis using Python's `tokenize` module
- Syntax analysis using Python's `ast` module
- Run Python code and inspect standard output and errors
- Open and save Python files
- Adjustable editor font size
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
.venv\\Scripts\\Activate.ps1
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

## Tests

```bash
python -m unittest discover -s tests -v
```

## Security

Code execution runs with the permissions of the current user. The runner is **not a security sandbox**. Do not execute untrusted code.

## Documentation

The Persian project guide is available at `docs/PROJECT_GUIDE.html`.
