import unittest

from helpers import SCRIPTS_DIR


class SubcommandBytecodeTest(unittest.TestCase):
    def test_delivery_subcommands_disable_bytecode_before_local_imports(self):
        for script_name in ("clean.py", "mr.py", "commit.py", "fast.py"):
            with self.subTest(script=script_name):
                text = (SCRIPTS_DIR / script_name).read_text(encoding="utf-8")
                bytecode_index = text.index("sys.dont_write_bytecode = True")
                helper_import_index = min(
                    index
                    for needle in ("import lifecycle", "import repo_flow")
                    if (index := text.find(needle)) != -1
                )

                self.assertLess(bytecode_index, helper_import_index)


if __name__ == "__main__":
    unittest.main()
