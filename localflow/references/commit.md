# Commit Gate

## Core Principle

Each commit should be atomic, reviewable, and explain the change without hiding unrelated work. Commit messages are part of the delivered interface.

## Process

Before staging, inspect the final diff and recent commit style with `git log -5 --oneline`. Follow the repository's scope and capitalization conventions when they do not conflict with this skill.

After review passes, stage only current-task files. Confirm `git diff --cached` contains the intended change and no sensitive or generated junk.

Do not stage unrelated user changes. Do not amend, squash, reorder, or rewrite existing commits unless the user explicitly requests it.

For multi-line messages, prefer `git commit -F <tempfile>` or the editor flow instead of embedding complex escaped newlines in `git commit -m`.

## Message Format

Use an English Conventional Commit:

```text
<type>(<scope>)!: <imperative summary>
```

`scope` and `!` are optional. Allowed types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `chore`, `build`, `ci`, `style`, `revert`.

Subject rules:

- Use imperative mood: `add`, `fix`, `remove`, not `added`, `adds`, or `adding`.
- Keep the subject at 50 characters when practical; hard cap 72.
- Do not end the subject with a period.
- Match the project's existing capitalization after the colon.

## Body

Skip the body when the subject is self-explanatory.

Add a body only for non-obvious why, breaking changes, security fixes, data migrations, reverts, or linked issues. Wrap body lines at 72 characters. Use `-` for bullets. Put issue references at the end, such as `Closes #42` or `Refs #17`.

For breaking changes, include `!` in the subject and a `BREAKING CHANGE:` body note.

## Never Include

Never include Chinese, Japanese, Korean, or any other non-English language in the commit subject or body, even if the user conversation or code comments are not English.

Never include AI assistant attribution or tool signatures, including `Co-Authored-By: Claude`, `Co-Authored-By: Codex`, `Generated with Claude Code`, emoji signatures, or mentions of Claude, Codex, Anthropic, OpenAI, or agent tooling.

Avoid filler such as "This commit", "I", "we", "now", "currently", or "as requested". The message should describe the change and, when needed, the reason.

## Stop Conditions

Stop before committing when the staged diff contains unrelated work, task-related checks are failing, branch naming is unsafe, the message describes more than the staged change, or the user requested review-only work.

Stop instead of guessing when a breaking-change marker, issue reference, or scope would materially change release notes or automation.

## Common Mistakes

- Letting `git add .` stage unrelated user work.
- Writing a message from the prompt instead of the staged diff.
- Restating filenames instead of explaining the behavior or contract change.
- Adding assistant attribution from a template or generated footer.

## Red Flags

- `git diff --cached` has files outside the task boundary.
- The commit subject needs "and" to describe multiple unrelated changes.
- The branch is protected and the user did not explicitly approve committing there.
- The commit message contains non-English text or tool attribution.
