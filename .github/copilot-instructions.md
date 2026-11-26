<!-- wally-init:entry:start -->
## Classify the request before entering development SOP

- Development SOP is required for feature implementation, bug fixes, refactoring, performance work, and changes to runtime behavior, APIs, data structures, configuration, scripts, Agent rules or Skills. Design, contracts and accompanying documentation within that development request remain part of its SOP; a small change or a document-only intermediate step is not an exemption. Follow task context when the user explicitly starts/resumes SOP.
- Handle directly without creating an SOP task: questions, explanations, read-only analysis/standalone review, status checks, unrelated conversation, and purely editorial documentation work, and staging/committing existing changes (git add / git commit). Inspect the actual request and diff; the Git operation itself does not require a new SOP task or retroactive six-phase artifacts, even when existing changes include code. Honor existing development delivery gates, project commit rules and user authorization.
- Scope follows the current requested work, not question phrasing, file suffix, line count, or whether the branch already has a task. Enter SOP if consultation turns into a development request. Mixed code, runtime configuration, rule or behavior changes are not documentation exemptions. Calling an existing development delivery a commit-only operation does not waive its applicable gates. A neutral Git hook result neither proves gate completion nor grants Commit/Push authorization.

## Mandatory checkpoint for development tasks

Once the request is classified as development, small changes, simple features, or adding one page do not exempt it from SOP. Reading this root file does not complete task routing. Before investigating implementation, editing business files, or executing change commands:

1. Read `.wally/core/entry.md` and run `python3 .wally/scripts/sop_context.py` to route by the actual branch. Reuse any current routing result and look up only missing fields.
2. For a matched task, use the script output to load the task overview, bound rules, project policy, and current phase. If there is no task and the user has not chosen a branch, ask for the branch as directed by the entry and wait. Routing stops there for this turn. Resolve other issues such as missing files or ambiguous matches before implementation.
3. In the first work update, report the actual branch, task directory, rules version, and current phase. If a task is pending creation, label the version as the currently installed version. Report only verified facts.
4. Before each phase, read its artifact and required bound rules. Complete Clarify and Plan before implementing. Repeat routing after compaction, resumption, branch changes, or delegation. Explicitly pass task, bound version, and phase to subagents; they follow this checkpoint too.

5. For knowledge, start at `.wally/docs/INDEX.md`; read and update relevant pages under the task-bound `core/knowledge.md` policy. Missing indexes fall back to actual Profile documentation paths and source; record gaps.
6. Repository-managed Skills live canonically under `.agents/skills/` (`clarify`, `sop-aware-code-review`, `wally-open-cli`), with per-skill symlinks into mainstream IDE/CLI `skills/` directories. Upon entering `01 Clarify` (unless formally skipped by SOP), read `.agents/skills/clarify/SKILL.md` together with the task-bound `core/clarify.md` before asking questions or editing `01-clarify.md`.

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

Checkpoint exit code 3 means awaiting confirmation. Show the reason and `CONFIRM SOP <id>` once in the reply. Do not also call a question tool or emit another question card for the same decision; the chat UI turns that text into one decision card. The user must still explicitly send that exact text in chat for the input Hook to record approval. Never send it on the user's behalf, edit `.wally/local/sop-confirmations.json`, fabricate artifacts or retry in a loop. Rejection, silence, invalid or stale IDs are not approval. Do not ask again for the same task/phase with unchanged evidence; recheck after changes to branch, task, phase, bound rules or relevant evidence. Without the input Hook, remain pending or satisfy the prerequisites; never claim automatic approval.

Confirmation permits continuation with the stated gaps. Record the actual user authorization, missing evidence and unverified scope in the overview. Do not auto-complete prerequisites or turn SKIPPED/unverified work into a pass; all other acceptance criteria still apply. Phase checks and Review continue to evaluate quality. General tools are not denied by an SOP command allowlist or context error. Shell/MCP are not comprehensively intercepted: the Agent must invoke phase checkpoints explicitly. Existing client permissions and user authorization remain effective.

The Hook loads context and requests the two scoped confirmations for recognized business edits. General Shell, Git and date commands are not restricted by an SOP allowlist. Explicitly run the corresponding --checkpoint before Implement/Deploy/IT, then await user confirmation or satisfy the prerequisites. Confirmation permits disclosed gaps, never a false completion claim. Without enabled, trusted, supported Hooks these remain instructions, not comprehensive interception. Existing client permissions, user constraints and authorization remain effective.
<!-- wally-init:entry:end -->
