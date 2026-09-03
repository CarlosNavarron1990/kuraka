---
name: implement-story
description: "Implement a single approved user story following the stack's idiomatic architecture. Creates models, schemas, repositories, services, endpoints, and migrations as needed. Used in Phase 4."
agent: "`backend-developer` (or `frontend-developer` for frontend stories)"
phase: "4 — see `kuraka`"
disable-model-invocation: true
user-invocable: false
---

# Implement Story

You are executing the Story Implementation skill (Phase 4 of the workflow)
for the project described in `kuraka.config.yaml`.

## Input

A single approved story file from
`${architecture.paths.docs_process_root}/stories/{ticket}-S{N}.md`.

## Pre-flight Checks

Before writing ANY code:

1. Read the story file completely.
2. Verify it was approved by `architect-reviewer` (Phase 3).
3. Check for stale terminology (compare against latest user corrections).
4. If the story references deprecated names → STOP and report.

## Implementation Order

Follow the implementation order specified in the stack profile for
`${stack.backend.framework}` (or `${stack.frontend.framework}` for
frontend stories). The profile defines the file order and idiomatic paths.

For example, with the `python-fastapi` profile:

1. Migration (if schema changes).
2. Models.
3. Schemas (Pydantic).
4. Repository.
5. Service.
6. Endpoint.

For Vue/Pinia (`vue-pinia` profile):

1. Types.
2. Services.
3. Stores.
4. Composables.
5. Components.

Adapt to the actual stack profile in use.

## After EACH file

```bash
${stack.backend.lint_cmd}     # or ${stack.frontend.lint_cmd} for frontend
```

Run from the project root. For frontend, also run
`${stack.frontend.typecheck_cmd}` immediately after editing type
definition files.

## After ALL steps in the story

```bash
${stack.backend.test_cmd}    # or ${stack.frontend.test_cmd}
```

## Constraints

- Max LOC per file: `conventions.max_file_loc` (frontend may use
  `max_frontend_file_loc` if defined).
- Max LOC per function: `conventions.max_function_loc`.
- All imports at top of file.
- No commented-out code.
- No hardcoded values — use enums (per `conventions.enums_for_states`),
  environment variables, or DB config.
- Null syntax matches `conventions.null_syntax`.
- Identifier language matches `conventions.naming_language`.
- Tenant scoping (if `conventions.multi_tenant: true`): include
  `conventions.tenant_column_name` in every tenant-scoped query;
  consult `.claude/project/conventions/tenant-isolation.md` if present
  for the project's specific patterns.

Stack-specific rules (e.g., "no try/except in endpoints" for FastAPI,
"all `<script setup lang='ts'>`" for Vue) live in the stack profile and
apply automatically.

### Precedence: the orchestrator prompt beats the story's `Files` table

When the orchestrator's prompt and the story's `Files` table disagree about a
deliverable, **the ORCHESTRATOR PROMPT WINS** — and you MUST report the conflict
explicitly in your final message, naming the dropped deliverable, so the
orchestrator can reassign it to whichever phase owns it.

Do not silently satisfy both. Do not silently satisfy the story.

*REQ-20260801: given "do not write new feature tests", one batch dropped two spec
files listed in its story, flagged the conflict, and Phase 6 picked them up —
correct. Another batch, given the same instruction, wrote 12 tests anyway. Making
this a rule instead of a coin flip is the point.*

## When Done

Report:

- Files created / modified.
- `${stack.*.lint_cmd}` result.
- `${stack.*.test_cmd}` result.
- Any issues found during implementation.
- **Any deliverable in the story's `Files` table that you did NOT produce**, and
  why (see precedence rule above).
- **Any user-visible behavior change the story did not explicitly request.**
  Answer this deliberately, not reflexively — in REQ-20260801 this question
  surfaced a silently-removed dashboard card and a broken image preview that no
  test caught.

**Never end your turn waiting on a background command.** Run the gate, read its
own exit code, and deliver the written report. A run that ends with "I'll wait
for the result" delivers nothing and its self-assessment is lost.
