"""Tests for the UI-independent background analysis task."""

import unittest

from pylex.analysis_tasks import analyze_source


class AnalysisTaskTests(unittest.TestCase):
    def test_all_mode_returns_lexical_syntax_and_diagnostics(self):
        result = analyze_source("value = 42")
        self.assertEqual(result["mode"], "all")
        self.assertEqual(result["lexical_count"], 4)
        self.assertTrue(result["syntax"].success)
        self.assertEqual(result["diagnostics"], [])

    def test_lexical_mode_does_not_run_syntax_report(self):
        result = analyze_source("print('ok')", mode="lexical")
        self.assertIn("lexical_report", result)
        self.assertNotIn("syntax_report", result)

    def test_syntax_mode_returns_parser_diagnostic(self):
        result = analyze_source("if True print(1)", mode="syntax")
        self.assertFalse(result["syntax"].success)
        self.assertEqual(result["syntax"].error_type, "SyntaxError")

    def test_cancellation_before_parser_phase_discards_result(self):
        result = analyze_source("value = 42", mode="all", is_cancelled=lambda: True)
        self.assertIsNone(result)

    def test_invalid_mode_is_rejected(self):
        with self.assertRaises(ValueError):
            analyze_source("pass", mode="unknown")


if __name__ == "__main__":
    unittest.main()
