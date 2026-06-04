---
name: localflow
description: Use when a local repository task involves code changes that need validation, dirty worktree handling, task branch selection, commit/push delivery, push authentication failures, temporary git worktree cleanup, missing localflow config that must be confirmed and written, or when the user invokes a localflow subcommand (`check`, `mr`, `commit`, or `clean`). Do not use for test-only explanation or one-off command execution unless it is part of delivering a code change or an explicit subcommand.
---

# Localflow

Use for local repository changes that should end as clarified, verified, committed, and delivered according to the repository's delivery mode.

Keep this file as the workflow entrypoint. Load the referenced files only when that phase is relevant. Stop conditions and red flags in those references override forward progress.

## Subcommands

### `localflow check`

Use when the user invokes the `localflow check` subcommand (`/localflow check` in Claude Code, `$localflow check` in Codex), asks to check localflow environment capability, or wants to know which local tools/auth paths are currently usable.

This is a read-only environment check, not a delivery workflow. Do not clarify requirements, create branches, edit repository files, commit, push, or clean worktrees for this subcommand.

1. Read [references/environment.md](references/environment.md).
2. Run the environment snapshot script for the user's current working directory. Probe the candidates below in order and use the first one that resolves:

   ```bash
   # 1. Repo-local copy when cwd is inside the localflow repo.
   uv run python ./localflow/scripts/check_environment.py --cwd "$PWD"

   # 2. Claude Code plugin install (prefer $CLAUDE_PLUGIN_ROOT when set).
   uv run python "${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/localflow/localflow}/localflow/scripts/check_environment.py" --cwd "$PWD"

   # 3. Codex skill install.
   uv run python "$HOME/.codex/skills/localflow/scripts/check_environment.py" --cwd "$PWD"
   ```

   If none of these paths exist on the current machine, stop and ask the user to point at the installed `check_environment.py`.

3. Report the Markdown snapshot path, the JSON snapshot path, and the actionable failures only. Keep secrets redacted.

### Env File Inspection

Use the deterministic env-file inspection script before deciding that a fresh
worktree lacks repository-local test configuration. It reports paths, git
tracking/ignore status, redacted key names, and same-repository sibling
worktree candidates; it does not validate env value semantics or print values.

Probe the candidates below in order and use the first one that resolves:

```bash
# 1. Repo-local copy when cwd is inside the localflow repo.
uv run python ./localflow/scripts/check_env_files.py --cwd "$PWD"

# 2. Claude Code plugin install (prefer $CLAUDE_PLUGIN_ROOT when set).
uv run python "${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/localflow/localflow}/localflow/scripts/check_env_files.py" --cwd "$PWD"

# 3. Codex skill install.
uv run python "$HOME/.codex/skills/localflow/scripts/check_env_files.py" --cwd "$PWD"
```

### `localflow mr`

Use when the user invokes `/localflow mr` in Claude Code or `$localflow mr` in Codex.

This command creates or inspects the MR/PR for the current already-committed task branch. It does not implement changes, commit, merge, or clean up lifecycle resources.

1. Run the deterministic MR script for the user's current working directory. Probe the candidates below in order and use the first one that resolves:

   ```bash
   # 1. Repo-local copy when cwd is inside the localflow repo.
   uv run python ./localflow/scripts/mr.py --cwd "$PWD" --host codex

   # 2. Claude Code plugin install (prefer $CLAUDE_PLUGIN_ROOT when set).
   uv run python "${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/localflow/localflow}/localflow/scripts/mr.py" --cwd "$PWD" --host claude

   # 3. Codex skill install.
   uv run python "$HOME/.codex/skills/localflow/scripts/mr.py" --cwd "$PWD" --host codex
   ```

2. Report the Markdown snapshot path, JSON snapshot path, MR/PR URL, action, and stop reason when present. Do not hand-write fallback `git`, `gh`, or `glab` commands unless the script reports a missing script path.

#### Snapshot path (shared checkout / live preview)

Use `--snapshot` when work is uncommitted on a shared checkout that must not be disturbed — for example a frontend dev server giving a single combined live preview while multiple agents edit the same directory and branch. The default `mr` flow stops on a dirty worktree or a long-lived branch; snapshot mode bypasses both by capturing the named files into a side branch through a throwaway index, **without touching the working tree, the real index, or `HEAD`**. The dev server keeps running and no branch is switched.

```bash
uv run python ./localflow/scripts/mr.py --cwd "$PWD" --host codex \
  --snapshot --branch feat/live-preview \
  --paths src/Preview.tsx src/hooks/usePreview.ts \
  --type feat --summary "add live preview" [--bump minor]
```

- `--paths` is required and scopes the snapshot to the task's files. In a shared directory this is what keeps another agent's concurrent edits out of the MR. Two agents editing the *same* file cannot be separated — that is the inherent limit of sharing one working directory.
- Supply the message as `--message "feat(scope): summary"` or as `--type`/`--scope`/`--summary` (+ `--body`, `--breaking`). The subject is validated as an English Conventional Commit before any git write.
- `--bump patch|minor|major` injects a version bump into the snapshot only (per `[version_policy]`); the on-disk version file is left untouched.
- Re-running the same `--branch` appends a commit (parent = the existing branch tip) and updates the open MR/PR; no force push.
- The snapshot is anchored on the **live** target: snapshot mode first `git fetch`es the base branch and reads/parents the snapshot on the freshly-fetched `origin/<base>`, so a shared checkout whose local tracking ref lags the real remote does not pull already-merged files into the review. A failed fetch stops with `base_fetch_failed`.
- If the resulting snapshot would change anything **outside `--paths`** relative to the live base, the script stops with `snapshot_base_drift` and does not push — the signature of a stale/behind base. Sync the base branch (or re-`git fetch`) and retry.

### `localflow commit`

Use when the user invokes `/localflow commit` in Claude Code or `$localflow commit` in Codex, or in the default isolated-worktree flow when a finished change needs to be committed (and optionally delivered) in one step.

This command stages ONLY the named `--paths`, writes an English Conventional Commit on the current task branch, and — with `--mr` — opens the review via the normal `mr` flow. It refuses to run on a detached HEAD or a long-lived branch, never uses `git add .`, and validates the commit subject before any git write.

1. Run the deterministic commit script for the user's current working directory. Probe the candidates below in order and use the first one that resolves:

   ```bash
   # 1. Repo-local copy when cwd is inside the localflow repo.
   uv run python ./localflow/scripts/commit.py --cwd "$PWD" --host codex \
     --paths src/Preview.tsx --type feat --scope preview --summary "add live preview" [--mr]

   # 2. Claude Code plugin install (prefer $CLAUDE_PLUGIN_ROOT when set).
   uv run python "${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/localflow/localflow}/localflow/scripts/commit.py" --cwd "$PWD" --host claude --paths <files...> --message "type(scope): summary" [--mr]

   # 3. Codex skill install.
   uv run python "$HOME/.codex/skills/localflow/scripts/commit.py" --cwd "$PWD" --host codex --paths <files...> --type <t> --summary "<s>" [--mr]
   ```

2. `--paths` is required and is the only thing staged. Supply the message as `--message "type(scope): summary"` or as `--type`/`--scope`/`--summary` (+ `--body`, `--breaking`). With `--mr`, the commit and the review open in one step; if the review step fails the commit is kept (rerun `mr`). Report the JSON/Markdown snapshot path, branch, head SHA, and — when `--mr` — the MR/PR URL, action, and stop reason.

#### Which path: worktree commit vs shared snapshot

- **Default (isolated worktree / dedicated task branch):** finish the change, then `localflow commit [--mr]`. This is the normal delivery path.
- **Shared checkout where multiple agents work the same branch** (heavy feature development, a shared frontend dev server): do NOT use `commit`; deliver with `localflow mr --snapshot --paths …`, which captures the files into a side branch without touching the working tree, index, or `HEAD`.

### `localflow clean`

Use when the user invokes `/localflow clean` in Claude Code or `$localflow clean` in Codex after a task has landed.

This command only cleans already-landed delivery units. It never merges. On a task branch, it cleans that branch only after its MR/PR is merged or the branch is already merged into the base branch for Local Landing. On a long-lived branch, it scans local branches, owned worktrees, and remote branches, then cleans only candidates that are already landed.

1. Run the deterministic clean script for the user's current working directory. Probe the candidates below in order and use the first one that resolves:

   ```bash
   # 1. Repo-local copy when cwd is inside the localflow repo.
   uv run python ./localflow/scripts/clean.py --cwd "$PWD" --host codex

   # 2. Claude Code plugin install (prefer $CLAUDE_PLUGIN_ROOT when set).
   uv run python "${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/localflow/localflow}/localflow/scripts/clean.py" --cwd "$PWD" --host claude

   # 3. Codex skill install.
   uv run python "$HOME/.codex/skills/localflow/scripts/clean.py" --cwd "$PWD" --host codex
   ```

2. Report the Markdown snapshot path, JSON snapshot path, cleanup action, cleaned branches, skipped branches, and stop reason when present. Do not manually delete branches or worktrees after the script stops.

## Workflow

1. **Clarify requirement.** Restate the task, acceptance criteria, scope, non-goals, and blockers. Read [references/clarify.md](references/clarify.md).
2. **Check environment capability.** Read or refresh the local CLI/auth/permission snapshot before assuming `git`, `gh`, `glab`, `docker`, package managers, or Python aliases work. Read [references/environment.md](references/environment.md).
3. **Read repository config.** If present, read the current-host config first: Codex uses `.codex/localflow.toml`; Claude Code uses `.claude/localflow.toml`. If the current-host file is missing, fall back to the other host's file. User instructions override config; config overrides defaults. If both host files exist, do not merge them. **If neither host's config file exists** (a subcommand result shows `config_path: null`), do not silently rely on heuristics: before the first delivery action, confirm `base_branch` / `delivery_mode` / `remote_provider` (only when ambiguous) / `remote` / `draft` / `version_policy` with the user, then write `.<host>/localflow.toml`. See [references/config.md](references/config.md).
4. **Resolve repository workflow.** Determine the long-lived base branch, delivery mode, task branch, and worktree lifecycle. Default to an isolated task worktree and do not edit the original checkout. Read [references/git.md](references/git.md).
5. **Implement and verify.** Use task-appropriate checks, fresh evidence, and review gates. Use TDD only when it fits code behavior work. Read [references/verify.md](references/verify.md).
6. **Commit.** Stage only current-task files and write a concise English Conventional Commit message. In the default isolated worktree, the deterministic `localflow commit` subcommand does this (add `--mr` to commit and open the review in one step); on a shared checkout where agents share a branch, skip the commit step and deliver with `localflow mr --snapshot --paths …` instead. Read [references/contrib.md](references/contrib.md).
7. **Deliver.** Use the repository delivery mode: Local Landing, Remote Review, or Push Only. Read [references/contrib.md](references/contrib.md).
8. **Finish lifecycle.** Clean up only the branch, remote branch, and worktree owned by the current delivery unit, then return to the selected long-lived branch. Read [references/git.md](references/git.md) and [references/contrib.md](references/contrib.md).

## Module Ownership

- `clarify.md` owns task intent and acceptance criteria.
- `environment.md` owns local CLI availability, auth, permission, and remote fallback evidence.
- `git.md` owns local branch/worktree lifecycle and cleanup mechanics.
- `verify.md` owns task acceptance evidence and review gates.
- `contrib.md` owns commit, push, remote branch, MR/PR delivery decisions, and deterministic `commit`/`mr`/`clean` subcommands.
- `config.md` owns the config schema and the no-config confirm-and-write gate.

## Repository Config

Repository config is optional and lives inside the target repository, not in the user's home directory:

- Codex: `.codex/localflow.toml`
- Claude Code: `.claude/localflow.toml`

Both files use the same schema. Prefer the current host's file; use the other only as fallback. Missing fields inherit normal localflow defaults. Invalid, conflicting, or unsafe config values are stop conditions when they affect the current task. When **neither** file exists, confirm the key settings with the user and write `.<host>/localflow.toml` before delivering, rather than silently using heuristics — see [references/config.md](references/config.md). The schema and the confirm-and-write gate are owned by [references/config.md](references/config.md).

## Stop Conditions

Stop and ask when the requirement, acceptance criteria, safe baseline, long-lived branch, delivery mode, auth recovery step, or task/file boundary cannot be determined.

Do not commit with task-related checks failing. Do not merge or clean up lifecycle resources while required review, CI, or user approval is still pending.
