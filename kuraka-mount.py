#!/usr/bin/env python3
"""kuraka-mount.py — mount the Kuraka vault into a consumer project.

Cross-platform (macOS / Linux / Windows) canonical implementation of the mount.
Replaces the old rsync/bash `mount-kuraka.sh` (which is now a thin wrapper around
this). No external dependencies — pure Python 3 + git. Sibling scripts are invoked
via `sys.executable` so it never assumes a `python3` on PATH (key on Windows).

What it does (same as before):
  1. banner + (TTY) interactive menu of categories / status-only + MCP detection
  2. pre-flight snapshot of local overrides, then copy the vault categories in
  3. re-apply project overrides on top, update .gitignore, register, offer restore
  4. auto-seed a migration-example layer, adoption check, command catalog + guide

Usage:  python3 kuraka-mount.py [target_dir]     (default: CWD)
"""

from __future__ import annotations

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
        # ENABLE_PROCESSED_OUTPUT | ENABLE_WRAP_AT_EOL_OUTPUT | ENABLE_VIRTUAL_TERMINAL_PROCESSING
        k.SetConsoleMode(k.GetStdHandle(-11), 7)
    except Exception:
        pass


def color_ok() -> bool:
    return sys.stdout.isatty() and not os.environ.get("NO_COLOR")


def run_py(script: str, *args: str, quiet: bool = False, check_env: bool = True):
    """Invoke a sibling vault script with the current interpreter. When quiet,
    capture+swallow output and never raise. Otherwise inherit stdio (so prompts
    and colored output pass through). Returns the returncode (or None on error)."""
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
    """Top-level .md/.sh files (matches the old `find -maxdepth 1` counter)."""
    if not dstdir.is_dir():
        return 0
    return sum(1 for p in dstdir.iterdir() if p.is_file() and p.suffix in (".md", ".sh"))


def _excluded(rel: Path, exclude: tuple[str, ...]) -> bool:
    return any(fnmatch(part, pat) for part in rel.parts for pat in exclude)


def sync_tree(src: Path, dst: Path, exclude: tuple[str, ...] = ()) -> None:
    """Mirror src→dst with `rsync --update` semantics: copy a file only if the
    destination is missing or older than the source. Skips paths whose any part
    matches an exclude glob (e.g. '*.append.md', '__pycache__')."""
    import shutil
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
            dp.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(sp, dp)


def copy_file(src: Path, dst: Path) -> None:
    import shutil
    if src.is_file():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


# ------------------------------------------------------------------------- main

def main() -> int:
    _enable_windows_ansi()
    target = Path(sys.argv[1] if len(sys.argv) > 1 else os.getcwd()).expanduser().resolve()

    if not VAULT.is_dir():
        print(f"❌ ERROR: vault no encontrado en {VAULT}", file=sys.stderr)
        return 1
    if not target.is_dir():
        print(f"❌ ERROR: target no existe: {target}", file=sys.stderr)
        return 1

    banner()
    print(f"   vault:  {VAULT}")
    print(f"   target: {target}")
    print("")

    claude = target / ".claude"
    claude.mkdir(parents=True, exist_ok=True)

    selected = {"agents", "skills", "commands", "rules", "artifacts"}
    menu_mode = "all"
    tty = sys.stdin.isatty()

    if tty:
        if (claude / "agents").is_dir():
            print("ℹ️  Kuraka YA está montado en este proyecto → esto es un re-mount (update).")
        else:
            print("🆕 Primer montaje de Kuraka en este proyecto.")
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

    # MCP + component detection (interactive only; single source of truth)
    if tty:
        run_py("kuraka-init.py", "--recommend-only", "--target", str(target))

    if menu_mode == "status":
        print("ℹ️  Modo 'solo estado' — no se montó nada.")
        return 0

    def want(cat: str) -> bool:
        return cat in selected

    # pre-flight: snapshot local overrides BEFORE the copy overwrites them.
    if (claude / "agents").is_dir():
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
        dst = claude / category
        if src.is_dir():
            dst.mkdir(parents=True, exist_ok=True)
            before = count_top(dst)
            sync_tree(src, dst, exclude=("*.append.md",))
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
        sync_tree(VAULT / "agents" / "contexts", claude / "agents" / "contexts")
        print("   ✓ agents/contexts/")

    # personal rules (meta-rules of the agent system)
    if want("rules"):
        for rule in ("16-agent-backup.md", "17-kuraka-token-optimizations.md"):
            src = VAULT / "rules" / rule
            if src.is_file():
                copy_file(src, claude / "rules" / rule)
                print(f"   ✓ rules/{rule}")

    # framework-level artifacts outside .claude/
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
            sync_tree(artifacts / "stack-profiles", claude / "stack-profiles")
            print("   ✓ stack-profiles/")
        if (artifacts / "templates").is_dir():
            sync_tree(artifacts / "templates", claude / "templates")
            print("   ✓ templates/")

    # record the vault baseline of what was just mounted, so override detection
    # can tell "never touched by the project" (stale → refresh next mount) from
    # "project-edited" (real override → preserve). Written BEFORE re-applying
    # overrides: the manifest must hold the vault baseline, not the override.
    try:
        import kuraka_common as _kc
        mounted_cats = tuple(c for c in _kc.OVERRIDE_CATEGORIES if want(c))
        if mounted_cats:
            n = _kc.write_mount_manifest(target, VAULT, mounted_cats)
            print(f"   ✓ mount manifest ({n} vault baselines → .claude/{_kc.MOUNT_MANIFEST_NAME})")
    except ImportError:
        print("   ⚠ kuraka_common.py not found — mount manifest skipped (override detection stays legacy)")

    # re-apply project-specific overrides on top of the fresh copy (always)
    run_py("kuraka-restore.py", str(target), "--overrides-only")

    # --- ensure .gitignore excludes personal content ---
    gitignore = target / ".gitignore"
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
    print(f"✅ Kuraka montado en {target}/.claude/")
    print("")

    # auto-register in the vault registry (best-effort)
    if run_py("kuraka-init.py", "--target", str(target), "--register-only", "--yes", quiet=True) == 0:
        print("   ✓ registrado en el registro del vault (projects/)")
        print("")

    # offer to restore Kuraka history (branch-switch recovery)
    if (VAULT / "kuraka-restore.py").exists():
        if tty:
            run_py("kuraka-restore.py", str(target))
        else:
            run_py("kuraka-restore.py", str(target), "--check")
            print("   ℹ️  Para restaurar la historia (si la hay):")
            print(f'      python3 "{VAULT / "kuraka-restore.py"}" "{target}"   # pregunta antes de pegar')
        print("")

    # auto-seed from a pre-populated migration-example layer (first-time adoption)
    seed_src = artifacts / "migration-examples" / f"{target.name}-project-layer"
    if seed_src.is_dir():
        seeded = False
        if not (target / "kuraka.config.yaml").exists() and (seed_src / "kuraka.config.yaml").is_file():
            copy_file(seed_src / "kuraka.config.yaml", target / "kuraka.config.yaml")
            print(f"   ✓ kuraka.config.yaml sembrado (migration-examples/{target.name}-project-layer → raíz)")
            seeded = True
        if not (claude / "project").is_dir():
            sync_tree(seed_src, claude / "project", exclude=("kuraka.config.yaml", "README.md"))
            print(f"   ✓ .claude/project/ sembrado (migration-examples/{target.name}-project-layer)")
            seeded = True
        if seeded:
            print("")

    # adoption check
    has_config = (target / "kuraka.config.yaml").exists()
    has_project = (claude / "project").is_dir()
    layer_src = seed_src
    if not has_config or not has_project:
        print("⚠️  ATENCIÓN — ADOPCIÓN INCOMPLETA")
        print("")
        if not has_config:
            print("   ❌ kuraka.config.yaml NO existe en el proyecto.")
        if not has_project:
            print("   ❌ .claude/project/ NO existe en el proyecto.")
        print("")
        print("   Los agentes refactorizados (v0.3+) leen kuraka.config.yaml para")
        print("   paths y comandos, y .claude/project/ para convenciones y lecciones.")
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
                print("     mkdir -p .claude/project")
                print('     cp -R "$SRC/." .claude/project/   # (excepto kuraka.config.yaml y README.md)')
        else:
            if not has_config:
                print('     cp "$KURAKA_VAULT/kuraka-artifacts/config-schema.yaml" ./kuraka.config.yaml')
                print("     # editá kuraka.config.yaml con los valores reales del proyecto")
            if not has_project:
                print("     mkdir -p .claude/project")
                print("     # creá los archivos del layer a medida (ver kuraka-artifacts/migration-examples/README.md)")
        print("")

    # command catalog + start guide (single source: kuraka-export.py)
    run_py("kuraka-export.py", "--catalog", str(claude / "commands"), "--env", "claude", str(target))

    print("📋 NOTAS DEL MONTAJE:")
    print("")
    print("  • Unstage cualquier fichero personal ya indexado en git:")
    print("     git restore --staged .claude/agents/ .claude/skills/ .claude/commands/ .claude/hooks/ 2>/dev/null || true")
    print("     git restore --staged .claude/rules/16-agent-backup.md .claude/rules/17-kuraka-token-optimizations.md 2>/dev/null || true")
    print("")
    if synced_agents:
        print("  • ⚠️  Reinicia Claude Code (/exit + nueva sesión) para registrar los agentes")
        print("     como subagent_type — el runtime lee .claude/agents/ solo al arrancar.")
    else:
        print("  • Agentes ya presentes y sincronizados. No hace falta reiniciar.")
    print("")
    print("  • (Recomendado) Componentes que potencian Kuraka:")
    print(f"     {VAULT}/RECOMMENDED-COMPONENTS.md")
    print("     → RTK (ahorro 70-90% de tokens), ui-ux-pro-max, Playwright MCP...")
    print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
