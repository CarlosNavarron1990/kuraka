---
project: <name>          # must match a projects/<name>.md
source: <RECURRING-ISSUES or RETRO-id>
date: <YYYY-MM-DD>
decision: pending        # pending | applied | rejected | deferred
applied: false
tags: [retro-triage]
---

# Triage — <project> — <date>

Source: [[RECURRING-ISSUES]] (or the specific RETRO).

For each finding, decide **routing** and record it. The routing rule: a finding is
**framework** if it would recur in ANY stack; **project** if it depends on this
project's conventions/oracle/schema. When in doubt → project (scoped, reversible).

| # | Finding | Routing | Target file | Severity | Status |
|---|---------|---------|-------------|----------|--------|
| 1 | <short description> | framework / project | `agents/<x>.md` or `<proj>/.claude/project/...` | HIGH/MED | applied / pending |
| 2 | | | | | |

## Patches (framework-routed findings)

Every **framework**-routed finding that targets a gold agent file needs a patch
sidecar before the control-plane app will apply it:

- **Path**: `retro-triage/patches/<card-id>.<finding-id>.md` — flat, no subdirectories.
  `<card-id>` is this card's filename stem (e.g. `2026-06-06-sie_v2`) and
  `<finding-id>` is the finding's id cell (the `#` column).
- **Content**: the file's raw bytes are the **FULL desired content of the target
  file** — not a diff. Byte-exact: what you put there is exactly what lands on
  `agents/<name>.md` (frontmatter, fences, trailing newline and all).
- **Ownership**: authored at triage time by the human / retro pipeline. The app
  treats the sidecar as READ-ONLY and **refuses** a framework apply whose sidecar
  is missing or blank.
- **Target-file cell**: must be EXACTLY `agents/<name>.md` — undecorated. No
  surrounding annotations like `(Rule T6)`, and no `rules/…` or `agents/contexts/…`
  paths (both are refused in this cut; OBS-1 lesson).

## Decisions & rationale
- **#1** — <why framework vs project; what changed; expected prevention>

## Follow-up
- [ ] Apply patch(es)
- [ ] Bump version (framework changes only)
- [ ] Sync project layer back to vault (`sync-obsidian` / re-run adoption rsync)
- [ ] Update `projects/<name>.md` `last_sync`
- [ ] Re-run pattern-detector next cycle to confirm prevention
