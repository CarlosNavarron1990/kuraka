---
name: refine-stories
description: "Break an approved REQ document into detailed implementable user stories. Used by story-refiner agent in Phase 2 of the workflow."
agent: "`story-refiner`"
phase: "2 — see `kuraka`"
disable-model-invocation: true
user-invocable: false
---

# Refine Stories

You are executing the Story Refinement skill (Phase 2 of the workflow)
for the project described in `kuraka.config.yaml`.

## Input

An approved REQ document from Phase 1.

## Steps

### 1. Load context

The `story-refiner` agent's Context section describes the full loading
order. The relevant inputs for this skill:

- `kuraka.config.yaml` for paths, layers, conventions, migration tool.
- `.claude/stack-profiles/${stack.backend.framework}.md` (and frontend
  if applicable) for idiomatic file paths and per-layer responsibilities.
- `.claude/project/conventions/*.md` — team architecture, tenant
  isolation, etc.
- `.claude/project/glossary.md` if present.

### 2. Decompose REQ into stories

Break the requirement into the smallest implementable units. Each story
should be:

- **Independent** — can be implemented without other stories being complete.
- **Testable** — has clear acceptance criteria.
- **Small** — 1–3 files to create/modify.

Typical decomposition follows the stack profile's layer order. For
example with `python-fastapi`:

- S1: Models + Migration (DB layer).
- S2: Repositories (data access layer).
- S3: Schemas (request/response).
- S4: Services (business logic).
- S5: Endpoints (HTTP layer).
- S6: Frontend (if applicable).

Adapt to the actual stack profile's layers.

### 3. For each story, define

1. **Acceptance criteria** — numbered, testable checklist.
2. **Schema changes** — exact table, column, type, nullable, default.
3. **API contract** — method, path, request body, response body.
4. **Files to create/modify** — exact paths from the stack profile's
   idiomatic layout + `architecture.paths.*`.
5. **Dependencies** — which stories must be complete first.
6. **Tests needed** — what test cases this story requires.
7. **Resolved mechanism** — for any parse/compare/serialize/classify step with
   >1 reasonable implementation, state the chosen mechanism in one AC line (no
   prose hedge).
8. **Binding snippets for structural pitfalls** — embed routing/DI-scope/
   lazy-load/wiring corrections as the EXACT code block in an AC, never as a
   prose "Technical Note".
9. **Tag edge-case AC rows** `[normative]` vs `[illustrative]`. Rename/move
   stories include a grep inventory of old-name references (evolve in place).

### 4. Naming and convention validation

Before outputting, scan every story for:

- Identifiers in a language other than `conventions.naming_language` → rename.
- Null syntax that doesn't match `conventions.null_syntax` → fix.
- Hardcoded values → replace with enums or config (per
  `conventions.enums_for_states`).
- Missing tenant scoping → if `conventions.multi_tenant: true`, every
  tenant-scoped table requires `conventions.tenant_column_name` and
  every query must filter by it.
- Vague FK targets → make explicit (`table.column`).

### 5. Staleness check

If the user has made corrections since the REQ was written:

- Compare current stories against the latest corrections.
- Regenerate any stale sections.
- Never carry outdated terminology forward.

### 6. Output

Create story files at
`${architecture.paths.docs_process_root}/stories/{ticket}-S{N}.md` and
present a summary table to the user.
