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
    if target_env == "antigravity" and src.suffix == ".md":
        text = src.read_text(encoding="utf-8", errors="ignore")
        text = text.replace(".claude/skills/", ".agents/skills/")
        text = text.replace(".claude/rules/", ".agents/rules/")
        text = text.replace(".claude/agents/", ".agents/agents/")
        text = text.replace(".claude/project/", ".agents/project/")
        text = text.replace(".claude/stack-profiles/", ".agents/stack-profiles/")
        text = text.replace(".claude/templates/", ".agents/templates/")
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


# ------------------------------------------------------------------------- main

def main() -> int:
    _enable_windows_ansi()

    # argument parsing for target directory and target platform
    target_dir_arg = None
    target_env = "claude"

    args_list = sys.argv[1:]
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
    if (platform_dir / "agents").is_dir():
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
            dst.mkdir(parents=True, exist_ok=True)
            before = count_top(dst)
            if category == "skills" and target_env == "antigravity":
                sync_antigravity_skills(src, dst)
            else:
                sync_tree(src, dst, exclude=("*.append.md",), target_env=target_env)
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
        for rule in ("16-agent-backup.md", "17-kuraka-token-optimizations.md"):
            src = VAULT / "rules" / rule
            if src.is_file():
                copy_file(src, platform_dir / "rules" / rule)
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
            sync_tree(artifacts / "stack-profiles", platform_dir / "stack-profiles")
            if target_env == "antigravity":
                sync_tree(artifacts / "stack-profiles", target / ".claude" / "stack-profiles")
            print("   ✓ stack-profiles/")
        if (artifacts / "templates").is_dir():
            sync_tree(artifacts / "templates", platform_dir / "templates")
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
    run_py("kuraka-restore.py", str(target), "--overrides-only")

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
            ".agents/.kuraka-mount-manifest.json",
            ".agent/workflows/",
            "# Per-cycle telemetry JSONs (noise; the consolidated DASHBOARD.md is tracked)",
            "docs/process/agent-telemetry/*.json",
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
            ".claude/.kuraka-mount-manifest.json",
            "# Per-cycle telemetry JSONs (noise; the consolidated DASHBOARD.md is tracked)",
            "docs/process/agent-telemetry/*.json",
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
        if tty:
            run_py("kuraka-restore.py", str(target))
        else:
            run_py("kuraka-restore.py", str(target), "--check")
            print("   ℹ️  Para restaurar la historia (si la hay):")
            print(f'      python3 "{VAULT / "kuraka-restore.py"}" "{target}"   # pregunta antes de pegar')
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
        cmd_dir = target / ".codex" / "prompts"
    else:
        cmd_dir = target / ".claude" / "commands"

    run_py("kuraka-export.py", "--catalog", str(cmd_dir), "--env", target_env, str(target))

    print("📋 NOTAS DEL MONTAJE:")
    print("")
    print("  • Unstage cualquier fichero personal ya indexado en git:")
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
