# Informe: Auditoría de los agentes Kuraka montados en Claude Code

> **Fecha:** 2026-08-22
> **Alcance:** lo que `kuraka-mount.py` inserta en `.claude/` de un proyecto consumidor para Claude Code — 23 agentes, 28 skills, contexts, reglas 16–19, comandos — cruzado con el estado actual de la plataforma Claude Code (docs oficiales, agosto 2026).
> **Enfoque:** ingeniería de IA senior, sin suavizar. Complementa (no repite) el `INFORME-DIAGNOSTICO-MEJORAS.md` previo, que evaluó la metodología SDD; este evalúa la **integración con Claude Code**: formato, prompts, enforcement, ruido y qué novedades de la plataforma adoptar.

---

## 1. Dictamen ejecutivo

**Calificación de ingeniería de prompts: 9/10. Calificación de integración con la plataforma Claude Code: 6/10.**

El contenido de los prompts está entre lo mejor que se puede encontrar en frameworks multi-agente: cada regla cita el incidente real que la motivó, los gates son verificables por comando, la verificación determinística vive en el orquestador a costo cero (regla T9), y existen bucles de meta-aprendizaje reales (harvest/eval/retro). Eso es práctica de frontera, no marketing.

El problema es **dónde vive el enforcement**: casi todo se sostiene por prosa que el modelo debe obedecer, cuando la plataforma 2026 ofrece mecanismos deterministas (hooks, `tools:`, `maxTurns`, `disallowedTools`, hooks por agente) que harían cumplir esas mismas reglas a costo 0 tokens y con garantía del harness, no del modelo. Los propios RETROs del framework documentan que la prosa falla de forma recurrente (telemetría omitida 3 ciclos seguidos, caps de tool-use ignorados 111/30, prosa advisory fallida 8 ciclos). La respuesta histórica del framework ha sido **más prosa** — y eso tiene un techo: cada regla nueva diluye la atención sobre las anteriores.

Además hay una deuda de formato: **las skills se montan en el formato pre-2025 (archivos `.md` planos), que Claude Code ya no registra como skills**; funcionan solo porque los agentes las leen como documentos por ruta. Irónicamente, el mount ya genera el formato nativo (`<nombre>/SKILL.md`) para Antigravity y Codex — los targets secundarios reciben mejor integración que el primario.

---

## 2. Estado de la plataforma Claude Code (agosto 2026) — lo que importa a Kuraka

Resumen de la investigación contra docs oficiales (code.claude.com/docs):

| Capacidad | Estado | Relevancia para Kuraka |
|---|---|---|
| Frontmatter de subagentes: `tools`, `disallowedTools`, `permissionMode`, `maxTurns`, `skills` (precarga), `memory` (user/project/local), `effort`, `background`, `isolation: worktree`, `hooks` por agente | ✅ Estable | **Alta** — casi nada de esto se usa hoy |
| `model:` en subagentes: `sonnet`/`opus`/`haiku`/`inherit` documentados; **`fable` no aparece en la lista documentada** | ⚠️ Verificar | **Crítica** — 5 agentes gate usan `fable` |
| Skills: formato canónico `skills/<nombre>/SKILL.md` (directorio + recursos); frontmatter `disable-model-invocation`, `user-invocable`, `context: fork`, `allowed-tools`, `model`, `effort` | ✅ Estable | **Alta** — Kuraka monta el formato viejo |
| Commands `.claude/commands/*.md` | ✅ Legacy soportado (fusionados con skills) | Los comandos Kuraka siguen funcionando |
| Hooks: 30 eventos (`PreToolUse`, `PostToolUse`, `SubagentStart/Stop`, `SessionStart`, etc.); tipos command/http/mcp/prompt/agent; configurables por agente | ✅ Estable | **Alta** — enforcement determinista |
| Agent Teams (`SendMessage`/`ListAgents` entre pares, task list compartida, file locking) | ⚠️ **EXPERIMENTAL** (flag `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS`) | Media — no apto para gates todavía |
| `/loop` (auto-ritmo con ScheduleWakeup), Monitor tool (streaming de un script en background), `/schedule` cloud | ✅ Estable | Media — supervisión de fases largas |
| Auto-memory por proyecto (MEMORY.md) + memoria por subagente (`memory:` scope) | ✅ Estable | Media — solapa con lessons-learned |
| Plugins (bundle de skills+agents+hooks+MCP con manifest y versión; marketplace) | ✅ Estable | **Estratégica** — es el "mount" nativo |
| Workflow tool (orquestación determinística programada) | ❌ No documentado públicamente de forma completa | Observar, no adoptar |
| Harness = el loop Plan→Act→Observe lo gestiona la plataforma (context compaction, permisos, hooks); mismo harness en Agent SDK | ✅ | Marco conceptual de las mejoras |

---

## 3. Inventario real de lo que se monta para Claude Code

- **`.claude/agents/`** — **23 agentes** (no 16, como dicen CLAUDe.md y el phase map): 13 del pipeline + inti/arki/amauta (entrada) + **7 "ayllu" fuera del phase map** (pentest-auditor, sentry-resolver, deploy-diagnostician, provider-contract-validator, migration-deployability, checkmarx-remediation, jira-ticket-sync). Σ 4.539 líneas.
- **`.claude/agents/contexts/`** — 16 archivos de reglas por agente + `output-schemas.md` (207 líneas, contrato entre agentes). Σ 1.246 líneas.
- **`.claude/skills/`** — 28 archivos `.md` **planos** (orquestador + fases). Σ 4.354 líneas.
- **`.claude/commands/`** — comandos verbatim (el `/kuraka` que arranca el flujo). Funcionan como legacy commands.
- **`.claude/rules/16..19`** — reglas meta del framework. **No es una ubicación nativa de Claude Code**: solo entran en contexto porque el comando `/kuraka` ordena leerlas (paso 2 y 4).
- Artefactos (`docs/process/**`, `tests/kuraka/**`) + manifest de mount con hash baseline (soporte de overrides — bien diseñado).

**Carga permanente**: las 23 descripciones suman ~8 KB (~2K tokens) que Claude Code inyecta en **cada sesión** del proyecto consumidor, se use Kuraka o no. Las descripciones ayllu son párrafos completos (provider-contract-validator: 834 caracteres; sentry-resolver: 727).

---

## 4. Hallazgos críticos (ordenados por severidad)

### H1 — Las skills se montan en un formato que Claude Code ya no registra ⚠️ BLOCKER-adjacent

El formato canónico es `skills/<nombre>/SKILL.md`. Los 28 `.md` planos en `.claude/skills/` **no se registran como skills invocables**: no aparecen en el menú `/`, Claude no las auto-descubre, y un subagente al que su prompt le dice "run the `verify-output` skill" **no puede invocarla con el Skill tool** — o la resuelve leyendo el archivo por ruta (funciona, pero es un fallback implícito) o falla e improvisa (ruido). Hoy el sistema se sostiene porque los prompts citan rutas (`.claude/skills/kuraka.md`), pero:

- Se pierde el frontmatter moderno: `context: fork`, `allowed-tools`, `disable-model-invocation`, precarga vía `skills:` en el frontmatter del agente.
- La palabra "skill" en 30+ sitios de los prompts describe algo que para la plataforma no es una skill.
- **El mount ya convierte a `SKILL.md` para Antigravity y Codex** (`sync_antigravity_skills`, `sync_codex_skills`) — falta exactamente la misma función para el target principal.

**Fix:** añadir `sync_claude_skills()` al mount (mismo patrón que Codex), con `disable-model-invocation: true` en las skills internas de fase (para que no contaminen el auto-discovery) y `user-invocable: false` donde aplique. Mantener compatibilidad de rutas un ciclo (symlink o doble copia) mientras se actualizan las referencias.

### H2 — `model: fable` en 5 agentes gate: no está en la lista documentada de valores de subagente

Docs oficiales de subagentes: `sonnet | opus | haiku | inherit`. Los 5 agentes frontier (po-analyst, architect-reviewer, code-reviewer, security-reviewer, final-auditor) declaran `fable`. Si el alias no resuelve en frontmatter de subagente, el fallback silencioso (o error) degradaría exactamente los GATES de juicio. **Verificación de 1 minuto:** invocar un subagente con `model: fable` y confirmar en `/cost` o telemetría qué modelo corrió. Si no resuelve: usar `inherit` (la sesión ya corre Fable) para el tier frontier, y documentarlo en `MODEL-ROUTING.yaml`.

### H3 — Contradicción interna montada: `kuraka-policies.md` §Model Routing está obsoleta

La tabla dice `opus` para po-analyst/architect/security/final-auditor y `sonnet` para code-reviewer (pre-Fable), e instruye "edit `model:` in the frontmatter" — **exactamente lo que la gobernanza actual prohíbe** (`MODEL-ROUTING.yaml` + `kuraka-apply-models.py` son la fuente única). El orquestador del consumidor lee ambas cosas. Es el ejemplo vivo del riesgo de redundancia sin sincronización (ver H7). **Fix:** reemplazar la sección por una referencia al mapa + regenerar.

### H4 — Cero uso de `tools:` / `disallowedTools:` — el aislamiento de roles es solo prosa

Ningún agente restringe herramientas. Consecuencias concretas:

- `code-reviewer`, `security-reviewer`, `architect-reviewer` **pueden editar código** — la regla "el revisor no arregla, reporta" se sostiene solo por obediencia del modelo.
- `pattern-detector`, `deployment-verifier` (haiku, mecánicos) tienen Write/Edit sin necesitarlo.
- La constraint más importante del framework ("orchestrator never writes source before Phase 4") tiene protocolo de violación de 4 pasos en prosa… porque ocurrió. Un `PreToolUse` hook puede hacerla estructuralmente imposible.

**Matriz propuesta (frontmatter):**

| Agente | Propuesta |
|---|---|
| code-reviewer, security-reviewer, architect-reviewer, migration-reviewer | `disallowedTools: Write, Edit, NotebookEdit` (Bash queda para lint/diff/grep) |
| po-analyst, story-refiner, final-auditor, pattern-detector | `disallowedTools: Write, Edit` + excepción de escritura solo en `docs/` vía hook, o aceptar Write (escriben REQ/stories/retros) pero bloquear rutas de código con PreToolUse hook |
| backend/frontend-developer, test-engineer, e2e-tester | sin restricción (implementan) |
| deployment-verifier | `tools: Read, Grep, Glob, Bash` |

### H5 — La telemetría (fallo #1 documentado del framework) puede ser un hook a costo cero

`kuraka-policies.md` exige apuntar `<usage>` tras **cada** invocación; los retros documentan la regresión: 12 de 31 runs sin registrar (el ciclo reportó 3,76M cuando gastó 5,90M). Es el caso de libro para un **`PostToolUse` hook (matcher: Task/Agent)** que ejecute un script que apende el JSON de telemetría determinísticamente: nunca se olvida, no consume tokens, y el orquestador deja de cargar con ~40 líneas de prosa de disciplina. Lo mismo aplica a:

- **Gate integrity (T7):** `PreToolUse` hook sobre Bash que rechace `make test | tail`-style pipes en comandos gate (patrón configurable por proyecto). El falso verde de REQ-20260611 se vuelve imposible, no "prohibido".
- **Validación de output (verify-output):** `SubagentStop` hook que corra un script de chequeo de secciones contra `output-schemas.md` — hoy cada agente relee 207 líneas al final de **cada fase** para auto-validarse (coste recurrente y cumplimiento variable).
- **Tool-use caps:** el cap por agente (30/50/40/25) que "se mide después" en prosa es literalmente el campo **`maxTurns`** del frontmatter — enforcement nativo.

### H6 — `.claude/rules/` no es una ubicación nativa; `alwaysApply: true` es un residuo de Cursor

Claude Code no auto-carga `.claude/rules/` — las reglas 16–19 solo entran cuando el flujo arranca por `/kuraka` (cuyo paso 2 ordena leerlas). Una sesión que trabaje sin `/kuraka` (muy común: "arréglame esto") opera **sin** las reglas de evidencia (19) ni las de token-optimization (17). El frontmatter `alwaysApply: true` (rules 17 y 19) es sintaxis de Cursor que Claude Code ignora silenciosamente. **Fix:** que el mount inyecte/actualice un bloque en el `CLAUDE.md` del consumidor con `@.claude/rules/19-evidence.md` (import nativo) para las reglas que deben ser siempre-activas, y deje 17 como lectura del comando (es específica de orquestación).

### H7 — Redundancia multi-capa sin mecanismo de sincronización

La misma regla vive en 3–5 sitios: scope-fidelity está en `kuraka.md` (Fase 5), `code-reviewer.md`, `backend-developer.md`, `security-reviewer.md` y `rules/17` T9; tenant-scoping en 5 agentes; los budgets en `kuraka-policies.md`, `rules/17` y `aggregate-telemetry.py` (con desacuerdo documentado por-fase vs por-agente). Parte es defensa-en-profundidad deliberada y correcta; el problema es que **no hay generador**: cuando la verdad cambia, las copias divergen (H3 es la prueba). `MODEL-ROUTING.yaml` → `kuraka-apply-models.py` es el patrón correcto ya inventado en este repo — extenderlo: una fuente por invariante compartido, con sección generada (`<!-- generated -->`) en cada archivo que la repite, y un check en `validate-kuraka.sh`.

### H8 — Documentación desincronizada del propio sistema

- "16 subagentes" en CLAUDE.md / README mientras se montan 23. Los 7 ayllu no aparecen en el phase map ni tienen criterio de invocación en el orquestador (son on-demand, pero eso no está declarado en ningún sitio central).
- `contexts/README.md` (2026-04-17) mapea las reglas 01–16 de sie_v2, que en cualquier otro consumidor **no existen** (gitignoradas del vault). Un agente que siga ese mapa en otro proyecto busca archivos inexistentes = tool calls de ruido.
- `kuraka-policies.md` mantiene "Max 10 minutes per invocation" tres pantallas antes de la sección de liveness que documenta un agente sano corriendo 7 horas (REQ-20260801). Las dos políticas coexisten sin reconciliación.

### H9 — Descripciones de agentes como párrafos: overhead permanente y peor routing

La `description` es el **criterio de enrutamiento** que Claude lee en cada sesión; su función es "cuándo delegar aquí", no documentar el agente. Las descripciones ayllu de 600–830 caracteres (con codenames quechua, política de read-only, entregables) gastan ~2K tokens por sesión × todas las sesiones × todos los proyectos, y diluyen la señal de routing. **Fix:** 1–2 frases orientadas a trigger ("Use when…"); el detalle ya vive en el body.

---

## 5. Diagnóstico de prompts, agente por agente

| Agente (modelo) | Veredicto | Notas |
|---|---|---|
| `po-analyst` (fable) | **Excelente** | La distinción fidelity-vs-gap-finding (regla 10) y el contract-first GATE ("observe, do not recall") son sofisticados y nacen de incidentes caros reales. Riesgo: 225 líneas y creciendo. |
| `story-refiner` (sonnet) | **Bueno** | El peor ofensor histórico de presupuesto (15/38 runs over) — pero el fix correcto ya está en T1.1/T10 (forma del prompt del orquestador), no en este archivo. Correcto no haberlo engordado. |
| `architect-reviewer` (fable) | **El mejor de la suite** | El Empirical Freeze Checklist (E1–E6: "run the mechanism before freezing") es práctica de frontera — atrapó defectos MAYOR pre-código 3 ciclos seguidos. Check 16 (parity table) muy bien atado a story-refiner 18b. |
| `backend-developer` (sonnet) | **Excelente** | "End at READY-FOR-EXTERNAL-VERIFY" es ejemplar: recorta el tail de auto-verificación que duplicaba al orquestador Y donde los runs largos morían. Scope-fidelity con evidencia de diff, deviations reporting — todo correcto. |
| `frontend-developer` (sonnet) | Bueno | Espejo del backend, coherente. |
| `code-reviewer` (fable) | **Excelente, con matiz** | Los "Directed checks" (contract cross-check, cache-namespace, single-submit…) son oro destilado de incidentes; el matiz: la mitad son greps mecánicos que un script/hook podría correr y pasarle el resultado — el fable debería gastar su juicio en lo no mecanizable. DEFERRED como severidad anti-inflación: muy bien. |
| `security-reviewer` (fable) | Sólido | OWASP clásico + tenant + "auth surfaces are YOUR lane" con verificación independiente de diff (lección guai). Correcto. |
| `test-engineer` (sonnet) | Correcto | Doble modo (planning/writing) bien delimitado. |
| `e2e-tester` (haiku) | ⚠️ Desajuste | 267 líneas de instrucciones sobre el modelo más pequeño: haiku degrada en cumplimiento con listas largas. O recortar el prompt a lo esencial o subir a sonnet (tier en MODEL-ROUTING). |
| `final-auditor` (fable) | **Excelente** | El Prior-Retro Application Check como GATE de cierre (no línea de reporte) ataca el fallo real (0/11 patches aplicados en facturacion-honorarios). El backup de vault como hard exit criterion: correcto. |
| `deployment-verifier`, `migration-reviewer`, `pattern-detector` (haiku) | Correcto | Tier adecuado a trabajo mecánico. |
| `amauta`/`inti`/`arki` (opus) | Bueno | "Never invent conventions" + verificación del inspect report contra realidad: bien. |
| Ayllu (7, opus) | Bueno en contenido | Fuera de gobernanza del phase map; descripciones infladas (H9); idioma mezclado (español) frente al core (inglés). |

**Sobre el conjunto:** el patrón "tejido cicatricial" — cada incidente añade una regla con su historia (REQ-20260703, DD-1031, LL-014…) — hoy es una fortaleza (reglas justificadas, no dogma) pero tiene curva de saturación: los prompts crecen ~monotónicamente y el cumplimiento por prosa cae con el número de reglas. La válvula de escape es H5: cada regla mecanizable que migra a hook es prosa que se puede **borrar** del prompt. El objetivo sano es que los prompts converjan a juicio + contexto, y el harness cargue con la disciplina.

## 6. ¿Generan ruido o retrabajo? — veredicto

**El sistema hoy genera menos retrabajo que cualquier alternativa razonable, y lo documenta con honestidad brutal** (los retros citados en los propios prompts son la prueba). Los focos de ruido residual, por evidencia interna:

1. **Doble instrucción de carga de contexto**: cada agente ordena "Load context 1..4" (config + stack profile + project layer + glosario) mientras `rules/17` T1 ordena al orquestador pre-digerir y prohibir la relectura. Cuando el digest llega, el agente tiene dos instrucciones en conflicto; los retros muestran que a veces relee igual (fases 2/2.5/3 corriendo 1,9× over). Fix: una línea condicional en la sección Context de cada agente: *"Si el prompt trae `## Context digest`, SALTA los pasos 1–2 salvo ambigüedad."*
2. **verify-output**: relectura de 207 líneas × cada agente × cada fase ≈ 15–25K tokens/ciclo de puro overhead de validación → hook `SubagentStop` (H5).
3. **Skills fantasma** (H1): el término "skill" resuelve por convención, no por plataforma — fuente latente de tool calls fallidos.
4. **contexts/README obsoleto** (H8): mapa hacia archivos inexistentes fuera de sie_v2.
5. **Carga fija de 23 descripciones** (H9) en sesiones que no usan Kuraka.

Ninguno de estos es estructural; todos tienen fix barato.

---

## 7. Novedades de Claude Code: qué adoptar, qué pilotar, qué esperar

### Adoptar ya (estable, alto ROI)

1. **Hooks** (H5) — telemetría PostToolUse, gate-integrity PreToolUse, validación SubagentStop, y el hook de guardia del orquestador (bloquear Write/Edit a `backend/`, `frontend/`, `tests/`, `migrations/` fuera de Fase 4). El mount ya tiene categoría `hooks` en el sync — está lista la tubería, falta el contenido.
2. **`tools:`/`disallowedTools:`/`maxTurns`** por agente (H4). Least-privilege gratis.
3. **Migración de skills a `SKILL.md`** (H1) con `disable-model-invocation` en las internas.
4. **`skills:` precarga en frontmatter**: `backend-developer` puede declarar `skills: [implement-story]` y la skill de fase llega precargada — elimina el paso "lee tu skill" y su tool call.
5. **`memory: project`** para `final-auditor` y `pattern-detector`: memoria nativa entre ciclos (dónde quedaron los patches pendientes, contadores de FRAMEWORK DEBT) sin reconstruir desde archivos.
6. **`context: fork`** para skills utilitarias que el orquestador corre y que no necesitan el historial (p. ej. `compact-context`, `detect-patterns`) — contexto limpio, coste menor.
7. **`/loop` + Monitor para liveness**: la política "poll the files, not the clock" (nacida del falso-muerto de 7h) es exactamente lo que Monitor hace nativo — un script que observa mtimes del árbol autorizado y streamea; y `background: true` en implementadores largos con notificación al terminar.

### Pilotar con cuidado (experimental)

8. **Agent Teams / SendMessage entre pares**: sigue detrás de flag experimental, sin resume, sin nesting. El hub-and-spoke de Kuraka **es la arquitectura correcta para un pipeline con gates de usuario** — no cambiarla. Piloto acotado donde sí brilla: Fase 4a‖4b (backend y frontend paralelos con file locking y mensajes de contrato entre ambos, en vez de relevo por orquestador). Mantener la advertencia T10: un resume re-cobra el transcript completo — sigue vigente y correcta.

### Estratégico (siguiente iteración del mount)

9. **Empaquetar Kuraka como plugin de Claude Code**: un plugin agrupa agents + skills + hooks + MCP con manifest **versionado** — es la versión nativa de lo que `mount-kuraka` + `SUITE-VERSION` hacen a mano hoy: distribución, actualización sin rsync, y el marketplace como canal si algún día se publica. El subsistema de overrides seguiría siendo necesario (el plugin no cubre tuning por proyecto), pero el mount se reduce a instalar el plugin + montar artifacts/rules.

### No adoptar todavía

10. **Workflow tool** — sin documentación pública completa; observar.

---

## 8. Plan de acción priorizado

| # | Acción | Esfuerzo | Impacto |
|---|---|---|---|
| P0-1 | Verificar empíricamente `model: fable` en frontmatter de subagente (H2); si no resuelve → `inherit` vía MODEL-ROUTING | 15 min | Evita degradación silenciosa de los 5 gates |
| P0-2 | Corregir `kuraka-policies.md` §Model Routing → referencia a MODEL-ROUTING.yaml (H3) | 15 min | Elimina contradicción montada |
| P0-3 | Actualizar "16 agentes"→23 + refrescar `contexts/README.md` + reconciliar timeout 10-min vs liveness (H8) | 1 h | Menos ruido documental |
| P0-4 | Recortar descripciones ayllu a 1–2 frases de trigger (H9) | 1 h | −60% overhead fijo por sesión |
| P1-1 | `disallowedTools`/`tools` + `maxTurns` en los 23 agentes según matriz (H4) | 2–3 h | Aislamiento de roles por harness |
| P1-2 | Hooks: telemetría (PostToolUse Task), gate-integrity (PreToolUse Bash), guardia del orquestador, validación de output (SubagentStop) (H5) | 1–2 días | Ataca el fallo #1 documentado; permite ADELGAZAR prosa |
| P1-3 | Línea "si hay digest, salta pasos 1–2" en la sección Context de cada agente (§6.1) | 1 h | Cierra el conflicto digest-vs-releer |
| P2-1 | `sync_claude_skills()` → formato `SKILL.md` + `disable-model-invocation` + precarga `skills:` en agentes (H1) | 1 día | Integración nativa; habilita fork/allowed-tools |
| P2-2 | Import nativo de `rules/19` vía CLAUDE.md del consumidor; retirar `alwaysApply` (H6) | 2 h | Reglas de evidencia siempre activas |
| P2-3 | `memory: project` en final-auditor/pattern-detector; `context: fork` en skills utilitarias | 2 h | Continuidad entre ciclos |
| P3-1 | Generador de secciones compartidas (patrón MODEL-ROUTING) para budgets/scope-fidelity + check en validate-kuraka.sh (H7) | 1–2 días | Fin del drift entre copias |
| P3-2 | Piloto Agent Teams solo para 4a‖4b, detrás de flag, con retro comparativo | 1 día | Datos antes de decidir |
| P3-3 | Prototipo de empaquetado como plugin (mount v2) | 3–5 días | Distribución/versionado nativos |

**Regla de oro para la evolución**: por cada regla que un hook pase a hacer cumplir, **borrar la prosa equivalente** de los prompts (dejando una línea: "enforced by hook X"). El éxito de P1-2 no se mide solo en fallos evitados sino en líneas de prompt eliminadas.

---

## 9. Cierre de la Parte I

Kuraka no necesita un rediseño: necesita **bajar al harness lo que hoy sostiene con prosa** y ponerse al día con el formato de skills. El contenido — los gates empíricos, la disciplina de evidencia, el meta-aprendizaje harvest/eval — está por delante de la industria; la integración con la plataforma está un año por detrás de lo que la plataforma ya ofrece. Las dos cosas se arreglan sin tocar la arquitectura hub-and-spoke, que sigue siendo la correcta para un pipeline con aprobación humana entre fases.

El plan de implementación detallado (olas, criterios de aceptación, convivencia multi-plataforma) vive en **`ROADMAP-CLAUDE-10.md`**. Lo que sigue es el catálogo concreto de mejoras a los prompts.

---

# Parte II — Catálogo de mejoras de prompts

Reglas del catálogo: ninguna mejora elimina una regla de contenido (todas nacieron de incidentes reales); lo que se elimina es **prosa cuya función pasa al harness** o **peso que no aporta señal**. Cada edición indica el archivo objetivo. Nada de esto toca los renders de Antigravity/Codex/Cursor: los cambios viven en el vault y las plataformas no-Claude reciben el render con los campos Claude-only sustraídos (ver ROADMAP §2).

## 10. Mejoras transversales (aplican a los 13 agentes de pipeline)

### 10.1 Protocolo de digest — cierra el conflicto "carga tu contexto" vs "no releas"

Hoy cada agente ordena cargar config + stack profile + project layer (pasos 1–4 de su sección Context), mientras `rules/17` T1 ordena al orquestador pre-digerir y prohibir la relectura. Cuando llega el digest, el agente tiene dos instrucciones en conflicto — y los retros muestran que relee (fases 2/2.5/3 a 1,9× de presupuesto). Insertar este bloque estándar **al inicio de la sección Context de cada agente**:

```markdown
> **Digest protocol:** if your prompt contains a `## Context digest` header, treat
> steps 1–2 below as ALREADY EXECUTED: do not re-read `kuraka.config.yaml` or the
> stack profile unless the digest is genuinely ambiguous for a specific decision —
> and if you do re-read, name the ambiguity in your report. Steps 3–4 (project
> layer, artifacts) still apply unless the digest includes them explicitly.
```

Una fuente (el bloque se genera; ver ROADMAP §2.3), trece inserciones.

### 10.2 Convención "enforced-by-harness" — la prosa se borra cuando el hook existe

Cada regla que un hook pase a hacer cumplir se sustituye en el prompt por una línea:

```markdown
*(Enforced by harness — hook `<nombre>`. Do not spend turns verifying this; if the
hook rejects your action, fix and retry.)*
```

Candidatas inmediatas (tras la Ola 2 del roadmap): la disciplina de telemetría en `kuraka-policies.md` (~40 líneas → 4), gate-integrity T7 en policies + rules/17 (~35 líneas → 6), la "Output Validation" final de cada agente (~8 líneas × 13 → 2 × 13), el protocolo de violación del orquestador en `kuraka.md` §Orchestrator constraint (queda la constraint, se va el protocolo de 4 pasos). **Métrica de éxito: líneas eliminadas, no añadidas.**

### 10.3 Compactación del tejido cicatricial

Los prompts acumulan la narrativa completa de cada incidente (REQ-20260703 aparece 6+ veces con su historia). La regla se queda; la narrativa se muda:

- Crear `agents/contexts/EVIDENCE.md` — registro por incidente (id, qué pasó, coste, reglas que originó).
- En los prompts, cada regla conserva solo la cita corta: `(evidence: REQ-20260703 → EVIDENCE.md)`.
- Target: −25–30 % de líneas en los agentes >200 líneas (`amauta` 303, `arki` 297, `e2e-tester` 267, `final-auditor` 249, `story-refiner` 234, `po-analyst` 225) **sin eliminar ninguna regla**.

Beneficio doble: menos tokens por invocación y más señal por línea (el modelo obedece mejor 20 reglas nítidas que 20 reglas envueltas en 6 historias).

### 10.4 Descriptions como triggers de enrutamiento

La `description` es el criterio con el que Claude decide delegar, y se carga en **toda** sesión del consumidor. Formato objetivo: 1–2 frases "Use when…", sin codename, sin política interna, sin entregables. Ejemplos de reescritura:

| Agente | Hoy | Propuesta |
|---|---|---|
| `provider-contract-validator` | 834 chars (política read-only, 3 entregables, codename, casos de uso) | "Validates an insurer's Postman collection against its spec and the repo's provider code; produces a prioritized findings report plus a corrected collection/environment. Use when onboarding or migrating a provider API contract." |
| `sentry-resolver` | 727 chars | "Triages Sentry issues for the backend: decomposes error funnels into root causes, cross-checks git for existing fixes, and files follow-ups. Use when the user asks to review or triage Sentry." |
| `deploy-diagnostician` | 681 chars | "Two modes: maintain per-project deploy runbooks, or diagnose deploy/runtime failures by locating the error before theorizing. Use for deploy docs or when a deployment breaks." |

Ahorro: ~60 % de los ~2K tokens fijos por sesión. El detalle eliminado ya vive en el body de cada agente (donde sí se lee al invocarlo).

### 10.5 Política de idioma única

Core en inglés, ayllu en español, `rules/17` mitad y mitad. No rompe nada, pero duplica el coste de mantener terminología (BLOCKER/bloqueante, gate/compuerta) y complica el harvest. Decisión recomendada: **inglés para todo lo que se monta** (los modelos siguen instrucciones técnicas marginalmente mejor en inglés y el vocabulario de severidades ya es inglés); el español queda para docs de usuario (`00-RESTAURAR…`, README). Aplicarlo de forma oportunista: cada archivo que se toque por otra razón se unifica, no como big-bang.

## 11. Mejoras por archivo

### 11.1 `skills/kuraka.md` (orquestador)

1. **Mapa de agentes on-demand.** Los 7 ayllu no aparecen en ningún mapa; el orquestador no tiene criterio central de cuándo existen. Añadir tras "Conditional agents":

   ```markdown
   ### On-demand agents (outside the phase map)
   | Agent | Invoke when | Never during |
   |---|---|---|
   | `pentest-auditor` | user asks for a whole-app security audit | a normal cycle (5.5 covers the diff) |
   | `sentry-resolver` | user asks to triage Sentry issues | — |
   | `deploy-diagnostician` | deploy runbook work or a deploy/runtime failure | — |
   | `provider-contract-validator` | provider API contract validation/migration | — |
   | `migration-deployability` | before merging a branch with migrations to a deploy branch | — |
   | `checkmarx-remediation` | a Checkmarx scan needs analysis/remediation plan | — |
   | `jira-ticket-sync` | user asks to sync/see pending Jira tickets | — |
   ```
2. **Corregir la incoherencia 8 vs 11 fases**: `commands/kuraka.md` describe "11-phase workflow"; `kuraka.md` define 8 (con subfases). Unificar el conteo (recomendado: "8 phases + subphases", en ambos).
3. Tras la Ola 2: sustituir el "Protocol if violated" del §Orchestrator constraint por la línea enforced-by-harness (10.2).

### 11.2 `skills/kuraka-policies.md`

1. **§Model Routing** (obsoleta, H3): sustituir la tabla entera por:
   ```markdown
   ## Model Routing
   Model↔agent assignments are governed centrally in the vault's `MODEL-ROUTING.yaml`
   (tiers: frontier/heavy/balanced/fast) and applied by `kuraka-apply-models.py`.
   NEVER hand-edit a `model:` frontmatter line — change the tier in the map and re-apply.
   Current assignments: see each agent's frontmatter (authoritative after apply).
   ```
2. **Reconciliar timeout**: "Max 10 minutes per invocation" contradice la sección de liveness (agente sano de 7 h, REQ-20260801). Sustituir por: *"No fixed wall-clock timeout. Health is judged by the liveness protocol (poll files, ≥2 polls ≥10 min apart), never by duration. Escalate to the user only when liveness fails."*
3. **Telemetría / tool-use caps**: tras la Ola 2, reducir a la definición del esquema + la línea enforced-by-harness; el cap de tool-uses pasa a `maxTurns` (frontmatter) y la tabla de acciones >1×/2×/3× se queda como guía de *interpretación*, no de captura.

### 11.3 `agents/code-reviewer.md` y `agents/security-reviewer.md` — juicio caro, mecánica barata

De los 9 "Directed checks" del code-reviewer, 5 son greps deterministas (design tokens, single-submit, namespace type-imports, sibling-guard restatements, cache-namespace enumeration); los greps de secret-scan del security-reviewer son 5 comandos fijos. Un modelo frontier gastando turnos en greps es el desperdicio inverso al de un haiku juzgando arquitectura.

- Crear `kuraka-artifacts/scripts/review-mechanics.sh` (greps parametrizados por config) que el **orquestador** corre a ~0 tokens y cuyo output entra al digest del reviewer como tabla de resultados.
- En los prompts: cada check mecánico se reformula como *"adjudicate the pre-run result in the digest (rerun only if the digest lacks it)"* — el reviewer **juzga** los hallazgos del grep (falsos positivos, severidad), no los ejecuta.
- Los checks de juicio (contract cross-check semántico, scope-fidelity, silent deviation, severity adjudication) quedan intactos: eso es lo que el fable debe hacer.

### 11.4 `agents/e2e-tester.md` — desajuste modelo/prompt

267 líneas sobre haiku. Dos opciones, en orden:
1. **Recortar a ~120 líneas** (scope + patrones esenciales + gate); mover el resto a `contexts/e2e-tester-rules.md` que ya existe para eso. Medir un ciclo.
2. Si el cumplimiento sigue flojo: subir el tier en `MODEL-ROUTING.yaml` (balanced), nunca editando el frontmatter.

### 11.5 `agents/final-auditor.md` — memoria nativa

Tras habilitar `memory: project` (Ola 4): el "Prior-Retro Application Check" deja de reconstruirse releyendo el RETRO anterior — el auditor mantiene en su memoria de agente el ledger de patches pendientes y contadores de `OPEN FRAMEWORK DEBT`, y el check pasa a ser "reconcilia tu ledger contra la realidad (grep de evidencia)", más barato y más difícil de perder entre ciclos.

### 11.6 Skills (en la migración a `SKILL.md`, Ola 3)

Frontmatter a añadir por tipo:

| Skill | Frontmatter |
|---|---|
| Fases internas (`analyze-requirement`, `implement-story`, `review-implementation`, `plan-tests`, `generate-*`, `verify-output`, `schema-freeze`, `refine-stories`, `review-stories`, `security-audit`, `run-audit`, `verify-deployment`, `validate-coverage`, `analyze-testability`, `write-tests`, `requirement-consistency-check`) | `disable-model-invocation: true` + `user-invocable: false` — solo las carga quien debe (agente vía `skills:` o lectura dirigida); dejan de contaminar el auto-discovery y el menú `/` |
| `kuraka`, `kuraka-modes`, `kuraka-policies` | `disable-model-invocation: true`; el punto de entrada sigue siendo el comando `/kuraka` |
| Utilitarias del orquestador (`compact-context`, `detect-patterns`, `gap-analysis`) | `context: fork` — corren con contexto limpio y devuelven solo el resultado |
| `facilitate-discovery`, `diagnose-deploy`, `seed-project-conventions` | invocables (`user-invocable: true`), con `argument-hint` |

Además: retirar de los frontmatter los campos no estándar `agent:` y `phase:` (Claude Code los ignora; la información ya está en el body como "Workflow Position") o moverlos a texto del body.

### 11.7 Agentes — frontmatter de capacidades (gobernado, no manual)

La matriz completa (`tools`/`disallowedTools`/`maxTurns`/`skills`/`memory`) se define en `AGENT-HARNESS.yaml` y la aplica `kuraka-apply-harness.py` (mismo patrón que MODEL-ROUTING) — ver ROADMAP §2.2. Nunca editar esos campos a mano.

### 11.8 `rules/` y `contexts/`

- `rules/17` y `rules/19`: retirar `alwaysApply: true` (Cursor-ism inerte) cuando el bloque gestionado en el CLAUDE.md del consumidor importe la 19 (Ola 3). Anotar en 17 qué reglas T pasaron a hooks (T0-medición → hook telemetría; T7-pipes → hook gate-integrity), conservando la explicación del *porqué*.
- `contexts/README.md`: regenerar separando "reglas de framework (16–19, siempre presentes)" de "reglas de proyecto (01–15, existen solo si el consumidor las tiene — verificar con `ls` antes de mapear)". Fecha y tabla actuales inducen tool calls a archivos inexistentes fuera de sie_v2.

### 11.9 Documentación del vault

- CLAUDE.md / README: 16 → **23 agentes** (13 pipeline + 3 entrada + 7 on-demand).
- `kuraka-policies.md` §tooling y `00-RESTAURAR…`: sin cambios de fondo; revisar menciones a "mount converts wikilinks" ya obsoletas si aparecen.
