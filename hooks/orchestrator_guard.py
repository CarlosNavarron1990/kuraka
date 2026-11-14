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

Standing exception for the USER-SELECTED **Ultra Ahorro** mode
(skills/kuraka-ahorro.md), where the main session IS the implementer: a write is
allowed when an active scope declaration in `.claude/ultra-ahorro/<cycle>.json`
names exactly this file. The first such write binds the cycle to the calling
session (`<cycle>.owner`, created O_EXCL from the real hook payload), so a second
session never inherits it; any status other than `active` revokes it at once.
The exception is per file and per session — never a global allow-file — and it
does not extend to shell writes, which the mode reviews in the final diff.

Fail-open: no kuraka.config.yaml, or no roots configured -> exit 0.
"""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

CYCLE_RE = re.compile(r"REQ-\d{8}-AHORRO-[A-Za-z0-9_-]{1,32}")


def _ultra_ahorro_allows(proj: Path, target: str, session: str) -> bool:
    """True when an ACTIVE Ultra Ahorro cycle owned by `session` declares
    `target` (an absolute, symlink-resolved path) in its allowed_files."""
    if not session:
        return False  # no verified session identity -> no exception
    root = proj / ".claude" / "ultra-ahorro"
    if not root.is_dir():
        return False
    for decl in sorted(root.glob("*.json")):
        try:
            state = json.loads(decl.read_text(encoding="utf-8"))
        except Exception:
            continue  # corrupt declaration grants nothing
        cycle = state.get("cycle_id")
        if (state.get("mode") != "ultra-ahorro" or state.get("status") != "active"
                or cycle != decl.stem or not CYCLE_RE.fullmatch(str(cycle))):
            continue
        allowed = state.get("allowed_files")
        if not isinstance(allowed, list):
            continue
        for entry in allowed:
            if (not isinstance(entry, str) or not entry or os.path.isabs(entry)
                    or ".." in entry.replace(os.sep, "/").split("/")):
                continue  # a malformed entry is ignored, never expanded
            if os.path.realpath(os.path.join(proj, entry)) != target:
                continue
            owner = root / f"{cycle}.owner"
            try:  # bind the cycle to the first session that actually writes
                fd = os.open(owner, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as fh:
                    json.dump({"session_id": session}, fh)
                return True
            except FileExistsError:
                try:
                    bound = json.loads(owner.read_text(encoding="utf-8"))
                except Exception:
                    return False
                return bound.get("session_id") == session
            except OSError:
                return False
    return False


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

    try:
        real = os.path.realpath(fp)
    except Exception:
        return 0
    if _ultra_ahorro_allows(Path(os.path.realpath(proj)), real,
                            str(data.get("session_id") or "")):
        return 0  # user-selected Ultra Ahorro: declared file, bound session

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
    if (proj / ".claude" / "ultra-ahorro").is_dir():
        sys.stderr.write(
            f"Ultra Ahorro is in use in this project but `{rel}` is NOT in the "
            f"active cycle's allowed_files (or the cycle is closed/aborted, or "
            f"bound to another session). Widening the scope means updating the "
            f"declaration AND re-checking eligibility — skills/kuraka-ahorro.md "
            f"§2; if the new surface breaks a criterion, leave the mode.\n"
        )
    return 2


if __name__ == "__main__":
    sys.exit(main())
