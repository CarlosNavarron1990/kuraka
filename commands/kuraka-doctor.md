---
name: kuraka-doctor
description: "Chequea que el estado Kuraka del proyecto esté realmente sano — config, layer, manifest de mount, ajustes de agentes sincronizados con el store central, RETROs archivados, telemetría adjunta y docs/process espejado. Verifica el RESULTADO, no los códigos de salida. Con --fix aplica las reparaciones seguras."
---

# /kuraka-doctor — ¿está fluyendo Kuraka en este proyecto?

Corré esto cuando quieras saber si lo que Kuraka debía dejar escrito está
realmente escrito. Un `kuraka-backup` que termina en 0 no lo prueba: en la
auditoría del store de agosto 2026 **todo** lo que estaba roto había pasado por
un backup verde — 5 proyectos corriendo sin `kuraka.config.yaml`, una suite de
agentes entera respaldada como si fuera "tuning del proyecto", telemetría que
nunca se adjuntó, y un proyecto renombrado con su historia partida en dos slugs.

## Ejecución

```bash
python3 "${KURAKA_VAULT:-/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka}/kuraka-doctor.py" <project-root>
```

Sin argumento usa el directorio actual. Otras formas:

| Comando | Para qué |
|---|---|
| `kuraka-doctor.py <proj>` | diagnóstico de un proyecto (exit 0 = sano, 1 = hallazgos) |
| `kuraka-doctor.py <proj> --fix` | aplica lo reparable y vuelve a chequear |
| `kuraka-doctor.py --all` | todos los proyectos registrados |
| `kuraka-doctor.py --all --brief` | una línea por proyecto |

## Qué revisa

| Chequeo | Qué detecta |
|---|---|
| `registry` | el directorio no está registrado en el store central |
| `config` | falta `kuraka.config.yaml`, o su `project.name` no coincide con el slug que el store ya usa (eso partiría la historia en dos) |
| `layer` | falta la capa de especialización del proyecto |
| `manifest` | falta el mount manifest de una plataforma, o quedó estampado con una suite vieja |
| `overrides` | los ajustes locales a agentes/skills/commands no coinciden con lo que guarda el store |
| `retros` | hay RETROs sin archivar en el vault |
| `telemetry` | hay ciclos con telemetría en el proyecto que no llegó al store |
| `state` | `docs/process` no está espejado |

## Cómo interpretar el resultado

- **Exit 0** — verde, no hay nada que hacer.
- **`--fix` lo resuelve** para `config`, `layer`, `registry`, `overrides`,
  `retros`, `telemetry` y `state`: redacta el borrador de config + esqueleto de
  layer (nunca pisa lo existente), registra, re-sincroniza overrides y corre el
  backup completo. Después vuelve a diagnosticar y te muestra lo que quedó.
- **`manifest` / `suite` piden re-mount**, a propósito: regenerar un manifest
  desde los archivos actuales congelaría como "línea base" un ajuste real del
  proyecto. El arreglo es `python3 kuraka-mount.py <proj> --update`.
- **Un desajuste de slug NO se arregla solo.** Es una decisión de nomenclatura:
  o alineás `project.name` al slug del store, o oficializás el rename con
  `python3 kuraka-merge-project.py <slug-viejo> <slug-nuevo>`, que fusiona la
  historia y deja el alias registrado.

## Dónde corre solo

No hace falta acordarse: está cableado en el ciclo de vida.

- **Al abrir la sesión** — hook `SessionStart` (`session_doctor.py`, solo Claude);
  calla si está todo bien, y si no, muestra los hallazgos como contexto. Nunca
  bloquea.
- **Al arrancar un ciclo** — preflight en `kuraka.md` §Prerequisites.
- **Al cerrar el ciclo** — Fase 7, junto al `kuraka-backup` obligatorio: el gate
  ahora exige RETRO + backup en 0 + doctor verde.
- **En cada mount** — `kuraka-mount.py` lo corre al final.
