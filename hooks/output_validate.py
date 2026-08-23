#!/usr/bin/env python3
"""Kuraka hook — output validator (SubagentStop).

Replaces the prose `verify-output` tail (each agent re-reading the 207-line
output-schemas.md at the end of EVERY phase) with a deterministic, zero-token
structural check on the subagent's final message. Conservative by design: it
checks only the universal contract (the `Confidence` line) plus the verdict
line for reviewer agents — the deep per-section schema stays documented in
output-schemas.md for humans and non-Claude platforms.

If a required marker is missing, exit 2 blocks the stop and feeds the missing
list back so the agent re-emits its final report once. Loop-guarded: it never
blocks the same agent twice (stop_hook_active / one-shot marker), and unknown
agent types always pass.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

REQUIRED: dict[str, list[str]] = {
    "po-analyst": ["Confidence"],
    "story-refiner": ["Confidence"],
    "architect-reviewer": ["Verdict:", "Confidence"],
    "code-reviewer": ["Verdict:", "Confidence"],
    "security-reviewer": ["Verdict:", "Confidence"],
    "migration-reviewer": ["Verdict:", "Confidence"],
    "backend-developer": ["Confidence"],
    "frontend-developer": ["Confidence"],
    "test-engineer": ["Confidence"],
    "e2e-tester": ["Confidence"],
    "deployment-verifier": ["Confidence"],
    "final-auditor": ["Confidence"],
    "pattern-detector": ["Confidence"],
}


def _last_assistant_text(transcript: Path) -> str:
    text = ""
    try:
        with transcript.open(encoding="utf-8", errors="ignore") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                msg = obj.get("message") if isinstance(obj.get("message"), dict) else obj
                if (obj.get("type") == "assistant" or msg.get("role") == "assistant"):
                    content = msg.get("content")
                    if isinstance(content, str):
                        text = content
                    elif isinstance(content, list):
                        parts = [c.get("text", "") for c in content
                                 if isinstance(c, dict) and c.get("type") == "text"]
                        if parts:
                            text = "\n".join(parts)
    except Exception:
        return ""
    return text


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if data.get("stop_hook_active"):
        return 0  # already continued once because of this hook — never loop

    agent = data.get("agent_type") or ""
    req = REQUIRED.get(agent)
    if not req:
        return 0

    proj = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd())
    if not (proj / "kuraka.config.yaml").is_file():
        return 0

    # one-shot guard (belt and braces alongside stop_hook_active)
    agent_id = re.sub(r"[^A-Za-z0-9_-]", "", str(data.get("agent_id") or ""))
    marker = None
    if agent_id:
        marker = proj / ".claude" / "hooks" / f".ov-{agent_id}"
        if marker.is_file():
            return 0

    tp = data.get("transcript_path")
    if not tp:
        return 0
    text = _last_assistant_text(Path(tp))
    if not text:
        return 0  # cannot judge — never block blind

    missing = [s for s in req if s not in text]
    if not missing:
        return 0

    if marker is not None:
        try:
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("1")
        except Exception:
            pass
    sys.stderr.write(
        f"Kuraka output-validate hook: your final report is missing required "
        f"element(s): {', '.join(missing)}. Re-emit your COMPLETE final report "
        f"including them (contract: .claude/agents/contexts/output-schemas.md"
        f"#{agent}), then end your turn.\n"
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
