# story-refiner — Context Loading

Read these sources in order before producing stories.

## 1. Project configuration (always)

- `kuraka.config.yaml` at the project root.

Use:

- `architecture.paths.*` — where stories and migrations live.
- `architecture.layers` — to validate that the story's "Files to
  Create/Modify" respects the layer ordering.
- `conventions.naming_language`, `null_syntax`, `multi_tenant`,
  `tenant_column_name`, `enums_for_states` — applied to every story's
  schema and AC text.
- `stack.database.migration_tool` — to pick the migration naming pattern.

## 2. Stack profile(s) (when present)

- `.claude/stack-profiles/${stack.backend.framework}.md`
- `.claude/stack-profiles/${stack.frontend.framework}.md` (if frontend stories)

Profiles define:

- Idiomatic file paths used to populate "Files to Create/Modify".
- Per-layer responsibilities used to validate story scope.
- Migration naming conventions for the configured tool.

## 3. Project specialization layer (when present)

Read each in order:

1. `.claude/project/conventions/*.md` — including:
   - `tenant-isolation.md` if present — for tenant-related stories.
   - `architecture.md` if present — for module/scope decisions.
2. `.claude/project/review-checks/story-refiner.md` — extra checks.
3. `.claude/project/lessons-learned/*.md` — `applies_to` includes `story-refiner`.
4. `.claude/project/agents/story-refiner.append.md` — addendum.
5. `.claude/project/glossary.md` — use the project's terms in stories.

## 3b. Architecture docs (when present)

- `docs/arquitectura/domain-model.md` — for stories touching stateful
  entities, ACs must match the frozen state machine (statuses,
  transitions, guards). A story that adds/changes a state is a
  domain-model change and must say so explicitly.
- `docs/arquitectura/flujos/` — the edge-case matrix (casuística) is a
  source of ACs; don't let cases the discovery already mapped drop out
  because the REQ summarized them.

Skip if absent (project without bootstrap docs).

## 4. The approved REQ (always, current cycle)

- The Phase 1 REQ document. Stories must derive from it directly; you
  don't extend scope without going back to the user.

## 5. Output schema (always, before returning)

- `.claude/agents/contexts/output-schemas.md#story-refiner` — per-story
  required sections. The `verify-output` skill validates each story file.

## Loading rationale

Stories sit between PO analysis (what) and implementation (how). The
config tells you the project's structural conventions; the stack profile
tells you the idiomatic file layout; the project layer tells you
team-specific rules and vocabulary; the REQ tells you what to break down.

Most-specific wins (project > stack > framework). If conflict between
the stack profile's file paths and the project's
`.claude/project/conventions/architecture.md`, the project layer wins.
