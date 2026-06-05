#!/usr/bin/env -S uv run
#
# /// script
# requires-python = ">=3.10"
# ///
"""Create or inspect the review request for the current localflow task branch."""

from __future__ import annotations

import argparse
import sys
import tempfile
from pathlib import Path

sys.dont_write_bytecode = True

import lifecycle
import repo_flow as flow


def create_review(
    cwd: Path,
    provider: str,
    branch: str,
    base: str,
    title: str,
    body: str,
    runner=flow.run_command,
) -> dict[str, object]:
    if provider == "github":
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as body_file:
            body_file.write(body)
            body_path = body_file.name
        args = ["gh", "pr", "create", "--base", base, "--head", branch, "--title", title, "--body-file", body_path]
        try:
            result = runner(args, cwd=cwd, timeout=60)
        finally:
            Path(body_path).unlink(missing_ok=True)
    else:
        args = [
            "glab",
            "mr",
            "create",
            "--source-branch",
            branch,
            "--target-branch",
            base,
            "--title",
            title,
            "--description",
            body,
            "--yes",
        ]
        result = runner(args, cwd=cwd, timeout=60)
    return {
        "ok": result.ok,
        "command": flow.command_text(args),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def run(cwd: Path, host: str, runner=flow.run_command) -> dict[str, object]:
    context = lifecycle.load_task_context(
        cwd,
        host,
        "mr",
        runner,
        detached_message="Current checkout is detached; localflow mr needs a named task branch.",
        long_lived_message="Refusing to create a review request from long-lived branch {branch}.",
    )
    if not context.get("ok"):
        return context
    config = context["config"]  # type: ignore[assignment]
    config_path = context["config_path"]
    root = Path(context["root"])
    branch = str(context["branch"])

    base_result = flow.resolve_base_branch(root, config, runner)
    if not base_result.get("name"):
        return base_result
    base_name = str(base_result["name"])
    base_ref = str(base_result["ref"])
    ahead = flow.commits_ahead(root, base_ref, runner)
    if not ahead:
        return flow.stop("no_branch_commits", f"Branch {branch} has no commits ahead of {base_name}.")

    remote = flow.DEFAULT_REMOTE
    url = flow.remote_url(root, remote, runner)
    provider_result = flow.resolve_provider(config, url, root, runner)
    if not provider_result.get("provider"):
        return provider_result
    provider = str(provider_result["provider"])

    subject_check = flow.validate_review_commit_subjects(root, base_ref, runner)
    if not subject_check.get("ok"):
        return flow.attach_outputs("mr", subject_check)

    existing = flow.find_review(root, provider, branch, runner)
    if existing:
        local_head = flow.head_sha(root, runner)
        state = flow.normalize_review_state(existing)
        if state != "open" or (local_head and existing.get("headRefOid") == local_head):
            data = {
                "ok": True,
                "action": "status",
                "provider": provider,
                "base_branch": base_name,
                "branch": branch,
                "url": existing.get("url"),
                "state": state,
                "head_sha": existing.get("headRefOid"),
                "config_path": config_path,
            }
            return flow.attach_outputs("mr", data)

        push = flow.push_branch(root, remote, branch, url, runner, config=config, config_path=config_path)
        if not push.ok:
            data = flow.stop("push_failed", "Could not push the task branch.", stderr=push.stderr)
            return flow.attach_outputs("mr", data)

        review = flow.find_review(root, provider, branch, runner) or existing
        data = {
            "ok": True,
            "action": "updated",
            "provider": provider,
            "base_branch": base_name,
            "branch": branch,
            "url": review.get("url"),
            "state": flow.normalize_review_state(review),
            "head_sha": local_head or review.get("headRefOid"),
            "config_path": config_path,
        }
        return flow.attach_outputs("mr", data)

    push = flow.push_branch(root, remote, branch, url, runner, config=config, config_path=config_path)
    if not push.ok:
        data = flow.stop("push_failed", "Could not push the task branch.", stderr=push.stderr)
        return flow.attach_outputs("mr", data)

    title = flow.commit_subject(root, runner)
    body = flow.build_review_body(branch, base_name, flow.commit_lines(root, base_ref, runner))
    created = create_review(root, provider, branch, base_name, title, body, runner)
    if not created["ok"]:
        data = flow.stop("review_create_failed", "Could not create the review request.", stderr=created["stderr"])
        return flow.attach_outputs("mr", data)

    review = flow.find_review(root, provider, branch, runner)
    data = {
        "ok": True,
        "action": "created",
        "provider": provider,
        "base_branch": base_name,
        "branch": branch,
        "url": (review or {}).get("url") or flow.first_line(created["stdout"]),
        "state": flow.normalize_review_state(review) if review else None,
        "head_sha": (review or {}).get("headRefOid"),
        "config_path": config_path,
    }
    return flow.attach_outputs("mr", data)


def compose_message(args: argparse.Namespace) -> str | None:
    if args.message:
        return args.message.strip()
    if args.type and args.summary:
        scope = f"({args.scope})" if args.scope else ""
        bang = "!" if args.breaking else ""
        return f"{args.type}{scope}{bang}: {args.summary.strip()}"
    return None


def run_snapshot(
    cwd: Path,
    host: str,
    *,
    branch: str,
    paths: list[str],
    message: str,
    base: str | None = None,
    body: str | None = None,
    runner=flow.run_command,
) -> dict[str, object]:
    """Create or update a review from a side-branch snapshot of `paths`.

    Captures the current worktree state of the named files into a branch without touching
    the working tree, real index, or HEAD, then pushes and opens (or reports) the review.
    This bypasses the dirty-worktree and long-lived-branch guards on purpose: it is the
    shared-checkout / live-preview path.
    """
    try:
        config, config_path = flow.load_repo_config(cwd, host, runner)
    except RuntimeError as exc:
        return flow.stop("not_git_repo", str(exc))
    config_status = flow.require_repo_config(config, config_path)
    if not config_status.get("ok"):
        return config_status
    root = flow.repo_root(cwd, runner)

    # Validate inputs before any git write so we never half-create a branch.
    subject_error = flow.validate_commit_subject(message)
    if subject_error:
        return flow.stop("invalid_commit_message", subject_error)
    branch_error = flow.validate_task_branch(branch)
    if branch_error:
        return flow.stop("invalid_task_branch", branch_error)
    if not paths:
        return flow.stop("paths_required", "Snapshot mode requires --paths to scope the task files.")
    for path in paths:
        if flow.is_ignored(root, path, runner):
            return flow.stop("ignored_path_staged", f"Refusing to snapshot a git-ignored path: {path}")

    # Resolve the remote + base name, then refresh the base from the remote so the
    # snapshot is anchored on the *live* target tip — not a stale local tracking ref.
    # On a shared checkout whose local origin/<base> lags the real remote, anchoring on
    # the stale ref makes the server diff the branch against the live target and pull in
    # already-merged files (as reverts). Fetch first; snapshot_drift below is the backstop.
    remote = flow.DEFAULT_REMOTE

    if base:
        base_name = base
    else:
        base_result = flow.resolve_base_branch(root, config, runner)
        if not base_result.get("name"):
            return base_result
        base_name = str(base_result["name"])

    fetch = flow.fetch_branch(root, remote, base_name, runner, config=config, config_path=config_path)
    remote_ref = f"{remote}/{base_name}"
    if fetch.ok and flow.ref_exists(root, remote_ref, runner):
        base_ref = remote_ref
    elif base:
        # An explicit --base may be a local-only / stacked branch with no remote ref;
        # fall back to it and let snapshot_drift catch a stale anchor.
        base_ref = flow.resolved_branch_ref(root, base_name, runner) or base_name
    else:
        return flow.stop(
            "base_fetch_failed",
            f"Could not refresh base branch '{base_name}' from '{remote}'.",
            stderr=fetch.stderr,
        )

    parent_ref = f"refs/heads/{branch}" if flow.branch_exists(root, branch, runner) else base_ref
    if parent_ref != base_ref:
        subject_check = flow.validate_review_commit_subjects(
            root,
            base_ref,
            runner,
            head_ref=parent_ref,
            extra_subject=message,
        )
        if not subject_check.get("ok"):
            return flow.attach_outputs("mr", subject_check)

    full_message = f"{message}\n\n{body.strip()}" if body else message
    snapshot = flow.snapshot_branch(root, branch, base_ref, list(paths), full_message, parent_ref, runner=runner)
    if not snapshot.get("ok"):
        return snapshot
    sha = str(snapshot["sha"])

    # Refuse to push a snapshot that touches anything beyond --paths relative to the
    # live base — the signature of a stale/behind base contaminating the review.
    drift = flow.snapshot_drift(root, base_ref, sha, list(paths), runner)
    if drift:
        return flow.attach_outputs("mr", drift)

    url = flow.remote_url(root, remote, runner)
    provider_result = flow.resolve_provider(config, url, root, runner)
    if not provider_result.get("provider"):
        return provider_result
    provider = str(provider_result["provider"])

    existing = flow.find_review(root, provider, branch, runner)

    push = flow.push_branch(root, remote, branch, url, runner, config=config, config_path=config_path)
    if not push.ok:
        data = flow.stop("push_failed", "Could not push the snapshot branch.", stderr=push.stderr)
        return flow.attach_outputs("mr", data)

    if not existing:
        body_text = flow.build_review_body(branch, base_name, [f"{sha[:9]} {message}"], [])
        created = create_review(root, provider, branch, base_name, message, body_text, runner)
        if not created["ok"]:
            data = flow.stop("review_create_failed", "Could not create the review request.", stderr=created["stderr"])
            return flow.attach_outputs("mr", data)

    review = flow.find_review(root, provider, branch, runner)
    data = {
        "ok": True,
        "action": "snapshot_updated" if existing else "snapshot_created",
        "provider": provider,
        "base_branch": base_name,
        "branch": branch,
        "url": (review or {}).get("url"),
        "state": flow.normalize_review_state(review) if review else None,
        "head_sha": sha,
        "included_files": list(paths),
        "worktree_untouched": True,
        "config_path": config_path,
    }
    return flow.attach_outputs("mr", data)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", default=".", help="Repository working directory")
    parser.add_argument("--host", choices=("codex", "claude", "pi"), default="codex")
    parser.add_argument(
        "--snapshot",
        action="store_true",
        help="Snapshot the named --paths into a side branch and open a review without touching the working tree.",
    )
    parser.add_argument("--branch", help="Task branch name (type/slug) for snapshot mode")
    parser.add_argument("--base", help="Base branch to target (default: resolved from config/heuristic)")
    parser.add_argument("--paths", nargs="+", default=[], help="Task files to include in the snapshot")
    parser.add_argument("--message", help="Full Conventional Commit subject for the snapshot")
    parser.add_argument("--type", help="Conventional Commit type (used with --summary)")
    parser.add_argument("--scope", help="Conventional Commit scope (used with --type/--summary)")
    parser.add_argument("--summary", help="Imperative summary (used with --type)")
    parser.add_argument("--body", help="Optional commit/MR body")
    parser.add_argument("--breaking", action="store_true", help="Mark the change as breaking (appends '!')")
    args = parser.parse_args()

    cwd = Path(args.cwd).resolve()
    if args.snapshot:
        if not args.branch:
            data = flow.stop("task_branch_required", "Snapshot mode requires --branch type/slug.")
        else:
            message = compose_message(args)
            if not message:
                data = flow.stop(
                    "commit_message_required",
                    "Snapshot mode requires --message or --type with --summary.",
                )
            else:
                data = run_snapshot(
                    cwd,
                    args.host,
                    branch=args.branch,
                    paths=args.paths,
                    message=message,
                    base=args.base,
                    body=args.body,
                )
    else:
        data = run(cwd, args.host)

    return flow.finish_command("mr", data)


if __name__ == "__main__":
    sys.exit(main())
