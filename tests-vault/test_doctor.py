"""Vault-side regression tests for kuraka-doctor.py.

The lesson of the 2026-08 store audit: a green exit code proves nothing about
the RESULT. Every defect found (5 projects with no kuraka.config.yaml, an entire
agent suite snapshotted as "overrides", telemetry never attached, a rename
splitting a project's history) had passed a successful mount and backup. The
doctor checks the state itself and is wired into the lifecycle — session start,
cycle start, Phase 7 and every mount — so none of it can go unnoticed again.

Run from the vault root:  python3 -m pytest tests-vault/ -v
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VAULT))

import kuraka_common as kc  # noqa: E402

DOCTOR = VAULT / "kuraka-doctor.py"
HOOK = VAULT / "hooks" / "session_doctor.py"


def _healthy(tmp_path: Path):
    """A minimal but genuinely healthy project + its own mini-vault.

    The mini-vault carries what a baseline comparison needs (SUITE-VERSION +
    agents/), so the test never writes into the real store."""
    store = tmp_path / "vault"
    (store / "projects").mkdir(parents=True)
    shutil.copy2(VAULT / "SUITE-VERSION", store / "SUITE-VERSION")
    shutil.copytree(VAULT / "agents", store / "agents")
    # the hook resolves the doctor through $KURAKA_VAULT, as it does in a real
    # consumer (it runs from .claude/hooks/, not from the vault)
    for f in ("kuraka-doctor.py", "kuraka_common.py"):
        shutil.copy2(VAULT / f, store / f)
    proj = tmp_path / "app"
    (proj / ".claude" / "agents").mkdir(parents=True)
    (proj / ".claude" / "project" / "conventions").mkdir(parents=True)
    (proj / ".claude" / "project" / "glossary.md").write_text("# g\n", encoding="utf-8")
    shutil.copy2(store / "agents" / "code-reviewer.md", proj / ".claude" / "agents")
    (proj / "kuraka.config.yaml").write_text(
        "schema_version: 1\nproject:\n  name: app\n", encoding="utf-8")
    kc.write_mount_manifest(proj, store, ("agents",), platform="claude")

    d = store / "projects" / "app"
    d.mkdir(parents=True)
    (d / "registry.md").write_text(f"---\nname: app\npath: {proj}\n---\n", encoding="utf-8")
    return store, proj


def _doctor(store: Path, proj: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(DOCTOR), str(proj), "--vault", str(store), *extra],
        capture_output=True, text=True)


def test_a_healthy_project_is_green(tmp_path):
    store, proj = _healthy(tmp_path)
    r = _doctor(store, proj)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "fluyendo correctamente" in r.stdout


def test_a_missing_config_is_a_finding_and_is_repairable(tmp_path):
    store, proj = _healthy(tmp_path)
    (proj / "kuraka.config.yaml").unlink()

    r = _doctor(store, proj)
    assert r.returncode == 1
    assert "[config]" in r.stdout

    r = _doctor(store, proj, "--fix")
    assert (proj / "kuraka.config.yaml").is_file()
    assert r.returncode == 0, r.stdout


def test_a_local_agent_tuning_out_of_sync_is_a_finding(tmp_path):
    store, proj = _healthy(tmp_path)
    with open(proj / ".claude" / "agents" / "code-reviewer.md", "a", encoding="utf-8") as fh:
        fh.write("\n<!-- ajuste local -->\n")

    r = _doctor(store, proj)
    assert r.returncode == 1 and "[overrides]" in r.stdout

    r = _doctor(store, proj, "--fix")
    assert r.returncode == 0, r.stdout
    stored = kc.overrides_dir(store, "app", "claude") / "agents" / "code-reviewer.md"
    assert "ajuste local" in stored.read_text()


def test_an_unarchived_retro_is_a_finding_and_is_repairable(tmp_path):
    store, proj = _healthy(tmp_path)
    retros = proj / "docs" / "process" / "agent-retrospectives"
    retros.mkdir(parents=True)
    (retros / "RETRO-REQ-1-demo.md").write_text(
        "# RETRO\n\n## Confidence: HIGH\n", encoding="utf-8")
    telem = proj / "docs" / "process" / "agent-telemetry"
    telem.mkdir(parents=True)
    (telem / "REQ-1-demo-telemetry.json").write_text("{}", encoding="utf-8")

    r = _doctor(store, proj)
    assert r.returncode == 1 and "[retros]" in r.stdout

    r = _doctor(store, proj, "--fix")
    assert r.returncode == 0, r.stdout
    assert (kc.cycles_dir(store, "app") / "REQ-1-demo" / "RETRO-REQ-1-demo.md").is_file()


def test_a_cycle_closed_without_telemetry_is_flagged(tmp_path):
    """On platforms without the PostToolUse hook nothing writes it — camisassis
    closed 16 cycles with none, and no gate ever said so."""
    store, proj = _healthy(tmp_path)
    retros = proj / "docs" / "process" / "agent-retrospectives"
    retros.mkdir(parents=True)
    (retros / "RETRO-REQ-3-demo.md").write_text(
        "# RETRO\n\n## Confidence: HIGH\n", encoding="utf-8")

    r = _doctor(store, proj, "--fix")   # archives it, then notices the gap
    assert r.returncode == 1
    assert "[telemetry]" in r.stdout and "sin telemetría" in r.stdout


def test_a_retro_without_the_confidence_line_is_flagged(tmp_path):
    """It archives fine but lands in INDEX.md with an empty verdict, so the
    cycle counts for nothing across projects (camisassis: 16 of 16)."""
    store, proj = _healthy(tmp_path)
    retros = proj / "docs" / "process" / "agent-retrospectives"
    retros.mkdir(parents=True)
    (retros / "RETRO-REQ-2-demo.md").write_text("# RETRO\n\nsin veredicto\n", encoding="utf-8")

    r = _doctor(store, proj, "--fix")   # archives it, then notices the gap
    assert r.returncode == 1
    assert "[verdict]" in r.stdout and "## Confidence:" in r.stdout


def test_a_slug_mismatch_is_reported_but_never_auto_fixed(tmp_path):
    """A rename is a naming decision — the doctor explains it, it does not act."""
    store, proj = _healthy(tmp_path)
    (proj / "kuraka.config.yaml").write_text(
        "schema_version: 1\nproject:\n  name: otro-nombre\n", encoding="utf-8")

    r = _doctor(store, proj, "--fix")
    assert r.returncode == 1
    assert "[config]" in r.stdout and "kuraka-merge-project.py" in r.stdout
    assert not (store / "projects" / "otro-nombre").exists()


def test_a_missing_manifest_asks_for_a_remount_instead_of_faking_one(tmp_path):
    """Regenerating the manifest from the current files would freeze a real
    project tuning as the baseline — so it is never done automatically."""
    store, proj = _healthy(tmp_path)
    (proj / ".claude" / kc.MOUNT_MANIFEST_NAME).unlink()

    r = _doctor(store, proj, "--fix")
    assert r.returncode == 1
    assert "[manifest]" in r.stdout and "--update" in r.stdout


def test_a_non_kuraka_directory_is_silent_in_brief_mode(tmp_path):
    store = tmp_path / "vault"
    (store / "projects").mkdir(parents=True)
    plain = tmp_path / "cualquier-repo"
    plain.mkdir()
    r = _doctor(store, plain, "--brief")
    assert r.returncode == 0 and r.stdout.strip() == ""


# --- the SessionStart hook ----------------------------------------------------

def _run_hook(proj: Path, store: Path) -> subprocess.CompletedProcess:
    env = {"KURAKA_VAULT": str(store), "PATH": "/usr/bin:/bin", "HOME": str(proj)}
    return subprocess.run([sys.executable, str(HOOK)], input=json.dumps({"cwd": str(proj)}),
                          capture_output=True, text=True, env=env)


def test_hook_is_silent_on_a_healthy_project(tmp_path):
    store, proj = _healthy(tmp_path)
    r = _run_hook(proj, store)
    assert r.returncode == 0 and r.stdout.strip() == ""


def test_hook_surfaces_findings_without_ever_blocking(tmp_path):
    store, proj = _healthy(tmp_path)
    (proj / "kuraka.config.yaml").unlink()
    r = _run_hook(proj, store)
    assert r.returncode == 0            # never blocks a session
    assert "[config]" in r.stdout and "--fix" in r.stdout


def test_hook_is_inert_outside_a_kuraka_project(tmp_path):
    store = tmp_path / "vault"
    (store / "projects").mkdir(parents=True)
    plain = tmp_path / "repo"
    plain.mkdir()
    r = _run_hook(plain, store)
    assert r.returncode == 0 and r.stdout.strip() == ""
