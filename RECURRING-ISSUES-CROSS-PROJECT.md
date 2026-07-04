# Recurring Issues Report — CROSS-PROJECT

**Generated:** 2026-07-03
**Scope:** First formal cross-project pattern analysis over the vault's full canonical retro corpus (`projects/*/cycles/*/RETRO-*.md`).
**RETROs analyzed:** 44, across 5 projects:

| Project | Retros | Date range |
|---|---:|---|
| guai-home-marketplace | 26 | 2026-05-30 → 2026-07-03 |
| kuraka-control | 8 | 2026-06-13 → 2026-06-25 |
| clinica-dental-2026 | 7 | 2026-06-07 → 2026-06-28 |
| dbcanvas | 2 | 2026-06 (REQ-20260607 cycles, audited ~06-25) |
| sie-integraciones | 1 | 2026-07-02 |

**Prior work incorporated (not re-derived):**
- `KURAKA-OPTIMIZATION-REPORT.md` (2026-06-27, C1–C14 over 38 retros) → implemented in vault commit **fdd1b0f** (2026-06-28, Waves 1–4).
- guai project-level `docs/process/RECURRING-ISSUES.md` (2026-07-03, 5 patterns) → generic findings promoted in vault commit **a51f92d** (2026-07-03).

Every pattern below is classified against those two commits (verified by grep in the current vault, not from the commit messages alone).

---

## Executive Summary

- **~230 normalized findings** indexed across the 44 retros (guai ~130, kuraka-control ~45, clinica ~32, dbcanvas ~17, sie ~10).
- **12 cross-project patterns** (2+ distinct projects). **9 are already addressed** by fdd1b0f and/or a51f92d — they move to "verify in next cycles", not to new proposals.
- **2 patterns have NO framework coverage** and are the new proposals: (P3) pre-existing infra bugs surfacing in Phase 4 because no environment pre-flight exists — present in **all 5 projects**; (P4) telemetry capture gaps — 4/5 projects, only the `budget_ok` field is currently integrity-checked.
- **3 enforcement gaps**: rules that existed at the time of a violation and were violated anyway (T7 order-dependence variant, T8 fix-digest, advisory tool-use caps). Per rule 4 of `detect-patterns`, these get enforcement mechanisms, not rewording.
- Positive cross-project signal worth preserving: the adversarial/empirical freeze (Wave 2) and the in-vivo probe produced pre-code BLOCKER catches in kuraka-control (S4, S5b-1, S5b-2 — 3 consecutive), clinica (3 consecutive probe cycles), and sie (GATE0 caught a digest contamination). The Wave 1 retro→patch loop check demonstrably closed the leak in clinica REQ-20260628 ("first cycle to close the loop").

---

## Findings Index Summary (distinct cycles mentioning each category, per project)

| Category | guai | kuraka-control | clinica | dbcanvas | sie | Projects |
|---|---:|---:|---:|---:|---:|---:|
| Contract/spec recalled-not-observed (incl. Swagger lies, enum/nullable guesses, doc-vs-artifact) | ~6 | 4 | 3 | 2 | 1 | **5** |
| Green ≠ correct / false-green gate (incl. build-green runtime crash, visual proxies) | ~5 | 1 | 2 | 1 | 1 | **5** |
| Pre-existing infra bug surfaced late (Phase 4+) | 2 | 4 | 4 | 2 | 1 | **5** |
| Telemetry/checkpoint capture gaps (missing runs, missing token counts, null durations) | 2 | 2 | 2 | 2 | 1 | **5**¹ |
| Cheap fix = expensive run (undigested fix-runs / reviewer full re-read) | 2 | 5 | 2 | 0 | 2 | **4** |
| Self-report trusted / claim propagation | 2 | 0 | 1 | 1 | 1 | **4** |
| Retro→patch application leak (loop not closed) | 3 | 1 | 2 | 1 | 0 | **4** |
| Mechanism hedged in prose / non-binding AC | 1 | 5 | 2 | 0 | 0 | **3** |
| Route/smoke against wrong or partial surface | 2 | 1 | 3 | 0 | 0 | **3** |
| Advisory limits don't fire (tool-use cap, latency band) | 1 | 5 | 1 | 0 | 0 | **3** |
| Nullable/enum mishandling on external-field seams | 1 | 4 | 0 | 0 | 0 | 2 |
| LOC/file-size limit detected late (Phase 5) | 1 | 2 | 0 | 1 | 0 | 3 |
| Scope drift (as an actual defect) | 1 | 0 | 0 | 0 | 0 | 1 |

¹ Telemetry gaps: guai = budget_ok-always-true + unwritten telemetry; sie = operational-signal variant. Counted conservatively as 4 solid + 1 variant in P4 below.

---

## Top Patterns (ranked by distinct-project count × cost)

### Pattern 1: Contract/spec recalled instead of observed — **5/5 projects** — ALREADY ADDRESSED (verify)

- **Occurrences:** guai REQ-20260611 (fabricated webhook contract, ~1.5M tokens rework), REQ-20260623 (schema asserted from memory), REQ-20260602 (closed enum vs real fixture), RETRO-20260530-perito (PO assumptions decided instead of flagged); clinica REQ-20260610 (7-field model vs 14-field verbatim payload), REQ-20260624 + REQ-20260625 (Swagger wrong on nearly everything; phantom `/plan/` prefix — caught by in-vivo 422 probe); kuraka-control S1 (seeded `z.enum` vs live vault data — GATE0 rewrite loop), S12 (enum-as-string); dbcanvas sqlite-store (Electron version trusted from stale CLAUDE.md, propagated into a story AC); sie DD1243 (Phase-1 digest carried v2 anchors into the v1 brief — caught by po-analyst reading the real code).
- **Root cause:** contracts, schemas, versions and payloads asserted from docs/memory/seeds instead of probed in vivo.
- **Already addressed by:** fdd1b0f Wave 2 — `agents/po-analyst.md` "Contract-first GATE (external integrations) — observe, do not recall"; `agents/architect-reviewer.md` check 14 (contract provenance: in-vivo probe, migration `file:line` quotes, field-by-field verbatim diff = BLOCKER if missing); `skills/analyze-requirement.md` §4b.
- **Post-fix evidence (rule is working):** clinica REQ-20260628 held clean; sie DD1243 (2026-07-02) GATE0 caught the contaminated digest before code. Both post-fix retros show the gate catching, not the bug landing.
- **Action:** none new. Verify it keeps holding; the dbcanvas "version-from-project-doc" variant is on the watch list.

### Pattern 2: "Green" ≠ correct — false-green gates — **5/5 projects** — ADDRESSED (with enforcement history; verify hard)

- **Occurrences:** guai REQ-20260623 (Makefile exit-code bug), REQ-20260611 (piped gate hid a collection failure), REQ-20260612 (test-DB schema divergence), REQ-20260703 (order-dependent guard test passed in-suite, failed isolated), RETRO-20260530-perito (green smoke missed a broken screen); clinica RETRO-2026-06-07 (closed on proxies — HTTP 200/`ng build` — without observing the rendered result), REQ-20260610 (`ng build` green, NG0203 at runtime); kuraka-control S5b-2 (typecheck absent from `make test` — a bad cast rode green ~3 cycles; green tests missed a no-op/404 bug); dbcanvas code-graph-mvp (build green, FE overlay silently never rendered); sie DD1243 (inverse variant: ~8 pre-existing red suites make full `npm test` unusable as a gate).
- **Root cause (three sub-mechanisms):** (a) the gate command itself can't fail (pipes, missing `--exit-code-from`); (b) the gate's definition of green is too narrow (no typecheck, no isolation runs, no rendered-state observation); (c) baseline noise (pre-existing red) makes green undefined — see Pattern 3 for the fix.
- **Already addressed by:** fdd1b0f Wave 1 (Rule 17 T7 gate integrity; typecheck in the definition of green) + Wave 4 (e2e full-page snapshot, empty-vs-broken disambiguation); a51f92d (T7 extended: exit code + absence-of-FAILED + isolated guard runs; test-engineer/backend-developer isolation rules; Phase 6.8 mandatory smoke with route pinning).
- **Enforcement history (why it's listed under gaps too):** T7 existed from 2026-06-28 and guai REQ-20260703 still recurred via a variant T7 didn't name (order-dependence). a51f92d closed exactly that variant today. This is the pattern most likely to mutate again — see Enforcement Gap 1.
- **Action:** none new beyond a51f92d; verify with priority in the next 3 cycles of every project.

### Pattern 3: Pre-existing infra bugs surface in Phase 4+ — no environment pre-flight — **5/5 projects** — **NOT ADDRESSED → NEW PROPOSAL #1 (HIGH)**

- **Occurrences:** guai REQ-20260611 (`jinja2` missing from requirements — app couldn't boot, discovered at S1 gates), REQ-20260612 (test-DB schema diverged from migrations, discovered mid-story); kuraka-control S12 + S1 (no eslint config → `make lint` fails; no `createApp()` factory), S2 (fragile vault-version regex debt), S5b-2 (`make test` never typechecked — latent 3 cycles); clinica REQ-20260612/13 (backend 404 + empty X-Acc made smoke ambiguous), REQ-20260625 (required FK with no catalog endpoint anywhere), REQ-20260628 (latent storage double-prefix from a prior feature); dbcanvas sqlite-store (`ci.yml` runs tests but never lint; native dep loading in the wrong Electron process), code-graph-mvp (pre-existing masker/CSRF gaps); sie DD1243 (stale fixture red on HEAD + ~8 pre-existing red suites cost a 131K-token fixup run and polluted the gate).
- **Root cause:** the first time the real stack (boot, lint, typecheck, full gate command) is exercised is *during* Phase 4 implementation. Pre-existing breakage then bills itself to the cycle, confounds gates, and is fixed opportunistically in-branch. The framework has **no pre-Phase-4 gate**: grep of `skills/kuraka.md` / `kuraka-modes.md` finds no Phase-0/pre-flight; Phase 6.8 smoke is post-implementation. Both the guai project report (Pattern 4) and multiple retros proposed this project-locally; at 5/5 projects it is framework-level by rule 1.
- **Structural fix (framework):** add a **Phase 3.9 "environment pre-flight"** step to `skills/kuraka.md` (orchestrator-run, deterministic, ~0 model tokens — consistent with T9): (1) boot the dev stack / health endpoint; (2) run the exact gate command that will judge Phase 4 once, plus typecheck and collection; (3) record the **baseline red set** (pre-existing failures) in the checkpoint — Phase-4 green is then defined as *no regression vs baseline + new tests green*, which also fixes sie's unusable-gate variant; (4) any boot/collect failure is fixed (or explicitly waived by the user) before Phase 4 starts. Companion note in `skills/kuraka-policies.md` (checkpoint schema: `baseline_red` field).
- **Where:** framework (`skills/kuraka.md`, `skills/kuraka-policies.md`).
- **Priority:** **HIGH** — highest-frequency unaddressed pattern (11+ cycles, 5/5 projects).

### Pattern 4: Telemetry/checkpoint capture gaps — **4/5 projects (+1 variant)** — PARTIALLY ADDRESSED → **NEW PROPOSAL #2 (HIGH)**

- **Occurrences:** dbcanvas code-graph-mvp (no telemetry JSON at all for the cycle) and sqlite-store (Phase 6.7/6.8 runs never logged; two sub-modes folded into one entry); clinica REQ-20260628 (telemetry is invocation-log only — no `total_tokens`/`tool_uses`/`duration_ms`, runs can't be ranked) and RETRO-REQ-20260613 (ambiguous-smoke/checkpoint gap variant); kuraka-control S12 (`duration_ms: null` renders a misleading 0.0s in the dashboard); guai REQ-20260703 (19/19 runs logged `budget_ok: true` including two over-cap runs). Variant: sie DD1243 (decisive prod-log evidence never consulted — operational-signal gap).
- **Root cause:** `skills/kuraka-policies.md` makes telemetry MANDATORY per run, but nothing *checks* it. a51f92d added an integrity check for exactly one field (`budget_ok` recompute in `aggregate-telemetry.py`); entries that are missing, zero-token without justification, or absent for a phase that the checkpoint says ran are still silently summed as zeros (confirmed in `aggregate-telemetry.py` — `int(r.get("total_tokens", 0) or 0)`).
- **Structural fix (framework, deterministic — same shape as the a51f92d budget_ok check):** extend `aggregate-telemetry.py` with a **completeness integrity section**: (a) flag runs with missing/zero `total_tokens`, `tool_uses` or `duration_ms` that lack the policies' explicit 0-token justification; (b) cross-check the cycle checkpoint's completed phases against telemetry entries and flag phases with no entry (the dbcanvas 6.7/6.8 case); (c) surface both in the DASHBOARD as "telemetry debt" per cycle. Optionally mirror as a final-auditor checklist line ("telemetry complete or debts justified").
- **Where:** framework (`aggregate-telemetry.py`; one line in `agents/final-auditor.md`).
- **Priority:** **HIGH** — this is the enforcement mechanism for an already-mandatory rule; without it the entire budget/optimization loop (T-rules, BUDGETS) runs on unverifiable data.

### Pattern 5: Cheap fix = expensive run (undigested re-runs) — **4/5 projects** — ADDRESSED TODAY (T10), enforcement gap remains

- **Occurrences:** clinica REQ-20260625 (2-line MINOR fix run cost 154K tokens — more than the full implementation; same shape previous cycle at 111K), REQ-20260612 (reviewer re-read 18 files, 101 tool uses); kuraka-control S1/S3/S4/S5a/S5b-2 (code-reviewer 25–58 min full re-reads in 4/8 cycles; T1 digest "still not applied" noted repeatedly); sie DD1243 (116K DRY-MINOR fix + 131K fixture fixup, retro explicitly notes Rule T8 existed and was not applied); guai (T8's original motivation; reviewer re-reads).
- **Root cause:** re-runs receive the full package instead of a delta digest. T8 (fdd1b0f) described the digest but is advisory — **sie DD1243 (2026-07-02) violated it post-fix**, the cleanest rule-fatigue case in the corpus.
- **Already addressed by:** a51f92d — Rule 17 **T10** (delta-only surgical re-runs) + T9 reviewer diff digest + kuraka-policies mid-cycle budget consequence (over-budget run ⇒ `budget_ok:false` + mandatory digest on next same-type run).
- **Residual gap:** the consequence only triggers on budget overrun; an undigested 154K fix-run under a generous budget never trips it, and nothing records whether a digest was actually provided. See Enforcement Gap 2 / Proposed Change 4.

### Pattern 6: Self-report trusted / claim propagation — **4/5 projects** — ALREADY ADDRESSED (a51f92d, verify)

- **Occurrences:** guai REQ-20260703 (false "untouched, verified by git diff" claim repeated verbatim by code-reviewer AND security-reviewer — full revert loop); dbcanvas sqlite-store (wrong Electron version propagated architect → story-refiner → story AC before backend-developer read the real artifact); sie DD1243 (digest anchors propagated cross-codebase until po-analyst reproduced them against real code); clinica RETRO-2026-06-07 (orchestrator declared done on proxies without observing the result — self-report-to-user variant).
- **Root cause:** downstream agents quote upstream claims instead of reproducing them.
- **Already addressed by:** a51f92d — `skills/kuraka.md` "claims are reproduced, never quoted"; Rule 17 T9 (zero-token deterministic orchestrator verification); backend-developer scope-fidelity hard rule; code-reviewer scope-fidelity diff; security-reviewer independent auth-surface diff. The dbcanvas and sie occurrences are the cross-project confirmation that T9 belongs in the framework (it was promoted from guai evidence alone).
- **Action:** none new; verify.

### Pattern 7: Retro→patch application leak (improvement loop not closed) — **4/5 projects** — ADDRESSED (Wave 1) with working evidence

- **Occurrences:** guai (proposals from REQ-20260611/20260623 documented as not landed by the project report's Gap 1); clinica REQ-20260625 (LL-004/LL-005 + probe rule proposed in 20260624 and never landed — "the most important process finding of this audit") → REQ-20260628 (§0 verifies all 4 patches landed: **loop closed for the first time**); kuraka-control (pattern-detector overdue at S5b-2: 8th retro, 3 since pass 1 — pre-dated the Wave 1 auto-trigger); dbcanvas (prior-retro patches not re-verified in cycle 1).
- **Already addressed by:** fdd1b0f Wave 1 — final-auditor/run-audit prior-retro application check + pattern-detector auto-trigger every 5 retros.
- **Evidence it works:** clinica REQ-20260628 is the direct post-fix proof. This report itself is the cross-project trigger firing.
- **Action:** none new; the check must keep appearing as §0 in every retro.

### Pattern 8: Mechanism hedged in prose / non-binding ACs — **3/5 projects** — ALREADY ADDRESSED (Wave 3, verify)

- **Occurrences:** kuraka-control S2, S3, S4, S5b-1, S5b-2 (LL-011/012/013 family — parse/compare/serialize mechanism hedged; S5b-1's `matter.stringify` would have silently corrupted every card write; all pre-date fdd1b0f); clinica REQ-20260610 (pitfall as prose Technical Note → implementer built the broken route) + REQ-20260613 (normative vs illustrative AC rows); guai (C7/C8 per the optimization report).
- **Already addressed by:** fdd1b0f Wave 3 — story-refiner name-the-mechanism + binding corrected snippets (check 15) + normative AC rows; architect-reviewer empirical adversarial freeze.
- **Action:** none new. No post-06-28 recurrence observed in the corpus.

### Pattern 9: Smoke/e2e against wrong or partial surface — **3/5 projects** — ALREADY ADDRESSED (a51f92d + Wave 4, verify)

- **Occurrences:** guai REQ-20260703 (green smoke against the wrong route), RETRO-20260530-perito (smoke green because the broken value only rendered on a screen the smoke skipped); clinica REQ-20260610 (dead sibling route), REQ-20260613 ("all controls hidden" read as no-access instead of matching-bug), REQ-20260628 (storage double-prefix); kuraka-control S12 (SPA nav full-reload variant).
- **Already addressed by:** a51f92d (e2e-tester route provenance pinned from the REQ; kuraka.md 6.8 route pinning — green against another route is a FAIL) + fdd1b0f Wave 4 (full-page snapshot, empty-vs-broken disambiguation).
- **Action:** none new; verify.

### Pattern 10: Advisory limits don't fire (tool-use / latency caps) — **3/5 projects** — PARTIALLY ADDRESSED → **NEW PROPOSAL #3 (MEDIUM)**

- **Occurrences:** kuraka-control S1, S3, S4, S5a, S5b-2 (code-reviewer 25–58 min, up to 106K tokens / 86–101 tool uses, "P1" carried across 5 retros with no consequence); clinica REQ-20260612 (101 tool uses vs cap 40, ~15 min vs 10-min policy — nothing fired because tokens stayed in budget); guai REQ-20260703 (budget_ok conflation — the token half, fixed today).
- **Root cause:** `kuraka-policies.md` defines per-category tool-use caps and latency expectations, but the only mid-cycle consequence added by a51f92d keys off **token** thresholds.
- **Structural fix:** extend the a51f92d mid-cycle consequence clause in `skills/kuraka-policies.md` to also trigger on tool-use-cap breach (>1.5×) — same consequence: flag the run, mandatory digest (T8/T10) on the next same-type run; recompute deterministically in `aggregate-telemetry.py` (it already sums `tool_uses`).
- **Where:** framework (`skills/kuraka-policies.md` + `aggregate-telemetry.py`).
- **Priority:** MEDIUM.

### Pattern 11: Nullable/enum mishandling at external-field seams — 2/5 projects — ALREADY ADDRESSED (Waves 2–3, verify)

- **Occurrences:** kuraka-control S1, S12, S5b-1, S5b-2 (LL-008 family: enum on externally-owned field; 4 nullable holes at the token/RL-5 seams — all pre-date fdd1b0f); guai (C9: null into token scope, fail-open).
- **Already addressed by:** fdd1b0f — architect-reviewer adversarial freeze (treat nullable contract fields as adversarial input), story-refiner binding snippets, security-reviewer seam checks.
- **Action:** none new; verify.

### Pattern 12: LOC/file-size limits detected late — 3/5 projects — ALREADY ADDRESSED (verify)

- **Occurrences:** guai REQ-20260602 (two files >500 LOC at Phase 5); kuraka-control S5b-1 + S5b-2 (functions >50 / files >400 LOC as Phase-5 IMPORTANTs, 2 consecutive cycles); dbcanvas code-graph-mvp (handler split for `max_file_loc`).
- **Already addressed by:** fdd1b0f Wave 3 — story-refiner check 14 ("size existing functions before adding wiring", pre-authorize extraction past `conventions.max_function_loc`).
- **Action:** none new; verify (all occurrences pre-date the fix).

---

## Enforcement Gaps (rules that existed and were still violated — mechanism, not rewording)

### Gap 1: T7 gate integrity — defeated by an unnamed variant (guai REQ-20260703)
- **Rule:** `rules/17` T7 (gate command integrity), in the vault since fdd1b0f (2026-06-28).
- **Violation:** guai REQ-20260703 (2026-07-03) — the gate was structurally sound, but an order-dependent guard test made green a lie anyway. The rule listed pipes/exit-codes; it didn't name isolation.
- **Diagnosis:** not rule fatigue but **rule under-specification** — the pattern mutates around the enumerated cases. a51f92d already extended T7 (isolated guard runs) and added T9 (deterministic orchestrator verification).
- **Enforcement mechanism (already in place as of today, must be exercised):** the T9 orchestrator step runs the isolation checks itself at 0 model tokens. Next-cycle verification in ALL projects (not just guai) is the test of whether the extension holds; if a third variant appears, the fix is a deterministic gate-linting script (grep Makefile/gate targets), not more prose.

### Gap 2: T8 fix-run digest — violated post-fix (sie DD1243, 2026-07-02)
- **Rule:** `rules/17` T8 (pre-extracted digest for fix-runs and reviewer), in the vault since fdd1b0f.
- **Violation:** sie DD1243 ran a 116K-token DRY-MINOR fix and a 131K fixture fixup with full-surface context; the retro itself notes T8 should have been applied. clinica REQ-20260625's 154K fix-run is the same shape (pre-fix, cited inside T8 as the motivating case — and it still happened again in sie after promotion).
- **Diagnosis:** T8 is advisory and **unauditable** — nothing records whether a digest was provided, and the a51f92d consequence only fires on budget overrun.
- **Enforcement mechanism:** add a `digest_provided: true|false` field to re-run/fix-run telemetry entries (schema in `kuraka-policies.md`), and have `aggregate-telemetry.py` flag any fix/re-run entry with `digest_provided: false` (or absent) the same way it now flags `budget_ok` contradictions. Proposed Change 4.

### Gap 3: Mandatory telemetry — mandated since the beginning, unenforced in 4 projects
- **Rule:** `skills/kuraka-policies.md` §Checkpointing/Telemetry (MANDATORY, every run, `total_tokens`+`tool_uses`+`duration_ms`).
- **Violations:** dbcanvas (both cycles), clinica REQ-20260628, kuraka-control S12 — see Pattern 4.
- **Diagnosis:** classic missing-enforcement: the writer is the only checker. a51f92d proved the fix shape works (deterministic recompute of `budget_ok`); extend it to completeness. Proposed Change 2.

### Gap 4: Tool-use caps — advisory, breached 6+ times with zero consequence
- **Rule:** `kuraka-policies.md` §Tool use limits per agent.
- **Violations:** kuraka-control ×5, clinica ×1 (Pattern 10).
- **Enforcement mechanism:** Proposed Change 3 (extend the mid-cycle consequence to tool-use breaches).

---

## Non-Patterns / Watch List

**WATCH (2 occurrences, single project — document, don't fix at framework level):**
- **Design-token referenced before defined** (kuraka-control S3 `--radius-card`, S5b-2 `--gold`) — project-layer CSS-token review-check already proposed in S5b-2; watch for a 2nd project.
- **Modal double-submit** (clinica ×2, F30 + REQ-20260624) — closed: LL-004 held when directly exercised in REQ-20260628. Watch only for regression.
- **React-namespace type imports** (kuraka-control S4 + S5a) — closed by project review-check §8 (suppressed in S5b-1/S5b-2).
- **Reviewer wall-clock outliers on multi-day sessions** (kuraka-control; `duration_ms` null/conflated) — folded into Pattern 4's completeness check.

**Single-project pattern at 3+ (project-layer fix owed, NOT framework):**
- **`:5174` Vite port collision** (kuraka-control, 6+ consecutive cycles) — trivially fixable in the project's dev config/README; its persistence across 6 retros is itself a small instance of Pattern 7. The project layer should land it next cycle.

**NOISE (1 occurrence — skip, but expensive ones noted):**
- **Wrong-target-codebase for a dual-implementation provider** (sie DD1243, ~406K tokens / 28.7% of the cycle wasted). Single project, but the costliest single finding in the non-guai corpus. The retro's project-layer Target-Codebase Gate is the right fix; promote to framework only if a second multi-codebase project reproduces it.
- Version-trusted-from-project-doc (dbcanvas Electron 41 vs 34.1.1) — variant of Pattern 1; the project-layer `version-verification.md` convention suffices; escalate on 2nd project.
- Prod-log operational signal not consulted (sie) — project-layer `phase1-provider-incident-logs.md` proposed in the retro.
- Destructive vault-sync incident (kuraka-control S12, `rsync --delete` wiped sie_v2 docs) — already structurally superseded by the central-store subsystem (kuraka-backup/restore, 2026-06-28); no live sync path with `--delete` from subagents remains.
- Stack-profile gaps (clinica angular, kuraka-control react-vite) — Wave 4 shipped angular/express/react profiles; react-vite still absent (LOW, framework artifact, listed below).
- dbcanvas FE-overlay silent non-render, sie `MmMadS` enum omission follow-up, guai one-off deferred debts — tracked in their own retros.

---

## Proposed Changes (NEW only — everything already covered by fdd1b0f/a51f92d is excluded)

| # | File | Change type | Description | Priority |
|---|------|-------------|-------------|----------|
| 1 | `skills/kuraka.md` (+ checkpoint schema in `skills/kuraka-policies.md`) | Add gate | **Phase 3.9 environment pre-flight** (orchestrator, deterministic, ~0 tokens per T9): boot stack/health, run the exact Phase-4 gate command + typecheck + collection once, record the **baseline red set** in the checkpoint; Phase-4 green = no regression vs baseline. Fix/waive boot failures before Phase 4. (Pattern 3 — 5/5 projects) | **HIGH** |
| 2 | `aggregate-telemetry.py` (+ 1 line in `agents/final-auditor.md`) | Add integrity check | **Telemetry completeness**: flag runs missing/zero `total_tokens`/`tool_uses`/`duration_ms` without the policies' 0-token justification; cross-check checkpoint phases vs telemetry entries; render "telemetry debt" in DASHBOARD. (Pattern 4 / Gap 3) | **HIGH** |
| 3 | `skills/kuraka-policies.md` (+ `aggregate-telemetry.py`) | Extend rule | Extend the a51f92d mid-cycle consequence to **tool-use-cap breaches** (>1.5× cap ⇒ flag + mandatory digest on next same-type run), recomputed deterministically. (Pattern 10 / Gap 4) | MEDIUM |
| 4 | `skills/kuraka-policies.md` telemetry schema + `aggregate-telemetry.py` | Add field | `digest_provided: bool` on fix/re-run telemetry entries; flag undigested re-runs — makes T8/T10 auditable. (Pattern 5 / Gap 2) | MEDIUM |
| 5 | `kuraka-artifacts/stack-profiles/react-vite.md` | Add artifact | Author the react-vite stack profile (kuraka-control S12 SPA-nav idiom, `<Link>` vs `<a>`, port config) — completes the Wave 4 set. | LOW |
| 6 | kuraka-control project layer | Project-layer | Land the `:5174` port fix (dev config/README) — 6-cycle-old friction; do NOT promote to framework. | LOW (project) |
| 7 | sie-integraciones project layer | Project-layer | Land DD1243's four proposed project-layer patches (target-codebase gate, prod-log grep, digest-hygiene lesson, T8 enforcement note) via its next final-auditor §0 check. | LOW (project) |

---

## Confidence: **HIGH**

- Patterns 1–3 rest on 5/5 distinct projects with dense, independently-extracted citations — far above the 2-project framework threshold; Pattern 3's absence of coverage was verified by grep (no Phase-0/pre-flight in `kuraka.md`/`kuraka-modes.md`), not assumed.
- "Already addressed" classifications were verified against the **current vault files** (scope-fidelity in backend-developer/code-reviewer/kuraka.md; T7/T9/T10 in rules/17; contract-first GATE in po-analyst; check 14 in architect-reviewer; budget_ok recompute in aggregate-telemetry.py), not just commit messages.
- MEDIUM-confidence caveat on the enforcement-gap diagnoses: the post-fdd1b0f window contains only 3 retros (clinica 06-28, sie 07-02, guai 07-03), so "rule working" vs "rule violated" judgments for Waves 1–4 rest on a small sample. The next pattern-detector pass (after ~5 more cycles) should re-test Patterns 1, 2, 5, 8, 9, 11, 12 against post-fix data only.

---

*Pattern Detector — cross-project pass 1. Corpus: 44 canonical retros under `projects/*/cycles/`. Next pass due after 5 new retros or 2026-08-03, whichever comes first.*
