---
description: Default isolated-worktree MR/PR review workflow
argument-hint: "(describe the change to deliver)"
---

# Localflow tree

Use the `localflow:localflow` skill for this request. If the Skill tool is available, invoke `localflow:localflow` before continuing, then follow that skill's workflow exactly.

This command always runs the **`tree`** subcommand: follow the skill's `### localflow tree` section exactly. This is the default isolated-worktree review workflow that proceeds through `localflow commit`, `localflow mr`, and later `localflow clean` after the MR/PR is merged.

If the repository has **no** localflow config file (`.codex/localflow.toml` / `.claude/localflow.toml` / `.pi/localflow.toml`), or the selected file is old schema, confirm `base_branch` / `remote_cli` / `passphrase` / `default_mode` with the user and write `.<host>/localflow.toml` before delivering. `passphrase` must point to an ignored file beside the config file, normally `file:passphrase`. Do not silently rely on heuristics, and never overwrite a current-schema config without an explicit request.

User request:

```text
$ARGUMENTS
```

If the user did not provide enough context, ask only the minimum questions required by the localflow workflow.
