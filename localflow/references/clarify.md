# Clarify

## Core Principle

Define what "done" means before changing files. Clarification owns intent, acceptance criteria, scope, non-goals, and blockers.

## Process

Inspect local context before asking. Use the repo, open files, failing output, branch state, or user-provided artifacts to resolve discoverable facts.

Restate the task when the request is ambiguous or broad:

- Goal: what outcome the user wants.
- Acceptance: what must be true for the task to be accepted.
- Scope: files, modules, services, or behavior included.
- Non-goals: explicit exclusions and things not to change.
- Constraints: test scope, branch preference, delivery mode, language, or timing.

Ask only for gaps that change direction, acceptance, risk, or delivery. Do not ask the user to locate information that can be found by inspecting the workspace.

## Outputs

Before implementation, the workflow should know:

- Task goal.
- Acceptance criteria.
- In-scope and out-of-scope boundaries.
- Any blocker requiring user choice.
- Whether the user asked for review-only, discussion-only, implementation, local landing, or remote review.

## Stop Conditions

Stop when safe implementation remains unclear after inspection, acceptance criteria conflict, non-goals conflict with the requested change, or the user explicitly asks to discuss without editing.

## Common Mistakes

- Implementing from a vague imperative without confirming acceptance.
- Asking questions before inspecting obvious local context.
- Treating a suggested approach as the actual requirement.
- Expanding scope because nearby code looks related.

## Red Flags

- The request includes exclusions such as "do not modify", "backend only", "review only", or named files/services to avoid.
- The task can be interpreted as either local landing or remote review and no repository preference is known.
- The user asks for a fix, but the original symptom cannot be reproduced or inspected.
