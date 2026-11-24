#!/usr/bin/env python3
"""Claude Code Stop hook: incrementally sync completed request usage.

Claude Code invokes Stop hooks with a JSON payload on stdin containing
``session_id``, ``transcript_path``, and ``cwd``. Each assistant entry in the
JSONL transcript carries ``message.usage`` (``input_tokens``,
``cache_read_input_tokens``, ``cache_creation_input_tokens``,
``output_tokens``) and a request identifier (``requestId`` or ``message.id``).

All failures are non-blocking and logged to ``/tmp/wally_debug/``.
"""
from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import sys
from typing import Any

sys.dont_write_bytecode = True

from _token_common import (  # noqa: E402
    CLIENT_CLAUDE,
    find_repo,
    find_task_dir,
    git_branch,
    install_deadline,
    log,
    normalize_usage,
    read_stdin_json,
    remaining_sec,
    sync_task_store,
    token_work_disabled,
)


def trusted_roots() -> list[Path]:
    """Directories that host genuine Claude Code session transcripts."""
    home = Path.home()
    roots = [home / ".claude" / "projects"]
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        roots.append(Path(env) / "projects")
    return roots


def is_trusted_transcript(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    for root in trusted_roots():
        try:
            resolved.relative_to(root.resolve())
            return True
        except (OSError, ValueError):
            continue
    return False


def _extract_text(content: Any) -> str:
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text = str(item.get("text") or "").strip()
                if text:
                    parts.append(text)
            elif isinstance(item, str) and item.strip():
                parts.append(item.strip())
        return " ".join(parts).strip()
    return ""


def _parse_timestamp_ms(raw: Any) -> int:
    if isinstance(raw, (int, float)):
        val = int(raw)
        return val if val > 10**12 else val * 1000
    if isinstance(raw, str) and raw.strip():
        text = raw.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return int(datetime.fromisoformat(text).timestamp() * 1000)
        except ValueError:
            return 0
    return 0


def parse_transcript(path: Path, session_id: str, branch: str) -> list[dict[str, Any]]:
    """Extract per-request usage records from a Claude Code JSONL transcript."""
    if not path.is_file():
        return []
    records_by_id: dict[str, dict[str, Any]] = {}
    last_prompt = ""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        log(f"claude_token_collect: failed reading transcript {path}: {exc}")
        return []

    for idx, line in enumerate(lines):
        if remaining_sec() < 0.25:
            break
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if not isinstance(entry, dict):
            continue

        entry_type = str(entry.get("type") or "").strip()
        message = entry.get("message") if isinstance(entry.get("message"), dict) else {}
        role = str(message.get("role") or entry_type).strip()

        if role == "user" and not entry.get("isMeta"):
            text = _extract_text(message.get("content") if message else entry.get("content"))
            if text:
                last_prompt = text[:500]
            continue

        usage = message.get("usage") if isinstance(message.get("usage"), dict) else None
        if not usage:
            continue

        req_id = str(
            entry.get("requestId")
            or message.get("id")
            or entry.get("uuid")
            or f"claude-{session_id or path.stem}-{idx}"
        ).strip()
        if not req_id:
            continue

        # Anthropic API reports non-cached input separately from cache_read/cache_creation.
        norm = normalize_usage({
            "uncached_input_tokens": usage.get("input_tokens"),
            "cache_read_input_tokens": usage.get("cache_read_input_tokens"),
            "cache_creation_input_tokens": usage.get("cache_creation_input_tokens"),
            "output_tokens": usage.get("output_tokens"),
        })
        if norm.get("total_tokens", 0) <= 0:
            continue

        records_by_id[req_id] = {
            "request_id": req_id,
            "session_id": str(entry.get("sessionId") or session_id or path.stem),
            "branch": branch,
            "client": CLIENT_CLAUDE,
            "source": "claude_stop",
            "transcript_path": str(path),
            "started_at": _parse_timestamp_ms(entry.get("timestamp")),
            "prompt": last_prompt,
            "model": str(message.get("model") or "unknown"),
            "usage": norm,
        }
    return list(records_by_id.values())


def main() -> int:
    install_deadline(2.5)
    payload = read_stdin_json()
    if not isinstance(payload, dict):
        return 0

    raw_transcript = str(payload.get("transcript_path") or "").strip()
    if not raw_transcript:
        return 0
    transcript = Path(raw_transcript).expanduser()
    if not is_trusted_transcript(transcript):
        return 0

    cwd = Path(str(payload.get("cwd") or os.getcwd())).expanduser()
    repo = find_repo(cwd)
    if repo is None:
        return 0
    branch = git_branch(repo)
    if not branch or token_work_disabled(branch):
        return 0
    task_dir = find_task_dir(repo, branch)
    if task_dir is None:
        return 0

    session_id = str(payload.get("session_id") or transcript.stem)
    records = parse_transcript(transcript, session_id, branch)
    if records:
        sync_task_store(repo, task_dir, records)
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:  # noqa: BLE001
        log(f"claude_token_collect: unhandled error: {exc}")
        sys.exit(0)
