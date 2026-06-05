import tempfile
import unittest
from pathlib import Path

from helpers import FakeRunner, fail, load_script, ok


fast = load_script("fast")


class FastModeTest(unittest.TestCase):
    def make_repo(self, config_text=None):
        temp = tempfile.TemporaryDirectory()
        base = Path(temp.name)
        task_root = base / "worktrees" / "feat-example"
        main_root = base / "repo"
        task_root.mkdir(parents=True)
        main_root.mkdir()
        (task_root / ".codex").mkdir()
        (task_root / ".codex" / "localflow.toml").write_text(
            config_text
            or """\
version = 1
base_branch = "main"
remote_cli = "none"
passphrase = "file:passphrase"
default_mode = "fast"
""",
            encoding="utf-8",
        )
        self.addCleanup(temp.cleanup)
        return task_root, main_root

    def linked_responses(self, task_root: Path, main_root: Path, *, branch="feat/example"):
        return {
            ("git", "rev-parse", "--show-toplevel"): [
                ok([], str(task_root)),
                ok([], str(task_root)),
                ok([], str(task_root)),
                ok([], str(main_root)),
            ],
            ("git", "branch", "--show-current"): [ok([], branch)],
            ("git", "status", "--porcelain"): [ok([], ""), ok([], ""), ok([], "")],
            ("git", "rev-parse", "--git-dir"): [ok([], str(main_root / ".git" / "worktrees" / "feat-example"))],
            ("git", "rev-parse", "--git-common-dir"): [ok([], str(main_root / ".git"))],
            ("git", "rev-parse", "--verify", "--quiet", "main"): [ok([]), ok([])],
            ("git", "fetch", "origin", "main"): [ok([])],
            ("git", "rev-parse", "--verify", "--quiet", "origin/main"): [ok([])],
            ("git", "merge-base", "--is-ancestor", "main", "origin/main"): [ok([])],
            ("git", "merge-base", "--is-ancestor", "origin/main", "main"): [ok([])],
            ("git", "checkout", "main"): [ok([])],
            ("git", "merge", "--ff-only", "origin/main"): [ok([])],
            ("git", "rebase", "main"): [ok([])],
            ("git", "rev-list", "--count", "main..HEAD"): [ok([], "1")],
            ("git", "rev-parse", "HEAD"): [ok([], "abc123")],
            ("git", "merge", "--ff-only", branch): [ok([])],
            ("git", "rev-list", "--left-right", "--count", "origin/main...main"): [ok([], "0 1")],
        }

    def test_fast_lands_locally_without_cleanup_or_push(self):
        task_root, main_root = self.make_repo()
        runner = FakeRunner(self.linked_responses(task_root, main_root))

        result = fast.run(task_root, "codex", runner)

        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "fast_landed")
        self.assertEqual(result["base_branch"], "main")
        self.assertEqual(result["branch"], "feat/example")
        self.assertEqual(result["head_sha"], "abc123")
        self.assertEqual(result["base_ahead_remote"], 1)
        self.assertEqual(result["cleanup"], "not_run")
        self.assertIn(("git", "rebase", "main"), runner.calls)
        self.assertIn(("git", "merge", "--ff-only", "feat/example"), runner.calls)
        self.assertFalse(any(call[:2] == ("git", "push") for call in runner.calls))
        self.assertFalse(any(call[:3] == ("git", "worktree", "remove") for call in runner.calls))
        self.assertFalse(any(call[:2] == ("gh", "pr") or call[:2] == ("glab", "mr") for call in runner.calls))
        self.assertFalse(any(call[:3] in {("git", "branch", "-d"), ("git", "branch", "-D")} for call in runner.calls))

    def test_fast_rejects_long_lived_branch(self):
        task_root, main_root = self.make_repo()
        responses = self.linked_responses(task_root, main_root)
        responses[("git", "branch", "--show-current")] = [ok([], "main")]
        runner = FakeRunner(responses)

        result = fast.run(task_root, "codex", runner)

        self.assertFalse(result["ok"])
        self.assertEqual(result["stop_reason"], "long_lived_branch")
        self.assertNotIn(("git", "rebase", "main"), runner.calls)

    def test_fast_rejects_dirty_task_worktree(self):
        task_root, main_root = self.make_repo()
        responses = self.linked_responses(task_root, main_root)
        responses[("git", "status", "--porcelain")] = [ok([], " M localflow/SKILL.md")]
        runner = FakeRunner(responses)

        result = fast.run(task_root, "codex", runner)

        self.assertFalse(result["ok"])
        self.assertEqual(result["stop_reason"], "dirty_worktree")
        self.assertNotIn(("git", "rebase", "main"), runner.calls)

    def test_fast_stops_on_rebase_conflict_before_local_merge(self):
        task_root, main_root = self.make_repo()
        responses = self.linked_responses(task_root, main_root)
        responses[("git", "rebase", "main")] = [fail([], "CONFLICT")]
        runner = FakeRunner(responses)

        result = fast.run(task_root, "codex", runner)

        self.assertFalse(result["ok"])
        self.assertEqual(result["stop_reason"], "rebase_failed")
        self.assertNotIn(("git", "merge", "--ff-only", "feat/example"), runner.calls)

    def test_fast_stops_when_base_diverged(self):
        task_root, main_root = self.make_repo()
        responses = self.linked_responses(task_root, main_root)
        responses[("git", "merge-base", "--is-ancestor", "main", "origin/main")] = [fail([])]
        responses[("git", "merge-base", "--is-ancestor", "origin/main", "main")] = [fail([])]
        runner = FakeRunner(responses)

        result = fast.run(task_root, "codex", runner)

        self.assertFalse(result["ok"])
        self.assertEqual(result["stop_reason"], "base_diverged")
        self.assertNotIn(("git", "rebase", "main"), runner.calls)
        self.assertNotIn(("git", "merge", "--ff-only", "feat/example"), runner.calls)

    def test_fast_stops_when_rebase_leaves_dirty_worktree(self):
        task_root, main_root = self.make_repo()
        responses = self.linked_responses(task_root, main_root)
        responses[("git", "status", "--porcelain")] = [ok([], ""), ok([], ""), ok([], " M localflow/SKILL.md")]
        runner = FakeRunner(responses)

        result = fast.run(task_root, "codex", runner)

        self.assertFalse(result["ok"])
        self.assertEqual(result["stop_reason"], "dirty_after_rebase")
        self.assertNotIn(("git", "merge", "--ff-only", "feat/example"), runner.calls)
        self.assertFalse(any(call[:3] == ("git", "worktree", "remove") for call in runner.calls))


if __name__ == "__main__":
    unittest.main()
