#!/usr/bin/env python3
"""Kuraka hook — gate command integrity (PreToolUse, matcher: Bash).

Enforces rule T7 deterministically: a GATE command (the project's test_cmd /
lint_cmd / typecheck_cmd from kuraka.config.yaml) must never be piped — the
shell reports the LAST command's exit code, so `make test | tail` reads a
failing suite as green (REQ-20260611 S3 advanced on exactly that false green).

Blocks (exit 2) any Bash command that pipes a configured gate command, with
the fix in stderr. Escape hatch for a deliberate, user-approved exception:
include the literal marker KURAKA_GATE_PIPE_OK in the command.

Fail-open: no config, unparseable input, or gate not present -> exit 0.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


def _has_pipe_after(cmd: str, start: int) -> bool:
    i = start
    while i < len(cmd):
        c = cmd[i]
        if c == "|":
            if i + 1 < len(cmd) and cmd[i + 1] == "|":  # logical OR, not a pipe
                i += 2
                continue
            if i > 0 and cmd[i - 1] == "|":
                i += 1
                continue
            if i > 0 and cmd[i - 1] == ">":  # >| clobber redirect
                i += 1
                continue
            return True
        i += 1
    return False


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    cmd = (data.get("tool_input") or {}).get("command") or ""
    if not cmd or "KURAKA_GATE_PIPE_OK" in cmd:
        return 0

    proj = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd())
    config = proj / "kuraka.config.yaml"
    if not config.is_file():
        return 0

    try:
        cfg = config.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return 0
    gates = []
    for m in re.finditer(r"^\s*(?:test_cmd|lint_cmd|typecheck_cmd):\s*\"?([^\"\n#]+?)\"?\s*$",
                         cfg, re.M):
        g = m.group(1).strip()
        if len(g) > 2:
            gates.append(g)

    for g in gates:
        idx = cmd.find(g)
        if idx == -1:
            continue
        if _has_pipe_after(cmd, idx + len(g)):
            sys.stderr.write(
                f"BLOCKED by Kuraka gate-integrity hook (rule T7): the gate command "
                f"`{g}` is piped, so the shell would report the PIPE's exit code and a "
                f"failing suite can read as green (this shipped a false green in "
                f"REQ-20260611).\n"
                f"Fix: run the gate command UNPIPED and assert on its own exit code; if "
                f"you must trim output, redirect to a file and read the file "
                f"(`{g} > /tmp/gate.log 2>&1; echo exit=$?`).\n"
                f"Deliberate exception (user-approved only): append the comment "
                f"marker KURAKA_GATE_PIPE_OK to the command.\n"
            )
            return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
