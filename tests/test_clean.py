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

    def pr_view_key(self):
        return (
            "gh",
            "pr",
            "view",
            "feat/example",
            "--json",
            "number,state,url,headRefName,baseRefName,headRefOid,mergeStateStatus,statusCheckRollup,isDraft,title",
        )

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

    def test_merged_pr_cleans_normal_checkout(self):
        root = self.make_repo()
        responses = self.base_responses(root)
        responses[self.pr_view_key()] = [
            ok([], json.dumps({"state": "MERGED", "url": "https://github.com/koko-t7i/example/pull/1", "headRefOid": "abc123"}))
        ]
        responses[("git", "fetch", "origin", "main")] = [ok([])]
        responses[("git", "push", "origin", "--delete", "feat/example")] = [ok([])]
        responses[("git", "rev-parse", "--git-dir")] = [ok([], ".git")]
        responses[("git", "rev-parse", "--git-common-dir")] = [ok([], ".git")]
        responses[("git", "checkout", "main")] = [ok([])]
        responses[("git", "branch", "-D", "feat/example")] = [ok([])]
        runner = FakeRunner(responses)

        result = clean.run(root, "codex", runner)

        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "cleaned")
        self.assertIn(("git", "push", "origin", "--delete", "feat/example"), runner.calls)
        self.assertIn(("git", "branch", "-D", "feat/example"), runner.calls)


if __name__ == "__main__":
    unittest.main()
