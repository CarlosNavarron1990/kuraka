---
name: compact-context
description: "Compress a verbose agent output into a summary before passing to the next agent. Prevents context bloat when one agent reads many files. Invoked automatically when previous output > 5000 tokens."
agent: "orchestrator (automatic)"
phase: "between phases — see `kuraka`"
user-invocable: false
context: fork
---

# Compact Context

Summarize an agent's output before forwarding to the next agent.

## When to invoke

Automatically, when:

- Previous agent output is > 5000 tokens.
- The next agent doesn't need the full detail, just the relevant facts.
- An exploration agent read 10+ files and the raw output is noisy.

Do NOT compact if:

- The next agent specifically needs the full artifact (e.g., code review
  reading the full REQ).
- The output is already structured (tables, schemas).
- Compaction would lose data needed downstream.

## Input

- The full output of the previous agent.
- The next agent's role (to know what matters).

## Steps

### 1. Identify the core artifacts

What did the previous agent PRODUCE (vs just investigated)? Keep the
produced artifacts.

Examples:

- `po-analyst` output: keep REQ + list of stories; summarize "exploration notes".
- `architect-reviewer` output: keep findings table and verdict; drop the
  rule-reading chatter.
- `test-engineer` output: keep test plan table; drop fixture discovery logs.

### 2. Extract decisions and conclusions

Keep:

- Verdicts (APPROVED / CHANGES_REQUIRED / etc.).
- Findings (severity + description + fix).
- File paths (absolute).
- Confidence level.

Drop:

- Step-by-step reasoning.
- File-by-file exploration narration.
- Quoted tool outputs (keep only relevant excerpts).

### 3. Preserve contracts

The next agent expects specific fields in the input. Preserve:

- File paths of produced artifacts.
- Schema references (e.g., "uses the project's tenant column" instead of
  citing a specific column name unless the next agent needs the literal).
- Critical warnings from the previous agent.

### 4. Produce compacted output

```markdown
## Compacted Context from {previous agent}

**Verdict:** {verdict}

**Artifacts produced:**
- {file_path}: {one-line description}

**Key findings / decisions:**
1. {finding}
2. {decision}

**Warnings for downstream:**
- {warning}

**Original length:** N tokens → Compacted: M tokens (X% reduction)
```

## Mode: pre-extracted digest (for fix-runs and the code-reviewer)

This skill also produces the **forward** digest that `rules/17` Rule T8 requires
— so a fix-run or a review doesn't reload the whole surface. Same compression
discipline, but instead of summarizing a *previous* agent's output you pre-cook
the *next* agent's working set:

- **Fix-run digest** (after a review proposes N MINOR/IMPORTANT fixes): emit one
  block per fix — `{absolute file path · line range · exact finding text to
  apply}`. Nothing else. The implementer applies these without re-reading the
  module unless a fix is genuinely ambiguous.

  ```markdown
  ## Fix digest — apply these, do NOT re-read the full surface
  1. `src/foo/bar.ts:142-148` — MINOR: replace `new Date(x)` with raw `x` (external YYYY-MM-DD, no coercion)
  2. `src/foo/baz.ts:31` — IMPORTANT: add `if (!id) return;` guard before token-scope bind
  ```

- **Reviewer digest** (before invoking `code-reviewer` on a large surface): emit
  the frozen schema/contracts + the named invariants / attack table to verify +
  the changed-file list with per-file LOC. A precise invariant table keeps the
  reviewer in-band even when the surface is large.

Estimated savings: 40–80K tokens per fix-run; reviewer latency from 25–58 min to
in-band (Rule T8 evidence).

## Rules

1. **Never lose file paths** — downstream agents need them.
2. **Never lose verdicts or severities** — they drive next-phase logic.
3. **Preserve confidence level** — if original was LOW confidence,
   compaction is LOW confidence.
4. **Mark what was dropped** — at the end, list "Dropped: exploration
   narration, rule-reading logs".
5. **If compaction reduces content by < 30%, skip it** — not worth the risk.
