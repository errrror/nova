# SOP 2.0 interaction and risk

Keep quality gates separate from confirmation cadence. Continue reversible local work within existing authorization. At phase boundaries report conclusions, evidence, elapsed time, and the next action; do not request repetitive start/end approvals.

## Stop boundaries

- Missing business input that changes implementation, major design decisions, or conflicting project rules.
- Actions beyond existing authorization or requiring approval from the execution environment. Assess shared/production deployment, resource deletion, external writes, and Commit/Push by their actual scope. Existing explicit authorization persists; starting an SOP does not authorize arbitrary external writes.
- Respect a user-requested stopping point at design, implementation, or commit preparation.
- Before a new development task is bound to a branch, ask whether to cut a new task branch. This chooses branch ownership; it is not an extra risk-based startup approval. Do not ask again after the user answers. Resume a branch that already has a bound task.

Present the decision alongside concrete reviewable work. Continue independent work while waiting. Record known inputs, authorization, and execution location in the overview; do not ask again. Silence is not authorization.

## Risk and recording depth

- Low: local, reversible work without external contract or schema changes. Use concise facts and evidence in the same template.
- Medium: cross-module changes, public interfaces, or substantial state logic. Explain dependencies, failure paths, compatibility, and rollback.
- High: cross-component changes, migrations, security, billing, concurrency consistency, or high-impact environments. Detail recovery, baselines, verification limits, release order, and rollback conditions.

Recommend and record risk from actual impact. Seek a user decision only for substantive disagreement or new decisions, without a fixed startup approval. Escalate risk and update Plan/testing when scope expands. Lines of code do not determine risk. Do not maintain three template families or waive applicable gates for low-risk work.

## Execution location

Continue in the currently authorized location. If the user selects hosted execution, record that choice, read the project's delegation guidance, complete the handoff, and stop subsequent local phases. Do not initiate external delegation without that choice or require the user to choose again.
