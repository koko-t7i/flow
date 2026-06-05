# Fast Mode

## Purpose

Use `fast` for isolated-worktree local integration.

`fast` keeps the long-lived branch clean while allowing rapid local landing:
each task still develops on a committed task branch in its own worktree, then
the task branch is rebased and fast-forward merged into the local long-lived
branch. It does not create MR/PRs, does not push, and does not clean.

## Lifecycle

1. Start from the selected long-lived branch: `main`, `test`, or `dev`.
2. Create or reuse one `type/slug` task branch in an isolated linked worktree.
3. Implement, verify, and commit only in that task worktree.
4. Run `localflow fast` from the clean task worktree.
5. The script fetches the remote base and fast-forwards the local base when
   possible. If local base is already ahead of remote, that is allowed. If local
   and remote base diverged, stop for manual integration.
6. The script rebases the task branch onto the local base, runs configured
   checks, and fast-forward merges the task branch into the local base.
7. The task worktree and branch remain in place. Run `localflow clean` later
   when cleanup is desired.

## Rules

- Development branch code must stay committed and the worktree must stay clean.
- Conflicts are resolved in the task worktree, not on the long-lived branch.
- `fast` does not push to remote and does not create a review request.
- `fast` reports whether the local base is ahead of remote after landing.
- `clean` is the only command allowed to delete task worktrees or branches.
