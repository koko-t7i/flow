---
name: flow
description: "Use for safe repository tasks: understand, orient, choose a workspace, implement, verify, create an MR/PR by default, and clean up after an authorized merge."
---

# Flow

Flow is a repository workflow skill, not a command toolkit.

Use it to move a repo task through one safe loop with minimal commands, repo-specific judgment, adaptive workspace isolation, and optional agent assignment when useful.

One public entrypoint: `/flow` or `$flow`. Treat user text as the repo goal.

## Core Flow

1. **Understand**
   - Inspect local context before asking.
   - Identify goal, acceptance criteria, scope, non-goals, constraints, and blockers.
   - Ask only for gaps that change direction, acceptance, risk, or delivery.

2. **Orient**
   - Inspect minimal state: branch, status, worktrees, dirty-file ownership, relevant files, and project conventions.
   - Identify the current branch and, when delivery matters, the environment branch and target; normally `main`, `test`, or `dev`.
   - Probe tools, auth, remotes, services, or CI only when the current work needs them.
   - Treat installed/configured/authenticated/permissioned as separate facts.
   - Keep `origin` stable unless the user explicitly asks to change it.

3. **Prepare Workspace**
   - Decide whether to reuse the current checkout or create a linked worktree from the task shape, risk, existing changes, parallel work, and delivery needs. File changes alone do not require a worktree.
   - Reuse the current checkout when its branch and dirty-file ownership are safe for the task. Create or switch branches only when the task or delivery needs one.
   - When using a worktree, follow repository branch conventions; otherwise name the branch `type/short-kebab-slug`.
   - Place new worktrees at `<repo-root>/.worktrees/<repo>-<branch>`, replacing `/` in the branch name with `-`, and ensure `.worktrees/` is ignored.
   - Inspect an existing target before reuse. Reuse it only when its branch and ownership match; stop rather than overwrite a collision or unknown worktree.
   - Do not implement or commit in detached HEAD. Resolve unclear or unrelated existing changes before editing.
   - Sync required local environment files into the task workspace only before tests or app commands that need them.
   - Preserve env-file relative paths and relevant permissions; confirm they are ignored before use.
   - If required env files are missing from the current checkout, inspect same-repository worktrees before declaring services unavailable.
   - If workspace safety or change ownership cannot be resolved, stop instead of guessing.

4. **Implement**
   - Edit task-owned files only.
   - Preserve unrelated user changes.
   - Follow repository conventions over generic preferences.
   - Avoid unrelated refactors, formatting churn, generated noise, logs, artifacts, and temporary files.

5. **Verify**
   - Prove the change satisfies the goal and acceptance criteria.
   - Use fresh evidence from the task workspace before claiming success.
   - Run the smallest useful checks first.
   - Expand to broader checks when risk, repo policy, or delivery requires it.
   - Treat tests passed as check evidence, not automatic proof of acceptance.
   - Treat subagent reports as advice; inspect the evidence before relying on them.
   - Review the final diff for task boundary, regressions, validation gaps, generated files, secrets, env files, logs, and artifacts.
   - Fix failures caused by the task; record unrelated failures without expanding scope unless asked.
   - Report skipped checks and remaining risk.

6. **Deliver**
   - After a file-changing task is complete and verified, default to committing task-owned changes, pushing the task branch, and creating or updating a ready-for-review MR/PR.
   - Skip review delivery only when the user explicitly declines it, the task is read-only or has no task-owned diff, or no usable remote, hosting integration, authentication, or permission is available.
   - Do not present incomplete work or failed task-related checks as ready for review. Stop and report the blocker instead.
   - Keep merge and force push behind explicit approval.

7. **Report**
   - End with concise evidence from what actually happened.
   - Include files changed, checks run, skipped checks, unrelated failures, and remaining risk.
   - For file-changing tasks, include the environment and task branches when relevant, plus the worktree path when one was used.
   - Include agent assignment, commit, delivery, and cleanup only when they were part of the task.

## Supporting Steps

Apply these details when the corresponding core step or task condition occurs.

### Assign Agent

- Keep simple, local, low-risk work in the current agent.
- Use an explore/search agent for broad codebase discovery.
- Use a planning agent for architecture, migration, or multi-step risk.
- Use a specialist or general implementation agent for large isolated coding tasks.
- Run agents in parallel only for independent read-only exploration or clearly separated work.
- Give delegated agents narrow prompts, clear scope, expected outputs, and file boundaries.
- The current agent owns final decisions, git state, verification, commit, delivery, and cleanup.

### Commit

- Commit verified task-owned changes when default review delivery applies, or when the user or repository workflow otherwise requires a commit.
- Inspect final diff.
- Stage only task-owned paths.
- Inspect staged diff.
- Use an English Conventional Commit subject.
- Keep commit content and message aligned with the staged diff.
- Exclude secrets, env files, generated junk, unrelated edits, and AI/tool attribution.
- After a review branch is pushed, append follow-up commits unless the user explicitly approves rewriting history.

### Deliver

- Default to creating or updating an MR/PR after successful implementation and verification unless a documented skip condition applies.
- If changes are on an environment branch, create a task branch before committing and pushing; never push task commits directly to the environment branch for review delivery.
- For review, create or update a delivery branch when needed, using task-owned changes and concise verification evidence.
- Follow the repository's review title convention when one exists; otherwise use a concise English Conventional Commit-style title, `type(scope): summary`, with optional scope, that describes the overall verified outcome.
- Build the MR/PR description from the verified diff and the user conversation, using the repository template when one exists.
- Make the description self-contained: explain the background and purpose; summarize the change scope and explicit non-goals; outline the implementation approach and important tradeoffs; assess relevant compatibility, data, API, configuration, permission, performance, security, dependency, deployment, and rollback impact; provide verification steps and evidence, including skipped checks; state known risks, limitations, dependencies, draft status, and reviewer focus when applicable; and preserve user-emphasized requirements or decisions.
- Write the whole description in one language, following the repository's existing MR/PR language and defaulting to English; never mix languages or add a translated duplicate. Identifiers, code, and quoted output stay verbatim.
- If no repository template exists, organize the applicable details under `Background`, `Changes`, `Implementation`, `Impact and Risks`, `Verification`, `Deployment and Rollback`, and `Review Focus`. Omit empty or inapplicable sections, do not invent user notes, and never expose secrets or sensitive information.
- Format verification evidence as concise bullets or prose. Lead with the result, put individual commands in inline code, and pair each command with its outcome.
- Do not use fenced `bash`, `sh`, `shell`, or `console` blocks for test methods or results in MR/PR descriptions; summarize relevant output instead of pasting a terminal transcript.
- Screenshots are not part of the MR/PR standard. Do not add a screenshot section.
- Push only intended branches.
- Prefer direct review creation over pre-listing reviews; inspect existing review only when creation reports one already exists.
- Create a ready review by default. Use draft status only when the user requests it or the repository workflow explicitly requires it.
- Avoid broad CI polling; check by commit SHA when CI evidence is required and not already reported.
- Recover auth without exposing secrets; use HTTPS fallback only with existing credentials or explicit authorization.
- Keep the intended environment branch clean and verified for local landing.
- MR/PR creation does not authorize merge. Merge and force push require explicit approval.
- After an explicitly authorized merge succeeds, perform the verified post-merge cleanup below without asking again.

### Clean Up

- Keep task resources while review is open. After a successful merge, verify the merged state, exact source branch, worktree ownership, and clean status before cleanup.
- Run cleanup from a surviving checkout, never from the worktree being removed.
- By default, delete the remote source branch, remove its clean linked worktree with `git worktree remove`, delete the merged local source branch with `git branch -d`, then run `git worktree prune`.
- Treat an already-deleted remote source branch as a successful no-op and continue the remaining cleanup.
- Never delete an environment branch, dirty worktree, unknown resource, or unmerged branch. Stop and report instead.
- Ask before cleanup outside this verified post-merge default or when ownership and merge state are unclear.

## Best Practices

- Prefer narrow commands over broad probes.
- Avoid default environment sweeps, fetch loops, review list scans, and CI polling.
- Never print, stage, commit, upload, or snapshot secret values from env files.
- Never read, print, store, upload, or script private keys, tokens, passphrases, or secret env values.
- Public key upload changes account security state and requires explicit approval.
- Use review CLIs only when review work needs them.
- Treat reset, restore, clean, rebase, merge, force push, and repository `rm -rf` as high risk.
- Before destructive actions outside verified post-merge cleanup, state the current branch, exact command, affected files/resources, and expected data loss or cleanup effect; wait for approval.

## Stop

Stop and ask when safe implementation remains unclear, acceptance criteria conflict, scope or ownership is unclear, no safe workspace can be chosen, required env files are unavailable for required checks, auth recovery would expose secrets, task-related checks fail, delivery target is unclear, destructive action lacks approval, post-merge cleanup is dirty or unverified, or agent boundaries cannot be resolved safely. If default review delivery is unavailable, finish the safe local work and report the exact delivery blocker instead of inventing a remote path.
