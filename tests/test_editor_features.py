"""Tests for Smart Editor's pure text helpers."""

import unittest

from pylex.editor_features import (
    find_matching_bracket,
    indentation_for_newline,
    smart_backspace_prefix,
    toggle_comment_block,
)


class SmartEditorFeatureTests(unittest.TestCase):
    def test_indents_after_suite_colon(self):
        self.assertEqual(indentation_for_newline("    if ready:"), "        ")

    def test_does_not_indent_after_colon_inside_string_or_comment(self):
        self.assertEqual(indentation_for_newline('    message = "value:"'), "    ")
        self.assertEqual(indentation_for_newline("    value = 1  #:"), "    ")

    def test_smart_backspace_moves_to_previous_indent_stop(self):
        self.assertEqual(smart_backspace_prefix("        "), "    ")
        self.assertEqual(smart_backspace_prefix("   "), "")
        self.assertIsNone(smart_backspace_prefix("  x"))

    def test_comment_toggle_preserves_indentation_and_line_endings(self):
        source = "if ready:\r\n    run()\r\n"
        commented = toggle_comment_block(source)
        self.assertEqual(commented, "# if ready:\r\n    # run()\r\n")
        self.assertEqual(toggle_comment_block(commented), source)

    def test_matching_brackets_ignores_strings_and_comments(self):
        source = 'call(")", [1, {"x": 2}]) # ]\n'
        opening = source.index("[")
        self.assertEqual(
            find_matching_bracket(source, opening),
            (opening, source.index("]", opening)),
        )

    def test_matching_bracket_scan_can_be_cancelled(self):
        source = "outer(inner[0])"
        self.assertIsNone(
            find_matching_bracket(source, source.index("("), lambda: True)
        )

    def test_matching_brackets_detects_nested_pair(self):
        source = "outer(inner[0])"
        opening = source.index("(")
        self.assertEqual(
            find_matching_bracket(source, opening),
            (opening, source.rindex(")")),
        )


    def test_matching_brackets_uses_python_tokens_across_multiple_lines(self):
        source = "result = call(\\n    values[0],\\n    {\\\"key\\\": 1},\\n)\\n"
        opening = source.index("(")
        self.assertEqual(
            find_matching_bracket(source, opening),
            (opening, source.index(")", opening)),
        )

    def test_matching_brackets_preserves_f_string_expression_support(self):
        source = 'message = f"result: {call(value)}"'
        opening = source.index("(")
        self.assertEqual(
            find_matching_bracket(source, opening),
            (opening, source.index(")", opening)),
        )

    def test_matching_bracket_falls_back_for_incomplete_source(self):
        source = "call(value"
        self.assertIsNone(find_matching_bracket(source, source.index("(")))


if __name__ == "__main__":
    unittest.main()
