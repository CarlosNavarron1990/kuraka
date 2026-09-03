# Query and data-access patterns

How this codebase reads and writes the database, what is safe, and what is the
standing hazard.

## There is no repository layer

Data access happens in two shapes, and knowing which one you are in decides
whether tenant isolation is automatic:

| Shape | Tenant filter | Where |
|---|---|---|
| Eloquent on a `BaseModel` subclass | **Automatic** via `TenantScope` | The intended path |
| `DB::table()` raw builder | **None. You write it or it leaks.** | 23 of 43 controllers |

`App\Services\*` is where non-trivial logic belongs, but services are not a
repository abstraction — they use Eloquent directly. Do not introduce a
repository pattern for a single story; it would be the only one in the codebase.

## The standing hazard: raw queries

`TenantScope::apply()` adds `WHERE tabla.tenant_id = app('tenant')->id` to
Eloquent queries only. It cannot see a `DB::table()` call.

**Rule: every raw query against a table carrying `tenant_id` must show its
filter in the same diff.** No exceptions, no "the controller already checked".

```php
// WRONG — returns every tenant's pets
DB::table('pets')->where('species', $species)->get();

// RIGHT
DB::table('pets')
    ->where('tenant_id', app('tenant')->id)
    ->where('species', $species)
    ->get();
```

A cross-tenant leak does not throw. It returns another clinic's data, renders
fine, and is discovered by a customer.

### Validators are the second blind spot

`Rule::unique()` and `Rule::exists()` build their own query with no model
attached, so the global scope never runs:

```php
Rule::unique('pets', 'name')->where(fn ($q) => $q->where('tenant_id', app('tenant')->id))
```

`App\Http\Validators\PetValidator` is the reference implementation. Any new
uniqueness or existence rule on a tenant table copies that shape.

## Transactions

There is **no consistent transaction discipline**. Multi-write flows
(sale → inventory → payment → cash movement) do not show an enclosing
`DB::transaction()`.

For new or modified code:

- Wrap multi-table writes that must succeed together in `DB::transaction()`.
- Keep external HTTP calls **outside** the transaction — a slow NubeFact must
  not hold a row lock. Write the local state, commit, then call out, then record
  the outcome.
- Do not widen an existing untransacted flow into a transaction as a side effect
  of an unrelated story; that is its own change with its own risk.

`<TODO: confirm with team>` whether to retrofit transactions into the sale flow.
See `docs/arquitectura/flujos/venta-y-comprobante.md` — it is the highest-value
candidate.

## Idempotency

No endpoint accepts an idempotency key. A double submit can duplicate a sale.
`<TODO: confirm with team>`. If you add one, `receipts` is where it matters
first.

## N+1

No eager-loading convention is enforced and there is no query-count assertion
anywhere. When you touch a list endpoint:

- Add `->with([...])` for relations the transformer reads.
- Check the transformer — that is where a lazy relation gets pulled per row.

Since there is no profiler wired up, the cheap check is reading the transformer
alongside the query, not measuring.

## Soft deletes

`clients` and `pets` carry `deleted_at`. `forceDestroy` and `restore` routes are
restricted to `admin`/`superadmin`. When querying these tables raw, remember
that Eloquent's soft-delete filter is also absent from `DB::table()` — you get
deleted rows back unless you exclude them.

## Timestamps and timezone

The database stores **naive Lima time** and PHP is the only writer.
`DB_TIMEZONE=-05:00` is mandatory in every environment: without it MySQL's
`DEFAULT current_timestamp()` writes UTC and lands 5 hours ahead.

Consequence for queries: never mix a MySQL-generated timestamp with a
PHP-generated one in a comparison without checking which wrote it.

## Migrations

`database/migrations/` holds **incremental patches**, not the full schema — the
bulk already exists in the target database. Before assuming a table or column is
absent, check the real database, not the migration folder.

CI **never** runs migrations (`deploy-backend.yml` says so deliberately). A
story with a migration needs a coordinated manual deploy step, planned in the
story.

## Review checklist

- [ ] Every `DB::table()` on a tenant table shows its `tenant_id` filter
- [ ] `Rule::unique()` / `Rule::exists()` scoped manually
- [ ] Multi-table writes wrapped in a transaction; HTTP calls outside it
- [ ] List endpoints eager-load what the transformer reads
- [ ] Raw queries on `clients`/`pets` account for `deleted_at`
- [ ] Migration present ⇒ story carries a manual deploy step
