"""Tests for the pdb-backed interactive debugger."""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

from pylex.debugger import DebugSession


class DebuggerTests(unittest.TestCase):
    def test_debugger_finishes_automatically_after_successful_run(self):
        session = DebugSession.start("print('debugger-ok')\n")
        script_path = session.script_path
        output = ""
        try:
            self.assertTrue(session.continue_execution())
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not session.done:
                output += session.read_available()
                time.sleep(0.02)
            session.wait(timeout=1)
            session._reader.join(timeout=2)
            output += session.read_available()
            self.assertTrue(session.done)
            self.assertEqual(session.completion_status, "finished")
            self.assertIn("debugger-ok", output)
        finally:
            session.close()
        self.assertFalse(script_path.exists())

    def test_program_output_cannot_fake_the_pdb_completion_marker(self):
        session = DebugSession.start(
            "import time\n"
            "print('The program finished and will be restarted', flush=True)\n"
            "time.sleep(0.3)\n"
            "print('still-running')\n"
        )
        output = ""
        try:
            self.assertTrue(session.continue_execution())
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not session.done:
                output += session.read_available()
                time.sleep(0.02)
            session.wait(timeout=1)
            session._reader.join(timeout=2)
            output += session.read_available()
            self.assertTrue(session.done)
            self.assertEqual(session.completion_status, "finished")
            self.assertIn("still-running", output)
        finally:
            session.close()

    def test_debugger_forwards_program_input_and_streams_prompt(self):
        session = DebugSession.start("name = input('Name: ')\nprint('Hello', name)\n")
        output = ""
        try:
            self.assertTrue(session.continue_execution())
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and "Name: " not in output:
                output += session.read_available()
                time.sleep(0.02)
            self.assertIn("Name: ", output)
            self.assertTrue(session.send_input("Ada"))
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not session.done:
                output += session.read_available()
                time.sleep(0.02)
            session.wait(timeout=1)
            session._reader.join(timeout=2)
            output += session.read_available()
            self.assertTrue(session.done)
            self.assertEqual(session.completion_status, "finished")
            self.assertIn("Hello Ada", output)
        finally:
            session.close()

    def test_debugger_reports_uncaught_exception_and_finishes(self):
        session = DebugSession.start("raise RuntimeError('debug-boom')\n")
        output = ""
        try:
            self.assertTrue(session.continue_execution())
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and not session.done:
                output += session.read_available()
                time.sleep(0.02)
            session.wait(timeout=1)
            session._reader.join(timeout=2)
            output += session.read_available()
            self.assertTrue(session.done)
            self.assertEqual(session.completion_status, "error")
            self.assertIn("RuntimeError: debug-boom", output)
        finally:
            session.close()

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

    @unittest.skipIf(os.name == "nt", "POSIX process-group semantics")
    def test_close_stops_child_holding_debugger_output_pipe(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "debugger-child-survived"
            child = (
                "import time; from pathlib import Path; "
                "time.sleep(2); Path(" + repr(str(marker)) + ").write_text('alive')"
            )
            source = (
                "import subprocess, sys\n"
                "subprocess.Popen([sys.executable, '-c', " + repr(child) + "])\n"
            )
            session = DebugSession.start(source, cwd=directory)
            try:
                self.assertTrue(session.continue_execution())
                time.sleep(0.3)
            finally:
                session.close()
            time.sleep(2.2)
            self.assertFalse(marker.exists())

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
        session = DebugSession.start("value = 1\n")
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
        session = DebugSession.start("value = 1\n")
        try:
            for operation in (
                lambda: session.set_breakpoint(0),
                lambda: session.set_temporary_breakpoint(-1),
                lambda: session.set_conditional_breakpoint(1, "value\nquit"),
                lambda: session.evaluate("value\nquit"),
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
