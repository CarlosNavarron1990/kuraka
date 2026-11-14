"""Phase 6.9 — user-validation ledger (kuraka-ajuste.py) — vault-only tests."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VAULT))
import kuraka_common as kc  # noqa: E402

CLI = VAULT / "kuraka-ajuste.py"


def _proj(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    root.mkdir()
    (root / "kuraka.config.yaml").write_text(
        "architecture:\n  paths:\n    docs_process_root: docs/process/\n", encoding="utf-8")
    return root


def _run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(CLI), *args], capture_output=True,
                          text=True, encoding="utf-8", check=False)


def test_full_round_trip_and_md(tmp_path):
    root = _proj(tmp_path)
    req = "REQ-20261114-ABC-7-demo"
    assert _run("add", str(root), "--req", req, "--tipo", "falto-preguntar",
                "--debio", "1 po-analyst", "--texto", "no preguntó el filtro").returncode == 0
    assert _run("add", str(root), "--req", req, "--tipo", "bug",
                "--debio", "6.8 recorrido", "--texto", "el botón no guarda").returncode == 0
    assert _run("ronda", str(root), "--req", req).returncode == 0
    assert _run("resolver", str(root), "--req", req, "--id", "1",
                "--resolucion", "delta S3").returncode == 0
    assert _run("resolver", str(root), "--req", req, "--id", "9",
                "--resolucion", "x").returncode == 1
    assert _run("aceptar", str(root), "--req", req, "--nota", "ok").returncode == 0
    r = _run("estado", str(root), "--req", req, "--json")
    s = json.loads(r.stdout)
    assert s["aceptacion"] == "tras-2-rondas" and s["rondas"] == 2
    assert s["ajustes_total"] == 2 and s["ajustes_falto"] == 1 and s["pendientes"] == 1
    assert s["por_debio"] == {"1 po-analyst": 1, "6.8 recorrido": 1}
    md = (root / "docs/process/ajustes" / f"AJUSTES-{req}.md").read_text(encoding="utf-8")
    assert "no preguntó el filtro" in md and "tras-2-rondas" in md


def test_first_pass_and_prefix_match(tmp_path):
    root = _proj(tmp_path)
    assert _run("aceptar", str(root), "--req", "REQ-20261114-ABC-8-x").returncode == 0
    # a shortened REQ id resolves to the same ledger
    s = json.loads(_run("estado", str(root), "--req", "REQ-20261114-ABC-8", "--json").stdout)
    assert s["aceptacion"] == "primera-ronda" and s["aceptado"]


def test_no_ledger_is_sin_registro(tmp_path):
    root = _proj(tmp_path)
    s = json.loads(_run("estado", str(root), "--req", "REQ-20261114-Z-1", "--json").stdout)
    assert s["aceptacion"] == "sin-registro" and not s["registro"]
    assert not (root / "docs/process/ajustes").exists()  # estado never creates


def test_cerrar_without_acceptance(tmp_path):
    root = _proj(tmp_path)
    req = "REQ-20261114-Q-2"
    _run("add", str(root), "--req", req, "--tipo", "ux", "--debio", "4b frontend-developer",
         "--texto", "muy lento")
    _run("cerrar", str(root), "--req", req, "--motivo", "usuario sin tiempo")
    s = kc.ajustes_summary(kc.find_ajustes(req, kc.ajustes_dir(root)))
    assert s["aceptacion"] == "sin-aceptacion" and s["cierre_sin_aceptacion"] == "usuario sin tiempo"


def test_archive_copies_ledger_and_stamps_meta(tmp_path):
    root = _proj(tmp_path)
    req = "REQ-20261114-ARC-1-feature"
    _run("add", str(root), "--req", "REQ-20261114-ARC-1", "--tipo", "falto-hacer",
         "--debio", "3 architect-reviewer", "--texto", "faltó el índice")
    _run("aceptar", str(root), "--req", "REQ-20261114-ARC-1")
    retros = root / "docs/process/agent-retrospectives"
    retros.mkdir(parents=True)
    (retros / f"RETRO-{req}.md").write_text("# r\n## Confidence: HIGH\n", encoding="utf-8")
    vault = tmp_path / "vault"
    rows = kc.archive_cycles(root, vault, "demo", "main", "docs/process", force=False)
    assert rows and rows[0]["status"] == "archived"
    dest = kc.cycles_dir(vault, "demo") / req
    assert (dest / "AJUSTES-REQ-20261114-ARC-1.jsonl").is_file()
    meta = (dest / "meta.yaml").read_text(encoding="utf-8")
    assert 'aceptacion: "tras-2-rondas"' in meta
    assert "ajustes_total: 1" in meta and "ajustes_falto: 1" in meta
    # second run is idempotent and keeps a single set of fields
    kc.archive_cycles(root, vault, "demo", "main", "docs/process", force=False)
    assert (dest / "meta.yaml").read_text(encoding="utf-8").count("aceptacion:") == 1


def test_archive_without_ledger_is_sin_registro(tmp_path):
    root = _proj(tmp_path)
    req = "REQ-20261114-NOL-1"
    retros = root / "docs/process/agent-retrospectives"
    retros.mkdir(parents=True)
    (retros / f"RETRO-{req}.md").write_text("# r\n## Confidence: HIGH\n", encoding="utf-8")
    vault = tmp_path / "vault"
    kc.archive_cycles(root, vault, "demo", "main", "docs/process", force=False)
    meta = (kc.cycles_dir(vault, "demo") / req / "meta.yaml").read_text(encoding="utf-8")
    assert 'aceptacion: "sin-registro"' in meta


def test_doctor_flags_accepted_cycle_missing_phase7(tmp_path):
    import importlib.util
    spec = importlib.util.spec_from_file_location("kdoctor", VAULT / "kuraka-doctor.py")
    doc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(doc)
    root = _proj(tmp_path)
    (root / "docs/process").mkdir(parents=True)
    req = "REQ-20250101-OLD-1-done"
    (root / "docs/process" / f"{req}.md").write_text("# req\n", encoding="utf-8")
    _run("aceptar", str(root), "--req", req)
    vault = tmp_path / "vault"
    (vault / "projects" / "demo").mkdir(parents=True)
    findings = doc.repo_findings(vault, root, "demo", "docs/process")
    cyc = [f for f in findings if f.code == "cycles"]
    assert any("falta solo la fase 7" in f.msg and req in f.msg for f in cyc)
    # the accepted cycle is not ALSO listed as a plain open cycle
    assert not any("abierto(s) sin RETRO" in f.msg and req in f.msg for f in cyc)
