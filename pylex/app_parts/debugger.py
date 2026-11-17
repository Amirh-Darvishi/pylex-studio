"""Debugger responsibilities for the PyLex application."""

# These modules intentionally consume the shared UI dependency namespace.
# ruff: noqa: F403, F405

from ..app_support import *  # noqa: F403


class DebuggerMixin:
    """Debugger UI behavior composed into :class:`PyLexApp`."""

    def toggle_breakpoint(self):
        line = int(self.editor.text.index("insert").split(".")[0])
        points = self.breakpoints.setdefault(self.editor, set())
        if line in points:
            points.remove(line)
            self.conditional_breakpoints.setdefault(self.editor, {}).pop(line, None)
            if self.debug_session is not None and not self.debug_session.done:
                self.debug_session.clear_breakpoint(line)
            self.editor.set_breakpoints(points)
            self.status.configure(text=f"Breakpoint removed from line {line}.")
        else:
            points.add(line)
            self.conditional_breakpoints.setdefault(self.editor, {}).pop(line, None)
            if self.debug_session is not None and not self.debug_session.done:
                self.debug_session.set_breakpoint(line)
            self.editor.set_breakpoints(points)
            self.status.configure(text=f"Breakpoint set on line {line}.")
        return line

    def start_debugging(self):
        if self.debug_session is not None and self.debug_session.done:
            self.debug_session.close()
            self.debug_session = None
        if self.execution is not None and not self.execution.done:
            self.status.configure(
                text="Stop normal execution before starting the debugger."
            )
            return
        if self.debug_session is not None and not self.debug_session.done:
            self.status.configure(text="A debugging session is already active.")
            return
        try:
            document = self._active_document()
            project = self._project_for_document(document)
            self.debugger_controller.start_document(
                self.editor.get_content(),
                document.get("path") if document else None,
                project,
                dirty=bool(document and document.get("dirty")),
                python_executable=self._interpreter_for_project(project).executable,
            )
        except (OSError, ValueError, TimeoutError) as exc:
            messagebox.showerror("Debugger Error", str(exc))
            return
        self._show(
            self.output, "Debugger started. Set breakpoints, then choose Continue.\n"
        )
        conditions = self.conditional_breakpoints.get(self.editor, {})
        for line in sorted(self.breakpoints.get(self.editor, set())):
            condition = conditions.get(line)
            if condition:
                self.debug_session.set_conditional_breakpoint(line, condition)
            else:
                self.debug_session.set_breakpoint(line)
        self.status.configure(
            text="Debugger ready — set breakpoints or press Continue."
        )
        self._poll_debugger()

    def debug_continue(self):
        if self.debug_session is None or self.debug_session.done:
            self.status.configure(text="No active debugging session.")
            return
        self.debug_session.continue_execution()
        self.status.configure(text="Debugger running...")

    def debug_step(self):
        if self.debug_session is None or self.debug_session.done:
            self.status.configure(text="No active debugging session.")
            return
        self.debug_session.step()
        self.status.configure(text="Stepping into next statement...")

    def debug_next(self):
        if self.debug_session is None or self.debug_session.done:
            self.status.configure(text="No active debugging session.")
            return
        self.debug_session.next()
        self.status.configure(text="Stepping over current statement...")

    def debug_variables(self):
        if self.debug_session is None or self.debug_session.done:
            self.status.configure(text="No active debugging session.")
            return
        self.debug_session.inspect_variables()
        self.status.configure(text="Requested current-frame variables.")

    def debug_stack(self):
        if self.debug_session is None or self.debug_session.done:
            self.status.configure(text="No active debugging session.")
            return
        self.debug_session.command("where")
        self.status.configure(text="Requested current stack trace.")

    def _active_debug_session(self):
        session = self.debug_session
        if session is None or session.done:
            self.status.configure(text="No active debugging session.")
            return None
        return session

    def debug_arguments(self):
        session = self._active_debug_session()
        if session is not None:
            session.show_arguments()
            self.status.configure(text="Requested current function arguments.")

    def debug_until(self):
        session = self._active_debug_session()
        if session is None:
            return
        line = int(self.editor.text.index("insert").split(".")[0])
        session.until(line)
        self.status.configure(text=f"Running until line {line}.")

    def debug_return(self):
        session = self._active_debug_session()
        if session is not None:
            session.return_from_frame()
            self.status.configure(text="Running until the current function returns.")

    def debug_jump(self):
        session = self._active_debug_session()
        if session is None:
            return
        line = simpledialog.askinteger(
            "Debugger — Jump to Line",
            "Target line:",
            parent=self,
            minvalue=1,
        )
        if line is not None:
            try:
                session.jump(line)
                self.status.configure(
                    text=f"Requested jump to line {line} (pdb frame restrictions apply)."
                )
            except ValueError as exc:
                messagebox.showerror("Debugger", str(exc))

    def debug_evaluate(self):
        session = self._active_debug_session()
        if session is None:
            return
        expression = simpledialog.askstring(
            "Debugger — Evaluate",
            "Python expression in the selected frame:",
            parent=self,
        )
        if expression is None:
            return
        try:
            session.pretty_print(expression)
            self.status.configure(text="Expression evaluation requested; see Output.")
        except ValueError as exc:
            messagebox.showerror("Debugger", str(exc))

    def debug_temporary_breakpoint(self):
        session = self._active_debug_session()
        if session is None:
            return
        line = int(self.editor.text.index("insert").split(".")[0])
        try:
            session.set_temporary_breakpoint(line)
            self.status.configure(
                text=f"Temporary breakpoint requested at line {line}."
            )
        except ValueError as exc:
            messagebox.showerror("Debugger", str(exc))

    def debug_conditional_breakpoint(self):
        session = self._active_debug_session()
        if session is None:
            return
        line = int(self.editor.text.index("insert").split(".")[0])
        condition = simpledialog.askstring(
            "Conditional Breakpoint",
            f"Stop at line {line} only when this expression is true:",
            parent=self,
        )
        if condition is None:
            return
        try:
            session.set_conditional_breakpoint(line, condition)
            self.breakpoints.setdefault(self.editor, set()).add(line)
            self.conditional_breakpoints.setdefault(self.editor, {})[line] = condition
            self.editor.set_breakpoints(self.breakpoints[self.editor])
            self.status.configure(
                text=f"Conditional breakpoint requested at line {line}."
            )
        except ValueError as exc:
            messagebox.showerror("Debugger", str(exc))

    def debug_manage_breakpoint(self, action):
        session = self._active_debug_session()
        if session is None:
            return
        number = simpledialog.askinteger(
            "Debugger — Breakpoint",
            "Breakpoint number (shown by pdb's breakpoint list):",
            parent=self,
            minvalue=1,
        )
        if number is None:
            return
        try:
            if action == "enable":
                session.enable_breakpoint(number)
                message = f"Enabled breakpoint {number}."
            elif action == "disable":
                session.disable_breakpoint(number)
                message = f"Disabled breakpoint {number}."
            else:
                count = simpledialog.askinteger(
                    "Ignore Breakpoint Hits",
                    "Number of hits to ignore:",
                    parent=self,
                    minvalue=1,
                )
                if count is None:
                    return
                session.ignore_breakpoint(number, count)
                message = f"Breakpoint {number} will ignore the next {count} hit(s)."
            self.status.configure(text=message)
        except ValueError as exc:
            messagebox.showerror("Debugger", str(exc))

    def debug_clear_breakpoints(self):
        points = self.breakpoints.setdefault(self.editor, set())
        points.clear()
        self.conditional_breakpoints.setdefault(self.editor, {}).clear()
        self.editor.set_breakpoints(points)
        session = self._active_debug_session()
        if session is not None:
            session.clear_all_breakpoints()
        self.status.configure(text="All breakpoints cleared.")

    def stop_debugging(self):
        if self.debug_session is None:
            self.status.configure(text="No active debugging session.")
            return
        self.debugger_controller.stop()
        self.status.configure(text="Stopping debugger...")

    def _poll_debugger(self):
        session = self.debug_session
        if session is None:
            return
        output = session.read_available()
        if output:
            self._append_output(output)
        if session.done:
            completion = session.completion_status
            session.close()
            final_output = session.read_available()
            if final_output:
                self._append_output(final_output)
            self.debugger_controller.finish(close=False, session=session)
            self._debug_poll = None
            if completion == "error":
                self._append_output(
                    "\nDEBUG RESULT: Unhandled exception detected.\n", "stderr"
                )
                self.status.configure(
                    text="Debugging finished with an unhandled exception."
                )
            elif completion == "finished":
                self._append_output(
                    "\nDEBUG RESULT: Program completed successfully.\n", "system"
                )
                self.status.configure(text="Debugging finished successfully.")
            else:
                self.status.configure(text="Debugging session stopped.")
            return
        self._debug_poll = self.after(80, self._poll_debugger)
