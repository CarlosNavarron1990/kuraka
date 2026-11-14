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


# Usage keys as the harness may emit them. The PostToolUse payload for Task/Agent
# carries a STRUCTURED tool_response (camelCase: totalTokens / totalToolUseCount /
# totalDurationMs); async hand-backs carry a <usage> XML block (snake_case). The
# first version only regex-scraped snake_case off the serialized blob, so 100% of
# rows logged total_tokens/duration_ms null in 6 projects (guai, azure, possuite,
# sie-integraciones, petsuite, piscosdalston) — the Phase-7 cross-check could
# confirm a run happened but never what it cost.
_USAGE_KEYS = {
    "total_tokens": ("totalTokens", "total_tokens", "subagent_tokens", "subagentTokens"),
    "tool_uses": ("totalToolUseCount", "tool_uses", "toolUses", "tool_use_count"),
    "duration_ms": ("totalDurationMs", "duration_ms", "durationMs"),
}


def _as_int(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return int(v)
    if isinstance(v, str) and v.strip().isdigit():
        return int(v.strip())
    return None


def _walk(obj, depth=0):
    if depth > 6:
        return
    if isinstance(obj, dict):
        yield obj
        for v in obj.values():
            yield from _walk(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk(v, depth + 1)


def extract_usage(resp, blob: str) -> dict:
    """Structured fields first (any nesting), then <usage> XML tags, then a
    `key: N` regex over the blob. Never raises; missing stays None (null, not 0)."""
    out = {k: None for k in _USAGE_KEYS}
    try:
        parsed = resp
        if isinstance(resp, str):
            try:
                parsed = json.loads(resp)
            except Exception:
                parsed = None
        for d in _walk(parsed):
            for field, keys in _USAGE_KEYS.items():
                if out[field] is not None:
                    continue
                for k in keys:
                    if k in d:
                        iv = _as_int(d[k])
                        if iv is not None:
                            out[field] = iv
                            break
    except Exception:
        pass
    for field, keys in _USAGE_KEYS.items():
        if out[field] is not None:
            continue
        for k in keys:
            mm = re.search(rf"<{k}>\s*(\d+)\s*</{k}>", blob) or \
                 re.search(rf"[\"']?{k}[\"']?\s*[:=]\s*(\d+)", blob)
            if mm:
                out[field] = int(mm.group(1))
                break
    return out


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

    usage = extract_usage(resp, blob)

    entry = {
        "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "hook",
        "agent": ti.get("subagent_type"),
        "description": ti.get("description"),
        "model": ti.get("model"),
        "total_tokens": usage["total_tokens"],
        "tool_uses": usage["tool_uses"],
        "duration_ms": usage["duration_ms"],
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
