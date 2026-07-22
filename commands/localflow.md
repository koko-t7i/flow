---
description: Run the local repository flow skill
argument-hint: "<goal or task>"
---

# Localflow

Use the `localflow:localflow` skill for this request. If the Skill tool is available, invoke `localflow:localflow` before continuing.

Treat `$ARGUMENTS` as the repo goal. Follow the core flow:

```text
Understand -> Orient -> Prepare worktree -> Implement -> Verify -> Report
```

Baseline:

- Minimal repo/tool checks only; separate installed/configured/auth/permission facts.
- Assign agents only when task shape warrants it; current agent owns final git/delivery decisions.
- Keep the original repository checkout on its environment branch (`main`, `test`, or `dev`).
- Pure read-only work may stay in the current checkout.
- Before any file change or task commit, create or safely reuse a dedicated task branch in a linked worktree; never implement in place, on an environment branch, or in detached HEAD.
- If worktree isolation cannot be established, stop instead of falling back to the original checkout.
- Sync required ignored env files only before tests or app commands that need them.
- Stage task-owned paths only and inspect staged diff.
- Preserve unrelated user changes, secrets, env files, logs, artifacts, and generated junk.
- Verify with fresh evidence before claiming success.
- Commit, deliver, and clean up only when requested or required by the task.
- Ask before destructive or irreversible git actions.

User request:

```text
$ARGUMENTS
```
