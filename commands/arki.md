---
description: "Bootstrap the initial architecture of a greenfield project from inti's discovery docs: invoke the arki agent to propose a stack (3 options), then generate kuraka.config.yaml, docs/arquitectura/ (ADRs), the .claude/project/ layer skeleton and the source tree. Run after /inti, once its discovery docs are approved."
argument-hint: ""
---

# Task: Arquitectura inicial del proyecto con arki

Convertí el discovery de `inti` en fundaciones concretas: stack + `kuraka.config.yaml`
+ `docs/arquitectura/` + esqueleto de `.claude/project/` + directorios fuente, para
que el proyecto quede listo para el primer ciclo `/kuraka`.

**Portabilidad**: el vault se lee de `$KURAKA_VAULT` (fallback al default del autor).

## Paso 1 — Verificar prerequisitos

Deben existir `docs/discovery/vision.md` y `docs/discovery/requirements.md` (los
genera `/inti`). Si NO existen, PARÁ y decile al usuario que corra `/inti` primero.

Si `kuraka.config.yaml` YA existe, avisá: el proyecto ya está bootstrapeado —
preguntá antes de regenerar.

## Paso 2 — Invocar al agente arki

Invocá el subagente **`arki`** (Task tool, `subagent_type: arki`) con estas
instrucciones:

> Leé `docs/discovery/vision.md` + `requirements.md` y los stack-profiles
> disponibles. Proponé **3 stacks candidatos** con tradeoffs (A seguro / B
> recomendado / C ambicioso) y esperá que el usuario elija. Una vez elegido,
> generá `kuraka.config.yaml`, `docs/arquitectura/` (ADRs), el skeleton de
> `.claude/project/` y el árbol fuente que compile vacío. No escribas lógica de
> negocio. Terminá con el Bootstrap Report y `## Confidence`.

Si la Task falla porque `arki` no es un subagente conocido, decile al usuario que
reinicie Claude Code (`/exit` + sesión nueva) y corra `/arki` de nuevo.

## Paso 3 — Relevar el Bootstrap Report

Presentá el stack elegido, lo generado y los próximos pasos. No marques el proyecto
como listo hasta que el usuario apruebe el stack y el scaffolding. El próximo paso
recomendado es `/llimpi`, no `/kuraka`.

## Notas

- Corré esto **una vez**, después de `/inti`. Luego corré **`/llimpi`** (prototipo,
  casos de uso y plan de ciclos en `docs/plan/v1/`) y recién después el primer `/kuraka`
  con el prompt de `C01`. Un proyecto sin interfaz de usuario puede saltar `/llimpi` si el
  usuario lo decide; entonces empezá con `/kuraka <requerimiento>`.
- arki no escribe lógica de negocio — solo bootstrap que compila/corre vacío.
