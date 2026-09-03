#!/usr/bin/env python3
"""kuraka-discover.py — find all Kuraka-mounted projects and reconcile the vault registry.

The registry (`projects/*.md`) is only as complete as what got registered. Projects
mounted with the old `mount-kuraka.sh` flow (which didn't register) drift out of view.
This scans the filesystem for the Kuraka marker (`<platform>/agents/po-analyst.md`, any
platform) and reconciles against the registry, in BOTH directions:

  - mounted + registered      → ✓ ok
  - mounted + NOT registered  → ❌ missing from registry (fix with --register)
  - registered + NOT mounted  → ⚠️ drift (registry points at a path with no live mount)
  - one path, SEVERAL slugs   → ⚠️ split store (the solution was renamed) → kuraka-merge-project.py

Read-only by default. With --register, the missing ones are added (via
`kuraka-init.py --register-only`, which never overwrites config/layer). Registered-but-
not-mounted entries are only reported, never auto-removed (e.g. sie_v2 on another branch).

  python3 kuraka-discover.py                 # report
  python3 kuraka-discover.py --register       # report + register the missing ones
  python3 kuraka-discover.py --roots ~/code,~/work
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

# Emit UTF-8 regardless of the console code page (Windows cp1252/cp850 crash guard).
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError, OSError):
        pass

DEFAULT_VAULT = "/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka"
DEFAULT_ROOTS = ["~/Desarrollos", "~/Documents/Trabajo"]
# A mount is recognised on ANY platform, not just Claude: an Antigravity-only
# project (.agents/) used to be reported as "registered but NOT mounted".
MARKERS = (
    (".claude", "agents", "po-analyst.md"),
    (".agents", "agents", "po-analyst.md"),
    (".cursor", "agents", "po-analyst.md"),
    (".codex", "agents", "po-analyst.toml"),
)
PRUNE = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build",
         ".next", ".nuxt", "target", ".pytest_cache", "vendor", ".cargo"}


def find_mounts(roots: list[Path], max_depth: int) -> list[Path]:
    found = []
    for root in roots:
        if not root.is_dir():
            continue
        base_depth = len(root.parts)
        for dirpath, dirnames, _files in os.walk(root):
            d = Path(dirpath)
            depth = len(d.parts) - base_depth
            if depth > max_depth:
                dirnames[:] = []
                continue
            if any((d / Path(*m)).exists() for m in MARKERS):
                found.append(d)
                dirnames[:] = []  # a Kuraka project — don't descend further
                continue
            dirnames[:] = [n for n in dirnames if n not in PRUNE and not n.startswith(".")]
    # de-dup + stable order
    return sorted({p.resolve() for p in found})


def registry_slugs(vault: Path) -> dict[Path, list[str]]:
    """Map registered project path -> the slugs registered for it.

    A path with MORE THAN ONE slug is a split store: the solution was renamed
    (or onboarded before its config had a name), so its history lives in two
    entries. Reads the unified layout (projects/<slug>/registry.md) and, for
    transition, any legacy top-level projects/*.md notes."""
    out: dict[Path, list[str]] = {}
    pdir = vault / "projects"
    if not pdir.is_dir():
        return out
    notes = list(pdir.glob("*/registry.md")) + list(pdir.glob("*.md"))
    for note in notes:
        for line in note.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = re.match(r"^path:\s*(.+?)\s*$", line)
            if m:
                label = note.parent.name if note.name == "registry.md" else note.name
                out.setdefault(Path(m.group(1).strip()).resolve(), []).append(label)
                break
    return out


def registry_paths(vault: Path) -> dict[Path, str]:
    """Back-compat view of registry_slugs(): one label per path."""
    return {p: slugs[0] for p, slugs in registry_slugs(vault).items()}


def register(vault: Path, project: Path) -> bool:
    init = vault / "kuraka-init.py"
    if not init.exists():
        return False
    r = subprocess.run([sys.executable, str(init), "--target", str(project),
                        "--register-only", "--yes"], capture_output=True, text=True, encoding="utf-8", errors="replace")
    return r.returncode == 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Discover Kuraka-mounted projects and reconcile the registry.")
    ap.add_argument("--vault", default=os.environ.get("KURAKA_VAULT", DEFAULT_VAULT))
    ap.add_argument("--roots", default=",".join(DEFAULT_ROOTS),
                    help="comma-separated dirs to scan (default: ~/Desarrollos,~/Documents/Trabajo)")
    ap.add_argument("--depth", type=int, default=6, help="max scan depth per root")
    ap.add_argument("--register", action="store_true", help="register the mounted-but-unregistered projects")
    args = ap.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    if not vault.is_dir():
        print(f"❌ vault no encontrado: {vault}", file=sys.stderr)
        return 1
    roots = [Path(r.strip()).expanduser() for r in args.roots.split(",") if r.strip()]

    mounted = [p for p in find_mounts(roots, args.depth) if p != vault]
    reg_all = registry_slugs(vault)
    dupes = {p: s for p, s in reg_all.items() if len(s) > 1}
    reg = {p: s[0] for p, s in reg_all.items()}
    reg_paths = set(reg)
    mounted_set = set(mounted)

    print(f"🔎 kuraka-discover · escaneando {', '.join(str(r) for r in roots)}")
    print("")

    missing = [p for p in mounted if p not in reg_paths]          # mounted, not registered
    ok = [p for p in mounted if p in reg_paths]                   # both
    drift = [p for p in reg_paths if p not in mounted_set]        # registered, not mounted

    for p in ok:
        print(f"   ✓ {p}")
    for p in missing:
        print(f"   ❌ sin registrar: {p}")
    for p in sorted(drift):
        print(f"   ⚠️ registrado pero NO montado: {p}  ({reg[p]})")

    for p, slugs in sorted(dupes.items()):
        print(f"   ⚠️ store PARTIDO en {len(slugs)} slugs: {p}  ({', '.join(sorted(slugs))})")

    print("")
    print(f"   montados: {len(mounted)} · registrados: {len(reg_paths)} · "
          f"sin registrar: {len(missing)} · drift: {len(drift)}"
          + (f" · duplicados: {len(dupes)}" if dupes else ""))

    if dupes:
        print("")
        print("   Un mismo directorio con dos slugs = la solución se renombró y su")
        print("   historia quedó partida. Fusionalos (el segundo argumento es el que queda):")
        for p, slugs in sorted(dupes.items()):
            a, b = sorted(slugs)[:2]
            print(f"     python3 kuraka-merge-project.py {a} {b} --dry-run")

    if missing and args.register:
        print("")
        print("   registrando los que faltan…")
        done = 0
        for p in missing:
            if register(vault, p):
                print(f"   + {p}")
                done += 1
            else:
                print(f"   ✗ falló: {p}")
        print(f"\n✅ {done}/{len(missing)} registrados.")
    elif missing:
        print("\n   → corre con --register para añadirlos al registro.")
    if drift:
        print("   → drift NO se auto-corrige (puede ser intencional: rama distinta, sin montar).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
