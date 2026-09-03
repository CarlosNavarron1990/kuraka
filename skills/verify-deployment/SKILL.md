---
name: verify-deployment
description: "Verify deployment readiness — Docker builds, nginx config, env vars documented, CI pipeline healthy. Final gate before merge. Used in Phase 6.7."
agent: "`deployment-verifier`"
phase: "6.7 — see `kuraka`"
disable-model-invocation: true
user-invocable: false
---

# Verify Deployment

Final deployment readiness gate before merge to main, for the project
described in `kuraka.config.yaml`.

## Input

- `docker-compose*.yml`
- Dockerfiles (backend, frontend)
- `nginx.conf`
- `.env.example` (root + per-service)
- `.github/workflows/*.yml` (or equivalent CI config)
- Migration files

## Steps

### 1. Validate Docker

```bash
docker compose config > /dev/null
```

### 2. Check env vars

- Grep the codebase for env var reads (`os.environ[...]`, `settings.X`,
  `process.env.X`, equivalent for the configured language).
- Compare against `.env.example` entries.
- Flag missing.

### 3. Check nginx (if changed)

```bash
nginx -t -c nginx.conf
```

### 4. Check CI pipeline (if changed)

- Read `.github/workflows/*.yml` (or equivalent).
- Verify the project's `${stack.backend.lint_cmd}` and
  `${stack.backend.test_cmd}` are invoked (and frontend equivalents if
  `stack.frontend` is present).

### 5. Migrations apply

Apply the migrations against the test DB using
`${stack.database.migration_tool}`:

```bash
# Example for Alembic; equivalent for other tools
alembic upgrade head
```

### 6. Build smoke test (if Dockerfiles changed)

```bash
docker compose build
docker compose up -d
sleep 10
curl -f http://localhost:8000/api/health   # or the project's actual health endpoint
```

### 7. Project-specific checks

Apply every check in
`.claude/project/review-checks/deployment-verifier.md` if it exists.
Common additions: specific env vars required by the project, specific
secrets layout, IP allowlists at the proxy layer.

### 8. Produce report

Use the format from the `deployment-verifier` agent prompt.

## Rules

1. **BLOCKER on missing env vars**.
2. **BLOCKER on invalid docker-compose**.
3. **Smoke test is mandatory if Docker changed**.
4. **Run `verify-output` before returning**.
