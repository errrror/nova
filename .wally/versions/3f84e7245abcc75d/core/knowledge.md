# Knowledge reading, incremental writing, and verification

Load this policy from the task-bound SOP version; read knowledge from the current working tree. Paths are repository-relative; metadata document paths are relative to `.wally/docs/`.

## Entry and authoritative sources

Read `.wally/docs/INDEX.md`, route by task intent and source path, then read relevant pages and verify against source. `fileToDocs` in `.wally/docs/.wiki-meta.json` is an impact hint, not proof of completeness. For missing indexes/metadata, incomplete mappings, or stale pages, inspect actual Profile documentation paths and source and record gaps. A skeleton, existing file, or loaded index does not prove its content was read.

- Architecture: `.wally/docs/overview/system-architecture.md` and `architecture/`; business: `business/`; dependencies: `integrations/index.md` and its children.
- Contracts: `contracts/`; operational knowledge: `operations/`. Maintain these through `wally-codewiki` Mode B.
- Keep existing authoritative API/SQL documents at their actual paths. SOP execution specifications live in `.wally/docs/apis/`, `sqls/`, `unittest/`, `integration_test/`, `devops/`, or existing paths explicitly bound by the Profile. Codewiki links to these authorities for shared facts instead of maintaining duplicate content.
- Do not create legacy `.wally/docs/architecture.md`, `relationship/`, or a `README.md` master index. Treat existing legacy paths as migration clues; route to confirmed authoritative pages from INDEX and preserve customization.

## Phase responsibilities

1. Clarify / Plan: read relevant business, architecture, contracts, dependencies, and test specifications. Record actual paths read, relevant conclusions, source checks, and gaps in phase artifacts. List expected affected knowledge pages in Plan.
2. Implement: recompute affected pages from the actual task diff using `fileToDocs` plus callers, downstream dependencies, configuration, tests, and added/deleted/renamed files. Update content, source anchors, related pages, INDEX, and metadata. Use `wally-codewiki` Mode B for knowledge pages and update SOP specifications at their existing authoritative paths. Task notes or changelog entries alone are insufficient. Record “source change → document path → update/no-update rationale → verification result”.
3. Deploy / IT: read Profile-bound deployment and unit/integration test specifications and relevant `operations/` and `integrations/` pages. Write new environment/runtime facts back to the same authorities. Reassess Docs after subsequent code changes.
4. Review / Commit: compare the final task diff with this mapping; verify paths, links, source anchors, INDEX/metadata consistency, and final behavior. Recheck fixes. Explicitly report missing, stale, or unverified documentation; do not mark Docs passed.

## Incremental scope and completion

Check both task changes and the wiki baseline scope and take their union; default `git diff` is insufficient. Include baseline-to-HEAD commits, staged and unstaged changes, and non-ignored untracked source files; inspect both old and new paths for deletions/renames. Do not ingest untracked sensitive files. Missing baselines/mappings require broader source inspection, not a no-update conclusion.

Preserve `origin: human` or `status: verified` pages; report drift and proposed revisions without automatic overwrite. Unresolved drift remains failed/unverified. Update metadata only after its scope passes verification. For uncommitted work, retain the committed baseline and record the actual inspected scope; HEAD does not represent uncommitted content. Partial updates must not advance the whole-wiki baseline. State any required bootstrap scope when knowledge is absent; never fabricate a pass.
