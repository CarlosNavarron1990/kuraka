---
name: review-migrations
description: "Review Alembic migrations for production safety. Checks zero-downtime, CONCURRENTLY for indexes, expand-contract for renames, downgrade presence. Conditional — only when migrations exist."
agent: "[[migration-reviewer]]"
phase: "5 (conditional) — see `kuraka`"
disable-model-invocation: true
user-invocable: false
---

# Review Migrations

## When to run

Only when the REQ includes changes to `backend/alembic/versions/`.
Otherwise, skip this step entirely.

## Input

- Migration files in `backend/alembic/versions/`
- Frozen schema from Phase 3

## Process

1. List all migration files changed/created in this cycle
2. For each migration, apply the safety checklist in `migration-reviewer.md`
3. Produce findings with severity
4. Verify downgrade() is implemented
5. Estimate execution time on production data size

## Output

Produce a review report with verdict APPROVED / APPROVED_WITH_NOTES / CHANGES_REQUIRED.

See `.claude/agents/migration-reviewer.md` for the full output format.

## Rules

1. **BLOCKER on one-shot destructive change**
2. **HIGH on NOT NULL without default**
3. **MEDIUM on CREATE INDEX without CONCURRENTLY for large tables**
4. **Downgrade is mandatory**
5. **Run [[verify-output]] before returning**
