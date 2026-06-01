---
description: Run a localflow subcommand or the full local repo workflow
argument-hint: "[check|mr|clean] (or describe the change to deliver)"
---

# Localflow

Use the `localflow:localflow` skill for this request. If the Skill tool is available, invoke `localflow:localflow` before continuing, then follow that skill's workflow exactly.

If the first argument is `check`, treat it as the `localflow check` subcommand: run only the environment capability snapshot, report results, and stop without editing the repository.

If the first argument is `mr`, treat it as the `localflow mr` subcommand: run only the deterministic MR/PR create-or-status script, report results, and stop without implementing, committing, merging, or cleaning up.

If the first argument is `clean`, treat it as the `localflow clean` subcommand: run only the deterministic cleanup script. The script must refuse cleanup unless the MR/PR is already merged or the task branch is already merged into the base branch. When invoked from a long-lived branch, it may scan and clean all safe landed leftovers while skipping unmerged work.

User request:

```text
$ARGUMENTS
```

If the user did not provide enough context, ask only the minimum questions required by the localflow workflow.
