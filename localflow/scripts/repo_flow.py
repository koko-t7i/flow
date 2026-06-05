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
REQUIRED_CONFIG_KEYS = ("base_branch", "remote_cli", "passphrase", "default_mode")
REMOTE_CLI_PROVIDERS = {"gh": "github", "glab": "gitlab"}
DEFAULT_REMOTE = "origin"


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
    elif host == "pi":
        candidates = [
            root / ".pi" / "localflow.toml",
            root / ".claude" / "localflow.toml",
            root / ".codex" / "localflow.toml",
        ]
    else:
        candidates = [root / ".codex" / "localflow.toml", root / ".claude" / "localflow.toml"]
    for path in candidates:
        if path.exists():
            return parse_toml_text(path.read_text(encoding="utf-8")), str(path)
    return {}, None


def validate_repo_config(config: dict[str, object], config_path: str | None) -> dict[str, object] | None:
    if config_path is None:
        return stop(
            "config_missing",
            "No localflow config found; confirm base_branch, remote_cli, passphrase, and default_mode first.",
        )

    missing = [key for key in REQUIRED_CONFIG_KEYS if key not in config]
    if missing:
        return stop(
            "config_schema_outdated",
            f"Localflow config is missing required field(s): {', '.join(missing)}.",
            config_path=config_path,
        )

    base_branch = str(config.get("base_branch") or "")
    if base_branch not in LONG_LIVED_BRANCHES:
        return stop("config_invalid", f"Unsupported base_branch: {base_branch}", config_path=config_path)

    remote_cli = str(config.get("remote_cli") or "").lower()
    if remote_cli not in {"gh", "glab", "none"}:
        return stop("config_invalid", f"Unsupported remote_cli: {remote_cli}", config_path=config_path)

    default_mode = str(config.get("default_mode") or "").lower()
    if default_mode not in {"tree", "fast"}:
        return stop("config_invalid", f"Unsupported default_mode: {default_mode}", config_path=config_path)

    passphrase = str(config.get("passphrase") or "")
    if not passphrase.startswith("file:"):
        return stop("config_invalid", "passphrase must use file:<name>.", config_path=config_path)
    rel = passphrase.removeprefix("file:")
    rel_path = Path(rel)
    if rel_path.is_absolute() or len(rel_path.parts) != 1 or rel_path.name in {"", ".", ".."}:
        return stop(
            "config_invalid",
            "passphrase must point to a file in the same directory as localflow.toml.",
            config_path=config_path,
        )

    return None


def require_repo_config(config: dict[str, object], config_path: str | None) -> dict[str, object]:
    error = validate_repo_config(config, config_path)
    if error:
        return error
    return {"ok": True}


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


def resolve_provider(
    config: dict[str, object],
    url: str | None,
    cwd: Path | None = None,
    runner=run_command,
) -> dict[str, str] | dict[str, object]:
    configured = str(config.get("remote_cli") or "").lower()
    if configured == "none":
        return stop("review_cli_disabled", "remote_cli is none; MR/PR review is disabled for this repository.")
    provider = REMOTE_CLI_PROVIDERS.get(configured)
    if provider:
        return {"provider": provider}
    return stop("config_schema_outdated", "Localflow config must set remote_cli to gh, glab, or none.")


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


def commit_subject_records(
    cwd: Path,
    base_ref: str,
    runner=run_command,
    *,
    head_ref: str = "HEAD",
) -> list[dict[str, str]] | None:
    result = runner(["git", "log", "--reverse", "--format=%H%x00%s", f"{base_ref}..{head_ref}"], cwd=cwd)
    if not result.ok:
        return None
    records: list[dict[str, str]] = []
    for line in result.stdout.splitlines():
        if "\x00" in line:
            sha, subject = line.split("\x00", 1)
        else:
            sha, subject = "", line
        subject = subject.strip()
        if subject:
            records.append({"sha": sha.strip(), "subject": subject})
    return records


def validate_review_commit_subjects(
    cwd: Path,
    base_ref: str,
    runner=run_command,
    *,
    head_ref: str = "HEAD",
    extra_subject: str | None = None,
) -> dict[str, object]:
    records = commit_subject_records(cwd, base_ref, runner, head_ref=head_ref)
    if records is None:
        return stop("commit_subjects_unavailable", "Could not inspect commit subjects before review push.")

    seen: dict[str, str] = {}
    for record in records:
        subject = record["subject"]
        error = validate_commit_subject(subject)
        if error:
            sha = record.get("sha")
            prefix = f"{sha[:9]} " if sha else ""
            return stop("invalid_commit_message", f"{prefix}{error}: {subject}")

        previous = seen.get(subject)
        if previous:
            current = record.get("sha", "")
            detail = f"{previous[:9]} and {current[:9]} " if current else ""
            return stop(
                "duplicate_commit_subject",
                f"Duplicate commit subject in review branch ({detail}): {subject}",
            )
        seen[subject] = record.get("sha", "")

    if extra_subject:
        subject = extra_subject.strip()
        error = validate_commit_subject(subject)
        if error:
            return stop("invalid_commit_message", f"{error}: {subject}")
        previous = seen.get(subject)
        if previous:
            return stop(
                "duplicate_commit_subject",
                f"Duplicate commit subject in review branch ({previous[:9]} and pending): {subject}",
            )

    return {"ok": True, "commits": records}


def build_review_body(branch: str, base: str, commits: list[str], checks: list[dict[str, object]] | None = None) -> str:
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
        lines.append("- Verified by agent workflow before delivery.")
    return "\n".join(lines) + "\n"


def needs_passphrase_retry(result: CommandResult) -> bool:
    lower = f"{result.stdout}\n{result.stderr}".lower()
    return "enter passphrase for key" in lower or "permission denied, please try again" in lower


def passphrase_file(config: dict[str, object], config_path: str | None, cwd: Path, runner=run_command) -> dict[str, object]:
    if config_path is None:
        return stop("config_missing", "Cannot resolve passphrase without a localflow config path.")
    value = str(config.get("passphrase") or "")
    if not value.startswith("file:"):
        return stop("passphrase_config_invalid", "passphrase must use file:<name>.")

    rel = value.removeprefix("file:")
    rel_path = Path(rel)
    if rel_path.is_absolute() or len(rel_path.parts) != 1 or rel_path.name in {"", ".", ".."}:
        return stop("passphrase_path_invalid", "passphrase file must live beside localflow.toml.")

    path = (Path(config_path).parent / rel_path).resolve()
    if not path.exists() or not path.is_file():
        return stop("passphrase_file_missing", f"Configured passphrase file is missing: {path}")

    root = repo_root(cwd, runner).resolve()
    try:
        rel_to_root = path.relative_to(root).as_posix()
    except ValueError:
        return stop("passphrase_path_invalid", "passphrase file must be inside the repository.")
    if not is_ignored(root, rel_to_root, runner):
        return stop("passphrase_file_not_ignored", f"Passphrase file must be git-ignored: {rel_to_root}")

    secret = path.read_text(encoding="utf-8").rstrip("\r\n")
    if not secret:
        return stop("passphrase_file_empty", "Configured passphrase file is empty.")
    return {"ok": True, "path": str(path), "secret": secret}


def run_with_passphrase(
    args: list[str],
    *,
    cwd: Path,
    config: dict[str, object],
    config_path: str | None,
    timeout: int,
    runner=run_command,
) -> CommandResult:
    loaded = passphrase_file(config, config_path, cwd, runner)
    if not loaded.get("ok"):
        return CommandResult(False, None, "", str(loaded.get("message")), args)

    temp_dir = tempfile.mkdtemp(prefix="localflow-askpass-")
    askpass = Path(temp_dir) / "askpass.sh"
    try:
        askpass.write_text("#!/bin/sh\nprintf '%s\\n' \"$LOCALFLOW_GIT_PASSPHRASE\"\n", encoding="utf-8")
        askpass.chmod(0o700)
        env = {
            "GIT_ASKPASS": str(askpass),
            "SSH_ASKPASS": str(askpass),
            "SSH_ASKPASS_REQUIRE": "force",
            "DISPLAY": os.environ.get("DISPLAY") or "localflow:0",
            "LOCALFLOW_GIT_PASSPHRASE": str(loaded["secret"]),
        }
        return runner(args, cwd=cwd, timeout=timeout, env=env)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def fetch_branch(
    cwd: Path,
    remote: str,
    branch: str,
    runner=run_command,
    *,
    config: dict[str, object] | None = None,
    config_path: str | None = None,
) -> CommandResult:
    """Refresh the remote-tracking ref for `branch` so callers can anchor on the live tip."""
    args = ["git", "fetch", remote, branch]
    result = runner(args, cwd=cwd, timeout=120)
    if result.ok or not config or not needs_passphrase_retry(result):
        return result
    return run_with_passphrase(args, cwd=cwd, config=config, config_path=config_path, timeout=120, runner=runner)


def push_branch(
    cwd: Path,
    remote: str,
    branch: str,
    url: str | None,
    runner=run_command,
    *,
    config: dict[str, object] | None = None,
    config_path: str | None = None,
) -> CommandResult:
    args = ["git", "push", "-u", remote, branch]
    result = runner(args, cwd=cwd, timeout=120)
    if not result.ok and config and needs_passphrase_retry(result):
        result = run_with_passphrase(args, cwd=cwd, config=config, config_path=config_path, timeout=120, runner=runner)
    if result.ok:
        return result
    fallback = https_remote_url(url)
    if fallback and fallback != url:
        fallback_result = runner(["git", "push", fallback, branch], cwd=cwd, timeout=120)
        if fallback_result.ok:
            return fallback_result
    return result


def delete_remote_branch(
    cwd: Path,
    remote: str,
    branch: str,
    url: str | None,
    runner=run_command,
    *,
    config: dict[str, object] | None = None,
    config_path: str | None = None,
) -> CommandResult:
    args = ["git", "push", remote, "--delete", branch]
    result = runner(args, cwd=cwd, timeout=120)
    if not result.ok and config and needs_passphrase_retry(result):
        result = run_with_passphrase(args, cwd=cwd, config=config, config_path=config_path, timeout=120, runner=runner)
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


def snapshot_branch(
    cwd: Path,
    branch: str,
    base_ref: str,
    paths: list[str],
    message: str,
    parent_ref: str,
    *,
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
    expected_json = str(CACHE_DIR / f"{name}.json")
    expected_md = str(CACHE_DIR / f"{name}.md")
    if data.get("json_path") == expected_json and data.get("markdown_path") == expected_md:
        return data
    payload = {key: value for key, value in data.items() if key not in {"json_path", "markdown_path"}}
    json_path, md_path = write_outputs(name, payload)
    return {**payload, "json_path": str(json_path), "markdown_path": str(md_path)}


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
