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

sys.dont_write_bytecode = True

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


def ref_names(cwd: Path, namespace: str, runner=flow.run_command) -> list[str] | None:
    result = runner(["git", "for-each-ref", "--format=%(refname:short)", namespace], cwd=cwd)
    if not result.ok:
        return None
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def remote_branch_names(cwd: Path, remote: str, runner=flow.run_command) -> list[str] | None:
    refs = ref_names(cwd, f"refs/remotes/{remote}", runner)
    if refs is None:
        return None
    prefix = f"{remote}/"
    branches = []
    for ref in refs:
        if ref == f"{remote}/HEAD" or not ref.startswith(prefix):
            continue
        branches.append(ref[len(prefix) :])
    return branches


def parse_worktree_entries(text: str) -> dict[str, dict[str, object]]:
    entries: dict[str, dict[str, object]] = {}
    current: dict[str, object] = {}

    def flush() -> None:
        branch = current.get("branch")
        if branch:
            entries[str(branch)] = dict(current)

    for line in [*text.splitlines(), ""]:
        if line.startswith("worktree "):
            flush()
            current = {"path": Path(line.split(" ", 1)[1])}
        elif line.startswith("HEAD "):
            current["head"] = line.split(" ", 1)[1]
        elif line.startswith("branch "):
            ref = line.split(" ", 1)[1]
            if ref.startswith("refs/heads/"):
                current["branch"] = ref.removeprefix("refs/heads/")
        elif not line:
            flush()
            current = {}
    return entries


def worktree_entries(cwd: Path, runner=flow.run_command) -> dict[str, dict[str, object]] | None:
    result = runner(["git", "worktree", "list", "--porcelain"], cwd=cwd)
    if not result.ok:
        return None
    return parse_worktree_entries(result.stdout)


def ref_sha(cwd: Path, ref: str, runner=flow.run_command) -> str | None:
    result = runner(["git", "rev-parse", ref], cwd=cwd)
    return flow.first_line(result.stdout) if result.ok else None


def skip(branch: str, reason: str, state: str | None = None) -> dict[str, object]:
    data: dict[str, object] = {"branch": branch, "reason": reason}
    if state:
        data["state"] = state
    return data


def cleanup_scanned_candidate(
    root: Path,
    branch: str,
    *,
    base_ref: str,
    provider: str,
    remote: str,
    url: str | None,
    local_exists: bool,
    remote_exists: bool,
    worktree: dict[str, object] | None,
    cleanup_remote: bool,
    runner=flow.run_command,
) -> tuple[str, dict[str, object], str | None]:
    local_sha = ref_sha(root, branch, runner) if local_exists else None
    remote_sha = ref_sha(root, f"{remote}/{branch}", runner) if remote_exists else None
    candidate_sha = local_sha or remote_sha or (str(worktree.get("head")) if worktree else None)

    review = flow.find_review(root, provider, branch, runner) if provider else None
    landed_by = "local_landing"
    state = "local_landed"
    review_url = None
    delete_flag = "-d"

    if review:
        state = flow.normalize_review_state(review) or "unknown"
        review_url = str(review.get("url") or "") or None
        if state != "merged":
            return "skipped", skip(branch, "review_not_merged", state), None
        if candidate_sha and review.get("headRefOid") and str(review["headRefOid"]) != candidate_sha:
            return "skipped", skip(branch, "head_sha_mismatch", state), None
        landed_by = "remote_review"
        delete_flag = "-D"
    else:
        ref = branch if local_exists else f"{remote}/{branch}"
        ancestor = runner(["git", "merge-base", "--is-ancestor", ref, base_ref], cwd=root)
        if not ancestor.ok:
            return "skipped", skip(branch, "review_not_merged"), None

    if worktree:
        path = Path(worktree["path"])
        if not owned_worktree(path):
            return "skipped", skip(branch, "worktree_ownership_unknown", state), None
        if not flow.is_clean_worktree(path, runner):
            return "skipped", skip(branch, "dirty_worktree", state), None

    remote_cleanup: dict[str, object] = {"skipped": not cleanup_remote or not remote_exists}
    if cleanup_remote and remote_exists:
        deleted = flow.delete_remote_branch(root, remote, branch, url, runner)
        tracking = flow.delete_remote_tracking_ref(root, remote, branch, runner) if deleted.ok else None
        remote_cleanup = {
            "ok": deleted.ok,
            "command": flow.command_text(deleted.args),
            "stderr": deleted.stderr,
            "tracking": (
                {
                    "ok": tracking.ok,
                    "command": flow.command_text(tracking.args),
                    "stderr": tracking.stderr,
                }
                if tracking
                else None
            ),
        }
        if not deleted.ok:
            return "failed", {"branch": branch, "remote_cleanup": remote_cleanup}, "remote_branch_delete_failed"
        if tracking and not tracking.ok:
            return "failed", {"branch": branch, "remote_cleanup": remote_cleanup}, "remote_tracking_delete_failed"

    local_steps: list[dict[str, object]] = []
    if worktree:
        path = Path(worktree["path"])
        remove = runner(["git", "worktree", "remove", str(path)], cwd=root)
        local_steps.append({"command": flow.command_text(remove.args), "ok": remove.ok, "stderr": remove.stderr})
        if not remove.ok:
            return "failed", {"branch": branch, "local_steps": local_steps}, "worktree_remove_failed"

    if local_exists:
        delete = runner(["git", "branch", delete_flag, branch], cwd=root)
        local_steps.append({"command": flow.command_text(delete.args), "ok": delete.ok, "stderr": delete.stderr})
        if not delete.ok:
            return "failed", {"branch": branch, "local_steps": local_steps}, "local_branch_delete_failed"

    return (
        "cleaned",
        {
            "branch": branch,
            "state": state,
            "landed_by": landed_by,
            "url": review_url,
            "remote_cleanup": remote_cleanup,
            "local_steps": local_steps,
            "worktree_removed": bool(worktree),
        },
        None,
    )


def scan_landed_cleanup(
    root: Path,
    config: dict[str, object],
    config_path: str | None,
    base_name: str,
    base_ref: str,
    provider: str,
    remote: str,
    url: str | None,
    runner=flow.run_command,
) -> dict[str, object]:
    local_branches = ref_names(root, "refs/heads", runner)
    if local_branches is None:
        return flow.stop("branch_scan_failed", "Could not list local branches.")
    remote_branches = remote_branch_names(root, remote, runner)
    if remote_branches is None:
        return flow.stop("branch_scan_failed", "Could not list remote branches.")
    worktrees = worktree_entries(root, runner)
    if worktrees is None:
        return flow.stop("worktree_scan_failed", "Could not list git worktrees.")

    cleanup_setting = str(flow.section(config, "delivery").get("cleanup_remote_branch") or "auto").lower()
    cleanup_remote = cleanup_setting not in {"false", "never", "no"}
    local_set = set(local_branches)
    remote_set = set(remote_branches)
    candidates = sorted((local_set | remote_set | set(worktrees)) - flow.LONG_LIVED_BRANCHES)

    cleaned: list[dict[str, object]] = []
    skipped: list[dict[str, object]] = []
    needs_prune = False
    for candidate in candidates:
        status, item, reason = cleanup_scanned_candidate(
            root,
            candidate,
            base_ref=base_ref,
            provider=provider,
            remote=remote,
            url=url,
            local_exists=candidate in local_set,
            remote_exists=candidate in remote_set,
            worktree=worktrees.get(candidate),
            cleanup_remote=cleanup_remote,
            runner=runner,
        )
        if status == "failed":
            return flow.stop(reason or "cleanup_failed", "Cleanup failed while scanning landed branches.", failed=item)
        if status == "skipped":
            skipped.append(item)
            continue
        cleaned.append(item)
        needs_prune = needs_prune or bool(item.get("worktree_removed"))

    prune_step = None
    if needs_prune:
        prune = runner(["git", "worktree", "prune"], cwd=root)
        prune_step = {"command": flow.command_text(prune.args), "ok": prune.ok, "stderr": prune.stderr}
        if not prune.ok:
            return flow.stop("worktree_prune_failed", "Worktree prune failed after cleanup.", cleaned=cleaned, skipped=skipped, prune_step=prune_step)

    data = {
        "ok": True,
        "action": "scanned_cleaned" if cleaned else "noop",
        "provider": provider or None,
        "base_branch": base_name,
        "branch": None,
        "state": "scanned",
        "cleaned": cleaned,
        "skipped": skipped,
        "prune_step": prune_step,
        "config_path": config_path,
    }
    json_path, md_path = flow.write_outputs("clean", data)
    return {**data, "json_path": str(json_path), "markdown_path": str(md_path)}


def run(cwd: Path, host: str, runner=flow.run_command) -> dict[str, object]:
    try:
        config, config_path = flow.load_repo_config(cwd, host, runner)
    except RuntimeError as exc:
        return flow.stop("not_git_repo", str(exc))

    root = flow.repo_root(cwd, runner)
    branch = flow.current_branch(root, runner)
    if not branch:
        return flow.stop("detached_head", "Current checkout is detached; localflow clean needs a named task branch.")
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
    provider_result = flow.resolve_provider(config, url, root, runner)
    provider = str(provider_result.get("provider") or "")

    if branch in flow.LONG_LIVED_BRANCHES:
        return scan_landed_cleanup(root, config, config_path, base_name, base_ref, provider, remote, url, runner)

    review = flow.find_review(root, provider, branch, runner) if provider else None

    landed_by = "local_landing"
    if review:
        if flow.normalize_review_state(review) != "merged":
            return flow.stop("review_not_merged", "MR/PR is not merged; localflow clean will not clean it.")
        if head and review.get("headRefOid") and str(review["headRefOid"]) != head:
            return flow.stop("head_sha_mismatch", "Local HEAD does not match the merged MR/PR head SHA.")
        fetch = flow.fetch_branch(root, remote, base_name, runner)
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
        tracking = flow.delete_remote_tracking_ref(root, remote, branch, runner) if deleted.ok else None
        remote_cleanup = {
            "ok": deleted.ok,
            "command": flow.command_text(deleted.args),
            "stderr": deleted.stderr,
            "tracking": (
                {
                    "ok": tracking.ok,
                    "command": flow.command_text(tracking.args),
                    "stderr": tracking.stderr,
                }
                if tracking
                else None
            ),
        }
        if not deleted.ok:
            return flow.stop("remote_branch_delete_failed", "Could not delete the remote task branch.", remote_cleanup=remote_cleanup)
        if tracking and not tracking.ok:
            return flow.stop("remote_tracking_delete_failed", "Could not delete the remote-tracking task branch.", remote_cleanup=remote_cleanup)

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
