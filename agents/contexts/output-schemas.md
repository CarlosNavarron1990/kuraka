# Agent Output Schemas

Every agent MUST self-validate its output against the schema below before returning.
This is the contract between agents — a violation blocks the workflow.

## Universal Requirements (all agents)

Every agent output MUST include:
- `## Confidence: HIGH / MEDIUM / LOW` at the end
- Explicit reference to which output file(s) were created (full paths)
- No unexplained TODO/FIXME markers in the produced artifact
- **No self-reported token / tool-use / duration counts.** Those numbers come ONLY
  from the harness `usage` block (or the telemetry hook log), which the orchestrator
  records. An agent's own count is systematically low (azure: below the harness in
  3/10 and 6/7 runs; piscosdalston, possuite, petsuite same) and then pollutes the
  telemetry. If a report must mention cost, mark the figure `[ESTIMACIÓN NO MEDIDA]`.
- Hygiene contract: `agents/contexts/subagent-hygiene.md` (scratchpad, background
  jobs, declared output exists, no fake notifications, no recursion, read-only git
  for review/verify agents).

If any requirement is missing, the output is invalid — re-generate before returning.

---

## po-analyst (Phase 1)

**Output file:** `${architecture.paths.docs_process_root}/REQ-{YYYYMMDD}-{ticket}-{slug}.md`

**Required sections (in order):**

1. `# REQ-{date}-{ticket}: {Title}` — H1 header with date and ticket
2. `## Workflow Status` — checklist of phases
3. `## 1. Requirement Summary` — 2-3 sentences
4. `## 2. Scope` — with `### In Scope` and `### Out of Scope`
5. `## 3. Table Inventory` — table with Action, Justification, Jira columns
6. `## 4. Affected Endpoints` — method/path/action/auth
7. `## 5. Affected Services & Repositories` — file paths
8. `## 6. Dependencies`
9. `## 7. Risk Assessment` — impact/mitigation table
10. `## 8. Proposed Stories` — numbered with dependencies
11. `## Confidence: HIGH / MEDIUM / LOW`

**Validation checks:**
- File path matches pattern `REQ-\d{8}-[A-Z]+-[a-z-]+\.md`
- All 8 numbered sections present
- Every table in Table Inventory has justification if "In Jira?" is No

---

## story-refiner (Phase 2)

**Output files:** `${architecture.paths.docs_process_root}/stories/{ticket}-S{N}.md` (one per story)

**Required sections per story:**

1. `# {ticket}-S{N}: {Title}` — H1 header
2. `## Description` — user story format
3. `## Acceptance Criteria` — numbered checkboxes, all testable
4. `## Schema Changes` — only if story has DB changes
5. `## API Contract` — only if story has endpoints
6. `## Files to Create/Modify` — table with File / Action / Description
7. `## Dependencies` — list of related stories
8. `## Technical Notes`
9. `## Confidence: HIGH / MEDIUM / LOW`

**Validation checks:**
- At least 3 acceptance criteria per story
- All file paths match the stack profile's idiomatic layout and `architecture.paths.*` from config
- Null syntax matches `conventions.null_syntax`
- No magic strings in AC — constants named explicitly (when `conventions.enums_for_states: true`)

---

## test-engineer — TEST_PLANNING mode (Phase 2.5)

**Output file:** `${architecture.paths.docs_process_root}/test-plans/TEST-PLAN-{ticket}.md`

**Required sections:**

1. `# Test Plan: {ticket}`
2. `## Stories Covered` — list referencing story IDs
3. `## Testability Constraints` — numbered list
4. `## Test Cases` — table with #/Story/Function/Test Case/Type/Category/**Input/Expected/Source/Kind** (`Kind` = ACCEPTANCE or INTERNAL; `Source` = AC id, REQ section, frozen-contract line or business rule)
5. `## Fixtures` — table with Fixture/Source/Purpose
6. `## Testability Risks` — table with Risk/Story/Impact/Mitigation
7. `## Estimated Test Count: N`
8. `## Files to Create`
9. `## Confidence: HIGH / MEDIUM / LOW`

**Validation checks:**
- Every story's AC has at least one test case row
- Every public function mentioned has 3+ test cases (happy + error + edge)
- All fixtures either exist in conftest.py or marked as "create new"
- Every case has a concrete `Expected` value and a `Source`; a case whose value the spec does not fix is listed as an open question, never guessed
- A user-visible change carries the `## Recorrido` table

---

## test-engineer — TEST_FIRST mode (Phase 3.95)

**Output:** the ACCEPTANCE test files (written from the plan + frozen contract, never from the code under change) + report returned as agent response.

**Required sections:**

1. `# Acceptance tests (red): {ticket}`
2. `## Tests written` — table with File/Test/Plan case #/Source
3. `## Red evidence` — the exact command, its exit code, and per test the failure reason (assertion / 404 / missing symbol). Collection, import, syntax or fixture errors are NOT valid red.
4. `## Lock` — the `kuraka-testlock.py lock` command run and the files locked
5. `## Confidence: HIGH / MEDIUM / LOW`

**Validation checks:**
- Every ACCEPTANCE case of the plan has a test (or a stated reason)
- Every test is red for the right reason on the current baseline
- The lock file exists and lists every test written

---

## architect-reviewer (Phase 3)

**Output file:** review report (returned as agent response, not a file)

**Required sections:**

1. `# Architecture Review - Stories + Test Plan`
2. `**Verdict:** APPROVED / APPROVED_WITH_MINOR / CHANGES_REQUIRED`
3. `## Summary` — 2-3 sentences
4. `## Findings` — table with # / Severity / Artifact / Description / Fix
5. `## Approved Stories` — list
6. `## Stories Requiring Changes` — list
7. `## Schema Freeze Status` — checklist
8. `## Confidence: HIGH / MEDIUM / LOW`

**Also produces:** `${architecture.paths.docs_process_root}/schemas/SCHEMA-FROZEN-{ticket}.md` if verdict is APPROVED.

**Validation checks:**
- Findings table has columns: #, Severity, Artifact, Description, Fix
- Every BLOCKER has a concrete Fix column value
- Severity is one of: BLOCKER / IMPORTANT / MINOR / SUGGESTION / PRAISE

---

## backend-developer (Phase 4)

**Output:** modified/created source files + a completion report.

**Completion report structure:**

1. `## Files Created` — list
2. `## Files Modified` — list with brief description
3. `## Test Status` — `${stack.backend.lint_cmd}` result, `${stack.backend.test_cmd}` result
4. `## Stories Implemented` — checkmark list
5. `## Confidence: HIGH / MEDIUM / LOW`

**Validation checks:**
- `${stack.backend.lint_cmd}` MUST pass (no errors). Frontend equivalents (`stack.frontend.*`) apply for frontend changes.
- `${stack.backend.test_cmd}` MUST pass (no failing tests).
- Every story from the input has a corresponding checkmark.

---

## code-reviewer (Phase 5)

**Output file:** review report (returned as agent response)

**Required sections:**

1. `# Code Review - Implementation`
2. `**Verdict:** APPROVED / APPROVED_WITH_MINOR / CHANGES_REQUIRED`
3. `## Summary`
4. `## Findings` — table with # / Severity / File:Line / Description / Fix
5. `## Positive Notes`
6. `## Next Steps`
7. `## Confidence: HIGH / MEDIUM / LOW`

**Validation checks:**
- Every finding references a specific `file.py:line`
- Every BLOCKER has a concrete Fix
- Severity vocabulary matches: BLOCKER / IMPORTANT / MINOR / SUGGESTION / PRAISE

---

## test-engineer — TEST_WRITING mode (Phase 6)

**Output:** test files + validation report

**Validation report structure:**

1. `## Test Files Created` — list of paths
2. `## Coverage vs Plan` — matches test plan from Phase 2.5? Yes/No + diff
3. `## Test Execution` — `${stack.backend.test_cmd}` output summary
4. `## Lint Check` — `${stack.backend.lint_cmd}` pass/fail
5. `## Confidence: HIGH / MEDIUM / LOW`

**Validation checks:**
- Every test case from TEST-PLAN-{ticket}.md has a corresponding test method
- All imports at module top (no imports inside methods)
- Test names follow the stack profile's idiomatic naming (e.g., for pytest: `test_should_{action}_when_{condition}`)

---

## final-auditor (Phase 7)

**Output file:** `${architecture.paths.docs_process_root}/agent-retrospectives/RETRO-{REQ-name}.md`

**Required sections:**

1. `## 1) Summary`
2. `## 2) Timeline of Rework`
3. `## 3) Agent Findings` — one subsection per agent used
4. `## 4) Systemic Issues`
5. `## 5) Workflow Improvements`
6. `## 6) Patches Proposed` — framework-prompt OR project-layer, with specific paths + exact text
7. `## 7) Next-Requirement Guardrails`
8. `## 8) Token & Latency Telemetry`
9. `## Confidence: HIGH / MEDIUM / LOW`

**Validation checks:**
- Every patch in section 6 has: file path + exact text to add + insertion point
- Telemetry table has all agents invoked during the cycle
- Every finding has a severity and a preventability rating

---

## Self-Validation Protocol

Before an agent returns its output, it MUST:

1. Read its section in this file
2. Check every required section is present
3. Check the output file is at the correct path (if applicable)
4. Check the Confidence line is present
5. If ANY check fails → re-generate the missing parts before returning

**If self-validation fails twice**, return an explicit `VALIDATION_FAILED` marker
with the specific missing sections. The orchestrator will ask the user how to
proceed rather than silently passing invalid output downstream.
