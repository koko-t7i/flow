# Environment Capability

## Core Principle

Do not infer tool availability, auth, or permissions from command names alone. Use the localflow environment snapshot before choosing Git, GitHub, GitLab, Docker, package-manager, or Python commands.

## Snapshot

The snapshot is local cache, not repository state:

- JSON: `~/.cache/codex-localflow/environment.json`
- Markdown: `~/.cache/codex-localflow/environment.md`

Refresh it when missing, older than 24 hours, or when the task depends on live auth or permissions:

```bash
uv run ./localflow/scripts/check_environment.py
```

If the current repository does not contain the skill source tree, use the installed skill copy:

```bash
uv run /home/koko/.codex/skills/localflow/scripts/check_environment.py --cwd "$PWD"
```

Read the Markdown summary first for quick decisions. Read the JSON when you need exact failure kinds, command paths, or probe output.

## Status Fields

- `installed`: the executable exists on `PATH`.
- `configured`: basic config/version probes succeeded.
- `auth_ok`: authenticated API or registry check succeeded when applicable.
- `permission_ok`: local runtime permission succeeded when applicable, such as Docker daemon access.
- `sudo_permission_ok`: non-interactive sudo runtime permission succeeded when applicable.

Keep these separate. A tool can be installed but unusable for a task because auth or permissions fail.

## Remote Operations

Prefer the repository's configured Git remote when it works. For SSH remotes, the snapshot checks fetch capability with:

```bash
GIT_SSH_COMMAND='ssh -o BatchMode=yes' git ls-remote --heads origin
```

Use the recorded failure kind:

- `ssh_publickey`: no accepted key was available for the remote.
- `ssh_interactive_passphrase_required`: a key likely exists but needs user passphrase entry.
- `ssh_agent_missing`: no usable `ssh-agent` is available in the shell.
- `remote_unreachable`: host or network failure, not an auth decision.

When SSH is blocked by publickey or passphrase state and `gh` or `glab` is authenticated, use that CLI for remote API operations. For fetch/push recovery, prefer a temporary HTTPS/token-backed fallback over rewriting `origin`.

Do not permanently change `origin` from SSH to HTTPS unless the user explicitly asks.

## SSH Key Boundaries

It is safe to discover public key files such as `~/.ssh/id_ed25519.pub` and `~/.ssh/id_rsa.pub`.

Never read, print, store, upload, or script private key contents or passphrases. If a passphrase is needed, stop and ask the user to unlock the key, for example:

```bash
eval "$(ssh-agent -s)"
ssh-add ~/.ssh/id_rsa
```

Uploading a public key to GitHub or GitLab changes account security state. Do it only after explicit user approval.

## Tool Notes

- `python` and `python3` are independent; use the one the snapshot marks installed.
- Docker requires both the client and daemon permission. `docker --version` alone does not prove container commands will work.
- Docker sudo probing uses `sudo -n docker info` only. It records passwordless sudo capability without prompting for a password.
- Run the environment snapshot with `uv run`; the script also records whether `uv`, `python`, and `python3` are available.
- `npm`/`pnpm` registry access and npm publish/auth state are separate from install/version checks.
- `gh` and `glab` auth status proves API access only when paired with a read-only API call such as `gh api user` or `glab api user`.
