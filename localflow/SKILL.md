---
name: localflow
description: Use when a local repository task involves code changes that need validation, dirty worktree handling, task branch selection, commit/push delivery, push authentication failures, or temporary git worktree cleanup. Do not use for test-only explanation or one-off command execution unless it is part of delivering a code change.
---

# Localflow

Use for local repo changes that should end as reviewed, committed, and pushed work. Stop at push; create no MR/PR unless explicitly asked.

Keep this file as the workflow entrypoint. Load the referenced files only when that phase is relevant. Stop conditions and red flags in those references override forward progress.

## Workflow

1. **Clarify and choose mode.** Make the request concrete, inspect local repo state, and decide whether this is a new task or existing dirty-tree delivery. Read [references/workflow.md](references/workflow.md).
2. **Branch and isolate.** Use the detected remote default for independent new tasks. Create or switch to a `type/slug` branch, and use a temporary worktree when new work could collide with local changes. Read [references/workflow.md](references/workflow.md).
3. **Implement and verify.** Use TDD where practical, run relevant repo checks, inspect the diff, and perform a final review gate. Read [references/validation.md](references/validation.md).
4. **Commit.** Stage only current-task files and write a concise English Conventional Commit message. Read [references/commit.md](references/commit.md) before committing.
5. **Push and clean up.** Push to `origin`, recover auth issues safely, clean up temporary worktrees, and report the final state. Read [references/push-cleanup.md](references/push-cleanup.md).

## Stop Conditions

Stop and ask when the requirement, safe baseline, branch target, auth recovery step, or task/file boundary cannot be determined from the repo and the user's request.

Do not commit with task-related checks failing. For unrelated failures, record evidence and leave them alone unless requested.

## Pressure Scenarios

Check these cases: new feature starts from a clean remote baseline; "commit/push these changes" stages only relevant dirty files; repos without `origin/main` use the real default; `Permission denied (publickey)` triggers SSH diagnosis without secret exposure; unrelated failing tests are reported, not silently fixed.
