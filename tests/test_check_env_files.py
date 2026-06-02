import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "localflow" / "scripts" / "check_env_files.py"


def load_module():
    spec = importlib.util.spec_from_file_location("check_env_files", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def init_repo(root: Path) -> None:
    git(root, "init", "-q", "--initial-branch=main")
    git(root, "config", "user.email", "localflow@example.test")
    git(root, "config", "user.name", "Localflow Test")


class CheckEnvFilesTest(unittest.TestCase):
    def test_cli_json_does_not_leak_env_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".env").write_text(
                "API_KEY=super-secret-value\nexport TOKEN=top-secret-token\n# PASSWORD=commented\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(SCRIPT_PATH), "--cwd", str(root)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            payload = json.loads(result.stdout)
            encoded = json.dumps(payload, sort_keys=True)
            self.assertNotIn("super-secret-value", encoded)
            self.assertNotIn("top-secret-token", encoded)
            self.assertEqual(payload["env_files"][0]["keys"], ["API_KEY", "TOKEN"])
            self.assertEqual(payload["env_files"][0]["key_count"], 2)

    def test_distinguishes_templates_from_actual_env_files(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            nested = root / "nested"
            nested.mkdir()
            (root / ".env").write_text("ROOT=value\n", encoding="utf-8")
            (root / ".env.local").write_text("LOCAL=value\n", encoding="utf-8")
            (root / ".env.example").write_text("EXAMPLE=value\n", encoding="utf-8")
            (nested / ".env.prod.example").write_text("PROD_EXAMPLE=value\n", encoding="utf-8")

            payload = module.check_repository(root, max_depth=2)

            self.assertEqual([item["path"] for item in payload["env_files"]], [".env", ".env.local"])
            self.assertEqual([item["path"] for item in payload["templates"]], [".env.example", "nested/.env.prod.example"])

    def test_identifies_tracked_ignored_and_untracked_env_files(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            init_repo(root)
            (root / ".gitignore").write_text(".env.ignored\n", encoding="utf-8")
            (root / ".env.tracked").write_text("TRACKED=value\n", encoding="utf-8")
            (root / ".env.ignored").write_text("IGNORED=value\n", encoding="utf-8")
            (root / ".env.untracked").write_text("UNTRACKED=value\n", encoding="utf-8")
            git(root, "add", ".gitignore", ".env.tracked")

            payload = module.check_repository(root)
            by_path = {item["path"]: item for item in payload["env_files"]}

            self.assertEqual(by_path[".env.tracked"]["status"], "tracked")
            self.assertTrue(by_path[".env.tracked"]["tracked"])
            self.assertEqual(by_path[".env.ignored"]["status"], "ignored")
            self.assertTrue(by_path[".env.ignored"]["ignored"])
            self.assertEqual(by_path[".env.untracked"]["status"], "untracked")

            warnings = {(item["kind"], item.get("path")) for item in payload["warnings"]}
            self.assertIn(("tracked_env_file", ".env.tracked"), warnings)
            self.assertIn(("unignored_env_file", ".env.untracked"), warnings)

    def test_finds_env_file_candidate_from_sibling_worktree(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "repo"
            sibling = base / "repo-sibling"
            root.mkdir()
            init_repo(root)
            (root / ".gitignore").write_text(".env.local\n", encoding="utf-8")
            (root / "README.md").write_text("repo\n", encoding="utf-8")
            git(root, "add", ".gitignore", "README.md")
            git(root, "commit", "-q", "-m", "init")
            git(root, "worktree", "add", "-q", "-b", "sibling-env", str(sibling))
            (sibling / ".env.local").write_text("SIBLING_ONLY=secret-from-sibling\n", encoding="utf-8")

            payload = module.check_repository(root)

            self.assertEqual(len(payload["sibling_candidates"]), 1)
            candidate = payload["sibling_candidates"][0]
            self.assertEqual(candidate["path"], ".env.local")
            self.assertEqual(candidate["sources"][0]["worktree"], "../repo-sibling")
            self.assertEqual(candidate["sources"][0]["branch"], "sibling-env")
            self.assertEqual(candidate["sources"][0]["status"], "ignored")
            self.assertEqual(candidate["sources"][0]["keys"], ["SIBLING_ONLY"])
            encoded = json.dumps(payload, sort_keys=True)
            self.assertNotIn("secret-from-sibling", encoded)
            self.assertIn(
                {"kind": "missing_sibling_env_file", "path": ".env.local", "sources": ["../repo-sibling"]},
                payload["warnings"],
            )

    def test_sibling_candidate_must_match_current_directory_layout(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "repo"
            sibling = base / "repo-sibling"
            root.mkdir()
            init_repo(root)
            (root / "server").mkdir()
            (root / ".gitignore").write_text("server/.env\napi/.env\n", encoding="utf-8")
            (root / "server" / "README.md").write_text("server\n", encoding="utf-8")
            git(root, "add", ".gitignore", "server/README.md")
            git(root, "commit", "-q", "-m", "init")
            git(root, "worktree", "add", "-q", "-b", "old-layout-env", str(sibling))
            (sibling / "api").mkdir()
            (sibling / "api" / ".env").write_text("OLD_LAYOUT=secret\n", encoding="utf-8")
            (sibling / "server" / ".env").write_text("SERVER_LAYOUT=secret\n", encoding="utf-8")

            payload = module.check_repository(root)

            self.assertEqual([item["path"] for item in payload["sibling_candidates"]], ["server/.env"])
            encoded = json.dumps(payload, sort_keys=True)
            self.assertNotIn("secret", encoded)


if __name__ == "__main__":
    unittest.main()
