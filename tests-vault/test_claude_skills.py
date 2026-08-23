"""Vault-side tests for Wave 3 — Claude-native skills (SKILL.md dirs), the
override-subsystem canonicalization, and the managed CLAUDE.md block.
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


mount = _load("kuraka_mount_w3", "kuraka-mount.py")


# --- sync_claude_skills -------------------------------------------------------

def test_claude_skills_render_double_copy_byte_identical(tmp_path):
    src = tmp_path / "skills"
    src.mkdir()
    body = "---\nname: a\ndescription: d\ndisable-model-invocation: true\n---\nbody\n"
    (src / "a.md").write_text(body, encoding="utf-8")
    sub = src / "evals"
    sub.mkdir()
    (sub / "x.md").write_text("aux\n", encoding="utf-8")

    dst = tmp_path / ".claude" / "skills"
    n = mount.sync_claude_skills(src, dst)
    assert n == 1
    assert (dst / "a" / "SKILL.md").read_text() == body      # registered form
    assert (dst / "a.md").read_text() == body                 # transition flat
    assert (dst / "evals" / "x.md").read_text() == "aux\n"    # subdirs preserved


def test_vault_skill_classification_applied():
    """Internal/core skills must not pollute the / menu or auto-invoke; the
    orchestrator utilities fork."""
    def fm_head(name: str) -> str:
        return (VAULT / "skills" / f"{name}.md").read_text(encoding="utf-8").split("\n---", 1)[0]
    for name in ("kuraka", "kuraka-policies", "implement-story", "verify-output"):
        head = fm_head(name)
        assert "disable-model-invocation: true" in head, name
        assert "user-invocable: false" in head, name
    for name in ("compact-context", "detect-patterns", "gap-analysis"):
        assert "context: fork" in fm_head(name), name
    for name in ("facilitate-discovery", "diagnose-deploy", "seed-project-conventions"):
        head = fm_head(name)
        assert "user-invocable: false" not in head, f"{name} must stay invocable"


def test_skill_claude_keys_stripped_for_non_claude(tmp_path):
    src = tmp_path / "s" / "k.md"
    src.parent.mkdir()
    src.write_text("---\nname: k\ndescription: d\ndisable-model-invocation: true\n"
                   "user-invocable: false\ncontext: fork\n---\nbody\n", encoding="utf-8")
    dst = tmp_path / "anti.md"
    mount.copy_file(src, dst, target_env="antigravity")
    head = dst.read_text().split("\n---", 1)[0]
    for key in ("disable-model-invocation", "user-invocable", "context:"):
        assert key not in head
    assert "name: k" in head


# --- override subsystem canonicalization -------------------------------------

def _mini_world(tmp_path):
    vault = tmp_path / "vault"
    (vault / "skills").mkdir(parents=True)
    (vault / "skills" / "a.md").write_text("---\nname: a\n---\nvault body\n")
    proj = tmp_path / "proj"
    skills = proj / ".claude" / "skills"
    (skills / "a").mkdir(parents=True)
    (skills / "a.md").write_text("---\nname: a\n---\nvault body\n")
    (skills / "a" / "SKILL.md").write_text("---\nname: a\n---\nvault body\n")
    return vault, proj, skills


def test_skill_md_dir_is_not_a_phantom_override(tmp_path):
    vault, proj, _ = _mini_world(tmp_path)
    assert kc.detect_overrides(proj, vault) == []


def test_edited_skill_md_is_detected_as_override(tmp_path):
    vault, proj, skills = _mini_world(tmp_path)
    (skills / "a" / "SKILL.md").write_text("---\nname: a\n---\nTUNED body\n")
    rels = [p.as_posix() for p in kc.detect_overrides(proj, vault)]
    assert rels == ["skills/a/SKILL.md"]


def test_restore_mirrors_skill_md_into_flat_copy(tmp_path):
    _, proj, skills = _mini_world(tmp_path)
    (skills / "a" / "SKILL.md").write_text("---\nname: a\n---\nTUNED body\n")
    fixed = kc._mirror_claude_skill_copies(skills)
    assert fixed == 1
    assert (skills / "a.md").read_text() == (skills / "a" / "SKILL.md").read_text()


# --- managed CLAUDE.md block --------------------------------------------------

def test_claude_md_block_created_appended_and_idempotent(tmp_path):
    target = tmp_path
    assert mount.ensure_claude_md_block(target) is True          # created
    text = (target / "CLAUDE.md").read_text()
    assert "@.claude/rules/19-evidence.md" in text
    assert mount.ensure_claude_md_block(target) is False         # idempotent

    (target / "CLAUDE.md").write_text("# My project\n\nuser content\n")
    assert mount.ensure_claude_md_block(target) is True          # appended
    text = (target / "CLAUDE.md").read_text()
    assert text.startswith("# My project") and "user content" in text
    assert text.count("kuraka:managed:begin") == 1

    # a stale managed block is rewritten in place, user content untouched
    stale = text.replace("@.claude/rules/19-evidence.md", "@old-import.md")
    (target / "CLAUDE.md").write_text(stale)
    assert mount.ensure_claude_md_block(target) is True
    text = (target / "CLAUDE.md").read_text()
    assert "@old-import.md" not in text and "user content" in text


def test_skill_colliding_with_a_command_is_not_registered(tmp_path):
    """A registered skill SHADOWS the same-named slash command. `kuraka` is a
    non-invocable skill AND the framework's entrypoint command, so mounting
    skills/kuraka/SKILL.md broke `/kuraka` ('this skill can only be invoked by
    Claude'). Only the flat copy may be mounted for colliding names."""
    src = tmp_path / "skills"
    src.mkdir()
    body = "---\nname: kuraka\ndescription: d\nuser-invocable: false\n---\nbody\n"
    (src / "kuraka.md").write_text(body, encoding="utf-8")

    dst = tmp_path / ".claude" / "skills"
    assert mount.sync_claude_skills(src, dst) == 1
    assert not (dst / "kuraka").exists()          # never registered
    assert (dst / "kuraka.md").read_text() == body  # still readable by path


def test_pre_existing_colliding_skill_dir_is_cleaned_up(tmp_path):
    """Projects mounted before the fix carry a stale skills/kuraka/SKILL.md;
    an update must remove it, not just stop writing it."""
    src = tmp_path / "skills"
    src.mkdir()
    (src / "kuraka.md").write_text("---\nname: kuraka\ndescription: d\n---\nb\n", encoding="utf-8")

    dst = tmp_path / ".claude" / "skills"
    (dst / "kuraka").mkdir(parents=True)
    (dst / "kuraka" / "SKILL.md").write_text("stale\n", encoding="utf-8")

    mount.sync_claude_skills(src, dst)
    assert not (dst / "kuraka" / "SKILL.md").exists()
    assert not (dst / "kuraka").exists()


def test_no_new_skill_command_collisions_in_the_vault():
    """Guard the inverse: adding a command that matches a skill name would
    silently drop that skill's registration."""
    skills = {p.stem for p in (VAULT / "skills").glob("*.md")}
    commands = {p.stem for p in (VAULT / "commands").glob("*.md")}
    assert skills & commands == {"kuraka"}, (
        f"unexpected skill/command name collision(s): {sorted(skills & commands)}")
