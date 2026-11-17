"""Lifecycle coordination for asynchronous file-loading operations."""


class FileLoadTicket:
    """Immutable identity for one file read within one UI lifecycle."""

    __slots__ = ("path", "generation")

    def __init__(self, path, generation):
        self.path = path
        self.generation = generation

    def __eq__(self, other):
        return (
            isinstance(other, FileLoadTicket)
            and self.path == other.path
            and self.generation == other.generation
        )

    def __hash__(self):
        return hash((self.path, self.generation))


class FileLoadCoordinator:
    """Track pending reads and invalidate stale completions without Tk access.

    All methods are intended to be called from the UI thread. Worker threads
    only perform file I/O and publish results through their result queues.
    """

    def __init__(self):
        self._generation = 0
        self._pending = {}

    def begin(self, path):
        """Create a ticket, or return None when this path is already pending."""
        if path in self._pending:
            return None
        ticket = FileLoadTicket(path, self._generation)
        self._pending[path] = ticket
        return ticket

    def is_current(self, ticket):
        """Whether a ticket still belongs to the current UI/workspace context."""
        return (
            ticket.generation == self._generation
            and self._pending.get(ticket.path) == ticket
        )

    def complete(self, ticket):
        """Forget a ticket only if it is still the registered operation."""
        if self._pending.get(ticket.path) != ticket:
            return False
        del self._pending[ticket.path]
        return True

    def invalidate(self):
        """Make every outstanding completion stale and allow fresh operations."""
        self._generation += 1
        self._pending.clear()

    @property
    def pending_count(self):
        return len(self._pending)
