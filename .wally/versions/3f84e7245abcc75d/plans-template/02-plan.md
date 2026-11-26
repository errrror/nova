# 02. Plan

## Design and change scope

Link requirement criteria, files/modules, dependencies, risk classification, and rationale.

## Call chains and compatibility

Record affected state machines, fallback/retry, terminal exits, side-effect timing, protocol/data changes, and rollback.

## UT design

Case IDs, initial states, assertions, and test locations; cover positive/negative/boundary/error cases and applicable Unicode inputs. Design lowest-layer Red/Green for bugs/performance.

## IT design (six-step workflow)

Case IDs, environment, prerequisite data, assertions, commands, and result criteria. Load relevant project extensions; design executable entrypoints for unsupported runner scenarios.
A/B: baseline version/evidence, equivalent conditions, post-fix verification, and multi-run performance statistics.

## Risks and completion conclusion

Decisions, uncovered boundaries, authorization needs, and fallback. Applicable tests are designed before implementation.

## Knowledge evidence

Follow the task-bound `core/knowledge.md` responsibilities for this phase. Record relevant paths actually read, source checks, gaps, affected documents and updates/no-update rationale, and validation results. Final Review checks the complete task diff.
