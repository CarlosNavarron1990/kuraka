---
description: Rule for preserving Kuraka state (agents, skills, commands, process docs) in the central vault — orchestrator-only, via kuraka-backup.py, never destructive
alwaysApply: true
---

# Kuraka Backup Rule (orchestrator-only, non-destructive)

## Where Kuraka state is preserved

The central vault is:

```
/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka/
```

Each project's state lives **namespaced under its own slug** in the unified store:

```
<vault>/projects/<slug>/
    registry.md      project registry note
    layer/           snapshot of .claude/project/ (specialization layer)
    state/           snapshot of docs/process/** (REQ, stories, schemas, checkpoints)
    cycles/<REQ>/    closed-cycle diagnostics (RETRO + telemetry + meta.yaml)
    overrides/       agent/skill/command files that diverge from the vault baseline
```

## HARD GUARD — who may write to the vault

- **Subagents NEVER sync, copy, rsync, or write anything into the vault.** Not
  agents, not skills, not docs — nothing. If you are a subagent (developer,
  reviewer, tester, auditor…) and believe something must be backed up, SAY SO in
  your report; the orchestrator handles it. A subagent touching the vault is a
  framework violation to be reported in the retro.
- **Backup is an orchestrator step, and it is one command:**

  ```bash
  python3 /Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka/kuraka-backup.py "$PWD"
  ```

  It snapshots layer + state + cycles + overrides into `projects/<slug>/`,
  namespaced and idempotent. It runs at **Phase 7** (the `final-auditor` gate
  requires its exit 0 — see `kuraka.md`), and may be run ad-hoc by the
  orchestrator any time state should be preserved (e.g. before a branch switch).

## Never destructive

- **NEVER use `--delete`** (rsync or otherwise) against any vault path. The
  vault aggregates state from MANY projects; a `--delete` scoped wrong wipes
  another project's data. (This happened: 2026-06-13, a subagent following the
  old version of this rule deleted a shared docs mirror.)
- Never write to a shared/top-level vault directory (`docs/`,
  `documentacion-backend/`, `agents/`, `skills/`…) from a consumer project.
  Consumer state goes ONLY under `projects/<slug>/` — and only via
  `kuraka-backup.py`.
- Copies only, never moves. The project's working tree is never the casualty of
  a backup.

## Agent/skill/command changes

Project-side tuning of `.claude/{agents,skills,commands}/*.md` needs **no manual
sync**: `kuraka-backup.py` snapshots divergent files into
`projects/<slug>/overrides/`, and every `mount-kuraka` re-applies them. Framework
improvements are integrated into the vault's canonical files by the **user via
`/kuraka-harvest` in the vault** — never pushed directly from a consumer project
session.

## Restore

Restoring on branch switch / re-mount is also orchestrator/user-run:

```bash
python3 /Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka/kuraka-restore.py "$PWD"
```

(`mount-kuraka` invokes it automatically and asks before pasting layer/state.)
