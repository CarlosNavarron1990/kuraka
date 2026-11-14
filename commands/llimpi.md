---
description: "Greenfield step after /arki and before the first /kuraka: build the prototype (every screen by user type and flow, each with its use-case card), register the design in the project layer, close the decisions the prototype assumed, and write docs/plan/vN/ — one checkbox .md per /kuraka cycle with a ready prompt and an R-DERIVA coverage table checked by script. Optional extras: Pencil high-fidelity file, navigable viewer, client PDF."
argument-hint: "[vN]  (opcional: versión del plan, por defecto v1)"
---

# Task: Prototipo, casos de uso y plan de ciclos con llimpi

Seguí la skill `llimpi` (`.claude/skills/llimpi.md`) de punta a punta. La ejecuta el
orquestador (no un subagente): necesita la herramienta de diseño disponible en la sesión
(Pencil MCP, el Artifact tool o HTML local).

Versión del plan: `$ARGUMENTS` (si está vacío, `v1`).

## Paso 1 — Verificar prerequisitos

- Deben existir `docs/discovery/vision.md`, `docs/discovery/requirements.md` y
  `kuraka.config.yaml`. Si falta alguno, PARÁ: corré `/inti` y luego `/arki`.
- Si ya existe `docs/plan/<vN>/00-ROADMAP.md`, avisá y preguntá si se crea una versión nueva.
- Elegí la herramienta de diseño (Paso 0 de la skill). Si el usuario quiere Pencil y el MCP no
  aparece entre las herramientas, ofrecé conectarlo (requiere reiniciar la sesión) o seguir con
  prototipo HTML.

## Paso 2 — Ejecutar la skill

Pasos 0 a 7: herramienta → inventario (confirmar con el usuario) → diseño → exportar
(opcional) → registrar el diseño → cerrar decisiones → plan de ciclos con cobertura → gate.

## Paso 3 — Gate

No marques el proyecto listo para `/kuraka` hasta que el usuario apruebe el prototipo y el plan.
El siguiente paso es `docs/plan/<vN>/C00-preparacion.md` y luego `/kuraka` con el prompt de `C01`.
