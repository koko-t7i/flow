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

import repo_flow as flow


def create_review(
    cwd: Path,
    provider: str,
    branch: str,
    base: str,
    title: str,
    body: str,
    draft: bool,
    runner=flow.run_command,
) -> dict[str, object]:
    if provider == "github":
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as body_file:
            body_file.write(body)
            body_path = body_file.name
        args = ["gh", "pr", "create", "--base", base, "--head", branch, "--title", title, "--body-file", body_path]
        if draft:
            args.append("--draft")
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
        if draft:
            args.append("--draft")
        result = runner(args, cwd=cwd, timeout=60)
    return {
        "ok": result.ok,
        "command": flow.command_text(args),
        "stdout": result.stdout,
        "stderr": result.stderr,
    }


def run(cwd: Path, host: str, runner=flow.run_command) -> dict[str, object]:
    try:
        config, config_path = flow.load_repo_config(cwd, host, runner)
    except RuntimeError as exc:
        return flow.stop("not_git_repo", str(exc))

    root = flow.repo_root(cwd, runner)
    branch = flow.current_branch(root, runner)
    if not branch:
        return flow.stop("detached_head", "Current checkout is detached; localflow mr needs a named task branch.")
    if branch in flow.LONG_LIVED_BRANCHES:
        return flow.stop("long_lived_branch", f"Refusing to create a review request from long-lived branch {branch}.")
    if not flow.is_clean_worktree(root, runner):
        return flow.stop("dirty_worktree", "Worktree or staged area is not clean; commit or discard changes first.")

    base_result = flow.resolve_base_branch(root, config, runner)
    if not base_result.get("name"):
        return base_result
    base_name = str(base_result["name"])
    base_ref = str(base_result["ref"])
    ahead = flow.commits_ahead(root, base_ref, runner)
    if not ahead:
        return flow.stop("no_branch_commits", f"Branch {branch} has no commits ahead of {base_name}.")

    mr_config = flow.section(config, "mr")
    remote = str(mr_config.get("remote") or "origin")
    url = flow.remote_url(root, remote, runner)
    provider_result = flow.resolve_provider(config, url, root, runner)
    if not provider_result.get("provider"):
        return provider_result
    provider = str(provider_result["provider"])

    existing = flow.find_review(root, provider, branch, runner)
    if existing:
        data = {
            "ok": True,
            "action": "status",
            "provider": provider,
            "base_branch": base_name,
            "branch": branch,
            "url": existing.get("url"),
            "state": flow.normalize_review_state(existing),
            "head_sha": existing.get("headRefOid"),
            "config_path": config_path,
        }
        json_path, md_path = flow.write_outputs("mr", data)
        return {**data, "json_path": str(json_path), "markdown_path": str(md_path)}

    checks_ok, checks = flow.run_checks(root, config, runner)
    if not checks_ok:
        data = flow.stop("checks_failed", "Configured pre-commit checks failed.", checks=checks)
        json_path, md_path = flow.write_outputs("mr", data)
        return {**data, "json_path": str(json_path), "markdown_path": str(md_path)}

    push = flow.push_branch(root, remote, branch, url, runner)
    if not push.ok:
        data = flow.stop("push_failed", "Could not push the task branch.", stderr=push.stderr, checks=checks)
        json_path, md_path = flow.write_outputs("mr", data)
        return {**data, "json_path": str(json_path), "markdown_path": str(md_path)}

    title = flow.commit_subject(root, runner)
    body = flow.build_review_body(branch, base_name, flow.commit_lines(root, base_ref, runner), checks)
    draft = bool(mr_config.get("draft") or False)
    created = create_review(root, provider, branch, base_name, title, body, draft, runner)
    if not created["ok"]:
        data = flow.stop("review_create_failed", "Could not create the review request.", stderr=created["stderr"])
        json_path, md_path = flow.write_outputs("mr", data)
        return {**data, "json_path": str(json_path), "markdown_path": str(md_path)}

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
        "checks": checks,
        "config_path": config_path,
    }
    json_path, md_path = flow.write_outputs("mr", data)
    return {**data, "json_path": str(json_path), "markdown_path": str(md_path)}


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
    bump: str | None = None,
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

    if base:
        base_ref = flow.resolved_branch_ref(root, base, runner) or base
        base_name = base
    else:
        base_result = flow.resolve_base_branch(root, config, runner)
        if not base_result.get("name"):
            return base_result
        base_name = str(base_result["name"])
        base_ref = str(base_result["ref"])

    parent_ref = f"refs/heads/{branch}" if flow.branch_exists(root, branch, runner) else base_ref

    version_info: dict[str, object] = {"decision": "unchanged", "reason": "no --bump requested"}
    version_blobs: list[tuple[str, str]] = []
    if bump:
        bump_result = flow.prepare_version_bump(root, config, bump, runner)
        if not bump_result.get("ok"):
            return bump_result
        version_info = bump_result["version"]  # type: ignore[assignment]
        version_blobs = bump_result["blobs"]  # type: ignore[assignment]

    full_message = f"{message}\n\n{body.strip()}" if body else message
    snapshot = flow.snapshot_branch(
        root, branch, base_ref, list(paths), full_message, parent_ref, version_blobs=version_blobs, runner=runner
    )
    if not snapshot.get("ok"):
        return snapshot
    sha = str(snapshot["sha"])

    mr_config = flow.section(config, "mr")
    remote = str(mr_config.get("remote") or "origin")
    url = flow.remote_url(root, remote, runner)
    provider_result = flow.resolve_provider(config, url, root, runner)
    if not provider_result.get("provider"):
        return provider_result
    provider = str(provider_result["provider"])

    existing = flow.find_review(root, provider, branch, runner)

    push = flow.push_branch(root, remote, branch, url, runner)
    if not push.ok:
        data = flow.stop("push_failed", "Could not push the snapshot branch.", stderr=push.stderr)
        json_path, md_path = flow.write_outputs("mr", data)
        return {**data, "json_path": str(json_path), "markdown_path": str(md_path)}

    if not existing:
        body_text = flow.build_review_body(branch, base_name, [f"{sha[:9]} {message}"], [])
        draft = bool(mr_config.get("draft") or False)
        created = create_review(root, provider, branch, base_name, message, body_text, draft, runner)
        if not created["ok"]:
            data = flow.stop("review_create_failed", "Could not create the review request.", stderr=created["stderr"])
            json_path, md_path = flow.write_outputs("mr", data)
            return {**data, "json_path": str(json_path), "markdown_path": str(md_path)}

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
        "version": version_info,
        "worktree_untouched": True,
        "config_path": config_path,
    }
    json_path, md_path = flow.write_outputs("mr", data)
    return {**data, "json_path": str(json_path), "markdown_path": str(md_path)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", default=".", help="Repository working directory")
    parser.add_argument("--host", choices=("codex", "claude"), default="codex")
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
    parser.add_argument("--bump", choices=("patch", "minor", "major"), help="Apply a SemVer bump per [version_policy]")
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
                    bump=args.bump,
                )
    else:
        data = run(cwd, args.host)

    if "json_path" not in data:
        json_path, md_path = flow.write_outputs("mr", data)
        data = {**data, "json_path": str(json_path), "markdown_path": str(md_path)}
    flow.print_summary(data)
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
