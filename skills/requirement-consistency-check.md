---
name: requirement-consistency-check
description: "Detect inconsistencies, ambiguity, hidden reversible decisions and scope gaps in a requirement BEFORE any analysis or implementation, and force a user clarification when a finding is blocking. Use this skill as the FIRST step of Kuraka Phase 1 (before analyze-requirement / gap-analysis) for every ticket, and again whenever the user expands scope mid-cycle ('ahora también X', 'te faltó Y', 'hay algo más'). Triggers: any new requirement, fragmented/incremental asks, migration/refactor/externalize/encrypt/cleanup requests, or contradictory instructions. Invokable by po-analyst, amauta, architect-reviewer. Output is a CLARIFY block, not a REQ — the REQ comes AFTER all BLOCKERs are resolved with the user."
disable-model-invocation: true
user-invocable: false
---

# Requirement Consistency Check — pre-analysis clarification gate

> Catches the rework class that no other gate caught in DD-1031: scope
> arriving in fragments, reversible architectural decisions taken without a
> recorded value test, missing v1 behavior trace, work that already exists,
> data-shape assumptions, and contradictory asks. Its job is to **stop and
> ask the user BEFORE work starts**, not to produce a deliverable.

This skill does **not** replace `analyze-requirement` or `gap-analysis`.
It runs *before* them and may block them.

---

## 1. When to run

- The FIRST step of Phase 1 for every ticket/requirement.
- Again, immediately, whenever the user expands or changes scope
  mid-cycle ("ahora también…", "te faltó…", "hay algo más…",
  "aprovecha y…"). Re-run on the *delta*, not the whole ticket.
- Before `gap-analysis` when the input is a migration/refactor.

## 2. Inconsistency taxonomy (run every check)

For each class, look for the signal; if present, emit a finding.

| # | Class | Signal | DD-1031 evidence |
|---|-------|--------|------------------|
| C1 | **Scope fragmentation / no DoD** | requirement is incremental, or has no explicit "definition of done" / acceptance oracle | "valida" → "+hardcodes" → "+migración" → "+encriptación" |
| C2 | **Reversible decision without value** | a structural/architectural change (externalize, new table/pattern, refactor, migrate vs skip) with no stated *concrete expected value* | externalizar todo → luego "¿para qué lo usamos?" → casi revert |
| C3 | **Missing v1 behavior trace** | a v1→v2 migration without the v1 source path + the missing-datum branch (omit / error / success) traced per message type | E13 construido antes de ver que v1 *omite* ACTUALIZACION |
| C4 | **Pre-existing implementation** | the asked work may already exist in the repo and was not audited | migración MySQL→PG ya estaba implementada y wired |
| C5 | **Channel data-shape assumption** | resolution/business logic will depend on a payload field not proven present in that channel's real sample | API NUEVOAVISO sin código postal → ZIP es email-only |
| C6 | **Contradiction** | two instructions in the requirement are mutually incompatible, or contradict a project rule (cite rule 05 §2, rule 18, etc.) | "externalizar vocab" vs rule 05 §2 (hardcode aceptable) |
| C7 | **Ambiguous scope words** | "migrar / refactorizar / externalizar / limpiar / encriptar X" without explicit boundaries (which files, which channels, which env) | "encripta las credenciales" → ¿cuáles?, ¿qué key?, ¿qué entorno? |

## 3. Classify each finding

- **BLOCKER** — proceeding risks rework or an unrecoverable/wide change:
  C2, C3, C4, C6 always; C1/C5/C7 when the answer materially changes
  scope or design. A BLOCKER **halts**: do not write the REQ scope, do
  not dispatch to Phase 2/4.
- **NOTE** — record in the REQ "Assumptions" section and proceed
  (low-impact ambiguity with a safe, stated default).

## 4. Output — the CLARIFY block

Emit exactly this, nothing else, when any finding exists:

```
## CLARIFY (requirement-consistency-check)

Status: BLOCKED | PROCEED-WITH-NOTES | CLEAN

### Blockers (must resolve with the user before Phase 1 continues)
| # | Class | Finding | Question to ask the user |
|---|-------|---------|--------------------------|
| 1 | C2 | {what} | {single concrete question} |

### Notes (recorded in REQ Assumptions, proceeding)
- C{n}: {assumption taken + safe default}
```

If `CLEAN`, say so in one line and continue to `analyze-requirement`.

## 5. Gate mechanics (orchestrator + po-analyst)

1. po-analyst runs this skill first. If `BLOCKED`, po-analyst does NOT
   write the REQ scope.
2. The orchestrator turns each Blocker row into an `AskUserQuestion`
   (one question per blocker, options when there is a sensible set),
   records the answer **verbatim** in the REQ under
   "Resolved clarifications", and only then continues.
3. On mid-cycle scope expansion: re-run on the delta; a new BLOCKER
   re-opens the gate before any further implementation.
4. Never assume a BLOCKER answer. The cost of one question is far below
   the cost of the rework it prevents (DD-1031: 13 runtime iterations,
   one near-revert, duplicate migration work).

## 6. Anti-patterns

- ❌ Treating every ambiguity as BLOCKER (analysis paralysis) — use NOTE
  with a safe default when impact is low.
- ❌ Running it once and ignoring scope creep — it MUST re-run on every
  "ahora también…".
- ❌ Producing a REQ alongside the CLARIFY block — CLARIFY first, REQ
  only after blockers are resolved.
