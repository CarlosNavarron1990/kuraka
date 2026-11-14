#!/usr/bin/env python3
"""kuraka-ajuste — Phase 6.9 ledger: the user's validation of the running cycle.

Zero tokens: the orchestrator calls this instead of hand-writing ledgers. Every
adjustment the user asks for while testing is recorded VERBATIM against the
cycle that is running, classified by who should have caught it, resolved, and
the cycle is closed only with an explicit acceptance. Phase 7 turns every
`falto-preguntar` / `falto-hacer` into a project-layer patch, and
`/kuraka-harvest` aggregates them across projects — that is how "what Kuraka
should have asked" reaches the framework.

Storage (source of truth, append-only):
    <docs_process_root>/ajustes/AJUSTES-<REQ>.jsonl
plus a regenerated human view AJUSTES-<REQ>.md next to it.

Usage:
    kuraka-ajuste.py add <root> --req REQ --tipo T --debio "1 po-analyst" --texto "..." [--resolucion "..."]
    kuraka-ajuste.py ronda <root> --req REQ
    kuraka-ajuste.py resolver <root> --req REQ --id N --resolucion "..."
    kuraka-ajuste.py aceptar <root> --req REQ [--nota "..."]
    kuraka-ajuste.py cerrar <root> --req REQ --motivo "..."      # close WITHOUT acceptance (recorded)
    kuraka-ajuste.py estado <root> --req REQ [--json]

Tipos: bug | ux | cambio-alcance | falto-preguntar | falto-hacer | entorno
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kuraka_common as kc  # noqa: E402

TIPO_HELP = {
    "bug": "no hace lo que el REQ ya pedía",
    "ux": "funciona, pero la experiencia no es la esperada",
    "cambio-alcance": "el usuario pide algo que no estaba en el REQ (decisión nueva)",
    "falto-preguntar": "Kuraka debió preguntarlo antes de implementar",
    "falto-hacer": "Kuraka debió hacerlo/verificarlo y no lo hizo",
    "entorno": "configuración, datos o despliegue, no el código del ciclo",
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ledger(root: Path, req: str, create: bool) -> Path:
    d = kc.ajustes_dir(root)
    found = kc.find_ajustes(req, d)
    if found is not None:
        return found
    if create:
        d.mkdir(parents=True, exist_ok=True)
    return d / f"AJUSTES-{req}.jsonl"


def _append(path: Path, ev: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(ev, ensure_ascii=False) + "\n")


def _cell(v) -> str:
    return str(v if v not in (None, "") else "—").replace("|", "\\|").replace("\n", " ")


def render_md(path: Path, req: str) -> Path:
    s = kc.ajustes_summary(path)
    out = path.with_suffix(".md")
    first = "sí" if s["aceptacion"] == "primera-ronda" else "no"
    lines = [
        f"# Ajustes y efectividad — {req}",
        "",
        "_Generado por `kuraka-ajuste.py` desde el `.jsonl` (no editar a mano)._",
        "",
        f"- **Aceptación:** `{s['aceptacion']}`"
        + (f" ({s['aceptado_ts']})" if s.get("aceptado_ts") else ""),
        f"- **Aceptado en primera ronda:** {first}",
        f"- **Rondas de validación:** {s['rondas']}",
        f"- **Ajustes:** {s['ajustes_total']} (faltó preguntar/hacer: {s['ajustes_falto']}; "
        f"pendientes sin resolver: {s['pendientes']})",
    ]
    if s.get("nota"):
        lines.append(f"- **Nota de aceptación:** {s['nota']}")
    if s.get("cierre_sin_aceptacion"):
        lines.append(f"- **Cierre SIN aceptación:** {s['cierre_sin_aceptacion']}")
    lines += ["", "## Ajustes", "",
              "| # | Ronda | Tipo | Debió detectarlo | Pedido del usuario (textual) | Resolución |",
              "|---|---|---|---|---|---|"]
    for a in s["ajustes"]:
        lines.append(f"| {a.get('id')} | {a.get('ronda')} | {_cell(a.get('tipo'))} | "
                     f"{_cell(a.get('debio'))} | {_cell(a.get('texto'))} | {_cell(a.get('resolucion'))} |")
    if not s["ajustes"]:
        lines.append("| — | — | — | — | sin ajustes | — |")
    if s["por_debio"]:
        lines += ["", "## Por fase/agente que debió detectarlo", "",
                  "| Fase / agente | Ajustes |", "|---|---|"]
        for k, v in sorted(s["por_debio"].items(), key=lambda kv: -kv[1]):
            lines.append(f"| {_cell(k)} | {v} |")
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="kuraka-ajuste", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("root", nargs="?", default=".", help="project root (default: cwd)")
        p.add_argument("--req", required=True, help="REQ of the RUNNING cycle")

    p = sub.add_parser("add", help="record an adjustment the user asked for")
    common(p)
    p.add_argument("--tipo", required=True, choices=kc.AJUSTE_TIPOS)
    p.add_argument("--debio", required=True,
                   help='phase/agent that should have caught it, e.g. "1 po-analyst"')
    p.add_argument("--texto", required=True, help="the user's words, verbatim")
    p.add_argument("--resolucion", default=None)
    p = sub.add_parser("ronda", help="open a new user-validation round")
    common(p)
    p = sub.add_parser("resolver", help="mark an adjustment resolved")
    common(p)
    p.add_argument("--id", type=int, required=True)
    p.add_argument("--resolucion", required=True)
    p = sub.add_parser("aceptar", help="record the user's explicit acceptance")
    common(p)
    p.add_argument("--nota", default=None)
    p = sub.add_parser("cerrar", help="close WITHOUT acceptance (reason recorded)")
    common(p)
    p.add_argument("--motivo", required=True)
    p = sub.add_parser("estado", help="effectiveness summary")
    common(p)
    p.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)

    root = Path(a.root).expanduser().resolve()
    if not root.is_dir():
        print(f"❌ no existe: {root}", file=sys.stderr)
        return 1
    path = _ledger(root, a.req, create=a.cmd != "estado")

    if a.cmd == "estado":
        s = kc.ajustes_summary(path if path.is_file() else None)
        if a.json:
            print(json.dumps(s, ensure_ascii=False, indent=1))
        else:
            print(f"{a.req}: aceptación={s['aceptacion']} rondas={s['rondas']} "
                  f"ajustes={s['ajustes_total']} faltó={s['ajustes_falto']} "
                  f"pendientes={s['pendientes']}")
        return 0

    s = kc.ajustes_summary(path if path.is_file() else None)
    if a.cmd == "add":
        nid = max([int(x.get("id", 0)) for x in s["ajustes"]] or [0]) + 1
        _append(path, {"ev": "add", "id": nid, "ronda": s["rondas"] or 1, "ts": _now(),
                       "tipo": a.tipo, "debio": a.debio, "texto": a.texto,
                       "resolucion": a.resolucion})
        msg = f"ajuste #{nid} ({a.tipo}, debió: {a.debio})"
    elif a.cmd == "ronda":
        n = (s["rondas"] or 1) + 1
        _append(path, {"ev": "ronda", "ronda": n, "ts": _now()})
        msg = f"ronda {n} abierta"
    elif a.cmd == "resolver":
        if not any(int(x.get("id", -1)) == a.id for x in s["ajustes"]):
            print(f"❌ no existe el ajuste #{a.id} en {path.name}", file=sys.stderr)
            return 1
        _append(path, {"ev": "resolver", "id": a.id, "resolucion": a.resolucion, "ts": _now()})
        msg = f"ajuste #{a.id} resuelto"
    elif a.cmd == "aceptar":
        if s["pendientes"]:
            print(f"⚠ {s['pendientes']} ajuste(s) sin resolver — se registra la aceptación igual "
                  f"(el RETRO lo mostrará)", file=sys.stderr)
        _append(path, {"ev": "aceptar", "ronda": s["rondas"] or 1, "ts": _now(), "nota": a.nota})
        msg = "aceptado por el usuario → corré la fase 7 AHORA (RETRO + kuraka-backup)"
    else:  # cerrar
        _append(path, {"ev": "cerrar", "motivo": a.motivo, "ts": _now()})
        msg = "cierre SIN aceptación registrado"
    md = render_md(path, a.req)
    s = kc.ajustes_summary(path)
    print(f"✓ {msg} · {path.relative_to(root)} · aceptación={s['aceptacion']} "
          f"rondas={s['rondas']} ajustes={s['ajustes_total']} faltó={s['ajustes_falto']}")
    print(f"  vista: {md.relative_to(root)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
