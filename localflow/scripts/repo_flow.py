#!/usr/bin/env python3
"""Shared deterministic helpers for localflow delivery scripts."""

from __future__ import annotations

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import ast
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


CACHE_DIR = Path.home() / ".cache" / "localflow"
LONG_LIVED_BRANCHES = {"main", "test", "dev"}
DEFAULT_TIMEOUT_SECONDS = 30
CONVENTIONAL_TYPES = {
    "feat",
    "fix",
    "refactor",
    "perf",
    "docs",
    "test",
    "chore",
    "build",
    "ci",
    "style",
    "revert",
}
BANNED_COMMIT_TOKENS = ("claude", "codex", "anthropic", "openai", "co-authored-by")


@dataclass
class CommandResult:
    ok: bool
    exit_code: int | None
    stdout: str
    stderr: str
    args: list[str] | str


def run_command(
    args: list[str] | str,
    *,
    cwd: Path,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    shell: bool = False,
    env: dict[str, str] | None = None,
) -> CommandResult:
    run_env = shell_command_env() if shell else None
    if env:
        run_env = {**(run_env if run_env is not None else os.environ), **env}
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            env=run_env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
            shell=shell,
        )
    except FileNotFoundError:
        return CommandResult(False, None, "", "command not found", args)
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            False,
            None,
            str(exc.stdout or "").strip(),
            str(exc.stderr or "command timed out").strip(),
            args,
        )
    return CommandResult(
        result.returncode == 0,
        result.returncode,
        result.stdout.strip(),
        result.stderr.strip(),
        args,
    )


def shell_command_env(
    base_env: dict[str, str] | None = None,
    executable: str | None = None,
) -> dict[str, str]:
    env = dict(base_env or os.environ)
    if not env.get("UV_RUN_RECURSION_DEPTH"):
        return env

    executable_dir = str(Path(executable or sys.executable).resolve().parent)
    path_parts = []
    for part in env.get("PATH", "").split(os.pathsep):
        if not part:
            continue
        if str(Path(part).resolve()) == executable_dir:
            continue
        path_parts.append(part)
    env["PATH"] = os.pathsep.join(path_parts)
    return env


def command_text(args: list[str] | str) -> str:
    if isinstance(args, str):
        return args
    return " ".join(shlex.quote(part) for part in args)


def stop(reason: str, message: str, **extra: object) -> dict[str, object]:
    return {"ok": False, "stop_reason": reason, "message": message, **extra}


def first_line(text: object) -> str | None:
    value = str(text or "").strip()
    return value.splitlines()[0] if value else None


def parse_toml_text(text: str) -> dict[str, object]:
    try:
        import tomllib

        return tomllib.loads(text)
    except ModuleNotFoundError:
        return parse_simple_toml(text)


def parse_simple_toml(text: str) -> dict[str, object]:
    data: dict[str, object] = {}
    section: dict[str, object] = data
    pending_key: str | None = None
    pending_values: list[str] = []

    def assign(target: dict[str, object], key: str, raw_value: str) -> None:
        value = raw_value.strip().rstrip(",")
        if value.startswith("[") and value.endswith("]"):
            try:
                parsed = ast.literal_eval(value)
            except (SyntaxError, ValueError):
                target[key] = re.findall(r'"([^"]*)"', value)
            else:
                target[key] = parsed if isinstance(parsed, list) else value
        elif value.lower() in {"true", "false"}:
            target[key] = value.lower() == "true"
        elif value.startswith('"') and value.endswith('"'):
            target[key] = value[1:-1]
        else:
            try:
                target[key] = int(value)
            except ValueError:
                target[key] = value

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if pending_key is not None:
            pending_values.append(line)
            if line.endswith("]"):
                assign(section, pending_key, " ".join(pending_values))
                pending_key = None
                pending_values = []
            continue
        if line.startswith("[") and line.endswith("]"):
            name = line[1:-1].strip()
            section = data.setdefault(name, {})  # type: ignore[assignment]
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value.startswith("[") and not value.endswith("]"):
            pending_key = key
            pending_values = [value]
            continue
        assign(section, key, value)
    return data


def repo_root(cwd: Path, runner=run_command) -> Path:
    result = runner(["git", "rev-parse", "--show-toplevel"], cwd=cwd)
    if not result.ok:
        raise RuntimeError("not a git repository")
    return Path(result.stdout)


def load_repo_config(cwd: Path, host: str, runner=run_command) -> tuple[dict[str, object], str | None]:
    root = repo_root(cwd, runner)
    if host == "claude":
        candidates = [root / ".claude" / "localflow.toml", root / ".codex" / "localflow.toml"]
    else:
        candidates = [root / ".codex" / "localflow.toml", root / ".claude" / "localflow.toml"]
    for path in candidates:
        if path.exists():
            return parse_toml_text(path.read_text(encoding="utf-8")), str(path)
    return {}, None


def section(config: dict[str, object], name: str) -> dict[str, object]:
    value = config.get(name)
    return value if isinstance(value, dict) else {}


def current_branch(cwd: Path, runner=run_command) -> str | None:
    result = runner(["git", "branch", "--show-current"], cwd=cwd)
    return first_line(result.stdout) if result.ok else None


def head_sha(cwd: Path, runner=run_command) -> str | None:
    result = runner(["git", "rev-parse", "HEAD"], cwd=cwd)
    return first_line(result.stdout) if result.ok else None


def is_clean_worktree(cwd: Path, runner=run_command) -> bool:
    result = runner(["git", "status", "--porcelain"], cwd=cwd)
    return result.ok and result.stdout.strip() == ""


def ref_exists(cwd: Path, ref: str, runner=run_command) -> bool:
    return runner(["git", "rev-parse", "--verify", "--quiet", ref], cwd=cwd).ok


def resolved_branch_ref(cwd: Path, branch: str, runner=run_command, *, prefer_remote: bool = False) -> str | None:
    refs = [f"origin/{branch}", branch] if prefer_remote else [branch, f"origin/{branch}"]
    for ref in refs:
        if ref_exists(cwd, ref, runner):
            return ref
    return None


def resolve_base_branch(cwd: Path, config: dict[str, object], runner=run_command) -> dict[str, str] | dict[str, object]:
    configured = config.get("base_branch")
    if configured:
        branch = str(configured)
        ref = resolved_branch_ref(cwd, branch, runner)
        if ref:
            return {"name": branch, "ref": ref}
        return stop("base_branch_missing", f"Could not resolve base branch from {branch}.")

    candidates = ["main", "test", "dev"]
    matches: list[tuple[int, int, str, str]] = []
    for index, branch in enumerate(candidates):
        ref = resolved_branch_ref(cwd, branch, runner, prefer_remote=True)
        if not ref:
            continue
        ahead = commits_ahead(cwd, ref, runner)
        matches.append((ahead if ahead is not None else sys.maxsize, index, branch, ref))
    if matches:
        _, _, branch, ref = min(matches)
        return {"name": branch, "ref": ref}
    return stop("base_branch_missing", f"Could not resolve base branch from {', '.join(candidates)}.")


def remote_url(cwd: Path, remote: str, runner=run_command) -> str | None:
    result = runner(["git", "remote", "get-url", remote], cwd=cwd)
    return first_line(result.stdout) if result.ok else None


def remote_host(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("git@") and ":" in url:
        return url.split("@", 1)[1].split(":", 1)[0]
    return urlparse(url).hostname


def infer_provider_from_cli_auth(
    host: str,
    cwd: Path,
    runner=run_command,
) -> dict[str, str] | dict[str, object]:
    matches: list[str] = []
    checks = [
        ("gitlab", ["glab", "auth", "status", "--hostname", host]),
        ("github", ["gh", "auth", "status", "--hostname", host]),
    ]
    for provider, args in checks:
        result = runner(args, cwd=cwd, timeout=8)
        if result.ok:
            matches.append(provider)
    if len(matches) == 1:
        return {"provider": matches[0]}
    if len(matches) > 1:
        return stop(
            "provider_ambiguous",
            f"Both GitHub and GitLab auth are configured for remote host: {host}. "
            "Set [delivery].remote_provider explicitly.",
        )
    return {}


def resolve_provider(
    config: dict[str, object],
    url: str | None,
    cwd: Path | None = None,
    runner=run_command,
) -> dict[str, str] | dict[str, object]:
    configured = str(section(config, "delivery").get("remote_provider") or "auto").lower()
    if configured in {"github", "gitlab"}:
        return {"provider": configured}
    if configured not in {"auto", ""}:
        return stop("provider_unsupported", f"Unsupported remote_provider: {configured}")
    host = remote_host(url)
    if host == "github.com":
        return {"provider": "github"}
    if host and "gitlab" in host:
        return {"provider": "gitlab"}
    if host and cwd is not None:
        cli_result = infer_provider_from_cli_auth(host, cwd, runner)
        if cli_result:
            return cli_result
    return stop("provider_ambiguous", f"Could not infer review provider from remote host: {host or 'absent'}.")


def https_remote_url(url: str | None) -> str | None:
    if not url:
        return None
    if url.startswith("git@") and ":" in url:
        host, path = url.split("@", 1)[1].split(":", 1)
        return f"https://{host}/{path}"
    return url


def commits_ahead(cwd: Path, base_ref: str, runner=run_command) -> int | None:
    result = runner(["git", "rev-list", "--count", f"{base_ref}..HEAD"], cwd=cwd)
    if not result.ok:
        return None
    try:
        return int(result.stdout.strip())
    except ValueError:
        return None


def commit_subject(cwd: Path, runner=run_command) -> str:
    result = runner(["git", "log", "-1", "--pretty=%s"], cwd=cwd)
    return first_line(result.stdout) or "Update branch"


def commit_lines(cwd: Path, base_ref: str, runner=run_command) -> list[str]:
    result = runner(["git", "log", "--oneline", f"{base_ref}..HEAD"], cwd=cwd)
    if not result.ok or not result.stdout:
        return []
    return result.stdout.splitlines()


def build_review_body(branch: str, base: str, commits: list[str], checks: list[dict[str, object]]) -> str:
    lines = [
        "## Summary",
        f"- Base: `{base}`",
        f"- Branch: `{branch}`",
        "",
        "## Commits",
    ]
    lines.extend([f"- `{line}`" for line in commits] or ["- No commits listed."])
    lines.extend(["", "## Verification"])
    if checks:
        for check in checks:
            status = "passed" if check.get("ok") else "failed"
            lines.append(f"- `{check.get('command')}`: {status}")
    else:
        lines.append("- No configured pre-commit checks.")
    return "\n".join(lines) + "\n"


def run_checks(cwd: Path, config: dict[str, object], runner=run_command) -> tuple[bool, list[dict[str, object]]]:
    commands = section(config, "validation").get("pre_commit") or []
    if not isinstance(commands, list):
        return False, [{"command": "validation.pre_commit", "ok": False, "stderr": "pre_commit must be a list"}]
    results: list[dict[str, object]] = []
    for command in commands:
        result = runner(str(command), cwd=cwd, shell=True, timeout=300)
        results.append(
            {
                "command": str(command),
                "ok": result.ok,
                "exit_code": result.exit_code,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        )
        if not result.ok:
            return False, results
    return True, results


def fetch_branch(cwd: Path, remote: str, branch: str, runner=run_command) -> CommandResult:
    """Refresh the remote-tracking ref for `branch` so callers can anchor on the live tip."""
    return runner(["git", "fetch", remote, branch], cwd=cwd, timeout=120)


def push_branch(cwd: Path, remote: str, branch: str, url: str | None, runner=run_command) -> CommandResult:
    result = runner(["git", "push", "-u", remote, branch], cwd=cwd, timeout=120)
    if result.ok:
        return result
    fallback = https_remote_url(url)
    if fallback and fallback != url:
        fallback_result = runner(["git", "push", "-u", fallback, branch], cwd=cwd, timeout=120)
        if fallback_result.ok:
            return fallback_result
    return result


def delete_remote_branch(cwd: Path, remote: str, branch: str, url: str | None, runner=run_command) -> CommandResult:
    result = runner(["git", "push", remote, "--delete", branch], cwd=cwd, timeout=120)
    if result.ok or "remote ref does not exist" in result.stderr.lower():
        return CommandResult(True, result.exit_code, result.stdout, result.stderr, result.args)
    fallback = https_remote_url(url)
    if fallback and fallback != url:
        fallback_result = runner(["git", "push", fallback, "--delete", branch], cwd=cwd, timeout=120)
        if fallback_result.ok or "remote ref does not exist" in fallback_result.stderr.lower():
            return CommandResult(True, fallback_result.exit_code, fallback_result.stdout, fallback_result.stderr, fallback_result.args)
    return result


def delete_remote_tracking_ref(cwd: Path, remote: str, branch: str, runner=run_command) -> CommandResult:
    ref = f"{remote}/{branch}"
    result = runner(["git", "branch", "-dr", ref], cwd=cwd)
    missing = "not found" in result.stderr.lower() or "branch not found" in result.stderr.lower()
    if result.ok or missing:
        return CommandResult(True, result.exit_code, result.stdout, result.stderr, result.args)
    return result


def review_view_command(provider: str, branch: str) -> list[str]:
    if provider == "github":
        return [
            "gh",
            "pr",
            "view",
            branch,
            "--json",
            "number,state,url,headRefName,baseRefName,headRefOid,mergeStateStatus,statusCheckRollup,isDraft,title",
        ]
    return ["glab", "mr", "view", branch, "--output", "json"]


def parse_review(provider: str, stdout: str) -> dict[str, object]:
    payload = json.loads(stdout)
    if provider == "github":
        return payload
    return {
        "number": payload.get("iid") or payload.get("id"),
        "state": payload.get("state"),
        "url": payload.get("web_url"),
        "headRefName": payload.get("source_branch"),
        "baseRefName": payload.get("target_branch"),
        "headRefOid": payload.get("sha"),
        "mergeStateStatus": payload.get("detailed_merge_status"),
        "title": payload.get("title"),
        "statusCheckRollup": payload.get("head_pipeline"),
    }


def find_review(cwd: Path, provider: str, branch: str, runner=run_command) -> dict[str, object] | None:
    result = runner(review_view_command(provider, branch), cwd=cwd, timeout=30)
    if not result.ok or not result.stdout:
        return None
    try:
        return parse_review(provider, result.stdout)
    except json.JSONDecodeError:
        return None


def normalize_review_state(review: dict[str, object] | None) -> str | None:
    if not review:
        return None
    state = str(review.get("state") or "").lower()
    if state in {"merged", "merge"}:
        return "merged"
    if state in {"open", "opened"}:
        return "open"
    if state in {"closed", "close"}:
        return "closed"
    return state or None


def validate_commit_subject(subject: str | None) -> str | None:
    """Return an error reason if the subject is not a valid English Conventional Commit, else None."""
    if not subject or not subject.strip():
        return "commit subject is empty"
    text = subject.strip()
    if not text.isascii():
        return "commit subject must be English/ASCII only"
    match = re.match(r"^(?P<type>[a-z]+)(\([^)]+\))?(!)?: .+", text)
    if not match:
        return "commit subject must follow Conventional Commits: type(scope)!: summary"
    if match.group("type") not in CONVENTIONAL_TYPES:
        return f"unknown commit type: {match.group('type')}"
    if len(text) > 72:
        return "commit subject exceeds 72 characters"
    if text.endswith("."):
        return "commit subject must not end with a period"
    lowered = text.lower()
    for token in BANNED_COMMIT_TOKENS:
        if token in lowered:
            return f"commit subject contains banned token: {token}"
    return None


def validate_task_branch(branch: str | None) -> str | None:
    """Return an error reason if branch is not a valid `type/slug` task branch, else None."""
    if not branch:
        return "task branch is empty"
    if branch in LONG_LIVED_BRANCHES:
        return f"refusing to use long-lived branch as a task branch: {branch}"
    if not re.match(r"^[a-z]+/[a-z0-9][a-z0-9._\-]*$", branch):
        return "task branch must follow type/slug (e.g. feat/live-preview)"
    branch_type = branch.split("/", 1)[0]
    if branch_type not in CONVENTIONAL_TYPES:
        return f"unknown task branch type: {branch_type}"
    return None


def is_ignored(cwd: Path, path: str, runner=run_command) -> bool:
    return runner(["git", "check-ignore", "-q", path], cwd=cwd).ok


def branch_exists(cwd: Path, branch: str, runner=run_command) -> bool:
    return ref_exists(cwd, f"refs/heads/{branch}", runner) or ref_exists(
        cwd, f"refs/remotes/origin/{branch}", runner
    )


def bump_semver(version: str, level: str) -> str | None:
    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", version.strip())
    if not match:
        return None
    major, minor, patch = (int(match.group(1)), int(match.group(2)), int(match.group(3)))
    if level == "major":
        major, minor, patch = major + 1, 0, 0
    elif level == "minor":
        minor, patch = minor + 1, 0
    elif level == "patch":
        patch += 1
    else:
        return None
    return f"{major}.{minor}.{patch}"


def prepare_version_bump(
    cwd: Path,
    config: dict[str, object],
    level: str,
    runner=run_command,
) -> dict[str, object]:
    """Compute bumped version blobs without touching the working tree.

    Reads each configured version file on disk (read-only), bumps the first SemVer it
    contains, hashes the bumped content into a git blob, and returns the blobs to inject
    into a snapshot index. Returns a stop() dict on failure.
    """
    policy = section(config, "version_policy")
    if not policy.get("enabled"):
        return stop("version_policy_disabled", "version_policy.enabled is not true; cannot --bump.")
    files = policy.get("files") or []
    if not isinstance(files, list) or not files:
        return stop("version_files_missing", "version_policy.files is empty; nothing to bump.")
    blobs: list[tuple[str, str]] = []
    summary: dict[str, object] | None = None
    for rel in files:
        rel = str(rel)
        path = Path(cwd) / rel
        if not path.exists():
            return stop("version_files_missing", f"configured version file is missing: {rel}")
        text = path.read_text(encoding="utf-8")
        match = re.search(r"\d+\.\d+\.\d+", text)
        if not match:
            return stop("version_files_unparseable", f"no SemVer found in {rel}")
        old = match.group(0)
        new = bump_semver(old, level)
        if not new:
            return stop("version_files_unparseable", f"could not bump version {old} in {rel}")
        new_text = text[: match.start()] + new + text[match.end() :]
        tmp = tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8")
        try:
            tmp.write(new_text)
            tmp.close()
            hashed = runner(["git", "hash-object", "-w", "--", tmp.name], cwd=cwd)
        finally:
            os.unlink(tmp.name)
        if not hashed.ok:
            return stop("version_files_unparseable", f"could not hash bumped {rel}: {hashed.stderr}")
        blob = first_line(hashed.stdout)
        if not blob:
            return stop("version_files_unparseable", f"empty blob hash for {rel}")
        blobs.append((rel, blob))
        if summary is None:
            summary = {"decision": "bumped", "from": old, "to": new, "files": files, "reason": f"--bump {level}"}
    return {"ok": True, "version": summary, "blobs": blobs}


def snapshot_branch(
    cwd: Path,
    branch: str,
    base_ref: str,
    paths: list[str],
    message: str,
    parent_ref: str,
    *,
    version_blobs: list[tuple[str, str]] | None = None,
    runner=run_command,
) -> dict[str, object]:
    """Capture the current worktree state of `paths` into a side branch commit.

    Uses a throwaway index (GIT_INDEX_FILE) so the real index, working tree, and HEAD are
    never touched. Includes untracked files and respects .gitignore. Returns
    {"ok": True, "sha": <commit>} or a stop() dict on failure.
    """
    index_dir = tempfile.mkdtemp(prefix="localflow-index-")
    index_path = str(Path(index_dir) / "index")
    env = {"GIT_INDEX_FILE": index_path}
    try:
        seed = runner(["git", "read-tree", base_ref], cwd=cwd, env=env)
        if not seed.ok:
            return stop("snapshot_failed", f"git read-tree failed: {seed.stderr}")
        if paths:
            added = runner(["git", "add", "--", *paths], cwd=cwd, env=env)
            if not added.ok:
                return stop("snapshot_failed", f"git add failed: {added.stderr}")
        for rel, blob in version_blobs or []:
            injected = runner(
                ["git", "update-index", "--add", "--cacheinfo", f"100644,{blob},{rel}"],
                cwd=cwd,
                env=env,
            )
            if not injected.ok:
                return stop("snapshot_failed", f"git update-index failed: {injected.stderr}")
        tree_result = runner(["git", "write-tree"], cwd=cwd, env=env)
        if not tree_result.ok:
            return stop("snapshot_failed", f"git write-tree failed: {tree_result.stderr}")
        tree = first_line(tree_result.stdout)
        if not tree:
            return stop("snapshot_failed", "git write-tree returned no tree")
        commit_result = runner(["git", "commit-tree", tree, "-p", parent_ref, "-m", message], cwd=cwd)
        if not commit_result.ok:
            return stop("snapshot_failed", f"git commit-tree failed: {commit_result.stderr}")
        commit = first_line(commit_result.stdout)
        if not commit:
            return stop("snapshot_failed", "git commit-tree returned no commit")
        update = runner(["git", "update-ref", f"refs/heads/{branch}", commit], cwd=cwd)
        if not update.ok:
            return stop("snapshot_failed", f"git update-ref failed: {update.stderr}")
        return {"ok": True, "sha": commit}
    finally:
        shutil.rmtree(index_dir, ignore_errors=True)


def snapshot_drift(
    cwd: Path,
    base_ref: str,
    sha: str,
    paths: list[str],
    runner=run_command,
) -> dict[str, object] | None:
    """Guard: a snapshot commit must change ONLY the scoped `paths` against its base.

    When the base is stale/behind the live remote target, the snapshot's diff against
    that base leaks unrelated files (already-merged work shows up as reverts). Returns a
    stop() dict in that case so the caller refuses to push; returns None when clean.
    """
    result = runner(["git", "diff", "--name-only", base_ref, sha], cwd=cwd)
    if not result.ok:
        return stop("snapshot_diff_failed", f"git diff failed: {result.stderr}")
    changed = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    extra = [path for path in changed if path not in set(paths)]
    if extra:
        return stop(
            "snapshot_base_drift",
            "Base is stale or the branch is behind: the snapshot would touch files outside "
            f"--paths: {', '.join(sorted(extra))}. Fetch/sync the base branch and retry.",
        )
    return None


def write_outputs(name: str, data: dict[str, object]) -> tuple[Path, Path]:
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    json_path = CACHE_DIR / f"{name}.json"
    md_path = CACHE_DIR / f"{name}.md"
    json_path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    md_path.write_text(render_markdown(name, data), encoding="utf-8")
    return json_path, md_path


def attach_outputs(name: str, data: dict[str, object]) -> dict[str, object]:
    if "json_path" in data:
        return data
    json_path, md_path = write_outputs(name, data)
    return {**data, "json_path": str(json_path), "markdown_path": str(md_path)}


def render_markdown(name: str, data: dict[str, object]) -> str:
    lines = [f"# Localflow {name}", "", f"- Generated: `{datetime.now(timezone.utc).isoformat()}`"]
    for key in (
        "ok",
        "action",
        "provider",
        "base_branch",
        "branch",
        "url",
        "state",
        "head_sha",
        "base_ahead_remote",
        "base_behind_remote",
        "cleanup",
        "stop_reason",
        "message",
    ):
        if key in data and data[key] is not None:
            lines.append(f"- {key}: `{data[key]}`")
    if data.get("cleanup_hint"):
        lines.append(f"- cleanup_hint: `{data['cleanup_hint']}`")
    if isinstance(data.get("version"), dict):
        version = data["version"]  # type: ignore[index]
        if version.get("decision") == "bumped":
            lines.append(f"- version: `bumped {version.get('from')} -> {version.get('to')}`")
    if data.get("included_files"):
        lines.extend(["", "## Included files"])
        lines.extend([f"- `{path}`" for path in data["included_files"]])  # type: ignore[index]
    if data.get("checks"):
        lines.extend(["", "## Checks"])
        for check in data["checks"]:  # type: ignore[index]
            lines.append(f"- `{check.get('command')}`: {'passed' if check.get('ok') else 'failed'}")
    if data.get("cleaned"):
        lines.extend(["", "## Cleaned"])
        for item in data["cleaned"]:  # type: ignore[index]
            lines.append(f"- `{item.get('branch')}`: {item.get('state')}")
    if data.get("skipped"):
        lines.extend(["", "## Skipped"])
        for item in data["skipped"]:  # type: ignore[index]
            state = f" ({item.get('state')})" if item.get("state") else ""
            lines.append(f"- `{item.get('branch')}`: {item.get('reason')}{state}")
    return "\n".join(lines) + "\n"


def print_summary(data: dict[str, object]) -> None:
    for key in (
        "ok",
        "action",
        "provider",
        "base_branch",
        "branch",
        "url",
        "state",
        "head_sha",
        "base_ahead_remote",
        "base_behind_remote",
        "cleanup",
        "stop_reason",
        "message",
    ):
        if key in data and data[key] is not None:
            print(f"{key}: {data[key]}")
    if data.get("cleanup_hint"):
        print(f"cleanup_hint: {data['cleanup_hint']}")


def finish_command(name: str, data: dict[str, object]) -> int:
    data = attach_outputs(name, data)
    print_summary(data)
    return 0 if data.get("ok") else 1
