#!/usr/bin/env python3
"""kuraka-restore.py — restore a project's Kuraka history from the central vault.

The companion to kuraka-backup.py. When you switch/create a branch and re-mount
Kuraka, the project's .claude/project layer and docs/process artifacts may be
gone (they were never in the solution's git). If the central store has history
for this project, this pastes it back — so you continue with the full accumulated
history on the new branch.

Safe by default: never overwrites an existing file in the project unless --force.
Restores layer (default: .claude/project) + state (docs/process); cycles/ stay central.

Usage:
    python3 kuraka-restore.py /path/to/project            # interactive prompt
    python3 kuraka-restore.py /path/to/project --yes      # restore without asking
    python3 kuraka-restore.py /path/to/project --check    # only report what exists
    python3 kuraka-restore.py /path/to/project --force    # overwrite existing files
    python3 kuraka-restore.py /path/to/project --layer-root .codex/project
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import kuraka_common as kc

DEFAULT_VAULT = "/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka"


def err(msg: str) -> None:
    print(msg, file=sys.stderr)


def restore_tree(src: Path, dst: Path, force: bool) -> tuple[int, int]:
    """Copy src→dst. Skip files already present unless force. Returns (copied, skipped)."""
    if not src.is_dir():
        return (0, 0)
    copied = skipped = 0
    for s in src.rglob("*"):
        if s.is_dir():
            continue
        rel = s.relative_to(src)
        d = dst / rel
        if d.exists() and not force:
            skipped += 1
            continue
        d.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(s, d)
        copied += 1
    return (copied, skipped)


def summarize(vault: Path, slug: str) -> str:
    p = kc.project_dir(vault, slug)
    parts = []
    for sub in ("layer", "state", "cycles", "overrides"):
        d = p / sub
        n = sum(1 for _ in d.rglob("*") if _.is_file()) if d.is_dir() else 0
        parts.append(f"{sub}={n}")
    side = p / "backup.yaml"
    last = ""
    if side.exists():
        for line in side.read_text(encoding="utf-8", errors="ignore").splitlines():
            if line.startswith("last_backup:"):
                last = line.split(":", 1)[1].strip()
    return f"{', '.join(parts)} archivos" + (f" · último backup {last}" if last else "")


def main() -> int:
    ap = argparse.ArgumentParser(description="Restore a project's Kuraka history from the vault.")
    ap.add_argument("project", nargs="?", help="consumer project root")
    ap.add_argument("--project", dest="project_opt", help="consumer project root")
    ap.add_argument("--name", help="slug override (default: config project.name or folder)")
    ap.add_argument("--vault", default=os.environ.get("KURAKA_VAULT", DEFAULT_VAULT))
    ap.add_argument("--docs-root", default="docs/process", help="project-relative docs/process root")
    ap.add_argument("--layer-root", default=".claude/project",
                    help="project-relative specialization layer (default: .claude/project)")
    ap.add_argument("--target", choices=("claude", "antigravity", "cursor", "codex"), help="target platform")
    ap.add_argument("--platform", help="platform directory name (e.g. agents, claude, codex, cursor)")
    ap.add_argument("--yes", "-y", action="store_true", help="restore without prompting")
    ap.add_argument("--no", action="store_true", help="never restore (report only)")
    ap.add_argument("--overrides-only", action="store_true",
                    help="only re-apply agent/skill/command overrides (always; no prompt) — used by mount")
    ap.add_argument("--skip-overrides", action="store_true",
                    help="do not restore platform overrides (used by Codex projection)")
    ap.add_argument("--check", action="store_true", help="only report whether history exists")
    ap.add_argument("--force", action="store_true", help="overwrite existing project files")
    args = ap.parse_args()

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

    platform = args.platform
    if not platform:
        if args.target == "antigravity" or (project / ".agents").is_dir():
            platform = "agents"
        elif args.target == "codex" or (project / ".codex").is_dir():
            platform = "codex"
        elif args.target == "cursor" or (project / ".cursor").is_dir():
            platform = "cursor"
        else:
            platform = "claude"

    layer_root = args.layer_root
    if layer_root == ".claude/project":
        p_dir = f".{platform}" if not platform.startswith(".") else platform
        if (project / p_dir / "project").is_dir() or platform != "claude":
            layer_root = f"{p_dir}/project"

    # --overrides-only: unconditional, silent-unless-applied re-apply of the
    # project's own agent/skill/command tunings on top of the fresh vault copy.
    # Called by mount on every run (TTY or not) — overrides must never be lost.
    if args.overrides_only:
        if args.skip_overrides:
            return 0
        oc = kc.restore_overrides(vault, slug, project, platform=platform)
        if oc:
            p_name = f".{platform}" if not platform.startswith(".") else platform
            print(f"   ✓ overrides re-aplicados: {oc} archivo(s) ({p_name}/{{agents,skills,commands}}, pisando la copia del vault)")
        return 0

    if not kc.has_history(vault, slug):
        print(f"ℹ️  el central no tiene historia para «{slug}». Nada que restaurar.")
        return 0

    print(f"🔁 kuraka-restore · {slug}  (plataforma: {platform})")
    print(f"   historia en central: {summarize(vault, slug)}")

    if args.check:
        return 0

    proceed = args.yes
    if not proceed and not args.no:
        try:
            ans = input(f"   ¿Restaurar la historia guardada de «{slug}» y continuar el trabajo? [s/N]: ").strip().lower()
            proceed = ans in ("s", "si", "sí", "y", "yes")
        except EOFError:
            proceed = False
    if not proceed:
        print("   (no se restauró — corré con --yes para confirmar sin prompt)")
        return 0

    layer_dst = project / layer_root
    lc, ls = restore_tree(kc.layer_dir(vault, slug), layer_dst, args.force)
    sc, ss = restore_tree(kc.state_dir(vault, slug) / "docs-process", project / args.docs_root, args.force)
    print(f"   layer → {layer_root.rstrip('/')}/   ({lc} copiados, {ls} ya existían)")
    print(f"   state → {args.docs_root}/  ({sc} copiados, {ss} ya existían)")
    if (ls or ss) and not args.force:
        print("   nota: los que ya existían NO se pisaron — usá --force para sobrescribir.")

    # overrides ALWAYS win over the freshly-mounted vault copy (that's their point),
    # so they overwrite regardless of --force.
    if not args.skip_overrides:
        oc = kc.restore_overrides(vault, slug, project, platform=platform)
        if oc:
            p_name = f".{platform}" if not platform.startswith(".") else platform
            print(f"   overrides → {p_name}/{{agents,skills,commands}}   ({oc} re-aplicado(s), pisando la copia del vault)")
    print("")
    print(f"✅ restore de {slug} completo.")
    return 0



if __name__ == "__main__":
    raise SystemExit(main())
