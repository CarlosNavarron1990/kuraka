#!/usr/bin/env python3
"""Kuraka hook — telemetry appender (PostToolUse, matcher: Task).

Fires after every subagent invocation and appends one JSONL entry to
<docs_process_root>/agent-telemetry/HOOK-LOG.jsonl, deterministically and at
zero model cost. This guarantees telemetry COMPLETENESS (the framework's #1
documented regression: REQ-20260801 recorded 19 of 31 runs; the cycle's real
cost was +57% over the reported one). The orchestrator's job is now to ENRICH
(phase, budget_ok, tokens_incremental) and consolidate into the REQ's curated
telemetry JSON — never to remember to capture.

Fail-open by design: any unexpected input exits 0. Only active in projects
with a kuraka.config.yaml.
"""
from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if data.get("tool_name") not in (None, "Task", "Agent"):
        return 0

    proj = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd())
    config = proj / "kuraka.config.yaml"
    if not config.is_file():
        return 0  # not a Kuraka project

    try:
        cfg = config.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        cfg = ""
    m = re.search(r"docs_process_root:\s*\"?([^\"\n#]+?)\"?\s*$", cfg, re.M)
    docs_root = (m.group(1).strip() if m else "docs/process").strip("/")

    ti = data.get("tool_input") or {}
    resp = data.get("tool_response")
    blob = ""
    try:
        blob = resp if isinstance(resp, str) else json.dumps(resp, ensure_ascii=False)
    except Exception:
        pass

    def _num(key: str):
        mm = re.search(rf"{key}\D{{0,4}}(\d+)", blob)
        return int(mm.group(1)) if mm else None

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "hook",
        "agent": ti.get("subagent_type"),
        "description": ti.get("description"),
        "model": ti.get("model"),
        "total_tokens": _num("total_tokens") or _num("subagent_tokens"),
        "tool_uses": _num("tool_uses"),
        "duration_ms": _num("duration_ms"),
        "session_id": data.get("session_id"),
    }

    try:
        outdir = proj / docs_root / "agent-telemetry"
        outdir.mkdir(parents=True, exist_ok=True)
        with (outdir / "HOOK-LOG.jsonl").open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
