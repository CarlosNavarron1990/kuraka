---
name: verify-output
description: "Self-validate agent output against the schema in output-schemas.md before returning. Prevents malformed handoffs between agents."
agent: "ALL agents"
phase: "at end of every phase — see `kuraka`"
disable-model-invocation: true
user-invocable: false
---

# Verify Output

> **Claude Code:** this protocol is enforced by the `output_validate`
> `SubagentStop` hook — agents do NOT run it manually there (the hook rejects
> a stop whose report misses the universal contract and the agent re-emits).
> The manual protocol below remains authoritative for platforms without the
> hook (Antigravity / Cursor / Codex) and as the human-readable contract.

Before returning your output to the orchestrator, execute this
self-validation protocol.

## Input

Your produced output (file path + content, or response text).

## Steps

### 1. Load your schema

Read `.claude/agents/contexts/output-schemas.md` and find your agent's
section.

### 2. Check required sections

For each required section in your schema:

- Is the section header present (correct H2 / H3 level)?
- Is the content non-empty?
- Does it match the expected format (table columns, list format)?

### 3. Check universal requirements

- [ ] `## Confidence: HIGH / MEDIUM / LOW` line is present at the end.
- [ ] File paths mentioned use absolute paths from the project root.
- [ ] No unexplained TODO / FIXME / XXX markers.

### 4. Check output location

If your output is a file:

- [ ] File path matches the pattern specified in the schema (typically
  derived from `${architecture.paths.docs_process_root}/`).
- [ ] File was actually written (not just returned in response).
- [ ] File is in the correct directory.

### 5. Apply validation checks

Each agent has specific validation checks listed in its schema section.
Run through them explicitly.

### 6. Handle failures

**If any check fails:**

- First failure: silently fix and re-validate.
- Second failure: return with explicit `VALIDATION_FAILED` marker:

  ```
  ## Self-Validation Failed

  Missing / malformed sections:
  - {section name}: {what's wrong}

  Please review before passing downstream.
  ```

**If all checks pass:** proceed to return output normally.

## Rules

1. **This skill is invoked implicitly by every agent at end of phase** —
   not by the user.
2. **Never skip validation** — the cost of a malformed output downstream
   is higher than the cost of re-generating.
3. **Do not change severity vocabulary** — stick to:
   BLOCKER / IMPORTANT / MINOR / SUGGESTION / PRAISE (or
   CRITICAL / HIGH / MEDIUM / LOW / INFO for security-reviewer).
4. **Confidence is mandatory** — if you can't honestly assess confidence,
   default to MEDIUM and explain why in the output.
