#!/usr/bin/env python3
"""
aggregate-telemetry.py — Kuraka telemetry dashboard.

Reads every telemetry JSON under docs/process/agent-telemetry/, aggregates
token/time usage per agent across cycles, flags outliers, and emits a Markdown
dashboard.

Usage:
    python3 aggregate-telemetry.py [project_root]
        (default: $PWD)

Output:
    docs/process/agent-telemetry/DASHBOARD.md

Exit codes:
    0 — dashboard written
    1 — no telemetry found or project layout invalid
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Emit UTF-8 regardless of the console code page (Windows cp1252/cp850 crash guard).
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError, OSError):
        pass


# Budgets from rules/17 and kuraka-policies.md (median — "target")
BUDGETS = {
    "po-analyst": (80_000, 200_000),
    "story-refiner": (60_000, 180_000),
    "test-engineer": (60_000, 300_000),  # covers both TEST_PLANNING and TEST_WRITING
    "architect-reviewer": (100_000, 180_000),  # raised 2026-07-07: empirical freeze (execute-the-mechanism) is worth the spend
    "backend-developer": (100_000, 400_000),
    "frontend-developer": (100_000, 400_000),
    "code-reviewer": (70_000, 200_000),
    "security-reviewer": (60_000, 180_000),
    "e2e-tester": (50_000, 200_000),
    "deployment-verifier": (30_000, 120_000),
    "final-auditor": (70_000, 150_000),  # raised 2026-07-07: prior-retro evidence checks justify the floor
    "migration-reviewer": (20_000, 80_000),
    "pattern-detector": (30_000, 100_000),
}


def find_telemetry_files(project_root: Path) -> list[Path]:
    telemetry_dir = project_root / "docs" / "process" / "agent-telemetry"
    if not telemetry_dir.is_dir():
        return []
    return sorted(telemetry_dir.glob("*-telemetry.json"))


def load_cycle(path: Path) -> dict | None:
    try:
        with path.open() as fp:
            return json.load(fp)
    except (json.JSONDecodeError, OSError) as exc:
        print(f"[warn] cannot parse {path.name}: {exc}", file=sys.stderr)
        return None


def render_dashboard(cycles: list[dict]) -> str:
    if not cycles:
        return "# Kuraka Telemetry Dashboard\n\n(no telemetry data yet)\n"

    lines: list[str] = []
    lines.append("# Kuraka Telemetry Dashboard")
    lines.append("")
    lines.append(f"_Generated: {datetime.now().isoformat(timespec='seconds')}_  ")
    lines.append(f"_Cycles analyzed: {len(cycles)}_")
    lines.append("")

    # --- per-cycle summary ---
    # NOTE: duration is WALL-CLOCK (includes tool/DB/container wait), NOT compute
    # spend. Only `total_tokens` reflects model compute and is the budget signal.
    # Runs with a non-ok status (session_limit / interrupted) are surfaced so a
    # 0-token interrupted run is not misread as "no work" (guai: stripe-webhooks
    # logged total_tokens: 0 on a session-limit run).
    INCOMPLETE_STATUSES = {"session_limit", "interrupted", "error"}

    lines.append("## Cycles")
    lines.append("")
    lines.append("| Cycle | Mode | Runs | Total tokens | Total tool uses | Wall-clock | Status |")
    lines.append("|-------|------|-----:|-------------:|----------------:|-----------:|--------|")

    for cycle in cycles:
        name = cycle.get("req_name", "(unknown)")
        mode = cycle.get("mode", "—")
        runs = cycle.get("runs", [])
        tokens = sum(int(r.get("total_tokens", 0) or 0) for r in runs)
        uses = sum(int(r.get("tool_uses", 0) or 0) for r in runs)
        ms = sum(int(r.get("duration_ms", 0) or 0) for r in runs)
        dur = f"{ms / 1000:.1f}s" if ms < 60_000 else f"{ms / 60_000:.1f}min"
        bad = sorted({
            str(r.get("status")) for r in runs
            if str(r.get("status", "ok")) in INCOMPLETE_STATUSES
        })
        # cycle-level status field too (e.g. interrupted mid-run, no telemetry)
        cstatus = str(cycle.get("status", "")).strip()
        if cstatus and cstatus not in ("ok",):
            bad.append(cstatus)
        status = "⚠️ " + ", ".join(bad) if bad else "ok"
        lines.append(f"| {name} | {mode} | {len(runs)} | {tokens:,} | {uses} | {dur} | {status} |")

    # --- per-agent aggregate ---
    per_agent: dict[str, dict] = defaultdict(lambda: {
        "invocations": 0,
        "tokens": 0,
        "tool_uses": 0,
        "duration_ms": 0,
        "over_budget": 0,
    })

    # budget_ok integrity: the orchestrator self-reports budget_ok per run, but
    # it must equal tokens-vs-hard-cap recomputed here. A recorded `true` on an
    # over-cap run means the check never fired mid-cycle (REQ-20260703: 19/19
    # entries said budget_ok:true while one run exceeded its hard cap and every
    # run exceeded its target).
    budget_ok_mismatches: list[tuple[str, str, str, int, int]] = []

    for cycle in cycles:
        cycle_name = cycle.get("req_name", "(unknown)")
        for run in cycle.get("runs", []):
            agent = run.get("agent", "(unknown)")
            a = per_agent[agent]
            a["invocations"] += 1
            t = int(run.get("total_tokens", 0) or 0)
            a["tokens"] += t
            a["tool_uses"] += int(run.get("tool_uses", 0) or 0)
            a["duration_ms"] += int(run.get("duration_ms", 0) or 0)

            _target, hard_cap = BUDGETS.get(agent, (None, None))
            if hard_cap and t > hard_cap:
                a["over_budget"] += 1
                if bool(run.get("budget_ok", False)):
                    budget_ok_mismatches.append(
                        (cycle_name, agent, str(run.get("mode", "")), t, hard_cap)
                    )

    lines.append("")
    lines.append("## Per-agent aggregate")
    lines.append("")
    lines.append("| Agent | Invocations | Total tokens | Avg tokens | Tokens/use | Avg duration | Over-budget |")
    lines.append("|-------|------------:|-------------:|-----------:|-----------:|-------------:|------------:|")

    ranking = sorted(per_agent.items(), key=lambda kv: kv[1]["tokens"], reverse=True)
    for agent, stats in ranking:
        n = stats["invocations"]
        avg_t = stats["tokens"] / n if n else 0
        per_use = stats["tokens"] / stats["tool_uses"] if stats["tool_uses"] else 0
        avg_dur_ms = stats["duration_ms"] / n if n else 0
        avg_dur = f"{avg_dur_ms / 1000:.1f}s" if avg_dur_ms < 60_000 else f"{avg_dur_ms / 60_000:.1f}min"
        over = stats["over_budget"]
        flag = f"⚠️ {over}/{n}" if over else f"0/{n}"
        lines.append(
            f"| {agent} | {n} | {stats['tokens']:,} | {avg_t:,.0f} | {per_use:,.0f} | {avg_dur} | {flag} |"
        )

    lines.append("")
    lines.append(
        "> _Over-budget is computed from **tokens only** (model compute). "
        "Avg duration is **wall-clock** — it includes tool/DB/container wait and "
        "is NOT a budget gate. A slow run with in-band tokens is a latency "
        "artifact, not overspend; investigate latency separately._"
    )

    # --- flags ---
    flagged = [(agent, stats) for agent, stats in per_agent.items() if stats["over_budget"]]
    if flagged:
        lines.append("")
        lines.append("## ⚠️ Agents over budget")
        lines.append("")
        for agent, stats in flagged:
            _target, hard_cap = BUDGETS.get(agent, (None, None))
            lines.append(
                f"- **{agent}** — {stats['over_budget']} of {stats['invocations']} invocations exceeded {hard_cap:,} tokens"
            )

    if budget_ok_mismatches:
        lines.append("")
        lines.append("## ⚠️ budget_ok integrity mismatches")
        lines.append("")
        lines.append(
            "Runs recorded `budget_ok: true` whose tokens exceed the agent's hard "
            "cap — the orchestrator's mid-cycle budget check did not fire. Fix the "
            "recording discipline (see `kuraka-policies.md` → Token Budget)."
        )
        lines.append("")
        lines.append("| Cycle | Agent | Run mode | Tokens | Hard cap |")
        lines.append("|-------|-------|----------|-------:|---------:|")
        for cycle_name, agent, run_mode, t, cap in budget_ok_mismatches:
            lines.append(f"| {cycle_name} | {agent} | {run_mode or '—'} | {t:,} | {cap:,} |")

    # --- totals ---
    total_tokens = sum(s["tokens"] for s in per_agent.values())
    total_uses = sum(s["tool_uses"] for s in per_agent.values())
    total_ms = sum(s["duration_ms"] for s in per_agent.values())
    lines.append("")
    lines.append("## Totals")
    lines.append("")
    lines.append(f"- Total tokens: **{total_tokens:,}**")
    lines.append(f"- Total tool uses: **{total_uses}**")
    lines.append(f"- Total duration: **{total_ms / 60_000:.1f} min**")
    lines.append(f"- Avg tokens per cycle: **{(total_tokens / len(cycles)):,.0f}**")
    lines.append("")
    lines.append("---")
    lines.append("_Budget table lives in `.claude/skills/kuraka-policies.md` and `rules/17`._")

    return "\n".join(lines) + "\n"


def main() -> int:
    project_root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    telemetry_files = find_telemetry_files(project_root)

    if not telemetry_files:
        print(f"[error] no telemetry JSON found under {project_root}/docs/process/agent-telemetry/", file=sys.stderr)
        return 1

    cycles = [c for c in (load_cycle(p) for p in telemetry_files) if c is not None]
    if not cycles:
        print("[error] all telemetry files failed to parse", file=sys.stderr)
        return 1

    dashboard = render_dashboard(cycles)
    dashboard_path = project_root / "docs" / "process" / "agent-telemetry" / "DASHBOARD.md"
    dashboard_path.write_text(dashboard, encoding="utf-8")
    print(f"[ok] dashboard written to {dashboard_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
