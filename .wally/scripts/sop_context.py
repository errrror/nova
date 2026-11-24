#!/usr/bin/env python3
"""Load actual bound SOP context and gate supported local tools.

This is a workflow check, not a sandbox or proof of model comprehension.
Never return an approval that overrides the client's own permissions.
"""
import argparse
from create_task import method_configured
import hashlib
import secrets
import json
from pathlib import Path
import re
import shlex
import subprocess
import sys


BRANCH = r"(?m)^\|\s*(?:Branch|\u5206\u652f)\s*\|\s*`?([^|`\n]+)`?\s*\|"
RULES = r"(?m)^\|\s*(?:SOP Rules|SOP \u89c4\u5219)\s*\|\s*`?([^|`\n]+)`?\s*\|"
PHASE = r"(?m)^- (?:Phase:|\u6b65\u9aa4\uff1a)\s*(0[1-6])\."
FILENAMES = {"01": "01-clarify.md", "02": "02-plan.md", "03": "03-implement.md",
             "04": "04-deploy.md", "05": "05-it.md", "06": "06-review-commit.md"}
SUMMARY_START = "<!-- wally:root-summary:start -->"
SUMMARY_END = "<!-- wally:root-summary:end -->"


def exported_section(text, start, end, required=False):
    if start not in text and end not in text and not required:
        return text  # Historical versions have no export markers.
    if (text.count(start) != 1 or text.count(end) != 1 or text.index(start) >= text.index(end)):
        raise ValueError("invalid or missing Core export markers: " + start)
    summary = text.split(start, 1)[1].split(end, 1)[0].strip()
    if not summary:
        raise ValueError("empty Core export: " + start)
    return summary


def workflow_summary(text, required=False):
    """Use one Core source for root summaries and bound-version hook outlines."""
    return exported_section(text, SUMMARY_START, SUMMARY_END, required)


def scope_summary(text, required=False):
    return exported_section(text, "<!-- wally:sop-scope:start -->", "<!-- wally:sop-scope:end -->", required)


def current_section(text):
    section = re.search(r"(?ms)^## (?:Current phase|\u5f53\u524d\u6b65\u9aa4)\s*\n(.*?)(?=^## |\Z)", text)
    if not section:
        raise ValueError("Missing current phase section in task overview")
    return section.group(1)


def phase_link(text):
    link = re.search(r"\]\(\./([^\n)]+)\)", current_section(text))
    if not link:
        raise ValueError("Missing current phase file link in task overview")
    return link.group(1)


def is_relative_to(path, root):
    """Containment check that works on every Python 3 (Path.is_relative_to is 3.9+)."""
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def inside(root, path):
    path = Path(path)
    if not path.is_absolute():
        path = root / path
    if not is_relative_to(path.resolve(), root):
        raise ValueError("SOP path escapes repository: " + str(path))
    return path


def read(root, relative):
    path = inside(root, relative)
    if not path.is_file():
        raise ValueError("Missing SOP file: " + str(relative))
    return path.read_text(encoding="utf-8")


def route(root):
    entry = read(root, ".wally/core/entry.md")
    # text= and capture_output= need Python 3.7. PIPE + universal_newlines work on 3.6.
    git = subprocess.run(["git", "-C", str(root), "branch", "--show-current"],
                         stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                         universal_newlines=True, timeout=3)
    branch = git.stdout.strip() if git.returncode == 0 else ""
    if not branch:
        raise ValueError("Cannot route SOP without an actual Git branch; resolve Git state first.")
    matches = []
    plans = inside(root, ".wally/plans")
    for overview in sorted(plans.glob("*/00-overview.md")):
        if overview.parent.name.startswith(("_", ".")):
            continue
        text = read(root, overview)
        match = re.search(BRANCH, text)
        if match and match.group(1).strip() == branch:
            matches.append((overview, text))
    if len(matches) != 1:
        if matches:
            raise ValueError("Multiple SOP tasks match branch " + branch + "; resolve ambiguity before changes.")
        raise ValueError(
            "No SOP task for branch " + branch + ". Before creating a task, ask the user whether to cut "
            "a new branch for this SOP and wait for the answer. Do not bind " + shlex.quote(branch) +
            " until they choose. Once they choose, read .wally/profiles/project.md and run "
            "python3 .wally/scripts/create_task.py YYYY-MM-DD_title --branch <chosen-branch>. "
            "Create and switch first when they want a new branch; staying is allowed only off main/master/HEAD. "
            "The script performs no Git operations.")
    overview, text = matches[0]
    rules = re.search(RULES, text)
    if not rules:
        snapshots = [".wally/compat/v1/" + name for name in ("CODEBUDDY.md", "AGENTS.md", "CLAUDE.md")]
        snapshot = next((p for p in snapshots if inside(root, p).is_file()), None)
        if not snapshot:
            raise ValueError("Historical task is missing its compat/v1 policy snapshot; do not use current rules.")
        artifact = inside(root, overview.parent / phase_link(text))
        if not is_relative_to(artifact.resolve(), overview.parent.resolve()):
            raise ValueError("Historical phase link escapes its task")
        return {"branch": branch, "task": overview.parent.relative_to(root).as_posix(),
                "core": ".wally/compat/v1", "phase": "legacy", "legacy": True, "overview": text,
                "documents": [(".wally/core/entry.md", entry), (snapshot, read(root, snapshot)),
                              (overview.relative_to(root).as_posix(), text),
                              (artifact.relative_to(root).as_posix(), read(root, artifact))]}
    core = rules.group(1).strip()
    if not re.fullmatch(r"\.wally/versions/[0-9a-f]{16}/core", core):
        raise ValueError("Invalid bound SOP Rules path; do not use the latest rules as a fallback.")
    phase = re.search(PHASE, current_section(text))
    if not phase:
        raise ValueError("Missing or invalid current phase in task overview.")
    phase = phase.group(1)
    task = overview.parent
    filename = phase_link(text)
    roles = {name[3:]: number for number, name in FILENAMES.items()}
    if (not filename.startswith(phase + "-") or filename[3:] not in roles or
            Path(filename).name != filename):
        raise ValueError("Current phase number and file link disagree; repair the overview before implementation")
    role = roles[filename[3:]]
    documents = [(".wally/core/entry.md", entry), (overview.relative_to(root).as_posix(), text)]
    task_profile = task / "profile.md"
    profile_rel = (task_profile.relative_to(root).as_posix()
                   if task_profile.is_file() else ".wally/profiles/project.md")
    for relative in (core + "/workflow.md", core + "/gates.md", core + "/interaction.md",
                     profile_rel,
                     (task / filename).relative_to(root).as_posix()):
        documents.append((relative, read(root, relative)))
    if role == "03":
        legacy_rules = task / "_rules" / "rules"
        rules_root = legacy_rules if legacy_rules.is_dir() else (root / ".wally" / "rules")
        rules_boundary = task.resolve() if rules_root == legacy_rules else root.resolve()
        if rules_root.is_dir() and not rules_root.is_symlink():
            if not is_relative_to(rules_root.resolve(), rules_boundary):
                raise ValueError("rules directory escapes allowed boundary")
            for path in sorted(rules_root.rglob("*")):
                if path.is_symlink() or not path.is_file():
                    continue
                if not is_relative_to(path.resolve(), rules_root.resolve()):
                    raise ValueError("rule file escapes rules directory")
                relative = path.relative_to(root).as_posix()
                documents.append((relative, read(root, relative)))
    # Old immutable releases predate this policy; never substitute latest Core.
    knowledge = core + "/knowledge.md"
    if inside(root, knowledge).is_file():
        documents.append((knowledge, read(root, knowledge)))
    if role == "01":
        documents.append((core + "/clarify.md", read(root, core + "/clarify.md")))
    return {"branch": branch, "task": task.relative_to(root).as_posix(), "core": core,
            "phase": phase, "role": role, "phase_file": filename, "documents": documents, "overview": text}


def context_text(result, compact=False):
    header = "SOP checkpoint: branch={branch}; task={task}; rules={core}; phase={phase}.".format(**result)
    documents = result["documents"]
    if compact and not result.get("legacy"):
        selected = []
        for path, content in documents:
            if path == result["core"] + "/workflow.md":
                selected.append((path + " (bound workflow outline)", workflow_summary(content)))
            elif path == result["task"] + "/00-overview.md":
                # Usage reports/time logs can grow indefinitely. Keep only
                # discovery, progress, and the current phase in startup context.
                content = re.split(r"(?m)^## (?:Time log|\u65f6\u95f4\u8bb0\u5f55)\s*$", content, maxsplit=1)[0]
                selected.append((path + " (routing and progress)", content))
            elif path in (result["core"] + "/knowledge.md", result["task"] + "/profile.md",
                          ".wally/profiles/project.md", result["task"] + "/" + result["phase_file"]):
                selected.append((path, content))
            elif path.startswith((result["task"] + "/_rules/rules/", ".wally/rules/")):
                selected.append((path, content))
        documents = selected
        header += ("\nStartup outline only. Run `python3 .wally/scripts/sop_context.py` to read the full bound "
                   "workflow, gates, interaction rules and phase; this outline is not a read receipt.")
    return header + "\nDo not bypass SOP based on task simplicity. Read the following actual bound files before acting.\n" + "\n".join(
        "\n--- " + path + " ---\n" + content for path, content in documents)


def tool_kind(payload):
    name = str(payload.get("tool_name", "")).lower().split(".")[-1]
    if name in ("bash", "shell", "exec_command", "run_shell_command"):
        return "shell"
    if name in ("write", "edit", "multiedit", "write_file", "edit_file", "apply_patch"):
        return "edit"
    return "other"


def plain_document(root, value, inspect_file=True):
    """Recognize passive text docs, excluding agent/runtime control files."""
    try:
        path = inside(root, value)
        relative = path.relative_to(root)
        if any(c in relative.as_posix() for c in ("*", "?", "[", "]", ":", "\n", "\r")):
            return False
        parts = relative.parts
        if not parts or any(p == ".." for p in parts):
            return False
        if parts[0] in (".git", ".agents", ".codex", ".cursor", ".claude", ".codebuddy", ".windsurf", ".agent", "skills"):
            return False
        if parts[0] == ".wally" and (len(parts) < 3 or parts[1] != "docs"):
            return False
        passive_root = len(parts) == 1 and (
            relative.name.upper().startswith(("README", "CHANGELOG", "CONTRIBUTING", "HISTORY")) or
            relative.name.upper() in ("LICENSE", "NOTICE", "AUTHORS"))
        passive_tree = parts[0] == "docs" or parts[:2] == (".wally", "docs")
        if not (passive_root or passive_tree):
            return False
        if relative.suffix.lower() not in (".md", ".rst", ".txt", ".adoc", ""):
            return False
        for parent in (path, *path.parents):
            if parent == root:
                break
            if parent.is_symlink():
                return False
        if inspect_file and path.exists():
            if not path.is_file() or path.stat().st_mode & 0o111:
                return False
            data = path.read_bytes()
            if b"\0" in data:
                return False
            data.decode("utf-8")
        return True
    except (OSError, ValueError):
        return False



def checkpoint_issue(root, result, checkpoint):
    """Two explicit workflow exceptions, never a general command allowlist."""
    if not result or result.get("legacy"):
        return None
    task = root / result["task"]
    evidence = []
    gaps = []
    if checkpoint == "implement":
        for number, filename in (("01", "01-clarify.md"), ("02", "02-plan.md")):
            done = bool(re.search(r"(?m)^- \[x\] " + number + r"\.", result["overview"], re.I))
            actual = read(root, task / filename)
            template = read(root, str(Path(result["core"]).parent / "plans-template" / filename))
            evidence.append([done, actual, template])
            if not done or actual.strip() == template.strip():
                gaps.append(filename + (" is still an empty template" if actual.strip() == template.strip() else " is not recorded complete"))
    else:
        config = json.loads(read(root, task / "execution.json"))
        method = config.get(checkpoint, {})
        evidence.append(config)
        if not method_configured(method):
            gaps.append(checkpoint.upper() + " has no configured command or guide ready for execution; supply missing information: " + "; ".join(method.get("gaps", [])))
    if not gaps:
        return None
    scope = json.dumps([result["branch"], result["task"], result["core"], result["phase"], checkpoint])
    fingerprint = hashlib.sha256(json.dumps([scope, evidence], sort_keys=True).encode()).hexdigest()
    return {"scope": scope, "fingerprint": fingerprint, "checkpoint": checkpoint,
            "reason": "; ".join(gaps)}


def confirmation_state(root):
    # Local workflow bookkeeping, not proof of authentication or a security boundary.
    path = inside(root, ".wally/local/sop-confirmations.json")
    if not path.exists():
        return path, {"pending": {}, "approved": {}}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(isinstance(data.get(k), dict) for k in ("pending", "approved")):
        raise ValueError("Invalid SOP confirmation state")
    required = ("scope", "fingerprint", "checkpoint", "reason", "token")
    for scope, pending in data["pending"].items():
        if (not isinstance(pending, dict) or not all(isinstance(pending.get(k), str) for k in required)
                or pending["scope"] != scope or pending["checkpoint"] not in ("implement", "deploy", "it")):
            raise ValueError("Invalid pending SOP confirmation")
    if not all(isinstance(value, str) for value in data["approved"].values()):
        raise ValueError("Invalid approved SOP confirmation")
    return path, data


def save_confirmation_state(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + "." + secrets.token_hex(6) + ".tmp")
    try:
        temporary.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        temporary.replace(path)
    finally:
        # Path.unlink's "missing_ok" keyword requires Python 3.8; keep 3.7 compatibility.
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def require_confirmation(root, issue):
    if not issue:
        return ""
    try:
        path, data = confirmation_state(root)
        if data["approved"].get(issue["scope"]) == issue["fingerprint"]:
            return ""
        pending = data["pending"].get(issue["scope"])
        if not pending or pending.get("fingerprint") != issue["fingerprint"]:
            pending = dict(issue, token=secrets.token_hex(6))
            data["pending"][issue["scope"]] = pending
            save_confirmation_state(path, data)
    except (OSError, ValueError, KeyError) as exc:
        return ("SOP user confirmation required: " + issue["reason"] +
                ". Confirmation state could not be verified: " + str(exc) +
                ". Do not continue this operation or treat the error as approval.")
    return ("SOP user confirmation required: " + issue["reason"] +
            ". Explain the missing evidence and proposed action to the user. Ask them to reply exactly `CONFIRM SOP " +
            pending["token"] + "` in chat to continue this task/phase despite these gaps, or complete the prerequisites. "
            "Wait for their reply; do not retry, auto-confirm, or edit confirmation state. "
            "Confirmation permits continuation only; record the exception and never mark unverified work as passed.")


def accept_confirmation(root, result, prompt):
    # Prefer a dedicated line, but also accept prompts wrapped with CLI
    # system-reminders / leading prose (fullmatch used to drop those).
    text = str(prompt or "").strip()
    match = re.search(r"(?m)^\s*CONFIRM SOP ([0-9a-f]{12})\s*$", text, re.IGNORECASE)
    if not match:
        match = re.search(r"CONFIRM SOP ([0-9a-f]{12})", text, re.IGNORECASE)
    if not match:
        return ""
    path, data = confirmation_state(root)
    pending = next((p for p in data["pending"].values() if p.get("token") == match.group(1)), None)
    if pending and result:
        issue = checkpoint_issue(root, result, pending["checkpoint"])
        if issue and issue["scope"] == pending["scope"] and issue["fingerprint"] == pending["fingerprint"]:
            data["approved"][issue["scope"]] = issue["fingerprint"]
            del data["pending"][issue["scope"]]
            save_confirmation_state(path, data)
            return "User confirmed this SOP exception. Retry the checkpoint/operation. Record missing evidence honestly; this is not a passed gate."
    return "SOP confirmation is unknown or stale; rerun the checkpoint and request a new confirmation. No authorization was recorded."


def check_tool(root, payload, result):
    # Shell/MCP operations are advisory. Agents must run --checkpoint before
    # implementation or nonconfigured Deploy/IT; arbitrary Shell isn't parsed.
    if not result or result.get("legacy") or tool_kind(payload) != "edit":
        return ""
    data = payload.get("tool_input", {})
    if isinstance(data, str):
        data = json.loads(data)
    if not isinstance(data, dict):
        return ""
    paths = [data[k] for k in ("file_path", "filePath", "path") if isinstance(data.get(k), str)]
    patch = data.get("command", data.get("patch", data.get("input", "")))
    if isinstance(patch, str):
        paths.extend(re.findall(r"(?m)^\*\*\* (?:Add|Update|Delete) File: (.+)$", patch))
        paths.extend(re.findall(r"(?m)^\*\*\* Move to: (.+)$", patch))
    if not paths or all(plain_document(root, p) for p in paths):
        return ""
    task = root / result["task"]
    if all(is_relative_to(inside(root, p).resolve(), task.resolve()) for p in paths):
        return ""
    phase = result.get("role", result["phase"])
    checkpoint = {"01": "implement", "02": "implement", "03": "implement", "04": "deploy", "05": "it"}.get(phase)
    return require_confirmation(root, checkpoint_issue(root, result, checkpoint)) if checkpoint else ""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=".")
    parser.add_argument("--hook", action="store_true")
    parser.add_argument("--checkpoint", choices=("implement", "deploy", "it"))
    parser.add_argument("--client", choices=("codex", "codebuddy", "cursor", "claude"), default="codex")
    parser.add_argument("--event", default="PreToolUse")
    args = parser.parse_args()
    root = Path(args.repo).resolve()
    payload, result, error = {}, None, ""
    try:
        if args.hook:
            payload = json.load(sys.stdin)
            if not isinstance(payload, dict):
                raise ValueError("invalid hook payload")
        result = route(root)
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        error = "SOP context warning: " + str(exc)
    if not args.hook:
        if error:
            print(error)
            return 1
        if args.checkpoint:
            message = require_confirmation(root, checkpoint_issue(root, result, args.checkpoint))
            print(message or "SOP checkpoint ready (prerequisites satisfied or exception explicitly confirmed). This is not evidence of execution or a passed test.")
            return 3 if message else 0
        print(context_text(result))
        return 0
    event = args.event.lower()
    pre_tool = event == "pretooluse"
    denial, receipt = "", ""
    try:
        if event in ("userpromptsubmit", "beforesubmitprompt"):
            receipt = accept_confirmation(root, result, payload.get("prompt", ""))
        if pre_tool:
            denial = check_tool(root, payload, result)
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        error = "SOP context warning: " + str(exc)
    text = (("SOP context: task={task}; rules={core}; phase={phase}. "
             "Run --checkpoint implement/deploy/it before starting that work; general operations are advisory.").format(**result)
            if pre_tool and result else context_text(result, compact=True) if result else error)
    if not pre_tool:
        try:
            scope = read(root, ".wally/core/scope.md")
        except (OSError, ValueError):
            scope = "Classify the request first. General operations are advisory; only explicit SOP exceptions require confirmation."
        if error and "No SOP task for branch" in error:
            text = "No development task is bound. This is informational, not a blocker for consultation or repository operations."
        text = scope + "\n\nTask routing below applies only to development requests:\n" + text
    text += "\n" + receipt
    if error and result:
        text += "\n" + error
    if args.client == "cursor":
        if event == "beforesubmitprompt":
            output = {"continue": True, "user_message": receipt}
        elif pre_tool:
            output = ({"permission": "deny", "user_message": denial, "agent_message": denial}
                      if denial else {"permission": "allow"})
        else:
            output = {"additional_context": text}
    else:
        specific = {"hookEventName": args.event}
        if denial:
            specific.update(permissionDecision="deny", permissionDecisionReason=denial)
        else:
            specific["additionalContext"] = text
        output = {"hookSpecificOutput": specific}
    print(json.dumps(output, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        # A workflow hook failure must not become a blanket tool prohibition.
        if "--hook" in sys.argv:
            print("{}")
            sys.exit(0)
        print("SOP checkpoint failed: " + str(exc), file=sys.stderr)
        sys.exit(1)
