# Push, Auth Recovery, and Cleanup

## Core Principle

Push only verified, current-task commits. Recover auth problems without exposing secrets, and clean up only state this workflow owns.

## Process

Before push, confirm branch name, commit message, current-task-only commits, test/check results, and clean staged state.

Push the branch to `origin`. Do not create an MR/PR unless explicitly asked.

## Auth Recovery

If push fails, inspect the remote URL, upstream configuration, and exact error.

For SSH failures, check agent state and whether the expected key is loaded in the same shell. If a passphrase is needed, ask through the interactive prompt; never print, store, script, or commit secrets.

Use HTTPS fallback only when credentials are already configured or explicitly authorized. Stop when the safe next action is unclear.

## Finishing Policy

Default finish state is: branch pushed, no MR/PR created. Create an MR/PR only when the user explicitly asks.

Do not force push unless the user explicitly asks and the target branch is confirmed. Do not delete local or remote branches unless the user explicitly asks.

If the user asks to discard work, require explicit confirmation before deleting a branch, removing a worktree, or dropping commits.

## Worktree Cleanup

After a successful push from a temporary worktree created for this task, delete the worktree and run `git worktree prune`.

Do not remove a worktree that contains unrelated user changes, is harness-owned, or was not created for this task.

## Final Report

Report: mode used; branch; commit hash/message; pushed ref; tests/checks run; skipped checks with reasons; review result and remaining risk; worktree cleanup; MR/PR status, normally "not created".

## Stop Conditions

Stop when push auth recovery would require storing or printing secrets, branch ownership is unclear, force-push safety cannot be established, or cleanup would affect work not created by this workflow.

## Common Mistakes

- Creating an MR/PR because the branch was pushed.
- Treating HTTPS fallback as safe when credentials are not already configured.
- Cleaning up a worktree just because it exists.
- Omitting skipped checks or remaining risk from the final report.

## Red Flags

- Push target is a protected or shared branch.
- The push requires force and the user did not explicitly request it.
- Auth troubleshooting would expose private keys, tokens, or passphrases.
- Worktree cleanup would remove uncommitted or unrelated user changes.
