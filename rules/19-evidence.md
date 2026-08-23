---
description: "Evidence rules for every Kuraka agent and the orchestrator: behavior claims cite the executable body; non-existence claims carry a positive control; frozen-artifact edits fix the body first, the summary last."
---

# Rule 19 — Evidence (R-CUERPO · R-CONTROL · R-ESPEJO)

Cross-cutting rules for ANY claim an agent or the orchestrator makes about code
or artifacts. Motivated by one cycle (facturacion-honorarios USREMAIL) with six
evidence failures across three agents plus the orchestrator: a REQ built on a
false "no validator exists" premise, a false finding sourced from a comment on a
fully commented-out body, and a freeze whose header rejected a decision its body
still implemented.

## R-CUERPO — behavior claims cite the executable body

A claim about what code DOES must cite the **executable body** with
`file:start-end` and reflect what those lines execute.

- A function/variable **name**, a **comment**, a docstring, a decision table, a
  design doc, or **another agent's report** is NEVER evidence of behavior.
- A commented-out or dead body means the behavior does NOT exist — a comment
  describing it is evidence of nothing.
- If you did not open the body this run, the claim is a hypothesis and must be
  labeled as such.

## R-CONTROL — non-existence claims carry a positive control

Every "X does not exist / is never called / has no validator" claim requires:

1. A grep for the **operation itself** (the call, the write, the annotation) —
   not for a guessed name of it. Names drift; operations don't.
2. A **positive control** pasted next to the `0 matches`: the same grep pattern
   run against a place where it MUST match (proving the pattern can hit). A
   `0 matches` without a positive control proves only that the grep can fail.

## R-ESPEJO — body first, summary last

When a gate decision changes a frozen artifact (freeze, REQ, story, checkpoint):

1. Grep the artifact for **every occurrence** the decision touches and fix each
   one **in the body FIRST** — including copy-literal blocks and examples.
2. Update the summary / header / decision table **LAST**, after the body agrees.

A header that says "F-5 rejected" over a body that still implements F-5 is worse
than no edit: reviewers read the header and inherit the lie. The mirror order
makes that state impossible.

## Scope

These rules bind every agent (analysis, implementation, review, audit) AND the
orchestrator's own artifacts (REQ premises, freeze coherence, checkpoints,
handoffs). Reviewer-specific reinforcements live in `code-reviewer` (re-derive
numbers, scope-fidelity diff) and `rules/17` T9 (reproduce claims, never quote
self-reports); this rule generalizes them to all claims of all agents.
