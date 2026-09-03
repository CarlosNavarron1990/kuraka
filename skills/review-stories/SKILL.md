---
name: review-stories
description: "Architect review of user stories before implementation begins. Validates architecture, naming, tenant strategy, and completeness. Used in Phase 3."
agent: "`architect-reviewer`"
phase: "3 — see `kuraka`"
disable-model-invocation: true
user-invocable: false
---

# Review Stories

You are executing the Architect Review skill for stories (Phase 3 of the
workflow) for the project described in `kuraka.config.yaml`.

## Input

Story files from Phase 2 at
`${architecture.paths.docs_process_root}/stories/`.

## Steps

### 1. Load context

Per the `architect-reviewer` agent's Context section:

- `kuraka.config.yaml` for paths, layers, conventions.
- Stack profile(s) for idiomatic patterns and architecture invariants.
- `.claude/project/conventions/*.md` for team-owned conventions.
- `.claude/project/review-checks/architect-reviewer.md` for project-specific
  checks (run these in addition to the generic checklist).
- `.claude/project/lessons-learned/*.md` filtered by `applies_to`.

### 2. Review each story against checklist

For EACH story, verify the items below. (The full checklist with severity
guidance lives in the `architect-reviewer` agent prompt.)

| # | Check | How to verify |
|---|-------|---------------|
| 1 | Identifier language matches `conventions.naming_language` | Grep for other-language identifiers in table/column/variable names |
| 2 | Tenant strategy (if `conventions.multi_tenant: true`) | Every tenant-scoped table has `conventions.tenant_column_name`; every query filters by it |
| 3 | Explicit FK targets | `references users.id` not just `references users` |
| 4 | No extra tables | Compare against REQ and ticket |
| 5 | File paths match the stack profile's idiomatic layout + `architecture.paths.*` | Compare paths in story against profile |
| 6 | Null syntax matches `conventions.null_syntax` | No mismatched style anywhere |
| 7 | No hardcoded values (when `conventions.enums_for_states: true`) | Enums or config for all states/types |
| 8 | Independent stories | Each can be implemented alone |
| 9 | API contracts complete | Request AND response defined |
| 10 | Testable criteria | Each acceptance criterion is verifiable |
| 11 | Migration naming follows the stack profile's convention for `${stack.database.migration_tool}` | Compare against profile |
| 12 | File size forecast | Will any file exceed `conventions.max_file_loc`? Plan a split. |

### 3. Project-specific checks

Apply every check in `.claude/project/review-checks/architect-reviewer.md`
if it exists. These typically cover pattern parity (migrations vs seeds,
directory structure, executable commands for new patterns).

### 4. Severity classification

- **BLOCKER** — Must fix before implementation. Missing tenant scoping,
  wrong architecture, security flaw, pattern without precedent.
- **IMPORTANT** — Should fix in this cycle. Naming issues, incomplete
  contracts, missing tests.
- **MINOR** — Can note for later. Style preferences, documentation gaps.

### 5. Output

Produce a review report with:

- Verdict: APPROVED / APPROVED_WITH_MINOR / CHANGES_REQUIRED.
- Findings table (severity, story, description, fix).
- List of approved stories.
- List of stories needing changes.

### 6. Gate decision

- If ANY BLOCKER exists → CHANGES_REQUIRED.
- If only IMPORTANT/MINOR → APPROVED_WITH_MINOR (can proceed with fixes
  during implementation).
- If all clear → APPROVED.
