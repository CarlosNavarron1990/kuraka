#!/usr/bin/env python3
"""kuraka-doctor.py — is this project's Kuraka state actually flowing?

Every defect fixed by hand on 2026-08-29/31 was silent: the mount exited 0, the
backup exited 0, and the store was still wrong (a whole agent suite snapshotted
as "overrides", 5 projects with no kuraka.config.yaml, telemetry never attached,
a rename splitting a project's history in two). A return code proved nothing —
so this checks the RESULT, not the exit status, and is wired into the lifecycle:

  · session start   → .claude/hooks/session_doctor.py (Claude), report only
  · cycle start     → skills/kuraka.md Prerequisites
  · cycle close     → Phase 7, next to the mandatory kuraka-backup.py
  · every mount     → kuraka-mount.py runs it at the end
  · on demand       → /kuraka-doctor

Checks, per mounted platform where it applies:

  registry   the directory is registered in the central store
  config     kuraka.config.yaml exists, and its project.name matches the slug
             the store already uses (a mismatch splits the history in two)
  layer      the platform's project/ specialization layer exists
  manifest   a mount manifest per platform, stamped with the vault's suite
  overrides  live divergences == what the store holds
  retros     every RETRO-*.md has its cycle archived
  telemetry  every cycle whose telemetry exists in the project has it attached
  state      docs/process mirrored into the store

Usage:
    python3 kuraka-doctor.py [project]        # default: $PWD
    python3 kuraka-doctor.py --all            # every registered project
    python3 kuraka-doctor.py [project] --fix  # apply the safe repairs, re-check
    python3 kuraka-doctor.py --brief          # one line unless something is wrong

Exit 0 = healthy · 1 = findings · 2 = could not run.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from pathlib import Path

import kuraka_common as kc

DEFAULT_VAULT = "/Users/xmn/Documents/Agentes/AgentesTrabajos/kuraka"
# Sibling tools live next to THIS file; `--vault` only says which store and which
# framework baseline to compare against (they coincide in normal use).
SCRIPTS = Path(__file__).resolve().parent

PLATFORM_TARGET = {"claude": "claude", "agents": "antigravity",
                   "codex": "codex", "cursor": "cursor"}

# how a finding is repaired: adopt (draft config/layer) | register | overrides |
# backup (cycles+telemetry+state) | remount | manual
class F:
    def __init__(self, code: str, msg: str, fix: str = "manual", hint: str = ""):
        self.code, self.msg, self.fix, self.hint = code, msg, fix, hint


def err(m: str) -> None:
    print(m, file=sys.stderr)


def mounted_platforms(project: Path) -> list[str]:
    return [k for k in PLATFORM_TARGET
            if (project / f".{k}" / "agents").is_dir()
            or (project / f".{k}" / "skills").is_dir()]


def config_name(project: Path) -> "str | None":
    """project.name as declared, or None when there is no config at all."""
    cfg = project / "kuraka.config.yaml"
    if not cfg.is_file():
        return None
    inside = False
    for line in cfg.read_text(encoding="utf-8", errors="ignore").splitlines():
        if re.match(r"^project:\s*$", line):
            inside = True
            continue
        if inside:
            m = re.match(r"^ {1,4}name:\s*(.+?)\s*$", line)
            if m:
                return m.group(1).strip().strip("\"'")
            if re.match(r"^\S", line):
                break
    return ""


def retro_reqs(project: Path, docs_root: str) -> set:
    out = set()
    for d in kc._retro_dirs(project, docs_root):
        for f in d.glob("RETRO-*.md"):
            if f.name != "RETRO-LATEST.md":
                out.add(f.stem[len("RETRO-"):])
    return out


def diagnose(vault: Path, project: Path, slug: str, docs_root: str) -> list:
    findings: list = []
    plats = mounted_platforms(project)
    if not plats:
        return [F("mount", "el proyecto no tiene Kuraka montado", "remount")]

    if not kc.registry_note(vault, slug).is_file():
        findings.append(F("registry", f"no está registrado en el store como «{slug}»", "register"))

    cn = config_name(project)
    if cn is None:
        findings.append(F("config", "falta kuraka.config.yaml — los agentes pierden "
                                    "docs_process_root y dispersan su salida", "adopt"))
    elif cn and kc.slugify(cn) != slug:
        findings.append(F("config", f"el config dice «{kc.slugify(cn)}» pero el store usa «{slug}»: "
                                    f"el próximo backup partiría su historia", "manual",
                          f"alineá project.name a «{slug}», o: "
                          f"python3 kuraka-merge-project.py {slug} {kc.slugify(cn)}"))

    if not any((project / f".{k}" / "project").is_dir() for k in plats):
        findings.append(F("layer", "falta el layer de especialización del proyecto", "adopt"))

    suite = kc.suite_version(vault)
    for k in plats:
        if not (project / f".{k}" / kc.MOUNT_MANIFEST_NAME).is_file():
            findings.append(F("manifest", f".{k}/ sin mount manifest — la detección de "
                                          f"overrides queda a ciegas", "remount"))
        else:
            v = kc.mounted_suite_version(project, k)
            if v != suite:
                findings.append(F("suite", f".{k}/ montado con la suite {v} (vault: {suite})",
                                  "remount"))
        live = {x.as_posix() for x in kc.detect_overrides(project, vault, platform=k)}
        store_dir = kc.overrides_dir(vault, slug, k)
        stored = {f.relative_to(store_dir).as_posix()
                  for f in store_dir.rglob("*.md")} if store_dir.is_dir() else set()
        stored.discard("MANIFEST.md")
        if live != stored:
            findings.append(F("overrides", f".{k}/: {len(live)} ajuste(s) locales vs "
                                           f"{len(stored)} en el store", "overrides"))

    reqs = retro_reqs(project, docs_root)
    cyc_dir = kc.cycles_dir(vault, slug)
    cycles = {d.name for d in cyc_dir.iterdir() if d.is_dir()} if cyc_dir.is_dir() else set()
    missing = reqs - cycles
    if missing:
        findings.append(F("retros", f"{len(missing)} RETRO sin archivar en el vault "
                                    f"({sorted(missing)[0]}…)", "backup"))

    telem_dir = project / docs_root / "agent-telemetry"
    telem = {f.name[:-len(kc.TELEMETRY_SUFFIX)] if f.name.endswith(kc.TELEMETRY_SUFFIX)
             else f.stem for f in telem_dir.glob("*.json")} if telem_dir.is_dir() else set()
    orphan = [c for c in cycles & telem
              if not any((cyc_dir / c).glob("*.json"))]
    if orphan:
        findings.append(F("telemetry", f"{len(orphan)} ciclo(s) con telemetría en el "
                                       f"proyecto pero no adjunta en el store", "backup"))

    # A RETRO with no `## Confidence:` line archives fine but lands in INDEX.md
    # with an empty verdict, so the cycle counts for nothing in any cross-project
    # comparison. Only the LAST closed cycle is actionable — that is the one you
    # can still fix; the historical pile (petsuite: 47, camisassis: 16 of 16) is
    # reported as context, never as a chore to go edit 47 old files.
    dated = []
    verdictless = set()
    for c in cycles:
        meta = cyc_dir / c / "meta.yaml"
        if not meta.is_file():
            continue
        txt = meta.read_text(encoding="utf-8", errors="ignore")
        m = re.search(r"^archived_at:\s*(\S+)", txt, re.M)
        dated.append((m.group(1) if m else "", c))
        if 'verdict: ""' in txt:
            verdictless.add(c)
    # Same scoping for a cycle closed with NO telemetry at all. On Claude the
    # PostToolUse hook writes it; the platforms without hooks only have the
    # manual prose, and that is how camisassis closed 16 cycles with none.
    if dated:
        last_c = max(dated)[1]
        if not any((cyc_dir / last_c).glob("*.json")):
            findings.append(F("telemetry", f"el último ciclo cerrado ({last_c}) se archivó "
                                           f"sin telemetría", "manual",
                              "escribí `<REQ>-telemetry.json` en "
                              f"{docs_root}/agent-telemetry/ (métricas no disponibles = "
                              "`null`/`unknown`, nunca 0) y re-corré el backup"))

    if dated:
        last = max(dated)[1]
        if last in verdictless:
            extra = len(verdictless) - 1
            findings.append(F("verdict", f"el último ciclo cerrado ({last}) no tiene la línea "
                                         f"`## Confidence:`: queda invisible para pattern-detector"
                                         + (f" — y hay {extra} histórico(s) igual" if extra else ""),
                              "manual",
                              "agregá `## Confidence: HIGH|MEDIUM|LOW` como última línea del "
                              "RETRO y volvé a correr el backup (el meta se rellena solo)"))

    src = project / docs_root
    if src.is_dir():
        n_src = sum(1 for f in src.rglob("*") if f.is_file() and not f.name.startswith("._"))
        dst = kc.state_dir(vault, slug) / "docs-process"
        n_dst = sum(1 for f in dst.rglob("*")
                    if f.is_file() and not f.name.startswith("._")) if dst.is_dir() else 0
        if n_src and n_dst < n_src:
            findings.append(F("state", f"docs/process: {n_dst} de {n_src} archivos en el store",
                              "backup"))
    return findings


def repair(vault: Path, project: Path, slug: str, fixes: set) -> list:
    """Run only the safe, idempotent repairs. Returns the actions taken."""
    done = []
    plats = mounted_platforms(project) or ["claude"]
    primary = next((k for k in plats if (project / f".{k}" / "project").is_dir()), plats[0])

    def run(*args) -> bool:
        r = subprocess.run([sys.executable, *args], capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        return r.returncode == 0

    if "adopt" in fixes:
        layer_root = f".{primary}/project"
        if run(str(SCRIPTS / "kuraka-init.py"), "--target", str(project), "--adopt",
               "--layer-root", layer_root, "--vault", str(vault), "--yes"):
            done.append("config/layer redactados (revisá los TODO con `amauta`)")
    if "register" in fixes:
        if run(str(SCRIPTS / "kuraka-init.py"), "--target", str(project),
               "--register-only", "--vault", str(vault), "--yes"):
            done.append("registrado en el store central")
    if "overrides" in fixes:
        for k in plats:
            run(str(SCRIPTS / "kuraka-backup.py"), str(project), "--name", slug,
                "--overrides-only", "--vault", str(vault), "--target", PLATFORM_TARGET[k])
        done.append("overrides re-sincronizados con el store")
    if "backup" in fixes:
        if run(str(SCRIPTS / "kuraka-backup.py"), str(project), "--name", slug,
               "--vault", str(vault), "--target", PLATFORM_TARGET[primary]):
            done.append("backup completo (retros + telemetría + state)")
    return done


def check_one(vault: Path, project: Path, docs_root: str, fix: bool,
              brief: bool, label: str = "") -> int:
    slug = kc.registered_slug_for_path(vault, project) or kc.project_slug(project)
    findings = diagnose(vault, project, slug, docs_root)

    if fix and findings:
        fixes = {f.fix for f in findings if f.fix not in ("manual", "remount")}
        if fixes:
            for action in repair(vault, project, slug, fixes):
                print(f"   🔧 {action}")
            findings = diagnose(vault, project, slug, docs_root)

    name = label or slug
    if not findings:
        print(f"✅ {name}: Kuraka fluyendo correctamente" if not brief
              else f"✅ {name}")
        return 0

    print(f"⚠️  {name}: {len(findings)} hallazgo(s)")
    for f in findings:
        print(f"   · [{f.code}] {f.msg}")
        if f.hint:
            print(f"     → {f.hint}")
        elif f.fix == "remount":
            print(f"     → python3 {SCRIPTS / 'kuraka-mount.py'} {project} --update")
        elif f.fix != "manual" and not fix:
            print("     → se arregla solo con --fix")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description="Health check of a project's Kuraka state.")
    ap.add_argument("project", nargs="?", help="project root (default: $PWD)")
    ap.add_argument("--vault", default=os.environ.get("KURAKA_VAULT", DEFAULT_VAULT))
    ap.add_argument("--docs-root", default="docs/process")
    ap.add_argument("--all", action="store_true", help="check every registered project")
    ap.add_argument("--fix", action="store_true", help="apply the safe repairs and re-check")
    ap.add_argument("--brief", action="store_true", help="one line per project")
    args = ap.parse_args()

    vault = Path(args.vault).expanduser().resolve()
    if not vault.is_dir():
        err(f"❌ vault no encontrado: {vault}")
        return 2

    if args.all:
        rc = 0
        for note in sorted((vault / "projects").glob("*/registry.md")):
            m = re.search(r"^path:\s*(.+)$", note.read_text(errors="ignore"), re.M)
            if not m:
                continue
            p = Path(m.group(1).strip())
            if not p.is_dir() or not mounted_platforms(p):
                continue
            rc = max(rc, check_one(vault, p, args.docs_root, args.fix, args.brief,
                                   note.parent.name))
        return rc

    project = Path(args.project or os.getcwd()).expanduser().resolve()
    if not project.is_dir():
        err(f"❌ no es un directorio: {project}")
        return 2
    if not mounted_platforms(project):
        if args.brief:
            return 0  # not a Kuraka project — stay silent
        err(f"❌ {project} no tiene Kuraka montado.")
        return 2
    return check_one(vault, project, args.docs_root, args.fix, args.brief)


if __name__ == "__main__":
    raise SystemExit(main())
