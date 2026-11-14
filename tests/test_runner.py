"""Tests for asynchronous Python execution."""
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

    def test_timeout_terminates_process(self):
        result = start_source("import time\ntime.sleep(3)", timeout=0.15).wait(5)
        self.assertEqual(result.status, "timed_out")
        self.assertIn("timed out", result.stderr.lower())

    def test_stop_terminates_running_process(self):
        handle = start_source("import time\nprint('ready', flush=True)\ntime.sleep(10)")
        deadline = time.monotonic() + 2
        while handle.process.poll() is None and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertTrue(handle.stop())
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
