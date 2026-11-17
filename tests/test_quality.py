"""Tests for quality-tool command construction and output parsing."""

import json
import queue
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from pylex.quality import (
    QualityPanel,
    parse_pytest_nodeids,
    parse_ruff_diagnostics,
    tool_argv,
)


class QualityToolTests(unittest.TestCase):
    def test_tool_commands_use_selected_interpreter_without_shell(self):
        self.assertEqual(
            tool_argv("C:/project/.venv/Scripts/python.exe", "ruff", ("check", ".")),
            ["C:/project/.venv/Scripts/python.exe", "-m", "ruff", "check", "."],
        )

    def test_rejects_unknown_tool_module(self):
        with self.assertRaises(ValueError):
            tool_argv("python", "unknown-tool", [])

    def test_ruff_json_diagnostics_are_normalized(self):
        payload = [
            {
                "filename": "sample.py",
                "code": "F401",
                "message": "Unused import",
                "location": {"row": 3, "column": 1},
                "end_location": {"row": 3, "column": 12},
                "fix": {"message": "Remove import"},
            }
        ]
        result = parse_ruff_diagnostics(json.dumps(payload))
        self.assertEqual(result[0]["path"], "sample.py")
        self.assertEqual(result[0]["line"], 3)
        self.assertEqual(result[0]["column"], 1)
        self.assertTrue(result[0]["fixable"])

    def test_ruff_parser_handles_invalid_output(self):
        self.assertEqual(parse_ruff_diagnostics("not json"), [])

    def test_close_cancels_quality_worker_that_has_not_published_process_yet(self):
        entered = threading.Event()
        release = threading.Event()
        process = SimpleNamespace(
            returncode=0,
            communicate=lambda input=None: ("", ""),
        )
        cancelled = []

        def delayed_popen(*_args, **_kwargs):
            entered.set()
            release.wait(3)
            return process

        panel = SimpleNamespace(
            _events=queue.Queue(),
            _worker=None,
            _process=None,
            _process_lock=threading.Lock(),
            _cancel_requested=threading.Event(),
            _closed=False,
            _poll_id="poll-id",
            _busy=False,
            _set_status=lambda _message: None,
            _clear_output=lambda: None,
            after_cancel=lambda job: cancelled.append(job),
        )
        with (
            patch("pylex.quality.subprocess.Popen", side_effect=delayed_popen),
            patch("pylex.quality.terminate_process_tree") as terminate,
        ):
            self.assertTrue(QualityPanel._start(panel, ["python"], Path.cwd(), {}))
            self.assertTrue(entered.wait(2))
            QualityPanel.close(panel)
            release.set()
            panel._worker.join(3)

        self.assertFalse(panel._worker.is_alive())
        self.assertEqual(cancelled, ["poll-id"])
        terminate.assert_any_call(process)
        self.assertTrue(panel._cancel_requested.is_set())

    def test_pytest_collection_parser_keeps_node_ids_and_deduplicates(self):
        output = (
            "tests/test_demo.py::test_one\n"
            "tests/test_demo.py::Suite::test_two\n"
            "tests/test_demo.py::test_one\n"
            "tests/test_demo.py::test_parameterized[value with spaces]\n"
            "\n4 tests collected in 0.02s\n"
        )
        self.assertEqual(
            parse_pytest_nodeids(output),
            [
                "tests/test_demo.py::test_one",
                "tests/test_demo.py::Suite::test_two",
                "tests/test_demo.py::test_parameterized[value with spaces]",
            ],
        )


if __name__ == "__main__":
    unittest.main()
