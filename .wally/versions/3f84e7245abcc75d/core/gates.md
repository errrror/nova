# SOP 2.0 quality gates

## Rules and evidence

Core defines quality requirements; the project profile binds language/runtime versions, commands, thresholds, and extensions. Existing stricter constraints remain effective. Do not silently lower gates through profiles or risk categories; resolve conflicts explicitly.
Report passed, failed, unverified, or inapplicable. Inapplicability requires evidence. Missing tools, empty results, all-skipped runs, and inaccessible environments are not passes.
Evidence includes the executed command, code version, input/environment, case/report identifier, key output, and conclusion. Cite only evidence actually read or executed in this task. Preserve necessary summaries of temporary reports in phase artifacts.

## Clarify / Plan

- Define verifiable goals, scope, dependencies, and unresolved questions. Do not implement guessed business decisions.
- Design UT/IT before implementation: positive, negative, boundary, and recovery cases. Assess affected call chains, fallback, retry, terminal exits, side-effect placement, compatibility, and rollback.
- Verify write idempotency and external-dependency failures. Declare UT mock boundaries; scenario tests isolate external dependencies only. For failure side effects test both final failure triggering once and intermediate failure followed by success not triggering. Check each terminal exit.
- Base the design on actual code, existing tests, architecture/interfaces, and upstream/downstream contracts. Establish responsibility boundaries before drawing conclusions.
- Design Unicode cases for JSON or multilingual data in UT and applicable IT.
- For bugs/performance define failure criteria, the lowest reproducible layer, before/after inputs, equivalent conditions, and metrics. When the environment baseline cannot run, identify comparable retained evidence and its limits.

## Implement

- Before coding, read project rules under `.wally/rules/` and follow them in code, tests, and documentation updates. If the directory is missing or contains only the directory note, record that there are no extra project rules. When a rule conflicts with these gates, the stricter requirement applies; stop and ask when the conflict cannot be resolved.
- Write a test exposing the issue before implementation. Red must be the expected assertion failure, not syntax/environment failure. Green uses the same assertions; rerun after refactoring or explain why none is needed.
- Measure incremental lines/branches of changed production code against project classification thresholds. No executable branches may be N/A. Never fabricate coverage or substitute whole-project coverage; let the user decide an unresolved verification boundary.
- Justify generated/declarative code exclusions. Documentation-only work does not fabricate Red/Green; other applicable gates still apply.
- Assess and update authoritative docs without parallel versions. Review the actual project language/runtime versions and rules for security, concurrency, idempotency, failure handling, and compatibility. Resolve high-severity findings before delivery.

## Deploy / IT / defect closure

- Deployment needs scope, version, effectiveness evidence, and executable rollback. Tests need isolation, authentication, and cleanup.
- Check each Plan case, assertion failures, environment/execution errors, skipped reasons, uncovered scope, and residual risk; exit code alone is insufficient.
- Bug/performance tasks with configured environment verification: run an unfixed baseline A when possible; otherwise use retained comparable historical evidence and explain why. Execute B under equivalent controlled conditions; performance requires multiple runs/statistics. Invalid A or failing B blocks Commit.
- Unconfigured Deploy/IT is automatically SKIPPED without requiring environment A/B. Keep code-level Red/Green and other applicable gates; explicitly state environment A/B is incomplete, never claim end-to-end verification. This exception does not excuse failures after configuration.

## Review / Commit

Recheck final diff, Plan deviations, applicable gates, docs, defect evidence, and time records. Prepare under project commit rules and authorization. When a collector is installed, actively run the matching report and inspect the result:
- Codex: `python3 .codex/scripts/token_report.py`
- CodeBuddy / Cursor: `python3 .codebuddy/scripts/token_report.py`
Do not reuse an old report after failure or handwrite usage. Missing, unsupported, or partial collection is not zero usage. With no collector, record not enabled rather than installing an extra client to obtain a zero report. Git, external writes, and resource release each follow actual authorization.

## Mandatory time-log audit

Before Review, the overview must have exactly six rows 01–06 for new tasks. Completed phases need start/end to seconds, duration, rounds, reasonable order, and Progress/artifact agreement.
Backfill only with identifiable conversation evidence and label the source. Without evidence return to and redo the missing phase with actual timestamps. Blank, missed, unsupported, or fabricated retrospective entries block Commit; conditional approval is prohibited.
Legitimate inherited/skipped phases need a reason and a complete zero-duration row: start=end, 0s, 0 rounds. Automatically skipped Deploy/IT retains the actual skip-decision time at task creation (start=end), 0s, and 0 rounds with an explicit not-executed note. This is decision time, not execution chronology. Review may temporarily lack its own end time while active, but must finish that row before approval. Recording times does not require extra user confirmations.

## Token conversation rollup

Keep per-request ledger semantics. In the overview, one row is one user conversation turn: sum Codex calls by thread/root turn and consecutive same-prompt CodeBuddy calls by session. Cursor whole-turn cumulative usage is already deduplicated by maximum; never sum its steps again. Do not commit raw token.json. State collection health and snapshot boundaries.

## Docs verification

Apply the bound `knowledge.md` policy. Record source-to-document impact and actual validation; final Review must cover changes made during Deploy/IT as well. Unresolved stale pages or unverified updates cannot pass Docs.
