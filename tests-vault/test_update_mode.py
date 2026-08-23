"""End-to-end test of kuraka-mount.py --update: framework refreshed, project
implementation history untouched, non-interactive, early exit before any
registry/state side effects.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]

HISTORY_LL = "# Lessons learned\n\nLL-001: contenido ACUMULADO del proyecto.\n"
HISTORY_DASH = "# Dashboard\n\ndatos reales del proyecto\n"
HISTORY_REQ = "# REQ-20260801\n\nhistorial de implementación\n"
USER_CLAUDE_MD = "# Mi proyecto\n\ninstrucciones del usuario\n"


def _run_update(proj: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VAULT / "kuraka-mount.py"), str(proj), "--update", *extra],
        capture_output=True, text=True, stdin=subprocess.DEVNULL, timeout=300)


def test_update_mode_refreshes_framework_without_touching_history(tmp_path):
    proj = tmp_path / "consumer"
    (proj / "docs" / "process" / "agent-telemetry").mkdir(parents=True)
    (proj / ".claude" / "agents").mkdir(parents=True)   # already mounted for claude
    (proj / "docs" / "process" / "lessons-learned.md").write_text(HISTORY_LL)
    (proj / "docs" / "process" / "agent-telemetry" / "DASHBOARD.md").write_text(HISTORY_DASH)
    (proj / "docs" / "process" / "REQ-20260801.md").write_text(HISTORY_REQ)
    (proj / "CLAUDE.md").write_text(USER_CLAUDE_MD)
    (proj / "kuraka.config.yaml").write_text(
        "architecture:\n  paths:\n    docs_process_root: docs/process\n")

    r = _run_update(proj)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "plataforma detectada: claude" in r.stdout
    assert "ACTUALIZADO" in r.stdout and "historial intacto" in r.stdout

    # --- history is byte-identical ---
    assert (proj / "docs/process/lessons-learned.md").read_text() == HISTORY_LL
    assert (proj / "docs/process/agent-telemetry/DASHBOARD.md").read_text() == HISTORY_DASH
    assert (proj / "docs/process/REQ-20260801.md").read_text() == HISTORY_REQ
    # config never regenerated; project layer never seeded
    assert "docs_process_root" in (proj / "kuraka.config.yaml").read_text()
    assert not (proj / ".claude" / "project").exists()

    # --- framework essentials landed ---
    cr = (proj / ".claude/agents/code-reviewer.md").read_text()
    assert "disallowedTools: Write, Edit, NotebookEdit" in cr      # harness caps
    assert (proj / ".claude/skills/plan-tests/SKILL.md").is_file() # SKILL.md dirs
    assert not (proj / ".claude/skills/kuraka").exists()           # would shadow /kuraka
    assert (proj / ".claude/skills/kuraka.md").is_file()           # transition flat
    assert (proj / ".claude/hooks/gate_integrity.py").is_file()    # hook pack
    settings = json.loads((proj / ".claude/settings.json").read_text())
    assert settings.get("hooks", {}).get("PostToolUse")            # wired
    assert (proj / ".claude/rules/19-evidence.md").is_file()
    assert (proj / "tests/kuraka/test_structure.py").is_file()     # eval harness

    # managed CLAUDE.md block appended, user content preserved
    cm = (proj / "CLAUDE.md").read_text()
    assert cm.startswith("# Mi proyecto") and "instrucciones del usuario" in cm
    assert "@.claude/rules/19-evidence.md" in cm

    # early exit: no registry side effects for this throwaway project
    assert not (VAULT / "projects" / "consumer").exists()


# --- platform awareness -------------------------------------------------------

def test_update_detects_antigravity_and_never_leaks_claude_material(tmp_path):
    proj = tmp_path / "anti-consumer"
    (proj / ".agents" / "agents").mkdir(parents=True)   # mounted for antigravity only
    (proj / "kuraka.config.yaml").write_text("architecture: {}\n")

    r = _run_update(proj)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "plataforma detectada: antigravity" in r.stdout
    # its own render landed…
    anti_cr = proj / ".agents" / "agents" / "code-reviewer.md"
    assert anti_cr.is_file()
    head = anti_cr.read_text(encoding="utf-8").split("\n---", 2)[1]
    assert "disallowedTools" not in head and "maxTurns" not in head  # stripped
    assert (proj / ".agents" / "skills" / "kuraka" / "SKILL.md").is_file()
    # …and NOTHING Claude-only was created (the antigravity mount legitimately
    # mirrors neutral stack-profiles/templates into .claude/ for path compat —
    # what must NOT appear is Claude-only material)
    for leak in ("agents", "skills", "hooks", "commands", "settings.json"):
        assert not (proj / ".claude" / leak).exists(), leak
    assert not (proj / ".agents" / "hooks").exists()
    assert not (VAULT / "projects" / "anti-consumer").exists()


def test_update_refuses_unmounted_platform_and_empty_projects(tmp_path):
    proj = tmp_path / "claude-only"
    (proj / ".claude" / "agents").mkdir(parents=True)
    r = _run_update(proj, "--target", "codex")          # codex NOT mounted here
    assert r.returncode != 0
    assert "NO está montado para 'codex'" in (r.stdout + r.stderr)
    assert not (proj / ".codex").exists()

    bare = tmp_path / "bare"
    bare.mkdir()
    r = _run_update(bare)                               # nothing mounted at all
    assert r.returncode != 0
    assert "ninguna plataforma" in (r.stdout + r.stderr)


def test_update_multi_platform_fans_out_per_render(tmp_path):
    proj = tmp_path / "dual"
    (proj / ".claude" / "agents").mkdir(parents=True)
    (proj / ".agents" / "agents").mkdir(parents=True)
    (proj / "kuraka.config.yaml").write_text("architecture: {}\n")

    r = _run_update(proj)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "plataformas montadas detectadas: claude, antigravity" in r.stdout
    # each platform got ITS render
    claude_cr = (proj / ".claude/agents/code-reviewer.md").read_text(encoding="utf-8")
    assert "disallowedTools: Write, Edit, NotebookEdit" in claude_cr
    anti_head = (proj / ".agents/agents/code-reviewer.md").read_text(
        encoding="utf-8").split("\n---", 2)[1]
    assert "disallowedTools" not in anti_head
    assert (proj / ".claude/hooks/gate_integrity.py").is_file()
    assert not (proj / ".agents/hooks").exists()
