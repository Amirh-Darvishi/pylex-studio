"""Tests for quality-tool command construction and output parsing."""

import json
import unittest

from pylex.quality import parse_pytest_nodeids, parse_ruff_diagnostics, tool_argv


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

    def test_pytest_collection_parser_keeps_node_ids_and_deduplicates(self):
        output = (
            "tests/test_demo.py::test_one\\n"
            "tests/test_demo.py::Suite::test_two\\n"
            "tests/test_demo.py::test_one\\n"
            "tests/test_demo.py::test_parameterized[value with spaces]\\n"
            "\\n4 tests collected in 0.02s\\n"
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
