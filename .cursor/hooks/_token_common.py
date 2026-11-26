#!/usr/bin/env python3
"""Shared helpers for the SOP token collectors (CodeBuddy, Cursor and Codex).

All collectors append usage records to the same
``.wally/plans/<task>/token.json``. Keeping the record shape, the merge rules
and the advisory lock in one module is what stops concurrent writers from
drifting apart and corrupting each other's state.

``sync_task_store`` is the entry point all collectors use: it drops requests
that another SOP task already owns before merging, so running two tasks from a
single chat window keeps two independent stores.

This module is copied into the target repository (``.codebuddy/hooks/``,
``.cursor/hooks/`` and ``.codex/hooks/``), so it must stay stdlib-only and must
never import from a collector.

Collectors are IDE hooks: they MUST finish in well under 3s and MUST NOT
block the session. Hard guarantees live here — ``install_deadline`` (SIGALRM
→ ``os._exit(0)``), a non-blocking stdin read, a timed flock, and a 1s git
timeout. Incremental merge means aborting is safe; the next event retries.

Store contract (``token.json``)::

    {
      "version": 1,
      "updated_at": "<iso8601>",
      "requests": [
        {
          "request_id": "<unique per request>",
          "session_id": "<conversation/session id>",
          "branch": "<branch when first observed>",
          "client": "codebuddy" | "cursor" | "codex",
          "source": "<collector-specific tag>",
          "transcript_path": "<path>",
          "started_at": <epoch ms>,
          "prompt": "<user prompt text>",
          "model": "<model>",
          "usage": {
            "input_tokens": 0, "uncached_input_tokens": 0,
            "cache_read_tokens": 0, "cache_write_tokens": 0,
            "output_tokens": 0, "total_tokens": 0, "credit": 0.0
          }
        }
      ]
    }
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any

DEBUG_LOG = Path("/tmp/wally_debug/stop_token_collect.log")
TOKEN_FILE_NAME = "token.json"

# Which task owns which request, kept outside any repository so it survives the
# branch switch that hides a finished task's directory. See ``foreign_ids``.
CLAIM_LEDGER_ENV = "WALLY_TOKEN_CLAIMS"
DEFAULT_CLAIM_LEDGER = Path.home() / ".wally" / "wally-init" / "token_claims.json"
MAX_CLAIMS = 5000

CLIENT_CODEBUDDY = "codebuddy"
CLIENT_CURSOR = "cursor"
CLIENT_CODEX = "codex"
CLIENT_CLAUDE = "claude"

# Legacy CodeBuddy records predate the ``client`` field; infer from ``source``.
CODEBUDDY_SOURCES = ("ide_index", "cli_jsonl")

# Hook host timeout is 3s. The process kills itself a bit earlier so it
# exits cleanly instead of being SIGKILL'd mid-write.
HOOK_DEADLINE_SEC = 2.5
STDIN_TIMEOUT_SEC = 0.8
GIT_TIMEOUT_SEC = 1.0
LOCK_WAIT_SEC = 0.4

_DEADLINE_AT: float | None = None


class LockTimeout(Exception):
    """Advisory lock was held by another collector past ``LOCK_WAIT_SEC``."""


def log(message: str) -> None:
    try:
        DEBUG_LOG.parent.mkdir(parents=True, exist_ok=True)
        with DEBUG_LOG.open("a", encoding="utf-8") as f:
            f.write(
                "[{}] {}\n".format(
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"), message
                )
            )
    except Exception:
        pass


def remaining_sec() -> float | None:
    if _DEADLINE_AT is None:
        return None
    return _DEADLINE_AT - time.monotonic()


def install_deadline(seconds: float = HOOK_DEADLINE_SEC) -> None:
    """Hard-kill this process so a stuck hook cannot block the IDE.

    Cursor/CodeBuddy wait on the hook command. A blocking ``stdin.read()``
    or ``flock`` would freeze the session until the host timeout. Collectors
    are incremental, so aborting is safe — the next event retries.
    """
    global _DEADLINE_AT
    _DEADLINE_AT = time.monotonic() + seconds
    try:
        import signal
    except ImportError:
        return

    def _abort(_signum, _frame):
        try:
            log(f"deadline: abort after {seconds:.1f}s")
        except Exception:
            pass
        os._exit(0)

    try:
        signal.signal(signal.SIGALRM, _abort)
        if hasattr(signal, "setitimer") and hasattr(signal, "ITIMER_REAL"):
            signal.setitimer(signal.ITIMER_REAL, seconds)
        else:
            signal.alarm(max(1, int(seconds)))
    except (AttributeError, ValueError, OSError):
        return


def _parse_json_dict(raw: str) -> dict | None:
    if not raw or not raw.strip():
        return None
    try:
        value = json.loads(raw)
    except ValueError:
        return None
    return value if isinstance(value, dict) else None


def read_stdin_json(timeout_sec: float = STDIN_TIMEOUT_SEC) -> dict:
    """Read the hook payload without waiting for the host to close stdin.

    TeamAI/CodeBuddy have been observed to write JSON and leave the pipe
    open; a blocking ``sys.stdin.read()`` then hangs until the IDE kills
    the hook. Stop as soon as a complete JSON object is parsed.
    """
    try:
        fd = sys.stdin.fileno()
    except (AttributeError, OSError, ValueError):
        try:
            parsed = _parse_json_dict(sys.stdin.read() or "")
        except Exception:
            return {}
        return parsed or {}

    import select

    chunks: list[bytes] = []
    deadline = time.monotonic() + max(0.0, timeout_sec)
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            break
        try:
            readable, _, _ = select.select([fd], [], [], remaining)
        except (OSError, ValueError):
            break
        if not readable:
            break
        try:
            data = os.read(fd, 65536)
        except OSError:
            break
        if not data:
            break
        chunks.append(data)
        parsed = _parse_json_dict(b"".join(chunks).decode("utf-8", "replace"))
        if parsed is not None:
            return parsed
    return _parse_json_dict(b"".join(chunks).decode("utf-8", "replace")) or {}


def as_int(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def as_float(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def find_repo(start: Path) -> Path | None:
    try:
        cur = start.resolve()
    except OSError:
        cur = start
    while True:
        if (cur / ".wally").is_dir():
            return cur
        if cur.parent == cur:
            return None
        cur = cur.parent


def token_work_disabled(branch: str) -> bool:
    """True on integration branches: collectors must no-op immediately.

    SOP work (and therefore token attribution) is forbidden on ``master`` /
    ``main`` and on release lines (``release``, ``release/...``). Historical
    tasks sometimes list ``master`` in Meta; collecting there would dump the
    whole mainline conversation onto those tasks.
    """
    name = (branch or "").strip()
    if name in ("master", "main"):
        return True
    return name == "release" or name.startswith("release/")


def git_branch(repo: Path) -> str:
    for command in (
        ["git", "symbolic-ref", "--short", "--quiet", "HEAD"],
        ["git", "branch", "--show-current"],
    ):
        try:
            # NOCA:dangerous-subprocess-use-audit(argv list, no shell)
            out = subprocess.check_output(
                command,
                cwd=str(repo),
                stderr=subprocess.DEVNULL,
                timeout=GIT_TIMEOUT_SEC,
            )
            branch = out.decode("utf-8", errors="replace").strip()
            if branch:
                return branch
        except Exception:
            pass
    return ""


def find_task_dir(repo: Path, branch: str) -> Path | None:
    """Locate `.wally/plans/<task>` whose overview Meta branch matches HEAD."""
    if not branch or token_work_disabled(branch):
        return None
    plans = repo / ".wally" / "plans"
    if not plans.is_dir():
        return None
    hits: list[tuple[float, Path]] = []
    for task in plans.iterdir():
        left = remaining_sec()
        if left is not None and left < 0.15:
            log(f"find_task_dir: stop scan, budget left={left:.3f}s")
            break
        if not task.is_dir() or task.name.startswith(("_", ".")):
            continue
        overview = task / "00-overview.md"
        if not overview.is_file():
            continue
        try:
            text = overview.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        match = re.search(r"\|\s*(?:Branch|\u5206\u652f)\s*\|\s*`?([^`\n\r|]+)`?\s*\|", text)
        if not match or match.group(1).strip() != branch:
            continue
        try:
            mtime = overview.stat().st_mtime
        except OSError:
            mtime = 0.0
        hits.append((mtime, task))
    if not hits:
        return None
    hits.sort(key=lambda item: item[0], reverse=True)
    return hits[0][1]


def normalize_usage(raw: dict) -> dict:
    """Normalize IDE/CLI usage while preserving the client's own accounting.

    input_tokens = uncached_input + cache_read + cache_write
    total_tokens = input_tokens + output_tokens (the IDE's ``Tokens`` value)

    Cursor ships ``input_tokens`` / ``output_tokens`` / ``cache_read_tokens`` /
    ``cache_write_tokens`` and no ``credit``; CodeBuddy ships a different field
    spelling plus ``credit``. Both collapse onto the same shape here.
    """
    if not isinstance(raw, dict):
        raw = {}

    output = as_int(
        raw.get("output_tokens")
        if "output_tokens" in raw
        else raw.get("outputTokens", raw.get("completion_tokens"))
    )
    cache_read = as_int(
        raw.get("cache_read_input_tokens")
        or raw.get("cache_read_tokens")
        or raw.get("cacheTokens")
    )
    if not cache_read:
        details = raw.get("inputTokensDetails") or raw.get("input_tokens_details")
        if isinstance(details, list):
            for item in details:
                if isinstance(item, dict) and "cached_tokens" in item:
                    cache_read = as_int(item.get("cached_tokens"))
                    break

    cache_write = as_int(
        raw.get("cache_creation_input_tokens")
        or raw.get("cache_creation_tokens")
        or raw.get("cache_write_tokens")  # Cursor spelling
        or raw.get("cachedWriteTokens")
    )
    input_tokens = raw.get("input_tokens")
    if input_tokens is None:
        input_tokens = raw.get("inputTokens", raw.get("prompt_tokens"))

    uncached = raw.get("uncached_input_tokens")
    if uncached is None:
        uncached = raw.get("cachedMissTokens")
    if input_tokens is None:
        input_tokens = as_int(uncached) + cache_read + cache_write
    input_tokens = as_int(input_tokens)
    if uncached is None:
        uncached = max(0, input_tokens - cache_read - cache_write)

    total = as_int(
        raw.get("total_tokens")
        if "total_tokens" in raw
        else raw.get("totalTokens")
    )
    if not total:
        total = input_tokens + output

    return {
        "input_tokens": input_tokens,
        "uncached_input_tokens": as_int(uncached),
        "cache_read_tokens": cache_read,
        "cache_write_tokens": cache_write,
        "output_tokens": output,
        "total_tokens": total,
        "credit": as_float(raw.get("credit")),
    }


def merge_cumulative_usage(previous: dict, incoming: dict) -> dict:
    """Merge Cursor's turn-cumulative counters by element-wise maximum.

    Cursor restates the *running total of the whole generation* on every
    ``afterAgentResponse``/``stop`` event, and only the closing events of a
    generation carry counters at all. Taking the maximum of the primitive
    counters therefore converges on the final turn total, tolerates
    out-of-order events, and never double counts — unlike a plain sum.

    Derived fields are recomputed so the invariant
    ``input = uncached + cache_read + cache_write`` always holds.
    """
    inp = max(as_int(previous.get("input_tokens")), as_int(incoming.get("input_tokens")))
    read = max(
        as_int(previous.get("cache_read_tokens")), as_int(incoming.get("cache_read_tokens"))
    )
    write = max(
        as_int(previous.get("cache_write_tokens")), as_int(incoming.get("cache_write_tokens"))
    )
    out = max(as_int(previous.get("output_tokens")), as_int(incoming.get("output_tokens")))
    return {
        "input_tokens": inp,
        "uncached_input_tokens": max(0, inp - read - write),
        "cache_read_tokens": read,
        "cache_write_tokens": write,
        "output_tokens": out,
        "total_tokens": inp + out,
        "credit": max(
            as_float(previous.get("credit")), as_float(incoming.get("credit"))
        ),
    }


@contextmanager
def file_lock(tag: str, wait_sec: float = LOCK_WAIT_SEC) -> Iterator[None]:
    """Serialize writers of ``tag`` with a timed non-blocking flock.

    A blocking ``LOCK_EX`` would stall the hook until the other writer
    (or a dead NFS lock) released — longer than the 3s host budget.
    Time out, skip the write, and let the next event retry.
    """
    digest = hashlib.sha256(tag.encode("utf-8")).hexdigest()[:16]
    lock_path = DEBUG_LOG.parent / f"token-{digest}.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock = lock_path.open("a+", encoding="utf-8")
    acquired = False
    fcntl_mod = None
    try:
        try:
            import fcntl as fcntl_mod
        except ImportError:
            fcntl_mod = None
        if fcntl_mod is not None:
            deadline = time.monotonic() + max(0.0, wait_sec)
            while True:
                try:
                    fcntl_mod.flock(
                        lock.fileno(), fcntl_mod.LOCK_EX | fcntl_mod.LOCK_NB
                    )
                    acquired = True
                    break
                except BlockingIOError:
                    left = deadline - time.monotonic()
                    if left <= 0:
                        raise LockTimeout(tag)
                    time.sleep(min(0.02, left))
                except OSError:
                    break
        yield
    finally:
        if acquired and fcntl_mod is not None:
            try:
                fcntl_mod.flock(lock.fileno(), fcntl_mod.LOCK_UN)
            except OSError:
                pass
        try:
            lock.close()
        except OSError:
            pass


def write_json(path: Path, payload: dict) -> None:
    temp = path.with_suffix(f"{path.suffix}.tmp.{os.getpid()}")
    temp.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    os.replace(str(temp), str(path))


def empty_store() -> dict:
    return {"version": 1, "updated_at": None, "requests": []}


def load_store(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return empty_store()
    if not isinstance(value, dict) or not isinstance(value.get("requests"), list):
        return empty_store()
    return value


def merge_store(
    path: Path,
    incoming: list[dict],
    usage_merger: Callable[[dict, dict], dict] | None = None,
    collection: dict | None = None,
    strict: bool = False,
) -> tuple[int, int, int] | None:
    """Merge by request_id under an advisory lock, then atomically replace.

    ``usage_merger`` lets a caller override how an *existing* record's usage is
    combined with a new observation (Cursor passes ``merge_cumulative_usage``).
    Without it the incoming usage simply replaces the stored one, which is
    correct for clients that report a final per-request value.

    Returns ``None`` when the store lock could not be acquired in time; the
    caller must not record claims in that case.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with file_lock(f"store:{path.resolve()}"):
            if strict and path.exists():
                store = json.loads(path.read_text(encoding="utf-8"))
                if not isinstance(store, dict) or not isinstance(store.get("requests"), list):
                    raise ValueError("invalid token store: " + str(path))
            else:
                store = load_store(path)
            records: dict[str, dict] = {
                str(item.get("request_id")): item
                for item in store["requests"]
                if isinstance(item, dict) and item.get("request_id")
            }
            added = updated = 0
            for item in incoming:
                key = item["request_id"]
                previous = records.get(key)
                if previous is None:
                    records[key] = item
                    added += 1
                    continue
                merged = dict(item)
                # Preserve the original branch: it is the closest attribution to
                # the request when first observed.
                merged["branch"] = previous.get("branch") or item.get("branch")
                if usage_merger is not None:
                    prev_usage = previous.get("usage")
                    next_usage = merged.get("usage")
                    if isinstance(prev_usage, dict) and isinstance(next_usage, dict):
                        merged["usage"] = usage_merger(prev_usage, next_usage)
                if previous != merged:
                    records[key] = merged
                    updated += 1

            ordered = sorted(
                records.values(),
                key=lambda item: (
                    as_int(item.get("started_at")),
                    str(item.get("request_id") or ""),
                ),
            )
            # Preserve optional collection health and future metadata when a
            # different client writes to the same task store.
            if collection:
                health = store.setdefault("collection", {})
                for client, value in collection.items():
                    current = health.setdefault(client, {})
                    current.setdefault("sessions", {}).update(value.get("sessions", {}))
            store.update({
                "version": 1,
                "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "requests": ordered,
            })
            write_json(path, store)
            return added, updated, len(ordered)
    except LockTimeout:
        log(f"skip merge: lock timeout {path}")
        return None


def task_key(task_dir: Path) -> str:
    try:
        return str(task_dir.resolve())
    except OSError:
        return str(task_dir)


def claim_ledger_path() -> Path:
    override = os.environ.get(CLAIM_LEDGER_ENV)
    return Path(override) if override else DEFAULT_CLAIM_LEDGER


def load_claims(path: Path) -> dict[str, str]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    claims = value.get("claims") if isinstance(value, dict) else None
    if not isinstance(claims, dict):
        return {}
    return {
        str(key): value
        for key, value in claims.items()
        if key and isinstance(value, str)
    }


def record_claims(task_dir: Path, request_ids: Iterable[str]) -> None:
    """Mark ``request_ids`` as owned by ``task_dir`` for every later collection."""
    ids = [str(rid) for rid in request_ids if rid]
    if not ids:
        return
    owner = task_key(task_dir)
    path = claim_ledger_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with file_lock(f"claims:{path}"):
            claims = load_claims(path)
            for rid in ids:
                # Re-insert so an active task keeps its claims at the young end
                # of the insertion order the pruning below relies on.
                claims.pop(rid, None)
                claims[rid] = owner
            for stale in list(claims)[: max(0, len(claims) - MAX_CLAIMS)]:
                del claims[stale]
            write_json(
                path,
                {
                    "version": 1,
                    "updated_at": datetime.now()
                    .astimezone()
                    .isoformat(timespec="seconds"),
                    "claims": claims,
                },
            )
    except LockTimeout:
        log(f"skip claims: lock timeout {path}")
    except OSError as error:
        log(f"claim ledger write failed {path}: {error}")


def store_request_ids(path: Path) -> set[str]:
    return {
        str(item["request_id"])
        for item in load_store(path)["requests"]
        if isinstance(item, dict) and item.get("request_id")
    }


def foreign_ids(repo: Path, task_dir: Path, request_ids: set[str]) -> set[str]:
    """Of ``request_ids``, the ones another SOP task already owns.

    One chat window can drive several SOP tasks in a row, and the CodeBuddy
    collector rescans the whole transcript on every Stop. Without this filter
    the earlier task's requests are replayed into the later task's store and
    inflate its report. Ownership goes to whichever task recorded a request
    first: sibling stores answer that while both task directories are checked
    out, the ledger answers it once a branch switch hides the earlier one.
    """
    if not request_ids:
        return set()
    owner = task_key(task_dir)
    foreign: set[str] = set()
    plans = repo / ".wally" / "plans"
    if plans.is_dir():
        for store in plans.glob(f"*/{TOKEN_FILE_NAME}"):
            if task_key(store.parent) == owner:
                continue
            foreign |= request_ids & store_request_ids(store)
    for rid, claimed_by in load_claims(claim_ledger_path()).items():
        if rid in request_ids and claimed_by != owner:
            foreign.add(rid)
    return foreign


def sync_task_store(
    repo: Path,
    task_dir: Path,
    incoming: list[dict],
    usage_merger: Callable[[dict, dict], dict] | None = None,
    *,
    collection: dict | None = None,
    require_write: bool = False,
) -> tuple[int, int, int, int]:
    """Merge ``incoming`` into the task store, minus requests owned elsewhere.

    Returns ``(added, updated, total, skipped)``.
    """
    ids = {str(item["request_id"]) for item in incoming if item.get("request_id")}
    foreign = foreign_ids(repo, task_dir, ids)
    mine = [item for item in incoming if str(item.get("request_id")) not in foreign]
    merged = merge_store(
        task_dir / TOKEN_FILE_NAME, mine, usage_merger=usage_merger,
        collection=collection,
        strict=require_write,
    )
    if merged is None:
        if require_write:
            raise LockTimeout(str(task_dir / TOKEN_FILE_NAME))
        return 0, 0, 0, len(foreign)
    added, updated, total = merged
    record_claims(task_dir, (str(item["request_id"]) for item in mine))
    return added, updated, total, len(foreign)
