# Changelog

## 5.2.2

- Added a Simplified Chinese README and language links between both README files.

## 5.2.1

- Moved release history out of the README and into this changelog.

## 5.2.0

- Required compact, result-first verification evidence with inline commands instead of fenced shell blocks in MR/PR descriptions.

## 5.1.0

- Made ready-for-review MR/PR creation the default after successful verified file-changing tasks.
- Kept merge and force push behind explicit approval and documented delivery skip conditions.

## 5.0.0 (Breaking)

- Made worktree isolation task-dependent instead of mandatory for every file change.
- Moved new worktrees to `.worktrees/<repo>-<branch>` inside the repository.
- Cleaned remote and local source branches, merged worktrees, and stale worktree metadata after a successful authorized merge.
- Moved standalone Codex installation to `$HOME/.agents/skills/flow` for direct `$flow` invocation.

## 4.0.0 (Breaking)

- Renamed the plugin, skill, command, and public entrypoint from `localflow` to `flow`.

## 3.0.0 (Breaking)

- Removed in-place implementation and non-worktree fallback for all file-changing tasks.
- Required a dedicated task branch and linked worktree before editing, generating, staging, or committing task changes.
- Kept read-only repository inspection available without creating a worktree.

## 2.0.0 (Breaking)

- Removed legacy public subcommands: `check`, `tree`, `fast`, `commit`, `mr`, and `clean`.
- Removed old helper scripts, split reference docs, repo-local config schema, and script tests.
- Replaced scripted routing with one flow skill.
