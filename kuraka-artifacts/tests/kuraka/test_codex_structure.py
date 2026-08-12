"""Structural contract for a project mounted with ``--target codex``."""

from __future__ import annotations

from pathlib import Path

import pytest


CODEX_COMMAND_SKILLS = {
    "amauta",
    "arki",
    "checkmarx-remediation",
    "inti",
    "kuraka",
    "kuraka-backup",
    "kuraka-update",
    "kuraka-wizard",
}
COMMAND_MARKER = "<!-- kuraka-codex-command-skill -->"


def _codex_dir(repo_root: Path) -> Path:
    path = repo_root / ".codex"
    if not path.is_dir():
        pytest.skip("Codex structural checks apply only to a Codex mount")
    return path


def _native_agents(codex_dir: Path) -> list[Path]:
    agents = sorted((codex_dir / "agents").glob("*.toml"))
    assert agents, "Codex mount has no native .codex/agents/*.toml definitions"
    return agents


def test_codex_agents_are_native_and_complete(repo_root: Path) -> None:
    codex_dir = _codex_dir(repo_root)
    agents = _native_agents(codex_dir)

    for agent in agents:
        content = agent.read_text(encoding="utf-8")
        assert "name = " in content, f"{agent.name}: missing TOML name"
        assert "description = " in content, f"{agent.name}: missing TOML description"
        assert "model = " not in content, (
            f"{agent.name}: Codex agents must inherit the active session model"
        )
        assert "developer_instructions = '''" in content, f"{agent.name}: missing developer instructions"
        assert "model_reasoning_effort = " in content, f"{agent.name}: missing reasoning effort"
        assert "sandbox_mode = " in content, f"{agent.name}: missing sandbox mode"
        assert ".claude/" not in content, f"{agent.name}: contains a Claude-only path"


def test_codex_does_not_duplicate_agents_as_skills(repo_root: Path) -> None:
    codex_dir = _codex_dir(repo_root)
    skill_root = codex_dir / "skills"
    for agent in _native_agents(codex_dir):
        duplicate = skill_root / agent.stem / "SKILL.md"
        if duplicate.exists():
            content = duplicate.read_text(encoding="utf-8")
            assert COMMAND_MARKER in content, (
                f"{agent.stem} is duplicated as a role skill instead of an "
                "intentional command entrypoint"
            )


def test_codex_commands_are_discoverable_skills(repo_root: Path) -> None:
    codex_dir = _codex_dir(repo_root)
    for name in CODEX_COMMAND_SKILLS:
        path = codex_dir / "skills" / name / "SKILL.md"
        assert path.is_file(), f"Codex command skill is missing: {name}"
        content = path.read_text(encoding="utf-8")
        assert f"name: {name}" in content
        assert "description:" in content
        assert ".claude/" not in content
        assert "$ARGUMENTS" not in content
        assert "/prompts:" not in content

    for name in ("amauta", "arki", "inti"):
        content = (codex_dir / "skills" / name / "SKILL.md").read_text(encoding="utf-8")
        assert "Task tool" not in content
        assert "restart Claude Code" not in content
        assert "reinicie Claude Code" not in content

    wizard = (codex_dir / "skills" / "kuraka-wizard" / "SKILL.md").read_text(encoding="utf-8")
    assert "~/.codex/prompts" not in wizard
    assert "| Codex | `AGENTS.md`, `.codex/agents/`, `.codex/skills/`" in wizard

    backup = (codex_dir / "skills" / "kuraka-backup" / "SKILL.md").read_text(encoding="utf-8")
    assert "--layer-root .codex/project --skip-overrides" in backup


def test_codex_mount_leaves_no_generated_legacy_prompts(repo_root: Path) -> None:
    codex_dir = _codex_dir(repo_root)
    for legacy_dir in (codex_dir / "prompts", codex_dir / "commands"):
        for path in legacy_dir.glob("*.md"):
            content = path.read_text(encoding="utf-8")
            assert "Kuraka — entorno Codex." not in content
            assert "Kuraka — entorno codex." not in content


def test_codex_orchestrator_requires_native_delegation(repo_root: Path) -> None:
    _codex_dir(repo_root)
    agents_md = (repo_root / "AGENTS.md").read_text(encoding="utf-8")
    normalized = " ".join(agents_md.split())
    assert "delegate each phase to the native Codex agent" in normalized
    assert "wait for its handoff" in normalized.lower()
    assert "$kuraka <requirement>" in agents_md


def test_codex_agent_config_sets_only_the_safe_concurrency_default(repo_root: Path) -> None:
    codex_dir = _codex_dir(repo_root)
    config = (codex_dir / "config.toml").read_text(encoding="utf-8")
    assert "[agents]" in config
    assert "max_concurrent_threads_per_session = 4" in config


def test_codex_orchestrator_skill_overrides_claude_usage_assumptions(repo_root: Path) -> None:
    codex_dir = _codex_dir(repo_root)
    kuraka_skill = (codex_dir / "skills" / "kuraka" / "SKILL.md").read_text(encoding="utf-8")
    assert "## Codex Platform Override" in kuraka_skill
    assert "never fabricate `0`" in kuraka_skill

    final_auditor = (codex_dir / "agents" / "final-auditor.toml").read_text(encoding="utf-8")
    assert "--layer-root .codex/project --skip-overrides" in final_auditor
    assert "$kuraka-backup.py" not in final_auditor
