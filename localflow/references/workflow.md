# Workflow, Branching, and Isolation

## Core Principle

Protect user work and repository history before optimizing for speed. Determine the real baseline, branch, and dirty-tree state before editing.

## Process

Make the request concrete: requirement, acceptance criteria, likely impact area, and explicit non-goals. Inspect local context before asking. If the user's description is unclear, analyze available context, briefly restate the understood task and remaining question, then wait for confirmation before implementing.

Run `git status`; identify branch, tracking state, uncommitted files, remote URL, and remote default. Prefer `origin/main` for independent new tasks only when it exists; otherwise use the detected remote default.

Choose one mode:

- **New task:** independent implementation. Start from the selected clean baseline, create/switch to a task branch, and use TDD where practical.
- **Existing changes:** user wants the current dirty tree delivered. Work in place; do not create a worktree by default.

Use the current `HEAD` only when the task explicitly depends on work already present on the current branch.

Use `type/slug` branches such as `feat/user-export`, `fix/login-timeout`, `test/cache-refresh`, or `refactor/cache-layer`.

## Protected Branches

Do not implement or commit directly on `main`, `master`, `dev`, `develop`, `staging`, `production`, `release/*`, or `hotfix/*` unless the user explicitly asks for that branch. Create a task branch from the safe baseline instead.

If the user asks to deliver existing dirty changes while on a protected branch, stop and confirm whether to create a task branch before staging.

## Worktree Isolation

Before creating a worktree, detect whether the current directory is already a linked worktree and whether it is inside a submodule. Do not create nested worktrees.

In new task mode, create a temporary git worktree if the task could collide with uncommitted local work. Create it from the selected baseline. Dirty changes do not appear in a new worktree unless deliberately copied or committed.

Track worktree provenance. Clean up only worktrees created for this task or clearly owned by this workflow.

## Stop Conditions

Stop when the requirement, acceptance criteria, safe baseline, branch target, dirty-tree ownership, or worktree isolation path cannot be determined.

Stop before push if the branch name does not follow `type/slug`, unless the user explicitly chose a different branch naming convention.

## Common Mistakes

- Starting from `HEAD` when the task is independent of current branch work.
- Asking the user where files or branches are before inspecting the repo.
- Creating a worktree without checking whether the current directory is already one.
- Assuming `origin/main` exists instead of detecting the remote default.

## Red Flags

- Current branch is protected and the user did not explicitly request direct work there.
- Uncommitted files exist and the task boundary does not explain whether they belong to this work.
- Safe baseline cannot be identified.
- A required worktree cannot be created or safely cleaned up.
