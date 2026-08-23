#!/usr/bin/env python3
"""Kuraka hook — orchestrator write guard (PreToolUse, matcher: Write|Edit|
MultiEdit|NotebookEdit).

Makes the hard invariant of skills/kuraka.md §Orchestrator constraint
structurally impossible instead of prose-enforced: the ORCHESTRATOR (the main
session — no agent_id in the hook input) never writes source files under the
project's configured code roots (backend_root / frontend_root / tests_root /
migrations_root). Implementation must route through backend-developer /
frontend-developer. Subagent writes pass through untouched (their own
tools/disallowedTools govern them), as do docs/config/.claude writes.

One-shot escape hatch for the documented, USER-APPROVED exception (≤5 LOC
post-review fix, kuraka-policies §Rate-limit): create the marker file
`.claude/hooks/ALLOW-ORCH-WRITE`; the hook consumes it and allows exactly one
write.

Fail-open: no kuraka.config.yaml, or no roots configured -> exit 0.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if data.get("agent_id") or data.get("agent_type"):
        return 0  # a subagent is writing — governed by its own tool config

    ti = data.get("tool_input") or {}
    fp = ti.get("file_path") or ti.get("notebook_path") or ""
    if not fp:
        return 0

    proj = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd())
    config = proj / "kuraka.config.yaml"
    if not config.is_file():
        return 0
    try:
        cfg = config.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return 0

    roots = []
    for m in re.finditer(
            r"^\s*(?:backend_root|frontend_root|tests_root|migrations_root):"
            r"\s*\"?([^\"\n#]+?)\"?\s*$", cfg, re.M):
        r = m.group(1).strip().strip("/")
        if r and r != ".":
            roots.append(r)
    if not roots:
        return 0

    try:
        rel = os.path.relpath(os.path.abspath(fp), proj)
    except Exception:
        return 0
    rel = rel.replace(os.sep, "/")
    if rel.startswith(".."):
        return 0  # outside the project — not ours to police

    hit = next((r for r in roots if rel == r or rel.startswith(r + "/")), None)
    if not hit:
        return 0

    marker = proj / ".claude" / "hooks" / "ALLOW-ORCH-WRITE"
    if marker.is_file():
        try:
            marker.unlink()
        except Exception:
            pass
        return 0  # one user-approved exception consumed

    sys.stderr.write(
        f"BLOCKED by Kuraka orchestrator-guard hook: `{rel}` is under the code root "
        f"`{hit}/`, and the ORCHESTRATOR never writes source files — all "
        f"implementation routes through `backend-developer` / `frontend-developer` "
        f"(skills/kuraka.md §Orchestrator constraint; editing docs/, .claude/ and "
        f"process artifacts stays allowed).\n"
        f"If this is the documented USER-APPROVED exception (≤5 LOC precise fix, "
        f"announced first — kuraka-policies §Rate-limit), have the user approve and "
        f"run: touch .claude/hooks/ALLOW-ORCH-WRITE  (allows exactly ONE write, then "
        f"a mandatory re-review by the owning agent).\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
