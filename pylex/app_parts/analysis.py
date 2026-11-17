"""Analysis responsibilities for the PyLex application."""

# These modules intentionally consume the shared UI dependency namespace.
# ruff: noqa: F403, F405

from ..app_support import *  # noqa: F403
from ..analysis_tasks import analyze_source


class AnalysisMixin:
    """Analysis UI behavior composed into PyLexApp."""

    def _on_document_changed(self, editor):
        self.mark_dirty(editor)
        if editor is self.editor:
            self._cancel_analysis()

    def _cancel_analysis(self):
        """Invalidate pending analysis and stop its worker at the next checkpoint."""
        self._analysis_generation = getattr(self, "_analysis_generation", 0) + 1
        cancel_event = getattr(self, "_analysis_cancel_event", None)
        if cancel_event is not None:
            cancel_event.set()
            self._analysis_cancel_event = None
        job = getattr(self, "_analysis_poll_job", None)
        if job is not None:
            try:
                self.after_cancel(job)
            except tk.TclError:
                pass
            self._analysis_poll_job = None

    def _start_analysis(self, mode):
        """Run analysis against an immutable editor snapshot on a worker thread."""
        editor = self.editor
        if editor is None:
            return
        self._cancel_analysis()
        generation = self._analysis_generation
        source = editor.get_content()
        cancel_event = threading.Event()
        result_queue = queue.Queue(maxsize=1)
        self._analysis_cancel_event = cancel_event
        self.status.configure(text="Analysis running in background...")

        def worker():
            try:
                result = analyze_source(source, mode, cancel_event.is_set)
                if result is not None and not cancel_event.is_set():
                    result_queue.put((True, result))
            except Exception as exc:
                if not cancel_event.is_set():
                    result_queue.put((False, exc))

        threading.Thread(
            target=worker,
            name="pylex-source-analysis",
            daemon=True,
        ).start()
        self._poll_analysis_result(
            generation, editor, source, cancel_event, result_queue
        )

    def _poll_analysis_result(
        self, generation, editor, source, cancel_event, result_queue
    ):
        if (
            generation != self._analysis_generation
            or cancel_event.is_set()
            or editor not in self.documents
            or editor is not self.editor
        ):
            return
        try:
            succeeded, result = result_queue.get_nowait()
        except queue.Empty:
            try:
                self._analysis_poll_job = self.after(
                    25,
                    lambda: self._poll_analysis_result(
                        generation, editor, source, cancel_event, result_queue
                    ),
                )
            except tk.TclError:
                cancel_event.set()
            return

        self._analysis_poll_job = None
        self._analysis_cancel_event = None
        if editor.get_content() != source:
            return
        if not succeeded:
            self.status.configure(
                text=f"Analysis failed — {type(result).__name__}: {result}"
            )
            return

        mode = result["mode"]
        self._set_diagnostics(result["diagnostics"])
        if mode in {"lexical", "all"}:
            self._show(self.lexical, result["lexical_report"])
        if mode in {"syntax", "all"}:
            self._show(self.syntax, result["syntax_report"])

        if mode == "lexical":
            if result["lexical_error"]:
                status = f"Lexical analysis failed — {result['lexical_error']}."
            else:
                status = (
                    f"Lexical analysis complete — {result['lexical_count']} tokens."
                )
        elif mode == "syntax":
            syntax = result["syntax"]
            status = (
                "Syntax analysis successful."
                if syntax.success
                else f"{syntax.error_type or 'Syntax error'} detected."
            )
        else:
            syntax = result["syntax"]
            lexical_status = (
                f"{result['lexical_count']} tokens"
                if result["lexical_error"] is None
                else f"failed ({result['lexical_error']})"
            )
            self.tabs.select(self.error_tree.master)
            status = (
                f"Analysis complete — {lexical_status}; "
                f"{'syntax valid' if syntax.success else syntax.error_type}; "
                f"{len(result['diagnostics'])} diagnostic(s)."
            )
        self.status.configure(text=status)

    def analyze_lexical(self):
        self._start_analysis("lexical")

    def analyze_syntax(self):
        self._start_analysis("syntax")

    def analyze_all(self):
        self._start_analysis("all")

    def clear_results(self):
        self._cancel_analysis()
        for panel in (self.output, self.lexical, self.syntax):
            panel.configure(state="normal")
            panel.delete("1.0", "end")
            panel.configure(state="disabled")
        for item in self.error_tree.get_children():
            self.error_tree.delete(item)
        self.diagnostics = []
        self.error_summary.configure(text="Results cleared.")
        self.editor.clear_diagnostic()
        self.status.configure(text="Analysis results cleared.")
