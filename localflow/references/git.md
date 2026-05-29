# Git Lifecycle

## Core Principle

Treat the long-lived branch, task branch, worktree, remote branch, and MR/PR as one delivery unit with an explicit lifecycle.

## Long-Lived Branch

Use one repository long-lived branch as the base and return target. Allowed long-lived branches are `main`, `test`, and `dev`.

If a repository preference is already known in the conversation or memory, reuse it. Otherwise choose from the existing `main`/`test`/`dev` branches. If multiple are plausible and the user has not chosen, ask once and then treat the answer as fixed for that repository.

Do not implement directly on the long-lived branch. Use it as the clean base for task branches and as the final local resting branch after cleanup.

## Task Branch and Worktree

New tasks default to a `type/slug` task branch plus an isolated worktree, created from the selected long-lived branch.

Use a lean preflight before creating a worktree: gather current branch, dirty state, worktree status, and submodule/nested-worktree risk in the fewest commands practical. Do not create nested worktrees.

In existing-changes mode, work in place only when the user clearly wants current dirty changes delivered. If those changes are on a long-lived branch, stop and confirm whether to move them to a task branch before staging.

Track lifecycle provenance:

- long-lived branch
- task branch
- worktree path
- remote branch, after push
- MR/PR URL, after creation
- delivery mode

## Lifecycle States

- **Prepared:** task branch and worktree exist.
- **In progress:** implementation and verification happen only in the task worktree.
- **Committed:** task commits exist and local checks/review gate are complete.
- **Delivered:** Local Landing merged locally, Remote Review MR/PR created, or Push Only pushed.
- **Landed:** local merge completed or MR/PR merged.
- **Cleaned:** task worktree and task branches owned by this delivery unit are removed; checkout is back on the long-lived branch.

## Cleanup Mechanics

Clean up local task branch and worktree only after the work has landed or the user explicitly aborts.

For Local Landing, cleanup after merging the task branch into the selected long-lived branch and rerunning required post-merge checks.

For Remote Review, keep the worktree and local task branch until the MR/PR is merged. Use the same worktree for review fixes, CI failures, and conflict resolution.

After landing:

- confirm the worktree has no uncommitted task work
- switch the main checkout back to the selected long-lived branch
- remove the task worktree if this workflow created it
- delete the local task branch
- run `git worktree prune` only when stale entries are detected or after failed/aborted worktree operations

Do not remove a worktree that is harness-owned, contains unrelated user changes, or was not created for this delivery unit.

## Stop Conditions

Stop when the long-lived branch cannot be chosen, the safe base cannot be identified, dirty-tree ownership is unclear, worktree isolation cannot be created, or cleanup would affect work outside this delivery unit.

## Common Mistakes

- Starting from current `HEAD` when the task should start from the long-lived branch.
- Creating a nested worktree.
- Cleaning a task worktree before Remote Review has merged.
- Leaving the checkout on a task branch after landing.

## Red Flags

- Current branch is `main`, `test`, or `dev` and edits are about to start in place.
- Uncommitted files exist but the task does not explain ownership.
- A task branch does not follow `type/slug`.
- Cleanup would delete work without explicit landing or abort confirmation.
