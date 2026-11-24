#!/usr/bin/env python3
"""Create a task bound to immutable SOP rules and a project policy snapshot."""
import argparse
from datetime import datetime
import json
from pathlib import Path
import re
import tempfile


def is_relative_to(path, root):
    """Containment check that works on every Python 3 (Path.is_relative_to is 3.9+)."""
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def method_configured(method):
    """Pending setup guides are not execution methods; retain legacy config semantics."""
    return (method.get("readiness") != "pending" and
            any(str(method.get(key) or "").strip() for key in ("command", "guide")))


def execution_config(root):
    """Read customer-owned execution methods; do not execute or infer them."""
    path = Path(root) / ".wally/config.json"
    if not is_relative_to(path.resolve(), Path(root).resolve()):
        raise ValueError("execution configuration escapes repository")
    if path.is_symlink() and not path.exists():
        raise ValueError("broken execution configuration link")
    if path.exists():
        config = json.loads(path.read_text(encoding="utf-8"))
    else:
        config = {"schema": 1,
                  "deploy": {"command": "", "guide": "", "verify": "", "rollback": ""},
                  "it": {"command": "", "guide": "", "success_criteria": ""}}
    if not isinstance(config, dict) or config.get("schema") != 1:
        raise ValueError("invalid execution configuration schema")
    for phase in ("deploy", "it"):
        method = config.get(phase, {})
        if not isinstance(method, dict) or any(not isinstance(method.get(key, ""), str)
                                              for key in ("command", "guide", "verify", "rollback", "success_criteria")):
            raise ValueError("invalid execution method: " + phase)
        if method.get("readiness") not in (None, "pending", "ready"):
            raise ValueError("invalid execution readiness: " + phase)
        if "gaps" in method and (not isinstance(method["gaps"], list) or
                                 any(not isinstance(item, str) for item in method["gaps"])):
            raise ValueError("invalid execution gaps: " + phase)
        if method.get("readiness") == "ready" and not method_configured(method):
            raise ValueError("ready execution method requires a command or guide: " + phase)
    return config


def templates(directory, steps, rule_root):
    if steps != 6:
        raise ValueError("new task templates must retain all six phases")
    result = {}
    for path in sorted(directory.rglob("*")):
        if not path.is_file():
            continue
        name = path.relative_to(directory).as_posix()
        text = path.read_text(encoding="utf-8").replace("{{STEPS}}", str(steps)).replace("{{RULE_ROOT}}", rule_root)
        result[name] = text
    return result


def create(root, name, branch):
    root = Path(root).resolve()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}_[\w.-]+", name) or name.endswith("."):
        raise ValueError("task name must be YYYY-MM-DD_title without path separators")
    datetime.strptime(name[:10], "%Y-%m-%d")
    if not branch or any(c in branch for c in "|`\n\r") or branch in ("main", "master", "HEAD"):
        raise ValueError("supply the actual non-default task branch")

    def inside(rel):
        path = root / rel
        if not is_relative_to(path.resolve(), root):
            raise ValueError("path escapes repository: " + str(rel))
        return path

    state = json.loads(inside(".wally/install-state.json").read_text())
    if state.get("translation_sources"):
        raise ValueError("finish pending project translations before creating a new task")
    if state.get("schema") != 2 or state.get("steps") != 6:
        raise ValueError("upgrade SOP initialization before creating six-phase tasks")
    revision = state["revision"]
    if not re.fullmatch(r"[0-9a-f]{16}", revision):
        raise ValueError("invalid SOP revision")
    rule_root = ".wally/versions/" + revision
    for filename in ("workflow.md", "gates.md", "interaction.md", "clarify.md"):
        if not inside(rule_root + "/core/" + filename).is_file():
            raise ValueError("missing bound SOP rule: " + filename)
    task = inside(".wally/plans/" + name)
    if task.exists():
        raise ValueError("task already exists: " + name)
    for overview in task.parent.glob("*/00-overview.md"):
        if overview.parent.name == "_template":
            continue
        # Read only the discovery key, not historical design or evidence.
        match = re.search(r"(?m)^\|\s*(?:Branch|\u5206\u652f)\s*\|\s*`?([^|`\n]+)`?\s*\|", inside(overview.relative_to(root)).read_text())
        if match and match.group(1).strip() == branch:
            raise ValueError("branch already belongs to task: " + overview.parent.name)
    files = templates(inside(rule_root + "/plans-template"), state["steps"], rule_root)
    if "00-overview.md" not in files:
        raise ValueError("missing bound overview template")
    # Verify the shared project profile exists; tasks reference .wally/profiles/project.md directly.
    inside(".wally/profiles/project.md").read_text()
    language = state.get("language", "zh")
    overview = files["00-overview.md"].replace("[YYYY-MM-DD] <Task title>", name).replace("[YYYY-MM-DD] <\u4efb\u52a1\u6807\u9898>", name)
    overview = overview.replace("`feature/xxx`", "`" + branch + "`").replace("| Created | YYYY-MM-DD |", "| Created | " + name[:10] + " |")
    overview = overview.replace("| \u521b\u5efa\u65e5\u671f | YYYY-MM-DD |", "| \u521b\u5efa\u65e5\u671f | " + name[:10] + " |")
    config = execution_config(root)
    files["execution.json"] = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
    decided_at = datetime.now().astimezone().isoformat(sep=" ", timespec="seconds")
    for number, phase, title in (("04", "deploy", "Deploy"), ("05", "it", "IT")):
        method = config.get(phase, {})
        configured = method_configured(method)
        status = "BLOCKED" if method.get("readiness") == "pending" else ("PENDING" if configured else "SKIPPED")
        reason = ("Customer execution method is configured; execute it when this phase is reached."
                  if configured else "No customer execution method is configured; not executed or verified.")
        if language == "zh":
            reason = ("\u5df2\u914d\u7f6e\u5ba2\u6237\u6267\u884c\u65b9\u6cd5\uff0c\u8fdb\u5165\u672c\u9636\u6bb5\u65f6\u6267\u884c\u3002"
                      if configured else "\u5ba2\u6237\u672a\u914d\u7f6e\u6267\u884c\u65b9\u6cd5\uff0c\u81ea\u52a8\u8df3\u8fc7\uff1b\u672a\u6267\u884c\u6216\u9a8c\u8bc1\u3002")
        if method.get("readiness") == "pending":
            reason = "Required execution setup is incomplete; request missing information from the user."
        header = ("Execution status" if language == "en" else "\u6267\u884c\u72b6\u6001")
        annotation = ("\n\n## " + header + "\n\n- Status: " + status + "\n- Reason: " + reason +
                      "\n- Configuration snapshot: `./execution.json` → `" + phase + "`\n")
        if method.get("readiness") == "pending":
            annotation += "- Setup pending; request missing information from the user: " + "; ".join(method.get("gaps", [])) + "\n"
        if not configured and method.get("readiness") != "pending":
            annotation += "- Skip decision at task creation: " + decided_at + "\n"
            overview = overview.replace("- [ ] " + number + ". " + title,
                                        "- [x] " + number + ". " + title + " [SKIPPED: not configured]")
            overview = re.sub(r"(?m)^\| " + number + r" \| " + title + r" \|.*$",
                              "| " + number + " | " + title + " | " + decided_at + " | " + decided_at +
                              " | 0s | 0 | SKIPPED: not configured; decision time, not execution |", overview)
        filename = number + ("-deploy.md" if phase == "deploy" else "-it.md")
        heading, body = files[filename].split("\n", 1)
        files[filename] = heading + annotation + "\n" + body
    files["00-overview.md"] = overview
    # Prepare all data before creating the task directory. Rename exposes it as one unit.
    task.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".new-task-", dir=task.parent) as staging:
        staged = Path(staging) / name
        staged.mkdir()
        for rel, text in files.items():
            path = staged / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        if task.exists():
            raise ValueError("task appeared while preparing: " + name)
        staged.rename(task)
    print("Created " + str(task) + " (SOP 2.0 / " + revision + ")")
    return task


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("--branch", required=True)
    parser.add_argument("--repo-root", default=".")
    args = parser.parse_args()
    try:
        create(args.repo_root, args.name, args.branch)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, "[ERROR] " + str(error) + "\n")


if __name__ == "__main__":
    main()
