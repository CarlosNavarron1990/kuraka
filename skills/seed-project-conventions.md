---
name: seed-project-conventions
description: "Canonical spec for seeding .claude/project/conventions/ + glossary. Executed by `arki` (greenfield mode — sourced from discovery docs) and `amauta` (brownfield mode — sourced from sampled code). Guarantees both onboarding paths produce the SAME convention surface the cycle agents consume, and that every resolved discovery decision lands somewhere the cycle actually reads."
---

# Seed Project Conventions

You are seeding the **project specialization layer** — the ONLY documentation
surface (besides `kuraka.config.yaml` and the stack profile) that the cycle
agents (`po-analyst`, `story-refiner`, `architect-reviewer`,
`backend-developer`, `frontend-developer`, `test-engineer`) load on every
phase. A convention that doesn't land here does not reach the agents.

## Modes

| Mode | Executed by | Source of truth | When evidence is missing |
|------|-------------|-----------------|--------------------------|
| **greenfield** | `arki` (Step 6) | `docs/discovery/vision.md` + `requirements.md` (+ `flujos/`, `decisiones-abiertas.md`) and the chosen stack profile | Use the stack profile's default and mark it as a default |
| **brownfield** | `amauta` (Step 5) | The code sampled in amauta Step 2 + the convention matrix (Step 3) | Write `<TODO: confirm with team>` — NEVER invent, never fall back to another project's pattern |

Both modes cite their evidence: greenfield cites the discovery doc + section;
brownfield cites `file:line` from the sampled code.

## Files to seed (all modes, always attempt each)

Create under `.claude/project/conventions/` (plus `glossary.md` at the layer
root). Skip a file ONLY when the concern is absent from the project (e.g. no
frontend → no `frontend-branding.md`), and say so in the onboarding report.

### 1. `architecture.md`
The actual layer/module pattern (Django apps / FastAPI 4-layer / Rails / …),
layer ordering, and where each concern lives. Brownfield: the pattern you
OBSERVED, including violations flagged as anti-patterns (non-blocking).

### 2. `naming.md`
Identifier conventions (case, prefixes/suffixes, file naming, language).
Brownfield: from the convention matrix, with confidence + evidence.

### 3. `api-design.md`
API golden rules: endpoint naming, error envelope (exact shape), pagination
scheme, versioning, auth header, status-code usage. Brownfield: extract from
the 3–5 sampled endpoints — the envelope/pagination/status codes are
observable; anything not observed is a `<TODO>`. Greenfield: from the stack
profile defaults adjusted per discovery.

### 4. `query-and-repository.md`
Data-access patterns: repository responsibilities, RLS/tenant enforcement
point, N+1 avoidance idiom, transaction + idempotency rules. Brownfield: from
the sampled repositories.

### 5. `frontend-branding.md` (whenever a frontend exists)
The design source of truth the `frontend-developer` reads for every UI story:

- **Design tokens** (palette, typography, spacing, radii). Greenfield: the
  tokens arki defines. Brownfield: extracted from the theme/tailwind/tokens
  file if one exists; otherwise `<TODO>`.
- **Layout patterns** (app-shell, nav, form/table patterns) at a high level.
- **Design-file wiring**: if a design file exists (Pencil `.pen`, Figma URL —
  including one passed in by the onboarding wizard), record its **path/URL**,
  how to read it (for `.pen`: the Pencil MCP, never `Read`/`Grep`), and a
  **frame index** table (screen → frame id → target component; leave rows
  `<TODO>` if unmapped). State explicitly: **when a design/frame exists it is
  mandatory** — a UI screen citing a frame is not done until visually faithful.
- If NO design file exists: still create the file with the tokens + the note
  "no design file yet — frontend uses these branding defaults; when a design
  is added, register it here and it becomes mandatory".

### 6. `tenant-isolation.md` (only if `conventions.multi_tenant: true`)
Tenant column, scoping enforcement point, RLS specifics, cross-tenant test
expectations.

### 7. `test-fixtures.md`
Catalog of fixtures/factories available in the codebase and the test pattern
in use (AAA / Given-When-Then, fixture style). `test-engineer` reads this
file when planning and writing tests. Brownfield: from the 3–5 sampled test
files. Greenfield: the pattern the stack profile prescribes + "no fixtures
yet — register them here as they are created".

### 8. Domain conventions + `glossary.md`
- `glossary.md`: domain vocabulary. Greenfield: from discovery. Brownfield:
  from models, enums, and comments — include entity names AND their key
  relations/states in one line each (this is the cycle's primary domain
  channel; don't leave it as a bare word list).
- One `conventions/<domain-topic>.md` per schema-shaping business rule (e.g.
  `money-and-ledger.md`, `pii-anonymization.md`).

## Hard rule — resolved decisions must land here (greenfield)

Every **resolved** decision in `docs/discovery/decisiones-abiertas.md` and
every RN/CF in `requirements.md` (value-flow model, matching/allocation,
concurrency limits, revenue recognition, approval policy, timing parameters)
MUST be written into a `conventions/` file or `glossary.md` — with a pointer
back to the discovery doc. `docs/discovery/` is user-facing; the cycle agents
only reliably load the project layer. A resolved decision that stays only in
discovery WILL be re-decided (differently) by `po-analyst` in some cycle.

## Per-file template

```markdown
# {Convention title}

## Context ({auto-extracted from the project | derived from discovery})

This project uses: {pattern}
Confidence: {HIGH | MEDIUM | LOW}   <!-- brownfield only -->
Source: {file:line refs | discovery doc + section}

## Rules

{Convention text — the project's actual vocabulary, not another project's.}

## Examples

{1–2 snippets: sampled code (brownfield) or idiomatic target (greenfield).}

## Anti-patterns {detected in the codebase | to avoid}

{Brownfield: violations seen while sampling — flag, don't block onboarding.}
```

## Output

Report back to the invoking agent (for its onboarding report): the list of
files created, per-file confidence (brownfield), the `<TODO>` count, and any
concern intentionally skipped with its reason.
