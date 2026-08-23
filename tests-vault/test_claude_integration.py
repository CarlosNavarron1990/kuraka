"""Vault-side regression tests for the Claude Code integration (Wave 1).

Guards the multi-platform coexistence contract:
  - the vault frontmatter is the CLAUDE-NATIVE SUPERSET;
  - the claude render is byte-identical to the vault (override subsystem);
  - non-Claude renders (antigravity / cursor / codex) SUBTRACT the
    Claude-only harness keys and keep their own path projections intact;
  - AGENT-HARNESS.yaml <-> agents/*.md stay a drift-free bijection.

Run from the vault root:  python3 -m pytest tests-vault/ -v
(These tests are vault-only: the directory is NOT mounted into consumers.)
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VAULT))

import kuraka_common as kc  # noqa: E402


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, VAULT / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mount = _load("kuraka_mount", "kuraka-mount.py")
harness = _load("kuraka_apply_harness", "kuraka-apply-harness.py")

SAMPLE = (
    "---\n"
    "name: sample-agent\n"
    'description: "A sample."\n'
    "model: opus\n"
    "tools: Read, Grep\n"
    "disallowedTools: Write, Edit\n"
    "maxTurns: 80\n"
    "skills: [implement-story, write-tests]\n"
    "memory: project\n"
    "color: red\n"
    "---\n"
    "\n"
    "Body keeps `maxTurns` mentions and reads `.claude/skills/kuraka.md`.\n"
)


# --- strip_claude_frontmatter -------------------------------------------------

def test_strip_removes_only_claude_keys():
    out = kc.strip_claude_frontmatter(SAMPLE)
    head = out.split("\n---\n")[0]
    for gone in ("tools:", "disallowedTools:", "maxTurns:", "skills:", "memory:"):
        assert gone not in head, f"{gone} leaked into a non-Claude render"
    for kept in ("name: sample-agent", "model: opus", "color: red", "description:"):
        assert kept in head


def test_strip_preserves_body_untouched():
    out = kc.strip_claude_frontmatter(SAMPLE)
    assert out.endswith("Body keeps `maxTurns` mentions and reads `.claude/skills/kuraka.md`.\n")


def test_strip_is_noop_without_claude_keys():
    plain = "---\nname: x\ndescription: d\nmodel: haiku\n---\nbody\n"
    assert kc.strip_claude_frontmatter(plain) == plain
    assert kc.strip_claude_frontmatter("no frontmatter at all\n") == "no frontmatter at all\n"


# --- copy_file per-platform renders ------------------------------------------

def _roundtrip(tmp_path: Path, target_env: str) -> str:
    src = tmp_path / "src" / "agent.md"
    src.parent.mkdir()
    src.write_text(SAMPLE, encoding="utf-8")
    dst = tmp_path / target_env / "agent.md"
    mount.copy_file(src, dst, target_env=target_env)
    return dst.read_text(encoding="utf-8")


def test_claude_render_is_verbatim(tmp_path):
    assert _roundtrip(tmp_path, "claude") == SAMPLE


def test_antigravity_render_strips_and_projects_paths(tmp_path):
    out = _roundtrip(tmp_path, "antigravity")
    assert "maxTurns:" not in out.split("\n---\n")[0]
    assert ".agents/skills/" in out and ".claude/skills/" not in out


def test_cursor_render_strips_without_path_projection(tmp_path):
    out = _roundtrip(tmp_path, "cursor")
    assert "maxTurns:" not in out.split("\n---\n")[0]
    assert ".claude/skills/" in out  # cursor keeps Claude-style paths today


def test_codex_render_strips_and_projects_paths(tmp_path):
    out = _roundtrip(tmp_path, "codex")
    assert "maxTurns:" not in out.split("\n---\n")[0]
    assert ".codex/skills/kuraka/SKILL.md" in out


# --- AGENT-HARNESS.yaml governance -------------------------------------------

def test_harness_map_is_valid_bijection():
    h = harness.load_harness()
    files = harness.agent_files()
    assert harness.validate(h, files) == []


def test_agents_match_harness_map_no_drift():
    h = harness.load_harness()
    for stem, path in harness.agent_files().items():
        text = path.read_text(encoding="utf-8")
        rendered = harness.render(text, harness.resolve(h, stem), h["emit"])
        assert rendered == text, f"agents/{stem}.md drifts from AGENT-HARNESS.yaml — run kuraka-apply-harness.py"


def test_vault_agents_leak_nothing_to_non_claude():
    keys = ("tools:", "disallowedTools:", "maxTurns:", "skills:", "memory:")
    for path in (VAULT / "agents").glob("*.md"):
        stripped = kc.strip_claude_frontmatter(path.read_text(encoding="utf-8"))
        head = stripped.split("\n---\n")[0]
        for line in head.splitlines():
            # a managed KEY starts the line; substrings inside description
            # prose (e.g. "Uses skills: ...") are fine
            assert not line.startswith(keys), \
                f"{path.name}: '{line.strip()}' would leak to a non-Claude render"


def test_reviewers_are_write_denied():
    for stem in ("code-reviewer", "security-reviewer", "migration-reviewer",
                 "migration-deployability"):
        text = (VAULT / "agents" / f"{stem}.md").read_text(encoding="utf-8")
        head = text.split("\n---\n")[0]
        assert "disallowedTools: Write, Edit, NotebookEdit" in head, stem
