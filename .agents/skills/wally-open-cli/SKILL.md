---
name: wally-open-cli
description: Delegate the current repository to open-source Wally for development or testing, then inspect or manage that task. Use for wally-open-cli, open-source delegation, status, list, approval, advance, skip, retry, and CLI configuration. Do not use it to implement locally, require a TAPD ticket, or replace the separate internal skill named wally-cli.
---

# wally-open-cli

This skill is installed only as `wally-open-cli`. Do not write or replace `.agents/skills/wally-cli/`. Internal TAPD delegation stays with the skill named `wally-cli`.

The open-source command is `wally-open-cli`, from the package `@tencent/wally-open-cli`. Do not install, upgrade, or invoke `@tencent/wally-cli`; that package is the internal client. The open-source flow creates a hosted task from a repository, component, and development branch. Requirements live in the SOP files on that branch. Wally does not read TAPD or any other ticket.

Do not ask for a TAPD URL and do not pass `--tapd-url`. Attach that flag only when the user already supplied a full ticket URL and asked to store it.

The hosted task name is the first line of `00-overview.md`. Before delegating, replace the template heading with the real requirement, for example `# [2026-11-03] Restore the import flag`. The service removes the date and the `#`, brackets, and quotes around that text, leaving `Restore the import flag`. A heading that still contains `<Task title>` or `YYYY-MM-DD` falls back to the development branch name.

## Readiness

Run `wally-open-cli --help` first. If the command is missing, install the open package: `npm install -g @tencent/wally-open-cli@latest --registry=https://mirrors.tencent.com/npm/`. Do not install `@tencent/wally-cli`; that package targets the internal deployment and treats a ticket URL as required.
Install `httpx` and `pydantic` with the user's Python only after `ModuleNotFoundError`. Do not install those names with npm.
`wally-open-cli config show` must show an `api_base_url` that includes the real port. An authorized `curl -s <api_base_url>/ok` should contain `"ok": true` before delegation. Never hardcode an environment IP. Precedence is argument, then `WALLY_API_BASE_URL`, then `~/.wally/config.json`, then the CLI default.

## Delegate

```bash
wally-open-cli delegate \
  --staffname "<wally-account>" \
  --task-flow dev_test \
  --repo "<actual-repository>" \
  --component-name "<actual-component>" \
  --base-branch "<actual-baseline>" \
  --new-branch "feature/<actual-task>" \
  --env-id None
```

Required inputs:

- `--staffname`: the Wally account that owns the task. Use `config show` only when that account is the current user. Ask when it is missing. Never infer a local username or a fixed name.
- `--task-flow`: `dev_test` after the plan hands off development and later stages; `test` when local implementation is done and only testing remains.
- `--repo`: the repository the user named. Do not read config, use a default, or invent one.
- `--component-name`: the matching component. Ask when missing. Comma-separate joint components.
- `--base-branch`: the actual baseline. Different components use `component:branch` mappings.
- `--new-branch`: the current local branch from `git branch --show-current`, starting with `feature/` or `hotfix/`. It must differ from every baseline. Do not use `main`, `master`, or `release/*`.
- `--env-id`: required by the CLI. Use the user's environment id, or `None` when they have none. Do not ask for a ticket to fill it.

`--tapd-url` is optional and omitted by default. A supplied value must be a full TAPD URL; a numeric id is rejected. Optional flags: `--pattern` (`code` by default, `ask` for Q&A), `--no-auto-commit`, `--it-plugins`, `--owner`, `--project-id`, `--assistant-id`, `--agent-name`. Use `--force-new` only when the user explicitly wants the previous task closed and a new one created.

For `dev_test`, `00-overview.md`, `01-clarify.md`, and `02-plan.md` must already be committed and pushed in the new branch's diff against the baseline. `test` does not require them. Do not use removed flags `--context-dir`, `--context-file`, or `--push-sop`.
Confirm the baseline and new branch with the user before running the command.

## Other actions

- `wally-open-cli init --staffname <account>` writes client configuration. Its repository value is display-only; delegate still needs an explicit `--repo`.
- `wally-open-cli status <task_id>` reads the returned task id.
- `wally-open-cli config show` shows the effective service address.
After delegation returns a task ID, report the ID and dashboard link. Follow progress with `status`. Report blockers without requesting or performing approvals in the handoff chat.

- Use `list`, `approve`, `advance`, `skip`, and `retry` only for the requested state change. Verify unfamiliar flags with the installed `--help`. Progress checks use `status`, not advance/skip/retry.

On success, report `task_id` and `wally_task_url`, and say that `wally-open-cli status <task_id>` can follow progress. On failure, quote `error`, keep the evidence, and do not claim the task was created or retry it automatically.
