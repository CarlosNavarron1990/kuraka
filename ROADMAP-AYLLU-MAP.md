# Roadmap — El mapa del ayllu en kuraka-control

> **Qué es esto.** El plan para llevar el prototipo del tablero de nodos
> (`kuraka-control-nodos.html`, publicado 2026-08-22) a una vista real de
> **kuraka-control**, encajándolo en lo que ese proyecto ya tiene construido.
> **Cómo se ejecuta:** como ciclos `/kuraka` DENTRO de kuraka-control — este
> documento es la entrada pre-flow (el material del REQ), nunca una licencia
> para escribir la feature a mano desde el vault.
> **Fecha:** 2026-08-22 · **Prototipo:** artifact `bd634131` · **Generador:**
> `kuraka-map.py` (vault).

---

## 1. Diagnóstico: dónde encaja en lo ya avanzado

### 1.1 Estado real de kuraka-control (verificado, 2026-08-22)

| Dimensión | Estado |
|---|---|
| Stack | Monorepo npm workspaces · **frontend** React 18 + Vite + Tailwind 4 + React Query + zustand + react-router · **backend** Express + **gray-matter** + yaml + **chokidar** + zod · **packages/contracts** (zod, seam único) |
| Ciclos cerrados | **S12 — design system** (tokens, `AgentCard`, `GovernanceBadge/Dot`, `MetricCard`, `ProjectCard`, `NavItem`, ruta `Showcase`) |
| Backend | Solo `routes/health.ts`; `services/`, `repositories/`, `domain/`, `lib/` son README placeholders |
| Contratos | `AgentKey` (enum), `Governance`, `ApiError`, `ProjectSummary` |
| Versión montada | `kuraka.lock` → **0.3.4** (2026-06-07). El vault hoy va por 1.1.0+sin-publicar |

### 1.2 El hueco exacto en el build order

`docs/discovery/spec-v1.md` §6 ya reserva el sitio:

| Story | Título | Estado |
|---|---|---|
| S12 | Design system | ✅ hecha |
| S1–S4 | Registry + Project Detail (header, config, layer browser) | pendientes |
| S5 · S7 · S6 | Triage · ACT runner · Telemetría | pendientes |
| **S8** | Resumen/Monitor + **Quipu + live-state watcher (spike first)** | pendiente |
| **S9** | **Agentes catalog + agent detail (governance)** | pendiente ← **aquí encaja** |
| S11 · S10 | Onboard wizard · Cross-project join | pendientes |

**El mapa del ayllu ES S9, reencuadrada**: el "catálogo de agentes" plano se
convierte en un **grafo navegable**, y el "agent detail" gana el **visor de
prompt completo**. No es una story nueva fuera de plan: es la forma que S9
debería tener a la luz del prototipo.

La capa **viva** (nodos que se encienden con ejecuciones reales) NO es S9: es
**S8**. Se construyen en ese orden y la segunda enchufa a la primera.

### 1.3 El hallazgo que desbloquea S8 (lo más importante de este análisis)

`adr-004-live-state-watcher.md` está en estado **spike** con esta frase:

> *"Discovery deja el transporte abierto **y** no define una **fuente de
> eventos**: hoy nada emite «el agente X entró en la fase Y». Es el único
> mecanismo genuinamente nuevo de v1, y tiene dos incógnitas, no una."*

**Esa incógnita ya está resuelta en el vault.** La Ola 2 de la integración
Claude añadió el hook `telemetry_append` (PostToolUse · Task), que escribe
`<docs_process_root>/agent-telemetry/HOOK-LOG.jsonl` — **una línea por cada
invocación real de subagente**, con agente, timestamp, tokens, tool_uses y
session_id, de forma determinista y sin depender de que el orquestador se
acuerde. Eso es exactamente la fuente de eventos que ADR-004 declaraba
inexistente: append-only, por proyecto, y ya la produce el framework montado.

**Acción derivada:** ADR-004 debe revisarse en el ciclo de S8 — la incógnita
#1 (fuente de eventos) pasa a RESUELTA; queda solo la #2 (transporte:
watch+SSE vs polling), que con `chokidar` ya en dependencias es una decisión
menor. Sin esto, S8 seguiría bloqueada por un spike que ya no aplica.

### 1.4 Deudas que este trabajo destapa (arreglar dentro del ciclo)

| # | Deuda | Impacto si no se arregla |
|---|---|---|
| D1 | `AgentKey` en contracts lista **16** agentes; el vault monta **23** | La validación zod **rechazaría** 7 agentes reales (los ayllu on-demand): el grafo vendría incompleto o el endpoint daría 500 |
| D2 | `tokens.css` define 16 tokens `--ag-*` | 7 nodos sin color propio; `AgentCard` resuelve `var(--ag-${key})` → variable inexistente |
| D3 | `kuraka.lock` = 0.3.4 vs vault 1.1.0+dev | El mapa se construiría contra un vault montado sin `skills:`, sin `maxTurns`, sin hooks — la vista se vería vacía de justo lo que la hace útil |
| D4 | El prototipo embebe los prompts (516 KB de HTML) | Insostenible como app: en producto los prompts se sirven **bajo demanda** por endpoint, no embebidos |

D3 es **precondición**: correr `kuraka-update` en kuraka-control antes de
abrir el ciclo (y así de paso se validan los gates de campo pendientes de las
Olas 0–4: HOOK-LOG completo, pipe bloqueado, menú `/` limpio).

---

## 2. Decisión de arquitectura pendiente (llevar al architect-reviewer)

**¿Quién parsea los `.md`: el backend en TypeScript, o `kuraka-map.py` como
subproceso?**

Los ADRs vigentes empujan en direcciones distintas y hay que resolverlo
explícitamente en Fase 3:

- **ADR-003 (live-fs-read)** — las LECTURAS las hace el backend en vivo, en
  cada request, sobre el filesystem del vault y de los proyectos.
- **ADR-005 (script-subprocess-boundary)** — el backend **no reimplementa**
  lógica de scripts del vault: los invoca y expone stdout + exit code. Pero su
  alcance declarado son las **acciones de gobernanza** (mount, validate,
  inspect), no las lecturas.

**Recomendación (a validar en el ciclo):** el backend implementa un
`services/ayllu-map.ts` que **parsea directo** con `gray-matter` (ADR-003),
porque (a) es una lectura, no una acción; (b) no depende de que el vault
montado traiga `kuraka-map.py` — proyectos con versiones viejas seguirían
funcionando; (c) evita un subproceso por request en la vista más navegada.

**Mitigación del riesgo de divergencia** (dos implementaciones del mismo
parseo): el JSON de `kuraka-map.py` se declara **contrato compartido** en
`packages/contracts` (`AylluMap`), y un test de contrato compara la salida de
`python3 kuraka-map.py --out` contra la respuesta del endpoint para el mismo
vault. Si divergen, falla el gate. `kuraka-map.py` sigue siendo la
implementación de referencia y la CLI offline (y la que alimenta el prototipo).

---

## 3. Las tres olas

### Ola A — S9: el mapa estático (el grafo real)

**Precondición:** `kuraka-update` en kuraka-control (D3).

| # | Entregable | Dónde |
|---|---|---|
| A1 | Contrato `AylluMap` (zod): `agents[]` (id, model, maxTurns, tools, disallowed, memory, skills, desc, phase), `edges[]` (from,to,label,src), `skills[]`, `skillLinks[]`, `commands[]`, `hooks[]`, `scripts[]`, `rules[]`, `suite`, `generated` | `packages/contracts/src/index.ts` |
| A2 | **D1**: `AgentKey` regenerado a los 23 agentes reales — mejor aún, dejar de ser enum cerrado y validarse contra el mapa (un agente nuevo en el vault no debe romper el backend) | contracts |
| A3 | **D2**: 7 tokens `--ag-*` nuevos + fallback `--ag-default` para agentes desconocidos | `frontend/src/theme/tokens.css` |
| A4 | `services/ayllu-map.ts` — parseo con gray-matter del frontmatter + los marcadores del cuerpo (`**Phase:**`, `**Receives from:**`, `**Delivers to:**`, `**Trigger:**`; refs con backticks = aristas) | `backend/src/services/` |
| A5 | `GET /api/ayllu/map` (mapa completo, sin prompts) y `GET /api/ayllu/doc/:kind/:id` (**D4**: el `.md` crudo bajo demanda: kind ∈ agent \| skill \| command) | `backend/src/routes/ayllu.ts` |
| A6 | Test de contrato `kuraka-map.py` ↔ endpoint (§2) | `backend` tests |
| A7 | Ruta `/ayllu` — canvas pan/zoom, nodos arrastrables, aristas con flujo direccional, ida y vuelta arqueadas, toggles skills/comandos, ficha lateral, visor de prompt completo (modal) | `frontend/src/routes/Ayllu.tsx` + `components/graph/*` |
| A8 | Reutilizar el design system de S12 (`AgentCard` como contenido del nodo, `GovernanceBadge`, tokens) en vez de estilos nuevos | frontend |
| A9 | Layout persistido por usuario (posiciones arrastradas) en `localStorage` vía zustand; botón "Reordenar" vuelve al layout calculado | frontend |

**Gate de la ola:** el grafo dibuja los 23 agentes y sus relevos leyendo el
vault real; ningún dato hardcodeado; editar un `.md` y recargar cambia el
grafo; los prompts abren bajo demanda.

### Ola B — gobernanza en el grafo (lo que lo hace kuraka-control y no un diagrama)

Aquí el mapa deja de ser documentación y se vuelve **panel de gobierno**,
enganchando con ADR-007 (dos colores) y el subsistema de overrides:

| # | Entregable |
|---|---|
| B1 | Selector de proyecto: el grafo se pinta **en el contexto de un proyecto registrado** |
| B2 | **Tinte de gobernanza por nodo** (ADR-007): framework vs **override del proyecto** — fuente: `<vault>/projects/<slug>/overrides/` + `.kuraka-mount-manifest.json` |
| B3 | Diff del override: al abrir el prompt de un agente tuneado, ver **vault vs proyecto** lado a lado (el visor ya renderiza `.md`; falta el diff) |
| B4 | Badge de **drift de suite** por proyecto (lock vs vault) reutilizando lo de S2 |
| B5 | Nodos "no montados": un agente que el vault tiene y el proyecto no (o al revés) se marca, no se oculta |

**Gate:** abrir dos proyectos distintos muestra grafos distintos donde difieren
sus overrides.

### Ola C — S8: la capa viva (el Quipu)

| # | Entregable |
|---|---|
| C1 | Revisar **ADR-004** con el hallazgo §1.3: fuente de eventos = `HOOK-LOG.jsonl` (decisión: RESUELTA); dejar solo la decisión de transporte |
| C2 | `services/hook-log-watcher.ts` con **chokidar** sobre `docs/process/agent-telemetry/HOOK-LOG.jsonl` de cada proyecto registrado (append-only → leer solo el delta) |
| C3 | Transporte a la UI: **SSE** (`GET /api/ayllu/stream`) — unidireccional, reconexión nativa, sin dependencia nueva |
| C4 | En el grafo: nodo que **se enciende** al ejecutarse su agente; **pulso viajero** en la arista del relevo (ya prototipado); rastro de los últimos N minutos |
| C5 | Barras de presupuesto por nodo leyendo la telemetría curada del REQ (engancha con S6) |
| C6 | Guardas que **reportan**: un bloqueo de `gate_integrity` / `orchestrator_guard` se ve en el grafo (requiere que esos hooks logueen su bloqueo — **cambio en el vault**, ver §5) |
| C7 | Fase actual del ciclo leída del checkpoint (`docs/process/checkpoints/*-state.json`) |

**Gate:** correr un `/kuraka` real en otro proyecto y ver el grafo animarse en
kuraka-control sin recargar.

---

## 4. Secuencia recomendada

```
kuraka-update (D3)  →  Ola A (S9)  →  Ola B (gobernanza)  →  Ola C (S8 · vivo)
                            ↑                                      ↑
                     no depende de S1–S7            conviene tras S6 (telemetría)
                                                    y S2 (drift)
```

**S9 puede adelantarse**: no depende de S1–S7 (lee el vault, no el registro de
proyectos). La Ola B sí quiere S1/S2 (selector y drift ya resueltos). La Ola C
conviene después de S6.

Si el objetivo es tener algo demostrable pronto, **Ola A sola ya es una vista
completa y útil** — y es la que convierte el prototipo en producto.

---

## 5. Trabajo que queda del lado del vault

| # | Tarea | Por qué |
|---|---|---|
| V1 | `kuraka-map.py` — mantenerlo como implementación de referencia + CLI; añadir `--schema` que emita el JSON Schema del contrato | Alimenta el test de contrato (§2) |
| V2 | Que los hooks `gate_integrity` y `orchestrator_guard` **registren su bloqueo** en un log (hoy solo devuelven exit 2 + stderr) | Sin eso, C6 no tiene datos |
| V3 | Considerar que `telemetry_append` incluya la **fase** activa (leyéndola del checkpoint) | Hoy el front la infiere; el dato en origen es más fiable |
| V4 | Publicar el prototipo como referencia de diseño en el ciclo (no como código a copiar) | El código de producto se escribe en el ciclo, con el design system de S12 |

---

## 6. Riesgos

| Riesgo | Mitigación |
|---|---|
| Divergencia entre el parseo TS y `kuraka-map.py` | Test de contrato en el gate (§2) |
| Los marcadores del cuerpo (`**Delivers to:**`) son convención, no esquema — un agente mal formateado desaparece del grafo | El endpoint reporta `unparsed[]`; la UI muestra "N agentes sin relevos declarados" en vez de callarlo |
| Ambición de la capa viva | Ola C es independiente: A y B ya entregan valor sin ella |
| Peso del grafo con muchos nodos | Los prompts ya salen del payload (D4); si hiciera falta, virtualizar el render |

---

## 7. Definición de terminado (la vista completa)

1. Abre en `/ayllu` con **todo encendido**; clic en el fondo vuelve al panorama.
2. Los 23 agentes, sus skills y los comandos salen **del vault real**, sin nada hardcodeado.
3. Cada nodo abre su **prompt completo** bajo demanda.
4. Las aristas muestran **dirección del flujo**, con ida y vuelta diferenciadas.
5. El grafo distingue **framework vs override** en el contexto de un proyecto.
6. Un ciclo real anima el grafo en vivo (Ola C).
7. `npm run lint && npm run typecheck && npm test` en verde, y la vista sobrevive el smoke de Fase 6.8 con un proyecto real.
