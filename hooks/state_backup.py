#!/usr/bin/env python3
"""Kuraka hook — continuous state backup (SubagentStop + Stop).

Phase 7 used to be the ONLY moment a cycle reached the central store. A cycle
that never closed left nothing behind: azure REQ-20261110-GUAI-3141 (REQ, 6
stories, test plan, telemetry) existed only in the working tree, and GitHub
Desktop then swept it into a stash on the next branch switch. This hook runs
`kuraka-backup.py <root> --state-only` (incremental layer + docs/process
snapshot, never deletes, no closure check) after subagents and at the end of a
turn, so the store always holds the in-flight cycle.

Throttled: at most once every THROTTLE_S per project (marker
`.claude/.kuraka-state-backup.stamp`, excluded locally by the mount). Fail-open:
no config, no vault, a timeout or any error exits 0 silently. Never blocks.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

DEFAULT_VAULT = "/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka"
THROTTLE_S = 600
TIMEOUT_S = 20
STAMP = ".kuraka-state-backup.stamp"


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}
    proj = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd())
    if not (proj / "kuraka.config.yaml").is_file():
        return 0
    stamp = proj / ".claude" / STAMP
    try:
        if stamp.is_file() and time.time() - stamp.stat().st_mtime < THROTTLE_S:
            return 0
    except OSError:
        return 0
    vault = Path(os.environ.get("KURAKA_VAULT") or DEFAULT_VAULT)
    backup = vault / "kuraka-backup.py"
    if not backup.is_file():
        return 0
    try:
        stamp.parent.mkdir(parents=True, exist_ok=True)
        stamp.write_text(str(int(time.time())), encoding="utf-8")
    except OSError:
        return 0
    try:
        subprocess.run(
            [sys.executable, str(backup), str(proj), "--state-only",
             "--target", "claude", "--vault", str(vault)],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=TIMEOUT_S, check=False,
        )
    except (OSError, subprocess.SubprocessError):
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
