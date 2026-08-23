# e2e-tester — Context Loading

Read these sources in order before writing E2E tests.

## 1. Project configuration (always)

- `kuraka.config.yaml` at the project root.

Use:

- `architecture.paths.frontend_root` — to locate `playwright.config.ts`
  and existing E2E tests.
- `stack.frontend.framework` — informs which stack profile to load.

## 2. Stack profile (when present)

- `.claude/stack-profiles/${stack.frontend.framework}.md`

The profile may document framework-specific selectors, routing patterns,
or component conventions useful when writing tests.

## 3. Project specialization layer (when present)

Read each in order:

1. `.claude/project/conventions/*.md` — including any e2e-specific
   conventions.
2. `.claude/project/review-checks/e2e-tester.md` if present.
3. `.claude/project/lessons-learned/*.md` — `applies_to` includes
   `e2e-tester`.
4. `.claude/project/agents/e2e-tester.append.md` — if present, addendum.
5. `.claude/project/glossary.md` — domain vocabulary used in test names
   (e.g., the project's actual terms for "user", "tenant", "case").

## 4. Artifacts (always, for the current cycle)

- `<frontend_root>/playwright.config.ts` (if exists).
- Existing E2E tests in `<frontend_root>/tests/e2e/` — read 1-2 as
  reference for the project's style.
- The REQ to understand which user flows changed.

## 5. Output schema (always, before returning)

- `.claude/agents/contexts/output-schemas.md#e2e-tester` (if defined; the
  agent's prompt has a default template otherwise).

## Loading rationale

The framework defines what to test (critical flows only) and how
(Playwright + page objects). The project layer tells you what the
project's flows actually are and what vocabulary to use in test names.

---

## CRUD test playbook — one recipe per operation (reference)

Consult this when the feature has create/read/update/delete surfaces:
generate **one spec per operation**, each following the matching recipe.
The recipes are **framework-general and self-contained** — in a NEW solution
they still apply; only adapt the concrete tokens (mutation endpoint names, the
success signal, the soft-delete mechanism, the identity field) by reading
`.claude/project/conventions/*.md` + the stack profile. The worked example in
brackets is one project's convention (`add-/upd-/state-/list-*` POST, envelope
`{error, mensaje, data}`, identity by `*_hash`, soft-delete via
`flag_est`/`flag_act`, audit `create_usu`/`update_usu`) — substitute your
project's.

Every recipe inherits the **cross-cutting** agent rules: fresh per-test auth
(Rule 11); golden-path STRICT with F-task-labeled expected-reds emitted to the
matrix (Rule 12); gating short-circuit for permission-hidden controls (Rule 7
+ gating helper); locale-aware date handling (Rule 14); and the ORCHESTRATOR
runs the gate in foreground.

### CREATE (insert · `add-*`)
1. Fill **only the REQUIRED fields** first — discover the required set from a
   live 422 probe (or the story contract; the form validators mirror it), with
   **unique/timestamp-derived** values so re-runs never collide.
2. Submit; assert success by the project's signal (envelope `error:"0"` / HTTP
   2xx). The create response is often **minimal** (`{status, mensaje,
   <entity>_hash}`) with **no list envelope and no tenant id** — read the new
   hash from it, and decode any needed context (company/tenant) from the
   **session `X-User`**, not from the response.
3. **TEARDOWN** — delete/soft-delete what you created (real-tenant `add-*`
   leave real rows and pollute nightly CI). Teardown parses the ACTUAL create
   response shape; if the entity has no delete endpoint, log the leftover +
   flag it, don't silently pollute.
4. Selects → open the panel and pick a real option; readonly datepickers →
   drive the calendar (or leave the default) — never assume ISO (Rule 14).

### UPDATE / EDIT (`upd-*`)
Full **per-field round-trip**: pick a target on **page 1 via the paginator**
(never the permission-gated search box; guard disabled boundary buttons with
`isEnabled()`); open edit; assert **EVERY editable field pre-loaded its current
value** ("se rescata"); change **EACH**; save; **re-fetch**; assert **EACH
persisted**; then **REVERT** every field to the original (leave no mutation).
Catalog **selects** and **readonly datepickers** are **OBSERVE-ONLY** (assert
pre-load, don't change — no reliable "next value" semantics). Decimals come
back as **strings** → compare with `Number()` and bump with `Number(x)+1`
(LL-017, LL-020).

### DELETE (soft-delete · `state-*`)
Business systems here **soft-delete** (a state flag), never physical delete.
Recipe: create a **throwaway** record (CREATE recipe) or pick an expendable
one; trigger delete; assert it **leaves the active list** (or its state badge
flips), NOT that it vanished from the DB; if the convention supports
restore/activate, toggle it back. **Never hard-delete a real record you didn't
create.** Confirm the mutation hit the **state/soft-delete** endpoint, not a
physical `DELETE`.

### READ / LIST (`list-*`)
Assert **list-success** (`Array.isArray(data)`) as distinct from
mutation-success; assert the **denormalized fields the UI actually renders**
(joined names/labels, counts), not just ids; and **capture + freeze the live
response shape BEFORE** writing field asserts — shape drifts (enveloped vs
flat, ES vs EN keys, ids omitted) are the #1 source of false reds (LL-009,
LL-017).
