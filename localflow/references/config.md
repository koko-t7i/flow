# Repository Config

Owns the localflow config schema and the **no-config confirm-and-write gate**:
what to do when a repository has no `localflow.toml`.

Config is optional and host-specific, committed inside the target repository:

- Codex reads `.codex/localflow.toml` first, then `.claude/localflow.toml`.
- Claude Code reads `.claude/localflow.toml` first, then `.codex/localflow.toml`.

User instructions override config; config overrides defaults. If both host files
exist, do not merge them. `load_repo_config` returns `({}, None)` when neither
file exists — that `config_path: null` in any subcommand result is the
**absent-config signal**.

## No-config gate (confirm, then write)

When neither host's config file exists, do NOT silently let the deterministic
scripts fall back to heuristics for the base branch and remote provider. Before
the first delivery action (`mr` / `commit` / `clean`):

1. **Detect.** No `.codex/localflow.toml` and no `.claude/localflow.toml` (or a
   subcommand returned `config_path: null`).
2. **Confirm with the user** (use the host's question UI, e.g. AskUserQuestion),
   pre-filling the heuristic guess as the default for each item:
   - `base_branch` — choose among the long-lived branches that actually exist
     (`main` / `test` / `dev`); default to the nearest one (fewest commits ahead).
   - `delivery_mode` — `remote_review` | `local_landing` | `push_only`.
   - `remote_provider` — **only ask when ambiguous**: the remote host is not
     `github.com` / `*gitlab*` AND both `gh` and `glab` auth resolve (or neither).
     When the provider is unambiguous, do not ask.
   - `remote` (default `origin`), `draft` (default `false`),
     `version_policy` (default disabled; if enabled, also confirm `files`).
3. **Write** the confirmed values to the **current host's** file
   (`.claude/localflow.toml` for Claude Code, `.codex/localflow.toml` for Codex)
   using the template below. Then continue the normal flow; subsequent runs see a
   non-null `config_path` and skip this gate.
4. **Never overwrite** an existing config file without an explicit user request.
   If a config already exists, skip this gate entirely.

The deterministic scripts are headless and intentionally keep their heuristic
fallbacks (for non-interactive / cron use); this gate is an agent-level step, not
a script change.

## Canonical template

Write this file with the confirmed values (omit `[version_policy]` /
`[validation]` sections when not used):

```toml
version = 1

base_branch = "main"
delivery_mode = "remote_review"
worktree_mode = "isolated"

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

[version_policy]
enabled = false
scheme = "semver"
files = []
```

## Schema

| Key | Where | Meaning | Default | Consumed by |
|-----|-------|---------|---------|-------------|
| `version` | root | Config format version (`1`). | — | informational |
| `base_branch` | root | Long-lived base / return branch. | nearest of `main`/`test`/`dev` | scripts (`resolve_base_branch`) |
| `delivery_mode` | root | `remote_review` / `local_landing` / `push_only`. | agent decides | agent/SKILL |
| `worktree_mode` | root | `isolated` (default) or `in_place`. | `isolated` | agent/SKILL |
| `remote_provider` | `[delivery]` | `github` or `gitlab` (`auto` = infer). | inferred from host / CLI auth | scripts (`resolve_provider`) |
| `cleanup_remote_branch` | `[delivery]` | Delete the remote branch on clean. | `auto` (= delete) | scripts (`clean`) |
| `create_review` / `wait_for_ci` | `[delivery]` | Delivery intent flags. | `true` / `false` | agent/SKILL |
| `remote` | `[mr]` | Git remote name. | `origin` | scripts (`mr`/`clean`) |
| `draft` | `[mr]` | Open the MR/PR as a draft. | `false` | scripts (`mr`) |
| `title_source` / `body_style` | `[mr]` | Review title/body sourcing. | latest commit / commits+checks | agent/SKILL |
| `enabled` / `scheme` / `files` | `[version_policy]` | In-commit version bump policy. | disabled / semver / `[]` | scripts (version bump) |
| `pre_commit` (+ `docs`/`code`) | `[validation]` | Commands run as pre-delivery checks. | `[]` | scripts (`run_checks`) |
