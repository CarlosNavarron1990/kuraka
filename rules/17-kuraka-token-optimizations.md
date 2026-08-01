---
description: Token-saving prompt patterns for orchestrating the Kuraka. Reduces cycle cost ~35% on low-risk changes without sacrificing rigor.
alwaysApply: true
---

# Kuraka Token Optimizations

Apply these rules whenever you orchestrate the Kuraka defined in
`.claude/skills/kuraka.md` (and companion files `kuraka-modes.md`,
`kuraka-policies.md`). They do not replace the Kuraka — they guide
*how* you prompt the subagents and *which* phases you invoke.

Baseline measured on the cycle of 2026-04-21 (homologate-new-scale-frontend):
**458K tokens** for a UI-only restyle of 7 files across 3 phases. Applying the
5 rules below, the same cycle would cost **~270–300K (-35%)**.

---

## Rule 0 — Scale the pipeline to the change's actual risk

Before launching Phase 1, evaluate the change surface and build a reduced
pipeline with only the phases that add value. Announce the pipeline, justify
which phases are skipped, and request user confirmation before invoking any
subagent.

**Surface → pipeline examples:**

| Surface | Phases to run | Phases to skip |
|---------|---------------|----------------|
| UI-only restyle (CSS classes, no logic, no types) | 1 + 2 + 4b | 2.5, 3, 5, 5.5, 6, 6.5, 6.7, 7 |
| Pure type tightening (no logic) | 1 + 4b + 5 | 2.5, 3, 5.5, 6, 6.5, 6.7, 7 |
| New endpoint with logic | full 8 phases | — |
| Auth / provider / schema change | full 8 phases + mandatory 5.5 | — |

Do not apply the rigid "Lite mode" criteria (≤ 3 files, ≤ 50 LOC) as the only
gate — they are narrow. Use them as a hint, not a law.

**Golden rule:** if you doubt whether to skip a phase, ask the user — don't assume.

---

## Rule T1 — Pre-cook a "context digest" into every subagent prompt

**Applies when:** you'll launch ≥ 2 subagents that share the same reference
files (e.g., `main.css`, visual reference pages, common rules).

**How:** before invoking the first agent, read those reference files yourself
(as orchestrator), extract the useful snippets once, and embed them into every
subagent prompt under a fixed header:

```
## Context digest (pre-extracted — do NOT re-read unless ambiguous)

### Design tokens available in main.css
- brand-lime, brand-text, brand-text-dim, brand-card, brand-panel,
  brand-border, brand-muted, brand-dark
- Component classes: card, btn-primary, btn-secondary, btn-danger,
  btn-icon, input-field, badge-lime|amber|blue|red|gray, table-row

### Reference patterns from BaremosPage.vue
- Header: `<h2 class="text-xl font-semibold text-brand-text">`
- Stepper with connector lines: {snippet with line numbers}
- Jobs table row: `<tr class="table-row">`
- Stat card: {snippet}

### Reference patterns from DuplicidadPage.vue
{snippet}
```

The agent only re-reads if it finds ambiguity.

**Digest-trust protocol (mandatory — the digest is only useful if it can be
trusted):**

- The orchestrator stamps the digest header **`VERIFIED`** only when it
  reproduced the claims itself (T9-style: ran the greps, read the cited lines
  this cycle, against THIS target). A `VERIFIED` digest may be consumed by the
  subagent **without re-reading the cited files** — re-grounding a stamped
  digest is the single worst recurring budget leak (guai: story-refiner over
  budget 6/29 cycles, one 287K/77-tool re-verification run). An **unstamped**
  digest is a hint, not truth: the agent treats its anchors as unverified claims.
- **Re-scope invalidates the digest.** If the cycle is re-pointed at a different
  codebase, module, branch, or target than the digest was built from, the
  orchestrator REBUILDS the digest from the target's real files and re-verifies
  every anchor (file:line, switch cases, enum values) before it enters a
  REQ/brief. A stale digest anchor leaked a phantom requirement from a sibling
  codebase into a brief (sie DD1243: ~406K tokens of mis-scoped work).
- **Hard context ceiling per agent:** the invocation states the digest/package
  budget; if the package would breach it before the agent's first tool call, the
  agent asks the orchestrator to narrow it instead of absorbing it.

**Estimated savings:** 30–50K tokens per additional subagent. For a 3-phase
workflow: **100–150K total.**

---

## Rule T2 — For restyles: verify only at the end, not per file

**Applies when:** the story does not change types or logic (pure
`<template>` + CSS class edits).

**How:** in the implementer's prompt, replace

> "Run `npm run typecheck` + `npm run lint` after each file. STOP on first error."

with

> "Make all class-level edits across the N files. Run `npm run typecheck` +
> `npm run lint` ONLY at the end. If either fails, identify the offending
> file from the error output and fix it."

**Why:** `vue-tsc --noEmit` reprocesses the full TS graph regardless of how
many files changed. Running it N times is identical in correctness to running
it once at the end, but costs N× in tokens and time.

For changes that **do** modify types or logic, keep the per-file check.

**Estimated savings:** 15–25K tokens + ~40% of implementation-phase time.

---

## Rule T3 — Collapse Phase 1 + Phase 2 into a single subagent for low-risk changes

**Applies when:** the surface is purely cosmetic (restyle, rename) or purely
mechanical (library swap with no contract change).

**How:** instead of [[po-analyst]] → gate → [[story-refiner]] → gate, launch one
subagent in combined mode. Prompt pattern:

```
You produce BOTH deliverables in one pass:
  (a) docs/process/REQ-{date}-{slug}.md — scope, risks, mode recommendation
  (b) docs/process/stories/REQ-{date}-S1.md — story with compact AC table (see T4)
```

This is consistent with `workflow.md`'s existing `LITE_COMBINED` mode; extend
its applicability beyond the strict 9 Lite criteria when the risk evaluation
is low.

**Do NOT collapse** when the change touches business logic, API contracts,
DB, auth or providers — there the phase separation adds real value.

**Estimated savings:** ~80–100K tokens (removes one full subagent startup +
one context re-read).

---

## Rule T4 — Compact "mapping-table" stories for mechanical patterns

**Applies when:** the story is a mechanical replacement pattern (CSS restyle,
identifier rename, import path change).

**How:** instruct the [[story-refiner]] to use a per-file mapping table
instead of narrative AC IDs:

```
Format the acceptance criteria as a mapping table per file, NOT as
narrative AC IDs:

| File | Before | After |
|------|--------|-------|
| UploadStep.vue | `bg-gray-800 rounded-xl p-6` | `card space-y-4` |
| UploadStep.vue | `bg-[#CCFF00] text-black ... hover:bg-[#B7FF1E]` | `btn-primary` |
| ... | ... | ... |

Reserve narrative AC for cases where behavior or ordering matters.
Target: ≤ 100 lines total story, not 300+.
```

**Estimated savings:** 30–40K tokens in the implementation phase (which
re-reads the story). Reference: cycle of 2026-04-21 produced a 314-line /
69-AC story — the same contract fits in ~80 lines as a compact table.

---

## Rule T5 — The subagent does not auto-verify what the orchestrator will verify

**Applies always** when the orchestrator has an external verification plan
(md5 of script blocks, diff stats, grep of imports, re-running
typecheck/lint).

**How:** add to the implementer's prompt:

```
Do NOT run verification scripts (md5, diff, grep) inside this agent.
The orchestrator will verify externally after you finish.
Report only:
  (1) files modified,
  (2) ACs satisfied,
  (3) any AC you couldn't satisfy and why.
```

**Estimated savings:** 10–15K tokens in duplicated verification tool uses.

---

## Checklist before invoking any workflow subagent

- [ ] Evaluated change surface (Rule 0) and picked the minimum phases
- [ ] Proposed the pipeline to the user with per-phase justification
- [ ] If ≥ 2 subagents share reference files → built context digest (T1)
- [ ] If restyle / mechanical → prompt asks for end-only typecheck/lint (T2)
- [ ] If restyle / mechanical → considered Phase 1+2 combined (T3)
- [ ] If restyle / mechanical → story asked as mapping table, not narrative (T4)
- [ ] Implementer prompt explicitly forbids auto-verification (T5)
- [ ] Reviewer prompts (Phase 5 / 5.5) include the pre-extracted
      changed-functions diff digest (T8 + T9) — scope check as a table, not a re-read
- [ ] Re-run of a phase already executed this cycle → delta-only prompt (T10),
      never the full context package again
- [ ] Deterministic verifications (scope diffs, smoke-route match, isolated
      guard tests) planned as ORCHESTRATOR steps at 0 tokens, not delegated (T9)
- [ ] Telemetry JSON is written after every `Agent` invocation, with `budget_ok`
      actually computed vs the phase threshold (never defaulted to `true`)

**Golden rule:** if you doubt whether a rule T applies, ask the user — don't
assume. The cost of a one-sentence confirmation is lower than the cost of a
wasted 200K-token subagent invocation.

---

## Rule T6 — Implementación secuencial + `make test` obligatorio por story (provider migrations)

**Aplica cuando** cualquiera de estas es cierta:
- La story crea o modifica un provider, processor o integration handler.
- La story crea un seed o una migration, o cambia un modelo SQLAlchemy.
- La story usa abstract base classes, mocks cross-module o fixtures custom.
- La story implementa más de una feature distinta (riesgo de interdependencia).

**Cómo**:
- NO lanzar varias stories en paralelo. Implementar las stories **secuencialmente**.
- Después de que cada story termine, correr el **gate COMPLETO** de la story —
  **todos los gates declarados del stack, no solo `make test`**: como mínimo
  `make test` **Y** `make typecheck` (mypy/vue-tsc/tsc) **Y** `make lint`, **antes**
  de empezar la siguiente. Un "verde" por story que corrió solo `pytest`+`ruff`
  **no es verde** si se saltó el typecheck (ver "Por qué", REQ-20260731-adelanto).
- Si CUALQUIERA de esos gates falla, arreglar el bug en la story actual antes de avanzar.
- Esta disciplina demostró entregar ~0 retrabajo cross-story (RETRO-DD-1031-rerun), frente a un batch que acumuló "23 fallos" (RETRO-DD-1031).

**Excepción**: stories puramente frontend sin cambios de backend pueden ir en batch, siempre que la verificación por-story corra igual el gate COMPLETO del frontend (lint + typecheck + test).

**Por qué**: en DD-896 (FM-02), 3 bugs distintos de S1 se descubrieron en Phase 6 después de implementar las 7 stories. En DD-1031 el batch paralelo acumuló bugs de S1+S3+S4 que se propagaron por re-implementaciones. En **REQ-20260731-adelanto** el gate per-story corrió `pytest`+`ruff` pero **no `mypy`**, y un BLOCKER de typecheck (`union-attr` por un `Empresa | None` sin guard, introducido en S4) sobrevivió hasta la Fase 5 de code review — habría sido 0 findings de haber corrido `make typecheck` por story. Secuencial + **gate completo** por story detecta el bug en su origen. Concuerda con "Definition of green" (`kuraka-policies.md`) y Rule T7: correr **todos** los gates declarados, nunca un subconjunto.

**Estimación de ahorro**: 50-100K tokens en provider migrations (elimina la tormenta de debugging de errores acumulados).

---

## Rule T7 — Gate command integrity (correctness, not token-saving)

**Aplica siempre** que el resultado de un test/typecheck sea el gate para
avanzar una story o fase.

**Cómo**: correr el comando del gate SIN pipe y asertar sobre **su propio**
exit code (`make test-run`, luego `$?`). NUNCA pipear el comando del gate
(`make ... | tail`, `... | grep`) — el shell reporta el exit code del ÚLTIMO
comando (el del pipe), así que una suite que falla puede leerse como verde. Si
hay que recortar la salida, redirigir a un archivo y leer el archivo.

Además: al planificar el pipeline, verificar que cada gate declarado realmente
**puede fallar**. Un `make test-run` sin `--exit-code-from`, un target que no
propaga el fallo, o un eslint no instalado (exit 127) son gates muertos —
arreglarlos o marcarlos `SKIPPED (broken: <reason>)` explícitamente, nunca
tratarlos como verde.

**Aserción del gate**: leer el exit code Y asertar la **ausencia** de "failed"
en la salida — nunca solo la presencia de "passed". Y antes de declarar verde
una fase, correr los **guard tests críticos aislados**
(`pytest <archivo>::<test>`): un exit 0 de suite completa puede ocultar un test
orden-dependiente (fixture module-scoped + monkeypatch function-scoped) que
pasa en agregado y falla solo — exactamente la regresión que el guard existe
para atrapar (REQ-20260703).

**Por qué**: REQ-20260611 S3 avanzó en FALSO VERDE (`make ... | tail`) con la
suite fallando en collection; REQ-20260703 cerró un gate con un guard test
falso-verde por orden. Ver también `kuraka-policies.md` → "Gate command
integrity" y "Definition of green".

---

## Rule T9 — Verificación determinística del orquestador a costo CERO (claims nunca se citan, se reproducen)

**Aplica siempre** antes de declarar verde cualquier gate de las fases 4–6.8.

**Problema**: en REQ-20260703, code-reviewer + security-reviewer gastaron
**325K tokens y ambos se perdieron el defecto principal** (un wiring fuera de
scope en un endpoint de auth) porque citaron el self-report del developer
("untouched, verified by git diff") en vez de correr el diff. Mientras tanto,
los dos runs de `orchestrator-gate` a **0 tokens** fueron los que detectaron y
confirmaron la verdad.

**Cómo**: todo lo verificable con un comando determinista lo corre el
orquestador directamente (0 tokens) — un subagente solo verifica lo que
requiere juicio:

- **Claims negativos de scope** ("no toqué X"): `git diff <baseline>..HEAD -- <path>`
  de cada función reportada como untouched, leído por el orquestador. El set de
  funciones cambiadas debe ser igual al set que la story autoriza como MODIFY —
  función extra ⇒ BLOCKER, de vuelta a Phase 4.
- **Ruta del smoke**: grep de la URL realmente golpeada en el log del smoke vs
  la ruta de producción que nombra el REQ. No coinciden ⇒ el smoke es FAIL.
- **Guard tests**: correr aislado cada test de aserción negativa (ver T7).
- **Digest para reviewers** (extiende T8): el orquestador pre-extrae los hunks
  por función del `git diff` y los pasa al code/security-reviewer como tabla
  "set cambiado vs set autorizado" — la verificación de scope se vuelve un
  chequeo de tabla, no una relectura de la superficie.
- **El entorno de la reproducción también se verifica** (la reproducción de un
  claim solo vale si corre en un entorno fiable):
  - Si la story tocó el manifest de dependencias, el lockfile o las migraciones,
    la imagen/entorno de test se **reconstruye ANTES** de reproducir el gate
    (no-cache si cambiaron migraciones). Nunca declarar verde sobre un
    contenedor con un install efímero o una capa `COPY . .` stale (adela: dos
    falsos verdes en un ciclo — "89 passed" con una dep ausente de la imagen;
    guai: ~179 fallos fantasma por imagen stale).
  - La reproducción corre en un **entorno limpio no sombreado por el host**
    (p. ej. un `node_modules` bind-mounted del host filtra binarios de otra
    plataforma).
  - Una ráfaga súbita de `Can't locate revision` / `column does not exist` tras
    tocar migraciones es una **regresión FALSA de entorno stale**: rebuild y
    re-run, nunca "arreglar" código para satisfacer una imagen vieja.

**Estimación de ahorro**: ~245K tokens por incidente evitado (el loop de
revert 6.8 de REQ-20260703) + ~100K en relecturas de reviewers. Y es una
mejora de calidad, no solo de costo: la verificación barata atrapa lo que la
cara no atrapó.

---

## Rule T10 — Re-runs quirúrgicos: re-invocar una fase con el DELTA, no con el paquete completo

**Aplica cuando** se re-invoca un agente para corregir/ajustar un artefacto que
él mismo ya produjo en este ciclo (story update, fix de un finding, ajuste de
un test plan).

**Problema**: en REQ-20260703, el re-run de story-refiner para cambiar UNA ruta
en S3 costó **171.744 tokens con solo 2 tool uses** — el prompt re-inyectó el
REQ completo + todas las stories + contexto de código. El agente no exploró
nada: todo el costo fue contexto re-pegado.

**Cómo**: el prompt de un re-run contiene SOLO:
1. El artefacto afectado (la story/plan/archivo a corregir — solo ese).
2. El delta a aplicar, en imperativo ("S3: reemplazar `/auth/register` por
   `/cliente/auth/register`; ajustar AC3 y AC14 en consecuencia").
3. La instrucción "NO releer el resto del paquete; el resto del ciclo no cambió".

**T10.a — agente NUEVO vs resume (medido, no intuitivo).** Reanudar un agente
re-factura TODO su transcript en cada mensaje. Para deltas pequeños sobre
archivos ya identificados, lanzá un agente NUEVO con prompt quirúrgico;
reanudá solo cuando el razonamiento necesario vive únicamente en el transcript
(una decisión de diseño a medio explicar, un estado exploratorio irrecuperable).
Caso real (facturacion-honorarios): reformular UNA línea de comentario vía
resume costó 117K; un run nuevo de 5 fixes costó 52K. Ante la duda: agente nuevo.

**T10.b — clasificá el patch ANTES de presupuestarlo como delta.** Un delta T10
solo es barato si es **textual y acotado** (renombrar, ajustar una AC, corregir
una ruta). Generar código/config **normativo nuevo** (un bloque copy-this, una
migración, un snippet de wiring) tiene presupuesto de run completo aunque llegue
como "fix". Lotes mixtos se parten en dos runs (uno textual T10, uno generativo
normal) — un "delta" mixto costó 281K contra un target de 30–50K.

**T10.c — tiers de presupuesto:**

| Tier | Alcance | Target |
|------|---------|--------|
| T10-S | 1 archivo, ≤3 edits textuales | 30–50K |
| T10-M | ≤3 archivos, ≤10 findings | 90–130K |
| T10-L | >3 archivos o cambio de contrato | T10 NO aplica — re-run de fase |

Pasá solo el imperativo por finding, no las justificaciones completas. Un run
T10-M en banda no es una violación; un T10-L disfrazado de delta sí.

**Estimación de ahorro**: 100–140K tokens por re-run de fase; 60–120K por
delta trivial que iba a resume.

---

## Rule T8 — Digest pre-extraído para fix-runs y para el code-reviewer

**Aplica cuando**: (a) lanzás un run de "aplicar N MINOR/IMPORTANT fixes" tras
un review, o (b) invocás al [[code-reviewer]] sobre una superficie grande.

**Problema**: estos runs recargan TODA la superficie para hacer cambios chicos.
Casos reales: un fix de 2 líneas costó **154K tokens** (clinica-dental,
REQ-20260625) porque el agente releyó el módulo/freeze/review completos; el
code-reviewer corrió 25–58 min en 4/8 ciclos releyendo archivos uno por uno
(kuraka-control P1). El costo es el contexto, no el trabajo.

**Cómo** (usá el skill [[compact-context]] para producir el digest):

- **Fix-run**: pasá SOLO `{archivo · rango de líneas · texto exacto del finding
  a aplicar}` por cada fix. Prohibí re-leer la superficie completa salvo
  ambigüedad real.
- **Code-reviewer**: pasá al inicio `{esquema/contratos congelados + tabla de
  decisión/invariantes a verificar + lista de archivos cambiados con su LOC}`.
  Una tabla de ataque/invariantes precisa hace al reviewer rápido aunque la
  superficie sea grande (validado en kuraka-control S5b-1).

**Estimación de ahorro**: 40–80K tokens por fix-run; latencia del reviewer de
25–58 min a in-band.
