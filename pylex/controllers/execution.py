"""Execution lifecycle controller with no dependency on the graphical interface."""


class ExecutionController:
    """Own one active execution handle and centralize process lifecycle checks."""

    def __init__(self, service):
        self.service = service
        self.handle = None

    @property
    def running(self):
        return self.handle is not None and not self.handle.done

    def start_document(self, *args, **kwargs):
        if self.running:
            raise RuntimeError("A program is already running.")
        self.handle = self.service.start_document(*args, **kwargs)
        return self.handle

    def stop(self):
        if not self.running:
            return False
        self.handle.force_stop()
        return True

    def finish(self, handle=None):
        if handle is not None and self.handle is not handle:
            return False
        self.handle = None
        return True
