"""Debugger lifecycle controller with no dependency on Tkinter."""


class DebuggerController:
    """Own the active debugger session and centralize its lifecycle."""

    def __init__(self, service):
        self.service = service
        self.session = None

    @property
    def running(self):
        return self.session is not None and not self.session.done

    def start_document(self, *args, **kwargs):
        if self.running:
            raise RuntimeError("A debugging session is already active.")
        if self.session is not None:
            self.session.close()
            self.session = None
        self.session = self.service.start_debugger_document(*args, **kwargs)
        return self.session

    def stop(self):
        if not self.running:
            return False
        self.session.stop()
        return True

    def finish(self, close=True, session=None):
        if session is not None and self.session is not session:
            return False
        current = self.session
        if current is not None and close:
            current.close()
        self.session = None
        return current is not None
