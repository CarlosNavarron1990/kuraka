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
