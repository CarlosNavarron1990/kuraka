---
name: run-audit
description: "Run final audit / retrospective after completing a development cycle. Analyzes rework causes, agent failures, and produces improvement recommendations. Used in Phase 7."
agent: "`final-auditor`"
phase: "7 — see `kuraka`"
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
- Exact text to add (not vague suggestions).

### 7. Produce RETRO document

Create at
`${architecture.paths.docs_process_root}/agent-retrospectives/RETRO-{REQ-name}.md`.

Also copy to `RETRO-LATEST.md` for easy access.

### 8. Ask user and apply patches

"Should I apply the proposed patches from section 6? Project-layer
changes and agent prompt tuning can be applied immediately to the mounted agent files (`.agents/` in Antigravity, `.claude/` in Claude Code, `.cursor/` in Cursor, `.codex/` in Codex); framework changes require
contributing back to the framework repo."
When approved by the user, apply project-layer and agent prompt patches directly to the corresponding mounted files.

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

### 10. Auto-trigger pattern-detector when due

Count the RETROs in
`${architecture.paths.docs_process_root}/agent-retrospectives/`. If the count is
a multiple of 5, or `RECURRING-ISSUES.md` is stale (older than the 5 most recent
retros), recommend running `detect-patterns` now and tell the user the count +
staleness. Do not leave it as a silent optional step — in practice it has been
deferred ~6 cycles while recurring patterns piled up unaggregated.
