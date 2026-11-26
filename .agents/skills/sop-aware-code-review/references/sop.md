# SOP Review Criteria

Evaluate each task strictly against its bound rules. Start by reading `00-overview.md` for version, rule paths, Profile, workflow, and task status. For `.wally` tasks, read the bound Core's `workflow.md` and `gates.md`, `.wally/profiles/project.md`, `.wally/review.md`, and the task's `execution.json` (legacy tasks with their own `profile.md` / `_rules/review.md` remain readable). Read relevant architecture, API, data, test, and deployment docs under `.wally/docs/` or `docs/`. Report missing or conflicting rule paths as evidence gaps; never retroactively judge historical tasks using newer templates.

## Layout & Gates

- Six-phase `.wally` tasks cover `00-overview.md` through `05-it.md` (`03` includes implementation, UT, incremental coverage, Docs, and incremental CR; match by headings and bound rules across English/Chinese variants).
- Legacy four-phase tasks cover `00` through `03` (Deploy/IT not applicable). Review the final Review/Commit phase only when explicitly requested; `03` incremental CR remains in scope.
- For current `.wally` six-phase tasks, inspect `deploy` and `it` in `execution.json`. When both `command` and `guide` are empty (and not marked `readiness: pending`), verify `SKIPPED` records, justification, timestamps, and disclosed unverified scope. When configured, missing permissions/tools/environment or failed runs must be recorded as failed/blocked rather than disguised as skipped.

## Evidence Checks

- **Status & Authorization**: Verify branch, goal, status, phase progression, and timeline. Tickets, branch prefixes, phase confirmations, or exception approvals are gates only when required by bound rules. Missing or out-of-order timestamps indicate an evidence gap, not automatic proof of retroactive fabrication.
- **Clarify & Plan**: Map acceptance criteria to design, files, tests, and delivery evidence. Check call chains, API/data migrations, legacy data/clients, rollout, rollback, and failure boundaries where relevant to the change.
- **Implement, UT & Incremental CR**: Verify plan deviations and their approvals, TDD/regression evidence, test commands, and key assertions. Confirm coverage metrics reflect current-version incremental coverage against task-bound thresholds. Self-review does not substitute for independent code review.
- **Deploy / IT**: Verify actual environment, deployed version, commands/jobs, per-case outcomes, traceable logs/run IDs, and rollback readiness. Distinguish assertion, execution, and environment failures. Re-verify if core logic changed after earlier runs. Skipped never counts as verified.
- **Docs**: Check whether architecture, config, API, data, test, or ops contract changes have matching doc updates, or a verifiable not-applicable justification.
