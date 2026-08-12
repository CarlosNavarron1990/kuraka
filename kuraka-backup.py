#!/usr/bin/env python3
"""kuraka-backup.py — snapshot a project's FULL Kuraka state into the central vault.

Why this exists: Kuraka generates lots of artifacts in a consumer project (the
.claude/project specialization layer, REQ/stories/test-plans/schemas under
docs/process, RETROs + telemetry). Users often DON'T commit those to the
solution's git (only source). On a branch switch they get lost. This copies the
whole Kuraka state back to the central store so it survives, branch-aware and
restorable to any branch (see kuraka-restore.py).

Runs automatically at cycle close (Phase 7, via final-auditor / run-audit) and
on demand. Copies (never moves); idempotent. No external dependencies.

Central layout (single directory per project):
    <vault>/projects/<slug>/
        layer/        ← <platform-layer>/**          (specialization layer)
        state/        ← docs/process/**              (in-flight Kuraka artifacts)
        cycles/<REQ>/ ← RETRO + telemetry + meta     (closed-cycle diagnostics)
        backup.yaml   ← last_backup, last_branch, branches[]

Usage:
    python3 kuraka-backup.py /path/to/project [--name slug] [--layer-root .codex/project] [--cycles-only] [--force]
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path

import kuraka_common as kc

DEFAULT_VAULT = "/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka"


def err(msg: str) -> None:
    print(msg, file=sys.stderr)


def update_backup_sidecar(vault: Path, slug: str, branch: str, today: str) -> None:
    """Track which branches this project has been backed up from (accumulative)."""
    side = kc.project_dir(vault, slug) / "backup.yaml"
    branches: list[str] = []
    if side.exists():
        for line in side.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = line.strip()
            if m.startswith("- "):
                branches.append(m[2:].strip())
    if branch and branch not in branches:
        branches.append(branch)
    lines = [
        f"project: {slug}",
        f"last_backup: {today}",
        f"last_branch: {branch}",
        "branches:",
    ]
    lines += [f"  - {b}" for b in branches] or ["  []"]
    side.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Snapshot a project's Kuraka state into the vault.")
    ap.add_argument("project", nargs="?", help="consumer project root")
    ap.add_argument("--project", dest="project_opt", help="consumer project root")
    ap.add_argument("--name", help="slug override (default: config project.name or folder)")
    ap.add_argument("--vault", default=os.environ.get("KURAKA_VAULT", DEFAULT_VAULT))
    ap.add_argument("--docs-root", default="docs/process", help="project-relative docs/process root")
    ap.add_argument("--layer-root", default=".claude/project",
                    help="project-relative specialization layer (default: .claude/project)")
    ap.add_argument("--cycles-only", action="store_true", help="only archive RETROs+telemetry (skip layer/state)")
    ap.add_argument("--overrides-only", action="store_true", help="only snapshot agent/skill/command overrides")
    ap.add_argument("--skip-overrides", action="store_true",
                    help="do not snapshot platform overrides (used by Codex projection)")
    ap.add_argument("--force", action="store_true", help="re-copy cycles already present")
    args = ap.parse_args()

    try:
        sys.stdout.reconfigure(line_buffering=True)
    except (AttributeError, ValueError):
        pass

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
    branch = kc.git_branch(project)
    today = date.today().isoformat()

    print(f"🗄️  kuraka-backup · {slug}  (rama: {branch})")
    print(f"   proyecto: {project}")
    print(f"   destino:  {kc.project_dir(vault, slug)}/")
    print("")

    # --overrides-only: lightweight pre-flight (called by mount before the vault
    # rsync clobbers any local agent tuning). Snapshot overrides and stop.
    if args.overrides_only:
        if args.skip_overrides:
            print("   overrides/ omitidos para esta proyección de plataforma")
            return 0
        n_ov = kc.snapshot_overrides(project, vault, slug)
        print(f"   overrides/ ← .claude/{{agents,skills,commands}}   ({n_ov} archivo(s) divergente(s))")
        print("")
        print(f"✅ overrides de {slug} respaldados.")
        return 0

    if not args.cycles_only:
        # layer = platform-specific project specialization
        layer_src = project / args.layer_root
        n_layer = kc.snapshot_tree(layer_src, kc.layer_dir(vault, slug))
        print(f"   layer/  ← {args.layer_root.rstrip('/')}/        ({n_layer} archivos)")
        # state = docs/process (REQ, stories, test-plans, schemas, checkpoints, …)
        state_src = project / args.docs_root
        n_state = kc.snapshot_tree(state_src, kc.state_dir(vault, slug) / "docs-process")
        print(f"   state/  ← {args.docs_root}/   ({n_state} archivos)")

    rows = kc.archive_cycles(project, vault, slug, branch, args.docs_root, args.force)
    n_arch = sum(1 for r in rows if r["status"] == "archived")
    added = kc.update_index(vault, rows, slug, args.force)
    print(f"   cycles/ ← {n_arch} ciclo(s) nuevo(s) "
          f"({len(rows) - n_arch} ya estaban), {added} fila(s) en INDEX.md")

    # overrides = project-specific agent/skill/command tunings (diverge from vault)
    if args.skip_overrides:
        print("   overrides/ omitidos para esta proyección de plataforma")
    else:
        n_ov = kc.snapshot_overrides(project, vault, slug)
        print(f"   overrides/ ← .claude/{{agents,skills,commands}}   ({n_ov} archivo(s) divergente(s))")

    update_backup_sidecar(vault, slug, branch, today)
    print("")
    print(f"✅ backup completo de {slug} (rama {branch}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
