# architect-reviewer — Context Loading

Read these sources in order before reviewing stories + test plan.

## 1. Project configuration (always)

- `kuraka.config.yaml` at the project root.

Use:

- `architecture.layers` — enforce that proposed stories respect the layer
  ordering and don't introduce skipping.
- `architecture.paths.*` — locate stories, test plans, schemas; verify
  proposed file paths in stories match.
- `conventions.{naming_language, null_syntax, multi_tenant,
  tenant_column_name, enums_for_states, max_file_loc, max_function_loc}` —
  validate stories against project conventions.
- `stack.backend.framework` and `stack.database.migration_tool` —
  determine which stack profile and migration patterns to expect.

## 2. Stack profile(s) (when present)

- `.claude/stack-profiles/${stack.backend.framework}.md`
- `.claude/stack-profiles/${stack.frontend.framework}.md` (if reviewing
  stories with frontend impact)

Profiles define:

- Idiomatic file paths (used to validate "File paths match the stack
  profile's layout").
- Per-layer responsibilities (used to flag stories that violate "no
  logic in inner layers").
- Migration naming conventions for `${stack.database.migration_tool}`.

## 3. Project specialization layer (when present)

Read each in order:

1. `.claude/project/conventions/*.md` — team architecture rules and
   domain-specific conventions.
2. `.claude/project/review-checks/architect-reviewer.md` — operational
   checks the project requires (pattern parity, migration vs seed,
   directory structure mirroring). Treat as required.
3. `.claude/project/lessons-learned/*.md` — read every file whose
   frontmatter `applies_to` includes `architect-reviewer`.
4. `.claude/project/agents/architect-reviewer.append.md` — if present,
   addendum.

## 3b. Architecture docs (when present)

- `docs/arquitectura/domain-model.md` — the schema you freeze must be
  consistent with it. If the stories require changing a frozen
  entity/state, that's a BLOCKER: either the stories adapt, or the user
  explicitly approves a domain-model change (update the doc in the same
  cycle).
- `docs/arquitectura/flujos/` — validate story ACs against the state
  machine + edge-case matrix for the flows in scope.
- `docs/arquitectura/*.md` ADRs (stack-decision, security-model,
  multitenant…) — architectural constraints the stories must respect.
- `docs/discovery/decisiones-abiertas.md` — a story that re-opens a ✅
  resolved decision without the user's sign-off is a BLOCKER.

Skip if absent (project without bootstrap docs).

## 4. Artifacts under review (always, for the current cycle)

- Story files in `${architecture.paths.docs_process_root}/stories/`.
- Test plan in
  `${architecture.paths.docs_process_root}/test-plans/TEST-PLAN-{ticket}.md`.
- The REQ document (for cross-referencing scope decisions).

## 5. Output schema (always, before returning)

- `.claude/agents/contexts/output-schemas.md#architect-reviewer` — your
  review report's required sections. The `verify-output` skill validates.

## Loading rationale

You are the gate between design and implementation. Your job is to catch
design flaws that would otherwise surface in Phase 4-6 as expensive
rework. The framework prompt defines your role; the stack profile tells
you what's idiomatic for the stack; the project layer tells you what's
idiomatic for this team and codebase.

Most-specific wins (project > stack > framework). If a project check
appears to relax a security/correctness rule, flag the conflict to the
user instead of silently picking.
