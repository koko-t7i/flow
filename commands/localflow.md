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

If the repository has **no** localflow config file (`.codex/localflow.toml` / `.claude/localflow.toml` / `.pi/localflow.toml`), or the selected file is old schema, confirm `base_branch` / `remote_cli` / `passphrase` / `default_mode` with the user and write `.<host>/localflow.toml` before delivering. `passphrase` must point to an ignored file beside the config file, normally `file:passphrase`. Do not silently rely on heuristics, and never overwrite a current-schema config without an explicit request.

User request:

```text
$ARGUMENTS
```

If the user did not provide enough context, ask only the minimum questions required by the localflow workflow.
