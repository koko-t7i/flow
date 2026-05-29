# Contribution

## Core Principle

Contribution owns the handoff from verified local changes to commit, push, MR/PR, merge, and remote branch cleanup. Local branch and worktree mechanics are owned by `git.md`.

## Commit

Before staging, inspect the final diff. Inspect recent commit style with `git log -5 --oneline` only when repository conventions are unknown or appear to conflict with this skill.

Stage only current-task files. Confirm `git diff --cached` contains the intended change and no sensitive or generated junk. Never use `git add .`.

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

If no preference is known, prefer Remote Review when a remote exists and `gh` or `glab` is available for that host. Use Local Landing when MR/PR tooling is unavailable or the repo is local-only. Use Push Only only when requested or when repository constraints require it.

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

### Lean Remote Review Path

When the environment snapshot or the current session has already proven remote auth for this host, do not re-run expensive discovery commands unless something fails.

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

## Stop Conditions

Stop when commit scope is unclear, task-related checks fail, delivery mode is unknown, auth recovery would expose secrets, force push would be required without approval, MR/PR merge lacks explicit approval, or remote branch cleanup ownership is unclear.

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
