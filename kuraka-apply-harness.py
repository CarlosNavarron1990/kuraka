#!/usr/bin/env python3
"""Apply AGENT-HARNESS.yaml to agent frontmatter — the single-source-of-truth
propagator for the Claude Code HARNESS capabilities of each Kuraka agent
(tools / disallowedTools / maxTurns / skills / memory).

Sibling of kuraka-apply-models.py, same contract:

  - Reads AGENT-HARNESS.yaml (next to this script), validates it against the
    real agents/*.md files (bijection: every file mapped, every mapping has a
    file), and rewrites each agent's frontmatter managed-key lines.
  - The applier OWNS every managed key: a key disabled in `emit:` (or absent
    from an agent's resolved config) is REMOVED from the frontmatter, so the
    map is always the whole truth.
  - Managed keys are written in canonical order right after the `model:` line
    (or after `name:` if there is no model line), one flat line each — that
    flat shape is what kuraka_common.strip_claude_frontmatter subtracts for
    non-Claude renders.

Usage:
    python3 kuraka-apply-harness.py            # apply the map to frontmatter
    python3 kuraka-apply-harness.py --check     # validate + report drift, exit 1 on drift

No external dependencies — a tiny purpose-built YAML reader handles the fixed
shape of AGENT-HARNESS.yaml (we control the file; no need for PyYAML).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

if sys.platform == "win32":
    for _s in (sys.stdout, sys.stderr):
        _s.reconfigure(encoding="utf-8")

VAULT = Path(__file__).resolve().parent
HARNESS = VAULT / "AGENT-HARNESS.yaml"
AGENTS_DIR = VAULT / "agents"

# Managed keys, in the canonical frontmatter emission order.
MANAGED_KEYS = ("tools", "disallowedTools", "maxTurns", "skills", "memory")
_MANAGED_LOWER = {k.lower(): k for k in MANAGED_KEYS}

VALID_MEMORY = {"user", "project", "local"}


def _fail(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(1)


def _coerce(val: str):
    v = val.strip().strip('"').strip("'")
    if v in ("true", "false"):
        return v == "true"
    if v.isdigit():
        return int(v)
    return v


def load_harness() -> dict:
    """Parse the fixed shape of AGENT-HARNESS.yaml: `emit` (flat map) plus
    `profiles`/`agents` (name at indent 2, fields at indent 4)."""
    if not HARNESS.is_file():
        _fail(f"AGENT-HARNESS.yaml not found at {HARNESS}")
    emit: dict[str, bool] = {}
    profiles: dict[str, dict] = {}
    agents: dict[str, dict] = {}
    section = None
    cur = None
    for raw in HARNESS.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        stripped = raw.strip()
        if " #" in stripped:  # inline comments (values never contain " #")
            stripped = stripped.split(" #", 1)[0].strip()
        if not stripped:
            continue
        if indent == 0:
            key = stripped.split(":", 1)[0].strip()
            section = key if key in ("emit", "profiles", "agents") else None
            cur = None
            continue
        if ":" not in stripped:
            continue
        key, _, val = stripped.partition(":")
        key, val = key.strip(), val.strip()
        if section == "emit" and indent == 2:
            emit[key] = _coerce(val) is True
        elif section in ("profiles", "agents"):
            bucket = profiles if section == "profiles" else agents
            if indent == 2 and not val:          # profile / agent name
                cur = key
                bucket[cur] = {}
            elif indent >= 4 and cur is not None:
                bucket[cur][key] = _coerce(val)
    return {"emit": emit, "profiles": profiles, "agents": agents}


def agent_files() -> dict[str, Path]:
    """stem -> path for every real agent definition (excludes contexts/)."""
    return {p.stem: p for p in sorted(AGENTS_DIR.glob("*.md"))}


def resolve(harness: dict, stem: str) -> dict:
    """Profile fields overlaid by agent-level fields (agent wins)."""
    spec = harness["agents"][stem]
    out: dict = {}
    prof = spec.get("profile")
    if prof:
        out.update(harness["profiles"].get(prof, {}))
    for k, v in spec.items():
        if k != "profile":
            out[k] = v
    return out


def validate(harness: dict, files: dict[str, Path]) -> list[str]:
    errs: list[str] = []
    for stem, spec in harness["agents"].items():
        prof = spec.get("profile")
        if prof and prof not in harness["profiles"]:
            errs.append(f"agent '{stem}' -> unknown profile '{prof}'")
        resolved = resolve(harness, stem) if not (prof and prof not in harness["profiles"]) else spec
        for k in resolved:
            if k not in MANAGED_KEYS:
                errs.append(f"agent '{stem}' has unmanaged key '{k}' (allowed: {MANAGED_KEYS})")
        mem = resolved.get("memory")
        if mem is not None and mem not in VALID_MEMORY:
            errs.append(f"agent '{stem}' memory '{mem}' not in {sorted(VALID_MEMORY)}")
        mt = resolved.get("maxTurns")
        if mt is not None and not isinstance(mt, int):
            errs.append(f"agent '{stem}' maxTurns '{mt}' is not an integer")
    for stem in files:
        if stem not in harness["agents"]:
            errs.append(f"agent file '{stem}.md' has no entry in AGENT-HARNESS.yaml")
    for stem in harness["agents"]:
        if stem not in files:
            errs.append(f"AGENT-HARNESS.yaml lists '{stem}' but no agents/{stem}.md exists")
    for k in harness["emit"]:
        if k not in MANAGED_KEYS:
            errs.append(f"emit toggle '{k}' is not a managed key {MANAGED_KEYS}")
    return errs


def _emit_line(key: str, value) -> str:
    if key == "skills":
        items = [s.strip() for s in str(value).split(",") if s.strip()]
        return f"skills: [{', '.join(items)}]"
    return f"{key}: {value}"


def render(text: str, resolved: dict, emit: dict[str, bool]) -> str:
    """Return the file text with managed frontmatter keys normalized to the map."""
    m = re.match(r"^---\n(.*?\n)---\n", text, re.S)
    if not m:
        return text  # no frontmatter — validator elsewhere owns this failure
    fm_body = m.group(1)
    kept: list[str] = []
    for line in fm_body.splitlines():
        key = line.split(":", 1)[0].strip().lower() if ":" in line else ""
        if not line.startswith((" ", "\t")) and key in _MANAGED_LOWER:
            continue  # drop every existing managed line; we re-emit below
        kept.append(line)
    new_lines = [
        _emit_line(k, resolved[k])
        for k in MANAGED_KEYS
        if emit.get(k) and k in resolved
    ]
    if new_lines:
        anchor = next((i for i, l in enumerate(kept) if l.startswith("model:")), None)
        if anchor is None:
            anchor = next((i for i, l in enumerate(kept) if l.startswith("name:")), -1)
        kept[anchor + 1:anchor + 1] = new_lines
    return "---\n" + "\n".join(kept) + "\n---\n" + text[m.end():]


def apply(harness: dict, files: dict[str, Path], check_only: bool) -> int:
    changed = 0
    drift: list[str] = []
    for stem, path in files.items():
        text = path.read_text(encoding="utf-8")
        new = render(text, resolve(harness, stem), harness["emit"])
        if new == text:
            continue
        drift.append(f"  {stem}")
        if not check_only:
            path.write_text(new, encoding="utf-8")
        changed += 1
    if drift:
        verb = "would change" if check_only else "changed"
        print(f"agent harness (claude) — {verb} {changed} agent(s):")
        print("\n".join(drift))
    else:
        print(f"agent harness (claude) — all {len(files)} agents already match the map.")
    return changed


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true",
                    help="validate + report drift without writing (exit 1 on drift)")
    args = ap.parse_args()

    harness = load_harness()
    files = agent_files()

    errs = validate(harness, files)
    if errs:
        print("❌ AGENT-HARNESS.yaml validation failed:", file=sys.stderr)
        for e in errs:
            print(f"   - {e}", file=sys.stderr)
        sys.exit(1)

    changed = apply(harness, files, check_only=args.check)
    if args.check and changed:
        sys.exit(1)   # drift present — useful as a CI gate
    print("✅ done." if not args.check else "✅ check complete.")


if __name__ == "__main__":
    main()
