# Localflow

`localflow` is a Codex skill for local repository changes that should end as
reviewed, committed, and pushed work.

Use it when a task involves code changes that need validation, dirty worktree
handling, task branch selection, commit/push delivery, push authentication
recovery, or temporary git worktree cleanup.

Do not use it for test-only explanations or one-off command execution unless
that work is part of delivering a code change.

## Repository Layout

```text
localflow/SKILL.md              # Canonical Codex skill
localflow/agents/openai.yaml    # Codex UI metadata
localflow/scripts/              # Deterministic helper scripts
skills/localflow                # Claude Code plugin symlink
```

## Validate

Refresh the local environment capability snapshot:

```bash
python3 ./localflow/scripts/check_environment.py
```

Validate the Codex skill after editing:

```bash
python3 /home/koko/.codex/skills/.system/skill-creator/scripts/quick_validate.py ./localflow
```

Validate the Claude Code plugin before installing:

```bash
claude plugin validate .
```

## Claude Code

This repository also exposes `localflow` as a Claude Code plugin. The Claude
skill path is `skills/localflow`, a symlink to the canonical `localflow`
directory, so Codex and Claude Code share the same `SKILL.md`.

Install from this local marketplace:

```bash
claude plugin marketplace add ./
claude plugin install localflow@localflow
```
