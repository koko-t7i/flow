#!/usr/bin/env -S uv run
#
# /// script
# requires-python = ">=3.10"
# ///
"""Clean a localflow delivery unit after it has landed."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import repo_flow as flow


def worktree_state(cwd: Path, runner=flow.run_command) -> dict[str, object]:
    root = flow.repo_root(cwd, runner)
    git_dir = runner(["git", "rev-parse", "--git-dir"], cwd=root)
    common_dir = runner(["git", "rev-parse", "--git-common-dir"], cwd=root)
    if not git_dir.ok or not common_dir.ok:
        return flow.stop("git_dir_unknown", "Could not inspect git worktree metadata.")
    git_path = (root / git_dir.stdout).resolve() if not Path(git_dir.stdout).is_absolute() else Path(git_dir.stdout).resolve()
    common_path = (
        (root / common_dir.stdout).resolve()
        if not Path(common_dir.stdout).is_absolute()
        else Path(common_dir.stdout).resolve()
    )
    linked = git_path != common_path
    return {"ok": True, "root": root, "git_dir": git_path, "common_dir": common_path, "linked": linked}


def owned_worktree(path: Path) -> bool:
    parts = path.parts
    home_superpowers = Path.home() / ".config" / "superpowers" / "worktrees"
    return path.is_relative_to(home_superpowers) or ".worktrees" in parts or "worktrees" in parts


def main_checkout_root(common_dir: Path, runner=flow.run_command) -> Path:
    result = runner(["git", "rev-parse", "--show-toplevel"], cwd=common_dir.parent)
    if not result.ok:
        raise RuntimeError("could not resolve main checkout")
    return Path(result.stdout)


def cleanup_local(
    cwd: Path,
    branch: str,
    base_name: str,
    landed_by: str,
    runner=flow.run_command,
) -> tuple[bool, list[dict[str, object]], str | None]:
    steps: list[dict[str, object]] = []
    state = worktree_state(cwd, runner)
    if not state.get("ok"):
        return False, steps, str(state.get("stop_reason"))
    root = Path(state["root"])

    if state["linked"]:
        if not owned_worktree(root):
            return False, steps, "worktree_ownership_unknown"
        try:
            main_root = main_checkout_root(Path(state["common_dir"]), runner)
        except RuntimeError:
            return False, steps, "main_checkout_unknown"
        if not flow.is_clean_worktree(main_root, runner):
            return False, steps, "main_checkout_dirty"
        checkout = runner(["git", "checkout", base_name], cwd=main_root)
        steps.append({"command": flow.command_text(checkout.args), "ok": checkout.ok, "stderr": checkout.stderr})
        if not checkout.ok:
            return False, steps, "base_checkout_failed"
        remove = runner(["git", "worktree", "remove", str(root)], cwd=main_root)
        steps.append({"command": flow.command_text(remove.args), "ok": remove.ok, "stderr": remove.stderr})
        if not remove.ok:
            return False, steps, "worktree_remove_failed"
        delete_flag = "-D" if landed_by == "remote_review" else "-d"
        delete = runner(["git", "branch", delete_flag, branch], cwd=main_root)
        steps.append({"command": flow.command_text(delete.args), "ok": delete.ok, "stderr": delete.stderr})
        if not delete.ok:
            return False, steps, "local_branch_delete_failed"
        prune = runner(["git", "worktree", "prune"], cwd=main_root)
        steps.append({"command": flow.command_text(prune.args), "ok": prune.ok, "stderr": prune.stderr})
        return prune.ok, steps, None if prune.ok else "worktree_prune_failed"

    checkout = runner(["git", "checkout", base_name], cwd=root)
    steps.append({"command": flow.command_text(checkout.args), "ok": checkout.ok, "stderr": checkout.stderr})
    if not checkout.ok:
        return False, steps, "base_checkout_failed"
    delete_flag = "-D" if landed_by == "remote_review" else "-d"
    delete = runner(["git", "branch", delete_flag, branch], cwd=root)
    steps.append({"command": flow.command_text(delete.args), "ok": delete.ok, "stderr": delete.stderr})
    return delete.ok, steps, None if delete.ok else "local_branch_delete_failed"


def run(cwd: Path, host: str, runner=flow.run_command) -> dict[str, object]:
    try:
        config, config_path = flow.load_repo_config(cwd, host, runner)
    except RuntimeError as exc:
        return flow.stop("not_git_repo", str(exc))

    root = flow.repo_root(cwd, runner)
    branch = flow.current_branch(root, runner)
    if not branch:
        return flow.stop("detached_head", "Current checkout is detached; localflow clean needs a named task branch.")
    if branch in flow.LONG_LIVED_BRANCHES:
        return flow.stop("long_lived_branch", f"Refusing to clean long-lived branch {branch}.")
    if not flow.is_clean_worktree(root, runner):
        return flow.stop("dirty_worktree", "Worktree or staged area is not clean; clean will not delete dirty work.")

    base_result = flow.resolve_base_branch(root, config, runner)
    if not base_result.get("name"):
        return base_result
    base_name = str(base_result["name"])
    base_ref = str(base_result["ref"])
    head = flow.head_sha(root, runner)

    mr_config = flow.section(config, "mr")
    remote = str(mr_config.get("remote") or "origin")
    url = flow.remote_url(root, remote, runner)
    provider_result = flow.resolve_provider(config, url)
    provider = str(provider_result.get("provider") or "")
    review = flow.find_review(root, provider, branch, runner) if provider else None

    landed_by = "local_landing"
    if review:
        if flow.normalize_review_state(review) != "merged":
            return flow.stop("review_not_merged", "MR/PR is not merged; localflow clean will not clean it.")
        if head and review.get("headRefOid") and str(review["headRefOid"]) != head:
            return flow.stop("head_sha_mismatch", "Local HEAD does not match the merged MR/PR head SHA.")
        fetch = runner(["git", "fetch", remote, base_name], cwd=root, timeout=120)
        if not fetch.ok:
            return flow.stop("base_fetch_failed", "Could not fetch the base branch after MR/PR merge.", stderr=fetch.stderr)
        landed_by = "remote_review"
    else:
        ancestor = runner(["git", "merge-base", "--is-ancestor", "HEAD", base_ref], cwd=root)
        if not ancestor.ok:
            return flow.stop("review_not_merged", "No merged MR/PR found and the task branch is not merged into base.")

    cleanup_setting = str(flow.section(config, "delivery").get("cleanup_remote_branch") or "auto").lower()
    remote_cleanup: dict[str, object] = {"skipped": cleanup_setting in {"false", "never", "no"}}
    if not remote_cleanup["skipped"]:
        deleted = flow.delete_remote_branch(root, remote, branch, url, runner)
        remote_cleanup = {
            "ok": deleted.ok,
            "command": flow.command_text(deleted.args),
            "stderr": deleted.stderr,
        }
        if not deleted.ok:
            return flow.stop("remote_branch_delete_failed", "Could not delete the remote task branch.", remote_cleanup=remote_cleanup)

    ok, local_steps, reason = cleanup_local(root, branch, base_name, landed_by, runner)
    if not ok:
        return flow.stop(reason or "local_cleanup_failed", "Local cleanup failed.", local_steps=local_steps)

    data = {
        "ok": True,
        "action": "cleaned",
        "provider": provider or None,
        "base_branch": base_name,
        "branch": branch,
        "url": (review or {}).get("url"),
        "state": "merged" if review else "local_landed",
        "landed_by": landed_by,
        "remote_cleanup": remote_cleanup,
        "local_steps": local_steps,
        "config_path": config_path,
    }
    json_path, md_path = flow.write_outputs("clean", data)
    return {**data, "json_path": str(json_path), "markdown_path": str(md_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", default=".", help="Repository working directory")
    parser.add_argument("--host", choices=("codex", "claude"), default="codex")
    args = parser.parse_args()
    data = run(Path(args.cwd).resolve(), args.host)
    if "json_path" not in data:
        json_path, md_path = flow.write_outputs("clean", data)
        data = {**data, "json_path": str(json_path), "markdown_path": str(md_path)}
    flow.print_summary(data)
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
