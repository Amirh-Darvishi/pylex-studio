"""Unit tests for PyLex Studio analysis components."""
import tokenize
import unittest

from pygments import lex
from pygments.lexers import PythonLexer
from pygments.token import Keyword

from pylex.analyzer import lexical_analysis, syntax_analysis, format_tokens
from pylex.editor import CodeEditor


class AnalyzerTests(unittest.TestCase):
    """Verify lexical tokenization and syntax diagnostics."""

    def test_keyword(self):
        self.assertIn("KEYWORD", [token.token_type for token in lexical_analysis("if True:\n    pass")])

    def test_builtin(self):
        self.assertIn("BUILTIN", [token.token_type for token in lexical_analysis("print(len([]))")])

    def test_valid_syntax(self):
        self.assertTrue(syntax_analysis("x = 3").success)

    def test_invalid_syntax(self):
        result = syntax_analysis("if True print(1)")
        self.assertFalse(result.success)
        self.assertIsNotNone(result.line)

    def test_multiline_string_is_one_string_token(self):
        tokens = lexical_analysis('value = """first\nsecond"""\n')
        strings = [token for token in tokens if token.token_type == "STRING"]
        self.assertEqual(len(strings), 1)
        self.assertIn("second", strings[0].value)

    def test_token_positions(self):
        tokens = lexical_analysis("x = 1\nprint(x)")
        print_token = next(token for token in tokens if token.value == "print")
        self.assertEqual((print_token.line, print_token.column), (2, 0))

    def test_unterminated_string_reports_token_error(self):
        with self.assertRaises((tokenize.TokenError, IndentationError, SyntaxError)):
            lexical_analysis('value = "unfinished')

    def test_pygments_highlighting_classifies_python_keyword(self):
        token_type = next(token_type for token_type, value in lex("if True:\n    pass", PythonLexer())
                          if value == "if")
        self.assertIn(token_type, Keyword)
        self.assertEqual(CodeEditor._tag_for_token(token_type), "py_keyword")

    def test_format_tokens_is_english(self):
        report = format_tokens(lexical_analysis("x = 1"))
        self.assertIn("TYPE", report)
        self.assertIn("LINE", report)


if __name__ == "__main__":
    unittest.main()
