#!/usr/bin/env python3
"""kuraka-mount.py — mount the Kuraka vault into a consumer project.

Cross-platform (macOS / Linux / Windows) canonical implementation of the mount.
Replaces the old rsync/bash `mount-kuraka.sh` (which is now a thin wrapper around
this). No external dependencies — pure Python 3 + git. Sibling scripts are invoked
via `sys.executable` so it never assumes a `python3` on PATH (key on Windows).

What it does:
  1. banner + (TTY) interactive menu of categories / status-only + MCP detection
  2. pre-flight snapshot of local overrides, then copy the vault categories in
  3. re-apply project overrides on top, update .gitignore, register, offer restore
  4. auto-seed a migration-example layer, adoption check, command catalog + guide

Usage:  python3 kuraka-mount.py [target_dir] [--target claude|antigravity|cursor|codex]
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from fnmatch import fnmatch
from pathlib import Path

# Emit UTF-8 regardless of the console code page (Windows cp1252/cp850 would
# otherwise crash with UnicodeEncodeError on our emoji/box-drawing output).
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError, OSError):
        pass

DEFAULT_VAULT = "/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka"


def _self_dir() -> Path:
    return Path(__file__).resolve().parent


VAULT = Path(os.environ.get("KURAKA_VAULT", "") or _self_dir()).expanduser().resolve()


# --------------------------------------------------------------------------- io

def _enable_windows_ansi() -> None:
    """Best-effort enable of ANSI/VT sequences on the Windows console."""
    if os.name != "nt":
        return
    try:
        import ctypes
        k = ctypes.windll.kernel32
        k.SetConsoleMode(k.GetStdHandle(-11), 7)
    except Exception:
        pass


def color_ok() -> bool:
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def run_py(script: str, *args: str, quiet: bool = False, check_env: bool = True):
    """Invoke a sibling vault script with the current interpreter."""
    import subprocess
    path = VAULT / script
    if not path.exists():
        return None
    env = dict(os.environ, KURAKA_VAULT=str(VAULT), PYTHONIOENCODING="utf-8") if check_env else None
    try:
        if quiet:
            r = subprocess.run([sys.executable, str(path), *args],
                               env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            r = subprocess.run([sys.executable, str(path), *args], env=env)
        return r.returncode
    except OSError:
        return None


def capture_py(script: str, *args: str) -> str:
    import subprocess
    path = VAULT / script
    if not path.exists():
        return ""
    try:
        r = subprocess.run([sys.executable, str(path), *args],
                           env=dict(os.environ, KURAKA_VAULT=str(VAULT), PYTHONIOENCODING="utf-8"),
                           capture_output=True, text=True)
        return r.stdout
    except OSError:
        return ""


# ------------------------------------------------------------------------ banner

def banner() -> None:
    d = "\033[38;5;242m" if color_ok() else ""
    reset = "\033[0m" if color_ok() else ""
    ans = VAULT / "assets" / "kuraka-banner.ans"
    txt = VAULT / "assets" / "kuraka-banner.txt"
    print("")
    if color_ok() and ans.exists():
        sys.stdout.write(ans.read_text(encoding="utf-8", errors="ignore"))
    elif txt.exists():
        sys.stdout.write(d + txt.read_text(encoding="utf-8", errors="ignore") + reset)
    else:
        c = "\033[38;5;214m" if color_ok() else ""
        for line in (
            "   ██╗  ██╗██╗   ██╗██████╗  █████╗ ██╗  ██╗ █████╗ ",
            "   █████╔╝ ██║   ██║██████╔╝███████║█████╔╝ ███████║",
            "   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝",
        ):
            print(f"{c}{line}{reset}")
    print(f"{d}        🪢  KURAKA · «el mayor» · framework multi-agente{reset}")
    print("")


# ---------------------------------------------------------------- file copying

def count_top(dstdir: Path) -> int:
    """Top-level .md/.sh files."""
    if not dstdir.is_dir():
        return 0
    return sum(1 for p in dstdir.iterdir() if p.is_file() and p.suffix in (".md", ".sh"))


def count_codex_skills(dstdir: Path) -> int:
    """Number of discoverable project-local Codex skills."""
    if not dstdir.is_dir():
        return 0
    return sum(1 for p in dstdir.iterdir() if p.is_dir() and (p / "SKILL.md").is_file())


def count_codex_agents(dstdir: Path) -> int:
    """Number of native Codex custom agent definitions."""
    if not dstdir.is_dir():
        return 0
    return sum(1 for p in dstdir.glob("*.toml") if p.is_file())


def _excluded(rel: Path, exclude: tuple[str, ...]) -> bool:
    return any(fnmatch(part, pat) for part in rel.parts for pat in exclude)


def sync_tree(src: Path, dst: Path, exclude: tuple[str, ...] = (), target_env: str = "claude") -> None:
    """Mirror src→dst with `rsync --update` semantics."""
    if not src.is_dir():
        return
    for root, _dirs, files in os.walk(src):
        for f in files:
            sp = Path(root) / f
            rel = sp.relative_to(src)
            if _excluded(rel, exclude):
                continue
            dp = dst / rel
            if dp.exists() and dp.stat().st_mtime >= sp.stat().st_mtime:
                continue
            copy_file(sp, dp, target_env=target_env)


def copy_file(src: Path, dst: Path, target_env: str = "claude") -> None:
    import shutil
    if not src.is_file():
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if target_env in ("antigravity", "codex") and src.suffix == ".md":
        text = src.read_text(encoding="utf-8", errors="ignore")
        if target_env == "antigravity":
            text = text.replace(".claude/skills/", ".agents/skills/")
            text = text.replace(".claude/rules/", ".agents/rules/")
            text = text.replace(".claude/agents/", ".agents/agents/")
            text = text.replace(".claude/project/", ".agents/project/")
            text = text.replace(".claude/stack-profiles/", ".agents/stack-profiles/")
            text = text.replace(".claude/templates/", ".agents/templates/")
        elif target_env == "codex":
            text = adapt_codex_paths(text)
        dst.write_text(text, encoding="utf-8")
    else:
        shutil.copy2(src, dst)


def sync_antigravity_skills(src_skills: Path, dst_skills: Path) -> int:
    """Sync vault skills to .agents/skills/ in Antigravity native skill structure:
    each skill is a directory .agents/skills/<skill_name>/SKILL.md, plus preserving
    subdirectories like evals/ and sentry-triage/."""
    dst_skills.mkdir(parents=True, exist_ok=True)
    count = 0
    for p in src_skills.glob("*.md"):
        skill_name = p.stem
        skill_dir = dst_skills / skill_name
        skill_dir.mkdir(parents=True, exist_ok=True)
        copy_file(p, skill_dir / "SKILL.md", target_env="antigravity")
        copy_file(p, dst_skills / p.name, target_env="antigravity")
        count += 1
    for d in src_skills.iterdir():
        if d.is_dir():
            sync_tree(d, dst_skills / d.name)
    return count


def _codex_skill_text(name: str, description: str, body: str, source_kind: str) -> str:
    """Render a Codex-native SKILL.md. Codex discovers project-local skills only
    from .codex/skills/<name>/SKILL.md, so vault skills and Kuraka agents are
    normalized into that shape for the Codex target."""
    description = adapt_codex_paths(description)
    body = adapt_codex_paths(body)
    platform_override = ""
    if name in {"kuraka", "kuraka-policies"}:
        platform_override = """## Codex Platform Override

This override takes precedence over Claude-specific wording below. When the
workflow says to invoke an agent, delegate to the matching native custom agent
in `.codex/agents/<name>.toml`, wait for its structured handoff, and apply the
gate before the next phase. The orchestrator never adopts a specialist role.

Codex may not expose Claude's `<usage>` block. Keep the telemetry file and
record phase, agent, attempt, timestamps, status, and produced artifacts.
Record unavailable token, tool-use, or duration values as `null` or `unknown`;
never fabricate `0`. Missing optional usage metrics do not block a gate.

"""
    return (
        "---\n"
        f"name: {name}\n"
        f'description: "{description}"\n'
        "---\n\n"
        f"> Kuraka Codex {source_kind}. Loaded from this project via `.codex/skills/{name}/SKILL.md`.\n\n"
        f"{platform_override}"
        f"{body.lstrip()}"
    )


def _frontmatter_and_body(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8", errors="ignore")
    fm: dict[str, str] = {}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            block = text[3:end]
            body = text[end + 4:].lstrip("\n")
            for raw in block.splitlines():
                if ":" not in raw:
                    continue
                k, _, v = raw.partition(":")
                fm[k.strip()] = v.strip().strip('"').strip("'")
            return fm, body
    return fm, text


def adapt_codex_paths(text: str) -> str:
    """Translate Claude paths and command mentions to the Codex projection.

    Root Markdown skills become SKILL.md directories in Codex, so convert the
    common explicit `.md` references before applying the broader replacements.
    """
    import re

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
    command_names = (
        "checkmarx-remediation", "kuraka-wizard", "kuraka-backup",
        "kuraka-update", "kuraka", "amauta", "inti", "arki",
    )
    for name in command_names:
        text = text.replace(f"/prompts:{name}", f"${name}")
        text = re.sub(
            rf"(?<![A-Za-z0-9_.$/])/{re.escape(name)}(?![A-Za-z0-9_.-])",
            f"${name}",
            text,
        )
    return text


def sync_codex_skills(src_skills: Path, dst_skills: Path) -> int:
    """Sync only reusable Kuraka skills as Codex-native project skills.

    Agent roles are rendered separately to `.codex/agents/*.toml`; publishing
    them as skills duplicates the catalog and prevents native delegation.
    """
    dst_skills.mkdir(parents=True, exist_ok=True)
    count = 0

    if src_skills.is_dir():
        for p in sorted(src_skills.glob("*.md")):
            if p.name.endswith(".append.md"):
                continue
            fm, body = _frontmatter_and_body(p)
            name = fm.get("name") or p.stem
            desc = fm.get("description") or f"Kuraka workflow skill: {name}"
            skill_dir = dst_skills / name
            skill_dir.mkdir(parents=True, exist_ok=True)
            (skill_dir / "SKILL.md").write_text(_codex_skill_text(name, desc, body, "skill"), encoding="utf-8")
            count += 1
        for d in src_skills.iterdir():
            if d.is_dir():
                sync_tree(d, dst_skills / d.name, target_env="codex")

    return count


CODEX_REASONING_EFFORT = {
    "frontier": "high",
    "heavy": "high",
    "balanced": "medium",
    "fast": "low",
}

CODEX_READ_ONLY_AGENTS = {
    "architect-reviewer",
    "code-reviewer",
    "security-reviewer",
    "final-auditor",
    "migration-reviewer",
    "pattern-detector",
}


def read_codex_agent_settings(vault: Path) -> dict[str, tuple[str | None, str]]:
    """Resolve Codex model settings from MODEL-ROUTING.yaml without PyYAML.

    A placeholder such as `<most-capable available>` intentionally omits the
    `model` key so the custom agent inherits the user's valid Codex model.
    """
    routing = vault / "MODEL-ROUTING.yaml"
    if not routing.is_file():
        return {}
    agent_tiers: dict[str, str] = {}
    codex_models: dict[str, str] = {}
    section = ""
    platform = ""
    for raw in routing.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        line = raw.strip().split(" #", 1)[0].strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if indent == 0:
            section = key
            platform = ""
        elif section == "agents":
            agent_tiers[key] = value
        elif section == "platforms" and indent == 2:
            platform = key
        elif section == "platforms" and platform == "codex" and indent >= 4:
            codex_models[key] = value

    settings: dict[str, tuple[str | None, str]] = {}
    for name, tier in agent_tiers.items():
        model = codex_models.get(tier)
        if model and (model.startswith("<") or model == "inherit"):
            model = None
        settings[name] = (model, CODEX_REASONING_EFFORT.get(tier, "medium"))
    return settings


def _toml_multiline_literal(text: str) -> str:
    """Encode instructions as a TOML multiline literal string."""
    if "'''" in text:
        raise ValueError("Codex agent source contains unsupported TOML literal delimiter")
    return "'''\n" + text.rstrip() + "\n'''"


def render_codex_agent_toml(name: str, description: str, body: str,
                             model: str | None, reasoning_effort: str,
                             sandbox_mode: str) -> str:
    """Render a native Codex custom agent from a Claude-source agent body."""
    instructions = f"""# Kuraka Codex Agent Contract

You are the `{name}` subagent in a gated Kuraka workflow. Work only on the
phase and inputs supplied by the orchestrator. Do not advance phases, invoke
other Kuraka agents, or request approval from the user directly.

Load the referenced skills, project layer, stack profile, rules, and output
schema before acting. Preserve evidence with file paths and run only the
validation appropriate to this phase.

Return exactly one handoff status:
- `DONE`: list produced or inspected artifacts and validation evidence.
- `CLARIFY`: state the blocking question and why it prevents a valid output.
- `BLOCKED`: state the missing dependency or failed precondition.
- `VALIDATION_FAILED`: state the failed check and affected artifacts.

The orchestrator owns checkpoints, telemetry, phase gates, user interaction,
and final decisions. Never invent unavailable usage metrics; report them as
`unknown` when requested.

--- Source role instructions ---

{adapt_codex_paths(body)}
"""
    lines = [
        f"name = {json.dumps(name)}",
        f"description = {json.dumps(adapt_codex_paths(description))}",
    ]
    if model:
        lines.append(f"model = {json.dumps(model)}")
    lines.extend([
        f"model_reasoning_effort = {json.dumps(reasoning_effort)}",
        f"sandbox_mode = {json.dumps(sandbox_mode)}",
        f"developer_instructions = {_toml_multiline_literal(instructions)}",
        "",
    ])
    return "\n".join(lines)


def sync_codex_agents(src_agents: Path, dst_agents: Path, vault: Path) -> int:
    """Compile Claude-source Markdown agents to native Codex TOML agents."""
    dst_agents.mkdir(parents=True, exist_ok=True)
    settings = read_codex_agent_settings(vault)
    count = 0
    for source in sorted(src_agents.glob("*.md")):
        fm, body = _frontmatter_and_body(source)
        name = fm.get("name") or source.stem
        description = fm.get("description") or f"Kuraka specialist agent: {name}."
        model, effort = settings.get(name, (None, "medium"))
        sandbox = "read-only" if name in CODEX_READ_ONLY_AGENTS else "workspace-write"
        rendered = render_codex_agent_toml(name, description, body, model, effort, sandbox)
        (dst_agents / f"{name}.toml").write_text(rendered, encoding="utf-8")
        count += 1
    return count


def ensure_codex_agent_config(config_path: Path) -> bool:
    """Add Kuraka's safe concurrency default without replacing user config."""
    key = "max_concurrent_threads_per_session"
    default = f"{key} = 4"
    if not config_path.exists():
        config_path.write_text("[agents]\n" + default + "\n", encoding="utf-8")
        return True

    lines = config_path.read_text(encoding="utf-8", errors="ignore").splitlines()
    section_start = None
    section_end = len(lines)
    for index, line in enumerate(lines):
        if line.strip() == "[agents]":
            section_start = index
            continue
        if section_start is not None and line.strip().startswith("["):
            section_end = index
            break
    if section_start is None:
        suffix = "\n" if lines else ""
        config_path.write_text("\n".join(lines) + suffix + "\n[agents]\n" + default + "\n", encoding="utf-8")
        return True
    if any(line.strip().startswith(key + " =") for line in lines[section_start + 1:section_end]):
        return False
    lines.insert(section_end, default)
    config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return True


# ------------------------------------------------------------------------- main

def main() -> int:
    _enable_windows_ansi()

    # argument parsing for target directory and target platform
    target_dir_arg = None
    target_env = "claude"

    args_list = sys.argv[1:]
    if any(arg in ("-h", "--help") for arg in args_list):
        print("Usage: python3 kuraka-mount.py [target_dir] [--target claude|antigravity|cursor|codex]")
        print("Mount Kuraka framework artifacts into a consumer project.")
        return 0
    i = 0
    while i < len(args_list):
        a = args_list[i]
        if a in ("--target", "-t"):
            if i + 1 < len(args_list):
                target_env = args_list[i + 1]
                i += 2
            else:
                i += 1
        elif a.startswith("--target="):
            target_env = a.split("=", 1)[1]
            i += 1
        else:
            if not target_dir_arg:
                target_dir_arg = a
            i += 1

    target = Path(target_dir_arg or os.getcwd()).expanduser().resolve()

    if not VAULT.is_dir():
        print(f"❌ ERROR: vault no encontrado en {VAULT}", file=sys.stderr)
        return 1
    if not target.is_dir():
        print(f"❌ ERROR: target no existe: {target}", file=sys.stderr)
        return 1

    banner()
    print(f"   vault:    {VAULT}")
    print(f"   target:   {target}")
    print(f"   entorno:  {target_env}")
    print("")

    # Determine platform customization directory
    if target_env == "antigravity":
        platform_dir = target / ".agents"
    elif target_env == "cursor":
        platform_dir = target / ".cursor"
    elif target_env == "codex":
        platform_dir = target / ".codex"
    else:
        platform_dir = target / ".claude"

    platform_dir.mkdir(parents=True, exist_ok=True)
    if target_env == "codex" and ensure_codex_agent_config(platform_dir / "config.toml"):
        print("   ✓ .codex/config.toml: límite de 4 subagentes concurrentes")

    selected = {"agents", "skills", "commands", "rules", "artifacts"}
    menu_mode = "all"
    tty = sys.stdin.isatty()

    if tty:
        if (platform_dir / "agents").is_dir():
            print(f"ℹ️  Kuraka YA está montado en este proyecto ({platform_dir.name}) → esto es un re-mount (update).")
        else:
            print(f"🆕 Primer montaje de Kuraka en este proyecto ({platform_dir.name}).")
        hist = capture_py("kuraka-restore.py", str(target), "--check")
        for line in hist.splitlines():
            if "historia en central" in line:
                print(f"   📦 El vault guarda historia de este proyecto: {line.split('central:',1)[1].strip()}")
                print("      → al terminar el montaje se te preguntará si restaurarla para continuar el trabajo.")
                break
        print("")
        print("¿Qué querés montar?")
        print("   [Enter] todo   ·   c) elegir categorías   ·   s) solo ver estado (sin montar)")
        try:
            choice = input("   > ").strip()
        except EOFError:
            choice = ""
        if choice.lower() == "c":
            print("   Categorías: agents  skills  commands  rules  artifacts")
            try:
                sel = input("   Ingresá las que querés (separadas por espacio) [todo]: ").strip()
            except EOFError:
                sel = ""
            if sel:
                selected = set(sel.split())
            print("")
        elif choice.lower() == "s":
            menu_mode = "status"

    if tty:
        run_py("kuraka-init.py", "--recommend-only", "--target", str(target))

    if menu_mode == "status":
        print("ℹ️  Modo 'solo estado' — no se montó nada.")
        return 0

    def want(cat: str) -> bool:
        return cat in selected

    # pre-flight: snapshot local overrides BEFORE the copy overwrites them.
    if target_env != "codex" and (platform_dir / "agents").is_dir():
        if run_py("kuraka-backup.py", str(target), "--overrides-only", quiet=True) == 0:
            print("   ✓ overrides locales respaldados al store central (pre-mount)")
            print("")

    # --- sync personal categories ---
    synced_agents = False
    for category in ("agents", "skills", "commands", "hooks"):
        wcat = "agents" if category == "hooks" else category
        if not want(wcat):
            continue
        src = VAULT / category
        dst = platform_dir / category
        if src.is_dir():
            if target_env == "codex" and category == "commands":
                # kuraka-export.py compiles command entrypoints to project-local
                # Codex skills. Current Codex does not discover .codex/commands
                # or .codex/prompts as custom slash commands.
                print("   → commands/  (se compilarán como skills Codex)")
                continue
            dst.mkdir(parents=True, exist_ok=True)
            if target_env == "codex" and category == "agents":
                before = count_codex_agents(dst)
            elif target_env == "codex" and category == "skills":
                before = count_codex_skills(dst)
            else:
                before = count_top(dst)
            if category == "skills" and target_env == "antigravity":
                sync_antigravity_skills(src, dst)
            elif category == "skills" and target_env == "codex":
                sync_codex_skills(src, dst)
            elif category == "agents" and target_env == "codex":
                sync_codex_agents(src, dst, VAULT)
            else:
                sync_tree(src, dst, exclude=("*.append.md",), target_env=target_env)
            if target_env == "codex" and category == "agents":
                after = count_codex_agents(dst)
            elif target_env == "codex" and category == "skills":
                after = count_codex_skills(dst)
            else:
                after = count_top(dst)
            delta = after - before
            if delta > 0:
                print(f"   + {category}/  ({delta} new, {after} total)")
                if category == "agents":
                    synced_agents = True
            else:
                print(f"   ✓ {category}/  (up to date, {after} total)")

    # contexts sub-directory
    if want("agents") and (VAULT / "agents" / "contexts").is_dir():
        sync_tree(VAULT / "agents" / "contexts", platform_dir / "agents" / "contexts", target_env=target_env)
        print("   ✓ agents/contexts/")

    # personal rules (meta-rules of the agent system)
    if want("rules"):
        for rule in ("16-agent-backup.md", "17-kuraka-token-optimizations.md",
                     "18-duplication-aware-refactor.md", "19-evidence.md"):
            src = VAULT / "rules" / rule
            if src.is_file():
                copy_file(src, platform_dir / "rules" / rule, target_env=target_env)
                print(f"   ✓ rules/{rule}")

    # framework-level artifacts outside platform_dir
    artifacts = VAULT / "kuraka-artifacts"
    if want("artifacts") and artifacts.is_dir():
        print("")
        print("[kuraka-mount] restoring Kuraka artifacts...")
        ll = artifacts / "docs" / "process" / "lessons-learned.md"
        if ll.is_file():
            copy_file(ll, target / "docs" / "process" / "lessons-learned.md")
            print("   ✓ docs/process/lessons-learned.md")
        dash = artifacts / "docs" / "process" / "agent-telemetry" / "DASHBOARD.md"
        if dash.is_file():
            copy_file(dash, target / "docs" / "process" / "agent-telemetry" / "DASHBOARD.md")
            print("   ✓ docs/process/agent-telemetry/DASHBOARD.md")
        if (artifacts / "tests" / "kuraka").is_dir():
            sync_tree(artifacts / "tests" / "kuraka", target / "tests" / "kuraka",
                      exclude=(".pytest_cache", "__pycache__"))
            print("   ✓ tests/kuraka/")
        if (artifacts / "stack-profiles").is_dir():
            sync_tree(artifacts / "stack-profiles", platform_dir / "stack-profiles", target_env=target_env)
            if target_env == "antigravity":
                sync_tree(artifacts / "stack-profiles", target / ".claude" / "stack-profiles")
            print("   ✓ stack-profiles/")
        if (artifacts / "templates").is_dir():
            sync_tree(artifacts / "templates", platform_dir / "templates", target_env=target_env)
            if target_env == "antigravity":
                sync_tree(artifacts / "templates", target / ".claude" / "templates")
            print("   ✓ templates/")

    # Export AGENTS.md + slash commands / workflows for target platform
    if target_env in ("antigravity", "cursor", "codex"):
        run_py("kuraka-export.py", str(target), "--target", target_env)

    # record mount manifest
    try:
        import kuraka_common as _kc
        mounted_cats = tuple(c for c in _kc.OVERRIDE_CATEGORIES if want(c))
        if mounted_cats:
            n = _kc.write_mount_manifest(target, VAULT, mounted_cats, platform=platform_dir.name)
            print(f"   ✓ mount manifest ({n} vault baselines → {platform_dir.name}/{_kc.MOUNT_MANIFEST_NAME})")
    except ImportError:
        print("   ⚠ kuraka_common.py not found — mount manifest skipped")

    # re-apply project-specific overrides
    if target_env != "codex":
        run_py("kuraka-restore.py", str(target), "--overrides-only", "--target", target_env)

    # --- ensure .gitignore excludes personal content ---
    gitignore = target / ".gitignore"
    if target_env == "antigravity":
        patterns = [
            "# Kuraka framework files (versioned externally; not source of this repo)",
            ".agents/agents/",
            ".agents/skills/",
            ".agents/commands/",
            ".agents/rules/16-agent-backup.md",
            ".agents/rules/17-kuraka-token-optimizations.md",
            ".agents/rules/18-duplication-aware-refactor.md",
            ".agents/rules/19-evidence.md",
            ".agents/.kuraka-mount-manifest.json",
            ".agent/workflows/",
            "# Per-cycle telemetry JSONs (noise; the consolidated DASHBOARD.md is tracked)",
            "docs/process/agent-telemetry/*.json",
            "# Tool scratch dirs (never track)",
            ".playwright-mcp/",
            ".pytest_cache/",
        ]
    elif target_env == "codex":
        patterns = [
            "# Kuraka framework files (versioned externally; not source of this repo)",
            ".codex/agents/",
            ".codex/skills/",
            ".codex/commands/",
            ".codex/prompts/",
            ".codex/rules/16-agent-backup.md",
            ".codex/rules/17-kuraka-token-optimizations.md",
            ".codex/rules/18-duplication-aware-refactor.md",
            ".codex/rules/19-evidence.md",
            ".codex/.kuraka-mount-manifest.json",
            "# Per-cycle telemetry JSONs (noise; the consolidated DASHBOARD.md is tracked)",
            "docs/process/agent-telemetry/*.json",
            "# Tool scratch dirs (never track)",
            ".playwright-mcp/",
            ".pytest_cache/",
        ]
    else:
        patterns = [
            "# Kuraka framework files (versioned externally; not source of this repo)",
            ".claude/agents/",
            ".claude/skills/",
            ".claude/commands/",
            ".claude/hooks/",
            ".claude/rules/16-agent-backup.md",
            ".claude/rules/17-kuraka-token-optimizations.md",
            ".claude/rules/18-duplication-aware-refactor.md",
            ".claude/rules/19-evidence.md",
            ".claude/.kuraka-mount-manifest.json",
            "# Per-cycle telemetry JSONs (noise; the consolidated DASHBOARD.md is tracked)",
            "docs/process/agent-telemetry/*.json",
            "# Tool scratch dirs (never track)",
            ".playwright-mcp/",
            ".pytest_cache/",
        ]

    existing = gitignore.read_text(encoding="utf-8", errors="ignore").splitlines() if gitignore.exists() else []
    to_add = [p for p in patterns if p not in existing]
    if to_add:
        with gitignore.open("a", encoding="utf-8") as fh:
            for p in to_add:
                fh.write(p + "\n")
        print("")
        print(f"   + {len(to_add)} entradas añadidas a .gitignore")

    print("")
    print(f"✅ Kuraka montado en {target}/{platform_dir.name}/")
    print("")

    # auto-register in the vault registry
    if run_py("kuraka-init.py", "--target", str(target), "--register-only", "--yes", quiet=True) == 0:
        print("   ✓ registrado en el registro del vault (projects/)")
        print("")

    # offer to restore Kuraka history
    if (VAULT / "kuraka-restore.py").exists():
        restore_layer_args = (("--layer-root", ".codex/project", "--skip-overrides")
                              if target_env == "codex" else ())
        if tty:
            run_py("kuraka-restore.py", str(target), *restore_layer_args)
        else:
            run_py("kuraka-restore.py", str(target), "--check")
            print("   ℹ️  Para restaurar la historia (si la hay):")
            layer_hint = (' --layer-root .codex/project --skip-overrides'
                          if target_env == "codex" else '')
            print(f'      python3 "{VAULT / "kuraka-restore.py"}" "{target}"{layer_hint}   # pregunta antes de pegar')
        print("")

    # auto-seed from a pre-populated migration-example layer
    seed_src = artifacts / "migration-examples" / f"{target.name}-project-layer"
    if seed_src.is_dir():
        seeded = False
        if not (target / "kuraka.config.yaml").exists() and (seed_src / "kuraka.config.yaml").is_file():
            copy_file(seed_src / "kuraka.config.yaml", target / "kuraka.config.yaml")
            print(f"   ✓ kuraka.config.yaml sembrado (migration-examples/{target.name}-project-layer → raíz)")
            seeded = True

        proj_dst = platform_dir / "project"
        if not proj_dst.is_dir():
            sync_tree(seed_src, proj_dst, exclude=("kuraka.config.yaml", "README.md"))
            if target_env == "antigravity":
                sync_tree(seed_src, target / ".claude" / "project", exclude=("kuraka.config.yaml", "README.md"))
            print(f"   ✓ {platform_dir.name}/project/ sembrado (migration-examples/{target.name}-project-layer)")
            seeded = True
        if seeded:
            print("")

    # adoption check
    has_config = (target / "kuraka.config.yaml").exists()
    has_project = (platform_dir / "project").is_dir() or (target / ".claude" / "project").is_dir()
    layer_src = seed_src
    if not has_config or not has_project:
        print("⚠️  ATENCIÓN — ADOPCIÓN INCOMPLETA")
        print("")
        if not has_config:
            print("   ❌ kuraka.config.yaml NO existe en el proyecto.")
        if not has_project:
            print(f"   ❌ {platform_dir.name}/project/ NO existe en el proyecto.")
        print("")
        print("   Los agentes refactorizados (v0.3+) leen kuraka.config.yaml para")
        print(f"   paths y comandos, y {platform_dir.name}/project/ para convenciones y lecciones.")
        print("   Sin esos dos artefactos, los agentes van a fallar o degradar a")
        print("   guidance genérico.")
        print("")
        print("   Para completar la adopción:")
        print("")
        print(f'     export KURAKA_VAULT="{VAULT}"')
        if layer_src.is_dir():
            print(f'     SRC="$KURAKA_VAULT/kuraka-artifacts/migration-examples/{target.name}-project-layer"')
            if not has_config:
                print('     cp "$SRC/kuraka.config.yaml" ./kuraka.config.yaml   # config pre-rellenado → RAÍZ del repo')
            if not has_project:
                print(f"     mkdir -p {platform_dir.name}/project")
                print(f'     cp -R "$SRC/." {platform_dir.name}/project/   # (excepto kuraka.config.yaml y README.md)')
        else:
            if not has_config:
                print('     cp "$KURAKA_VAULT/kuraka-artifacts/config-schema.yaml" ./kuraka.config.yaml')
                print("     # editá kuraka.config.yaml con los valores reales del proyecto")
            if not has_project:
                print(f"     mkdir -p {platform_dir.name}/project")
                print("     # creá los archivos del layer a medida (ver kuraka-artifacts/migration-examples/README.md)")
        print("")

    # command catalog + start guide
    if target_env == "antigravity":
        cmd_dir = target / ".agent" / "workflows"
    elif target_env == "cursor":
        cmd_dir = target / ".cursor" / "commands"
    elif target_env == "codex":
        cmd_dir = target / ".codex" / "skills"
    else:
        cmd_dir = target / ".claude" / "commands"

    run_py("kuraka-export.py", "--catalog", str(cmd_dir), "--env", target_env, str(target))

    print("📋 NOTAS DEL MONTAJE:")
    print("")
    print("  • Unstage cualquier fichero personal ya indexado en git:")
    if target_env == "codex":
        print("     git restore --staged .codex/agents/ .codex/skills/ 2>/dev/null || true")
        print("     git restore --staged .codex/rules/16-agent-backup.md .codex/rules/17-kuraka-token-optimizations.md 2>/dev/null || true")
    else:
        print(f"     git restore --staged {platform_dir.name}/agents/ {platform_dir.name}/skills/ {platform_dir.name}/commands/ 2>/dev/null || true")
        print(f"     git restore --staged {platform_dir.name}/rules/16-agent-backup.md {platform_dir.name}/rules/17-kuraka-token-optimizations.md 2>/dev/null || true")
    print("")
    if synced_agents:
        print(f"  • Agentes sincronizados en {platform_dir.name}/.")
    else:
        print("  • Agentes ya presentes y sincronizados.")
    print("")
    print("  • (Recomendado) Componentes que potencian Kuraka:")
    print(f"     {VAULT}/RECOMMENDED-COMPONENTS.md")
    print("     → RTK (ahorro 70-90% de tokens), ui-ux-pro-max, Playwright MCP...")
    print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
