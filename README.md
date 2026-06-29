# Localflow

Localflow is a repository flow skill for coding agents. It keeps local work small and safe:
understand the goal, inspect only what matters, assign the right agent when useful,
isolate when useful, implement, verify, commit, deliver, and clean up only when appropriate.

Version 2 is intentionally lean: one semantic entrypoint focused on the repository flow.

## Entry

Claude Code and pi:

```text
/localflow <goal or task>
```

Codex:

```text
$localflow <goal or task>
```

Examples:

```text
/localflow fix login redirect and open a PR
/localflow commit this README cleanup
/localflow land this clean branch locally
/localflow clean the merged task branch
```

## Flow

1. **Understand** — clarify scope only when needed.
2. **Orient** — inspect minimal repo state and relevant files.
3. **Assign** — choose current agent, explorer, planner, or implementer by task shape.
4. **Isolate** — use current checkout by default; create branch/worktree only when safer.
5. **Implement** — edit task-owned files and preserve user work.
6. **Verify** — run focused checks, broader checks when needed.
7. **Commit** — stage only task paths and use English Conventional Commit.
8. **Deliver** — create review or land locally when appropriate.
9. **Clean up** — remove only landed or explicitly abandoned resources.

## Best Practices

- Prefer narrow commands over broad probes.
- Assign agents by task shape; keep final git and delivery responsibility in the current agent.
- Do not default to isolated worktrees.
- Do not pre-list reviews or poll CI unless needed.
- Require approval for merge, force push, reset, branch deletion, worktree removal, and remote ref deletion.
- Never read, print, store, or script secrets.

## Install

### Claude Code

```bash
claude plugin marketplace add ./
claude plugin install localflow@localflow
```

Validate:

```bash
claude plugin validate .
```

### Codex

```bash
ln -s "$PWD/localflow" "$HOME/.codex/skills/localflow"
```

When the Codex validator is available:

```bash
uv run --with pyyaml python "$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py" ./localflow
```

### Pi

```bash
ln -s "$PWD/localflow" "$HOME/.pi/skills/localflow"
```

## Development

```bash
claude plugin validate .
uv run --with pyyaml python "$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py" ./localflow
git diff --check
test "$(find commands -type f | wc -l | tr -d ' ')" = "1"
```

## Layout

```text
.
├── .claude-plugin/
├── commands/localflow.md
├── localflow/
│   ├── SKILL.md
│   └── agents/
├── skills/localflow -> ../localflow
└── README.md
```

## Breaking Changes In 2.0.0

- Removed legacy public subcommands: `check`, `tree`, `fast`, `commit`, `mr`, and `clean`.
- Removed old helper scripts, split reference docs, repo-local config schema, and script tests.
- Replaced scripted routing with one flow skill.
