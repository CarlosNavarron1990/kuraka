"""Fixtures compartidos para la suite de evaluación del Kuraka."""

from __future__ import annotations

from pathlib import Path

import pytest


VALID_MODELS = {"fable", "opus", "sonnet", "haiku"}


@pytest.fixture(scope="session")
def repo_root() -> Path:
    """Raíz del proyecto sie_v2."""
    return Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def claude_dir(repo_root: Path) -> Path:
    path = repo_root / ".claude"
    if not path.is_dir():
        pytest.skip("Claude structural checks apply only to a Claude mount")
    return path


@pytest.fixture(scope="session")
def agents_dir(claude_dir: Path) -> Path:
    return claude_dir / "agents"


@pytest.fixture(scope="session")
def skills_dir(claude_dir: Path) -> Path:
    return claude_dir / "skills"


@pytest.fixture(scope="session")
def output_schemas_path(agents_dir: Path) -> Path:
    return agents_dir / "contexts" / "output-schemas.md"


@pytest.fixture(scope="session")
def kuraka_md(skills_dir: Path) -> str:
    return (skills_dir / "kuraka.md").read_text(encoding="utf-8")


def parse_frontmatter(text: str) -> dict[str, str]:
    """Parse YAML frontmatter of a markdown file into a flat dict.

    Minimal parser — handles `key: value` pairs only. Sufficient for Kuraka
    agent/skill frontmatter which is always flat.
    """
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    block: list[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        block.append(line)

    result: dict[str, str] = {}
    for raw in block:
        if ":" not in raw:
            continue
        key, _, value = raw.partition(":")
        result[key.strip()] = value.strip().strip('"').strip("'")
    return result
