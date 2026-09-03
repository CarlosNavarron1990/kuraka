# Tenant isolation

## Context (auto-extracted from the project)

Single database, one `tenant_id` column on every tenant-owned table. Tenants
reach the app at `{slug}.petsuite.pe`.

Confidence: **HIGH** on the mechanism; the measurements below are also HIGH.

**This is the highest-risk structural issue in the codebase**, and the reason
this file exists: automatic tenant isolation covers **4 of 29 models (14%)**.
Everything else scopes by hand, or does not scope at all.

`kuraka.config.yaml` sets `multi_tenant: true`, `tenant_column_name: tenant_id`.

## Rules

### How the tenant is resolved

`App\Http\Middleware\ResolveTenant` (alias `tenant`) picks the tenant in this
order: `X-Tenant` header → subdomain → (only on `/auth/login`) the domain part
of the submitted email. It binds the result as `app('tenant')` and into
`App\Support\Tenant\TenantContext` (a static holder for places where DI is
inconvenient, e.g. validators).

**`tenant` must precede `jwt` in every route's middleware array**, because
`JwtAuth` compares the JWT `tid` claim against the resolved tenant and returns
`TENANT_MISMATCH` otherwise. The standard protected stack is
`['tenant','jwt','tenant_block']`.

### The automatic path, and how little it covers

`App\Models\BaseModel` is an 11-line shell that does one thing:
`use BelongsToTenant;` (`app/Models/BaseModel.php:10`). The trait
(`app/Traits/BelongsToTenant.php:12-19`) applies `TenantScope` as a global
scope and auto-fills `tenant_id` on `creating`.

| Measurement | Value |
|---|---|
| Models extending `BaseModel` (i.e. auto-scoped) | **4 / 29** — `Product`, `InventoryMovement`, `ProductCategory`, `Client` |
| Models extending `Illuminate\…\Model` directly | 25 / 29 |
| `TenantScope` behaviour when `app('tenant')` is unbound | **no-op** (`app/Scopes/TenantScope.php:13-15`) |

That last row matters: in a context without a resolved tenant (an Artisan
command, a queued job, a test that forgot to bind), the scope silently returns
everything. It fails open, not closed.

### Rules for new and modified code

1. **A new tenant-owned model extends `App\Models\BaseModel`.** Not
   `Illuminate\Database\Eloquent\Model`. This is the default; deviating needs a
   reason in the story.
2. **A new tenant-owned table gets a `tenant_id` column** in its migration,
   plus an index, plus `tenant_id` in any unique constraint (composite, never
   bare — see `create_payment_requests_table.php:40-42` for the pattern and
   its Spanish rationale comment).
3. **`DB::table()` bypasses the global scope entirely.** If you must use it on
   a tenant-owned table, add `->where('tenant_id', $tenantId)` explicitly and
   say so in the story. A `DB::table()` query against a tenant-owned table with
   no tenant predicate is a **BLOCKER**, not a style finding.
4. **`Rule::unique()` and `Rule::exists()` are NOT covered by the global
   scope** — they build their own query builder and never boot the model.
   Scope them manually by `app('tenant')->id`. `App\Http\Validators\PetValidator`
   is the reference implementation.
5. **A test that touches tenant-scoped data must bind a tenant**
   (`app()->instance('tenant', $t)`), or the scope no-ops and the test proves
   nothing.
6. Never trust the JWT `role` claim for authorization — the effective role
   comes from the `user_tenant` pivot, since one user can belong to several
   tenants with different roles. See `workspace-and-deploys.md` for the
   RBAC/plan matrix.

### Frontend side

`TokenService` stores `petsuite_access_token`, `petsuite_refresh_token` and
`petsuite_tenant` in **cookies scoped to `.petsuite.pe`**, so the session
survives the hop to `{slug}.petsuite.pe`. The user profile lives in
`localStorage`, which is **not** shared across subdomains — hence the
`loadCurrentUserOnBootstrap` app initializer in `app.config.ts`, which
re-fetches `GET /me` before any guard runs.

The superadmin surface (`admin.petsuite.pe`) is never sent an `X-Tenant`
header and uses a separate token service, interceptor and guard. Do not reuse
tenant-user plumbing there.

## Examples (sampled from this codebase)

The correct manual pattern, as a model scope rather than an inline `where`:

```php
// app/Models/Payment.php:70-73
public function scopeForTenant($q, $tenantId) { … }
// used as: Payment::withVoided()->forTenant($tenantId)
```

The codebase's own admission of the gap, in a Spanish comment:

```php
// app/Models/Payment.php:38-39
// ver ExcludeVoidedScope para las limitaciones (no cubre DB::table crudo)
```

## Anti-patterns detected in the codebase

Not blocking; flag for a future cleanup story.

1. **Tenant isolation is opt-in and mostly opted out** — 4/29 models carry the
   global scope. Migrating the remaining 25 to `BaseModel` is the single
   highest-value hardening story available.
2. **23/43 controllers use raw `DB::table()`**, re-deriving the tenant
   predicate by hand each time — including four-way joins built inline
   (`MedicalRecordController.php:70-87`).
3. **Tenant/JWT context extraction copy-pasted verbatim three times** —
   `ServiceController.php:15-32`, `MedicalRecordController.php:13-27`,
   `RoleMiddleware.php:14-23` — each re-reading `tenant_id ?? tid` from the
   token, despite `JwtAuth.php:98-103` already putting it on the request and in
   the container. Three copies means three places to get it wrong.
4. **`TenantScope` fails open** when no tenant is bound.
5. **`tenant_id` appears in only 16/46 migrations.** That undercounts the real
   schema — 27 of the migrations are `add_*` column patches and the base tables
   predate this folder — but it does mean the migration history cannot be used
   to prove which tables are tenant-scoped. Check the model and the live schema,
   not the migrations.
6. **Timezone hardcoded per-instance, not per-tenant** —
   `private string $tenantTz = 'America/Lima';`
   (`ValidateAppointmentScheduleService.php:14-15`) in a multi-tenant app.
7. **`/debug-host` (`routes/api.php:21-28`) is public and unauthenticated and
   dumps the entire resolved tenant object.**
