---
name: gap-analysis
description: "Produce a pre-REQ gap analysis document that bridges a source codebase (current state) and a target architecture (desired state). Use this skill WHENEVER the user mentions migration, refactor, port, rewrite, modernization, or version upgrade between two explicit codebases — including phrases like 'migrate X from v1 to v2', 'analyze existing module for refactor', 'compare module A vs module B', 'gap analysis', 'feasibility study', 'pre-REQ research'. Output is a structured document with Parts A (origin analysis), B (target patterns), C (bridge mapping), D (next-phase recommendations) that feeds into Kuraka Phase 1. Invokable by po-analyst, amauta, or architect-reviewer. Always prefer this skill over writing a formal REQ when the input is a migration/refactor ticket — the formal REQ comes AFTER the gap analysis."
user-invocable: false
context: fork
---

# Gap Analysis — Pre-REQ Bridge Document

> Skill for producing the **bridge document** between "what exists" and
> "what must exist" BEFORE writing a formal REQ. It does not replace the
> REQ; it feeds it.

Kuraka frames a formal REQ (Phase 1) with implementable stories. But when
the input is a **migration / refactor between two codebases**, the PO
first needs to understand what exists today, what patterns exist in the
target, and how to bridge them. That understanding is the gap analysis.

---

## 1. When to use this skill

Use this skill if **any** of these conditions holds:

- The ticket / user mentions "migration", "port", "rewrite", "refactor",
  "modernization", "upgrade" with two explicit codebases.
- There are distinct versions of the same system as origin and target
  (v1 → v2, legacy → modern, JS → Python, etc.).
- The user asks to analyze existing code as **input for a future REQ**,
  not as a direct REQ.
- You are `po-analyst` / `amauta` / `architect-reviewer` and the ticket
  is a migration — apply this skill before the formal REQ.

**Do NOT use this skill when:**

- It's a greenfield feature with no existing origin → use `analyze-requirement`.
- It's onboarding a whole project without Kuraka → use `amauta` with its
  brownfield flow.
- The analysis already exists and it's time to produce the formal REQ
  → use `analyze-requirement` taking the GAP doc as input.

---

## 2. Required inputs

Before reading code, confirm with the user (or extract from context) the
4 inputs below. If any is missing or ambiguous, **ask before proceeding**:

| Input | What it is | Example |
|---|---|---|
| **Source context** | Absolute path(s) + available docs of the origin | `legacy_repo/src/providers/<name>/` |
| **Target context** | Absolute path(s) + ≥2 reference implementations in the destination | `${architecture.paths.backend_root}/api/services/providers/<existing1>/`, `<existing2>/` |
| **Ticket reference** (optional) | Ticket key or reference for traceability | TICKET-XXX |
| **Scope boundary** | What is in and out of scope | "Inbound only; outbound is out" |

Don't assume. Asking 30s now avoids a 500-line misaligned document.

---

## 3. Output: location and format

Create the document at:

```
${architecture.paths.docs_process_root}/GAP-{YYYYMMDD}-{ticket-or-slug}.md
```

Prefix **`GAP-`** (not `REQ-`) — signals it's pre-REQ. The formal REQ
derived from it will have its own `REQ-` file in Phase 1 of Kuraka.

### Mandatory template (Parts A / B / C / D)

```markdown
# Gap Analysis — {Ticket} {Title}

## 0. Metadata
- Ticket: {key + link}
- Date: {YYYY-MM-DD}
- Origin: {path + 1-line description}
- Target: {path + 1-line description}
- Scope: {in / out}
- This document is NOT the formal REQ. It feeds Phase 1 Kuraka (analyze-requirement).

## Part A — Origin analysis (current state)

### A.1 File inventory
Table: file | LOC | 1-line purpose

### A.2 Integration type / architecture
Protocol(s), libraries, authentication, external endpoints, internal dependencies.

### A.3 Main flows
For each relevant flow (inbound / outbound / sync):
- Trigger
- Event / message types supported
- Parsing / transformation (cite file:line, flag fragilities)
- Side effects (DB, emails, external calls)

### A.4 Hardcoded values detected
Complete table: file:line | value | category | observations

### A.5 Evident problems
Checklist with concrete file:line:
- Hardcoded codes
- Fragile parsing
- No transactions / weak consistency
- Silent error handling
- No structured logging
- No typing
- Imports inside functions
- No tests

### A.6 Dependencies
Internal (modules in the same repo) + external (libraries, APIs).

### A.7 Complexity and size
Total LOC + per file, long functions, files exceeding `conventions.max_file_loc`.

## Part B — Target architecture (available patterns)

### B.1 Base classes / primitives
For each one: file, contract (key methods), when to extend it.

### B.2 Shared components
Factories, registries, rule services, cross-cutting utilities.

### B.3 Reference implementations (≥2)
Analyze ≥2 modules already implemented in the target:
- File structure
- How they extend the base classes
- Patterns they replicate (examples with file:line)
- Schemas / types used

### B.4 Ticket vs reality discrepancies
If the ticket mentions references that don't exist (e.g., a module that
was renamed or never created), document it here as a blocking GAP.

### B.5 Pre-conclusion of applicable base class
Given the origin's integration type (A.2), which base class in the
target applies? (justified)

## Part C — Bridge from origin → target

### C.1 Hardcoded value → target mapping
For each value in A.4, indicate where it should live in target
(DB / config / enum / removed).

### C.2 Flows origin → target classes
Table: origin flow | equivalent target class | required changes

### C.3 Proposed structure
File tree proposed in target, with justification per file. File paths
follow the stack profile's idiomatic layout for `${stack.backend.framework}`.

### C.4 Identified risks (≥5)
Table: risk | impact (H/M/L) | mitigation

### C.5 Upstream dependencies
What must exist before starting implementation (DB migrations, seeds,
configuration, business decisions).

### C.6 Open questions for the team
Numbered list of ambiguities requiring human decision. Blockers first.

## Part D — Recommendations for next steps

### D.1 Immediate next phase
Concrete actions (DB, schema, seeds, credential rotations, etc.) to
move to the formal REQ.

### D.2 Expected content of the formal REQ
Which sections the REQ should have when written, specific to this case.

### D.3 Warnings for implementation
Sensitive points (secrets, data migration, backward compatibility) that
must appear in the story / implementation.

### D.4 Refactor proposals (when applicable)
If you detected duplicated logic across reference implementations in
target, propose extractions (see `.claude/project/conventions/` for the
project's duplication-aware-refactor rule if present).
```

---

## 4. Recommended process (order)

1. **Context digest**: list files and `wc -l` in both codebases before
   reading content. Embed the digest at the top of the prompt if you'll
   invoke subagents.

2. **Wide skim**: read structure (trees, `__init__.py`, `index.js`,
   function names) before details.

3. **Part A first, then B**: don't mix. Completing A fully before
   entering B reduces re-reads.

4. **Part C at the end of A+B**: the mapping depends on both.

5. **Part D derives from C**: don't improvise — each recommendation must
   trace to a line in C.

6. **No auto-verification**: don't run verification checks inside the
   skill. The orchestrator validates at the end.

---

## 5. Writing rules

- **Every assertion cites `file:line`** — if you can't cite, it's not an
  assertion, it's a hypothesis (mark it as such).
- **Don't modify any source file** — you only create the document under
  `${architecture.paths.docs_process_root}/`.
- **Don't invent conventions** — if you didn't see it in the real code,
  mark it as TODO.
- **LOC with `wc -l`**, not by sight.
- **Ticket vs real code contradictions** → document them explicitly in
  B.4, don't silence them.
- **Identifier language**: per `conventions.naming_language`.

---

## 6. Completeness criteria

The GAP doc is ready to pass to Phase 1 Kuraka when:

- Parts A, B, C, D complete (no placeholders).
- A.4 lists **≥10 concrete hardcoded values** with file:line.
- B.3 analyzes **≥2 reference implementations**.
- C.1 has complete mapping for every hardcoded value.
- C.4 lists **≥5 identified risks**.
- C.6 enumerates open questions, with blockers visually separated.

---

## 7. Composition with Kuraka agents

| Invoking agent | When |
|---|---|
| `po-analyst` | Input is a migration / refactor ticket; before `analyze-requirement` |
| `amauta` | Adapting a legacy provider / module that didn't go through Kuraka |
| `architect-reviewer` | Freezing target schema; needs the gap doc to validate design |

**Output feed:**

- Main feed: `analyze-requirement` uses the GAP doc as source to write
  `REQ-...md`.
- Secondary feed: `schema-freeze` consults C.1 and C.5 to decide the
  target schema.

**Does not replace:**

- `analyze-requirement` (produces REQ with stories) — GAP doc is its input.
- `refine-stories` (produces verifiable AC) — comes after.
- `schema-freeze` (freezes DB schema) — comes after.

---

## 8. Final checklist before delivery

- [ ] All inputs confirmed with the user before starting.
- [ ] Document at
  `${architecture.paths.docs_process_root}/GAP-{YYYYMMDD}-{slug}.md`.
- [ ] Parts A / B / C / D complete with real content.
- [ ] ≥10 hardcoded values, ≥2 references, ≥5 risks.
- [ ] Open questions listed in C.6 with blockers marked.
- [ ] Recommendations per next phase in D.1 / D.2 / D.3.
- [ ] Refactor proposals in D.4 if duplication was detected.
- [ ] No source file modified.
- [ ] Ticket vs reality discrepancies documented.
