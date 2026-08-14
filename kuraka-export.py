#!/usr/bin/env python3
"""kuraka-export.py — render the Kuraka workflow as portable instructions for
non-Claude-Code AI tools (Codex, Cursor, Antigravity) via AGENTS.md and each
platform's native reusable-workflow surface.

Why: Claude Code gets the full multi-subagent orchestration (mount-kuraka.sh).
Codex also supports native custom agents, so its export delegates to rendered
`.codex/agents/*.toml` definitions. Cursor and Antigravity retain the portable
single-thread role checklist.

Invoked via:  kuraka mount --target codex|cursor|antigravity  [dir]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

import kuraka_common as kc

DEFAULT_VAULT = "/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka"
TARGETS = ("codex", "cursor", "antigravity")

# Commands that are sie_v2-project-specific (hardcode `cd sie_v2`) or Claude-only —
# never exported to other tools. sync-from-vault is a Claude-only vault→project
# migration. kuraka-wizard IS exported: it is platform-aware (detects the tool it's
# running in and checks the mount for THAT platform), so it works in every environment.
EXPORT_SKIP = {"clean-cases", "lint", "run-tests", "sync-from-vault", "kuraka-harvest", "kuraka-eval"}

# Cursor and Antigravity expose command files directly. Current Codex releases
# discover project workflows as skills instead (explicitly via `$name` or
# `/skills`), so Codex is handled separately in export_codex_command_skills().
TARGET_CMD_DIR = {
    "cursor": (".cursor", "commands"),
    "antigravity": (".agent", "workflows"),
}
ANTIGRAVITY_MAX = 12000  # per-workflow character limit
CODEX_COMMAND_MARKER = "<!-- kuraka-codex-command-skill -->"
CODEX_ENTRYPOINT_START = "<!-- kuraka-codex-entrypoint:start -->"
CODEX_ENTRYPOINT_END = "<!-- kuraka-codex-entrypoint:end -->"

# Curated short labels + arg hints for the post-mount catalog (single source of
# truth for how commands are advertised). Unknown commands fall back to their
# frontmatter description (truncated).
CMD_ORDER = [
    "kuraka", "kuraka-wizard", "amauta", "inti", "arki",
    "kuraka-backup", "kuraka-update", "checkmarx-remediation", "sync-from-vault",
]
CMD_LABEL = {
    "kuraka": ("<requerimiento>", "Orquestador: ciclo multi-fase completo para un requerimiento"),
    "kuraka-wizard": ("", "Onboarding guiado: detecta tu plataforma + estado y rutea el paso"),
    "amauta": ("", "Brownfield: extrae convenciones del código real → config + layer"),
    "inti": ("[descripción]", "Greenfield: entrevista de discovery para un proyecto sin código"),
    "arki": ("", "Greenfield: arquitectura inicial desde el discovery de inti"),
    "kuraka-backup": ("", "Respalda el estado Kuraka del proyecto al vault central"),
    "kuraka-update": ("", "Actualiza el framework montado desde el vault"),
    "checkmarx-remediation": ("", "Remediación Checkmarx: tickets SAST/SCA/API → informe + checklist"),
    "sync-from-vault": ("", "(solo Claude) migra agents/skills/commands del vault al proyecto"),
}
CODEX_COMMAND_NAMES = tuple(sorted(CMD_LABEL, key=len, reverse=True))


def err(m: str) -> None:
    print(m, file=sys.stderr)


def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split a `---`-delimited YAML frontmatter block from the body. Returns
    ({key: value}, body). Only flat `key: value` pairs are read (enough here)."""
    fm: dict = {}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            block = text[3:end]
            body = text[end + 4:].lstrip("\n")
            for line in block.splitlines():
                m = re.match(r'^\s*([A-Za-z0-9_-]+):\s*"?(.*?)"?\s*$', line)
                if m:
                    fm[m.group(1)] = m.group(2)
            return fm, body
    return fm, text


def adapt_codex_paths(text: str) -> str:
    """Translate Claude paths and command mentions to the Codex projection."""
    text = re.sub(
        r"\.claude/skills/([A-Za-z0-9_-]+)\.md",
        r".codex/skills/\1/SKILL.md",
        text,
    )
    text = (text.replace(".claude/skills/", ".codex/skills/")
                .replace(".claude/rules/", ".codex/rules/")
                .replace(".claude/agents/", ".codex/agents/")
                .replace(".claude/project/", ".codex/project/")
                .replace(".claude/stack-profiles/", ".codex/stack-profiles/")
                .replace(".claude/templates/", ".codex/templates/")
                .replace(".claude/", ".codex/")
                .replace("Requires a Claude Code restart afterward.",
                         "Requires a new Codex session afterward."))
    text = text.replace(
        'kuraka-backup.py" <project-root>',
        'kuraka-backup.py" <project-root> --layer-root .codex/project --skip-overrides',
    )
    for name in CODEX_COMMAND_NAMES:
        text = text.replace(f"/prompts:{name}", f"${name}")
        text = re.sub(
            rf"(?<![A-Za-z0-9_.$/])/{re.escape(name)}(?![A-Za-z0-9_.-])",
            f"${name}",
            text,
        )
    return text


def command_desc(path: Path) -> str:
    """Description of a command: frontmatter `description`, else first non-empty
    body line (trimmed)."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    fm, body = parse_frontmatter(text)
    if fm.get("description"):
        return fm["description"].strip()
    for line in body.splitlines():
        if line.strip():
            return line.strip().lstrip("#").strip()
    return ""


def read_agents(vault: Path) -> list[tuple[str, str]]:
    """(name, description) per vault agent, from frontmatter."""
    out = []
    adir = vault / "agents"
    for f in sorted(adir.glob("*.md")):
        text = f.read_text(encoding="utf-8", errors="ignore")
        nm = re.search(r"^name:\s*(.+)$", text, re.M)
        ds = re.search(r'^description:\s*"?(.+?)"?\s*$', text, re.M)
        name = nm.group(1).strip() if nm else f.stem
        desc = ds.group(1).strip() if ds else ""
        out.append((name, desc))
    return out


def read_agent_tiers(vault: Path) -> tuple[dict[str, str], dict[str, str]]:
    """(agent -> tier, tier -> one-line meaning) from MODEL-ROUTING.yaml.
    Empty dicts if the map is absent (older vaults) — the role table then just
    omits the tier column. Light parse of the fixed shape; no PyYAML."""
    routing = vault / "MODEL-ROUTING.yaml"
    agents: dict[str, str] = {}
    tiers: dict[str, str] = {}
    if not routing.is_file():
        return agents, tiers
    section = None
    for raw in routing.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        s = raw.strip()
        if " #" in s:
            s = s.split(" #", 1)[0].strip()
        if indent == 0:
            key = s.split(":", 1)[0].strip()
            section = key if key in ("tiers", "agents") else None
            continue
        if ":" not in s:
            continue
        k, _, v = s.partition(":")
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if section == "tiers":
            tiers[k] = v
        elif section == "agents":
            agents[k] = v
    return agents, tiers


def read_config(project: Path) -> dict:
    """Best-effort parse of the few kuraka.config.yaml fields we surface."""
    cfg = project / "kuraka.config.yaml"
    d: dict = {}
    if not cfg.exists():
        return d
    top = sub = None
    for raw in cfg.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        key = raw.strip().split(":", 1)[0].strip()
        val = raw.strip().split(":", 1)[1].strip().strip("\"'") if ":" in raw else ""
        if indent == 0:
            top, sub = key, None
            if val:
                d[key] = val
        elif indent == 2:
            sub = key
            if val:
                d[f"{top}.{key}"] = val
        elif indent >= 4 and top and sub:
            if val:
                d[f"{top}.{sub}.{key}"] = val
    return d


def _g(cfg: dict, *keys: str, default: str = "—") -> str:
    for k in keys:
        if cfg.get(k):
            return cfg[k]
    return default


def render_agents_md(project: Path, slug: str, cfg: dict, agents: list[tuple[str, str]],
                     agent_tiers: dict[str, str] | None = None,
                     tier_meanings: dict[str, str] | None = None,
                     target: str = "codex") -> str:
    backend = _g(cfg, "stack.backend.framework", "stack.backend.language")
    frontend = _g(cfg, "stack.frontend.framework")
    lang = _g(cfg, "conventions.naming_language", default="english")
    tenant = _g(cfg, "conventions.multi_tenant", default="false")
    maxf = _g(cfg, "conventions.max_file_loc", default="—")
    maxfn = _g(cfg, "conventions.max_function_loc", default="—")
    if target == "antigravity":
        project_layer_dir = ".agents/project"
        skills_dir = ".agents/skills"
        agents_dir = ".agents/agents"
        has_layer = ((project / ".agents" / "project").is_dir() or (project / ".claude" / "project").is_dir())
    elif target == "codex":
        project_layer_dir = ".codex/project"
        skills_dir = ".codex/skills"
        agents_dir = ".codex/agents"
        has_layer = ((project / ".codex" / "project").is_dir() or (project / ".claude" / "project").is_dir())
    else:
        project_layer_dir = ".claude/project"
        skills_dir = ".claude/skills"
        agents_dir = ".claude/agents"
        has_layer = (project / ".claude" / "project").is_dir()

    if target == "codex":
        def adapt_role_description(text: str) -> str:
            return adapt_codex_paths(text)
        agents = [(name, adapt_role_description(description)) for name, description in agents]

    agent_tiers = agent_tiers or {}
    tier_meanings = tier_meanings or {}
    # When MODEL-ROUTING.yaml is present, the role table gains a "Model tier"
    # column so a non-Claude tool (which picks its own model) knows which roles
    # need its strongest model. Claude Code ignores this — it reads the real
    # `model:` alias from each .claude/agents/*.md frontmatter instead.
    if agent_tiers:
        roles = "\n".join(f"| `{n}` | `{agent_tiers.get(n, '—')}` | {d} |" for n, d in agents)
        roles_header = "| Role | Model tier | What it owns |\n|------|-----------|--------------|"
        order = ["frontier", "heavy", "balanced", "fast"]
        present = [t for t in order if t in tier_meanings] + \
                  [t for t in tier_meanings if t not in order]
        legend_rows = "\n".join(f"- **`{t}`** — {tier_meanings[t]}" for t in present)
        legend = (
            "\n**Model-tier legend** (this tool picks its own model — match the tier: "
            "give `frontier`/`heavy` roles your most capable model, `fast` a cheap one):\n"
            f"{legend_rows}\n"
        )
    else:
        roles = "\n".join(f"| `{n}` | {d} |" for n, d in agents)
        roles_header = "| Role | What it owns |\n|------|--------------|"
        legend = ""

    return f"""# AGENTS.md — Kuraka workflow for `{slug}`

> Auto-generated by `kuraka mount --target …` from the Kuraka vault. Do not edit by
> hand — re-run the command to refresh. Claude Code uses the native multi-subagent
> version under `.claude/`; this file is the portable equivalent for Codex / Cursor /
> Antigravity and any other AGENTS.md-aware tool.

You are working in a project governed by **Kuraka**, a disciplined development
workflow. {"Act as the orchestrator: delegate each phase to the native Codex agent named below, wait for its handoff, then run the gate before continuing." if target == "codex" else "Adopt the relevant role below per phase and follow the gated 8-phase flow as a checklist."}

## Stack

- Backend: **{backend}**  ·  Frontend: **{frontend}**
- Naming language: `{lang}`  ·  multi-tenant: `{tenant}`
- Max file LOC: `{maxf}`  ·  max function LOC: `{maxfn}`
- Full config: `kuraka.config.yaml`. {f"Project-specific conventions, lessons-learned and review-checks live in `{project_layer_dir}/` — READ THEM FIRST." if has_layer else f"No `{project_layer_dir}/` layer yet — run onboarding (amauta) to extract conventions."}

{f'''## Codex/Kuraka Artifacts

- Native Kuraka skills are available under `{skills_dir}/<name>/SKILL.md`.
- Native Kuraka agents are available under `{agents_dir}/<name>.toml`.
- Start the main workflow with `$kuraka <requirement>` or select `kuraka` from
  `/skills`. Codex reserves direct slash commands for its own command set.
- Invoke the named agent sequentially for each phase; pass phase, approved input
  artifact, required skill, allowed paths, and expected output. Wait for its
  `DONE`, `CLARIFY`, `BLOCKED`, or `VALIDATION_FAILED` handoff before any gate.
- Never implement, review, or approve a phase by adopting a specialist role in
  the orchestrator thread. Parallel delegation requires an explicit plan proving
  independent files and a merge order.

''' if target == "codex" else ""}## How to work here — the 8-phase discipline

Run a change through these phases. Each has a **gate**: do not advance until it
passes. Scale down (skip phases) only for trivial changes, and say which you skip.

1. **PO analysis** (role `po-analyst`): restate the requirement; for external
   integrations get the **real captured contract** (payload + auth + events) —
   never invent it; classify config required-vs-defaulted.
2. **Story refinement** (role `story-refiner`): testable acceptance criteria;
   **name the mechanism** for any parse/serialize step; embed structural fixes as
   copy-this snippets, not prose; mark edge-case ACs normative vs illustrative.
3. **Test planning** (role `test-engineer`): plan happy+error+edge per function,
   a full-contract assertion, and ≥1 live-path test for external clients.
4. **Architect review + SCHEMA FREEZE** (role `architect-reviewer`): freeze the
   schema from the **observed runtime contract** (in-vivo probe), not from docs;
   run the suspect write/security path before freezing; treat every nullable
   external field as adversarial; check LOC budgets now, not at review.
5. **Implementation** (roles `backend-developer` / `frontend-developer`): one
   story at a time; **"green" = lint + typecheck + test** (a green test runner is
   NOT a clean build); commit per story.
6. **Code review** (role `code-reviewer`): 6D + the directed contract cross-check
   (implemented bodies vs frozen schema/verbatim, byte-exact); normalize external
   strings before compare; reserve BLOCKER for must-fix-now (use DEFERRED otherwise).
7. **Security review** (role `security-reviewer`): OWASP, tenant isolation, auth,
   no fail-open mock defaults in prod.
8. **Tests + E2E + deploy-verify + FINAL AUDIT** (roles `test-engineer`,
   `e2e-tester`, `deployment-verifier`, `final-auditor`): **green tests ≠ working
   feature** — run a live smoke; write a short retro of what caused rework.

### Non-negotiables (apply in every phase)
- **Observe, don't recall**: contracts/schemas/fixtures come from the running
  system or the file, never from memory. Quote `file:line` for schema claims.
- **Schema freeze before implementation** — no DB/contract changes mid-build.
- **Green build ≠ runtime-correct** — exercise the real path (a live smoke) before
  declaring done; distinguish empty-state from broken-state.
- **User approval between phases** — do not auto-advance through gates.

## Roles ({"delegate by native agent name" if target == "codex" else "adopt the mindset per phase"})

{roles_header}
{roles}
{legend}
## Token saving

If RTK is installed for your tool, its hook compresses command output
automatically (70–90% on grep/cat/test/git). For byte-exact reads (contract
cross-checks) use `rtk proxy <cmd>` so no field is truncated.

## Project specifics

{f"Read `{project_layer_dir}/conventions/*.md`, `{project_layer_dir}/lessons-learned/*.md` and `{project_layer_dir}/review-checks/*.md` — they override the generic guidance above." if has_layer else f"Run the onboarding (amauta) to generate `{project_layer_dir}/` with this project's real conventions."}
"""


def render_cursor_mdc(slug: str) -> str:
    return f"""---
description: Kuraka workflow + conventions for {slug} (8-phase discipline, contract-first, green=lint+typecheck+test)
alwaysApply: true
---

# Kuraka workflow (Cursor)

Follow the full Kuraka discipline described in **`AGENTS.md`** at the repo root.
Key non-negotiables:

- Observe contracts/schemas from the running system or the file — never from memory.
- Schema freeze before implementation; no contract changes mid-build.
- "Green" = lint + typecheck + test (a green test runner is not a clean build).
- Green tests ≠ working feature — run a live smoke before declaring done.
- Adopt the relevant role per phase (po-analyst → architect-reviewer → developers
  → code-reviewer → security-reviewer → final-auditor); see AGENTS.md → Roles.
- Project-specific conventions live in `.claude/project/` — read them first.
"""


def _preamble(target: str) -> str:
    if target == "antigravity":
        return (
            "> **Kuraka — entorno Antigravity.** En Antigravity adoptás vos cada rol secuencialmente en el hilo principal.\n"
            "> **REGLAS DE EJECUCIÓN, TABLA VISUAL Y CONTINUIDAD DEL CICLO:**\n"
            "> 1. **TABLA VISUAL DE ESTADO OBLIGATORIA (`📊 Estado del Workflow`)**: En cada intervención, al inicio del ciclo, al completar cada fase y al cerrar el requerimiento, DEBÉS publicar el desglose visual del progreso:\n"
            ">    ```markdown\n"
            ">    ### 📊 Estado del Workflow\n"
            ">    - [x] Fase 1: PO Analysis (po-analyst) — COMPLETED\n"
            ">    - [x] Fase 2: Story Refinement (story-refiner) — COMPLETED\n"
            ">    - [ ] Fase 2.5: Test Planning (test-engineer) — IN_PROGRESS\n"
            ">    - [ ] Fase 3: Architect Review (architect-reviewer) — PENDING\n"
            ">    - [ ] Fase 3.9: Environment Pre-flight (orchestrator) — PENDING\n"
            ">    - [ ] Fase 4a: Backend Implementation (backend-developer) — PENDING\n"
            ">    - [ ] Fase 4b: Frontend Implementation (frontend-developer) — PENDING\n"
            ">    - [ ] Fase 5: Code Review & Security (code-reviewer + security-reviewer) — PENDING\n"
            ">    - [ ] Fase 6: Tests & Smoke Runtime (test-engineer + orchestrator) — PENDING\n"
            ">    - [ ] Fase 7: Final Audit & Vault Backup (final-auditor) — PENDING\n"
            ">    ```\n"
            "> 2. **EJECUCIÓN EN FOREGROUND — NO USAR BACKGROUND TASKS/SUBAGENTES**: Antigravity NO debe lanzar `manage_task`, `browser_subagent` ni comandos en background para ejecutar las fases de Kuraka. Todo el trabajo se realiza paso a paso en esta conversación activa.\n"
            "> 3. **ADOPCIÓN DE ROLES EN FOREGROUND**: Adoptá vos mismo el rol indicado por fase (`po-analyst` → `story-refiner` → `test-engineer` → `architect-reviewer` → `backend-developer`/`frontend-developer` → `code-reviewer` → `security-reviewer` → `test-engineer` → `final-auditor`).\n"
            "> 4. **MODO PASO A PASO VS MODO AUTOMÁTICO (AUTO-PILOT)**:\n"
            ">    - Al finalizar la Fase 1 (y en las consultas de gate), mostrá la tabla `📊 Estado del Workflow` y preguntá al usuario:\n"
            ">      *¿Cómo querés proceder?*\n"
            ">      *1) Modo Paso a Paso (Manual)*: Te presentaré el resultado de cada fase y esperaré tu aprobación previa antes de avanzar.\n"
            ">      *2) Modo Automático (Auto-pilot)*: Ejecutaré el resto del ciclo secuencialmente en foreground de principio a fin, reportando la finalización de cada fase con la tabla visual `📊 Estado del Workflow` actualizada hasta completar la auditoría final (Fase 7) y el respaldo.\n"
            ">    - Si el usuario selecciona el **Modo Automático (Auto-pilot)** o pide 'ejecutá automático' / 'completa el ciclo', NO te detengas a esperar confirmaciones en los gates intermedios (a menos que ocurra un `BLOCKER` insalvable). Avanzá autónomamente fase por fase, publicando los artefactos y la tabla `📊 Estado del Workflow` actualizada en cada fase.\n"
            "> 5. **FASE 7 OBLIGATORIA (RETRO + AJUSTE DE AGENTES)**: El ciclo NO termina tras pasar las pruebas. Una vez aprobados los tests (Fase 6/6.8), avanzá obligatoriamente a la Fase 7 (`final-auditor` / `run-audit`): redactá el `RETRO`, aplicá los parches de optimización directamente en `.agents/agents/`, `.agents/skills/` o `.agents/project/` para ajustar los agentes en ciclos futuros, y ejecutá `python3 kuraka-backup.py <project-root> --target antigravity`.\n"
            "> 6. Consultá las convenciones en `.agents/project/` o `.claude/project/`, y los skills en `.agents/skills/` o `.claude/skills/`.\n\n"
        )
    if target == "codex":
        return (
            "> **Kuraka — entorno Codex.** Usá `$kuraka` y las skills locales de\n"
            "> `.codex/skills/`. Cuando el flujo requiera un especialista, delegá al\n"
            "> custom agent nativo `.codex/agents/<nombre>.toml`; no adoptes su rol en\n"
            "> el hilo orquestador. Esperá su handoff y aplicá el gate antes de continuar.\n"
            "> Las convenciones locales viven en `.codex/project/`.\n\n"
        )
    return (
        f"> **Kuraka — entorno {target}.** Este entorno no lanza subagentes aislados\n"
        f"> como Claude Code. Cuando un paso pida \"invocar el subagente X\", **adoptá\n"
        f"> vos ese rol** siguiendo `AGENTS.md` (raíz del repo) y el flujo de fases con\n"
        f"> gates. Si existe `.agents/project/` o `.claude/project/`, sus convenciones aplican igual.\n\n"
    )


def transform_command(name: str, text: str, target: str) -> str:
    """Turn a vault command into a portable prompt for `target`. Adapts the arg
    placeholder, prepends the role preamble, and special-cases kuraka-update."""
    fm, body = parse_frontmatter(text)
    desc = fm.get("description") or command_desc_from_body(body)
    arg_hint = fm.get("argument-hint", "")

    body = command_body_for_target(name, body, target)

    # argument placeholder: codex substitutes $ARGUMENTS natively; others don't.
    if target != "codex":
        body = body.replace("$ARGUMENTS", "(los argumentos que escribiste después del comando)")

    if target == "antigravity":
        # Adapt paths from .claude/ to .agents/ for Antigravity environment
        body = body.replace(".claude/skills/", ".agents/skills/")
        body = body.replace(".claude/rules/", ".agents/rules/")
        body = body.replace(".claude/agents/", ".agents/agents/")
        body = body.replace(".claude/project/", ".agents/project/")
        body = body.replace(".claude/stack-profiles/", ".agents/stack-profiles/")
        body = body.replace("subagente", "rol")
        body = body.replace("subagents", "roles")
        body = body.replace("subagent", "role")
        body = body.replace("launching any subagent", "adopting any role")
        body = body.replace("invoking the first subagent", "adopting the first role")
    elif target == "codex":
        # Adapt paths from Claude's native layout to Codex's project-local layout.
        desc = adapt_codex_paths(desc)
        body = adapt_codex_paths(body)

    body = _preamble(target) + body

    if target == "cursor":
        # Cursor commands are plain markdown (filename = command name).
        return body
    # codex + antigravity read a frontmatter block.
    head = ["---", f'description: "{desc}"']
    if target == "codex" and arg_hint:
        head.append(f'argument-hint: "{arg_hint}"')
    return "\n".join(head) + "\n---\n\n" + body


def command_desc_from_body(body: str) -> str:
    for line in body.splitlines():
        if line.strip():
            return line.strip().lstrip("#").strip()[:200]
    return ""


def command_body_for_target(name: str, body: str, target: str) -> str:
    """Return target-specific command content before platform adaptation."""
    if name != "kuraka-update":
        return body
    noun = "skills" if target == "codex" else "comandos"
    return (
        "# Actualizar Kuraka en este proyecto\n\n"
        f"En {target}, refrescá el framework (AGENTS.md + {noun}) re-corriendo\n"
        "el mount desde tu solución:\n\n"
        "```bash\n"
        f"kuraka mount --target {target}\n"
        "```\n\n"
        f"Eso regenera AGENTS.md y los {noun} de este entorno desde el vault.\n"
    )


def adapt_codex_command_semantics(name: str, body: str) -> str:
    """Replace Claude-only execution wording in Codex command entrypoints."""
    body = re.sub(
        r"\(Task tool, `subagent_type: ([A-Za-z0-9_-]+)`\)",
        r"(native Codex custom agent from `.codex/agents/\1.toml`)",
        body,
    )
    replacements = {
        "If the Task call fails": "If Codex delegation fails",
        "Si la Task falla": "Si la delegación de Codex falla",
        "restart Claude Code (`/exit` + new session)": "start a new Codex session",
        "restart Claude Code\n(`/exit` + new session)": "start a new Codex session",
        "reinicie Claude Code (`/exit` + sesión nueva)": "abra una sesión nueva de Codex",
        "subagents register only at session start": "the mounted agent catalog reloads at session start",
        "los subagentes se registran solo al iniciar sesión": "el catálogo de agentes se recarga al iniciar la sesión",
    }
    for old, new in replacements.items():
        body = body.replace(old, new)

    if name == "kuraka-wizard":
        wizard_replacements = {
            "| under `.claude/commands/`, and `.claude/agents/` exists | **Claude Code** |":
                "| under Claude's native command directory, with its native agents present | **Claude Code** |",
            "| Claude Code | `.claude/agents/` (18 .md), `.claude/commands/`, `.claude/skills/` | `kuraka mount`  (elegí Claude) | restart Claude Code: `/exit` + new session (subagents register only at start) |":
                "| Claude Code | native Claude agents, commands and skills | `kuraka mount` (elegí Claude) | restart Claude Code: `/exit` + new session |",
            "| invoked as `/prompts:…` from `~/.codex/prompts/`, `AGENTS.md` exists | **Codex** |":
                "| selected from `/skills` or mentioned as `$kuraka-wizard`, `AGENTS.md` + `.codex/skills/` exist | **Codex** |",
            "| Codex | `AGENTS.md`, and prompts in `~/.codex/prompts/` | `kuraka mount --target codex` (luego copiá `.codex/prompts/*.md` → `~/.codex/prompts/`) | reabrí `codex` |":
                "| Codex | `AGENTS.md`, `.codex/agents/`, `.codex/skills/` | `kuraka mount --target codex` | abrí una sesión nueva de Codex |",
            "differently — Claude Code uses native subagents under `.claude/`; the others adopt\nroles via `AGENTS.md` + native slash-commands.":
                "differently — Claude Code and Codex use native subagents; Cursor and\nAntigravity use their own workspace workflow surfaces.",
            "Once the platform mount is OK, check the project's Kuraka config (the project layer\nlives in `.claude/project/` for **all** platforms — every agent/role reads it):":
                "Once the platform mount is OK, check the project's Kuraka config. In this\nCodex projection, every native agent reads the layer from `.codex/project/`:",
            "In Claude these are `/inti` and `/arki`; in Cursor/Codex/Antigravity, adopt the `inti` then `arki` role.":
                "In Codex invoke `$inti` and then `$arki`; each workflow delegates to its native custom agent.",
            "A Cursor mount has no\n  `.claude/agents/` and that's correct; its \"mount\" is `AGENTS.md` + `.cursor/commands/`.":
                "A Codex mount has `.codex/agents/` and `.codex/skills/`; absence of `.claude/` is expected.",
        }
        for old, new in wizard_replacements.items():
            body = body.replace(old, new)
    elif name == "kuraka-backup":
        body = body.replace(
            'python3 "$VAULT/kuraka-backup.py" "$PROJECT_ROOT"',
            'python3 "$VAULT/kuraka-backup.py" "$PROJECT_ROOT" '
            '--layer-root .codex/project --skip-overrides',
        )
    return body


def _codex_command_body(name: str, body: str) -> str:
    """Adapt a legacy command body to Codex's explicit skill invocation.

    Skills receive the complete user request; Codex does not substitute the
    legacy custom-prompt `$ARGUMENTS` placeholder.
    """
    argument_text = (
        f"the text in the current user request after the `${name}` skill mention"
    )
    body = command_body_for_target(name, body, "codex")
    body = adapt_codex_command_semantics(name, body)
    body = adapt_codex_paths(body)
    return body.replace("$ARGUMENTS", argument_text)


def render_codex_command_skill(name: str, text: str) -> str:
    """Compile a Claude-source command to a project-local Codex skill."""
    fm, body = parse_frontmatter(text)
    desc = adapt_codex_paths(
        fm.get("description") or command_desc_from_body(body)
        or f"Run the Kuraka {name} workflow."
    )
    invocation = (
        f"Select `{name}` from `/skills` or mention `${name}` in the prompt. "
        f"Treat text after `${name}` as this workflow's arguments."
    )
    return (
        "---\n"
        f"name: {name}\n"
        f"description: {json.dumps(desc, ensure_ascii=False)}\n"
        "---\n\n"
        f"{CODEX_COMMAND_MARKER}\n"
        f"# Kuraka command: {name}\n\n"
        f"> Generated from `commands/{name}.md`. {invocation}\n\n"
        f"{_preamble('codex')}"
        f"{_codex_command_body(name, body).lstrip()}"
    )


def add_codex_entrypoint(skill_path: Path, name: str) -> None:
    """Add an idempotent explicit-invocation block to a canonical vault skill."""
    text = skill_path.read_text(encoding="utf-8", errors="ignore")
    if CODEX_ENTRYPOINT_START in text:
        before, _, tail = text.partition(CODEX_ENTRYPOINT_START)
        _, separator, after = tail.partition(CODEX_ENTRYPOINT_END)
        text = before.rstrip() + ("\n\n" + after.lstrip() if separator else "")
    block = f"""{CODEX_ENTRYPOINT_START}
## Codex explicit invocation

Select `{name}` from `/skills` or mention `${name}` in the prompt. Treat any
text after `${name}` in the current user request as the workflow input. Direct
`/{name}` is not a custom command surface in Codex.
{CODEX_ENTRYPOINT_END}"""
    skill_path.write_text(text.rstrip() + "\n\n" + block + "\n", encoding="utf-8")


def _is_vault_skill(vault: Path, name: str) -> bool:
    return ((vault / "skills" / f"{name}.md").is_file()
            or (vault / "skills" / name / "SKILL.md").is_file())


def cleanup_generated_codex_command_files(project: Path) -> int:
    """Remove only legacy prompt/command files carrying Kuraka's generator mark."""
    removed = 0
    generated = re.compile(r"> \*\*Kuraka — entorno [Cc]odex\.")
    for root in (project / ".codex" / "prompts", project / ".codex" / "commands"):
        if not root.is_dir():
            continue
        for path in root.glob("*.md"):
            content = path.read_text(encoding="utf-8", errors="ignore")
            if generated.search(content):
                path.unlink()
                removed += 1
    return removed


def export_codex_command_skills(vault: Path, project: Path,
                                quiet: bool = False) -> int:
    """Compile user-facing Kuraka commands to discoverable Codex skills.

    A command whose name already belongs to a canonical vault skill (currently
    `kuraka`) augments that skill with invocation guidance instead of replacing
    its authoritative body. Unrelated project-authored skills are preserved.
    """
    src_dir = vault / "commands"
    dst_root = project / ".codex" / "skills"
    dst_root.mkdir(parents=True, exist_ok=True)
    exported = 0
    preserved = 0

    for source in sorted(src_dir.glob("*.md")):
        name = source.stem
        if name in EXPORT_SKIP:
            continue
        skill_path = dst_root / name / "SKILL.md"
        if skill_path.is_file() and _is_vault_skill(vault, name):
            add_codex_entrypoint(skill_path, name)
            exported += 1
            continue
        if skill_path.is_file():
            existing = skill_path.read_text(encoding="utf-8", errors="ignore")
            if CODEX_COMMAND_MARKER not in existing:
                preserved += 1
                if not quiet:
                    print(f"   ⚠️  ${name}: skill local existente preservada; comando Kuraka no la reemplazó")
                continue
        skill_path.parent.mkdir(parents=True, exist_ok=True)
        rendered = render_codex_command_skill(
            name, source.read_text(encoding="utf-8", errors="ignore")
        )
        skill_path.write_text(rendered, encoding="utf-8")
        exported += 1

    removed = cleanup_generated_codex_command_files(project)
    if not quiet:
        print(f"   + {exported} comandos Codex → .codex/skills/<nombre>/SKILL.md")
        if preserved:
            print(f"   ℹ️  {preserved} skills locales preservadas por colisión de nombre")
        if removed:
            print(f"   ✓ {removed} prompts/comandos Codex obsoletos retirados")
    return exported


def export_commands(vault: Path, project: Path, target: str, quiet: bool = False) -> int:
    """Render vault commands on the target's native workflow surface."""
    src_dir = vault / "commands"
    if not src_dir.is_dir():
        return 0
    if target == "codex":
        return export_codex_command_skills(vault, project, quiet)
    parent, sub = TARGET_CMD_DIR[target]
    out_dir = project / parent / sub
    out_dir.mkdir(parents=True, exist_ok=True)
    n = 0
    for f in sorted(src_dir.glob("*.md")):
        name = f.stem
        if name in EXPORT_SKIP:
            continue
        rendered = transform_command(name, f.read_text(encoding="utf-8", errors="ignore"), target)
        if target == "antigravity" and len(rendered) > ANTIGRAVITY_MAX:
            print(f"   ⚠️  {name}: {len(rendered)} chars > límite {ANTIGRAVITY_MAX} de Antigravity — truncado.")
            rendered = rendered[:ANTIGRAVITY_MAX - 200] + "\n\n> …(truncado por el límite de Antigravity).\n"
        (out_dir / f.name).write_text(rendered, encoding="utf-8")
        if target == "antigravity":
            alt_dir = project / ".agents" / "workflows"
            alt_dir.mkdir(parents=True, exist_ok=True)
            (alt_dir / f.name).write_text(rendered, encoding="utf-8")
        n += 1
    if not quiet:
        print(f"   + {n} comandos → {parent}/{sub}/")
    return n


def print_catalog(commands_dir: Path, env: str, project: Path | None = None) -> None:
    """Print native command/skill entrypoints and a start guide for `env`."""
    if not commands_dir.is_dir():
        return
    if env == "codex":
        candidates = list(commands_dir.glob("*/SKILL.md"))
        present = {
            path.parent.name for path in candidates
            if (CODEX_COMMAND_MARKER in path.read_text(encoding="utf-8", errors="ignore")
                or path.parent.name in CMD_ORDER)
        }
    else:
        present = {p.stem for p in commands_dir.glob("*.md")}
    ordered = [c for c in CMD_ORDER if c in present] + sorted(present - set(CMD_ORDER))
    print("")
    if env == "codex":
        print('📚 WORKFLOWS CODEX (invocálos con "$" o desde "/skills"):')
    else:
        print('📚 COMANDOS DISPONIBLES (invocálos con "/"):')
    print("")
    for name in ordered:
        arg, label = CMD_LABEL.get(name, ("", ""))
        if not label:
            path = (commands_dir / name / "SKILL.md" if env == "codex"
                    else commands_dir / f"{name}.md")
            desc = command_desc(path)
            label = (desc[:86] + "…") if len(desc) > 87 else desc
        prefix = "$" if env == "codex" else "/"
        invoke = f"{prefix}{name} {arg}".strip()
        print(f"   {invoke:<26} {label}")
    print("")
    _print_start_guide(env, project)


def _print_start_guide(env: str, project: Path | None) -> None:
    proj = str(project) if project else "<proyecto>"
    print("🚀 CÓMO EMPEZAR:")
    print("")
    if env == "claude":
        print(f"   1. cd {proj}")
        print("   2. Abrí Claude Code:  claude")
        print("      (si ya estaba abierto: /exit y sesión nueva — los subagentes se")
        print("       registran solo al iniciar sesión)")
        print("   3. Primer uso:")
        print("      • Proyecto con código, sin config →  /amauta   (brownfield)")
        print("      • Proyecto nuevo (solo idea)       →  /inti  y luego  /arki  (greenfield)")
        print("      • ¿No sabés por dónde empezar?     →  /kuraka-wizard   (te guía)")
        print("      • Ya listo, a trabajar             →  /kuraka <requerimiento>")
    elif env == "cursor":
        print(f"   1. Abrí el proyecto en Cursor:  {proj}")
        print("   2. Reiniciá el chat de Cursor (para que tome AGENTS.md).")
        print("   3. En el chat, tipeá  /  → aparecen los comandos de .cursor/commands/")
        print("   4. Primer uso:")
        print("      • ¿No sabés por dónde empezar?     →  /kuraka-wizard   (detecta plataforma + estado)")
        print("      • Proyecto con código, sin config  →  /amauta          (brownfield)")
        print("      • Proyecto nuevo (solo idea)       →  /inti  y luego  /arki   (greenfield)")
        print("      • Ya listo, a trabajar             →  /kuraka <requerimiento>")
        print("      (En Cursor NO se monta .claude/: el setup es AGENTS.md + estos comandos.)")
    elif env == "codex":
        print(f"   1. Abrí Codex en el proyecto:  cd {proj} && codex")
        print("      Codex carga `AGENTS.md`, agentes nativos desde `.codex/agents/`")
        print("      y skills locales desde `.codex/skills/`.")
        print("      Iniciá una sesión nueva después de cada mount para recargar el catálogo.")
        print("   2. Usá `/skills` para elegir un workflow o mencioná la skill directamente:")
        print("      • ¿No sabés por dónde empezar?  →  $kuraka-wizard")
        print("      • Brownfield →  $amauta     · Greenfield →  $inti + $arki")
        print("      • A trabajar →  $kuraka <requerimiento>")
        print("      Codex reserva `/...` para comandos internos: `/kuraka` no es registrable")
        print("      como alias local. El equivalente nativo es `$kuraka` o `/skills`.")
    elif env == "antigravity":
        print(f"   1. Abrí el workspace en Antigravity:  {proj}")
        print("   2. Invocá los workflows con  /nombre  (leídos de .agent/workflows/). Primer uso:")
        print("      • ¿No sabés por dónde empezar?  →  /kuraka-wizard   (detecta plataforma + estado)")
        print("      • Brownfield →  /amauta     · Greenfield →  /inti + /arki")
        print("      • A trabajar →  /kuraka <requerimiento>")
        print("      (En Antigravity NO se monta .claude/: el setup es AGENTS.md + estos comandos.)")
    print("")


def main() -> int:
    ap = argparse.ArgumentParser(description="Export Kuraka as portable AGENTS.md for non-Claude tools.")
    ap.add_argument("project", nargs="?", help="target project root")
    ap.add_argument("--project", dest="project_opt", help="target project root")
    ap.add_argument("--target", choices=TARGETS, help="codex | cursor | antigravity")
    ap.add_argument("--vault", default=os.environ.get("KURAKA_VAULT", DEFAULT_VAULT))
    ap.add_argument("--name", help="slug override")
    # standalone catalog mode (used by mount-kuraka.sh for the Claude flow)
    ap.add_argument("--catalog", metavar="COMMANDS_DIR",
                    help="only print the command catalog for COMMANDS_DIR and exit")
    ap.add_argument("--env", default="claude",
                    help="environment for the start guide (claude|cursor|codex|antigravity)")
    args = ap.parse_args()

    # --catalog: print the catalog + start guide for a commands dir, then exit.
    if args.catalog:
        cdir = Path(args.catalog).expanduser()
        proj_raw = args.project_opt or args.project
        proj = Path(proj_raw).expanduser().resolve() if proj_raw else None
        print_catalog(cdir, args.env, proj)
        return 0

    if not args.target:
        err("❌ falta --target (codex | cursor | antigravity).")
        return 1

    vault = Path(args.vault).expanduser().resolve()
    if not vault.is_dir():
        err(f"❌ vault no encontrado: {vault}")
        return 1
    project_raw = args.project_opt or args.project
    if not project_raw:
        err("❌ falta la ruta del proyecto.")
        return 1
    project = Path(project_raw).expanduser().resolve()
    if not project.is_dir():
        err(f"❌ proyecto no es un directorio: {project}")
        return 1

    slug = kc.project_slug(project, args.name)
    cfg = read_config(project)
    agents = read_agents(vault)
    agent_tiers, tier_meanings = read_agent_tiers(vault)

    print(f"🧩 kuraka export · target={args.target} · {slug}")
    agents_md = render_agents_md(project, slug, cfg, agents, agent_tiers, tier_meanings, args.target)
    (project / "AGENTS.md").write_text(agents_md, encoding="utf-8")
    print(f"   + AGENTS.md  ({len(agents)} roles, {len(agents_md.splitlines())} líneas)")

    if args.target == "cursor":
        rules_dir = project / ".cursor" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        (rules_dir / "kuraka.mdc").write_text(render_cursor_mdc(slug), encoding="utf-8")
        print("   + .cursor/rules/kuraka.mdc")

    if args.target == "antigravity":
        print("   ℹ️  Antigravity: se generó AGENTS.md. Verificá si tu versión también")
        print("      lee reglas de workspace propias; si es así, avisá para añadir ese target.")

    # Export user entrypoints using this tool's native workflow surface.
    export_commands(vault, project, args.target)

    print("")
    print(f"✅ export {args.target} completo. (Claude Code sigue usando .claude/ vía 'kuraka mount'.)")

    # catalog of available commands + how to start in this environment
    if args.target == "codex":
        catalog_dir = project / ".codex" / "skills"
    else:
        parent, sub = TARGET_CMD_DIR[args.target]
        catalog_dir = project / parent / sub
    print_catalog(catalog_dir, args.target, project)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
