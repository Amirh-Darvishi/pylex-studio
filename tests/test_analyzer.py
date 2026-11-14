"""آزمون‌های واحد تحلیل‌گر."""
import unittest
from pylex.analyzer import lexical_analysis, syntax_analysis

class AnalyzerTests(unittest.TestCase):
    """رفتارهای پایه تحلیل لغوی و نحوی را می‌آزماید."""
    def test_keyword(self):
        self.assertIn("KEYWORD", [t.token_type for t in lexical_analysis("if True:\n pass")])
    def test_valid_syntax(self):
        self.assertTrue(syntax_analysis("x = 3").success)
    def test_invalid_syntax(self):
        self.assertFalse(syntax_analysis("if True print(1)").success)

if __name__ == "__main__":
    unittest.main()
