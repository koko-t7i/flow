#!/usr/bin/env -S uv run
#
# /// script
# requires-python = ">=3.10"
# ///
"""Land the current localflow task branch into the local base branch without cleanup."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.dont_write_bytecode = True

import lifecycle
import repo_flow as flow


def run(cwd: Path, host: str, runner=flow.run_command) -> dict[str, object]:
    context = lifecycle.load_task_context(cwd, host, "fast", runner)
    if not context.get("ok"):
        return context
    config = context["config"]  # type: ignore[assignment]
    config_path = context["config_path"]
    root = Path(context["root"])
    branch = str(context["branch"])

    worktree = lifecycle.linked_main_checkout(root, runner)
    if not worktree.get("ok"):
        return worktree
    main_root = Path(worktree["main_root"])

    base_result = flow.resolve_base_branch(root, config, runner)
    if not base_result.get("name"):
        return base_result
    base_name = str(base_result["name"])

    remote = flow.DEFAULT_REMOTE
    base_sync = lifecycle.sync_local_base(main_root, remote, base_name, runner, config=config, config_path=config_path)
    if not base_sync.get("ok"):
        return base_sync
    remote_ref = str(base_sync["remote_ref"])

    rebase = runner(["git", "rebase", base_name], cwd=root, timeout=120)
    rebase_step = {"command": flow.command_text(rebase.args), "ok": rebase.ok, "stderr": rebase.stderr}
    if not rebase.ok:
        return flow.stop("rebase_failed", "Could not rebase task branch onto the local base branch.", rebase_step=rebase_step)

    ahead = flow.commits_ahead(root, base_name, runner)
    if not ahead:
        return flow.stop("no_branch_commits", f"Branch {branch} has no commits ahead of {base_name}.", rebase_step=rebase_step)

    if not flow.is_clean_worktree(root, runner):
        return flow.stop("dirty_after_rebase", "Task worktree is dirty after rebase; local landing stopped.")

    head = flow.head_sha(root, runner)
    merge = runner(["git", "merge", "--ff-only", branch], cwd=main_root, timeout=120)
    merge_step = {"command": flow.command_text(merge.args), "ok": merge.ok, "stderr": merge.stderr}
    if not merge.ok:
        return flow.stop("local_merge_failed", "Could not fast-forward merge the task branch into local base.", merge_step=merge_step)

    counts = lifecycle.left_right_count(main_root, remote_ref, base_name, runner)
    common = {
        "action": "fast_landed",
        "base_branch": base_name,
        "branch": branch,
        "head_sha": head,
        "base_sync": base_sync.get("base_sync"),
        "base_ahead_remote": counts["right"],
        "base_behind_remote": counts["left"],
        "cleanup": "not_run",
        "cleanup_hint": "Run localflow clean after reviewing the landed task branch/worktree.",
        "config_path": config_path,
        "rebase_step": rebase_step,
        "merge_step": merge_step,
    }
    data = {"ok": True, **common}
    return flow.attach_outputs("fast", data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", default=".", help="Repository working directory")
    parser.add_argument("--host", choices=("codex", "claude", "pi"), default="codex")
    args = parser.parse_args()
    data = run(Path(args.cwd).resolve(), args.host)
    return flow.finish_command("fast", data)


if __name__ == "__main__":
    sys.exit(main())
