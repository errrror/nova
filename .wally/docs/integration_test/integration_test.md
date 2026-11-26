# Integration testing

Record the project's actual runner, environment, authentication/configuration, data preparation/isolation, assertions, result criteria, cleanup, and evidence locations.

For six-step tasks design cases in Plan, execute after deployment, and record individual results plus aggregate gates in the task's IT artifact. Distinguish assertion, environment, and execution errors; empty/all-skipped runs are not passes. For defect/performance A/B retain comparable before/after evidence and limits.

Use the project's applicable profile extension for specialist runners. Do not invent commands, access, or successful results. Keep all six phases. If it.command and it.guide in the task execution.json are unset, automatically skip IT and disclose missing validation. Once configured, unavailable environments or failed execution block; never claim end-to-end verification.


During initialization, populate this execution guidance from actual project files. Record sources, working directory, commands, prerequisites, result criteria and cleanup/rollback. In `.wally/config.json`, set optional `readiness: pending` and concrete `gaps` when required information is missing; ask the user and wait for the required information. Mark the phase BLOCKED, not automatically skipped; a guide path alone must not activate it. Set ready only after static verification. This is not evidence of execution. Existing configs without readiness retain legacy command/guide semantics.
