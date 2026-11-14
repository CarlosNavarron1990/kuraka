"""Claude account plans (MODEL-ROUTING.yaml claude_plans) — vault-only tests.

A non-max plan rewrites ONLY the agent `model:` line at mount time, inside
render_for_platform (the function the mount manifest hashes). These tests pin:
max is the identity render, pro/team downgrade per tier, skills are untouched,
the manifest records the plan, and detect_overrides neither flags the plan
render as a tuning nor hides a real tuning made on top of it.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pytest

VAULT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VAULT))
import kuraka_common as kc  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_plan():
    prev = kc._CLAUDE_PLAN
    yield
    kc._CLAUDE_PLAN = prev


def _agent(name: str) -> str:
    return (VAULT / "agents" / f"{name}.md").read_text(encoding="utf-8")


def test_max_plan_equals_vault_frontmatter_column():
    r = kc.load_model_routing(VAULT)
    assert r["claude_plans"]["max"] == r["platforms"]["claude"]
    for plan in kc.CLAUDE_PLANS:
        assert set(r["claude_plans"][plan]) == set(r["tiers"]), plan


def test_max_render_is_byte_identical():
    kc.set_claude_plan("max")
    for p in (VAULT / "agents").glob("*.md"):
        text = p.read_text(encoding="utf-8")
        assert kc.render_for_platform(text, "claude", VAULT) == text, p.name


@pytest.mark.parametrize("plan", ["pro", "team"])
def test_cheap_plans_route_by_tier(plan):
    kc.set_claude_plan(plan)
    r = kc.load_model_routing(VAULT)
    col = r["claude_plans"][plan]
    for name, tier in r["agents"].items():
        out = kc.render_for_platform(_agent(name), "claude", VAULT)
        fm, _ = kc.split_frontmatter(out)
        assert fm["model"] == col[tier], name
        # only the model line changes
        assert [l for l in out.splitlines() if not l.startswith("model:")] == \
               [l for l in _agent(name).splitlines() if not l.startswith("model:")]
    assert col["frontier"] in ("sonnet", "haiku") and col["fast"] == "haiku"


def test_skills_are_not_rewritten_on_cheap_plans():
    kc.set_claude_plan("pro")
    text = (VAULT / "skills" / "kuraka-ahorro.md").read_text(encoding="utf-8")
    assert kc.render_for_platform(text, "claude", VAULT) == text


def test_plan_aliases():
    assert kc.normalize_claude_plan("Pro Max") == "max"
    assert kc.normalize_claude_plan("teams") == "team"
    assert kc.normalize_claude_plan("20") == "pro"
    assert kc.normalize_claude_plan("enterprise") is None


def test_pro_mount_is_not_an_override_but_a_tuning_is(tmp_path):
    proj = tmp_path / "proj"
    agents = proj / ".claude" / "agents"
    agents.mkdir(parents=True)
    kc.set_claude_plan("pro")
    for p in (VAULT / "agents").glob("*.md"):
        (agents / p.name).write_text(
            kc.render_for_platform(p.read_text(encoding="utf-8"), "claude", VAULT),
            encoding="utf-8")
    kc.write_mount_manifest(proj, VAULT, ("agents",), platform=".claude")
    assert kc.manifest_claude_plan(proj) == "pro"
    kc.set_claude_plan("max")  # a different process-wide plan must not matter
    assert kc.detect_overrides(proj, VAULT, "claude") == []
    tuned = agents / "backend-developer.md"
    tuned.write_text(tuned.read_text(encoding="utf-8") + "\nProject tuning line.\n",
                     encoding="utf-8")
    assert [p.as_posix() for p in kc.detect_overrides(proj, VAULT, "claude")] == \
           ["agents/backend-developer.md"]
    shutil.rmtree(proj)
