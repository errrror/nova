# Project Profile

- Extension: generic
- Extension Version: 2.0
- Workflow: {{STEPS}} steps
- Language/runtime/framework versions: follow the project's actual rules, not assumed latest versions
- Project Rules: {{RULE_PATHS}}
- Technical Docs: {{DOC_PATHS}}
- Branches and baseline: follow project Git conventions

## Quality gates

Bind actual UT, incremental coverage, lint/format, and IT commands from repository configuration and CI; do not invent them.
Default incremental line/branch thresholds: ordinary business 80%/70%, core logic 90%/80%, high-risk infrastructure 90%/85%; glue/adapter/simple CRUD lines 70%–80%, recording any relaxed branch threshold and rationale. Exclude generated/declarative code with evidence; no executable branches may be N/A. Stricter project rules remain effective.

## Execution adapters

- Clarify: Core guidance plus relevant project-domain constraints.
- Implement: follow project rules under `.wally/rules/`.
- Deploy: customer-owned deploy.command or deploy.guide in `.wally/config.json`; automatically skip when neither is set. Otherwise follow actual environment, authorization, effectiveness, and rollback instructions.
- IT: customer-owned it.command or it.guide and result criteria in `.wally/config.json`; automatically skip when neither is set. Once configured, missing tools/environment or failed execution is blocked/failed, never silently skipped or passed.
- Review: coding rules, version matrix, and `.wally/review.md`.
- Commit: {{COMMIT_PATH}}; Commit/Push each follow user authorization.
- External tracking/resource release/hosted delegation: configure for the project; no configuration means no automatic action.
- Token: {{CLIENTS}}; not enabled is not zero usage.

## Project customizations

Fill actual commands, gate sources, and specialist limits. Upgrades preserve this entire file. Compare and merge preset changes manually rather than overwriting project policy.


During initialization, populate this execution guidance from actual project files. Record sources, working directory, commands, prerequisites, result criteria and cleanup/rollback. In `.wally/config.json`, set optional `readiness: pending` and concrete `gaps` when required information is missing; ask the user and wait for the required information. Mark the phase BLOCKED, not automatically skipped; a guide path alone must not activate it. Set ready only after static verification. This is not evidence of execution. Existing configs without readiness retain legacy command/guide semantics.
