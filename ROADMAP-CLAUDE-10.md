# Roadmap: integración Kuraka ↔ Claude Code a 10/10

> **Fecha:** 2026-08-22 · **Base:** `INFORME-AGENTES-CLAUDE-CODE-2026-08.md` (diagnóstico) · **Estado plataforma:** docs oficiales Claude Code, agosto 2026.
> **Restricción de diseño (innegociable):** todo lo Claude-específico convive SOLO en el render para Claude Code. Antigravity (Gemini), Codex, Cursor y futuros targets no deben recibir ni un campo, hook o formato que no entiendan.

---

## 1. Scorecard — qué significa 10/10

| # | Dimensión | Hoy | Meta | Cómo se mide (criterio verificable) |
|---|---|:--:|:--:|---|
| D1 | Formato nativo de skills | 2 | 10 | Todas las skills en `.claude/skills/<n>/SKILL.md`; `/` menu limpio (solo invocables); 0 referencias rotas (`grep -r "skills/.*\.md"` sin matches planos) |
| D2 | Enforcement por harness (hooks) | 0 | 10 | 4 hooks activos (telemetría, gate-integrity, guardia orquestador, validación output); ≥120 líneas de prosa de disciplina eliminadas de los prompts |
| D3 | Least-privilege (frontmatter de capacidades) | 1 | 10 | 23/23 agentes con `tools`/`disallowedTools`/`maxTurns` gobernados por `AGENT-HARNESS.yaml`; `--check` en verde |
| D4 | Telemetría determinista | 3 | 10 | 100 % de invocaciones registradas por hook (0 entradas manuales); un ciclo completo sin huecos en el JSON |
| D5 | Coherencia documental/config | 5 | 10 | 0 contradicciones montadas (model routing, 16-vs-23, 8-vs-11 fases, timeout-vs-liveness); `validate-kuraka.sh` extendido pasa |
| D6 | Higiene de prompts | 6 | 10 | Digest protocol en 13/13; descriptions ≤200 chars; agentes >200 líneas reducidos ≥25 % sin perder reglas |
| D7 | Memoria/continuidad nativa | 3 | 10 | `memory: project` activo en final-auditor y pattern-detector; ledger de patches vive en memoria de agente |
| D8 | Supervisión de ejecución larga | 2 | 10 | Liveness por Monitor/script (no prosa); implementadores largos con `background: true` |
| D9 | Aislamiento multi-plataforma | 7 | 10 | Test estructural: ningún render no-Claude contiene campos Claude-only; ningún render Claude pierde contenido |
| D10 | Distribución (plugin) | 0 | — | *Stretch* — no puntúa para el 10/10; ver Ola 5 |

**Puntuación global = media D1–D9.** Al diagnosticar: ~3,2.

**Re-medición 2026-08-22 (Olas 0–4 ejecutadas): ~9,1.**
D1: 9 (falta retirar la copia flat + migrar referencias — próxima versión de
suite) · D2: 9 · D3: 9,5 · D4: 9 · D5: 9,5 · D6: 8,5 (digest 13/13,
descriptions, e2e −26%, EVIDENCE.md; compactación profunda de
amauta/arki/inti/po-analyst queda como política incremental "archivo tocado =
archivo compactado") · D7: 9 · D8: 8,5 (`background:` deliberadamente NO fijado
en frontmatter — es decisión por-story del orquestador, documentada en
policies) · D9: 10. Las décimas restantes hasta 10 son los **gates de campo**:
un ciclo Normal real en kuraka-control con HOOK-LOG completo, un pipe
bloqueado, menú `/` limpio, y el residual de `model: fable` vía frontmatter.

---

## 2. Arquitectura de convivencia multi-plataforma

Principio único, derivado del código existente:

> **El vault es el superset nativo de Claude; las demás plataformas RESTAN en el render.**

Está ya precedentado: el frontmatter del vault lleva `model:` (Claude-style) y el export lo descarta para Antigravity/Cursor/Codex; `copy_file(..., target_env)` ya reescribe rutas para no-Claude; las skills ya se convierten a `SKILL.md` para Antigravity/Codex. Ninguna plataforma no-Claude falla hoy por campos que no entiende — pero lo haremos explícito para que jamás dependa de tolerancia YAML.

### 2.1 Regla de oro del subsistema de overrides

`detect_overrides` compara **byte a byte** el archivo montado contra su baseline del vault. Por eso:

- **PROHIBIDO** inyectar frontmatter en tiempo de mount para Claude: cada agente aparecería como override y el harvest se llenaría de falsos positivos.
- Los campos Claude-only (`tools`, `disallowedTools`, `maxTurns`, `skills`, `memory`, `background`, `isolation`, `permissionMode`, `hooks`) **viven en los archivos del vault** (aplicados por script, ver 2.2). El render Claude sigue siendo copia verbatim → overrides intactos.
- Los renders no-Claude pasan por `strip_claude_frontmatter()` dentro del transform ya existente de `copy_file` — un set fijo `CLAUDE_ONLY_KEYS` en `kuraka_common.py`, compartido por `kuraka-mount.py` y `kuraka-export.py`.

### 2.2 Gobernanza central: `AGENT-HARNESS.yaml` (patrón MODEL-ROUTING)

Nuevo archivo hermano de `MODEL-ROUTING.yaml`:

```yaml
# AGENT-HARNESS.yaml — capacidades de harness por agente (SOLO render Claude).
# NUNCA editar tools/maxTurns/etc. en el frontmatter a mano: cambiar aquí y
# correr kuraka-apply-harness.py. Las demás plataformas los sustraen en render.
profiles:
  reviewer:        { disallowedTools: [Write, Edit, NotebookEdit], maxTurns: 40 }
  analyst:         { maxTurns: 30 }        # escriben docs/ — Write permitido; hook guarda rutas de código
  implementer:     { maxTurns: 50 }
  mechanical:      { tools: [Read, Grep, Glob, Bash], maxTurns: 25 }
agents:
  code-reviewer:      { profile: reviewer, skills: [review-implementation] }
  security-reviewer:  { profile: reviewer, skills: [security-audit] }
  architect-reviewer: { profile: reviewer, skills: [review-stories, schema-freeze] }
  migration-reviewer: { profile: reviewer }
  po-analyst:         { profile: analyst,  skills: [requirement-consistency-check, analyze-requirement] }
  story-refiner:      { profile: analyst,  skills: [refine-stories] }
  backend-developer:  { profile: implementer, skills: [implement-story] }
  frontend-developer: { profile: implementer, skills: [implement-story] }
  test-engineer:      { profile: implementer, skills: [plan-tests, generate-unit-tests, generate-endpoint-tests, validate-coverage, analyze-testability] }
  e2e-tester:         { profile: implementer, skills: [generate-e2e-tests] }
  deployment-verifier:{ profile: mechanical, skills: [verify-deployment] }
  pattern-detector:   { profile: mechanical, skills: [detect-patterns], memory: project }
  final-auditor:      { profile: analyst,  skills: [run-audit], memory: project, maxTurns: 25 }
  # ayllu/on-demand: perfiles según su naturaleza (pentest/sentry/provider = reviewer-like read-mostly)
```

`kuraka-apply-harness.py` (espejo de `kuraka-apply-models.py`): aplica el mapa al frontmatter de `agents/*.md`, `--check` reporta drift (exit 1). `validate-kuraka.sh` lo invoca. Nota: los `maxTurns` reemplazan la tabla de tool-use caps de `kuraka-policies.md` como *enforcement*; la tabla queda como referencia de interpretación.

### 2.3 Matriz de convivencia por artefacto

| Artefacto | Claude (`.claude/`) | Antigravity (`.agents/`) | Codex (`.codex/`) | Cursor |
|---|---|---|---|---|
| Frontmatter de capacidades (2.2) | ✅ verbatim | strip `CLAUDE_ONLY_KEYS` | strip | strip |
| `model:` | ✅ (MODEL-ROUTING) | drop (ya hoy) | drop (ya hoy) | drop |
| Skills | **NUEVO** `sync_claude_skills()` → `<n>/SKILL.md` + frontmatter §11.6 del informe | ya nativo (`sync_antigravity_skills`) | ya nativo (`sync_codex_skills`) | render actual |
| Hooks (`hooks/claude/**`) | ✅ scripts a `.claude/hooks/` + merge en `settings.json` | **no montar** | **no montar** | no montar |
| Bloque gestionado en CLAUDE.md del consumidor (import regla 19) | ✅ `<!-- kuraka:managed:begin/end -->` | equivalente propio si su plataforma lo soporta; si no, omitir | omitir | omitir |
| Commands | verbatim (legacy ok) | export adaptado (ya hoy) | compilados a skills (ya hoy) | export (ya hoy) |
| Digest protocol / prosa de prompts | ✅ (es texto: portable) | ✅ igual | ✅ igual | ✅ igual |

Las mejoras de **contenido** de prompts (Parte II del informe) son portables a todas las plataformas — solo el *enforcement* es Claude-only. Donde un hook Claude elimina prosa, el render no-Claude **conserva** la prosa: `copy_file` para no-Claude reinyecta un bloque `## Discipline (non-Claude platforms)` generado desde una fuente única (`kuraka-artifacts/discipline/*.md`), para que Gemini/Codex no pierdan las reglas que en Claude cubre el harness. (Implementación: marcador `<!-- discipline:telemetry -->` en el prompt; Claude lo deja como línea enforced-by-harness, no-Claude lo expande.)

### 2.4 Guardas anti-choque (tests)

Extender `tests/kuraka/`:

- `test_no_claude_only_keys_in_exports` — renderiza un mount de prueba por target y asserta que ningún archivo no-Claude contiene claves de `CLAUDE_ONLY_KEYS`.
- `test_claude_render_verbatim` — el render Claude de agents es byte-idéntico al vault (protege overrides).
- `test_harness_map_coverage` — todo agente existe en `AGENT-HARNESS.yaml` y viceversa (espejo del check de modelos).
- `test_skill_dirs_wellformed` — cada `SKILL.md` con `name` = dirname y `description` presente.

---

## 3. Olas de implementación

### Ola 0 — Correcciones y verificación (½ día) → D5 parcial ✅ COMPLETADA 2026-08-22

> Resultado: `fable` verificado (subagente corrió sobre `claude-fable-5`);
> policies corregidas (model routing + timeout); conteos unificados (23 agentes,
> 8 fases); mapa on-demand añadido a `kuraka.md`; `contexts/README.md`
> regenerado; 10 descriptions recortadas (Σ descripciones 7.962→5.268 chars,
> todas ≤300). Registrado en SUITE-CHANGELOG §Sin publicar. Residual: confirmar
> `model: fable` vía frontmatter en la próxima sesión de un consumidor montado.

| Tarea | Criterio de aceptación |
|---|---|
| 0.1 Verificar `model: fable` en frontmatter de subagente (spawn de prueba + confirmar modelo en telemetría/costo). Si no resuelve: tier frontier → `inherit` en MODEL-ROUTING + re-apply | Evidencia del modelo real ejecutado, pegada en el commit |
| 0.2 `kuraka-policies.md` §Model Routing → referencia a MODEL-ROUTING.yaml (informe §11.2.1) | 0 menciones a "edit `model:` in frontmatter" |
| 0.3 Reconciliar timeout 10-min vs liveness (§11.2.2) | Una sola política de salud |
| 0.4 Docs: 16→23 agentes; 8-vs-11 fases unificado; `contexts/README.md` regenerado | `grep -rn "16 subagent\|11-phase"` limpio |
| 0.5 Descriptions ayllu → trigger-style (§10.4) | 23/23 descriptions ≤ ~200 chars |

Riesgo: nulo. Todo portable (texto), cero impacto en otros targets.

### Ola 1 — Capacidades gobernadas (2–3 días) → D3, D9 ✅ COMPLETADA 2026-08-22

> Resultado: `AGENT-HARNESS.yaml` + `kuraka-apply-harness.py` aplicados a los 23
> agentes (revisores write-denied, deployment-verifier con allowlist, maxTurns
> ~2× del cap blando); `strip_claude_frontmatter` en `copy_file` para todo
> target ≠ claude (no-op verificado en los 87 archivos actuales; Antigravity/
> Codex conservan sus pipelines intactos); 11 tests vault-only en verde;
> self-checks en validate-kuraka.sh; L3 de Lite ajustado (reviewer no escribe
> tests). `emit.skills`/`emit.memory` quedan apagados hasta Olas 3/4.
> Pendiente del gate: mount de humo real en kuraka-control en el próximo mount
> del usuario (evita ensuciar el registry con un target de prueba).

1. `CLAUDE_ONLY_KEYS` + `strip_claude_frontmatter()` en `kuraka_common.py`; enganchar en el transform no-Claude de `copy_file` y en `kuraka-export.py`.
2. `AGENT-HARNESS.yaml` + `kuraka-apply-harness.py` (+ `--check` en `validate-kuraka.sh`).
3. Aplicar la matriz (2.2) a los 23 agentes.
4. Tests 2.4 (los dos primeros + coverage).
5. Mount de prueba en kuraka-control: verificar que reviewers no pueden editar (intento bloqueado por harness) y que un mount Antigravity no muestra los campos.

Gate de salida: `kuraka-apply-harness.py --check` y `pytest tests/kuraka/` verdes; ciclo Lite de humo en kuraka-control sin fricción nueva.

### Ola 2 — Pack de hooks + adelgazamiento de prosa (3–5 días) → D2, D4 ✅ COMPLETADA 2026-08-22

> Resultado: 4 hooks (`hooks/`) montados solo-Claude con merge no destructivo en
> settings.json; bloques `discipline/` re-expandidos en renders no-Claude
> (mecanismo §2.3 implementado en `_expand_discipline`); prosa de enforcement
> sustituida por notas-slim en policies/kuraka.md/13 agentes (la relectura
> terminal de output-schemas.md queda eliminada en Claude); 22 tests en verde.
> Gate pendiente de campo: un ciclo Normal real en kuraka-control verificando
> (a) HOOK-LOG.jsonl completo, (b) bloqueo de un pipe deliberado — en el
> próximo mount del usuario.

Contenido del pack (`hooks/claude/` en el vault; mount solo-Claude + merge no destructivo en `settings.json` del consumidor, bloque gestionado):

| Hook | Evento | Qué hace |
|---|---|---|
| `telemetry-append.sh` | `PostToolUse` (matcher Task/Agent) | Apende la entrada JSON de telemetría del run (fase inferida del checkpoint activo). Elimina la clase entera "12 de 31 runs sin registrar" |
| `gate-integrity.sh` | `PreToolUse` (Bash) | Rechaza pipes sobre comandos gate declarados en `kuraka.config.yaml` (`stack.*.test_cmd`, `lint_cmd`, `typecheck_cmd`): el falso verde T7 se vuelve imposible |
| `orchestrator-guard.sh` | `PreToolUse` (Write/Edit) | En sesión orquestadora (sin `agent_id`), bloquea escrituras a `backend_root`/`frontend_root`/`tests_root`/`migrations_root` salvo flag de Fase 4+ en el checkpoint |
| `output-validate.sh` | `SubagentStop` | Chequea headers requeridos del output contra `output-schemas.md` (por `agent_type`); si falla, devuelve el motivo → el retry de policies se dispara con causa concreta |

Después de activarlos: **pasada de borrado de prosa** (informe §10.2) — telemetría, T7, protocolo de violación, Output Validation por agente — con el mecanismo §2.3 para que los renders no-Claude conserven la disciplina en texto.

Gate de salida: un ciclo Normal completo en kuraka-control con (a) telemetría 100 % por hook, (b) un intento deliberado de `make test | tail` bloqueado, (c) ≥120 líneas netas eliminadas de prompts montados en Claude sin pérdida en no-Claude (diff de renders).

### Ola 3 — Skills nativas + reglas siempre-activas (3–4 días) → D1, D5 ✅ COMPLETADA 2026-08-22

> Resultado: `sync_claude_skills()` (doble copia SKILL.md + flat, byte-idéntica);
> canonicalización + espejo en el subsistema de overrides; clasificación de
> invocabilidad en las 28 skills (núcleo/fase no invocables, utilidades `context:
> fork`, 3 user-facing); precarga `skills:` activa en 14 agentes; bloque
> gestionado en CLAUDE.md del consumidor con la regla 19; `alwaysApply` retirado.
> 29 tests vault + 3 checks nuevos en el harness montado. Residuales: retirar el
> flat + migrar referencias + sync-obsidian a dirs en la PRÓXIMA versión de
> suite; validar en el próximo mount real que `/` solo muestra las 3 invocables.

1. `sync_claude_skills()` en el mount (patrón `sync_codex_skills`): `<n>/SKILL.md` + frontmatter por tipo (informe §11.6). Periodo de transición de 1 versión de suite: doble copia (dir + flat) para no romper referencias por ruta; retirar la flat en la siguiente.
2. Actualizar los tocados por el cambio de layout: `detect_overrides`/backup/restore (glob `skills/*/SKILL.md`), `scripts/sync-obsidian.sh`, `tests/kuraka/test_structure.py`, referencias `.claude/skills/x.md` → `.claude/skills/x/SKILL.md` en agents/commands.
3. `skills:` precarga por agente (ya mapeado en AGENT-HARNESS, Ola 1 lo deja listo — aquí se activa el beneficio: eliminar el paso "read your skill" de los prompts).
4. `context: fork` en utilitarias (`compact-context`, `detect-patterns`, `gap-analysis`).
5. Bloque gestionado en CLAUDE.md del consumidor con `@.claude/rules/19-evidence.md`; retirar `alwaysApply` de rules 17/19.

Gate de salida: en un consumidor montado, `/` muestra solo las skills invocables; una sesión SIN `/kuraka` responde ya bajo la regla 19; suite estructural verde; `kuraka-backup.py --overrides-only` detecta correctamente un override de skill en el nuevo layout.

### Ola 4 — Memoria, supervisión y pulido de prompts (2–3 días) → D6, D7, D8 ✅ COMPLETADA 2026-08-22

> Resultado: `memory: project` emitido (final-auditor ledger de patches en
> memoria; pattern-detector índice incremental con watermark); watcher de
> liveness (`hooks/liveness_watch.sh`, Monitor/background) con la política como
> regla de decisión; digest protocol insertado en 13/13 agentes; `EVIDENCE.md`
> creado como destino del tejido cicatricial (compactación profunda:
> incremental); e2e-tester 282→209 líneas (playbook CRUD movido a su context
> file); `review_mechanics.sh` para los greps de revisores (el fable adjudica,
> el script barre). 35 tests vault en verde. Decisión: `background: true` NO va
> en frontmatter — es una elección por-story del orquestador (policies §liveness).

1. `memory: project` activo (final-auditor, pattern-detector) + edición §11.5 del informe (ledger de patches en memoria).
2. Liveness por Monitor: script `liveness-watch.sh` (mtimes del árbol autorizado, streaming) + `background: true` para implementadores en stories L; la política prose "poll the files" se reduce a "launch the watcher".
3. Digest protocol en 13/13 agentes (§10.1) + compactación de tejido cicatricial (§10.3, `EVIDENCE.md`) + e2e-tester recortado (§11.4) + review-mechanics.sh para los checks grep de reviewers (§11.3).
4. Re-medición del scorecard §1 con un ciclo real (telemetría del hook como fuente).

Gate de salida: scorecard D1–D9 ≥ 9 de media; RETRO del ciclo de validación sin regresiones atribuibles al roadmap.

### Ola 5 — Estratégica (opcional, no bloquea el 10/10)

- **Piloto Agent Teams** (flag experimental) SOLO para Fase 4a‖4b con file locking; hub-and-spoke intacto para gates. Decisión por retro comparativo (tokens, retrabajo, latencia) vs. ciclo equivalente sin teams.
- **Empaquetado como plugin de Claude Code**: manifest desde `SUITE-VERSION`, bundle agents+skills+hooks; el mount queda para artifacts/rules/overrides. Habilita distribución y versionado nativos.
- **Workflow tool**: seguir docs; adoptar solo cuando esté documentado públicamente.

---

## 4. Secuencia, dependencias y esfuerzo total

```
Ola 0 (½d) ──► Ola 1 (2–3d) ──► Ola 2 (3–5d) ──► Ola 3 (3–4d) ──► Ola 4 (2–3d) ──► [Ola 5]
   docs         capacidades       hooks +          skills           memoria/
   + fable      + strip           borrar prosa     nativas          supervisión
```

**Total al 10/10: ~11–15 días de trabajo efectivo**, validable ola a ola con ciclos reales en kuraka-control. Dependencias duras: 2.1 (strip) antes que cualquier campo nuevo en el vault; hooks antes de borrar prosa; doble copia de skills antes de retirar las flat.

## 5. Reglas permanentes post-roadmap

1. **Vault = superset Claude; no-Claude resta.** Ningún feature nuevo se añade inyectando en mount para Claude.
2. **Campos de harness solo vía `AGENT-HARNESS.yaml`** (como `model:` vía MODEL-ROUTING). El `--check` en validate es el guardián.
3. **Hook nuevo ⇒ prosa borrada** (y bloque discipline generado para no-Claude). Se mide en el diff.
4. **Toda mejora de contenido de prompt es multi-plataforma por defecto**; solo el enforcement es per-target.
5. Los bumps de `SUITE-VERSION` por estas olas pasan por `/kuraka-harvest` como siempre (aprobación por ítem).
