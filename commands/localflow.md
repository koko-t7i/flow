---
description: Run the localflow check subcommand or the full local repo workflow
argument-hint: "[check] (or describe the change to deliver)"
---

# Localflow

Use the `localflow:localflow` skill for this request. If the Skill tool is available, invoke `localflow:localflow` before continuing, then follow that skill's workflow exactly.

If the first argument is `check`, treat it as the `localflow check` subcommand: run only the environment capability snapshot, report results, and stop without editing the repository.

User request:

```text
$ARGUMENTS
```

If the user did not provide enough context, ask only the minimum questions required by the localflow workflow.
