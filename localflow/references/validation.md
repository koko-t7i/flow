# Validation and Review

## Core Principle

Evidence comes before claims. Do not say work is complete, fixed, passing, or ready to commit without fresh verification output.

## Process

Break work into observable checks. When practical, write the failing test first, confirm the expected failure, implement the smallest fix, rerun, then refactor only when it improves the current change.

Run relevant tests and repo-provided lint/format checks. Prefer the smallest convincing checks for the changed feature unless the user asks for broader validation.

Inspect `git diff` before staging. Confirm the diff contains only task-related work and no secrets, credentials, local env files, logs, build artifacts, or temporary files.

In existing changes mode, stage only requested-task files and leave unrelated user changes unstaged.

## Review Gate

Review the final diff as a code reviewer before committing. Check acceptance criteria, regressions, hard correctness issues, missing edge cases/tests, unrelated refactors, accidental churn, generated-file noise, and task-boundary drift.

Stop on any high-confidence blocking issue. If all blockers are resolved or only unrelated risks remain, proceed to commit.

## Unrelated Failures

Fix failures caused by this task. For existing or unrelated failures, record the command, failure summary, and why it appears unrelated. Do not fix unrelated failures unless requested.

Do not commit with task-related checks failing.

## Stop Conditions

Stop when a task-related check fails repeatedly, a regression cannot be explained, the diff includes unclear unrelated changes, or verification commands are unavailable and no equivalent check can be found.

Stop before any completion claim if the current turn has not run the command that proves it.

## Common Mistakes

- Treating a clean-looking diff as proof that tests pass.
- Reporting "done" after partial validation.
- Fixing unrelated failures because they appeared during validation.
- Ignoring generated files that changed as side effects.

## Red Flags

- The only verification is a previous run from another turn.
- `git diff` includes secrets, env files, logs, build artifacts, or unrelated formatting churn.
- The final review finds a blocker but implementation continues anyway.
- A test failure touches the changed behavior and is labeled unrelated without evidence.
