# Kuraka hooks (Claude Code only)

Deterministic, zero-token enforcement of the framework rules that prose
repeatedly failed to hold (telemetry completeness, gate integrity, orchestrator
role isolation, output structure). Mounted by `kuraka-mount.py` into the
consumer's `.claude/hooks/` **only for the claude target** — Antigravity /
Cursor / Codex never receive them; their renders instead keep the full manual
discipline prose via the `discipline/` block expansion (see CLAUDE.md).

| Hook | Event (matcher) | Enforces | On violation |
|---|---|---|---|
| `telemetry_append.py` | PostToolUse (Task\|Agent) + SubagentStop | Telemetry completeness: two rows per subagent in `<docs_process_root>/agent-telemetry/HOOK-LOG.jsonl`, joined by `agent_id`. `event: launch` at PostToolUse — Claude Code launches subagents in the BACKGROUND, so the response is only an `async_launched` ack with no usage (reading tokens there is why 869/869 rows in 9 projects were `null`). `event: stop` at SubagentStop — cost computed from `agent_transcript_path` (usage de-duplicated by message id): `total_tokens` (context + output of the last turn, comparable with the budgets), `tool_uses`, `duration_ms`, `turns`, `*_sum` (real spend across turns); cumulative, `seq` grows when the agent is resumed. A launch with no stop = an agent that never finished. A synchronous response that carries usage is logged as one `event: run`. `kuraka_common.hook_runs` collapses the rows; `kuraka-doctor` flags an old hook, a missing SubagentStop wiring, or stop rows without tokens | n/a — capture only; the orchestrator enriches + consolidates |
| `gate_integrity.py` | PreToolUse (Bash) | Rule T7: gate commands (`test_cmd`/`lint_cmd`/`typecheck_cmd`) never piped. Only the gate's OWN segment counts (scan stops at `;` `&&` `||` `&` newline) and `|` inside quotes is data; placeholder values (`TODO`/`TBD`/`<cmd>`, empty) are not gates | exit 2 + fix; escape: `KURAKA_GATE_PIPE_OK` marker in the command (user-approved) |
| `orchestrator_guard.py` | PreToolUse (Write/Edit) | Orchestrator never writes under code roots; subagents unaffected | exit 2; one-shot user-approved escape: `touch .claude/hooks/ALLOW-ORCH-WRITE`. Standing exception for the user-selected **Ultra Ahorro** mode: a write passes when an `active` `.claude/ultra-ahorro/<cycle>.json` names exactly that file — the first such write binds the cycle to the calling `session_id` (`<cycle>.owner`, O_EXCL), so no other session inherits it, and any non-`active` status revokes it |
| `output_validate.py` | SubagentStop | Universal output contract (Confidence line; Verdict for reviewers) | exit 2 once (loop-guarded); agent re-emits its report |
| `retro_contract.py` | PostToolUse (Write) | The RETRO **file** carries `## Confidence: HIGH\|MEDIUM\|LOW` — what `find_verdict` parses into `meta.yaml` + `projects/INDEX.md` | exit 2 once per RETRO (loop-guarded); the agent appends the line |
| `session_doctor.py` | SessionStart | Kuraka state health (`kuraka-doctor.py --brief`): config, layer, mount manifest, overrides↔store, retros archived, telemetry attached, state mirrored | never blocks — surfaces the findings as context; repair with `kuraka-doctor.py --fix` |
| `pr_gate.py` | PreToolUse (Bash) | `validar-pr` gate: `gh pr create/new/ready` needs an APROBABLE report for HEAD; blocks a push to a protected branch or one that skips pre-push. **Inert unless the project adopted validar-pr** (`.claude/project/validar-pr/config.sh`); `workflow.validar_pr.enforce_hook: false` turns it off | exit 2 with the reason; fail-open on any error |
| `state_backup.py` | SubagentStop + Stop | Continuous backup: `kuraka-backup.py --state-only` (incremental layer + docs/process, never deletes, no closure check) so an UNCLOSED cycle still reaches the store — azure GUAI-3141 never reached Phase 7 and its files were swept into a git stash | never blocks; throttled to once per 10 min (`.claude/.kuraka-state-backup.stamp`); fail-open |

Ultra Ahorro's other invariant — **zero subagents** — is NOT a hook: subagent
spawns do not go through `PreToolUse`, so there is nothing to intercept. It is
enforced natively by `disallowed-tools: Task` in the skill's frontmatter, which
removes delegation from the tool pool while the skill is active (the same
frontmatter pins `model:`/`effort:`). Platforms without that contract keep the
manual prose via `discipline/ultra-ahorro-evidence.md`.

All hooks are fail-open (unexpected input → exit 0) and inert outside a Kuraka
project (they require `kuraka.config.yaml`). Wiring lives in
`settings-hooks.json`, merged non-destructively into `.claude/settings.json`
by the mount (kuraka-owned entries are replaced; user entries preserved).

## Orchestrator scripts (not hooks — launched on demand)

| Script | Launched by | Purpose |
|---|---|---|
| `liveness_watch.sh <paths...>` | orchestrator, via Monitor / background Bash at Phase-4 start | Streams a line on file activity under the implementer's authorized paths; replaces manual mtime polling (the DECISION rule stays in kuraka-policies §liveness) |
| `review_mechanics.sh [files...]` | orchestrator, before Phase 5 / 5.5 | Runs the deterministic reviewer greps (secrets, console.log, design tokens, double-submit, namespace type-imports…) and emits a markdown table for the reviewer digest — the reviewer adjudicates, the script sweeps |
