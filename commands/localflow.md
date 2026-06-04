---
description: Run a localflow subcommand or the full local repo workflow
argument-hint: "[check|mr|commit|clean] (or describe the change to deliver)"
---

# Localflow

Use the `localflow:localflow` skill for this request. If the Skill tool is available, invoke `localflow:localflow` before continuing, then follow that skill's workflow exactly.

If the first argument is `check`, treat it as the `localflow check` subcommand: run only the environment capability snapshot, report results, and stop without editing the repository.

If the first argument is `mr`, treat it as the `localflow mr` subcommand: run only the deterministic MR/PR create-or-status script, report results, and stop without implementing, committing, merging, or cleaning up. For a shared checkout that must not be disturbed (e.g. a single combined live preview while multiple agents edit the same directory and branch), use the script's `--snapshot --branch <type/slug> --paths <files...> --message <...>` mode: it captures the named files into a side branch without touching the working tree, index, or `HEAD`, then opens or updates the review.

If the first argument is `commit`, treat it as the `localflow commit` subcommand: run only the deterministic commit script, which stages only the named `--paths`, writes an English Conventional Commit on the current task branch, and (with `--mr`) opens the review in one step. Use this in the default isolated-worktree flow; it refuses to run on a long-lived or detached branch and never uses `git add .`. For a shared checkout where multiple agents work the same branch, prefer `mr --snapshot --paths <files...>` instead.

If the first argument is `clean`, treat it as the `localflow clean` subcommand: run only the deterministic cleanup script. The script must refuse cleanup unless the MR/PR is already merged or the task branch is already merged into the base branch. When invoked from a long-lived branch, it may scan and clean all safe landed leftovers while skipping unmerged work.

If the repository has **no** localflow config file (`.codex/localflow.toml` / `.claude/localflow.toml`), confirm `base_branch` / `delivery_mode` / `remote_provider` (only when ambiguous) / `remote` / `draft` / `version_policy` with the user and write `.<host>/localflow.toml` before delivering — do not silently rely on heuristics. Skip when a config already exists; never overwrite one without an explicit request.

User request:

```text
$ARGUMENTS
```

If the user did not provide enough context, ask only the minimum questions required by the localflow workflow.
