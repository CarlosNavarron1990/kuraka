# LL-001 — Un fixture que declara su propio esquema no puede detectar la deriva codigo↔BD

**Date**: 2026-08-26 (escrita 2026-08-29, Phase 7 de REQ-20260825-mascotas-del-usuario)
**Cycle / incident**: REQ-20260822-appclient-fase0bis + REQ-20260825-registro-cliente-roto
**Cost**: push roto en produccion desde siempre (`user_device_tokens` jamas existio), un 500
en el registro organico (`tenants.is_active` inventado por un fixture), un token falso en el
registro; dos ciclos de remediacion (~3,4M tokens el par).

## What happened

Tres defectos graves sobrevivieron a suites 100% verdes. phpunit corre en sqlite `:memory:`
y los tests creaban su esquema a mano en `setUp` — el esquema del test era una TRANSCRIPCION
HUMANA del real.

## Root cause

Toda transcripcion deriva. Un fixture que declara su propio mundo no puede, por construccion,
detectar una deriva entre codigo y base de datos: el test y el codigo comparten la misma
alucinacion. No fue UNA capa de silencio sino CUATRO alineadas: (1) tests contra esquema
autodeclarado; (2) deploy sin un solo test; (3) app que capturaba el fallo sin distinguirlo de
un no-op; (4) migracion untracked que ningun `migrate --force` desplegaria.

## The rule that follows from it

El esquema de los tests se DERIVA (dump + migraciones versionadas), nunca se declara.
`Schema::create` en tests solo dentro de `tests/Support/RealSchemaFixtures.php`.

**Corolario (REQ-20260825-mascotas)**: sqlite tampoco valida ENUMs — un literal fuera del ENUM
de MariaDB pasa todos los tests y falla en produccion. Los valores de ENUM se verifican contra
la migracion, no contra el fixture.

## How it is enforced now

- `.claude/rules/20-esquema-real-en-tests.md` (regla de proyecto) + gate de Phase 5
  (`grep -rn "Schema::create" tests/` solo puede matchear en `RealSchemaFixtures.php`).
- Limite asumido: sqlite ≠ MariaDB. El cierre real (job de CI contra la MariaDB del compose)
  sigue PENDIENTE como REQ propio.
