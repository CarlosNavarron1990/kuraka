---
name: run-audit
description: "Run final audit / retrospective after completing a development cycle. Analyzes rework causes, agent failures, and produces improvement recommendations. Used in Phase 7."
agent: "`final-auditor`"
phase: "7 — see `kuraka`"
disable-model-invocation: true
user-invocable: false
---

# Run Audit

You are executing the Final Audit skill (Phase 7 of the workflow) for
the project described in `kuraka.config.yaml`.

## Input

The complete development cycle:

- REQ document (Phase 1).
- Story files (Phase 2).
- Architect review (Phase 3) and code / security reviews (Phase 5 / 5.5).
- Implemented code (Phase 4).
- Test results (Phase 6).
- Smoke test results (Phase 6.8) if applicable.
- User corrections / feedback throughout.

## Steps

### 0. Verify prior-retro application (RUN FIRST)

Open the previous RETRO and its `## 6) Patches Proposed`. For each proposed
patch, verify it was actually applied (grep the agent prompt / project-layer
file, or confirm the file exists). Record the result as section `0)` of the new
RETRO. **This is a closing gate**: a project-layer patch is applied NOW and
verified with its declared evidence command (paste the result), or carries a
per-patch user decline in writing — never closed silently un-applied; ≥2 retros
un-applied = must-apply. Framework-tier patches are never applied from a
consumer project: record them as `OPEN FRAMEWORK DEBT` with an occurrence
counter (`proposed in N retros`) for the vault's `/kuraka-harvest` to land. An
LL written this cycle ships its INDEX.md row in the same change (verify
`grep -c`). This closes the retro→apply→verify loop (soft wording did not hold:
guai 3 cycles of un-landed patches; facturacion 0/11, framework tier 0%).

### 1. Collect evidence

Read:

- `${architecture.paths.docs_process_root}/REQ-*.md` (the REQ for this cycle).
- `${architecture.paths.docs_process_root}/stories/*.md` (all stories).
- Previous retros in
  `${architecture.paths.docs_process_root}/agent-retrospectives/`.
- The conversation history for user corrections.
- The Phase 6.9 user-validation ledger: `python3 "${KURAKA_VAULT}/kuraka-ajuste.py"
  estado <project-root> --req <REQ> --json` (`ajustes/AJUSTES-<REQ>.md`). It is the
  verbatim record of what the user had to ask to adjust — the RETRO's
  `## Efectividad` section is built from it, never from memory.

### 2. Count iteration loops

An iteration loop = user correction → agent response → user correction.

For each loop, document:

- What was corrected.
- Which agent produced the incorrect output.
- At what phase it could have been caught.
- Was it preventable?

### 3. Analyze each agent

For each agent invoked in the cycle:

- **What failed?** Specific failure, not vague.
- **Why?** Root cause (missing check, stale data, wrong assumption).
- **Where to fix:** framework prompt OR project layer
  (prefer project layer for project-specific patterns; framework only
  for truly universal issues).
- **Concrete fix text:** exact text to add, with target file path.

### 4. Identify systemic issues

Patterns that span multiple agents:

- Naming consistency failures.
- Architecture rule violations.
- Scope creep.
- Communication gaps.

### 5. Propose improvements

Concrete, actionable changes:

- New gates / checkpoints to add to the workflow.
- New checks to add to agents (framework or project layer).
- Process changes.

### 6. Write patches

For each agent / file that needs updating, specify:

- Type: framework patch (affects all consumers) OR project-layer addition
  (affects only this project).
- Exact file path.
- Exact text to add (not vague suggestions) — for FRAMEWORK patches only, ≤15
  lines each. A PROJECT-LAYER patch is applied on its file with the edit/write
  tool and recorded in the RETRO as one line (`file · what changed · evidence`);
  the text is not pasted twice and no apply-script is generated.

RETRO budget by cycle size (`size:` in the prompt, default M): S ≤120 · M ≤220
· L ≤400 lines. The telemetry table is copied from the curated JSON /
`kuraka-close.py`, not re-derived.

### 7. Produce RETRO document

Create at
`${architecture.paths.docs_process_root}/agent-retrospectives/RETRO-{REQ-name}.md`.

Also point `RETRO-LATEST.md` at it — as a symlink, re-created with `ln -sfn RETRO-{REQ}.md RETRO-LATEST.md`.
NEVER `cp`/write onto an existing `RETRO-LATEST.md`: if it is a symlink, the write goes THROUGH it and
clobbers the previous cycle's retro (guai-home: a 166 B stub overwrote a 31 KB RETRO, 2 incidents).
Where symlinks are unavailable, `rm -f RETRO-LATEST.md` first, then copy.

**Mandatory section — `## Efectividad (validación del usuario)`:**

<!-- Built from `python3 "${KURAKA_VAULT}/kuraka-ajuste.py" estado <root> --req <REQ> --json`
     (Phase 6.9 ledger, `ajustes/AJUSTES-<REQ>.md`). Never re-derived from memory. -->
- Aceptación: `<primera-ronda | tras-N-rondas | sin-aceptacion | sin-registro>` · rondas: N · ajustes: N · faltó preguntar/hacer: N · pendientes: N

| # | Tipo | Debió detectarlo | Pedido del usuario (textual) | Patch aplicado (capa del proyecto) |
|---|------|------------------|------------------------------|------------------------------------|

For EVERY `falto-preguntar` / `falto-hacer` row: a concrete patch to the project
layer — the `.append.md` of the agent named in "debió" (a question it must ask,
a check it must run), a `lessons-learned/` entry, or a `review-checks/` line —
applied in this phase and tagged `harvest-candidate` so `/kuraka-harvest` can
lift it into the vault. `bug` / `ux` rows: say which gate or recorrido step
should have failed and didn't. `sin-registro` (no ledger) is itself a finding:
the cycle closed without the user's validation being recorded.

**Contract of the RETRO FILE — the last line is mandatory:**

```markdown
## Confidence: HIGH | MEDIUM | LOW
```

It is not decoration and not the same thing as the confidence line of your
*response*: `kuraka-backup.py` parses it out of the FILE (`find_verdict`) into
`cycles/<REQ>/meta.yaml` and into the cross-project `projects/INDEX.md`, which is
what `pattern-detector` reads to compare cycles across projects. A RETRO without
it is archived but nearly invisible: it becomes a row with an empty verdict.

State it explicitly here — do NOT rely on the platform reminding you. On Claude
the `output_validate.py` hook (SubagentStop) enforces the line on your response,
so it tends to end up in the file too; the platforms without hooks only have the
manual prose, and in practice that produced whole projects of verdict-less
retros (camisassis: 16 of 16 archived with `verdict: ""`, so none of its cycles
count in any cross-project comparison).

### 8. Ask user and apply patches

"Should I apply the proposed patches from section 6? Project-layer
changes and agent prompt tuning can be applied immediately to the mounted agent files (`.agents/` in Antigravity, `.claude/` in Claude Code, `.cursor/` in Cursor, `.codex/` in Codex); framework changes require
contributing back to the framework repo."
When approved by the user, apply project-layer and agent prompt patches directly to the corresponding mounted files.
The `falto-preguntar` / `falto-hacer` patches from `## Efectividad` go to the
PROJECT LAYER (`.claude/project/agents/<agent>.append.md`, `lessons-learned/`,
`review-checks/`) with a `harvest-candidate` tag line, so the Phase 7 backup
carries them to the vault store and `/kuraka-harvest` sees them grouped across
projects.

### 9. Back up the cycle state to the vault (MANDATORY — last step)

This closes the cycle by snapshotting the project's full Kuraka state into the
vault's unified store:

```bash
python3 "${KURAKA_VAULT:-/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka}/kuraka-backup.py" <project-root> [--target <antigravity|claude|cursor|codex>]
```

Snapshots `layer/` (`.claude/project`), `state/docs-process/` (REQ, stories,
test-plans, schemas, checkpoints) and `cycles/<REQ>/` (RETRO + telemetry + meta,
branch-tagged) into `projects/<slug>/`, and appends to `projects/INDEX.md`.
Idempotent. Do NOT skip: it (1) lets Kuraka learn from failures across ALL
projects and (2) preserves the work outside the solution's git so a branch switch
can't lose it (`kuraka-restore.py` pastes it back on the next mount). Confirm
the command exited 0.

**It will exit 1 if the RETRO you just wrote has no `## Confidence:` line** — the
state is snapshotted, but the cycle does not close until you add it and re-run
(the `meta.yaml` then fills in by itself). This is enforced in the script rather
than in a hook so that it holds on EVERY platform: only Claude has hooks, and on
the others prose alone left whole projects of verdict-less cycles. A cycle with
no telemetry is warned about, not blocked.

### 10. Verify the state actually landed (exit 0 is not evidence)

```bash
python3 "${KURAKA_VAULT:-/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka}/kuraka-doctor.py" <project-root>
```

Re-reads the central store and confirms what step 9 was supposed to produce:
this cycle's RETRO archived, its telemetry attached, the agent tuning applied in
step 8 snapshotted as an override, `docs/process` mirrored, the mount manifest
stamped with the current suite, and the config's `project.name` still agreeing
with the slug the store uses. Record its verdict in the RETRO.

Non-zero does NOT close the cycle: run it again with `--fix` (it applies the safe
repairs and re-checks) and act on whatever remains — a missing mount manifest
needs `kuraka-mount.py <project> --update`; a slug mismatch is a naming decision,
never an automatic rewrite. Every silent breakage found in the 2026-08 store
audit had passed a green `kuraka-backup` first.

### 10. Auto-trigger pattern-detector when due

Count the RETROs in
`${architecture.paths.docs_process_root}/agent-retrospectives/`. If the count is
a multiple of 5, or `RECURRING-ISSUES.md` is stale (older than the 5 most recent
retros), recommend running `detect-patterns` now and tell the user the count +
staleness. Do not leave it as a silent optional step — in practice it has been
deferred ~6 cycles while recurring patterns piled up unaggregated.
