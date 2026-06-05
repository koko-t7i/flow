"""Shared lifecycle helpers for localflow delivery modes."""

from __future__ import annotations

from pathlib import Path

import repo_flow as flow


def worktree_state(cwd: Path, runner=flow.run_command) -> dict[str, object]:
    root = flow.repo_root(cwd, runner)
    git_dir = runner(["git", "rev-parse", "--git-dir"], cwd=root)
    common_dir = runner(["git", "rev-parse", "--git-common-dir"], cwd=root)
    if not git_dir.ok or not common_dir.ok:
        return flow.stop("git_dir_unknown", "Could not inspect git worktree metadata.")
    git_path = (
        (root / git_dir.stdout).resolve()
        if not Path(git_dir.stdout).is_absolute()
        else Path(git_dir.stdout).resolve()
    )
    common_path = (
        (root / common_dir.stdout).resolve()
        if not Path(common_dir.stdout).is_absolute()
        else Path(common_dir.stdout).resolve()
    )
    return {
        "ok": True,
        "root": root,
        "git_dir": git_path,
        "common_dir": common_path,
        "linked": git_path != common_path,
    }


def owned_worktree(path: Path) -> bool:
    parts = path.parts
    home_superpowers = Path.home() / ".config" / "superpowers" / "worktrees"
    return path.is_relative_to(home_superpowers) or ".worktrees" in parts or "worktrees" in parts


def main_checkout_root(common_dir: Path, runner=flow.run_command) -> Path:
    result = runner(["git", "rev-parse", "--show-toplevel"], cwd=common_dir.parent)
    if not result.ok:
        raise RuntimeError("could not resolve main checkout")
    return Path(result.stdout)


def require_clean_task_branch(root: Path, command_name: str, runner=flow.run_command) -> dict[str, object]:
    branch = flow.current_branch(root, runner)
    if not branch:
        return flow.stop("detached_head", f"Current checkout is detached; localflow {command_name} needs a named task branch.")
    if branch in flow.LONG_LIVED_BRANCHES:
        return flow.stop(
            "long_lived_branch",
            f"Refusing to run localflow {command_name} directly on long-lived branch {branch}.",
        )
    if not flow.is_clean_worktree(root, runner):
        return flow.stop("dirty_worktree", "Worktree or staged area is not clean; commit or discard changes first.")
    return {"ok": True, "branch": branch}


def linked_main_checkout(root: Path, runner=flow.run_command) -> dict[str, object]:
    state = worktree_state(root, runner)
    if not state.get("ok"):
        return state
    if not state["linked"]:
        return flow.stop("worktree_required", "localflow fast requires an isolated linked worktree.")
    if not owned_worktree(root):
        return flow.stop("worktree_ownership_unknown", "Current worktree is not owned by localflow.")
    try:
        main_root = main_checkout_root(Path(state["common_dir"]), runner)
    except RuntimeError:
        return flow.stop("main_checkout_unknown", "Could not resolve the main checkout for this worktree.")
    return {**state, "main_root": main_root}


def checkout_base(main_root: Path, base_name: str, runner=flow.run_command) -> dict[str, object]:
    if not flow.is_clean_worktree(main_root, runner):
        return flow.stop("main_checkout_dirty", "Main checkout is dirty; cannot switch or merge the base branch.")
    checkout = runner(["git", "checkout", base_name], cwd=main_root)
    step = {"command": flow.command_text(checkout.args), "ok": checkout.ok, "stderr": checkout.stderr}
    if not checkout.ok:
        return flow.stop("base_checkout_failed", "Could not checkout the local base branch.", base_step=step)
    return {"ok": True, "base_step": step}


def sync_local_base(main_root: Path, remote: str, base_name: str, runner=flow.run_command) -> dict[str, object]:
    """Fetch remote base and fast-forward local base when possible.

    Local base may already be ahead of remote after earlier fast landings; that
    is allowed. Divergence is not.
    """
    if not flow.ref_exists(main_root, base_name, runner):
        return flow.stop("base_branch_missing", f"Local base branch does not exist: {base_name}")

    fetch = flow.fetch_branch(main_root, remote, base_name, runner)
    fetch_step = {"command": flow.command_text(fetch.args), "ok": fetch.ok, "stderr": fetch.stderr}
    if not fetch.ok:
        return flow.stop("base_fetch_failed", "Could not fetch the base branch before local landing.", base_step=fetch_step)

    remote_ref = f"{remote}/{base_name}"
    if not flow.ref_exists(main_root, remote_ref, runner):
        return flow.stop("base_branch_missing", f"Remote base branch does not exist: {remote_ref}", base_step=fetch_step)

    local_ancestor = runner(["git", "merge-base", "--is-ancestor", base_name, remote_ref], cwd=main_root)
    remote_ancestor = runner(["git", "merge-base", "--is-ancestor", remote_ref, base_name], cwd=main_root)

    checkout = checkout_base(main_root, base_name, runner)
    if not checkout.get("ok"):
        return {**checkout, "base_fetch_step": fetch_step}

    if local_ancestor.ok:
        merge = runner(["git", "merge", "--ff-only", remote_ref], cwd=main_root)
        merge_step = {"command": flow.command_text(merge.args), "ok": merge.ok, "stderr": merge.stderr}
        if not merge.ok:
            return flow.stop("base_fast_forward_failed", "Could not fast-forward local base branch.", base_step=merge_step)
        return {
            "ok": True,
            "remote_ref": remote_ref,
            "base_sync": "fast_forwarded",
            "base_fetch_step": fetch_step,
            "base_checkout_step": checkout.get("base_step"),
            "base_merge_step": merge_step,
        }

    if remote_ancestor.ok:
        return {
            "ok": True,
            "remote_ref": remote_ref,
            "base_sync": "already_ahead_or_equal",
            "base_fetch_step": fetch_step,
            "base_checkout_step": checkout.get("base_step"),
        }

    return flow.stop("base_diverged", f"Local {base_name} and {remote_ref} have diverged; manual integration is required.")


def left_right_count(cwd: Path, left_ref: str, right_ref: str, runner=flow.run_command) -> dict[str, int | None]:
    result = runner(["git", "rev-list", "--left-right", "--count", f"{left_ref}...{right_ref}"], cwd=cwd)
    if not result.ok:
        return {"left": None, "right": None}
    parts = result.stdout.split()
    if len(parts) != 2:
        return {"left": None, "right": None}
    try:
        return {"left": int(parts[0]), "right": int(parts[1])}
    except ValueError:
        return {"left": None, "right": None}
