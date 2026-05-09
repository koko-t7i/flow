# Localflow

This repository contains the `localflow` Codex skill.

The skill defines a local code-change workflow from requirement clarification through TDD, review, commit, push, and temporary worktree cleanup.

## Claude Code

The repository also exposes `localflow` as a Claude Code plugin. The Claude skill path is `skills/localflow`, a symlink to the canonical `localflow` skill directory so Codex and Claude Code share the same `SKILL.md`.

Validate the plugin before installing:

```bash
claude plugin validate .
```

Install from this local marketplace:

```bash
claude plugin marketplace add ./
claude plugin install localflow@localflow
```
