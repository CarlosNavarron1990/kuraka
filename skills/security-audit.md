---
name: security-audit
description: "Dedicated security audit of implemented code. Runs OWASP Top 10 checks, secret scan, tenant isolation audit, and authentication audit. Blocks deployment on CRITICAL findings. Used in Phase 5.5."
agent: "`security-reviewer`"
phase: "5.5 — see `kuraka`"
disable-model-invocation: true
user-invocable: false
---

# Security Audit

Perform a focused security review of the changes in this cycle, for the
project described in `kuraka.config.yaml`.

## Input

- Implemented code files modified in Phase 4.
- REQ document (security context).
- Environment / config files (`.env.example`, docker-compose).

## Process

### 1. Load context

Per the `security-reviewer` agent's Context section:

- `kuraka.config.yaml` for paths and tenant convention flags.
- Stack profile for framework-specific security patterns (auth dependency
  mechanism, route declaration syntax, ORM injection vectors).
- `.claude/project/review-checks/security-reviewer.md` for project-specific
  greps (narrower paths, internal patterns).
- `.claude/project/conventions/tenant-isolation.md` if present.
- `.claude/project/lessons-learned/*.md` filtered by `applies_to`.

### 2. OWASP Top 10 scan

Go through each OWASP category and search for patterns in the changed
code. Use `grep` to find violations quickly. See the `security-reviewer`
agent prompt for the full table.

### 3. Secret scan

Execute the universal secret-finding regexes (the framework prompt has
the canonical patterns). Adjust file extensions to the project's
`stack.*.language` values.

For project-specific extra greps (narrower paths, project-internal secret
patterns), apply the commands in
`.claude/project/review-checks/security-reviewer.md` if it exists.

If any match is not from a test fixture, mark as CRITICAL.

### 4. Tenant isolation audit (when `conventions.multi_tenant: true`)

For every modified repository / data-access function:

- Check function signature includes `conventions.tenant_column_name` (or
  context object).
- Check every data-access call filters by the tenant column.
- Flag any function that returns cross-tenant data.

### 5. Auth audit

For every new / modified endpoint:

- Check it has the framework's auth dependency mechanism (see the stack
  profile for the syntax — e.g., `Depends(require_role(...))` for FastAPI).
- Verify role matches the REQ's auth requirements.

### 6. Produce report

Use the output format from the `security-reviewer` agent prompt.

## Rules

1. **CRITICAL blocks merge** — no overrides.
2. **Be explicit about fixes** — show corrected code.
3. **Never disable security as a fix**.
4. **Run `verify-output` before returning**.
