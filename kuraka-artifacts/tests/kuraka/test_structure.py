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
