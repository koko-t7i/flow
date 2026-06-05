---
description: Run a localflow subcommand or the full local repo workflow
argument-hint: "[check|tree|fast|mr|commit|clean] (or describe the change to deliver)"
---

# Localflow

Use the `localflow:localflow` skill for this request. If the Skill tool is available, invoke `localflow:localflow` before continuing, then follow that skill's workflow exactly.

Dispatch by first argument, then use the matching subcommand section in the skill:

| Argument | Meaning |
| --- | --- |
| `check` | Read-only environment capability snapshot. |
| `tree` | Default isolated-worktree MR/PR review workflow. |
| `fast` | Local landing for a clean committed task worktree; no push, MR/PR, or cleanup. |
| `mr` | Create or inspect the current branch MR/PR; supports `--snapshot` for shared live-preview checkouts. |
| `commit` | Stage only named `--paths`, commit, and optionally open MR/PR with `--mr`. |
| `clean` | Clean only already-landed branches/worktrees/remotes. |

If the repository has **no** localflow config file (`.codex/localflow.toml` / `.claude/localflow.toml`), confirm `base_branch` / `delivery_mode` / `remote_provider` (only when ambiguous) / `remote` / `draft` / `version_policy` with the user and write `.<host>/localflow.toml` before delivering — do not silently rely on heuristics. Skip when a config already exists; never overwrite one without an explicit request.

User request:

```text
$ARGUMENTS
```

If the user did not provide enough context, ask only the minimum questions required by the localflow workflow.
