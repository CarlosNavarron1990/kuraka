"""Vault-side tests for the infra fixes harvested from consumer projects
(suite harvest 2026-11): telemetry hook usage parsing, aggregator robustness,
gate-integrity segment/quote awareness, cycle re-archiving, project instruments
in backup/doctor.
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
sys.path.insert(0, str(VAULT))

import kuraka_common as kc  # noqa: E402


def _load(mod_name: str, filename: str):
    spec = importlib.util.spec_from_file_location(mod_name, VAULT / filename)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


tele = _load("telemetry_append_h", "hooks/telemetry_append.py")
gate = _load("gate_integrity_h", "hooks/gate_integrity.py")
agg = _load("aggregate_telemetry_h", "aggregate-telemetry.py")

CONFIG = """\
architecture:
  paths:
    docs_process_root: docs/process
stack:
  backend:
    test_cmd: "make test-run"
    lint_cmd: "TODO"
"""


def _proj(tmp_path: Path) -> Path:
    proj = tmp_path / "proj"
    proj.mkdir()
    (proj / "kuraka.config.yaml").write_text(CONFIG, encoding="utf-8")
    return proj


def _hook(script: str, payload: dict, proj: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(proj))
    return subprocess.run([sys.executable, str(VAULT / "hooks" / script)],
                          input=json.dumps(payload), capture_output=True, text=True, env=env)


# --- telemetry hook ----------------------------------------------------------

def test_structured_camelcase_usage_is_captured(tmp_path):
    proj = _proj(tmp_path)
    payload = {"tool_name": "Agent", "tool_input": {"subagent_type": "code-reviewer"},
               "tool_response": {"content": [{"type": "text", "text": "ok"}],
                                 "totalTokens": 52_000, "totalToolUseCount": 17,
                                 "totalDurationMs": 81_000}}
    assert _hook("telemetry_append.py", payload, proj).returncode == 0
    row = json.loads((proj / "docs/process/agent-telemetry/HOOK-LOG.jsonl").read_text().splitlines()[-1])
    assert (row["total_tokens"], row["tool_uses"], row["duration_ms"]) == (52_000, 17, 81_000)


def test_usage_xml_block_is_captured():
    blob = "report <usage><subagent_tokens>109522</subagent_tokens><tool_uses>46</tool_uses>" \
           "<duration_ms>217530</duration_ms></usage>"
    assert tele.extract_usage(blob, blob) == {
        "total_tokens": 109522, "tool_uses": 46, "duration_ms": 217530}


def test_missing_usage_stays_null_never_zero():
    assert tele.extract_usage({"content": "x"}, '{"content": "x"}') == {
        "total_tokens": None, "tool_uses": None, "duration_ms": None}


# --- aggregator --------------------------------------------------------------

def test_combined_phase_label_covers_each_phase():
    cycle = {"runs": [{"agent": "po-analyst", "phase": "1+2+2.5", "total_tokens": 300_000,
                       "tool_uses": 40, "duration_ms": 1}]}
    debts = agg.compute_telemetry_debt(cycle, ["1", "2", "2.5"])
    assert not [d for d in debts if "no telemetry entry" in d]


def test_orchestrator_entry_or_marker_covers_any_phase():
    cycle = {"runs": [{"agent": "orchestrator", "phase": "6.5", "total_tokens": 0}]}
    assert not agg.compute_telemetry_debt(cycle, ["6.5"])
    assert not agg.compute_telemetry_debt({"runs": []}, ["6.6-orchestrator", "user-validation"])
    assert agg.compute_telemetry_debt({"runs": []}, ["6.5"])  # unmarked: still a debt


def test_non_numeric_values_are_a_debt_not_a_crash(tmp_path):
    cycle = {"req_name": "REQ-x", "runs": [
        {"agent": "backend-developer", "phase": "4a", "total_tokens": "unknown",
         "tool_uses": "unknown", "duration_ms": "n/a"}]}
    debts = agg.compute_telemetry_debt(cycle, None)
    assert any("non-numeric total_tokens" in d for d in debts)
    out = agg.render_dashboard([cycle])  # must not raise ValueError
    assert "backend-developer" in out


def test_budget_ok_is_computed_and_mismatches_flagged_both_ways():
    cycle = {"req_name": "REQ-x", "runs": [
        # over the Phase-3 cap (150K) but typed true
        {"agent": "architect-reviewer", "phase": "3", "total_tokens": 170_000,
         "tool_uses": 10, "duration_ms": 1, "budget_ok": True},
        # under the Phase-4a cap (400K) but typed false
        {"agent": "backend-developer", "phase": "4a", "total_tokens": 170_000,
         "tool_uses": 10, "duration_ms": 1, "budget_ok": False},
        # L-size story: 500K is within 1.5 x 400K
        {"agent": "backend-developer", "phase": "4a", "size": "L", "total_tokens": 500_000,
         "tool_uses": 10, "duration_ms": 1, "budget_ok": True},
    ]}
    out = agg.render_dashboard([cycle])
    assert "recorded True / computed False" in out
    assert "recorded False / computed True" in out
    assert out.count("/ computed") == 2


def test_combined_variant_cap_is_the_sum_of_its_phases():
    assert agg.cap_for_run({"phase": "1+2+2.5"}, "po-analyst") == 530_000
    assert agg.cap_for_run({"phase": "3", "variant": "3+probe"}, "architect-reviewer") == 195_000


# --- gate integrity ----------------------------------------------------------

def _gate(cmd: str, proj: Path) -> int:
    return _hook("gate_integrity.py", {"tool_input": {"command": cmd}}, proj).returncode


def test_a_piped_gate_is_still_blocked(tmp_path):
    proj = _proj(tmp_path)
    assert _gate("make test-run | tail -5", proj) == 2
    assert _gate("make test-run 2>&1 | tail", proj) == 2


def test_a_pipe_in_a_later_statement_or_quotes_is_not_the_gate(tmp_path):
    proj = _proj(tmp_path)
    assert _gate("make test-run > /tmp/g.log 2>&1; echo $?; grep FAIL /tmp/g.log | tail", proj) == 0
    assert _gate("make test-run && grep -E 'a|b' out | head", proj) == 0
    assert _gate("make test-run -k 'x|y' > f", proj) == 0
    assert _gate("make test-run > f\ngrep x f | wc -l", proj) == 0


def test_placeholder_gate_values_are_not_gates(tmp_path):
    proj = _proj(tmp_path)  # lint_cmd: "TODO"
    assert _gate("echo TODO | cat", proj) == 0
    assert gate.is_placeholder_gate("TBD") and gate.is_placeholder_gate("<cmd>")
    assert not gate.is_placeholder_gate("ruff check .")


# --- cycle archive -----------------------------------------------------------

def _retro_proj(tmp_path: Path, req: str, text: str) -> Path:
    proj = tmp_path / "app"
    d = proj / "docs" / "process" / "agent-retrospectives"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"RETRO-{req}.md").write_text(text, encoding="utf-8")
    return proj


def test_a_corrected_retro_is_re_archived(tmp_path):
    req = "REQ-20261101-demo"
    vault = tmp_path / "vault"
    proj = _retro_proj(tmp_path, req, "# R\n\n## Confidence: MEDIUM\n")
    kc.archive_cycles(proj, vault, "demo", "main", "docs/process", False)
    _retro_proj(tmp_path, req, "# R corrected\n\n## Confidence: HIGH\n")
    rows = kc.archive_cycles(proj, vault, "demo", "main", "docs/process", False)
    assert rows[0]["status"] == "updated"
    dest = kc.cycles_dir(vault, "demo") / req
    assert "corrected" in (dest / f"RETRO-{req}.md").read_text()
    assert 'verdict: "HIGH"' in (dest / "meta.yaml").read_text()
    rows = kc.archive_cycles(proj, vault, "demo", "main", "docs/process", False)
    assert rows[0]["status"] == "skip"  # unchanged now


# --- project instruments -----------------------------------------------------

def test_project_rules_and_untracked_scripts_are_snapshotted_and_missing_ones_reported(tmp_path):
    proj = tmp_path / "app"
    (proj / ".claude" / "rules").mkdir(parents=True)
    (proj / ".claude" / "rules" / "19-evidence.md").write_text("framework", encoding="utf-8")
    (proj / ".claude" / "rules" / "30-team.md").write_text("team rule", encoding="utf-8")
    (proj / "scripts").mkdir()
    (proj / "scripts" / "scope-fence.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    vault = tmp_path / "vault"
    counts = kc.snapshot_instruments(proj, vault, "app")
    assert counts == {"rules": 1, "scripts": 1}  # framework rule excluded
    base = kc.project_dir(vault, "app")
    assert (base / "rules" / "30-team.md").is_file()
    assert not (base / "rules" / "19-evidence.md").exists()
    (proj / "scripts" / "scope-fence.sh").unlink()
    assert kc.missing_instruments(proj, vault, "app") == {"rules": [], "scripts": ["scope-fence.sh"]}


def _doctor_store(tmp_path: Path):
    store = tmp_path / "vault"
    (store / "projects").mkdir(parents=True)
    shutil.copy2(VAULT / "SUITE-VERSION", store / "SUITE-VERSION")
    shutil.copytree(VAULT / "agents", store / "agents")
    proj = tmp_path / "app"
    (proj / ".claude" / "agents").mkdir(parents=True)
    (proj / ".claude" / "project").mkdir(parents=True)
    (proj / ".claude" / "project" / "glossary.md").write_text("# g\n", encoding="utf-8")
    shutil.copy2(store / "agents" / "code-reviewer.md", proj / ".claude" / "agents")
    (proj / "kuraka.config.yaml").write_text(
        "schema_version: 1\nproject:\n  name: app\nstack:\n  backend:\n"
        "    test_cmd: \"TODO\"\n    lint_cmd: \"\"   # none\n", encoding="utf-8")
    kc.write_mount_manifest(proj, store, ("agents",), platform="claude")
    d = store / "projects" / "app"
    d.mkdir(parents=True)
    (d / "registry.md").write_text(f"---\nname: app\npath: {proj}\n---\n", encoding="utf-8")
    return store, proj


def _doctor(store: Path, proj: Path, *extra: str):
    return subprocess.run([sys.executable, str(VAULT / "kuraka-doctor.py"), str(proj),
                           "--vault", str(store), *extra], capture_output=True, text=True)


def test_doctor_flags_placeholder_gates_but_not_declared_empty(tmp_path):
    store, proj = _doctor_store(tmp_path)
    r = _doctor(store, proj)
    assert "[gates]" in r.stdout and "test_cmd=TODO" in r.stdout
    assert "lint_cmd" not in r.stdout


def test_doctor_flags_an_all_null_hook_log(tmp_path):
    store, proj = _doctor_store(tmp_path)
    td = proj / "docs" / "process" / "agent-telemetry"
    td.mkdir(parents=True)
    (td / "HOOK-LOG.jsonl").write_text(
        "\n".join(json.dumps({"agent": "x", "total_tokens": None}) for _ in range(4)) + "\n")
    assert "total_tokens null" in _doctor(store, proj).stdout


def test_doctor_restores_lost_scripts_but_never_resurrects_rules(tmp_path):
    store, proj = _doctor_store(tmp_path)
    base = kc.project_dir(store, "app")
    (base / "scripts").mkdir(parents=True)
    (base / "scripts" / "cardinality-gate.sh").write_text("#!/bin/sh\n", encoding="utf-8")
    (base / "rules").mkdir(parents=True)
    (base / "rules" / "30-team.md").write_text("r", encoding="utf-8")
    r = _doctor(store, proj)
    assert "cardinality-gate.sh" in r.stdout and "30-team.md" in r.stdout
    _doctor(store, proj, "--fix")
    assert (proj / "scripts" / "cardinality-gate.sh").is_file()
    assert not (proj / ".claude" / "rules" / "30-team.md").exists()
