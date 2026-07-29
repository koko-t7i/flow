---
description: Run the repository flow
argument-hint: "<goal or task>"
---

# Flow

Use the `flow:flow` skill for this request. If the Skill tool is available, invoke `flow:flow` before continuing.

Treat `$ARGUMENTS` as the repo goal. Follow the core flow:

```text
Understand -> Orient -> Prepare workspace -> Implement -> Verify -> Deliver -> Report
```

Baseline:

- Minimal repo/tool checks only; separate installed/configured/auth/permission facts.
- Assign agents only when task shape warrants it; current agent owns final git/delivery decisions.
- Choose the current checkout or a linked worktree from task risk, existing changes, parallel work, and delivery needs; file changes alone do not require isolation.
- When using a worktree, place it at `<repo-root>/.worktrees/<repo>-<branch>`, replacing `/` in the branch with `-`, and never overwrite a collision.
- Do not implement or commit in detached HEAD; stop when workspace safety or change ownership is unclear.
- Sync required ignored env files only before tests or app commands that need them.
- Stage task-owned paths only and inspect staged diff.
- Preserve unrelated user changes, secrets, env files, logs, artifacts, and generated junk.
- Verify with fresh evidence before claiming success.
- Follow repository MR/PR title conventions; otherwise use a concise English Conventional Commit-style title for the overall verified outcome.
- MR/PR descriptions must be self-contained with background and purpose, change scope and non-goals, implementation approach and tradeoffs, relevant impact and risks, verification evidence, deployment and rollback details, dependencies or draft status, and reviewer focus when applicable, while following repository templates and protecting sensitive information.
- Screenshots are not part of the MR/PR standard; do not add a screenshot section.
- After a verified file-changing task, commit task-owned changes, push the task branch, and create or update a ready MR/PR by default; skip only when the user declines, no task diff exists, or remote delivery is unavailable.
- MR/PR creation never authorizes merge or force push.
- After an explicitly authorized merge succeeds, delete the remote source branch, remove its clean worktree, safely delete the merged local branch, and run `git worktree prune`; stop on dirty or unverified resources.
- Ask before destructive or irreversible git actions outside verified post-merge cleanup.

User request:

```text
$ARGUMENTS
```
