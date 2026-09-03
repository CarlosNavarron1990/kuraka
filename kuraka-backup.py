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
        overrides/<platform>/<cat>/ ← project agent/skill/command tuning
        backup.yaml   ← last_backup, last_overrides, last_branch, branches[]

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


def update_backup_sidecar(vault: Path, slug: str, branch: str, today: str,
                          overrides_only: bool = False,
                          overrides_done: bool = True) -> None:
    """Track which branches this project has been backed up from (accumulative).

    A `--overrides-only` run (the mount pre-flight) does NOT move `last_backup`
    — that date means "full state snapshotted at cycle close". It records
    `last_overrides` instead, so a store can be told 'mounted recently, never
    fully backed up' from 'stale'."""
    side = kc.project_dir(vault, slug) / "backup.yaml"
    branches: list[str] = []
    prev: dict[str, str] = {}
    if side.exists():
        for line in side.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = line.strip()
            if m.startswith("- "):
                branches.append(m[2:].strip())
            elif ":" in m and not m.endswith(":"):
                k, v = m.split(":", 1)
                prev[k.strip()] = v.strip()
    if branch and branch not in branches:
        branches.append(branch)
    last_backup = prev.get("last_backup", "—") if overrides_only else today
    last_branch = prev.get("last_branch", branch) if overrides_only else branch
    lines = [
        f"project: {slug}",
        f"last_backup: {last_backup}",
        f"last_branch: {last_branch}",
        f"last_overrides: {today if overrides_done else prev.get('last_overrides', '—')}",
        "branches:",
    ]
    lines += [f"  - {b}" for b in branches] or ["  []"]
    side.parent.mkdir(parents=True, exist_ok=True)
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
    ap.add_argument("--target", choices=("claude", "antigravity", "cursor", "codex"), help="target platform")
    ap.add_argument("--platform", help="platform directory name (e.g. agents, claude, codex, cursor)")
    ap.add_argument("--cycles-only", action="store_true", help="only archive RETROs+telemetry (skip layer/state)")
    ap.add_argument("--overrides-only", action="store_true", help="only snapshot agent/skill/command overrides")
    ap.add_argument("--skip-overrides", action="store_true",
                    help="do not snapshot platform overrides (used by Codex projection)")
    ap.add_argument("--force", action="store_true", help="re-copy cycles already present")
    ap.add_argument("--allow-incomplete-retro", action="store_true",
                    help="archive a cycle whose RETRO has no `## Confidence:` line "
                         "(deliberate exception; the cycle stays unusable for "
                         "cross-project comparison)")
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

    # Guard against a silent store split: this directory may already own an entry
    # under another slug (the config's project.name was edited, or `amauta` wrote
    # a different one). Backing up under the new slug would strand the existing
    # history. The registered slug wins unless --name says otherwise.
    registered = kc.registered_slug_for_path(vault, project)
    if registered and registered != slug and not args.name:
        err(f"⚠️  este proyecto ya está registrado como «{registered}», pero "
            f"kuraka.config.yaml dice «{slug}».")
        err(f"   Uso «{registered}» para no partir su historia "
            f"({kc.project_dir(vault, registered)}).")
        err(f"   Si el rename es intencional: cambiá `path:` en el registry y corré")
        err(f"     python3 kuraka-merge-project.py {registered} {slug}")
        err("")
        slug = registered

    platform = kc.detect_platform(project, args.target, args.platform)

    layer_root = args.layer_root
    if layer_root == ".claude/project":
        p_dir = kc.platform_dirname(platform)
        if (project / p_dir / "project").is_dir() or platform != "claude":
            layer_root = f"{p_dir}/project"

    print(f"🗄️  kuraka-backup · {slug}  (rama: {branch}, plataforma: {platform})")
    print(f"   proyecto: {project}")
    print(f"   destino:  {kc.project_dir(vault, slug)}/")
    print("")

    # --overrides-only: lightweight pre-flight (called by mount before the vault
    # rsync clobbers any local agent tuning). Snapshot overrides and stop.
    if args.overrides_only:
        if args.skip_overrides:
            print("   overrides/ omitidos para esta proyección de plataforma")
            return 0
        n_ov = kc.snapshot_overrides(project, vault, slug, platform=platform)
        p_name = kc.platform_dirname(platform)
        print(f"   overrides/{kc.store_platform(platform)}/ ← {p_name}/{{agents,skills,commands}}"
              f"   ({n_ov} archivo(s) divergente(s))")
        # Only for a REGISTERED project: a pre-flight on a throwaway/unregistered
        # target must leave no trace in projects/.
        if kc.registry_note(vault, slug).is_file():
            update_backup_sidecar(vault, slug, branch, today, overrides_only=True)
        print("")
        print(f"✅ overrides de {slug} respaldados.")
        return 0

    if not args.cycles_only:
        # layer = platform-specific project specialization
        layer_src = project / layer_root
        n_layer = kc.snapshot_tree(layer_src, kc.layer_dir(vault, slug))
        print(f"   layer/  ← {layer_root.rstrip('/')}/        ({n_layer} archivos)")
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
        n_ov = kc.snapshot_overrides(project, vault, slug, platform=platform)
        p_name = kc.platform_dirname(platform)
        print(f"   overrides/{kc.store_platform(platform)}/ ← {p_name}/{{agents,skills,commands}}"
              f"   ({n_ov} archivo(s) divergente(s))")


    update_backup_sidecar(vault, slug, branch, today,
                          overrides_done=not args.skip_overrides)
    print("")

    # Cycle-close contract, enforced HERE because this is the only gate every
    # platform runs. Hooks are Claude-only; on Antigravity/Cursor/Codex the
    # framework relied on prose, and prose alone produced whole projects of
    # verdict-less cycles (camisassis: 16 of 16) — archived, but invisible to
    # pattern-detector and to any cross-project comparison. Phase 7's hard exit
    # criterion is already "kuraka-backup exits 0", so refusing here turns the
    # rule into a deterministic gate on every editor, with no hook API needed.
    # Scope: what this run archived, PLUS the most recent cycle in the store —
    # otherwise simply re-running the backup without fixing anything would pass
    # (the second time the cycle is "already archived" and gets skipped).
    # The older pile is left to kuraka-doctor to report, never to block on.
    def _meta(req: str) -> str:
        m = kc.cycles_dir(vault, slug) / req / "meta.yaml"
        return m.read_text(encoding="utf-8", errors="ignore") if m.is_file() else ""

    to_check = {r["req"] for r in rows if r["status"] == "archived"}
    latest = kc.latest_cycle(vault, slug)
    if latest:
        to_check.add(latest)
    no_verdict = sorted(r for r in to_check if 'verdict: ""' in _meta(r))
    no_telem = sorted(r for r in to_check if "has_telemetry: false" in _meta(r))
    if no_telem:
        err(f"⚠️  {len(no_telem)} ciclo(s) archivados SIN telemetría: "
            f"{', '.join(no_telem[:3])}"
            + (" …" if len(no_telem) > 3 else ""))
        err(f"   escribí `<REQ>-telemetry.json` en {args.docs_root}/agent-telemetry/ "
            f"(métricas no disponibles = `null`/`unknown`, nunca 0) y re-corré este backup.")
        err("")
    if no_verdict and not args.allow_incomplete_retro:
        err(f"❌ el estado se respaldó, pero el ciclo NO cierra: "
            f"{len(no_verdict)} RETRO sin la línea de veredicto.")
        for req in no_verdict[:5]:
            err(f"   · {req}")
        err("")
        err("   Agregá como ÚLTIMA línea de cada RETRO:")
        err("       ## Confidence: HIGH | MEDIUM | LOW")
        err("   La parsea find_verdict hacia cycles/<REQ>/meta.yaml y hacia")
        err("   projects/INDEX.md — sin ella el ciclo no cuenta para pattern-detector.")
        err("   Después re-corré este backup (el meta se rellena solo).")
        err("   Excepción deliberada: --allow-incomplete-retro")
        return 1

    print(f"✅ backup completo de {slug} (rama {branch}).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
