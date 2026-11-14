---
name: validar-pr
description: "Pre-PR gate, local and before the PR exists: merges the branch onto the current base in an isolated clone, runs the project's mechanical checks + official suite only for what the PR touches, then a blind `claude -p` reviewer (no author context, fed the diff + a growing catalogue of typical errors) and, when executable code changes, an end-to-end probe on an isolated stack. Writes `.git/validar-pr/<sha>.md`; a Claude hook blocks `gh pr create|ready` without an APROBABLE report for HEAD. Use before opening or updating a PR, when the hook blocks, or when someone says 'valida la PR' / 'abre la PR' / 'listo para PR'. Not needed per commit."
---

# validar-pr — gate local antes de la PR

**Regla: ninguna PR sin validación completa, y la validación es ANTES de crear la PR, en
local.** Nada corre en la CI (no gasta minutos). La PR llega al revisor humano probada y
pre-revisada; la revisión humana pasa a ser una lectura de confirmación. La IA se usa una vez
por PR (y, al actualizarla, solo sobre lo nuevo). Los commits no ejecutan nada.

> Adoptada en el harvest 2026-11 desde sie-integraciones y guai-agents-platform-azure, donde
> el mismo gate corría idéntico en 4 repos con solo `REPO.md`/`config.sh` propios.

## Piezas — qué es del vault y qué es del proyecto

| Pieza | Dónde vive | De quién |
|---|---|---|
| `scripts/validar-pr.sh`, `comun.sh`, `git-ro.sh`, `stack.sh`, `contexto-pr.py` | `.claude/skills/validar-pr/` (montado) | vault — no se edita en el proyecto |
| `scripts/validar-push.sh` (pre-push: nada directo a ramas protegidas) + `instalar-hooks.sh` (lo activa sin pisar hooks ajenos) | `.claude/skills/validar-pr/scripts/` | vault |
| baterías `test-validar-pr.sh` (piezas comunes, sin Docker) + `test-hook-claude.sh` (`pr_gate.py`) | `.claude/skills/validar-pr/scripts/` | vault — `validar-pr.sh` las corre cuando la PR toca la herramienta |
| `prompt-pr.md` (cómo revisa y entrega el revisor) | `.claude/skills/validar-pr/` | vault |
| `errores-tipicos.md` general | `.claude/skills/validar-pr/` | vault |
| `config.sh` (rama base, clave de tarea, lint, suite, stack aislado) | **capa del proyecto**: `.claude/project/validar-pr/config.sh` | proyecto (plantilla: `config.example.sh`) |
| `REPO.md` (cómo levantar y probar cada tipo de cambio) | `.claude/project/validar-pr/REPO.md` | proyecto |
| `errores-tipicos.md` del repo (lo que ya se coló AQUÍ) | `.claude/project/validar-pr/errores-tipicos.md` | proyecto |
| normativas del equipo (opcional; p. ej. su propio `normativas-check.sh`) | función `vp_normativas` en `config.sh`, script en la capa o en el repo | proyecto |
| hook `pr_gate.py` | `.claude/hooks/` (cableado por el mount, solo Claude) | vault |

La capa del proyecto no la pisa el mount y `kuraka-backup.py` la respalda. Una instalación
vieja con `config.sh` junto a la skill sigue funcionando (se lee como fallback).

**Convivencia con un validar-pr propio del equipo.** Si el repo VERSIONA su propia
`.claude/skills/validar-pr/` (o su `settings.json` ya cablea `validar-pr/scripts/hook-claude`),
esa es la herramienta del equipo: el mount no la pisa y `pr_gate.py` queda inerte (no hay
doble puerta). Para pasarse a la del vault: mover `config.sh`/`REPO.md`/`errores-tipicos.md`
propios a `.claude/project/validar-pr/` y dejar de versionar la copia de la skill.

## Cuándo corre cada cosa

| Momento | Qué se ejecuta | Tokens | Si falla |
|---|---|---|---|
| Una vez por clon | `scripts/instalar-hooks.sh` (activa el pre-push; nunca pisa uno ajeno) | 0 | avisa |
| `git commit` | nada | 0 | — |
| Subir la rama | `validar-push.sh`: solo impide subir directo a una rama protegida | 0 | bloquea la subida |
| Antes de abrir o actualizar la PR | `scripts/validar-pr.sh --crear-pr`, en local | 1 revisión | no crea la PR e imprime el informe |
| Claude va a crear la PR o a subir | hook `pr_gate.py` (PreToolUse Bash): informe APROBABLE de HEAD; sin push a protegida ni `--no-verify` | 0 | bloquea |

`kuraka.config.yaml`:
```yaml
workflow:
  base_branch: develop        # rama base de las PR (si config.sh no fija VP_RAMA_BASE)
  validar_pr:
    enforce_hook: true        # el hook bloquea `gh pr create|ready` sin APROBABLE
```

## Cómo funciona

`validar-pr.sh`, lo barato primero y solo lo que toca la PR:
1. **Copia aislada** (clon local con `.git` propio, no `git worktree`) con el commit fusionado
   sobre la base actual. Conflictos → para y dice cómo resolver.
2. **Normativas, lint/formato y secretos** de lo que cambia la PR frente a la base
   (gitleaks si está instalado + reglas propias).
3. **Suite oficial** solo de las partes que toca la PR (`vp_toca` en `config.sh`). Una PR solo
   de herramientas o docs no lanza la suite. **Si algo de esto falla, no se llama a la IA.**
4. **Revisión con IA, sin contexto del autor**: `claude -p` ligero (sin ajustes, plugins ni
   MCP del usuario), con el diff dentro del prompt, `prompt-pr.md` y las dos listas de errores
   típicos. Lee la tarea (Jira por REST si hay `JIRA_URL`/`JIRA_USER`/`JIRA_TOKEN`; clave
   según `VP_CLAVE_REGEX`) y la PR recortadas. Primera vez: toda la PR; después, solo lo
   nuevo desde la última validación revisada (completa otra vez si se fusionó la base o con
   `--completa`). **Punta a punta** en un stack aislado (`vp*`, proveedores en mock) solo si
   cambia código que se ejecuta.
5. **Informe** en `.git/validar-pr/<sha>.md`. Su PRIMERA línea es la marca que lee el hook:
   `<!-- validar-pr sha=<sha> base=<sha> veredicto=APROBABLE|CAMBIOS -->`. Con `--crear-pr`,
   además publica/actualiza la PR con el informe en la descripción (pasa antes el filtro de
   secretos).

El revisor autónomo solo puede leer (git vía `git-ro.sh`), `docker ps` y manejar el stack
aislado con `stack.sh` (solo proyectos `vp*`, nunca el stack del dev).

**Contrato del stack aislado** (lo usan el revisor y la skill `recorrido-e2e`):

| Comando | Qué hace | Lo define el proyecto en `config.sh` |
|---|---|---|
| `stack.sh arriba <vp…>` / `abajo <vp…>` | levanta / baja el stack aislado (proveedores en mock) | `vp_stack_arriba`, `vp_stack_abajo` |
| `stack.sh url <vp…>` | imprime `VP_BACK_URL=…` y `VP_FRONT_URL=…` (eval-able; solo `127.0.0.1`/`localhost`) | `vp_url` / `vp_front_url`, o `VP_BACK_URL` / `VP_FRONT_URL` fijas |
| `stack.sh http <vp…> MÉTODO /ruta [json] [cabecera…]` | llamada al backend del stack (la URL la arma el script) | `VP_HTTP_EXEC` + `VP_PUERTO_HTTP`, o `vp_url` |
| `stack.sh dc <vp…> exec\|logs\|ps\|top\|port\|images …` | compose acotado al stack aislado | `vp_dc` |

**Modelo**: el tier *frontier* del plan de Claude con que se montó Kuraka
(`.claude/.kuraka-mount-manifest.json` → `claude_plan_models.frontier`): plan **max** →
`fable`, reserva `opus`; **pro/team** → `sonnet`, reserva `haiku`; sin manifest → `opus`,
reserva `sonnet`. Siempre alias. Mandan, en este orden: el entorno
(`VALIDAR_PR_MODELO` / `VALIDAR_PR_MODELO_RESERVA`), `config.sh` (`VP_MODELO` / `VP_MODELO_RESERVA`), el plan.
La reserva solo entra si el principal no llega a responder; si respondió sin veredicto, se da
por CAMBIOS (repetir pagaría la revisión dos veces). Tope de turnos: `VALIDAR_PR_TURNOS`.

**Requisitos**: `claude` con sesión, `gh` con sesión, `docker` si la suite o el stack lo usan,
Python 3, y lo que diga `REPO.md`.

## Qué hacer (dev o agente trabajando para un dev)

1. **Rama** desde la base actual y **sin tracking**:
   `git switch -c tipo/PROJ-123-descripcion --no-track origin/<base>`.
2. **Commits** pequeños; no se comprueba nada en el commit.
3. **Validar**: `bash .claude/skills/validar-pr/scripts/validar-pr.sh [--crear-pr --titulo "<tipo>(<ámbito>): <descripción> (PROJ-123)"]`.
   Si sale CAMBIOS: arreglar, commitear y repetir (incremental).
4. **Falso positivo claro**: no se salta. Se explica en la PR y se propone el ajuste de
   `errores-tipicos.md` del repo, `REPO.md` o `config.sh` en una PR aparte.

### Como agente, además
- Nunca crear la PR saltándose `validar-pr.sh`: el hook lo bloquea sin informe APROBABLE.
- No lanzar la validación tras cada commit: una vez, cuando la rama está lista para PR.
- **`workflow.commit_policy: user`** (el equipo hace las mutaciones de git): lanzar
  `validar-pr.sh` **sin** `--crear-pr` y entregar el informe; `pr-writer` redacta la
  descripción con su tabla de Verificación tomada de ese informe.
- No decir «probado» sin haber ejecutado la prueba. Separar lo EJECUTADO de lo LEÍDO.

## Cómo mejora sin crecer en coste

Cuando un revisor humano o la CI encuentre algo que la validación debió cazar, se añade **una
línea** al `errores-tipicos.md` del repo con la comprobación general (no el caso concreto). Si
la línea vale para cualquier proyecto, se propone al vault (harvest) para la lista general.

## Adopción en un proyecto

1. `mkdir -p .claude/project/validar-pr && cp .claude/skills/validar-pr/config.example.sh .claude/project/validar-pr/config.sh`
2. Completar `config.sh` (rama base, `VP_CLAVE_REGEX`, `vp_lint_rapido`, `vp_suite_oficial`, y
   el stack aislado si hay punta a punta) y escribir `REPO.md`.
3. `bash .claude/skills/validar-pr/scripts/instalar-hooks.sh` (pre-push; no pisa hooks ajenos).
4. `bash .claude/skills/validar-pr/scripts/test-validar-pr.sh` (batería, sin Docker) y una
   validación en una rama de prueba; el informe debe salir en `.git/validar-pr/`.
5. Para apagar el bloqueo del hook sin desinstalar nada: `workflow.validar_pr.enforce_hook: false`.

## Lecciones de las propias herramientas (no repetirlas)

- La copia es un clon local con `.git` propio: el `.git` de un worktree apunta a una ruta del
  host que no existe dentro de los contenedores de la suite.
- El `npm ci` de la copia va con `HUSKY=0` (si no, escribe `core.hooksPath` en la config
  compartida del clon del dev).
- El informe pasa el filtro de secretos antes de publicarse: el revisor leyó texto de
  terceros (tarea, PR).
- Solo cuenta la primera línea del informe para el hook: el texto del revisor podría citar
  la marca de aprobado.
- El hook falla **en cerrado** solo sobre lo que vigila: si no puede leer el comando o no hay
  git para leer HEAD, bloquea `gh … pr …` y `push`; todo lo demás pasa. En Windows lee el
  JSON en UTF-8 (un mensaje de commit con acentos no se podría comprobar).
- Las comprobaciones de commit se quitaron: fallaban por entorno en Windows y, en un merge,
  daban por nuevo lo que venía de la base. Todo va antes de la PR.
- Una subida sin destino manda la rama actual o su upstream: una rama creada con tracking a
  `develop` empujaba a `develop` sin nombrarla. Crear ramas con `--no-track`.
- Las baterías que crean repos de prueba limpian `git rev-parse --local-env-vars`: dentro de
  un hook de git, `GIT_DIR` apunta al repo REAL.
- El instalador no actúa con `VALIDAR_PR_DENTRO` ni en `validar-pr-wt-*`: la config de git es
  compartida con el clon del dev.
- En Git Bash, `TMPDIR` pasa a ruta Windows (`C:/…`) para Docker Compose y las rutas que van
  al `PATH` vuelven a `/c/…`; Python se busca como `python3`, `python` o `py`.
- Si el modelo principal no responde (saldo, límite, red) entra la reserva; si respondió sin
  veredicto, no se repite (se pagaría dos veces): se da por CAMBIOS.
