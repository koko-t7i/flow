---
name: local-workflow
description: Local code-change workflow for Codex. Use when a task involves local code modification, TDD, requirement confirmation, task breakdown, test repair, review, committing, pushing a new branch, deciding whether to isolate work in a git worktree, or cleaning up a temporary worktree after push.
---

# Local Workflow

Use this workflow for local repository changes that should end as a reviewed, committed, pushed branch. Stop at push; do not create an MR or PR unless the user separately asks.

## 1. Clarify Scope

Start by making the request concrete:

- Identify the requirement, acceptance criteria, likely impact area, and explicit non-goals.
- If the user is asking a question or the request is underspecified, restate the understood task before asking for confirmation.
- In the restatement include what the user wants solved, the expected result, likely affected code, and the current unknowns.
- Ask follow-up questions only when the gap changes implementation direction, acceptance criteria, or risk boundaries.
- Inspect the repo or existing context first when the missing detail can reasonably be discovered locally.

Stop if the requirement or acceptance criteria remain too unclear to implement safely after restating and asking for confirmation.

## 2. Inspect State And Choose Baseline

Before implementation, inspect the repository state:

- Run `git status`, identify the current branch, and check remote tracking state.
- Check for uncommitted changes and note which files they touch.
- Confirm the baseline branch and remote state. Stop if the baseline or remote cannot be determined.
- For independent new tasks, base work on `origin/main`.
- Use the current `HEAD` only when the task explicitly depends on work already present on the current branch.

## 3. Decide Worktree Isolation

Protect existing local work:

- If the current task could affect code touched by uncommitted changes, create a temporary git worktree.
- Create the worktree from the selected baseline, not from assumptions about the current working directory.
- Remember that dirty uncommitted changes do not automatically appear in a new worktree. Do not rely on them unless they are deliberately copied or committed as part of the chosen baseline.
- Stop if worktree isolation is required but the worktree cannot be created.

After a successful push from a temporary worktree, remove that worktree and run `git worktree prune`.

## 4. Create The Task Branch

Create or switch to a task branch before editing. Use `type/slug`:

- `feat/user-export`
- `fix/login-timeout`
- `test/cache-refresh`
- `refactor/cache-layer`

Use a branch type that matches the change. Stop before push if the branch name does not follow `type/slug`.

## 5. Execute With TDD

Work in small verifiable steps:

- Break the requirement into small tasks with observable checks.
- Write a failing test first for each behavior when the repository has a practical test surface.
- Run the focused test and confirm it fails for the expected reason.
- Implement the smallest code change that makes the test pass.
- Run the focused test again.
- If tests fail, determine whether the failure comes from the current change.
- Fix failures caused by the current change before continuing.
- If a failure is existing or unrelated, record evidence and leave it alone unless the user requested that fix.
- Refactor only when it improves the current change, then rerun the relevant tests.

Do not commit when tests related to the current task are failing.

## 6. Verify Before Review

Before review, run the checks appropriate to the repository:

- Run relevant tests.
- Run formatter or lint commands when the repo provides them.
- If no usable test or check command exists, record that explicitly.
- Inspect `git diff`.
- Confirm the diff contains only task-related files.
- Confirm no secrets, credentials, local env files, logs, build artifacts, or temporary files are staged or included.

## 7. Review Gate

Review the final diff as a code reviewer:

- Look for behavioral regressions, hard correctness issues, missing edge cases, and missing tests.
- Check that the implementation matches the acceptance criteria and non-goals.
- Check for unrelated refactors or accidental file churn.
- Stop if review finds a high-confidence hard issue.
- Proceed only when the review has no blocking issue.

## 8. Commit

Commit only after the review gate passes:

- Stage only files that belong to the current task.
- Use an English Conventional Commit message, such as `feat: add user export`.
- Confirm the branch contains only commits related to this task.
- Confirm the commit does not include unrelated files, secrets, credentials, local env files, logs, build artifacts, or temporary files.

## 9. Push And Clean Up

Before push:

- Confirm the branch name follows `type/slug`.
- Confirm the commit message follows Conventional Commits.
- Confirm relevant tests and checks passed, or record why a command was unavailable.
- Confirm the branch contains only current-task commits.

Push the new branch to `origin`. If push fails and local evidence is not enough to identify a safe fix, stop and report the failure.

After a successful push from a temporary worktree, delete the worktree and run `git worktree prune`.
