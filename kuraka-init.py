#!/usr/bin/env python3
"""kuraka-init.py — one-shot Kuraka initializer for a target project.

Collapses the adoption dance (inspect → mount → config → project skeleton → register)
into a single command. The ONLY manual step left afterwards is restarting Claude Code
in the target (the runtime registers subagents at session start — no script can do that).

Runs two ways:

  Interactive (you, now):
      python3 kuraka-init.py [target_dir]
      # prompts for anything missing

  Non-interactive (the web app / automation later):
      python3 kuraka-init.py --target /path --name foo --mode normal --yes

What it does (in this order, so `mount` never prints "ADOPCIÓN INCOMPLETA"):
  1. kuraka-inspect.py <target>          → stack detection (JSON)
  2. draft kuraka.config.yaml            → from inspect, with TODO placeholders
  3. .claude/project/ skeleton           → conventions/ lessons-learned/ review-checks/ agents/
  4. mount-kuraka.sh <target>            → agents + skills + commands + rules + artifacts
  5. projects/<name>.md in the vault     → registry upsert (status: onboarding)

It never overwrites an existing kuraka.config.yaml or a populated .claude/project/.
After it finishes: restart Claude Code in the target, then run `amauta` to fill the
config TODOs from real code (Brownfield) — or `inti`/`arki` for greenfield.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import kuraka_common as kc

DEFAULT_VAULT = "/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka"
DEFAULT_VERSION = "0.3.4"  # stamped into the registry note; override with --version

# Recommended companion components. Kuraka works without them, but several agents
# rely on or strongly benefit from them. Keep in sync with RECOMMENDED-COMPONENTS.md.
# Component detection, in order of precedence per entry:
#   detect: a CLI name resolvable via shutil.which  (e.g. RTK)
#   mcp:    a server key expected under mcpServers in ~/.claude.json / project .mcp.json
#   (neither): a Claude Code skill — not detectable from here, print recommendation.
RECOMMENDED_COMPONENTS = [
    {
        "name": "RTK (rtk-ai/rtk)", "priority": "strong", "detect": "rtk",
        "used_by": "ALL agents (bash/test/grep/git output)",
        "why": "CLI proxy that compresses command output before it hits context — 70–90% token savings.",
        "install": "brew install rtk  (o: cargo install --git https://github.com/rtk-ai/rtk) && rtk init -g",
    },
    {
        "name": "ui-ux-pro-max", "priority": "recommended", "detect": None,
        "used_by": "frontend-developer, impeccable",
        "why": "UI/UX design intelligence (styles, palettes, fonts, UX guidelines, charts).",
        "install": "Claude Code plugin marketplace → add the ui-ux-pro-max skill.",
    },
    {
        "name": "Playwright MCP", "priority": "recommended", "detect": None, "mcp": "playwright",
        "used_by": "e2e-tester (Phase 6.5), checkmarx-remediation",
        "why": "Browser end-to-end tests + live capture (Checkmarx login).",
        "install": "claude mcp add playwright  (o configurá el servidor Playwright MCP en Claude Code).",
    },
    {
        "name": "magic / 21st MCP", "priority": "optional", "detect": None, "mcp": "magic",
        "used_by": "frontend-developer (scaffolding)",
        "why": "UI component generation/refinement.",
        "install": "Configurá el servidor magic / 21st MCP en Claude Code.",
    },
    {
        "name": "impeccable (skill)", "priority": "optional", "detect": None,
        "used_by": "frontend-developer UI review/polish",
        "why": "Visual audit and refinement of interfaces.",
        "install": "Claude Code plugin marketplace → add the impeccable skill.",
    },
    {
        "name": "Jira / ticket MCP", "priority": "optional", "detect": None, "mcp": "jira",
        "used_by": "po-analyst (Phase 1)",
        "why": "Fetch the real ticket instead of pasting the description.",
        "install": "Configurá tu MCP de issue-tracker (Jira/Linear/…) en Claude Code.",
    },
]

# language -> default package manager (best-effort; user/amauta confirms)
PKG_BY_LANG = {
    "python": "pip",
    "typescript": "npm",
    "javascript": "npm",
    "go": "go-mod",
    "rust": "cargo",
    "ruby": "bundler",
    "java": "maven",
    "csharp": "dotnet",
    "php": "composer",
}


# --------------------------------------------------------------------------- IO

def err(msg: str) -> None:
    print(msg, file=sys.stderr)


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    try:
        ans = input(f"{prompt}{suffix}: ").strip()
    except EOFError:
        ans = ""
    return ans or default


def confirm(prompt: str, assume_yes: bool) -> bool:
    if assume_yes:
        return True
    return ask(f"{prompt} (y/N)", "n").lower() in ("y", "yes", "s", "si")


def slugify(name: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", name).strip("-").lower()
    return s or "project"


# ----------------------------------------------------------------------- steps

def run_inspect(vault: Path, target: Path) -> dict:
    script = vault / "kuraka-inspect.py"
    if not script.exists():
        err(f"⚠️  kuraka-inspect.py no encontrado en {vault}; sigo sin detección de stack.")
        return {}
    try:
        out = subprocess.run(
            [sys.executable, str(script), str(target)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=False,
        )
        return json.loads(out.stdout) if out.stdout.strip() else {}
    except (json.JSONDecodeError, OSError) as e:
        err(f"⚠️  no pude parsear el inspect ({e}); sigo con un config más genérico.")
        return {}


def stack_summary(insp: dict) -> str:
    """Human-readable one-liner for the registry note."""
    parts = []
    be = insp.get("backend") or {}
    fe = insp.get("frontend") or {}
    if be.get("language"):
        parts.append("+".join(filter(None, [be.get("language"), be.get("framework")])))
    if fe.get("framework"):
        parts.append(fe["framework"])
    s = " / ".join(parts) if parts else "unknown"
    if insp.get("structure") and insp["structure"] != "single-package":
        s += f" ({insp['structure']})"
    return s


def build_config(name: str, mode: str, insp: dict, confidence_note: str) -> str:
    be = insp.get("backend") or {}
    fe = insp.get("frontend") or {}
    has_be = bool(be.get("language"))
    has_fe = bool(fe.get("framework"))
    orm = (be.get("orm_candidates") or ["none"])[0]
    mig = be.get("migration_tool") or "none"
    has_db = mig not in ("none", None) or orm not in ("none", None)

    lines = [
        f"# kuraka.config.yaml — DRAFT generated by kuraka-init on {date.today().isoformat()}",
        f"# {confidence_note}",
        "# Review every `# TODO`. Best: restart Claude Code here and run `amauta` to fill",
        "# these from real code (Brownfield), or `arki` for greenfield. Schema reference:",
        "#   kuraka-artifacts/config-schema.yaml in the vault.",
        "",
        "schema_version: 1",
        "",
        "project:",
        f"  name: {name}",
        "  description: |",
        "    TODO: describe what this project is and who uses it.",
        '  repo_url: ""',
        "",
        "stack:",
    ]

    if has_be:
        pkg = PKG_BY_LANG.get(be.get("language", ""), "other")
        lines += [
            "  backend:",
            f"    language: {be.get('language')}",
            f"    framework: {be.get('framework') or 'other'}",
            f"    package_manager: {pkg}            # TODO confirm",
            f"    orm: {orm}",
            '    lint_cmd: "TODO"',
            '    test_cmd: "TODO"',
            '    typecheck_cmd: ""',
            '    format_cmd: ""',
        ]
    if has_fe:
        lang = "typescript" if fe.get("typescript") else "javascript"
        lines += [
            "  frontend:",
            f"    language: {lang}",
            f"    framework: {fe.get('framework')}",
            "    package_manager: npm            # TODO confirm",
            f"    state_mgmt: {fe.get('state_manager') or 'none'}",
            '    lint_cmd: "TODO"',
            '    test_cmd: "TODO"',
            '    typecheck_cmd: "TODO"',
            '    format_cmd: ""',
        ]
    if has_db:
        lines += [
            "  database:",
            "    engine: TODO                    # postgres | mysql | sqlite | mongodb | ...",
            f"    migration_tool: {mig}",
        ]

    lines += [
        "",
        "architecture:",
        "  layers: []                        # TODO: define layer order (amauta/arki)",
        "  paths:",
        '    backend_root: "TODO/"' if has_be else "    # backend_root: omitted (no backend detected)",
        '    frontend_root: "TODO/"' if has_fe else "    # frontend_root: omitted (no frontend detected)",
        "    tests_root: tests/",
        f'    migrations_root: "TODO/"' if has_db else "    # migrations_root: omitted",
        "    docs_process_root: docs/process/",
        "",
        "conventions:",
        "  naming_language: english          # TODO confirm",
        '  null_syntax: "T | None"',
        "  multi_tenant: false               # TODO confirm",
        "  tenant_column_name: tenant_id",
        "  enums_for_states: true",
        "  max_file_loc: 700",
        "  max_function_loc: 50",
        "  max_frontend_file_loc: 400",
        "",
        "workflow:",
        f"  default_mode: {mode}",
        "  gates_require_user_approval: true",
        "  parallel_implementation: false",
        "",
    ]
    return "\n".join(lines)


def write_config(target: Path, content: str, assume_yes: bool) -> bool:
    cfg = target / "kuraka.config.yaml"
    if cfg.exists():
        err(f"   ✓ kuraka.config.yaml ya existe — lo respeto, no lo sobreescribo.")
        return False
    cfg.write_text(content, encoding="utf-8")
    print(f"   + kuraka.config.yaml (DRAFT — revisa los TODO)")
    return True


def project_layer_populated(target: Path) -> bool:
    """True if .claude/project/ has real content (a subdir holding files), i.e. it was
    filled by amauta/arki — not just an empty skeleton we created."""
    base = target / ".claude" / "project"
    subdirs = ["conventions", "lessons-learned", "review-checks", "agents"]
    return base.exists() and any(
        (base / d).exists() and any((base / d).iterdir()) for d in subdirs if (base / d).exists()
    )


def write_project_skeleton(target: Path, already_populated: bool) -> None:
    base = target / ".claude" / "project"
    subdirs = ["conventions", "lessons-learned", "review-checks", "agents"]
    if already_populated:
        err("   ✓ .claude/project/ ya tiene contenido — no toco el skeleton.")
        return
    for d in subdirs:
        (base / d).mkdir(parents=True, exist_ok=True)
    readme = base / "README.md"
    if not readme.exists():
        readme.write_text(
            "# Project specialization layer\n\n"
            "Filled by `amauta` (Brownfield) or `arki` (greenfield) from real code.\n\n"
            "- `conventions/*.md` — architecture/style rules the agents enforce.\n"
            "- `review-checks/<agent>.md` — extra checks per reviewer agent.\n"
            "- `lessons-learned/*.md` — institutional knowledge (frontmatter `applies_to`).\n"
            "- `agents/<agent>.append.md` — per-agent addenda (escape hatch).\n"
            "- `glossary.md` — domain vocabulary.\n",
            encoding="utf-8",
        )
    glossary = base / "glossary.md"
    if not glossary.exists():
        glossary.write_text("# Glossary\n\nTODO: domain terms.\n", encoding="utf-8")
    print("   + .claude/project/ skeleton (conventions, lessons-learned, review-checks, agents)")


def run_mount(vault: Path, target: Path) -> int:
    # Canonical mount is the cross-platform kuraka-mount.py (invoked with the same
    # interpreter, so it works on Windows where there may be no `python3`/bash).
    script = vault / "kuraka-mount.py"
    if not script.exists():
        err(f"❌ kuraka-mount.py no encontrado en {vault}")
        return 1
    env = dict(os.environ, KURAKA_VAULT=str(vault))
    proc = subprocess.run([sys.executable, str(script), str(target)], env=env)
    return proc.returncode


def upsert_registry(vault: Path, name: str, target: Path, insp: dict,
                    mode: str, version: str, has_layer: bool) -> None:
    reg = kc.registry_note(vault, name)  # projects/<slug>/registry.md (unified store)
    reg.parent.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    stack = stack_summary(insp)
    layer_val = "true" if has_layer else "false"

    if reg.exists():
        text = reg.read_text(encoding="utf-8")
        # light frontmatter update: last_mount, stack, has_project_layer
        def repl(field: str, value: str, s: str) -> str:
            pat = re.compile(rf"^({re.escape(field)}:).*$", re.MULTILINE)
            return pat.sub(rf"\1 {value}", s, count=1) if pat.search(s) else s
        text = repl("last_mount", today, text)
        text = repl("stack", f'"{stack}"', text)
        text = repl("has_project_layer", layer_val, text)
        reg.write_text(text, encoding="utf-8")
        print(f"   ~ projects/{name}/registry.md (registro actualizado)")
        return

    fm = (
        "---\n"
        f"name: {name}\n"
        f"path: {target}\n"
        'repo_url: ""\n'
        f'stack: "{stack}"\n'
        f"kuraka_version: {version}\n"
        f"has_project_layer: {layer_val}\n"
        f"default_mode: {mode}\n"
        'focus_scope: ""\n'
        "status: onboarding\n"
        f"last_mount: {today}\n"
        'last_sync: ""\n'
        "tags: [kuraka-project]\n"
        "---\n\n"
        f"# {name}\n\n"
        f"Registered by kuraka-init on {today}. Stack (detected): {stack}.\n\n"
        "## Onboarding\n"
        "- Draft `kuraka.config.yaml` generated with TODOs — refine with `amauta`.\n"
        "- Restart Claude Code rooted in the project to register subagents.\n"
    )
    reg.write_text(fm, encoding="utf-8")
    print(f"   + projects/{name}/registry.md (registrado en el vault)")


def _installed_mcp_servers(target: Path | None = None) -> set[str]:
    """Server keys configured under mcpServers, merged from the global
    ~/.claude.json and (if given) the project-local .mcp.json. Empty on any error."""
    servers: set[str] = set()
    sources = [Path(os.path.expanduser("~/.claude.json"))]
    if target is not None:
        sources.append(target / ".mcp.json")
    for src in sources:
        try:
            data = json.loads(src.read_text(encoding="utf-8"))
            servers |= set(data.get("mcpServers", {}).keys())
        except (OSError, ValueError):
            continue
    return servers


def recommend_components(vault: Path, target: Path | None = None) -> None:
    """Print recommended companion components and detect which are present —
    CLIs via `which`, MCP servers via the mcpServers config.

    Never installs anything — external tools are an explicit user decision.
    """
    icon = {"strong": "🔴", "recommended": "🟡", "optional": "⚪"}
    installed_mcp = _installed_mcp_servers(target)
    print("🧩 Componentes recomendados (opcional — Kuraka funciona sin ellos):")
    print("")
    missing_strong = []
    missing_mcp = []
    for c in RECOMMENDED_COMPONENTS:
        mark = icon.get(c["priority"], "•")
        if c.get("detect"):
            present = shutil.which(c["detect"]) is not None
            status = "✓ instalado" if present else "— falta"
            if not present and c["priority"] == "strong":
                missing_strong.append(c)
        elif c.get("mcp"):
            present = c["mcp"] in installed_mcp
            status = "✓ instalado (MCP)" if present else "— falta (MCP no configurado)"
            if not present:
                missing_mcp.append(c)
        else:
            status = "(skill — verificá en Claude Code)"
        print(f"   {mark} {c['name']:<22} {status}")
        print(f"      usa: {c['used_by']}")
        print(f"      {c['why']}")
        print(f"      instalar: {c['install']}")
        print("")
    if installed_mcp:
        print(f"   MCP configurados detectados: {', '.join(sorted(installed_mcp))}")
        print("")
    if missing_strong:
        print("   ⚠️  Falta un componente de alto impacto:")
        for c in missing_strong:
            print(f"      → {c['name']}: {c['install']}")
        print("")
    if missing_mcp:
        print("   ℹ️  MCP recomendados no configurados:")
        for c in missing_mcp:
            print(f"      → {c['name']}: {c['install']}")
        print("")
    print(f"   Detalle completo: {vault}/RECOMMENDED-COMPONENTS.md")
    print("")


# ------------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser(description="One-shot Kuraka initializer for a target project.")
    ap.add_argument("target", nargs="?", help="target project dir (default: prompt)")
    ap.add_argument("--target", dest="target_opt", help="target project dir")
    ap.add_argument("--name", help="project slug (default: target basename)")
    ap.add_argument("--mode", default="normal", help="default workflow mode (default: normal)")
    ap.add_argument("--vault", default=os.environ.get("KURAKA_VAULT", DEFAULT_VAULT))
    ap.add_argument("--version", default=DEFAULT_VERSION, help="kuraka_version stamped in registry")
    ap.add_argument("--yes", "-y", action="store_true", help="non-interactive; assume yes")
    ap.add_argument("--no-mount", action="store_true", help="skip mount step")
    ap.add_argument("--register-only", action="store_true",
                    help="only inspect + upsert the registry note (no config/skeleton/mount)")
    ap.add_argument("--create", action="store_true", help="create target dir if missing")
    ap.add_argument("--no-components", action="store_true",
                    help="skip the recommended-components recommendation step")
    ap.add_argument("--recommend-only", action="store_true",
                    help="only print the recommended-components + MCP detection, then exit (used by mount)")
    args = ap.parse_args()

    # Line-buffer so our prints interleave correctly with subprocess output even
    # when stdout is a pipe (e.g. captured by the future web backend).
    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

    vault = Path(args.vault).expanduser().resolve()
    if not vault.is_dir():
        err(f"❌ vault no encontrado: {vault}")
        return 1

    # --recommend-only: pure detection (called by mount). Target is optional and
    # only used to also read a project-local .mcp.json.
    if args.recommend_only:
        rec_raw = args.target_opt or args.target
        rec_target = Path(rec_raw).expanduser().resolve() if rec_raw else None
        recommend_components(vault, rec_target if (rec_target and rec_target.is_dir()) else None)
        return 0

    target_raw = args.target_opt or args.target
    if not target_raw and not args.yes:
        target_raw = ask("Ruta del proyecto donde montar Kuraka")
    if not target_raw:
        err("❌ falta la ruta del proyecto (target).")
        return 1
    target = Path(target_raw).expanduser().resolve()

    if not target.exists():
        if args.create or confirm(f"{target} no existe. ¿Crearlo?", args.yes):
            target.mkdir(parents=True, exist_ok=True)
        else:
            err("❌ target no existe.")
            return 1
    if not target.is_dir():
        err(f"❌ target no es un directorio: {target}")
        return 1

    name = kc.project_slug(target, args.name)  # config project.name first → one slug everywhere
    mode = args.mode

    print("🪢 kuraka-init")
    print(f"   vault:  {vault}")
    print(f"   target: {target}")
    print(f"   name:   {name}   mode: {mode}")
    print("")

    # 1. inspect
    insp = run_inspect(vault, target)
    conf = insp.get("confidence")
    confidence_note = (
        f"from kuraka-inspect (confidence {conf})" if conf is not None
        else "stack detection unavailable — generic draft"
    )
    if insp:
        print(f"   detección: {stack_summary(insp)}  (confidence {conf})")

    # Detect existing project layer BEFORE we touch the skeleton, so a freshly
    # created (empty) skeleton is correctly reported as not-yet-populated.
    has_layer = project_layer_populated(target)

    if not args.register_only:
        # 2 + 3 BEFORE mount so mount doesn't warn "ADOPCIÓN INCOMPLETA"
        write_config(target, build_config(name, mode, insp, confidence_note), args.yes)
        write_project_skeleton(target, already_populated=has_layer)
        # 4. mount
        if not args.no_mount:
            print("", flush=True)
            rc = run_mount(vault, target)
            if rc != 0:
                err(f"❌ mount-kuraka.sh salió con código {rc}")
                return rc

    # 5. registry (always)
    print("")
    upsert_registry(vault, name, target, insp, mode, args.version, has_layer)

    # 6. recommended components (skip for register-only / --no-components)
    if not args.register_only and not args.no_components:
        print("")
        recommend_components(vault, target)

    # final
    print("")
    if args.register_only:
        print("✅ registrado en el vault (solo registro).")
        return 0
    print("✅ kuraka-init completo.")
    print("")
    print("   ÚNICO paso manual restante:")
    print(f"     cd {target}")
    print("     # reinicia Claude Code (sesión nueva en esta carpeta) para registrar subagentes")
    print("     # luego: invoca `amauta` para rellenar los TODO del config desde el código real")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
