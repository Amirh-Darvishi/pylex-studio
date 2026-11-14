"""Tests for the pdb-backed interactive debugger."""
import time
import unittest

from pylex.debugger import DebugSession


class DebuggerTests(unittest.TestCase):
    def test_debugger_runs_source_and_captures_output(self):
        session = DebugSession.start("print('debugger-ok')\n")
        script_path = session.script_path
        try:
            self.assertTrue(session.continue_execution())
            deadline = time.monotonic() + 5
            output = ""
            while time.monotonic() < deadline:
                output += session.read_available()
                if "debugger-ok" in output:
                    break
                if session.done:
                    break
                time.sleep(0.02)
            self.assertIn("debugger-ok", output)
            # pdb remains interactive at its post-run prompt until quit.
            self.assertTrue(session.command("q"))
            session.wait(timeout=5)
            session._reader.join(timeout=2)
            output += session.read_available()
        finally:
            session.close()
        self.assertFalse(script_path.exists())

    def test_breakpoint_and_step_commands_are_available(self):
        session = DebugSession.start("value = 1\nvalue += 1\nprint(value)\n")
        try:
            self.assertTrue(session.set_breakpoint(2))
            self.assertTrue(session.continue_execution())
            deadline = time.monotonic() + 5
            output = ""
            while time.monotonic() < deadline:
                output += session.read_available()
                if "Breakpoint" in output or "(Pdb)" in output:
                    break
                if session.done:
                    break
                time.sleep(0.02)
            self.assertTrue(session.step())
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
