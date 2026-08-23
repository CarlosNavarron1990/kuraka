"""Vault-side tests for the Wave-2 hook pack + discipline expansion + settings
merge. Hooks are exercised as real subprocesses with fixture stdin, exactly as
Claude Code invokes them (JSON on stdin, exit code as verdict).
"""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(VAULT))


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, VAULT / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


mount = _load("kuraka_mount_w2", "kuraka-mount.py")

CONFIG = """\
architecture:
  paths:
    docs_process_root: docs/process
    backend_root: backend
    frontend_root: frontend
    tests_root: tests
    migrations_root: migrations
stack:
  backend:
    test_cmd: "make test-run"
    lint_cmd: "ruff check ."
"""


def _proj(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "kuraka.config.yaml").write_text(CONFIG, encoding="utf-8")
    return proj


def _run_hook(script: str, payload: dict, proj: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(proj))
    return subprocess.run(
        [sys.executable, str(VAULT / "hooks" / script)],
        input=json.dumps(payload), capture_output=True, text=True, env=env)


# --- gate_integrity -----------------------------------------------------------

def test_gate_blocks_piped_gate_command(tmp_path):
    r = _run_hook("gate_integrity.py",
                  {"tool_input": {"command": "make test-run | tail -5"}}, _proj(tmp_path))
    assert r.returncode == 2 and "T7" in r.stderr


def test_gate_allows_unpiped_and_logical_or(tmp_path):
    proj = _proj(tmp_path)
    for cmd in ("make test-run", "make test-run || echo failed",
                "make test-run > /tmp/g.log 2>&1; echo $?",
                "make test-run | tail KURAKA_GATE_PIPE_OK"):
        r = _run_hook("gate_integrity.py", {"tool_input": {"command": cmd}}, proj)
        assert r.returncode == 0, cmd


def test_gate_ignores_non_gate_pipes_and_non_kuraka_projects(tmp_path):
    proj = _proj(tmp_path)
    r = _run_hook("gate_integrity.py",
                  {"tool_input": {"command": "git log | head -3"}}, proj)
    assert r.returncode == 0
    bare = tmp_path / "bare"; bare.mkdir()
    r = _run_hook("gate_integrity.py",
                  {"tool_input": {"command": "make test-run | tail"}}, bare)
    assert r.returncode == 0


# --- orchestrator_guard -------------------------------------------------------

def test_guard_blocks_main_session_code_write(tmp_path):
    proj = _proj(tmp_path)
    r = _run_hook("orchestrator_guard.py",
                  {"tool_input": {"file_path": str(proj / "backend" / "x.py")}}, proj)
    assert r.returncode == 2 and "backend-developer" in r.stderr


def test_guard_allows_subagent_docs_and_one_shot_marker(tmp_path):
    proj = _proj(tmp_path)
    r = _run_hook("orchestrator_guard.py",
                  {"agent_id": "abc", "tool_input": {"file_path": str(proj / "backend/x.py")}}, proj)
    assert r.returncode == 0  # subagent writes pass through
    r = _run_hook("orchestrator_guard.py",
                  {"tool_input": {"file_path": str(proj / "docs" / "REQ.md")}}, proj)
    assert r.returncode == 0  # docs are the legitimate exception
    marker = proj / ".claude" / "hooks" / "ALLOW-ORCH-WRITE"
    marker.parent.mkdir(parents=True)
    marker.write_text("1")
    r = _run_hook("orchestrator_guard.py",
                  {"tool_input": {"file_path": str(proj / "backend/x.py")}}, proj)
    assert r.returncode == 0 and not marker.exists()  # one-shot, consumed


# --- telemetry_append ---------------------------------------------------------

def test_telemetry_appends_hook_log(tmp_path):
    proj = _proj(tmp_path)
    payload = {"tool_name": "Task", "session_id": "s1",
               "tool_input": {"subagent_type": "backend-developer", "description": "impl S1"},
               "tool_response": "done <usage>total_tokens: 12345, tool_uses: 7, duration_ms: 8000</usage>"}
    r = _run_hook("telemetry_append.py", payload, proj)
    assert r.returncode == 0
    log = proj / "docs/process/agent-telemetry/HOOK-LOG.jsonl"
    entry = json.loads(log.read_text().splitlines()[0])
    assert entry["agent"] == "backend-developer"
    assert entry["total_tokens"] == 12345 and entry["tool_uses"] == 7


# --- output_validate ----------------------------------------------------------

def _transcript(tmp_path: Path, final_text: str) -> Path:
    t = tmp_path / "transcript.jsonl"
    lines = [
        {"type": "user", "message": {"role": "user", "content": "go"}},
        {"type": "assistant",
         "message": {"role": "assistant",
                     "content": [{"type": "text", "text": final_text}]}},
    ]
    t.write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
    return t


def test_output_validate_blocks_once_on_missing_confidence(tmp_path):
    proj = _proj(tmp_path)
    tp = _transcript(tmp_path, "# Code Review\n**Verdict:** APPROVED\nall good")
    payload = {"agent_type": "code-reviewer", "agent_id": "a1",
               "transcript_path": str(tp)}
    r = _run_hook("output_validate.py", payload, proj)
    assert r.returncode == 2 and "Confidence" in r.stderr
    r = _run_hook("output_validate.py", payload, proj)   # one-shot guard
    assert r.returncode == 0


def test_output_validate_passes_complete_report_and_unknown_agents(tmp_path):
    proj = _proj(tmp_path)
    tp = _transcript(tmp_path, "**Verdict:** APPROVED\n## Confidence\nHIGH")
    r = _run_hook("output_validate.py",
                  {"agent_type": "code-reviewer", "agent_id": "a2",
                   "transcript_path": str(tp)}, proj)
    assert r.returncode == 0
    r = _run_hook("output_validate.py",
                  {"agent_type": "not-a-kuraka-agent", "transcript_path": str(tp)}, proj)
    assert r.returncode == 0
    r = _run_hook("output_validate.py",
                  {"agent_type": "code-reviewer", "stop_hook_active": True,
                   "transcript_path": str(tp)}, proj)
    assert r.returncode == 0


# --- discipline expansion in renders -----------------------------------------

MARKED = ("---\nname: x\ndescription: d\n---\n\nslim note\n"
          "<!-- kuraka:discipline:gate-integrity -->\n")


def test_discipline_expands_for_non_claude_only(tmp_path):
    src = tmp_path / "s" / "f.md"; src.parent.mkdir()
    src.write_text(MARKED, encoding="utf-8")
    dc = tmp_path / "claude.md"; da = tmp_path / "anti.md"
    mount.copy_file(src, dc, target_env="claude")
    mount.copy_file(src, da, target_env="antigravity")
    assert "<!-- kuraka:discipline:gate-integrity -->" in dc.read_text()
    anti = da.read_text()
    assert "Manual gate-integrity discipline" in anti
    assert "kuraka:discipline" not in anti


# --- settings.json merge ------------------------------------------------------

def test_settings_merge_preserves_user_hooks_and_is_idempotent(tmp_path):
    pdir = tmp_path / ".claude"; pdir.mkdir()
    user_entry = {"matcher": "Bash",
                  "hooks": [{"type": "command", "command": "./my-own-hook.sh"}]}
    (pdir / "settings.json").write_text(json.dumps(
        {"model": "opus", "hooks": {"PreToolUse": [user_entry]}}), encoding="utf-8")
    assert mount.merge_claude_hook_settings(pdir) is True
    merged = json.loads((pdir / "settings.json").read_text())
    assert merged["model"] == "opus"
    pre = merged["hooks"]["PreToolUse"]
    assert user_entry in pre
    assert any(".claude/hooks/gate_integrity.py" in h["command"]
               for e in pre for h in e["hooks"])
    assert merged["hooks"]["PostToolUse"] and merged["hooks"]["SubagentStop"]
    assert mount.merge_claude_hook_settings(pdir) is False  # idempotent


def test_settings_merge_refuses_corrupt_settings(tmp_path):
    pdir = tmp_path / ".claude"; pdir.mkdir()
    (pdir / "settings.json").write_text("{not json", encoding="utf-8")
    res = mount.merge_claude_hook_settings(pdir)
    assert isinstance(res, str)
    assert (pdir / "settings.json").read_text() == "{not json"  # untouched
