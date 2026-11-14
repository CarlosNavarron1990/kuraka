#!/usr/bin/env python3
"""Local evidence for Codex Ultra Ahorro; no model calls or permission changes."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def inside(root, relative):
    path = Path(relative)
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("Expected a project-relative path")
    resolved = (root / path).resolve()
    if resolved == root or root not in resolved.parents:
        raise ValueError("Path escapes the project")
    return resolved


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def snapshot(root, state):
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root, capture_output=True, check=True,
    )
    names = set(os.fsdecode(result.stdout).split("\0")) - {""}
    names.update(state["allowed_files"])
    ignored = set(state["artifacts"])
    files = {}
    for name in sorted(names):
        if name.startswith(".codex/ultra-ahorro/") or name in ignored:
            continue
        path = root / name
        # Hash the link itself; never read data outside the project through it.
        if path.is_symlink():
            data = os.fsencode(os.readlink(path))
        elif path.is_file():
            inside(root, name)
            data = path.read_bytes()
        elif path.is_dir():
            raise ValueError(f"Directory/submodule needs a regular workflow: {name}")
        else:
            continue
        mode = path.lstat().st_mode & 0o777
        files[name] = hashlib.sha256(str(mode).encode() + b"\0" + data).hexdigest()
    return files


def fingerprint(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()


def changed_files(state, current):
    baseline = state["baseline"]
    return sorted(name for name in baseline.keys() | current.keys()
                  if baseline.get(name) != current.get(name))


def load_state(root, cycle):
    if not re.fullmatch(r"REQ-\d{8}-AHORRO-[a-f0-9]{12}", cycle):
        raise ValueError("Invalid cycle ID")
    path = inside(root, f".codex/ultra-ahorro/{cycle}/state.json")
    state = json.loads(path.read_text(encoding="utf-8"))
    if state["project_root"] != str(root) or state["cycle_id"] != cycle:
        raise ValueError("Cycle belongs to another project")
    return path, state


def start(root, args):
    git_root = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root,
                              capture_output=True, text=True, check=True).stdout.strip()
    if Path(git_root).resolve() != root:
        raise ValueError("--project must be the Git root")
    if not (root / "kuraka.config.yaml").is_file():
        raise ValueError("Missing kuraka.config.yaml; onboard the project first")
    docs = inside(root, args.docs_root).relative_to(root).as_posix()
    if docs.split("/")[0] in (".git", ".codex"):
        raise ValueError("Process artifacts must be outside .git and .codex")
    allowed = []
    for name in args.files:
        path = inside(root, name)
        if path.is_dir() or (root / name).is_symlink():
            raise ValueError("Scope must list individual non-symlink files")
        relative = path.relative_to(root).as_posix()
        if relative.startswith((".git/", ".codex/")):
            raise ValueError("Framework/config changes need a regular workflow")
        allowed.append(relative)
    cycle = f"REQ-{datetime.now(timezone.utc):%Y%m%d}-AHORRO-{uuid4().hex[:12]}"
    state = {
        "cycle_id": cycle, "project_root": str(root), "mode": "ultra-ahorro",
        "status": "active", "started_at": now(), "objective": args.objective,
        "allowed_files": sorted(set(allowed)), "checks": [],
        "artifacts": [f"{docs}/agent-retrospectives/RETRO-{cycle}.md",
                      f"{docs}/agent-telemetry/{cycle}-telemetry.json"],
    }
    path = inside(root, f".codex/ultra-ahorro/{cycle}/state.json")
    state["baseline"] = snapshot(root, state)
    for name in state["allowed_files"]:
        source = root / name
        if source.is_file():
            saved = path.parent / "baseline" / name
            saved.parent.mkdir(parents=True, exist_ok=True)
            saved.write_bytes(source.read_bytes())
    write_json(path, state)
    return {"cycle": cycle, "status": "active", "files": state["allowed_files"]}


def close(root, path, state, args, current):
    if state["status"] == "closed":
        return {"cycle": args.cycle, "status": "closed", "artifacts": state["artifacts"]}
    changed = changed_files(state, current)
    outside = set(changed) - set(state["allowed_files"])
    if outside:
        raise ValueError("Out-of-scope changes: " + ", ".join(sorted(outside)))
    # The latest run of EACH selected command must be green on the final files.
    checks = {tuple(c["command"]): c for c in state["checks"]}
    if not checks or any(c["exit_code"] != 0 or c["fingerprint"] != fingerprint(current)
                         for c in checks.values()):
        raise ValueError("Missing, failed or stale checks; verify the final files")
    retro, telemetry = [inside(root, name) for name in state["artifacts"]]
    retro.parent.mkdir(parents=True, exist_ok=True)
    ended = now()
    run = {"phase": "U", "agent": "codex-main", "attempt": 1,
           "status": "ok", "model": None, "total_tokens": None,
           "tool_uses": None, "duration_ms": None,
           "started_at": state["started_at"], "ended_at": ended,
           "artifacts": state["artifacts"], "usage_source": "unavailable"}
    write_json(telemetry, {"req_name": args.cycle, "mode": "ultra-ahorro",
                          "status": "ok", "subagents": 0,
                          "subagents_source": "workflow-contract-not-measured",
                          "runs": [run], "checks": list(checks.values())})
    evidence = "\n".join(f"- `{json.dumps(c['command'], ensure_ascii=False)}`: exit 0"
                         for c in checks.values())
    retro.write_text(
        f"# {args.cycle}\n\nMode: ultra-ahorro (Codex, self-reviewed).\n\n"
        f"## Objective\n\n{state['objective']}\n\n## Result\n\n{args.summary}\n\n"
        f"## Changed files\n\n" + "\n".join(f"- `{n}`" for n in changed)
        + f"\n\n## Verification\n\n{evidence}\n\n"
        f"Token consumption unavailable; zero subagents is the workflow contract.\n\n"
        f"## Confidence: {args.confidence}\n", encoding="utf-8")
    state.update(status="closed", ended_at=ended, changed_files=changed)
    write_json(path, state)
    return {"cycle": args.cycle, "status": "closed", "artifacts": state["artifacts"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    sub = parser.add_subparsers(dest="action", required=True)
    begin = sub.add_parser("start")
    begin.add_argument("--docs-root", required=True)
    begin.add_argument("--objective", required=True)
    begin.add_argument("--files", nargs="+", required=True)
    for name in ("status", "check", "close", "abort"):
        action = sub.add_parser(name)
        action.add_argument("--cycle", required=True)
        if name == "check":
            action.add_argument("command", nargs=argparse.REMAINDER)
        if name == "close":
            action.add_argument("--summary", required=True)
            action.add_argument("--confidence", choices=("HIGH", "MEDIUM", "LOW"), required=True)
        if name == "abort":
            action.add_argument("--reason", required=True)
    args = parser.parse_args()
    root = args.project.resolve()
    try:
        if args.action == "start":
            output = start(root, args)
        else:
            path, state = load_state(root, args.cycle)
            if args.action == "status":
                current = snapshot(root, state)
                changed = changed_files(state, current)
                output = {"cycle": args.cycle, "status": state["status"],
                          "changed_files": changed,
                          "out_of_scope": sorted(set(changed) - set(state["allowed_files"]))}
            elif state["status"] != "active" and not (
                    args.action == "close" and state["status"] == "closed"):
                raise ValueError("Cycle is no longer active")
            elif args.action == "abort":
                state.update(status="aborted", reason=args.reason, ended_at=now())
                write_json(path, state)
                output = {"cycle": args.cycle, "status": "aborted", "edits_preserved": True}
            elif args.action == "check":
                command = args.command[1:] if args.command[:1] == ["--"] else args.command
                if not command:
                    raise ValueError("Provide a verification command after --")
                before = fingerprint(snapshot(root, state))
                log = path.parent / f"check-{len(state['checks']) + 1}.log"
                with log.open("w", encoding="utf-8") as stream:
                    result = subprocess.run(command, cwd=root, stdout=stream, stderr=stream)
                check = {"command": command, "exit_code": result.returncode,
                         "fingerprint": before, "log": str(log.relative_to(root))}
                state["checks"].append(check)
                write_json(path, state)
                with log.open("rb") as stream:
                    stream.seek(max(0, log.stat().st_size - 2000))
                    tail = stream.read().decode("utf-8", errors="replace")
                print(json.dumps({**check, "output_tail": tail}, ensure_ascii=False))
                return 0 if result.returncode == 0 else 1
            else:
                output = close(root, path, state, args, snapshot(root, state))
        print(json.dumps(output, ensure_ascii=False))
        return 0
    except (OSError, ValueError, KeyError, subprocess.CalledProcessError) as exc:
        print(f"Ultra Ahorro: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
