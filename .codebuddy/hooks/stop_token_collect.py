#!/usr/bin/env python3
"""CodeBuddy Stop hook: incrementally sync completed request usage.

The Stop event often fires before the current request's ``usage`` is flushed.
CodeBuddy reports a *final per-request* usage, so repeats simply replace.
This hook therefore never waits for one request. On every Stop it scans every
usage-bearing request in the current transcript and idempotently merges unseen
requests into the active task's ``.wally/plans/<task>/token.json``. A request
missed now is recovered by a later Stop event.

A single chat window may drive one SOP task after another, and the transcript
does not restart when the task does, so this full rescan would otherwise replay
the earlier task's requests into the later task's store. ``sync_task_store``
drops requests another task already owns.

The hook only collects structured data. It never edits an SOP overview.
``token_report.py`` renders the final prompt/token/credit report at Commit.
Must finish in <3s: ``install_deadline`` kills the process at 2.5s;
stdin is read with a deadline (the host may never close the pipe);
store/claim locks time out instead of blocking. Abort is safe — the
next Stop retries.

All failures are non-blocking and logged to /tmp/wally_debug/.

Cursor sessions write to the *same* ``token.json`` through
``cursor_token_collect.py``; the shared store format, merge rules and lock live
in ``_token_common.py``.
"""
from __future__ import annotations

from collections.abc import Iterable
import json
import os
from pathlib import Path
import re
import sys
from typing import Any

# Importing the shared module would otherwise drop a __pycache__/ directory into
# the repository's hooks/ folder on every single hook invocation.
sys.dont_write_bytecode = True

from _token_common import (  # noqa: E402
    CLIENT_CODEBUDDY,
    as_float,
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

IDE_DATA_ROOTS = (
    "Library/Application Support/CodeBuddyExtension/Data",  # macOS
    ".config/CodeBuddyExtension/Data",  # Linux
    "AppData/Roaming/CodeBuddyExtension/Data",  # Windows
)


def read_payload() -> dict:
    return read_stdin_json()


def trusted_roots() -> list[Path]:
    """Directories that host genuine CodeBuddy sessions.

    Anything outside these (e.g. Bugbot's ``~/.bugbot/codebuddy-config-dir``
    or any other CODEBUDDY_CONFIG_DIR override) is treated as interference.
    """
    home = Path.home()
    roots = [home / ".codebuddy" / "projects"]
    for relative in IDE_DATA_ROOTS:
        roots.append(home / relative)
    env = os.environ.get("CODEBUDDY_EXTENSION_DATA")
    if env:
        roots.append(Path(env))
    return roots


def is_trusted_transcript(path: Path) -> bool:
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    parts = set(resolved.parts)
    # Reject Bugbot / sandboxed config-dir couriers outright.
    if ".bugbot" in parts or "codebuddy-config-dir" in parts:
        return False
    for root in trusted_roots():
        try:
            resolved.relative_to(root.resolve())
            return True
        except (ValueError, OSError):
            continue
    return False


def resolve_transcript(payload: dict) -> Path | None:
    supplied = str(payload.get("transcript_path") or "")
    if supplied:
        path = Path(supplied)
        candidate: Path | None = None
        if path.is_file():
            candidate = path
        elif path.is_dir() and (path / "index.json").is_file():
            candidate = path / "index.json"
        if candidate is not None:
            if is_trusted_transcript(candidate):
                return candidate
            # Bugbot or another config-dir override: ignore and fall back to
            # locating the real IDE session by session_id below.
            log(f"ignore untrusted transcript_path={candidate}")

    session_id = str(payload.get("session_id") or "")
    if not session_id:
        return None

    left = remaining_sec()
    if left is not None and left < 0.3:
        log(f"skip transcript glob: budget left={left:.3f}s")
        return None

    candidates: list[Path] = []
    cli_root = Path.home() / ".codebuddy" / "projects"
    if cli_root.is_dir():
        candidates.extend(cli_root.glob(f"*/{session_id}.jsonl"))

    for relative in IDE_DATA_ROOTS:
        root = Path.home() / relative
        if not root.is_dir():
            continue
        candidates.extend(root.glob(f"*/CodeBuddyIDE/*/history/*/{session_id}/index.json"))
        candidates.extend(root.glob(f"*/CodeBuddyIDE/*/history/{session_id}/index.json"))

    candidates = [c for c in candidates if is_trusted_transcript(c)]
    if not candidates:
        return None

    # Prefer genuine IDE history index.json over CLI jsonl when both exist for
    # the same session_id — IDE is where CodeBuddy UI token/credit live.
    ide_hits = [c for c in candidates if c.name == "index.json" and "history" in c.parts]
    pool = ide_hits or candidates
    pool.sort(
        key=lambda path: path.stat().st_mtime if path.exists() else 0, reverse=True
    )
    return pool[0]


def content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if not isinstance(item, dict):
            continue
        if item.get("type") in ("text", "input_text") and item.get("text"):
            parts.append(str(item["text"]))
    return "\n".join(parts)


def clean_prompt(text: str) -> str:
    """Prefer the explicit user_query over injected rules/tool hints."""
    if not text:
        return ""
    match = re.search(r"<user_query>\s*(.*?)\s*</user_query>", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # CLI prompts may contain system-reminder blocks before the real text.
    cleaned = re.sub(
        r"<system-reminder\b.*?</system-reminder>", "", text, flags=re.DOTALL
    ).strip()
    return cleaned or text.strip()


_IDE_MSG_CACHE: dict[str, dict] = {}


def read_ide_message(session_dir: Path, message_id: str) -> dict:
    key = f"{session_dir}:{message_id}"
    cached = _IDE_MSG_CACHE.get(key)
    if cached is not None:
        return cached
    path = session_dir / "messages" / f"{message_id}.json"
    try:
        value = json.loads(path.read_text(encoding="utf-8", errors="replace"))
        parsed = value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        parsed = {}
    _IDE_MSG_CACHE[key] = parsed
    return parsed


def ide_message_body(message: dict) -> dict:
    raw = message.get("message")
    if isinstance(raw, str):
        try:
            value = json.loads(raw)
            return value if isinstance(value, dict) else {}
        except ValueError:
            return {}
    return raw if isinstance(raw, dict) else {}


def ide_model(session_dir: Path, refs: Iterable[str], metadata: dict[str, dict]) -> str:
    for message_id in reversed(list(refs)):
        if metadata.get(message_id, {}).get("role") != "assistant":
            continue
        message = read_ide_message(session_dir, message_id)
        try:
            extra = json.loads(message.get("extra") or "{}")
        except ValueError:
            extra = {}
        if isinstance(extra, dict):
            model = extra.get("modelName") or extra.get("modelId")
            if model:
                return str(model)
    return "unknown"


def ide_prompt(session_dir: Path, refs: Iterable[str], metadata: dict[str, dict]) -> str:
    for message_id in reversed(list(refs)):
        if metadata.get(message_id, {}).get("role") != "user":
            continue
        message = read_ide_message(session_dir, message_id)
        return clean_prompt(content_text(ide_message_body(message).get("content")))
    return ""


def scan_ide(path: Path, session_id: str, branch: str) -> list[dict]:
    try:
        index = json.loads(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, ValueError):
        return []
    if not isinstance(index, dict):
        return []

    metadata = {
        item["id"]: item
        for item in index.get("messages", [])
        if isinstance(item, dict) and item.get("id")
    }
    records: list[dict] = []
    for request in index.get("requests", []):
        if not isinstance(request, dict) or not request.get("id"):
            continue
        raw_usage = request.get("usage")
        if not isinstance(raw_usage, dict) or not raw_usage:
            continue
        left = remaining_sec()
        if left is not None and left < 0.2:
            log(f"scan_ide: stop early, budget left={left:.3f}s scanned={len(records)}")
            break
        usage = normalize_usage(raw_usage)
        if not usage["total_tokens"]:
            continue
        refs = request.get("messages") or []
        records.append(
            {
                "request_id": str(request["id"]),
                "session_id": session_id,
                "branch": branch,
                "client": CLIENT_CODEBUDDY,
                "source": "ide_index",
                "transcript_path": str(path),
                "started_at": request.get("startedAt"),
                "prompt": ide_prompt(path.parent, refs, metadata),
                "model": ide_model(path.parent, refs, metadata),
                "usage": usage,
            }
        )
    return records


def cli_usage(message: dict) -> dict:
    provider = message.get("providerData")
    raw_usage = provider.get("rawUsage") if isinstance(provider, dict) else {}
    for parent, key in (
        ("providerData", "usage"),
        ("providerData", "rawUsage"),
        ("message", "usage"),
    ):
        container = message.get(parent)
        if isinstance(container, dict) and isinstance(container.get(key), dict):
            usage = normalize_usage(container[key])
            if usage["total_tokens"]:
                if not usage["credit"] and isinstance(raw_usage, dict):
                    usage["credit"] = as_float(raw_usage.get("credit"))
                return usage
    return {}


def cli_user_message(by_id: dict[str, dict], assistant: dict) -> dict:
    """Find the user turn behind an assistant reply.

    The chain is not always ``user -> assistant``: after the first turn the CLI
    inserts role-less bookkeeping records, so walk up ``parentId`` until a user
    message appears instead of reading the immediate parent.
    """
    seen: set[str] = set()
    node = by_id.get(str(assistant.get("parentId") or ""))
    while isinstance(node, dict):
        node_id = str(node.get("id") or "")
        if node_id in seen:
            break
        seen.add(node_id)
        if node.get("role") == "user":
            return node
        node = by_id.get(str(node.get("parentId") or ""))
    return {}


def scan_cli(path: Path, session_id: str, branch: str) -> list[dict]:
    messages: list[dict] = []
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                value = json.loads(line)
            except ValueError:
                continue
            if isinstance(value, dict):
                messages.append(value)
    except OSError:
        return []

    by_id = {
        message["id"]: message
        for message in messages
        if isinstance(message, dict) and message.get("id")
    }
    records: list[dict] = []
    for assistant in messages:
        if assistant.get("role") != "assistant" or not assistant.get("id"):
            continue
        usage = cli_usage(assistant)
        if not usage:
            continue
        left = remaining_sec()
        if left is not None and left < 0.2:
            log(f"scan_cli: stop early, budget left={left:.3f}s scanned={len(records)}")
            break
        user = cli_user_message(by_id, assistant)
        provider = assistant.get("providerData") or {}
        model = (
            provider.get("requestModelName")
            or provider.get("requestModelId")
            or provider.get("model")
            or "unknown"
        )
        records.append(
            {
                "request_id": str(assistant["id"]),
                "session_id": session_id or str(assistant.get("sessionId") or ""),
                "branch": branch,
                "client": CLIENT_CODEBUDDY,
                "source": "cli_jsonl",
                "transcript_path": str(path),
                "started_at": assistant.get("timestamp"),
                "prompt": clean_prompt(content_text(user.get("content"))),
                "model": str(model),
                "usage": usage,
            }
        )
    return records


def main() -> None:
    payload = read_payload()
    cwd = Path(
        payload.get("cwd")
        or os.environ.get("CODEBUDDY_PROJECT_DIR")
        or os.environ.get("CLAUDE_PROJECT_DIR")
        or os.getcwd()
    )
    repo = find_repo(cwd)
    if repo is None:
        log(f"skip: no .wally near cwd={cwd}")
        return

    branch = git_branch(repo)
    if token_work_disabled(branch):
        log(f"skip: token collect disabled on branch={branch!r}")
        return
    task_dir = find_task_dir(repo, branch)
    if task_dir is None:
        log(f"skip: no task for branch={branch!r}")
        return

    transcript = resolve_transcript(payload)
    if transcript is None:
        log("skip: transcript not found session={}".format(payload.get("session_id")))
        return

    session_id = str(payload.get("session_id") or transcript.parent.name)
    if transcript.name.endswith(".jsonl"):
        incoming = scan_cli(transcript, session_id, branch)
    else:
        incoming = scan_ide(transcript, session_id, branch)

    added, updated, total, skipped = sync_task_store(repo, task_dir, incoming)
    pending = 0
    if not transcript.name.endswith(".jsonl"):
        try:
            index = json.loads(transcript.read_text(encoding="utf-8"))
            pending = sum(
                1
                for request in index.get("requests", [])
                if isinstance(request, dict) and not request.get("usage")
            )
        except (OSError, ValueError):
            pass
    log(
        f"sync task={task_dir.name} source={transcript} scanned={len(incoming)} "
        f"added={added} updated={updated} other-task={skipped} "
        f"total={total} pending={pending}"
    )


if __name__ == "__main__":
    install_deadline()
    try:
        main()
    except Exception as error:
        log(f"fatal {type(error).__name__}: {error}")
    sys.exit(0)
