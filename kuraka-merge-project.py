#!/usr/bin/env python3
"""kuraka-merge-project.py — fuse two central-store entries of the SAME project.

Why this exists: the store is keyed by slug, and the slug comes from
`kuraka.config.yaml project.name` (else the folder name). Renaming a solution —
or onboarding it once before the config existed — creates a SECOND slug for the
same directory, and the project's history ends up split across both
(`plugginsqlagent` + `dbcanvas` → /Users/xmn/Desarrollos/PlugginSQLAgent, 2026-08).
`kuraka-discover.py` reports these; this merges them.

Policy: NON-DESTRUCTIVE toward the target. Files present only in the source are
copied in; a file present in BOTH with different content keeps the TARGET copy and
is reported (use --prefer-source to invert). The source entry is removed only after
a successful merge (--keep-source to leave it).

    python3 kuraka-merge-project.py <slug-viejo> <slug-actual> [--dry-run] [--yes]
    python3 kuraka-merge-project.py plugginsqlagent dbcanvas --yes
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from datetime import date
from pathlib import Path

import kuraka_common as kc

DEFAULT_VAULT = "/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka"

MERGE_TREES = ("layer", "state", "cycles", "overrides")


def err(msg: str) -> None:
    print(msg, file=sys.stderr)


def registry_path(note: Path) -> str:
    if not note.is_file():
        return ""
    for line in note.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"^path:\s*(.+?)\s*$", line)
        if m:
            return m.group(1).strip()
    return ""


def merge_tree(src: Path, dst: Path, prefer_source: bool,
               dry_run: bool) -> tuple[int, list[str]]:
    """Copy src→dst without clobbering. Returns (copied, conflicting rel paths)."""
    if not src.is_dir():
        return (0, [])
    copied = 0
    conflicts: list[str] = []
    for s in sorted(src.rglob("*")):
        if s.is_dir() or s.name.startswith("._"):
            continue
        rel = s.relative_to(src)
        d = dst / rel
        if d.exists():
            if d.read_bytes() == s.read_bytes():
                continue
            conflicts.append(rel.as_posix())
            if not prefer_source:
                continue
        if not dry_run:
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(s, d)
        copied += 1
    return (copied, conflicts)


def read_sidecar(p: Path) -> tuple[dict, list[str]]:
    fields, branches = {}, []
    if not p.is_file():
        return fields, branches
    for line in p.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = line.strip()
        if m.startswith("- "):
            branches.append(m[2:].strip())
        elif ":" in m and not m.endswith(":"):
            k, v = m.split(":", 1)
            fields[k.strip()] = v.strip()
    return fields, branches


def merge_sidecar(src: Path, dst: Path, slug: str, dry_run: bool) -> None:
    """Union of branches, latest of each date field. Target keeps its identity."""
    sf, sb = read_sidecar(src)
    df, db = read_sidecar(dst)
    if not sf and not df:
        return

    def latest(key: str) -> str:
        vals = [v for v in (sf.get(key), df.get(key)) if v and v != "—"]
        return max(vals) if vals else "—"

    branches = db + [b for b in sb if b not in db]
    lines = [
        f"project: {slug}",
        f"last_backup: {latest('last_backup')}",
        f"last_branch: {df.get('last_branch') or sf.get('last_branch', '')}",
        f"last_overrides: {latest('last_overrides')}",
        "branches:",
    ]
    lines += [f"  - {b}" for b in branches] or ["  []"]
    if not dry_run:
        dst.write_text("\n".join(lines) + "\n", encoding="utf-8")


def record_alias(note: Path, old_slug: str, dry_run: bool) -> None:
    """Keep the former name in the target's registry note: frontmatter `aliases`
    (so a discover/merge run recognises it) + a dated line in the body."""
    if not note.is_file():
        return
    text = note.read_text(encoding="utf-8", errors="ignore")
    if re.search(rf"^aliases:.*\b{re.escape(old_slug)}\b", text, re.M):
        return
    m = re.search(r"^aliases:\s*\[(.*?)\]\s*$", text, re.M)
    if m:
        current = [x.strip() for x in m.group(1).split(",") if x.strip()]
        current.append(old_slug)
        text = text[:m.start()] + f"aliases: [{', '.join(current)}]" + text[m.end():]
    else:
        text = re.sub(r"^(path:.*)$", rf"\1\naliases: [{old_slug}]", text, count=1, flags=re.M)
    note_line = (f"\n## Historial de nombres\n\n"
                 f"- `{old_slug}` → `{note.parent.name}` (fusionado {date.today().isoformat()}; "
                 f"la solución se renombró, el store estaba partido en dos slugs).\n")
    if "## Historial de nombres" in text:
        text = text.rstrip("\n") + f"\n- `{old_slug}` → `{note.parent.name}` " \
                                   f"(fusionado {date.today().isoformat()}).\n"
    else:
        text = text.rstrip("\n") + "\n" + note_line
    if not dry_run:
        note.write_text(text, encoding="utf-8")


def reslug_index(vault: Path, old: str, new: str, dry_run: bool) -> int:
    """Re-point the cross-project cycle index rows of the old slug."""
    idx = kc.store_root(vault) / "INDEX.md"
    if not idx.is_file():
        return 0
    lines = idx.read_text(encoding="utf-8", errors="ignore").splitlines()
    out, changed, seen = [], 0, set()
    for line in lines:
        if line.startswith("|"):
            cells = [c.strip() for c in line.split("|")]
            if len(cells) > 3 and cells[2] == old:
                line = line.replace(f"| {old} |", f"| {new} |", 1)
                changed += 1
            if len(cells) > 4 and cells[2] in (old, new):
                key = (new, cells[3])
                if key in seen:
                    continue  # the same cycle was indexed under both slugs
                seen.add(key)
        out.append(line)
    if changed and not dry_run:
        idx.write_text("\n".join(out) + "\n", encoding="utf-8")
    return changed


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Merge two central-store entries of the same project (rename fallout).")
    ap.add_argument("source", help="slug to absorb (the old name)")
    ap.add_argument("target", help="slug to keep (the current name)")
    ap.add_argument("--vault", default=os.environ.get("KURAKA_VAULT", DEFAULT_VAULT))
    ap.add_argument("--prefer-source", action="store_true",
                    help="on a content conflict keep the SOURCE file (default: target wins)")
    ap.add_argument("--keep-source", action="store_true", help="do not delete the source entry")
    ap.add_argument("--dry-run", action="store_true", help="report only")
    ap.add_argument("--yes", "-y", action="store_true", help="do not prompt")
    args = ap.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    src_dir = kc.project_dir(vault, args.source)
    dst_dir = kc.project_dir(vault, args.target)
    if not src_dir.is_dir():
        err(f"❌ no existe projects/{args.source}/")
        return 1
    if not dst_dir.is_dir():
        err(f"❌ no existe projects/{args.target}/")
        return 1
    if src_dir == dst_dir:
        err("❌ source y target son el mismo slug")
        return 1

    sp = registry_path(kc.registry_note(vault, args.source))
    tp = registry_path(kc.registry_note(vault, args.target))
    print(f"🔗 kuraka-merge-project · {args.source} → {args.target}"
          f"{'  (dry-run)' if args.dry_run else ''}")
    print(f"   origen:  projects/{args.source}/   path: {sp or '(sin registry)'}")
    print(f"   destino: projects/{args.target}/   path: {tp or '(sin registry)'}")
    if sp and tp and Path(sp) != Path(tp):
        print("")
        print("   ⚠️  los dos registros apuntan a rutas DISTINTAS — no parece un rename.")
        if not args.yes:
            try:
                if input("   ¿Fusionar igual? [s/N]: ").strip().lower() not in ("s", "si", "sí", "y", "yes"):
                    print("   cancelado.")
                    return 0
            except EOFError:
                print("   cancelado.")
                return 0
    print("")

    if not args.yes and not args.dry_run:
        try:
            if input(f"   ¿Fusionar y eliminar projects/{args.source}/? [s/N]: ").strip().lower() \
                    not in ("s", "si", "sí", "y", "yes"):
                print("   cancelado.")
                return 0
        except EOFError:
            print("   cancelado (sin TTY: usá --yes).")
            return 0

    total_conflicts: list[str] = []
    for tree in MERGE_TREES:
        copied, conflicts = merge_tree(src_dir / tree, dst_dir / tree,
                                       args.prefer_source, args.dry_run)
        total_conflicts += [f"{tree}/{c}" for c in conflicts]
        if copied or conflicts:
            print(f"   {tree}/  ← {copied} archivo(s) copiado(s)"
                  + (f", {len(conflicts)} conflicto(s)" if conflicts else ""))

    merge_sidecar(src_dir / "backup.yaml", dst_dir / "backup.yaml", args.target, args.dry_run)
    n_idx = reslug_index(vault, args.source, args.target, args.dry_run)
    if n_idx:
        print(f"   INDEX.md ← {n_idx} fila(s) re-apuntada(s) a {args.target}")
    record_alias(kc.registry_note(vault, args.target), args.source, args.dry_run)
    print(f"   registry.md ← alias `{args.source}` registrado en {args.target}")

    if total_conflicts:
        keeper = "origen" if args.prefer_source else "destino"
        print("")
        print(f"   ⚠️  {len(total_conflicts)} archivo(s) presentes en ambos con contenido"
              f" distinto — se conservó el del {keeper}:")
        for c in total_conflicts[:15]:
            print(f"      · {c}")
        if len(total_conflicts) > 15:
            print(f"      … y {len(total_conflicts) - 15} más")

    if not args.keep_source and not args.dry_run:
        shutil.rmtree(src_dir)
        print("")
        print(f"   🗑️  projects/{args.source}/ eliminado")

    print("")
    print(f"✅ {args.source} fusionado en {args.target}."
          if not args.dry_run else f"✅ dry-run completo (no se escribió nada).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
