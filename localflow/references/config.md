# Repository Config

Owns the localflow config schema and the **no-config confirm-and-write gate**:
what to do when a repository has no `localflow.toml`.

Config is optional and host-specific, committed inside the target repository:

- Codex reads `.codex/localflow.toml` first, then `.claude/localflow.toml`.
- Claude Code reads `.claude/localflow.toml` first, then `.codex/localflow.toml`.
- Pi reads `.pi/localflow.toml` first, then `.claude/localflow.toml`, then `.codex/localflow.toml`.

User instructions override config; config overrides defaults. If both host files
exist, do not merge them. `load_repo_config` returns `({}, None)` when neither
file exists — that `config_path: null` in any subcommand result is the
**absent-config signal**. Existing old-schema config files that miss required
fields are stale and must be replaced through the same confirmation flow.

## No-config gate (confirm, then write)

When neither host's config file exists, or the selected config is old schema, do
NOT silently let deterministic scripts fall back to heuristics. Before the first
delivery action (`mr` / `commit` / `clean`):

1. **Detect.** No `.codex/localflow.toml`, `.claude/localflow.toml`, or `.pi/localflow.toml`, or a
   subcommand returned `config_missing` / `config_schema_outdated`.
2. **Confirm with the user** (use the host's question UI, e.g. AskUserQuestion),
   pre-filling the heuristic guess as the default for each item:
   - `base_branch` — choose among the long-lived branches that actually exist
     (`main` / `test` / `dev`); default to the nearest one (fewest commits ahead).
   - `remote_cli` — `gh` | `glab` | `none`. Use `none` only when this repo should
     not create MR/PR reviews from localflow.
   - `passphrase` — always write `file:passphrase`; the real passphrase lives
     beside the config file (`.codex/passphrase`, `.claude/passphrase`, or
     `.pi/passphrase`) and
     must be git-ignored.
   - `default_mode` — `tree` | `fast`; default to `tree`.
3. **Write** the confirmed values to the **current host's** file
   (`.claude/localflow.toml` for Claude Code, `.codex/localflow.toml` for Codex,
   `.pi/localflow.toml` for pi) using the template below. Then continue the normal flow; subsequent runs see a
   non-null current-schema config and skip this gate.
4. **Never overwrite** an existing config file without an explicit user request.
   If a config already exists, skip this gate entirely.

The deterministic scripts are headless and intentionally keep their heuristic
fallbacks (for non-interactive / cron use); this gate is an agent-level step, not
a script change.

## Canonical template

Write this file with the confirmed values:

```toml
version = 1

base_branch = "main"
remote_cli = "gh"
passphrase = "file:passphrase"
default_mode = "tree"
```

## Schema

| Key | Where | Meaning | Default | Consumed by |
|-----|-------|---------|---------|-------------|
| `version` | root | Config format version (`1`). | — | informational |
| `base_branch` | root | Long-lived base / return branch. | ask user | scripts (`resolve_base_branch`) |
| `remote_cli` | root | Review CLI: `gh`, `glab`, or `none`. | ask user | scripts (`resolve_provider`) |
| `passphrase` | root | Local ignored passphrase file reference. | `file:passphrase` | git retry helpers |
| `default_mode` | root | Default workflow: `tree` or `fast`. | `tree` | agent/SKILL |

`origin` is the fixed git remote. MR/PR creation is always non-draft. `remote_cli
= "none"` disables review creation and remote branch cleanup; use `fast` for
local landing.
