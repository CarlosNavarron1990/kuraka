---
name: sentry-triage
description: |
  Triage Sentry issues for guai-platform-backend: sweep active issues,
  decompose a persistent_error funnel into root causes, cross-reference
  against git and the known-errors catalog, and decide resolution.
  Use whenever the user says "revisa Sentry", "qué pasa con este issue",
  "por qué sigue disparando GUAI-PLATFORM-BACKEND-X", "triage sentry".
  Read-only on Sentry unless the user explicitly asks to resolve/assign.
---

# sentry-triage

Turn a Sentry issue (or a sweep) into a resolution decision for
`guai-platform-backend`. Precursor operativo del agente `sentry-resolver`
(spec en `sie_v2/docs/integraciones/sentry/sentry-resolver-agent-spec.md`).

**Depends on:** Sentry MCP tools (`search_issues`, `search_events`,
`get_sentry_resource`, `update_issue`, `analyze_issue_with_seer`). Connection:
org `insurtech-bu`, project `guai-platform-backend` (memoria
`reference_sentry_mcp_config`). Known-error corpus:
`sie_v2/docs/integraciones/sentry/known-errors-guai-backend.md`.

---

## Cuándo usarla

- "Revisa qué hay activo en Sentry esta semana."
- "Este issue está resolved pero sigue disparando, ¿por qué?"
- "Descompón GUAI-PLATFORM-BACKEND-1Y."
- Antes de cerrar un issue de `persistent_error` (nunca cerrar en bloque).

## Método (5 pasos)

### 1. Barrido de lo que está ACTIVO (no de lo nuevo)
`firstSeen:-24h` se pierde regresiones (first-seen viejo, actividad reciente).
Para "qué está activo" usar `search_issues` SIN filtro de firstSeen, con
`sort=freq`, o `lastSeen:-7d`. Sin booleanos `OR`/`AND` (la API los rechaza) —
una consulta por término.

### 2. Descomponer antes de diagnosticar
Un issue de `persistent_error` es un **embudo multi-causa**, no un bug (ver
§0 del catálogo). Su fingerprint agrupa proveedores, `type_message_code` y
causas raíz distintas bajo una huella. Para descomponer:
- `get_sentry_resource` sobre el issue → leer `Extra Data`: `last_error`,
  `type_message_code`, `unique_id` (el prefijo revela el proveedor),
  `retries`, `tenant_id`.
- Muestrear varios eventos (no uno): un `case_id`/`unique_id` compartido entre
  los eventos *más recientes* de dos issues prueba causalidad de ESA
  ocurrencia, no de todo el grupo.

### 3. Clasificar con el catálogo
Cruzar el `last_error` contra la tabla firma→causa
(`known-errors-guai-backend.md` §2). Cada firma mapea a un KE-NN con
clasificación (bug clasificación / config / infra / datos / auth / esperado)
y acción. Si la firma no está en la tabla, es un KE nuevo — añadirlo.

### 4. Cruzar con el código real (obligatorio)
Antes de tratar un issue como "sin arreglar":
- `git log --oneline -20` y `git log HEAD..<rama-integración> | wc -l` — la
  rama puede estar detrás y el fix estar mergeado río arriba (lección DD-1331:
  se trabajó 64 commits por detrás).
- `git log -S "<fragmento del error>"` — ¿existe ya un commit que lo toca?
  (hotfix branches se llaman `hotfix/DD-XXXX-...`).
- `resolved` + `lastSeen` reciente = regresión o falsa resolución. Casi
  siempre significa que la "resolución" cubrió UNA causa del embudo, no todas.

### 5. Decidir y (opcional) actuar
- **No resoluble en bloque** (KE-01) → enlazar sub-causas, no cerrar.
- **Bug de código** (KE-02, KE-05) → abrir/confirmar follow-up con file:line.
- **Config/datos** (KE-03, KE-07) → localizar el origen (grep/seed/contracts),
  no parchear el síntoma.
- **Infra** (KE-04) → si ya se maneja (`_handle_guai_unavailable`), es que la
  detección no cubrió esa forma; si no, esperar/escalar. No marcar resolved.
- **Escritura en Sentry** (`update_issue` para resolver/asignar) SOLO con
  permiso explícito del usuario en el turno actual. Read-only por defecto.

## Anti-patrones (aprendidos a base de golpes)

- ❌ Cerrar `persistent_error` en bloque → reaparece (es multi-causa).
- ❌ Filtrar por `firstSeen:-24h` para "qué está activo" → pierde regresiones.
- ❌ Generalizar causalidad desde un solo evento → los grupos agregan muchas.
- ❌ Diagnosticar sin `git log` → el fix puede estar mergeado y no desplegado.
- ❌ `OR`/`AND` en la query de `search_issues` → HTTP 400.
- ❌ Escribir en Sentry sin permiso del turno.

## Salida esperada

Un veredicto por issue: `{issue_id, KE-NN, clasificación, causa raíz en una
frase, evidencia (event/last_error/file:line), acción, ¿resoluble?}`. Si el
usuario pide, actualizar el issue vía `update_issue`. Registrar cada issue
triado en el LEDGER (ver spec del agente) para no re-triarlo.
