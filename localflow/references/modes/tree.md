# Tree Mode

## Purpose

Use `tree` for the default isolated-worktree review flow.

`tree` keeps the long-lived branch clean, develops the task in its own branch
and worktree, and delivers through MR/PR review. It never lands locally by
itself and never cleans worktrees or branches.

## Lifecycle

1. Start from the selected long-lived branch: `main`, `test`, or `dev`.
2. Create or reuse one `type/slug` task branch in an isolated linked worktree.
3. Implement and verify only in that task worktree.
4. Commit scoped task files with `localflow commit`.
5. Open or update review with `localflow mr`, or use `localflow commit --mr`.
6. Keep the task worktree and task branch for review fixes until the MR/PR has
   landed.
7. Run `localflow clean` only when the MR/PR is merged or the user explicitly
   aborts the delivery unit.

## Rules

- Do not edit directly on `main`, `test`, or `dev`.
- Do not merge or clean just because a review exists.
- Do not delete the task worktree before review fixes and CI are finished.
- Use `mr --snapshot` only for the separate shared-checkout live-preview case.
