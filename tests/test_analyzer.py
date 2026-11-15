"""Unit tests for PyLex Studio analysis and diagnostic components."""

import tokenize
import unittest

from pygments import lex
from pygments.lexers import PythonLexer
from pygments.token import Keyword

from pylex.analyzer import (
    lexical_analysis,
    syntax_analysis,
    format_tokens,
    collect_diagnostics,
)
from pylex.editor import CodeEditor


class AnalyzerTests(unittest.TestCase):
    """Verify token spans, syntax diagnostics, and de-duplicated errors."""

    def test_keyword(self):
        self.assertIn(
            "KEYWORD",
            [token.token_type for token in lexical_analysis("if True:\n    pass")],
        )

    def test_builtin(self):
        self.assertIn(
            "BUILTIN",
            [token.token_type for token in lexical_analysis("print(len([]))")],
        )

    def test_valid_syntax(self):
        self.assertTrue(syntax_analysis("x = 3").success)

    def test_invalid_syntax(self):
        result = syntax_analysis("if True print(1)")
        self.assertFalse(result.success)
        self.assertIsNotNone(result.line)
        self.assertEqual(result.error_type, "SyntaxError")

    def test_indentation_error_keeps_exact_type(self):
        result = syntax_analysis("def calculate():\nprint(1)")
        self.assertFalse(result.success)
        self.assertEqual(result.error_type, "IndentationError")
        self.assertEqual(result.line, 2)
        self.assertIsNotNone(result.column)

    def test_multiline_string_is_one_string_token(self):
        tokens = lexical_analysis('value = """first\nsecond"""\n')
        strings = [token for token in tokens if token.token_type == "STRING"]
        self.assertEqual(len(strings), 1)
        self.assertIn("second", strings[0].value)

    def test_token_positions_include_end_span(self):
        tokens = lexical_analysis("x = 1\nprint(x)")
        print_token = next(token for token in tokens if token.value == "print")
        self.assertEqual((print_token.line, print_token.column), (2, 0))
        self.assertEqual((print_token.end_line, print_token.end_column), (2, 5))

    def test_unterminated_string_reports_token_error(self):
        with self.assertRaises((tokenize.TokenError, IndentationError, SyntaxError)):
            lexical_analysis('value = "unfinished')

    def test_collect_diagnostics_deduplicates_same_syntax_issue(self):
        diagnostics = collect_diagnostics('value = "unfinished')
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].line, 1)
        self.assertIn(diagnostics[0].error_type, {"SyntaxError", "TokenError"})

    def test_collect_diagnostics_reports_indentation_error_once(self):
        diagnostics = collect_diagnostics("def calculate():\nprint(1)")
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].error_type, "IndentationError")
        self.assertEqual(diagnostics[0].line, 2)

    def test_diagnostics_are_sorted_by_source_location(self):
        diagnostics = collect_diagnostics("def f():\nprint('x')")
        self.assertEqual(
            [(item.line, item.column) for item in diagnostics],
            sorted((item.line, item.column) for item in diagnostics),
        )

    def test_unclosed_parenthesis_prefers_one_parser_diagnostic(self):
        diagnostics = collect_diagnostics('print("Hello"')
        self.assertEqual(len(diagnostics), 1)
        self.assertEqual(diagnostics[0].error_type, "SyntaxError")
        self.assertIn("never closed", diagnostics[0].message)

    def test_error_column_converts_to_editor_coordinates(self):
        source = 'print("Hello"'
        result = syntax_analysis(source)
        diagnostic = collect_diagnostics(source)[0]
        self.assertEqual(diagnostic.column + 1, result.column)
        self.assertEqual(diagnostic.line, result.line)

    def test_pygments_highlighting_classifies_python_keyword(self):
        token_type = next(
            token_type
            for token_type, value in lex("if True:\n    pass", PythonLexer())
            if value == "if"
        )
        self.assertIn(token_type, Keyword)
        self.assertEqual(CodeEditor._tag_for_token(token_type), "py_keyword")

    def test_format_tokens_includes_span_heading(self):
        report = format_tokens(lexical_analysis("x = 1"))
        self.assertIn("TYPE", report)
        self.assertIn("LINE", report)
        self.assertIn("END", report)
        self.assertGreaterEqual(len(report.splitlines()), 3)

    def test_format_tokens_escapes_multiline_values(self):
        report = format_tokens(lexical_analysis('value = """one\ntwo"""'))
        self.assertIn(r"one\ntwo", report)


if __name__ == "__main__":
    unittest.main()
