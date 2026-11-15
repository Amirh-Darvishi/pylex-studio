"""Tests for streaming, cancellable Python process execution."""
import os
import subprocess
import tempfile
from pathlib import Path
import sys
import time
import unittest

from pylex.runner import run_source, start_source


class RunnerTests(unittest.TestCase):
    def test_captures_stdout_stderr_and_exit_code(self):
        result = start_source(
            "import sys\nprint('hello')\nprint('problem', file=sys.stderr)\nsys.exit(3)"
        ).wait(5)
        self.assertEqual(result.stdout.strip(), "hello")
        self.assertIn("problem", result.stderr)
        self.assertEqual(result.exit_code, 3)
        self.assertEqual(result.status, "finished")

    def test_streams_output_before_process_finishes(self):
        handle = start_source(
            "import time\nprint('first', flush=True)\ntime.sleep(0.5)\nprint('second')",
            timeout=3,
        )
        deadline = time.monotonic() + 2
        events = []
        while time.monotonic() < deadline and not any("first" in item[1] for item in events):
            events.extend(handle.read_available())
            time.sleep(0.02)
        self.assertTrue(any(channel == "stdout" and "first" in value
                            for channel, value in events))
        self.assertFalse(handle.done)
        self.assertEqual(handle.wait(5).status, "finished")

    def test_interactive_stdin_is_forwarded_to_running_program(self):
        handle = start_source(
            "name = input('Name: ')\nprint('hello', name)",
            timeout=5,
        )
        deadline = time.monotonic() + 2
        output = []
        while time.monotonic() < deadline:
            output.extend(handle.read_available())
            if any("Name:" in chunk for channel, chunk in output if channel == "stdout"):
                break
            time.sleep(0.02)
        self.assertTrue(handle.send_input("PyLex"))
        result = handle.wait(5)
        self.assertEqual(result.status, "finished")
        self.assertIn("hello PyLex", result.stdout)

    def test_saved_file_accepts_interactive_stdin(self):
        with tempfile.TemporaryDirectory() as folder:
            script = Path(folder) / "ask.py"
            script.write_text("answer = input('Answer: ')\nprint(answer.upper())\n", encoding="utf-8")
            handle = start_file(script, timeout=5)
            self.assertTrue(handle.send_input("pylex"))
            result = handle.wait(5)
            self.assertEqual(result.status, "finished")
            self.assertIn("PYLEX", result.stdout)

    def test_missing_library_is_captured_as_runtime_error(self):
        result = start_source("import pylex_test_missing_package_abc123").wait(5)
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("ModuleNotFoundError", result.stderr)
        self.assertIn("pylex_test_missing_package_abc123", result.stderr)

    def test_unlimited_timeout_allows_longer_execution(self):
        result = start_source(
            "import time\nprint('started', flush=True)\ntime.sleep(0.25)\nprint('finished')",
            timeout=None,
        ).wait(5)
        self.assertEqual(result.status, "finished")
        self.assertIn("finished", result.stdout)

    def test_timeout_terminates_process(self):
        result = start_source("import time\ntime.sleep(3)", timeout=0.15).wait(5)
        self.assertEqual(result.status, "timed_out")
        self.assertIn("timed out", result.stderr.lower())

    def test_force_stop_works_with_unlimited_timeout(self):
        handle = start_source(
            "import time\nprint('ready', flush=True)\ntime.sleep(10)",
            timeout=None,
        )
        deadline = time.monotonic() + 2
        while handle.process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(handle.force_stop())
        result = handle.wait(5)
        self.assertEqual(result.status, "stopped")

    def test_force_stop_terminates_running_process(self):
        handle = start_source("import time\nprint('ready', flush=True)\ntime.sleep(10)")
        deadline = time.monotonic() + 2
        while handle.process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(handle.force_stop())
        result = handle.wait(5)
        self.assertEqual(result.status, "stopped")

    def test_legacy_run_source_api_is_preserved(self):
        stdout, stderr, exit_code = run_source("print('legacy')")
        self.assertEqual(stdout.strip(), "legacy")
        self.assertEqual(stderr, "")
        self.assertEqual(exit_code, 0)

    def test_temporary_script_is_removed(self):
        handle = start_source("print('cleanup')")
        script_path = handle.script_path
        result = handle.wait(5)
        self.assertEqual(result.status, "finished")
        self.assertFalse(script_path.exists())


if __name__ == "__main__":
    unittest.main()
