# Verify

## Core Principle

Evidence before claims. Completion, fixes, passing checks, and readiness to land require fresh evidence from the current code state.

`clarify.md` defines acceptance criteria. This module proves whether those criteria are met and whether the change is safe to deliver.

## Claim Gate

Before claiming success:

1. Identify the exact claim.
2. Classify it as `TASK`, `FIX`, `CHECK`, or `FEATURE_GO`.
3. Identify the command, checklist, or review evidence that proves it.
4. Run or inspect fresh evidence in the current tree.
5. Compare evidence to the claim scope.
6. Report `VERIFIED`, `NOT_VERIFIED`, or `MANUAL_VERIFY_REQUIRED`.

Reject claims that are broader than the evidence. A passing test does not prove requirements coverage. A clean diff does not prove tests pass. A subagent or tool report is not enough without checking the evidence.

## Task-Appropriate Validation

Use TDD when the task changes code behavior and a meaningful failing test can be written. Confirm the expected failure, implement the smallest fix, rerun, then refactor only when it improves the current change.

For non-code tasks, use the relevant acceptance evidence instead:

- skill/docs: skill validators, plugin validators, link/structure checks, `git diff --check`
- config: parser/schema/load checks and targeted startup or smoke checks
- refactor: existing behavior tests, typecheck/build, and diff review proving behavior did not intentionally change
- delivery-only tasks: branch, commit, remote, MR/PR, and cleanup state checks

Prefer the smallest convincing checks for the changed surface unless the user asks for broader validation.

## Review Gate

Before committing or landing, review the final diff as a code reviewer. Check:

- acceptance criteria coverage
- task boundary and non-goals
- regressions and edge cases
- test or validation gaps
- unrelated refactors or formatting churn
- generated-file noise
- secrets, credentials, local env files, logs, build artifacts, and temporary files

Stop on high-confidence blockers.

## Unrelated Failures

Fix failures caused by this task. For existing or unrelated failures, record the command, failure summary, and why it appears unrelated. Do not fix unrelated failures unless requested.

Do not commit, merge, or create an MR/PR with task-related checks failing.

## Stop Conditions

Return `NOT_VERIFIED` when evidence is stale, partial, failed, or does not cover the claim.

Return `MANUAL_VERIFY_REQUIRED` when a required environment, canonical command, or manual acceptance step is unavailable.

Stop before any completion or readiness claim if the current turn has not gathered evidence that proves it.

## Common Mistakes

- Treating "tests passed" as proof that the task meets acceptance criteria.
- Reusing old verification output after more edits.
- Applying TDD language to documentation or workflow-only changes.
- Fixing unrelated failures because they appeared during validation.

## Red Flags

- The final review finds a blocker but delivery continues.
- `git diff` includes unrelated files, secrets, env files, logs, artifacts, or generated noise.
- The claim is `FEATURE_GO` but only task-local checks were run.
- Review evidence comes only from the implementer's report.
