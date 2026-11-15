"""Safe, shell-free Git operations for a PyLex Studio workspace."""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path


class GitError(RuntimeError):
    """Raised when Git is unavailable, a repository is invalid, or a command fails."""


@dataclass(frozen=True)
class GitChange:
    """One path reported by Git status."""
    path: str
    index_status: str
    worktree_status: str

    @property
    def status(self):
        return self.index_status + self.worktree_status

    @property
    def staged(self):
        return self.index_status != " " and self.index_status != "?"

    @property
    def unstaged(self):
        return self.worktree_status != " " or self.status == "??"


@dataclass(frozen=True)
class GitStatus:
    """Snapshot of the current branch and working-tree state."""
    branch: str
    upstream: str | None
    ahead: int
    behind: int
    changes: tuple[GitChange, ...]

    @property
    def clean(self):
        return not self.changes


@dataclass(frozen=True)
class GitCommit:
    """Compact commit-history entry."""
    short_hash: str
    full_hash: str
    author: str
    date: str
    subject: str


class GitService:
    """Run a constrained set of Git commands inside one workspace.

    Commands are always passed as argument lists (never through a shell), run
    from the repository root, and disable interactive credential prompts.
    """

    def __init__(self, root, timeout=30):
        self.root = Path(root).expanduser().resolve()
        self.timeout = max(1, int(timeout))
        if not self.root.is_dir():
            raise GitError(f"Workspace directory does not exist: {self.root}")
        probe = self._run("rev-parse", "--show-toplevel", check=False)
        if probe.returncode:
            raise GitError("The opened workspace is not inside a Git repository.")
        actual = Path(probe.stdout.strip()).resolve()
        self.root = actual

    def _run(self, *args, check=True, timeout=None):
        env = dict(os.environ)
        env.update({
            "GIT_TERMINAL_PROMPT": "0",
            "GCM_INTERACTIVE": "Never",
            "GIT_OPTIONAL_LOCKS": "0" if args[:2] == ("status", "--porcelain=v1") else "1",
        })
        try:
            result = subprocess.run(
                ["git", *map(str, args)],
                cwd=str(self.root),
                env=env,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
                timeout=self.timeout if timeout is None else timeout,
                check=False,
            )
        except FileNotFoundError as exc:
            raise GitError("Git executable was not found. Install Git and ensure it is on PATH.") from exc
        except subprocess.TimeoutExpired as exc:
            raise GitError(f"Git command timed out after {exc.timeout} seconds.") from exc
        if check and result.returncode:
            detail = result.stderr.strip() or result.stdout.strip() or "Unknown Git error."
            raise GitError(detail)
        return result

    def _pathspec(self, path):
        candidate = Path(path)
        if candidate.is_absolute():
            resolved = candidate.resolve()
        else:
            resolved = (self.root / candidate).resolve()
        try:
            relative = resolved.relative_to(self.root)
        except ValueError as exc:
            raise GitError("Git operations are restricted to paths inside the workspace.") from exc
        if str(relative) in {"", "."}:
            raise GitError("A file path is required for this operation.")
        return relative.as_posix()

    def status(self):
        result = self._run("status", "--porcelain=v1", "--branch", "--untracked-files=all")
        lines = result.stdout.splitlines()
        branch, upstream, ahead, behind = "HEAD", None, 0, 0
        changes = []
        for line in lines:
            if line.startswith("## "):
                header = line[3:]
                if "..." in header:
                    branch, tracking = header.split("...", 1)
                    if " [" in tracking:
                        upstream, counts = tracking.split(" [", 1)
                        counts = counts.rstrip("]")
                        for item in counts.split(", "):
                            if item.startswith("ahead "):
                                ahead = int(item[6:])
                            elif item.startswith("behind "):
                                behind = int(item[7:])
                    else:
                        upstream = tracking
                else:
                    branch = header.split(" ", 1)[0]
                continue
            if len(line) < 3:
                continue
            code, path = line[:2], line[3:]
            if " -> " in path:
                path = path.rsplit(" -> ", 1)[1]
            changes.append(GitChange(path, code[0], code[1]))
        return GitStatus(branch, upstream, ahead, behind, tuple(changes))

    def diff(self, path=None, staged=False):
        args = ["diff", "--no-ext-diff", "--no-color", "--no-renames"]
        if staged:
            args.append("--cached")
        if path is not None:
            args.extend(["--", self._pathspec(path)])
        return self._run(*args).stdout

    def stage(self, path):
        return self._run("add", "--", self._pathspec(path)).stdout

    def stage_all(self):
        return self._run("add", "-A").stdout

    def unstage(self, path):
        return self._run("reset", "-q", "HEAD", "--", self._pathspec(path)).stdout

    def unstage_all(self):
        return self._run("reset", "-q", "HEAD").stdout

    def discard(self, path):
        relative = self._pathspec(path)
        state = next((item for item in self.status().changes if item.path == relative), None)
        if state is None:
            return ""
        if state.index_status != " ":
            raise GitError("This file has staged changes. Unstage it before discarding worktree edits.")
        if state.status == "??":
            target = (self.root / relative).resolve()
            if target.is_dir() and not target.is_symlink():
                raise GitError("Discarding untracked directories is disabled for safety.")
            target.unlink(missing_ok=True)
            return ""
        return self._run("restore", "--worktree", "--", relative).stdout

    def commit(self, message):
        message = str(message).strip()
        if not message:
            raise GitError("Enter a commit message before committing.")
        self._run("diff", "--cached", "--quiet", check=False)
        if self._run("diff", "--cached", "--name-only").stdout.strip() == "":
            raise GitError("There are no staged changes to commit.")
        return self._run("commit", "-m", message).stdout

    def branches(self):
        output = self._run("branch", "--format=%(HEAD)%00%(refname:short)%00%(upstream:short)").stdout
        result = []
        for line in output.splitlines():
            parts = line.split("\x00")
            if len(parts) >= 2:
                result.append({"current": parts[0] == "*", "name": parts[1],
                               "upstream": parts[2] if len(parts) > 2 else ""})
        return result

    @staticmethod
    def _validate_branch_name(name):
        value = str(name).strip()
        if not value or value.startswith("-"):
            raise GitError("Enter a valid branch name.")
        result = subprocess.run(
            ["git", "check-ref-format", "--branch", value],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, text=True, shell=False, check=False,
        )
        if result.returncode:
            raise GitError("Git rejected this branch name.")
        return value

    def create_branch(self, name, switch=True):
        value = self._validate_branch_name(name)
        args = ["switch"]
        if switch:
            args.extend(["-c", value])
        else:
            args.extend(["--create", value, "--no-guess"])
        return self._run(*args).stdout

    def switch_branch(self, name):
        value = self._validate_branch_name(name)
        return self._run("switch", "--", value).stdout

    def log(self, limit=100):
        count = max(1, min(500, int(limit)))
        fmt = "%H%x1f%h%x1f%an%x1f%ad%x1f%s"
        output = self._run("log", f"-{count}", f"--pretty=format:{fmt}", "--date=short").stdout
        entries = []
        for line in output.splitlines():
            parts = line.split("\x1f", 4)
            if len(parts) == 5:
                entries.append(GitCommit(*parts))
        return entries

    def remotes(self):
        output = self._run("remote", "-v").stdout
        found = []
        for line in output.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[2] == "(fetch)" and parts[0] not in found:
                found.append(parts[0])
        return found

    def fetch(self, remote="origin"):
        return self._run("fetch", "--prune", remote, timeout=max(self.timeout, 120)).stdout

    def pull(self, remote="origin"):
        return self._run("pull", "--ff-only", remote, timeout=max(self.timeout, 120)).stdout

    def push(self, remote="origin", set_upstream=False):
        status = self.status()
        args = ["push"]
        if set_upstream or not status.upstream:
            args.append("--set-upstream")
        args.extend([remote, status.branch])
        return self._run(*args, timeout=max(self.timeout, 120)).stdout

    def stash(self, message="PyLex Studio temporary changes"):
        return self._run("stash", "push", "-u", "-m", str(message)).stdout

    def stash_list(self, limit=50):
        count = max(1, min(200, int(limit)))
        return self._run("stash", "list", f"--max-count={count}").stdout
