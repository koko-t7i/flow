# Localflow

Localflow is a repository flow skill for coding agents. It keeps local work small and safe:
understand the goal, inspect only what matters, isolate every file-changing task in a linked
worktree, implement, verify, and report. It adds agents, commits, delivery, and cleanup only
when the task actually needs them.

Version 3 keeps one semantic entrypoint and makes task worktrees mandatory for repository changes.

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
3. **Prepare worktree** — create or reuse a dedicated task branch and linked worktree before changing files.
4. **Implement** — edit task-owned files and preserve user work.
5. **Verify** — prove the change satisfies the goal with the smallest useful checks.
6. **Report** — summarize the evidence and only mention optional steps that actually happened.

Use these conditionally:

- **Assign** — choose an explorer, planner, or implementer only when task shape warrants it.
- **Commit** — stage only task paths and use English Conventional Commit when committing is requested or required.
- **Deliver** — create review or land locally when appropriate.
- **Clean up** — remove only landed or explicitly abandoned resources.

## Best Practices

- Prefer narrow commands over broad probes.
- Assign agents by task shape only when useful; keep final git and delivery responsibility in the current agent.
- Keep the original repository checkout on its environment branch.
- Allow read-only work in the current checkout, but use a dedicated task branch and linked worktree before any file change or task commit.
- Never implement in the original checkout, directly on an environment branch, or in detached HEAD; stop if a safe task worktree cannot be established.
- Reuse an existing linked worktree only when its task branch and dirty-file ownership match the task.
- Sync required env files only before checks that need them, without printing or staging secrets.
- Verify with fresh evidence from the current worktree before claiming success.
- Stage only task-owned files and inspect the staged diff before commit.
- Keep commits English Conventional Commit; make version decisions only for shipped behavior changes.
- Make MR/PR descriptions cover core functionality, notable boundary conditions, user-emphasized requirements or decisions, and verification evidence; follow repository templates and exclude sensitive information.
- Prefer direct review creation over pre-listing reviews; avoid broad CI polling.
- Require approval for merge, force push, reset, branch deletion, worktree removal, remote ref deletion, and destructive cleanup.
- Never read, print, store, upload, or script secrets.

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

## Breaking Changes In 3.0.0

- Removed in-place implementation and non-worktree fallback for all file-changing tasks.
- Require a dedicated task branch and linked worktree before editing, generating, staging, or committing task changes.
- Keep read-only repository inspection available without creating a worktree.

## Breaking Changes In 2.0.0

- Removed legacy public subcommands: `check`, `tree`, `fast`, `commit`, `mr`, and `clean`.
- Removed old helper scripts, split reference docs, repo-local config schema, and script tests.
- Replaced scripted routing with one flow skill.
