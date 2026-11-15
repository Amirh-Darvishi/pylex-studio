"""Tests for the shell-free Git integration service."""
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pylex.git import GitError, GitService, GitChange


class GitServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        subprocess.run(["git", "init", "-q"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.name", "PyLex Tests"], cwd=self.root, check=True)
        subprocess.run(["git", "config", "user.email", "tests@example.invalid"], cwd=self.root, check=True)
        (self.root / "tracked.txt").write_text("initial\n", encoding="utf-8")
        subprocess.run(["git", "add", "tracked.txt"], cwd=self.root, check=True)
        subprocess.run(["git", "commit", "-qm", "initial"], cwd=self.root, check=True)
        self.git = GitService(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_status_reports_branch_and_unstaged_file(self):
        (self.root / "tracked.txt").write_text("changed\n", encoding="utf-8")
        status = self.git.status()
        self.assertTrue(status.branch)
        self.assertEqual(len(status.changes), 1)
        self.assertEqual(status.changes[0].path, "tracked.txt")
        self.assertTrue(status.changes[0].unstaged)

    def test_stage_and_unstage(self):
        (self.root / "tracked.txt").write_text("changed\n", encoding="utf-8")
        self.git.stage("tracked.txt")
        self.assertTrue(self.git.status().changes[0].staged)
        self.git.unstage("tracked.txt")
        self.assertFalse(self.git.status().changes[0].staged)

    def test_diff_staged_and_commit(self):
        (self.root / "tracked.txt").write_text("changed\n", encoding="utf-8")
        self.git.stage("tracked.txt")
        self.assertIn("+changed", self.git.diff(staged=True))
        self.git.commit("update tracked file")
        self.assertTrue(self.git.status().clean)
        self.assertEqual(self.git.log(1)[0].subject, "update tracked file")

    def test_create_and_switch_branch(self):
        original = self.git.status().branch
        self.git.create_branch("feature/git-ui")
        self.assertEqual(self.git.status().branch, "feature/git-ui")
        branches = self.git.branches()
        self.assertIn(original, [item["name"] for item in branches])
        self.assertTrue(any(item["current"] and item["name"] == "feature/git-ui" for item in branches))
        self.git.switch_branch(original)

    def test_stage_all_and_unstage_all(self):
        (self.root / "tracked.txt").write_text("changed\\n", encoding="utf-8")
        (self.root / "new.txt").write_text("new\\n", encoding="utf-8")
        self.git.stage_all()
        self.assertTrue(all(item.staged for item in self.git.status().changes))
        self.git.unstage_all()
        self.assertFalse(any(item.staged for item in self.git.status().changes))

    def test_unstage_rejects_untracked_file(self):
        (self.root / "new.txt").write_text("new\\n", encoding="utf-8")
        with self.assertRaisesRegex(GitError, "Untracked"):
            self.git.unstage("new.txt")

    def test_reject_path_outside_workspace(self):
        with self.assertRaises(GitError):
            self.git.stage(self.root.parent / "outside.txt")

    def test_reject_empty_commit_message(self):
        with self.assertRaises(GitError):
            self.git.commit("  ")

    def test_non_repository_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(GitError):
                GitService(folder)

    def test_missing_git_executable_has_actionable_error(self):
        with patch("pylex.git.subprocess.run", side_effect=FileNotFoundError):
            with self.assertRaisesRegex(GitError, "Git executable"):
                GitService(self.root)


if __name__ == "__main__":
    unittest.main()
