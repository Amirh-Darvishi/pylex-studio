"""Regression tests for asynchronous file-load lifecycle coordination."""

from pylex.file_loading import FileLoadCoordinator


def test_duplicate_path_is_not_loaded_twice():
    coordinator = FileLoadCoordinator()
    first = coordinator.begin("workspace/data.json")
    assert first is not None
    assert coordinator.begin("workspace/data.json") is None
    assert coordinator.pending_count == 1


def test_completed_ticket_is_removed_and_path_can_be_reloaded():
    coordinator = FileLoadCoordinator()
    first = coordinator.begin("workspace/data.json")
    assert coordinator.complete(first)
    assert not coordinator.is_current(first)
    second = coordinator.begin("workspace/data.json")
    assert second is not None
    assert second != first


def test_invalidation_makes_pending_results_stale():
    coordinator = FileLoadCoordinator()
    old_ticket = coordinator.begin("workspace/large.json")
    coordinator.invalidate()
    assert not coordinator.is_current(old_ticket)
    assert coordinator.pending_count == 0
    new_ticket = coordinator.begin("workspace/large.json")
    assert new_ticket is not None
    assert new_ticket.generation > old_ticket.generation


def test_stale_completion_cannot_remove_a_newer_load_for_same_path():
    coordinator = FileLoadCoordinator()
    old_ticket = coordinator.begin("workspace/large.json")
    coordinator.invalidate()
    new_ticket = coordinator.begin("workspace/large.json")
    assert not coordinator.complete(old_ticket)
    assert coordinator.is_current(new_ticket)
    assert coordinator.pending_count == 1

def test_cancel_removes_only_the_requested_pending_path():
    coordinator = FileLoadCoordinator()
    first = coordinator.begin("workspace/first.json")
    second = coordinator.begin("workspace/second.json")

    assert coordinator.cancel(first.path) == first
    assert not coordinator.is_current(first)
    assert coordinator.is_current(second)
    assert coordinator.pending_count == 1


def test_stale_cancel_cannot_remove_a_newer_load_for_same_path():
    coordinator = FileLoadCoordinator()
    old_ticket = coordinator.begin("workspace/large.json")
    coordinator.cancel(old_ticket.path)
    new_ticket = coordinator.begin("workspace/large.json")

    assert coordinator.cancel(old_ticket.path) == new_ticket
    assert not coordinator.is_current(new_ticket)
    assert coordinator.pending_count == 0

