---
description: Run the local repository flow skill
argument-hint: "<goal or task>"
---

# Localflow

Use the `localflow:localflow` skill for this request. If the Skill tool is available, invoke `localflow:localflow` before continuing.

Treat `$ARGUMENTS` as the repo goal. Follow the flow:

```text
Understand → Orient → Assign agent → Prepare worktree → Implement → Verify → Commit → Deliver → Clean up
```

Baseline:

- Minimal repo/tool checks only.
- Assign agents by task shape; current agent owns final git/delivery decisions.
- Keep the original repository checkout on its environment branch (`main`, `test`, or `dev`).
- Use a linked worktree by default, rooted at the target environment branch.
- Create feature or delivery branches only inside linked worktrees, and only when needed.
- Sync required env files into the linked worktree before tests or app commands.
- Stage task-owned paths only.
- Preserve unrelated user changes.
- Ask before destructive or irreversible git actions.

User request:

```text
$ARGUMENTS
```
