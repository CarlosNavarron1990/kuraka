"""Vault-side regression tests for the RETRO file contract hook.

`## Confidence: HIGH|MEDIUM|LOW` in the RETRO **file** is what `find_verdict`
parses into `cycles/<REQ>/meta.yaml` and `projects/INDEX.md`. Nothing enforced it
on the file until 2026-08-31 — `output_validate.py` judges the agent's RESPONSE —
so only 58 of 189 archived cycles carried a verdict, and the rest are invisible
to `pattern-detector`. This hook closes that at write time on Claude; elsewhere
the Phase 7 gate (`kuraka-doctor`) catches it before the cycle closes.

Run from the vault root:  python3 -m pytest tests-vault/ -v
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]
HOOK = VAULT / "hooks" / "retro_contract.py"

BODY = "# RETRO\n\n" + ("Analisis del ciclo. " * 40) + "\n"


def _project(tmp_path: Path, kuraka: bool = True) -> Path:
    proj = tmp_path / "proj"
    (proj / "docs" / "process" / "agent-retrospectives").mkdir(parents=True)
    if kuraka:
        (proj / "kuraka.config.yaml").write_text("project:\n  name: p\n", encoding="utf-8")
    return proj


def _write(proj: Path, name: str, text: str) -> Path:
    f = proj / "docs" / "process" / "agent-retrospectives" / name
    f.write_text(text, encoding="utf-8")
    return f


def _fire(proj: Path, path: Path, tool: str = "Write") -> subprocess.CompletedProcess:
    payload = {"tool_name": tool, "cwd": str(proj),
               "tool_input": {"file_path": str(path)}}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps(payload),
                          capture_output=True, text=True,
                          env={"CLAUDE_PROJECT_DIR": str(proj), "PATH": "/usr/bin:/bin"})


def test_a_retro_without_the_verdict_line_is_rejected_once(tmp_path):
    proj = _project(tmp_path)
    f = _write(proj, "RETRO-REQ-1.md", BODY)

    r = _fire(proj, f)
    assert r.returncode == 2
    assert "## Confidence:" in r.stderr and "RETRO-REQ-1.md" in r.stderr

    r = _fire(proj, f)            # loop guard: never blocks the same RETRO twice
    assert r.returncode == 0


def test_a_complete_retro_passes(tmp_path):
    proj = _project(tmp_path)
    for verdict in ("HIGH", "MEDIUM", "LOW"):
        f = _write(proj, f"RETRO-{verdict}.md", BODY + f"\n## Confidence: {verdict}\n")
        assert _fire(proj, f).returncode == 0, verdict


def test_a_partial_first_write_is_not_a_violation(tmp_path):
    """The RETRO is often built up; a short stub must not be judged."""
    proj = _project(tmp_path)
    f = _write(proj, "RETRO-REQ-2.md", "# RETRO\n\nempezando\n")
    assert _fire(proj, f).returncode == 0


def test_non_retro_files_and_the_latest_copy_are_ignored(tmp_path):
    proj = _project(tmp_path)
    other = _write(proj, "REQ-1.md", BODY)
    latest = _write(proj, "RETRO-LATEST.md", BODY)
    assert _fire(proj, other).returncode == 0
    assert _fire(proj, latest).returncode == 0


def test_the_hook_is_inert_outside_a_kuraka_project(tmp_path):
    proj = _project(tmp_path, kuraka=False)
    f = _write(proj, "RETRO-REQ-3.md", BODY)
    assert _fire(proj, f).returncode == 0


def test_the_hook_fails_open_on_unexpected_input(tmp_path):
    r = subprocess.run([sys.executable, str(HOOK)], input="no soy json",
                       capture_output=True, text=True)
    assert r.returncode == 0
