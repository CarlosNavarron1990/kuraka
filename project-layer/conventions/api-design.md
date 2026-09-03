# API design — golden rules

Derived from `routes/api.php` (939 lines) and `App\Helpers\ApiResponse`, as the
API actually behaves today. Deviations in new endpoints are review findings.

## Response envelope — non-negotiable

Every endpoint returns through `App\Helpers\ApiResponse`:

| Method | Line | Shape |
|---|---|---|
| `ok($data, $message, $status)` | 7 | `{success: true, message, data, errors: null}` |
| `fail($errors, $message, $status, $code)` | 17 | `{success: false, message, data: null, errors}` |
| `okPaginated($paginator, $message, $status)` | 49 | `ok()` plus pagination metadata |

Never `response()->json()` directly. The frontend types this as `ApiEnvelope<T>`
in every `*.models.ts`; a bare JSON response breaks the contract silently —
`res.success` is `undefined`, which is falsy, so the UI reports failure on a
successful call.

## Error codes are part of the contract

`fail()` takes a `$code` that the frontend switches on. These are consumed by
`auth.interceptor.ts` and changing one is a breaking change across both repos:

| Code | Meaning | Frontend reaction |
|---|---|---|
| `INVALID_TOKEN` | Token unverifiable, including expired | Queued refresh + retry (once) |
| `UNAUTHENTICATED`, `MISSING_BEARER`, `INVALID_TOKEN_TYPE` | Session unusable | Logout |
| `TENANT_MISMATCH` | JWT `tid` ≠ resolved tenant | 401 |
| `TENANT_BLOCKED` | Tenant delinquent | Redirect `/account-blocked`, session kept |
| `CAPTCHA_REQUIRED` | Turnstile demanded on login | Show challenge |

Adding a code means adding it to `SESSION_INVALID_CODES` or the relevant branch
in the interceptor **in the same cycle**, or the frontend treats it as a generic
error.

## Naming and shape

- Plural resource nouns, kebab where multiword: `/pets`, `/medical-records`,
  `/payment-requests`, `/cash-register`.
- Nested only one level, for genuine ownership: `/pets/{id}/vaccinations`.
- Actions that aren't CRUD go as a sub-path verb:
  `PATCH /appointments/{id}/status`, `POST /tenant/logo`.
- No version prefix. The API is unversioned — frontend and backend deploy
  together-ish and there are no external consumers except the service-token
  endpoints. `<TODO: confirm with team>` whether that holds once third parties
  integrate.

## Route ordering matters

Lumen matches in declaration order. **Literal segments before parameterized
ones**, or `/appointments/calendar` is captured by `/appointments/{id}`.
`routes/api.php` carries an `ORDEN CORREGIDO` comment above the appointments
block marking where this already bit.

## Middleware composition

```php
// Public but tenant-aware
$router->group(['middleware' => 'tenant'], ...);

// Standard protected group
$router->group(['middleware' => ['tenant','jwt','tenant_block']], function () {
    $router->put('/tenant', [
        'middleware' => Permissions::mw('tenant_settings', 'write'),
        'uses' => 'Tenant\TenantController@update'
    ]);
});
```

Rules:

1. `tenant` **always** before `jwt` — `JwtAuth` compares `tid` against the
   resolved tenant.
2. Per-route authorization goes through `Permissions::mw($module, $access)`,
   never hand-written `'role:admin,vet'`. The helper emits both the role list
   and the plan gate from the central matrix.
3. A route exempt from `tenant_block` (reachable while delinquent) must say why
   in a comment — payment and branding endpoints are the legitimate cases.

## Pagination, filtering, sorting

`okPaginated()` wraps an Eloquent paginator. Query params observed:
`page`, `per_page`, `search`, plus resource-specific filters (`client_id`,
`species`). The frontend builds these with `HttpParams`, omitting empty values.

`<TODO: confirm with team>` there is no documented default or maximum
`per_page`. An unbounded page size is a denial-of-service surface worth capping.

## Status codes

| Code | Used for |
|---|---|
| 200 | Success, including creates in some controllers |
| 401 | Unauthenticated / token problems |
| 403 | Role, plan, tenant-blocked, captcha |
| 404 | Not found — **including cross-tenant access**, since `TenantScope` hides it |
| 422 | Validation failure |

Note 404-not-403 for another tenant's resource is the correct behaviour: it
doesn't leak that the record exists.

## Checklist for a new endpoint

- [ ] Responds through `ApiResponse`
- [ ] In the right middleware group, `tenant` before `jwt`
- [ ] Authorization via `Permissions::mw()`, module registered in all four places
- [ ] Literal segments declared before parameterized siblings
- [ ] Validator scopes uniqueness/existence by `app('tenant')->id` manually
- [ ] Sensitive mutation calls `AuditLogger::log()`
- [ ] Any new error `$code` handled in `auth.interceptor.ts`
