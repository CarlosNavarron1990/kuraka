---
agent: amauta
target: kuraka-control
target_path: /Users/xmn/Desarrollos/kuraka-control
date: 2026-08-01
suite_version: 1.1.0
baseline: true            # primera corrida de este par agente+target
---

# EVAL — amauta vs kuraka-control (baseline)

Corrida manual que originó `/kuraka-eval` (sesión 2026-08-01→05). Sandbox:
outputs a scratchpad, repo solo-lectura, estado pre-onboarding simulado.
30 artefactos generados; superficie completa de `seed-project-conventions`
+ `docs/arquitectura/` producida. Confianza del agente: HIGH.

## Spot-checks (Fase 3)

| Afirmación del agente | Veredicto | Evidencia |
|---|---|---|
| Envelope de error `{error:{code,message,detail}}` | CONFIRMADA | `backend/src/routes/triage.ts:279` + zod contract; converge con `api-contract.md` humano |
| Imports relativos siempre con `.js` | CONFIRMADA | 75/75 en backend |
| `zustand` declarado sin uso real | CONFIRMADA | solo strings en fixtures; `stores/` solo README |
| Sin auth y `app.listen` sin host | CONFIRMADA | `backend/src/index.ts` (bind a todas las interfaces) |
| Token-drift diseño↔CSS (11/13 + 5 tokens inexistentes) | CONFIRMADA | diseño `accent:#e6b53f` vs CSS `--accent:#d4af37` |

Reglas de oro: cumplidas (35 `<TODO>`, evidencia `file:line`, sin patrones
ajenos, corrigió 3 falsos del inspect: zustand/vitest-backend/prettier).

## Gaps (ids estables)

| id | Clase | Destino | Estado tras esta corrida |
|---|---|---|---|
| `domain-model-loc-limit` | definition-bug | amauta Step 6 | FIX aplicado (split permitido) |
| `tests-root-single-dir` | schema-bug | config-schema | FIX aplicado (`extra_tests_roots`) |
| `monorepo-third-root` | schema-bug | config-schema | FIX aplicado (`shared_roots`) |
| `null-syntax-python-bias` | schema-bug | config-schema | FIX aplicado (enum ampliado) |
| `enums-for-states-boolean` | schema-bug | config-schema | FIX aplicado (política string) |
| `workflow-fields-no-source` | missing-guidance | amauta Step 4 + schema | FIX aplicado (defaults, no TODO en enums) |
| `design-file-no-extension` | missing-guidance | skill §5 | FIX aplicado (detección por contenido) |
| `frames-not-built` | missing-guidance | skill §5 | FIX aplicado (`<TODO (not built)>`) |
| `token-drift-no-diff` | missing-guidance | skill §5 | FIX aplicado (diff obligatorio) |
| `sampling-assumes-db` | missing-guidance | amauta Step 2 | ABIERTO (sin fix; adaptación quedó a criterio) |
| `profile-divergence-unreported` | missing-guidance | amauta Step 1 | FIX aplicado (reporte de divergencias) |
| `verify-output-missing` | false-alarm | — | DESCARTADO (la skill existe; el sandbox no la tenía) |
| `lessons-registry-duplicate` | definition-bug | amauta Step 5 | FIX aplicado (buscar registro preexistente) |
| `domain-convention-criteria` | missing-guidance | skill §8 | ABIERTO (criterio de qué archivos de dominio crear sigue siendo juicio del agente) |

Extra encontrado en Fase 3 (no reportado por el agente):
`tenant-column-empty-invalid` (schema-bug) — FIX aplicado (vacío/null válidos
con `multi_tenant: false`).

## Comparativa vs baseline

Sin corrida previa — **esta corrida es el baseline**. Próximo run esperado:
verificar que los 12 FIX no reaparecen y que `sampling-assumes-db` +
`domain-convention-criteria` siguen como únicos PERSISTENTES (o se cierran).
