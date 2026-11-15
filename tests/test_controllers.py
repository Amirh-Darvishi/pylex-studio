"""Unit tests for UI-independent application controllers."""

import tempfile
import unittest
from pathlib import Path

from pylex.controllers import (
    DebuggerController,
    DocumentController,
    ExecutionController,
    WorkspaceController,
)
from pylex.core.project import Project


class FakeHandle:
    def __init__(self, done=False):
        self.done = done
        self.stopped = False
        self.closed = False

    def force_stop(self):
        self.stopped = True

    def stop(self):
        self.stopped = True

    def close(self):
        self.closed = True


class FakeService:
    def __init__(self):
        self.execution = FakeHandle()
        self.debugger = FakeHandle()

    def start_document(self, *args, **kwargs):
        return self.execution

    def start_debugger_document(self, *args, **kwargs):
        return self.debugger


class WorkspaceControllerTests(unittest.TestCase):
    def test_open_close_and_restore_workspace(self):
        with tempfile.TemporaryDirectory() as folder:
            controller = WorkspaceController()
            project = controller.open(folder)
            self.assertEqual(project.root, Path(folder).resolve())
            self.assertIs(controller.project, project)
            self.assertIs(controller.close(), project)
            self.assertIsNone(controller.project)
            self.assertIsNone(controller.restore(str(Path(folder) / "missing")))

    def test_project_context_for_external_file(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            workspace = root / "workspace"
            external = root / "outside.py"
            workspace.mkdir()
            external.write_text("print('ok')", encoding="utf-8")
            controller = WorkspaceController(Project.open(workspace))
            context = controller.project_for_file(external)
            self.assertEqual(context.root, root.resolve())


class DocumentControllerTests(unittest.TestCase):
    def test_register_activate_dirty_find_and_remove(self):
        first, second = object(), object()
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "main.py"
            path.write_text("print('ok')", encoding="utf-8")
            documents = DocumentController()
            documents.register(first, {"path": path, "dirty": False})
            documents.register(second, {"path": None, "dirty": False})
            self.assertIs(documents.active_editor, second)
            self.assertIs(documents.get(), documents.get(second))
            self.assertIs(documents.find_path(path), first)
            self.assertTrue(documents.mark_dirty(first))
            self.assertTrue(documents.get(first)["dirty"])
            documents.activate(first)
            self.assertIs(documents.active_editor, first)
            self.assertIsNotNone(documents.remove(first))
            self.assertIs(documents.active_editor, second)

    def test_duplicate_registration_and_unknown_activation_are_rejected(self):
        editor = object()
        controller = DocumentController()
        controller.register(editor, {"path": None, "dirty": False})
        with self.assertRaises(ValueError):
            controller.register(editor, {})
        with self.assertRaises(KeyError):
            controller.activate(object())


class ExecutionControllerTests(unittest.TestCase):
    def test_start_stop_and_finish(self):
        service = FakeService()
        controller = ExecutionController(service)
        handle = controller.start_document("print('ok')")
        self.assertIs(controller.handle, handle)
        self.assertTrue(controller.running)
        with self.assertRaises(RuntimeError):
            controller.start_document("print('another')")
        self.assertTrue(controller.stop())
        self.assertTrue(handle.stopped)
        self.assertTrue(controller.finish(handle))
        self.assertIsNone(controller.handle)
        self.assertFalse(controller.running)

    def test_finish_ignores_stale_handle(self):
        controller = ExecutionController(FakeService())
        current = controller.start_document("pass")
        self.assertFalse(controller.finish(FakeHandle()))
        self.assertIs(controller.handle, current)


class DebuggerControllerTests(unittest.TestCase):
    def test_start_stop_and_finish(self):
        service = FakeService()
        controller = DebuggerController(service)
        session = controller.start_document("print('debug')")
        self.assertIs(controller.session, session)
        self.assertTrue(controller.running)
        with self.assertRaises(RuntimeError):
            controller.start_document("pass")
        self.assertTrue(controller.stop())
        self.assertTrue(session.stopped)
        self.assertTrue(controller.finish(session=session))
        self.assertTrue(session.closed)
        self.assertIsNone(controller.session)

    def test_start_closes_completed_previous_session(self):
        service = FakeService()
        controller = DebuggerController(service)
        previous = FakeHandle(done=True)
        controller.session = previous
        current = controller.start_document("pass")
        self.assertTrue(previous.closed)
        self.assertIs(controller.session, current)


if __name__ == "__main__":
    unittest.main()
