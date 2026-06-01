# Contribution

## Core Principle

Contribution owns the handoff from verified local changes to commit, push, MR/PR, merge, and remote branch cleanup. Local branch and worktree mechanics are owned by `git.md`.

## Commit

Before staging, inspect the final diff. Inspect recent commit style with `git log -5 --oneline` only when repository conventions are unknown or appear to conflict with this skill.

Stage only current-task files. Confirm `git diff --cached` contains the intended change and no sensitive or generated junk. Never use `git add .`.

Before committing, make a version decision for the target repository. If repository config defines `[version_policy]`, use it; otherwise inspect common version sources such as `package.json`, `pyproject.toml`, `Cargo.toml`, `pom.xml`, `VERSION`, changelog/release docs, or package manifests. Do not create a version file just because none exists.

When `[version_policy] enabled = true`, bump one of the configured `files` in the same commit if the staged diff changes shipped behavior, public commands, APIs, install/update behavior, package contents, or a bug in released capability. Use the configured `scheme`; if no scheme is known, default to SemVer. Do not bump for README wording, comments, spelling, tests-only changes, or internal refactors with no user-visible contract change.

For SemVer, choose the smallest version bump that honestly describes the shipped change:

| Bump | Rule | Examples |
| --- | --- | --- |
| `PATCH` `x.y.Z` | Backward-compatible fix. | Bug fix, security fix without public contract break, correction to released commands/config/install/update behavior, or workflow rule correction. |
| `MINOR` `x.Y.0` | Backward-compatible public capability addition. | New public command, API, config option, workflow capability, snapshot field, package content, install/update behavior, or deprecation notice. |
| `MAJOR` `X.0.0` | Incompatible public contract change. | Removed or renamed command/API/config/schema, incompatible default behavior change, or migration that requires users or agents to change usage. |

When multiple categories apply, choose the highest bump: `MAJOR` over `MINOR` over `PATCH`. Reset lower segments when bumping `MINOR` or `MAJOR`.

Treat `0.y.z` versions with the same table unless the target repository defines a stricter pre-1.0 policy. Do not turn every pre-1.0 change into `MINOR` by default; use `PATCH` for small backward-compatible fixes such as `0.1.0` to `0.1.1`.

If `[version_policy] enabled = false`, no version source exists, or the staged change is non-shipping only, leave the version unchanged. Stop when a bump is required but configured version files are missing, cannot be parsed, or cannot be safely updated in the same commit.

The final report must include either `version bumped from <old> to <new> because <reason>` or `version unchanged because <reason>`.

Use an English Conventional Commit:

```text
<type>(<scope>)!: <imperative summary>
```

`scope` and `!` are optional. Allowed types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `chore`, `build`, `ci`, `style`, `revert`.

Use imperative mood, keep the subject near 50 characters when practical, hard cap 72, and do not end the subject with a period.

Add a body only for non-obvious why, breaking changes, security fixes, data migrations, reverts, or linked issues. For breaking changes, include `!` and a `BREAKING CHANGE:` note.

Never include non-English text, AI attribution, tool signatures, or mentions of Claude, Codex, Anthropic, OpenAI, or agent tooling in commit messages, MR/PR titles, or MR/PR descriptions.

For multi-line messages, prefer `git commit -F <tempfile>` or the editor flow instead of complex escaped newlines in `git commit -m`.

## Repository Delivery Mode

Resolve delivery mode once per repository and reuse it by default:

- **Remote Review:** push the task branch and create an MR/PR automatically.
- **Local Landing:** merge the task branch into the selected long-lived branch locally.
- **Push Only:** push the task branch without MR/PR or local landing.

If repository config sets `delivery_mode`, use it unless the user explicitly requested a different delivery. If no preference is known, prefer Remote Review when a remote exists and `gh` or `glab` is available for that host. Use Local Landing when MR/PR tooling is unavailable or the repo is local-only. Use Push Only only when requested or when repository constraints require it.

MR/PR creation is automatic in Remote Review mode. MR/PR merge always requires explicit user approval after review.

## Push and MR/PR

Before push, confirm branch name, commit message, current-task-only commits, check results, and clean staged state.

Recover push authentication safely:

- inspect remote URL, upstream, and exact error
- for SSH, check agent state and loaded keys in the same shell
- never print, store, script, or commit secrets
- use HTTPS fallback only when credentials are already configured or explicitly authorized

In Remote Review mode:

- push the task branch
- create an MR/PR with a concise summary and verification evidence
- keep the local task branch and worktree for review, CI, and conflict fixes
- wait for explicit user approval before merging

## Deterministic MR and Clean Subcommands

Use `localflow mr` when the user wants to create or inspect the current branch MR/PR without running the full implementation workflow. The command is script-driven:

```bash
uv run ./localflow/scripts/mr.py --cwd "$PWD" --host codex
```

The script validates that the current branch is a clean task branch with commits ahead of the base branch, runs configured `pre_commit` checks, pushes the branch, and creates or reports the existing review request. It never commits, merges, or cleans up.

Use `localflow clean` only after the work has landed:

```bash
uv run ./localflow/scripts/clean.py --cwd "$PWD" --host codex
```

The clean script never merges. It must refuse cleanup unless the current branch's MR/PR is already merged, or the task branch is already merged into the base branch for Local Landing. If the MR/PR is open, closed without merge, has a mismatched head SHA, the worktree is dirty, or lifecycle ownership is unclear, it stops without deleting the remote branch, local branch, or worktree.

### Lean Remote Review Path

When the environment snapshot or the current session has already proven remote auth for this host, do not re-run expensive discovery commands unless something fails. If repository config sets `[delivery] remote_provider`, use that provider unless set to `auto`.

For a normal GitLab MR from the current task branch, do not pre-list MRs. Prefer this short path:

```bash
git push -u origin <branch>
glab mr create --source-branch <branch> --target-branch <target> --title "<title>" --description "$(cat <mr.md>)" --yes
glab mr view <branch> --output json
```

Use the MR response to confirm `state`, `source_branch`, `target_branch`, `sha`, `detailed_merge_status`, `head_pipeline`, and `web_url`.

If MR creation fails because an MR already exists, inspect that MR instead of retrying creation:

```bash
glab mr view <branch> --output json
```

Avoid defaulting to `glab repo view`, `glab mr create --help`, repeated `glab auth status`, pre-listing MRs, or broad CI polling. If `head_pipeline` is `null` and CI evidence is required, check by SHA once:

```bash
glab api '/projects/:id/pipelines?sha=<sha>'
```

If both checks show no pipeline, report that no pipeline was created instead of polling. If JSON filtering is needed, prefer `python3`; do not assume `jq` or `python` exist.

## Landing and Remote Cleanup

In Local Landing mode, merge into the selected long-lived branch after verification and review gate pass. Run required post-merge checks before cleanup.

In Remote Review mode, merge only after the user explicitly approves. After merge, delete the remote task branch unless the platform already deleted it or the user says to keep it. Do not add a remote branch cleanup check when the platform confirms source-branch removal; inspect only when cleanup state is unclear.

In Push Only mode, report the pushed ref and leave merge/MR decisions to the user unless repository preference says otherwise.

After landing or confirmed abort, hand off to `git.md` for local branch/worktree cleanup.

## Final Report

Report:

- delivery mode
- long-lived branch
- task branch
- commit hash/message
- pushed ref, if any
- MR/PR URL and status, if any
- checks run and skipped checks
- review result and remaining risk
- remote branch cleanup
- local branch/worktree cleanup
- localflow config path used, or `absent`
- version decision and reason

## Stop Conditions

Stop when configured version files are missing while version bump is required, commit scope is unclear, task-related checks fail, delivery mode is unknown, auth recovery would expose secrets, force push would be required without approval, MR/PR merge lacks explicit approval, or remote branch cleanup ownership is unclear.

## Common Mistakes

- Asking every time whether to create MR/PR after the repository is in Remote Review mode.
- Merging an MR/PR because it was created.
- Letting `git add .` stage unrelated user work.
- Deleting remote branches before the work has landed.
- Pre-listing MR/PRs before creation on the normal path.
- Polling CI when MR/PR status already proves the required state.

## Red Flags

- Commit message describes more than the staged diff.
- Push target is a protected or shared branch.
- Remote Review worktree is cleaned before MR/PR merge.
- Merge or force push is about to happen without explicit user approval.
