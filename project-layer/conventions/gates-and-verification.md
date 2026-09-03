# Gates and verification

## Context (auto-extracted from the project)

This project has **one working automated gate**: the Angular production build.
Everything else is either absent or asserts nothing.

Confidence: **HIGH** — derived from `composer.json`, `package.json`,
`phpunit.xml`, `angular.json`, both `.github/workflows/*.yml`, and a read of
the two frontend spec files.

Rule T7 (`.claude/rules/17-kuraka-token-optimizations.md`) applies with full
force here: **a gate that cannot fail must be marked `SKIPPED (broken: …)`,
never treated as green.**

## Rules

### The gate reality table

| Gate | Command | Status |
|---|---|---|
| Backend lint | — | `SKIPPED (broken: nothing wired)` |
| Backend format | — | `SKIPPED (broken: nothing wired)` |
| Backend typecheck | — | `SKIPPED (broken: no static analyser)` |
| Backend test | `cd petsuite-backend/petsuite-api && vendor/bin/phpunit` | RUNS — asserts nothing about this codebase |
| Frontend lint | — | `SKIPPED (broken: no ESLint at all)` |
| Frontend format | — | `SKIPPED (broken: prettier not installed, no script)` |
| Frontend test | `cd petsuite-fronted/web && npm test` | **CURRENTLY RED** — see below |
| Frontend typecheck/build | `cd petsuite-fronted/web && npm run build` | **THE ONLY WORKING GATE** |
| CI | both workflows | Deploy-only. Neither runs a single test. |

### Why each backend gate is dead

- **Lint / format.** `petsuite-api/.styleci.yml` declares `preset: laravel`,
  but StyleCI is a hosted service — the file alone runs nothing locally and
  nothing in GitHub Actions. `composer.json` has no `scripts.test`, no
  `scripts.lint`, no `scripts.format` (only `post-root-package-install`).
  Reporting `.styleci.yml` as a lint gate is a false green.
- **Typecheck.** No phpstan, no psalm in `require-dev`. Zero occurrences of
  `declare(strict_types=1)` anywhere under `app/`. The strongest static check
  available is a syntax pass, and it is not wired:
  `find app routes -name '*.php' -print0 | xargs -0 -n1 php -l`.
- **Test.** `tests/` contains exactly two files: `tests/TestCase.php` (Lumen
  boilerplate) and `tests/ExampleTest.php` (the stock
  `test_that_base_endpoint_returns_a_successful_response`). **Zero first-party
  tests against ~22,300 LOC.** A green phpunit means "the app booted and `/`
  answered" — nothing more. Never cite it as evidence that a change is correct.

Also note `phpunit.xml:13-15` sets `APP_ENV=testing`, `CACHE_DRIVER=array`,
`QUEUE_CONNECTION=sync` but **no DB override** — the first DB-touching test
written here will hit the connection in the real `.env`. Fix that before
writing it.

### The frontend test gate is red right now

`src/app/app.spec.ts:22` asserts:

```ts
expect(compiled.querySelector('h1')?.textContent).toContain('Hello, web');
```

`App`'s template (`src/app/app.ts:12-15`) renders only `<router-outlet />` and
`<app-toast-container />`. There is no `h1`, so `querySelector` returns null,
`?.textContent` is `undefined`, and the assertion fails. This is un-updated
Angular CLI boilerplate.

**Consequence**: `npm test` cannot be used as a gate until that spec is fixed
or deleted. Do not "work around" it by reading a partial tally — fix it in the
first story that touches the frontend, then the gate becomes usable.

The only real test in the repo is `src/app/core/auth/auth.interceptor.spec.ts`
— and it is good: it asserts that three concurrent 401s collapse into exactly
one `POST /auth/refresh` and that all three retries carry the new bearer token
plus `X-Tenant`. Treat it as the reference for how a spec should look here.

### `npm run build` is the only gate worth defending

`tsconfig.json` sets `strict: true`, `noImplicitOverride`,
`noPropertyAccessFromIndexSignature`, `noImplicitReturns`,
`noFallthroughCasesInSwitch`, and Angular's `strictTemplates: true` +
`strictInjectionParameters: true` + `strictInputAccessModifiers: true`.

Because `strictTemplates` is on, the **full-graph build catches template type
errors that `tsc --noEmit` does not**. Use `npm run build`, not `tsc`.

Caveat: 180 occurrences of `: any` across `src/` routinely defeat it — worst
offenders `calendar.page.ts` (16), `medical-record-detail.page.ts` (12),
`payment-list.page.ts` (11). A green build over an `any`-typed surface proves
little. Prefer tightening types in the file you touch over trusting the gate.

### Gate command integrity (rule T7, restated for this repo)

- Run the gate command **without a pipe** and assert on its own exit code.
  `npm run build | tail` reports the exit code of `tail`. Redirect to a file
  and read the file if the output is too long.
- Assert the **absence of failure markers**, not merely the presence of a
  success marker.
- Before declaring a phase green, confirm the gate you ran **can actually
  fail**. In this workspace that means: only `npm run build` qualifies today.

### What replaces the missing gates

Because automation is absent, verification here is **deterministic
orchestrator checks + a human**, per rule T9:

1. `git diff <baseline>..HEAD -- <path>` for every "I did not touch X" claim —
   run by the orchestrator, never quoted from a developer self-report.
2. `grep` the actual route/URL exercised by a smoke against the route the story
   names.
3. A live authenticated smoke of the changed surface. Angular runtime failures
   (NG0203 and friends) are invisible to `ng build`.
4. `php -l` on every changed PHP file — cheap, and it is the only backend
   static signal that exists.

## Anti-patterns detected in the codebase

Not blocking; flag for a future cleanup story.

1. Zero backend tests against ~22,300 LOC, including auth, tenant isolation and
   billing.
2. `app.spec.ts` shipped broken — nobody has run `npm test` in a long time.
3. Neither CI workflow runs any test or lint step; CI green means "deployed".
4. Prettier is configured (`package.json:8-18`: `printWidth: 100`,
   `singleQuote: true`, `parser: angular` for HTML) but is not a dependency and
   has no script, so formatting depends entirely on each developer's editor.
