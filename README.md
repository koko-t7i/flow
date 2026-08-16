# Flow

[English](README.md) | [简体中文](README.zh-CN.md)

Flow is a repository skill for coding agents. It keeps local work small and safe:
understand the goal, inspect only what matters, choose the right workspace, implement,
verify, deliver through review by default, and report. It adds worktrees and agents only
when the task actually needs them.

## Entry

Claude Code and pi:

```text
/flow <goal or task>
```

Codex:

```text
$flow <goal or task>
```

Examples:

```text
/flow fix login redirect and open a PR
/flow commit this README cleanup
/flow land this clean branch locally
/flow clean the merged task branch
```

## Flow

1. **Understand** — clarify scope only when needed.
2. **Orient** — inspect minimal repo state and relevant files.
3. **Prepare workspace** — reuse the checkout or create a linked worktree when the task benefits from isolation.
4. **Implement** — edit task-owned files and preserve user work.
5. **Verify** — prove the change satisfies the goal with the smallest useful checks.
6. **Deliver** — commit, push, and create or update a ready MR/PR by default.
7. **Report** — summarize the evidence and delivery result.

Use these conditionally:

- **Assign** — choose an explorer, planner, or implementer only when task shape warrants it.
- **Clean up** — remove only landed or explicitly abandoned resources.

## Best Practices

- Prefer narrow commands over broad probes.
- Assign agents by task shape only when useful; keep final git and delivery responsibility in the current agent.
- Choose workspace isolation from task risk, existing changes, parallel work, and delivery needs; file changes alone do not require a worktree.
- Place new worktrees at `<repo-root>/.worktrees/<repo>-<branch>`, replacing `/` in branch names with `-`.
- Reuse an existing checkout or worktree only when its branch and dirty-file ownership match the task; never overwrite a collision.
- Never implement or commit in detached HEAD; stop when workspace safety or change ownership is unclear.
- Sync required env files only before checks that need them, without printing or staging secrets.
- Verify with fresh evidence from the task workspace before claiming success.
- Stage only task-owned files and inspect the staged diff before commit.
- Keep commits English Conventional Commit; use patch for compatible fixes, minor for backward-compatible capabilities or workflow defaults, and major only for genuinely incompatible public changes.
- After verified file-changing work, commit, push, and create or update a ready MR/PR by default; skip only when explicitly declined, no task diff exists, or remote delivery is unavailable.
- Creating an MR/PR never authorizes merge or force push.
- Follow repository MR/PR title conventions; when none exist, use a concise English Conventional Commit-style title that describes the overall verified outcome.
- Make MR/PR descriptions self-contained with background and purpose, change scope and non-goals, implementation approach and tradeoffs, relevant impact and risks, verification evidence, deployment and rollback details, dependencies or draft status, and reviewer focus when applicable; follow repository templates and exclude sensitive information.
- Write MR/PR descriptions in one language, following the repository's existing language and defaulting to English; no mixed languages or translated duplicates.
- Present verification as concise result-first bullets with commands in inline code; never use fenced shell blocks for test methods or results.
- Screenshots are not part of the MR/PR standard; do not add a screenshot section.
- Prefer direct review creation over pre-listing reviews; avoid broad CI polling.
- Require approval for merge, force push, reset, and destructive cleanup outside the verified post-merge default.
- After an authorized merge succeeds, delete the remote source branch, clean worktree, and merged local branch, then run `git worktree prune`.
- Never read, print, store, upload, or script secrets.

## Install

Flow installs as a plain skill. Run these commands from the repository root, then
start a new agent session so the skill is picked up.

### Claude Code

```bash
ln -s "$PWD/flow" "$HOME/.claude/skills/flow"
```

### Codex

```bash
ln -s "$PWD/flow" "$HOME/.agents/skills/flow"
```

When the Codex validator is available:

```bash
uv run --with pyyaml python "$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py" ./flow
```

### Pi

```bash
ln -s "$PWD/flow" "$HOME/.pi/skills/flow"
```

Because each target is a symlink, pulling a new Flow version updates every
installation; no reinstall step is needed.

## Development

```bash
uv run --with pyyaml python "$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py" ./flow
git diff --check
```

## Layout

```text
.
├── .worktrees/ (ignored, when used)
├── CHANGELOG.md
├── flow/
│   ├── SKILL.md
│   └── agents/
├── README.zh-CN.md
└── README.md
```
