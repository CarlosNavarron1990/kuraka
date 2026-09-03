---
name: facilitate-discovery
description: "Design-thinking discovery facilitator (Tinkuy, from Quechua 'encuentro/convergencia' — the gathering where ideas meet). Given a raw idea, the orchestrator convenes a council of dynamically-authored domain experts (e.g. accountant + administrator for an accounting product), runs diverge/converge rounds with the user, synthesizes a design brief, and optionally promotes the valuable experts into the project specialization layer for reuse. Runs BEFORE the requirement exists — it produces the brief that feeds po-analyst (existing projects) or inti/arki (greenfield)."
---

# Tinkuy — Design-Thinking Discovery Facilitator

> *Tinkuy* (Quechua) — the encounter, the gathering where two currents
> meet and converge. Here it is the council: the orchestrator convenes
> domain experts around a raw idea so that, before a single requirement
> is written, the bases of the system are discussed by the right voices.

This skill is run by the **orchestrator** (the Claude running `kuraka`),
**not** by a subagent. Reason: only the top-level orchestrator can spawn
subagents — a subagent cannot convene a panel. The orchestrator therefore
wears the "facilitator" hat: it authors the expert personas, spawns them
as ephemeral subagents, moderates the discussion, and synthesizes.

This is the entry point of the **Discovery mode** (see `kuraka-modes.md`).

---

## When to use

- The user has an **idea**, not a requirement ("quiero un software de
  contabilidad"), and wants to discuss the bases of the system with
  domain experts before anything is defined.
- Works in three contexts:
  - **Existing project** (brownfield, Kuraka already mounted): the brief
    feeds `po-analyst` (Phase 1).
  - **Greenfield**: the brief feeds `inti` / `arki` (Bootstrap).
  - **Mid-project, fuzzy new feature**: the brief feeds `po-analyst` for
    that feature's cycle.

**When NOT to use**: the requirement is already articulated and only
needs structuring → go straight to `po-analyst`. Discovery is for the
fuzzy front-end, not for closing an already-clear ask.

---

## Prerequisites

- A raw idea from the user (a phrase, a paragraph, a brief). If the user
  gave **less than 2 sentences**, ask for a bit more before convening the
  council — do not guess the domain.
- `kuraka.config.yaml` is **optional** here. Discovery can run before the
  project is mapped. If it exists, read `project.{name,description}` and
  `conventions.naming_language` to keep vocabulary consistent.

---

## Hybrid model (ephemeral first, persistent on demand)

Two halves, by design:

1. **Ephemeral council (default, no restart):** experts are spawned as
   throwaway subagents via the Agent tool, with system prompts authored
   on the fly. You converse with them *through the facilitator* in the
   same session. Nothing is persisted. Cheap, fluid, zero friction.
2. **Promotion (opt-in, persistent):** at the end, with explicit user
   approval, the orchestrator writes the worthwhile experts to
   `.claude/project/agents/{slug}.md` (real, reusable agents). One Claude
   Code restart registers them; thereafter they can be invoked directly
   and referenced from the project layer (e.g. as reviewers of stories in
   their domain).

Persisted experts live in the **consumer project**, never in the vault —
they are specific to that project's domain.

---

## Budget & guardrails (HARD)

- **Experts**: 2 minimum, **4 maximum**. More voices = more noise and
  tokens, not more signal. If the domain seems to need >4, group them
  (e.g. "finanzas+tributario" as one fiscal expert) and say so.
- **Rounds**: default **2** diverge/converge cycles. Cap at 4. Each round
  must end in a facilitator synthesis — never dump raw expert output on
  the user.
- **Synthesis is mandatory.** The user talks to the *facilitator*, who
  relays a converged view + the open conflicts. Raw multi-expert
  transcripts are for your reasoning, not the user's screen.
- **Anti-hallucination (golden rule, like `amauta`):** any domain claim
  that is regulatory, legal, fiscal, accounting-standard, medical, or
  otherwise externally-governed MUST be tagged
  `⚠️ VALIDAR con experto humano` in the brief. An LLM "accountant" can
  reason about structure; it cannot be the source of truth for NIIF/IFRS,
  tax law, or jurisdiction-specific rules. Never present invented
  regulation as fact.
- **Token optimization**: apply `rules/17-kuraka-token-optimizations.md`.
  Give each ephemeral expert a *focused* prompt (its lens + the idea +
  the specific question of the round), not the entire conversation.

---

## Process

### D1 — Frame the idea and design the council

1. Read the raw idea. In one sentence, state the **domain** and the
   **core value** as you understand them, and confirm with the user if
   ambiguous.
2. Decide **which 2–4 expert lenses** the domain genuinely needs. Pick
   for *diversity of perspective*, not redundancy. Examples:
   - *Accounting product* → `contador` (domain accounting),
     `admin-finanzas` (business administration / process), optionally
     `fiscal-tributario` (tax/compliance) and `ux-operativo` (the day-to-day
     user who lives in the tool).
   - *Logistics product* → `operaciones-logistica`, `costos`,
     `integraciones-edi`.
   - Always consider including **one "skeptic / end-user" lens** whose job
     is to push back on complexity and ask "who actually needs this".
3. For each expert, author a **persona spec** using
   `.claude/templates/domain-expert.template.md` as the shape:
   name/slug, the lens, what they're expert in, what they must challenge,
   and the explicit reminder that regulatory claims need human validation.
4. Present the proposed council to the user in a short table
   (slug · lens · why this voice) and ask for a green light or edits
   **before** spawning. The user may add/remove a voice.

### D2 — Convene the ephemeral council (diverge → converge)

For each round (default 2):

**Diverge** — spawn the experts as ephemeral subagents, in parallel when
independent. Each gets a focused prompt:

> You are {persona}. Lens: {lens}. The idea is: "{idea}".
> Round {n} question: {the round's question}.
> Output: (a) 3–6 concrete proposals/observations from YOUR lens only,
> (b) the top risks or wrong assumptions you see, (c) anything that needs
> validation by a human domain expert (tag it). Be concrete; no preamble.

Round questions escalate:
- **Round 1** — "What are the core entities, processes, and non-obvious
  rules of this domain that the system MUST respect? What would a naive
  builder get wrong?"
- **Round 2** — "Given the convergence so far {summary}, where do the
  experts disagree, what is the minimum viable scope, and what must be
  deferred?"
- (Round 3–4 only if real conflicts remain unresolved.)

**Converge** — the facilitator (you) reads all expert outputs and produces
a **single synthesis** for the user:
- Points of agreement (the emerging bases of the system).
- **Conflicts** between experts, stated as a choice for the user to make.
- Open questions for the user.
- A running list of `⚠️ VALIDAR con experto humano` items.

Then **converse with the user**: present the synthesis, let them react,
decide conflicts, add constraints. Feed their decisions into the next
round's question. Stop early if convergence is reached before the cap.

### D3 — Synthesize the design brief

Write `docs/discovery/design-brief-{slug}.md` using
`.claude/templates/design-brief.template.md`. It captures:

- One-liner + domain + core value.
- The council (which voices participated and why).
- **Domain bases**: entities, processes, business rules surfaced and
  agreed — with regulatory items clearly tagged for human validation.
- Tentative scope IN / OUT (explicitly tentative — `po-analyst` owns the
  real scope gate).
- Glossary seed (domain vocabulary, for `.claude/project/glossary.md`).
- Open questions + decisions taken (verbatim, with who decided).
- Risks, including every `⚠️ VALIDAR con experto humano` flag.

Keep it ≤ 250 LOC. Present a ≤ 300-word summary to the user for approval.

### D4 — Promote experts (opt-in, persistent half)

Ask the user explicitly:

> "¿Quieres conservar a alguno de estos expertos como agente permanente
> del proyecto, para que ayude en fases posteriores (p.ej. revisar
> stories del dominio)? Si sí, dime cuáles."

For each expert the user wants to keep:

1. Write `.claude/project/agents/{slug}.md` from the
   `domain-expert.template.md` (filled with the persona spec from D1,
   plus the `model:` frontmatter — default `sonnet`, `opus` only if the
   lens is judgment-heavy).
2. Add a one-line pointer in the design brief's "Promoted experts"
   section so later phases know they exist.
3. Tell the user a **Claude Code restart is required** for the new agents
   to register (subagents register at session start only), and remind
   them to re-run `mount-kuraka` is NOT needed — these live in the
   project layer, not the vault.

If the user wants none, that's fine — the ephemeral council already did
its job and the brief stands on its own.

### D5 — Hand off

Tell the user the next step based on context:
- **Existing / mid-project** → `/kuraka` → Phase 1 `po-analyst`, which
  reads `docs/discovery/design-brief-{slug}.md` as input.
- **Greenfield** → `inti` (to formalize vision/requirements) then `arki`,
  both of which should read the brief.

---

## Orchestrator constraint (still applies)

Discovery runs before Phase 4, so the orchestrator must **not** create or
modify source files (`backend/`, `frontend/`, `tests/`, `migrations/`).
The only writes Discovery makes are:
- `docs/discovery/design-brief-{slug}.md`
- `.claude/project/agents/{slug}.md` (promotion) — editing `.claude/` and
  `docs/` is the documented legitimate exception in `kuraka`.

If a domain expert proposes implementation, capture it as a note in the
brief — do not write code.

## Output Validation

Before returning, run the `verify-output` skill. Required:

- `docs/discovery/design-brief-{slug}.md` exists.
- Every regulatory/legal/standard claim is tagged
  `⚠️ VALIDAR con experto humano`.
- Number of experts is between 2 and 4.
- Summary ends with `## Confidence: HIGH / MEDIUM / LOW`.
