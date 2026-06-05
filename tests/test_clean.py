import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "localflow" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


repo_flow = load_script("repo_flow")
clean = load_script("clean")


class FakeRunner:
    def __init__(self, responses):
        self.responses = {key: list(value) for key, value in responses.items()}
        self.calls = []

    def __call__(self, args, *, cwd, timeout=30, shell=False):
        key = ("shell", args) if shell else tuple(args)
        self.calls.append(key)
        values = self.responses.get(key)
        if not values:
            return repo_flow.CommandResult(False, 1, "", f"unexpected command: {key}", args)
        return values.pop(0)


def ok(args, stdout="", stderr=""):
    return repo_flow.CommandResult(True, 0, stdout, stderr, args)


def fail(args, stderr="failed"):
    return repo_flow.CommandResult(False, 1, "", stderr, args)


class CleanCommandTest(unittest.TestCase):
    def make_repo(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / ".codex").mkdir()
        (root / ".codex" / "localflow.toml").write_text(
            """
base_branch = "main"

[delivery]
remote_provider = "github"
cleanup_remote_branch = "auto"
""",
            encoding="utf-8",
        )
        self.addCleanup(temp.cleanup)
        return root

    def base_responses(self, root: Path):
        return {
            ("git", "rev-parse", "--show-toplevel"): [ok([], str(root)), ok([], str(root)), ok([], str(root))],
            ("git", "branch", "--show-current"): [ok([], "feat/example")],
            ("git", "status", "--porcelain"): [ok([], ""), ok([], "")],
            ("git", "rev-parse", "--verify", "--quiet", "main"): [ok([])],
            ("git", "rev-parse", "HEAD"): [ok([], "abc123")],
            ("git", "remote", "get-url", "origin"): [ok([], "git@github.com:koko-t7i/example.git")],
        }

    def pr_view_key(self, branch="feat/example"):
        return (
            "gh",
            "pr",
            "view",
            branch,
            "--json",
            "number,state,url,headRefName,baseRefName,headRefOid,mergeStateStatus,statusCheckRollup,isDraft,title",
        )

    def main_responses(self, root: Path):
        responses = self.base_responses(root)
        responses[("git", "branch", "--show-current")] = [ok([], "main")]
        responses[("git", "status", "--porcelain")] = [ok([], "")]
        responses[("git", "rev-parse", "--show-toplevel")] = [ok([], str(root)), ok([], str(root))]
        responses.pop(("git", "rev-parse", "HEAD"))
        return responses

    def test_open_pr_never_cleans(self):
        root = self.make_repo()
        responses = self.base_responses(root)
        responses[self.pr_view_key()] = [
            ok([], json.dumps({"state": "OPEN", "url": "https://github.com/koko-t7i/example/pull/1", "headRefOid": "abc123"}))
        ]
        runner = FakeRunner(responses)

        result = clean.run(root, "codex", runner)

        self.assertFalse(result["ok"])
        self.assertEqual(result["stop_reason"], "review_not_merged")
        self.assertFalse(any(call[:3] == ("git", "branch", "-D") for call in runner.calls))
        self.assertFalse(any(call[:3] == ("git", "worktree", "remove") for call in runner.calls))
        self.assertFalse(any(call[:3] == ("git", "push", "origin") for call in runner.calls))

    def test_no_review_and_not_landed_never_cleans(self):
        root = self.make_repo()
        responses = self.base_responses(root)
        responses[self.pr_view_key()] = [fail([])]
        responses[("git", "merge-base", "--is-ancestor", "HEAD", "main")] = [fail([])]
        runner = FakeRunner(responses)

        result = clean.run(root, "codex", runner)

        self.assertFalse(result["ok"])
        self.assertEqual(result["stop_reason"], "review_not_merged")
        self.assertFalse(any(call[:3] in {("git", "branch", "-d"), ("git", "branch", "-D")} for call in runner.calls))

    def test_local_landing_cleans_only_when_clean_is_invoked(self):
        root = self.make_repo()
        responses = self.base_responses(root)
        responses[self.pr_view_key()] = [fail([])]
        responses[("git", "merge-base", "--is-ancestor", "HEAD", "main")] = [ok([])]
        responses[("git", "push", "origin", "--delete", "feat/example")] = [
            fail([], "remote ref does not exist")
        ]
        responses[("git", "branch", "-dr", "origin/feat/example")] = [ok([])]
        responses[("git", "rev-parse", "--git-dir")] = [ok([], ".git")]
        responses[("git", "rev-parse", "--git-common-dir")] = [ok([], ".git")]
        responses[("git", "checkout", "main")] = [ok([])]
        responses[("git", "branch", "-d", "feat/example")] = [ok([])]
        runner = FakeRunner(responses)

        result = clean.run(root, "codex", runner)

        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "cleaned")
        self.assertEqual(result["state"], "local_landed")
        self.assertEqual(result["landed_by"], "local_landing")
        self.assertIn(("git", "branch", "-d", "feat/example"), runner.calls)
        self.assertNotIn(("git", "branch", "-D", "feat/example"), runner.calls)

    def test_merged_pr_cleans_normal_checkout(self):
        root = self.make_repo()
        responses = self.base_responses(root)
        responses[self.pr_view_key()] = [
            ok([], json.dumps({"state": "MERGED", "url": "https://github.com/koko-t7i/example/pull/1", "headRefOid": "abc123"}))
        ]
        responses[("git", "fetch", "origin", "main")] = [ok([])]
        responses[("git", "push", "origin", "--delete", "feat/example")] = [ok([])]
        responses[("git", "branch", "-dr", "origin/feat/example")] = [ok([])]
        responses[("git", "rev-parse", "--git-dir")] = [ok([], ".git")]
        responses[("git", "rev-parse", "--git-common-dir")] = [ok([], ".git")]
        responses[("git", "checkout", "main")] = [ok([])]
        responses[("git", "branch", "-D", "feat/example")] = [ok([])]
        runner = FakeRunner(responses)

        result = clean.run(root, "codex", runner)

        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "cleaned")
        self.assertIn(("git", "push", "origin", "--delete", "feat/example"), runner.calls)
        self.assertIn(("git", "branch", "-dr", "origin/feat/example"), runner.calls)
        self.assertIn(("git", "branch", "-D", "feat/example"), runner.calls)

    def test_main_scans_and_cleans_only_landed_candidates(self):
        root = self.make_repo()
        merged_tree = root.parent / "worktrees" / "docs-merged"
        open_tree = root.parent / "worktrees" / "fix-open"
        responses = self.main_responses(root)
        responses[("git", "for-each-ref", "--format=%(refname:short)", "refs/heads")] = [
            ok([], "main\ndocs/merged\nfix/open")
        ]
        responses[("git", "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin")] = [
            ok([], "origin/main\norigin/docs/merged\norigin/fix/open\norigin/fix/remote-only")
        ]
        responses[("git", "worktree", "list", "--porcelain")] = [
            ok(
                [],
                f"""worktree {root}
HEAD base123
branch refs/heads/main

worktree {merged_tree}
HEAD merged123
branch refs/heads/docs/merged

worktree {open_tree}
HEAD open123
branch refs/heads/fix/open
""",
            )
        ]
        responses[("git", "rev-parse", "docs/merged")] = [ok([], "merged123")]
        responses[("git", "rev-parse", "origin/docs/merged")] = [ok([], "merged123")]
        responses[("git", "rev-parse", "fix/open")] = [ok([], "open123")]
        responses[("git", "rev-parse", "origin/fix/open")] = [ok([], "open123")]
        responses[("git", "rev-parse", "origin/fix/remote-only")] = [ok([], "remote123")]
        responses[self.pr_view_key("docs/merged")] = [
            ok([], json.dumps({"state": "MERGED", "url": "https://github.com/koko-t7i/example/pull/2", "headRefOid": "merged123"}))
        ]
        responses[self.pr_view_key("fix/open")] = [
            ok([], json.dumps({"state": "OPEN", "url": "https://github.com/koko-t7i/example/pull/3", "headRefOid": "open123"}))
        ]
        responses[self.pr_view_key("fix/remote-only")] = [
            ok([], json.dumps({"state": "MERGED", "url": "https://github.com/koko-t7i/example/pull/4", "headRefOid": "remote123"}))
        ]
        responses[("git", "status", "--porcelain")] = [ok([], ""), ok([], "")]
        responses[("git", "push", "origin", "--delete", "docs/merged")] = [ok([])]
        responses[("git", "branch", "-dr", "origin/docs/merged")] = [ok([])]
        responses[("git", "worktree", "remove", str(merged_tree))] = [ok([])]
        responses[("git", "branch", "-D", "docs/merged")] = [ok([])]
        responses[("git", "push", "origin", "--delete", "fix/remote-only")] = [ok([])]
        responses[("git", "branch", "-dr", "origin/fix/remote-only")] = [ok([])]
        responses[("git", "worktree", "prune")] = [ok([])]
        runner = FakeRunner(responses)

        result = clean.run(root, "codex", runner)

        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "scanned_cleaned")
        self.assertEqual({item["branch"] for item in result["cleaned"]}, {"docs/merged", "fix/remote-only"})
        self.assertEqual(result["skipped"], [{"branch": "fix/open", "reason": "review_not_merged", "state": "open"}])
        self.assertIn(("git", "push", "origin", "--delete", "docs/merged"), runner.calls)
        self.assertIn(("git", "worktree", "remove", str(merged_tree)), runner.calls)
        self.assertIn(("git", "branch", "-D", "docs/merged"), runner.calls)
        self.assertIn(("git", "push", "origin", "--delete", "fix/remote-only"), runner.calls)
        self.assertIn(("git", "branch", "-dr", "origin/fix/remote-only"), runner.calls)
        self.assertNotIn(("git", "push", "origin", "--delete", "fix/open"), runner.calls)
        self.assertNotIn(("git", "worktree", "remove", str(open_tree)), runner.calls)

    def test_main_scan_skips_dirty_landed_worktree(self):
        root = self.make_repo()
        merged_tree = root.parent / "worktrees" / "docs-dirty"
        responses = self.main_responses(root)
        responses[("git", "for-each-ref", "--format=%(refname:short)", "refs/heads")] = [ok([], "main\ndocs/dirty")]
        responses[("git", "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin")] = [ok([], "origin/main")]
        responses[("git", "worktree", "list", "--porcelain")] = [
            ok(
                [],
                f"""worktree {root}
HEAD base123
branch refs/heads/main

worktree {merged_tree}
HEAD dirty123
branch refs/heads/docs/dirty
""",
            )
        ]
        responses[("git", "rev-parse", "docs/dirty")] = [ok([], "dirty123")]
        responses[self.pr_view_key("docs/dirty")] = [
            ok([], json.dumps({"state": "MERGED", "url": "https://github.com/koko-t7i/example/pull/5", "headRefOid": "dirty123"}))
        ]
        responses[("git", "status", "--porcelain")] = [ok([], ""), ok([], " M SKILL.md")]
        runner = FakeRunner(responses)

        result = clean.run(root, "codex", runner)

        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "noop")
        self.assertEqual(result["cleaned"], [])
        self.assertEqual(result["skipped"], [{"branch": "docs/dirty", "reason": "dirty_worktree", "state": "merged"}])
        self.assertNotIn(("git", "push", "origin", "--delete", "docs/dirty"), runner.calls)
        self.assertNotIn(("git", "worktree", "remove", str(merged_tree)), runner.calls)


if __name__ == "__main__":
    unittest.main()
