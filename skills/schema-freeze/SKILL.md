---
name: schema-freeze
description: "Validate and freeze database schema before implementation begins. Ensures table inventory matches the ticket, all names follow conventions, tenant strategy is defined, and FKs are explicit. Gate between Phase 3 and Phase 4."
agent: "`architect-reviewer`"
phase: "3 (gate) — see `kuraka`"
disable-model-invocation: true
user-invocable: false
---

# Schema Freeze

You are executing the Schema Freeze skill — a mandatory gate before
implementation begins for the project described in `kuraka.config.yaml`.

## Purpose

Prevent the #1 cause of rework: implementing against a moving schema.
After this skill runs and the user approves, the schema is FROZEN. No DB
changes during implementation.

## Steps

### 1. Collect all schema definitions

From the approved stories, extract:

- Every table (CREATE or ALTER).
- Every column with type, nullable, default.
- Every FK relationship.
- Every index.
- Every enum.

### 1b. Contract source of truth — observe, do not recall (MANDATORY)

The #1 historical cost across projects (clinica-dental 4 cycles, guai 7 cycles)
is freezing a contract that was **recalled or read from docs** instead of
**observed from the running system**. Before freezing any endpoint, table, or
external-integration contract:

- **Never trust API docs / Swagger / OpenAPI as the source of truth.** They drift
  (phantom route prefixes, hidden required FKs, wrong field names, wrong
  required/optional). Treat them as a hint only.
- **Run an authenticated in-vivo probe** for each new/re-wired endpoint and record
  it: e.g. send malformed JSON → expect 422 to reveal the real required fields;
  use multipart for file endpoints. The freeze must cite the **probe artifact**,
  not the docs, as its source. If RTK is active, run the probe via `rtk proxy <cmd>`
  so the full response body is captured byte-exact (the filtered form may truncate).
- **Every DB column / FK / constraint claim must quote the defining migration**
  (`file:line`). Never assert schema from memory or from `pg_constraint` alone.
- **Verbatim-payload fidelity:** if the user supplied exact request/response
  bodies (Postman, backend, chat), build a `field · type · id-vs-hash/opaque ·
  serialization-format · endpoint` table and diff EVERY generated interface
  against it. A field present in the verbatim body but absent/renamed/retyped, or
  a wrong serialization format (e.g. ISO-8601 vs `Y-m-d H:i:s`), is BLOCKER-adjacent.

### 2. Validate against the ticket

| Table | In Stories | In Ticket | Match? | Action |
|-------|------------|-----------|--------|--------|
| table_a | Yes | Yes | OK | Proceed |
| table_b | Yes | No | JUSTIFY | Need explicit reason |
| table_c | No | Yes | MISSING | Add to stories |

### 3. Naming audit

For EVERY table and column:

- [ ] Name is in `conventions.naming_language`.
- [ ] Name follows the stack profile's naming idiom (snake_case for
  Python/Ruby, camelCase for TypeScript/JS, etc.).
- [ ] Name is descriptive (min 3 chars).
- [ ] No abbreviated names without justification.

### 4. Tenant strategy

If `conventions.multi_tenant: true`, for EVERY table:

- [ ] Has `conventions.tenant_column_name` column (or justified exception).
- [ ] FK to the tenants table defined.
- [ ] All repository / data-access queries will filter by tenant column.

Consult `.claude/project/conventions/tenant-isolation.md` if present for
the project's specific patterns and anti-patterns.

### 5. FK completeness

For EVERY foreign key:

- [ ] Source column defined (table.column).
- [ ] Target defined (table.column, not just table).
- [ ] ON DELETE behavior specified.
- [ ] Index on FK column planned.

### 6. Migration compatibility

- [ ] Migration naming follows the stack profile's convention for
  `${stack.database.migration_tool}`.
- [ ] No column drops without 2-week deprecation.
- [ ] Data migration planned if renaming columns.
- [ ] Downgrade path defined.
- [ ] Project-specific migration conventions respected (e.g., data in
  SQL seeds vs Alembic — see
  `.claude/project/conventions/migrations.md` if present).

### 7. Output: frozen schema document

```markdown
# Schema Freeze — {ticket}

**Date:** {YYYY-MM-DD}
**Status:** FROZEN

## Tables

### {table_name}
| Column | Type | Nullable | Default | FK | Index |
|--------|------|----------|---------|-----|-------|

## Enums
- {EnumName}: value1, value2, value3

## Migration Plan
1. {migration_file}: {description}

## Contract Provenance (per endpoint / external contract)
| Contract | Source of truth | Evidence |
|----------|-----------------|----------|
| POST /api/v1/x | in-vivo 422 probe | {probe output / file} |
| {table}.{col} | migration | {file:line} |

## Approved By
- [ ] User approval
```

Path:
`${architecture.paths.docs_process_root}/schemas/SCHEMA-FROZEN-{ticket}.md`

### 8. Gate

Present to user: "This is the frozen schema. After approval, NO DB
changes during implementation. Approve?"
