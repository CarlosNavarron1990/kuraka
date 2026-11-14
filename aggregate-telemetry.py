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
import re
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


# PER-PHASE thresholds ("investigate if exceeds", size M) — authoritative per
# kuraka-policies.md → Token Budget ("One budget model: PHASE thresholds win").
# Keep in sync with that table. BUDGETS above stays the fallback for entries
# whose phase cannot be resolved.
PHASE_CAPS = {
    "1": 200_000, "2": 180_000, "2.5": 150_000, "3": 150_000,
    "4a": 400_000, "4b": 400_000, "5": 200_000, "5.5": 180_000,
    "6": 300_000, "6.5": 200_000, "6.7": 120_000, "7": 150_000,
}
SIZE_FACTOR = {"S": 2 / 3, "M": 1.0, "L": 1.5}
VARIANT_FACTOR = {"3+probe": 1.3}


def _phase_base(label: str) -> str:
    m = re.match(r"\s*(\d+(?:\.\d+)?[a-z]?)", str(label))
    return m.group(1) if m else ""


def cap_for_run(run: dict, agent: str) -> int | None:
    """Hard cap for one run: phase table x declared size (S/M/L) x declared
    variant. A combined label `1+2+2.5` is the sum of its phases (the named
    variant in kuraka-policies). Falls back to the per-agent cap."""
    phase = str(run.get("phase", ""))
    variant = str(run.get("variant") or "")
    size = str(run.get("size") or "M").strip().upper()[:1]
    factor = SIZE_FACTOR.get(size, 1.0)
    label = variant if "+" in variant and variant not in VARIANT_FACTOR else phase
    bases = [_phase_base(p) for p in label.split("+")]
    if bases and all(b in PHASE_CAPS for b in bases):
        cap = sum(PHASE_CAPS[b] for b in bases) * factor
        cap *= VARIANT_FACTOR.get(variant, 1.0)
        return int(cap)
    return BUDGETS.get(agent, (None, None))[1]


def find_telemetry_files(project_root: Path) -> list[Path]:
    telemetry_dir = project_root / "docs" / "process" / "agent-telemetry"
    if not telemetry_dir.is_dir():
        return []
    return sorted(p for p in telemetry_dir.glob("*-telemetry.json")
                  if not p.name.startswith("._"))  # skip macOS AppleDouble files


def load_checkpoint_phases(project_root: Path) -> dict[str, list[str]]:
    """Map req_name -> phases_completed from docs/process/checkpoints/*-state*.json."""
    ckpt_dir = project_root / "docs" / "process" / "checkpoints"
    result: dict[str, list[str]] = {}
    if not ckpt_dir.is_dir():
        return result
    for path in sorted(ckpt_dir.glob("*-state*.json")):
        if path.name.startswith("._"):
            continue
        try:
            with path.open() as fp:
                data = json.load(fp)
        except (json.JSONDecodeError, OSError, UnicodeDecodeError):
            continue
        req = data.get("req_name")
        phases = data.get("phases_completed")
        if req and isinstance(phases, list):
            result[str(req)] = [str(p) for p in phases]
    return result


def num(value) -> int | None:
    """Coerce a telemetry number. Non-numeric values ("unknown", "n/a", "") are
    None — never a crash (guai FD-13: `int("unknown")` killed the aggregator on 3
    files) and never a silent 0 (null means unmeasured, not free)."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        v = value.strip().replace(",", "").replace("_", "")
        if v.isdigit():
            return int(v)
    return None


NUMERIC_FIELDS = ("total_tokens", "tool_uses", "duration_ms", "tokens_incremental")


def split_phase_label(label: str) -> set[str]:
    """`1+2+2.5` (combined po-analyst run, the default since Lite v2) covers phases
    1, 2 and 2.5; `3.9-preflight` covers 3.9. Without this split every combined
    cycle reported 3 false "no telemetry entry" debts (editorial F-2 9/9,
    piscosdalston FD-4)."""
    out: set[str] = set()
    for part in str(label).split("+"):
        part = part.strip()
        if not part:
            continue
        out.add(part)
        out.add(part.split("-")[0])
        b = _phase_base(part)
        if b:
            out.add(b)
    return out


def is_orchestrator_phase_marker(phase: str) -> bool:
    """A checkpoint entry may declare the phase was run by the orchestrator
    directly (`6.5-orchestrator`, `6.5@orchestrator`): no Agent call, no entry."""
    p = str(phase).lower()
    return "orchestrator" in p or p.endswith("@orch")


# Phases the orchestrator runs directly by design — a missing telemetry entry
# for these is normal (kuraka-policies: only real Agent invocations are logged).
ORCHESTRATOR_OWNED_PHASES = {"3.9", "6.8"}


def compute_telemetry_debt(cycle: dict, checkpoint_phases: list[str] | None) -> list[str]:
    """Completeness integrity (kuraka-policies → Token Telemetry): flag runs whose
    numbers can't be trusted, and checkpoint-completed phases with no entry."""
    debts: list[str] = []
    seen_phases: set[str] = set()
    for run in cycle.get("runs", []):
        agent = str(run.get("agent", "(unknown)"))
        phase = str(run.get("phase", "?"))
        # A 0-token `agent: orchestrator*` entry is how any orchestrator-run phase
        # (3.9, 6.5, 6.8, ...) declares itself covered.
        seen_phases.update(split_phase_label(phase))
        for field in NUMERIC_FIELDS:
            raw = run.get(field)
            if raw is not None and num(raw) is None:
                debts.append(f"phase {phase} · {agent}: non-numeric {field}={raw!r} (record null when unmeasured)")
        if agent.startswith("orchestrator"):
            continue  # orchestrator-side entries legitimately log 0
        status = str(run.get("status", "ok"))
        if status != "ok":
            continue  # session_limit / interrupted / error already self-describe
        if run.get("usage_source") == "unavailable":
            debts.append(f"phase {phase} · {agent}: usage unavailable (not zero)")
            continue
        tokens = num(run.get("total_tokens")) or 0
        if tokens == 0:
            debts.append(f"phase {phase} · {agent}: status ok but 0/missing total_tokens")
            continue
        if not run.get("tool_uses"):
            debts.append(f"phase {phase} · {agent}: missing/zero tool_uses on a {tokens:,}-token run")
        if not run.get("duration_ms"):
            debts.append(f"phase {phase} · {agent}: missing/zero duration_ms on a {tokens:,}-token run")
        if run.get("resumed") and run.get("tokens_incremental") is None:
            debts.append(
                f"phase {phase} · {agent}: resumed run without tokens_incremental "
                f"({tokens:,} is the cumulative transcript, not the delta's cost)"
            )
    if checkpoint_phases:
        for phase in checkpoint_phases:
            base = _phase_base(phase)  # "3.9-preflight" / "3.9 (note)" -> "3.9"
            if not base:
                continue  # user-validation, gates, notes: not an agent phase
            if base in ORCHESTRATOR_OWNED_PHASES or is_orchestrator_phase_marker(phase):
                continue
            parts = {_phase_base(p) for p in phase.split("+")} | {base}
            if not (parts & seen_phases) and phase not in seen_phases:
                debts.append(f"checkpoint says phase {phase} completed but no telemetry entry exists (orchestrator-direct or missing?)")
    return debts


def effective_tokens(run: dict) -> int:
    """Compute spend for a run, correcting for RESUMED agents.

    A resumed agent (SendMessage / continue) reports the CUMULATIVE tokens of its
    whole transcript, not the tokens the delta actually cost. Summing those inflates
    the cycle: REQ-20260804-audit-columns reports 2,729,123 tokens while the real
    incremental spend is ~1,985,000 (+37%), because 4 of 15 runs are resumes.

    When the orchestrator records `resumed: true` + `tokens_incremental`, that value
    is authoritative for aggregation. Otherwise fall back to `total_tokens`.
    """
    if run.get("resumed") and run.get("tokens_incremental") is not None:
        return num(run.get("tokens_incremental")) or 0
    return num(run.get("total_tokens")) or 0


def has_token_measurement(run: dict) -> bool:
    key = "tokens_incremental" if run.get("resumed") else "total_tokens"
    return num(run.get(key)) is not None


def measured_total(total: int, known: int, count: int) -> str:
    if not known:
        return "n/a"
    return f"{total:,}" + (" + unknown" if known < count else "")


def load_cycle(path: Path) -> dict | None:
    try:
        with path.open() as fp:
            return json.load(fp)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        print(f"[warn] cannot parse {path.name}: {exc}", file=sys.stderr)
        return None


def render_dashboard(cycles: list[dict], checkpoints: dict[str, list[str]] | None = None) -> str:
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
        tokens = sum(effective_tokens(r) for r in runs)
        uses = sum(num(r.get("tool_uses")) or 0 for r in runs)
        # null/missing durations are legitimate (multi-day combined sessions);
        # render n/a instead of a misleading 0.0s
        timed = [num(r.get("duration_ms")) for r in runs if num(r.get("duration_ms"))]
        ms = sum(timed)
        if not timed:
            dur = "n/a"
        else:
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
        token_label = measured_total(tokens, sum(has_token_measurement(r) for r in runs), len(runs))
        uses_label = measured_total(uses, sum(num(r.get("tool_uses")) is not None for r in runs), len(runs))
        lines.append(f"| {name} | {mode} | {len(runs)} | {token_label} | {uses_label} | {dur} | {status} |")

    # --- per-agent aggregate ---
    per_agent: dict[str, dict] = defaultdict(lambda: {
        "invocations": 0,
        "tokens": 0,
        "tool_uses": 0,
        "duration_ms": 0,
        "timed_runs": 0,
        "over_budget": 0,
        "known_tokens": 0,
        "known_uses": 0,
    })

    # budget_ok integrity: the orchestrator self-reports budget_ok per run, but
    # it must equal tokens-vs-hard-cap recomputed here. A recorded `true` on an
    # over-cap run means the check never fired mid-cycle (REQ-20260703: 19/19
    # entries said budget_ok:true while one run exceeded its hard cap and every
    # run exceeded its target).
    # budget_ok is COMPUTED here (tokens <= hard cap); a hand-typed value is only
    # compared, never trusted — mismatches in BOTH directions are listed (petsuite
    # 4 module cycles and guai 0926 had 11 false values typed by hand).
    budget_ok_mismatches: list[tuple[str, str, str, int, int, str]] = []

    for cycle in cycles:
        cycle_name = cycle.get("req_name", "(unknown)")
        for run in cycle.get("runs", []):
            agent = run.get("agent", "(unknown)")
            a = per_agent[agent]
            a["invocations"] += 1
            a["known_tokens"] += has_token_measurement(run)
            a["known_uses"] += num(run.get("tool_uses")) is not None
            t = effective_tokens(run)
            a["tokens"] += t
            a["tool_uses"] += num(run.get("tool_uses")) or 0
            if num(run.get("duration_ms")):
                a["duration_ms"] += num(run.get("duration_ms"))
                a["timed_runs"] += 1

            hard_cap = cap_for_run(run, agent)
            if hard_cap and t > hard_cap:
                a["over_budget"] += 1
            if hard_cap and has_token_measurement(run) and "budget_ok" in run:
                computed = t <= hard_cap
                recorded = run.get("budget_ok")
                if isinstance(recorded, str):
                    recorded = recorded.strip().lower() in ("true", "yes", "1")
                if bool(recorded) != computed:
                    budget_ok_mismatches.append(
                        (cycle_name, agent, str(run.get("mode", "")), t, hard_cap,
                         f"recorded {bool(recorded)} / computed {computed}")
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
        # average over runs that actually recorded a duration; n/a if none did
        if stats["timed_runs"]:
            avg_dur_ms = stats["duration_ms"] / stats["timed_runs"]
            avg_dur = f"{avg_dur_ms / 1000:.1f}s" if avg_dur_ms < 60_000 else f"{avg_dur_ms / 60_000:.1f}min"
        else:
            avg_dur = "n/a"
        over = stats["over_budget"]
        flag = f"⚠️ {over}/{n}" if over else f"0/{n}"
        total_label = measured_total(stats["tokens"], stats["known_tokens"], n)
        complete = stats["known_tokens"] == n
        avg_label = f"{avg_t:,.0f}" if complete else "n/a"
        ratio_label = (f"{per_use:,.0f}" if complete and stats["known_uses"] == n
                       and stats["tool_uses"] else "n/a")
        if not complete:
            flag += " (usage incomplete)"
        lines.append(
            f"| {agent} | {n} | {total_label} | {avg_label} | {ratio_label} | {avg_dur} | {flag} |"
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
            lines.append(
                f"- **{agent}** — {stats['over_budget']} of {stats['invocations']} invocations "
                f"exceeded their phase threshold (phase x size x variant, kuraka-policies)"
            )

    # --- telemetry completeness debt (kuraka-policies → "Completeness is CHECKED") ---
    debt_rows: list[tuple[str, str]] = []
    for cycle in cycles:
        name = cycle.get("req_name", "(unknown)")
        ckpt = (checkpoints or {}).get(str(name))
        for debt in compute_telemetry_debt(cycle, ckpt):
            debt_rows.append((str(name), debt))
    if debt_rows:
        lines.append("")
        lines.append("## ⚠️ Telemetry debt (completeness)")
        lines.append("")
        lines.append(
            "Runs whose numbers cannot be trusted, or checkpoint-completed phases "
            "with no telemetry entry. The budget/optimization loop is only as good "
            "as this data — clear or justify each debt in the cycle's retro."
        )
        lines.append("")
        lines.append("| Cycle | Debt |")
        lines.append("|-------|------|")
        for name, debt in debt_rows:
            lines.append(f"| {name} | {debt} |")

    if budget_ok_mismatches:
        lines.append("")
        lines.append("## ⚠️ budget_ok integrity mismatches")
        lines.append("")
        lines.append(
            "Runs whose recorded `budget_ok` disagrees with the value computed here "
            "(tokens vs the agent's hard cap). The computed value is authoritative; "
            "a hand-typed `true` on an over-cap run means the mid-cycle budget check "
            "did not fire (see `kuraka-policies.md` → Token Budget)."
        )
        lines.append("")
        lines.append("| Cycle | Agent | Run mode | Tokens | Hard cap | budget_ok |")
        lines.append("|-------|-------|----------|-------:|---------:|-----------|")
        for cycle_name, agent, run_mode, t, cap, verdict in budget_ok_mismatches:
            lines.append(f"| {cycle_name} | {agent} | {run_mode or '—'} | {t:,} | {cap:,} | {verdict} |")

    # --- totals ---
    total_tokens = sum(s["tokens"] for s in per_agent.values())
    total_uses = sum(s["tool_uses"] for s in per_agent.values())
    total_ms = sum(s["duration_ms"] for s in per_agent.values())
    run_count = sum(s["invocations"] for s in per_agent.values())
    known_tokens = sum(s["known_tokens"] for s in per_agent.values())
    known_uses = sum(s["known_uses"] for s in per_agent.values())
    token_label = measured_total(total_tokens, known_tokens, run_count)
    uses_label = measured_total(total_uses, known_uses, run_count)
    duration_label = (f"{total_ms / 60_000:.1f} min" if any(
        s["timed_runs"] for s in per_agent.values()) else "n/a")
    average_label = f"{total_tokens / len(cycles):,.0f}" if known_tokens == run_count and run_count else "n/a"
    lines.append("")
    lines.append("## Totals")
    lines.append("")
    lines.append(f"- Total tokens: **{token_label}**")
    lines.append(f"- Total tool uses: **{uses_label}**")
    lines.append(f"- Total duration: **{duration_label}**")
    lines.append(f"- Avg tokens per cycle: **{average_label}**")
    lines.append("")
    lines.append("---")
    lines.append("_Budget table lives in `.claude/skills/kuraka-policies.md` and `rules/17`._")

    return "\n".join(lines) + "\n"


def render_effectiveness(project_root: Path) -> str:
    """'Efectividad' table from the Phase 6.9 ledgers (ajustes/AJUSTES-*.jsonl).
    Empty string when there are none (or kuraka_common is not importable)."""
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import kuraka_common as kc
    except ImportError:
        return ""
    d = kc.ajustes_dir(project_root)
    files = sorted(p for p in d.glob("AJUSTES-*.jsonl") if not p.name.startswith("._")) if d.is_dir() else []
    if not files:
        return ""
    out = ["", "## Efectividad (validación del usuario — fase 6.9)", "",
           "| Ciclo | Aceptación | Rondas | Ajustes | Faltó preguntar/hacer | Pendientes |",
           "|---|---|---:|---:|---:|---:|"]
    first = 0
    for f in files:
        s = kc.ajustes_summary(f)
        first += s["aceptacion"] == "primera-ronda"
        out.append(f"| {f.stem[len('AJUSTES-'):]} | {s['aceptacion']} | {s['rondas']} | "
                   f"{s['ajustes_total']} | {s['ajustes_falto']} | {s['pendientes']} |")
    out += ["", f"- Aceptados en primera ronda: **{first}/{len(files)}**", ""]
    return "\n".join(out) + "\n"


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

    dashboard = render_dashboard(cycles, load_checkpoint_phases(project_root))
    dashboard += render_effectiveness(project_root)
    dashboard_path = project_root / "docs" / "process" / "agent-telemetry" / "DASHBOARD.md"
    dashboard_path.write_text(dashboard, encoding="utf-8")
    print(f"[ok] dashboard written to {dashboard_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
