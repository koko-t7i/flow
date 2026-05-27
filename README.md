# Localflow

`localflow` is a local repository workflow skill for changes that should end
as clarified, verified, committed, and delivered. It is published as a
first-class Claude Code plugin and as a Codex skill from the same source tree.

Use it when a task involves code changes that need validation, dirty worktree
handling, task branch selection, commit/push delivery, push authentication
recovery, or temporary git worktree cleanup.

Do not use it for test-only explanations or one-off command execution unless
that work is part of delivering a code change.

## Repository Layout

```text
.claude-plugin/                 # Claude Code plugin and marketplace manifests
commands/localflow.md           # Claude Code slash command entrypoint
skills/localflow                # Claude Code skill (symlink to ./localflow)
localflow/SKILL.md              # Shared skill workflow, loaded by both hosts
localflow/agents/openai.yaml    # Codex UI metadata
localflow/references/           # Workflow modules loaded on demand
localflow/scripts/              # Deterministic helper scripts
tests/                          # Script tests
```

## Validate

Refresh the local environment capability snapshot:

```bash
uv run ./localflow/scripts/check_environment.py
```

Validate the Claude Code plugin before installing:

```bash
claude plugin validate .
```

Validate the Codex skill after editing, if a Codex skill-creator install is
available locally:

```bash
python3 "$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py" ./localflow
```

## Install

### Claude Code

Install from this local marketplace:

```bash
claude plugin marketplace add ./
claude plugin install localflow@localflow
```

After install, invoke the slash command:

```text
/localflow check
/localflow <describe the change to deliver>
```

### Codex

Symlink the `localflow` directory into the Codex skills location:

```bash
ln -s "$PWD/localflow" "$HOME/.codex/skills/localflow"
```

After install, invoke the skill:

```text
$localflow check
$localflow <describe the change to deliver>
```
