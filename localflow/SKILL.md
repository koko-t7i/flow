---
name: localflow
description: "Use for repository tasks that need a safe local flow: understand, orient, prepare an isolated task worktree before any file changes, implement, verify, and report, with agents, commits, delivery, and cleanup added only when needed."
---

# Localflow

Localflow is a repository flow skill. It is not a command toolkit.

Use it to move a repo task through one safe loop with minimal commands, repo-specific judgment, mandatory worktree isolation for file-changing tasks, and optional agent assignment when useful.

One public entrypoint: `/localflow` or `$localflow`. Treat user text as the repo goal.

## Core Flow

1. **Understand**
   - Inspect local context before asking.
   - Identify goal, acceptance criteria, scope, non-goals, constraints, and blockers.
   - Ask only for gaps that change direction, acceptance, risk, or delivery.

2. **Orient**
   - Inspect minimal state: branch, status, worktrees, dirty-file ownership, relevant files, and project conventions.
   - For a file-changing task, choose the environment branch as base and delivery target; normally `main`, `test`, or `dev`.
   - Probe tools, auth, remotes, services, or CI only when the current work needs them.
   - Treat installed/configured/authenticated/permissioned as separate facts.
   - Keep `origin` stable unless the user explicitly asks to change it.

3. **Prepare Worktree**
   - Read-only inspection, review, explanation, and status reporting may stay in the current checkout.
   - Before any file edit, formatter, code generation, migration, or task commit, use a linked worktree on a dedicated task branch created from the environment branch.
   - Never implement, stage task changes, or commit them in the original checkout or directly on an environment branch.
   - Follow repository branch conventions; otherwise name the task branch `type/short-kebab-slug` and place the worktree in a non-nested sibling directory.
   - If the current directory is already a linked worktree, reuse it only when it is on a compatible task branch and dirty-file ownership is clear. Do not use detached HEAD and do not create nested worktrees.
   - If existing changes in the original checkout may belong to the task, confirm ownership before moving or recreating them in the task worktree. Do not continue, stage, or commit them in place.
   - Sync required local environment files into the task worktree only before tests or app commands that need them.
   - Preserve env-file relative paths and relevant permissions; confirm they are ignored before use.
   - If required env files are missing from the source checkout, inspect same-repository sibling worktrees before declaring services unavailable.
   - If the environment branch, change ownership, or safe worktree cannot be resolved, stop instead of falling back to in-place work.
   - Never switch the original checkout away from its environment branch unless the user explicitly asks.

4. **Implement**
   - Edit task-owned files only.
   - Preserve unrelated user changes.
   - Follow repository conventions over generic preferences.
   - Avoid unrelated refactors, formatting churn, generated noise, logs, artifacts, and temporary files.

5. **Verify**
   - Prove the change satisfies the goal and acceptance criteria.
   - Use fresh evidence from the current worktree before claiming success.
   - Run the smallest useful checks first.
   - Expand to broader checks when risk, repo policy, or delivery requires it.
   - Treat tests passed as check evidence, not automatic proof of acceptance.
   - Treat subagent reports as advice; inspect the evidence before relying on them.
   - Review the final diff for task boundary, regressions, validation gaps, generated files, secrets, env files, logs, and artifacts.
   - Fix failures caused by the task; record unrelated failures without expanding scope unless asked.
   - Report skipped checks and remaining risk.

6. **Report**
   - End with concise evidence from what actually happened.
   - Include files changed, checks run, skipped checks, unrelated failures, and remaining risk.
   - For file-changing tasks, include the environment branch, task branch, and worktree path.
   - Include agent assignment, commit, delivery, and cleanup only when they were part of the task.

## Conditional Steps

Use these only when the task shape, user request, risk, or repo policy requires them.

### Assign Agent

- Keep simple, local, low-risk work in the current agent.
- Use an explore/search agent for broad codebase discovery.
- Use a planning agent for architecture, migration, or multi-step risk.
- Use a specialist or general implementation agent for large isolated coding tasks.
- Run agents in parallel only for independent read-only exploration or clearly separated work.
- Give delegated agents narrow prompts, clear scope, expected outputs, and file boundaries.
- The current agent owns final decisions, git state, verification, commit, delivery, and cleanup.

### Commit

- Commit only when requested, required by delivery, or normal repo flow for the task.
- Inspect final diff.
- Stage only task-owned paths.
- Inspect staged diff.
- Use an English Conventional Commit subject.
- Keep commit content and message aligned with the staged diff.
- Make a version decision only when shipped behavior, public commands, APIs, install/update behavior, package contents, or released capability changes.
- Exclude secrets, env files, generated junk, unrelated edits, and AI/tool attribution.
- After a review branch is pushed, append follow-up commits unless the user explicitly approves rewriting history.

### Deliver

- Deliver according to repo norms and user intent.
- For review, create or update a delivery branch when needed, using task-owned changes and concise verification evidence.
- Follow the repository's review title convention when one exists; otherwise use a concise English Conventional Commit-style title, `type(scope): summary`, with optional scope, that describes the overall verified outcome.
- Build the MR/PR description from the verified diff and the user conversation, using the repository template when one exists.
- At minimum, describe the core functionality or outcome, boundary conditions or limitations reviewers should notice, user-emphasized requirements or decisions when present, and verification evidence including skipped checks or remaining risk.
- If no repository template exists, organize those details under `Core Functionality`, `Boundary Conditions`, `User Notes` when applicable, and `Verification`. Do not invent user notes or expose secrets or sensitive information.
- Push only intended branches.
- Prefer direct review creation over pre-listing reviews; inspect existing review only when creation reports one already exists.
- Avoid broad CI polling; check by commit SHA when CI evidence is required and not already reported.
- Recover auth without exposing secrets; use HTTPS fallback only with existing credentials or explicit authorization.
- Keep the intended environment branch clean and verified for local landing.
- Merge and force push require explicit approval.

### Clean Up

- Cleanup is separate from delivery.
- Keep linked worktrees and local delivery branches for review fixes until remote review has landed.
- Remove only merged, landed, or explicitly abandoned resources.
- Name exact branches, worktrees, or remote refs before deletion.
- Never delete dirty, unknown, unowned, or unmerged work.
- Prune worktrees only when stale entries are detected or after failed/aborted worktree operations.

## Best Practices

- Prefer narrow commands over broad probes.
- Avoid default environment sweeps, fetch loops, review list scans, and CI polling.
- Never print, stage, commit, upload, or snapshot secret values from env files.
- Never read, print, store, upload, or script private keys, tokens, passphrases, or secret env values.
- Public key upload changes account security state and requires explicit approval.
- Use review CLIs only when review work needs them.
- Treat reset, restore, clean, rebase, merge, force push, branch deletion, worktree removal, remote ref deletion, and repository `rm -rf` as high risk.
- Before destructive actions, state the current branch, exact command, affected files/resources, and expected data loss or cleanup effect; wait for approval.

## Stop

Stop and ask when safe implementation remains unclear, acceptance criteria conflict, scope or ownership is unclear, the environment branch for a file-changing task cannot be chosen, task changes cannot be safely moved out of the original checkout, a dedicated task branch and linked worktree cannot be created or safely reused, required env files are unavailable for required checks, auth recovery would expose secrets, task-related checks fail, delivery target is unclear, destructive action lacks approval, cleanup ownership is unclear, or agent boundary cannot be resolved safely. Never use in-place implementation as a fallback.
