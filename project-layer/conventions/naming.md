# Naming and language

## Context (auto-extracted from the project)

This team writes **English identifiers, Spanish comments, and Spanish
user-facing strings**. Those are three separate rules and they are applied
consistently enough to be treated as the convention.

Confidence: **HIGH** — 24/24 backend files and 24/24 frontend files sampled
agree on identifiers and comments. User-facing strings are ~3/4 Spanish with a
real English minority (quantified below).

`kuraka.config.yaml` can only express one `naming_language`; it is set to
`english` because that field governs identifiers. It does **not** license
English comments or English UI copy.

## Rules

### The three-language split

| Layer | Language | Enforce as |
|---|---|---|
| Identifiers — classes, methods, variables, types, DB tables/columns, routes | **English** | finding if Spanish |
| Comments and docblocks | **Spanish** | finding if English (except vendor skeleton) |
| User-facing strings — API `message`, UI copy, toasts, labels | **Spanish** | finding if English |
| Machine-readable error codes | **English SCREAMING_SNAKE** | finding otherwise |
| Commit messages | **Spanish, unaccented, Conventional Commits** | see below |

Evidence: identifiers — `AppointmentController`, `$tenantId`, `medical_records`,
`assigned_user_id`, `planAllowsModule`, routes `/dashboard`, `/upgrade-plan`.
Comments — `app/Helpers/ApiResponse.php:19,24,32`, `app/Http/Middleware/JwtAuth.php:29-35`,
`src/app/app.config.ts:19-22,33-46`, `src/app/core/auth/auth.interceptor.ts:17-19`.
Error codes — `MISSING_BEARER`, `INVALID_TOKEN_TYPE`, `TENANT_MISMATCH`,
`TENANT_BLOCKED`, `CAPTCHA_REQUIRED`, `OUTSIDE_ACCESS_SCHEDULE`.

The only identifier leak is the public route `/libro-reclamaciones`
(`routes/api.php:52`) — a Peruvian legal requirement whose name is fixed by
regulation. Leave it.

### Commit messages

Conventional Commits, Spanish, **unaccented**: `feat(scope): descripcion corta`.
Match the existing history. The CI workflows' own comments are written the same
way (`deploy-backend.yml`, `deploy-frontend.yml` are fully commented in Spanish).

### Backend (PHP)

| Element | Convention |
|---|---|
| Classes | `PascalCase` + role suffix: `*Controller`, `*Service`, `*Validator`, `*Transformer`, `*Middleware`, `*Scope` |
| Methods | `camelCase`; REST verbs `index/show/store/update/destroy` where they fit |
| Variables | `$camelCase` — **0 snake_case variables found across all 43 controllers** (218 distinct camelCase vars) |
| Array / JSON payload keys | `snake_case` (mirrors DB columns) |
| DB tables | `snake_case` plural — `medical_records`, `payment_requests`, `quota_credits`. One exception: the pivot `user_tenant` is singular |
| DB columns | `snake_case`; FKs `*_id`; datetimes `*_at`; booleans `is_*` |
| Migration files | `YYYY_MM_DD_NNNNNN_{verb}_{thing}_table.php`; verbs `create_` (14), `add_` (27), plus `alter_`/`drop_`/`rename_`/`update_`. The timestamp suffix is usually hand-written (`000001`), not artisan-generated |
| Routes | kebab-case URIs, array action form `['uses' => 'Controller@method']`. **No named routes** — 0 occurrences of `'as'` in `routes/api.php` |
| Middleware aliases | `snake_case` (`tenant_block`, `superadmin_jwt`, `service_token`) |
| States / roles / plans | `final` const-holder classes in `app/Support/` — `AppointmentStatus`, `UserRole`, `Plans`, `Permissions`. **Not** native PHP enums. Magic strings are a finding |

**Nullable syntax in PHP is `?T`** for parameters and return types
(`?int $x`, `: ?string`); `T|null` in docblocks.

Typing is partial and layer-dependent, and this is the convention to *improve*
rather than copy:

- Services are well typed — `JwtService.php:11-13` typed properties, `: array` /
  `: string` / `: void` returns; `ValidateAppointmentScheduleService.php:17-23`
  fully typed including `?int`.
- Controllers mostly are not — **0 of 5 sampled controllers type their action
  return**. Private helpers *are* typed (`ServiceController.php:15` `: int`).
- `declare(strict_types=1)` appears **nowhere** under `app/`.

Rule for new code: **type service signatures fully; type new private helpers;
type new controller actions where the file already does so.** Do not add
`declare(strict_types=1)` to an existing file as a drive-by — it changes
coercion behaviour for the whole file.

### Frontend (TypeScript / Angular)

| Element | Convention |
|---|---|
| Files | **kebab-case, always.** The only uppercase filename in `src/` is the stray `NotificationHelper.php` |
| File suffixes | `.page.ts` (36) for routed screens, `.component.ts` (37) for reusables and modals. Also `.api.ts` (26), `.routes.ts` (15), `.service.ts` (14), `.models.ts` (6), `.guard.ts` (5), `.config.ts` (5), `.store.ts` (4), `.interceptor.ts` (3), `.mapper.ts` (2) |
| Classes | Match the file suffix — `PetFormComponent`, `SalesReportPage`, `AppointmentsApi`, `ClientsStore` |
| Selectors | `app-` prefix (62/66), matching `angular.json` `"prefix": "app"` |
| Route consts | `SCREAMING_SNAKE` — `CLIENTS_ROUTES`, `SUPERADMIN_ROUTES` |
| Signals | bare camelCase; private backing signal `_name`, exposed via `computed()`. **No `$` suffix** — `$` is reserved for observables |
| Observables | `name$`; the private subject `nameSubject` |
| Services | `*.api.ts` = thin HTTP wrapper in `data-access/`; `*.service.ts` = cross-cutting singleton in `core/services/`. All `@Injectable({ providedIn: 'root' })` |
| DTO fields | **`snake_case`**, mirroring the PHP contract, inside otherwise-camelCase TS |
| Interfaces | `PascalCase`, no `I` prefix |
| DI | `inject()` (301 occurrences) over constructor injection (15 files) |

**Nullable syntax in TypeScript is `T | null`.** Under `strict: true`,
`field?: T` (optional property) and `field: T | null` (nullable) are **not**
interchangeable — an acceptance criterion must say which one it means.

### i18n

**There is none.** No `@angular/localize`, no `ngx-translate`, no `i18n=`
attributes, no locale files. Spanish copy is hardcoded in templates, in
`auth.interceptor.ts:51-65`, and in config maps like `ROLE_LABELS`
(`permissions.config.ts:23-26`).

`<TODO: confirm with team>` — is single-language Spanish a permanent decision,
or deferred debt? Adding a second language today means touching every template.

## Examples (sampled from this codebase)

Spanish rationale comments are a real strength here and should be preserved and
imitated — they explain *why*, not *what*:

- `app/Http/Middleware/JwtAuth.php:29-35` — why `$next()` sits outside the try
- `app/Services/Auth/JwtService.php:58-68` — why the `role` claim is only informational
- `app/Support/Permissions.php:5-19` — the module-addition procedure
- `src/app/core/auth/auth.interceptor.ts:17-19,31-33,104-108` — the refresh policy
- `src/app/app.config.ts:47-92` — why the app initializers exist

## Anti-patterns detected in the codebase

Not blocking; flag for a future cleanup story.

1. **User-facing message language is inconsistent.** Of ~300 `'message' => …`
   literals in controllers, ~223 are Spanish and ~26 clearly English. The same
   controller disagrees with itself: `AuthController.php:100`
   `'Credenciales inválidas'` vs `AuthController.php:316` `'Invalid credentials'`.
   Also English: `'Validation error'` (`AuthController.php:47`),
   `'Missing tenant context'` (`ServiceController.php:38`),
   `'Tenant required'` / `'Tenant not found'` (`ResolveTenant.php:39,50`).
   **New strings go in Spanish.**
2. **422 bodies are mixed-language.** No validator passes a `$messages` array,
   so field-level errors fall through to Laravel's English defaults ("The
   client id field is required") inside a Spanish envelope
   (`'Validación fallida'`, `MedicalRecordController.php:418`).
3. **Two validation rule syntaxes.** Validator classes use the array form
   `['required','integer']` (`AppointmentValidator.php:9`); controllers that
   bypass them use the pipe form `'required|email'` (`AuthController.php:40`).
4. **Two competing validation entry points** — the static `*Validator` classes
   vs `app/Http/Requests/AppointmentChangeStatusRequest.php`, which itself
   calls `response()->json()`.
5. **Change-log comments left in code** instead of relying on git —
   `// ✅`, `// ← NUEVO`, `// ← AGREGAR ESTA LÍNEA`. Backend:
   `AuditLogger.php:13,22`, `AppointmentValidator.php:15-20`,
   `PetTransformer.php:63-64`. Frontend: `src/app/app.ts:12`,
   `pet-form.component.ts:27-28`.
6. **Docblocks are prose-only and sparse** — ~262 `/**` vs 328 `public function`,
   heavily skewed (`SuperAdminTenantController` has 0 for 9 public methods).
   Where they exist they carry no `@param`/`@return`; full tag-style docblocks
   appear only in untouched vendor skeleton. This is acceptable — the inline
   Spanish `//` rationale comments carry the real information.
7. **Four `ps-` selectors** break the `app-` prefix: `ps-pet-form`,
   `ps-client-form`, `ps-appointment-form`, `ps-appointment-modal`.
8. **`cookie.util.ts`** is the lone singular `.util.ts` among four `.utils.ts`.
9. **180 `: any` in `src/`** defeating `strict: true`, plus 12 stray
   `console.log` and 14 native `alert()` calls used for validation UX despite a
   real `ToastService` existing.
