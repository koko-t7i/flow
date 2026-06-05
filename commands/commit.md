---
description: Stage only named --paths, commit, and optionally open MR/PR with --mr
argument-hint: "--paths <path>... [--mr]"
---

# Localflow commit

Use the `localflow:localflow` skill for this request. If the Skill tool is available, invoke `localflow:localflow` before continuing, then follow that skill's workflow exactly.

This command always runs the **`commit`** subcommand: follow the skill's `### localflow commit` section exactly. It stages only the named `--paths`, commits, and optionally opens an MR/PR when `--mr` is passed.

If the repository has **no** localflow config file (`.codex/localflow.toml` / `.claude/localflow.toml` / `.pi/localflow.toml`), or the selected file is old schema, confirm `base_branch` / `remote_cli` / `passphrase` / `default_mode` with the user and write `.<host>/localflow.toml` before delivering. `passphrase` must point to an ignored file beside the config file, normally `file:passphrase`. Do not silently rely on heuristics, and never overwrite a current-schema config without an explicit request.

Arguments:

```text
$ARGUMENTS
```
