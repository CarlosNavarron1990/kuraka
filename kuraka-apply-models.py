#!/usr/bin/env python3
"""Apply MODEL-ROUTING.yaml to agent frontmatter — the single-source-of-truth
propagator for which model each Kuraka agent runs on.

Reads MODEL-ROUTING.yaml (next to this script), validates it against the real
agents/*.md files, and rewrites each agent's frontmatter `model:` line to the
model its tier resolves to on the target platform.

Only the `claude` platform is machine-applied: Claude Code subagents take a
per-agent `model:` field in frontmatter, so there is a real target to write.
The non-Claude platforms (antigravity, cursor, codex) don't take a per-subagent
model — the export drops the field and the user picks a model in-tool — so their
columns are recommendations surfaced elsewhere (AGENTS.md role table), not
written here. `--platform` is accepted for forward-compat but only `claude`
mutates files today.

Usage:
    python3 kuraka-apply-models.py                # apply the claude column
    python3 kuraka-apply-models.py --check         # validate only, exit 1 on drift
    python3 kuraka-apply-models.py --platform claude   # explicit (default)

No external dependencies — a tiny purpose-built YAML reader handles the fixed
shape of MODEL-ROUTING.yaml (we control the file; no need for PyYAML).
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parent
ROUTING = VAULT / "MODEL-ROUTING.yaml"
AGENTS_DIR = VAULT / "agents"

# Values Claude Code accepts for a subagent `model:` field (bare aliases +
# inherit); a full model id (claude-*) is also allowed and matched separately.
CLAUDE_ALIASES = {
    "fable", "opus", "sonnet", "haiku",
    "best", "opusplan", "opus[1m]", "sonnet[1m]", "inherit",
}


def _fail(msg: str) -> "NoReturn":  # type: ignore[name-defined]
    print(f"❌ {msg}", file=sys.stderr)
    sys.exit(1)


def load_routing() -> dict:
    """Parse the fixed shape of MODEL-ROUTING.yaml: three top-level maps
    (tiers, platforms, agents). Values are scalars or one nested level. Good
    enough for this file; not a general YAML parser."""
    if not ROUTING.is_file():
        _fail(f"MODEL-ROUTING.yaml not found at {ROUTING}")
    tiers: dict[str, str] = {}
    platforms: dict[str, dict[str, str]] = {}
    agents: dict[str, str] = {}
    section = None
    cur_platform = None
    for raw in ROUTING.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        stripped = raw.strip()
        # strip inline comments (safe: our values never contain " #")
        if " #" in stripped:
            stripped = stripped.split(" #", 1)[0].strip()
        if indent == 0:
            key = stripped.split(":", 1)[0].strip()
            section = key if key in ("tiers", "platforms", "agents") else None
            cur_platform = None
            continue
        if ":" not in stripped:
            continue
        key, _, val = stripped.partition(":")
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if section == "tiers":
            tiers[key] = val
        elif section == "agents":
            agents[key] = val
        elif section == "platforms":
            if indent == 2:               # platform name (has no scalar value)
                cur_platform = key
                platforms[cur_platform] = {}
            elif indent >= 4 and cur_platform is not None:
                platforms[cur_platform][key] = val
    return {"tiers": tiers, "platforms": platforms, "agents": agents}


def agent_files() -> dict[str, Path]:
    """stem -> path for every real agent definition (excludes contexts/)."""
    return {p.stem: p for p in sorted(AGENTS_DIR.glob("*.md"))}


def read_model(path: Path) -> str | None:
    m = re.search(r"^model:\s*(.+?)\s*$", path.read_text(encoding="utf-8"), re.M)
    return m.group(1).strip() if m else None


def validate(routing: dict, files: dict[str, Path]) -> list[str]:
    """Structural checks. Returns a list of error strings (empty = OK)."""
    errs: list[str] = []
    tiers = set(routing["tiers"])
    platforms = routing["platforms"]
    agents = routing["agents"]

    if "claude" not in platforms:
        errs.append("platforms.claude is missing (the authoritative column)")
    # every tier resolves on claude, to an accepted value
    for tier in tiers:
        model = platforms.get("claude", {}).get(tier)
        if not model:
            errs.append(f"platforms.claude has no model for tier '{tier}'")
        elif model not in CLAUDE_ALIASES and not model.startswith("claude-"):
            errs.append(
                f"platforms.claude.{tier} = '{model}' is not a Claude Code model "
                f"value (expected an alias {sorted(CLAUDE_ALIASES)} or a claude-* id)"
            )
    # every agent -> a known tier
    for agent, tier in agents.items():
        if tier not in tiers:
            errs.append(f"agent '{agent}' -> unknown tier '{tier}'")
    # bijection between agent files and the agents map
    for stem in files:
        if stem not in agents:
            errs.append(f"agent file '{stem}.md' has no tier in MODEL-ROUTING.yaml")
    for agent in agents:
        if agent not in files:
            errs.append(f"MODEL-ROUTING.yaml lists '{agent}' but no agents/{agent}.md exists")
    return errs


def apply(routing: dict, files: dict[str, Path], platform: str,
          check_only: bool) -> int:
    col = routing["platforms"].get(platform, {})
    changed = 0
    drift: list[str] = []
    for stem, path in files.items():
        tier = routing["agents"][stem]
        target = col.get(tier)
        if not target:
            _fail(f"platform '{platform}' has no model for tier '{tier}' (agent {stem})")
        current = read_model(path)
        if current == target:
            continue
        drift.append(f"  {stem:<32} {current!s:<10} -> {target}")
        if not check_only:
            text = path.read_text(encoding="utf-8")
            new = re.sub(r"^model:.*$", f"model: {target}", text, count=1, flags=re.M)
            if new == text:  # no model line at all -> insert after name:
                new = re.sub(r"^(name:.*)$", rf"\1\nmodel: {target}", text,
                             count=1, flags=re.M)
            path.write_text(new, encoding="utf-8")
        changed += 1
    if drift:
        verb = "would change" if check_only else "changed"
        print(f"model routing ({platform}) — {verb} {changed} agent(s):")
        print("\n".join(drift))
    else:
        print(f"model routing ({platform}) — all {len(files)} agents already match the map.")
    return changed


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--platform", default="claude",
                    help="which platform column to apply (default: claude; "
                         "only claude mutates frontmatter today)")
    ap.add_argument("--check", action="store_true",
                    help="validate + report drift without writing (exit 1 on drift)")
    args = ap.parse_args()

    routing = load_routing()
    files = agent_files()

    errs = validate(routing, files)
    if errs:
        print("❌ MODEL-ROUTING.yaml validation failed:", file=sys.stderr)
        for e in errs:
            print(f"   - {e}", file=sys.stderr)
        sys.exit(1)

    if args.platform != "claude":
        print(f"ℹ️  platform '{args.platform}' is a recommendation-only column "
              f"(non-Claude tools pick their own model); nothing written. "
              f"Its mapping is surfaced in the exported AGENTS.md role table.")
        # still report what it WOULD map to, for visibility
        args.check = True

    changed = apply(routing, files, args.platform, check_only=args.check)
    if args.check and changed:
        sys.exit(1)   # drift present — useful as a CI gate
    print("✅ done." if not args.check else "✅ check complete.")


if __name__ == "__main__":
    main()
