# 06. Review + Commit

## Final Review

Final diff, changed evidence recheck, findings/fixes, Plan deviations, defect closure, and unresolved risks.

## Time-log audit

Check each phase's start/end, duration, rounds, and artifacts. Recover times only from real conversation evidence. Blank/missed/unsupported retrospective records fail: return to and redo the missing phase, record actual times, and do not enter Commit.

## External systems and resources

Actual authorized handling/results, or evidence of inapplicability. Never report unexecuted actions as successful.

## Commit preparation

- Message and explicitly staged files:
- Token report: before committing, roll up this task's `token.json` into `00-overview.md` (run `python3 .codebuddy/scripts/token_report.py`, `.claude/scripts/token_report.py`, or `.codex/scripts/token_report.py` and verify the `<!-- TOKEN_USAGE_START -->` section is updated; never commit raw `token.json`); state not enabled/partial honestly.
- Overview updates and applicable gate conclusions:
- Commit/Push authorization and stop boundaries:

## Execution results

Actual Commit/Push results and failure reasons. Preparation alone is recorded as not executed, not submitted.

## Knowledge evidence

Follow the task-bound `core/knowledge.md` responsibilities for this phase. Record relevant paths actually read, source checks, gaps, affected documents and updates/no-update rationale, and validation results. Final Review checks the complete task diff.
