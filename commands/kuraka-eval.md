---
description: "VAULT-ONLY. Evalúa las definiciones de agentes del framework ejecutándolas en sandbox contra un proyecto real: (1) cruza projects/*/overrides/ para priorizar qué agente evaluar y corroborar gaps, (2) audita el contrato productor→consumidor de documentación, (3) ejecuta el agente con outputs al scratchpad (el repo objetivo es solo-lectura), (4) verifica sus afirmaciones contra el código real por muestreo, (5) recolecta gaps de definición y los propone como mejoras (aprobación por ítem, nunca auto-aplicar), (6) persiste la corrida en evals/runs/ y la compara contra el baseline anterior del mismo agente+target (gaps CERRADOS/REAPARECIDOS/PERSISTENTES/NUEVOS → veredicto MEJORÓ/IGUAL/EMPEORÓ). Complemento de /kuraka-harvest: harvest detecta los patrones de fallo comunes entre proyectos y parcha el central; eval mide si el parche dio mejor resultado por agente/fase."
---

# Task: Kuraka agent-definition eval (sandbox + verificación + baseline)

Reproduce el ciclo de mejora ejecutado el 2026-08-01/05 (validación de `amauta`
contra kuraka-control) para CUALQUIER agente del framework. Corre SIEMPRE desde
el vault (`/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka`).

**Rol de cada loop** (intención declarada por el usuario, 2026-08-05):
- `/kuraka-harvest` detecta los **patrones de fallo comunes a la mayoría de
  proyectos** (vía `projects/*/overrides/` + retros) → se parcha el repo
  central → los proyectos reciben el fix en su próximo `kuraka update` /
  `kuraka mount`.
- `/kuraka-eval` **mide si el ajuste aplicado dio mejor resultado**, por
  agente/fase que estaba mal: cada corrida persiste un baseline y la
  siguiente se compara contra él (gaps cerrados / reaparecidos / nuevos).

**Argumentos** (todos opcionales): `[agente] [--target <path|slug>]`
- `agente`: qué definición evaluar. Default: `amauta` (onboarding brownfield).
  Soporta también `inti`/`arki` (greenfield — usa un dir temporal vacío como
  target) y agentes de ciclo (`po-analyst`, `story-refiner`, …) dándoles un
  requirement sintético.
- `--target`: path a un repo real, o slug del registro `projects/`. Default:
  elegir del registro un proyecto cuyo stack ejercite al agente (brownfield
  con backend+frontend es lo ideal; `kuraka-control` fue el caso probado).

## Reglas duras (no negociables)

1. **El repo objetivo es SOLO LECTURA.** Todos los artefactos que el agente
   escribiría en el proyecto van a `<scratchpad>/kuraka-eval-<agente>-<slug>/output/`
   tratado como raíz del proyecto.
2. **El subagente evaluado NUNCA escribe en el vault** (rules/16). Solo el
   orquestador de este comando edita el vault, y solo tras aprobación por ítem.
3. **Simular estado pre-onboarding** cuando se evalúa onboarding: el subagente
   debe IGNORAR `.claude/`, `kuraka.config.yaml` y `kuraka.lock` existentes del
   target — su fuente de verdad es el código. Si no, solo copia la capa vigente
   y el eval no mide nada.
4. **Mejoras a agentes = propuesta en tabla + aprobación por ítem.** Igual que
   `/kuraka-harvest`: NUNCA auto-aplicar cambios de comportamiento.

## Fase 1 — Auditoría de contrato + cruce con el store de overrides

**1a. Cruce con `projects/*/overrides/`** (señal de priorización y contexto):

- Contar overrides por agente/skill a través de TODOS los proyectos del store
  (leer los `MANIFEST.md`; ignorar los clasificados como stale). Producir el
  ranking: un mismo agente overrideado en **≥2 proyectos** = definición débil
  confirmada por la práctica → candidato prioritario del eval.
- Si el usuario no fijó `[agente]`, proponer el objetivo desde este ranking.
- Guardar el ranking para la Fase 4: un gap del eval que COINCIDE con un
  override existente en varios proyectos no es hipótesis — es un candidato a
  core ya validado en producción; anotarlo como `confirmed-by-overrides` y
  señalarlo a `/kuraka-harvest` (la integración formal sigue siendo suya).
- Este cruce NO reemplaza al harvest: aquí los overrides son evidencia para
  dirigir y corroborar el eval, no se integran desde este comando.

**1b. Auditoría de contrato** — mapear productor→consumidor de documentación:

- Para cada documento que los agentes de onboarding generan (`amauta` Step 5/6,
  `arki` Step 5/6, skill `seed-project-conventions`), grep en `agents/`,
  `agents/contexts/`, `skills/`, `commands/`: ¿qué agente del ciclo lo CARGA?
- Reportar: **docs write-only** (se generan, nadie los lee), **docs "if
  present" que nadie siembra** (se leen, nadie los genera), y **asimetrías
  greenfield vs brownfield** (arki produce X, amauta no, o viceversa).
- Verificar que la superficie de `seed-project-conventions.md` siga igual a lo
  que los Context de los agentes de ciclo esperan (ese contrato es lo que las
  fases 2026-08 cerraron; una regresión aquí es hallazgo BLOCKER).

## Fase 2 — Ejecución en sandbox

1. Preparación: `mkdir <scratchpad>/kuraka-eval-.../output/`; para brownfield,
   generar `python3 kuraka-inspect.py <target> > .../inspect-report.json`.
2. Lanzar UN subagente (general-purpose, modelo = tier del agente evaluado en
   `MODEL-ROUTING.yaml`) con un prompt que incluya, en este orden:
   - Los archivos-definición que DEBE leer y seguir paso a paso: el
     `agents/<agente>.md` del vault + las skills que ese agente invoca +
     stack profiles relevantes + `config-schema.yaml` si genera config.
   - Los inputs del rol (inspect report, requirement sintético, design files
     detectados — lo que el flujo real le pasaría).
   - Las reglas duras 1–3 de arriba, literales.
   - El contrato de retorno: (a) lista completa de archivos generados,
     (b) el reporte que la definición exige (Step 7 / summary), y
     (c) una sección **"GAPS DE LA DEFINICIÓN"** — todo punto donde la
     definición fue ambigua, contradictoria o le faltó guía al ejecutar.
     Esta sección es el producto principal del eval.

## Fase 3 — Verificación adversarial (no confiar en el reporte)

Elegir ≥4 afirmaciones no triviales del output y confirmarlas o refutarlas
contra el código/artefactos reales del target (grep/read directo):

- Convenciones extraídas (¿el envelope/naming/patrón citado existe en el
  `file:line` citado? ¿la estadística "N/N archivos" se sostiene?).
- Reglas de oro: ¿usó `<TODO>` en vez de inventar? ¿evidencia `file:line` en
  cada regla? ¿impuso patrones de otro proyecto? (cualquier invención = hallazgo
  crítico del eval, aunque el resto esté bien).
- Si el target ya tiene convenciones escritas a mano, comparar: la convergencia
  independiente extracción↔documento-humano es la mejor señal de fidelidad.
- Contrastar contra el schema: ¿el `kuraka.config.yaml` generado valida contra
  `kuraka-artifacts/config-schema.json`? (usar `jsonschema` si está disponible).

## Fase 4 — Triage y propuestas

Clasificar cada gap reportado + cada fallo de verificación:

| Clase | Destino |
|---|---|
| definition-bug (la definición manda algo imposible/contradictorio) | fix en `agents/<x>.md` o la skill |
| schema-bug (el config-schema no puede expresar la realidad) | fix en `config-schema.{yaml,json}` — cuidar retrocompatibilidad y re-validar configs reales |
| missing-guidance (caso real sin instrucción) | añadir guía al agente/skill |
| false-alarm (el recurso existía; el sandbox no lo tenía) | descartar, anotar |

Presentar tabla de propuestas → aprobación POR ÍTEM → aplicar solo lo aprobado
→ registrar en `SUITE-CHANGELOG.md` bajo la sección **"Sin publicar"** (el bump
de versión sigue siendo exclusivo de `/kuraka-harvest`).

## Fase 5 — Registro del baseline y comparación entre corridas

Cada corrida se PERSISTE en el vault (no solo en el scratchpad) para poder
medir si un ajuste mejoró al agente:

1. **Escribir** `evals/runs/EVAL-<agente>-<slug>-<YYYYMMDD>.md` con:
   - Frontmatter: `agent`, `target`, `date`, `suite_version` (leer
     `SUITE-VERSION`) — así los resultados se agrupan por versión de suite,
     igual que los retros.
   - Tabla de **spot-checks** (afirmación → CONFIRMADA/REFUTADA + evidencia).
   - Lista de **gaps con id estable** (slug corto por gap, p.ej.
     `domain-model-loc-limit`, `token-drift-no-diff`) + clase + destino.
   - Fixes aplicados en esta corrida (si hubo Fase 4).
2. **Comparar contra el baseline**: buscar el `EVAL-<agente>-<slug>-*.md`
   anterior más reciente. Clasificar cada gap por id:
   - **CERRADO** — estaba antes, ya no aparece (el ajuste funcionó).
   - **REAPARECIDO** — se había cerrado y volvió (regresión: hallazgo crítico).
   - **PERSISTENTE** — sigue igual (el ajuste no lo cubrió o no se aplicó).
   - **NUEVO** — no estaba antes.
   Y emitir el **veredicto por agente/fase evaluada**:
   `MEJORÓ` (cerrados > nuevos+reaparecidos) / `IGUAL` / `EMPEORÓ`.
   Sin corrida previa → esta corrida ES el baseline; decirlo explícitamente.
3. Reporte final al usuario: ranking de overrides (1a) + contrato (1b) +
   fidelidad (fase 3) + gaps aplicados/descartados (fase 4) + **comparativa
   vs baseline y veredicto** (este punto es la razón de ser del comando).
4. Dejar los artefactos del sandbox en el scratchpad (evidencia de la corrida)
   y sugerir el siguiente paso: si hubo fixes, re-run tras aplicarlos; si hubo
   gaps `confirmed-by-overrides`, correr `/kuraka-harvest`.

## Historial

- 2026-08-01/05 — primer eval (manual, esta misma mecánica): `amauta` vs
  `kuraka-control`. Resultado: superficie completa generada, 5 spot-checks
  confirmados (envelope, imports `.js`, zustand sin uso, listen sin host,
  token-drift diseño↔CSS), 14 gaps → 6 fixes en amauta/skill, 6 en
  config-schema, 1 falsa alarma (`verify-output` sí existe), quedando la
  ambigüedad N (criterio de archivos de dominio) como observación.
