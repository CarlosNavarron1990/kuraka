"""Codex direct-mode mounting, scope evidence, closure and archive compatibility."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

VAULT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VAULT))
import kuraka_common as kc


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, VAULT / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


mount = module("mount_ahorro", "kuraka-mount.py")
export = module("export_ahorro", "kuraka-export.py")
aggregate = module("aggregate_ahorro", "aggregate-telemetry.py")
SCRIPT = VAULT / "skills/kuraka-ahorro/scripts/cycle.py"


def run(project, *args, ok=True):
    result = subprocess.run([sys.executable, str(SCRIPT), "--project", str(project), *args],
                            capture_output=True, text=True)
    if ok:
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)
    assert result.returncode != 0, result.stdout
    return result.stderr


@pytest.fixture
def project(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "kuraka.config.yaml").write_text("project:\n  name: fixture\n")
    (tmp_path / "app.py").write_text("value = 1\n")
    (tmp_path / "unrelated.txt").write_text("user work\n")
    return tmp_path


def begin(project):
    return run(project, "start", "--docs-root", "custom/process",
               "--objective", "Correct local value", "--files", "app.py")["cycle"]


def check(project, cycle, expression="assert open('app.py').read() == 'value = 2\\n'"):
    return run(project, "check", "--cycle", cycle, "--", sys.executable, "-c", expression)


def close(project, cycle, ok=True):
    return run(project, "close", "--cycle", cycle, "--summary", "Corrected local value",
               "--confidence", "HIGH", ok=ok)


def test_closure_preserves_baseline_and_archives_without_specialist(project, tmp_path):
    cycle = begin(project)
    baseline = project / ".codex/ultra-ahorro" / cycle / "baseline/app.py"
    assert baseline.read_text() == "value = 1\n"
    (project / "app.py").write_text("value = 2\n")
    check(project, cycle)
    result = close(project, cycle)
    assert close(project, cycle) == result  # idempotent; no duplicate record
    assert (project / "unrelated.txt").read_text() == "user work\n"
    telemetry = json.loads((project / result["artifacts"][1]).read_text())
    assert telemetry["subagents"] == 0
    assert telemetry["runs"][0]["total_tokens"] is None
    store = tmp_path / "store"
    rows = kc.archive_cycles(project, store, "fixture", "main", "custom/process", False)
    assert rows[0]["status"] == "archived" and rows[0]["telem"] is True
    meta = kc.cycles_dir(store, "fixture") / cycle / "meta.yaml"
    assert 'verdict: "HIGH"' in meta.read_text()


def test_close_refuses_missing_failed_stale_and_out_of_scope_evidence(project):
    cycle = begin(project)
    assert "Missing" in close(project, cycle, ok=False)
    run(project, "check", "--cycle", cycle, "--", sys.executable, "-c", "raise SystemExit(1)", ok=False)
    assert "failed" in close(project, cycle, ok=False)
    # A different green command must not conceal the selected failing check.
    check(project, cycle, "pass")
    assert "failed" in close(project, cycle, ok=False)
    run(project, "abort", "--cycle", cycle, "--reason", "Choose a new verification plan")
    cycle = begin(project)
    check(project, cycle, "pass")
    (project / "app.py").write_text("value = 2\n")
    assert "stale" in close(project, cycle, ok=False)
    check(project, cycle, "pass")
    (project / "unrelated.txt").write_text("concurrent work\n")
    assert "Out-of-scope" in close(project, cycle, ok=False)


def test_failed_check_can_be_retried_and_abort_keeps_edits(project):
    cycle = begin(project)
    expression = "assert open('app.py').read() == 'value = 2\\n'"
    run(project, "check", "--cycle", cycle, "--", sys.executable, "-c", expression, ok=False)
    (project / "app.py").write_text("value = 2\n")
    check(project, cycle, expression)
    assert close(project, cycle)["status"] == "closed"
    second = begin(project)
    (project / "app.py").write_text("value = 3\n")
    run(project, "abort", "--cycle", second, "--reason", "Risk discovered")
    assert (project / "app.py").read_text() == "value = 3\n"
    assert "no longer active" in close(project, second, ok=False)


@pytest.mark.parametrize("path", ["../escape", "/tmp/escape", ".", ".git/config"])
def test_invalid_scope_is_rejected(project, path):
    run(project, "start", "--docs-root", "docs/process", "--objective", "test",
        "--files", path, ok=False)


def test_symlink_escape_is_rejected(project, tmp_path):
    (project / "link").symlink_to(project.parent)
    run(project, "start", "--docs-root", "docs/process", "--objective", "test",
        "--files", "link/outside.txt", ok=False)


def test_codex_mount_has_short_router_full_reference_and_no_phantom_overrides(tmp_path):
    skills = tmp_path / ".codex/skills"
    mount.sync_codex_skills(VAULT / "skills", skills)
    export.export_codex_command_skills(VAULT, tmp_path, quiet=True)
    router = (skills / "kuraka/SKILL.md").read_text()
    reference = skills / "kuraka/references/workflow.md"
    assert len(router.splitlines()) < 80
    assert "references/workflow.md" in router and reference.is_file()
    assert len(reference.read_text().splitlines()) > 500
    assert ".claude/" not in reference.read_text()
    assert (skills / "kuraka-ahorro/scripts/cycle.py").is_file()
    assert kc.detect_overrides(tmp_path, VAULT, platform="codex") == []
    kc.write_mount_manifest(tmp_path, VAULT, ("skills",), platform="codex")
    assert kc.detect_overrides(tmp_path, VAULT, platform="codex") == []
    reference.write_text(reference.read_text() + "\nProject-specific tuning\n")
    assert Path("skills/kuraka/references/workflow.md") in kc.detect_overrides(
        tmp_path, VAULT, platform="codex")


def test_the_evidence_helper_is_bundled_only_where_it_is_used(tmp_path):
    """Claude enforces the mode with skill frontmatter + the orchestrator guard,
    so it receives the skill but NOT this helper; Antigravity has neither
    mechanism and receives nothing. See tests-vault/test_claude_ultra_ahorro.py."""
    mount.sync_antigravity_skills(VAULT / "skills", tmp_path / "agents")
    assert not (tmp_path / "agents/kuraka-ahorro.md").exists()
    assert not (tmp_path / "agents/kuraka-ahorro").exists()
    kc.write_mount_manifest(tmp_path, VAULT, ("skills",), platform="antigravity")
    assert "skills/kuraka-ahorro.md" not in kc.load_mount_manifest(tmp_path, "antigravity")

    mount.sync_claude_skills(VAULT / "skills", tmp_path / "claude")
    assert (tmp_path / "claude/kuraka-ahorro/SKILL.md").is_file()
    assert not (tmp_path / "claude/kuraka-ahorro/scripts").exists()


def test_unavailable_usage_is_not_rendered_as_zero():
    cycle = {"req_name": "test", "mode": "ultra-ahorro", "runs": [
        {"agent": "codex-main", "total_tokens": None, "tool_uses": None,
         "usage_source": "unavailable"}]}
    dashboard = aggregate.render_dashboard([cycle])
    assert "| test | ultra-ahorro | 1 | n/a | n/a |" in dashboard
    assert "| codex-main | 1 | n/a | n/a | n/a |" in dashboard
    assert "Total tokens: **n/a**" in dashboard


def test_real_codex_update_and_mounted_harness(tmp_path):
    (tmp_path / ".codex/agents").mkdir(parents=True)
    (tmp_path / "kuraka.config.yaml").write_text(
        "project:\n  name: ahorro-fixture\nworkflow:\n  default_mode: normal\n"
        "  codex_default_mode: ultra-ahorro\n")
    result = subprocess.run(
        [sys.executable, str(VAULT / "kuraka-mount.py"), str(tmp_path),
         "--target", "codex", "--update"],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (tmp_path / ".claude/hooks").exists()
    assert "Ultra Ahorro" in (tmp_path / "AGENTS.md").read_text()
    check = subprocess.run([sys.executable, "-m", "pytest", "tests/kuraka/", "-q"],
                           cwd=tmp_path, capture_output=True, text=True)
    assert check.returncode == 0, check.stdout + check.stderr
