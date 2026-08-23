"""Structural tests for the Kuraka agent system.

These tests validate the static contract between agents, skills and the
workflow orchestrator. They do NOT invoke agents — see `README.md`.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from conftest import VALID_MODELS, parse_frontmatter


# ---------------------------------------------------------------------------
# Agents
# ---------------------------------------------------------------------------


def test_should_find_at_least_10_agents_when_listing(agents_dir: Path) -> None:
    agent_files = list(agents_dir.glob("*.md"))
    assert len(agent_files) >= 10, f"expected ≥10 agent files, got {len(agent_files)}"


@pytest.mark.parametrize("fname", ["po-analyst.md", "story-refiner.md", "architect-reviewer.md",
                                    "backend-developer.md", "frontend-developer.md", "code-reviewer.md",
                                    "security-reviewer.md", "test-engineer.md", "e2e-tester.md",
                                    "deployment-verifier.md", "final-auditor.md", "migration-reviewer.md",
                                    "pattern-detector.md"])
def test_should_have_valid_frontmatter_when_agent_file_exists(agents_dir: Path, fname: str) -> None:
    path = agents_dir / fname
    assert path.exists(), f"missing agent file: {fname}"

    fm = parse_frontmatter(path.read_text(encoding="utf-8"))
    assert fm.get("name"), f"{fname}: missing 'name' in frontmatter"
    assert fm["name"] == fname.replace(".md", ""), f"{fname}: name mismatch (frontmatter='{fm['name']}')"
    assert fm.get("description"), f"{fname}: missing 'description'"
    assert fm.get("model") in VALID_MODELS, (
        f"{fname}: invalid model '{fm.get('model')}' (expected one of {VALID_MODELS})"
    )


def test_should_have_fable_for_judgment_agents(agents_dir: Path) -> None:
    """Agentes de juicio complejo deben usar el tier frontier (Fable)."""
    judgment_agents = ["architect-reviewer", "security-reviewer", "final-auditor", "po-analyst"]
    for name in judgment_agents:
        fm = parse_frontmatter((agents_dir / f"{name}.md").read_text(encoding="utf-8"))
        assert fm.get("model") == "fable", f"{name} should use 'fable' for judgment work, got '{fm.get('model')}'"


def test_should_have_haiku_for_mechanical_agents(agents_dir: Path) -> None:
    """Agentes de checks mecánicos deben usar Haiku (coste 5× menor)."""
    mechanical_agents = ["deployment-verifier", "pattern-detector", "migration-reviewer", "e2e-tester"]
    for name in mechanical_agents:
        fm = parse_frontmatter((agents_dir / f"{name}.md").read_text(encoding="utf-8"))
        assert fm.get("model") == "haiku", f"{name} should use 'haiku' for mechanical work, got '{fm.get('model')}'"


# ---------------------------------------------------------------------------
# Kuraka skill self-consistency
# ---------------------------------------------------------------------------


def test_should_have_kuraka_skill_split_into_three_files(skills_dir: Path) -> None:
    for name in ("kuraka.md", "kuraka-modes.md", "kuraka-policies.md"):
        assert (skills_dir / name).exists(), f"missing skill file: {name}"


def test_should_not_leave_old_workflow_skill_file(skills_dir: Path) -> None:
    assert not (skills_dir / "workflow.md").exists(), "old workflow.md should have been removed"


def test_should_reference_every_agent_in_kuraka_phase_map(kuraka_md: str) -> None:
    expected_agents = [
        "po-analyst", "story-refiner", "architect-reviewer",
        "backend-developer", "frontend-developer", "code-reviewer",
        "security-reviewer", "test-engineer", "e2e-tester",
        "deployment-verifier", "final-auditor", "migration-reviewer",
    ]
    for agent in expected_agents:
        assert f"`{agent}`" in kuraka_md, f"kuraka.md missing reference to `{agent}`"


# ---------------------------------------------------------------------------
# Output schemas coverage
# ---------------------------------------------------------------------------


def test_should_have_output_schema_for_every_phase_producing_output(output_schemas_path: Path) -> None:
    schemas = output_schemas_path.read_text(encoding="utf-8")
    expected_sections = [
        "po-analyst",
        "story-refiner",
        "test-engineer",
        "architect-reviewer",
        "backend-developer",
        "code-reviewer",
        "final-auditor",
    ]
    for section in expected_sections:
        assert f"## {section}" in schemas, f"output-schemas.md missing section for `{section}`"


# ---------------------------------------------------------------------------
# Claude-native registration (skills as SKILL.md dirs + harness capabilities)
# ---------------------------------------------------------------------------


def _command_stems(claude_dir: Path) -> set[str]:
    cmds = claude_dir / "commands"
    return {p.stem for p in cmds.glob("*.md")} if cmds.is_dir() else set()


def test_should_register_every_skill_as_skill_md_dir(skills_dir: Path,
                                                     claude_dir: Path) -> None:
    """Claude Code only registers skills/<n>/SKILL.md dirs; the flat .md files
    are a transition compat copy. Every flat skill must have its dir form —
    EXCEPT a skill whose name collides with a slash command (a registered skill
    shadows the command), which is mounted flat-only by design."""
    colliding = _command_stems(claude_dir)
    missing = [p.stem for p in skills_dir.glob("*.md")
               if p.stem not in colliding
               and not (skills_dir / p.stem / "SKILL.md").exists()]
    assert not missing, f"skills without SKILL.md dir form: {missing}"


def test_should_not_register_a_skill_that_shadows_a_command(skills_dir: Path,
                                                            claude_dir: Path) -> None:
    """The inverse guard: a skill sharing a command's name must NOT be mounted
    as a registered dir — that shadowing broke `/kuraka` ("this skill can only
    be invoked by Claude") until the mount started skipping it."""
    for stem in _command_stems(claude_dir):
        if (skills_dir / f"{stem}.md").exists():
            assert not (skills_dir / stem / "SKILL.md").exists(), (
                f"skills/{stem}/SKILL.md shadows the /{stem} command — "
                f"the mount must ship only the flat copy for colliding names")


def test_should_not_collide_kuraka_core_with_slash_commands(skills_dir: Path,
                                                            claude_dir: Path) -> None:
    """The /kuraka entry point is the COMMAND; the core skills must not also
    register slash commands or auto-invoke. (`kuraka` itself is flat-only — see
    the shadowing guard above — so only its companions are checked here.)"""
    colliding = _command_stems(claude_dir)
    for name in ("kuraka", "kuraka-modes", "kuraka-policies"):
        if name in colliding:
            continue
        p = skills_dir / name / "SKILL.md"
        if not p.exists():
            pytest.skip("pre-Wave-3 mount")
        fm = parse_frontmatter(p.read_text(encoding="utf-8"))
        assert str(fm.get("user-invocable")).lower() == "false", name
        assert str(fm.get("disable-model-invocation")).lower() == "true", name


def test_should_deny_write_tools_to_pure_reviewers(agents_dir: Path) -> None:
    """Role isolation by harness: pure reviewer agents carry the Write/Edit
    denial in frontmatter (governed by the vault's AGENT-HARNESS.yaml)."""
    for name in ("code-reviewer", "security-reviewer", "migration-reviewer"):
        fm = parse_frontmatter((agents_dir / f"{name}.md").read_text(encoding="utf-8"))
        denied = fm.get("disallowedTools", "")
        assert "Write" in denied and "Edit" in denied, (
            f"{name}: expected Write/Edit in disallowedTools, got '{denied}'")


# ---------------------------------------------------------------------------
# No orphan references
# ---------------------------------------------------------------------------


def test_should_not_reference_old_workflow_skill_in_agents(agents_dir: Path) -> None:
    offenders: list[str] = []
    for md in agents_dir.glob("*.md"):
        content = md.read_text(encoding="utf-8")
        if "skills/workflow.md" in content:
            offenders.append(md.name)
    assert not offenders, f"agents still reference skills/workflow.md: {offenders}"


def test_should_not_reference_old_workflow_skill_in_skills(skills_dir: Path) -> None:
    offenders: list[str] = []
    for md in skills_dir.glob("*.md"):
        if md.name.startswith("kuraka"):
            continue  # kuraka files may have historical notes
        content = md.read_text(encoding="utf-8")
        if "skills/workflow.md" in content or "`workflow`" in content:
            offenders.append(md.name)
    assert not offenders, f"skills still reference old 'workflow' name: {offenders}"
