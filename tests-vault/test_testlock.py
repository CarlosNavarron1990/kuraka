"""kuraka-testlock — locked acceptance tests (spec first). Vault-only tests."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("testlock", VAULT / "kuraka-testlock.py")
tl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tl)


def _proj(tmp_path: Path) -> Path:
    root = tmp_path / "p"
    (root / "tests").mkdir(parents=True)
    (root / "kuraka.config.yaml").write_text(
        "architecture:\n  paths:\n    docs_process_root: docs/proc/\n", encoding="utf-8")
    (root / "tests" / "test_a.py").write_text("def test_a():\n    assert f() == 3  # AC-1\n")
    (root / "tests" / "test_b.py").write_text("def test_b():\n    assert g() == 'x'  # AC-2\n")
    return root


def test_lock_then_verify_clean(tmp_path, capsys):
    root = _proj(tmp_path)
    assert tl.main(["lock", str(root), "--req", "R1", "tests/test_a.py", "tests/test_b.py"]) == 0
    lock = root / "docs/proc/checkpoints/TESTLOCK-R1.json"
    assert set(json.loads(lock.read_text())["files"]) == {"tests/test_a.py", "tests/test_b.py"}
    assert tl.main(["verify", str(root), "--req", "R1"]) == 0


def test_modified_or_deleted_fails(tmp_path, capsys):
    root = _proj(tmp_path)
    tl.main(["lock", str(root), "--req", "R1", "tests/test_a.py", "tests/test_b.py"])
    (root / "tests/test_a.py").write_text("def test_a():\n    assert f() == 4\n")  # bent to the code
    (root / "tests/test_b.py").unlink()
    capsys.readouterr()
    assert tl.main(["verify", str(root), "--req", "R1"]) == 1
    out = capsys.readouterr().out
    assert "tests/test_a.py — modificado" in out and "tests/test_b.py — borrado" in out


def test_unlock_allows_one_change_and_relock_consumes(tmp_path):
    root = _proj(tmp_path)
    tl.main(["lock", str(root), "--req", "R1", "tests/test_a.py"])
    assert tl.main(["unlock", str(root), "--req", "R1", "--file", "tests/test_a.py",
                    "--motivo", "el plan tenía 3, el contrato dice 4", "--aprobado-por", "user"]) == 0
    (root / "tests/test_a.py").write_text("def test_a():\n    assert f() == 4  # AC-1 v2\n")
    assert tl.main(["verify", str(root), "--req", "R1"]) == 0
    tl.main(["lock", str(root), "--req", "R1", "tests/test_a.py"])  # re-arm
    data = json.loads((root / "docs/proc/checkpoints/TESTLOCK-R1.json").read_text())
    assert data["unlocks"][0].get("consumed")
    (root / "tests/test_a.py").write_text("def test_a():\n    assert True\n")
    assert tl.main(["verify", str(root), "--req", "R1"]) == 1


def test_unlock_requires_locked_file(tmp_path):
    root = _proj(tmp_path)
    assert tl.main(["unlock", str(root), "--req", "R1", "--file", "tests/test_a.py",
                    "--motivo", "x", "--aprobado-por", "user"]) == 1


def test_verify_without_lock_warns_but_passes(tmp_path, capsys):
    root = _proj(tmp_path)
    assert tl.main(["verify", str(root), "--req", "R9"]) == 0
    assert "3.95" in capsys.readouterr().out
