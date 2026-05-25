import importlib.util
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "localflow" / "scripts" / "check_environment.py"


def load_module():
    spec = importlib.util.spec_from_file_location("check_environment", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


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
