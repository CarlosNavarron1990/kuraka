"""Vault-side regression tests for cycle archiving (RETRO + telemetry).

A closed cycle is archived as cycles/<REQ>/ = RETRO + telemetry + meta.yaml. Two
gaps found auditing the 15 mounted projects on 2026-08-31:

  1. telemetry is written AFTER the RETRO (the final-auditor closes the cycle, the
     dashboard aggregates later), but an already-archived cycle was skipped whole,
     so one that had been archived telemetry-less stayed that way forever;
  2. the join key was the exact filename, while projects name the telemetry with
     the short REQ id and the RETRO with the full slug — 7 of petsuite's 14
     telemetry files never reached the store.

Run from the vault root:  python3 -m pytest tests-vault/ -v
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VAULT))

import kuraka_common as kc  # noqa: E402


def _project(tmp_path: Path, req: str, telemetry_name: str | None = None) -> Path:
    proj = tmp_path / "proj"
    retros = proj / "docs" / "process" / "agent-retrospectives"
    retros.mkdir(parents=True)
    (retros / f"RETRO-{req}.md").write_text(
        f"# RETRO {req}\n\nVeredicto: HIGH\n", encoding="utf-8")
    if telemetry_name:
        td = proj / "docs" / "process" / "agent-telemetry"
        td.mkdir(parents=True, exist_ok=True)
        (td / telemetry_name).write_text('{"phases": []}', encoding="utf-8")
    return proj


def _archive(proj: Path, vault: Path, force: bool = False):
    return kc.archive_cycles(proj, vault, "demo", "main", "docs/process", force)


def _cycle(vault: Path, req: str) -> Path:
    return kc.cycles_dir(vault, "demo") / req


def test_exact_telemetry_is_archived_with_the_cycle(tmp_path):
    req = "REQ-20260813-alta-cliente"
    proj = _project(tmp_path, req, f"{req}-telemetry.json")
    rows = _archive(proj, tmp_path / "vault")
    assert rows[0]["status"] == "archived" and rows[0]["telem"] is True
    assert (_cycle(tmp_path / "vault", req) / f"{req}-telemetry.json").is_file()
    assert "has_telemetry: true" in (_cycle(tmp_path / "vault", req) / "meta.yaml").read_text()


def test_late_telemetry_is_attached_to_an_already_archived_cycle(tmp_path):
    req = "REQ-20260813-alta-cliente"
    vault = tmp_path / "vault"
    proj = _project(tmp_path, req)                      # RETRO only, no telemetry yet
    _archive(proj, vault)
    meta = _cycle(vault, req) / "meta.yaml"
    assert "has_telemetry: false" in meta.read_text()

    td = proj / "docs" / "process" / "agent-telemetry"  # …telemetry lands later
    td.mkdir(parents=True, exist_ok=True)
    (td / f"{req}-telemetry.json").write_text('{"phases": []}', encoding="utf-8")

    rows = _archive(proj, vault)                        # no --force needed
    assert rows[0]["status"] == "skip" and rows[0].get("telem_added") is True
    assert (_cycle(vault, req) / f"{req}-telemetry.json").is_file()
    assert "has_telemetry: true" in meta.read_text()


def test_short_req_telemetry_matches_the_full_slug_retro(tmp_path):
    """petsuite: REQ-20260813-REQ-011-telemetry.json for
    RETRO-REQ-20260813-REQ-011-slot-duration-overlap-prevention.md"""
    req = "REQ-20260813-REQ-011-slot-duration-overlap-prevention"
    proj = _project(tmp_path, req, "REQ-20260813-REQ-011-telemetry.json")
    rows = _archive(proj, tmp_path / "vault")
    assert rows[0]["telem"] is True
    assert (_cycle(tmp_path / "vault", req) / "REQ-20260813-REQ-011-telemetry.json").is_file()


def test_telemetry_named_without_the_suffix_still_matches(tmp_path):
    """adela writes docs/process/agent-telemetry/<REQ>.json, not
    <REQ>-telemetry.json. Inside that directory a .json IS telemetry."""
    req = "REQ-20260723-afiliacion-padron"
    proj = _project(tmp_path, req, f"{req}.json")
    rows = _archive(proj, tmp_path / "vault")
    assert rows[0]["telem"] is True
    assert (_cycle(tmp_path / "vault", req) / f"{req}.json").is_file()


def test_the_dashboard_is_not_mistaken_for_telemetry(tmp_path):
    req = "REQ-20260723-afiliacion-padron"
    proj = _project(tmp_path, req)
    td = proj / "docs" / "process" / "agent-telemetry"
    td.mkdir(parents=True, exist_ok=True)
    (td / "DASHBOARD.md").write_text("# dashboard\n", encoding="utf-8")
    rows = _archive(proj, tmp_path / "vault")
    assert rows[0]["telem"] is False
    assert not list(_cycle(tmp_path / "vault", req).glob("*.md"))[1:]  # only the RETRO


def test_the_confidence_line_becomes_the_archived_verdict(tmp_path):
    req = "REQ-20260830-demo"
    proj = _project(tmp_path, req)
    retro = proj / "docs" / "process" / "agent-retrospectives" / f"RETRO-{req}.md"
    retro.write_text("# RETRO\n\nbla\n\n## Confidence: HIGH\n", encoding="utf-8")
    rows = _archive(proj, tmp_path / "vault")
    assert rows[0]["verdict"] == "HIGH"
    assert 'verdict: "HIGH"' in (_cycle(tmp_path / "vault", req) / "meta.yaml").read_text()


def test_a_verdict_added_later_reaches_an_archived_cycle(tmp_path):
    """A RETRO archived without the Confidence line used to stay verdict-less
    forever — invisible to INDEX.md and pattern-detector (camisassis: 16/16)."""
    req = "REQ-20260830-demo"
    vault = tmp_path / "vault"
    proj = _project(tmp_path, req)
    _archive(proj, vault)
    meta = _cycle(vault, req) / "meta.yaml"
    assert 'verdict: ""' in meta.read_text()

    retro = proj / "docs" / "process" / "agent-retrospectives" / f"RETRO-{req}.md"
    retro.write_text(retro.read_text() + "\n## Confidence: MEDIUM\n", encoding="utf-8")

    rows = _archive(proj, vault)
    assert rows[0].get("verdict_added") is True
    assert 'verdict: "MEDIUM"' in meta.read_text()


# --- the cycle-close gate (every platform, no hook API needed) ----------------

def _backup(proj: Path, vault: Path, *extra: str):
    return subprocess.run(
        [sys.executable, str(VAULT / "kuraka-backup.py"), str(proj), "--name", "demo",
         "--vault", str(vault), "--target", "antigravity", *extra],
        capture_output=True, text=True)


def _antigravity_project(tmp_path: Path, retro_text: str) -> Path:
    """A project mounted for a platform that has NO hooks — where the framework
    used to rely on prose alone (camisassis closed 16 cycles verdict-less)."""
    proj = tmp_path / "proj"
    (proj / ".agents" / "agents").mkdir(parents=True)
    (proj / "kuraka.config.yaml").write_text("project:\n  name: demo\n", encoding="utf-8")
    retros = proj / "docs" / "process" / "agent-retrospectives"
    retros.mkdir(parents=True)
    (retros / "RETRO-REQ-1.md").write_text(retro_text, encoding="utf-8")
    return proj


def test_the_cycle_does_not_close_without_a_verdict_on_any_platform(tmp_path):
    vault = tmp_path / "vault"
    (vault / "projects").mkdir(parents=True)
    proj = _antigravity_project(tmp_path, "# RETRO\n\nsin veredicto\n")

    r = _backup(proj, vault)
    assert r.returncode == 1
    assert "NO cierra" in r.stderr and "## Confidence:" in r.stderr
    # the state IS preserved — it is the cycle that stays open, not the backup
    assert (kc.cycles_dir(vault, "demo") / "REQ-1" / "RETRO-REQ-1.md").is_file()


def test_re_running_the_backup_does_not_launder_a_verdictless_cycle(tmp_path):
    """The first version only checked NEWLY archived cycles, so a second run
    passed silently — the cycle was already archived and got skipped."""
    vault = tmp_path / "vault"
    (vault / "projects").mkdir(parents=True)
    proj = _antigravity_project(tmp_path, "# RETRO\n\nsin veredicto\n")

    assert _backup(proj, vault).returncode == 1
    assert _backup(proj, vault).returncode == 1


def test_adding_the_verdict_closes_the_cycle(tmp_path):
    vault = tmp_path / "vault"
    (vault / "projects").mkdir(parents=True)
    proj = _antigravity_project(tmp_path, "# RETRO\n\nsin veredicto\n")
    _backup(proj, vault)

    retro = proj / "docs" / "process" / "agent-retrospectives" / "RETRO-REQ-1.md"
    retro.write_text(retro.read_text() + "\n## Confidence: HIGH\n", encoding="utf-8")

    r = _backup(proj, vault)
    assert r.returncode == 0, r.stdout + r.stderr
    assert 'verdict: "HIGH"' in (kc.cycles_dir(vault, "demo") / "REQ-1" / "meta.yaml").read_text()


def test_missing_telemetry_warns_but_does_not_block(tmp_path):
    """A verdict is a judgment the auditor must give; telemetry can legitimately
    be unavailable on a platform without usage metrics."""
    vault = tmp_path / "vault"
    (vault / "projects").mkdir(parents=True)
    proj = _antigravity_project(tmp_path, "# RETRO\n\n## Confidence: MEDIUM\n")

    r = _backup(proj, vault)
    assert r.returncode == 0
    assert "SIN telemetría" in r.stderr


def test_the_escape_hatch_is_explicit(tmp_path):
    vault = tmp_path / "vault"
    (vault / "projects").mkdir(parents=True)
    proj = _antigravity_project(tmp_path, "# RETRO\n\nsin veredicto\n")
    assert _backup(proj, vault, "--allow-incomplete-retro").returncode == 0


def test_an_ambiguous_prefix_is_never_guessed(tmp_path):
    req = "REQ-20260813-REQ-011-slot-duration"
    proj = _project(tmp_path, req, "REQ-20260813-REQ-011-telemetry.json")
    td = proj / "docs" / "process" / "agent-telemetry"
    (td / "REQ-20260813-REQ-011-slot-telemetry.json").write_text("{}", encoding="utf-8")
    rows = _archive(proj, tmp_path / "vault")
    assert rows[0]["telem"] is False          # two candidates → attach none
    assert not list(_cycle(tmp_path / "vault", req).glob("*-telemetry.json"))


def test_a_prefix_must_end_on_a_req_boundary(tmp_path):
    """`REQ-20260813-REQ-01` must not claim the cycle `REQ-20260813-REQ-011…`."""
    req = "REQ-20260813-REQ-011-slot-duration"
    proj = _project(tmp_path, req, "REQ-20260813-REQ-01-telemetry.json")
    rows = _archive(proj, tmp_path / "vault")
    assert rows[0]["telem"] is False


def test_a_too_short_stem_never_matches(tmp_path):
    req = "REQ-20260813-alta-cliente"
    proj = _project(tmp_path, req, "REQ-telemetry.json")
    rows = _archive(proj, tmp_path / "vault")
    assert rows[0]["telem"] is False
