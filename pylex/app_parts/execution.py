"""Execution responsibilities for the PyLex application."""

from ..app_support import *  # noqa: F403


class ExecutionMixin:
    """Execution UI behavior composed into :class:`PyLexApp`."""

    def run_code(self):
        if self.debug_session is not None and not self.debug_session.done:
            self.status.configure(
                text="Stop debugging before starting normal execution."
            )
            return
        if self.execution is not None and not self.execution.done:
            self.status.configure(
                text="A program is already running. Force Stop it before starting another."
            )
            return
        source = self.editor.get_content()
        document = self._active_document()
        project = self._project_for_document(document)
        try:
            interpreter = self._interpreter_for_project(project)
        except (OSError, ValueError, TimeoutError) as exc:
            messagebox.showerror("Python Interpreter", str(exc))
            return
        dependencies, scan_error = inspect_dependencies(
            source, search_root=project.root, python_executable=interpreter.executable
        )
        self._update_dependency_view(dependencies, scan_error, interpreter.executable)
        self._show(self.output, "")
        env = python_environment(interpreter.executable)
        self._append_output(
            f"Python: {env['version']} | {env['executable']}\n"
            f"Environment: {'virtual environment' if env['virtual_environment'] else 'base interpreter'}\n",
            "system",
        )
        missing = [item for item in dependencies if item.status == "missing"]
        if scan_error:
            self._append_output(scan_error + "\n", "stderr")
        if missing:
            lines = [
                "DEPENDENCY CHECK — missing imports detected",
                "Install into this exact interpreter using the commands below:",
            ]
            lines.extend(
                f"  • {item.import_name} → {item.distribution}: "
                f"{env['executable']} -m pip install {item.distribution}"
                for item in missing
            )
            if not env["pip_available"]:
                lines.append(
                    "pip is unavailable in this interpreter. Use Tools → Python Interpreter → Repair pip first."
                )
            lines.append(
                "Static scanning cannot detect every dynamic import; runtime errors are also reported.\n"
            )
            self._append_output("\n".join(lines) + "\n", "system")
        elif not scan_error:
            self._append_output(
                "Dependency check: no missing imports detected.\n", "system"
            )
        self._append_output("Starting program...\n", "system")
        try:
            timeout = self.preferences["timeout_seconds"]
            self.execution_controller.start_document(
                source,
                document.get("path") if document else None,
                project,
                timeout=timeout,
                dirty=bool(document and document.get("dirty")),
                python_executable=interpreter.executable,
            )
        except OSError as exc:
            self._append_output(f"Could not start Python process: {exc}\n", "stderr")
            self.status.configure(text="Could not start Python process.")
            return
        timeout_label = "unlimited" if timeout is None else f"{timeout} seconds"
        self._append_output(f"Execution timeout: {timeout_label}.\n", "system")
        self._last_timeout_display = None
        self.status.configure(
            text=f"Running — timeout: {timeout_label}. Shift+F5 / Force Stop terminates the process tree."
        )
        self._poll_execution()

    def stop_execution(self):
        if self.execution_controller.stop():
            self.status.configure(text="Force-stopping process and child processes...")
            return
        if self.debugger_controller.stop():
            self.status.configure(text="Force-stopping debugger and child processes...")
            return
        self.status.configure(text="No program is currently running.")

    def _poll_execution(self):
        handle = self.execution
        if handle is None:
            return
        for channel, content in handle.read_available():
            self._append_output(content, channel)
        if not handle.done:
            timeout = handle.timeout
            if timeout is None:
                display = "unlimited"
                status_text = (
                    "Running — no time limit. Use Force Stop / Shift+F5 to terminate."
                )
            else:
                remaining = max(
                    0, int(timeout - (time.monotonic() - handle.started_at) + 0.999)
                )
                display = str(remaining)
                status_text = (
                    f"Running — {remaining}s remaining before timeout. "
                    "Use Force Stop / Shift+F5 to terminate."
                )
            if display != self._last_timeout_display:
                self.status.configure(text=status_text)
                self._last_timeout_display = display
            self._execution_poll = self.after(60, self._poll_execution)
            return
        result = handle.result
        # Drain any final chunks queued as the reader threads close.
        for channel, content in handle.read_available():
            self._append_output(content, channel)
        self._append_output(
            f"\n{'=' * 64}\nExecution: {result.status.upper()}\n"
            f"Exit code: {result.exit_code}\nDuration: {result.duration:.2f}s\n",
            "system",
        )
        if result.stderr:
            self._report_runtime_error(result.stderr)
        self.status.configure(
            text=f"Execution {result.status} — exit code {result.exit_code}."
        )
        self.execution_controller.finish(handle)
        self._execution_poll = None

    def run_active_file_in_terminal(self):
        """Run the active, saved editor document in the integrated shell."""
        document = self._active_document()
        if document is None:
            messagebox.showinfo("Run Active File", "Open a Python file first.")
            return
        if document["path"] is None or document["dirty"]:
            if not self.save_file():
                return
            document = self._active_document()
        path = document.get("path") if document else None
        if path is None or not Path(path).is_file():
            messagebox.showwarning(
                "Run Active File", "Save the active file before running it in Terminal."
            )
            return
        _cwd, _env, interpreter = self._terminal_context()
        if not interpreter:
            messagebox.showerror(
                "Run Active File",
                "No Python interpreter is available for this workspace.",
            )
            return
        session = self.open_terminal()
        if session is None or not session.running:
            messagebox.showerror(
                "Run Active File", "Could not create a terminal for this file."
            )
            return
        frame = self.terminal_panel._current_frame()
        view = self.terminal_panel.views.get(frame, {})
        shell = view.get("shell", self.terminal_panel.shell_var.get())
        try:
            command = python_file_command(shell, interpreter, path)
        except ValueError as exc:
            messagebox.showerror("Run Active File", str(exc))
            return
        if not self.terminal_panel.run_command(command):
            messagebox.showerror(
                "Run Active File", "The terminal session is not ready."
            )

    def _send_output_input(self, _event=None):
        """Forward one line from Output to the active run or debug process."""
        if not hasattr(self, "output_input"):
            return "break"
        value = self.output_input.get()
        accepted = False
        if self.execution is not None and not self.execution.done:
            accepted = self.execution.send_input(value)
        elif self.debug_session is not None and not self.debug_session.done:
            accepted = self.debug_session.send_input(value)
        if not accepted:
            self.status.configure(text="No running program is waiting for input.")
            return "break"
        self._append_output(value + "\n", "system")
        self.output_input.delete(0, "end")
        self.output_input.focus_set()
        self.status.configure(text="Input sent to the running program.")
        return "break"

    def _append_output(self, content, channel="stdout"):
        self.output.configure(state="normal")
        self.output.insert(
            "end",
            content,
            channel if channel in {"stdout", "stderr", "system"} else "stdout",
        )
        self.output.see("end")
        self.output.configure(state="disabled")

    def clear_output(self):
        self.output.configure(state="normal")
        self.output.delete("1.0", "end")
        self.output.configure(state="disabled")
        self.status.configure(text="Output cleared.")

    def save_output(self):
        content = self.output.get("1.0", "end-1c")
        if not content:
            self.status.configure(text="There is no output to save.")
            return
        path = filedialog.asksaveasfilename(
            title="Save Execution Output",
            defaultextension=".txt",
            filetypes=[
                ("Text files", "*.txt"),
                ("Log files", "*.log"),
                ("All files", "*.*"),
            ],
        )
        if not path:
            return
        try:
            Path(path).write_text(content, encoding="utf-8")
            self.status.configure(text=f"Output saved to {path}.")
        except OSError as exc:
            messagebox.showerror("Save Output Error", str(exc))

    def _report_runtime_error(self, stderr):
        exception_matches = re.findall(
            r"^([A-Za-z_][\w.]*(?:Error|Exception)): (.*)$",
            stderr,
            re.MULTILINE,
        )
        if not exception_matches:
            return
        error_type, message = exception_matches[-1]
        line_matches = re.findall(r'File "[^"]+", line (\d+)', stderr)
        line = int(line_matches[-1]) if line_matches else 1
        source_lines = self.editor.get_content().splitlines()
        source_line = source_lines[line - 1] if 1 <= line <= len(source_lines) else ""
        if error_type == "ModuleNotFoundError":
            missing = re.search(r"No module named ['\"]([^'\"]+)['\"]", message)
            if missing:
                module = missing.group(1)
                from .dependencies import PIP_NAMES

                package = PIP_NAMES.get(
                    module.split(".", 1)[0], module.split(".", 1)[0]
                )
                interpreter = self._interpreter_for_project(
                    self._project_for_document(self._active_document())
                ).executable
                message = (
                    f"Missing library '{module}'. Install it into the active interpreter with: "
                    f'"{interpreter}" -m pip install "{package}"'
                )
        from .analyzer import Diagnostic

        diagnostic = Diagnostic(
            error_type,
            message,
            line,
            0,
            line,
            0,
            source_line,
        )
        self._set_diagnostics([diagnostic])
        self.tabs.select(self.error_tree.master)
        self.status.configure(
            text=f"Runtime error: {error_type} — line {line}. See Errors and Output."
        )

