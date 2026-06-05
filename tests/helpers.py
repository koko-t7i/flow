import importlib.util
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = REPO_ROOT / "localflow" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def load_script(name: str):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS_DIR / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


repo_flow = load_script("repo_flow")


class FakeRunner:
    def __init__(self, responses):
        self.responses = {key: list(value) for key, value in responses.items()}
        self.calls = []

    def __call__(self, args, *, cwd, timeout=30, shell=False, env=None):
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
