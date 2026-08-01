---
name: analyze-requirement
description: "Analyze a Jira ticket or raw requirement and produce a structured REQ document. Used by po-analyst agent in Phase 1 of the workflow."
agent: "`po-analyst`"
phase: "1 — see `kuraka`"
---

# Analyze Requirement

You are executing the PO Analysis skill (Phase 1 of the workflow) for the
project described in `kuraka.config.yaml`.

## Input

The user provides either:

- A Jira ticket key (or equivalent ticket identifier) with description.
- A raw requirement text.

## Steps

### 1. Gather context

Read in this order (the `po-analyst` agent's Context section describes
the full loading sequence):

1. `kuraka.config.yaml` — project root.
2. `.claude/stack-profiles/${stack.backend.framework}.md` — for layer
   responsibilities and idiomatic file paths.
3. `.claude/project/conventions/*.md` — team conventions (architecture,
   tenant isolation, etc.).
4. `.claude/project/glossary.md` if present — domain vocabulary.
5. `.claude/project/lessons-learned/*.md` filtered by `applies_to`
   including `po-analyst`.
6. `docs/arquitectura/domain-model.md` + `docs/discovery/requirements.md`
   (resolved decisions) + `docs/discovery/decisiones-abiertas.md` — when
   present. Proposed tables must be consistent with the frozen domain
   model, and resolved decisions are never silently re-decided (conflicts
   → flag in the REQ).

### 2. Analyze the requirement

Identify:

- **What** needs to be built (features, endpoints, UI).
- **Where** it fits in the architecture (which layers per
  `architecture.layers`, which modules).
- **What tables** are needed (compare against the ticket).
- **What endpoints** are needed.
- **What services / repositories / equivalents** are affected.
- **What risks** exist.

### 3. Produce REQ document

Create the file at
`${architecture.paths.docs_process_root}/REQ-{YYYYMMDD}-{ticket}-{slug}.md`
using the template from the `po-analyst` agent definition.

### 4. Table inventory validation

For EVERY table you propose:

- Is it mentioned in the ticket? Mark "Yes".
- If NOT in the ticket, provide explicit justification or remove it.
- Include the action: CREATE, ALTER, or NONE (reference only).
- If `conventions.multi_tenant: true`, classify each table as
  tenant-scoped (yes/no) with justification for any "no".

### 4b. Contract provenance & verbatim fidelity (external integrations)

For any external service / existing endpoint / webhook in scope:

- Require a **real captured payload** + auth header + (for webhooks) event list.
  Open and parse every referenced fixture before describing it — never from memory.
- Treat Swagger/OpenAPI as a hint, not truth. If no live probe is possible yet,
  mark the contract `UNVERIFIED` so `architect-reviewer` probes it in Phase 3.
- If the user gave verbatim bodies, attach a `field · type · id-vs-hash ·
  serialization-format · endpoint` table for the downstream fidelity diff.
- Classify any new config var as REQUIRED (secret/connection, no safe default)
  vs DEFAULTED (operational constant); flag "N new required vars per env" for sign-off.

### 5. Scope boundary

Be explicit about what is IN scope and OUT of scope. Common mistakes:

- Adding auth / user tables when the ticket doesn't mention them.
- Adding catalog / lookup tables when enums would suffice.
- Proposing tables from other tickets.

### 6. Project-specific checks

Execute every check in `.claude/project/review-checks/po-analyst.md`
if it exists. These may include provider directory enumeration,
mailbox conventions, PII inventory cross-references, etc.

### 7. Present to user

Show the REQ and ask for approval before proceeding to Phase 2.
