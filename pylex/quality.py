"""Formatting, linting, and test-explorer services for PyLex Studio."""

from __future__ import annotations

import json
import os
import queue
import re
import subprocess
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from .process_control import attach_process_job, terminate_process_tree
from .ui.context_menu import ContextMenu


def tool_argv(interpreter, module, arguments=()):
    """Build a shell-free command for a tool in the selected Python environment."""
    allowed = {"black", "ruff", "pytest", "pip"}
    if module not in allowed:
        raise ValueError(f"Unsupported quality tool: {module}")
    args = [str(item) for item in arguments]
    return [str(interpreter), "-m", module, *args]


def _process_options():
    """Isolate quality tools so Stop can terminate their complete process tree."""
    if os.name == "nt":
        return {"creationflags": getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)}
    return {"start_new_session": True}


def parse_ruff_diagnostics(output):
    """Convert Ruff's JSON output into stable, editor-friendly diagnostics."""
    try:
        payload = json.loads(output or "[]")
    except json.JSONDecodeError:
        return []
    diagnostics = []
    if not isinstance(payload, list):
        return diagnostics
    for item in payload:
        if not isinstance(item, dict):
            continue
        location = item.get("location") or {}
        end = item.get("end_location") or {}
        diagnostics.append(
            {
                "path": str(item.get("filename") or ""),
                "line": int(location.get("row") or 1),
                "column": int(location.get("column") or 1),
                "end_line": int(end.get("row") or location.get("row") or 1),
                "end_column": int(end.get("column") or location.get("column") or 1),
                "code": str(item.get("code") or "RUFF"),
                "message": str(item.get("message") or "Lint diagnostic"),
                "fixable": bool(item.get("fix")),
            }
        )
    return diagnostics


def parse_pytest_nodeids(output):
    """Extract collected pytest node IDs while ignoring its summary lines."""
    found = []
    seen = set()
    for raw in (output or "").splitlines():
        line = raw.strip()
        if "::" not in line or line.startswith(("=", "<")):
            continue
        # Quiet collection normally emits one node ID per line. Keep the full
        # ID (including parameter IDs containing spaces) and tolerate the
        # bullet prefixes used by some pytest plugins.
        candidate = line.lstrip("*- ").strip()
        # Do not split on spaces: parameterized node IDs may contain them.
        if "::" in candidate and candidate not in seen:
            seen.add(candidate)
            found.append(candidate)
    return found


class QualityPanel(ttk.Frame):
    """Non-blocking Black/Ruff/pytest workbench bound to the active workspace."""

    def __init__(
        self,
        master,
        context_provider,
        document_provider,
        apply_source,
        navigate_diagnostic,
        status_callback=None,
        project_format_guard=None,
    ):
        super().__init__(master, padding=5)
        self.context_provider = context_provider
        self.document_provider = document_provider
        self.apply_source = apply_source
        self.navigate_diagnostic = navigate_diagnostic
        self.status_callback = status_callback or (lambda _message: None)
        self.project_format_guard = project_format_guard or (lambda: True)
        self._events = queue.Queue()
        self._worker = None
        self._process = None
        self._process_lock = threading.Lock()
        self._cancel_requested = threading.Event()
        self._closed = False
        self._poll_id = None
        self._busy = False
        self._tests = []
        self._diagnostics = []
        self._build()
        self._poll_id = self.after(100, self._poll)

    def _build(self):
        actions = ttk.Frame(self)
        actions.pack(fill="x", pady=(0, 5))
        for label, action in (
            ("Format Buffer", self.format_buffer),
            ("Format Project", self.format_project),
            ("Lint Buffer", self.lint_buffer),
            ("Lint Project", self.lint_project),
            ("Install Tools", self.install_tools),
            ("Stop", self.stop),
        ):
            ttk.Button(actions, text=label, command=action).pack(side="left", padx=2)
        self.status = ttk.Label(self, text="Ready")
        self.status.pack(fill="x", pady=(0, 4))

        self.notebook = ttk.Notebook(self)
        self.notebook.pack(fill="both", expand=True)
        tests_frame = ttk.Frame(self.notebook, padding=4)
        test_actions = ttk.Frame(tests_frame)
        test_actions.pack(fill="x", pady=(0, 4))
        ttk.Button(
            test_actions, text="Discover Tests", command=self.discover_tests
        ).pack(side="left", padx=2)
        ttk.Button(test_actions, text="Run All", command=self.run_all_tests).pack(
            side="left", padx=2
        )
        ttk.Button(
            test_actions, text="Run Selected", command=self.run_selected_test
        ).pack(side="left", padx=2)
        self.test_tree = ttk.Treeview(
            tests_frame,
            columns=("nodeid", "result"),
            show="headings",
            selectmode="browse",
        )
        self.test_tree.heading("nodeid", text="Test")
        self.test_tree.heading("result", text="Result")
        self.test_tree.column("nodeid", width=650)
        self.test_tree.column("result", width=110, anchor="center")
        self.test_tree.pack(fill="both", expand=True)
        # Double-clicking a discovered test (or pressing Enter) runs that test.
        self.test_tree.bind("<Double-1>", self._run_test_from_event)
        self.test_tree.bind("<Return>", self._run_test_from_event)
        self.test_tree.bind(
            "<Button-3>",
            lambda event: self._show_tree_context_menu(
                self.test_tree, event, tests=True
            ),
            add="+",
        )
        self.notebook.add(tests_frame, text="Test Explorer")

        diagnostics_frame = ttk.Frame(self.notebook, padding=4)
        self.diagnostic_tree = ttk.Treeview(
            diagnostics_frame,
            columns=("code", "file", "line", "column", "message"),
            show="headings",
        )
        for key, label, width in (
            ("code", "Rule", 75),
            ("file", "File", 190),
            ("line", "Line", 55),
            ("column", "Column", 65),
            ("message", "Message", 430),
        ):
            self.diagnostic_tree.heading(key, text=label)
            self.diagnostic_tree.column(key, width=width)
        self.diagnostic_tree.pack(fill="both", expand=True)
        self.diagnostic_tree.bind("<Double-1>", self._open_diagnostic)
        self.diagnostic_tree.bind(
            "<Button-3>",
            lambda event: self._show_tree_context_menu(self.diagnostic_tree, event),
            add="+",
        )
        self.notebook.add(diagnostics_frame, text="Lint Diagnostics")

        output_frame = ttk.Frame(self.notebook, padding=4)
        self.output = tk.Text(output_frame, wrap="none", height=8, state="disabled")
        self.output.pack(fill="both", expand=True)
        self.output.bind(
            "<Shift-MouseWheel>", self._scroll_output_horizontally, add="+"
        )
        self.output.bind("<Button-3>", self._show_output_context_menu, add="+")
        self.notebook.add(output_frame, text="Tool Output")

    def _context_menu(self):
        root = self.winfo_toplevel()
        preferences = getattr(root, "preferences", {})
        font_family = (
            root._resolved_ui_font()
            if hasattr(root, "_resolved_ui_font")
            else "Segoe UI"
        )
        return ContextMenu(
            self,
            palette=getattr(root, "theme_palette", {}),
            font_family=font_family,
            font_size=preferences.get("ui_font_size", 9),
        )

    def _show_tree_context_menu(self, tree, event, tests=False):
        row = tree.identify_row(event.y)
        column = tree.identify_column(event.x)
        if row:
            if row not in tree.selection():
                tree.selection_set(row)
            tree.focus(row)
        menu = self._context_menu()
        if row:
            values = tree.item(row, "values")
            menu.add_command(
                label="Copy Row",
                command=lambda: self._copy_context_text(" | ".join(map(str, values))),
            )
            if column and column != "#0":
                index = int(column[1:]) - 1
                if 0 <= index < len(values):
                    menu.add_command(
                        label="Copy Cell",
                        command=lambda value=values[index]: self._copy_context_text(
                            value
                        ),
                    )
            menu.add_separator()
            if tests:
                menu.add_command(
                    label="Run Selected Test", command=self.run_selected_test
                )
            else:
                menu.add_command(label="Open Diagnostic", command=self._open_diagnostic)
                menu.add_command(
                    label="Copy Diagnostic Message",
                    command=lambda: self._copy_context_text(
                        values[-1] if values else ""
                    ),
                )
        if tests:
            menu.add_command(label="Discover Tests", command=self.discover_tests)
            menu.add_command(label="Run All Tests", command=self.run_all_tests)
        else:
            menu.add_command(
                label="Select All Diagnostics",
                command=lambda: tree.selection_set(tree.get_children("")),
            )
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _copy_context_text(self, value):
        self.clipboard_clear()
        self.clipboard_append(str(value))

    def _show_output_context_menu(self, event):
        menu = self._context_menu()
        try:
            selected = bool(self.output.tag_ranges("sel"))
        except tk.TclError:
            selected = False
        menu.add_command(
            label="Copy Selection",
            command=lambda: self.output.event_generate("<<Copy>>"),
            state="normal" if selected else "disabled",
        )
        menu.add_command(
            label="Select All",
            command=lambda: self.output.tag_add("sel", "1.0", "end-1c"),
        )
        menu.add_separator()
        menu.add_command(label="Clear Tool Output", command=self._clear_output)
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()
        return "break"

    def _scroll_output_horizontally(self, event):
        """Scroll tool output horizontally while Shift and the wheel are used."""
        self.output.xview_scroll(-int(event.delta / 120) * 3, "units")
        return "break"

    def _context(self):
        root, interpreter, env = self.context_provider()
        root = Path(root).expanduser().resolve()
        return root, str(interpreter), dict(env)

    def _document(self):
        editor, path, source = self.document_provider()
        if path is None:
            root, _interpreter, _env = self._context()
            path = root / "untitled.py"
        return editor, Path(path).expanduser().resolve(), str(source)

    def _set_status(self, message):
        self.status.configure(text=message)
        self.status_callback(message)

    def _append_output(self, content):
        self.output.configure(state="normal")
        self.output.insert("end", content)
        self.output.see("end")
        self.output.configure(state="disabled")

    def _clear_output(self):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")

    def _start(self, argv, cwd, env, *, stdin=None, callback=None, label="Running"):
        if self._closed:
            return False
        if self._busy:
            self._set_status("A quality tool is already running.")
            return False
        self._cancel_requested.clear()
        self._busy = True
        self._set_status(label + "...")
        self._clear_output()

        def worker():
            try:
                process = subprocess.Popen(
                    argv,
                    cwd=str(cwd),
                    env=env,
                    stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    **_process_options(),
                )
                attach_process_job(process)
                with self._process_lock:
                    self._process = process
                    cancelled = self._closed or self._cancel_requested.is_set()
                if cancelled:
                    terminate_process_tree(process)
                stdout, stderr = process.communicate(input=stdin)
                # A tool may exit while leaving helper processes behind.
                terminate_process_tree(process)
                self._events.put(
                    ("complete", (process.returncode, stdout, stderr, callback))
                )
            except Exception as exc:
                self._events.put(("error", (exc, callback)))

        self._worker = threading.Thread(target=worker, daemon=True)
        self._worker.start()
        return True

    def _poll(self):
        if self._closed:
            return
        try:
            while True:
                kind, payload = self._events.get_nowait()
                self._busy = False
                with self._process_lock:
                    self._process = None
                if kind == "error":
                    exc, callback = payload
                    self._append_output(f"{type(exc).__name__}: {exc}\n")
                    self._set_status("Tool failed to start.")
                    if callback:
                        callback(None, "", str(exc))
                    continue
                code, stdout, stderr, callback = payload
                if stdout:
                    self._append_output(stdout)
                if stderr:
                    self._append_output(stderr)
                self._set_status(
                    "Completed successfully."
                    if code == 0
                    else f"Finished with exit code {code}."
                )
                if callback:
                    callback(code, stdout, stderr)
        except queue.Empty:
            pass
        try:
            self._poll_id = self.after(100, self._poll)
        except tk.TclError:
            self._poll_id = None

    def stop(self):
        self._cancel_requested.set()
        with self._process_lock:
            process = self._process
        if process is not None:
            terminate_process_tree(process)
            self._set_status("Stopping quality tool...")
        else:
            self._set_status("Stopping quality tool...")

    def close(self):
        """Stop pending or active quality work and cancel its UI poller."""
        self._closed = True
        self._cancel_requested.set()
        if self._poll_id is not None:
            try:
                self.after_cancel(self._poll_id)
            except tk.TclError:
                pass
            self._poll_id = None
        with self._process_lock:
            process = self._process
            self._process = None
        if process is not None:
            terminate_process_tree(process)

    def _tool_missing(self, module):
        messagebox.showerror(
            "Quality Tools",
            f"{module} is not installed in the selected Python interpreter. "
            "Use Install Tools to install Black, Ruff, and pytest in that environment.",
            parent=self.winfo_toplevel(),
        )

    def install_tools(self):
        try:
            root, interpreter, env = self._context()
        except Exception as exc:
            messagebox.showerror(
                "Install Tools", str(exc), parent=self.winfo_toplevel()
            )
            return
        if not messagebox.askyesno(
            "Install Quality Tools",
            (
                "Install or upgrade Black, Ruff, and pytest in the currently selected "
                "project interpreter?"
            ),
            parent=self.winfo_toplevel(),
        ):
            return
        self._start(
            tool_argv(
                interpreter, "pip", ("install", "--upgrade", "black", "ruff", "pytest")
            ),
            root,
            env,
            label="Installing Black, Ruff, and pytest",
        )

    def format_buffer(self):
        try:
            root, interpreter, env = self._context()
            editor, path, source = self._document()
        except Exception as exc:
            messagebox.showerror(
                "Format Buffer", str(exc), parent=self.winfo_toplevel()
            )
            return

        def completed(code, stdout, stderr):
            if code == 0:
                self.apply_source(editor, stdout)
                self._set_status("Current editor buffer formatted with Black.")
            elif "No module named black" in stderr:
                self._tool_missing("Black")

        self._start(
            tool_argv(
                interpreter, "black", ("--quiet", "--stdin-filename", str(path), "-")
            ),
            root,
            env,
            stdin=source,
            callback=completed,
            label="Formatting current buffer",
        )

    def format_project(self):
        try:
            root, interpreter, env = self._context()
        except Exception as exc:
            messagebox.showerror(
                "Format Project", str(exc), parent=self.winfo_toplevel()
            )
            return
        if not self.project_format_guard():
            return
        if not messagebox.askyesno(
            "Format Project",
            f"Black will reformat Python files under:\n{root}\n\n"
            "Save open editor changes first. Continue?",
            parent=self.winfo_toplevel(),
        ):
            return
        self._start(
            tool_argv(interpreter, "black", (str(root),)),
            root,
            env,
            label="Formatting project with Black",
        )

    def lint_buffer(self):
        try:
            root, interpreter, env = self._context()
            _editor, path, source = self._document()
        except Exception as exc:
            messagebox.showerror("Lint Buffer", str(exc), parent=self.winfo_toplevel())
            return

        def completed(code, stdout, stderr):
            if code in (0, 1):
                self._display_diagnostics(parse_ruff_diagnostics(stdout))
                self.notebook.select(1)
            elif "No module named ruff" in stderr:
                self._tool_missing("Ruff")

        self._start(
            tool_argv(
                interpreter,
                "ruff",
                ("check", "--output-format=json", "--stdin-filename", str(path), "-"),
            ),
            root,
            env,
            stdin=source,
            callback=completed,
            label="Linting current buffer",
        )

    def lint_project(self):
        try:
            root, interpreter, env = self._context()
        except Exception as exc:
            messagebox.showerror("Lint Project", str(exc), parent=self.winfo_toplevel())
            return

        def completed(code, stdout, stderr):
            if code in (0, 1):
                self._display_diagnostics(parse_ruff_diagnostics(stdout))
                self.notebook.select(1)
            elif "No module named ruff" in stderr:
                self._tool_missing("Ruff")

        self._start(
            tool_argv(
                interpreter, "ruff", ("check", "--output-format=json", str(root))
            ),
            root,
            env,
            callback=completed,
            label="Linting project",
        )

    def _display_diagnostics(self, diagnostics):
        self._diagnostics = diagnostics
        self.diagnostic_tree.delete(*self.diagnostic_tree.get_children())
        for index, item in enumerate(diagnostics):
            self.diagnostic_tree.insert(
                "",
                "end",
                iid=f"diag-{index}",
                values=(
                    item["code"],
                    item["path"],
                    item["line"],
                    item["column"],
                    item["message"],
                ),
            )
        self._set_status(f"Ruff found {len(diagnostics)} diagnostic(s).")

    def _open_diagnostic(self, _event=None):
        selected = self.diagnostic_tree.selection()
        if not selected:
            return
        index = int(selected[0].split("-", 1)[1])
        self.navigate_diagnostic(self._diagnostics[index])

    def _run_test_from_event(self, event=None):
        """Run the row under the pointer, or the current row on Enter."""
        if event is not None and getattr(event, "y", None) is not None:
            item = self.test_tree.identify_row(event.y)
            if item:
                self.test_tree.selection_set(item)
                self.test_tree.focus(item)
        self.run_selected_test()
        return "break"

    def discover_tests(self):
        try:
            root, interpreter, env = self._context()
        except Exception as exc:
            messagebox.showerror(
                "Test Explorer", str(exc), parent=self.winfo_toplevel()
            )
            return

        def completed(code, stdout, stderr):
            if code == 0:
                self._tests = parse_pytest_nodeids(stdout)
                self.test_tree.delete(*self.test_tree.get_children())
                for index, nodeid in enumerate(self._tests):
                    self.test_tree.insert(
                        "", "end", iid=f"test-{index}", values=(nodeid, "Discovered")
                    )
                self.notebook.select(0)
                self._set_status(f"Discovered {len(self._tests)} test(s).")
            elif (
                "No module named pytest" in stderr or "No module named pytest" in stdout
            ):
                self._tool_missing("pytest")
                self._set_status(
                    (
                        "pytest is missing from the selected interpreter. "
                        "Use Install Tools."
                    )
                )
            else:
                # Keep the collection error visible and make the failure actionable.
                detail = (stderr or stdout).strip()
                self._set_status(
                    (
                        "Test discovery failed; inspect Tool Output for "
                        "collection/import errors."
                    )
                )
                if not detail:
                    self._append_output(
                        f"pytest collection exited with code {code} and "
                        "produced no diagnostic.\n"
                    )

        self._start(
            tool_argv(
                interpreter,
                "pytest",
                (
                    "--collect-only",
                    "-q",
                    "--disable-warnings",
                    "--no-header",
                    str(root),
                ),
            ),
            root,
            env,
            callback=completed,
            label="Discovering tests",
        )

    def run_all_tests(self):
        self._run_tests(None)

    def run_selected_test(self):
        selection = self.test_tree.selection()
        if not selection:
            self._set_status("Select a test in Test Explorer first.")
            return
        index = int(selection[0].split("-", 1)[1])
        self._run_tests(self._tests[index])

    def _run_tests(self, nodeid):
        try:
            root, interpreter, env = self._context()
        except Exception as exc:
            messagebox.showerror("Run Tests", str(exc), parent=self.winfo_toplevel())
            return
        args = ["-v", str(nodeid)] if nodeid else ["-v", str(root)]

        def completed(code, stdout, stderr):
            combined = stdout + "\n" + stderr
            for index, test_id in enumerate(self._tests):
                match = re.search(
                    re.escape(test_id) + r"\s+(PASSED|FAILED|SKIPPED|ERROR)", combined
                )
                if match:
                    self.test_tree.set(f"test-{index}", "result", match.group(1))
            self.notebook.select(0)
            if "No module named pytest" in stderr:
                self._tool_missing("pytest")
            elif code == 0:
                self._set_status("Tests passed.")
            else:
                self._set_status(f"Tests finished with exit code {code}.")

        self._start(
            tool_argv(interpreter, "pytest", args),
            root,
            env,
            callback=completed,
            label="Running tests",
        )
