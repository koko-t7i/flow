---
name: localflow
description: Use when a local repository task involves code changes that need validation, dirty worktree handling, task branch selection, commit/push delivery, push authentication failures, temporary git worktree cleanup, or when the user invokes the `localflow check` subcommand (`/localflow check` in Claude Code, `$localflow check` in Codex) to refresh local CLI/auth/permission capability. Do not use for test-only explanation or one-off command execution unless it is part of delivering a code change or the explicit check subcommand.
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
   uv run ./localflow/scripts/check_environment.py --cwd "$PWD"

   # 2. Claude Code plugin install (prefer $CLAUDE_PLUGIN_ROOT when set).
   uv run "${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/localflow/localflow}/localflow/scripts/check_environment.py" --cwd "$PWD"

   # 3. Codex skill install.
   uv run "$HOME/.codex/skills/localflow/scripts/check_environment.py" --cwd "$PWD"
   ```

   If none of these paths exist on the current machine, stop and ask the user to point at the installed `check_environment.py`.

3. Report the Markdown snapshot path, the JSON snapshot path, and the actionable failures only. Keep secrets redacted.

## Workflow

1. **Clarify requirement.** Restate the task, acceptance criteria, scope, non-goals, and blockers. Read [references/clarify.md](references/clarify.md).
2. **Check environment capability.** Read or refresh the local CLI/auth/permission snapshot before assuming `git`, `gh`, `glab`, `docker`, package managers, or Python aliases work. Read [references/environment.md](references/environment.md).
3. **Read repository config.** If present, read the current-host config first: Codex uses `.codex/localflow.toml`; Claude Code uses `.claude/localflow.toml`. If the current-host file is missing, fall back to the other host's file. User instructions override config; config overrides defaults. If both host files exist, do not merge them.
4. **Resolve repository workflow.** Determine the long-lived base branch, delivery mode, task branch, and worktree lifecycle. Read [references/git.md](references/git.md).
5. **Implement and verify.** Use task-appropriate checks, fresh evidence, and review gates. Use TDD only when it fits code behavior work. Read [references/verify.md](references/verify.md).
6. **Commit.** Stage only current-task files and write a concise English Conventional Commit message. Read [references/contrib.md](references/contrib.md).
7. **Deliver.** Use the repository delivery mode: Local Landing, Remote Review, or Push Only. Read [references/contrib.md](references/contrib.md).
8. **Finish lifecycle.** Clean up only the branch, remote branch, and worktree owned by the current delivery unit, then return to the selected long-lived branch. Read [references/git.md](references/git.md) and [references/contrib.md](references/contrib.md).

## Module Ownership

- `clarify.md` owns task intent and acceptance criteria.
- `environment.md` owns local CLI availability, auth, permission, and remote fallback evidence.
- `git.md` owns local branch/worktree lifecycle and cleanup mechanics.
- `verify.md` owns task acceptance evidence and review gates.
- `contrib.md` owns commit, push, remote branch, and MR/PR delivery decisions.

## Repository Config

Repository config is optional and lives inside the target repository, not in the user's home directory:

- Codex: `.codex/localflow.toml`
- Claude Code: `.claude/localflow.toml`

Both files use the same schema. Prefer the current host's file; use the other only as fallback. Missing fields inherit normal localflow defaults. Invalid, conflicting, or unsafe config values are stop conditions when they affect the current task.

## Stop Conditions

Stop and ask when the requirement, acceptance criteria, safe baseline, long-lived branch, delivery mode, auth recovery step, or task/file boundary cannot be determined.

Do not commit with task-related checks failing. Do not merge or clean up lifecycle resources while required review, CI, or user approval is still pending.
