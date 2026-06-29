---
description: Run the local repository flow skill
argument-hint: "<goal or task>"
---

# Localflow

Use the `localflow:localflow` skill for this request. If the Skill tool is available, invoke `localflow:localflow` before continuing.

Treat `$ARGUMENTS` as the repo goal. Follow the flow:

```text
Understand → Orient → Assign agent → Isolate when useful → Implement → Verify → Commit → Deliver → Clean up
```

Baseline:

- Minimal repo/tool checks only.
- Assign agents by task shape; current agent owns final git/delivery decisions.
- Current checkout by default; branch/worktree only when safer.
- Stage task-owned paths only.
- Preserve unrelated user changes.
- Ask before destructive or irreversible git actions.

User request:

```text
$ARGUMENTS
```
