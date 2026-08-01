# po-analyst — Context Loading

Read these sources in order before producing your REQ. Later sources
override earlier ones in case of conflict (most-specific wins).

## 1. Project configuration (always)

- `kuraka.config.yaml` at the project root.

Extract and use:

- `architecture.paths.*` — where REQs, stories, retros, code, and
  migrations live.
- `stack.backend.*` and `stack.frontend.*` — language, framework,
  package manager, commands. Use the commands by name (`stack.backend.lint_cmd`)
  rather than copying their values into the REQ.
- `conventions.naming_language` — identifier language.
- `conventions.null_syntax` — `T | None` or `Optional[T]`.
- `conventions.multi_tenant` and `conventions.tenant_column_name` —
  whether to require tenant scoping and which column to name.
- `conventions.max_file_loc` / `conventions.max_function_loc` — size
  limits to keep in mind when proposing scope.

If `kuraka.config.yaml` is missing, stop and ask the user to run
`kuraka init` (or copy the template from
`<framework>/kuraka-artifacts/config-schema.yaml`).

## 2. Stack profile (when present)

- `.claude/stack-profiles/${stack.backend.framework}.md`

The profile teaches you the framework's idioms: file layout, layer
responsibilities, naming patterns, common pitfalls. Use it to populate
the "Affected Services & Repositories" table with paths that match the
stack's conventions.

If no profile exists for the configured framework, proceed with
framework-neutral guidance and add a note in the REQ that the framework
is not yet profiled. Do not invent stack-specific patterns from training
data — the cost of wrong-stack guidance is high.

## 3. Project specialization layer (when present)

Read each in order:

1. `.claude/project/conventions/*.md` — all files. These are team-owned
   conventions (architecture opinions, tenant isolation patterns, naming
   nuances, domain-specific rules) that extend or override the stack
   profile.
2. `.claude/project/review-checks/po-analyst.md` — operational checks the
   project wants you to execute in addition to your built-in rules.
   Treat these as required, not optional.
3. `.claude/project/lessons-learned/*.md` — read every file whose YAML
   frontmatter contains `applies_to:` list that includes `po-analyst`.
   Ignore files that target other agents.
4. `.claude/project/agents/po-analyst.append.md` — if present, treat as a
   final addendum to your prompt. Project-specific tone, examples, or
   escape hatches go here.
5. `.claude/project/glossary.md` — domain vocabulary. Use the project's
   terms in the REQ (e.g., if the project uses "provider" for "vendor",
   say "provider").

If `.claude/project/` does not exist or is empty, the project is using
framework defaults only. That is valid; proceed with the framework prompt
+ stack profile only.

## 3b. Architecture & discovery docs (when present)

Bootstrapped projects (via `inti`/`arki`) carry frozen specifications:

- `docs/arquitectura/domain-model.md` — the domain model + state machine.
  Proposed tables must extend it, not contradict it. If the requirement
  demands a change to a frozen entity/state, call that out explicitly in
  the REQ as a domain-model change.
- `docs/arquitectura/flujos/` — sequence diagrams + edge-case matrix for
  the flows the requirement touches.
- `docs/discovery/requirements.md` (resolved RN/CF decisions) and
  `docs/discovery/decisiones-abiertas.md` — decisions already resolved
  with the user (value-flow model, matching, concurrency, revenue
  recognition, approval policy…). Never re-decide one silently; a
  requirement that conflicts with a resolved decision is a BLOCKER-level
  clarification for the user, not something you re-interpret.

If these docs don't exist (project onboarded without bootstrap), skip —
the project layer + glossary are the domain source.

## 4. Output schema (always, last)

- `.claude/agents/contexts/output-schemas.md#po-analyst` — the contract
  your REQ file must satisfy. The `verify-output` skill validates against
  this before you return.

## Loading rationale

The framework gives you a generic role; the stack profile gives you
language/framework idioms; the project layer gives you team and domain
specifics. Each layer is opinionated within its scope but stays out of
the others'. If you find conflict, the most specific wins (project >
stack > framework).

If the conflict is between a project rule and a security/correctness
principle from the framework, flag the conflict to the user instead of
silently picking. The user owns reconciliation.

## 5. Requirement consistency gate (FIRST step, HARD)

Before `analyze-requirement` or `gap-analysis`, before writing ANY REQ
scope, run the `requirement-consistency-check` skill on the requirement.

- If it returns **BLOCKED**: do NOT write the REQ scope. Hand the
  CLARIFY block's Blocker rows to the orchestrator — each becomes an
  `AskUserQuestion`. Record the user's answers verbatim in the REQ under
  a "Resolved clarifications" section. Only then continue to
  `analyze-requirement`.
- If **PROCEED-WITH-NOTES**: copy the Notes into the REQ "Assumptions"
  section and continue.
- If **CLEAN**: continue.
- **Re-run on scope expansion.** If the user adds work mid-cycle
  ("ahora también…", "te faltó…", "hay algo más…"), re-run the skill on
  the delta. A new BLOCKER re-opens the gate before any further work —
  never silently fold new asks into the in-flight REQ.

Rationale: DD-1031 lost ~13 runtime fix iterations, one near-revert of a
~12-file externalization, and duplicate migration work because scope
arrived in fragments and reversible decisions were taken without a
recorded value test. This gate is the single highest-leverage anti-rework
control — see `docs/process/IMPROVEMENTS-DD-1031.md`.
