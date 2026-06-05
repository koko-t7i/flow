import tempfile
import unittest
from pathlib import Path

from helpers import REPO_ROOT, load_script


SCRIPT_PATH = REPO_ROOT / "localflow" / "scripts" / "check_environment.py"


def load_module():
    return load_script("check_environment")


class CheckEnvironmentTest(unittest.TestCase):
    def test_redact_masks_tokens_and_secret_like_values(self):
        module = load_module()

        text = "Token: gho_abcdef123456\npassword=my-secret\nauth_header=Bearer abc.def"

        redacted = module.redact(text)

        self.assertNotIn("gho_abcdef123456", redacted)
        self.assertNotIn("my-secret", redacted)
        self.assertNotIn("abc.def", redacted)
        self.assertIn("<redacted>", redacted)

    def test_classify_git_remote_failure_splits_ssh_auth_cases(self):
        module = load_module()

        self.assertEqual(module.classify_git_remote_failure("Permission denied (publickey)."), "ssh_publickey")
        self.assertEqual(
            module.classify_git_remote_failure("Could not open a connection to your authentication agent."),
            "ssh_agent_missing",
        )
        self.assertEqual(
            module.classify_git_remote_failure("Enter passphrase for key '/home/user/.ssh/id_rsa':"),
            "ssh_interactive_passphrase_required",
        )
        self.assertEqual(module.classify_git_remote_failure("Could not resolve hostname github.com"), "remote_unreachable")

    def test_missing_command_probe_is_not_installed(self):
        module = load_module()

        probe = module.probe_command("definitely-not-a-localflow-command", ["--version"])

        self.assertIs(probe["installed"], False)
        self.assertIs(probe["configured"], False)
        self.assertIsNone(probe["auth_ok"])
        self.assertIsNone(probe["permission_ok"])

    def test_api_user_summary_keeps_only_identity_fields(self):
        module = load_module()

        summary = module.api_user_summary(
            '{"login":"koko-t7i","username":"koko","email":"person@example.com","token":"secret"}'
        )

        self.assertEqual(summary, {"login": "koko-t7i", "username": "koko"})

    def test_render_markdown_includes_sudo_status(self):
        module = load_module()

        markdown = module.render_markdown(
            {
                "generated_at": "2026-05-26T00:00:00+00:00",
                "cwd": "/tmp/repo",
                "tools": {
                    "docker": {
                        "installed": True,
                        "configured": True,
                        "auth_ok": None,
                        "permission_ok": False,
                        "sudo_permission_ok": True,
                        "version": "Docker version 29.2.0",
                    }
                },
            }
        )

        self.assertIn("Sudo OK", markdown)
        self.assertIn("| docker | yes | yes | n/a | no | yes | Docker version 29.2.0 |", markdown)

    def test_render_markdown_prefers_configured_passphrase_or_cli_fallback(self):
        module = load_module()

        markdown = module.render_markdown(
            {
                "generated_at": "2026-05-26T00:00:00+00:00",
                "cwd": "/tmp/repo",
                "tools": {
                    "git": {
                        "origin": {"host": "github.com", "protocol": "ssh"},
                        "origin_check": {"can_fetch": False, "failure_kind": "ssh_interactive_passphrase_required"},
                        "ssh_agent": {"available": False},
                    }
                },
            }
        )

        self.assertIn("configured ignored passphrase file", markdown)
        self.assertIn("authenticated `gh`/`glab`", markdown)
        self.assertNotIn("ssh-add", markdown)
        self.assertNotIn("unlock", markdown.lower())

    def test_default_cache_dir_is_neutral(self):
        module = load_module()

        self.assertEqual(module.CACHE_DIR, Path.home() / ".cache" / "localflow")
        self.assertEqual(module.LEGACY_CACHE_DIR, Path.home() / ".cache" / "codex-localflow")
        self.assertEqual(module.DEFAULT_JSON_PATH, module.CACHE_DIR / "environment.json")
        self.assertEqual(module.DEFAULT_MARKDOWN_PATH, module.CACHE_DIR / "environment.md")

    def test_migrate_legacy_cache_moves_files_and_removes_empty_dir(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            legacy = base / "codex-localflow"
            new = base / "localflow"
            legacy.mkdir()
            (legacy / "environment.json").write_text("{}", encoding="utf-8")

            migrated = module.migrate_legacy_cache(legacy_dir=legacy, new_dir=new)

            self.assertTrue(migrated)
            self.assertFalse(legacy.exists())
            self.assertTrue((new / "environment.json").exists())

    def test_migrate_legacy_cache_is_noop_when_new_dir_exists(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            legacy = base / "codex-localflow"
            new = base / "localflow"
            legacy.mkdir()
            new.mkdir()
            (legacy / "environment.json").write_text("legacy", encoding="utf-8")

            migrated = module.migrate_legacy_cache(legacy_dir=legacy, new_dir=new)

            self.assertFalse(migrated)
            self.assertTrue((legacy / "environment.json").exists())

    def test_migrate_legacy_cache_is_noop_when_legacy_missing(self):
        module = load_module()
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            legacy = base / "codex-localflow"
            new = base / "localflow"

            migrated = module.migrate_legacy_cache(legacy_dir=legacy, new_dir=new)

            self.assertFalse(migrated)
            self.assertFalse(new.exists())
