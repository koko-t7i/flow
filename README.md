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
.claude/localflow.toml          # Repo-local Claude Code workflow defaults
.codex/localflow.toml           # Repo-local Codex workflow defaults
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

## Repository Config

Projects can commit host-specific workflow defaults to reduce repeated
decisions:

```text
.codex/localflow.toml
.claude/localflow.toml
```

Both files use the same schema. Codex reads `.codex/localflow.toml` first and
Claude Code reads `.claude/localflow.toml` first; the other file is only a
fallback. User instructions still override config.

Localflow defaults to `worktree_mode = "isolated"` for implementation tasks:
create a task branch in an isolated worktree, and keep the original checkout as
the base/return point. Use `in_place` only as an explicit exception when the
repository should persist current-branch delivery without repeated user
instructions. The current branch must still be safe and dirty-tree ownership
must be clear.

Example:

```toml
version = 1

base_branch = "main"
delivery_mode = "remote_review"
worktree_mode = "isolated"

[version_policy]
enabled = true
scheme = "semver"
files = [".claude-plugin/plugin.json"]

[validation]
docs = ["git diff --check"]
code = ["python3 -m unittest discover -s tests"]
pre_commit = ["git diff --check", "python3 -m unittest discover -s tests"]

[delivery]
remote_provider = "github"
create_review = true
wait_for_ci = false
cleanup_remote_branch = "auto"

[mr]
remote = "origin"
title_source = "latest_commit_subject"
body_style = "commits_and_checks"
draft = false
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
/localflow mr
/localflow clean
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
$localflow mr
$localflow clean
$localflow <describe the change to deliver>
```

`localflow mr` creates or inspects the current branch review request: GitHub
repositories get a PR, GitLab repositories get an MR. `localflow clean` only
cleans already-landed delivery units. From a task branch it cleans that branch;
from a long-lived branch it scans safe leftovers and skips anything still
unmerged, dirty, or not owned by localflow.
