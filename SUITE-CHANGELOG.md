# SUITE-CHANGELOG — versionado de la suite Kuraka

Registro de versiones del framework (agentes + skills + rules + commands + scripts).
La versión vigente vive en `SUITE-VERSION` (una línea). Cada `mount` la estampa en
`.claude/.kuraka-mount-manifest.json` (`suite_version`) del proyecto consumidor, y
`kuraka-backup.py` la copia al `meta.yaml` de cada ciclo archivado — así cada RETRO
queda atribuido a la versión de suite con la que corrió, y se puede comparar
retrabajo/ajustes entre versiones.

## Esquema de versión (semver adaptado)

- **MAJOR** — cambio que rompe contrato con proyectos montados (esquema de
  `kuraka.config.yaml`, mapa de fases, formato de checkpoint/telemetría).
- **MINOR** — integración de un harvest: agentes nuevos, checks nuevos, cambios
  de comportamiento en agentes/skills. Es el bump típico de `/kuraka-harvest`.
- **PATCH** — correcciones sin cambio de comportamiento (typos, bugs de scripts).

## Cómo se evalúa una versión

`/kuraka-harvest` llena la sección **Resultados** de cada versión leyendo
`projects/*/cycles/*/meta.yaml` (agrupa por `suite_version`): nº de ciclos,
verdicts, señales de retrabajo en los RETRO (BLOCKERs tardíos, re-ejecuciones,
overrides nuevos que corrigen al framework). Menos retrabajo con la versión N+1
que con la N = la integración funcionó.

---

## Sin publicar (pendiente de bump por `/kuraka-harvest`)

Cambios 2026-08-01→05 — paridad de onboarding + cableado de especificaciones al
ciclo. Origen: análisis de contrato productor→consumidor + **primer agent-eval**
(`amauta` ejecutado en sandbox contra `kuraka-control`, 5 spot-checks
confirmados, 14 gaps de definición recolectados). Mecánica reproducible en el
nuevo comando `/kuraka-eval`.

### Añadido
- **`skills/seed-project-conventions.md`** — spec canónica compartida del
  sembrado de `.claude/project/conventions/` + glossary, con modo greenfield
  (`arki`, fuente discovery) y brownfield (`amauta`, fuente código sampleado).
  Brownfield ahora produce la MISMA superficie que greenfield: `api-design`,
  `query-and-repository`, `frontend-branding` (con diff obligatorio de tokens
  diseño↔código y registro de design files aun sin extensión),
  `test-fixtures`, dominio + glossary con relaciones. Registrada en el array
  `SKILLS=()` de `sync-obsidian.sh`.
- **Cableado de especificaciones al ciclo** — `po-analyst`, `story-refiner` y
  `architect-reviewer` (agente + `contexts/*-rules.md` + `analyze-requirement`)
  cargan `docs/arquitectura/domain-model.md`, `flujos/` y las decisiones
  resueltas de discovery cuando existen; reabrir una decisión ✅ o contradecir
  el domain model congelado = BLOCKER. Antes esos docs eran write-only.
- **`amauta` genera `docs/arquitectura/` real** — `domain-model.md` (entidades/
  estados extraídos, split permitido si no cabe en 200 LOC),
  `integrations-overview.md`, `security-model.md`; detecta lessons-learned
  preexistentes (no duplica registro); reporta divergencias perfil↔proyecto
  como señal para harvest; TODO solo en campos de texto libre (enums/workflow
  conservan el default del framework).
- **`kuraka-wizard`** regla C pasa los design files detectados a `amauta`.
- **`commands/kuraka-eval.md`** — el eval-loop reproducible (symlink en
  `.claude/commands/`, en `EXPORT_SKIP`): cruza `projects/*/overrides/` como
  señal de priorización/corroboración, ejecuta en sandbox, verifica claims,
  y **persiste cada corrida en `evals/runs/`** comparando contra el baseline
  anterior (CERRADO/REAPARECIDO/PERSISTENTE/NUEVO → MEJORÓ/IGUAL/EMPEORÓ).
  Baseline inicial registrado: `EVAL-amauta-kuraka-control-20260801.md`
  (12 fixes aplicados, 2 gaps abiertos, 1 falsa alarma).

### Corregido
- **`config-schema.{yaml,json}`** (retrocompatible, sigue `schema_version: 1`):
  `null_syntax` amplia el enum a TS/Rust (`T | null` ya existía en dbcanvas y
  NO validaba); `enums_for_states` acepta política
  `always|own-vocabulary-only|never` (booleans = alias legacy);
  `tenant_column_name` admite vacío/null cuando `multi_tenant: false` (la
  config real de kuraka-control no validaba); nuevos opcionales
  `paths.extra_tests_roots` (monorepo/co-located) y `paths.shared_roots`
  (seam de contratos; cambios ahí = cambio de contrato).

### Corregido — Ola 0 de integración Claude Code (2026-08-22)

Origen: auditoría `INFORME-AGENTES-CLAUDE-CODE-2026-08.md` + `ROADMAP-CLAUDE-10.md`.

- **`model: fable` verificado empíricamente** — un subagente lanzado con el alias
  `fable` corrió sobre `claude-fable-5` (evidencia: system prompt del run,
  2026-08-22). El tier frontier de `MODEL-ROUTING.yaml` queda confirmado.
  Residual: confirmar una vez en sesión de consumidor que un agente registrado
  por frontmatter resuelve igual.
- **`kuraka-policies.md` §Model Routing** — tabla obsoleta (pre-Fable, con
  instrucción de editar frontmatter a mano) sustituida por referencia a
  `MODEL-ROUTING.yaml` + `kuraka-apply-models.py` como única vía.
- **`kuraka-policies.md` §Timeout** — eliminado el timeout fijo de 10 min, que
  contradecía el protocolo de liveness (REQ-20260801: agente sano de 7 h). La
  salud se juzga solo por liveness (polls de archivos), nunca por duración.
- **Conteos unificados** — `commands/kuraka.md` decía "11-phase" (kuraka.md
  define 8 + subfases); CLAUDE.md decía 16 subagentes (hay 23: 13 pipeline +
  3 entrada + 7 on-demand).
- **`skills/kuraka.md`** — nueva sección "On-demand agents (outside the phase
  map)": tabla de invocación de los 7 agentes ayllu con su trigger y qué fase
  NO sustituyen. Antes no existía criterio central de invocación.
- **`agents/contexts/README.md`** — regenerado: separa reglas de framework
  (16–19, siempre presentes) de reglas de proyecto (01–15, solo sie_v2 — con
  instrucción de `ls` antes de mapear, para no buscar archivos inexistentes en
  otros consumidores). Estaba fechado 2026-04-17.
- **Descriptions de 10 agentes recortadas a estilo trigger** (provider-contract-
  validator 834→~250 chars, sentry-resolver, deploy-diagnostician, inti,
  pentest-auditor, checkmarx-remediation, arki, migration-deployability,
  amauta, jira-ticket-sync): la description es el criterio de enrutamiento que
  Claude Code carga en TODA sesión del consumidor (~2K tokens fijos, −60 %);
  el detalle (política read-only, entregables, codename quechua) sigue en el
  body de cada agente. De paso se retiró la mención hardcodeada a
  `guai-platform-backend` en sentry-resolver (project-specific en agente de
  framework).

### Añadido — Ola 1 de integración Claude (capacidades gobernadas, 2026-08-22)

Origen: `ROADMAP-CLAUDE-10.md` Ola 1 (dimensiones D3 least-privilege + D9
aislamiento multi-plataforma). Regla de convivencia: **el vault es el superset
nativo de Claude; las plataformas no-Claude SUSTRAEN en el render** — Antigravity/
Codex/Cursor no reciben ninguna clave que no entiendan, y el render Claude sigue
siendo copia byte-idéntica del vault (requisito del subsistema de overrides).

- **`AGENT-HARNESS.yaml` + `kuraka-apply-harness.py`** — fuente única de las
  capacidades de harness Claude por agente (`tools` / `disallowedTools` /
  `maxTurns`; `skills` y `memory` declarados pero con emisión apagada hasta las
  Olas 3/4). Mismo patrón de gobernanza que MODEL-ROUTING: nunca editar esas
  claves a mano; `--check` reporta drift (exit 1). Aplicado a los 23 agentes:
  revisores puros (`code-reviewer`, `security-reviewer`, `migration-reviewer`,
  `migration-deployability`) con `disallowedTools: Write, Edit, NotebookEdit`
  (aislamiento de rol por harness, no por prosa); `deployment-verifier` con
  allowlist `Read, Grep, Glob, Bash`; `maxTurns` como tope duro anti-runaway a
  ~2× del cap blando de policies (el cap blando 1× sigue siendo del orquestador).
- **`kuraka_common.strip_claude_frontmatter` + `CLAUDE_ONLY_FRONTMATTER_KEYS`** —
  sustracción de claves Claude-only en `copy_file` para todo target ≠ claude
  (Antigravity y Codex conservan intactas sus reescrituras de rutas; Cursor, que
  copiaba verbatim, ahora también sustrae). Verificado no-op sobre los 87
  archivos previos del vault.
- **`tests-vault/test_claude_integration.py`** (vault-only, no se monta): 11
  tests que fijan el contrato — render claude verbatim, renders no-Claude sin
  fugas de claves y con sus proyecciones de rutas intactas, biyección y no-drift
  mapa↔agentes, revisores write-denied.
- **`validate-kuraka.sh`** — self-checks del vault: corre ambos `--check`
  (models + harness) antes de validar el mount del consumidor.

### Corregido — Ola 1 (2026-08-22)

- **`kuraka-modes.md` L3 (Lite)** — el `code-reviewer` ya no "escribe tests si
  faltan": lista los tests faltantes como findings y el orquestador enruta un
  micro-pase al agente L2. Coherente con su denegación de Write/Edit y con el
  aislamiento de rol (un revisor que escribe los tests que luego aprueba se
  auto-audita). El RETRO corto de L3 se devuelve como contenido del informe y lo
  persiste el orquestador.

### Añadido — Ola 2 de integración Claude (hooks + adelgazamiento de prosa, 2026-08-22)

Origen: `ROADMAP-CLAUDE-10.md` Ola 2 (D2 enforcement por harness + D4 telemetría
determinista). Los cuatro fallos de disciplina más documentados del framework
pasan de prosa-que-el-modelo-debe-obedecer a enforcement determinista a 0 tokens.

- **`hooks/` (Claude-only)** — 4 hooks Python autocontenidos, fail-open, inertes
  fuera de un proyecto Kuraka (requieren `kuraka.config.yaml`):
  `telemetry_append.py` (PostToolUse/Task → apende cada run a
  `agent-telemetry/HOOK-LOG.jsonl`; la completitud deja de depender de la
  memoria del orquestador — regresión de 3 ciclos, 12/31 runs perdidos),
  `gate_integrity.py` (PreToolUse/Bash → bloquea pipes sobre
  `test_cmd`/`lint_cmd`/`typecheck_cmd`; el falso verde T7 se vuelve imposible;
  escape aprobado: `KURAKA_GATE_PIPE_OK`), `orchestrator_guard.py`
  (PreToolUse/Write|Edit → la sesión principal no escribe bajo los code roots;
  excepción one-shot `touch .claude/hooks/ALLOW-ORCH-WRITE`), y
  `output_validate.py` (SubagentStop → contrato universal Confidence/Verdict,
  con guarda anti-bucle; reemplaza la relectura terminal de las 207 líneas de
  `output-schemas.md` por agente y por fase).
- **Cableado**: `kuraka-mount.py` monta `hooks/` SOLO para el target claude y
  hace merge no destructivo e idempotente de `hooks/settings-hooks.json` en el
  `.claude/settings.json` del consumidor (entradas kuraka reemplazadas, hooks
  del usuario preservados, settings corrupto nunca se pisa).
- **Bloques discipline (`discipline/`)**: donde un hook reemplaza prosa, el
  vault deja nota-slim + marcador `<!-- kuraka:discipline:<n> -->`; los renders
  no-Claude re-expanden el marcador a la prosa manual completa
  (`_expand_discipline`) — Antigravity/Cursor/Codex no pierden ninguna regla.
  Aplicado en: `kuraka.md` §Orchestrator constraint (protocolo de violación),
  `kuraka-policies.md` §Gate integrity y §Token Telemetry (el orquestador ahora
  ENRIQUECE y concilia contra HOOK-LOG.jsonl en Fase 7), sección Output
  Validation de los 13 agentes de pipeline (+ reglas inline de code-reviewer y
  migration-reviewer), y nota de plataforma en `skills/verify-output.md`.
- **Tests**: `tests-vault/test_hooks.py` — 11 tests nuevos (22 totales en
  verde): hooks ejercitados como subprocesos reales (bloqueos, escapes one-shot,
  guarda anti-bucle, parseo de usage), expansión discipline solo-no-Claude, y
  merge de settings preservando hooks del usuario.

### Añadido — Ola 3 de integración Claude (skills nativas + regla siempre-activa, 2026-08-22)

Origen: `ROADMAP-CLAUDE-10.md` Ola 3 (D1 formato nativo de skills + D5). Claude
Code solo registra skills como directorios `skills/<n>/SKILL.md`; los `.md`
planos que montábamos NO se registraban (funcionaban solo como lecturas por ruta).

- **`sync_claude_skills()`** en el mount (target claude): cada `skills/<n>.md`
  del vault aterriza como `.claude/skills/<n>/SKILL.md` (forma registrada) Y
  como el flat `.claude/skills/<n>.md` (compat de transición — las referencias
  por ruta de los agentes siguen resolviendo; el flat se retira una versión de
  suite después de migrar las referencias). Ambas copias byte-idénticas al vault.
- **Overrides**: `_skill_dir_canonical` canonicaliza `skills/<n>/SKILL.md` al
  baseline `skills/<n>.md` (sin esto, cada SKILL.md era un override fantasma);
  un SKILL.md editado se detecta como override real; `restore_overrides` ahora
  espeja SKILL.md → flat (`_mirror_claude_skill_copies`, SKILL.md manda).
- **Clasificación de invocabilidad** (frontmatter del vault, sustraído para
  no-Claude — `disable-model-invocation`/`user-invocable`/`context` añadidos a
  `CLAUDE_ONLY_FRONTMATTER_KEYS`): 19 skills internas de fase + verify-output y
  el núcleo kuraka/kuraka-modes/kuraka-policies = no invocables ni auto-invocables
  (evita colisión de `/kuraka` skill-vs-command y limpia el menú `/`);
  compact-context/detect-patterns/gap-analysis = `context: fork` (contexto
  limpio); facilitate-discovery/diagnose-deploy/seed-project-conventions siguen
  invocables.
- **Precarga `skills:` activada** (`emit.skills: true` en AGENT-HARNESS):
  14 agentes precargan sus skills de fase — se elimina el paso "lee tu skill".
- **Regla 19 siempre activa**: `ensure_claude_md_block` — el mount escribe un
  bloque gestionado (`<!-- kuraka:managed:begin/end -->`) en el CLAUDE.md del
  consumidor con `@.claude/rules/19-evidence.md`; idempotente, contenido del
  usuario intacto. Retirado el `alwaysApply: true` (Cursor-ism inerte) de las
  reglas 17/19.
- **Tests**: +7 vault-only (29 en verde) — doble copia byte-idéntica, no-fantasma
  y detección de override en SKILL.md, espejo en restore, strip de claves de
  skill para no-Claude, bloque CLAUDE.md idempotente. El harness estructural
  montado (`tests/kuraka/test_structure.py`) gana 3 checks: SKILL.md por skill,
  no-colisión del núcleo kuraka con slash commands, y revisores write-denied.

**Residuales de transición** (retirar el flat en la próxima versión de suite):
migrar las referencias `.claude/skills/<n>.md` de agentes/commands a
`<n>/SKILL.md`, y actualizar `sync-obsidian.sh` al layout de directorios (hoy
sigue funcionando gracias a las copias flat). Las claves informativas `agent:`/
`phase:` en frontmatter de skills se conservan (Claude las ignora).

### Añadido — Ola 4 de integración Claude (memoria, supervisión, higiene de prompts, 2026-08-22)

Origen: `ROADMAP-CLAUDE-10.md` Ola 4 (D6/D7/D8). Cierre del roadmap ejecutable
en vault; re-medición del scorecard: ~3,2 → **~9,1** (décimas restantes = gates
de campo en el próximo ciclo real).

- **`memory: project` activo** (`emit.memory: true`): `final-auditor` mantiene
  su **patch-ledger** en memoria de agente (pendientes + contadores de OPEN
  FRAMEWORK DEBT; el Prior-Retro Check parte de conciliar el ledger, no de
  releer el RETRO anterior); `pattern-detector` mantiene un **pattern-index**
  incremental con watermark (procesa solo retros nuevos). Fallback manual
  documentado para plataformas sin memoria.
- **`hooks/liveness_watch.sh`**: watcher streaming de mtimes sobre las rutas
  autorizadas del implementador (Monitor / Bash background) — reemplaza el
  polling manual; la política de liveness queda como REGLA DE DECISIÓN y
  recomienda lanzar implementadores L como subagente background. Decisión:
  `background:` NO se fija en frontmatter (elección por-story del orquestador).
- **Digest protocol en 13/13 agentes de pipeline**: si el prompt trae
  `## Context digest`, los pasos de carga config/stack-profile se consideran
  ejecutados — cierra el conflicto "carga tu contexto" vs T1 "no releas"
  (fases 2/2.5/3 corrían 1,9× re-derivando).
- **`agents/contexts/EVIDENCE.md`**: registro por incidente (18 entradas:
  DD-1031, REQ-20260611/0703/0801/0804, LL-009/014/016/017/020, S5c, guai,
  clinica-dental, facturacion, adela/dbcanvas/sie-v2…) — los prompts citan por
  ID; la narrativa vive aquí. Convención de compactación: archivo tocado =
  narrativa movida.
- **`e2e-tester` 282→209 líneas** (−26% sobre haiku): playbook CRUD completo
  movido a `contexts/e2e-tester-rules.md` (el agente conserva el puntero
  obligatorio); reglas 8–14 comprimidas a su núcleo accionable con provenance.
- **`hooks/review_mechanics.sh`**: los greps deterministas de los revisores
  (secretos, console.log/print, tokens de diseño, double-submit, namespace
  type-imports, imports-en-funciones) corren como script del orquestador a ~0
  tokens; `code-reviewer`/`security-reviewer` ADJUDICAN el resultado del digest
  (falso positivo vs finding + severidad) en vez de ejecutar greps con un
  modelo frontier. Grep POSIX (`[[:space:]]`) — compatible macOS/Linux.
- **Tests**: +6 vault-only (35 en verde), incluido smoke real de
  review_mechanics con plantas de secreto/console.log detectadas.

### Añadido — `kuraka-mount.py --update` (framework-only refresh, 2026-08-22)

- **Modo `--update` / `-u` / `update`** en el mount: actualiza SOLO la capa de
  framework (agents con capacidades de harness, skills `SKILL.md` + flat,
  commands, rules, hooks + merge en settings.json, bloque CLAUDE.md, contexts,
  stack-profiles, templates, tests/kuraka), re-aplica overrides, y por diseño
  NO toca historial ni contenido del proyecto: `docs/process/**` (REQ, retros,
  checkpoints, telemetría, lessons-learned), `.claude/project/`,
  `kuraka.config.yaml`, ni el registro del vault (sale antes de auto-register/
  restore/seed/adopción). No interactivo. Superficies: `mount-kuraka --update`,
  alias `kuraka-update` (dotfiles) y el comando `/kuraka-update` reescrito para
  usarlo.
- **Fix de clobber latente en el mount completo**: los seeds de
  `docs/process/lessons-learned.md` y `agent-telemetry/DASHBOARD.md` se
  copiaban SIN guarda en cada re-mount (`copy_file` no compara mtimes),
  pisando el contenido acumulado del proyecto con la plantilla del vault.
  Ahora son seed **solo-si-falta** en todos los modos.
- **Consciente de plataforma** (corrección sobre la primera versión del modo,
  mismo día): `--update` sin `--target` **auto-detecta** la(s) plataforma(s) ya
  montadas en el proyecto (`.claude`/`.agents`/`.codex`/`.cursor` con `agents/`)
  y refresca CADA una con su propio render — el riesgo de plantar material
  solo-Claude en un proyecto Antigravity/Codex/Cursor (o al revés) queda
  cerrado. Con `--target` explícito, verifica que esa plataforma esté montada y
  se NIEGA a estrenarla (eso es del mount completo). Proyecto multi-plataforma →
  fan-out secuencial por plataforma. `/kuraka-update` (comando) detecta la raíz
  por cualquier plataforma, no solo `.claude`.
- **Tests e2e** (`tests-vault/test_update_mode.py`, 39 en verde): historial
  byte-idéntico + framework esencial en claude; detección antigravity con
  render limpio (sin claves Claude-only, sin hooks, sin `.claude/agents`);
  rechazo de plataforma no montada y de proyecto sin montar; fan-out dual
  claude+antigravity con el render correcto en cada lado; cero efectos en el
  registry.

### Corregido — `/kuraka` quedaba inaccesible tras `kuraka-update` (2026-08-22)

- **Síntoma**: después de un `kuraka-update`, invocar `/kuraka` en el proyecto
  respondía *"This skill can only be invoked by Claude, not directly by users"*.
- **Causa**: la Ola 3 empezó a montar la forma registrada
  `.claude/skills/<n>/SKILL.md`. El nombre `kuraka` existe a la vez como skill
  (núcleo del orquestador, `user-invocable: false` a propósito) y como comando
  de entrada (`commands/kuraka.md`). Una skill registrada **eclipsa** al comando
  del mismo nombre, así que `/kuraka` resolvía a la skill no invocable en vez de
  al comando. Solo se manifestaba en proyectos ya actualizados a la Ola 3
  (antes existía únicamente la copia plana, que Claude Code no registra).
- **Fix** en `kuraka-mount.py::sync_claude_skills` (aplica a mount completo y a
  `--update`): una skill cuyo nombre coincide con un `commands/*.md` se monta
  SOLO como copia plana `.claude/skills/<n>.md` — que es como la leen el comando
  y el orquestador — y cualquier `<n>/SKILL.md` previamente montado se **borra**
  (limpia los proyectos ya afectados en su próximo update, sin pasos manuales).
- **Tests**: +3 vault-only (42 en verde): no-registro del nombre en colisión,
  limpieza del `SKILL.md` obsoleto, y guarda inversa que falla si aparece una
  colisión skill↔comando nueva en el vault.
- Proyecto afectado y ya corregido: `PetSuite`.


### Añadido — `kuraka-map.py` (capa de datos del tablero kuraka-control, 2026-08-22)

- **`kuraka-map.py`** — emite el grafo de cableado vivo de la suite como JSON,
  parseando SOLO archivos reales: frontmatter de `agents/*.md` (model, maxTurns,
  tools/disallowedTools, skills, memory) + los marcadores que los agentes ya
  declaran en su cuerpo (`**Phase**`, `**Receives from**`, `**Delivers to**`,
  `**Trigger**` — las referencias con backticks se vuelven aristas),
  `skills/*.md` (invocabilidad/fork), `hooks/`, `commands/` y `rules/16-19`.
  Editar un .md y regenerar recablea el grafo — cero curación manual.
  Modos: stdout, `--out`, y `--inject <html>` (reemplaza el marcador
  `/*__KURAKA_DATA_END__*/` del prototipo de tablero de nodos). Es la capa de
  datos de la feature kuraka-control: el prototipo embebe un snapshot; la
  versión viva lo serviría/consumiría directo.
- **`ROADMAP-AYLLU-MAP.md`** — plan para llevar el prototipo del tablero de
  nodos a kuraka-control como ciclos `/kuraka` (entrada pre-flow, no
  implementación desde el vault). Encaje analizado contra el estado real de ese
  proyecto: la vista **es la story S9** ya reservada en su build order, y la
  capa viva es **S8**. Hallazgo clave: `HOOK-LOG.jsonl` (hook `telemetry_append`
  de la Ola 2) es la **fuente de eventos que `adr-004-live-state-watcher`
  declaraba inexistente** — desbloquea ese spike. Deudas detectadas en
  kuraka-control: `AgentKey` con 16 de 23 agentes, 16 tokens `--ag-*`, y
  `kuraka.lock` en 0.3.4 (precondición: correr `kuraka-update` allí).

### Corregido — gates de campo de las Olas 0–4 (validación en kuraka-control, 2026-08-23)

Primera verificación **en un consumidor real** de todo lo montado por las Olas
0–4. Resultado: los 4 gates de campo que quedaban pendientes en el roadmap
pasan, y el ejercicio encontró un bug propio.

- **BUG PROPIO CORREGIDO** — `kuraka-artifacts/tests/kuraka/test_structure.py`:
  el check `test_should_register_every_skill_as_skill_md_dir` (añadido en la
  Ola 3) **contradecía la regla de colisión skill↔command** añadida después:
  exigía `SKILL.md` para TODA skill, incluida `kuraka`, que se monta flat-only
  a propósito (una skill registrada ensombrece al comando homónimo). El arnés
  fallaba en cualquier proyecto montado. Ahora exime a las skills que colisionan
  con un comando y se añade el guard inverso
  (`test_should_not_register_a_skill_that_shadows_a_command`). Verificado en
  kuraka-control: **26 pasan, 0 fallan**.
- **Gates de campo verificados** contra kuraka-control (mount del 2026-08-23,
  manifest `suite_version: 1.1.0`, 85 baselines, 23 agentes, 28 skills en
  formato SKILL.md, 4 hooks + 2 scripts cableados en `.claude/settings.json`):
  `validate-kuraka.sh` 0 errores/0 warnings; `gate_integrity` bloquea
  (exit 2) `npm -w backend run test | tail` y deja pasar el comando sin pipe;
  `orchestrator_guard` bloquea la escritura del orquestador en `backend/`
  (exit 2), deja pasar la del subagente y la de `docs/`.
- **Deuda detectada (no corregida aquí)**: el modo `--update` **no actualiza
  `kuraka.lock`** — kuraka-control quedó con `kuraka_version: 0.3.4` /
  `mounted_at: 2026-06-07` mientras su manifest ya dice 1.1.0. Es el dato que
  la story S2 de ese proyecto usará para el indicador de drift. Queda como
  pregunta abierta del ciclo S9 (ver su `docs/process/INPUT-S9-ayllu-map.md`).

## [1.1.0] — 2026-08-01 (primer harvest)

### Añadido
- **`jira-ticket-sync`** — nuevo agente condicional pre-flow (fase 0), adoptado
  y generalizado desde el override custom de `sie-integraciones` (rutas ahora
  config-driven vía `kuraka.config.yaml`, no hardcodes del proyecto). Registrado
  en `MODEL-ROUTING.yaml` (tier `fast`), `scripts/sync-obsidian.sh` y la tabla
  de agentes condicionales de `skills/kuraka.md`.
- **Versionado de suite** — `SUITE-VERSION` + este changelog;
  `kuraka_common.write_mount_manifest` estampa `suite_version` en el manifest de
  mount; `archive_cycles` lo copia al `meta.yaml` de cada ciclo.
- **`/kuraka-harvest`** — comando (solo vault) que recolecta overrides de
  `projects/*/overrides/`, los clasifica (stale / tuning de proyecto / candidato
  core), detecta agentes custom nuevos, propone integraciones y gestiona el bump
  de versión.
- **Design source of truth** (venía sin commitear en el working tree, entra en
  esta versión): `frontend-developer` lee el diseño real (Pencil MCP/Figma) como
  fuente de verdad; `arki` Step 6b siembra `frontend-branding.md`; `inti`
  registra frame index al prototipar; `kuraka-wizard` detecta design files no
  registrados. `arki` además endurece el criterio "skeleton buildable AND
  runnable" (LL-007).

### Añadido — Tier 1 del harvest (P1–P15 de `HARVEST-2026-08-01.md`, aprobado por el usuario)
- **P1** `rules/16-agent-backup.md` reescrita: backup solo-orquestador vía
  `kuraka-backup.py`, subagentes jamás escriben el vault, nunca `--delete`
  (cierra el incidente 2026-06-13).
- **P2** Git solo-lectura para agentes de revisión/verificación
  (`kuraka-policies` §Agent Invocation Policy).
- **P3** Prior-Retro Application Check pasa a GATE de cierre: patch aplicado+
  verificado o rechazo por escrito; framework-tier → `OPEN FRAMEWORK DEBT` con
  contador; LL sin fila en INDEX = invisible (`final-auditor`, `run-audit`).
- **P4** Protocolo de confianza de digests: stamp `VERIFIED`, techo de contexto,
  rebuild en re-scope (`rules/17` T1).
- **P5** Overhaul T10: agente nuevo vs resume (T10.a), clasificación del patch
  (T10.b), tiers S/M/L (T10.c).
- **P6** Entorno de gates verificado: rebuild tras deps/migraciones, entorno no
  sombreado, ráfaga post-migración = falsa regresión (`rules/17` T9 +
  `kuraka-policies` §green).
- **P7** Re-probe de entorno por gate con re-poll (`kuraka.md` §3.9).
- **P10** Check de invalidación de caché por namespace (`code-reviewer`;
  recurrió en 3 proyectos).
- **P11** Tabla de paridad para flujos replicados / caminos duales
  (`story-refiner` 18b + `architect-reviewer` check 16).
- **P12** Smoke ejecutado por usuario como gate; ciclos auth/seguridad cierran
  `PENDING-SMOKE`, nunca DONE sin smoke (`kuraka.md` §6.8).
- **P13** Role-lock obligatorio en el preámbulo de toda invocación de subagente
  (`kuraka-policies`).
- **P14** Nueva `rules/19-evidence.md` (R-CUERPO / R-CONTROL / R-ESPEJO); el
  mount ahora monta también las rules 18 y 19 (la 18 no se montaba — gap
  pre-existente corregido).
- **P15** Contratos congelados nunca parafraseados; configs validadas con el
  parser real, no con grep (`kuraka.md` §General rules).

### Corregido
- **`detect_overrides` / `write_mount_manifest` / `restore_overrides` ignoran
  ficheros AppleDouble (`._*`)** — el snapshot de `facturacion-honorarios` era
  100% basura de metadata de macOS (78 ficheros `._*` tratados como overrides y
  re-aplicados en cada mount). Snapshot purgado del store.
- **P8** `aggregate-telemetry.py`: filtra `._*`, captura `UnicodeDecodeError`,
  duraciones null → `n/a` y fuera de promedios (propuesto en 4 retros de
  facturacion-honorarios sin aterrizar).
- **P9** `kuraka-mount.py`: `.playwright-mcp/` y `.pytest_cache/` añadidos al
  gitignore que escribe el mount (propuesto en 3 retros de guai).

### Resultados (llenado por harvests futuros)
- _pendiente — ciclos con `suite_version: 1.1.0` aún no archivados_

---

## [1.0.0] — baseline (estado a 2026-07-30, commit `0c51dd4`)

Estado del framework antes del primer harvest: 21 agentes, routing centralizado
en `MODEL-ROUTING.yaml` (gates de juicio → `fable`), mount cross-platform
(`kuraka-mount.py`), store unificado `projects/<slug>/` con backup/restore de
overrides, manifest de mount para distinguir staleness de tuning.

### Resultados
- Todos los ciclos archivados hasta la fecha tienen `suite_version: "unknown"`
  (anteriores al estampado); se atribuyen a esta baseline.
