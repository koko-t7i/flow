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
mr = load_script("mr")


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


class MrCommandTest(unittest.TestCase):
    def make_repo(self, config_text="base_branch = \"main\"\n"):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / ".codex").mkdir()
        (root / ".codex" / "localflow.toml").write_text(config_text, encoding="utf-8")
        self.addCleanup(temp.cleanup)
        return root

    def base_responses(self, root: Path):
        return {
            ("git", "rev-parse", "--show-toplevel"): [ok([], str(root)), ok([], str(root))],
            ("git", "branch", "--show-current"): [ok([], "feat/example")],
            ("git", "status", "--porcelain"): [ok([], "")],
            ("git", "rev-parse", "--verify", "--quiet", "main"): [ok([])],
            ("git", "rev-list", "--count", "main..HEAD"): [ok([], "1")],
            ("git", "remote", "get-url", "origin"): [ok([], "git@github.com:koko-t7i/example.git")],
        }

    def test_current_host_config_wins_without_merging_fallback(self):
        root = self.make_repo(
            """
base_branch = "main"

[delivery]
remote_provider = "github"
"""
        )
        (root / ".claude").mkdir()
        (root / ".claude" / "localflow.toml").write_text(
            """
base_branch = "test"

[delivery]
remote_provider = "gitlab"
""",
            encoding="utf-8",
        )
        runner = FakeRunner({("git", "rev-parse", "--show-toplevel"): [ok([], str(root))]})

        config, path = repo_flow.load_repo_config(root, "codex", runner)

        self.assertEqual(config["base_branch"], "main")
        self.assertEqual(repo_flow.section(config, "delivery")["remote_provider"], "github")
        self.assertTrue(str(path).endswith(".codex/localflow.toml"))

    def test_dirty_worktree_stops_before_create_or_push(self):
        root = self.make_repo()
        responses = self.base_responses(root)
        responses[("git", "status", "--porcelain")] = [ok([], " M file.txt")]
        runner = FakeRunner(responses)

        result = mr.run(root, "codex", runner)

        self.assertFalse(result["ok"])
        self.assertEqual(result["stop_reason"], "dirty_worktree")
        self.assertNotIn(("git", "push", "-u", "origin", "feat/example"), runner.calls)

    def test_provider_inference_supports_github_pr_and_gitlab_mr(self):
        self.assertEqual(
            repo_flow.resolve_provider({}, "git@github.com:koko-t7i/example.git")["provider"],
            "github",
        )
        self.assertEqual(
            repo_flow.resolve_provider({}, "git@gitlab.com:koko-t7i/example.git")["provider"],
            "gitlab",
        )
        self.assertEqual(repo_flow.review_view_command("github", "feat/example")[:3], ["gh", "pr", "view"])
        self.assertEqual(repo_flow.review_view_command("gitlab", "feat/example")[:3], ["glab", "mr", "view"])

    def test_auto_base_branch_uses_nearest_long_lived_branch(self):
        root = self.make_repo("")
        responses = {
            ("git", "rev-parse", "--verify", "--quiet", "origin/main"): [ok([])],
            ("git", "rev-list", "--count", "origin/main..HEAD"): [ok([], "475")],
            ("git", "rev-parse", "--verify", "--quiet", "origin/test"): [ok([])],
            ("git", "rev-list", "--count", "origin/test..HEAD"): [ok([], "1")],
            ("git", "rev-parse", "--verify", "--quiet", "origin/dev"): [fail([])],
            ("git", "rev-parse", "--verify", "--quiet", "dev"): [fail([])],
        }
        runner = FakeRunner(responses)

        result = repo_flow.resolve_base_branch(root, {}, runner)

        self.assertEqual(result, {"name": "test", "ref": "origin/test"})

    def test_provider_inference_uses_cli_auth_for_self_hosted_gitlab(self):
        root = self.make_repo()
        runner = FakeRunner(
            {
                ("glab", "auth", "status", "--hostname", "git.aurtech.cc"): [ok([])],
                ("gh", "auth", "status", "--hostname", "git.aurtech.cc"): [fail([])],
            }
        )

        result = repo_flow.resolve_provider(
            {},
            "https://git.aurtech.cc/w3/rpc-gateway.git",
            root,
            runner,
        )

        self.assertEqual(result["provider"], "gitlab")

    def test_self_hosted_gitlab_mr_returns_status_without_duplicate_create(self):
        root = self.make_repo()
        review = {
            "iid": 207,
            "state": "opened",
            "web_url": "https://git.aurtech.cc/w3/rpc-gateway/-/merge_requests/207",
            "source_branch": "feat/example",
            "target_branch": "main",
            "sha": "abc123",
            "detailed_merge_status": "checking",
            "title": "refactor: update api",
        }
        responses = self.base_responses(root)
        responses[("git", "remote", "get-url", "origin")] = [ok([], "https://git.aurtech.cc/w3/rpc-gateway.git")]
        responses[("glab", "auth", "status", "--hostname", "git.aurtech.cc")] = [ok([])]
        responses[("gh", "auth", "status", "--hostname", "git.aurtech.cc")] = [fail([])]
        responses[("glab", "mr", "view", "feat/example", "--output", "json")] = [ok([], json.dumps(review))]
        runner = FakeRunner(responses)

        result = mr.run(root, "codex", runner)

        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "status")
        self.assertEqual(result["provider"], "gitlab")
        self.assertEqual(result["url"], review["web_url"])
        self.assertFalse(any(call[:3] == ("glab", "mr", "create") for call in runner.calls))

    def test_simple_toml_preserves_escaped_quotes_in_command_arrays(self):
        config = repo_flow.parse_simple_toml(
            """
[validation]
pre_commit = [
  "python3 \\"$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py\\" ./localflow",
  "git diff --check",
]
"""
        )

        self.assertEqual(
            repo_flow.section(config, "validation")["pre_commit"],
            [
                'python3 "$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py" ./localflow',
                "git diff --check",
            ],
        )

    def test_shell_command_env_removes_uv_python_path(self):
        env = repo_flow.shell_command_env(
            base_env={"UV_RUN_RECURSION_DEPTH": "1", "PATH": "/uv/python/bin:/usr/bin"},
            executable="/uv/python/bin/python3",
        )

        self.assertEqual(env["PATH"], "/usr/bin")

    def test_existing_pr_returns_status_without_duplicate_create(self):
        root = self.make_repo()
        review = {
            "number": 7,
            "state": "OPEN",
            "url": "https://github.com/koko-t7i/example/pull/7",
            "headRefOid": "abc123",
        }
        responses = self.base_responses(root)
        responses[
            (
                "gh",
                "pr",
                "view",
                "feat/example",
                "--json",
                "number,state,url,headRefName,baseRefName,headRefOid,mergeStateStatus,statusCheckRollup,isDraft,title",
            )
        ] = [ok([], json.dumps(review))]
        runner = FakeRunner(responses)

        result = mr.run(root, "codex", runner)

        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "status")
        self.assertEqual(result["url"], review["url"])
        self.assertFalse(any(call[:3] == ("gh", "pr", "create") for call in runner.calls))

    def test_github_create_uses_fixed_title_body_and_push(self):
        root = self.make_repo()
        responses = self.base_responses(root)
        view_key = (
            "gh",
            "pr",
            "view",
            "feat/example",
            "--json",
            "number,state,url,headRefName,baseRefName,headRefOid,mergeStateStatus,statusCheckRollup,isDraft,title",
        )
        responses[view_key] = [
            fail([]),
            ok([], json.dumps({"state": "OPEN", "url": "https://github.com/koko-t7i/example/pull/8"})),
        ]
        responses[("git", "push", "-u", "origin", "feat/example")] = [ok([])]
        responses[("git", "log", "-1", "--pretty=%s")] = [ok([], "docs: update workflow")]
        responses[("git", "log", "--oneline", "main..HEAD")] = [ok([], "abc123 docs: update workflow")]
        runner = FakeRunner(responses)

        def dynamic_runner(args, *, cwd, timeout=30, shell=False):
            if isinstance(args, list) and args[:3] == ["gh", "pr", "create"]:
                runner.calls.append(tuple(args))
                return ok(args)
            return runner(args, cwd=cwd, timeout=timeout, shell=shell)

        result = mr.run(root, "codex", dynamic_runner)

        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "created")
        self.assertIn(("git", "push", "-u", "origin", "feat/example"), runner.calls)
        self.assertTrue(any(call[:3] == ("gh", "pr", "create") for call in runner.calls))


if __name__ == "__main__":
    unittest.main()
