"""Reusable command registry for application actions.

The registry is deliberately UI-agnostic so command discovery and execution can
be tested without creating a Tk root window.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass(frozen=True)
class Command:
    """A user-invokable application command."""

    command_id: str
    label: str
    shortcut: str
    action: Callable[[], object]


class CommandRegistry:
    """Store commands by stable ID and provide predictable text search."""

    def __init__(self, commands: Iterable[Command] = ()):
        self._commands: dict[str, Command] = {}
        for command in commands:
            self.register(command)

    def register(self, command: Command) -> None:
        """Register a command, rejecting duplicate or empty identifiers."""
        command_id = command.command_id.strip()
        if not command_id:
            raise ValueError("A command ID is required.")
        if command_id in self._commands:
            raise ValueError(f"Command already registered: {command_id}")
        if not command.label.strip():
            raise ValueError("A command label is required.")
        self._commands[command_id] = command

    def get(self, command_id: str) -> Command | None:
        """Return a command by stable ID, if it exists."""
        return self._commands.get(command_id)

    def all(self) -> tuple[Command, ...]:
        """Return commands in registration order."""
        return tuple(self._commands.values())

    def search(self, query: str = "") -> list[Command]:
        """Search labels, IDs, and shortcuts case-insensitively."""
        term = str(query).strip().casefold()
        if not term:
            return list(self._commands.values())
        matches = []
        for command in self._commands.values():
            searchable = " ".join(
                (command.label, command.command_id, command.shortcut)
            ).casefold()
            if term in searchable:
                matches.append(command)
        return matches

    def execute(self, command_id: str) -> bool:
        """Execute a registered action; return False for unknown IDs."""
        command = self.get(command_id)
        if command is None:
            return False
        command.action()
        return True
