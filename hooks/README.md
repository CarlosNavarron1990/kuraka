# Kuraka hooks (Claude Code only)

Deterministic, zero-token enforcement of the framework rules that prose
repeatedly failed to hold (telemetry completeness, gate integrity, orchestrator
role isolation, output structure). Mounted by `kuraka-mount.py` into the
consumer's `.claude/hooks/` **only for the claude target** — Antigravity /
Cursor / Codex never receive them; their renders instead keep the full manual
discipline prose via the `discipline/` block expansion (see CLAUDE.md).

| Hook | Event (matcher) | Enforces | On violation |
|---|---|---|---|
| `telemetry_append.py` | PostToolUse (Task) | Telemetry completeness: appends every subagent run to `<docs_process_root>/agent-telemetry/HOOK-LOG.jsonl` | n/a — capture only; the orchestrator enriches + consolidates |
| `gate_integrity.py` | PreToolUse (Bash) | Rule T7: gate commands (`test_cmd`/`lint_cmd`/`typecheck_cmd`) never piped | exit 2 + fix; escape: `KURAKA_GATE_PIPE_OK` marker in the command (user-approved) |
| `orchestrator_guard.py` | PreToolUse (Write/Edit) | Orchestrator never writes under code roots; subagents unaffected | exit 2; one-shot user-approved escape: `touch .claude/hooks/ALLOW-ORCH-WRITE` |
| `output_validate.py` | SubagentStop | Universal output contract (Confidence line; Verdict for reviewers) | exit 2 once (loop-guarded); agent re-emits its report |

All hooks are fail-open (unexpected input → exit 0) and inert outside a Kuraka
project (they require `kuraka.config.yaml`). Wiring lives in
`settings-hooks.json`, merged non-destructively into `.claude/settings.json`
by the mount (kuraka-owned entries are replaced; user entries preserved).

## Orchestrator scripts (not hooks — launched on demand)

| Script | Launched by | Purpose |
|---|---|---|
| `liveness_watch.sh <paths...>` | orchestrator, via Monitor / background Bash at Phase-4 start | Streams a line on file activity under the implementer's authorized paths; replaces manual mtime polling (the DECISION rule stays in kuraka-policies §liveness) |
| `review_mechanics.sh [files...]` | orchestrator, before Phase 5 / 5.5 | Runs the deterministic reviewer greps (secrets, console.log, design tokens, double-submit, namespace type-imports…) and emits a markdown table for the reviewer digest — the reviewer adjudicates, the script sweeps |
