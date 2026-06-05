---
description: Land a clean committed task worktree locally; no push, MR/PR, or cleanup
argument-hint: ""
---

# Localflow fast

Use the `localflow:localflow` skill for this request. If the Skill tool is available, invoke `localflow:localflow` before continuing, then follow that skill's workflow exactly.

This command always runs the **`fast`** subcommand: follow the skill's `### localflow fast` section exactly. It lands a clean, already-committed task worktree into the local long-lived branch by rebase + fast-forward merge. It does not create an MR/PR, does not push to remote, and does not clean task worktrees or branches.

If the repository has **no** localflow config file (`.codex/localflow.toml` / `.claude/localflow.toml`), or the selected file is old schema, confirm `base_branch` / `remote_cli` / `passphrase` / `default_mode` with the user and write `.<host>/localflow.toml` before delivering. `passphrase` must point to an ignored file beside the config file, normally `file:passphrase`. Do not silently rely on heuristics, and never overwrite a current-schema config without an explicit request.

Additional arguments (if any):

```text
$ARGUMENTS
```
