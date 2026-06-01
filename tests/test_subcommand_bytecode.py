import unittest
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "localflow" / "scripts"


class SubcommandBytecodeTest(unittest.TestCase):
    def test_delivery_subcommands_disable_bytecode_before_local_imports(self):
        for script_name in ("clean.py", "mr.py"):
            with self.subTest(script=script_name):
                text = (SCRIPTS_DIR / script_name).read_text(encoding="utf-8")
                bytecode_index = text.index("sys.dont_write_bytecode = True")
                helper_import_index = text.index("import repo_flow")

                self.assertLess(bytecode_index, helper_import_index)


if __name__ == "__main__":
    unittest.main()
