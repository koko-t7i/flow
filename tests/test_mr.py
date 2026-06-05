import json
import tempfile
import unittest
from pathlib import Path

from helpers import FakeRunner, fail, load_script, ok, repo_flow


mr = load_script("mr")


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


GH_VIEW_FIELDS = "number,state,url,headRefName,baseRefName,headRefOid,mergeStateStatus,statusCheckRollup,isDraft,title"


class SnapshotModeTest(unittest.TestCase):
    def make_repo(self, config_text='base_branch = "main"\n'):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        (root / ".codex").mkdir()
        (root / ".codex" / "localflow.toml").write_text(config_text, encoding="utf-8")
        self.addCleanup(temp.cleanup)
        return root

    def snapshot_responses(self, root, *, branch="feat/live-preview", message="feat: add live preview", review=None):
        gh_view = ("gh", "pr", "view", branch, "--json", GH_VIEW_FIELDS)
        view_value = ok([], json.dumps(review)) if review else fail([])
        return {
            ("git", "rev-parse", "--show-toplevel"): [ok([], str(root)), ok([], str(root))],
            ("git", "rev-parse", "--verify", "--quiet", "main"): [ok([])],
            ("git", "fetch", "origin", "main"): [ok([])],
            ("git", "rev-parse", "--verify", "--quiet", "origin/main"): [ok([])],
            ("git", "read-tree", "origin/main"): [ok([])],
            ("git", "add", "--", "src/Preview.tsx"): [ok([])],
            ("git", "write-tree"): [ok([], "tree123")],
            ("git", "commit-tree", "tree123", "-p", "origin/main", "-m", message): [ok([], "commit456")],
            ("git", "update-ref", f"refs/heads/{branch}", "commit456"): [ok([])],
            ("git", "diff", "--name-only", "origin/main", "commit456"): [ok([], "src/Preview.tsx")],
            ("git", "remote", "get-url", "origin"): [ok([], "git@github.com:koko-t7i/example.git")],
            ("git", "push", "-u", "origin", branch): [ok([])],
            gh_view: [view_value, ok([], json.dumps(review or {"state": "OPEN", "url": "https://github.com/x/pull/1"}))],
        }

    def dynamic(self, runner):
        def _runner(args, *, cwd, timeout=30, shell=False, env=None):
            if isinstance(args, list) and args[:3] == ["gh", "pr", "create"]:
                runner.calls.append(tuple(args))
                return ok(args)
            return runner(args, cwd=cwd, timeout=timeout, shell=shell, env=env)

        return _runner

    def test_snapshot_creates_branch_without_touching_worktree(self):
        root = self.make_repo()
        runner = FakeRunner(self.snapshot_responses(root))

        result = mr.run_snapshot(
            root,
            "codex",
            branch="feat/live-preview",
            paths=["src/Preview.tsx"],
            message="feat: add live preview",
            runner=self.dynamic(runner),
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "snapshot_created")
        self.assertEqual(result["head_sha"], "commit456")
        self.assertEqual(result["included_files"], ["src/Preview.tsx"])
        # The snapshot pipeline ran in order, anchored on the freshly-fetched remote tip.
        for call in (
            ("git", "fetch", "origin", "main"),
            ("git", "read-tree", "origin/main"),
            ("git", "add", "--", "src/Preview.tsx"),
            ("git", "write-tree"),
            ("git", "commit-tree", "tree123", "-p", "origin/main", "-m", "feat: add live preview"),
            ("git", "update-ref", "refs/heads/feat/live-preview", "commit456"),
            ("git", "diff", "--name-only", "origin/main", "commit456"),
            ("git", "push", "-u", "origin", "feat/live-preview"),
        ):
            self.assertIn(call, runner.calls)
        self.assertTrue(any(c[:3] == ("gh", "pr", "create") for c in runner.calls))
        # It never inspects/mutates the working tree, HEAD, or real index.
        self.assertNotIn(("git", "status", "--porcelain"), runner.calls)
        self.assertFalse(any(c[:2] == ("git", "checkout") for c in runner.calls))
        self.assertFalse(any(c[:2] == ("git", "stash") for c in runner.calls))
        self.assertFalse(any(c[:2] == ("git", "commit") for c in runner.calls))

    def test_snapshot_rejects_invalid_message_before_any_git_write(self):
        root = self.make_repo()
        runner = FakeRunner(self.snapshot_responses(root))

        result = mr.run_snapshot(
            root,
            "codex",
            branch="feat/live-preview",
            paths=["src/Preview.tsx"],
            message="feat: add live preview.",  # trailing period
            runner=runner,
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["stop_reason"], "invalid_commit_message")
        self.assertNotIn(("git", "read-tree", "origin/main"), runner.calls)

    def test_snapshot_rejects_non_ascii_message(self):
        root = self.make_repo()
        runner = FakeRunner(self.snapshot_responses(root))

        result = mr.run_snapshot(
            root,
            "codex",
            branch="feat/live-preview",
            paths=["src/Preview.tsx"],
            message="feat: 添加实时预览",
            runner=runner,
        )

        self.assertEqual(result["stop_reason"], "invalid_commit_message")
        self.assertNotIn(("git", "read-tree", "origin/main"), runner.calls)

    def test_snapshot_rejects_ignored_path(self):
        root = self.make_repo()
        responses = self.snapshot_responses(root)
        responses[("git", "check-ignore", "-q", ".env")] = [ok([])]
        runner = FakeRunner(responses)

        result = mr.run_snapshot(
            root,
            "codex",
            branch="feat/live-preview",
            paths=[".env"],
            message="feat: add live preview",
            runner=runner,
        )

        self.assertEqual(result["stop_reason"], "ignored_path_staged")
        self.assertNotIn(("git", "read-tree", "origin/main"), runner.calls)

    def test_snapshot_uses_existing_branch_tip_as_parent_and_updates(self):
        root = self.make_repo()
        review = {"state": "OPEN", "url": "https://github.com/koko-t7i/example/pull/9", "headRefOid": "old"}
        responses = self.snapshot_responses(root, review=review)
        # Branch already exists locally -> parent is its tip, commit-tree changes accordingly.
        responses[("git", "rev-parse", "--verify", "--quiet", "refs/heads/feat/live-preview")] = [ok([])]
        responses[("git", "commit-tree", "tree123", "-p", "refs/heads/feat/live-preview", "-m", "feat: add live preview")] = [ok([], "commit456")]
        runner = FakeRunner(responses)

        result = mr.run_snapshot(
            root,
            "codex",
            branch="feat/live-preview",
            paths=["src/Preview.tsx"],
            message="feat: add live preview",
            runner=self.dynamic(runner),
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["action"], "snapshot_updated")
        self.assertIn(
            ("git", "commit-tree", "tree123", "-p", "refs/heads/feat/live-preview", "-m", "feat: add live preview"),
            runner.calls,
        )
        # Existing review -> do not create a duplicate.
        self.assertFalse(any(c[:3] == ("gh", "pr", "create") for c in runner.calls))

    def test_snapshot_with_version_bump_injects_blob(self):
        root = self.make_repo(
            'base_branch = "main"\n\n[version_policy]\nenabled = true\nfiles = ["plugin.json"]\n'
        )
        (root / "plugin.json").write_text('{"name": "x", "version": "0.9.0"}\n', encoding="utf-8")
        responses = self.snapshot_responses(root)
        responses[("git", "update-index", "--add", "--cacheinfo", "100644,blobsha,plugin.json")] = [ok([])]
        runner = FakeRunner(responses)

        def dynamic_runner(args, *, cwd, timeout=30, shell=False, env=None):
            if isinstance(args, list) and args[:2] == ["git", "hash-object"]:
                runner.calls.append(("git", "hash-object"))
                return ok([], "blobsha")
            if isinstance(args, list) and args[:3] == ["gh", "pr", "create"]:
                runner.calls.append(tuple(args))
                return ok(args)
            return runner(args, cwd=cwd, timeout=timeout, shell=shell, env=env)

        result = mr.run_snapshot(
            root,
            "codex",
            branch="feat/live-preview",
            paths=["src/Preview.tsx"],
            message="feat: add live preview",
            bump="minor",
            runner=dynamic_runner,
        )

        self.assertTrue(result["ok"])
        self.assertEqual(result["version"]["decision"], "bumped")
        self.assertEqual(result["version"]["to"], "0.10.0")
        self.assertIn(
            ("git", "update-index", "--add", "--cacheinfo", "100644,blobsha,plugin.json"),
            runner.calls,
        )

    def test_snapshot_version_bump_requires_enabled_policy(self):
        root = self.make_repo()  # no [version_policy]
        runner = FakeRunner(self.snapshot_responses(root))

        result = mr.run_snapshot(
            root,
            "codex",
            branch="feat/live-preview",
            paths=["src/Preview.tsx"],
            message="feat: add live preview",
            bump="minor",
            runner=runner,
        )

        self.assertEqual(result["stop_reason"], "version_policy_disabled")

    def test_snapshot_stops_when_base_fetch_fails(self):
        # An auto-resolved base must refresh from the remote; a failed fetch must stop
        # rather than silently snapshot against a possibly-stale local tracking ref.
        root = self.make_repo()
        responses = self.snapshot_responses(root)
        responses[("git", "fetch", "origin", "main")] = [fail([], "network down")]
        runner = FakeRunner(responses)

        result = mr.run_snapshot(
            root,
            "codex",
            branch="feat/live-preview",
            paths=["src/Preview.tsx"],
            message="feat: add live preview",
            runner=runner,
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["stop_reason"], "base_fetch_failed")
        # Never anchored, committed, or pushed against a stale base.
        self.assertNotIn(("git", "read-tree", "origin/main"), runner.calls)
        self.assertFalse(any(c[:2] == ("git", "push") for c in runner.calls))

    def test_snapshot_rejects_base_drift_before_push(self):
        # If the snapshot touches anything beyond --paths relative to the live base,
        # the base is stale/behind: refuse to push the contaminated review.
        root = self.make_repo()
        responses = self.snapshot_responses(root)
        responses[("git", "diff", "--name-only", "origin/main", "commit456")] = [
            ok([], "src/Preview.tsx\nsrc/Other.tsx")
        ]
        runner = FakeRunner(responses)

        result = mr.run_snapshot(
            root,
            "codex",
            branch="feat/live-preview",
            paths=["src/Preview.tsx"],
            message="feat: add live preview",
            runner=self.dynamic(runner),
        )

        self.assertFalse(result["ok"])
        self.assertEqual(result["stop_reason"], "snapshot_base_drift")
        self.assertIn("src/Other.tsx", result["message"])
        # Guard fires before any push / review create.
        self.assertFalse(any(c[:2] == ("git", "push") for c in runner.calls))
        self.assertFalse(any(c[:3] == ("gh", "pr", "create") for c in runner.calls))


if __name__ == "__main__":
    unittest.main()
