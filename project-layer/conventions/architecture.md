# Architecture

## Context (auto-extracted from the project)

This team uses a **thin-controller Lumen backend** (controller → service →
model, with validators and transformers as cross-cutting adjuncts) and a
**feature-per-folder standalone Angular frontend**.

Confidence: **HIGH** on what the patterns are; **MEDIUM** on how consistently
they are followed — roughly half the backend predates the convention, and the
frontend uses four different folder layouts. Both splits are quantified below.

## Rules

### Backend: controller → service → model

`kuraka.config.yaml` declares `architecture.layers: [controller, service, model]`.
The full request shape is:

```
route (routes/api.php)
  → middleware stack           app/Http/Middleware/*
  → controller                 app/Http/Controllers/**
      ├─ validator             app/Http/Validators/*Validator.php  (static validateCreate/validateUpdate)
      ├─ service               app/Services/**                     (business logic)
      ├─ transformer           app/Transformers/*Transformer.php   (response shaping)
      └─ ApiResponse::ok|fail|okPaginated                          app/Helpers/ApiResponse.php
  → model                      app/Models/**
```

`validator` and `transformer` are **not ordered layers** — they are helpers a
controller calls directly. Do not treat "controller called a transformer" as a
layer skip.

Rules for new and modified code:

- **A controller wires; it does not decide.** Anything beyond a guard clause,
  a validator call, a service call and a transformer call belongs in a service.
- **A service never returns an HTTP response.** Services throw or return data.
  Only controllers and middleware speak `response()`.
- **Every response goes through `ApiResponse`** — `ok()`, `fail()`,
  `okPaginated()` — producing `{success, message, data, errors}`. Never raw
  `response()->json()` from a controller.
- **`DB::table()` is a last resort.** It bypasses global scopes, casts,
  accessors, soft deletes and model events. In a multi-tenant app that is a
  data-leak vector, not a style preference. See `tenant-isolation.md`.
- Sensitive mutations call `App\Helpers\AuditLogger::log()`.
- Appointment status is a state machine: `App\Support\AppointmentStatus::canTransition()`
  plus `ChangeAppointmentStatusService` is the **only** place that may write
  `appointments.status`; it also appends to `AppointmentStatusHistory`.
- `routes/api.php` (~939 lines) is the single routing file. Declare literal
  segments before parameterized ones — `$router` matches in declaration order.

### Honesty note: half the backend does not follow this

Measured over all 43 controllers:

| Observation | Count |
|---|---|
| Controllers issuing raw `DB::table()` directly | **23 / 43 (53%)** |
| Controllers using Eloquent `::where(` directly | 9 / 43 (21%) |
| Controllers importing anything from `App\Services` | 16 / 43 (37%) |
| Controllers using `ApiResponse::` | 25 / 43 (58%) |
| Raw `response()->json(` call sites across `app/` | **355, in 35 files** |
| LOC in `app/Http/Controllers/` vs `app/Services/` | 12,327 vs 4,512 |

**Enforce the layering for NEW and MODIFIED code only. Never retro-flag an
untouched legacy controller.** A reviewer who opens `MedicalRecordController.php`
(1,278 LOC) and files findings against code the story did not touch is
generating noise, not signal. Scope every finding to the diff.

When a story *does* modify one of these files, the bar is: leave the touched
function better (route the new path through a service), not rewrite the file.

Two DB-access styles coexist by vintage: Query Builder (`DB::table`) in the
older large controllers, Eloquent + model scopes (e.g.
`Payment::withVoided()->forTenant()`, `app/Models/Payment.php:70-73`) in the
newer ones. Follow the style already present in the file you are editing unless
the story says otherwise.

### Frontend: feature-per-folder, standalone components

The majority convention (11 of 23 features) is:

```
src/app/features/<feature>/
  <feature>.routes.ts          lazy route group, exported as SCREAMING_SNAKE const
  data-access/*.api.ts         @Injectable({providedIn:'root'}), inject(HttpClient) + inject(API_BASE_URL)
  data-access/*.models.ts      DTOs (snake_case fields, mirroring the PHP contract)
  data-access/*.store.ts       shared state (only where genuinely shared)
  ui/<component>/              .ts + .html + .css triplet
```

Cross-feature pieces live in `src/app/shared/{components,ui}`; cross-cutting
singletons in `src/app/core/{auth,config,services,utils}`.

Rules:

- **Components never inject `HttpClient` directly** — always go through a
  `data-access/*.api.ts`. Holds for ~94% of files; 6 known violations
  (`tenant-settings-modal`, `change-password-modal`, `my-profile-modal`,
  `onboarding-wizard.page`, `receipt-viewer`, and `prescriptions.service`).
- **Lazy-load routed features** with `loadComponent` / `loadChildren`. Two
  eager exceptions exist in `app.routes.ts` (`LoginComponent`,
  `LayoutComponent`).
- Guards are functional `CanActivateFn` + `inject()`; `roleGuard` returns a
  `createUrlTree` (never boolean `false`) so the user lands on
  `/access-denied` or `/upgrade-plan`.
- `authInterceptor`'s failure policy is deliberate and documented in comments:
  only a 401 with code `INVALID_TOKEN` triggers a single queued
  refresh-and-retry (one in-flight refresh serves all concurrent failures);
  other `SESSION_INVALID_CODES` log out; 403/404/422/5xx raise a toast and
  never destroy the session; `403 TENANT_BLOCKED` redirects to
  `/account-blocked`. **Preserve that shape.**
- Interceptor order matters and is fixed:
  `[authInterceptor, superadminInterceptor, timeoutInterceptor]`.
- Three `provideAppInitializer` hooks pre-load auth state so guards see a
  resolved user/plan on hard refresh. `loadCurrentUserOnBootstrap` re-fetches
  `GET /me` before any guard runs, because the profile lives in `localStorage`
  which is **not** shared across `{slug}.petsuite.pe` subdomains (tokens are,
  via cookies scoped to `.petsuite.pe`).

### State: signals and BehaviorSubject coexist, with no bridge

This is the frontend's most important structural caveat.

| Idiom | Count |
|---|---|
| `signal(` / `signal<` | 74 + 82 |
| `computed(` | 26 |
| `effect(` | 3 |
| `new BehaviorSubject` | **11** |
| `new Subject` | **4** |
| `toSignal()` — the bridge between them | **0** |

(15 subject instances in total, spread over 8 files. The bare string
`BehaviorSubject` appears 15 times, but 4 of those are imports and type
annotations, not instantiations — count `new BehaviorSubject` when re-checking.)

Of the 4 `*.store.ts` files, **3 are RxJS-only** (`vaccination-reminders.store.ts`,
`clients.store.ts`, `medical-records.store.ts`) and only `core/auth/auth.store.ts`
is signal-based. Stores are the exception anyway — 4 stores for 23 features;
most pages hold state as plain mutable class fields and call the API in
`ngOnInit`.

Rules:

- **Do not mix the two idioms inside one feature.** Match whatever the feature
  already uses. Introducing a `BehaviorSubject` into a signal-based feature (or
  vice versa) without a `toSignal()` bridge creates two sources of truth.
- Naming keeps them distinguishable: signals are bare camelCase with an
  optional `_` -prefixed private backing signal exposed via `computed()`;
  observables end in `$` and their private subject in `Subject`.
- Manual subscriptions need `takeUntilDestroyed` (used 15×) or the async pipe.

`<TODO: confirm with team>` — is signals the intended destination for all new
state, with RxJS stores to be migrated? The code shows a drift in that
direction but no decision record.

## Examples (sampled from this codebase)

Thin controller, the pattern to follow — `app/Http/Controllers/ServiceController.php`
(267 LOC, 0 try/catch, delegates validation to `ServiceValidator`, shapes via
`ServiceTransformer`).

The RBAC/plan middleware helper, used on protected routes:

```php
// routes/api.php:174
$router->put('/tenant', [
    'middleware' => Permissions::mw('tenant_settings', 'write'),  // ['role:admin', 'plan:tenant_settings']
    'uses' => 'Tenant\TenantController@update'
]);
```

The registered middleware aliases (`bootstrap/app.php:86-94`) — the full set,
which `petsuite-backend/CLAUDE.md` under-documents:

| Alias | Class |
|---|---|
| `tenant` | `App\Http\Middleware\ResolveTenant` |
| `jwt` | `App\Http\Middleware\JwtAuth` |
| `role` | `App\Http\Middleware\RoleMiddleware` |
| `plan` | `App\Http\Middleware\PlanMiddleware` |
| `superadmin_jwt` | `App\Http\Middleware\JwtAuthSuperAdmin` |
| `tenant_block` | `App\Http\Middleware\TenantBlockMiddleware` |
| `service_token` | `App\Http\Middleware\ServiceTokenAuth` |

Global middleware: `App\Http\Middleware\CorsMiddleware` (`bootstrap/app.php:81-84`).
`Authenticate.php` and `ExampleMiddleware.php` are unregistered Lumen skeleton
— dead.

**Middleware order is load-bearing**: `tenant` must precede `jwt`, because
`JwtAuth` compares the JWT `tid` claim against the resolved tenant. The
standard protected group is `['tenant','jwt','tenant_block']`.

Three separate auth surfaces, do not conflate them:

1. **Tenant users** — RS256 JWT from `App\Services\Auth\JwtService` (keys in
   `storage/keys/*.pem`, gitignored). Middleware `jwt`. Access token +
   30-day refresh; `/auth/refresh` does **not** rotate the refresh token.
2. **Superadmin** (`admin.petsuite.pe`) — entirely separate: `superadmin_jwt`,
   own `SuperAdminTokenService` / `superadminInterceptor` /
   `superAdminAuthGuard`, routes under `/superadmin/*`, never sent `X-Tenant`.
3. **Machine-to-machine** — `service_token`, for the external commercial agent
   (tenant lookup by RUC, payment-request status).

## Anti-patterns detected in the codebase

Not blocking; flag for a future cleanup story.

1. **Fat controllers** — `AuthController` 1,285 LOC, `MedicalRecordController`
   1,278, `PaymentController` 1,086, `SuperAdminTenantController` 907,
   `AppointmentController` 859. `MedicalRecordController.php:70-87` builds a
   four-way `leftJoin` inline.
2. **JWT-context extraction copy-pasted verbatim three times** —
   `ServiceController.php:15-32`, `MedicalRecordController.php:13-27`,
   `RoleMiddleware.php:14-23` — despite `JwtAuth.php:98-103` already putting
   the same data on the request and in the container.
3. **The response envelope is hand-rolled 355 times.** Drift already exists:
   `ServiceController.php:38` returns only `{message}`;
   `AuthController.php:98-104` adds a 5th key `captcha_required`. Pagination
   has three shapes — `ApiResponse::okPaginated()` emits `items/pagination/links`,
   `ServiceController.php:77-85` emits `items/pagination`, `PaymentController.php:75-80`
   emits `items/meta`.
4. **A service returns an HTTP response** —
   `app/Services/Appointments/ChangeAppointmentStatusService.php` calls
   `response()->json(`, breaking transport-independence. Contrast
   `ValidateAppointmentScheduleService`, which correctly throws.
5. **`env()` called at runtime outside `config/`** — `JwtService.php:17-19,24,30`,
   `ValidateAppointmentScheduleService.php:35`, `Handler.php:85`. Silently
   breaks under `config:cache`.
6. **Business config hardcoded in a service** —
   `private string $tenantTz = 'America/Lima';`
   (`ValidateAppointmentScheduleService.php:14-15`) in a multi-tenant app.
7. **Token detail leaked to clients**, guarded only by a TODO comment —
   `JwtAuth.php:45-46` returns `get_class($e)` with the note
   `// si no quieres exponer detalle en prod, luego lo quitamos`.
8. **`ApiResponse::fail` has a dead no-op branch** — `ApiResponse.php:38-40`.
9. **Frontend folder layout diverges four ways** across 23 features:
   `data-access/`+`ui/` (11), `data-access/` only with components at the
   feature root (4), `pages/` (2: payments, reports), `pages/`+`components/`+`services/`
   (1: prescriptions), flat with no subfolders (4), and `auth` as a namespace of
   sub-features (1). Several `data-access/`+`ui/` features also drop a page at
   the feature root, bypassing `ui/`. `shared/` is itself split into
   `shared/components/` (9) and `shared/ui/` (1).
   **Follow the majority convention for new features.**
10. **Two different pet APIs** — `features/clients/data-access/pets.api.ts` and
    `features/pets/data-access/pets.api.ts`.
11. **`ApiEnvelope<T>` is duplicated 14 times and a second name `ApiResponse<T>`
    6 more — 20 copies of the same 4-field type, with no shared definition in
    `core/`.** `PaginationMeta` is likewise re-declared per feature.
12. **No `OnPush` anywhere** (0 occurrences) and no signal `input()`/`output()`
    (0 occurrences; 82 `@Input()`, 48 `@Output()`, 74 `EventEmitter`). The
    compensation is **120 manual `detectChanges()` calls across 19 files** —
    a smell, not a convention to copy. Zone.js is still in use.
13. **Giant components** — `superadmin-tenants.page.ts` 897 LOC,
    `calendar.page.ts` 861, `sales.page.ts` 687.
14. **`src/app/services/NotificationHelper.php`** — a Laravel PHP class inside
    the Angular source tree. Not compiled; pure dead weight.
