# Kuraka — Personal Development Agent System

<p align="center">
  <img src="assets/kuraka-logo.png" alt="Kuraka" width="240">
</p>

> **Kuraka** (Quechua, *kuraq* = "el mayor"): líder local que coordinaba
> especialistas (quipucamayocs) bajo un plan mayor. Aquí es el orquestador de
> agentes de IA que dirigen el ciclo de desarrollo.

Sistema portable de agentes especializados para Claude Code. Se monta en
cualquier proyecto (nuevo o existente) mediante `mount-kuraka.sh`, detecta
stack con `kuraka-inspect.py`, y orquesta un workflow de 8 fases con 18
agentes. Reduce ~55% de tokens por ciclo vs. un workflow ingenuo (y más con
RTK activo: 70–90% en operaciones de dev).

**Lo que aporta el diseño actual:**
- **Aprendizaje cross-proyecto**: cada ciclo audita (RETRO) y se respalda al
  vault central; `pattern-detector` consolida si un fallo es de un proyecto o
  de todos, y se ajustan los agentes/skills base (las "4 olas" de optimización —
  ver `KURAKA-OPTIMIZATION-REPORT.md`).
- **Store central unificado** (`projects/<slug>/`): conserva la historia de
  Kuraka de cada proyecto **fuera del git de la solución**; al cambiar de rama
  se restaura sin perder nada (`kuraka-backup.py` / `kuraka-restore.py`).
- **Componentes recomendados** (RTK, ui-ux-pro-max, Playwright MCP…) que el
  instalador sugiere y detecta — ver `RECOMMENDED-COMPONENTS.md`.

---

## Arquitectura: vault ↔ proyecto

El repo Kuraka es un **vault** (fuente de la verdad). No contiene código de
aplicación — contiene las definiciones de agentes, skills, commands y rules
que se *montan* en cualquier proyecto consumidor.

```mermaid
flowchart LR
    subgraph Vault["🪢 Kuraka Vault (este repo)"]
        direction TB
        VA["agents/<br/>18 .md"]
        VS["skills/<br/>26 .md"]
        VC["commands/*.md"]
        VR["rules/16-18.md"]
        VK["kuraka-artifacts/<br/>docs + tests + stack-profiles"]
        VSC["scripts py/sh<br/>mount · init · backup · restore"]
    end

    subgraph Project["📦 Consumer Project"]
        direction TB
        PA[".claude/agents/"]
        PS[".claude/skills/"]
        PC[".claude/commands/"]
        PR[".claude/rules/"]
        PD["docs/process/"]
        PT["tests/kuraka/"]
        CC([Claude Code<br/>runtime])
    end

    Vault ==>|"mount-kuraka.sh<br/>[[link]] → ` `"| Project
    Project -.->|"sync-obsidian.sh hook<br/>` ` → [[link]]"| Vault
    PA & PS & PR & PC --> CC

    style Vault fill:#f5f0e8,stroke:#8b7355
    style Project fill:#e8f0f5,stroke:#3a6b8b
    style CC fill:#fff4a3,stroke:#b89200
```

- **Flecha sólida** (`mount-kuraka.sh`): copia del vault al proyecto, convierte
  wikilinks de Obsidian `[[name]]` → backticks `` `name` `` que Claude Code espera.
- **Flecha punteada** (`sync-obsidian.sh` via hook): reversión al vault, con
  guard del 80% para evitar pisar el baúl si el `.claude/` del proyecto está
  incompleto (p.ej. tras un `git switch`).
- `commands/*.md` se copia verbatim en ambos sentidos — nunca usa wikilinks.

---

## Instalación — paso a paso por sistema operativo

**Requisitos** (todos los SO): **Python 3** y **git** en el PATH. Kuraka no tiene
dependencias `pip` — son scripts Python/shell puros. El mount es Python (sin
`rsync`/bash), así que corre igual en macOS, Linux y **Windows nativo (sin WSL)**.

Hay dos formas de instalar en cada SO: **(A)** una línea en un equipo nuevo (clona
solo), o **(B)** desde un repo que ya descargaste/clonaste. Elegí una.

---

### 🍎 macOS · 🐧 Linux

**A) Equipo nuevo — un comando** (clona a `~/.kuraka` + pone `kuraka` en el PATH):

```bash
curl -fsSL https://raw.githubusercontent.com/xaman1990/kuraka/main/install.sh | bash
#   (carpeta a elección:  ... | bash -s -- ~/dev/kuraka )
```

**B) Ya lo descargaste/clonaste** — desde adentro del repo:

```bash
cd /ruta/a/kuraka
git submodule update --init --recursive     # si clonaste sin submódulos
bash install.sh
```

**Después (ambos casos):**

```bash
# 1. abrí una terminal NUEVA   (o:  source ~/.zshrc)
# 2. verificá
kuraka doctor
# 3. (recomendado) RTK — ahorra 70–90% de tokens
brew install rtk && rtk init -g
```

---

### 🪟 Windows (PowerShell)

**A) Equipo nuevo — un comando** (clona a `%USERPROFILE%\.kuraka`):

```powershell
irm https://raw.githubusercontent.com/xaman1990/kuraka/main/install.ps1 | iex
```

**B) Ya lo descargaste (ZIP o clon)** — desde adentro de la carpeta:

```powershell
cd C:\ruta\a\kuraka
git submodule update --init --recursive     # solo si es un clon git (opcional)
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

**Después (ambos casos):**

```powershell
# 1. CERRÁ y abrí una terminal PowerShell NUEVA  (para tomar PATH + variables)
# 2. verificá
kuraka doctor
```

> **Notas Windows.** El instalador setea `KURAKA_VAULT` (variable de usuario) y
> agrega el vault al PATH. El CLI es `kuraka.cmd` → `kuraka.py`. `git` es opcional
> si instalás desde una copia ya descargada (el mount es Python puro; sin git solo
> se pierde el etiquetado por rama). El banner a color se ve en **Windows
> Terminal**; en la consola vieja cae a ASCII (esperado).

---

### Montar Kuraka en tu proyecto (igual en los 3 SO)

Una vez instalado el CLI, desde **la carpeta de tu solución**:

```bash
cd /ruta/a/tu-proyecto          # Windows:  cd C:\ruta\a\tu-proyecto
kuraka mount                    # monta acá (o:  kuraka mount /otra/ruta)
```

`kuraka mount` (interactivo) te deja elegir el **entorno** (Claude Code / Codex /
Cursor / Antigravity) y **qué categorías** montar, detecta los **MCP** instalados,
avisa si ya hay **historia guardada** en el vault (y ofrece restaurarla), y al
terminar imprime el **catálogo de comandos `/`** con la **guía de inicio**.

Para Claude Code: **reiniciá la sesión** (`/exit` + `claude`) después de montar —
los subagentes se registran solo al inicio de sesión.

**Comandos del CLI** (mismos en todos los SO):

```text
kuraka mount [dir]           montar/actualizar aquí (o en dir) — Claude Code
kuraka mount --target codex|cursor|antigravity [dir]   otros entornos de IA
kuraka init  [dir]           instalación completa (inspect+config+skeleton+mount+registro)
kuraka update                actualizar el framework del proyecto actual
kuraka backup | restore      respaldar / restaurar historia contra el store central
kuraka inspect | discover | dashboard | validate | doctor
```

> `kuraka init` hace la instalación guiada del proyecto (config + capa
> `.claude/project` desde el código real) y al final **lista los componentes
> recomendados y detecta cuáles ya tenés**.

> **Fallback manual** (sin instalador): seteá `KURAKA_VAULT` a la ruta del vault y
> corré los scripts directo — `python3 $KURAKA_VAULT/kuraka-mount.py <dir>`
> (cross-platform) o `bash $KURAKA_VAULT/mount-kuraka.sh <dir>` (Unix).

---

## Flujo de uso completo (ciclo de vida)

```mermaid
flowchart TD
    I["1 · Instalar (una vez)<br/>curl …/install.sh | bash  +  RTK (rtk init -g)"] --> M
    M["2 · Montar en el proyecto<br/>kuraka mount  (o kuraka init)<br/>↳ ofrece restaurar historia del central"] --> R["3 · Reiniciar Claude Code<br/>(/exit + sesión nueva → registra subagentes)"]
    R --> O["4 · Onboarding (1ª vez)<br/>/kuraka-wizard → /amauta (brownfield)<br/>o inti→arki (greenfield)"]
    O --> C["5 · Trabajar un requerimiento<br/>/kuraka → 8 fases (o modo reducido)"]
    C --> A["6 · Cierre de ciclo (Phase 7)<br/>final-auditor: RETRO + telemetría<br/>↳ kuraka-backup.py → store central"]
    A --> L["7 · Aprendizaje cross-proyecto<br/>pattern-detector consolida → ajustes al vault"]
    L -->|nuevo ciclo| C
    A -.->|cambio de rama| SW["git switch + mount-kuraka<br/>↳ '¿restaurar historia? s/n' (kuraka-restore.py)"]
    SW --> C
    L -.->|mejoras del framework| U["/kuraka-update en cada solución<br/>baja agentes/skills/commands nuevos"]
    U --> C

    style I fill:#fff4a3
    style A fill:#c7f0c7
    style L fill:#f5f0e8
    style SW fill:#e8f0f5
    style U fill:#d5f0d5
```

| Paso | Qué corre | Resultado |
|------|-----------|-----------|
| 1. Instalar (una vez) | `curl -fsSL …/install.sh \| bash`, `rtk init -g` | clona el vault + CLI `kuraka` en el PATH + `KURAKA_VAULT` seteado + ahorro de tokens activo |
| 2. Montar | `kuraka mount` (o `kuraka init`) desde la solución | copia el framework al `.claude/` del proyecto; si hay historia en el central, **ofrece restaurarla** |
| 3. Reiniciar | `/exit` + sesión nueva | Claude Code registra los subagentes/commands |
| 4. Onboarding | `/kuraka-wizard` → `/amauta` (o `inti`/`arki`) | `kuraka.config.yaml` + `.claude/project/` desde el código real |
| 5. Ciclo | `/kuraka` | feature implementada con las 8 fases (o el modo que toque) |
| 6. Cierre | `final-auditor` (Phase 7) | RETRO + telemetría + **backup al store central** (`kuraka-backup.py`) |
| 7. Aprendizaje | `pattern-detector` / `/kuraka-update` | consolida fallos cross-proyecto → ajusta el vault → baja a las soluciones |

**Persistencia fuera del git de la solución:** vos commiteás solo tu código
fuente; lo de Kuraka (REQ, stories, schemas, capa `.claude/project`, RETROs)
queda en el `.claude/`/`docs/process` del proyecto (gitignored) **y** respaldado
en el store central. Al cambiar/crear rama, `mount-kuraka` detecta la historia y
te ofrece re-pegarla — así no se pierde nada aunque nunca subas Kuraka a git.

---

## Componentes

### Agentes (`agents/`, 18 en total)

**Workflow core (13)**:
- `po-analyst` — Phase 1: análisis de requerimiento
- `story-refiner` — Phase 2: refinamiento de stories con AC verificables
- `test-engineer` — Phase 2.5 + Phase 6: test planning + test writing
- `architect-reviewer` — Phase 3: review de stories + schema freeze
- `backend-developer`, `frontend-developer` — Phase 4
- `code-reviewer` — Phase 5: review 6D
- `security-reviewer` — Phase 5.5: OWASP + tenant + auth
- `e2e-tester` — Phase 6.5: Playwright golden path
- `deployment-verifier` — Phase 6.7: docker/env/CI checks
- `final-auditor` — Phase 7: retrospectiva + telemetry
- `migration-reviewer`, `pattern-detector` — conditional

**Bootstrap (3)**:
- `amauta` — brownfield onboarding (lee inspect + muestrea código → genera rules/docs)
- `inti` — greenfield discovery (entrevista → vision + requirements)
- `arki` — greenfield architecture (discovery → stack proposal + scaffolding)

**Seguridad / remediación (2)**:
- `checkmarx-remediation` — abre Checkmarx (Playwright), confirma findings SAST/SCA y remedia
- `pentest-auditor` — auditoría de pentest sobre el cambio

**Model routing**: opus (juicio), sonnet (impl/balanced), haiku (mecánico).

### Skills (`skills/`)

- `kuraka.md` — flujo principal y phase map
- `kuraka-modes.md` — variantes (Bootstrap, Brownfield, Lite, Retroactive, Reducido)
- `kuraka-policies.md` — retry, timeout, telemetry, checkpointing, tooling
- Skills específicos por fase (`analyze-requirement`, `implement-story`, etc.)

### Scripts

| Script | Función |
|---|---|
| `install.sh` / `install.ps1` | **Setup de máquina (una vez)**: registra `KURAKA_VAULT` + pone el CLI en el PATH (Unix / Windows) |
| `kuraka` / `kuraka.py` (+ `kuraka.cmd`) | **CLI único** (bash Unix / Python cross-platform): `mount`/`init`/`update`/`backup`/`restore`/`inspect`/`discover`/`dashboard`/`validate`/`doctor` |
| `kuraka-init.py` | **Instalador one-shot de proyecto**: inspect → config → skeleton → mount → registro + recomienda componentes |
| `kuraka-mount.py` | **Mount canónico cross-platform** (Python puro, sin rsync): copia categorías + overrides + gitignore + registro + catálogo/guía. Corre en macOS/Linux/Windows |
| `mount-kuraka.sh` | Wrapper Unix delgado → `kuraka-mount.py` (mantiene el entrypoint `bash mount-kuraka.sh`) |
| `kuraka-backup.py` | Snapshot del estado Kuraka del proyecto → store central (`layer`+`state`+`cycles`, etiqueta rama) |
| `kuraka-restore.py` | Restaura la historia del central → proyecto (pregunta; no pisa sin `--force`) |
| `kuraka-export.py` | Genera `AGENTS.md` + comandos «/» nativos (`.cursor/commands`, `.agent/workflows`, `.codex/prompts`) para Codex/Cursor/Antigravity (`kuraka mount --target …`) |
| `kuraka-archive.py` | Archiva solo los diagnósticos de ciclo (wrapper cycles-only de backup) |
| `kuraka-discover.py` | Descubre proyectos montados en disco y reconcilia el registro |
| `validate-kuraka.sh` | Valida frontmatter de agentes/skills + refs huérfanas |
| `kuraka-inspect.py` | Detector de stack (backend/frontend/DB/testing/CI/containers, monorepo) |
| `aggregate-telemetry.py` | Dashboard agregado de tokens/tiempo multi-ciclo (compute vs wall-clock) |
| `kuraka_common.py` | Módulo compartido: identidad única (`project_slug`) + rutas del store |

### Rules personales (`rules/`)

Solo las meta-reglas del sistema Kuraka:
- `16-agent-backup.md` — sync a Obsidian vault / backup
- `17-kuraka-token-optimizations.md` — patrones T1–T8 de ahorro de tokens
  (digest, end-only typecheck, mapping-table, gate-integrity, fix-run/reviewer digest…)
- `18-duplication-aware-refactor.md` — refactor consciente de duplicación

Las reglas 01–15 son convenciones de código **específicas del proyecto** y
viven en el git del proyecto, no aquí.

### Artifacts (`kuraka-artifacts/`)

Restaurados a cualquier proyecto via `mount-kuraka.sh`:
- `stack-profiles/` — guía idiomática por stack (`python-fastapi`, `vue-pinia`,
  `angular`, `express`, `react`) + `_template.md` para nuevos
- `docs/process/lessons-learned.md` — lecciones indexadas como `[LL-NNN]`
- `docs/process/agent-telemetry/DASHBOARD.md` — plantilla del dashboard
- `tests/kuraka/` — suite pytest de validación estructural

### Componentes recomendados (`RECOMMENDED-COMPONENTS.md`)

Kuraka funciona sin ellos, pero rinden mucho mejor con:

| Componente | Prioridad | Quién lo usa | Para qué |
|---|:--:|---|---|
| **RTK** (rtk-ai/rtk) | 🔴 | todos los agentes | proxy CLI por hook transparente; 70–90% menos tokens en bash/test/grep |
| **ui-ux-pro-max** | 🟡 | `frontend-developer` | inteligencia de diseño UI/UX |
| **Playwright MCP** | 🟡 | `e2e-tester`, `checkmarx-remediation` | tests de navegador + login en vivo |
| **impeccable** | ⚪ | frontend | auditoría/pulido visual |

`kuraka-init.py` los lista y detecta al instalar. RTK se activa con `rtk init -g`
(hook global) — sin cablear nada en los agentes. Para chequeos byte-exactos de
contrato los agentes usan `rtk proxy <cmd>` (salida cruda, sin truncar).

---

## Flujo Normal: las 8 fases

Ciclo de desarrollo por defecto en proyectos con Kuraka ya montado. Cada fase
tiene un **gate** (aprobación del usuario o checks en verde) antes de avanzar —
el orquestador nunca auto-avanza.

```mermaid
flowchart TD
    Start([📥 REQ o ticket Jira]) --> P1["Phase 1<br/><b>po-analyst</b><br/>📝 analyze-requirement"]
    P1 -->|REQ aprobado| P2["Phase 2<br/><b>story-refiner</b><br/>📋 refine-stories"]
    P2 -->|Stories aprobadas| P25["Phase 2.5<br/><b>test-engineer</b> (planning)<br/>🧪 plan-tests"]
    P25 -->|Test plan aprobado| P3["Phase 3<br/><b>architect-reviewer</b><br/>🏛 review-stories + schema-freeze"]
    P3 -->|Sin BLOCKERS<br/>schema congelado| P4{"Phase 4<br/>Implementación"}
    P4 --> P4a["<b>backend-developer</b><br/>💻 implement-story<br/>ruff + make test"]
    P4 --> P4b["<b>frontend-developer</b><br/>🎨 implement-story<br/>lint + typecheck + test"]
    P4a -->|Checks OK| P5
    P4b -->|Checks OK| P5["Phase 5<br/><b>code-reviewer</b><br/>🔍 review-implementation (6D)"]
    P5 -->|Sin BLOCKER / IMPORTANT| P55["Phase 5.5<br/><b>security-reviewer</b><br/>🔒 security-audit (OWASP)"]
    P55 -->|Sin CRITICAL| P6["Phase 6<br/><b>test-engineer</b> (writing)<br/>✅ generate-unit + endpoint tests"]
    P6 -->|Tests pasan| P65["Phase 6.5<br/><b>e2e-tester</b><br/>🎭 generate-e2e-tests"]
    P65 -->|Playwright OK| P67["Phase 6.7<br/><b>deployment-verifier</b><br/>🚢 verify-deployment"]
    P67 -->|Sin BLOCKER| P7["Phase 7<br/><b>final-auditor</b><br/>📊 run-audit"]
    P7 --> End([📦 Retro + telemetría])

    P3 -.->|Si hay alembic/| MR["<b>migration-reviewer</b><br/>condicional"]

    style Start fill:#fff4a3
    style End fill:#c7f0c7
    style P4a fill:#e8f0f5
    style P4b fill:#f5e8f0
    style P55 fill:#f5d5d5
    style MR fill:#f5f0e8,stroke-dasharray: 3 3
```

**Model routing por fase**: `opus` para juicio (po-analyst, architect-reviewer,
code-reviewer, security-reviewer, final-auditor), `sonnet` para implementación,
`haiku` para mecánico (pattern-detector).

---

## Modos del workflow

No todos los cambios requieren las 8 fases. El Kuraka escala el pipeline al
riesgo real del cambio — decisión **antes** de invocar ningún agente:

```mermaid
flowchart TD
    Start([🆕 Nueva tarea]) --> Q1{¿El proyecto<br/>existe?}
    Q1 -->|No, solo idea| Boot["🌱 <b>Bootstrap</b><br/>inti → arki → Normal"]
    Q1 -->|Sí, sin Kuraka| Brown["🏚 <b>Brownfield</b><br/>kuraka-inspect → amauta → Normal"]
    Q1 -->|Sí, con Kuraka| Q2{¿Superficie<br/>del cambio?}

    Q2 -->|Lógica, DB,<br/>contrato API,<br/>provider, auth| Norm["⚙️ <b>Normal</b><br/>8 fases completas"]
    Q2 -->|UI-only, types-only,<br/>rename mecánico| Red["🎯 <b>Reducido por riesgo</b><br/>3–5 fases seleccionadas"]
    Q2 -->|Trivial: ≤3 archivos<br/>≤50 LOC + 7 criterios| Lite["⚡ <b>Lite</b><br/>3 fases"]
    Q2 -->|Código ya escrito<br/>sin workflow| Retro["⚠️ <b>Retroactive</b><br/>4 fases<br/>anti-pattern, evítalo"]

    Boot -.->|una vez| Norm
    Brown -.->|una vez| Norm

    style Boot fill:#c7f0c7
    style Brown fill:#f5f0e8
    style Norm fill:#e8f0f5
    style Red fill:#fff4a3
    style Lite fill:#d5f0d5
    style Retro fill:#f5d5d5,stroke-dasharray: 3 3
```

| Modo | Cuándo | Fases |
|------|--------|:-----:|
| **Discovery** (Design-Thinking) | Solo una idea, sin requerimiento aún | `facilitate-discovery` (concejo Tinkuy) → po-analyst / inti |
| **Bootstrap** | Proyecto nuevo (solo idea) | `inti` → `arki` → Normal |
| **Brownfield** | Proyecto existente sin Kuraka | `kuraka-inspect` → `amauta` → Normal |
| **Normal** | Cambio en proyecto con Kuraka | 8 fases |
| **Reducido por riesgo** | Cambio estrecho (UI-only, rename, types) | 3–5 fases |
| **Lite** | Trivial (≤ 3 archivos, ≤ 50 LOC, 7 criterios más) | 3 fases |
| **Retroactive** | Código ya implementado (anti-pattern) | 4 fases |

Detalle de criterios y templates por modo en `skills/kuraka-modes.md`.

---

## Comandos slash (dentro del proyecto)

Una vez montado Kuraka y reiniciado Claude Code, estos comandos quedan
disponibles en `.claude/commands/`. Todos son **portables**: resuelven el
vault desde `$KURAKA_VAULT` (con respaldo) y detectan la raíz del proyecto
buscando `.claude/` hacia arriba, así funcionan en cualquier máquina y desde
cualquier subdirectorio.

El mount imprime este catálogo (con la guía de inicio) al terminar, así que no
hace falta recordarlos.

| Comando | Para qué |
|---|---|
| `/kuraka-wizard` | **Asistente de arranque.** Detecta el estado (montado, config, código, greenfield/brownfield) y ejecuta o encamina el siguiente paso correcto. Re-ejecutable: cada corrida avanza una etapa y para limpio en los puntos de reinicio. |
| `/amauta` | **Mapea un proyecto existente** (brownfield) en un paso: corre `kuraka-inspect` si falta y luego invoca al agente `amauta` para generar `kuraka.config.yaml` + `.claude/project/` extrayendo convenciones del código real. |
| `/inti` | **Discovery greenfield.** Entrevista estructurada para un proyecto que solo existe como idea; produce `docs/discovery/vision.md` + `requirements.md`. Antesala de `/arki`. |
| `/arki` | **Arquitectura greenfield.** Toma el discovery de `/inti` y genera stack (3 opciones) + `kuraka.config.yaml` + `docs/arquitectura/` + esqueleto del layer y del árbol fuente. |
| `/kuraka-update` | **Actualiza el framework montado** en este proyecto desde el vault (nuevos agentes/skills/commands/templates). No toca `kuraka.config.yaml`, `.claude/project/` ni `docs/`. |
| `/kuraka-backup` | **Acomoda el proyecto al store central**: snapshotea su estado Kuraka completo (`layer`+`state`+`cycles`+`overrides`) a `projects/<slug>/` del vault. Correr tras `/kuraka-update`; Phase 7 lo corre solo en cada cierre. |
| `/kuraka` | Orquesta un ciclo de desarrollo completo para un requerimiento dado. |

Estos mismos comandos se exportan a **Codex / Cursor / Antigravity** (ver más
abajo), donde se invocan igual con `/` (en Codex, `/prompts:<nombre>`).

> **Importante**: tras `/kuraka-update` (o cualquier mount) hay que reiniciar
> Claude Code (`/exit` + sesión nueva) — agentes, skills y commands se
> registran solo al inicio de sesión.

### Onboarding paso a paso (proyecto existente)

```bash
# 1. Desde la solución (repo recién clonado, sin nada montado):
cd /ruta/al/proyecto
kuraka init        # inspect + config + skeleton + mount + registro + componentes
#   …o solo el mount:  kuraka mount

# 2. Reinicia Claude Code en el proyecto (/exit + sesión nueva)

# 3. En la sesión nueva, deja que el wizard te guíe:
/kuraka-wizard        # → detecta brownfield-sin-config → invoca amauta
#   (o directo: /amauta)

# 4. Aprueba la matriz de convenciones de amauta y resuelve los <TODO>.
#    El proyecto queda listo para /kuraka o para Discovery.
```

### Actualizar un proyecto que ya tenía Kuraka

```bash
cd /ruta/al/proyecto
kuraka update         # trae lo nuevo del vault (rsync --update) → reinicia Claude Code
# (equivalente dentro de Claude Code: /kuraka-update)
```

> **Portabilidad entre máquinas**: el único ajuste por equipo es una línea en
> `~/.zshrc`: `export KURAKA_VAULT="/ruta/donde/clonaste/kuraka"`. Con eso,
> `mount-kuraka.sh`, el alias y todos los comandos slash apuntan al lugar
> correcto. Si no está, caen al respaldo y, si no existe, te avisan en vez de
> fallar en silencio.

---

## Modo Discovery (Design-Thinking — Tinkuy)

Cuando tienes una **idea, no un requerimiento** ("quiero un software de
contabilidad") y quieres discutir las bases del sistema con expertos de
dominio **antes** de definir nada. Es el front-end difuso que se sienta
*antes* de `po-analyst`.

**Cómo se usa**: en la sesión del proyecto, simplemente plantea la idea:

```
Tengo una idea, no un requerimiento todavía: {tu idea}.
Quiero discutir las bases con expertos antes de definir nada.
```

El orquestador corre la skill `facilitate-discovery` (concejo Tinkuy):

1. **D1** — clasifica el dominio y propone 2–4 expertos (p.ej. contador +
   admin-finanzas + un escéptico/usuario). Apruebas el concejo.
2. **D2** — convoca un panel **efímero** (subagentes desechables, **sin
   reinicio**) y corre rondas diverge/converge; conversas con ellos a través
   del facilitador, que sintetiza y te devuelve los conflictos.
3. **D3** — sintetiza `docs/discovery/design-brief-{slug}.md`.
4. **D4** (opcional) — **promueve** los expertos valiosos a agentes
   permanentes en `.claude/project/agents/` (un reinicio los registra).

**Híbrido por diseño**: el panel arranca efímero (cero fricción) y solo los
expertos que valga la pena se vuelven permanentes y reutilizables.

**Guardas**: 2–4 expertos, 2 rondas por defecto, síntesis obligatoria, y todo
reclamo regulatorio/legal/normativo se marca `⚠️ VALIDAR con experto humano`
(el concejo razona sobre estructura, no es fuente de verdad para NIIF/IFRS,
ley tributaria, etc.). El brief alimenta luego a `po-analyst` (proyecto
existente) o a `inti`/`arki` (greenfield). Detalle en
`skills/facilitate-discovery.md`.

---

## Otros entornos de IA (Codex, Cursor, Antigravity)

Kuraka da su orquestación multi-subagente completa en **Claude Code**. Para otros
entornos, `mount` genera la versión **portable** del workflow vía `AGENTS.md` (el
estándar que leen Codex, Cursor, Antigravity, Gemini CLI…):

```bash
kuraka mount --target codex        # AGENTS.md + comandos «/» en .codex/prompts/ (staging)
kuraka mount --target cursor       # AGENTS.md + .cursor/rules/kuraka.mdc + .cursor/commands/
kuraka mount --target antigravity  # Montaje completo en .agents/ (agentes, skills, reglas) + .agent/workflows/ (comandos «/»)
kuraka mount                        # (default) Claude Code → .claude/ completo
```

Además del `AGENTS.md`, cada target recibe los **comandos «/» nativos** del vault,
convertidos al mecanismo de cada herramienta:

| Tool | Comandos en | Se invocan con | Nota |
|---|---|---|---|
| Cursor | `.cursor/commands/*.md` | `/nombre` | por-repo, listo tras montar |
| Antigravity | `.agent/workflows/*.md` y `.agents/` | `/nombre` | por-repo; montaje completo de agentes y skills |
| Codex | `.codex/prompts/*.md` (staging) | `/prompts:nombre` | Codex los lee de tu **home**: `cp .codex/prompts/*.md ~/.codex/prompts/` |

Se exportan todos menos los específicos de sie_v2 (`clean-cases`, `lint`,
`run-tests`) y el `sync-from-vault` (solo Claude). El mount imprime al final el
**catálogo de comandos** disponibles y la **guía de inicio** de tu entorno.

Qué porta y qué no:
- **Porta** (como guía): la disciplina de 8 fases con gates, los no-negociables
  (observar contratos, schema freeze, "green = lint+typecheck+test", green ≠
  working), las convenciones del stack, cada agente convertido en un **rol** que
  el agente único adopta por fase, y los comandos «/».
- **No porta**: el *fan-out automático* de subagentes (es propio del tool `Task`
  de Claude Code). En esos entornos los roles se invocan manualmente.
- **RTK** sí funciona en todos (Cursor, Codex, Gemini CLI…): corré su `rtk init`
  y el ahorro de tokens aplica igual.

Todo se regenera con re-correr el comando; toma el stack/convenciones de
`kuraka.config.yaml` y los roles/comandos del vault.

---

## Store central + backup/restore (historia fuera del git de la solución)

Toda la historia de Kuraka de cada proyecto vive en **un solo directorio** del
vault, `projects/<slug>/` (fusión de los antiguos `cycle-archive/` y
`projects-docs/`):

```
projects/
├── README.md                 (doc)        INDEX.md (catálogo de ciclos)
└── <slug>/                    slug = kuraka.config.yaml project.name (canónico)
    ├── registry.md           ficha: path, stack, modo, status
    ├── backup.yaml           last_backup, last_branch, branches[]
    ├── layer/                snapshot de .claude/project/ (convenciones, lessons, review-checks)
    ├── state/docs-process/   snapshot de docs/process/ (REQ, stories, test-plans, schemas, checkpoints)
    └── cycles/<REQ>/          RETRO + telemetry + meta (diagnósticos por ciclo)
```

- **Identidad única**: el slug sale del `project.name` del config vía
  `kuraka_common.project_slug`, usado por init/backup/restore/archive/discover —
  un proyecto tiene **un solo nombre** en todas las herramientas.
- **Backup** (`kuraka-backup.py`): automático en Phase 7 y on-demand
  (`/kuraka-backup`). Etiqueta la rama en cada ciclo.
- **Restore** (`kuraka-restore.py`): al montar/cambiar de rama, `mount-kuraka`
  pregunta *"¿restauro la historia de `<slug>`?"* y re-pega `layer/` + `state/`
  **sin pisar** lo existente (`--force` para sobrescribir).
- **Aprendizaje cross-proyecto**: `pattern-detector` lee todos los
  `projects/*/cycles/**` para detectar fallos sistémicos (de todos los proyectos,
  no de uno solo) y proponer ajustes al vault base.
- **Política de git**: el store es **solo disco** (`projects/` está gitignored).
  Sobrevive a los cambios de rama de la solución; no se sube con el vault.

**Caso de uso clave** — no perder trabajo al cambiar de rama:

```bash
# Trabajaste en rama-A con Kuraka (REQ, stories, schemas) y NO lo subiste a git.
git switch rama-B          # o git switch -c rama-nueva
mount-kuraka               # detecta historia en el central →
                           #   "¿Restaurar la historia de <slug>? [s/N]"  → s
# todo el histórico vuelve a rama-B; seguís donde quedaste.
```

---

## Qué NO está en este repo

- **Reglas 01–15** de convenciones de equipo (son específicas del proyecto consumidor y viven en el git de ese proyecto)
- **Código de aplicación** de ningún proyecto consumidor — **excepto el Control Plane**
  (`kuraka-control/`), que es la app oficial para gobernar el framework y se distribuye
  como **submódulo git** ([repo](https://github.com/xaman1990/kuraka-control)). Se construye
  *con* Kuraka (dogfood) y gobierna *a* Kuraka (hub-and-spoke).
- **REQs, stories, retros** de ciclos específicos (esos viven en el `kipus/` de cada proyecto)

---

## Estado del arte

Baseline medido en un ciclo de referencia:
**458K tokens** para un restyle de 7 archivos en 3 fases.

Con los patrones T1–T8 aplicados + model routing + agentes nativos registrados:
proyección **~200K tokens** por ciclo equivalente (−55%). Con **RTK** activo
(hook global) se suma 70–90% de ahorro en operaciones de dev (grep/cat/test/git),
complementario a las reglas T (ellas reducen *cuántas veces* leés; RTK reduce el
*costo de cada lectura*).

**Optimización continua basada en datos**: el análisis cross-proyecto de 38
retrospectivas produjo 14 hallazgos comunes y 4 "olas" de mejoras ya aplicadas a
los agentes/skills/rules base (`KURAKA-OPTIMIZATION-REPORT.md`). El loop se
auto-sostiene: `final-auditor` verifica que los parches de la retro anterior se
aplicaron, y `pattern-detector` se auto-dispara cada 5 ciclos.

Telemetría continua vía `aggregate-telemetry.py` (separa compute de wall-clock).

---

## Licencia

Uso personal. Compartible con el equipo bajo acuerdo.

---

*Última revisión: 2026-07-15 (d) — separación patrón/mecánica en los agentes de prueba: `e2e-tester`, `test-engineer` y sus skills quedan 100% stack-agnósticos (0 tokens de framework) y las mecánicas Angular/Material se movieron a `kuraka-artifacts/stack-profiles/angular.md` (nuevas secciones "Unit-test gotchas" y "E2E mechanics": DateAdapter Luxon, stub `_loadDependencies` de transloco, `[attr.aria-label]`/NG0303, `[formcontrolname]`, `mat-select` vía cdk-overlay, datepicker readonly dd/MM, `*appCanAccess` = elemento ausente, paginador con boundaries, gate Karma). Los agentes ahora cargan el stack-profile antes de escribir selectores → portables a React/Vue sin arrastrar Angular. Antes (c): e2e-tester + skill generate-e2e-tests: nuevo "CRUD test playbook" con una receta autocontenida y portable por operación (CREATE/insert con teardown, UPDATE/EDIT round-trip por-campo, DELETE soft-delete sin borrado físico, READ/LIST con shape+denormalizados) para generar TODAS las pruebas correctas en otra solución sin depender de las LLs del proyecto. Antes (b): e2e-tester Strict Rule 14 (inputs de fecha/datepicker son locale-formatted, no ISO; readonly = observe-only) autocontenida + portable sin las LLs del proyecto; nota de portabilidad en las reglas 8–14; misma regla en el skill generate-e2e-tests; nueva LL-020. Antes (a): mejoras a los agentes de pruebas (e2e-tester, test-engineer) y skills con reglas de test contra backend real (auth con refresh tokens rotativos, golden-path STRICT + expected-reds etiquetados, edición por-campo round-trip) y unit tests Angular/Material (DateAdapter Luxon, `_loadDependencies` transloco, `[attr.aria-label]`, gate Karma); LL-016…LL-019 en `projects/clinica-dental-2026/layer/lessons-learned/`. Base: store central `projects/<slug>/` + backup/restore branch-aware + CLI `kuraka`; 18 agentes; stack-profiles angular/express/react.*

---

*Last synced (docs): 2026-07-24 — RETRO-REQ-20260724-admin-rbac-visibility-refinements (GuaiHome Cycle 5).*
