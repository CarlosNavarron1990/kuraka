#!/usr/bin/env python3
"""kuraka-export.py — render the Kuraka workflow as portable instructions for
non-Claude-Code AI tools (Codex, Cursor, Antigravity) via AGENTS.md
(+ .cursor/rules for Cursor).

Why: Claude Code gets the full multi-subagent orchestration (mount-kuraka.sh).
Other tools don't spawn isolated subagents, so here each Kuraka agent becomes a
ROLE/persona the single agent adopts per phase, and the 8-phase discipline plus
the non-negotiable rules become a checklist in one instruction file every
AGENTS.md-aware tool reads.

Invoked via:  kuraka mount --target codex|cursor|antigravity  [dir]
"""

from __future__ import annotations

import argparse
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
EXPORT_SKIP = {"clean-cases", "lint", "run-tests", "sync-from-vault"}

# Where each tool reads its slash-commands from, and how it invokes them.
TARGET_CMD_DIR = {
    "cursor": (".cursor", "commands"),
    "antigravity": (".agent", "workflows"),
    "codex": (".codex", "prompts"),       # staged; user copies to ~/.codex/prompts
}
ANTIGRAVITY_MAX = 12000  # per-workflow character limit

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
                     tier_meanings: dict[str, str] | None = None) -> str:
    backend = _g(cfg, "stack.backend.framework", "stack.backend.language")
    frontend = _g(cfg, "stack.frontend.framework")
    lang = _g(cfg, "conventions.naming_language", default="english")
    tenant = _g(cfg, "conventions.multi_tenant", default="false")
    maxf = _g(cfg, "conventions.max_file_loc", default="—")
    maxfn = _g(cfg, "conventions.max_function_loc", default="—")
    has_layer = (project / ".claude" / "project").is_dir()

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
workflow. Other tools spawn one agent, not many — so **you adopt the relevant
*role* below per phase** and follow the gated 8-phase flow as a checklist.

## Stack

- Backend: **{backend}**  ·  Frontend: **{frontend}**
- Naming language: `{lang}`  ·  multi-tenant: `{tenant}`
- Max file LOC: `{maxf}`  ·  max function LOC: `{maxfn}`
- Full config: `kuraka.config.yaml`. {"Project-specific conventions, lessons-learned and review-checks live in `.claude/project/` — READ THEM FIRST." if has_layer else "No `.claude/project/` layer yet — run onboarding (amauta) to extract conventions."}

## How to work here — the 8-phase discipline

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

## Roles (adopt the mindset per phase)

{roles_header}
{roles}
{legend}
## Token saving

If RTK is installed for your tool, its hook compresses command output
automatically (70–90% on grep/cat/test/git). For byte-exact reads (contract
cross-checks) use `rtk proxy <cmd>` so no field is truncated.

## Project specifics

{"Read `.claude/project/conventions/*.md`, `.claude/project/lessons-learned/*.md` and `.claude/project/review-checks/*.md` — they override the generic guidance above." if has_layer else "Run the onboarding (amauta) to generate `.claude/project/` with this project's real conventions."}
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
            "> **Kuraka — entorno Antigravity.** En Antigravity adoptás vos cada rol secuencialmente.\n"
            "> **REGLA DE CONTINUIDAD Y EJECUCIÓN DEL CICLO:**\n"
            "> 1. Al ejecutar la Fase 1 (`po-analyst`), generá el documento REQ, presentá la tabla de fases y la pregunta del gate.\n"
            "> 2. **CONTINUIDAD OBLIGATORIA DEL FLUJO**: Una vez que el usuario apruebe o indique continuar, **ADOPTÁ DE INMEDIATO** el rol de la siguiente fase (`story-refiner` para Fase 2 → `test-engineer` para Fase 2.5 → `architect-reviewer` para Fase 3 → `backend-developer`/`frontend-developer` para Fase 4 → `code-reviewer` para Fase 5 → `security-reviewer` para Fase 5.5 → `test-engineer` para Fase 6 → `final-auditor` para Fase 7).\n"
            "> 3. No te detengas ni abandones el ciclo a mitad de camino; avanza rol por rol hasta completar la auditoría final y el archivado.\n"
            "> 4. Consultá las convenciones en `.agents/project/` o `.claude/project/`, y los skills en `.agents/skills/` o `.claude/skills/`.\n\n"
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

    if name == "kuraka-update":
        body = (
            "# Actualizar Kuraka en este proyecto\n\n"
            f"En {target}, refrescá el framework (AGENTS.md + comandos) re-corriendo\n"
            f"el mount desde tu solución:\n\n"
            "```bash\n"
            f"kuraka mount --target {target}\n"
            "```\n\n"
            "Eso regenera AGENTS.md y los comandos de este entorno desde el vault.\n"
        )

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


def export_commands(vault: Path, project: Path, target: str, quiet: bool = False) -> int:
    """Render vault/commands/*.md as native slash-commands for `target`. Returns
    the number exported."""
    src_dir = vault / "commands"
    if not src_dir.is_dir():
        return 0
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
    """Print the available `/` commands (curated labels) + a start guide for `env`.
    Reusable: mount-kuraka.sh calls this with --catalog for the Claude flow."""
    if not commands_dir.is_dir():
        return
    present = {p.stem for p in commands_dir.glob("*.md")}
    ordered = [c for c in CMD_ORDER if c in present] + sorted(present - set(CMD_ORDER))
    print("")
    print('📚 COMANDOS DISPONIBLES (invocálos con "/"):')
    print("")
    for name in ordered:
        arg, label = CMD_LABEL.get(name, ("", ""))
        if not label:
            desc = command_desc(commands_dir / f"{name}.md")
            label = (desc[:86] + "…") if len(desc) > 87 else desc
        invoke = f"/{name} {arg}".strip()
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
        print("   1. Instalá los comandos (Codex los lee de tu home, no del repo):")
        print("        mkdir -p ~/.codex/prompts && cp .codex/prompts/*.md ~/.codex/prompts/")
        print(f"   2. Abrí Codex en el proyecto:  cd {proj} && codex")
        print("   3. Tipeá  /  y elegí. Primer uso:")
        print("      • ¿No sabés por dónde empezar?  →  /prompts:kuraka-wizard   (detecta plataforma + estado)")
        print("      • Brownfield →  /prompts:amauta     · Greenfield →  /prompts:inti + /prompts:arki")
        print("      • A trabajar →  /prompts:kuraka <requerimiento>")
        print("      (En Codex NO se monta .claude/: el setup es AGENTS.md + estos comandos.)")
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
    agents_md = render_agents_md(project, slug, cfg, agents, agent_tiers, tier_meanings)
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

    # export the slash-commands as this tool's native commands
    export_commands(vault, project, args.target)

    print("")
    print(f"✅ export {args.target} completo. (Claude Code sigue usando .claude/ vía 'kuraka mount'.)")

    # catalog of available commands + how to start in this environment
    parent, sub = TARGET_CMD_DIR[args.target]
    print_catalog(project / parent / sub, args.target, project)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
