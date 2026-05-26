#!/usr/bin/env python3
"""Write a redacted localflow environment capability snapshot."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


CACHE_DIR = Path.home() / ".cache" / "codex-localflow"
DEFAULT_JSON_PATH = CACHE_DIR / "environment.json"
DEFAULT_MARKDOWN_PATH = CACHE_DIR / "environment.md"
DEFAULT_TIMEOUT_SECONDS = 6
SECRET_PATTERNS = (
    re.compile(r"(?i)\b(authorization|auth[_-]?header|token|password|passwd|secret)(\s*[:=]\s*)([^\n]+)"),
    re.compile(r"(?i)\b(Bearer)\s+([A-Za-z0-9._~+/=-]+)"),
    re.compile(r"\b(gh[opsu]_[A-Za-z0-9_]{6,}|github_pat_[A-Za-z0-9_]+|glpat-[A-Za-z0-9_-]+)\b"),
)


def redact(text: str | None) -> str:
    if not text:
        return ""
    redacted = text
    redacted = SECRET_PATTERNS[0].sub(r"\1\2<redacted>", redacted)
    redacted = SECRET_PATTERNS[1].sub(r"\1 <redacted>", redacted)
    redacted = SECRET_PATTERNS[2].sub("<redacted>", redacted)
    return redacted


def run_command(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: int = DEFAULT_TIMEOUT_SECONDS,
    env: dict[str, str] | None = None,
) -> dict[str, object]:
    try:
        result = subprocess.run(
            args,
            cwd=cwd,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return {
            "ok": False,
            "exit_code": None,
            "stdout": "",
            "stderr": "command not found",
            "timed_out": False,
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "ok": False,
            "exit_code": None,
            "stdout": redact(exc.stdout if isinstance(exc.stdout, str) else ""),
            "stderr": redact(exc.stderr if isinstance(exc.stderr, str) else "command timed out"),
            "timed_out": True,
        }
    return {
        "ok": result.returncode == 0,
        "exit_code": result.returncode,
        "stdout": redact(result.stdout.strip()),
        "stderr": redact(result.stderr.strip()),
        "timed_out": False,
    }


def first_line(value: object) -> str | None:
    text = str(value or "").strip()
    return text.splitlines()[0] if text else None


def api_user_summary(stdout: object) -> dict[str, object]:
    text = str(stdout or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        return {"raw": redact(first_line(text) or "")}
    if not isinstance(payload, dict):
        return {}

    summary: dict[str, object] = {}
    for key in ("login", "username", "name"):
        value = payload.get(key)
        if value:
            summary[key] = redact(str(value))
    return summary


def command_status(probe: dict[str, object]) -> dict[str, object]:
    return {
        "ok": probe["ok"],
        "exit_code": probe["exit_code"],
        "timed_out": probe["timed_out"],
        "stderr": probe["stderr"],
    }


def probe_command(name: str, version_args: list[str], *, timeout: int = DEFAULT_TIMEOUT_SECONDS) -> dict[str, object]:
    path = shutil.which(name)
    if not path:
        return {
            "installed": False,
            "configured": False,
            "auth_ok": None,
            "permission_ok": None,
            "path": None,
            "version": None,
            "version_probe": None,
        }

    probe = run_command([name, *version_args], timeout=timeout)
    return {
        "installed": True,
        "configured": probe["ok"],
        "auth_ok": None,
        "permission_ok": None,
        "path": path,
        "version": first_line(probe["stdout"]) or first_line(probe["stderr"]),
        "version_probe": probe,
    }


def classify_git_remote_failure(output: str) -> str | None:
    lower = output.lower()
    if "could not open a connection to your authentication agent" in lower:
        return "ssh_agent_missing"
    if "enter passphrase for key" in lower or "permission denied, please try again" in lower:
        return "ssh_interactive_passphrase_required"
    if "permission denied (publickey)" in lower or "perm denied (publickey)" in lower:
        return "ssh_publickey"
    if "could not resolve hostname" in lower or "name or service not known" in lower or "temporary failure" in lower:
        return "remote_unreachable"
    if "could not read from remote repository" in lower:
        return "ssh_publickey"
    return None


def remote_metadata(remote_url: str | None) -> dict[str, str | None]:
    if not remote_url:
        return {"url": None, "protocol": None, "host": None}
    if remote_url.startswith("git@") and ":" in remote_url:
        host = remote_url.split("@", 1)[1].split(":", 1)[0]
        return {"url": redact(remote_url), "protocol": "ssh", "host": host}
    parsed = urlparse(remote_url)
    protocol = "ssh" if parsed.scheme == "ssh" else parsed.scheme or None
    return {"url": redact(remote_url), "protocol": protocol, "host": parsed.hostname}


def safe_global_git_config() -> dict[str, str]:
    allowed = {
        "core.editor",
        "credential.helper",
        "init.defaultbranch",
        "pull.rebase",
        "user.email",
        "user.name",
    }
    result = run_command(["git", "config", "--global", "--list"], timeout=3)
    config: dict[str, str] = {}
    if not result["ok"]:
        return config
    for line in str(result["stdout"]).splitlines():
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.lower()
        if key in allowed:
            config[key] = redact(value)
    return config


def public_key_inventory() -> list[dict[str, str | None]]:
    keys: list[dict[str, str | None]] = []
    ssh_dir = Path.home() / ".ssh"
    for key_path in sorted(ssh_dir.glob("*.pub")):
        fingerprint = run_command(["ssh-keygen", "-lf", str(key_path)], timeout=3)
        keys.append(
            {
                "path": str(key_path),
                "fingerprint": first_line(fingerprint["stdout"]) if fingerprint["ok"] else None,
            }
        )
    return keys


def probe_git(cwd: Path) -> dict[str, object]:
    probe = probe_command("git", ["--version"])
    if not probe["installed"]:
        return probe

    probe["global_config"] = safe_global_git_config()
    remote_result = run_command(["git", "remote", "get-url", "origin"], cwd=cwd, timeout=3)
    remote_url = first_line(remote_result["stdout"]) if remote_result["ok"] else None
    probe["origin"] = remote_metadata(remote_url)
    probe["public_keys"] = public_key_inventory()

    ssh_agent = run_command(["ssh-add", "-l"], timeout=3)
    probe["ssh_agent"] = {
        "available": ssh_agent["ok"],
        "summary": first_line(ssh_agent["stdout"]) or first_line(ssh_agent["stderr"]),
        "failure_kind": classify_git_remote_failure(str(ssh_agent["stderr"])),
    }

    if remote_url:
        env = os.environ.copy()
        env["GIT_SSH_COMMAND"] = "ssh -o BatchMode=yes"
        remote_check = run_command(["git", "ls-remote", "--heads", "origin"], cwd=cwd, timeout=8, env=env)
        combined = f"{remote_check['stdout']}\n{remote_check['stderr']}"
        probe["origin_check"] = {
            "can_fetch": remote_check["ok"],
            "failure_kind": None if remote_check["ok"] else classify_git_remote_failure(combined),
            "probe": remote_check,
        }
        probe["auth_ok"] = remote_check["ok"]
    else:
        probe["origin_check"] = {"can_fetch": None, "failure_kind": "origin_missing", "probe": remote_result}
        probe["auth_ok"] = None

    probe["configured"] = bool(probe.get("global_config"))
    return probe


def probe_gh() -> dict[str, object]:
    probe = probe_command("gh", ["--version"])
    if not probe["installed"]:
        return probe
    auth = run_command(["gh", "auth", "status"], timeout=8)
    user = run_command(["gh", "api", "user"], timeout=8)
    probe["auth_status"] = auth
    probe["api_user"] = api_user_summary(user["stdout"]) if user["ok"] else {}
    probe["api_user_probe"] = command_status(user)
    probe["auth_ok"] = auth["ok"] and user["ok"]
    probe["configured"] = auth["ok"]
    return probe


def probe_glab() -> dict[str, object]:
    probe = probe_command("glab", ["--version"], timeout=8)
    if not probe["installed"]:
        return probe
    auth = run_command(["glab", "auth", "status"], timeout=8)
    user = run_command(["glab", "api", "user"], timeout=8)
    probe["auth_status"] = auth
    probe["api_user"] = api_user_summary(user["stdout"]) if user["ok"] else {}
    probe["api_user_probe"] = command_status(user)
    probe["auth_ok"] = auth["ok"] and user["ok"]
    probe["configured"] = auth["ok"]
    return probe


def probe_npm_like(name: str) -> dict[str, object]:
    probe = probe_command(name, ["--version"])
    if not probe["installed"]:
        return probe
    registry = run_command([name, "config", "get", "registry"], timeout=6)
    probe["registry"] = first_line(registry["stdout"]) if registry["ok"] else None
    if name == "npm":
        whoami = run_command(["npm", "whoami"], timeout=6)
        probe["whoami"] = whoami
        probe["auth_ok"] = whoami["ok"]
    return probe


def probe_docker() -> dict[str, object]:
    probe = probe_command("docker", ["--version"])
    if not probe["installed"]:
        return probe
    compose = run_command(["docker", "compose", "version"], timeout=6)
    info = run_command(["docker", "info"], timeout=8)
    probe["compose_version"] = first_line(compose["stdout"]) if compose["ok"] else None
    probe["compose_probe"] = compose
    probe["daemon_probe"] = info
    probe["permission_ok"] = info["ok"]
    probe["configured"] = compose["ok"]
    return probe


def build_snapshot(cwd: Path) -> dict[str, object]:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cwd": str(cwd),
        "cache": {
            "json": str(DEFAULT_JSON_PATH),
            "markdown": str(DEFAULT_MARKDOWN_PATH),
        },
        "tools": {
            "git": probe_git(cwd),
            "gh": probe_gh(),
            "glab": probe_glab(),
            "node": probe_command("node", ["--version"]),
            "npm": probe_npm_like("npm"),
            "pnpm": probe_npm_like("pnpm"),
            "python": probe_command("python", ["--version"]),
            "python3": probe_command("python3", ["--version"]),
            "docker": probe_docker(),
        },
    }


def status_text(value: object) -> str:
    if value is True:
        return "yes"
    if value is False:
        return "no"
    return "n/a"


def render_markdown(snapshot: dict[str, object]) -> str:
    tools = snapshot["tools"]
    assert isinstance(tools, dict)
    lines = [
        "# Localflow Environment Snapshot",
        "",
        f"- Generated: `{snapshot['generated_at']}`",
        f"- Working directory: `{snapshot['cwd']}`",
        "",
        "| Tool | Installed | Configured | Auth OK | Permission OK | Version |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for name, raw_tool in tools.items():
        tool = raw_tool if isinstance(raw_tool, dict) else {}
        version = str(tool.get("version") or tool.get("compose_version") or "")
        lines.append(
            "| {name} | {installed} | {configured} | {auth_ok} | {permission_ok} | {version} |".format(
                name=name,
                installed=status_text(tool.get("installed")),
                configured=status_text(tool.get("configured")),
                auth_ok=status_text(tool.get("auth_ok")),
                permission_ok=status_text(tool.get("permission_ok")),
                version=version.replace("|", "\\|"),
            )
        )

    git = tools.get("git", {})
    if isinstance(git, dict):
        origin = git.get("origin", {})
        origin_check = git.get("origin_check", {})
        ssh_agent = git.get("ssh_agent", {})
        lines.extend(
            [
                "",
                "## Git Remote",
                "",
                f"- Origin host: `{origin.get('host') if isinstance(origin, dict) else None}`",
                f"- Origin protocol: `{origin.get('protocol') if isinstance(origin, dict) else None}`",
                f"- Can fetch with BatchMode SSH: `{origin_check.get('can_fetch') if isinstance(origin_check, dict) else None}`",
                f"- Failure kind: `{origin_check.get('failure_kind') if isinstance(origin_check, dict) else None}`",
                f"- SSH agent available: `{ssh_agent.get('available') if isinstance(ssh_agent, dict) else None}`",
            ]
        )

    lines.extend(
        [
            "",
            "## Remote Operation Guidance",
            "",
            "- Prefer the configured Git remote when it works.",
            "- If SSH fails because of publickey or passphrase state, use authenticated `gh`/`glab` for remote API operations and token-backed HTTPS fallback.",
            "- Do not permanently rewrite `origin` unless the user explicitly asks.",
            "- Never read, print, store, or upload private key contents or passphrases.",
            "",
        ]
    )
    return "\n".join(lines)


def write_snapshot(snapshot: dict[str, object], json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(snapshot), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cwd", type=Path, default=Path.cwd(), help="Repository directory to inspect.")
    parser.add_argument("--json", type=Path, default=DEFAULT_JSON_PATH, help="JSON output path.")
    parser.add_argument("--markdown", type=Path, default=DEFAULT_MARKDOWN_PATH, help="Markdown output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    snapshot = build_snapshot(args.cwd.resolve())
    write_snapshot(snapshot, args.json, args.markdown)
    print(f"Wrote {args.json}")
    print(f"Wrote {args.markdown}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
