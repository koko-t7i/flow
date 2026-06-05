# Localflow

Localflow is a local repository workflow for agents that need to make scoped
changes without dirtying the user's main checkout. It keeps the base branch
clean, moves implementation into task branches/worktrees, runs repository
checks, and delivers through review or local integration.

The same source tree is packaged as:

- a Claude Code plugin with `/localflow`
- a Codex skill with `$localflow`

Use it for work that may need branch selection, validation, commit creation,
push/auth recovery, MR/PR creation, or cleanup after landing. Do not use it for
one-off shell commands or explanation-only test runs unless they are part of
delivering a code change.

## What It Does

Localflow turns a repository task into a repeatable lifecycle:

1. Resolve the repository config and long-lived base branch.
2. Work on a dedicated task branch, usually in an isolated linked worktree.
3. Stage only explicitly named files.
4. Write an English Conventional Commit.
5. Run configured checks before delivery.
6. Open or update a GitHub PR / GitLab MR, or land locally in `fast` mode.
7. Clean only already-landed branches, worktrees, and remotes when asked.

It is intentionally conservative:

- It does not edit directly on `main`, `test`, or `dev` for implementation work.
- It does not use `git add .`.
- It does not clean worktrees or branches automatically after review creation.
- It does not merge MR/PRs without explicit approval.
- It does not print, commit, or snapshot secrets.

## Workflow Modes

`tree` is the default. `fast` still uses a task branch and isolated worktree;
it only changes the delivery path.

Use `tree` for normal feature/fix work that should be reviewed remotely. It
creates a task branch in an isolated worktree, commits scoped files, and opens
or updates an MR/PR.

Use `fast` when multiple local tasks need quick integration without remote
review. It rebases and fast-forward merges a clean committed task branch into
the local base branch. It does not push, open review, or clean.

Use `mr --snapshot` when a shared checkout must stay live, for example one
frontend preview while multiple agents edit the same directory. It captures
only named `--paths` into a side branch without touching the working tree,
index, or `HEAD`.

Use `clean` after a branch, worktree, or remote has landed. It deletes only safe
landed leftovers and skips open, dirty, mismatched, or unowned candidates.

## Commands

Claude Code:

```text
/localflow check
/localflow tree
/localflow fast
/localflow mr
/localflow commit
/localflow clean
/localflow <describe the change to deliver>
```

Codex:

```text
$localflow check
$localflow tree
$localflow fast
$localflow mr
$localflow commit
$localflow clean
$localflow <describe the change to deliver>
```

The deterministic scripts behind those commands live in `localflow/scripts/`.
They write JSON and Markdown snapshots under `~/.cache/localflow/`.

Common script entrypoints:

```bash
uv run python ./localflow/scripts/check_environment.py --cwd "$PWD"
uv run python ./localflow/scripts/commit.py --cwd "$PWD" --host codex \
  --paths README.md --message "docs: update readme" --mr
uv run python ./localflow/scripts/mr.py --cwd "$PWD" --host codex
uv run python ./localflow/scripts/fast.py --cwd "$PWD" --host codex
uv run python ./localflow/scripts/clean.py --cwd "$PWD" --host codex
```

For shared-checkout delivery:

```bash
uv run python ./localflow/scripts/mr.py --cwd "$PWD" --host codex \
  --snapshot --branch feat/live-preview \
  --paths src/Preview.tsx src/hooks/usePreview.ts \
  --type feat --summary "add live preview"
```

## Repository Config

Projects can commit host-specific workflow defaults:

```text
.codex/localflow.toml
.claude/localflow.toml
```

Codex reads `.codex/localflow.toml` first. Claude Code reads
`.claude/localflow.toml` first. The other file is a fallback only; the two files
are not merged.

Current schema:

```toml
version = 1

base_branch = "main"
remote_cli = "gh"
passphrase = "file:passphrase"
default_mode = "tree"
```

Fields:

- `base_branch`: long-lived branch to use as the base and return point.
- `remote_cli`: `gh`, `glab`, or `none`.
- `passphrase`: local ignored passphrase file beside the config file, usually
  `file:passphrase`.
- `default_mode`: `tree` or `fast`.

If no config exists, or the selected config is old schema, localflow asks for
these settings before the first delivery action instead of silently relying on
heuristics.

## Install

### Claude Code

Install from this local marketplace:

```bash
claude plugin marketplace add ./
claude plugin install localflow@localflow
```

Validate the plugin:

```bash
claude plugin validate .
```

### Codex

Install by symlinking this repository's skill directory:

```bash
ln -s "$PWD/localflow" "$HOME/.codex/skills/localflow"
```

Validate the skill when the Codex system validator is available:

```bash
python3 "$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py" ./localflow
```

## Development

Run the full test suite:

```bash
python3 -m unittest discover -s tests
```

Run the standard validation set used before delivery:

```bash
python3 "$HOME/.codex/skills/.system/skill-creator/scripts/quick_validate.py" ./localflow
claude plugin validate .
git diff --check
python3 -m unittest discover -s tests
```

Refresh the local environment capability snapshot:

```bash
uv run python ./localflow/scripts/check_environment.py --cwd "$PWD"
```

Inspect environment-file candidates without printing secret values:

```bash
uv run python ./localflow/scripts/check_env_files.py --cwd "$PWD"
```

## Repository Layout

```text
.claude-plugin/                 # Claude Code plugin and marketplace manifests
.claude/localflow.toml          # Repo-local Claude Code workflow defaults
.codex/localflow.toml           # Repo-local Codex workflow defaults
commands/localflow.md           # Claude Code slash command entrypoint
skills/localflow                # Claude Code skill symlink to ./localflow
localflow/SKILL.md              # Shared workflow entrypoint
localflow/agents/openai.yaml    # Codex UI metadata
localflow/references/           # Workflow modules loaded on demand
localflow/scripts/              # Deterministic helper scripts
tests/                          # Script tests
```

## Cleanup

Cleanup is explicit. Run it only after the delivery unit has landed:

```bash
uv run python ./localflow/scripts/clean.py --cwd "$PWD" --host codex
```

On a task branch, `clean` removes only that landed branch/worktree. On a
long-lived branch, it scans local branches, owned worktrees, and remote
branches, then cleans only candidates that are already landed.
