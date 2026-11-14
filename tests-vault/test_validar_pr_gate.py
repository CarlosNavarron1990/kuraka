"""validar-pr (vault skill) + hooks/pr_gate.py — vault-only tests.

Pins the semantics adopted from the guai-agents-platform-azure team hook
(2026-11): APROBABLE-for-HEAD gate on `gh pr create|new|ready`, protected-branch
push block, no pre-push bypass, fail-CLOSED only on what the gate guards, and
coexistence (inert when the project versions its own validar-pr). Also runs the
skill's own batteries (no Docker, no network) so the shell pieces stay green.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

VAULT = Path(__file__).resolve().parents[1]
HOOK = VAULT / "hooks" / "pr_gate.py"
SCRIPTS = VAULT / "skills" / "validar-pr" / "scripts"

pytestmark = pytest.mark.skipif(shutil.which("git") is None, reason="git required")


def _env(proj: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_") and k != "VALIDAR_PR_DENTRO"}
    env.update(CLAUDE_PROJECT_DIR=str(proj), GIT_CONFIG_GLOBAL="/dev/null", PYTHONUTF8="1")
    return env


def _run(proj: Path, cmd: "str | None" = None, raw: "str | None" = None) -> int:
    payload = raw if raw is not None else json.dumps({"tool_input": {"command": cmd}})
    return subprocess.run([sys.executable, str(HOOK)], input=payload.encode(), cwd=proj,
                          env=_env(proj), capture_output=True).returncode


def _git(proj: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(proj), "-c", "user.email=t@t", "-c", "user.name=t",
                           "-c", "commit.gpgsign=false", *args], env=_env(proj),
                          capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def adopted(tmp_path: Path) -> Path:
    proj = tmp_path / "p"
    (proj / ".claude/project/validar-pr").mkdir(parents=True)
    (proj / ".claude/project/validar-pr/config.sh").write_text('VP_RAMAS_PROTEGIDAS="main qa"\n')
    _git(proj.parent, "init", "-q", str(proj))
    _git(proj, "commit", "-q", "--allow-empty", "-m", "init")
    _git(proj, "checkout", "-q", "-b", "feat/x", "--no-track")
    return proj


def _approve(proj: Path) -> None:
    sha = _git(proj, "rev-parse", "HEAD")
    d = proj / ".git" / "validar-pr"
    d.mkdir(exist_ok=True)
    (d / f"{sha}.md").write_text(f"<!-- validar-pr sha={sha} base={'0' * 40} veredicto=APROBABLE -->\nok\n")


def test_pr_needs_aprobable_report_for_head(adopted):
    assert _run(adopted, "gh pr create --title x") == 2
    _approve(adopted)
    assert _run(adopted, "gh pr create --title x") == 0
    _git(adopted, "commit", "-q", "--allow-empty", "-m", "nuevo")  # HEAD moved
    assert _run(adopted, "gh pr ready 3") == 2


def test_protected_branches_come_from_layer_config(adopted):
    assert _run(adopted, "git push origin qa") == 2
    assert _run(adopted, "git push origin develop") == 0  # not protected in this repo
    assert _run(adopted, "git push --no-verify origin feat/x") == 2
    assert _run(adopted, 'git commit -m "git push origin main"') == 0


def test_fail_closed_only_on_what_it_guards(adopted):
    assert _run(adopted, raw="no-json gh pr create") == 2
    assert _run(adopted, raw="no-json git push origin feat/x") == 2
    assert _run(adopted, raw="no-json ls -la") == 0


def test_inert_when_not_adopted(tmp_path):
    _git(tmp_path, "init", "-q")
    assert _run(tmp_path, "gh pr create --title x") == 0
    assert _run(tmp_path, "git push origin main") == 0


def test_inert_when_project_versions_its_own_validar_pr(adopted):
    own = adopted / ".claude/skills/validar-pr"
    own.mkdir(parents=True)
    (own / "SKILL.md").write_text("del equipo\n")
    (own / "config.sh").write_text("VP_RAMA_BASE=develop\n")
    _git(adopted, "add", ".claude/skills/validar-pr")
    assert _run(adopted, "gh pr create --title x") == 0  # the team's hook gates, not Kuraka


def test_inert_when_settings_wire_team_hook(adopted):
    (adopted / ".claude/settings.json").write_text(json.dumps({"hooks": {"PreToolUse": [{"hooks": [
        {"type": "command", "command": "bash .claude/skills/validar-pr/scripts/hook-claude.sh"}]}]}}))
    assert _run(adopted, "gh pr create --title x") == 0


def test_enforce_hook_false_turns_it_off(adopted):
    (adopted / "kuraka.config.yaml").write_text("workflow:\n  validar_pr:\n    enforce_hook: false\n")
    assert _run(adopted, "gh pr create --title x") == 0


def test_skill_copies_identical():
    assert (VAULT / "skills/validar-pr.md").read_bytes() == (VAULT / "skills/validar-pr/SKILL.md").read_bytes()


@pytest.mark.skipif(shutil.which("bash") is None, reason="bash required")
@pytest.mark.parametrize("battery", ["test-hook-claude.sh", "test-validar-pr.sh"])
def test_skill_batteries_green(battery):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    r = subprocess.run(["bash", str(SCRIPTS / battery)], capture_output=True, text=True,
                       env=env, timeout=300)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
