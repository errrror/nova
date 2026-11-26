# 03. Implement + UT + Docs

## Project rules

Before coding, read every rule file under `.wally/rules/` and follow them in code, tests, and documentation updates. Record the paths actually read, how each constraint applied to this change, and any conflict with Core. If the directory is missing or contains only the directory note, record that there are no extra project rules.

## Actual changes and Plan deviations

## Red → Green → Refactor

Link each Plan case group to commands, versions, expected failure causes, key output, and passing counts. Justify omitted refactoring and non-executable-code exclusions.

## UT and incremental coverage

Record code classification, line/branch thresholds, measured incremental results, report evidence, uncovered code, and regression results.

## Defect regression (when applicable)

Actual defect assertions, before/after evidence, lowest-layer regression, and remaining environment verification.

## Docs

Affected authoritative documents, changes, and evidence for documents requiring no update.

## Incremental CR

Read project rules, including `.wally/rules/`, and language versions; record reviewed diff, findings, fixes, rechecks, and unresolved risks.

## Completion conclusion

Passed/failed/unverified/inapplicable TDD, coverage, Docs, and CR with evidence. Failing applicable gates block Deploy.

## Knowledge evidence

Follow the task-bound `core/knowledge.md` responsibilities for this phase. Record relevant paths actually read, source checks, gaps, affected documents and updates/no-update rationale, and validation results. Final Review checks the complete task diff.
