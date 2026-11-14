"""Coexistence + continuous backup + doctor findings — vault-only tests.

Pins the 2026-11 azure lessons:
  1. files the project VERSIONS are project-owned: mount never overwrites them,
     never baselines them, detect_overrides never snapshots them, restore never
     pastes over them; a tracked file inside a skill dir owns the whole skill.
  2. Kuraka ignores live in .git/info/exclude, never in the project's .gitignore.
  3. a tracked settings.json → hooks go to settings.local.json.
  4. a tracked CLAUDE.md → managed block goes to CLAUDE.local.md.
  6. kuraka-backup --state-only is incremental and never deletes.
  7. the state_backup hook is throttled and fail-open.
  8/9. doctor flags open cycles (by REQ date stamp) and Kuraka state in a stash.
No test mounts through main() (that registers the target in projects/).
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

VAULT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VAULT))
import kuraka_common as kc  # noqa: E402


def _load(filename: str, name: str):
    spec = importlib.util.spec_from_file_location(name, VAULT / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mount = _load("kuraka-mount.py", "kuraka_mount_coexist")
doctor = _load("kuraka-doctor.py", "kuraka_doctor_coexist")


def _git(repo: Path, *args: str) -> str:
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t",
               GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    for k in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"):
        env.pop(k, None)
    return subprocess.run(["git", "-C", str(repo), *args], check=True, env=env,
                          capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "proj"
    (r / ".claude" / "skills" / "validar-pr").mkdir(parents=True)
    (r / ".claude" / "rules").mkdir(parents=True)
    (r / ".claude" / "skills" / "validar-pr" / "SKILL.md").write_text("team skill\n")
    (r / ".claude" / "settings.json").write_text(json.dumps(
        {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": [
            {"type": "command", "command": "bash team.sh"}]}]}}))
    (r / "CLAUDE.md").write_text("# Team\n")
    (r / ".claude" / "rules" / "19-evidence.md").write_text("team rule\n")
    (r / ".gitignore").write_text("node_modules/\n")
    _git(r, "init", "-q")
    _git(r, "add", "-A")
    _git(r, "commit", "-qm", "init")
    mount._init_ownership(r.resolve())
    return r.resolve()


def _tracked_snapshot(r: Path) -> dict:
    return {p: (r / p).read_bytes() for p in kc.git_tracked_files(r)}


# --- 1. project-owned files -------------------------------------------------

def test_project_owned_skills_and_keys():
    tracked = {".claude/skills/validar-pr/SKILL.md", ".claude/skills/own.md",
               ".claude/rules/01-x.md"}
    owned = kc.project_owned_skills(tracked, ".claude")
    assert owned == {"validar-pr", "own"}
    assert kc.is_project_owned("skills/validar-pr.md", ".claude", tracked, owned)
    assert kc.is_project_owned("skills/validar-pr/scripts/x.sh", ".claude", tracked, owned)
    assert not kc.is_project_owned("skills/kuraka.md", ".claude", tracked, owned)


def test_copy_file_never_overwrites_a_tracked_file(repo):
    before = _tracked_snapshot(repo)
    mount.copy_file(VAULT / "rules" / "19-evidence.md",
                    repo / ".claude" / "rules" / "19-evidence.md")
    assert _tracked_snapshot(repo) == before
    assert ".claude/rules/19-evidence.md" in mount._OWN["skipped"]
    # untracked destinations are still written
    mount.copy_file(VAULT / "rules" / "21-gates-vivos.md",
                    repo / ".claude" / "rules" / "21-gates-vivos.md")
    assert (repo / ".claude" / "rules" / "21-gates-vivos.md").is_file()


def test_tracked_skill_dir_owns_the_whole_skill(repo):
    mount.sync_claude_skills(VAULT / "skills", repo / ".claude" / "skills")
    assert (repo / ".claude" / "skills" / "validar-pr" / "SKILL.md").read_text() == "team skill\n"
    assert not (repo / ".claude" / "skills" / "validar-pr.md").exists()
    assert not (repo / ".claude" / "skills" / "validar-pr" / "scripts").exists()
    assert (repo / ".claude" / "skills" / "kuraka-modes" / "SKILL.md").is_file()


def test_manifest_and_overrides_ignore_project_owned(repo):
    mount.sync_claude_skills(VAULT / "skills", repo / ".claude" / "skills")
    kc.write_mount_manifest(repo, VAULT, ("skills",), platform=".claude")
    files = json.loads((repo / ".claude" / kc.MOUNT_MANIFEST_NAME).read_text())["files"]
    assert not any("validar-pr" in k for k in files)
    assert "skills/kuraka-modes.md" in files
    assert kc.detect_overrides(repo, VAULT, "claude") == []


def test_restore_never_pastes_over_a_tracked_file(repo, tmp_path, monkeypatch):
    vault = tmp_path / "vault"
    store = vault / "projects" / "proj" / "overrides" / "claude" / "skills" / "validar-pr"
    store.mkdir(parents=True)
    (store / "SKILL.md").write_text("old snapshot\n")
    skipped: list = []
    n = kc.restore_overrides(vault, "proj", repo, platform="claude", skipped=skipped)
    assert n == 0
    assert (repo / ".claude" / "skills" / "validar-pr" / "SKILL.md").read_text() == "team skill\n"
    assert skipped == [".claude/skills/validar-pr/SKILL.md"]


# --- 2. local excludes ------------------------------------------------------

def test_ignores_go_to_info_exclude_not_gitignore(repo):
    msg = mount.write_local_excludes(repo, repo / ".gitignore", ["# c", ".claude/agents/"])
    assert (repo / ".gitignore").read_text() == "node_modules/\n"
    excl = (repo / ".git" / "info" / "exclude").read_text()
    assert mount._EXCLUDE_BEGIN in excl and ".claude/agents/" in excl
    mount.write_local_excludes(repo, repo / ".gitignore", ["# c", ".claude/agents/"])
    assert (repo / ".git" / "info" / "exclude").read_text().count(mount._EXCLUDE_BEGIN) == 1
    assert "exclude" in msg


def test_uncommitted_kuraka_gitignore_block_is_reported_not_edited(repo):
    (repo / ".gitignore").write_text("node_modules/\n# Kuraka framework files (x)\n.claude/agents/\n")
    msg = mount.write_local_excludes(repo, repo / ".gitignore", [".claude/agents/"])
    assert "SIN commitear" in msg
    assert "# Kuraka framework files" in (repo / ".gitignore").read_text()
    names = [f.code for f in doctor.repo_findings(VAULT, repo, "proj", "docs/process")]
    assert "gitignore" in names


# --- 3/4. tracked settings.json and CLAUDE.md -------------------------------

def test_tracked_settings_json_gets_hooks_in_local(repo):
    before = (repo / ".claude" / "settings.json").read_bytes()
    assert mount.merge_claude_hook_settings(repo / ".claude") is True
    assert (repo / ".claude" / "settings.json").read_bytes() == before
    local = json.loads((repo / ".claude" / "settings.local.json").read_text())
    assert any("state_backup.py" in h["command"]
               for e in local["hooks"]["Stop"] for h in e["hooks"])


def test_tracked_claude_md_gets_block_in_local(repo):
    assert mount.ensure_claude_md_block(repo) is True
    assert (repo / "CLAUDE.md").read_text() == "# Team\n"
    assert "kuraka:managed:begin" in (repo / "CLAUDE.local.md").read_text()


# --- 6/7. continuous backup -------------------------------------------------

def test_snapshot_incremental_never_deletes(tmp_path):
    src, dst = tmp_path / "s", tmp_path / "d"
    src.mkdir(); dst.mkdir()
    (src / "a.md").write_text("1")
    (dst / "keep.md").write_text("store-only")
    assert kc.snapshot_tree_incremental(src, dst) == 1
    assert kc.snapshot_tree_incremental(src, dst) == 0
    assert (dst / "keep.md").read_text() == "store-only"


def test_state_backup_hook_fail_open_and_throttled(tmp_path):
    proj = tmp_path / "p"
    proj.mkdir()
    hook = VAULT / "hooks" / "state_backup.py"
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(proj), KURAKA_VAULT=str(tmp_path / "novault"))
    r = subprocess.run([sys.executable, str(hook)], input="{}", text=True, env=env)
    assert r.returncode == 0 and not (proj / ".claude" / ".kuraka-state-backup.stamp").exists()
    (proj / "kuraka.config.yaml").write_text("project:\n  name: p\n")
    r = subprocess.run([sys.executable, str(hook)], input="{}", text=True, env=env)
    assert r.returncode == 0  # vault missing → silent
    settings = json.loads((VAULT / "hooks" / "settings-hooks.json").read_text())["hooks"]
    for ev in ("Stop", "SubagentStop"):
        assert any("state_backup.py" in h["command"] for e in settings[ev] for h in e["hooks"])


# --- 8/9. doctor ------------------------------------------------------------

def test_doctor_open_cycles_use_req_date_and_ticket_key(repo, tmp_path):
    docs = repo / "docs" / "process"
    (docs / "agent-retrospectives").mkdir(parents=True)
    (docs / "REQ-20261110-GUAI-3141-urgencias.md").write_text("x")       # open
    (docs / "REQ-20261007-GUAI-2979-autocita.md").write_text("x")        # closed by key
    (docs / "agent-retrospectives" / "RETRO-REQ-20261007-GUAI-2979-otra.md").write_text("x")
    (docs / "REQ-20261110-GUAI-3141-S1.md").write_text("story")          # not a REQ
    opened = doctor.open_cycles(tmp_path / "vault", repo, "proj", "docs/process")
    assert opened == ["REQ-20261110-GUAI-3141-urgencias"]


def test_doctor_finds_kuraka_state_in_a_stash(repo):
    (repo / "kuraka.config.yaml").write_text("project:\n  name: p\n")
    (repo / "docs" / "process").mkdir(parents=True)
    (repo / "docs" / "process" / "REQ-x.md").write_text("x")
    _git(repo, "stash", "push", "-u", "-q", "-m", "desktop")
    assert not (repo / "kuraka.config.yaml").exists()
    hits = doctor.stashed_kuraka_state(repo, "docs/process")
    assert hits and hits[0][0] == "stash@{0}"
    assert "kuraka.config.yaml" in hits[0][2]
    f = [x for x in doctor.repo_findings(VAULT, repo, "proj", "docs/process") if x.code == "stash"]
    assert f and "stash@{0}^3" in f[0].hint
