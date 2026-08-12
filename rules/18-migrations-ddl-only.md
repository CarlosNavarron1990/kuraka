# Migrations are DDL-only; reference data lives in the canonical seed

> Established 2026-06-25 (Kuraka REQ-20260625-config-cleanup-and-canonical-seed).

## The rule

1. **Alembic migrations under `backend/migrations/versions/` are DDL-only** from
   `000003` onward: `CREATE/ALTER/DROP TABLE`, columns, indexes, constraints.
   **NO `INSERT`, `op.bulk_insert`, or `op.execute("INSERT …")`** in any migration
   `>= 000003`.
   - `000001` (baseline schema) and `000002` (the historical reference seed) are the
     **deployed baseline** — they are immutable history, do NOT edit them.

2. **ALL reference/seed data lives in the canonical seed**
   `backend/scripts/seed_reference_data.py::seed_reference_data(db)`:
   roles, modules, permissions, role_permissions, categories, coverage_areas,
   platform_config, status_phases, statuses, **status_transitions (all edges)**.
   - The seed is **idempotent** (`ON CONFLICT DO NOTHING`), resolves FK ids by
     `code`/`key` (never hardcodes integer ids), and runs in FK-safe order.
   - It runs **after** migrations at 3 points: `main.py` lifespan (post
     `alembic upgrade head`), `tests/conftest.py setup_database` (after
     `command.upgrade(head)`), and `make seed-reference`.

3. **Adding new reference data → edit `seed_reference_data()`, never a migration.**
   If a new status/transition/role is needed, add it to the seed (idempotently).
   The strict `apply_transition` gate (`apply-transition-strict-gate`) raises 409
   for any unseeded transition edge — so a new transition MUST be added to the seed.

## Why

Separating schema (migrations) from data (one canonical idempotent seed) keeps
migrations clean and re-playable, gives a single source of truth for reference data,
and lets reference data evolve without minting a migration per row. Mixing data
inserts into migrations (the old `000004`) fragmented the seed and made the chain
harder to reason about.

## Enforcement

- A meta-test scans `backend/migrations/versions/*.py >= 000003` and fails on any
  `INSERT`/`bulk_insert`/`op.execute(... INSERT ...)`.
- Reviewers reject any reference-data INSERT added to a migration.
