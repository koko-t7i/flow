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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", default=".", help="Repository working directory")
    parser.add_argument("--host", choices=("codex", "claude"), default="codex")
    args = parser.parse_args()
    data = run(Path(args.cwd).resolve(), args.host)
    if "json_path" not in data:
        json_path, md_path = flow.write_outputs("mr", data)
        data = {**data, "json_path": str(json_path), "markdown_path": str(md_path)}
    flow.print_summary(data)
    return 0 if data.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
