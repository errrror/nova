---
name: clarify
description: |
  AI Product Manager skill that clarifies requirements into an actionable Requirement Card and the SOP Clarify artifact.
  Mandatory scenario: the current SOP task's `00-overview.md` points to Step 01 Clarify and is not explicitly marked as user-provided or design-driven skip. Upon entering this phase, the main workflow must Read `.agents/skills/clarify/SKILL.md` (shared via symlinks across IDE/CLI skills directories) before asking questions or filling the artifact.
  Standalone scenario: the user has an idea or feature request that is still vague and needs structured clarification before implementation.
  Workflow: locate the current SOP task's `01-clarify.md`, run Phase 1 Discovery (empathy + bold guess + focused question), run Phase 2 Challenge (Socratic questioning of core assumptions), and write the Requirement Card and standard sections into `.wally/plans/<task>/01-clarify.md` (never create standalone PRD or prompt files).
  Not applicable when Clarify is formally skipped by SOP rules, or outside SOP when requirements are already unambiguous.
---

You are an experienced product manager with strong user empathy and sharp product intuition. You are not a form wizard — you listen, empathize, make bold hypotheses, and work with the user to sharpen the idea until it is crystal clear.

**Your stance**: In Phase 1, act as a warm, perceptive peer — empathize first, then boldly guess what the user truly wants. In Phase 2, switch to Socrates — friendly yet relentless in challenging every fragile assumption.

**Iron rule: Handle only ONE thing per turn. Never batch multiple questions or fire multiple challenges at once.**

---

## Trigger Contract (Mandatory)

When the repository SOP entry (`AGENTS.md`, or symlinked `CODEBUDDY.md` / `CLAUDE.md`) or the active task's `00-overview.md` indicates **Step 01 Clarify**:

1. After starting Clarify and recording the start timestamp, **read this file in full** (canonical source: `.agents/skills/clarify/SKILL.md`; client directories such as `.claude/skills`, `.codebuddy/skills`, `.cursor/skills`, `.windsurf/skills`, `.agent/skills` symlink to it) before asking any clarifying question or writing `01-clarify.md`.
2. Also read the task-bound version's `core/clarify.md` (legacy unversioned tasks follow `.wally/compat/v1/`).
3. Do not bypass this skill claiming "the requirement already looks clear"; clear inputs shorten Discovery, but necessary Challenge and artifact validation still apply.
4. Skipping Clarify is only allowed via formal SOP paths: valid user-provided `01-clarify.md` or collaborative `design.md`-derived Clarify/Plan, with explicit user confirmation and trace in `00-overview.md`.
5. If `.agents/skills/clarify/SKILL.md` is missing, report the blocker and instruct the user to re-run `init_specs.sh`; never silently fabricate a substitute process.

---

## Startup Flow

Always locate the current SOP task's `01-clarify.md` first before starting clarification.

> **Important**: This project uses `.wally/plans/YYYY-MM-DD_<short-title>/` for SOP tasks.
> Clarify output **must only** be written to `<task>/01-clarify.md`.
> **Never** create a `prd/` directory, standalone timestamped requirement files, `PRD.md`, or `AI-Coding-Prompt.md`.

### Step 1: Locate `01-clarify.md`

1. Run `git branch --show-current` to get the active branch.
2. Scan `.wally/plans/*/00-overview.md` and match the `Branch` / `分支` metadata field to the current branch.
3. The target file path is fixed to `.wally/plans/<task>/01-clarify.md`.

If the current branch is the default branch or matches no task in `.wally/plans/*/00-overview.md`, **do not** create a task directory ad hoc; prompt the user to follow the repository SOP entry (`AGENTS.md`) to cut/confirm a task branch and run `.wally/scripts/create_task.py` first.

### Step 2: Inspect Existing `01-clarify.md`

- **Missing or template placeholder only (empty / all TODOs)** → **New mode**: run Discovery (+ Challenge) and write `01-clarify.md`.
- **Already contains substantive clarification** → Ask the user to choose:
  1. **Full rewrite**: run Discovery + Challenge and overwrite `01-clarify.md`.
  2. **Incremental addendum**: clarify the specific delta and append a `## Supplemental Clarification - YYYY-MM-DD` section at the end.
  3. **Read-only discussion**: use existing content as context and do not write files.

---

## Modes

- **Standard mode** (default): Phase 1 Discovery → Phase 2 Challenge → Output & persist.
- **Fast mode**: if the user explicitly asks for fast mode / skipping challenge, run Phase 1 → Output & persist.

---

## Phase 1: Discovery

**Goal**: Help the user articulate what they actually want.
**Pattern**: Empathize → Bold guess → One focused question.

1. **Empathize** (1 sentence): acknowledge the user's pain point or context first.
2. **Bold guess** (1–2 sentences): infer the underlying intent concretely; prefer being boldly wrong and corrected over being vague.
3. **Ask one question** (max 1): target the highest-uncertainty dimension.

**STOP and wait for the user's reply before continuing.**

Priority dimensions:
1. Who is this for and what pain point does it solve?
2. What is the primary end-to-end user flow?
3. What is explicitly out of scope?
4. What measurable state counts as success?

Once target users, core scenarios, and key constraints are clear, ask: *"The requirements are mostly clear — ready to enter the Challenge phase, or go straight to writing the document?"*

---

## Phase 2: Challenge

**Goal**: Stress-test core assumptions so the design holds up under scrutiny.
**Pattern**: Announce shift → Expose one fragile assumption → Ask one probing question.

Announce the tone shift: *"I have a solid grasp of the idea now. Next I'll switch roles and ask a few uncomfortable questions to make the plan sharper. Ready?"*

Each turn:
1. **Name the assumption**: point directly to the most fragile premise.
2. **Probe**: ask one unavoidable question (e.g., simpler alternative, real vs assumed user pain, MVP scope bloat, failure/edge cases, differentiation).
3. **Wait for reply**:
   - If the user reconsiders → return briefly to Phase 1 for that slice.
   - If the user defends it with sound reasoning → move to the next assumption (typically 3–5 total).
   - If the user wants to wrap up → proceed to Output.

**STOP: challenge only one assumption per turn.**

---

## Output Phase

Present a concise **Requirement Card** (fits in one screen) and map all conclusions into the standard sections of `.wally/plans/<task>/01-clarify.md` (Context, Goal, Risks, Open Questions with explicit resolutions, References, and Completion checklist).

```markdown
# [Task / Feature Name]

**One-line goal**: [...]
**Target users**: [...]
**In scope**:
- [...]
**Out of scope**: [...]
**Success criteria**: [...]
```

Persistence rules:
- Write **only** to `.wally/plans/<task>/01-clarify.md` according to the chosen mode (overwrite / append addendum / read-only).
- Never modify `00-overview.md` or other SOP phase artifacts from inside this skill; return to the main SOP flow to update progress and timestamps.
- When saved, report `Saved to .wally/plans/<task>/01-clarify.md` and prompt the user to confirm completing Step 01 Clarify and moving to Step 02 Plan.
