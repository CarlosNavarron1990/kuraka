---
description: Token-saving prompt patterns for orchestrating the Kuraka. Reduces cycle cost ~35% on low-risk changes without sacrificing rigor.
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

**Digest invalidation and ceiling** *(1.1.0 harvest P4 — restored 2026-11; lost in
the 2026-08-12 rewrite):*

- **Re-scope invalidates the digest.** If the cycle is re-pointed at a different
  codebase, module, branch, or target than the digest was built from, the
  orchestrator REBUILDS the digest from the target's real files and re-verifies
  every anchor (file:line, switch cases, enum values) before it enters a
  REQ/brief; every `[VERIFICADO]` mark from the old target drops to
  `[SIN VERIFICAR]`. A stale digest anchor leaked a phantom requirement from a
  sibling codebase into a brief (sie DD1243: ~406K tokens of mis-scoped work).
- **Hard context ceiling per agent:** the invocation states the digest/package
  budget; if the package would breach it before the agent's first tool call, the
  agent asks the orchestrator to narrow it instead of absorbing it.

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

## Rule T3 — Phases 1 + 2 + 2.5 collapse into a single subagent BY DEFAULT

**Applies BY DEFAULT**, in every mode. Phases 1 (REQ), 2 (stories) and 2.5
(test plan) run as ONE `po-analyst` invocation unless a trigger forces the
split: ≥4 stories, or stories the user must approve separately from the REQ.
This rule used to be limited to cosmetic/mechanical surfaces; measurement over
197 archived runs promoted it to the default — the split was the single most
expensive default in the suite.

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

**Measured savings:** ~350K tokens per cycle. Medians over 197 archived runs:
Phase 1 = 123K, Phase 2 = 171K, Phase 2.5 = 179K (473K total) against 123K for
the combined `1+2` run (17 cycles). The saving is not the prose it skips — it
is two subagent startups and two context re-reads that never happen.

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
principal: test, lint y typecheck de cada workspace.

**Los comandos salen del proyecto, nunca de este texto.** Se leen de
`kuraka.config.yaml` (`stack.<workspace>.test_cmd` / `lint_cmd` /
`typecheck_cmd`) o de `conventions/gate-commands.md` de la capa del proyecto; los
scripts frontend, de `jq .scripts package.json`. Si un workspace no define
typecheck, se registra el sustituto realmente corrido (p. ej. `npx tsc --noEmit`)
marcado como sustituto. Un valor `TODO`/`TBD`/vacío en el config **no es un
gate**: se reporta como hueco, nunca como verde. (Este texto citaba antes los
comandos de un proyecto concreto — `make test-run`, `npm run type-check` — y
`po-analyst` los copió en 4 artefactos de otro proyecto que no los tenía:
possuite FD-1, azure FD-8.)

Registrar exit code, conteos, `gates_measured_at` (HEAD) y una lista
`baseline_red` explícita **para cada uno**. Una línea base de OTRO ciclo no
sirve: se mide en este (editorial F-31). Un gate sin línea base grabada no puede distinguir *preexistente* de
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
exit code (el `test_cmd` del proyecto, luego `$?`). NUNCA pipear el comando del gate
(`make ... | tail`, `... | grep`) — el shell reporta el exit code del ÚLTIMO
comando (el del pipe), así que una suite que falla puede leerse como verde. Si
hay que recortar la salida, redirigir a un archivo y leer el archivo.

Además: al planificar el pipeline, verificar que cada gate declarado realmente
**puede fallar**. Un target de docker-compose sin `--exit-code-from`, un target que no
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

**Un runner por host**: un gate leído mientras otra suite, corrida de mutación o
E2E corre en el mismo host es **nulo** — se repite a solas. Un test que falla
solo bajo carga se corre **aislado 3 veces** antes de llamarlo flaky
(editorial F-15, 5 retros). Detalle en `kuraka-policies.md` → "Definition of
green".

**Por qué**: REQ-20260611 S3 avanzó en FALSO VERDE (`make ... | tail`) con la
suite fallando en collection; REQ-20260703 cerró un gate con un guard test
falso-verde por orden. Ver también `kuraka-policies.md` → "Gate command
integrity" y "Definition of green" (entorno actual, verde atado a HEAD, comandos
del proyecto).

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
- **El entorno de la reproducción también se verifica**: si la story tocó el
  manifest de dependencias, el lockfile o las migraciones, la imagen/contenedores
  de test se **reconstruyen/recrean ANTES** de reproducir el gate; nunca sobre un
  entorno sombreado por el host; una ráfaga de `Can't locate revision` /
  `column does not exist` tras tocar migraciones es regresión FALSA de imagen
  stale — rebuild y re-run (1.1.0 P6, restaurado 2026-11; detalle en
  `kuraka-policies.md` → "Definition of green").
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

*(T10.b/T10.c — 1.1.0 harvest P5, restaurados 2026-11; se perdieron en la
reescritura del 2026-08-12.)*

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
T10-M en banda no es una violación; un T10-L disfrazado de delta sí. El cost
artifact también escala: un delta sobre un archivo de stories enorme paga la
lectura del archivo entero — una story nueva va en su propio archivo
(editorial F-17).

**T10.d — un delta TEXTUAL sobre `docs/` no lleva agente.** Registrar las
respuestas del usuario, renombrar un campo, corregir un valor en una AC o un
oráculo, alinear una story con el freeze: lo aplica el orquestador con la
herramienta de edición (`docs/` es suyo), a ~0 tokens. El tier T10-S queda para
deltas que requieren juicio del agente sobre su propio artefacto. Nunca se
"aplica" un delta generando un script con el texto embebido ni reescribiendo el
archivo entero (estimator-v2 S05: 11 min y un script de 94K caracteres para
registrar 20 respuestas; 7 min para 28 correcciones de redacción).

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

---

## Rule T11 — Los micro-deltas se agrupan: el suelo del subagente es ~60K

Un delta de 2 lineas costo 59.634 tokens y 2 tool uses (REQ-20260822,
revert CRIT-2): el arranque de cualquier subagente en este proyecto
(definicion + CLAUDE.md + reglas) cuesta ~55-60K antes del primer tool use.

**El piso son 60K; el costo ESPERADO es el doble.** La mediana medida sobre
1197 runs de 100 ciclos archivados es de **120-180K por invocacion, sea cual
sea la fase** — 4a 162K, 2.5 179K, 5 124K, 7 47K. Los 60K son lo que cuesta un
delta trivial, no lo que cuesta una invocacion tipica. La consecuencia
refuerza la regla: agrupar no ahorra 60K por micro-delta evitado, ahorra ~150K.
Una micro-tarea NO amortiza un subagente. Acumula los micro-deltas
pendientes y despachalos en UN solo run con la lista completa; reserva el
run individual para cuando el delta no puede esperar al siguiente batch.

## Rule T12 — Presupuesto de mutacion y de infraestructura de test

La verificacion por mutacion duplica el trabajo por test (romper, correr,
confirmar, restaurar) y una story que monta infraestructura de test paga
ficheros extra. Evidencia: los 5 desvios de tool_uses de REQ-20260825
(1.02x-1.84x) y el 1.26x/1.50x del test-engineer de REQ-20260822 fueron
TODOS friccion legitima de esta clase. Al lanzar esas fases, declara el cap
de tool_uses multiplicado x1.5 EN EL PROMPT. No se recorta la practica
(es la que convirtio "este test puede fallar" en hecho): se presupuesta,
para que un WARN vuelva a significar anomalia y no rutina.

**El techo de turnos del harness no se presupuesta, se respeta.** Con
`maxTurns` ≈ 100, una fase de test con >12 criterios + mutaciones, o una story de
>~15 archivos / >2 capas, se corta SIN reporte (editorial F-16/LL-022; guai
FD-15: una story necesitó 3 runs). Se parte el lote antes de lanzar, el reporte
se escribe incremental desde el primer turno y a ~80 tool calls el agente corre
su gate y devuelve con la lista de lo pendiente. Detalle en `kuraka-policies.md`
→ "Tool use limits per agent".

---

## Rule T13 — El costo de un ciclo es `150K x invocaciones`, no `tokens x prosa`

Medicion sobre 100 ciclos archivados (160M de tokens): la mediana por
invocacion de subagente es de 120-180K **independientemente de la fase**,
porque el piso lo pone el arranque del agente (definicion + reglas + contexto),
no su trabajo. De ahi salen tres consecuencias operativas:

1. **Acortar definiciones de agentes casi no mueve la aguja.** Reescribir un
   `agents/*.md` para que sea mas corto ahorra unos pocos K de un run de 150K.
   Optimiza el NUMERO de runs antes que su contenido.
2. **El modo se elige contando invocaciones.** Normal = mediana 13 runs =
   1.81M. Reduced = 6 runs = 601K. Lite = 3 runs = ~450K. Declara el conteo
   previsto al usuario junto con el pipeline (ver `kuraka.md` §Initial
   decision) — ese numero ES el presupuesto del ciclo.
3. **Una fase que no puede justificar su disparador no se corre.** Cada fase
   opcional cuesta ~150K; el disparador (schema, contrato, auth, flujo, infra)
   es lo que la paga. Sin disparador, la fase se omite CON registro en el
   Workflow Status, nunca en silencio.

**Lo que NO se recorta por presupuesto**: 3.9 (determinista, ~0 tokens), 6.8
(smoke) y 7 (mediana 47K, la fase mas barata de la suite). Tampoco el tier de
modelo de los gates de juicio: un ciclo mal cerrado cuesta 1.8M de retrabajo,
que es mas que todo lo que ahorraria degradarlos.

## Rule T1.1(c-bis) — El «FULL consumer set» cubre tambien los simbolos que se CITAN como el mecanismo (M-3, RETRO-REQ-20260909; aplicado 2026-09-14)

T1.1(c) exige el conjunto completo de consumidores de todo simbolo que el REQ dice
**reemplazar, renombrar o borrar**. Se extiende a todo simbolo que el REQ **CITAN como el
mecanismo** de una decision — el guard que reescribe un destino, el helper que resuelve un
id, la constante que fija un limite — aunque el REQ no lo toque.

Razon: si el mecanismo tiene mas consumidores de los que el REQ cree, la decision que se
apoya en el es correcta para uno y falsa para los demas. Evidencia REQ-20260914: el
digest clasifico `push('/cliente')` como «discutible» sin abrir
`router/index.ts:456-459`, el guard que lo reescribe a `cliente-datos` — o sea que ese
«Atras» REINICIABA el alta. El mecanismo no estaba en alcance; decidia el alcance.

## Rule T12.1 — El `tool_uses_cap` se DECLARA en el prompt y se ESCRIBE en la telemetria (P-6, RETRO-REQ-20260908/0909; aplicado 2026-09-14 tras 2 ciclos)

T12 dice que ciertas fases merecen un cap de tool-uses x1,5. No se aplicaba porque no
existia el campo donde escribirlo, asi que `budget_ok` solo miraba tokens y 12 de 28 runs
de un ciclo quedaron en WARN por friccion legitima — un WARN que significa «rutina» deja
de significar «anomalia».

Contrato: el prompt de cada fase declara `tool_uses_cap: <n>` y la entrada de telemetria
de ese run lo COPIA junto a `tool_uses`. `budget_ok` se calcula contra AMBOS techos. Un
run sin `tool_uses_cap` en su entrada es telemetria incompleta y se declara como deuda en
el §0 del RETRO.
