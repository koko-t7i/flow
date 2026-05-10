---
name: localflow
description: Use when a local repository task involves code changes that need validation, dirty worktree handling, task branch selection, commit/push delivery, push authentication failures, or temporary git worktree cleanup. Do not use for test-only explanation or one-off command execution unless it is part of delivering a code change.
---

# Localflow

Use for local repo changes that should end as reviewed, committed, and pushed work. Stop at push; create no MR/PR unless explicitly asked.

## 1. Clarify Scope

Make the request concrete: requirement, acceptance criteria, likely impact area, and explicit non-goals. Inspect local context before asking. If the user's description is unclear, analyze the available context, briefly restate the understood task and remaining question, then wait for user confirmation before implementing. Ask only for gaps that change direction, acceptance, or risk. Stop if safe implementation remains unclear.

## 2. Inspect State And Choose Mode

Run `git status`; identify branch, tracking state, uncommitted files, remote URL, and remote default. Prefer `origin/main` for independent new tasks only when it exists; otherwise use the detected remote default. Stop if the safe baseline cannot be determined.

Choose one mode:

- **New task:** independent implementation. Start from the selected clean baseline, create/switch to a task branch, and use TDD where practical.
- **Existing changes:** user wants the current dirty tree delivered. Work in place; do not create a worktree by default.

Use the current `HEAD` only when the task explicitly depends on work already present on the current branch.

## 3. Decide Worktree Isolation

In new task mode, create a temporary git worktree if the task could collide with uncommitted local work. Create it from the selected baseline. Dirty changes do not appear in a new worktree unless deliberately copied or committed. Stop if required isolation cannot be created. After a successful push from a temporary worktree, delete it and run `git worktree prune`.

## 4. Create The Task Branch

Use `type/slug` branches such as `feat/user-export`, `fix/login-timeout`, `test/cache-refresh`, or `refactor/cache-layer`. In existing changes mode, keep the current branch if it is already correct; otherwise create/switch before staging. Stop before push if the branch name does not follow `type/slug`.

## 5. Execute With TDD

Break work into observable checks. When practical, write the failing test first, confirm the expected failure, implement the smallest fix, rerun, then refactor only when it improves the current change. Fix failures caused by this task. For existing or unrelated failures, record evidence and leave them alone unless requested. Do not commit with task-related tests failing.

## 6. Verify Before Review

Run relevant tests and repo-provided lint/format checks; record unavailable commands. Inspect `git diff`. Confirm the diff and staged files contain only task-related work and no secrets, credentials, local env files, logs, build artifacts, or temporary files. In existing changes mode, stage only requested-task files and leave unrelated user changes unstaged.

## 7. Review Gate

Review the final diff as a code reviewer. Check acceptance criteria, regressions, hard correctness issues, missing edge cases/tests, unrelated refactors, and accidental churn. Stop on any high-confidence blocking issue.

## 8. Commit

After review passes, stage only current-task files. Use an English Conventional Commit message such as `feat: add user export`. Confirm the branch and commit contain only current-task work and no sensitive or generated junk.

## 9. Push, Recover Auth, And Clean Up

Before push, confirm branch name, Conventional Commit message, test/check results, and current-task-only commits.

Push the branch to `origin`. If push fails:

- Inspect the remote URL, upstream configuration, and exact error.
- For SSH failures, check agent state and whether the expected key is loaded in the same shell.
- If a passphrase is needed, ask through the interactive prompt; never print, store, or commit secrets.
- Use HTTPS fallback only when credentials are already configured or explicitly authorized.
- Stop when the safe next action is unclear.

After a successful push from a temporary worktree, delete the worktree and run `git worktree prune`.

## 10. Final Report

Report: mode used; branch; commit hash/message; pushed ref; tests/checks run; skipped checks with reasons; review result and remaining risk; worktree cleanup; MR/PR status, normally "not created".

## Pressure Scenarios

Check these cases: new feature starts from clean remote baseline; "commit/push these changes" stages only relevant dirty files; repos without `origin/main` use the real default; `Permission denied (publickey)` triggers SSH diagnosis without secret exposure; unrelated failing tests are reported, not silently fixed.
