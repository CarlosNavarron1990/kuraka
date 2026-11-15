#!/usr/bin/env python3
"""kuraka-close — close (or abandon) a cycle in ONE command (0 tokens).

132 of 294 archived cycles have no verdict, 98 no telemetry, and ~100 more sit
open in their projects with no way to tell "abandoned" from "forgot Phase 7".
Closing was four manual steps spread over prose; this is the one gate.

    python3 kuraka-close.py <root> --list
    python3 kuraka-close.py <root> --req REQ [--sin-aceptacion "motivo"]
    python3 kuraka-close.py <root> --req REQ --abandonar --motivo "…"

Closing checks, in order: RETRO with its `## Confidence:` line · user
acceptance (Phase 6.9 ledger) · locked acceptance tests intact · telemetry
(reconciled against HOOK-LOG.jsonl; DERIVED from it when the curated JSON was
never written) · then kuraka-backup, which archives the cycle and stamps
mode/size/invocations/rework into meta.yaml. A blocker skips the archive, still
backs up the state, and exits 1. Standalone Python 3, no dependencies.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kuraka_common as kc  # noqa: E402

DEFAULT_VAULT = str(Path(__file__).resolve().parent)
HERE = Path(__file__).resolve().parent


def _doctor():
    spec = importlib.util.spec_from_file_location("kuraka_doctor", HERE / "kuraka-doctor.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _slug(vault: Path, root: Path) -> str:
    return kc.registered_slug_for_path(vault, root) or kc.project_slug(root)


def _read_json(p: Path) -> dict:
    try:
        d = json.loads(p.read_text(encoding="utf-8", errors="ignore"))
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}


def find_retro(root: Path, docs_root: str, req: str) -> "Path | None":
    cands = []
    for d in kc._retro_dirs(root, docs_root):
        exact = d / f"RETRO-{req}.md"
        if exact.is_file():
            return exact
        cands += [f for f in d.glob(f"RETRO-{req}*.md") if not f.name.startswith("._")]
    return cands[0] if len(cands) == 1 else None


def cycle_window(root: Path, docs_root: str, req: str) -> "tuple[str | None, dict]":
    """Start of the cycle: the preflight marker, else the REQ's date stamp."""
    pre = _read_json(root / docs_root / "checkpoints" / f"PREFLIGHT-{req}.json")
    if pre.get("started_at"):
        return str(pre["started_at"]), pre
    m = re.match(r"^REQ-(?:LITE-)?(\d{4})(\d{2})(\d{2})", req)
    return (f"{m.group(1)}-{m.group(2)}-{m.group(3)}T00:00:00+00:00" if m else None), pre


def settle_partial(runs: list) -> int:
    """Recompute the cost of runs the hook read before the transcript was
    complete (`partial`), now that the agent is long finished."""
    pending = [r for r in runs if r.get("partial") and r.get("transcript")]
    if not pending:
        return 0
    spec = importlib.util.spec_from_file_location("telemetry_append", HERE / "hooks" / "telemetry_append.py")
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    n = 0
    for r in pending:
        u = hook.transcript_usage(r["transcript"])
        if u.get("total_tokens") is not None:
            u.pop("last_text", None)
            r.update({k: v for k, v in u.items() if v is not None})
            r["partial"] = False
            n += 1
    return n


def derive_telemetry(req: str, runs: list, pre: dict) -> dict:
    return {
        "req_name": req, "mode": pre.get("mode", ""), "size": pre.get("size", ""),
        "source": "hook-derived",
        "note": "Generado por kuraka-close desde HOOK-LOG.jsonl: el orquestador no escribió "
                "la telemetría curada. `phase` es null (el hook no la conoce).",
        "runs": [{
            "phase": None, "agent": r.get("agent"), "description": r.get("description"),
            "model": r.get("model"), "total_tokens": r.get("total_tokens"),
            "tool_uses": r.get("tool_uses"), "duration_ms": r.get("duration_ms"),
            "status": "lost" if r.get("lost") else "ok", "agent_id": r.get("agent_id"),
            "resumed": bool(r.get("resumed")),
        } for r in runs],
    }


def cmd_list(vault: Path, root: Path, docs_root: str, slug: str) -> int:
    opened = _doctor().open_cycles(vault, root, slug, docs_root, min_age_h=0)
    if not opened:
        print(f"✅ {slug}: ningún ciclo abierto")
        return 0
    print(f"{slug}: {len(opened)} ciclo(s) abierto(s)")
    now = time.time()
    for req in opened:
        m = re.match(r"^REQ-(?:LITE-)?(\d{8})", req)
        try:
            ts = datetime.strptime(m.group(1), "%Y%m%d").timestamp() if m else (root / docs_root / f"{req}.md").stat().st_mtime
            age = f"{int((now - ts) // 86400)} d"
        except (ValueError, OSError):
            age = "?"
        st = _read_json(root / docs_root / "checkpoints" / f"{req}-state.json")
        phase = str(st.get("current_phase") or st.get("phase") or "—")[:28]
        aj = kc.ajustes_summary(kc.find_ajustes(req, root / docs_root / "ajustes"))
        acc = aj.get("aceptacion") if aj.get("registro") else "sin 6.9"
        retro = "RETRO ✓" if find_retro(root, docs_root, req) else "sin RETRO"
        print(f"   · {req}  ·  {age}  ·  fase: {phase}  ·  {acc}  ·  {retro}")
    print(f"   cerrar:    python3 {HERE / 'kuraka-close.py'} {root} --req <REQ>")
    print(f"   abandonar: python3 {HERE / 'kuraka-close.py'} {root} --req <REQ> --abandonar --motivo \"…\"")
    return 0


def main() -> int:
    kc.force_utf8_io()
    ap = argparse.ArgumentParser(description="Cerrar o abandonar un ciclo Kuraka.")
    ap.add_argument("project", nargs="?", default=os.getcwd())
    ap.add_argument("--req")
    ap.add_argument("--list", action="store_true", help="listar los ciclos abiertos")
    ap.add_argument("--abandonar", action="store_true", help="cerrar SIN RETRO, con motivo")
    ap.add_argument("--motivo", default="")
    ap.add_argument("--sin-aceptacion", default="", metavar="MOTIVO",
                    help="cerrar aunque el usuario no haya aceptado (queda registrado)")
    ap.add_argument("--allow-incomplete-retro", action="store_true")
    ap.add_argument("--no-backup", action="store_true", help="solo verificar, no archivar")
    ap.add_argument("--target", choices=("claude", "antigravity", "cursor", "codex"),
                    help="plataforma montada (se pasa a kuraka-backup)")
    ap.add_argument("--vault", default=os.environ.get("KURAKA_VAULT", DEFAULT_VAULT))
    args = ap.parse_args()

    root = Path(args.project).expanduser().resolve()
    vault = Path(args.vault).expanduser().resolve()
    if not root.is_dir() or not vault.is_dir():
        print(f"❌ ruta inválida: {root if not root.is_dir() else vault}", file=sys.stderr)
        return 2
    docs_root = kc.config_docs_root(root)
    slug = _slug(vault, root)

    if args.list:
        return cmd_list(vault, root, docs_root, slug)
    if not args.req:
        print("❌ falta --req (o usá --list)", file=sys.stderr)
        return 2
    req = args.req

    if args.abandonar:
        if len(args.motivo.strip()) < 8:
            print("❌ --abandonar exige --motivo \"por qué se dejó\" (para el harvest)", file=sys.stderr)
            return 2
        if find_retro(root, docs_root, req):
            print(f"❌ {req} ya tiene RETRO: cerralo normalmente (sin --abandonar)", file=sys.stderr)
            return 2
        dest = kc.cycles_dir(vault, slug) / req
        if (dest / "meta.yaml").is_file() and kc.ABANDONED not in (dest / "meta.yaml").read_text(encoding="utf-8", errors="ignore"):
            print(f"❌ {req} ya está archivado como ciclo cerrado", file=sys.stderr)
            return 2
        branch = kc.git_branch(root)
        kc.abandon_cycle(vault, slug, req, args.motivo, branch, kc.mounted_suite_version(root))
        kc.update_index(vault, [{"req": req, "status": "archived", "verdict": kc.ABANDONED,
                                 "telem": False, "branch": branch}], slug, force=False)
        print(f"🗄  {req} cerrado como ABANDONADO — {args.motivo.strip()}")
        print(f"   {dest / 'meta.yaml'}")
        return 0

    blockers: list = []
    warns: list = []
    oks: list = []

    # 1. RETRO + verdict
    retro = find_retro(root, docs_root, req)
    if retro is None:
        blockers.append(f"no hay RETRO-{req}.md — falta la fase 7 (final-auditor)")
    else:
        verdict = kc.find_verdict(retro.read_text(encoding="utf-8", errors="ignore"))
        if verdict:
            oks.append(f"RETRO con veredicto {verdict}")
        elif args.allow_incomplete_retro:
            warns.append("RETRO sin `## Confidence:` (--allow-incomplete-retro)")
        else:
            blockers.append(f"{retro.name} no tiene la línea `## Confidence: HIGH|MEDIUM|LOW`")

    # 2. user acceptance (Phase 6.9)
    aj = kc.ajustes_summary(kc.find_ajustes(req, root / docs_root / "ajustes"))
    if not aj.get("registro"):
        warns.append("sin registro de validación del usuario (fase 6.9 no corrida)")
    elif aj.get("aceptado"):
        oks.append(f"aceptado por el usuario · {aj.get('ajustes_total', 0)} ajuste(s), "
                   f"{aj.get('ajustes_falto', 0)} «faltó»")
    elif aj.get("cierre_sin_aceptacion"):
        warns.append(f"cerrado sin aceptación: {aj['cierre_sin_aceptacion']}")
    elif args.sin_aceptacion.strip():
        subprocess.run([sys.executable, str(HERE / "kuraka-ajuste.py"), "cerrar", str(root),
                        "--req", req, "--motivo", args.sin_aceptacion.strip()],
                       capture_output=True, text=True)
        warns.append(f"cerrado sin aceptación: {args.sin_aceptacion.strip()}")
    else:
        blockers.append(f"el usuario no aceptó el ciclo ({aj.get('pendientes', 0)} ajuste(s) pendientes) — "
                        "`kuraka-ajuste.py aceptar`, o --sin-aceptacion \"motivo\"")

    # 3. locked acceptance tests
    if (root / docs_root / "checkpoints" / f"TESTLOCK-{req}.json").is_file():
        r = subprocess.run([sys.executable, str(HERE / "kuraka-testlock.py"), "verify", str(root), "--req", req],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode == 0:
            oks.append("tests de aceptación bloqueados: intactos")
        else:
            blockers.append("tests de aceptación cambiados sin unlock:\n" + (r.stdout or "").strip())
    else:
        warns.append("sin tests de aceptación bloqueados (fase 3.95 no corrida)")

    # 4. telemetry: reconcile with / derive from the hook log
    telem_dir = root / docs_root / "agent-telemetry"
    since, pre = cycle_window(root, docs_root, req)
    rows = kc.read_hook_log(telem_dir / "HOOK-LOG.jsonl")
    hruns = kc.hook_runs(rows, since=since) if since else []
    settle_partial(hruns)
    costed = [r for r in hruns if r.get("total_tokens") is not None]
    lost = [r for r in hruns if r.get("lost")]
    curated = kc._find_telemetry(req, [telem_dir], retro or (root / docs_root / "x" / "y"))
    if curated is None:
        if costed:
            out = telem_dir / f"{req}{kc.TELEMETRY_SUFFIX}"
            out.write_text(json.dumps(derive_telemetry(req, hruns, pre), indent=2, ensure_ascii=False) + "\n",
                           encoding="utf-8")
            warns.append(f"telemetría curada ausente → derivada de HOOK-LOG ({len(hruns)} corrida(s), sin fase): {out.name}")
        else:
            warns.append("sin telemetría: ni JSON curado ni filas con costo en HOOK-LOG"
                         + ("" if pre else " (y sin PREFLIGHT que marque el inicio del ciclo)"))
    else:
        data = _read_json(curated)
        cruns = [r for r in data.get("runs") or [] if isinstance(r, dict) and r.get("agent") != "orchestrator"]
        touched = False
        for k in ("mode", "size"):
            if not data.get(k) and pre.get(k):
                data[k] = pre[k]
                touched = True
        if touched:
            curated.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        if pre and len(hruns) > len(cruns):
            warns.append(f"HOOK-LOG registra {len(hruns)} corrida(s) en el ciclo y la telemetría curada {len(cruns)} "
                         f"— {len(hruns) - len(cruns)} sin contabilizar")
        else:
            oks.append(f"telemetría curada: {len(cruns)} corrida(s)")
    if lost:
        warns.append(f"{len(lost)} subagente(s) lanzado(s) que nunca terminaron: "
                     + ", ".join(sorted({str(r.get('agent')) for r in lost})))

    for m in oks:
        print(f"   ✓ {m}")
    for m in warns:
        print(f"   ⚠ {m}")
    for m in blockers:
        print(f"   ✗ {m}")

    if args.no_backup:
        return 1 if blockers else 0

    backup = [sys.executable, str(HERE / "kuraka-backup.py"), str(root), "--vault", str(vault)]
    if args.target:
        backup += ["--target", args.target]
    if blockers:
        # The cycle does not close, but its state must still leave the working tree.
        subprocess.run(backup + ["--state-only"], capture_output=True, text=True)
        print(f"❌ {req} NO cierra: {len(blockers)} bloqueo(s). El estado quedó respaldado igual.")
        return 1
    if args.allow_incomplete_retro:
        backup.append("--allow-incomplete-retro")
    r = subprocess.run(backup, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print((r.stdout or "")[-1200:] + (r.stderr or "")[-1200:])
        print(f"❌ {req}: kuraka-backup salió {r.returncode} — el ciclo no quedó cerrado")
        return 1

    meta = kc.cycles_dir(vault, slug) / (retro.stem[len("RETRO-"):] if retro else req) / "meta.yaml"
    text = meta.read_text(encoding="utf-8", errors="ignore") if meta.is_file() else ""
    g = lambda k: (re.search(rf'^{k}:\s*"?([^"\n]*)"?\s*$', text, re.M) or [None, "—"])[1] or "—"  # noqa: E731
    tok = g("tokens_total")
    tok = f"{int(tok) / 1e6:.2f}M" if tok.isdigit() else tok
    print(f"✅ {req} cerrado · veredicto {g('verdict')} · modo {g('mode')} · tamaño {g('size')} · "
          f"{g('invocaciones')} invocación(es) · {g('retrabajo')} de retrabajo · {tok} tokens · "
          f"aceptación {g('aceptacion')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
