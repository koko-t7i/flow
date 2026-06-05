# Contribution

## Core Principle

Contribution owns the handoff from verified local changes to commit, push, MR/PR, merge, and remote branch cleanup. Local branch and worktree mechanics are owned by `git.md`.

## Commit

Before staging, inspect the final diff. Inspect recent commit style with `git log -5 --oneline` only when repository conventions are unknown or appear to conflict with this skill.

Stage only current-task files. Confirm `git diff --cached` contains the intended change and no sensitive or generated junk. Never use `git add .`.

Before committing, make a version decision for the target repository by inspecting common version sources such as `package.json`, `pyproject.toml`, `Cargo.toml`, `pom.xml`, `VERSION`, changelog/release docs, or package manifests. Do not create a version file just because none exists.

Bump the relevant version source in the same commit only when repository conventions require it and the staged diff changes shipped behavior, public commands, APIs, install/update behavior, package contents, or a bug in released capability. Do not bump for README wording, comments, spelling, tests-only changes, or internal refactors with no user-visible contract change.

For SemVer, choose the smallest version bump that honestly describes the shipped change:

| Bump | Rule | Examples |
| --- | --- | --- |
| `PATCH` `x.y.Z` | Backward-compatible fix. | Bug fix, security fix without public contract break, correction to released commands/config/install/update behavior, or workflow rule correction. |
| `MINOR` `x.Y.0` | Backward-compatible public capability addition. | New public command, API, config option, workflow capability, snapshot field, package content, install/update behavior, or deprecation notice. |
| `MAJOR` `X.0.0` | Incompatible public contract change. | Removed or renamed command/API/config/schema, incompatible default behavior change, or migration that requires users or agents to change usage. |

When multiple categories apply, choose the highest bump: `MAJOR` over `MINOR` over `PATCH`. Reset lower segments when bumping `MINOR` or `MAJOR`.

Treat `0.y.z` versions with the same table unless the target repository defines a stricter pre-1.0 policy. Do not turn every pre-1.0 change into `MINOR` by default; use `PATCH` for small backward-compatible fixes such as `0.1.0` to `0.1.1`.

If no version source exists or the staged change is non-shipping only, leave the version unchanged. Stop when a required bump cannot be parsed or safely updated in the same commit.

The final report must include either `version bumped from <old> to <new> because <reason>` or `version unchanged because <reason>`.

Use an English Conventional Commit:

```text
<type>(<scope>)!: <imperative summary>
```

`scope` and `!` are optional. Allowed types: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `chore`, `build`, `ci`, `style`, `revert`.

Use imperative mood, keep the subject near 50 characters when practical, hard cap 72, and do not end the subject with a period.

Add a body only for non-obvious why, breaking changes, security fixes, data migrations, reverts, or linked issues. For breaking changes, include `!` and a `BREAKING CHANGE:` note.

Never include non-English text, AI attribution, tool signatures, or mentions of Claude, Codex, Anthropic, OpenAI, or agent tooling in commit messages, MR/PR titles, or MR/PR descriptions.

When updating an already-pushed review branch, do not rewrite history unless
the user explicitly approves force push. Append a follow-up commit instead, but
give that commit its own precise Conventional Commit subject; do not reuse an
existing subject in the same review.

For multi-line messages, prefer `git commit -F <tempfile>` or the editor flow instead of complex escaped newlines in `git commit -m`.

## Repository Delivery Mode

Resolve delivery mode once per repository and reuse it by default:

- **Remote Review:** push the task branch and create an MR/PR automatically.
- **Local Landing:** merge the task branch into the selected long-lived branch locally.

Use `default_mode` from repository config unless the user explicitly requested a different delivery. `tree` is Remote Review and requires `remote_cli = "gh"` or `remote_cli = "glab"`. `fast` is Local Landing and does not require a review CLI.

MR/PR creation is automatic in Remote Review mode. MR/PR merge always requires explicit user approval after review.

`tree` mode is the normal Remote Review workflow. `fast` mode is a Local
Landing workflow for a committed isolated worktree; it does not push, create a
review request, or clean worktrees/branches.

## Push and MR/PR

Before push, confirm branch name, commit message, current-task-only commits,
check results, and clean staged state. `localflow mr` refuses to push a review
branch when any commit ahead of the base has an invalid Conventional Commit
subject or when two commits in the review share the same subject.

Recover push authentication safely:

- inspect remote URL, upstream, and exact error
- for SSH passphrase prompts, retry only through the configured ignored passphrase file
- when the passphrase file is unavailable, use the configured `gh`/`glab` path or HTTPS fallback
- never print, store, script, or commit secrets
- use HTTPS fallback only when credentials are already configured or explicitly authorized

In Remote Review mode:

- push the task branch
- create an MR/PR with a concise summary and verification evidence
- keep the local task branch and worktree for review, CI, and conflict fixes
- wait for explicit user approval before merging

## Deterministic Subcommands

`SKILL.md` owns subcommand routing and runnable script examples. This reference owns the contribution rules those scripts enforce.

- `localflow commit` stages only named `--paths`, validates an English Conventional Commit subject before git writes, and can chain into `mr` with `--mr`.
- `localflow mr` creates or reports the current clean task branch review. Snapshot mode is the shared-checkout exception: it captures only named `--paths` into a side branch without touching the working tree, index, or `HEAD`.
- `localflow fast` is the local landing entrypoint for a committed isolated worktree. Mode details live in [modes/fast.md](modes/fast.md).
- `localflow clean` is the only cleanup entrypoint. It never merges and only deletes branches, worktrees, or remotes that are already landed.

### Lean Remote Review Path

When repository config sets `remote_cli`, use that CLI directly and do not re-run provider discovery unless the configured command fails.

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

If both checks show no pipeline, report that no pipeline was created instead of polling. If JSON filtering is needed, prefer `uv run python`; do not assume `jq` exists.

## Landing and Remote Cleanup

In Local Landing mode, merge into the selected long-lived branch after verification and review gate pass. Run required post-merge checks before cleanup.

In Remote Review mode, merge only after the user explicitly approves. After merge, delete the remote task branch unless the platform already deleted it or the user says to keep it. Do not add a remote branch cleanup check when the platform confirms source-branch removal; inspect only when cleanup state is unclear.

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

Stop when a required version bump cannot be safely applied, commit scope is unclear, task-related checks fail, delivery mode is unknown, auth recovery would expose secrets, force push would be required without approval, MR/PR merge lacks explicit approval, or remote branch cleanup ownership is unclear.

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
