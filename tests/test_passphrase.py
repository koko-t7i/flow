import tempfile
import unittest
from pathlib import Path

from helpers import FakeRunner, fail, ok, repo_flow


class PassphraseConfigTest(unittest.TestCase):
    def make_repo(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        config_dir = root / ".codex"
        config_dir.mkdir()
        config_path = config_dir / "localflow.toml"
        config = {
            "version": 1,
            "base_branch": "main",
            "remote_cli": "gh",
            "passphrase": "file:passphrase",
            "default_mode": "tree",
        }
        self.addCleanup(temp.cleanup)
        return root, config_path, config

    def test_passphrase_file_must_exist(self):
        root, config_path, config = self.make_repo()
        runner = FakeRunner({("git", "rev-parse", "--show-toplevel"): [ok([], str(root))]})

        result = repo_flow.passphrase_file(config, str(config_path), root, runner)

        self.assertEqual(result["stop_reason"], "passphrase_file_missing")

    def test_passphrase_file_must_be_ignored(self):
        root, config_path, config = self.make_repo()
        (root / ".codex" / "passphrase").write_text("secret\n", encoding="utf-8")
        runner = FakeRunner(
            {
                ("git", "rev-parse", "--show-toplevel"): [ok([], str(root))],
                ("git", "check-ignore", "-q", ".codex/passphrase"): [fail([])],
            }
        )

        result = repo_flow.passphrase_file(config, str(config_path), root, runner)

        self.assertEqual(result["stop_reason"], "passphrase_file_not_ignored")

    def test_passphrase_file_reads_ignored_same_directory_secret(self):
        root, config_path, config = self.make_repo()
        (root / ".codex" / "passphrase").write_text("secret\n", encoding="utf-8")
        runner = FakeRunner(
            {
                ("git", "rev-parse", "--show-toplevel"): [ok([], str(root))],
                ("git", "check-ignore", "-q", ".codex/passphrase"): [ok([])],
            }
        )

        result = repo_flow.passphrase_file(config, str(config_path), root, runner)

        self.assertTrue(result["ok"])
        self.assertEqual(result["secret"], "secret")

    def test_passphrase_file_rejects_paths_outside_config_directory(self):
        root, config_path, config = self.make_repo()
        config["passphrase"] = "file:../passphrase"
        runner = FakeRunner({})

        result = repo_flow.passphrase_file(config, str(config_path), root, runner)

        self.assertEqual(result["stop_reason"], "passphrase_path_invalid")


if __name__ == "__main__":
    unittest.main()
