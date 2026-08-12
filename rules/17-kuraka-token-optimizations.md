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

**Estimated savings:** 30–50K tokens per additional subagent. For a 3-phase
workflow: **100–150K total.**

### T1.1 — For ANALYSIS phases the digest is a checklist, not a judgement call

A digest for an **analysis** phase (1, 2, 2.5, 3) MUST carry, in addition to
source structure:

- **(a)** every existing test that asserts a COUNT over anything the REQ adds to
  (`len(x) == N`, `toHaveCount(N)`), with `file:line`;
- **(b)** the exception → HTTP status map for every error class the REQ's
  contracts name;
- **(c)** the FULL consumer set (grep output, **verbatim**) for every symbol the
  REQ claims to replace, rename or delete;
- **(d)** the call-site count for every function the REQ claims can "simply be
  replaced".
- **(e)** every `file:line` citation the REQ makes about existing code, carrying
  its **confidence mark**: `[VERIFICADO <cmd>]` / `[SIN VERIFICAR]` / `[ASUNCIÓN]`.
  Analysis phases (2 / 2.5 / 3) **re-verify only the last two marks** — a citation
  marked `[VERIFICADO]` is cited and moved past, never re-derived. Without the mark
  the agent cannot tell *already checked* from *merely believed*, so it re-derives
  100% of them.

Without (a)–(e) the agent re-derives them file by file, and that is where the
budget goes.

**Evidence for (e) — REQ-20260804-audit-columns:** `story-refiner` spent
**278,325 tokens / 111 tool uses** (1.55× the token cap, **3.7× the tool-use cap**)
re-verifying the 12 tables the REQ already cited by `file:line`. The lesson is NOT
"spend less": that same pass found a real REQ bug (`updated_by_id` re-stamp
semantics) and the phase-3 review, verifying against a live DB, dropped 21 indexes
and 2 dead tables. The lesson is **make the REQ prove what it asserts**, so
phase-2 verification is *targeted* instead of *exhaustive* — the finding is kept,
the re-derivation is not.

**Evidence (REQ-20260801):** phases 2, 2.5 and 3 ran **4-for-4 over budget at
~1.9×** doing exactly this re-derivation, while every Phase-4 batch given a
strict two-file read list ran **12-for-12 in band at 0.46× of cap** — over a
*wider* surface. Same repo, same week, same agent families. The variable was the
prompt shape, not the task.

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
- [ ] Re-run of a phase already executed this cycle → **FRESH agent** with a
      delta-only prompt (T10) — never `SendMessage`/resume on a large transcript
- [ ] Analysis phase (1 / 2 / 2.5 / 3) → digest carries T1.1 items (a)–(d):
      count-asserting tests, exception→HTTP map, verbatim consumer sets,
      call-site counts
- [ ] Phase 3.9 baselined **every** gate command, one per workspace — not just
      the primary test suite (T7.1)
- [ ] Every factual claim in an `AskUserQuestion` option was reproduced by a
      command first, or is marked `sin verificar` (T9.1)
- [ ] Deterministic verifications (scope diffs, smoke-route match, isolated
      guard tests) planned as ORCHESTRATOR steps at 0 tokens, not delegated (T9)
- [ ] Telemetry JSON is written after every `Agent` invocation, with `budget_ok`
      actually computed vs the phase threshold (never defaulted to `true`)

**Golden rule:** if you doubt whether a rule T applies, ask the user — don't
assume. The cost of a one-sentence confirmation is lower than the cost of a
wasted 200K-token subagent invocation.

---

## Rule T0 — El tope de presupuesto es una ACCIÓN del orquestador, no un consejo

**Aplica siempre**, después de CADA invocación de `Agent`.

El tope deja de ser texto advisory en un fichero append de agente. El orquestador
mide `total_tokens` contra el umbral de la fase (`kuraka-policies.md` → Token
Budget) y actúa, a coste 0 tokens:

| Consumo | Acción del orquestador |
|---|---|
| **> 1,0×** | WARN, escribir `budget_note`, continuar |
| **> 1,5×** | WARN + **escribir en el checkpoint la causa** antes de la siguiente invocación |
| **> 2,0×** | **PARADA DURA.** No invocar la siguiente fase hasta re-cortar el digest o el alcance, y escribir el re-corte en el checkpoint |

**Por qué es una acción y no una frase:** seis retros previos propusieron la
misma advertencia en prosa durante **ocho ciclos**. `story-refiner` acumula
**15/38 runs sobre presupuesto** entre ciclos, y en REQ-20260801 gastó 366,7K y
luego 416,9K. Re-proponer prosa no es un plan.

**Un solo modelo de presupuesto** (ver P9): mandan los **umbrales por FASE** de
`kuraka-policies.md`, porque codifican lo que la fase *debería costar*, no lo que
el agente *suele gastar*. Si el agregador usa umbrales por agente, se corrige el
agregador, no la regla.

---

## Rule T7.1 — La 3.9 mide TODOS los gates, uno por workspace

El pre-flight de Fase 3.9 debe ejecutar y registrar, **por workspace**, TODOS los
comandos por los que cualquier gate posterior vaya a juzgarse — no solo la suite
principal. En este proyecto:

```
backend:   make test-run
frontend:  npm run type-check   Y   npm run lint   Y   npm test
```

Registrar exit code, conteos y una lista `baseline_red` explícita **para cada
uno**. Un gate sin línea base grabada no puede distinguir *preexistente* de
*regresión*.

**Evidencia (REQ-20260801):** solo se midió `make test-run`. Cuando
`npm run lint` devolvió 1 durante S3, hubo que reconstruir la línea base a
posteriori para averiguar si el error era nuestro.

---

## Rule T6 — Implementación secuencial + `make test` obligatorio por story (provider migrations)

**Aplica cuando** cualquiera de estas es cierta:
- La story crea o modifica un provider, processor o integration handler.
- La story crea un seed o una migration, o cambia un modelo SQLAlchemy.
- La story usa abstract base classes, mocks cross-module o fixtures custom.
- La story implementa más de una feature distinta (riesgo de interdependencia).

**Cómo**:
- NO lanzar varias stories en paralelo. Implementar las stories **secuencialmente**.
- Después de que cada story termine, correr `make test` (o `make test-fast`) **antes** de empezar la siguiente.
- Si `make test` falla, arreglar el bug en la story actual antes de avanzar.
- Esta disciplina demostró entregar ~0 retrabajo cross-story (RETRO-DD-1031-rerun), frente a un batch que acumuló "23 fallos" (RETRO-DD-1031).

**Excepción**: stories puramente frontend sin cambios de backend pueden ir en batch, siempre que la verificación sea por-story.

**Por qué**: en DD-896 (FM-02), 3 bugs distintos de S1 se descubrieron en Phase 6 después de implementar las 7 stories. En DD-1031 el batch paralelo acumuló bugs de S1+S3+S4 que se propagaron por re-implementaciones. Secuencial + make-test por story detecta el bug en su origen.

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

**Estimación de ahorro**: ~245K tokens por incidente evitado (el loop de
revert 6.8 de REQ-20260703) + ~100K en relecturas de reviewers. Y es una
mejora de calidad, no solo de costo: la verificación barata atrapa lo que la
cara no atrapó.

### T9.1 — T9 aplica también a las afirmaciones del PROPIO orquestador

T9 prohíbe **citar** el claim de un agente en vez de reproducirlo. Aplica con la
misma fuerza a las afirmaciones factuales del **orquestador**: el texto de las
opciones de `AskUserQuestion`, los resúmenes de gate y los informes de fase.

Cualquier afirmación sobre **dónde vive un artefacto, qué contiene un contenedor,
qué enruta una config o qué produjo un comando** debe reproducirse (un comando,
pegado) ANTES de hacer la pregunta — o marcarse explícitamente como `sin
verificar` en el propio texto de la opción.

**Evidencia (REQ-20260801):** la opción que el usuario eligió afirmaba que las 50
imágenes de catálogo "van dentro de la imagen del contenedor del backend". No era
cierto: se copiaban al volumen en tiempo de ejecución. La decisión era buena; la
justificación presentada para tomarla era falsa. Un solo
`grep -n catalog_images backend/Dockerfile` lo habría detectado.

Un usuario que decide sobre una premisa falsa no ha decidido.

---

## Rule T10 — Re-runs quirúrgicos: re-invocar una fase con el DELTA, no con el paquete completo

**Aplica cuando** se re-invoca un agente para corregir/ajustar un artefacto que
él mismo ya produjo en este ciclo (story update, fix de un finding, ajuste de
un test plan).

**Problema**: en REQ-20260703, el re-run de story-refiner para cambiar UNA ruta
en S3 costó **171.744 tokens con solo 2 tool uses** — el prompt re-inyectó el
REQ completo + todas las stories + contexto de código. El agente no exploró
nada: todo el costo fue contexto re-pegado.

**MECANISMO DE ENTREGA — esta es la parte que falla, no el prompt:**

Entregá el delta **CREANDO UN AGENTE NUEVO** cuyo prompt lleve únicamente:
`{el artefacto a editar, pegado o nombrado}` + `{el delta, en imperativo}` +
`{no releas nada más}`.

**NUNCA entregues un delta por `SendMessage` / resume cuando el transcript del
agente previo sea grande.** Un resume **REPRODUCE el transcript completo** antes
de leer el prompt del delta, así que un prompt ajustado no compra nada.

**Evidencia (REQ-20260801):** un delta de 8 ediciones gastó **416.946 tokens —
un 13,7% MÁS** que los 366.705 del run que venía a corregir, contra un objetivo
de 30–50K. El prompt era correcto; el transporte lo anuló.

Reservá el resume para agentes con contexto acumulado pequeño **o** genuinamente
necesario.

**Detector en vuelo** (ya documentado en `story-refiner.append.md`, y disparó
correctamente en este ciclo): **tokens ALTOS + tool-use BAJO = contexto
re-pegado**. El run de remediación dio **8.871 tokens por tool-use** frente a
3.667 del original. Comprobá ese ratio en cuanto un run devuelva.

**Cómo**: el prompt de un re-run contiene SOLO:
1. El artefacto afectado (la story/plan/archivo a corregir — solo ese).
2. El delta a aplicar, en imperativo ("S3: reemplazar `/auth/register` por
   `/cliente/auth/register`; ajustar AC3 y AC14 en consecuencia").
3. La instrucción "NO releer el resto del paquete; el resto del ciclo no cambió".

Target: **30–50K tokens** por re-run (vs 120–170K con contexto completo).

**Estimación de ahorro**: 100–140K tokens por re-run de fase.

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
