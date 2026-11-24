# SOP 2.0 workflow

<!-- wally:sop-scope:start -->
## Classify the request before entering development SOP

- Development SOP is required for feature implementation, bug fixes, refactoring, performance work, and changes to runtime behavior, APIs, data structures, configuration, scripts, Agent rules or Skills. Design, contracts and accompanying documentation within that development request remain part of its SOP; a small change or a document-only intermediate step is not an exemption. Follow task context when the user explicitly starts/resumes SOP.
- Handle directly without creating an SOP task: questions, explanations, read-only analysis/standalone review, status checks, unrelated conversation, and purely editorial documentation work, and staging/committing existing changes (git add / git commit). Inspect the actual request and diff; the Git operation itself does not require a new SOP task or retroactive six-phase artifacts, even when existing changes include code. Honor existing development delivery gates, project commit rules and user authorization.
- Scope follows the current requested work, not question phrasing, file suffix, line count, or whether the branch already has a task. Enter SOP if consultation turns into a development request. Mixed code, runtime configuration, rule or behavior changes are not documentation exemptions. Calling an existing development delivery a commit-only operation does not waive its applicable gates. A neutral Git hook result neither proves gate completion nor grants Commit/Push authorization.
<!-- wally:sop-scope:end -->

## Recovery and task creation

1. Use `git branch --show-current`. Match only the Branch discovery field in `.wally/plans/*/00-overview.md`, then read the matched task. Resolve multiple matches instead of choosing arbitrarily.
2. Read its SOP Rules path, project policy snapshot, and current phase before loading phase artifacts and relevant rules. Never overwrite an existing task using templates from another version.
3. When no task exists and this development SOP is about to start, tell the user the current branch and ask whether to cut a new task branch. Wait for an explicit answer before creating the task or editing code. Do not treat an already checked-out non-default branch as the task branch. If the user wants a new branch, agree on a name under project conventions, preserve uncommitted work, create and switch to it, then run `python3 .wally/scripts/create_task.py YYYY-MM-DD_title --branch <chosen-branch>`. Staying on the current branch is allowed only when it is not main/master/HEAD. Do not implement on the default branch. The script performs no Git operations. If this request already names the task branch (stay or create), follow that choice without asking again. If the current branch already has a bound task, resume it and do not ask.
4. Recover unversioned historical tasks through `.wally/compat/v1/`. A missing snapshot blocks recovery; do not apply 2.0 implicitly. Explicit migration requires assessment of existing evidence and contract differences.

<!-- wally:root-summary:start -->
## Phases and completion criteria

For new development tasks only. Consultation and lightweight documentation operations do not activate this workflow. Existing tasks always follow their bound version; this outline does not replace a historical task contract.

- 01 Clarify: measurable goals, scope, success criteria, key constraints, and unresolved business questions. Read `.agents/skills/clarify/SKILL.md` and this version's `clarify.md`; validate sufficient inputs without repeating interviews.
- 02 Plan: impact, call chains/state machines, data/protocol compatibility, UT/IT design, risks, and rollback.
- 03 Implement + UT + Docs: follow project rules under `.wally/rules/`, then Red → Green → Refactor → incremental coverage → Docs → incremental CR. Applicable gates must pass before Deploy.
- 04 Deploy: environment, baseline, scope, effective-version verification, and rollback. Preserve defect baselines before hot updates.
- 05 IT: execute Plan, inspect individual results and aggregate gates, and close defect A/B verification.
- 06 Review + Commit: read `.agents/skills/sop-aware-code-review/SKILL.md` (also applicable to 03 incremental CR), recheck changed evidence, time logs, and residual risk; handle authorized external systems/resources and prepare the commit before authorized Git operations.

### Phase Dependency Summary (Skills / Rules / Tools & Checkpoints)

| Phase | Skill (`.agents/skills/`) | Rules (Bound Version / Task Snapshot) | Tools / Checkpoints |
|---|---|---|---|
| 01 Clarify | `clarify/SKILL.md` | `core/clarify.md`, `core/gates.md`, `core/knowledge.md` | `sop_context.py`, `create_task.py`, `date` |
| 02 Plan | — | `core/workflow.md`, `core/gates.md`, `core/knowledge.md` | `.wally/docs/INDEX.md`, `date` |
| 03 Implement + UT + Docs | `sop-aware-code-review/SKILL.md` (incremental CR) | `.wally/rules/`, `core/gates.md`, `core/knowledge.md` | `sop_context.py --checkpoint implement`, UT/coverage commands |
| 04 Deploy | Optional `wally-open-cli/SKILL.md` | `core/gates.md` | `sop_context.py --checkpoint deploy`, task snapshot `execution.json` |
| 05 IT | Optional `wally-open-cli/SKILL.md` | `core/gates.md` | `sop_context.py --checkpoint it`, task snapshot `execution.json` |
| 06 Review + Commit | `sop-aware-code-review/SKILL.md` | `.wally/review.md`, `.wally/commit.md`, `core/gates.md` | Client `token_report.py`, `git`, `date` |

New tasks always retain all six phases 01–06. A method explicitly marked `readiness: pending` is incomplete even with a guide/command: mark it BLOCKED and request the missing `gaps` from the user; do not auto-skip it. Only ready methods (or legacy configurations without readiness) use the command/guide rule below; ready does not mean execution passed. Before Deploy/IT read this task's `execution.json`: when both command and guide are empty, automatically skip without preparing environments or invoking tools; retain the generated SKIPPED records and zero-duration rows. If either method is set, execute the customer instructions. Missing environment, permission, or tools and execution failures must not be disguised as unconfigured skips. Skipped is not passed: disclose missing deployment/integration verification in Review and enforce other applicable gates. Historical tasks continue under their own bound rules.

Before actual Implement, Deploy or IT work, run `python3 .wally/scripts/sop_context.py --checkpoint implement`, `--checkpoint deploy` or `--checkpoint it`, respectively. If Clarify/Plan is incomplete or still an empty template, or the user intends to execute Deploy/IT without a configured method, explain the missing evidence, proposed action and impact, then wait for explicit user confirmation. Automatically skipping an unconfigured Deploy/IT phase requires no confirmation. An exception does not supply an execution method: obtain real commands/guidance rather than guessing.

Checkpoint exit code 3 means awaiting confirmation. Use an available question tool or chat to show the reason and `CONFIRM SOP <id>`; the user must explicitly send that exact text in chat for the input Hook to record approval. Never send it on the user's behalf, edit `.wally/local/sop-confirmations.json`, fabricate artifacts or retry in a loop. Rejection, silence, invalid or stale IDs are not approval. Do not ask again for the same task/phase with unchanged evidence; recheck after changes to branch, task, phase, bound rules or relevant evidence. Without the input Hook, remain pending or satisfy the prerequisites; never claim automatic approval.

Confirmation permits continuation with the stated gaps. Record the actual user authorization, missing evidence and unverified scope in the overview. Do not auto-complete prerequisites or turn SKIPPED/unverified work into a pass; all other acceptance criteria still apply. Phase checks and Review continue to evaluate quality. General tools are not denied by an SOP command allowlist or context error. Shell/MCP are not comprehensively intercepted: the Agent must invoke phase checkpoints explicitly. Existing client permissions and user authorization remain effective.

<!-- wally:root-summary:end -->

## Recording and rollback

- The overview is the source of truth for progress, authorization, and cross-phase decisions. Keep one Progress entry per phase and update Current phase. Record task facts rather than duplicating manuals.
- At each start/end use `date "+%Y-%m-%d %H:%M:%S"`. Record seconds, duration, and conversation rounds. Recover missing times only from this task's identifiable conversation evidence and cite it. Otherwise return to the missing phase, redo it, and record actual times. Preserve previous records and reasons. Blank or guessed retrospective entries cannot pass Review/Commit.
- Validate and reuse user-provided Clarify/Plan work; record inputs and any justified skip rather than deleting the original design.
- Return design defects to Plan, code/test/docs defects to Implement, and rerun after environment repairs. Revalidate evidence affected by changes instead of merely changing checkboxes.
- Read other tasks only when explicitly requested. Their evidence cannot prove this task passed. Do not maintain a shared global plan.md.
- Complete overview/report preparation before `git add`. Record actual Commit/Push results; preparation alone is not delivery.

## Reusable lessons

Add only actual, reusable lessons to the project's existing experience file. Deduplicate, state applicability and source, and keep one-off constraints in the task. Persistent project-rule changes require authorization; do not expand rules speculatively.

## Knowledge lifecycle

Read `knowledge.md` from this bound Core version for all development phases. It defines shared documentation routing, incremental updates, and final Docs verification.
