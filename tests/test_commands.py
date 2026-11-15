"""Tests for the UI-independent application command registry."""

import unittest

from pylex.commands import Command, CommandRegistry


class CommandRegistryTests(unittest.TestCase):
    def setUp(self):
        self.calls = []
        self.registry = CommandRegistry(
            [
                Command("file.save", "Save File", "Ctrl+S", lambda: self.calls.append("save")),
                Command("run.active", "Run Current File", "F5", lambda: self.calls.append("run")),
                Command("view.theme", "Toggle Theme", "", lambda: self.calls.append("theme")),
            ]
        )

    def test_search_matches_labels_ids_and_shortcuts(self):
        self.assertEqual(
            [item.command_id for item in self.registry.search("save")],
            ["file.save"],
        )
        self.assertEqual(
            [item.command_id for item in self.registry.search("run.active")],
            ["run.active"],
        )
        self.assertEqual(
            [item.command_id for item in self.registry.search("F5")],
            ["run.active"],
        )

    def test_search_is_case_insensitive_and_empty_query_returns_all(self):
        self.assertEqual(len(self.registry.search("TOGGLE")), 1)
        self.assertEqual(len(self.registry.search()), 3)

    def test_register_rejects_duplicate_and_empty_ids(self):
        command = Command("file.save", "Save Again", "", lambda: None)
        with self.assertRaises(ValueError):
            self.registry.register(command)
        with self.assertRaises(ValueError):
            self.registry.register(Command(" ", "Invalid", "", lambda: None))

    def test_execute_runs_known_command_once(self):
        self.assertTrue(self.registry.execute("file.save"))
        self.assertEqual(self.calls, ["save"])

    def test_execute_unknown_command_is_safe(self):
        self.assertFalse(self.registry.execute("missing"))
        self.assertEqual(self.calls, [])

    def test_get_and_all_preserve_registration_order(self):
        self.assertEqual(self.registry.get("run.active").label, "Run Current File")
        self.assertEqual(
            [item.command_id for item in self.registry.all()],
            ["file.save", "run.active", "view.theme"],
        )


if __name__ == "__main__":
    unittest.main()
