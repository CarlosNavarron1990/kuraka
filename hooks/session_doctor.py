#!/usr/bin/env python3
"""Kuraka hook — state health check at session start (SessionStart).

Runs `kuraka-doctor.py --brief` against the project and surfaces its findings as
context, so a broken Kuraka state is visible BEFORE a cycle starts instead of
being discovered months later in the vault (2026-08: 5 projects running with no
kuraka.config.yaml, a whole agent suite mis-snapshotted as "overrides",
telemetry never attached, one project's history split across two slugs).

Report only — it never repairs and never blocks a session; the fix is
`kuraka-doctor.py --fix` (or a `--update` re-mount), and the operator decides.

Fail-open by design: no vault, no config, a timeout or any unexpected input all
exit 0 silently. Inert outside a Kuraka project.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

DEFAULT_VAULT = "/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka"
TIMEOUT_S = 25


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}

    proj = Path(os.environ.get("CLAUDE_PROJECT_DIR") or data.get("cwd") or os.getcwd())
    if not (proj / "kuraka.config.yaml").is_file():
        # No config is itself a finding, but only for a project that HAS a mount.
        if not any((proj / f".{p}" / "agents").is_dir()
                   for p in ("claude", "agents", "codex", "cursor")):
            return 0  # not a Kuraka project at all

    vault = Path(os.environ.get("KURAKA_VAULT") or DEFAULT_VAULT)
    doctor = vault / "kuraka-doctor.py"
    if not doctor.is_file():
        return 0

    try:
        r = subprocess.run(
            [sys.executable, str(doctor), str(proj), "--brief", "--vault", str(vault)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=TIMEOUT_S,
        )
    except (OSError, subprocess.SubprocessError):
        return 0

    if r.returncode == 0:
        return 0  # healthy — say nothing, a session start is not a report

    out = (r.stdout or "").strip()
    if out:
        print("Kuraka — estado del proyecto (kuraka-doctor):")
        print(out)
        print("Arreglo: python3 \"%s\" \"%s\" --fix" % (doctor, proj))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
