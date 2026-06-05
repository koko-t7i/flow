---
description: Create or inspect the current branch MR/PR
argument-hint: "[--snapshot]"
---

# Localflow mr

Use the `localflow:localflow` skill for this request. If the Skill tool is available, invoke `localflow:localflow` before continuing, then follow that skill's workflow exactly.

This command always runs the **`mr`** subcommand: follow the skill's `### localflow mr` section exactly. It creates or inspects the MR/PR for the current already-committed task branch (`--snapshot` produces a shared live-preview checkout). It does not implement changes, commit, merge, or clean up lifecycle resources.

If the repository has **no** localflow config file (`.codex/localflow.toml` / `.claude/localflow.toml`), or the selected file is old schema, confirm `base_branch` / `remote_cli` / `passphrase` / `default_mode` with the user and write `.<host>/localflow.toml` before delivering. `passphrase` must point to an ignored file beside the config file, normally `file:passphrase`. Do not silently rely on heuristics, and never overwrite a current-schema config without an explicit request.

Additional arguments (if any):

```text
$ARGUMENTS
```
