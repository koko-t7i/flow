---
name: localflow
description: Use when a local repository task involves code changes that need validation, dirty worktree handling, task branch selection, commit/push delivery, push authentication failures, temporary git worktree cleanup, or when the user invokes `$localflow check` to refresh local CLI/auth/permission capability. Do not use for test-only explanation or one-off command execution unless it is part of delivering a code change or the explicit check subcommand.
---

# Localflow

Use for local repository changes that should end as clarified, verified, committed, and delivered according to the repository's delivery mode.

Keep this file as the workflow entrypoint. Load the referenced files only when that phase is relevant. Stop conditions and red flags in those references override forward progress.

## Subcommands

### `$localflow check`

Use when the user invokes `$localflow check`, asks to check localflow environment capability, or wants to know which local tools/auth paths are currently usable.

This is a read-only environment check, not a delivery workflow. Do not clarify requirements, create branches, edit repository files, commit, push, or clean worktrees for this subcommand.

1. Read [references/environment.md](references/environment.md).
2. Run the environment snapshot script for the user's current working directory:

   ```bash
   python3 ./localflow/scripts/check_environment.py --cwd "$PWD"
   ```

   If the current repository does not contain the skill source tree, run the installed skill copy instead:

   ```bash
   python3 /home/koko/.codex/skills/localflow/scripts/check_environment.py --cwd "$PWD"
   ```

3. Report the Markdown snapshot path, the JSON snapshot path, and the actionable failures only. Keep secrets redacted.

## Workflow

1. **Clarify requirement.** Restate the task, acceptance criteria, scope, non-goals, and blockers. Read [references/clarify.md](references/clarify.md).
2. **Check environment capability.** Read or refresh the local CLI/auth/permission snapshot before assuming `git`, `gh`, `glab`, `docker`, package managers, or Python aliases work. Read [references/environment.md](references/environment.md).
3. **Resolve repository workflow.** Determine the long-lived base branch, delivery mode, task branch, and worktree lifecycle. Read [references/git.md](references/git.md).
4. **Implement and verify.** Use task-appropriate checks, fresh evidence, and review gates. Use TDD only when it fits code behavior work. Read [references/verify.md](references/verify.md).
5. **Commit.** Stage only current-task files and write a concise English Conventional Commit message. Read [references/contrib.md](references/contrib.md).
6. **Deliver.** Use the repository delivery mode: Local Landing, Remote Review, or Push Only. Read [references/contrib.md](references/contrib.md).
7. **Finish lifecycle.** Clean up only the branch, remote branch, and worktree owned by the current delivery unit, then return to the selected long-lived branch. Read [references/git.md](references/git.md) and [references/contrib.md](references/contrib.md).

## Module Ownership

- `clarify.md` owns task intent and acceptance criteria.
- `environment.md` owns local CLI availability, auth, permission, and remote fallback evidence.
- `git.md` owns local branch/worktree lifecycle and cleanup mechanics.
- `verify.md` owns task acceptance evidence and review gates.
- `contrib.md` owns commit, push, remote branch, and MR/PR delivery decisions.

## Stop Conditions

Stop and ask when the requirement, acceptance criteria, safe baseline, long-lived branch, delivery mode, auth recovery step, or task/file boundary cannot be determined.

Do not commit with task-related checks failing. Do not merge or clean up lifecycle resources while required review, CI, or user approval is still pending.
