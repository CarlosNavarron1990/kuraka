"""Claude-native Ultra Ahorro: harness contract, mount shape and write guard."""
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
import kuraka_common as kc

GUARD = VAULT / "hooks" / "orchestrator_guard.py"
SKILL = VAULT / "skills" / "kuraka-ahorro.md"
CYCLE = "REQ-20260914-AHORRO-01"


def module(name, filename):
    spec = importlib.util.spec_from_file_location(name, VAULT / filename)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


mount = module("mount_claude_ahorro", "kuraka-mount.py")


# --------------------------------------------------------------------------
# The mode's enforcement lives in Claude-only frontmatter, not in prose.
# --------------------------------------------------------------------------

def test_skill_frontmatter_carries_the_claude_harness_contract():
    fm, body = kc.split_frontmatter(SKILL.read_text(encoding="utf-8"))
    assert fm["name"] == "kuraka-ahorro" and fm["description"]
    # zero subagents is a harness fact here: subagent spawns never reach a
    # PreToolUse hook, so removing the tool is the only real enforcement.
    assert fm["disallowed-tools"] == "Task"
    assert fm["model"] == "sonnet" and fm["effort"] == "medium"
    assert "$ARGUMENTS" not in body


def test_claude_only_keys_are_subtracted_for_other_platforms():
    for key in ("model", "effort", "disallowed-tools"):
        assert key in SKILL.read_text(encoding="utf-8").split("---")[1]
    stripped = kc.strip_claude_frontmatter(SKILL.read_text(encoding="utf-8"))
    head = stripped.split("---")[1]
    assert "effort:" not in head and "disallowed-tools:" not in head
    assert "name: kuraka-ahorro" in head  # the portable keys survive


# --------------------------------------------------------------------------
# Mount shape per platform.
# --------------------------------------------------------------------------

def test_claude_mount_registers_the_skill_without_the_codex_helper(tmp_path):
    skills = tmp_path / ".claude" / "skills"
    mount.sync_claude_skills(VAULT / "skills", skills)
    registered = skills / "kuraka-ahorro" / "SKILL.md"
    assert registered.is_file() and (skills / "kuraka-ahorro.md").is_file()
    # byte-identical to the vault: the override subsystem compares bytes
    assert registered.read_bytes() == SKILL.read_bytes()
    assert not (skills / "kuraka-ahorro" / "scripts").exists()
    assert "cycle.py" not in registered.read_text(encoding="utf-8")
    assert ".codex/" not in registered.read_text(encoding="utf-8")


@pytest.mark.parametrize("platform", ["agents", "cursor"])
def test_platforms_without_an_enforceable_contract_do_not_receive_the_mode(tmp_path, platform):
    skills = tmp_path / "skills"
    if platform == "agents":
        mount.sync_antigravity_skills(VAULT / "skills", skills)
    else:
        mount.sync_tree(VAULT / "skills", skills, exclude=("*.append.md",)
                        + ("kuraka-ahorro", "kuraka-ahorro.md"), target_env="cursor")
    assert not (skills / "kuraka-ahorro.md").exists()
    assert not (skills / "kuraka-ahorro").exists()
    kc.write_mount_manifest(tmp_path, VAULT, ("skills",), platform=platform)
    assert "skills/kuraka-ahorro.md" not in kc.load_mount_manifest(tmp_path, platform)


def test_codex_keeps_the_helper_protocol_the_claude_render_omits(tmp_path):
    skills = tmp_path / ".codex" / "skills"
    mount.sync_codex_skills(VAULT / "skills", skills)
    text = (skills / "kuraka-ahorro" / "SKILL.md").read_text(encoding="utf-8")
    assert ".codex/skills/kuraka-ahorro/scripts/cycle.py" in text
    assert (skills / "kuraka-ahorro" / "scripts" / "cycle.py").is_file()
    assert ".claude/" not in text and "$kuraka-ahorro" in text
    # the discipline marker must be EXPANDED, never shipped raw
    assert "kuraka:discipline" not in text
    assert "do **not** write that JSON file" in text


def test_codex_skill_projection_expands_discipline_for_every_skill(tmp_path):
    """Regression: the Codex SKILL.md rebuild used to skip expand_discipline, so
    Codex was the one platform receiving raw markers instead of the prose."""
    skills = tmp_path / ".codex" / "skills"
    mount.sync_codex_skills(VAULT / "skills", skills)
    raw = [p for p in skills.rglob("SKILL.md")
           if "kuraka:discipline" in p.read_text(encoding="utf-8")]
    assert raw == []


def test_claude_mount_manifest_reports_no_phantom_override(tmp_path):
    mount.sync_claude_skills(VAULT / "skills", tmp_path / ".claude" / "skills")
    kc.write_mount_manifest(tmp_path, VAULT, ("skills",), platform="claude")
    assert "skills/kuraka-ahorro.md" in kc.load_mount_manifest(tmp_path, "claude")
    assert kc.detect_overrides(tmp_path, VAULT, platform="claude") == []
    flat = tmp_path / ".claude" / "skills" / "kuraka-ahorro.md"
    flat.write_text(flat.read_text(encoding="utf-8") + "\nProject tuning\n")
    assert Path("skills/kuraka-ahorro.md") in kc.detect_overrides(
        tmp_path, VAULT, platform="claude")


# --------------------------------------------------------------------------
# The write guard: the mode's only real exception to the orchestrator rule.
# --------------------------------------------------------------------------

@pytest.fixture
def project(tmp_path):
    (tmp_path / "kuraka.config.yaml").write_text(
        "architecture:\n  paths:\n    frontend_root: src\n    tests_root: tests\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / ".claude" / "ultra-ahorro").mkdir(parents=True)
    return tmp_path


def declare(project, filename=CYCLE, **overrides):
    state = {"schema_version": 1, "mode": "ultra-ahorro", "cycle_id": CYCLE,
             "status": "active", "objective": "Local fix",
             "allowed_files": ["src/a.ts"], "baseline_dirty": []}
    state.update(overrides)
    (project / ".claude" / "ultra-ahorro" / f"{filename}.json").write_text(
        json.dumps(state), encoding="utf-8")
    return state


def guard(project, path, session="session-A", **extra):
    payload = {"session_id": session, "cwd": str(project), "tool_name": "Edit",
               "tool_input": {"file_path": str(project / path)}, **extra}
    done = subprocess.run([sys.executable, str(GUARD)], input=json.dumps(payload),
                          text=True, capture_output=True,
                          env={**os.environ, "CLAUDE_PROJECT_DIR": str(project)})
    return done.returncode


def test_declared_file_is_allowed_and_binds_the_cycle_to_that_session(project):
    declare(project)
    assert guard(project, "src/a.ts") == 0
    owner = project / ".claude" / "ultra-ahorro" / f"{CYCLE}.owner"
    assert json.loads(owner.read_text())["session_id"] == "session-A"
    assert guard(project, "src/a.ts") == 0                      # same session again
    assert guard(project, "src/a.ts", session="session-B") == 2  # never inherited


def test_the_exception_is_per_file_not_per_cycle(project):
    declare(project, allowed_files=["src/a.ts"])
    assert guard(project, "src/b.ts") == 2
    assert guard(project, "tests/a.spec.ts") == 2
    # a file outside every configured code root was never guarded to begin with
    assert guard(project, "docs/process/notes.md") == 0


@pytest.mark.parametrize("state", [
    {"status": "closed"}, {"status": "aborted"}, {"mode": "lite"},
    {"cycle_id": "REQ-20260914-AHORRO-02"},        # id must match its filename
    {"cycle_id": "../../etc/passwd"},              # id is never a path
    {"allowed_files": "src/a.ts"},                 # not a list
    {"allowed_files": ["../outside/a.ts"]},
    {"allowed_files": ["/etc/passwd"]},
    {"allowed_files": ["src/../../escape.ts"]},
])
def test_an_invalid_or_inactive_declaration_grants_nothing(project, state):
    declare(project, **state)  # always stored as <CYCLE>.json
    assert guard(project, "src/a.ts") == 2


def test_corrupt_declaration_and_missing_session_grant_nothing(project):
    declare(project)
    assert guard(project, "src/a.ts", session="") == 2
    (project / ".claude" / "ultra-ahorro" / f"{CYCLE}.json").write_text("{not json")
    assert guard(project, "src/a.ts") == 2


def test_a_symlink_cannot_smuggle_a_write_out_of_the_declared_file(project, tmp_path):
    outside = tmp_path.parent / "outside.ts"
    outside.write_text("secret\n")
    (project / "src" / "a.ts").symlink_to(outside)
    declare(project, allowed_files=["src/b.ts"])
    # resolving through the link must not make it look like the declared file
    assert guard(project, "src/a.ts") == 2


def test_subagent_writes_and_projects_without_the_mode_are_untouched(project):
    declare(project)
    assert guard(project, "src/b.ts", agent_id="frontend-developer") == 0
    assert guard(project, "src/a.ts", agent_id="frontend-developer") == 0
    (project / "kuraka.config.yaml").unlink()
    assert guard(project, "src/b.ts") == 0  # fail-open outside a Kuraka project


def test_one_shot_escape_hatch_still_works_alongside_the_mode(project):
    hooks = project / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    (hooks / "ALLOW-ORCH-WRITE").touch()
    assert guard(project, "src/b.ts") == 0
    assert not (hooks / "ALLOW-ORCH-WRITE").exists()  # consumed
    assert guard(project, "src/b.ts") == 2


# --------------------------------------------------------------------------
# Entry points and workflow coherence.
# --------------------------------------------------------------------------

def test_the_kuraka_command_short_circuits_before_loading_the_pipeline():
    text = (VAULT / "commands" / "kuraka.md").read_text(encoding="utf-8")
    short_circuit = text.index("Ultra Ahorro short-circuit")
    assert short_circuit < text.index(".claude/skills/kuraka.md")
    assert "--modo ultra-ahorro" in text and "ultra-ahorro" in text.split("---")[1]


def test_modes_document_places_the_mode_and_keeps_lite_distinct():
    text = (VAULT / "skills" / "kuraka-modes.md").read_text(encoding="utf-8")
    assert "## Mode: Ultra Ahorro" in text
    assert "0 agents — direct execution" in text
    assert "not yet measured" in text  # no invented saving percentage
    mirror = VAULT / "skills" / "kuraka-modes" / "SKILL.md"
    assert mirror.read_bytes() == (VAULT / "skills" / "kuraka-modes.md").read_bytes()


def test_orchestrator_constraint_names_the_mode_exception():
    text = (VAULT / "skills" / "kuraka.md").read_text(encoding="utf-8")
    section = text[text.index("## Orchestrator constraint"):]
    assert "Ultra Ahorro" in section[:1800]


def test_config_schemas_accept_the_mode_and_stay_backward_compatible():
    schema = json.loads((VAULT / "kuraka-artifacts" / "config-schema.json")
                        .read_text(encoding="utf-8"))
    workflow = schema["properties"]["workflow"]["properties"]
    assert "ultra-ahorro" in workflow["default_mode"]["enum"]
    assert set(workflow["ultra_ahorro"]["properties"]) == {
        "enabled", "max_source_files", "max_changed_lines",
        "max_fix_attempts", "context_warning_tokens"}
    # every new field optional: a config predating the mode still validates
    assert "ultra_ahorro" not in schema["properties"]["workflow"].get("required", [])


def test_a_real_claude_mount_registers_the_mode_and_ignores_its_state(tmp_path):
    (tmp_path / ".claude" / "agents").mkdir(parents=True)
    (tmp_path / "kuraka.config.yaml").write_text(
        "project:\n  name: ahorro-claude-fixture\nworkflow:\n"
        "  default_mode: ultra-ahorro\n")
    done = subprocess.run(
        [sys.executable, str(VAULT / "kuraka-mount.py"), str(tmp_path), "--update"],
        capture_output=True, text=True, stdin=subprocess.DEVNULL)
    assert done.returncode == 0, done.stdout + done.stderr
    assert (tmp_path / ".claude/skills/kuraka-ahorro/SKILL.md").is_file()
    assert not (tmp_path / ".claude/skills/kuraka-ahorro/scripts").exists()
    assert ".claude/ultra-ahorro/" in (tmp_path / ".gitignore").read_text()
    settings = json.loads((tmp_path / ".claude/settings.json").read_text())
    wired = json.dumps(settings["hooks"]["PreToolUse"])
    assert "orchestrator_guard.py" in wired
    validate = subprocess.run(["bash", str(VAULT / "validate-kuraka.sh"), str(tmp_path)],
                              capture_output=True, text=True)
    assert validate.returncode == 0, validate.stdout + validate.stderr
