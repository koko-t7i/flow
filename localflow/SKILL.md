---
name: localflow
description: "Use for repository tasks that should move through a safe local flow: understand, orient, assign the right agent, prepare a worktree, implement, verify, commit, deliver, and clean up."
---

# Localflow

Localflow is a repository flow skill. It is not a command toolkit.

Use it to move a repo task through one safe loop with minimal commands, repo-specific judgment, and automatic agent assignment when useful.

One public entrypoint: `/localflow` or `$localflow`. Treat user text as the repo goal.

## Flow

1. **Understand**
   - Identify goal, scope, acceptance criteria, and non-goals.
   - Ask only when missing context blocks safe work.

2. **Orient**
   - Inspect minimal state: branch/status, relevant files, and project conventions.
   - Check tools, auth, remotes, or CI only when current work needs them.
   - Infer base/target branch from repo state and user intent.

3. **Assign agent**
   - Keep simple, local, low-risk work in the current agent.
   - Use an explore/search agent for broad codebase discovery.
   - Use a planning agent for architecture, migration, or multi-step risk.
   - Use a specialist or general implementation agent for large isolated coding tasks.
   - Run agents in parallel only for independent read-only exploration or clearly separated work.
   - The current agent owns final decisions, git state, verification, commit, delivery, and cleanup.

4. **Prepare worktree**
   - Keep the original repository checkout on its environment branch, usually `main`, `test`, or `dev`.
   - Use a linked worktree as the default implementation workspace.
   - Create the linked worktree from the target environment branch, and keep that branch as the base and delivery target.
   - If implementation needs a feature or delivery branch, create it only inside the linked worktree.
   - If Git cannot check out the same environment branch in multiple worktrees, use a task branch or detached checkout inside the linked worktree.
   - Sync required local environment files into the linked worktree before running tests or app commands.
   - Never switch the original repository checkout away from its environment branch unless the user explicitly asks.

5. **Implement**
   - Edit task-owned files only.
   - Preserve unrelated user changes.
   - Follow repository conventions over generic preferences.

6. **Verify**
   - Prove the change satisfies the goal.
   - Run the smallest useful checks first.
   - Expand to broader checks when risk, repo policy, or delivery requires it.
   - Report skipped checks and remaining risk.

7. **Commit**
   - Inspect final diff.
   - Stage only task-owned paths.
   - Inspect staged diff.
   - Use an English Conventional Commit subject.
   - Exclude secrets, generated junk, unrelated edits, and AI/tool attribution.

8. **Deliver**
   - Deliver according to repo norms and user intent.
   - For review, create or update a delivery branch only when needed, using task-owned changes and concise verification evidence.
   - For local landing, keep the intended environment branch clean and verified.
   - Merge and force push require explicit approval.

9. **Clean up**
   - Cleanup is separate from delivery.
   - Remove only merged, landed, or explicitly abandoned resources.
   - Name exact branches, worktrees, or remote refs before deletion.
   - Never delete dirty, unknown, or unmerged work.

## Best Practices

- Prefer narrow commands over broad probes.
- Assign agents by task shape, not by habit; do not delegate trivial work.
- Give delegated agents narrow prompts, clear scope, expected outputs, and file boundaries.
- Treat subagent findings as advice; verify before editing or delivery.
- Avoid default environment sweeps, fetch loops, review list scans, and CI polling.
- Copy only needed env files or templates into linked worktrees; preserve permissions when relevant.
- Never print, stage, commit, or upload secret values from env files.
- Use review CLIs only when review work needs them.
- Use snapshot-style delivery only for shared live checkouts; include exact task paths only.
- Treat reset, rebase, merge, force push, branch deletion, worktree removal, and remote ref deletion as high risk.
- Never read, print, store, or script private keys, tokens, passphrases, or secret env values.

## Stop

Stop and ask when scope, ownership, target branch, required env files, destructive action, auth recovery, failing required checks, delivery target, or agent boundary cannot be resolved safely.

## Report

End with concise evidence: agent assignment, environment branch, worktree path, any delivery branch, files changed, checks, commit, delivery, cleanup, skipped checks, and remaining risk.
