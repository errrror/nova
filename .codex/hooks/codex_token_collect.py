#!/usr/bin/env python3
"""Collect Codex per-response usage into an explicitly bound SOP task.

Only token_usage_record is an accounting source. token_count is diagnostic:
its cumulative totals must never be added to per-response usage. Runtime
indexes/cursors live outside the repository; token.json remains the task ledger.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True
from _token_common import (  # noqa: E402
    CLIENT_CODEX,
    file_lock,
    find_repo,
    find_task_dir,
    git_branch,
    install_deadline,
    log,
    read_stdin_json,
    remaining_sec,
    sync_task_store,
    token_work_disabled,
    write_json,
)

EVENTS = ("UserPromptSubmit", "SubagentStart", "Stop", "SubagentStop", "Interrupt", "SessionEnd")


def state_dir() -> Path:
    """Resolve the Codex runtime state directory, honoring the env override."""
    return Path(os.environ.get("WALLY_CODEX_STATE_DIR") or
                Path.home() / ".wally/wally-init/codex")


def state_path(session_id: str) -> Path:
    """Build the per-session state file path inside the state directory."""
    return state_dir() / (hashlib.sha256(session_id.encode()).hexdigest() + ".json")


def read_json(path: Path) -> dict:
    """Read a JSON object from `path`, returning `{}` on any read/parse failure."""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def load_state(path: Path) -> dict:
    """Load and validate the Codex runtime state file, raising on corruption."""
    value = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(value, dict) or not value.get("session_id") or
            not isinstance(value.get("bindings"), dict) or
            not isinstance(value.get("threads"), dict)):
        raise ValueError("invalid Codex runtime state")
    return value


def registered_session(thread_id: str) -> str:
    """Resolve a known parent even before its transcript has been flushed."""
    for path in state_dir().glob("*.json"):
        if remaining_sec() is not None and remaining_sec() < 0.6:
            break
        state = read_json(path)
        if thread_id in state.get("threads", {}):
            return str(state.get("session_id") or thread_id)
    return thread_id


def timestamp_ms(value) -> int:
    """Convert an ISO timestamp to epoch milliseconds, defaulting to 0 on failure."""
    try:
        return int(datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp() * 1000)
    except (ValueError, TypeError, OverflowError):
        return 0


def text_content(content) -> str:
    """Extract plain text from a Codex message's string or structured content."""
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(str(x.get("text") or "") for x in content
                         if isinstance(x, dict) and x.get("type") in ("text", "input_text")).strip()
    return ""


def read_meta(path: Path) -> dict:
    """First metadata is authoritative; forks can contain older parent metadata."""
    try:
        with path.open("rb") as stream:
            line = stream.readline()
        row = json.loads(line)
        meta = row.get("payload")
        if row.get("type") == "session_meta" and isinstance(meta, dict) and meta.get("id"):
            return meta
    except (OSError, ValueError, AttributeError):
        pass
    return {}


def identity(meta: dict) -> dict:
    """Derive the thread/session/parent identity fields from session metadata."""
    source = meta.get("source")
    sub = source.get("subagent", {}) if isinstance(source, dict) else {}
    spawn = sub.get("thread_spawn", {}) if isinstance(sub, dict) else {}
    return {
        "thread_id": str(meta.get("id") or ""),
        "session_id": str(meta.get("session_id") or meta.get("id") or ""),
        "parent_thread_id": str(meta.get("parent_thread_id") or spawn.get("parent_thread_id") or ""),
        "agent_path": str(meta.get("agent_path") or spawn.get("agent_path") or ""),
        "agent_type": "guardian" if sub.get("other") == "guardian" else "",
        "history_start": meta.get("subagent_history_start_ordinal"),
    }


def normalize_codex_usage(raw: dict) -> dict:
    """Validate and normalize a raw Codex usage payload into the shared shape."""
    if not isinstance(raw, dict):
        raise ValueError("missing usage")
    values = {}
    for name in ("input_tokens", "cached_input_tokens", "cache_write_input_tokens",
                 "output_tokens", "reasoning_output_tokens", "total_tokens"):
        value = raw.get(name, 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise ValueError("invalid token counter: " + name)
        values[name] = value
    for name in ("input_tokens", "output_tokens", "total_tokens"):
        if name not in raw:
            raise ValueError("missing counter: " + name)
    inp, out = values["input_tokens"], values["output_tokens"]
    read, write = values["cached_input_tokens"], values["cache_write_input_tokens"]
    if read + write > inp or values["reasoning_output_tokens"] > out or values["total_tokens"] != inp + out:
        raise ValueError("inconsistent token counters")
    return {
        "input_tokens": inp, "uncached_input_tokens": inp - read - write,
        "cache_read_tokens": read, "cache_write_tokens": write,
        "output_tokens": out, "reasoning_output_tokens": values["reasoning_output_tokens"],
        "total_tokens": values["total_tokens"], "credit": 0.0,
    }


def scan_transcript(path: Path, cursor: dict | None = None) -> tuple[list[dict], dict]:
    """Return staged rows/cursor. Caller commits cursor only AFTER task writes.

    Incomplete tail lines are retried. Complete malformed lines are skipped and
    diagnosed. Replacement/truncation resets the cursor; response ids dedupe.
    """
    old = copy.deepcopy(cursor or {})
    stat = path.stat()
    fingerprint = [stat.st_dev, stat.st_ino]
    if old.get("file_id") != fingerprint or stat.st_size < old.get("offset", 0):
        old = {}
    if old.get("anchor"):
        with path.open("rb") as stream:
            stream.seek(max(0, old["offset"] - 128))
            anchor = hashlib.sha256(stream.read(min(old["offset"], 128))).hexdigest()
        if anchor != old["anchor"]:
            # Also detect truncate-and-regrow between two hook invocations.
            old = {}
    current = old or {"offset": 0, "contexts": {}, "seen_turns": {}, "bad_lines": 0, "legacy": False}
    current.update(file_id=fingerprint, partial=False)
    records = []
    with path.open("rb") as stream:
        stream.seek(current["offset"])
        while True:
            left = remaining_sec()
            if left is not None and left < 0.6:
                current["partial"] = stream.tell() < os.fstat(stream.fileno()).st_size
                break
            line = stream.readline()
            if not line:
                break
            if not line.endswith(b"\n"):
                current["partial"] = True
                break
            current["offset"] = stream.tell()
            try:
                row = json.loads(line)
                payload = row.get("payload")
                if not isinstance(payload, dict):
                    raise ValueError("invalid payload")
                kind = row.get("type")
                if kind == "session_meta":
                    if not current.get("identity"):
                        current["identity"] = identity(payload)
                    continue
                owner = current.get("identity", {})
                # Ignore copied parent context as well as copied accounting.
                boundary = owner.get("history_start")
                if boundary is not None and row.get("ordinal", boundary) < boundary:
                    continue
                if kind == "turn_context":
                    turn = str(payload.get("turn_id") or "")
                    current["turn_id"] = turn
                    ctx = current["contexts"].setdefault(turn, {})
                    ctx.update(model=payload.get("model") or "unknown",
                               root_turn_id=payload.get("root_turn_id") or turn)
                elif kind == "event_msg" and payload.get("type") == "task_started":
                    current["turn_id"] = str(payload.get("turn_id") or "")
                elif kind == "event_msg" and payload.get("type") == "token_count":
                    current["legacy"] = True
                elif kind == "event_msg" and payload.get("type") == "item_completed":
                    item = payload.get("item") or {}
                    if item.get("type") == "UserMessage" and owner.get("agent_type") != "guardian":
                        turn = str(payload.get("turn_id") or current.get("turn_id") or "")
                        current["contexts"].setdefault(turn, {})["prompt"] = text_content(item.get("content"))
                elif kind == "response_item":
                    # A guardian prompt embeds the parent's review transcript.
                    # Do not duplicate that conversation in task data or cursors.
                    if owner.get("agent_type") == "guardian":
                        continue
                    if (payload.get("type") == "message" and payload.get("role") == "user") or payload.get("type") == "agent_message":
                        # Only incoming agent messages are prompts for a child.
                        if payload.get("type") != "agent_message" or payload.get("recipient") in (owner.get("agent_path"), owner.get("thread_id")):
                            current["contexts"].setdefault(current.get("turn_id", ""), {})["prompt"] = text_content(payload.get("content"))
                elif kind == "token_usage_record":
                    if payload.get("thread_id") != owner.get("thread_id"):
                        continue
                    if payload.get("session_id") != owner.get("session_id"):
                        raise ValueError("session identity mismatch")
                    response = payload.get("response_id")
                    turn, root_turn = payload.get("turn_id"), payload.get("root_turn_id")
                    if not all(isinstance(x, str) and x for x in (response, turn, root_turn)):
                        raise ValueError("missing request identity")
                    usage = normalize_codex_usage(payload.get("usage"))
                    ctx = current["contexts"].get(turn, {})
                    current["seen_turns"][root_turn] = True
                    records.append({
                        "request_id": "codex:" + response, "client": CLIENT_CODEX,
                        "source": "codex_rollout", "session_id": owner["session_id"],
                        "thread_id": owner["thread_id"], "turn_id": turn,
                        "root_turn_id": root_turn, "parent_thread_id": owner["parent_thread_id"],
                        "agent_path": owner["agent_path"],
                        "agent_kind": "subagent" if owner["parent_thread_id"] else "main",
                        **({"agent_type": "guardian"} if owner.get("agent_type") == "guardian" else {}),
                        "transcript_path": str(path), "started_at": timestamp_ms(row.get("timestamp")),
                        "prompt": ctx.get("prompt", ""), "model": ctx.get("model", "unknown"),
                        "usage": usage,
                    })
            except (ValueError, TypeError, AttributeError, KeyError) as error:
                current["bad_lines"] += 1
                log(f"codex: invalid log record {path.name}: {type(error).__name__}")
        stream.seek(max(0, current["offset"] - 128))
        current["anchor"] = hashlib.sha256(stream.read(min(current["offset"], 128))).hexdigest()
    return records, current


def locate_transcript(thread_id: str, homes: list[Path]) -> Path | None:
    """Search by a registered id only, never enumerate unrelated chat contents."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", thread_id):
        return None
    for home in homes:
        for folder in (home / "sessions", home / "archived_sessions"):
            for path in folder.glob(f"**/*{thread_id}.jsonl"):
                if remaining_sec() is not None and remaining_sec() < 0.6:
                    return None
                if read_meta(path).get("id") == thread_id:
                    return path
    return None


def register_thread(state: dict, thread_id: str, path=None, **fields) -> None:
    """Record or update a thread's known path, lineage and root turn in `state`."""
    if not thread_id:
        return
    entry = state["threads"].setdefault(thread_id, {})
    entry.update({k: v for k, v in fields.items() if v})
    if fields.get("root_turn_id"):
        entry.setdefault("root_turns", {})[fields["root_turn_id"]] = True
    if path:
        meta = read_meta(Path(path))
        ident = identity(meta)
        if ident["thread_id"] == thread_id and ident["session_id"] == state["session_id"]:
            entry.update(path=str(Path(path).resolve()), **ident)


def codex_homes(state: dict) -> list[Path]:
    """Retain custom homes for reports run outside the original environment."""
    homes = set(state.get("codex_homes", []))
    for entry in state["threads"].values():
        if entry.get("path"):
            for parent in Path(entry["path"]).resolve().parents:
                if parent.name in ("sessions", "archived_sessions"):
                    homes.add(str(parent.parent))
                    break
    if not homes:
        homes.add(str(Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex").resolve()))
    state["codex_homes"] = sorted(homes)
    return [Path(home) for home in sorted(homes)]


def discovery_budget_low() -> bool:
    """True once too little time remains to safely run guardian discovery."""
    left = remaining_sec()
    # Leave time for accounting and persisting the discovery continuation.
    return left is not None and left < 1.2


def guardian_matches(state: dict, thread_id: str, metadata: dict) -> bool:
    """Check whether `metadata` is a guardian transcript bound to `thread_id`."""
    ident = identity(metadata)
    parent = state["threads"].get(ident["parent_thread_id"], {})
    parent_id = identity(read_meta(Path(parent["path"]))) if parent.get("path") else {}
    return (ident["thread_id"] == thread_id and ident["session_id"] == state["session_id"] and
            ident["agent_type"] == "guardian" and thread_id != ident["parent_thread_id"] and
            parent_id.get("thread_id") == ident["parent_thread_id"] and
            parent_id.get("session_id") == state["session_id"])


def discover_guardians(state: dict) -> dict:
    """Read only index candidates and their first metadata line, never guess tasks.

    Guardian does not currently enter the SubagentStart index. Codex's SQLite
    thread catalog supplies candidates, not attribution: session AND registered
    parent must match the transcript before its body can be read. Request-level
    root_turn_id then uses exactly the same immutable SOP bindings as other rows.
    The catalog is an internal format; missing/changed/locked data is incomplete.
    """
    health = {"status": "ok", "issues": []}
    positions = state.setdefault("guardian_discovery_positions", {})
    pending_issues = state.setdefault("guardian_discovery_issues", {})
    for home in codex_homes(state):
        databases = []
        for candidate in home.glob("state_*.sqlite"):
            match = re.fullmatch(r"state_(\d+)\.sqlite", candidate.name)
            if match:
                databases.append((int(match.group(1)), candidate))
        if not databases:
            health["issues"].append("index_missing")
            continue
        path = max(databases, key=lambda item: item[0])[1]
        key = str(path)
        db = None
        issues = list(pending_issues.get(key, []))
        completed = False
        try:
            db = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True, timeout=0.05)
            db.execute("PRAGMA query_only = ON")
            db.set_progress_handler(lambda: int(discovery_budget_low()), 1000)
            candidates = db.execute(
                "SELECT id, rollout_path FROM threads WHERE id > ? AND source LIKE ? ORDER BY id",
                (positions.get(key, ""), '%"guardian"%'))
            for thread_id, log_path in candidates:
                if discovery_budget_low():
                    health["issues"].append("budget")
                    break
                metadata = read_meta(Path(log_path))
                ident = identity(metadata)
                if not metadata:
                    issues.append("candidate_metadata_unavailable")
                elif ident["session_id"] == state["session_id"]:
                    if guardian_matches(state, thread_id, metadata):
                        register_thread(state, thread_id, log_path, discovered_by="codex_thread_index")
                    else:
                        issues.append("candidate_identity_unverified")
                positions[key] = thread_id
            else:
                # Revisit the catalog on the next event: rows can be published
                # late, and an existing guardian thread can review later turns.
                positions.pop(key, None)
                completed = True
        except (sqlite3.Error, OSError, ValueError, TypeError) as error:
            health["issues"].append("index_unavailable:" + type(error).__name__)
        finally:
            if db is not None:
                db.close()
        health["issues"].extend(issues)
        if completed:
            pending_issues.pop(key, None)
        else:
            pending_issues[key] = sorted(set(issues))
    if health["issues"]:
        health["status"] = "partial"
        health["issues"] = sorted(set(health["issues"]))
    return health


def valid_binding(binding: dict) -> bool:
    """Do not recreate task directories hidden by a later branch checkout."""
    overview = Path(binding["task"]) / "00-overview.md"
    try:
        text = overview.read_text(encoding="utf-8")
    except OSError:
        return False
    match = re.search(r"\|\s*(?:Branch|\u5206\u652f)\s*\|\s*`?([^`\n\r|]+)`?\s*\|", text)
    return bool(match and match.group(1).strip() == binding["branch"])


def ledger_digest(task: Path, session_id: str) -> str:
    """Detect checkout/restore of this session's ledger without other-client noise."""
    path = task / "token.json"
    store = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"requests": []}
    if not isinstance(store, dict) or not isinstance(store.get("requests"), list):
        raise ValueError("invalid token store: " + str(path))
    rows = [item for item in store["requests"] if isinstance(item, dict) and
            item.get("client") == CLIENT_CODEX and item.get("session_id") == session_id]
    rows.sort(key=lambda item: str(item.get("request_id", "")))
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def task_groups(state: dict, only_task: Path | None) -> dict:
    """Group bound turns by task directory, deferring turns whose task is hidden."""
    groups = {}
    for turn, binding in state["bindings"].items():
        task = Path(binding["task"])
        if only_task is not None and task != only_task.resolve():
            continue
        if not valid_binding(binding):
            # A checkout may hide an older task; defer its rows without
            # preventing progress on the current task.
            if only_task is not None:
                raise OSError("bound task is unavailable: " + str(task))
            continue
        group = groups.setdefault(str(task), {"binding": binding, "turns": set(), "records": []})
        group["turns"].add(turn)
    return groups


def synchronize(state: dict, *, only_task: Path | None = None) -> dict:
    """Rescan bound threads and persist freshly observed records into their tasks."""
    staged = copy.deepcopy(state)
    groups = task_groups(staged, only_task)
    snapshots = staged.setdefault("ledger_snapshots", {})
    for task, group in groups.items():
        digest = ledger_digest(Path(task), state["session_id"])
        if snapshots.get(task) != digest:
            for entry in staged["threads"].values():
                seen = set((entry.get("cursor") or {}).get("seen_turns", {}))
                if seen & group["turns"]:
                    entry.pop("cursor", None)
        snapshots[task] = digest
    discovery = discover_guardians(staged)
    rows = list(staged.get("deferred_records", {}).values())
    for thread_id, entry in staged["threads"].items():
        if remaining_sec() is not None and remaining_sec() < 0.6:
            entry["scan_status"] = "partial"
            continue
        path = Path(entry["path"]) if entry.get("path") else None
        if path is None or not path.is_file():
            path = locate_transcript(thread_id, codex_homes(staged))
        if path is None or not path.is_file():
            entry["scan_status"] = "missing"
            continue
        metadata = read_meta(path)
        if ((entry.get("agent_type") == "guardian" or identity(metadata)["agent_type"] == "guardian") and
                not guardian_matches(staged, thread_id, metadata)):
            entry["scan_status"] = "partial"
            continue
        register_thread(staged, thread_id, path)
        if not entry.get("path") or read_meta(path).get("id") != thread_id:
            entry["scan_status"] = "partial"
            continue
        try:
            found, cursor = scan_transcript(path, entry.get("cursor"))
            if cursor.get("identity", {}).get("session_id") != state["session_id"]:
                entry["scan_status"] = "partial"
                continue
            entry["cursor"] = cursor
            rows.extend(found)
            entry["scan_status"] = ("partial" if cursor["partial"] or cursor["bad_lines"] else
                                    "ok" if cursor["seen_turns"] else
                                    "unsupported" if cursor["legacy"] else "pending")
        except OSError:
            entry["scan_status"] = "missing"

    deferred = {}
    for row in rows:
        binding = staged["bindings"].get(row["root_turn_id"])
        if binding and binding["task"] in groups:
            row["branch"] = binding["branch"]
            groups[binding["task"]]["records"].append(row)
        elif binding:
            deferred[row["request_id"]] = row

    for group in groups.values():
        sources = []
        for thread_id, entry in staged["threads"].items():
            relevant = (thread_id == state["session_id"] or
                        (entry.get("agent_type") == "guardian" and not
                         (entry.get("cursor") or {}).get("seen_turns")) or
                        bool(set(entry.get("root_turns", {})) & group["turns"]) or
                        bool(set((entry.get("cursor") or {}).get("seen_turns", {})) & group["turns"]))
            if relevant:
                status = entry.get("scan_status", "pending")
                seen = set((entry.get("cursor") or {}).get("seen_turns", {}))
                if status == "ok" and not seen & group["turns"]:
                    status = "pending"
                sources.append({"thread_id": thread_id, "agent_path": entry.get("agent_path", ""),
                                "status": status})
        statuses = {x["status"] for x in sources}
        status = ("partial" if discovery["status"] != "ok" or statuses & {"partial", "missing"} else
                  "unsupported" if "unsupported" in statuses else
                  "pending" if not sources or "pending" in statuses else "ok")
        health = {"status": status, "as_of": datetime.now().astimezone().isoformat(timespec="seconds"),
                  "sources": sources, "guardian_discovery": discovery}
        binding = group["binding"]
        sync_task_store(Path(binding["repo"]), Path(binding["task"]), group["records"],
                        collection={"codex": {"sessions": {state["session_id"]: health}}},
                        require_write=True)
        snapshots[binding["task"]] = ledger_digest(Path(binding["task"]), state["session_id"])
    # Persist deferred structured records in the SAME atomic state write as
    # their cursors. Hidden/excluded tasks can resume without starving later
    # requests in a large log; a failed write leaves both at the previous point.
    staged["deferred_records"] = deferred
    return staged


def process_hook(payload: dict, repo: Path | None = None) -> None:
    """Handle one IDE hook event: bind/replay the session and sync its task store."""
    event = payload.get("hook_event_name")
    if event not in EVENTS:
        return
    supplied = payload.get("transcript_path")
    meta = read_meta(Path(supplied)) if supplied else {}
    ident = identity(meta)
    supplied_session = str(payload.get("session_id") or "")
    session_id = ident["session_id"] or (registered_session(supplied_session) if supplied_session else "")
    if not session_id:
        return
    # Reject unrelated explicit paths instead of attributing another session.
    if meta and payload.get("session_id") not in (ident["session_id"], ident["thread_id"]):
        return
    repo = find_repo(repo or Path(payload.get("cwd") or os.getcwd()))
    branch = git_branch(repo) if repo else ""
    if repo is None or token_work_disabled(branch):
        return
    task = find_task_dir(repo, branch) if repo and not token_work_disabled(branch) else None
    path = state_path(session_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock("codex-state:" + str(path)):
        state = load_state(path) if path.exists() else {
            "version": 1, "session_id": session_id, "bindings": {}, "threads": {}}
        primary = ident["thread_id"] or str(payload.get("session_id") or session_id)
        register_thread(state, primary, supplied)
        turn = str(payload.get("turn_id") or "")
        entry = state["threads"][primary]
        root_turn = turn
        if primary != session_id:
            context = (entry.get("cursor") or {}).get("contexts", {}).get(turn, {})
            root_turn = context.get("root_turn_id") or entry.get("root_turn_id") or ""
        # Only a main-thread event may establish a binding. Children never
        # choose a task from their cwd/branch, even when the parent was unbound.
        if primary == session_id and root_turn and task and root_turn not in state["bindings"]:
            state["bindings"][root_turn] = {"repo": str(repo.resolve()), "task": str(task.resolve()), "branch": branch}
            # A task can be created during a turn. Replay its earlier requests,
            # but unbound historical turns remain ineligible.
            for old in state["threads"].values():
                if root_turn in (old.get("cursor") or {}).get("seen_turns", {}):
                    old.pop("cursor", None)
        if event in ("SubagentStart", "SubagentStop"):
            child = str(payload.get("agent_id") or "")
            register_thread(state, child, payload.get("agent_transcript_path"),
                            parent_thread_id=primary, root_turn_id=root_turn,
                            agent_type=payload.get("agent_type"))
        # Persist discovery/bindings before expensive scans, but never advance
        # read cursors until all task stores have committed successfully.
        write_json(path, state)
        updated = synchronize(state)
        write_json(path, updated)


def refresh_task(task: Path) -> None:
    """Re-run synchronization for every session bound to `task`."""
    target = task.resolve()
    expected = set(read_json(target / "token.json").get("collection", {})
                    .get("codex", {}).get("sessions", {}))
    refreshed = set()
    for path in state_dir().glob("*.json"):
        state = read_json(path)
        if not any(b.get("task") == str(target) for b in state.get("bindings", {}).values()):
            continue
        with file_lock("codex-state:" + str(path)):
            updated = synchronize(load_state(path), only_task=target)
            write_json(path, updated)
            refreshed.add(updated["session_id"])
    if expected - refreshed:
        raise OSError("Codex runtime bindings are missing; snapshot could not be refreshed")


def main() -> int:
    """Parse CLI arguments and run the hook or a task refresh."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--refresh-task", type=Path)
    args = parser.parse_args()
    # Reports use their caller's timeout, which can surface failure. The hook's
    # hard deadline exits successfully to avoid interrupting the coding agent.
    if not args.refresh_task:
        install_deadline(2.5)
    try:
        if args.refresh_task:
            refresh_task(args.refresh_task)
        else:
            process_hook(read_stdin_json(), args.repo)
    except Exception as error:
        log(f"codex collect failed: {type(error).__name__}: {error}")
        return 1 if args.refresh_task else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
