#!/usr/bin/env python3
"""Kuraka hook — RETRO file contract (PostToolUse, matcher: Write).

The `## Confidence: HIGH|MEDIUM|LOW` line of a RETRO **file** is what
`kuraka-backup.py::find_verdict` parses into `cycles/<REQ>/meta.yaml` and into
the cross-project `projects/INDEX.md` that `pattern-detector` reads. Without it
the cycle is archived but counts for nothing in any comparison.

Until 2026-08-31 nothing enforced it on the file: `output_validate.py` checks the
agent's RESPONSE, and the RETRO template never asked for it. Result across the
store: only 58 of 189 archived cycles had a verdict — 35 missing in a pure-Claude
project, all 16 of an Antigravity one.

Fires when a RETRO is written, before the cycle closes. exit 2 feeds the miss
back so the agent appends the line to the file it just wrote.

Loop-guarded (never blocks the same file twice), fail-open on anything
unexpected, and inert outside a Kuraka project.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

CONFIDENCE_RE = re.compile(r"^##\s*Confidence:\s*(HIGH|MEDIUM|LOW)\b", re.M | re.I)
# a partial first write is not a violation — only judge something retro-shaped
MIN_RETRO_CHARS = 400


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0
    if data.get("tool_name") not in ("Write", None):
        return 0

    proj = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd())
    if not (proj / "kuraka.config.yaml").is_file():
        return 0  # not a Kuraka project

    raw = (data.get("tool_input") or {}).get("file_path") or ""
    if not raw:
        return 0
    path = Path(raw)
    if not path.name.startswith("RETRO-") or path.suffix != ".md":
        return 0
    if path.name == "RETRO-LATEST.md":
        return 0  # a copy of the real one — judged at its source

    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 0
    if len(text) < MIN_RETRO_CHARS or CONFIDENCE_RE.search(text):
        return 0

    marker = proj / ".claude" / "hooks" / f".rc-{path.stem}"
    if marker.is_file():
        return 0  # already asked once for this RETRO — never loop
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("1", encoding="utf-8")
    except OSError:
        pass

    print(
        f"RETRO incompleto: {path.name} no tiene la línea de veredicto.\n"
        "Agregá como ÚLTIMA línea del archivo:\n"
        "    ## Confidence: HIGH | MEDIUM | LOW\n"
        "No es decoración: kuraka-backup la parsea hacia cycles/<REQ>/meta.yaml y "
        "hacia projects/INDEX.md — sin ella el ciclo se archiva pero queda invisible "
        "para pattern-detector.",
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
