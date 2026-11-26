#!/usr/bin/env python3
"""Cursor hooks: attribute per-turn token usage to the active SOP task.

Registered as a **project** hook (``<repo>/.cursor/hooks.json``) on three
events::

    beforeSubmitPrompt  → remember the user prompt for this generation
    afterAgentResponse  → record the running token counters
    stop                → record the closing token counters

How Cursor reports usage (verified against real hook traffic)
-------------------------------------------------------------
Cursor injects ``input_tokens`` / ``output_tokens`` / ``cache_read_tokens`` /
``cache_write_tokens`` into the ``afterAgentResponse`` and ``stop`` payloads.
They are **turn-cumulative**: every event inside a generation restates the
running total for that generation, and only the closing events of a generation
carry them at all (intermediate steps end in a tool call and report nothing).

``input_tokens`` already includes the cache counters, i.e.
``input = uncached + cache_read + cache_write``, and ``total = input + output``.

Consequences for this collector:
- Records are keyed by ``generation_id`` (one generation = one user message =
  one turn), so a turn is one row — never one row per LLM round-trip.
- Repeats are merged with an element-wise **maximum**, not a sum, so the final
  turn total wins and nothing is double counted.
- Turns that never report usage (aborted / no closing event) are dropped,
  matching the CodeBuddy collector's ``total_tokens == 0 → skip`` rule.
- Cursor has no ``credit`` concept; the column renders as ``—``.

Caveat: those token fields are **not** part of Cursor's documented hook schema
(docs list only ``{status, loop_count}`` for ``stop`` and ``{text}`` for
``afterAgentResponse``). They are stable in practice, so we read them when
present and degrade to a skipped turn when they are absent rather than failing.

Project hooks only run in a **trusted workspace**, and ``CURSOR_PROJECT_DIR``
is injected by Cursor, so attribution needs no configuration.
Must finish in <3s: ``install_deadline`` kills the process at 2.5s;
stdin is read with a deadline (the host may never close the pipe);
store/claim locks time out instead of blocking. Abort is safe — the
next hook event retries.

All failures are non-blocking and logged to /tmp/wally_debug/.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from time import time
from typing import Any

# Importing the shared module would otherwise drop a __pycache__/ directory into
# the repository's hooks/ folder on every single hook invocation.
sys.dont_write_bytecode = True

from _token_common import (  # noqa: E402
    CLIENT_CURSOR,
    as_int,
    find_repo,
    find_task_dir,
    git_branch,
    install_deadline,
    log,
    merge_cumulative_usage,
    normalize_usage,
    read_stdin_json,
    sync_task_store,
    token_work_disabled,
)

# Prompts are staged here between beforeSubmitPrompt and the usage-bearing
# event instead of inside .wally/, so the repository only ever gains token.json.
STAGE_DIR = Path("/tmp/wally_debug/cursor_prompts")

COLLECT_EVENTS = ("afterAgentResponse", "stop")
PROMPT_EVENTS = ("beforeSubmitPrompt",)


def read_payload() -> dict:
    return read_stdin_json()


def stage_path(generation_id: str) -> Path:
    # generation_id is an opaque UUID from Cursor; strip anything path-shaped.
    safe = "".join(ch for ch in generation_id if ch.isalnum() or ch in "-_")[:128]
    return STAGE_DIR / f"{safe}.json"


def stage_prompt(payload: dict, generation_id: str) -> None:
    try:
        STAGE_DIR.mkdir(parents=True, exist_ok=True)
        stage_path(generation_id).write_text(
            json.dumps(
                {
                    "prompt": str(payload.get("prompt") or "").strip(),
                    "model": resolve_model(payload),
                    "started_at": now_ms(),
                    "conversation_id": payload.get("conversation_id") or "",
                    "transcript_path": payload.get("transcript_path") or "",
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    except OSError as error:
        log(f"stage failed generation={generation_id}: {error}")


def read_stage(generation_id: str) -> dict:
    try:
        value = json.loads(stage_path(generation_id).read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def now_ms() -> int:
    return int(time() * 1000)


def resolve_model(payload: dict) -> str:
    """`model_id` is the resolved model; `model` is the legacy composer slug."""
    return str(payload.get("model_id") or payload.get("model") or "unknown")


def repo_candidates(payload: dict[str, Any]) -> list[Path]:
    """Workspace roots first: a multiroot window may nest the .wally repo."""
    candidates: list[Path] = []
    for key in ("CURSOR_PROJECT_DIR", "CLAUDE_PROJECT_DIR"):
        env = os.environ.get(key)
        if env:
            candidates.append(Path(env))
    for root in payload.get("workspace_roots") or []:
        if isinstance(root, str) and root:
            candidates.append(Path(root))
    cwd = payload.get("cwd")
    if isinstance(cwd, str) and cwd:
        candidates.append(Path(cwd))
    candidates.append(Path(os.getcwd()))
    return candidates


def resolve_repo(payload: dict[str, Any]) -> Path | None:
    seen = set()
    for candidate in repo_candidates(payload):
        try:
            key = str(candidate)
        except OSError:
            continue
        if key in seen:
            continue
        seen.add(key)
        repo = find_repo(candidate)
        if repo is not None:
            return repo
    return None


def cursor_usage(payload: dict) -> dict:
    """Cursor's counters, mapped onto the shared usage shape (no credit)."""
    return normalize_usage(
        {
            "input_tokens": payload.get("input_tokens"),
            "output_tokens": payload.get("output_tokens"),
            "cache_read_tokens": payload.get("cache_read_tokens"),
            "cache_write_tokens": payload.get("cache_write_tokens"),
            "credit": 0,
        }
    )


def build_record(payload: dict, branch: str, event: str) -> dict | None:
    generation_id = str(payload.get("generation_id") or "")
    if not generation_id:
        return None
    stage = read_stage(generation_id)
    usage = cursor_usage(payload)
    # A turn that never closed reports nothing; skip it like CodeBuddy does.
    if not usage["total_tokens"]:
        return None
    return {
        "request_id": generation_id,
        "session_id": str(payload.get("conversation_id") or ""),
        "branch": branch,
        "client": CLIENT_CURSOR,
        "source": "cursor_hook",
        "hook_event": event,
        "transcript_path": str(
            payload.get("transcript_path") or stage.get("transcript_path") or ""
        ),
        "started_at": as_int(stage.get("started_at")) or now_ms(),
        "prompt": str(stage.get("prompt") or ""),
        "model": str(stage.get("model") or resolve_model(payload)),
        "usage": usage,
    }


def main() -> None:
    payload = read_payload()
    event = str(payload.get("hook_event_name") or "")
    if event not in COLLECT_EVENTS + PROMPT_EVENTS:
        return

    generation_id = str(payload.get("generation_id") or "")
    if not generation_id:
        log(f"skip: missing generation_id event={event}")
        return

    repo = resolve_repo(payload)
    if repo is None:
        log(f"skip: no .wally in workspace_roots={payload.get('workspace_roots')}")
        return

    branch = git_branch(repo)
    if token_work_disabled(branch):
        log(f"skip: token collect disabled on branch={branch!r}")
        return

    if event in PROMPT_EVENTS:
        stage_prompt(payload, generation_id)
        return

    task_dir = find_task_dir(repo, branch)
    if task_dir is None:
        log(f"skip: no task for branch={branch!r}")
        return

    record = build_record(payload, branch, event)
    if record is None:
        log(f"skip: no usage in event={event} generation={generation_id[:8]}")
        return

    added, updated, total, skipped = sync_task_store(
        repo, task_dir, [record], usage_merger=merge_cumulative_usage
    )
    log(
        f"sync task={task_dir.name} event={event} generation={generation_id[:8]} "
        f"added={added} updated={updated} other-task={skipped} total={total}"
    )


if __name__ == "__main__":
    install_deadline()
    try:
        main()
    except Exception as error:
        log(f"fatal {type(error).__name__}: {error}")
    sys.exit(0)
