import importlib.util
import re
import sys
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "localflow" / "scripts"
CONFIG_DOC = REPO_ROOT / "localflow" / "references" / "config.md"
sys.path.insert(0, str(SCRIPTS_DIR))


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


repo_flow = load_script("repo_flow")


def canonical_template() -> str:
    text = CONFIG_DOC.read_text(encoding="utf-8")
    match = re.search(r"```toml\n(.*?)```", text, re.DOTALL)
    assert match, "references/config.md must contain a ```toml canonical template"
    return match.group(1)


class ConfigTemplateTest(unittest.TestCase):
    def _assert_keys(self, config):
        self.assertEqual(config.get("version"), 1)
        self.assertEqual(config.get("base_branch"), "main")
        self.assertEqual(config.get("delivery_mode"), "remote_review")
        self.assertEqual(repo_flow.section(config, "delivery")["remote_provider"], "github")
        self.assertEqual(repo_flow.section(config, "mr")["remote"], "origin")
        self.assertEqual(repo_flow.section(config, "mr")["draft"], False)
        self.assertEqual(repo_flow.section(config, "version_policy")["enabled"], False)
        self.assertEqual(repo_flow.section(config, "version_policy")["files"], [])

    def test_template_parses_via_tomllib(self):
        # parse_toml_text uses the stdlib tomllib (strict TOML) when available.
        self._assert_keys(repo_flow.parse_toml_text(canonical_template()))

    def test_template_parses_via_simple_parser(self):
        # The hand-rolled fallback must also handle the documented schema.
        self._assert_keys(repo_flow.parse_simple_toml(canonical_template()))


if __name__ == "__main__":
    unittest.main()
