# Unit testing specification

> Source: actual test directories, build/package configuration, CI, project rules, and runtime versions. Fill concrete commands and paths; a generic template is not a verified test strategy.

## Versions and execution

Supported language/interpreter/framework versions, dependency installation, configuration/fixtures, test discovery, focused test commands, full regression commands, and CI entrypoints. Document expected success output and failure diagnostics. Secrets come from environment/vault/ignored local configuration.

Use project-approved software sources for dependencies. During SOP initialization, check setup and test commands against repository configuration and CI definitions. Run them during authorized environment setup or testing.

## Test layers and boundaries

- Function UT isolates dependencies and verifies public observable behavior.
- Scenario UT exercises real project calls, mocking external DB/MQ/RPC/HTTP boundaries only.
- IT uses actual integration boundaries and separate directories/data; scenario UT cannot be claimed as completed environment validation.

## Case design

Link requirements and Plan IDs. Cover positive/negative/boundary/error/recovery paths, empty/single/oversize/negative inputs, authentication, Unicode/JSON, timeouts/retries/fallback, idempotent writes, concurrency, transactions, and terminal side effects where applicable.
For failure-triggered side effects test final failure triggers once, intermediate failure followed by success does not trigger, and each terminal exit. Keep tests deterministic, isolated, and repeatable with realistic fixtures and cleanup.

## TDD evidence

Write a defect-revealing test before implementation; Red must fail its intended assertion rather than environment/syntax. Record the same test's Green and post-refactor result, commands, versions, and output. Explain justified non-executable-code exclusions or unnecessary refactoring.

## Coverage

Measure incremental lines/branches on changed production code, not whole-project coverage. Bind actual commands, reports, code classifications, and exclusions. Default thresholds: ordinary business 80%/70%, core 90%/80%, high-risk infrastructure 90%/85%; glue/adapter/simple CRUD lines 70%–80%, with actual relaxed branch threshold/rationale recorded. Stricter project rules apply. Exclude generated/declarative code with evidence; no executable branches may be N/A. Missing reports remain unverified.

## Mocks and fixtures

State boundary, rationale, expected interactions, input/output shapes, failure behavior, and cleanup. Avoid mocking the behavior under test or assertions mirroring implementation. Document fixture provenance, required seed data, runtime configuration, and isolation of parallel runs.

## Regression and review

Retain stable defect cases, link before/after evidence, check affected call chains and compatibility, and revalidate after changes. Record passes/failures/blocked/skipped honestly. Maintain this specification when commands, dependencies, fixtures, or policy change, linking implementation/CI evidence and version checked.
