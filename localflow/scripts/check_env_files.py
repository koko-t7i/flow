#!/usr/bin/env -S uv run
#
# /// script
# requires-python = ">=3.10"
# ///
"""Inspect repository .env files without exposing values."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


sys.dont_write_bytecode = True

DEFAULT_MAX_DEPTH = 4
DEFAULT_TIMEOUT_SECONDS = 5
SKIP_DIRS = {
    ".git",
    ".mypy_cache",
    ".next",
    ".pytest_cache",
    ".tox",
    ".venv",
    "__pycache__",
    "build",
    "coverage",
    "dist",
    "node_modules",
    "venv",
}
TEMPLATE_MARKERS = {"example", "sample", "template"}
KEY_PATTERN = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")


def run_git(args: list[str], *, cwd: Path, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> tuple[bool, int | None, str, str]:
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False, None, "", ""
    return result.returncode == 0, result.returncode, result.stdout, result.stderr


def git_repo_root(cwd: Path) -> Path | None:
    ok, _, stdout, _ = run_git(["rev-parse", "--show-toplevel"], cwd=cwd)
    if not ok:
        return None
    return Path(stdout.strip()).resolve()


def posix_relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def relative_worktree_path(path: Path, root: Path) -> str:
    return Path(os.path.relpath(path.resolve(), start=root.resolve())).as_posix()


def is_env_filename(name: str) -> bool:
    return name == ".env" or name.startswith(".env.")


def is_template_filename(name: str) -> bool:
    if not is_env_filename(name) or name == ".env":
        return False
    return any(part in TEMPLATE_MARKERS for part in name.split(".")[2:])


def iter_env_paths(root: Path, max_depth: int = DEFAULT_MAX_DEPTH) -> list[Path]:
    paths: list[Path] = []
    root = root.resolve()
    for current, dirnames, filenames in os.walk(root):
        current_path = Path(current)
        relative = current_path.relative_to(root)
        depth = 0 if relative == Path(".") else len(relative.parts)

        dirnames[:] = sorted(name for name in dirnames if name not in SKIP_DIRS)
        if depth >= max_depth:
            dirnames[:] = []

        for filename in sorted(filenames):
            if not is_env_filename(filename):
                continue
            candidate = current_path / filename
            if candidate.is_file():
                paths.append(candidate)
    return sorted(paths, key=lambda item: posix_relative(item, root))


def extract_keys(path: Path) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return keys

    for line in lines:
        stripped = line.lstrip()
        if not stripped or stripped.startswith("#"):
            continue
        match = KEY_PATTERN.match(line)
        if not match:
            continue
        key = match.group(1)
        if key not in seen:
            seen.add(key)
            keys.append(key)
    return keys


def tracked_paths(root: Path) -> set[str]:
    ok, _, stdout, _ = run_git(["ls-files", "-z"], cwd=root)
    if not ok:
        return set()
    return {item for item in stdout.split("\0") if item}


def is_ignored(root: Path, relative_path: str) -> bool:
    _, exit_code, _, _ = run_git(["check-ignore", "--quiet", "--", relative_path], cwd=root)
    return exit_code == 0


def file_git_state(root: Path, relative_path: str, tracked: set[str], inside_git: bool) -> dict[str, object]:
    if not inside_git:
        return {"tracked": False, "ignored": False, "status": "unknown"}

    is_tracked = relative_path in tracked
    ignored = False if is_tracked else is_ignored(root, relative_path)
    if is_tracked:
        status = "tracked"
    elif ignored:
        status = "ignored"
    else:
        status = "untracked"
    return {"tracked": is_tracked, "ignored": ignored, "status": status}


def describe_env_file(path: Path, root: Path, tracked: set[str], inside_git: bool) -> dict[str, object]:
    relative_path = posix_relative(path, root)
    keys = extract_keys(path)
    return {
        "path": relative_path,
        **file_git_state(root, relative_path, tracked, inside_git),
        "key_count": len(keys),
        "keys": keys,
    }


def parse_worktree_entries(text: str) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    current: dict[str, object] = {}

    def flush() -> None:
        if current.get("path"):
            entries.append(dict(current))

    for line in [*text.splitlines(), ""]:
        if line.startswith("worktree "):
            flush()
            current = {"path": Path(line.split(" ", 1)[1]).resolve()}
        elif line.startswith("branch "):
            ref = line.split(" ", 1)[1]
            if ref.startswith("refs/heads/"):
                current["branch"] = ref.removeprefix("refs/heads/")
        elif not line:
            flush()
            current = {}
    return entries


def git_worktrees(root: Path) -> list[dict[str, object]]:
    ok, _, stdout, _ = run_git(["worktree", "list", "--porcelain"], cwd=root)
    if not ok:
        return []
    return sorted(parse_worktree_entries(stdout), key=lambda item: str(item["path"]))


def sibling_candidates(root: Path, max_depth: int) -> list[dict[str, object]]:
    candidates: dict[str, dict[str, object]] = {}
    current_root = root.resolve()

    for worktree in git_worktrees(root):
        worktree_root = Path(worktree["path"]).resolve()
        if worktree_root == current_root or not worktree_root.exists():
            continue

        source_tracked = tracked_paths(worktree_root)
        for path in iter_env_paths(worktree_root, max_depth=max_depth):
            if is_template_filename(path.name):
                continue
            relative_path = posix_relative(path, worktree_root)
            if not (current_root / Path(relative_path).parent).is_dir():
                continue
            if (current_root / relative_path).exists():
                continue

            source = describe_env_file(path, worktree_root, source_tracked, True)
            source.pop("path", None)
            source["worktree"] = relative_worktree_path(worktree_root, current_root)
            if worktree.get("branch"):
                source["branch"] = worktree["branch"]

            candidate = candidates.setdefault(relative_path, {"path": relative_path, "sources": []})
            candidate["sources"].append(source)  # type: ignore[union-attr]

    result = list(candidates.values())
    for candidate in result:
        candidate["sources"] = sorted(candidate["sources"], key=lambda item: str(item["worktree"]))  # type: ignore[index]
    return sorted(result, key=lambda item: str(item["path"]))


def build_warnings(env_files: list[dict[str, object]], candidates: list[dict[str, object]]) -> list[dict[str, object]]:
    warnings: list[dict[str, object]] = []
    for item in env_files:
        path = str(item["path"])
        if item["tracked"]:
            warnings.append({"kind": "tracked_env_file", "path": path})
        if item["status"] == "untracked":
            warnings.append({"kind": "unignored_env_file", "path": path})

    for candidate in candidates:
        warnings.append(
            {
                "kind": "missing_sibling_env_file",
                "path": candidate["path"],
                "sources": [source["worktree"] for source in candidate["sources"]],  # type: ignore[index]
            }
        )
    return sorted(warnings, key=lambda item: (str(item["kind"]), str(item["path"])))


def check_repository(cwd: Path, max_depth: int = DEFAULT_MAX_DEPTH) -> dict[str, object]:
    cwd = cwd.resolve()
    if not cwd.exists():
        return {"ok": False, "error": "cwd_not_found", "warnings": [{"kind": "cwd_not_found"}]}
    if not cwd.is_dir():
        return {"ok": False, "error": "cwd_not_directory", "warnings": [{"kind": "cwd_not_directory"}]}

    repo_root = git_repo_root(cwd)
    inside_git = repo_root is not None
    root = repo_root or cwd
    tracked = tracked_paths(root) if inside_git else set()

    env_files: list[dict[str, object]] = []
    templates: list[dict[str, object]] = []
    for path in iter_env_paths(root, max_depth=max_depth):
        item = describe_env_file(path, root, tracked, inside_git)
        if is_template_filename(path.name):
            templates.append(item)
        else:
            env_files.append(item)

    candidates = sibling_candidates(root, max_depth) if inside_git else []
    warnings = build_warnings(env_files, candidates)
    if not inside_git:
        warnings.append({"kind": "not_git_repository"})

    return {
        "ok": True,
        "schema_version": 1,
        "scan": {"root": ".", "max_depth": max_depth},
        "git": {"inside_work_tree": inside_git, "worktree_count": len(git_worktrees(root)) if inside_git else 0},
        "summary": {
            "env_file_count": len(env_files),
            "template_count": len(templates),
            "sibling_candidate_count": len(candidates),
            "warning_count": len(warnings),
        },
        "env_files": env_files,
        "templates": templates,
        "sibling_candidates": candidates,
        "warnings": warnings,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Inspect repository .env files without printing values.")
    parser.add_argument("--cwd", type=Path, default=Path.cwd(), help="Repository or subdirectory to inspect.")
    parser.add_argument("--max-depth", type=int, default=DEFAULT_MAX_DEPTH, help="Maximum directory depth to scan.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = check_repository(args.cwd, max_depth=args.max_depth)
    json.dump(payload, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
