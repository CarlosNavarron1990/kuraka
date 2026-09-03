# Workspace shape and deploys

## Context (auto-extracted from the project)

This project is a **workspace of two independent git repositories**, not a
monorepo and not a single package. The workspace root itself is **not** under
git.

Confidence: **HIGH** — the `inspect-report.json` verdict `single-package` is
wrong; corrected against the real directory layout and both
`.github/workflows/`.

| Path | Git repo | Command root |
|---|---|---|
| `petsuite-backend/` | `luiggifigueroa24-ctrl/petsuite-backend` | `petsuite-backend/petsuite-api/` |
| `petsuite-fronted/` | `luiggifigueroa24-ctrl/petsuite-fronted` | `petsuite-fronted/web/` |
| `.claude/`, `docs/`, `tests/kuraka/` | untracked (root `.gitignore`) | workspace root |

The directory and repo name `petsuite-fronted` is misspelled. That is the real
name — do not "fix" it in paths, imports, or CI config.

## Rules

### 1. A change spanning both sides is two commits and two deploys

There is no atomic cross-repo commit. Sequence backend first, then frontend, so
the frontend never ships against an endpoint that does not exist yet. This is
why `workflow.parallel_implementation` is `false` in `kuraka.config.yaml`.

### 2. Adding or changing a module means FOUR edits across both repos

The RBAC matrix and the plan-gating matrix are mirrored on both sides. All four
must move together or the UI and the API disagree:

| # | Repo | File | What |
|---|---|---|---|
| 1 | backend | `app/Support/Permissions.php` | `MODULES`: module → role → `full`\|`read` |
| 2 | backend | `app/Support/Plans.php` | `MODULE_MIN_PLAN` |
| 3 | frontend | `src/app/core/auth/permissions.config.ts` | `MODULE_ACCESS` **+ `ROUTE_MODULE_MAP`** |
| 4 | frontend | `src/app/core/auth/plan-access.config.ts` | `MODULE_MIN_PLAN` |

Routes consume the backend pair through one helper:

```php
// app/Support/Permissions.php:109-114
public static function mw(string $module, string $access = self::READ): array
{
    $roles = implode(',', self::rolesFor($module, $access));
    return ['role:' . $roles, 'plan:' . $module];
}
```

`Permissions::MODULES`' own docblock (`app/Support/Permissions.php:5-19`)
states the three-step rule in Spanish; step 3 there omits `ROUTE_MODULE_MAP`,
which is nonetheless required. **The frontend copies are UX only — the backend
403 is the real barrier.** Never treat a frontend guard as enforcement.

### 3. Backend deploy: SSH to Lightsail, and it does NOT run migrations

`petsuite-backend/.github/workflows/deploy-backend.yml`, on push to `main`:

1. `appleboy/ssh-action` into the Lightsail host
2. `git checkout -- petsuite-api/storage/ || true`
3. `git pull origin main`
4. `docker exec petsuite_api_php composer install --no-dev --optimize-autoloader`
5. `docker restart petsuite_api_php`

The workflow header says so explicitly, in Spanish: migrations are run **by
hand on the server** (`php artisan migrate`) so they can be reviewed before
production. Therefore:

- **Any story containing a migration has a manual deploy step.** It is not
  done when CI is green. Say so in the story's Definition of Done, and name the
  exact `php artisan migrate` invocation.
- Code is a bind-mounted volume, so the restart is what picks up changes.
- Files that live **only on the server** and are never in git:
  `.env`, `docker-compose.yml`, `petsuite-api/storage/keys/*.pem`,
  `petsuite-api/storage/rds-ca.pem`.

### 4. Frontend deploy: build → S3 → CloudFront invalidation

`petsuite-fronted/.github/workflows/deploy-frontend.yml`, on push to `main`:
Node 20 → `npm ci` → `npx ng build --configuration production` →
`aws s3 sync web/dist/web/browser s3://$S3_BUCKET --delete` →
`aws cloudfront create-invalidation --paths "/*"`.

The production build IS the frontend's only static gate, so a broken build
blocks the deploy. That is the one real safety net in the pipeline.

### 5. Neither workflow runs tests

Both pipelines are deploy-only. There is no `phpunit` step and no `npm test`
step in either repo. CI green means "it deployed", never "it works". See
`gates-and-verification.md`.

## Examples (sampled from this codebase)

Local Docker, from `petsuite-backend/` — note there is **no database service**
in the compose file; the DB is external (AWS RDS):

```yaml
# petsuite-backend/docker-compose.yml
services:
  api_php:    # build ./Dockerfile (php:8.2-fpm), mounts ./petsuite-api:/var/www
  api_nginx:  # nginx:1.25-alpine, ports 80/443, mounts ./nginx/default.conf
```

`petsuite-backend/CLAUDE.md:23-27` still documents a compose stack with
`mariadb` + `phpmyadmin` on ports 3306/8081 and a repo root of
`C:\Proyecto\petsuite`. **That is drift** — the current
`docker-compose.yml` has neither service.

## Anti-patterns detected in the codebase

Not blocking; flag for a future cleanup story.

1. `petsuite-backend/CLAUDE.md` refers to the backend root as
   `backend/petsuite-api`; the real path is `petsuite-backend/petsuite-api`.
   The same file omits the `plan`, `tenant_block`, `superadmin_jwt` and
   `service_token` middleware aliases and predates the `Permissions::mw()`
   helper. Treat the **root** `CLAUDE.md` as authoritative.
2. `petsuite-fronted/web/petsuite_dump.sql` — a 240 KB production-shaped
   database dump committed at the frontend project root.
3. `petsuite-backend/petsuite-api/gen_jwt.php` and `test-pdf.php` — stray dev
   scripts at the repo root, not gitignored. `gen_jwt.php` references
   `auth('api')->login()`, which this codebase does not use, and hardcodes
   `/var/www/...` paths. Dead and broken.
4. `routes/api.php:21-38` ships two **public, unauthenticated** debug routes:
   `/debug-host` dumps request headers and the entire resolved tenant object;
   `/debug-routes-services` dumps the route table. Information disclosure in
   production.
