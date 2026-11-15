#!/usr/bin/env python3
"""kuraka-preflight — environment check BEFORE Phase 1 (0 tokens).

118 of 295 archived RETROs mention the environment (docker down, a busy port,
a missing .env key, a second migration head, a baseline that was already red).
Every one of those was discovered by an agent in Phase 4 or 6, at agent prices,
and often misread as a defect of the cycle's own change. This script finds them
first, deterministically, and records the result as the cycle's OPEN marker.

    python3 kuraka-preflight.py <root> --req REQ [--mode normal] [--size M]
                                [--tests | --gates] [--permitir-base-roja "motivo"]
    python3 kuraka-preflight.py <root>            # ad-hoc check, writes nothing

With --req it writes <docs_process_root>/checkpoints/PREFLIGHT-<REQ>.json:
`started_at` (kept across re-runs — it is the window kuraka-close uses to
attribute HOOK-LOG rows to the cycle), mode, size, suite version, Claude plan,
baseline git head and every check. Exit 0 = go (warnings allowed), 1 = a
blocker, 2 = usage error. Standalone Python 3, no dependencies.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kuraka_common as kc  # noqa: E402

DEFAULT_VAULT = str(Path(__file__).resolve().parent)
_PLACEHOLDER = re.compile(r"^(todo|tbd|fixme|n/?a|none|null|~|-+|<.*>|\.\.\.)?$", re.I)
OK, INFO, WARN, FAIL = "ok", "info", "warn", "fail"
ICON = {OK: "✓", INFO: "·", WARN: "⚠", FAIL: "✗"}


def config_scalars(text: str) -> dict:
    """`a.b.c -> value` for every scalar of a block-style YAML mapping. Enough
    for kuraka.config.yaml (no anchors, no flow maps); lists are skipped."""
    out: dict = {}
    stack: list = []  # (indent, key)
    for raw in text.splitlines():
        if not raw.strip() or raw.lstrip().startswith(("#", "- ")):
            continue
        m = re.match(r"^(\s*)([A-Za-z0-9_.\-]+):[ \t]*(.*)$", raw)
        if not m:
            continue
        indent, key, val = len(m.group(1)), m.group(2), m.group(3)
        while stack and stack[-1][0] >= indent:
            stack.pop()
        val = re.sub(r"\s+#.*$", "", val).strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        path = ".".join([k for _, k in stack] + [key])
        if val in ("", "|", ">", "|-", ">-"):
            stack.append((indent, key))
        else:
            out[path] = val
    return out


def is_placeholder(v: "str | None") -> bool:
    v = (v or "").strip()
    return bool(_PLACEHOLDER.match(v)) or len(v) <= 2


def sh(cmd, cwd: Path, timeout: int = 20) -> "tuple[int, str]":
    try:
        r = subprocess.run(cmd, cwd=str(cwd), shell=isinstance(cmd, str),
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
        return r.returncode, (r.stdout or "") + (r.stderr or "")
    except subprocess.TimeoutExpired:
        return 124, f"timeout tras {timeout}s"
    except OSError as e:
        return 127, str(e)


class Report:
    def __init__(self) -> None:
        self.checks: list = []

    def add(self, cid: str, status: str, msg: str, hint: str = "", **extra) -> None:
        self.checks.append({"id": cid, "status": status, "msg": msg,
                            **({"hint": hint} if hint else {}), **extra})

    def worst(self) -> str:
        for s in (FAIL, WARN):
            if any(c["status"] == s for c in self.checks):
                return s
        return OK


# --- checks -------------------------------------------------------------------

def check_git(root: Path, rep: Report) -> dict:
    info = {"branch": "", "head": ""}
    rc, out = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"], root)
    if rc != 0:
        rep.add("git", WARN, "no es un repositorio git", "git init — los ignores de Kuraka viven en .git/info/exclude")
        return info
    info["branch"] = out.strip()
    info["head"] = sh(["git", "rev-parse", "--short", "HEAD"], root)[1].strip()
    dirty = [l for l in sh(["git", "status", "--porcelain", "--untracked-files=no"], root)[1].splitlines() if l.strip()]
    if dirty:
        rep.add("git", WARN, f"{len(dirty)} archivo(s) versionado(s) con cambios sin commitear en «{info['branch']}»",
                "commiteá o descartá antes de abrir el ciclo: el diff del ciclo se mezcla con esto", files=dirty[:8])
    elif info["branch"] in ("main", "master", "develop"):
        rep.add("git", WARN, f"el ciclo arrancaría sobre «{info['branch']}»", "creá la rama del ciclo")
    else:
        rep.add("git", OK, f"rama «{info['branch']}» limpia @ {info['head']}")
    return info


def gate_commands(cfg: dict) -> list:
    out = []
    for side in ("backend", "frontend"):
        for kind in ("test_cmd", "lint_cmd", "typecheck_cmd"):
            key = f"stack.{side}.{kind}"
            if key in cfg:
                out.append((side, kind, cfg[key]))
    return out


def _make_targets(root: Path) -> "set | None":
    mk = next((root / n for n in ("Makefile", "makefile", "GNUmakefile") if (root / n).is_file()), None)
    if mk is None:
        return None
    return set(re.findall(r"^([A-Za-z0-9_.\-]+)\s*:(?!=)", mk.read_text(encoding="utf-8", errors="ignore"), re.M))


def check_gates(root: Path, cfg: dict, rep: Report) -> list:
    gates = gate_commands(cfg)
    if not gates:
        rep.add("gates", FAIL, "kuraka.config.yaml no define ningún gate (test_cmd / lint_cmd / typecheck_cmd)",
                "completá stack.<backend|frontend>.*_cmd (o corré `amauta`)")
        return []
    usable = []
    targets = _make_targets(root)
    for side, kind, cmd in gates:
        name = f"{side}.{kind}"
        if is_placeholder(cmd):
            sev = FAIL if kind == "test_cmd" else WARN
            rep.add("gates", sev, f"{name} es un placeholder («{cmd}») — ese gate no corre",
                    "poné el comando real en kuraka.config.yaml")
            continue
        first = cmd.split("&&")[0].strip().split()
        while first and re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", first[0]):
            first = first[1:]  # leading VAR=value
        if first and first[0] == "cd" and "&&" in cmd:
            first = cmd.split("&&", 1)[1].strip().split()
        tool = first[0] if first else ""
        if tool and not tool.startswith((".", "/")) and shutil.which(tool) is None:
            rep.add("gates", FAIL, f"{name}: «{tool}» no está en el PATH", f"comando: {cmd}")
            continue
        if tool == "make" and targets is not None:
            tgt = next((a for a in first[1:] if not a.startswith("-") and "=" not in a), None)
            if tgt and tgt not in targets:
                rep.add("gates", FAIL, f"{name}: el Makefile no tiene el target «{tgt}»", f"comando: {cmd}")
                continue
        usable.append((side, kind, cmd))
    if len(usable) == len(gates):
        rep.add("gates", OK, f"{len(gates)} gate(s) definidos y ejecutables")
    return usable


def check_env(root: Path, cfg: dict, rep: Report) -> None:
    dirs = {root}
    for k in ("architecture.paths.backend_root", "architecture.paths.frontend_root"):
        if cfg.get(k):
            dirs.add((root / cfg[k]).resolve())
    found = False
    for d in sorted(dirs):
        ex = next((d / n for n in (".env.example", ".env.sample", ".env.template") if (d / n).is_file()), None)
        if ex is None:
            continue
        found = True
        rel = os.path.relpath(d, root)
        env = d / ".env"
        keys = lambda p: {m.group(1) for m in re.finditer(  # noqa: E731
            r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=", p.read_text(encoding="utf-8", errors="ignore"), re.M)}
        if not env.is_file():
            # A warning, not a blocker: plenty of projects inject env from the
            # compose file or the shell. The baseline run is the real proof.
            rep.add("env", WARN, f"{rel}/.env no existe (hay {ex.name})", f"cp {ex.name} .env y completá los valores")
            continue
        missing = sorted(keys(ex) - keys(env))
        if missing:
            rep.add("env", WARN, f"{rel}/.env: faltan {len(missing)} clave(s) de {ex.name}: "
                    + ", ".join(missing[:8]) + (" …" if len(missing) > 8 else ""),
                    "agregalas antes de que un agente las descubra en runtime")
        else:
            rep.add("env", OK, f"{rel}/.env cubre las claves de {ex.name}")
    if not found:
        rep.add("env", INFO, "sin .env.example — nada que comparar")


def check_deps(root: Path, cfg: dict, rep: Report) -> None:
    dirs = [root]
    fr = cfg.get("architecture.paths.frontend_root")
    if fr:
        dirs.append((root / fr).resolve())
    seen = set()
    for d in dirs:
        if d in seen or not (d / "package.json").is_file():
            continue
        seen.add(d)
        rel = os.path.relpath(d, root)
        nm = d / "node_modules"
        if not nm.is_dir():
            rep.add("deps", FAIL, f"{rel}: hay package.json pero no node_modules", "instalá dependencias (npm ci / pnpm i / yarn)")
            continue
        lock = next((d / n for n in ("package-lock.json", "pnpm-lock.yaml", "yarn.lock") if (d / n).is_file()), None)
        marker = next((nm / n for n in (".package-lock.json", ".modules.yaml", ".yarn-integrity") if (nm / n).is_file()), None)
        if lock and marker and lock.stat().st_mtime > marker.stat().st_mtime + 2:
            rep.add("deps", WARN, f"{rel}: {lock.name} es más nuevo que node_modules", "reinstalá dependencias")
        else:
            rep.add("deps", OK, f"{rel}: node_modules al día")


def compose_ports(root: Path) -> "tuple[Path | None, list]":
    f = next((root / n for n in ("docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml")
              if (root / n).is_file()), None)
    if f is None:
        return None, []
    ports = []
    for m in re.finditer(r"^\s*-\s*[\"']?(?:[\d.]+:)?(?:\$\{[^}:]*:-(\d+)\}|(\d+)):\d+(?:/\w+)?[\"']?\s*(?:#.*)?$",
                         f.read_text(encoding="utf-8", errors="ignore"), re.M):
        ports.append(int(m.group(1) or m.group(2)))
    return f, sorted(set(ports))


def port_busy(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.4)
        return s.connect_ex(("127.0.0.1", port)) == 0


def check_docker(root: Path, rep: Report) -> None:
    f, ports = compose_ports(root)
    if f is None:
        return
    if shutil.which("docker") is None:
        rep.add("docker", WARN, f"hay {f.name} pero docker no está instalado")
        return
    rc, _ = sh(["docker", "info", "--format", "{{.ServerVersion}}"], root, timeout=15)
    if rc != 0:
        rep.add("docker", WARN, f"hay {f.name} pero el daemon de docker no responde",
                "abrí Docker antes del ciclo si los tests o el smoke usan el stack")
        return
    rc, out = sh(["docker", "compose", "-f", f.name, "ps", "-q"], root, timeout=20)
    running = rc == 0 and bool(out.strip())
    busy = [p for p in ports if port_busy(p)]
    if running:
        rep.add("docker", OK, f"stack de {f.name} levantado ({len(out.split())} contenedor(es))")
    elif busy:
        rep.add("docker", FAIL, f"puerto(s) {', '.join(map(str, busy))} ocupado(s) y el stack de {f.name} NO está levantado",
                "otro proceso los usa: liberalos o el `up` del ciclo va a fallar", ports=busy)
    else:
        rep.add("docker", INFO, f"stack de {f.name} detenido; puertos {', '.join(map(str, ports)) or '—'} libres")


def check_migrations(root: Path, cfg: dict, rep: Report) -> str:
    tool = (cfg.get("stack.database.migration_tool") or "").lower()
    mroot = cfg.get("architecture.paths.migrations_root")
    if tool != "alembic" or not mroot or not (root / mroot).is_dir():
        return ""
    revs, downs = {}, set()
    for f in (root / mroot).glob("*.py"):
        text = f.read_text(encoding="utf-8", errors="ignore")
        r = re.search(r"^revision(?:\s*:\s*[\w\[\], |]+)?\s*=\s*[\"']([^\"']+)[\"']", text, re.M)
        if not r:
            continue
        revs[r.group(1)] = f.name
        d = re.search(r"^down_revision(?:\s*:\s*[\w\[\], |]+)?\s*=\s*(.+)$", text, re.M)
        if d:
            downs.update(re.findall(r"[\"']([^\"']+)[\"']", d.group(1)))
    heads = sorted(r for r in revs if r not in downs)
    if len(heads) > 1:
        rep.add("migrations", FAIL, f"alembic tiene {len(heads)} heads: " + ", ".join(revs[h] for h in heads[:4]),
                "unificá con un merge de revisiones ANTES de que el ciclo agregue otra", heads=heads)
    elif heads:
        rep.add("migrations", OK, f"alembic: 1 head ({revs[heads[0]]}), {len(revs)} revisión(es)")
    return heads[0] if len(heads) == 1 else ""


def check_doctor(vault: Path, root: Path, rep: Report) -> None:
    doctor = vault / "kuraka-doctor.py"
    if not doctor.is_file():
        return
    rc, out = sh([sys.executable, str(doctor), str(root), "--brief", "--vault", str(vault)], root, timeout=60)
    lines = [l.strip(" ·") for l in out.splitlines() if l.strip().startswith("·")]
    if rc == 0:
        rep.add("kuraka", OK, "estado Kuraka sano (kuraka-doctor)")
    else:
        rep.add("kuraka", WARN, f"kuraka-doctor: {len(lines) or 1} hallazgo(s)" + (": " + lines[0][:110] if lines else ""),
                f"python3 {doctor} {root} --fix", findings=lines[:10])


def run_baseline(root: Path, gates: list, kinds: tuple, timeout: int, rep: Report, ack: str) -> list:
    results = []
    for side, kind, cmd in gates:
        if kind not in kinds:
            continue
        t0 = time.time()
        rc, out = sh(cmd, root, timeout=timeout)
        tail = [l for l in out.splitlines() if l.strip()][-12:]
        res = {"gate": f"{side}.{kind}", "cmd": cmd, "exit": rc, "seconds": round(time.time() - t0, 1), "tail": tail}
        results.append(res)
        if rc == 0:
            rep.add("baseline", OK, f"{side}.{kind} verde antes del ciclo ({res['seconds']}s)")
        elif ack:
            rep.add("baseline", WARN, f"{side}.{kind} ya estaba ROJO antes del ciclo (exit {rc}) — aceptado: {ack}",
                    "todo lo que falle igual al final NO es del ciclo; lo demás sí", tail=tail[-4:])
        else:
            rep.add("baseline", FAIL, f"{side}.{kind} ya está ROJO antes de empezar (exit {rc})",
                    "arreglalo primero, o re-corré con --permitir-base-roja \"motivo\" para dejarlo asentado",
                    tail=tail[-6:])
    return results


def main() -> int:
    kc.force_utf8_io()
    ap = argparse.ArgumentParser(description="Chequeo de entorno antes de la fase 1 de un ciclo Kuraka.")
    ap.add_argument("project", nargs="?", default=os.getcwd())
    ap.add_argument("--req", help="REQ del ciclo: escribe checkpoints/PREFLIGHT-<REQ>.json (marca de apertura)")
    ap.add_argument("--mode", default="", help="modo del ciclo (normal | lite | reduced | …)")
    ap.add_argument("--size", default="", help="tamaño declarado: S | M | L")
    ap.add_argument("--tests", action="store_true", help="correr los test_cmd como línea base")
    ap.add_argument("--gates", action="store_true", help="línea base de tests + lint + typecheck")
    ap.add_argument("--timeout", type=int, default=900, help="segundos por gate de línea base")
    ap.add_argument("--permitir-base-roja", default="", metavar="MOTIVO",
                    help="dejar asentado que la línea base ya estaba roja y seguir")
    ap.add_argument("--vault", default=os.environ.get("KURAKA_VAULT", DEFAULT_VAULT))
    ap.add_argument("--json", action="store_true", help="imprimir el reporte como JSON")
    args = ap.parse_args()

    root = Path(args.project).expanduser().resolve()
    vault = Path(args.vault).expanduser().resolve()
    if not root.is_dir():
        print(f"❌ no existe: {root}", file=sys.stderr)
        return 2
    size = args.size.strip().upper()[:1]
    if args.size and size not in ("S", "M", "L"):
        print("❌ --size debe ser S, M o L", file=sys.stderr)
        return 2

    rep = Report()
    cfg_file = root / "kuraka.config.yaml"
    cfg = config_scalars(cfg_file.read_text(encoding="utf-8", errors="ignore")) if cfg_file.is_file() else {}
    if not cfg_file.is_file():
        rep.add("config", FAIL, "falta kuraka.config.yaml", "kuraka init / kuraka mount lo crean")
    git = check_git(root, rep)
    gates = check_gates(root, cfg, rep) if cfg else []
    check_env(root, cfg, rep)
    check_deps(root, cfg, rep)
    check_docker(root, rep)
    mig_head = check_migrations(root, cfg, rep)
    check_doctor(vault, root, rep)
    baseline = []
    if args.tests or args.gates:
        kinds = ("test_cmd", "lint_cmd", "typecheck_cmd") if args.gates else ("test_cmd",)
        baseline = run_baseline(root, gates, kinds, args.timeout, rep, args.permitir_base_roja.strip())
    else:
        rep.add("baseline", INFO, "línea base de tests NO corrida (usá --tests)")

    status = rep.worst()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    report = {
        "req": args.req or "", "status": status, "checked_at": now, "started_at": now,
        "mode": args.mode.strip().lower(), "size": size,
        "suite_version": kc.mounted_suite_version(root), "claude_plan": kc.manifest_claude_plan(root) or "",
        "branch": git["branch"], "baseline_git_head": git["head"], "baseline_migration_head": mig_head,
        "baseline": baseline, "checks": rep.checks,
    }

    out_path = None
    if args.req:
        docs_root = kc.config_docs_root(root)
        out_path = root / docs_root / "checkpoints" / f"PREFLIGHT-{args.req}.json"
        if out_path.is_file():
            try:
                prev = json.loads(out_path.read_text(encoding="utf-8"))
                # The cycle was opened before: keep its start and its declared
                # mode/size unless this run states them again.
                report["started_at"] = prev.get("started_at") or now
                report["mode"] = report["mode"] or prev.get("mode", "")
                report["size"] = report["size"] or prev.get("size", "")
                report["baseline_git_head"] = prev.get("baseline_git_head") or report["baseline_git_head"]
                report["reruns"] = int(prev.get("reruns") or 0) + 1
            except Exception:
                pass
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        head = {OK: "✅ entorno listo", WARN: "⚠️  entorno listo con avisos", FAIL: "❌ entorno NO listo"}[status]
        print(f"{head} — {root.name}" + (f" · {args.req}" if args.req else ""))
        for c in rep.checks:
            print(f"   {ICON[c['status']]} [{c['id']}] {c['msg']}")
            if c.get("hint") and c["status"] in (WARN, FAIL):
                print(f"       → {c['hint']}")
            for line in c.get("tail", []) if c["status"] == FAIL else []:
                print(f"       | {line[:150]}")
        if out_path:
            print(f"   registro: {os.path.relpath(out_path, root)}")
    return 1 if status == FAIL else 0


if __name__ == "__main__":
    raise SystemExit(main())
