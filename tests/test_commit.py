import json
import tempfile
import unittest
from pathlib import Path

from helpers import FakeRunner, fail, load_script, ok, repo_flow


commit = load_script("commit")
DEFAULT_CONFIG = """\
version = 1
base_branch = "main"
remote_cli = "gh"
passphrase = "file:passphrase"
default_mode = "tree"
"""

GH_VIEW_FIELDS = "number,state,url,headRefName,baseRefName,headRefOid,mergeStateStatus,statusCheckRollup,isDraft,title"


class CommitModeTest(unittest.TestCase):
    def make_repo(self, config_text=DEFAULT_CONFIG):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / ".codex").mkdir()
        (root / ".codex" / "localflow.toml").write_text(config_text, encoding="utf-8")
        self.addCleanup(temp.cleanup)
        return root

    def commit_responses(self, root, *, branch="feat/example", toplevel=2):
        flows = max(1, toplevel // 2)  # current_branch is read once per flow (commit, then mr)
        return {
            ("git", "rev-parse", "--show-toplevel"): [ok([], str(root)) for _ in range(toplevel)],
            ("git", "branch", "--show-current"): [ok([], branch) for _ in range(flows)],
            ("git", "check-ignore", "-q", "src/Preview.tsx"): [fail([])],
            ("git", "add", "--", "src/Preview.tsx"): [ok([])],
            ("git", "diff", "--cached", "--quiet"): [fail([])],  # exit 1 => staged changes exist
            ("git", "rev-parse", "HEAD"): [ok([], "commit789")],
        }

    def dynamic(self, runner):
        # Normalise the dynamic temp-file path in `git commit -F <tmp>` and intercept
        # `gh pr create` so they can be asserted by a stable key.
        def _runner(args, *, cwd, timeout=30, shell=False, env=None):
            if isinstance(args, list) and args[:2] == ["git", "commit"] and "-F" in args:
                runner.calls.append(("git", "commit", "-F"))
                return ok(args)
            if isinstance(args, list) and args[:3] == ["gh", "pr", "create"]:
                runner.calls.append(tuple(args))
                return ok(args)
            return runner(args, cwd=cwd, timeout=timeout, shell=shell, env=env)

        return _runner

    def test_commit_stages_only_paths_and_commits(self):
        root = self.make_repo()
        runner = FakeRunner(self.commit_responses(root))

        result = commit.run_commit(
            root,
            "codex",
            paths=["src/Preview.tsx"],
            message="feat: add live preview",
            runner=self.dynamic(runner),
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "committed")
        self.assertEqual(result["head_sha"], "commit789")
        self.assertEqual(result["staged_files"], ["src/Preview.tsx"])
        for call in (
            ("git", "add", "--", "src/Preview.tsx"),
            ("git", "diff", "--cached", "--quiet"),
            ("git", "commit", "-F"),
            ("git", "rev-parse", "HEAD"),
        ):
            self.assertIn(call, runner.calls)
        # Never stages the whole tree.
        self.assertFalse(any(c[:3] == ("git", "add", ".") for c in runner.calls))
        self.assertFalse(any(c[:3] == ("git", "add", "-A") for c in runner.calls))

    def test_commit_rejects_invalid_message_before_any_git_write(self):
        root = self.make_repo()
        runner = FakeRunner(self.commit_responses(root))

        result = commit.run_commit(
            root,
            "codex",
            paths=["src/Preview.tsx"],
            message="feat: add live preview.",  # trailing period
            runner=runner,
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["stop_reason"], "invalid_commit_message")
        self.assertFalse(any(c[:2] == ("git", "add") for c in runner.calls))

    def test_commit_rejects_long_lived_branch(self):
        root = self.make_repo()
        responses = self.commit_responses(root)
        responses[("git", "branch", "--show-current")] = [ok([], "main")]
        runner = FakeRunner(responses)

        result = commit.run_commit(
            root,
            "codex",
            paths=["src/Preview.tsx"],
            message="feat: add live preview",
            runner=runner,
        )

        self.assertEqual(result["stop_reason"], "long_lived_branch")
        self.assertFalse(any(c[:2] == ("git", "add") for c in runner.calls))

    def test_commit_rejects_ignored_path(self):
        root = self.make_repo()
        responses = self.commit_responses(root)
        responses[("git", "check-ignore", "-q", ".env")] = [ok([])]
        runner = FakeRunner(responses)

        result = commit.run_commit(
            root,
            "codex",
            paths=[".env"],
            message="feat: add live preview",
            runner=runner,
        )

        self.assertEqual(result["stop_reason"], "ignored_path_staged")
        self.assertFalse(any(c[:2] == ("git", "add") for c in runner.calls))

    def test_commit_stops_when_nothing_staged(self):
        root = self.make_repo()
        responses = self.commit_responses(root)
        responses[("git", "diff", "--cached", "--quiet")] = [ok([])]  # exit 0 => nothing staged
        runner = FakeRunner(responses)

        result = commit.run_commit(
            root,
            "codex",
            paths=["src/Preview.tsx"],
            message="feat: add live preview",
            runner=self.dynamic(runner),
        )

        self.assertEqual(result["stop_reason"], "nothing_staged")
        self.assertFalse(any(c == ("git", "commit", "-F") for c in runner.calls))

    def _mr_responses(self, root, *, view=None):
        view_key = ("gh", "pr", "view", "feat/example", "--json", GH_VIEW_FIELDS)
        return {
            ("git", "status", "--porcelain"): [ok([], "")],
            ("git", "rev-parse", "--verify", "--quiet", "main"): [ok([])],
            ("git", "rev-list", "--count", "main..HEAD"): [ok([], "1")],
            ("git", "remote", "get-url", "origin"): [ok([], "git@github.com:koko-t7i/example.git")],
            ("git", "log", "--reverse", "--format=%H%x00%s", "main..HEAD"): [
                ok([], "abc123\x00feat: add live preview")
            ],
            view_key: [fail([]), ok([], json.dumps(view or {"state": "OPEN", "url": "https://github.com/x/pull/1"}))],
            ("git", "push", "-u", "origin", "feat/example"): [ok([])],
            ("git", "log", "-1", "--pretty=%s"): [ok([], "feat: add live preview")],
            ("git", "log", "--oneline", "main..HEAD"): [ok([], "abc123 feat: add live preview")],
        }

    def test_commit_then_mr_chains_into_review(self):
        root = self.make_repo()
        responses = self.commit_responses(root, toplevel=4)  # commit (2) + mr.run (2)
        responses.update(self._mr_responses(root))
        runner = FakeRunner(responses)

        result = commit.run_commit(
            root,
            "codex",
            paths=["src/Preview.tsx"],
            message="feat: add live preview",
            open_mr=True,
            runner=self.dynamic(runner),
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "created")
        # The commit happened first, then the review was opened.
        self.assertEqual(result["commit"]["action"], "committed")
        self.assertTrue(result["json_path"].endswith("commit.json"))
        self.assertTrue(result["markdown_path"].endswith("commit.md"))
        self.assertIn(("git", "commit", "-F"), runner.calls)
        self.assertIn(("git", "push", "-u", "origin", "feat/example"), runner.calls)
        self.assertTrue(any(c[:3] == ("gh", "pr", "create") for c in runner.calls))

    def test_commit_mr_failure_keeps_commit(self):
        root = self.make_repo()
        responses = self.commit_responses(root, toplevel=4)
        responses.update(self._mr_responses(root))
        responses[("git", "push", "-u", "origin", "feat/example")] = [fail([], "auth denied")]
        runner = FakeRunner(responses)

        result = commit.run_commit(
            root,
            "codex",
            paths=["src/Preview.tsx"],
            message="feat: add live preview",
            open_mr=True,
            runner=self.dynamic(runner),
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["stop_reason"], "push_failed")
        # The commit is real and is NOT rolled back when the review step fails.
        self.assertEqual(result["commit"]["action"], "committed")
        self.assertIn(("git", "commit", "-F"), runner.calls)
        self.assertFalse(any(c[:3] == ("gh", "pr", "create") for c in runner.calls))


if __name__ == "__main__":
    unittest.main()
