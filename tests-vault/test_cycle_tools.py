"""Cycle instrumentation — vault-only tests.

Three things that had no deterministic owner until 2026-11:
  1. the telemetry hook reads a subagent's cost at SubagentStop (Claude Code
     launches subagents in the background: the PostToolUse response is an
     `async_launched` ack with no usage — 869/869 rows were null). Fixtures are
     REAL payloads captured from Claude Code 2.1.325.
  2. kuraka-preflight: environment blockers found before Phase 1.
  3. kuraka-close: one gate to close or abandon a cycle; meta.yaml gets
     mode / size / invocaciones / retrabajo / tokens_total.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

VAULT = Path(__file__).resolve().parents[1]
FX = VAULT / "tests-vault" / "fixtures"
sys.path.insert(0, str(VAULT))
import kuraka_common as kc  # noqa: E402


def _load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, VAULT / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tele = _load("telemetry_append_ct", "hooks/telemetry_append.py")
pre = _load("kuraka_preflight_ct", "kuraka-preflight.py")
doctor = _load("kuraka_doctor_ct", "kuraka-doctor.py")

CONFIG = """\
schema_version: 1
project:
  name: app
stack:
  backend:
    test_cmd: "{test}"
    lint_cmd: "{lint}"
  database:
    migration_tool: alembic
architecture:
  paths:
    migrations_root: migrations/
    docs_process_root: docs/process/
"""
PY = sys.executable


def _proj(tmp_path: Path, test: str = f"{PY} -c pass", lint: str = f"{PY} -c pass") -> Path:
    proj = tmp_path / "app"
    proj.mkdir()
    (proj / "kuraka.config.yaml").write_text(CONFIG.format(test=test, lint=lint), encoding="utf-8")
    return proj


def _hook(payload: dict, proj: Path):
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(proj))
    return subprocess.run([PY, str(VAULT / "hooks" / "telemetry_append.py")],
                          input=json.dumps(payload), capture_output=True, text=True, env=env)


def _log(proj: Path) -> list:
    return kc.read_hook_log(proj / "docs/process/agent-telemetry/HOOK-LOG.jsonl")


def _stop_payload(tmp_path: Path) -> dict:
    tr = tmp_path / "subagents" / "agent-a83054bbdc1a6d9a4.jsonl"
    tr.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(FX / "agent-transcript.jsonl", tr)
    p = json.loads((FX / "hook-subagentstop.json").read_text())
    p["agent_transcript_path"] = str(tr)
    return p


# --- 1. telemetry hook --------------------------------------------------------

def test_async_launch_is_a_launch_row_without_cost(tmp_path):
    proj = _proj(tmp_path)
    assert _hook(json.loads((FX / "hook-posttooluse-agent-async.json").read_text()), proj).returncode == 0
    (row,) = _log(proj)
    assert row["event"] == "launch" and row["agent_id"] == "a83054bbdc1a6d9a4"
    assert row["total_tokens"] is None and row["agent"] == "general-purpose"
    assert row["model"] == "claude-haiku-5-5"  # resolvedModel when the call names none


def test_subagent_stop_reads_cost_from_the_transcript(tmp_path):
    proj = _proj(tmp_path)
    payload = _stop_payload(tmp_path)
    assert _hook(payload, proj).returncode == 0
    (row,) = _log(proj)
    assert row["event"] == "stop" and row["agent"] == "general-purpose"
    assert row["total_tokens"] == 14512 and row["turns"] == 1 and row["tool_uses"] == 0
    assert row["output_tokens_sum"] == 4 and row["cache_creation_sum"] == 14506
    assert row["description"] == "Reply with ok" and row["seq"] == 1 and row["resumed"] is False
    _hook(payload, proj)  # the agent was resumed and stopped again
    assert [r["seq"] for r in _log(proj)] == [1, 2] and _log(proj)[1]["resumed"] is True


def test_stop_without_a_readable_transcript_stays_null_not_zero(tmp_path):
    proj = _proj(tmp_path)
    p = json.loads((FX / "hook-subagentstop.json").read_text())
    p["agent_transcript_path"] = str(tmp_path / "missing.jsonl")
    assert _hook(p, proj).returncode == 0
    assert _log(proj)[0]["total_tokens"] is None


def test_transcript_usage_dedups_blocks_of_one_api_message(tmp_path):
    u1 = {"input_tokens": 10, "cache_read_input_tokens": 1000, "cache_creation_input_tokens": 0, "output_tokens": 50}
    u2 = {"input_tokens": 5, "cache_read_input_tokens": 2000, "cache_creation_input_tokens": 100, "output_tokens": 70}
    rows = [
        {"timestamp": "2026-11-14T10:00:00.000Z", "message": {"role": "user", "content": "go"}},
        # one API message, written once per content block with the same usage
        {"timestamp": "2026-11-14T10:00:05.000Z", "message": {"id": "m1", "role": "assistant", "model": "claude-sonnet-5-5", "usage": u1, "content": [{"type": "text", "text": "x"}]}},
        {"timestamp": "2026-11-14T10:00:05.500Z", "message": {"id": "m1", "role": "assistant", "model": "claude-sonnet-5-5", "usage": u1, "content": [{"type": "tool_use", "id": "t1"}]}},
        {"timestamp": "2026-11-14T10:00:20.000Z", "message": {"id": "m2", "role": "assistant", "model": "claude-sonnet-5-5", "usage": u2, "content": [{"type": "tool_use", "id": "t2"}]}},
    ]
    t = tmp_path / "t.jsonl"
    t.write_text("\n".join(json.dumps(r) for r in rows))
    u = tele.transcript_usage(t)
    assert u["turns"] == 2 and u["tool_uses"] == 2
    assert u["output_tokens_sum"] == 120 and u["cache_read_sum"] == 3000
    assert u["total_tokens"] == 5 + 2000 + 100 + 70  # last turn: context + output
    assert u["duration_ms"] == 20_000 and u["model"] == "claude-sonnet-5-5"


def test_hook_wiring_covers_both_events():
    h = json.loads((VAULT / "hooks" / "settings-hooks.json").read_text())["hooks"]
    post = [e for e in h["PostToolUse"] if "telemetry_append" in json.dumps(e)]
    assert post and "Agent" in post[0]["matcher"] and "Task" in post[0]["matcher"]
    assert "telemetry_append" in json.dumps(h["SubagentStop"])


def test_hook_runs_collapses_launch_stop_and_flags_lost():
    rows = [
        {"ts": "2026-11-14T10:00:00+00:00", "event": "launch", "agent_id": "a1", "agent": "backend-developer"},
        {"ts": "2026-11-14T10:01:00+00:00", "event": "launch", "agent_id": "a2", "agent": "code-reviewer"},
        {"ts": "2026-11-14T10:05:00+00:00", "event": "stop", "agent_id": "a1", "agent": "backend-developer", "total_tokens": 100, "seq": 1},
        {"ts": "2026-11-14T10:09:00+00:00", "event": "stop", "agent_id": "a1", "agent": "backend-developer", "total_tokens": 180, "seq": 2},
        {"ts": "2026-11-13T09:00:00+00:00", "agent": "legacy", "total_tokens": None},
    ]
    runs = kc.hook_runs(rows)
    assert [(r.get("agent"), r.get("total_tokens"), r["lost"]) for r in runs] == [
        ("backend-developer", 180, False), ("code-reviewer", None, True), ("legacy", None, False)]
    assert len(kc.hook_runs(rows, since="2026-11-14T00:00:00+00:00")) == 2


# --- cycle metrics ------------------------------------------------------------

def _telemetry(path: Path, **top) -> Path:
    data = {"req_name": "REQ-X", "mode": "Normal", "runs": [
        {"phase": "1+2+2.5", "agent": "po-analyst", "total_tokens": 100, "size": "M"},
        {"phase": "4a-S1", "agent": "backend-developer", "total_tokens": 200},
        {"phase": "4a-S2", "agent": "backend-developer", "total_tokens": 200},  # planned, not rework
        {"phase": "5", "agent": "code-reviewer", "total_tokens": 50},
        {"phase": "5-fix", "agent": "backend-developer", "total_tokens": 80},
        {"phase": "4a", "agent": "backend-developer", "total_tokens": 300, "resumed": True, "tokens_incremental": 40},
        {"phase": "6", "agent": "test-engineer", "total_tokens": 60, "attempt": 2},
        {"phase": "4b", "agent": "frontend-developer", "total_tokens": 70, "rework": True},
        {"phase": "7", "agent": "orchestrator", "total_tokens": 0},
    ], **top}
    path.write_text(json.dumps(data))
    return path


def test_cycle_metrics_counts_rework_not_planned_runs(tmp_path):
    m = kc.cycle_metrics(_telemetry(tmp_path / "REQ-X-telemetry.json"))
    assert m["mode"] == "normal" and m["size"] == "M" and m["telemetria"] == "curada"
    assert m["invocaciones"] == 8          # the orchestrator's 0-token row is not an invocation
    assert m["retrabajo"] == 3             # 5-fix, attempt 2, rework: true
    assert m["tokens_total"] == 100 + 200 + 200 + 50 + 80 + 40 + 60 + 70
    assert kc.cycle_metrics(tmp_path / "nope.json")["telemetria"] == ""


def test_attach_metrics_is_idempotent_and_backfills(tmp_path):
    dest = tmp_path / "REQ-X"
    dest.mkdir()
    (dest / "meta.yaml").write_text('project: app\nreq: REQ-X\nverdict: "HIGH"\n')
    assert kc._attach_metrics(dest) is False  # no telemetry: nothing invented
    _telemetry(dest / "REQ-X-telemetry.json", size="L")
    assert kc._attach_metrics(dest) is True
    text = (dest / "meta.yaml").read_text()
    assert 'mode: "normal"' in text and 'size: "L"' in text and "retrabajo: 3" in text
    assert 'verdict: "HIGH"' in text
    assert kc._attach_metrics(dest) is False


# --- 2. preflight -------------------------------------------------------------

def _preflight(proj: Path, vault: Path, *extra: str):
    return subprocess.run([PY, str(VAULT / "kuraka-preflight.py"), str(proj), "--vault", str(vault), *extra],
                          capture_output=True, text=True)


def test_config_scalars_reads_nested_paths():
    cfg = pre.config_scalars(CONFIG.format(test="make t", lint="TODO") + "  list:\n    - a\n")
    assert cfg["stack.backend.test_cmd"] == "make t"
    assert cfg["architecture.paths.docs_process_root"] == "docs/process/"
    assert cfg["project.name"] == "app"


def test_preflight_blocks_on_placeholder_test_gate(tmp_path):
    proj = _proj(tmp_path, test="TODO")
    r = _preflight(proj, tmp_path)
    assert r.returncode == 1 and "placeholder" in r.stdout


def test_preflight_blocks_on_missing_tool_and_make_target(tmp_path):
    proj = _proj(tmp_path, test="definitely-not-a-binary-xyz run", lint="make nope")
    (proj / "Makefile").write_text("test:\n\ttrue\n")
    r = _preflight(proj, tmp_path)
    assert r.returncode == 1
    assert "no está en el PATH" in r.stdout and "no tiene el target «nope»" in r.stdout


def test_preflight_opens_the_cycle_and_keeps_its_start(tmp_path):
    proj = _proj(tmp_path)
    r = _preflight(proj, tmp_path, "--req", "REQ-20261114-X", "--mode", "normal", "--size", "m", "--tests")
    assert r.returncode == 0, r.stdout + r.stderr
    f = proj / "docs/process/checkpoints/PREFLIGHT-REQ-20261114-X.json"
    first = json.loads(f.read_text())
    assert first["mode"] == "normal" and first["size"] == "M" and first["started_at"]
    assert first["baseline"][0]["exit"] == 0
    first["started_at"] = "2026-11-01T00:00:00+00:00"
    f.write_text(json.dumps(first))
    _preflight(proj, tmp_path, "--req", "REQ-20261114-X")
    again = json.loads(f.read_text())
    assert again["started_at"] == "2026-11-01T00:00:00+00:00"  # the cycle's start survives re-runs
    assert again["mode"] == "normal" and again["size"] == "M" and again["reruns"] == 1


def test_red_baseline_blocks_until_the_user_accepts_it(tmp_path):
    proj = _proj(tmp_path, test=f"{PY} -c \"import sys; print('3 failed'); sys.exit(1)\"")
    r = _preflight(proj, tmp_path, "--tests")
    assert r.returncode == 1 and "ya está ROJO" in r.stdout and "3 failed" in r.stdout
    r = _preflight(proj, tmp_path, "--tests", "--permitir-base-roja", "deuda conocida")
    assert r.returncode == 0 and "deuda conocida" in r.stdout


def test_preflight_blocks_on_two_alembic_heads(tmp_path):
    proj = _proj(tmp_path)
    mig = proj / "migrations"
    mig.mkdir()
    (mig / "0001_a.py").write_text('revision = "a1"\ndown_revision = None\n')
    (mig / "0002_b.py").write_text('revision: str = "b2"\ndown_revision: str | None = "a1"\n')
    assert "1 head" in _preflight(proj, tmp_path).stdout
    (mig / "0002_c.py").write_text('revision = "c3"\ndown_revision = "a1"\n')
    r = _preflight(proj, tmp_path)
    assert r.returncode == 1 and "2 heads" in r.stdout


def test_env_keys_missing_is_a_warning(tmp_path):
    proj = _proj(tmp_path)
    (proj / ".env.example").write_text("A=1\nB=2\nexport C=3\n")
    (proj / ".env").write_text("A=1\n")
    r = _preflight(proj, tmp_path)
    assert r.returncode == 0 and "faltan 2 clave(s)" in r.stdout and "B, C" in r.stdout


# --- 3. close -----------------------------------------------------------------

REQ = "REQ-20261114-X-demo"


def _store(tmp_path: Path):
    store = tmp_path / "vault"
    (store / "projects" / "app").mkdir(parents=True)
    shutil.copy2(VAULT / "SUITE-VERSION", store / "SUITE-VERSION")
    shutil.copytree(VAULT / "agents", store / "agents")
    proj = _proj(tmp_path)
    (proj / ".claude" / "agents").mkdir(parents=True)
    kc.write_mount_manifest(proj, store, ("agents",), platform="claude")
    (store / "projects" / "app" / "registry.md").write_text(f"---\nname: app\npath: {proj}\n---\n")
    (proj / "docs" / "process").mkdir(parents=True)
    (proj / "docs" / "process" / f"{REQ}.md").write_text("# req\n")
    return store, proj


def _close(proj: Path, store: Path, *extra: str):
    return subprocess.run([PY, str(VAULT / "kuraka-close.py"), str(proj), "--vault", str(store), *extra],
                          capture_output=True, text=True)


def test_close_refuses_a_cycle_without_retro(tmp_path):
    store, proj = _store(tmp_path)
    r = _close(proj, store, "--req", REQ)
    assert r.returncode == 1 and "falta la fase 7" in r.stdout
    assert not (store / "projects" / "app" / "cycles" / REQ).exists()


def test_abandon_closes_the_cycle_with_its_reason(tmp_path):
    store, proj = _store(tmp_path)
    assert doctor.open_cycles(store, proj, "app", "docs/process", min_age_h=0) == [REQ]
    assert _close(proj, store, "--req", REQ, "--abandonar").returncode == 2  # a reason is mandatory
    r = _close(proj, store, "--req", REQ, "--abandonar", "--motivo", "el cliente canceló el alcance")
    assert r.returncode == 0, r.stdout + r.stderr
    meta = (store / "projects" / "app" / "cycles" / REQ / "meta.yaml").read_text()
    assert 'verdict: "ABANDONED"' in meta and "el cliente canceló" in meta
    assert doctor.open_cycles(store, proj, "app", "docs/process", min_age_h=0) == []
    assert "ningún ciclo abierto" in _close(proj, store, "--list").stdout


def test_close_derives_telemetry_from_the_hook_log_and_stamps_metrics(tmp_path):
    store, proj = _store(tmp_path)
    dp = proj / "docs" / "process"
    assert _preflight(proj, store, "--req", REQ, "--mode", "lite", "--size", "S").returncode == 0
    (dp / "agent-retrospectives").mkdir()
    (dp / "agent-retrospectives" / f"RETRO-{REQ}.md").write_text("# retro\n\n## Confidence: HIGH\n")
    (dp / "agent-telemetry").mkdir()
    rows = [
        {"ts": "2099-01-01T00:00:00+00:00", "event": "launch", "agent_id": "a1", "agent": "backend-developer"},
        {"ts": "2099-01-01T00:05:00+00:00", "event": "stop", "agent_id": "a1", "agent": "backend-developer", "total_tokens": 150000, "tool_uses": 30, "seq": 1},
        {"ts": "2099-01-01T00:06:00+00:00", "event": "launch", "agent_id": "a2", "agent": "code-reviewer"},
    ]
    (dp / "agent-telemetry" / "HOOK-LOG.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    r = _close(proj, store, "--req", REQ)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "derivada de HOOK-LOG" in r.stdout and "nunca terminaron" in r.stdout
    derived = json.loads((dp / "agent-telemetry" / f"{REQ}-telemetry.json").read_text())
    assert derived["source"] == "hook-derived" and derived["mode"] == "lite"
    assert [x["status"] for x in derived["runs"]] == ["ok", "lost"]
    meta = (store / "projects" / "app" / "cycles" / REQ / "meta.yaml").read_text()
    assert 'verdict: "HIGH"' in meta and 'mode: "lite"' in meta and 'size: "S"' in meta
    assert "invocaciones: 2" in meta and "tokens_total: 150000" in meta and 'telemetria: "hook"' in meta
    assert "cerrado · veredicto HIGH" in r.stdout


def test_close_blocks_when_the_user_has_not_accepted(tmp_path):
    store, proj = _store(tmp_path)
    dp = proj / "docs" / "process"
    (dp / "agent-retrospectives").mkdir()
    (dp / "agent-retrospectives" / f"RETRO-{REQ}.md").write_text("# retro\n\n## Confidence: HIGH\n")
    aj = [PY, str(VAULT / "kuraka-ajuste.py")]
    subprocess.run(aj + ["add", str(proj), "--req", REQ, "--tipo", "bug", "--debio", "4a backend-developer",
                         "--texto", "el total no suma"], capture_output=True, text=True, check=True)
    r = _close(proj, store, "--req", REQ)
    assert r.returncode == 1 and "no aceptó el ciclo" in r.stdout
    assert not (store / "projects" / "app" / "cycles" / REQ).exists()
    r = _close(proj, store, "--req", REQ, "--sin-aceptacion", "el usuario salió de vacaciones")
    assert r.returncode == 0, r.stdout + r.stderr


# --- the last turn may not be in the transcript yet at SubagentStop -----------

def test_stop_before_the_final_turn_is_flushed_is_marked_partial(tmp_path):
    proj = _proj(tmp_path)
    p = _stop_payload(tmp_path)
    p["last_assistant_message"] = "a final answer the transcript does not hold yet"
    assert _hook(p, proj).returncode == 0
    (row,) = _log(proj)
    assert row["partial"] is True and row["total_tokens"] == 14512
    assert row["transcript"] == p["agent_transcript_path"]


def test_close_recomputes_partial_rows_from_the_transcript(tmp_path):
    close = _load("kuraka_close_ct", "kuraka-close.py")
    tr = tmp_path / "agent-x.jsonl"
    shutil.copy2(FX / "agent-transcript.jsonl", tr)
    runs = [{"agent_id": "x", "partial": True, "transcript": str(tr), "total_tokens": 1},
            {"agent_id": "y", "partial": True, "transcript": str(tmp_path / "gone.jsonl"), "total_tokens": 7}]
    assert close.settle_partial(runs) == 1
    assert runs[0]["total_tokens"] == 14512 and runs[0]["partial"] is False
    assert runs[1]["total_tokens"] == 7 and runs[1]["partial"] is True  # never zeroed


def test_foreground_run_and_its_stop_are_one_invocation():
    rows = [
        {"ts": "t1", "event": "stop", "agent_id": "a1", "agent": "general-purpose", "total_tokens": 45263, "partial": True, "seq": 1},
        {"ts": "t1", "event": "run", "agent_id": "a1", "agent": "code-reviewer", "total_tokens": 49674, "tool_uses": 1},
    ]
    for order in (rows, rows[::-1]):
        (run,) = kc.hook_runs(order)
        assert run["total_tokens"] == 49674 and run["agent"] == "code-reviewer"
        assert run["lost"] is False and run["partial"] is False
