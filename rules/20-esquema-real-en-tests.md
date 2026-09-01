# Regla 20 — El esquema de los tests se DERIVA, nunca se declara

> Propuesta en RETRO-REQ-20260825-registro-cliente-roto (§6); aplicada en la
> Phase 7 de REQ-20260825-mascotas-del-usuario (2026-08-29).

Motivada por tres defectos que sobrevivieron a suites 100% verdes
(REQ-20260822/REQ-20260825): `user_device_tokens` inexistente en produccion,
`tenants.is_active` inventado por un fixture, y un token falso que ningun test
ejercitaba. Mecanismo comun: phpunit corre en sqlite `:memory:` y los tests
creaban su esquema a mano — el test y el codigo compartian la misma
alucinacion.

1. **PROHIBIDO `Schema::create` en tests fuera de
   `tests/Support/RealSchemaFixtures.php`.** Todo test que necesite una tabla
   la pide al helper; si falta, se ANADE AL HELPER derivandola del dump
   (`petsuite_backup.sql`) o, si el dump no la trae, de la migracion
   versionada — documentando la fuente en el docblock.
   **Gate (Phase 5, code-reviewer)**: `grep -rn "Schema::create" tests/` solo
   puede matchear dentro de `RealSchemaFixtures.php`. Fuera = IMPORTANT.
2. Toda columna NUEVA que el codigo del ciclo referencie se verifica contra el
   esquema real (dump + migraciones versionadas) en Phase 3, con el comando
   pegado en el freeze. "El fixture la tiene" NO es evidencia: el fixture es
   un derivado, no la fuente.
3. La fixture hereda el retraso del dump (`client_vet_affiliations` no estaba;
   se derivo de la migracion `2026_08_08_000001`). Cuando el dump se
   actualice, auditar `RealSchemaFixtures` contra el (tarea de la Phase 6.7).
4. **LIMITE ASUMIDO**: sqlite no es MariaDB (tipos, collations, defaults,
   validacion de ENUM — evidencia nueva de REQ-20260825-mascotas: un
   `source: 'app_explicit'` fuera del ENUM habria pasado en sqlite y fallado
   en MariaDB strict). Esta regla NO cubre esa clase de defectos. El cierre
   real es un job de CI que corra la suite contra la MariaDB del compose —
   REQ propio, pendiente.
