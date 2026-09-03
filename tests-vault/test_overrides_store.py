"""Vault-side regression tests for the override subsystem.

Guards the two defects found auditing the central store on 2026-08-29:

  1. The mount manifest recorded the RAW VAULT hash while a non-Claude mount
     writes a RENDER of it. Every mounted file on Antigravity/Cursor/Codex then
     read as a project override (petsuite 104, camisassis 153, codex 52), the
     whole suite was snapshotted and re-applied on each mount, and the project
     froze on an old framework version. The manifest now stores the hash of the
     file AS MOUNTED (kuraka_common.render_for_platform — the very function
     kuraka-mount.copy_file uses).

  2. The store was a single flat overrides/ dir for a project that may be
     mounted for several platforms at once, so the last snapshot won and a
     restore could paste one platform's render into another platform's mount.
     It is now scoped per platform (overrides/<platform>/…), with a migration
     for the legacy flat layout.

Run from the vault root:  python3 -m pytest tests-vault/ -v
"""
from __future__ import annotations

import hashlib
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


mount = _load("kuraka_mount_ov", "kuraka-mount.py")

# a real vault agent that carries Claude-only harness keys AND .claude/ paths
SOURCE = VAULT / "agents" / "code-reviewer.md"


def _mount_agent(project: Path, target_env: str, name: str = "code-reviewer.md") -> Path:
    """Mount one agent exactly as kuraka-mount would for `target_env`."""
    dst = project / kc.platform_dirname(target_env) / "agents" / name
    mount.copy_file(SOURCE, dst, target_env=target_env)
    return dst


# --- 1. the manifest baseline is what the mount actually wrote ----------------

def test_render_for_platform_reproduces_the_mount_byte_for_byte(tmp_path):
    for target in ("claude", "antigravity", "cursor", "codex"):
        dst = _mount_agent(tmp_path / target, target)
        expected = kc.render_for_platform(
            SOURCE.read_text(encoding="utf-8", errors="ignore"), target, VAULT)
        assert dst.read_bytes() == expected.encode("utf-8"), target


def test_manifest_records_the_rendered_hash_not_the_vault_hash(tmp_path):
    kc.write_mount_manifest(tmp_path, VAULT, ("agents",), platform="agents")
    manifest = kc.load_mount_manifest(tmp_path, "agents")
    key = "agents/code-reviewer.md"
    vault_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    rendered = kc.render_for_platform(
        SOURCE.read_text(encoding="utf-8", errors="ignore"), "agents", VAULT)
    assert manifest[key] == hashlib.sha256(rendered.encode("utf-8")).hexdigest()
    assert manifest[key] != vault_hash  # the whole point


def test_claude_manifest_stays_the_vault_hash(tmp_path):
    kc.write_mount_manifest(tmp_path, VAULT, ("agents",), platform="claude")
    manifest = kc.load_mount_manifest(tmp_path, "claude")
    assert manifest["agents/code-reviewer.md"] == hashlib.sha256(
        SOURCE.read_bytes()).hexdigest()


# --- 2. a fresh non-Claude mount is NOT an override ---------------------------

def test_fresh_antigravity_mount_reports_no_overrides(tmp_path):
    for p in sorted((VAULT / "agents").glob("*.md")):
        mount.copy_file(p, tmp_path / ".agents" / "agents" / p.name,
                        target_env="antigravity")
    kc.write_mount_manifest(tmp_path, VAULT, ("agents",), platform="agents")
    assert kc.detect_overrides(tmp_path, VAULT, platform="agents") == []


def test_fresh_antigravity_mount_needs_no_manifest_either(tmp_path):
    """Even a legacy mount with no manifest: the render of the current vault is
    recognised, so nothing is mistaken for tuning."""
    _mount_agent(tmp_path, "antigravity")
    assert kc.detect_overrides(tmp_path, VAULT, platform="agents") == []


def test_real_tuning_is_still_detected_on_non_claude(tmp_path):
    dst = _mount_agent(tmp_path, "antigravity")
    kc.write_mount_manifest(tmp_path, VAULT, ("agents",), platform="agents")
    with open(dst, "a", encoding="utf-8") as fh:
        fh.write("\n<!-- tuning propio del proyecto -->\n")
    assert kc.detect_overrides(tmp_path, VAULT, platform="agents") == [
        Path("agents/code-reviewer.md")]


def test_custom_agent_without_vault_baseline_is_an_override(tmp_path):
    d = tmp_path / ".agents" / "agents"
    d.mkdir(parents=True)
    (d / "agente-propio.md").write_text("---\nname: agente-propio\n---\n", encoding="utf-8")
    assert kc.detect_overrides(tmp_path, VAULT, platform="agents") == [
        Path("agents/agente-propio.md")]


def test_codex_skill_projection_is_the_baseline(tmp_path):
    """Codex does NOT copy root skills — it rebuilds them as native SKILL.md
    (sync_codex_skills). The manifest baseline must be that projection, or all
    37 mounted skills read as overrides."""
    src = VAULT / "skills" / "kuraka-policies.md"
    dst = tmp_path / ".codex" / "skills" / "kuraka-policies" / "SKILL.md"
    dst.parent.mkdir(parents=True)
    mount.sync_codex_skills(VAULT / "skills", tmp_path / ".codex" / "skills")
    kc.write_mount_manifest(tmp_path, VAULT, ("skills",), platform="codex")
    manifest = kc.load_mount_manifest(tmp_path, "codex")
    assert manifest["skills/kuraka-policies.md"] == hashlib.sha256(
        dst.read_bytes()).hexdigest()
    assert kc.detect_overrides(tmp_path, VAULT, platform="codex") == []
    assert src.is_file()  # the vault side of the projection still exists


def test_codex_command_published_as_skill_is_not_an_override(tmp_path):
    """kuraka-export publishes each vault COMMAND as .codex/skills/<n>/SKILL.md.
    It has no `skills/` baseline, so without the marker rule it read as custom."""
    name = sorted(p.stem for p in (VAULT / "commands").glob("*.md"))[0]
    d = tmp_path / ".codex" / "skills" / name
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        f"---\nname: {name}\n---\n\n"
        f"{kc.CODEX_COMMAND_MARKER.decode()}\n# Kuraka command: {name}\n",
        encoding="utf-8")
    assert kc.detect_overrides(tmp_path, VAULT, platform="codex") == []


def test_codex_entrypoint_block_is_not_an_override(tmp_path):
    """The '## Codex explicit invocation' block the export appends on top of the
    skill projection is a mount artifact, not a project edit."""
    mount.sync_codex_skills(VAULT / "skills", tmp_path / ".codex" / "skills")
    target = tmp_path / ".codex" / "skills" / "kuraka" / "SKILL.md"
    with open(target, "a", encoding="utf-8") as fh:
        fh.write("\n<!-- kuraka-codex-entrypoint:start -->\n## Codex explicit "
                 "invocation\n\nSelect `kuraka` from `/skills`.\n"
                 "<!-- kuraka-codex-entrypoint:end -->\n")
    assert kc.detect_overrides(tmp_path, VAULT, platform="codex") == []
    # a real edit on top of it is still caught
    with open(target, "a", encoding="utf-8") as fh:
        fh.write("\nTUNING\n")
    assert Path("skills/kuraka/SKILL.md") in kc.detect_overrides(
        tmp_path, VAULT, platform="codex")


def test_directory_only_vault_skill_is_not_a_phantom_override(tmp_path):
    """A vault skill that exists ONLY as skills/<n>/SKILL.md (sentry-triage)
    used to be canonicalized to the non-existent flat skills/<n>.md and read as
    a custom file in every project."""
    dir_skills = [d.name for d in (VAULT / "skills").iterdir()
                  if d.is_dir() and (d / "SKILL.md").is_file()
                  and not (VAULT / "skills" / f"{d.name}.md").is_file()]
    assert dir_skills, "el vault ya no tiene skills sólo-directorio"
    name = dir_skills[0]
    dst = tmp_path / ".claude" / "skills" / name / "SKILL.md"
    dst.parent.mkdir(parents=True)
    mount.copy_file(VAULT / "skills" / name / "SKILL.md", dst, target_env="claude")
    assert kc.detect_overrides(tmp_path, VAULT, platform="claude") == []


# --- 3. the store is scoped per platform --------------------------------------

def test_snapshot_and_restore_are_platform_scoped(tmp_path):
    vault_store = tmp_path / "vault-store"
    (vault_store / "projects").mkdir(parents=True)
    project = tmp_path / "proj"

    # the same agent, tuned differently in each platform's mount
    claude_file = _mount_agent(project, "claude")
    anti_file = _mount_agent(project, "antigravity")
    with open(claude_file, "a", encoding="utf-8") as fh:
        fh.write("\nTUNING-CLAUDE\n")
    with open(anti_file, "a", encoding="utf-8") as fh:
        fh.write("\nTUNING-ANTIGRAVITY\n")

    # snapshot both, using the REAL vault as the baseline source
    assert kc.snapshot_overrides(project, VAULT, "demo", platform="claude") == 1
    assert kc.snapshot_overrides(project, VAULT, "demo", platform="agents") == 1
    store = kc.overrides_root(VAULT, "demo")
    try:
        assert (store / "claude" / "agents" / "code-reviewer.md").is_file()
        assert (store / "antigravity" / "agents" / "code-reviewer.md").is_file()
        # neither snapshot clobbered the other
        assert "TUNING-CLAUDE" in (store / "claude" / "agents" / "code-reviewer.md").read_text()
        assert "TUNING-ANTIGRAVITY" in (store / "antigravity" / "agents" / "code-reviewer.md").read_text()

        # a claude restore must never paste the antigravity render
        target = tmp_path / "fresh"
        _mount_agent(target, "claude")
        kc.restore_overrides(VAULT, "demo", target, platform="claude")
        restored = (target / ".claude" / "agents" / "code-reviewer.md").read_text()
        assert "TUNING-CLAUDE" in restored and "TUNING-ANTIGRAVITY" not in restored
        # harness frontmatter intact (an antigravity render would have lost it)
        assert "maxTurns" in restored.split("\n---", 1)[0]
    finally:
        import shutil
        shutil.rmtree(kc.project_dir(VAULT, "demo"), ignore_errors=True)


def test_legacy_flat_store_migrates_to_its_platform(tmp_path):
    slug = "demo-legacy"
    root = kc.overrides_root(VAULT, slug)
    try:
        (root / "agents").mkdir(parents=True)
        (root / "agents" / "x.md").write_text("legacy\n", encoding="utf-8")
        (root / "MANIFEST.md").write_text(
            "# Overrides — project-specific tunings snapshotted from .agents/\n",
            encoding="utf-8")
        assert kc.migrate_legacy_overrides(VAULT, slug) == "agents"
        assert (root / "antigravity" / "agents" / "x.md").read_text() == "legacy\n"
        assert not (root / "agents").exists()
        assert (root / "antigravity" / "MANIFEST.md").is_file()
        # idempotent
        assert kc.migrate_legacy_overrides(VAULT, slug) is None
    finally:
        import shutil
        shutil.rmtree(kc.project_dir(VAULT, slug), ignore_errors=True)


# --- 4. platform resolution ---------------------------------------------------

def test_explicit_target_beats_autodetection(tmp_path):
    (tmp_path / ".claude" / "agents").mkdir(parents=True)
    (tmp_path / ".agents" / "agents").mkdir(parents=True)
    # autodetection used to pick .agents/ and snapshot the wrong platform
    assert kc.detect_platform(tmp_path, target="claude") == "claude"
    assert kc.detect_platform(tmp_path, target="antigravity") == "agents"
    assert kc.detect_platform(tmp_path, platform="codex") == "codex"


def test_autodetection_prefers_the_most_recently_mounted_platform(tmp_path):
    import os
    import time
    for p in (".claude", ".agents"):
        (tmp_path / p / "agents").mkdir(parents=True)
        (tmp_path / p / kc.MOUNT_MANIFEST_NAME).write_text("{}", encoding="utf-8")
    recent = tmp_path / ".claude" / kc.MOUNT_MANIFEST_NAME
    os.utime(recent, (time.time() + 60, time.time() + 60))
    assert kc.detect_platform(tmp_path) == "claude"
