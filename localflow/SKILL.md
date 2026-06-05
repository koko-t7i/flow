---
name: localflow
description: Use when a local repository task involves code changes that need validation, dirty worktree handling, task branch selection, commit/push delivery, push authentication failures, temporary git worktree cleanup, missing localflow config that must be confirmed and written, or when the user invokes a localflow subcommand (`check`, `tree`, `fast`, `mr`, `commit`, or `clean`). Do not use for test-only explanation or one-off command execution unless it is part of delivering a code change or an explicit subcommand.
---

# Localflow

Use for local repository changes that should end as clarified, verified, committed, and delivered according to the repository's delivery mode.

Keep this file as the workflow entrypoint. Load the referenced files only when that phase is relevant. Stop conditions and red flags in those references override forward progress.

## Subcommands

### Script Resolution

When a subcommand says to run `<script>.py`, resolve the first existing script path in this order:

1. Repo-local copy: `./localflow/scripts/<script>.py`
2. Claude Code plugin install: `${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/localflow/localflow}/localflow/scripts/<script>.py`
3. Codex skill install: `$HOME/.codex/skills/localflow/scripts/<script>.py`
4. Pi skill install: `$HOME/.pi/skills/localflow/scripts/<script>.py`

For scripts that accept `--host`, use `--host codex` in Codex, `--host claude` in Claude Code, and `--host pi` in pi. If none of the paths exist, stop and ask the user to point at the installed script. Report generated JSON/Markdown paths plus the command-specific result fields; keep secrets redacted.

### `localflow check`

Use when the user invokes the `localflow check` subcommand (`/localflow check` in Claude Code or pi, `$localflow check` in Codex), asks to check localflow environment capability, or wants to know which local tools/auth paths are currently usable.

This is a read-only environment check, not a delivery workflow. Do not clarify requirements, create branches, edit repository files, commit, push, or clean worktrees for this subcommand.

1. Read [references/environment.md](references/environment.md).
2. Run `check_environment.py` for the user's current working directory:

   ```bash
   uv run python ./localflow/scripts/check_environment.py --cwd "$PWD"
   ```

3. Report the Markdown snapshot path, JSON snapshot path, and actionable failures only.

### Env File Inspection

Use the deterministic env-file inspection script before deciding that a fresh
worktree lacks repository-local test configuration. It reports paths, git
tracking/ignore status, redacted key names, and same-repository sibling
worktree candidates; it does not validate env value semantics or print values.

Run `check_env_files.py` via the shared script resolution order:

```bash
uv run python ./localflow/scripts/check_env_files.py --cwd "$PWD"
```

### `localflow mr`

Use when the user invokes `/localflow mr` in Claude Code or pi, or `$localflow mr` in Codex.

This command creates or inspects the MR/PR for the current already-committed task branch. It does not implement changes, commit, merge, or clean up lifecycle resources.

1. Run `mr.py` for the user's current working directory:

   ```bash
   uv run python ./localflow/scripts/mr.py --cwd "$PWD" --host codex
   ```

2. Report the Markdown snapshot path, JSON snapshot path, MR/PR URL, action, and stop reason when present. Do not hand-write fallback `git`, `gh`, or `glab` commands unless the script reports a missing script path.

### `localflow tree`

Use when the user invokes `/localflow tree` in Claude Code or pi, or `$localflow tree` in Codex, or asks for the normal isolated-worktree review flow.

This is the default review workflow. Read [references/modes/tree.md](references/modes/tree.md), then continue through the normal workflow using `localflow commit`, `localflow mr`, and later `localflow clean` after the MR/PR is merged.

### `localflow fast`

Use when the user invokes `/localflow fast` in Claude Code or pi, or `$localflow fast` in Codex, after a task branch has already been committed in an isolated worktree.

This command lands the clean task branch into the local long-lived branch by rebase + fast-forward merge. It does not create an MR/PR, does not push to remote, and does not clean task worktrees or branches.

1. Read [references/modes/fast.md](references/modes/fast.md).
2. Run `fast.py` from the clean committed task worktree:

   ```bash
   uv run python ./localflow/scripts/fast.py --cwd "$PWD" --host codex
   ```

3. Report the Markdown snapshot path, JSON snapshot path, base branch, task branch, landed SHA, post-merge check result, local base ahead/behind remote counts, and that cleanup was not run. Do not manually delete worktrees or branches after `fast`; use `localflow clean` when cleanup is desired.

#### Snapshot path (shared checkout / live preview)

Use `--snapshot` when work is uncommitted on a shared checkout that must not be disturbed — for example a frontend dev server giving a single combined live preview while multiple agents edit the same directory and branch. The default `mr` flow stops on a dirty worktree or a long-lived branch; snapshot mode bypasses both by capturing the named files into a side branch through a throwaway index, **without touching the working tree, the real index, or `HEAD`**. The dev server keeps running and no branch is switched.

```bash
uv run python ./localflow/scripts/mr.py --cwd "$PWD" --host codex \
  --snapshot --branch feat/live-preview \
  --paths src/Preview.tsx src/hooks/usePreview.ts \
  --type feat --summary "add live preview"
```

- `--paths` is required and scopes the snapshot to the task's files. In a shared directory this is what keeps another agent's concurrent edits out of the MR. Two agents editing the *same* file cannot be separated — that is the inherent limit of sharing one working directory.
- Supply the message as `--message "feat(scope): summary"` or as `--type`/`--scope`/`--summary` (+ `--body`, `--breaking`). The subject is validated as an English Conventional Commit before any git write.
- Re-running the same `--branch` appends a commit (parent = the existing branch tip) and updates the open MR/PR; no force push.
- The snapshot is anchored on the **live** target: snapshot mode first `git fetch`es the base branch and reads/parents the snapshot on the freshly-fetched `origin/<base>`, so a shared checkout whose local tracking ref lags the real remote does not pull already-merged files into the review. A failed fetch stops with `base_fetch_failed`.
- If the resulting snapshot would change anything **outside `--paths`** relative to the live base, the script stops with `snapshot_base_drift` and does not push — the signature of a stale/behind base. Sync the base branch (or re-`git fetch`) and retry.

### `localflow commit`

Use when the user invokes `/localflow commit` in Claude Code or pi, or `$localflow commit` in Codex, or in the default isolated-worktree flow when a finished change needs to be committed (and optionally delivered) in one step.

This command stages ONLY the named `--paths`, writes an English Conventional Commit on the current task branch, and — with `--mr` — opens the review via the normal `mr` flow. It refuses to run on a detached HEAD or a long-lived branch, never uses `git add .`, and validates the commit subject before any git write.

1. Run `commit.py` from the task worktree:

   ```bash
   uv run python ./localflow/scripts/commit.py --cwd "$PWD" --host codex \
     --paths src/Preview.tsx --type feat --scope preview --summary "add live preview" [--mr]
   ```

2. `--paths` is required and is the only thing staged. Supply the message as `--message "type(scope): summary"` or as `--type`/`--scope`/`--summary` (+ `--body`, `--breaking`). With `--mr`, the commit and the review open in one step; if the review step fails the commit is kept (rerun `mr`). Report the JSON/Markdown snapshot path, branch, head SHA, and — when `--mr` — the MR/PR URL, action, and stop reason.

#### Which path: worktree commit vs shared snapshot

- **Default (isolated worktree / dedicated task branch):** finish the change, then `localflow commit [--mr]`. This is the normal delivery path.
- **Shared checkout where multiple agents work the same branch** (heavy feature development, a shared frontend dev server): do NOT use `commit`; deliver with `localflow mr --snapshot --paths …`, which captures the files into a side branch without touching the working tree, index, or `HEAD`.

### `localflow clean`

Use when the user invokes `/localflow clean` in Claude Code or pi, or `$localflow clean` in Codex, after a task has landed.

This command only cleans already-landed delivery units. It never merges. On a task branch, it cleans that branch only after its MR/PR is merged or the branch is already merged into the base branch for Local Landing. On a long-lived branch, it scans local branches, owned worktrees, and remote branches, then cleans only candidates that are already landed.

1. Run `clean.py` for the user's current working directory:

   ```bash
   uv run python ./localflow/scripts/clean.py --cwd "$PWD" --host codex
   ```

2. Report the Markdown snapshot path, JSON snapshot path, cleanup action, cleaned branches, skipped branches, and stop reason when present. Do not manually delete branches or worktrees after the script stops.

## Workflow

1. **Clarify requirement.** Restate the task, acceptance criteria, scope, non-goals, and blockers. Read [references/clarify.md](references/clarify.md).
2. **Check environment capability.** Read or refresh the local CLI/auth/permission snapshot before assuming `git`, `gh`, `glab`, `docker`, package managers, or Python aliases work. Read [references/environment.md](references/environment.md).
3. **Read repository config.** If present, read the current-host config first: Codex uses `.codex/localflow.toml`; Claude Code uses `.claude/localflow.toml`; pi uses `.pi/localflow.toml`. If the current-host file is missing, fall back to the other hosts' files. User instructions override config; config overrides defaults. If both host files exist, do not merge them. **If neither host's config file exists or the file is old schema**, do not silently rely on heuristics: before the first delivery action, confirm `base_branch` / `remote_cli` / `passphrase` / `default_mode` with the user, then write `.<host>/localflow.toml`. See [references/config.md](references/config.md).
4. **Resolve repository workflow.** Determine the long-lived base branch, default mode (`tree` or `fast`), task branch, and worktree lifecycle. Default to `tree` with an isolated task worktree and do not edit the original checkout. `remote_cli = "none"` means no MR/PR review can be created; use `fast` for local landing. Read [references/git.md](references/git.md), [references/modes/tree.md](references/modes/tree.md), and [references/modes/fast.md](references/modes/fast.md) as needed.
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
- `modes/tree.md` owns the isolated-worktree remote-review flow.
- `modes/fast.md` owns the isolated-worktree local-integration flow.

## Repository Config

Repository config is optional and lives inside the target repository, not in the user's home directory:

- Codex: `.codex/localflow.toml`
- Claude Code: `.claude/localflow.toml`
- Pi: `.pi/localflow.toml`

All files use the same schema. Prefer the current host's file; use the other only as fallback. The required fields are `base_branch`, `remote_cli`, `passphrase`, and `default_mode`; missing or old-schema fields are stop conditions until the user confirms the current repository settings. See [references/config.md](references/config.md). The schema and the confirm-and-write gate are owned by [references/config.md](references/config.md).

## Stop Conditions

Stop and ask when the requirement, acceptance criteria, safe baseline, long-lived branch, delivery mode, auth recovery step, or task/file boundary cannot be determined.

Do not commit with task-related checks failing. Do not merge or clean up lifecycle resources while required review, CI, or user approval is still pending.
