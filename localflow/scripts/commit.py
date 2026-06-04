#!/usr/bin/env -S uv run
#
# /// script
# requires-python = ">=3.10"
# ///
"""Commit the current task's scoped --paths and optionally open the review in one step."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

import mr
import repo_flow as flow


def run_commit(
    cwd: Path,
    host: str,
    *,
    paths: list[str],
    message: str,
    body: str | None = None,
    open_mr: bool = False,
    runner=flow.run_command,
) -> dict[str, object]:
    """Stage ONLY the named task --paths, write a Conventional Commit, and (with
    --mr) open the review via the normal mr flow.

    Built for the default isolated-worktree delivery path. The shared-checkout /
    multi-agent path uses `mr --snapshot` instead, which never touches the worktree.
    """
    try:
        config, config_path = flow.load_repo_config(cwd, host, runner)
    except RuntimeError as exc:
        return flow.stop("not_git_repo", str(exc))
    root = flow.repo_root(cwd, runner)

    # Validate everything BEFORE any git write so we never half-stage.
    branch = flow.current_branch(root, runner)
    if not branch:
        return flow.stop("detached_head", "Current checkout is detached; localflow commit needs a named task branch.")
    if branch in flow.LONG_LIVED_BRANCHES:
        return flow.stop(
            "long_lived_branch",
            f"Refusing to commit task work directly onto long-lived branch {branch}.",
        )
    subject_error = flow.validate_commit_subject(message)
    if subject_error:
        return flow.stop("invalid_commit_message", subject_error)
    if not paths:
        return flow.stop("paths_required", "localflow commit requires --paths to scope the task files.")
    for path in paths:
        if flow.is_ignored(root, path, runner):
            return flow.stop("ignored_path_staged", f"Refusing to stage a git-ignored path: {path}")

    # Stage ONLY the named paths — never `git add .`.
    added = runner(["git", "add", "--", *paths], cwd=root)
    if not added.ok:
        return flow.stop("stage_failed", f"git add failed: {added.stderr}")
    # `git diff --cached --quiet` exits 0 when the index has no staged changes.
    staged = runner(["git", "diff", "--cached", "--quiet"], cwd=root)
    if staged.ok:
        return flow.stop("nothing_staged", "No staged changes in --paths; nothing to commit.")

    full_message = f"{message}\n\n{body.strip()}" if body else message
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as message_file:
        message_file.write(full_message)
        message_path = message_file.name
    try:
        committed = runner(["git", "commit", "-F", message_path], cwd=root)
    finally:
        Path(message_path).unlink(missing_ok=True)
    if not committed.ok:
        return flow.stop("commit_failed", f"git commit failed: {committed.stderr}")

    commit_data: dict[str, object] = {
        "ok": True,
        "action": "committed",
        "branch": branch,
        "head_sha": flow.head_sha(root, runner),
        "staged_files": list(paths),
        "message": message,
        "config_path": config_path,
    }

    if not open_mr:
        json_path, md_path = flow.write_outputs("commit", commit_data)
        return {**commit_data, "json_path": str(json_path), "markdown_path": str(md_path)}

    # One-shot: chain into the normal review flow. The commit is real and correct,
    # so a failing mr does NOT roll it back — surface mr's stop and keep the commit.
    mr_result = mr.run(root, host, runner)
    data: dict[str, object] = {**mr_result, "commit": commit_data}
    if "json_path" not in data:
        json_path, md_path = flow.write_outputs("commit", data)
        data = {**data, "json_path": str(json_path), "markdown_path": str(md_path)}
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", default=".", help="Repository working directory")
    parser.add_argument("--host", choices=("codex", "claude"), default="codex")
    parser.add_argument("--paths", nargs="+", default=[], help="Task files to stage (only these are committed)")
    parser.add_argument("--message", help="Full Conventional Commit subject")
    parser.add_argument("--type", help="Conventional Commit type (used with --summary)")
    parser.add_argument("--scope", help="Conventional Commit scope (used with --type/--summary)")
    parser.add_argument("--summary", help="Imperative summary (used with --type)")
    parser.add_argument("--body", help="Optional commit/MR body")
    parser.add_argument("--breaking", action="store_true", help="Mark the change as breaking (appends '!')")
    parser.add_argument(
        "--mr",
        action="store_true",
        dest="open_mr",
        help="After committing, open the review via the normal mr flow (commit + push + MR in one step).",
    )
    args = parser.parse_args()

    cwd = Path(args.cwd).resolve()
    message = mr.compose_message(args)
    if not message:
        data = flow.stop("commit_message_required", "localflow commit requires --message or --type with --summary.")
    elif not args.paths:
        data = flow.stop("paths_required", "localflow commit requires --paths to scope the task files.")
    else:
        data = run_commit(
            cwd,
            args.host,
            paths=args.paths,
            message=message,
            body=args.body,
            open_mr=args.open_mr,
        )

    if "json_path" not in data:
        json_path, md_path = flow.write_outputs("commit", data)
        data = {**data, "json_path": str(json_path), "markdown_path": str(md_path)}
    flow.print_summary(data)
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
