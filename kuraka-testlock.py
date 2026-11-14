#!/usr/bin/env python3
"""kuraka-testlock — lock the cycle's acceptance tests (spec first).

Phase 3.95 writes the acceptance tests RED from the test plan's oracles, before
any implementation exists. From then on nobody may bend them to the code: this
script records their sha256 and `verify` fails if a locked test was modified or
deleted without a user-approved `unlock` record. Zero tokens; the developer,
the reviewer and the Phase 4/6 gates call it.

Storage: <docs_process_root>/checkpoints/TESTLOCK-<REQ>.json

Usage:
    kuraka-testlock.py lock   <root> --req REQ <test files...>   # add/refresh entries
    kuraka-testlock.py verify <root> --req REQ                    # exit 1 on unapproved change
    kuraka-testlock.py unlock <root> --req REQ --file F --motivo "..." --aprobado-por user
    kuraka-testlock.py status <root> --req REQ [--json]

An `unlock` allows ONE file to change; re-run `lock` on it after the fix to
re-arm it (that consumes the unlock).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kuraka_common as kc  # noqa: E402


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _lock_path(root: Path, req: str) -> Path:
    return root / kc.config_docs_root(root) / "checkpoints" / f"TESTLOCK-{req}.json"


def _load(root: Path, req: str) -> dict:
    p = _lock_path(root, req)
    if p.is_file():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            pass
    return {"req": req, "files": {}, "unlocks": []}


def _save(root: Path, req: str, data: dict) -> Path:
    p = _lock_path(root, req)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
                 encoding="utf-8")
    return p


def _rel(root: Path, f: str) -> str:
    p = Path(f)
    p = p if p.is_absolute() else (root / p)
    try:
        return p.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return Path(f).as_posix()


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _diffstat(root: Path, rel: str) -> str:
    try:
        r = subprocess.run(["git", "diff", "--stat", "HEAD", "--", rel], cwd=root,
                           capture_output=True, text=True, check=False)
        return r.stdout.strip().splitlines()[0] if r.stdout.strip() else ""
    except OSError:
        return ""


def _open_unlock(data: dict, rel: str) -> "dict | None":
    for u in reversed(data.get("unlocks", [])):
        if u.get("file") == rel and not u.get("consumed"):
            return u
    return None


def cmd_lock(root: Path, req: str, files: list[str]) -> int:
    data = _load(root, req)
    missing = []
    for f in files:
        rel = _rel(root, f)
        p = root / rel
        if not p.is_file():
            missing.append(rel)
            continue
        data["files"][rel] = {"sha256": _sha(p), "locked_at": _now()}
        u = _open_unlock(data, rel)
        if u:
            u["consumed"] = _now()
    if missing:
        print("❌ no existen: " + ", ".join(missing), file=sys.stderr)
        return 1
    out = _save(root, req, data)
    print(f"🔒 {len(files)} test(s) bloqueado(s) → {out.relative_to(root).as_posix()}")
    return 0


def check(root: Path, req: str) -> list[tuple[str, str, str]]:
    """[(file, problem, detail)] for every locked test changed without unlock."""
    data = _load(root, req)
    out = []
    for rel, meta in sorted(data.get("files", {}).items()):
        p = root / rel
        if _open_unlock(data, rel):
            continue
        if not p.is_file():
            out.append((rel, "borrado", ""))
        elif _sha(p) != meta.get("sha256"):
            out.append((rel, "modificado", _diffstat(root, rel)))
    return out


def cmd_verify(root: Path, req: str) -> int:
    data = _load(root, req)
    if not data.get("files"):
        print(f"⚠️  {req}: no hay tests bloqueados (¿se corrió la fase 3.95?)")
        return 0
    bad = check(root, req)
    if not bad:
        n = len(data["files"])
        print(f"✅ {req}: {n} test(s) de aceptación intactos")
        return 0
    print(f"❌ {req}: {len(bad)} test(s) de aceptación cambiados sin `unlock` aprobado:")
    for rel, prob, det in bad:
        print(f"   · {rel} — {prob}" + (f"  ({det})" if det else ""))
    print("   → si el test está mal: reportar `conflicto de especificación`; con el OK del "
          "usuario: kuraka-testlock.py unlock … --aprobado-por user, y luego lock otra vez")
    return 1


def cmd_unlock(root: Path, req: str, file: str, motivo: str, by: str) -> int:
    data = _load(root, req)
    rel = _rel(root, file)
    if rel not in data.get("files", {}):
        print(f"❌ {rel} no está bloqueado en {req}", file=sys.stderr)
        return 1
    if not motivo.strip() or not by.strip():
        print("❌ --motivo y --aprobado-por son obligatorios", file=sys.stderr)
        return 1
    data.setdefault("unlocks", []).append(
        {"file": rel, "motivo": motivo, "aprobado_por": by, "at": _now()})
    _save(root, req, data)
    print(f"🔓 {rel} desbloqueado ({by}: {motivo}). Re-bloquealo con `lock` tras el cambio.")
    return 0


def cmd_status(root: Path, req: str, as_json: bool) -> int:
    data = _load(root, req)
    bad = {f: (p, d) for f, p, d in check(root, req)}
    rows = []
    for rel in sorted(data.get("files", {})):
        u = _open_unlock(data, rel)
        state = "desbloqueado" if u else (bad[rel][0] if rel in bad else "intacto")
        rows.append({"file": rel, "estado": state})
    if as_json:
        print(json.dumps({"req": req, "tests": rows, "unlocks": data.get("unlocks", [])},
                         ensure_ascii=False, indent=1))
    else:
        for r in rows:
            print(f"{r['estado']:13} {r['file']}")
        print(f"unlocks registrados: {len(data.get('unlocks', []))}")
    return 0


def main(argv: "list[str] | None" = None) -> int:
    ap = argparse.ArgumentParser(prog="kuraka-testlock", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("lock", "verify", "unlock", "status"):
        sp = sub.add_parser(name)
        sp.add_argument("root")
        sp.add_argument("--req", required=True)
        if name == "lock":
            sp.add_argument("files", nargs="+")
        if name == "unlock":
            sp.add_argument("--file", required=True)
            sp.add_argument("--motivo", required=True)
            sp.add_argument("--aprobado-por", dest="by", required=True)
        if name == "status":
            sp.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    root = Path(a.root).expanduser().resolve()
    if a.cmd == "lock":
        return cmd_lock(root, a.req, a.files)
    if a.cmd == "verify":
        return cmd_verify(root, a.req)
    if a.cmd == "unlock":
        return cmd_unlock(root, a.req, a.file, a.motivo, a.by)
    return cmd_status(root, a.req, a.json)


if __name__ == "__main__":
    sys.exit(main())
