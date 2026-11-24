# Code review guide

Incremental CR belongs in `03-implement.md`. Read the task profile's relevant project rules first and review against actual language/runtime versions, never assumed latest syntax. Project rules take precedence. Final Review rechecks changed evidence rather than duplicating this checklist.

## SOP compliance — P0 blocking gate

Identify the task by branch; read its bound Core gates.md and project policy snapshot. Unversioned tasks use compat/v1 review rules. Check Progress, phase artifacts, and complete start/end/duration/rounds records: six phases 01–06 for new tasks. Blank, missed, unsupported, or invented retrospective times fail. Backfill only from real identifiable conversation evidence; otherwise redo the missing phase with actual times. Review's own end can remain blank only while in progress, never at approval.
Record evidence for inherited/skipped phases. Deploy/IT is automatically skipped only when its command and guide in execution.json are unset. Configured failures or low risk do not permit a skip. Automatic skip rows record actual decision time at task creation, not execution. Check Branch, SOP Version/Rules, profile snapshot, task type/status, risk, and authorization. Missing task rules cannot fall back to current rules. Failed compliance cannot receive conditional approval or proceed to code review; fix first. Follow the task's interaction cadence without fixed confirmation ceremonies.

## Severity

- High/blocking: security, data loss, protocol breakage, or performance regression; fix before merge.
- Medium: missing boundaries/error handling, poor testability, or ambiguous names; fix or explicitly record disposition.
- Low: style, refactoring, and documentation suggestions; optional.

## Blocking checks

- Parameterize SQL; no embedded secrets. Validate every external input, escape output for HTML/SQL/Shell context, and use standard cryptography.
- Cover empty/single/oversize/negative/out-of-range inputs. Protect concurrent shared state, define transactions/rollback, and honor idempotency/retry/timeouts.
- Bind circuit-breaking, alerts, charging, and state writes to final responsibility/terminal exits. Inspect fallback, retries, routing redelivery, legacy fallback, and every terminal exit; do not trigger on intermediate failures or miss final ones.
- Log key paths and errors with trace_id/request_id and context; configure relevant metrics/alerts.

## Standard checks

- UT records Red → Green → Refactor. Incremental line/branch coverage meets this code category's gates; whole-project coverage is not a substitute.
- Public contracts define inputs/outputs/errors. Avoid hidden global state; use clear names, focused functions, suitable abstraction layers, and factor repeated logic (three or more copies).
- Maintain protocol backward compatibility, rollbackable schema changes, and constrained dependency versions.
- Explain why in comments. Synchronize affected authoritative API/SQL/architecture/devops/unittest docs. Use realistic test data.

## Feedback format

Start with SOP compliance: task overview path, time rows/evidence, Progress agreement, and pass/fail rationale. On failure return to the missing phase; do not accept a missed-time note as closure.
Then report `[severity] [file:line] finding`, evidence/impact, and a concrete correction.

## Knowledge consistency

- [ ] Apply the task-bound `core/knowledge.md` policy to the final task diff. Check `.wally/docs/INDEX.md`, affected codewiki pages, authoritative SOP specifications, and `.wiki-meta.json` mappings; verify actual content and source anchors. Record protected-page drift and missing/unverified items; unresolved items do not pass Docs.
