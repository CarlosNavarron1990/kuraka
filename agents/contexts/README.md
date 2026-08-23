# Agent Context Snapshots

Condensed rule references per agent type. Each agent reads ONLY its relevant
rules instead of the whole `rules/` directory — this reduces token consumption
per agent invocation.

## Two tiers of rules — check existence before mapping

- **Framework rules (16–19)** — ship with every Kuraka mount and are ALWAYS
  present in a consumer project: `16-agent-backup`,
  `17-kuraka-token-optimizations`, `18-duplication-aware-refactor`,
  `19-evidence` (plus `18-migrations-ddl-only` / `19-docs-process-repo-root`
  where mounted).
- **Project rules (01–15)** — owned by the consumer project's own git; they do
  **NOT** ship with the framework and exist only in projects that define them
  (historically sie_v2). **Before following any 01–15 row below, run
  `ls .claude/rules/` and skip rows whose file is absent** — do not search for
  or request missing files; their absence is normal, not an error.

## Framework rule-to-agent mapping (always valid)

| Rule | Applies to |
|------|-----------|
| 16-agent-backup | `final-auditor`, orchestrator |
| 17-kuraka-token-optimizations | orchestrator (shapes every subagent prompt; agents don't read it directly) |
| 18-duplication-aware-refactor | `backend-developer`, `frontend-developer`, `code-reviewer` |
| 19-evidence | ALL agents + the orchestrator's own artifacts |

## Project rule-to-agent mapping (only where the files exist)

> `pentest-auditor` (Qhawaq) is a standalone, on-demand **whole-app** security
> auditor (CSRF / TLS / session / SQLi / access control). It is NOT a Kuraka
> phase agent: it reads the same security rules as `Security` (05, 11) plus the
> entire codebase, and writes HTML + Markdown reports under `docs/seguridad/`.
> Its context file is `pentest-auditor-rules.md`.

| Rule | PO | Refiner | Architect | Code Rev | Backend | Frontend | Security | Test Eng | Auditor | Pattern |
|------|:--:|:-------:|:---------:|:--------:|:-------:|:--------:|:--------:|:--------:|:-------:|:-------:|
| 01-solid-principles | | | | x | x | | | | | |
| 02-clean-code | | | | x | x | x | | | | |
| 03-file-organization | | | x | x | x | x | | | | |
| 04-backend-architecture | x | x | x | x | x | | | | | |
| 05-backend-conventions | | x | x | x | x | | x | | | |
| 06-project-structure | x | x | x | x | x | x | | | | |
| 07-providers | | | | * | * | | | | | |
| 08-testing | | | x | x | x | | | x | | |
| 09-frontend-standards | | | | * | | x | | | | |
| 10-code-review | | | | x | | | | | | |
| 11-security-audit | | | | | | | x | | | |
| 12-insurance-api-connector | | | | * | * | | | | | |
| 13-db-migrations | | x | x | | x | | | | | |
| 14-incident-integration | | | | | | | | | | |
| 15-data-mapping-specs | | | | | | | | | | |

`*` = only when the change touches that domain (providers, frontend, insurance APIs)

## Usage

Agents reference their context file in the "Context" section:
```markdown
## Context
Read: `.claude/agents/contexts/{agent}-rules.md` for the list of rules to read.
```

Last updated: 2026-08-22
