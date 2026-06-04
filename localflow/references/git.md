# Git Lifecycle

## Core Principle

Treat the long-lived branch, task branch, worktree, remote branch, and MR/PR as one delivery unit with an explicit lifecycle.

## Long-Lived Branch

Use one repository long-lived branch as the base and return target. Allowed long-lived branches are `main`, `test`, and `dev`.

If repository config sets `base_branch`, use it after confirming the branch exists. Otherwise, if a repository preference is already known in the conversation or memory, reuse it. Otherwise choose from the existing `main`/`test`/`dev` branches. If multiple are plausible and the user has not chosen, ask once and then treat the answer as fixed for that repository.

Do not implement directly on the long-lived branch or original checkout. Use it only as the clean base for task worktrees and as the final local resting branch after cleanup.

## Long-Lived Branch Destructive Guard

When the current branch is `main`, `test`, or `dev`, do not run destructive operations unless the user has explicitly instructed or confirmed that exact operation.

Destructive operations include commands that discard, overwrite, delete, or force-update work. Treat equivalent commands and aliases the same way.

| Command pattern | What can be lost | Long-lived branch rule |
| --- | --- | --- |
| `git reset --hard` | Uncommitted tracked-file edits and index state. | Require explicit confirmation. |
| `git clean -fd`, `git clean -fdx` | Untracked files, ignored files with `-x`, generated or local-only files. | Require explicit confirmation. |
| `git checkout -- <path>` | Local edits in selected tracked files. | Require explicit confirmation. |
| `git restore <path>`, `git restore --source ... <path>` | Local edits in selected tracked files, or replacement from another tree. | Require explicit confirmation. |
| `git branch -D <branch>` | Local commits reachable only from that branch. | Require explicit confirmation; never target a long-lived branch. |
| `git worktree remove --force <path>` | Uncommitted work inside that worktree. | Require explicit confirmation and ownership proof. |
| `rm -rf <repo-path>` | Files or directories under repository ownership. | Require explicit confirmation. |
| `git push --force`, `git push --force-with-lease` | Remote commits or review history. | Require explicit confirmation; never force-push a shared long-lived branch. |

Before using an exception, state the current branch, exact command, affected files or resources, and expected data loss or cleanup effect. Wait for the user's confirmation before continuing.

Read-only inspection, fetch, fast-forward synchronization, and creating an isolated task worktree from a long-lived branch are not destructive operations.

## Task Branch and Worktree

New tasks default to a `type/slug` task branch plus an isolated worktree, created from the selected long-lived branch. Missing `worktree_mode` means `isolated`.

Do not ask whether to create a worktree for normal implementation work. Create or reuse a safe task worktree before editing files. If the current directory is already a linked worktree, reuse it only when it is on a task branch, not nested, and dirty-tree ownership is clear.

If repository config sets `worktree_mode = "isolated"`, use an isolated worktree. If it sets `worktree_mode = "in_place"`, treat the config as durable current-branch delivery approval for that repository, so the user does not need to repeat it every task. Work in place only when the current branch is not a long-lived branch and dirty-tree ownership is clear.

Use a lean preflight before creating a worktree: gather current branch, dirty state, worktree status, and submodule/nested-worktree risk in the fewest commands practical. Do not create nested worktrees.

After creating or selecting an isolated worktree, run `check_env_files.py` from the source checkout, task worktree, or installed localflow copy to inspect repository env-file availability before verification. Sync local ignored environment files that repository checks need from the source checkout into the task worktree. Preserve relative paths for files such as `.env`, `.env.*`, `*/.env`, and `*/.env.*`; do not print secret values; confirm the copied files are ignored with `git check-ignore` or `git status --ignored`; never stage or commit them. If the source checkout lacks the required env files, use the script's same-repository sibling worktree candidates before declaring databases, Redis, or other local services unavailable, and report only the source path used.

In existing-changes mode, do not keep editing the original checkout by default. Stop when the original checkout is dirty, identify the files, and move or recreate the work in a task worktree only after the user clearly confirms those changes belong to the current task. If those changes are on a long-lived branch, do not stage or continue there.

## Shared-Checkout Snapshot

Some setups require one shared checkout to stay live — most commonly a frontend dev server giving a single combined preview while several agents edit the same directory and branch. A live preview binds to a directory, not a branch, so isolating into per-agent worktrees would split the preview. For these, do not switch the branch or commit on the shared checkout. Instead use `localflow mr --snapshot` (see contrib.md), which records the named task files into a side branch through a throwaway `GIT_INDEX_FILE`, leaving the working tree, real index, and `HEAD` untouched. This is a non-destructive, read-only operation on the shared checkout (consistent with the destructive-guard table above), so the preview is never interrupted and no other agent's context is disturbed. Scope it with `--paths`; two agents editing the same file still cannot be separated, which is the inherent limit of sharing one working directory.

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

Stop when configured `base_branch` does not exist, configured `worktree_mode` is unsafe for the current branch, the long-lived branch cannot be chosen, the safe base cannot be identified, dirty-tree ownership is unclear, worktree isolation cannot be created, existing changes cannot be safely moved to a task worktree, or cleanup would affect work outside this delivery unit.

## Common Mistakes

- Starting from current `HEAD` when the task should start from the long-lived branch.
- Editing files in the original checkout before entering a task worktree.
- Running destructive operations from `main`, `test`, or `dev` without explicit user confirmation.
- Creating a nested worktree.
- Cleaning a task worktree before Remote Review has merged.
- Leaving the checkout on a task branch after landing.

## Red Flags

- Current branch is `main`, `test`, or `dev` and edits are about to start in place.
- Current branch is `main`, `test`, or `dev` and a destructive command is about to run without explicit confirmation.
- Uncommitted files exist but the task does not explain ownership.
- A task branch does not follow `type/slug`.
- Cleanup would delete work without explicit landing or abort confirmation.
