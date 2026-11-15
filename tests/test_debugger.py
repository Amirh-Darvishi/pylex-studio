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

    def test_force_stop_closes_unresponsive_debuggee(self):
        session = DebugSession.start("import time\ntime.sleep(30)\n")
        try:
            self.assertTrue(session.continue_execution())
            time.sleep(0.1)
            self.assertTrue(session.stop())
            session.wait(timeout=5)
            self.assertTrue(session.done)
        finally:
            session.close()

    def test_breakpoint_and_step_commands_are_available(self):
        session = DebugSession.start("value = 1\nvalue += 1\nprint(value)\n")
        try:
            self.assertTrue(session.set_breakpoint(2))
            self.assertTrue(session.continue_execution())
            deadline = time.monotonic() + 5
            output = ""
            while time.monotonic() < deadline:
                output += session.read_available()
                if "Breakpoint 1" in output or "(2)<module>()" in output:
                    break
                if session.done:
                    break
                time.sleep(0.02)
            self.assertTrue(session.step())
        finally:
            session.close()


    def test_advanced_commands_validate_arguments(self):
        session = DebugSession.start("value = 1\\n")
        try:
            self.assertTrue(session.set_conditional_breakpoint(1, "value == 1"))
            self.assertTrue(session.set_temporary_breakpoint(1))
            self.assertTrue(session.until(1))
            self.assertTrue(session.return_from_frame())
            self.assertTrue(session.jump(1))
            self.assertTrue(session.show_arguments())
            self.assertTrue(session.pretty_print("value"))
            self.assertTrue(session.enable_breakpoint(1))
            self.assertTrue(session.disable_breakpoint(1))
            self.assertTrue(session.ignore_breakpoint(1, 2))
            self.assertTrue(session.clear_all_breakpoints())
        finally:
            session.close()

    def test_advanced_commands_reject_invalid_input(self):
        session = DebugSession.start("value = 1\\n")
        try:
            for operation in (
                lambda: session.set_breakpoint(0),
                lambda: session.set_temporary_breakpoint(-1),
                lambda: session.set_conditional_breakpoint(1, "value\\nquit"),
                lambda: session.evaluate("value\\nquit"),
                lambda: session.pretty_print("  "),
                lambda: session.jump("not-a-line"),
                lambda: session.ignore_breakpoint(1, 0),
            ):
                with self.assertRaises(ValueError):
                    operation()
        finally:
            session.close()


if __name__ == "__main__":
    unittest.main()
