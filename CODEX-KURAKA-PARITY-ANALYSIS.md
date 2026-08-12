# Analisis de paridad Kuraka para Codex

## Operational Maintenance

Use the vault skill `skills/sync-codex-parity/` after any change to Kuraka's
Claude-source agents, skills, commands, rules, routing, artifacts, or lifecycle
scripts. It turns this analysis into a repeatable Codex synchronization workflow
and requires fixture-based verification that Claude Code and Antigravity output
remain unchanged for Codex-only work.

**Fecha:** 2026-08-11  
**Alcance:** agentes, skills, orquestacion, gates y dependencias montadas por `kuraka mount --target codex`.  
**Restriccion:** no modificar el comportamiento existente de Claude Code ni Antigravity; Codex debe generarse mediante una transformacion especifica del target.

## Estado de implementacion

La fase P0 de este analisis esta implementada en el renderer Codex:

- `kuraka-mount.py` compila cada `agents/<name>.md` a
  `.codex/agents/<name>.toml` con instrucciones completas, sandbox, modelo y
  esfuerzo de razonamiento por tier.
- Las skills se montan como skills reales; los roles ya no se duplican dentro
  de `.codex/skills/`.
- Los comandos de usuario se compilan como skills Codex en
  `.codex/skills/<name>/SKILL.md`; se invocan con `$name` o desde `/skills`.
  Los antiguos `.codex/prompts/` y `.codex/commands/` generados se retiran sin
  borrar archivos locales desconocidos.
- Backup y restore reciben el layer `.codex/project/` de forma explícita. El
  mount Codex no toca el store de overrides Claude; los overrides centrales
  propios de Codex requieren todavía el manifest de destinos generado de P2.
- `AGENTS.md` y las proyecciones Codex de `kuraka` y `kuraka-policies` ordenan
  delegacion secuencial, handoffs estructurados y telemetria sin datos
  inventados.
- `MODEL-ROUTING.yaml` incluye todos los agentes y resuelve los modelos Codex.
- El mount genera `.codex/config.toml` de forma no destructiva y la suite
  estructural comprueba agentes nativos, skills, routing, config y delegacion.

P1 y P2 siguen pendientes: preflight declarativo de MCP por agente, compilador
de agentes dinamicos de discovery, manifest de destinos con hashes, persistencia
central de overrides Codex y una migracion guiada para mounts antiguos. No
bloquean la paridad base del flujo secuencial.

## Conclusion ejecutiva (estado previo)

El montaje actual conserva gran parte del **contenido** de Kuraka, pero todavia no alcanza paridad de **ejecucion** con Claude Code. Codex detecta las instrucciones convertidas a `SKILL.md`, pero los archivos `.codex/agents/*.md` no son agentes nativos. Como consecuencia, el prompt actual pide adoptar cada rol en el hilo principal: se pierden el aislamiento de contexto, el modelo por rol, los limites de permisos, la telemetria por invocacion y la delegacion real.

La correccion principal no consiste en reescribir los agentes fuente. Debe agregarse un compilador Codex que convierta cada `agents/<name>.md` en `.codex/agents/<name>.toml`, manteniendo intactos los `.md` usados por Claude. En paralelo, las skills deben publicarse en `.codex/skills/<name>/SKILL.md`, y el orquestador Codex debe solicitar explicitamente los subagentes correspondientes.

La documentacion y la verificacion contra Codex CLI confirman que:

- Codex carga instrucciones de proyecto desde `AGENTS.md` y aplica precedencia por directorio ([OpenAI Docs: AGENTS.md](https://developers.openai.com/codex/guides/agents-md)).
- Las skills se activan de forma explicita con `$skill` o desde `/skills`, y
  tambien pueden activarse implicitamente mediante `description`
  ([OpenAI Docs: skills](https://developers.openai.com/codex/skills)). En la
  version CLI validada, el mount de proyecto `.codex/skills/` se descubre de
  forma nativa.
- Los agentes de proyecto son TOML bajo `.codex/agents/` y requieren `name`, `description` y `developer_instructions`; pueden configurar modelo, razonamiento, sandbox, MCP y skills ([OpenAI Docs: subagents](https://developers.openai.com/codex/multi-agent)).
- Codex puede delegar cuando el usuario, `AGENTS.md` o una skill lo indica. La delegacion esta habilitada por defecto en versiones actuales.

## Flujo que debe conservarse

Claude ejecuta Kuraka como una cadena controlada:

1. El comando `kuraka` carga `kuraka`, `kuraka-modes`, `kuraka-policies` y las reglas del proyecto.
2. El orquestador inspecciona alcance, propone modo y pipeline, presenta el solution outline y espera aprobacion.
3. Cada fase invoca un agente especializado con contexto aislado y skills concretas.
4. El agente genera un artefacto con el esquema definido en `agents/contexts/output-schemas.md`.
5. El orquestador valida el resultado, registra telemetria, actualiza el checkpoint y presenta el gate al usuario.
6. Solo despues de la aprobacion avanza a la fase siguiente.
7. Implementacion, revision y seguridad permanecen separadas; el smoke runtime precede siempre a la auditoria final.
8. La auditoria produce RETRO, aplica o registra mejoras y respalda el ciclo en el vault.

La version Codex debe mantener esta secuencia. El soporte de subagentes no autoriza paralelizar fases dependientes: solo son paralelizables tareas realmente independientes, como backend/frontend sin archivos compartidos o revisiones de solo lectura.

## Brechas del montaje actual

| Area | Estado actual | Riesgo | Estado requerido |
|---|---|---|---|
| Agentes | Se copian `.md` y tambien se convierten en skills | Codex no los registra como custom agents; todos los roles corren en el hilo principal | Generar `.codex/agents/*.toml` |
| Skills | Se generaban 52 entradas bajo `.codex/skills/` | 23 entradas duplicaban agentes y podian exceder el presupuesto inicial | Montar solo skills reutilizables en `.codex/skills/` |
| Comandos | Se exportaban a `.codex/prompts/` y `.codex/commands/` | Codex CLI no descubre esos archivos ni permite registrar `/kuraka` como alias local | Compilar cada entrypoint a skill; usar `$kuraka` o `/skills` |
| Orquestacion | El preambulo dice "adopta vos ese rol" | Pierde aislamiento, delegacion y ownership de fase | `$kuraka` debe pedir subagentes por nombre y esperar sus resultados |
| Model routing | Codex aparece como recommendation-only | La premisa es obsoleta: custom agents aceptan `model` y `model_reasoning_effort` | Compilar tiers a TOML Codex |
| Permisos | Todos heredan el hilo principal | Un revisor puede editar y un implementador puede exceder alcance | Definir `sandbox_mode` y limites por agente |
| Contextos | Se copian, pero solo como referencias Markdown | Pueden quedar inertes o no leerse | Cada TOML debe ordenar su secuencia de carga y validacion |
| Reglas | `.codex/rules/*.md` no garantiza carga automatica | Gates importantes pueden omitirse | `AGENTS.md` y `$kuraka` deben cargar reglas explicitamente |
| Gates | Resumidos en `AGENTS.md` | El resumen no contiene todos los preflights, checkpoints y fallbacks | La skill `kuraka` sigue siendo la fuente completa |
| Telemetria | Espera un bloque `<usage>` propio de Claude | Codex puede no exponer ese contrato al prompt | Adaptador Codex; nunca inventar tokens faltantes |
| MCP | Dependencias solo se mencionan en prosa | Jira, Sentry, Postman, navegador o docs pueden faltar al ejecutar | Declarar dependencias y hacer preflight |
| Tests | La suite estructural solo valida `.claude/` | Una regresion Codex puede pasar inadvertida | Suite de contrato especifica para Codex |

Un problema adicional es que `migration-deployability` no aparece actualmente en `MODEL-ROUTING.yaml`; por eso queda sin tier en la exportacion. Todo agente montable debe existir exactamente una vez en ese mapa.

## Transformacion requerida para cada agente

Cada `agents/<name>.md` debe seguir siendo la fuente de verdad. Para Codex se debe generar:

```toml
name = "backend-developer"
description = "Implementa historias backend aprobadas durante la fase 4 de Kuraka."
# Sin `model`: hereda el modelo activo de la sesion de Codex.
model_reasoning_effort = "medium"
sandbox_mode = "workspace-write"
developer_instructions = """
<cuerpo completo del agente, con rutas Codex y protocolo de handoff>
"""
```

La transformacion comun debe:

1. Eliminar frontmatter exclusivo de Claude (`color`, alias de modelo Claude).
2. Convertir `.claude/project/` a `.codex/project/`, contextos a una ruta Codex estable y skills a `.codex/skills/`.
3. Mantener completos los checklists, reglas, formatos de salida y evidencia historica del agente; no resumirlos en `AGENTS.md`.
4. Agregar un contrato de invocacion: fase, inputs obligatorios, skills que debe cargar, output esperado y criterio de `BLOCKED`.
5. Prohibir que el subagente avance de fase o dialogue directamente con el usuario. Si necesita una decision, devuelve un `CLARIFY` estructurado al orquestador.
6. Exigir `verify-output` antes del handoff y citar artefactos creados o inspeccionados.
7. Heredar el modelo activo de la sesion de Codex por defecto. El routing solo
   define `model_reasoning_effort`; un `model` por agente requiere validacion
   explicita en la integracion de Codex donde se ejecutara.
7. Separar ownership: el orquestador coordina y ejecuta gates deterministas; nunca implementa codigo salvo las excepciones ya definidas por Kuraka.

## Ajustes por grupo de agentes

### Flujo principal

| Agentes | Ajuste Codex necesario |
|---|---|
| `po-analyst` | Ejecutar primero `requirement-consistency-check`; devolver preguntas al padre en vez de usar `AskUserQuestion`; no crear REQ con BLOCKER abierto. |
| `story-refiner` | Recibir la ruta del REQ aprobado; cargar `refine-stories`; devolver lista exacta de historias y archivos generados. |
| `test-engineer` | El prompt de spawn debe incluir obligatoriamente `mode = TEST_PLANNING` o `TEST_WRITING`; cada modo carga skills y outputs distintos. |
| `architect-reviewer` | Preferir razonamiento alto; ejecutar `review-stories` y `schema-freeze`; no habilitar implementacion hasta emitir freeze verificable. |
| `backend-developer`, `frontend-developer` | `workspace-write`, alcance por historias y rutas autorizadas; el padre espera la finalizacion y corre lint, typecheck y tests en foreground. |
| `code-reviewer`, `security-reviewer` | No modificar codigo. Idealmente `read-only`, devolviendo Markdown estructurado para que el padre persista el reporte sin alterar su contenido. |
| `e2e-tester` | Puede escribir tests, pero no ejecutar gates largos en background; el orquestador corre Playwright y conserva el exit code real. |
| `deployment-verifier` | Separar chequeos read-only de cualquier reparacion; cambios de infraestructura requieren una nueva fase aprobada. |
| `final-auditor` | Leer checkpoint, reportes, smoke y telemetria Codex; marcar metricas no disponibles como `unknown`, nunca `0`; exigir backup antes del cierre. |
| `migration-reviewer` | Invocacion condicional y read-only; se activa solo si el inventario real contiene migraciones. |

### Onboarding y discovery

- `inti`, `arki` y `amauta` deben crear `.codex/project/`, no `.claude/project/`.
- `facilitate-discovery` y los agentes promovidos deben generar `.codex/agents/<slug>.toml`, no Markdown de agente Claude.
- `arki` y `amauta` deben producir la misma superficie de convenciones y glosario, independientemente del target.
- La creacion de un agente dinamico debe validar TOML y avisar que puede requerirse una sesion nueva para asegurar su registro.

### Agentes especializados

- `jira-ticket-sync`: preflight de Jira MCP y modo sin escritura remota salvo autorizacion explicita.
- `sentry-resolver`: dependencia Sentry, lectura por defecto y prohibicion de cerrar o asignar issues sin permiso.
- `provider-contract-validator`: dependencias Postman/documentos, secretos nunca embebidos y smoke limitado a operaciones autorizadas.
- `checkmarx-remediation` y `pentest-auditor`: navegador/herramientas de seguridad declarados; separar auditoria de remediacion.
- `deploy-diagnostician` y `migration-deployability`: inputs de entorno obligatorios, comandos destructivos prohibidos y evidencia del estado real.
- `pattern-detector`: read-only sobre retros; las propuestas framework se registran como deuda y no modifican automaticamente el vault desde un consumidor.

## Skills y dependencias

Las skills reales deben conservar su estructura nativa:

```text
.codex/skills/<skill>/
├── SKILL.md
├── references/      # cuando exista
├── scripts/         # cuando exista
├── assets/          # cuando exista
└── agents/openai.yaml  # opcional: UI, politica y dependencias
```

No conviene publicar nuevamente los 23 agentes como skills: Codex limita el catalogo inicial de skills y puede acortar descripciones u omitir entradas cuando es grande. Los roles deben vivir en `.codex/agents/`; las skills deben representar capacidades reutilizables. Sus `description` necesitan triggers front-loaded y limites claros para que la activacion implicita sea fiable.

Para skills que requieren MCP, `agents/openai.yaml` puede declarar la dependencia. El mount no debe sobrescribir conexiones o secretos del usuario: debe validar disponibilidad, fusionar configuracion de forma estructurada y reportar dependencias faltantes antes de iniciar la fase afectada.

## Orquestador Codex propuesto

`AGENTS.md` debe ser compacto y estable: reglas globales, ubicacion de fuentes y mandato de cargar `$kuraka`. El detalle completo permanece en skills y agentes para aprovechar progressive disclosure.

La skill `$kuraka` para Codex debe usar este protocolo:

1. Cargar `kuraka-modes`, `kuraka-policies`, config, stack profiles, project layer y reglas.
2. Inspeccionar el repositorio y presentar outcome, superficies IN/OUT, preguntas, modo y pipeline.
3. Esperar aprobacion antes del primer spawn.
4. Invocar el custom agent de la fase por nombre con inputs, paths autorizados, skill requerida y output esperado.
5. Esperar al agente; no ejecutar gates sobre un agente activo.
6. Validar output, persistir artefacto, registrar telemetria disponible y actualizar checkpoint.
7. Presentar el gate y detenerse hasta la respuesta del usuario.
8. Reanudar desde checkpoint sin repetir fases aprobadas.
9. Ejecutar preflight 3.9, gates deterministas y smoke 6.8 en el hilo principal.
10. Invocar `final-auditor` solo con smoke completo o una excepcion expresamente aprobada y documentada.

Codex permite subagentes paralelos, pero Kuraka debe mantener secuencia por defecto. Solo se delega en paralelo cuando el plan declara independencia, archivos no compartidos, criterio de reunion y orden de merge. Los reviewers no deben correr mientras un implementador conserva el arbol.

## Routing de modelos y permisos

`MODEL-ROUTING.yaml` debe dejar de tratar Codex como recommendation-only. La compilacion puede resolver por tier:

| Tier Kuraka | Uso | Configuracion sugerida |
|---|---|---|
| `frontier` | freeze, seguridad, review critico, auditoria | modelo mas capaz disponible; reasoning `high` o superior |
| `heavy` | discovery, arquitectura, auditorias amplias | modelo capaz; reasoning `high` |
| `balanced` | implementacion, stories, tests | modelo equilibrado; reasoning `medium` |
| `fast` | checks mecanicos y exploracion acotada | modelo rapido; reasoning `low` o `medium` |

Los nombres concretos deben validarse contra los modelos disponibles para la instalacion/cuenta. Si no se puede resolver un modelo, es mas seguro omitir `model` y heredar el del padre que escribir un identificador invalido. `model_reasoning_effort` puede mantenerse por tier cuando la version instalada lo soporte.

Debe generarse o fusionarse `.codex/config.toml` sin reemplazar configuracion del usuario:

```toml
[agents]
enabled = true
max_concurrent_threads_per_session = 4
```

La concurrencia cuatro es un limite, no una orden de paralelizar el pipeline.

## Telemetria y checkpoints

El contrato actual asume que cada llamada Claude devuelve `<usage>` con tokens, tools y duracion. Esa suposicion no debe trasladarse literalmente. Se propone un adaptador por plataforma:

- Campos siempre disponibles: agente, fase, intento, estado, timestamps, artefactos producidos y resultado del gate.
- Campos opcionales: tokens, tool uses y duracion reportada por la sesion.
- Valor ausente: `null`/`unknown`, nunca cero fabricado.
- Un thread reanudado conserva `thread_id` y registra si la metrica es acumulada o incremental.
- El checkpoint se escribe despues de cada gate y conserva los IDs de threads solo como diagnostico; la reanudacion funcional depende de artefactos, no de que un thread siga vivo.

`aggregate-telemetry.py` y `final-auditor` deben aceptar ambos esquemas sin degradar una ausencia de metrica a trabajo nulo.

## Plan de implementacion propuesto

### P0 - Paridad funcional

1. Crear `render_codex_agent_toml()` y generar todos los agentes en `.codex/agents/*.toml`.
2. Montar skills canonicas en `.codex/skills/` y dejar de duplicar agentes como skills.
3. Cambiar el preambulo Codex: delegar agentes nativos, no adoptar todos los roles en el hilo principal.
4. Adaptar rutas de skills, contextos, project layer, reglas, templates y stack profiles.
5. Convertir `MODEL-ROUTING.yaml` y `kuraka-apply-models.py` para emitir modelo/effort Codex.
6. Fusionar `.codex/config.toml` de forma no destructiva.

### P1 - Confiabilidad

1. Implementar telemetria multiplataforma y resume por checkpoint.
2. Declarar/prevalidar MCP y herramientas por skill o agente.
3. Crear el compilador de agentes dinamicos para discovery.
4. Definir sandbox por rol y contratos `CLARIFY`, `BLOCKED`, `VALIDATION_FAILED` y `DONE`.
5. Mantener `AGENTS.md` compacto y eliminar prompts Codex heredados para evitar instrucciones divergentes.

### P2 - Distribucion y mantenimiento

1. Considerar un plugin Kuraka para distribuir skills, agentes y dependencias de forma versionada.
2. Añadir migracion de mounts Codex antiguos (`.codex/prompts`,
   `.codex/commands` y agentes `.md`) sin borrar archivos personalizados del usuario.
3. Versionar un manifiesto Codex con hashes para distinguir archivos generados de archivos locales.
4. Respaldar y reinyectar overrides Codex usando ese manifiesto, sin compartir
   el namespace de overrides Claude.

## Pruebas de aceptacion

La mejora no debe considerarse completa solo porque los archivos existen.

### Estructurales

- Todos los agentes fuente generan un TOML parseable con los tres campos requeridos.
- No queda ninguna ruta operativa `.claude/` dentro del output Codex.
- Cada skill referenciada existe en `.codex/skills/<name>/SKILL.md`.
- Cada comando exportable existe como skill y no contiene `$ARGUMENTS`, rutas
  `.claude/` ni referencias a `/prompts:<name>`.
- Cada agente aparece exactamente una vez en `MODEL-ROUTING.yaml`.
- Los outputs requeridos tienen schema en `output-schemas.md`.
- El merge de `.codex/config.toml` preserva claves y MCP definidos por el usuario.

### Descubrimiento real

- Codex lista `$kuraka`, `$kuraka-modes` y `$kuraka-policies` desde un proyecto temporal.
- Codex reconoce `po-analyst`, `backend-developer`, `code-reviewer` y `final-auditor` como custom agents, no como skills.
- Un agente recibe su modelo/effort y sandbox esperados.

### Flujo minimo de paridad

1. Ejecutar Kuraka sobre una fixture pequeña.
2. Confirmar que presenta solution outline y pipeline antes de delegar.
3. Confirmar que `po-analyst` se ejecuta en otro thread y produce REQ.
4. Rechazar el gate y verificar que no aparece una historia ni se invoca fase 2.
5. Aprobar y continuar hasta una implementacion pequeña.
6. Verificar que implementador y reviewer son threads distintos.
7. Verificar checkpoint, telemetria, gate command sin pipe, smoke y RETRO.

### Regresion multiplataforma

- Ejecutar las pruebas actuales de Claude sin cambios de snapshots ni frontmatter.
- Ejecutar un mount Antigravity y comparar su arbol con el baseline previo.
- Ejecutar dos mounts Codex consecutivos para comprobar idempotencia y preservacion de customizaciones locales.

## Recomendacion final

La proxima iteracion debe centrarse primero en **agentes TOML nativos + skills canonicas + orquestador con delegation**. Esos tres cambios recuperan la semantica central de Kuraka. Telemetria, MCP y empaquetado son importantes, pero no compensan un pipeline donde todos los roles siguen ejecutandose en el mismo hilo.

La implementacion debe hacerse como un backend de renderizado Codex separado. Los agentes Markdown, skills y reglas del vault continuan siendo la fuente comun; Claude y Antigravity no necesitan cambios para que Codex alcance paridad.
