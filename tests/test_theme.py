"""Tests for the centralized application theme definitions."""

import unittest

from pylex.ui.theme import THEMES, get_theme


class ThemeDefinitionTests(unittest.TestCase):
    def test_dark_theme_is_the_default_and_uses_darkly(self):
        self.assertIs(get_theme("dark"), THEMES["dark"])
        self.assertEqual(get_theme(None)["bootstrap_theme"], "darkly")

    def test_light_theme_uses_flatly(self):
        self.assertEqual(get_theme("light")["bootstrap_theme"], "flatly")

    def test_both_themes_define_required_classic_widget_colors(self):
        required = {
            "window_bg", "editor_bg", "editor_fg", "selection_bg",
            "menu_bg", "menu_fg", "accent", "danger", "surface",
            "violet", "success", "warning", "panel_bg", "border",
            "current_line", "error_line", "bracket_bg",
            "file_python", "file_web", "file_markup", "file_style", "file_data",
        }
        for theme in THEMES.values():
            self.assertTrue(required.issubset(theme))


if __name__ == "__main__":
    unittest.main()
