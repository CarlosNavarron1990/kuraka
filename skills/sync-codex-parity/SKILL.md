---
name: sync-codex-parity
description: Keep Kuraka's Codex integration behaviorally aligned after changes to Claude-source agents, skills, commands, rules, model routing, mount logic, or export logic. Use when adapting new Kuraka framework content for Codex, investigating a Claude-to-Codex parity gap, or validating that Codex updates do not change Claude Code or Antigravity output.
---

# Sync Codex Parity

Work from the Kuraka vault. If this skill is loaded from a consumer project,
locate the vault through `KURAKA_VAULT` before changing anything. Treat
`agents/`, `skills/`, `commands/`, `rules/`, `MODEL-ROUTING.yaml`, and
`kuraka-artifacts/` as source material; do not fork or edit them merely to
satisfy a Codex limitation.

Read `references/parity-contract.md` before editing. Use
`$KURAKA_VAULT/CODEX-KURAKA-PARITY-ANALYSIS.md` for the complete rationale and
current gaps when it is available.

## Workflow

1. Inspect `git status --short` and the source diff. Preserve unrelated worktree
   changes and identify whether the change affects agents, skills, commands,
   rules, routing, artifacts, or lifecycle scripts.
2. Trace the source through `kuraka-mount.py` and `kuraka-export.py`. Change the
   target-specific Codex transformation, not the Claude or Antigravity branch.
3. Map the changed feature to a native Codex surface. Render agents as TOML with
   `developer_instructions`; keep reusable workflows and user commands as
   `SKILL.md` directories; use `AGENTS.md` for project instructions. Codex
   entrypoints are `$name` or `/skills`, not project-defined `/name` aliases.
   Do not copy Claude-only metadata or command syntax as if Codex understood it.
4. Preserve orchestration semantics explicitly. Describe phase gates, required
   artifacts, handoffs, validation, escalation, and model intent in generated
   Codex instructions. Do not rely on filename copying to retain this behavior.
5. Test a fresh temporary mount. Confirm expected Codex files exist, frontmatter
   and TOML parse, and the installed Codex CLI discovers at least one new skill
   or agent. Run the structural test harness where available.
6. Compare fresh Claude and Antigravity mounts before and after the change.
   Their generated trees must be unchanged unless the user explicitly requested
   a cross-platform source change.

## Required Checks

Run the relevant commands after implementation:

```sh
python3 -m py_compile kuraka-mount.py kuraka-export.py
python3 kuraka-apply-models.py --check
python3 kuraka-mount.py --help
bash validate-kuraka.sh <claude-fixture>
cd <fixture> && python3 -m pytest tests/kuraka/ -v
```

For Codex, mount into an empty fixture and inspect the generated tree. Use
`codex debug prompt-input '<probe>'` when available to verify runtime discovery;
do not assume a path is supported without checking the installed CLI.

## Guardrails

- Keep Claude Code and Antigravity branches byte-stable for Codex-only work.
- Never overwrite target-project overrides, user `AGENTS.md`, credentials, or
  project configuration.
- Keep Codex backup/restore isolated from the Claude override store until a
  generated-destination manifest can identify Codex overrides safely.
- Keep model routing centralized in `MODEL-ROUTING.yaml`. Codex agents inherit
  the active session model by default; route only their reasoning effort. Add a
  per-agent `model` override only after validating it in the target Codex
  integration.
- Prefer deterministic transforms and structural tests over undocumented manual
  repair steps.
- Record an unresolved platform capability as a gap in the analysis instead of
  silently dropping workflow behavior.
